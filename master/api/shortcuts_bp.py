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
#  Licensed under GPL v2 — see LICENSE.
# ============================================================
"""
Shortcuts blueprint — operator-configurable macro buttons that appear
on the Drive tab.

Each shortcut is a small button that fires a single action (toggle an
arm, play a choreo, play a sound, etc.). The operator configures the
count + label + icon + action target from Settings → Shortcuts; the
Drive tab renders the buttons in two pads, one above each joystick.

Endpoints:
  GET  /shortcuts                 → full list + count
  POST /shortcuts            (admin) save the full list (replaces)
  POST /shortcuts/<id>/trigger    → execute the action; returns
                                    {state: 'on'|'off'|'fired'}
                                    so the frontend can update the
                                    indicator dot.

Persistence: master/config/shortcuts.json, atomic write tmp+rename+
fsync+chmod 0o600 via _atomic_write_json (same pattern as choreo
write_cfg_atomic from the audit hardening).

Action types (v1):
  arms_toggle         target = "1".."6" (arm slot)
  body_panel_toggle   target = "Servo_S0".."Servo_S31"
  dome_panel_toggle   target = "Servo_M0".."Servo_M31"
  play_choreo         target = ".chor" name (no extension)
  play_sound          target = sound stem
  play_random_audio   target = category name
  none                (placeholder — does nothing, no flash)

Toggle state is tracked in `reg.shortcut_states` (in-memory dict) and
also mirrored in shortcuts.json so it survives a Master restart. A
shortcut whose underlying servo is moved by choreo/manual UI will
drift; the next click will reconcile (the toggle opens whatever's
closed and closes whatever's open via _is_extended() check).

Threat model: GET + POST trigger are LAN-public (same as the Drive
tab joystick endpoints — operator-tier, not admin). POST /shortcuts
(save config) is admin-only since it can change what every button
does. Action targets validated against on-disk reality (choreo file
exists, sound file exists, arm# in arms_cfg) before dispatch.
"""
from __future__ import annotations

import json
import logging
import os
import re
import secrets
import threading
import time
from pathlib import Path

from flask import Blueprint, request, jsonify

import master.registry as reg
from master.api._admin_auth import require_admin

log = logging.getLogger(__name__)

shortcuts_bp = Blueprint('shortcuts', __name__)

_SHORTCUTS_FILE = os.path.join(
    os.path.dirname(__file__), '..', 'config', 'shortcuts.json',
)
_SHORTCUTS_LOCK = threading.Lock()

# B5/P2 fix 2026-05-16: per-shortcut trigger lock + debounce.
# Was: double-tap on arms_toggle / panel_toggle spawned 2 daemon
# threads racing same servo (UART duplication + PCA9685 race).
# 150ms debounce per-sid blocks rapid re-trigger; the lock
# serializes legitimate sequential presses.
_TRIGGER_LOCKS: dict[str, threading.Lock] = {}
_TRIGGER_LOCKS_GUARD = threading.Lock()
_LAST_TRIGGER_TS: dict[str, float] = {}
_TRIGGER_DEBOUNCE_S = 0.15


def _per_sid_lock(sid: str) -> threading.Lock:
    with _TRIGGER_LOCKS_GUARD:
        lk = _TRIGGER_LOCKS.get(sid)
        if lk is None:
            lk = threading.Lock()
            _TRIGGER_LOCKS[sid] = lk
        return lk


# B2/B3/B4 fix 2026-05-16: explicit exceptions for trigger failures.
# Lets the endpoint surface a precise toast vs silent 'off'/'fired'.
class _ShortcutBusy(Exception):
    """Raised when the action conflicts with another in-flight one."""
class _ShortcutRefused(Exception):
    """Raised when a hardware/safety condition refuses the trigger."""

# Cap to avoid pathological configs flooding the Drive tab.
_MAX_SHORTCUTS = 12

