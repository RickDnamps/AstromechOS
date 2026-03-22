# ============================================================
#  ██████╗ ██████╗       ██████╗ ██████╗
#  ██╔══██╗╚════██╗      ██╔══██╗╚════██╗
#  ██████╔╝ █████╔╝      ██║  ██║ █████╔╝
#  ██╔══██╗██╔═══╝       ██║  ██║██╔═══╝
#  ██║  ██║███████╗      ██████╔╝███████╗
#  ╚═╝  ╚═╝╚══════╝      ╚═════╝ ╚══════╝
#
#  R2-D2 Control System — Distributed Robot Controller
# ============================================================
#  Copyright (C) 2025 RickDnamps
#  https://github.com/RickDnamps/R2D2_Control
#
#  This file is part of R2D2_Control.
#
#  R2D2_Control is free software: you can redistribute it
#  and/or modify it under the terms of the GNU General
#  Public License as published by the Free Software
#  Foundation, either version 2 of the License, or
#  (at your option) any later version.
#
#  R2D2_Control is distributed in the hope that it will be
#  useful, but WITHOUT ANY WARRANTY; without even the implied
#  warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
#  PURPOSE. See the GNU General Public License for details.
#
#  You should have received a copy of the GNU GPL along with
#  R2D2_Control. If not, see <https://www.gnu.org/licenses/>.
# ============================================================
"""
Blueprint API Bluetooth Controller — Config, statut et jumelage.

Endpoints:
  GET  /bt/status            → état connexion + config actuelle
  POST /bt/enable            {"enabled": bool}
  POST /bt/config            {"gamepad_type": str, "deadzone": float, "inactivity_timeout": int, "mappings": {...}}
  POST /bt/estop_reset       → réarme après E-Stop (remet estop_active = False)

  POST /bt/scan/start        → démarre scan BT 15 sec
  GET  /bt/scan/devices      → liste des appareils découverts + jumelés
  POST /bt/pair              {"address": "AA:BB:CC:DD:EE:FF"} → pair + trust + connect
  POST /bt/unpair            {"address": "AA:BB:CC:DD:EE:FF"} → remove
"""

import re
import subprocess
import threading
import time

from flask import Blueprint, request, jsonify
import master.registry as reg

# ── État interne du scan ──────────────────────────────────────────
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
def bt_enable():
    body    = request.get_json(silent=True) or {}
    enabled = bool(body.get('enabled', True))
    if reg.bt_ctrl:
        reg.bt_ctrl.set_enabled(enabled)
    return jsonify({'status': 'ok', 'enabled': enabled})


@bt_bp.post('/config')
def bt_config():
    body = request.get_json(silent=True) or {}
    if not reg.bt_ctrl:
        return jsonify({'error': 'BTController non disponible'}), 503

    patch = {}
    if 'gamepad_type'       in body: patch['gamepad_type']       = str(body['gamepad_type'])
    if 'deadzone'           in body: patch['deadzone']           = float(body['deadzone'])
    if 'inactivity_timeout' in body: patch['inactivity_timeout'] = int(body['inactivity_timeout'])
    if 'mappings'           in body: patch['mappings']           = dict(body['mappings'])

    ok = reg.bt_ctrl.update_cfg(patch)
    return jsonify({'status': 'ok' if ok else 'error', 'cfg': reg.bt_ctrl.get_cfg()})


@bt_bp.post('/estop_reset')
def bt_estop_reset():
    """Réarme après E-Stop BT — remet le flag estop_active à False."""
    reg.estop_active = False
    return jsonify({'status': 'ok'})


# ── Jumelage BT ───────────────────────────────────────────────────

def _btctl(*args, timeout=8) -> tuple[bool, str]:
    """Lance une commande bluetoothctl non-interactive. Retourne (ok, stdout)."""
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
    """Retourne les devices déjà jumelés (trusted) via bluetoothctl devices Paired."""
    _, out = _btctl('devices', 'Paired', timeout=4)
    devices = []
    for line in out.splitlines():
        m = re.match(r'Device\s+([0-9A-F:]{17})\s+(.*)', line.strip())
        if m:
            devices.append({'address': m.group(1), 'name': m.group(2).strip() or m.group(1)})
    return devices


def _scan_worker(duration: int):
    global _scan_active, _scan_devices
    try:
        proc = subprocess.Popen(
            ['bluetoothctl'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1
        )
        proc.stdin.write('scan on\n'); proc.stdin.flush()
        deadline = time.time() + duration
        while time.time() < deadline:
            try:
                line = proc.stdout.readline()
            except Exception:
                break
            m = re.search(r'\[NEW\] Device\s+([0-9A-F:]{17})\s+(.*)', line)
            if m:
                addr, name = m.group(1), m.group(2).strip()
                with _scan_lock:
                    _scan_devices[addr] = name or addr
        proc.stdin.write('scan off\n'); proc.stdin.flush()
        proc.terminate()
    finally:
        with _scan_lock:
            _scan_active = False


@bt_bp.post('/scan/start')
def bt_scan_start():
    """Lance un scan Bluetooth de 15 secondes."""
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
    """Retourne les appareils découverts + déjà jumelés."""
    with _scan_lock:
        discovered = [{'address': a, 'name': n} for a, n in _scan_devices.items()]
        scanning   = _scan_active
    paired = _paired_devices()
    paired_addrs = {d['address'] for d in paired}
    # Exclure les appareils déjà jumelés de la liste "découverts"
    discovered = [d for d in discovered if d['address'] not in paired_addrs]
    return jsonify({'scanning': scanning, 'discovered': discovered, 'paired': paired})


@bt_bp.post('/pair')
def bt_pair():
    """Pair + trust + connect un appareil BT par adresse MAC."""
    body    = request.get_json(silent=True) or {}
    address = body.get('address', '').strip().upper()
    if not re.match(r'^([0-9A-F]{2}:){5}[0-9A-F]{2}$', address):
        return jsonify({'error': 'adresse invalide'}), 400

    def _do_pair():
        _btctl('pair',    address, timeout=20)
        _btctl('trust',   address, timeout=5)
        _btctl('connect', address, timeout=10)

    threading.Thread(target=_do_pair, daemon=True).start()
    return jsonify({'status': 'pairing', 'address': address})


@bt_bp.post('/unpair')
def bt_unpair():
    """Supprime un appareil BT jumelé."""
    body    = request.get_json(silent=True) or {}
    address = body.get('address', '').strip().upper()
    if not re.match(r'^([0-9A-F]{2}:){5}[0-9A-F]{2}$', address):
        return jsonify({'error': 'adresse invalide'}), 400
    ok, out = _btctl('remove', address, timeout=5)
    return jsonify({'status': 'ok' if ok else 'error', 'detail': out.strip()})
