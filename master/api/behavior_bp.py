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
_CHOREO_NAME_RE = _re.compile(r'^[A-Za-z0-9_.\- ]+$')


def _valid_choreo_name(name: str) -> bool:
    """True if `name` is a syntactically valid choreo name AND a matching
    .chor file exists in the choreo directory."""
    if not name or not _CHOREO_NAME_RE.match(name):
        return False
    return os.path.isfile(os.path.join(_CHOREO_DIR, name + '.chor'))


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
    data = request.get_json(silent=True) or {}
    enabled = bool(data.get('enabled', False))
    be = reg.behavior_engine
    if be is None:
        return jsonify({'ok': False, 'error': 'BehaviorEngine not initialized'}), 503
    be.set_alive(enabled)
    return jsonify({'ok': True, 'alive_enabled': enabled})


@behavior_bp.get('/status')
def get_status():
    """Current behavior engine state."""
    cfg = _get_cfg()
    now = time.monotonic()
    last = reg.last_activity
    ago = round(now - last, 1) if last > 0 else None
    return jsonify({
        'alive_enabled':       cfg.getboolean('behavior', 'alive_enabled',       fallback=False),
        'startup_enabled':     cfg.getboolean('behavior', 'startup_enabled',     fallback=False),
        'startup_delay':       cfg.getfloat  ('behavior', 'startup_delay',       fallback=5.0),
        'startup_choreo':      cfg.get       ('behavior', 'startup_choreo',      fallback='startup.chor'),
        'idle_mode':           cfg.get       ('behavior', 'idle_mode',           fallback='choreo'),
        'idle_timeout_min':    cfg.getfloat  ('behavior', 'idle_timeout_min',    fallback=10.0),
        'idle_audio_category': cfg.get       ('behavior', 'idle_audio_category', fallback='happy'),
        'idle_choreo_list':    [c.strip() for c in cfg.get('behavior', 'idle_choreo_list', fallback='').split(',') if c.strip()],
        'dome_auto_on_alive':  cfg.getboolean('behavior', 'dome_auto_on_alive',  fallback=True),
        'last_activity_ago_s': ago,
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
    data = request.get_json(silent=True) or {}
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

        try:
            cfg_path = os.path.normpath(_CFG_PATH)
            write_cfg_atomic(parser, cfg_path)
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