# Allowed action types — adding here must be paired with a handler in
# _ACTIONS below (server-side dispatch).
_ACTION_TYPES = {
    'none',
    'arms_toggle',
    'body_panel_toggle',
    'dome_panel_toggle',
    'play_choreo',
    'play_sound',
    'play_random_audio',
    'play_animation',   # W16 fix 2026-05-16 — bind Imperial March etc. to Drive shortcut
}

# Limits picked to match other UX caps already in the project (servo
# label 40, category id 32). Icons cap = 8 because one emoji glyph
# can be up to ~10 codepoints (ZWJ + skin tone) but we restrict to
# typical single-glyph operator picks; if they need more they can
# paste anyway and we'll truncate.
_LABEL_MAX  = 32
_ICON_MAX   = 8


# ─────────────────────────────────────────────────────────────────────
# Persistence helpers
# ─────────────────────────────────────────────────────────────────────

def _default_state() -> dict:
    return {'count': 0, 'shortcuts': []}


def _read_shortcuts() -> dict:
    """Read shortcuts.json. Returns the default empty state if the file
    is missing or unreadable — never raises."""
    if not os.path.exists(_SHORTCUTS_FILE):
        return _default_state()
    try:
        with open(_SHORTCUTS_FILE, encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict) or 'shortcuts' not in data:
            return _default_state()
        return data
    except (OSError, json.JSONDecodeError) as e:
        log.warning("shortcuts.json unreadable (%s) — using defaults", e)
        return _default_state()


def _atomic_write_json(path: str, data: dict) -> None:
    """tmp + os.replace + fsync + chmod 0o600 — same pattern as
    write_cfg_atomic in master/config/config_loader.py.

    User-reported 2026-05-16: rotate 3 .bak generations BEFORE write
    so an unintended mutation can be recovered via SSH (cp shortcuts
    .json.bak1 shortcuts.json + restart)."""
    from master.config.config_loader import rotate_backup as _rotate
    os.makedirs(os.path.dirname(path), exist_ok=True)
    _rotate(path)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.flush()
        try:
            os.fsync(f.fileno())
        except OSError:
            pass
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


# ─────────────────────────────────────────────────────────────────────
# Validation
# ─────────────────────────────────────────────────────────────────────

def _sanitize_label(raw) -> str:
    s = str(raw or '').strip()[:_LABEL_MAX]
    # Strip control chars defence-in-depth (same family of writes that
    # ended up in local.cfg in the Settings audit).
    return ''.join(c for c in s if c >= ' ' and c not in '\n\r\x00\x7f')


def _sanitize_icon(raw) -> str:
    return str(raw or '').strip()[:_ICON_MAX]


def _validate_action(action_type: str, target) -> tuple[bool, str]:
    """Return (ok, error_message). target is type-dependent."""
    if action_type not in _ACTION_TYPES:
        return False, f'unknown action type: {action_type}'
    if action_type == 'none':
        return True, ''
    t = str(target or '').strip()
    if not t:
        return False, f'{action_type} requires a target'

    if action_type == 'arms_toggle':
        try:
            arm_n = int(t)
        except ValueError:
            return False, 'arms_toggle target must be an integer arm slot'
        from master.api.servo_bp import _read_arms_cfg
        arms = _read_arms_cfg()
        if arm_n < 1 or arm_n > arms.get('count', 0):
            return False, f'arm {arm_n} out of range (1..{arms.get("count", 0)})'
        return True, ''

    if action_type in ('body_panel_toggle', 'dome_panel_toggle'):
        from master.api.servo_bp import BODY_SERVOS, DOME_SERVOS
        valid = BODY_SERVOS if action_type == 'body_panel_toggle' else DOME_SERVOS
        if t not in valid:
            return False, f'unknown panel: {t}'
        return True, ''

    if action_type == 'play_choreo':
        # Same regex as choreo_bp._CHOREO_NAME_RE + on-disk check.
        import re
        if not re.match(r'^[A-Za-z0-9_.\- ]+$', t):
            return False, 'invalid choreo name'
        choreo_dir = os.path.join(os.path.dirname(__file__), '..', 'choreographies')
        if not os.path.isfile(os.path.join(choreo_dir, t + '.chor')):
            return False, f'choreo not found: {t}'
        return True, ''

    if action_type == 'play_sound':
        # Defer to audio_bp's existing safe sound resolver.
        from master.api.audio_bp import _safe_sound_path
        if _safe_sound_path(t) is None:
            return False, f'sound not found: {t}'
        return True, ''

    if action_type == 'play_random_audio':
        # Category must exist in the sound index.
        from master.api.audio_bp import _get_index
        cats = _get_index().get('categories', {})
        if t not in cats:
            return False, f'unknown audio category: {t}'
        if not cats[t]:
            return False, f'category "{t}" has no sounds'
        return True, ''

    if action_type == 'play_animation':
        # W16 fix 2026-05-16: T-code must exist in the canonical
        # ANIMATIONS dict. Target is the integer mode as string.
        try:
            mode_int = int(t)
        except (TypeError, ValueError):
            return False, f'play_animation target must be a numeric T-code, got: {t!r}'
        from master.lights.base_controller import BaseLightsController
        if mode_int not in BaseLightsController.ANIMATIONS:
            return False, f'unknown animation T-code: {mode_int}'
        return True, ''

    return False, f'unhandled action type: {action_type}'


