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
#  useful, but WITHOUT ANY WARRANTY; without even the implied
#  warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
#  PURPOSE. See the GNU General Public License for details.
#
#  You should have received a copy of the GNU GPL along with
#  AstromechOS. If not, see <https://www.gnu.org/licenses/>.
# ============================================================
"""
Blueprint API Bluetooth Controller — Config, status and pairing.

Endpoints:
  GET  /bt/status            → connection state + current config
                               (+ active_device_mac + device_profiles)
  POST /bt/enable            {"enabled": bool}
  POST /bt/config            {"gamepad_type": str, "deadzone": float, "inactivity_timeout": int, "mappings": {...}}
  POST /bt/estop_reset       → re-arm after E-Stop (resets estop_active = False)

  POST /bt/scan/start        → start 15-second BT scan
  GET  /bt/scan/devices      → list of discovered + already-paired devices
  POST /bt/pair              {"address": "AA:BB:CC:DD:EE:FF"} → pair + trust + connect
  POST /bt/unpair            {"address": "AA:BB:CC:DD:EE:FF"} → remove

  Custom-mapping (per-device button bindings, operator-defined):
  POST   /bt/capture/start   → enter 10s "press any button" capture mode
  GET    /bt/capture/poll    → polling endpoint for the UI capture wizard
  POST   /bt/capture/cancel  → abort capture session early
  POST   /bt/custom_mapping  → upsert a {device_mac, mapping{...}} entry
  DELETE /bt/custom_mapping/<id>   → drop a single mapping (body carries MAC)
  DELETE /bt/device_profile/<mac>  → drop a whole device profile
"""

import logging
import re
import secrets
import subprocess
import threading
import time

from flask import Blueprint, request, jsonify
from master.api._admin_auth import require_admin, get_json_object
import master.registry as reg

log = logging.getLogger(__name__)

# ── Internal scan state ───────────────────────────────────────────
_scan_lock    = threading.Lock()
_scan_active  = False
_scan_devices: dict[str, str] = {}   # address → name

bt_bp = Blueprint('bt', __name__, url_prefix='/bt')


@bt_bp.get('/status')
def bt_status():
    if reg.bt_ctrl:
        out = reg.bt_ctrl.get_status()
        # Custom-mappings surface: active_device_mac + device_profiles.
        # Read from driver state (active MAC) + persisted cfg (profiles).
        # LAN-open same as the rest of /bt/status — MACs are already
        # surfaced via /bt/scan/devices (admin), and the frontend needs
        # this on every poll to drive the runner overlay. If we later
        # tighten the scan endpoint, this should follow.
        try:
            out['active_device_mac'] = getattr(reg.bt_ctrl, '_active_device_mac', None)
        except Exception:
            out['active_device_mac'] = None
        try:
            cfg = reg.bt_ctrl.get_cfg() or {}
            profiles = cfg.get('device_profiles', {})
            out['device_profiles'] = profiles if isinstance(profiles, dict) else {}
        except Exception:
            out['device_profiles'] = {}
        return jsonify(out)
    return jsonify({
        'bt_connected': False, 'bt_enabled': False,
        'bt_name': '—', 'bt_battery': 0, 'bt_gamepad_type': 'ps',
        'active_device_mac': None,
        'device_profiles': {},
    })


@bt_bp.post('/enable')
@require_admin
def bt_enable():
    body    = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    enabled = bool(body.get('enabled', True))
    if reg.bt_ctrl:
        reg.bt_ctrl.set_enabled(enabled)
    return jsonify({'status': 'ok', 'enabled': enabled})


# Mapping shape is {action_name: button_code}. The action_name is the
# semantic role ('throttle', 'estop', etc.) and the button_code is the
# evdev identifier ('BTN_MODE', 'ABS_Y', ...). Allowlist BOTH so a
# typo or malicious POST can't silently disable the gamepad E-STOP.
# Audit finding CR-3 2026-05-15: previously the endpoint accepted any
# dict with no validation. Mirrors the action names actually consumed
# by _handle_button + _handle_axis in bt_controller_driver.
_VALID_BT_MAPPING_ACTIONS = {
    'throttle', 'steer', 'dome',
    'panel_dome', 'panel_body',
    'audio', 'estop', 'turbo',
    # 'camera' = future feature (camera-on-servos tilt). 2026-05-16:
    # accept the key in the allowlist so the operator's chosen axis
    # persists in bt_config.json. No dispatch yet — _handle_axis ignores
    # this key until the camera-servo hardware is installed.
    'camera',
}
# Mapping keys whose VALUE is allowed to be an empty string (= 'none').
# Camera is the only one — operator might want to leave camera tilt
# unmapped on a controller that doesn't have a free stick.
_BT_MAPPING_ALLOW_EMPTY = {'camera'}
import re as _re_bt
# Button code = evdev BTN_*, ABS_*, KEY_*, or generic alphanumeric
# (covers 'dpad_up' style synthetic codes too). Bounded to 32 chars.
_VALID_BT_BUTTON_RE = _re_bt.compile(r'^[A-Za-z][A-Za-z0-9_]{0,31}$')

# Shared MAC regex for both /bt/pair etc. and _btctl defense-in-depth.
_BT_MAC_RE = _re_bt.compile(r'^[0-9A-F]{2}(:[0-9A-F]{2}){5}$')

