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
    body    = request.get_json(silent=True) or {}
    enabled = bool(body.get('enabled', True))
    if reg.bt_ctrl:
        reg.bt_ctrl.set_enabled(enabled)
    return jsonify({'status': 'ok', 'enabled': enabled})


@bt_bp.post('/config')
@require_admin
def bt_config():
    body = request.get_json(silent=True) or {}
    if not reg.bt_ctrl:
        return jsonify({'error': 'BTController not available'}), 503

    patch = {}
    if 'gamepad_type'       in body: patch['gamepad_type']       = str(body['gamepad_type'])
    if 'deadzone'           in body: patch['deadzone']           = float(body['deadzone'])
    if 'inactivity_timeout' in body: patch['inactivity_timeout'] = int(body['inactivity_timeout'])
    if 'mappings'           in body: patch['mappings']           = dict(body['mappings'])

    ok = reg.bt_ctrl.update_cfg(patch)
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

def _btctl(*args, timeout=8) -> tuple[bool, str]:
    """Runs a non-interactive bluetoothctl command. Returns (ok, stdout)."""
    try:
        r = subprocess.run(
            ['bluetoothctl', '--', *args],
            capture_output=True, text=True, timeout=timeout
        )
        out = r.stdout + r.stderr
        return (r.returncode == 0), out
    except Exception as e:
        return False, str(e)


def _paired_devices() -> list[dict]:
    """Returns already-paired devices via bluetoothctl devices Paired."""
    try:
        r = subprocess.run(
            ['bluetoothctl', 'devices', 'Paired'],
            capture_output=True, text=True, timeout=4
        )
        out = _strip_ansi(r.stdout + r.stderr)
        devices = []
        for line in out.splitlines():
            m = re.search(r'Device\s+([0-9A-Fa-f:]{17})\s+(.*)', line)
            if m:
                addr = m.group(1).upper()
                name = m.group(2).strip() or addr
                devices.append({'address': addr, 'name': name})
        return devices
    except Exception:
        return []


def _strip_ansi(text: str) -> str:
    return re.sub(r'\x1b\[[0-9;]*m', '', text)


def _all_devices() -> dict[str, str]:
    """Returns all devices known to bluetoothctl (address → name)."""
    try:
        r = subprocess.run(
            ['bluetoothctl', 'devices'],
            capture_output=True, text=True, timeout=4
        )
        out = _strip_ansi(r.stdout + r.stderr)
        devices = {}
        for line in out.splitlines():
            m = re.search(r'Device\s+([0-9A-Fa-f:]{17})\s+(.*)', line)
            if m:
                addr = m.group(1).upper()
                name = m.group(2).strip()
                devices[addr] = name if name and name != addr else addr
        return devices
    except Exception:
        return {}


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
def bt_scan_devices():
    """Returns discovered devices + already-paired devices."""
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
    body    = request.get_json(silent=True) or {}
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
    body    = request.get_json(silent=True) or {}
    address = body.get('address', '').strip().upper()
    if not re.match(r'^([0-9A-F]{2}:){5}[0-9A-F]{2}$', address):
        return jsonify({'error': 'invalid address'}), 400
    ok, out = _btctl('remove', address, timeout=5)
    return jsonify({'status': 'ok' if ok else 'error', 'detail': out.strip()})
