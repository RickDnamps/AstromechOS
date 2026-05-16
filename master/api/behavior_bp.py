# ============================================================
#   █████╗  ██████╗ ███████╗
#  ██╔══██╗██╔═══██╗██╔════╝
#  ███████║██║   ██║███████╗
#  ██╔══██║██║   ██║╚════██║
#  ██║  ██║╚██████╔╝███████║
#  ╚═╝  ╚═╝ ╚═════╝ ╚══════╝
#
#  AstromechOS — Open control platform for astromech builders
# ============================================================
#  Copyright (C) 2026 RickDnamps
#  https://github.com/RickDnamps/AstromechOS
#
#  This file is part of AstromechOS.
#
#  AstromechOS is free software: you can redistribute it
#  and/or modify it under the terms of the GNU General
#  Public License as published by the Free Software
#  Foundation, either version 2 of the License, or
#  (at your option) any later version.
#
#  AstromechOS is distributed in the hope that it will be
#  useful, but WITHOUT ANY WARRANTY; without even the
#  implied warranty of MERCHANTABILITY or FITNESS FOR A
#  PARTICULAR PURPOSE. See the GNU General Public License
#  for more details.
# ============================================================
"""
Blueprint API Behavior — BehaviorEngine REST endpoints.

Endpoints:
  POST /behavior/alive    {"enabled": true|false}
  GET  /behavior/status   → {alive_enabled, startup_enabled, idle_mode, ...}
  POST /behavior/config   → save full behavior config to local.cfg
"""

import logging
import os
import time
import configparser
from flask import Blueprint, request, jsonify
from master.api._admin_auth import require_admin
import master.registry as reg
from master.config.config_loader import write_cfg_atomic
# B-48 (audit 2026-05-15): share settings_bp's write lock so concurrent
# saves of /behavior/config and /settings/config can't lose data via
# RMW interleave on local.cfg.
from master.api.settings_bp import _cfg_write_lock

log = logging.getLogger(__name__)

behavior_bp = Blueprint('behavior', __name__, url_prefix='/behavior')

_CFG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'local.cfg')

# B-69 / B-70 (audit 2026-05-15): validate every choreo name persisted
# to local.cfg against the on-disk choreographies directory. Otherwise
# a malicious POST could store '../../etc/passwd' or any arbitrary
# string, and the BehaviorEngine later tries to load it.
_CHOREO_DIR = os.path.join(os.path.dirname(__file__), '..', 'choreographies')
import re as _re
# Audit finding M-6 2026-05-15: the previous regex allowed leading-
# dot files (.hidden.chor) and weird multi-dot names. on_disk check
# already blocks the worst, but tighten anyway: first char alphanum,
# 64-char cap, no leading dots.
_CHOREO_NAME_RE = _re.compile(r'^[A-Za-z0-9][A-Za-z0-9_\- ]{0,63}$')


def _strip_chor_ext(name: str) -> str:
    """Strip a trailing '.chor' so cfg values that historically shipped
    with the extension still validate. Audit finding CR-6 2026-05-15:
    local.cfg.example shipped 'startup.chor' but the frontend select
    uses bare names, so save would reject the shipped defaults."""
    if isinstance(name, str) and name.endswith('.chor'):
        return name[:-5]
    return name


def _valid_choreo_name(name: str) -> bool:
    """True if `name` is a syntactically valid choreo name AND a matching
    .chor file exists in the choreo directory. Tolerates a trailing
    '.chor' extension for backward-compat with shipped configs."""
    name = _strip_chor_ext(name)
    if not name or not _CHOREO_NAME_RE.match(name):
        return False
    return os.path.isfile(os.path.join(_CHOREO_DIR, name + '.chor'))


# ─── Cascade helpers (audit CR-7 2026-05-15) ─────────────────────
# Called by choreo_bp on choreo rename/delete so behavior config
# stays consistent. Without this, renaming patrol.chor would silently
# break the operator's idle rotation — engine logs "ALIVE choreo
# not found" and skips that pass forever.