# gamepad_type is free-form metadata used only for the UI label —
# allow any short printable string but bound the length.
_GAMEPAD_TYPE_MAX = 32


@bt_bp.post('/config')
@require_admin
def bt_config():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({'error': 'expected JSON object'}), 400
    if not reg.bt_ctrl:
        return jsonify({'error': 'BTController not available'}), 503

    patch = {}
    # gamepad_type — free-form label, length-bounded, printable only.
    if 'gamepad_type' in body:
        gt = str(body['gamepad_type']).strip()
        if not gt or len(gt) > _GAMEPAD_TYPE_MAX or not gt.isprintable():
            return jsonify({'error': 'gamepad_type must be 1..32 printable chars'}), 400
        patch['gamepad_type'] = gt.lower()

    # deadzone — finite float clamped to [0, 0.5]
    if 'deadzone' in body:
        try:
            dz = float(body['deadzone'])
        except (TypeError, ValueError):
            return jsonify({'error': 'deadzone must be a number'}), 400
        import math
        if not math.isfinite(dz):
            return jsonify({'error': 'deadzone must be finite'}), 400
        patch['deadzone'] = max(0.0, min(0.5, dz))

    # inactivity_timeout — int clamped to [0, 3600] seconds. 0 = off.
    if 'inactivity_timeout' in body:
        try:
            it = int(body['inactivity_timeout'])
        except (TypeError, ValueError):
            return jsonify({'error': 'inactivity_timeout must be an integer'}), 400
        patch['inactivity_timeout'] = max(0, min(3600, it))

    # audio_category — must match the strict category regex used by
    # audio_bp + exist in the slave's sound index. Audit reclass R4
    # 2026-05-15.
    if 'audio_category' in body:
        cat = str(body['audio_category']).strip().lower()
        if not _re_bt.match(r'^[a-z0-9_]{1,32}$', cat):
            return jsonify({'error': 'audio_category must be lowercase a-z0-9_ ≤32 chars'}), 400
        patch['audio_category'] = cat

    # mappings — shape is {action_name: button_code}. Both sides
    # allowlisted so a typo can't silently disable the gamepad E-STOP.
    if 'mappings' in body:
        raw = body['mappings']
        if not isinstance(raw, dict):
            return jsonify({'error': 'mappings must be an object'}), 400
        clean = {}
        for action, btn in raw.items():
            act_s = str(action).strip().lower()
            btn_s = str(btn).strip()
            if act_s not in _VALID_BT_MAPPING_ACTIONS:
                return jsonify({
                    'error': f'invalid mapping action: {act_s!r} '
                             f'(allowed: {sorted(_VALID_BT_MAPPING_ACTIONS)})',
                }), 400
            # Empty value allowed only for keys in _BT_MAPPING_ALLOW_EMPTY
            # (camera = 'none' selectable). All others must pass the regex.
            if btn_s == '' and act_s in _BT_MAPPING_ALLOW_EMPTY:
                clean[act_s] = ''
                continue
            if not _VALID_BT_BUTTON_RE.match(btn_s):
                return jsonify({'error': f'invalid button code: {btn_s!r}'}), 400
            clean[act_s] = btn_s
        # B14 fix 2026-05-16: reject same button bound to >1 action.
        # Was: silent if/elif fallthrough at runtime — first action
        # in the chain wins, the rest never fire (operator's binding
        # looked saved but didn't work).
        # Skip empty values in the dupe check (multiple optional axes
        # can all be 'none').
        non_empty_vals = [b for b in clean.values() if b != '']
        dupes = [b for b in non_empty_vals if non_empty_vals.count(b) > 1]
        if dupes:
            return jsonify({
                'error': f'button(s) bound to multiple actions: {sorted(set(dupes))}',
            }), 400
        patch['mappings'] = clean

    # M3 fix 2026-05-16 (security review): if mappings.estop is changing,
    # scan all device profiles for custom mappings that would collide with
    # the NEW estop button → silently dead bindings (E-STOP check fires
    # first in _handle_button). Reject the change with a clear error so
    # operator can re-bind those custom mappings before changing estop.
    if 'mappings' in patch and 'estop' in patch['mappings']:
        new_estop = patch['mappings']['estop']
        try:
            current_cfg = reg.bt_ctrl.get_cfg() or {}
            old_estop = (current_cfg.get('mappings') or {}).get('estop')
            if new_estop != old_estop:
                conflicts = []
                profiles = current_cfg.get('device_profiles', {}) or {}
                for mac, profile in profiles.items():
                    for cm in (profile.get('custom_button_mappings') or []):
                        if cm.get('button') == new_estop:
                            conflicts.append(
                                f"{profile.get('name', mac)}: {cm.get('label') or cm.get('id', '?')}"
                            )
                if conflicts:
                    return jsonify({
                        'error': f'cannot set estop button to {new_estop!r} — '
                                 f'it conflicts with existing custom mappings: '
                                 f'{conflicts}. Delete or re-bind those custom mappings first.',
                    }), 409
        except Exception:
            log.exception("Failed to check estop collision against custom mappings")

    ok = reg.bt_ctrl.update_cfg(patch)
    # E2 fix 2026-05-16: changing inactivity_timeout while gamepad is
    # actively driving could trip the watchdog instantly (operator
    # lowered to 1s but had been holding stick for >1s). Refresh the
    # watermark so the new threshold starts from NOW.
    if 'inactivity_timeout' in patch:
        try:
            import time as _t
            reg.bt_ctrl._last_input_t = _t.time()
            reg.bt_ctrl._inactivity_pause = False
        except Exception:
            pass
    return jsonify({'status': 'ok' if ok else 'error', 'cfg': reg.bt_ctrl.get_cfg()})


