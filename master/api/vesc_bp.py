"""
Blueprint API VESC — Phase 2.
Expose la télémétrie et la configuration des VESC de propulsion.

Endpoints:
  GET  /vesc/telemetry         → télémétrie live des deux VESC
  POST /vesc/config            {"scale": 0.8}   → power scale (10-100%)
  POST /vesc/invert            {"side": "L"}    → inverse moteur L ou R
"""

from flask import Blueprint, request, jsonify
import master.registry as reg

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
    """Télémétrie live des deux VESC + power scale actuel."""
    telem = getattr(reg, 'vesc_telem', {'L': None, 'R': None})
    scale = getattr(reg, 'vesc_power_scale', 1.0)
    connected = (telem.get('L') is not None or telem.get('R') is not None)

    def _enrich(d):
        if d is None:
            return None
        return {**d, 'fault_str': _fault_str(d.get('fault', 0))}

    return jsonify({
        'connected':   connected,
        'power_scale': scale,
        'L': _enrich(telem.get('L')),
        'R': _enrich(telem.get('R')),
    })


@vesc_bp.post('/config')
def set_config():
    """Règle le power scale (0.1-1.0). Envoyé au Slave via UART VCFG:."""
    body = request.get_json(silent=True) or {}
    try:
        scale = max(0.1, min(1.0, float(body.get('scale', 1.0))))
    except (TypeError, ValueError):
        return jsonify({'error': 'scale doit être un float 0.1-1.0'}), 400

    reg.vesc_power_scale = scale
    if reg.uart:
        reg.uart.send('VCFG', f'scale:{scale:.2f}')
    return jsonify({'status': 'ok', 'power_scale': scale})


@vesc_bp.post('/invert')
def invert_motor():
    """Inverse le sens d'un moteur. Body: {"side": "L"} ou {"side": "R"}."""
    body = request.get_json(silent=True) or {}
    side = body.get('side', '').upper()
    if side not in ('L', 'R'):
        return jsonify({'error': 'side doit être "L" ou "R"'}), 400
    if reg.uart:
        reg.uart.send('VINV', side)
    return jsonify({'status': 'ok', 'side': side})