def _normalize_shortcut(raw: dict, idx: int) -> tuple[dict | None, str]:
    """Return (clean_dict, error). The clean dict gets persisted."""
    if not isinstance(raw, dict):
        return None, f'#{idx}: not an object'
    label  = _sanitize_label(raw.get('label', ''))
    icon   = _sanitize_icon(raw.get('icon', ''))
    color  = str(raw.get('color', '') or '').strip()[:9]   # #rrggbbaa
    if color and not (color.startswith('#') and all(c in '0123456789abcdefABCDEF' for c in color[1:])):
        color = ''   # silently drop invalid color, keep the rest
    action = raw.get('action', {}) or {}
    if not isinstance(action, dict):
        return None, f'#{idx}: action must be an object'
    a_type   = str(action.get('type', 'none')).strip()
    a_target = action.get('target', '')
    ok, err = _validate_action(a_type, a_target)
    if not ok:
        return None, f'#{idx}: {err}'
    # ID — preserve if present (so the running state cache survives),
    # else generate a new one.
    sid = raw.get('id') or secrets.token_hex(6)
    return {
        'id':     sid,
        'label':  label,
        'icon':   icon,
        'color':  color,
        'action': {'type': a_type, 'target': str(a_target or '').strip()},
    }, ''


# ─────────────────────────────────────────────────────────────────────
# State (toggle on/off per shortcut)
# ─────────────────────────────────────────────────────────────────────
# In-memory mirror so the trigger endpoint can decide what to do on
# the next click without re-reading shortcuts.json every time.
# Persisted to disk so it survives a Master restart at the right state.
def _state_dict() -> dict:
    if not hasattr(reg, 'shortcut_states') or reg.shortcut_states is None:
        reg.shortcut_states = {}
    return reg.shortcut_states


def _seed_state_from_disk(data: dict) -> None:
    """Load persisted toggle states into reg at module init or after
    a save. Unknown ids fall back to 'off'."""
    saved = data.get('states', {})
    state = _state_dict()
    state.clear()
    for sc in data.get('shortcuts', []):
        sid = sc['id']
        state[sid] = saved.get(sid, 'off')


def _persist_state() -> None:
    """Snapshot reg.shortcut_states back to shortcuts.json."""
    with _SHORTCUTS_LOCK:
        data = _read_shortcuts()
        data['states'] = dict(_state_dict())
        _atomic_write_json(_SHORTCUTS_FILE, data)


# ─────────────────────────────────────────────────────────────────────
# Cascade helpers — other blueprints call these when they rename or
# delete a resource that a shortcut might target (choreo, sound,
# category). Keeps shortcuts.json consistent so the runner doesn't
# fail a trigger on a stale name. User-reported 2026-05-15: 'quand
# j'ai changé le nom d'une choreo le shortcut était cassé ... il
# faut que cela soit blindé'.
# ─────────────────────────────────────────────────────────────────────