def _rewrite_behavior_choreo(transform) -> int:
    """Apply `transform(name) -> new_name_or_None` to startup_choreo
    and every entry in idle_choreo_list. None drops the entry.
    Returns the number of values changed."""
    import logging as _logging
    _log = _logging.getLogger(__name__)
    changed = 0
    with _cfg_write_lock:
        parser = _get_cfg()
        if not parser.has_section('behavior'):
            return 0
        # startup_choreo
        cur = _strip_chor_ext(parser.get('behavior', 'startup_choreo', fallback=''))
        if cur:
            new = transform(cur)
            if new is None:
                parser.set('behavior', 'startup_choreo', '')
                parser.set('behavior', 'startup_enabled', 'false')
                changed += 1
            elif new != cur:
                parser.set('behavior', 'startup_choreo', new)
                changed += 1
        # idle_choreo_list
        raw = parser.get('behavior', 'idle_choreo_list', fallback='')
        if raw:
            items = []
            list_changed = False
            for c in raw.split(','):
                c = _strip_chor_ext(c.strip())
                if not c:
                    continue
                new = transform(c)
                if new is None:
                    list_changed = True
                    continue
                if new != c:
                    list_changed = True
                items.append(new)
            if list_changed:
                parser.set('behavior', 'idle_choreo_list', ','.join(items))
                changed += 1
        if changed:
            write_cfg_atomic(parser, _CFG_PATH)
            # Invalidate the mtime cache so the next read picks up the change
            _BEHAVIOR_CFG_CACHE['mtime'] = 0.0
            # B7 fix 2026-05-16: ALSO refresh the BehaviorEngine's
            # private self._cfg snapshot. Previously the engine kept
            # reading stale old_target from its in-memory parser; on
            # next idle trigger, os.path.isfile() failed → skipped
            # silently. Now in sync.
            try:
                import master.registry as _r
                if getattr(_r, 'behavior_engine', None) is not None:
                    fresh = configparser.ConfigParser()
                    fresh.read(_CFG_PATH)
                    _r.behavior_engine._cfg = fresh
            except Exception:
                _log.exception("behavior_bp cascade: failed to refresh engine cfg snapshot")
            _log.info("behavior_bp cascade: %d values rewritten", changed)
    return changed


def cascade_rename(action_type: str, old_target: str, new_target: str) -> int:
    """Update behavior config when a choreo is renamed."""
    if action_type != 'play_choreo':
        return 0
    return _rewrite_behavior_choreo(
        lambda n: new_target if n == old_target else n
    )


def cascade_delete(action_type: str, target: str) -> int:
    """Drop deleted choreo from startup + idle list."""
    if action_type != 'play_choreo':
        return 0
    return _rewrite_behavior_choreo(
        lambda n: None if n == target else n
    )


def _get_cfg() -> configparser.ConfigParser:
    """Read the current local.cfg. B-217 (remaining tabs audit
    2026-05-15): mtime-keyed cache. /behavior/status is hit on every
    Settings tab open + frequent polls; re-parsing the file on each
    call was unnecessary I/O."""
    try:
        mt = os.path.getmtime(_CFG_PATH)
    except OSError:
        mt = 0.0
    cached = _BEHAVIOR_CFG_CACHE['cfg']
    if cached is not None and _BEHAVIOR_CFG_CACHE['mtime'] == mt:
        return cached
    parser = configparser.ConfigParser()
    parser.read(_CFG_PATH)
    _BEHAVIOR_CFG_CACHE['cfg']   = parser
    _BEHAVIOR_CFG_CACHE['mtime'] = mt
    return parser


_BEHAVIOR_CFG_CACHE: dict = {'mtime': 0.0, 'cfg': None}


@behavior_bp.post('/alive')
@require_admin
def set_alive():
    """Toggle ALIVE mode on or off."""
    data = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    enabled = bool(data.get('enabled', False))
    be = reg.behavior_engine
    if be is None:
        return jsonify({'ok': False, 'error': 'BehaviorEngine not initialized'}), 503
    be.set_alive(enabled)
    return jsonify({'ok': True, 'alive_enabled': enabled})