@bt_bp.post('/estop_reset')
def bt_estop_reset():
    """Re-arm after a BT-button E-Stop. Delegates to /system/estop_reset
    via internal call so we get the full stow sequence (unfreeze servos,
    safe-home stow at _SAFE_SLEW_SPEED) instead of just flipping the
    flag. The flag-only version left frozen servos in the air and no
    panel close — exactly the bug the system route was built to avoid."""
    from master.api.status_bp import system_estop_reset
    return system_estop_reset()


# ── BT Pairing ────────────────────────────────────────────────────

# Subcommands that take a MAC address as their second arg.
_BTCTL_MAC_VERBS = {'pair', 'unpair', 'connect', 'disconnect', 'trust', 'untrust', 'remove'}


def _btctl(*args, timeout=8) -> tuple[bool, str]:
    """Runs a non-interactive bluetoothctl command. Returns (ok, stdout).

    Audit finding A4-M2 2026-05-15: defense-in-depth. The caller-side
    MAC regex at /bt/pair etc. is the primary check, but if a future
    caller forgets the regex this helper would happily pass anything
    (including `--help` or CLI flags) to bluetoothctl. Assert MAC
    shape here too — fails fast in dev with a clear error.
    """
    if args and len(args) >= 2 and args[0] in _BTCTL_MAC_VERBS:
        # Audit finding BT M-5 2026-05-15: also normalize the args
        # list so subprocess receives the upper-cased MAC. bluetoothctl
        # is permissive on case but some versions return "Device not
        # found" for lowercase. Tuple→list conversion is cheap.
        mac_upper = str(args[1]).upper()
        if not _BT_MAC_RE.match(mac_upper):
            return False, f'_btctl: invalid MAC for verb {args[0]!r}: {args[1]!r}'
        args = list(args)
        args[1] = mac_upper
        args = tuple(args)
    try:
        r = subprocess.run(
            ['bluetoothctl', '--', *args],
            capture_output=True, text=True, timeout=timeout
        )
        out = r.stdout + r.stderr
        return (r.returncode == 0), out
    except (subprocess.TimeoutExpired, OSError) as e:
        # Narrow exception (was bare Exception). Real subprocess
        # failures are TimeoutExpired or OSError (ENOENT if
        # bluetoothctl not installed). Anything else is a bug we
        # want to see.
        return False, str(e)