def cascade_rename(action_type: str, old_target: str, new_target: str) -> int:
    """Update every shortcut whose action matches (type, old_target)
    to point at new_target. Atomic write under _SHORTCUTS_LOCK.
    Returns the number of shortcuts updated."""
    if not action_type or not old_target or not new_target:
        return 0
    if old_target == new_target:
        return 0
    with _SHORTCUTS_LOCK:
        data = _read_shortcuts()
        changed = 0
        for sc in data.get('shortcuts', []):
            act = sc.get('action') or {}
            if act.get('type') == action_type and act.get('target') == old_target:
                act['target'] = new_target
                sc['action'] = act
                changed += 1
        if changed:
            _atomic_write_json(_SHORTCUTS_FILE, data)
    if changed:
        log.info("Shortcuts cascade rename: %s '%s'→'%s' updated %d entries",
                 action_type, old_target, new_target, changed)
    return changed


def cascade_delete(action_type: str, target: str) -> int:
    """Neutralize every shortcut whose action matches (type, target)
    by switching its action to 'none' (preserves label/icon so the
    operator notices and reconfigures, vs silently dropping the
    button). Returns the number of shortcuts neutralized."""
    if not action_type or not target:
        return 0
    with _SHORTCUTS_LOCK:
        data = _read_shortcuts()
        changed = 0
        for sc in data.get('shortcuts', []):
            act = sc.get('action') or {}
            if act.get('type') == action_type and act.get('target') == target:
                sc['action'] = {'type': 'none', 'target': ''}
                changed += 1
        if changed:
            _atomic_write_json(_SHORTCUTS_FILE, data)
    if changed:
        log.info("Shortcuts cascade delete: %s '%s' neutralized %d entries",
                 action_type, target, changed)
    return changed


# Seed state on module import so a fresh Master boot remembers the
# last persisted on/off per shortcut.
_seed_state_from_disk(_read_shortcuts())


# ─────────────────────────────────────────────────────────────────────
# Action dispatch
# ─────────────────────────────────────────────────────────────────────
# Each handler takes (target_str) and returns the new state string.
# Handlers MAY call internal helpers (preferred) instead of round-
# tripping through HTTP. They MUST honour existing safety chains
# (estop, lock_mode, vesc_safety) — which is automatic when delegating
# to the existing motion / servo / audio entry points.

def _act_arms_toggle(target: str, current: str) -> str:
    arm_n = int(target)
    # Lazy import to avoid circular at module load time.
    from master.api.servo_bp import (
        _read_arms_cfg, _read_panels_cfg,
        _arm_open_sequence, _arm_close_sequence,
    )
    arms = _read_arms_cfg()
    idx = arm_n - 1
    if idx < 0 or idx >= arms.get('count', 0):
        return current
    arm   = arms['servos'][idx]
    panel = arms['panels'][idx]
    delay = arms['delays'][idx]
    if not arm:
        return current
    cfg = _read_panels_cfg()
    new_action = 'close' if current == 'on' else 'open'
    target_fn = _arm_open_sequence if new_action == 'open' else _arm_close_sequence
    threading.Thread(
        target=target_fn,
        args=(arm, panel, delay, cfg),
        daemon=True,
        name=f'shortcut-arm{arm_n}-{new_action}',
    ).start()
    return 'on' if new_action == 'open' else 'off'


def _act_body_panel_toggle(target: str, current: str) -> str:
    if not reg.servo:
        return current
    from master.api.servo_bp import _read_panels_cfg, _panel_angle, _panel_speed
    cfg = _read_panels_cfg()
    if current == 'on':
        a = _panel_angle(target, 'close', cfg); s = _panel_speed(target, cfg)
        reg.servo.close(target, a, s)
        return 'off'
    a = _panel_angle(target, 'open', cfg); s = _panel_speed(target, cfg)
    reg.servo.open(target, a, s)
    return 'on'