@behavior_bp.post('/test_trigger')
@require_admin
def test_trigger():
    """W1 fix 2026-05-16: fire the idle reaction NOW, bypassing the
    timeout gate but still respecting E-STOP/stow/lock_mode. Operator
    uses this to preview ALIVE behavior without waiting N minutes.
    Returns which mode was dispatched."""
    be = reg.behavior_engine
    if be is None:
        return jsonify({'ok': False, 'error': 'BehaviorEngine not initialized'}), 503
    # Respect safety chain — never bypass these
    if be._is_safety_locked():
        return jsonify({'ok': False, 'error': 'safety chain engaged (E-STOP/stow/lock)'}), 503
    mode = be._cfg.get('behavior', 'idle_mode', fallback='choreo')
    try:
        if mode == 'sounds':
            be._trigger_sounds()
        elif mode == 'sounds_lights':
            be._trigger_sounds()
            be._trigger_lights()
        elif mode == 'lights':
            be._trigger_lights()
        elif mode == 'choreo':
            be._trigger_choreo()
        else:
            return jsonify({'ok': False, 'error': f'unknown idle_mode: {mode}'}), 400
    except Exception as e:
        log.exception("test_trigger failed")
        return jsonify({'ok': False, 'error': str(e)}), 500
    be._last_idle_trigger = time.monotonic()
    return jsonify({'ok': True, 'mode_fired': mode})


@behavior_bp.post('/test_startup')
@require_admin
def test_startup():
    """W2 fix 2026-05-16: fire the startup choreo NOW (skipping the
    boot delay) so operator can preview without rebooting Master.
    Still respects safety chain via safe_play."""
    be = reg.behavior_engine
    if be is None:
        return jsonify({'ok': False, 'error': 'BehaviorEngine not initialized'}), 503
    choreo_name = be._cfg.get('behavior', 'startup_choreo', fallback='startup')
    if choreo_name.endswith('.chor'):
        choreo_name = choreo_name[:-5]
    choreo_path = os.path.join(be._choreo_dir, choreo_name + '.chor')
    if not os.path.isfile(choreo_path):
        return jsonify({'ok': False, 'error': f'startup choreo not found: {choreo_name}'}), 404
    chor = be._load_choreo(choreo_path)
    if not chor:
        return jsonify({'ok': False, 'error': 'failed to load startup choreo'}), 500
    from master.api.choreo_bp import safe_play
    ok = safe_play(chor, log_label='behavior:test_startup')
    return jsonify({'ok': bool(ok), 'choreo': choreo_name})


