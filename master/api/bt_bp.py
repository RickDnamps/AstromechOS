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
  POST /bt/enable            {"enabled": bool}
  POST /bt/config            {"gamepad_type": str, "deadzone": float, "inactivity_timeout": int, "mappings": {...}}
  POST /bt/estop_reset       → re-arm after E-Stop (resets estop_active = False)

  POST /bt/scan/start        → start 15-second BT scan
  GET  /bt/scan/devices      → list of discovered + already-paired devices
  POST /bt/pair              {"address": "AA:BB:CC:DD:EE:FF"} → pair + trust + connect
  POST /bt/unpair            {"address": "AA:BB:CC:DD:EE:FF"} → remove
"""

import logging
import re
import subprocess
import threading
import time

from flask import Blueprint, request, jsonify
from master.api._admin_auth import require_admin
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
        return jsonify(reg.bt_ctrl.get_status())
    return jsonify({
        'bt_connected': False, 'bt_enabled': False,
        'bt_name': '—', 'bt_battery': 0, 'bt_gamepad_type': 'ps',
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
}
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
            if not _VALID_BT_BUTTON_RE.match(btn_s):
                return jsonify({'error': f'invalid button code: {btn_s!r}'}), 400
            clean[act_s] = btn_s
        # B14 fix 2026-05-16: reject same button bound to >1 action.
        # Was: silent if/elif fallthrough at runtime — first action
        # in the chain wins, the rest never fire (operator's binding
        # looked saved but didn't work).
        dupes = [b for b in clean.values() if list(clean.values()).count(b) > 1]
        if dupes:
            return jsonify({
                'error': f'button(s) bound to multiple actions: {sorted(set(dupes))}',
            }), 400
        patch['mappings'] = clean

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