def _act_dome_panel_toggle(target: str, current: str) -> str:
    if not reg.dome_servo:
        return current
    from master.api.servo_bp import _read_panels_cfg, _panel_angle, _panel_speed
    cfg = _read_panels_cfg()
    if current == 'on':
        a = _panel_angle(target, 'close', cfg); s = _panel_speed(target, cfg)
        reg.dome_servo.close(target, a, s)
        return 'off'
    a = _panel_angle(target, 'open', cfg); s = _panel_speed(target, cfg)
    reg.dome_servo.open(target, a, s)
    return 'on'


def _act_play_choreo(target: str, current: str) -> str:
    # B3 fix 2026-05-16: distinguish 'another choreo playing' (409
    # conflict) from clean refusal. Was silently 'off' → UI showed
    # no feedback. Now raises to surface a toast.
    if reg.choreo and reg.choreo.is_playing():
        status = reg.choreo.get_status() or {}
        if status.get('name') == target:
            reg.choreo.stop()
            return 'off'
        raise _ShortcutBusy(f"another sequence playing: {status.get('name', '?')}")
    if not reg.choreo:
        return 'off'
    from master.api.choreo_bp import safe_play, _safe_choreo_path
    path, err = _safe_choreo_path(target)
    if err is not None or not path or not os.path.isfile(path):
        return 'off'
    try:
        with open(path, encoding='utf-8') as f:
            chor = json.load(f)
    except (OSError, json.JSONDecodeError):
        return 'off'
    # B2 fix 2026-05-16: was ignoring safe_play() return → false 'fired'
    # green pulse even when the canonical refused (estop, lock,
    # stow). Now propagate the refusal so the runner can toast.
    ok = safe_play(chor, loop=False, log_label=f'shortcut:{target}')
    if not ok:
        raise _ShortcutRefused('sequence refused (safety lock or another playing)')
    return 'fired'


# B4 fix 2026-05-16: audio handlers must hold _audio_state_lock around
# the registry mutation — P4 fix from audio_bp B-10 was re-introduced
# by these handlers writing reg.audio_* directly.
def _act_play_sound(target: str, current: str) -> str:
    # B6 fix 2026-05-16: defense-in-depth path re-validation at trigger
    # time. Was: _safe_sound_path called only at save → tampered
    # shortcuts.json could pass through with newlines/control chars.
    from master.api.audio_bp import (
        _schedule_audio_reset, _get_sound_duration_ms,
        _safe_sound_path, _audio_state_lock,
    )
    safe_target, perr = _safe_sound_path(target)
    if perr is not None or not safe_target:
        log.warning("play_sound shortcut: invalid target %r (%s)", target, perr)
        return 'off'
    if not reg.uart:
        raise _ShortcutRefused('Slave UART unavailable — sound not sent')
    try:
        with _audio_state_lock:
            if reg.audio_playing and reg.audio_current == target:
                reg.uart.send('S', 'STOP')
                reg.audio_playing = False
                reg.audio_current = ''
                return 'off'
            reg.uart.send('S', target)
            reg.audio_playing = True
            reg.audio_current = target
        _schedule_audio_reset(_get_sound_duration_ms(target))
    except OSError as e:
        log.warning("play_sound UART send failed: %s", e)
        raise _ShortcutRefused('UART send failed')
    return 'fired'


def _act_play_random_audio(target: str, current: str) -> str:
    from master.api.audio_bp import (
        _schedule_audio_reset, _category_avg_duration_ms,
        RANDOM_PLAY_PREFIX, _audio_state_lock,
    )
    # B6: re-validate category name (defense-in-depth)
    if not re.match(r'^[a-z0-9_]{1,32}$', str(target)):
        return 'off'
    if not reg.uart:
        raise _ShortcutRefused('Slave UART unavailable')
    tagged = f'{RANDOM_PLAY_PREFIX}{target}'
    try:
        with _audio_state_lock:
            if reg.audio_playing and reg.audio_current == tagged:
                reg.uart.send('S', 'STOP')
                reg.audio_playing = False
                reg.audio_current = ''
                return 'off'
            reg.uart.send('S', f'RANDOM:{target}')
            reg.audio_playing = True
            reg.audio_current = tagged
        _schedule_audio_reset(_category_avg_duration_ms(target) + 500)
    except OSError as e:
        log.warning("play_random_audio UART send failed: %s", e)
        raise _ShortcutRefused('UART send failed')
    return 'fired'


