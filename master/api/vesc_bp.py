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
Blueprint API VESC — Phase 2.
Exposes telemetry and configuration for the propulsion VESCs.

Endpoints:
  GET  /vesc/telemetry         → live telemetry for both VESCs
  POST /vesc/config            {"scale": 0.8}   → power scale (10-100%)
  POST /vesc/invert            {"side": "L"}    → invert motor L or R
  GET  /vesc/can/scan          → CAN bus scan via Slave (timeout 8s)
"""

import configparser
import os
from flask import Blueprint, request, jsonify
import master.registry as reg

_LOCAL_CFG = '/home/artoo/r2d2/master/config/local.cfg'


def _save_vesc_cfg(**kwargs) -> None:
    """Persist one or more keys to local.cfg [vesc]."""
    cfg = configparser.ConfigParser()
    if os.path.exists(_LOCAL_CFG):
        cfg.read(_LOCAL_CFG)
    if not cfg.has_section('vesc'):
        cfg.add_section('vesc')
    for k, v in kwargs.items():
        cfg.set('vesc', k, str(v))
    with open(_LOCAL_CFG, 'w', encoding='utf-8') as f:
        cfg.write(f)

vesc_bp = Blueprint('vesc', __name__, url_prefix='/vesc')

_FAULT_NAMES = {
    0:  'NONE',
    1:  'OVER_VOLTAGE',
    2:  'UNDER_VOLTAGE',
    3:  'DRV',
    4:  'ABS_OVER_CURRENT',
    5:  'OVER_TEMP_FET',
    6:  'OVER_TEMP_MOTOR',
    7:  'GATE_DRIVER_OVER_VOLTAGE',
    8:  'GATE_DRIVER_UNDER_VOLTAGE',
    9:  'MCU_UNDER_VOLTAGE',
    10: 'WATCHDOG_RESET',
}


def _fault_str(code: int) -> str:
    return _FAULT_NAMES.get(code, f'FAULT_{code}')


@vesc_bp.get('/telemetry')
def get_telemetry():
    """Live telemetry for both VESCs + current power scale."""
    import time as _time
    telem = getattr(reg, 'vesc_telem', {'L': None, 'R': None})
    scale = getattr(reg, 'vesc_power_scale', 1.0)
    now   = _time.time()

    # A side is considered live only if its last update was within 3 seconds
    def _is_live(d):
        return d is not None and (now - d.get('ts', 0)) < 3.0

    def _enrich(d):
        if not _is_live(d):
            return None
        return {**d, 'fault_str': _fault_str(d.get('fault', 0))}

    live_L = _enrich(telem.get('L'))
    live_R = _enrich(telem.get('R'))
    connected = (live_L is not None or live_R is not None)

    return jsonify({
        'connected':   connected,
        'power_scale': scale,
        'L': live_L,
        'R': live_R,
    })


@vesc_bp.post('/config')
def set_config():
    """Sets the power scale (0.1-1.0). Sent to Slave via UART VCFG:."""
    body = request.get_json(silent=True) or {}
    try:
        scale = max(0.1, min(1.0, float(body.get('scale', 1.0))))
    except (TypeError, ValueError):
        return jsonify({'error': 'scale must be a float 0.1-1.0'}), 400

    reg.vesc_power_scale = scale
    _save_vesc_cfg(power_scale=f'{scale:.2f}')
    if reg.uart:
        reg.uart.send('VCFG', f'scale:{scale:.2f}')
    return jsonify({'status': 'ok', 'power_scale': scale})


@vesc_bp.get('/config')
def get_config():
    """Returns current VESC configuration (power_scale + invert states + drive mode)."""
    return jsonify({
        'power_scale': getattr(reg, 'vesc_power_scale', 1.0),
        'invert_L':    getattr(reg, 'vesc_invert_L', False),
        'invert_R':    getattr(reg, 'vesc_invert_R', False),
        'duty_mode':   getattr(reg, 'vesc_duty_mode', False),
    })


@vesc_bp.post('/mode')
def set_mode():
    """Switches drive mode. Body: {"duty": true/false}. Not persisted — resets on reboot."""
    body = request.get_json(silent=True) or {}
    duty = bool(body.get('duty', False))
    reg.vesc_duty_mode = duty
    if reg.uart:
        reg.uart.send('VCFG', f'mode:{"duty" if duty else "rpm"}')
    return jsonify({'status': 'ok', 'duty_mode': duty})


@vesc_bp.post('/invert')
def invert_motor():
    """
    Sets motor direction. Body: {"side": "L", "state": true/false}.
    State is persisted to local.cfg and sent to Slave via UART VINV:L:1.
    """
    body = request.get_json(silent=True) or {}
    side = body.get('side', '').upper()
    if side not in ('L', 'R'):
        return jsonify({'error': 'side must be "L" or "R"'}), 400
    state = bool(body.get('state', False))

    if side == 'L':
        reg.vesc_invert_L = state
    else:
        reg.vesc_invert_R = state

    _save_vesc_cfg(**{f'invert_{side.lower()}': '1' if state else '0'})

    if reg.uart:
        reg.uart.send('VINV', f'{side}:{"1" if state else "0"}')

    return jsonify({'status': 'ok', 'side': side, 'state': state})


@vesc_bp.get('/can/scan')
def can_scan():
    """
    Starts a CAN bus scan via UART → Slave → VESC 1 USB.
    Slave replies with CANFOUND:id1,id2 or CANFOUND:ERR.
    Timeout 8s — returns {'ids': [...], 'count': N}.
    """
    if not reg.uart:
        return jsonify({'error': 'UART not available'}), 503

    # Reset the previous scan state
    reg.vesc_can_scan_result = None
    reg.vesc_can_scan_event.clear()

    # Send the scan command to the Slave
    reg.uart.send('CANSCAN', 'start')

    # Wait for the response (max 8s — scan 11 IDs × ~0.12s + margin)
    got = reg.vesc_can_scan_event.wait(timeout=8.0)
    if not got:
        return jsonify({'error': 'Timeout — Slave not available or VESCs not connected via USB'}), 504

    result = reg.vesc_can_scan_result
    if result is None:
        return jsonify({'error': 'Scan failed — VescDriver not ready (Phase 2 not activated?)'}), 500

    return jsonify({'ids': result, 'count': len(result)})