@behavior_bp.get('/status')
def get_status():
    """Current behavior engine state."""
    cfg = _get_cfg()
    now = time.monotonic()
    last = reg.last_activity
    ago = round(now - last, 1) if last > 0 else None
    # WOW polish H4 2026-05-15: compute time-until-next-idle-trigger
    # so the Behavior panel can show 'Next idle reaction in 9:58'
    # countdown. Operator sees the system is armed and how long
    # before the next thing happens. None when alive disabled.
    alive_enabled = cfg.getboolean('behavior', 'alive_enabled', fallback=False)
    idle_timeout_min = cfg.getfloat('behavior', 'idle_timeout_min', fallback=10.0)
    next_idle_s = None
    if alive_enabled and last > 0:
        idle_at = last + (idle_timeout_min * 60.0)
        next_idle_s = max(0, round(idle_at - now, 1))
    # B16 fix 2026-05-16: surface whether the active idle_mode has its
    # dependency ready (audio/teeces driver actually available). Was:
    # silent no-op infinite loop if driver degraded.
    cur_mode = cfg.get('behavior', 'idle_mode', fallback='choreo')
    idle_mode_ready = True
    idle_mode_reason = ''
    if cur_mode in ('sounds', 'sounds_lights') and not reg.uart:
        idle_mode_ready = False
        idle_mode_reason = 'UART not available (Slave audio unreachable)'
    if cur_mode in ('lights', 'sounds_lights'):
        teeces_ok = bool(reg.teeces and reg.teeces.is_ready())
        if not teeces_ok:
            idle_mode_ready = False
            idle_mode_reason = (idle_mode_reason + '; ' if idle_mode_reason else '') + 'lights driver not ready'
    # W7 fix 2026-05-16: surface last-fired idle choreo so frontend can
    # show a green-dot marker on the matching pill (parité Audio/Sequences)
    be = reg.behavior_engine
    last_choreo = getattr(be, '_last_choreo_name', '') if be else ''
    last_choreo_ts = getattr(be, '_last_choreo_ts', 0.0) if be else 0.0
    last_choreo_ago = round(now - last_choreo_ts, 1) if last_choreo_ts > 0 else None
    return jsonify({
        'alive_enabled':       alive_enabled,
        'last_idle_choreo':    last_choreo,
        'last_idle_choreo_ago_s': last_choreo_ago,
        'startup_enabled':     cfg.getboolean('behavior', 'startup_enabled',     fallback=False),
        'startup_delay':       cfg.getfloat  ('behavior', 'startup_delay',       fallback=5.0),
        'startup_choreo':      cfg.get       ('behavior', 'startup_choreo',      fallback='startup.chor'),
        'idle_mode':           cur_mode,
        'idle_mode_ready':     idle_mode_ready,
        'idle_mode_reason':    idle_mode_reason,
        'idle_timeout_min':    idle_timeout_min,
        'idle_audio_category': cfg.get       ('behavior', 'idle_audio_category', fallback='happy'),
        'idle_choreo_list':    [c.strip() for c in cfg.get('behavior', 'idle_choreo_list', fallback='').split(',') if c.strip()],
        'dome_auto_on_alive':  cfg.getboolean('behavior', 'dome_auto_on_alive',  fallback=True),
        'last_activity_ago_s': ago,
        'next_idle_in_s':      next_idle_s,
    })