def _act_none(target: str, current: str) -> str:
    return 'off'


def _act_play_animation(target: str, current: str) -> str:
    """W16 fix 2026-05-16: trigger a T-code animation as a shortcut.
    Re-validates the T-code at trigger time (defense-in-depth: the
    .chor catalogue could have changed between save and fire)."""
    try:
        mode_int = int(target)
    except (TypeError, ValueError):
        log.warning("play_animation shortcut: invalid target %r", target)
        return 'off'
    from master.lights.base_controller import BaseLightsController
    if mode_int not in BaseLightsController.ANIMATIONS:
        log.warning("play_animation shortcut: unknown T-code %d", mode_int)
        return 'off'
    if not reg.teeces:
        return 'off'
    reg.teeces.animation(mode_int)
    return 'fired'


_ACTIONS = {
    'none':                _act_none,
    'arms_toggle':         _act_arms_toggle,
    'body_panel_toggle':   _act_body_panel_toggle,
    'dome_panel_toggle':   _act_dome_panel_toggle,
    'play_choreo':         _act_play_choreo,
    'play_sound':          _act_play_sound,
    'play_random_audio':   _act_play_random_audio,
    'play_animation':      _act_play_animation,
}


# ─────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────

@shortcuts_bp.get('/shortcuts')
def get_shortcuts():
    """List configured shortcuts + their current toggle states."""
    data = _read_shortcuts()
    return jsonify({
        'count':     len(data.get('shortcuts', [])),
        'max':       _MAX_SHORTCUTS,
        'shortcuts': data.get('shortcuts', []),
        'states':    dict(_state_dict()),
    })


@shortcuts_bp.post('/shortcuts')
@require_admin
def save_shortcuts():
    """Replace the full shortcuts list. Body: {shortcuts: [...]}
    Validates every entry; on the first failure returns 400 with the
    offending index + reason."""
    body = request.get_json(silent=True)
    # Reject anything that isn't a JSON object — a top-level array
    # would otherwise raise AttributeError on body.get and 500 the
    # request. (Audit finding M-2.)
    if not isinstance(body, dict):
        body = {}
    raw_list = body.get('shortcuts', [])
    if not isinstance(raw_list, list):
        return jsonify({'error': 'shortcuts must be a list'}), 400
    if len(raw_list) > _MAX_SHORTCUTS:
        return jsonify({
            'error': f'too many shortcuts (max {_MAX_SHORTCUTS})',
        }), 400

    cleaned = []
    for idx, raw in enumerate(raw_list):
        norm, err = _normalize_shortcut(raw, idx)
        if err:
            return jsonify({'error': err}), 400
        cleaned.append(norm)

    # Preserve toggle states for shortcuts whose id is unchanged.
    state = _state_dict()
    new_state = {sc['id']: state.get(sc['id'], 'off') for sc in cleaned}
    # transient 'fired' should not persist across a config save
    for k, v in list(new_state.items()):
        if v == 'fired':
            new_state[k] = 'off'

    with _SHORTCUTS_LOCK:
        out = {'shortcuts': cleaned, 'states': new_state}
        _atomic_write_json(_SHORTCUTS_FILE, out)
        # P1 fix 2026-05-16: was clearing state OUTSIDE the lock →
        # concurrent trigger read OLD state while disk had NEW → state
        # drift on next persist. Now atomic.
        state.clear()
        state.update(new_state)

    log.info("Shortcuts saved: %d entries", len(cleaned))
    return jsonify({
        'status':    'ok',
        'count':     len(cleaned),
        'shortcuts': cleaned,
        'states':    new_state,
    })