def _paired_devices() -> list[dict]:
    """Returns already-paired devices via bluetoothctl devices Paired."""
    try:
        r = subprocess.run(
            ['bluetoothctl', 'devices', 'Paired'],
            capture_output=True, text=True, timeout=4
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        # B-106 (audit 2026-05-15): narrow except + log. Bare except
        # returning [] looked identical to 'no paired devices' so a
        # broken BT stack hid permanently. Now log a warning so the
        # operator sees the real error in journalctl.
        log.warning("bluetoothctl devices Paired failed: %s", e)
        return []
    out = _strip_ansi(r.stdout + r.stderr)
    devices = []
    for line in out.splitlines():
        m = re.search(r'Device\s+([0-9A-Fa-f:]{17})\s+(.*)', line)
        if m:
            addr = m.group(1).upper()
            name = _sanitize_device_name(m.group(2)) or addr
            devices.append({'address': addr, 'name': name})
    return devices


def _strip_ansi(text: str) -> str:
    return re.sub(r'\x1b\[[0-9;]*m', '', text)


def _sanitize_device_name(raw: str) -> str:
    """Sanitize a BT device name before returning it to the frontend.

    Audit finding M-1 2026-05-15: bluetoothctl can emit any UTF-8
    string a device advertises. Frontend uses textContent so we're
    XSS-safe today, but a future caller (Android, log viewer) that
    forgets and innerHTML's the list would reopen the surface.
    Strip non-printable + cap length defense-in-depth. Keeps emoji
    + accents (which printable() accepts) but drops control codes.
    """
    if not raw:
        return ''
    clean = ''.join(c for c in raw if c.isprintable())
    return clean[:64].strip()


def _all_devices() -> dict[str, str]:
    """Returns all devices known to bluetoothctl (address → name)."""
    try:
        r = subprocess.run(
            ['bluetoothctl', 'devices'],
            capture_output=True, text=True, timeout=4
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        log.warning("bluetoothctl devices failed: %s", e)
        return {}
    out = _strip_ansi(r.stdout + r.stderr)
    devices = {}
    for line in out.splitlines():
        m = re.search(r'Device\s+([0-9A-Fa-f:]{17})\s+(.*)', line)
        if m:
            addr = m.group(1).upper()
            name = _sanitize_device_name(m.group(2))
            devices[addr] = name if name and name != addr else addr
    return devices


def _scan_worker(duration: int):
    global _scan_active, _scan_devices
    proc = None
    try:
        # Start scan via stdin pipe. stdout/stderr go to DEVNULL so the
        # pipe buffer can't fill (B-85 was already addressed by DEVNULL,
        # confirmed during MEDIUM audit pass 2026-05-15).
        proc = subprocess.Popen(
            ['bluetoothctl'],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, text=True
        )
        proc.stdin.write('scan on\n'); proc.stdin.flush()

        deadline = time.time() + duration
        while time.time() < deadline:
            time.sleep(2)
            found = _all_devices()
            with _scan_lock:
                _scan_devices.update(found)

        proc.stdin.write('scan off\n'); proc.stdin.flush()
        time.sleep(0.5)
    except (OSError, BrokenPipeError) as e:
        # B-86 (audit 2026-05-15): narrow except + log. Was bare
        # `except Exception: pass` which swallowed every scan failure
        # silently — operator got zero feedback when BT stack errored.
        log.warning("BT scan worker error: %s", e)
    finally:
        # B-85 / B-86: always terminate + reap the child so zombie
        # bluetoothctl processes can't accumulate over repeated scans.
        if proc is not None:
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                try:
                    proc.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    pass
            except OSError:
                pass
        with _scan_lock:
            _scan_active = False


@bt_bp.post('/scan/start')
@require_admin
def bt_scan_start():
    """Starts a 15-second Bluetooth scan."""
    global _scan_active, _scan_devices
    with _scan_lock:
        if _scan_active:
            return jsonify({'status': 'already_scanning'})
        _scan_active  = True
        _scan_devices = {}
    threading.Thread(target=_scan_worker, args=(15,), daemon=True).start()
    return jsonify({'status': 'scanning', 'duration': 15})


@bt_bp.get('/scan/devices')
@require_admin
def bt_scan_devices():
    """Returns discovered devices + already-paired devices.
    B11 fix 2026-05-16: was LAN-open → exposed paired MAC addresses +
    sanitized names to anyone on the LAN. MAC addresses enable device
    fingerprinting + controller names could leak operator's other
    devices ('John's iPhone 15 Pro'). Admin-gate matches the mutation
    endpoints in this blueprint."""
    with _scan_lock:
        discovered = [{'address': a, 'name': n} for a, n in _scan_devices.items()]
        scanning   = _scan_active
    paired = _paired_devices()
    paired_addrs = {d['address'] for d in paired}
    # Exclude already-paired devices from the "discovered" list
    discovered = [d for d in discovered if d['address'] not in paired_addrs]
    return jsonify({'scanning': scanning, 'discovered': discovered, 'paired': paired})


@bt_bp.post('/pair')
@require_admin
def bt_pair():
    """Pair + trust + connect a BT device by MAC address."""
    body    = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    address = body.get('address', '').strip().upper()
    if not re.match(r'^([0-9A-F]{2}:){5}[0-9A-F]{2}$', address):
        return jsonify({'error': 'invalid address'}), 400

    def _do_pair():
        _btctl('pair',    address, timeout=20)
        _btctl('trust',   address, timeout=5)
        _btctl('connect', address, timeout=10)

    threading.Thread(target=_do_pair, daemon=True).start()
    return jsonify({'status': 'pairing', 'address': address})


@bt_bp.post('/unpair')
@require_admin
def bt_unpair():
    """Removes a paired BT device."""
    body    = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    address = body.get('address', '').strip().upper()
    if not re.match(r'^([0-9A-F]{2}:){5}[0-9A-F]{2}$', address):
        return jsonify({'error': 'invalid address'}), 400
    ok, out = _btctl('remove', address, timeout=5)
    return jsonify({'status': 'ok' if ok else 'error', 'detail': out.strip()})


# ──────────────────────────────────────────────────────────────────
# BT Custom Mappings — per-device operator-defined button bindings
# ──────────────────────────────────────────────────────────────────
# Schema (lives under device_profiles[<MAC>].custom_button_mappings in
# bt_config.json — driver agent owns the in-memory side):
#   {id: 12-hex, button: 'BTN_*', action: {type, target},
#    label?: str, icon?: str}
#
# Validation is performed at BOTH save time (here) and trigger time
# (driver _fire_custom_mapping reuses shortcuts_bp.dispatch_action which
# re-validates against on-disk reality). Defense-in-depth so a tampered
# bt_config.json can't escape strict-mode checks.

# Per-device cap. Mirrors shortcuts' _MAX_SHORTCUTS = 12 — same UX
# argument (a controller has ~12 spare buttons after the standard
# mappings; more than that is a configuration smell).
_MAX_BT_CUSTOM_MAPPINGS = 12

# Strict MAC regex (uppercase canonical form). Matches the format the
# driver stores in cfg + the format bluetoothctl + evdev .uniq returns
# after our _btctl normalization. Lowercase + mixed accepted via .upper()
# normalization in each endpoint.
_BT_PROFILE_MAC_RE = _re_bt.compile(r'^[0-9A-Fa-f:]{17}$')

# Label/icon caps mirror shortcuts (_LABEL_MAX=32, _ICON_MAX=8).
_BT_LABEL_MAX = 32
_BT_ICON_MAX  = 8


def _sanitize_bt_label(raw) -> str:
    """Same family of sanitization as shortcuts_bp._sanitize_label —
    strip control chars + cap length so a malicious profile can't
    inject newlines/null bytes into bt_config.json."""
    s = str(raw or '').strip()[:_BT_LABEL_MAX]
    return ''.join(c for c in s if c >= ' ' and c not in '\n\r\x00\x7f')


def _sanitize_bt_icon(raw) -> str:
    s = str(raw or '').strip()[:_BT_ICON_MAX]
    return ''.join(c for c in s if c >= ' ' and c not in '\n\r\x00\x7f')


def _normalize_mac(raw) -> str | None:
    """Return upper-cased MAC, or None if invalid. The driver stores
    profiles keyed by upper-case MAC — every lookup must normalize."""
    s = str(raw or '').strip().upper()
    if not _BT_PROFILE_MAC_RE.match(s):
        return None
    return s


def _read_device_profiles() -> dict:
    """Snapshot of device_profiles from the driver cfg. Returns {} if
    BT driver is unavailable or the field is missing. Caller is expected
    to deep-copy individual profiles before mutating."""
    if not reg.bt_ctrl:
        return {}
    try:
        cfg = reg.bt_ctrl.get_cfg() or {}
    except Exception:
        return {}
    profiles = cfg.get('device_profiles', {})
    return profiles if isinstance(profiles, dict) else {}


def _persist_device_profiles(profiles: dict) -> bool:
    """Write the full updated device_profiles dict back through the
    driver's atomic update_cfg path (tmp+rename+fsync+chmod 0600 +
    cross-thread cfg lock — see bt_controller_driver._cfg_save_lock).
    Returns True on success."""
    if not reg.bt_ctrl:
        return False
    return bool(reg.bt_ctrl.update_cfg({'device_profiles': profiles}))


# ── Capture mode state (module-level) ──────────────────────────────
# The driver owns the real capture state (set by _handle_button on the
# next button press); this lock just serializes the "start" path so two
# admins can't open overlapping sessions. The defense-in-depth Timer
# guarantees the driver's capture flag can't latch ON indefinitely if
# the operator closes the browser tab before a button is pressed.
_capture_lock = threading.Lock()
_capture_id: str | None = None
_capture_expires_at_ms: int = 0
_capture_safety_timer: threading.Timer | None = None

# 10s window — matches the wizard's countdown. +0.5s safety margin so
# the timer fires AFTER the driver-side expiry (no race on cancel).
_CAPTURE_DURATION_S      = 10.0
_CAPTURE_SAFETY_MARGIN_S = 0.5


def _safety_cancel_capture(for_capture_id: str | None = None) -> None:
    """Defense-in-depth: if the driver's expiry mechanism is buggy /
    a future refactor drops it, this fires after _CAPTURE_DURATION_S +
    margin and forces the driver back to non-capture state.
    M4 fix 2026-05-16 (security review): only cancel if the session id
    matches the one this Timer was created for. Was: a delayed Timer
    from a previous (cancelled) session could fire AFTER a new session
    started and silently clobber it."""
    global _capture_id, _capture_expires_at_ms
    with _capture_lock:
        if for_capture_id is not None and _capture_id != for_capture_id:
            # Superseded — this timer is for an old session. Skip.
            return
        _capture_id = None
        _capture_expires_at_ms = 0
    try:
        if reg.bt_ctrl and hasattr(reg.bt_ctrl, 'cancel_capture'):
            reg.bt_ctrl.cancel_capture()
    except Exception:
        log.exception("safety cancel_capture failed")


@bt_bp.post('/capture/start')
@require_admin
def bt_capture_start():
    """Enter button-capture mode. The driver listens for the next
    EV_KEY press on the active controller and stashes the button code.
    Returns {capture_id, expires_at_ms} or 409 if another session is
    already in progress.

    The capture_id is opaque (cryptographic random) — clients echo it
    back via /capture/poll so a stale tab can't poll a fresh session
    started by a different admin (matches the optimistic concurrency
    token pattern in choreo categories)."""
    global _capture_id, _capture_expires_at_ms, _capture_safety_timer
    if not reg.bt_ctrl:
        return jsonify({'error': 'BTController not available'}), 503
    if not hasattr(reg.bt_ctrl, 'enter_capture_mode'):
        return jsonify({'error': 'capture mode not supported by current driver build'}), 503
    with _capture_lock:
        # Reject overlapping sessions. _capture_expires_at_ms is wall
        # clock ms; if it's already past, treat as cleanly closed.
        now_ms = int(time.time() * 1000)
        if _capture_id is not None and now_ms < _capture_expires_at_ms:
            return jsonify({
                'error': 'capture already in progress',
                'capture_id': _capture_id,
                'expires_at_ms': _capture_expires_at_ms,
            }), 409
        try:
            reg.bt_ctrl.enter_capture_mode(_CAPTURE_DURATION_S)
        except Exception as e:
            log.exception("enter_capture_mode failed")
            return jsonify({'error': f'driver capture init failed: {e}'}), 500
        _capture_id = secrets.token_hex(8)
        _capture_expires_at_ms = now_ms + int(_CAPTURE_DURATION_S * 1000)
        # Cancel any lingering safety timer first (caller of /capture/cancel
        # may have already cleared it, but be defensive).
        if _capture_safety_timer is not None:
            try:
                _capture_safety_timer.cancel()
            except Exception:
                pass
        # M4 fix: pass the session id so a delayed Timer from a prior
        # (cancelled) session can't clobber a fresh one.
        _capture_safety_timer = threading.Timer(
            _CAPTURE_DURATION_S + _CAPTURE_SAFETY_MARGIN_S,
            _safety_cancel_capture,
            args=(_capture_id,),
        )
        _capture_safety_timer.daemon = True
        _capture_safety_timer.start()
    return jsonify({
        'capture_id': _capture_id,
        'expires_at_ms': _capture_expires_at_ms,
    })


@bt_bp.get('/capture/poll')
@require_admin
def bt_capture_poll():
    """Return the current capture state. Driver reports one of:
      'listening'  → no button pressed yet
      'captured'   → button stashed, response carries `button`
      'expired'    → 10s elapsed with no press
      'cancelled'  → explicitly cancelled by /capture/cancel

    Always 200 — the state field is the truth, not the HTTP code (lets
    polling clients use a single happy-path branch)."""
    if not reg.bt_ctrl:
        return jsonify({'state': 'cancelled', 'button': None, 'remaining_ms': 0})
    if not hasattr(reg.bt_ctrl, 'get_capture_state'):
        return jsonify({'state': 'cancelled', 'button': None, 'remaining_ms': 0})
    try:
        state_info = reg.bt_ctrl.get_capture_state() or {}
    except Exception:
        log.exception("get_capture_state failed")
        return jsonify({'state': 'cancelled', 'button': None, 'remaining_ms': 0})
    state    = str(state_info.get('state') or 'cancelled')
    button   = state_info.get('button')
    if state not in ('listening', 'captured', 'expired', 'cancelled'):
        state = 'cancelled'
    # Driver MAY report remaining_ms; if it doesn't, compute from our
    # _capture_expires_at_ms which is the same window.
    remaining_ms = state_info.get('remaining_ms')
    if remaining_ms is None:
        with _capture_lock:
            now_ms = int(time.time() * 1000)
            remaining_ms = max(0, _capture_expires_at_ms - now_ms)
    return jsonify({
        'state':        state,
        'button':       button,
        'remaining_ms': int(remaining_ms),
    })


@bt_bp.post('/capture/cancel')
@require_admin
def bt_capture_cancel():
    """Abort an in-flight capture session. Idempotent — returns ok=true
    even if no session was active."""
    global _capture_id, _capture_expires_at_ms, _capture_safety_timer
    with _capture_lock:
        _capture_id = None
        _capture_expires_at_ms = 0
        if _capture_safety_timer is not None:
            try:
                _capture_safety_timer.cancel()
            except Exception:
                pass
            _capture_safety_timer = None
    try:
        if reg.bt_ctrl and hasattr(reg.bt_ctrl, 'cancel_capture'):
            reg.bt_ctrl.cancel_capture()
    except Exception:
        log.exception("driver cancel_capture failed")
    return jsonify({'ok': True})


# ── Custom mapping CRUD ────────────────────────────────────────────

def _validate_custom_mapping(mapping_raw, profile, *, allow_id_reuse: str | None = None) -> tuple[dict | None, str]:
    """Validate + normalize a single custom_button_mappings entry.
    Returns (clean_dict, '') on success or (None, error_msg) on failure.

    `profile` is the (already-fetched) device_profile dict we'll be
    inserting into — used to enforce the per-MAC uniqueness rules.
    `allow_id_reuse` is the existing mapping id we're replacing (for
    upsert / edit); duplicate-button checks ignore that id."""
    if not isinstance(mapping_raw, dict):
        return None, 'mapping must be an object'

    # Button code — same allowlist as legacy mappings (B-50 audit).
    btn = str(mapping_raw.get('button') or '').strip()
    if not _VALID_BT_BUTTON_RE.match(btn):
        return None, f'invalid button code: {btn!r}'

    # CRITICAL: E-STOP button is reserved — operator must never bind it
    # to anything else. Mirrors shortcuts cap of 'no shortcut binds the
    # E-STOP servo'. Driver-side _handle_button checks the E-STOP code
    # FIRST, so a custom mapping with this button would never fire
    # anyway, but rejecting at save time gives the operator immediate
    # feedback instead of a silent dead button.
    estop_btn = 'BTN_MODE'
    if reg.bt_ctrl:
        try:
            cfg = reg.bt_ctrl.get_cfg() or {}
            estop_btn = cfg.get('mappings', {}).get('estop', 'BTN_MODE')
        except Exception:
            pass
    if btn == estop_btn:
        return None, f'button {btn!r} reserved for E-STOP'

    # Per-profile uniqueness: a button can map to AT MOST one custom
    # action on the same device. Edit path passes allow_id_reuse so the
    # mapping we're replacing doesn't count as a duplicate of itself.
    existing = profile.get('custom_button_mappings', []) or []
    for m in existing:
        if not isinstance(m, dict):
            continue
        if allow_id_reuse and m.get('id') == allow_id_reuse:
            continue
        if m.get('button') == btn:
            return None, f'button {btn!r} already bound on this device'

    # Action — defer to shortcuts_bp validator so action types stay in
    # lockstep with shortcuts (single source of truth for what 'play_
    # choreo' / 'play_sound' / etc. accept). Lazy import to avoid the
    # bt_bp ↔ shortcuts_bp circular at module load time.
    action = mapping_raw.get('action') or {}
    if not isinstance(action, dict):
        return None, 'action must be an object'
    a_type   = str(action.get('type') or '').strip()
    a_target = str(action.get('target') or '').strip()
    from master.api.shortcuts_bp import _validate_action
    ok, err = _validate_action(a_type, a_target)
    if not ok:
        return None, err

    # ID — preserve if present + matches a 12-hex pattern; otherwise
    # generate a fresh one. secrets.token_hex(6) = 12 hex chars.
    raw_id = str(mapping_raw.get('id') or '').strip()
    if raw_id and re.match(r'^[0-9a-f]{12}$', raw_id):
        sid = raw_id
    else:
        sid = secrets.token_hex(6)

    return {
        'id':     sid,
        'button': btn,
        'action': {'type': a_type, 'target': a_target},
        'label':  _sanitize_bt_label(mapping_raw.get('label', '')),
        'icon':   _sanitize_bt_icon(mapping_raw.get('icon', '')),
    }, ''


@bt_bp.post('/custom_mapping')
@require_admin
def bt_custom_mapping_upsert():
    """Add or replace a custom button mapping on a device profile.

    Body: {device_mac, mapping: {id?, button, action: {type, target},
                                  label?, icon?}}
    The presence of `id` triggers a replace (preserves the slot in the
    profile's list); absence → fresh insert with a generated id.
    Returns {ok: true, mapping: {...full normalized entry...}}."""
    try:
        body = get_json_object()
        if body is None:
            return jsonify({'error': 'expected JSON object'}), 400
        if not reg.bt_ctrl:
            return jsonify({'error': 'BTController not available'}), 503

        mac = _normalize_mac(body.get('device_mac'))
        if mac is None:
            return jsonify({'error': 'invalid device_mac'}), 400

        # Profiles dict is mutated under the driver's _cfg_save_lock
        # (held by update_cfg). To avoid a TOCTOU between read+write we
        # snapshot, mutate, and write back the whole dict — driver
        # update_cfg replaces device_profiles atomically.
        profiles = dict(_read_device_profiles())
        profile  = dict(profiles.get(mac) or {})
        if 'custom_button_mappings' not in profile or not isinstance(profile['custom_button_mappings'], list):
            profile['custom_button_mappings'] = []

        # Cap check — count current mappings, factoring in whether we're
        # replacing an existing one (replace doesn't grow the list).
        raw_mapping = body.get('mapping') or {}
        edit_id = str((raw_mapping.get('id') or '')).strip()
        is_edit = bool(edit_id) and any(
            isinstance(m, dict) and m.get('id') == edit_id
            for m in profile['custom_button_mappings']
        )
        if not is_edit and len(profile['custom_button_mappings']) >= _MAX_BT_CUSTOM_MAPPINGS:
            return jsonify({
                'error': f'too many custom mappings (max {_MAX_BT_CUSTOM_MAPPINGS} per device)',
            }), 400

        clean, err = _validate_custom_mapping(
            raw_mapping, profile,
            allow_id_reuse=edit_id if is_edit else None,
        )
        if err:
            return jsonify({'error': err}), 400

        # Upsert: drop any existing entry with the same id, then append.
        # Order preserved for the rest of the list so the UI doesn't
        # shuffle on edit.
        profile['custom_button_mappings'] = [
            m for m in profile['custom_button_mappings']
            if isinstance(m, dict) and m.get('id') != clean['id']
        ]
        profile['custom_button_mappings'].append(clean)

        # Bookkeeping: preserve / seed the device-meta fields. The
        # driver populates name + type + last_seen on connect via
        # _ensure_device_profile, but an admin may upsert against a MAC
        # that hasn't connected yet (preconfiguring before the BT pair).
        profile.setdefault('name', '')
        profile.setdefault('type', '')
        profile.setdefault('last_seen', 0)

        profiles[mac] = profile
        if not _persist_device_profiles(profiles):
            return jsonify({'error': 'persist failed'}), 500
        log.info("BT custom mapping upserted: mac=%s id=%s button=%s action=%s",
                 mac, clean['id'], clean['button'], clean['action'])
        return jsonify({'ok': True, 'mapping': clean})
    except Exception as e:
        log.exception("bt_custom_mapping_upsert failed")
        return jsonify({'error': f'internal error: {e}'}), 500


@bt_bp.delete('/custom_mapping/<mid>')
@require_admin
def bt_custom_mapping_delete(mid: str):
    """Remove a single mapping by id. Body MUST carry device_mac so we
    don't have to scan every profile (also lets the frontend match its
    optimistic mutation pattern: it knows which device it edited)."""
    try:
        body = get_json_object() or {}
        if not reg.bt_ctrl:
            return jsonify({'error': 'BTController not available'}), 503

        mac = _normalize_mac(body.get('device_mac'))
        if mac is None:
            return jsonify({'error': 'invalid device_mac'}), 400
        # Validate the id format defensively — 12-hex was the format we
        # generated; a longer/garbage id can be safely 404'd without
        # touching the profile.
        if not re.match(r'^[0-9a-f]{12}$', str(mid or '')):
            return jsonify({'error': 'invalid mapping id'}), 400

        profiles = dict(_read_device_profiles())
        profile  = dict(profiles.get(mac) or {})
        existing = profile.get('custom_button_mappings', []) or []
        new_list = [m for m in existing
                    if isinstance(m, dict) and m.get('id') != mid]
        if len(new_list) == len(existing):
            return jsonify({'error': 'mapping not found'}), 404

        profile['custom_button_mappings'] = new_list
        profiles[mac] = profile
        if not _persist_device_profiles(profiles):
            return jsonify({'error': 'persist failed'}), 500
        log.info("BT custom mapping deleted: mac=%s id=%s", mac, mid)
        return jsonify({'ok': True})
    except Exception as e:
        log.exception("bt_custom_mapping_delete failed")
        return jsonify({'error': f'internal error: {e}'}), 500


@bt_bp.delete('/device_profile/<mac>')
@require_admin
def bt_device_profile_delete(mac: str):
    """Drop a whole device profile (and all its custom mappings).
    Operator-facing: forgets a controller that was paired once and is
    no longer used. Different from /bt/unpair which removes BT pairing
    at the OS level — this only cleans up bt_config.json."""
    try:
        norm = _normalize_mac(mac)
        if norm is None:
            return jsonify({'error': 'invalid MAC'}), 400
        if not reg.bt_ctrl:
            return jsonify({'error': 'BTController not available'}), 503
        profiles = dict(_read_device_profiles())
        if norm not in profiles:
            return jsonify({'error': 'profile not found'}), 404
        profiles.pop(norm, None)
        if not _persist_device_profiles(profiles):
            return jsonify({'error': 'persist failed'}), 500
        log.info("BT device profile deleted: mac=%s", norm)
        return jsonify({'ok': True})
    except Exception as e:
        log.exception("bt_device_profile_delete failed")
        return jsonify({'error': f'internal error: {e}'}), 500


# ──────────────────────────────────────────────────────────────────
# Cascade hooks — called from choreo_bp + audio_bp when a sound /
# choreo is renamed or deleted. Mirrors shortcuts_bp.cascade_rename /
# cascade_delete so a renamed choreo doesn't leave a dead binding on a
# BT controller's custom button.
# ──────────────────────────────────────────────────────────────────

def cascade_rename_in_bt(action_type: str, old_target: str, new_target: str) -> int:
    """Rewrite every device_profile's custom_button_mappings entry
    whose action matches (type, old_target) to point at new_target.
    Returns total number of mappings updated across all profiles.

    Single update_cfg() call at the end so the atomic write fires once
    per cascade event (not once per profile). If nothing matched, no
    write happens."""
    if not action_type or not old_target or not new_target:
        return 0
    if old_target == new_target:
        return 0
    if not reg.bt_ctrl:
        return 0
    profiles = dict(_read_device_profiles())
    changed = 0
    new_profiles = {}
    for mac, prof in profiles.items():
        if not isinstance(prof, dict):
            new_profiles[mac] = prof
            continue
        prof_copy = dict(prof)
        maps = list(prof_copy.get('custom_button_mappings', []) or [])
        for m in maps:
            if not isinstance(m, dict):
                continue
            act = m.get('action') or {}
            if act.get('type') == action_type and act.get('target') == old_target:
                act = dict(act)
                act['target'] = new_target
                m['action'] = act
                changed += 1
        prof_copy['custom_button_mappings'] = maps
        new_profiles[mac] = prof_copy
    if changed:
        if _persist_device_profiles(new_profiles):
            log.info("BT cascade rename: %s '%s'→'%s' updated %d mapping(s)",
                     action_type, old_target, new_target, changed)
        else:
            log.warning("BT cascade rename: persist failed for %s '%s'→'%s'",
                        action_type, old_target, new_target)
    return changed


def cascade_delete_in_bt(action_type: str, target: str) -> int:
    """Neutralize every custom_button_mappings entry whose action
    matches (type, target) by switching its action to 'none' (preserves
    label/icon so the operator notices and can rebind). Mirrors
    shortcuts_bp.cascade_delete behavior — softer than removing the
    mapping entry, gives the operator a chance to recover."""
    if not action_type or not target:
        return 0
    if not reg.bt_ctrl:
        return 0
    profiles = dict(_read_device_profiles())
    changed = 0
    new_profiles = {}
    for mac, prof in profiles.items():
        if not isinstance(prof, dict):
            new_profiles[mac] = prof
            continue
        prof_copy = dict(prof)
        maps = list(prof_copy.get('custom_button_mappings', []) or [])
        for m in maps:
            if not isinstance(m, dict):
                continue
            act = m.get('action') or {}
            if act.get('type') == action_type and act.get('target') == target:
                m['action'] = {'type': 'none', 'target': ''}
                changed += 1
        prof_copy['custom_button_mappings'] = maps
        new_profiles[mac] = prof_copy
    if changed:
        if _persist_device_profiles(new_profiles):
            log.info("BT cascade delete: %s '%s' neutralized %d mapping(s)",
                     action_type, target, changed)
        else:
            log.warning("BT cascade delete: persist failed for %s '%s'",
                        action_type, target)
    return changed