@behavior_bp.post('/config')
@require_admin
def save_config():
    """Save full behavior configuration to local.cfg.

    B-48 (audit 2026-05-15): the entire read-modify-write cycle runs
    under settings_bp._cfg_write_lock so a concurrent /settings/config
    POST can't load the same baseline, mutate independently, and lose
    one side's keys at the os.replace step.
    """
    data = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    with _cfg_write_lock:
        parser = _get_cfg()
        if not parser.has_section('behavior'):
            parser.add_section('behavior')

        def _set(key, value):
            parser.set('behavior', key, str(value))

        # B-215 / B-216 / B-218 (remaining tabs audit 2026-05-15):
        # value validation per key — clamps + allowlists. Catches
        # non-numeric, out-of-range, and unknown enums BEFORE persist
        # so BehaviorEngine never reads junk back.
        _VALID_IDLE_MODES = {'sounds', 'sounds_lights', 'lights', 'choreo'}

        def _safe_int_clamp(field, raw, lo, hi):
            try:
                return max(lo, min(hi, int(raw)))
            except (TypeError, ValueError):
                raise ValueError(f"{field} must be an integer ({lo}..{hi})")

        if 'startup_enabled'     in data: _set('startup_enabled',     'true' if data['startup_enabled'] else 'false')
        if 'startup_delay'       in data:
            try:
                _set('startup_delay', str(_safe_int_clamp('startup_delay', data['startup_delay'], 0, 300)))
            except ValueError as e:
                return jsonify({'ok': False, 'error': str(e)}), 400
        if 'startup_choreo'      in data:
            # B-69: validate against on-disk choreographies before
            # persisting; empty string means "no startup choreo".
            name = str(data['startup_choreo']).strip()
            if name and not _valid_choreo_name(name):
                return jsonify({'ok': False, 'error': f'unknown choreo: {name}'}), 400
            _set('startup_choreo', name)
        if 'alive_enabled'       in data: _set('alive_enabled',       'true' if data['alive_enabled'] else 'false')
        if 'idle_timeout_min'    in data:
            try:
                _set('idle_timeout_min', str(_safe_int_clamp('idle_timeout_min', data['idle_timeout_min'], 1, 1440)))
            except ValueError as e:
                return jsonify({'ok': False, 'error': str(e)}), 400
        if 'idle_mode'           in data:
            mode = str(data['idle_mode']).strip().lower()
            if mode not in _VALID_IDLE_MODES:
                return jsonify({'ok': False, 'error': f'idle_mode must be one of {sorted(_VALID_IDLE_MODES)}'}), 400
            _set('idle_mode', mode)
        if 'idle_audio_category' in data:
            # Validate against actual audio categories on disk
            cat = str(data['idle_audio_category']).strip().lower()
            try:
                from master.api.audio_bp import _get_index
                valid_cats = set(_get_index().get('categories', {}).keys())
            except Exception:
                valid_cats = set()   # can't validate — accept anything
            if valid_cats and cat and cat not in valid_cats:
                return jsonify({'ok': False, 'error': f'unknown audio category: {cat}'}), 400
            _set('idle_audio_category', cat)
        if 'idle_choreo_list'    in data:
            # B-70: same validation per entry — drop unknown names with
            # a 400 instead of letting BehaviorEngine try a path that
            # doesn't exist. Empty list is allowed.
            raw = data['idle_choreo_list']
            items = raw if isinstance(raw, list) else [s for s in str(raw).split(',')]
            items = [str(n).strip() for n in items if str(n).strip()]
            for n in items:
                if not _valid_choreo_name(n):
                    return jsonify({'ok': False, 'error': f'unknown choreo: {n}'}), 400
            _set('idle_choreo_list', ','.join(items))
        if 'dome_auto_on_alive'  in data: _set('dome_auto_on_alive',  'true' if data['dome_auto_on_alive'] else 'false')

        # E22 fix 2026-05-16: refuse dome_auto + idle_mode=choreo combo
        # backend-side too (frontend disables the checkbox but SSH/curl
        # bypasses). When choreo mode owns dome via tracks, ALIVE's
        # random rotation would race the choreo's dome commands →
        # motor jitter.
        final_mode = parser.get('behavior', 'idle_mode', fallback='choreo')
        final_dome_auto = parser.getboolean('behavior', 'dome_auto_on_alive', fallback=True)
        if final_mode == 'choreo' and final_dome_auto:
            return jsonify({
                'ok': False,
                'error': 'dome_auto_on_alive cannot be true when idle_mode is choreo (choreos may own dome)',
            }), 400

        # E12 fix 2026-05-16: if cascade or save leaves idle_choreo_list
        # empty AND idle_mode is choreo, the engine would log spam every
        # 30s ('idle_choreo_list is empty'). Demote to 'sounds' so the
        # operator gets predictable behavior instead of silent failure.
        if final_mode == 'choreo':
            final_list = parser.get('behavior', 'idle_choreo_list', fallback='').strip()
            if not final_list:
                parser.set('behavior', 'idle_mode', 'sounds')
                log.warning("save_config: idle_mode=choreo with empty list — demoted to 'sounds'")

        try:
            cfg_path = os.path.normpath(_CFG_PATH)
            write_cfg_atomic(parser, cfg_path)
            # E4 fix 2026-05-16: invalidate the GET cache so /behavior/
            # status reflects the save immediately, regardless of
            # filesystem mtime granularity.
            _BEHAVIOR_CFG_CACHE['mtime'] = 0.0
            # B-236 / B-237 (remaining tabs audit 2026-05-15): snapshot-
            # on-write. Mutating the engine's existing parser via
            # `.read(path)` while _tick reads from it could see torn
            # state (configparser internal dicts are not atomically
            # mutated). Atomic ref assignment of a NEW parser is
            # GIL-safe; the engine's next read sees either old or new
            # whole.
            be = reg.behavior_engine
            if be:
                fresh = configparser.ConfigParser()
                fresh.read(cfg_path)
                be._cfg = fresh
            log.info("Behavior config saved")
            return jsonify({'ok': True})
        except Exception as e:
            log.exception("Failed to save behavior config")
            return jsonify({'ok': False, 'error': str(e)}), 500