@shortcuts_bp.post('/shortcuts/<sid>/trigger')
def trigger_shortcut(sid: str):
    """Execute the shortcut's action. Returns the new state."""
    # B5/P2 fix 2026-05-16: per-sid debounce — reject rapid re-trigger
    # within 150ms (double-tap, BT autorepeat, sticky touch button).
    now = time.monotonic()
    last = _LAST_TRIGGER_TS.get(sid, 0)
    if (now - last) < _TRIGGER_DEBOUNCE_S:
        return jsonify({'error': 'debounced', 'state': 'off'}), 429
    _LAST_TRIGGER_TS[sid] = now

    # Per-sid lock — serialize the dispatcher so concurrent triggers
    # from web + Android can't race the state read+write.
    lk = _per_sid_lock(sid)
    if not lk.acquire(blocking=False):
        return jsonify({'error': 'busy', 'state': 'off'}), 429
    try:
        return _trigger_shortcut_impl(sid)
    finally:
        lk.release()


def dispatch_action(sid: str, a_type: str, a_target: str,
                    current: str = 'off') -> tuple[str, str | None, int]:
    """BT Custom Mappings reuse: shared dispatch helper.
    Takes action inline (no shortcuts.json lookup).
    Returns (new_state, error_msg_or_None, http_status).
    Honors all safety gates + per-handler exceptions identically to
    _trigger_shortcut_impl. Caller is responsible for the per-sid lock
    + debounce.

    Used by:
    - shortcuts_bp _trigger_shortcut_impl (wrapper: reads shortcuts.json
      then calls this)
    - bt_controller_driver _fire_custom_mapping (custom button mappings
      bound to BT controller buttons)
    """
    handler = _ACTIONS.get(a_type)
    if handler is None:
        return ('off', f'no handler for action: {a_type}', 500)

    # Safety chain — same gates as _trigger_shortcut_impl
    if reg.estop_active and current != 'on' and a_type != 'none':
        return ('off', 'E-STOP active — reset to use shortcuts', 403)
    if getattr(reg, 'stow_in_progress', False) and a_type in ('arms_toggle', 'body_panel_toggle', 'dome_panel_toggle'):
        return ('off', 'stow in progress — wait for servos to settle', 503)
    if reg.lock_mode == 2 and a_type in ('arms_toggle', 'body_panel_toggle', 'dome_panel_toggle', 'play_choreo'):
        return ('off', 'Child Lock — only sounds/lights/dome rotation allowed', 403)

    try:
        new_state = handler(a_target, current)
        return (new_state, None, 200)
    except _ShortcutBusy as e:
        return ('off', str(e), 409)
    except _ShortcutRefused as e:
        return ('off', str(e), 503)
    except Exception as e:
        log.exception("dispatch_action failed: %s (action=%s target=%s)",
                      sid, a_type, a_target)
        return ('off', f'action failed: {e}', 500)


def _trigger_shortcut_impl(sid: str):
    data = _read_shortcuts()
    sc = next((s for s in data.get('shortcuts', []) if s.get('id') == sid), None)
    if sc is None:
        return jsonify({'error': 'shortcut not found'}), 404

    state = _state_dict()
    current = state.get(sid, 'off')
    a_type   = sc.get('action', {}).get('type', 'none')
    a_target = sc.get('action', {}).get('target', '')

    new_state, err, status = dispatch_action(sid, a_type, a_target, current)
    if err is not None:
        return jsonify({'error': err, 'state': new_state}), status

    # 'fired' is transient — persist as 'off' so dots reflect "nothing
    # currently extended/open" for one-shot actions.
    state[sid] = 'off' if new_state == 'fired' else new_state
    if new_state != 'fired':
        try:
            _persist_state()
        except OSError as e:
            log.warning("Could not persist shortcut state: %s", e)

    return jsonify({'status': 'ok', 'id': sid, 'state': new_state})
