"""
Blueprint API Bluetooth Controller — Config et statut.

Endpoints:
  GET  /bt/status          → état connexion + config actuelle
  POST /bt/enable          {"enabled": bool}
  POST /bt/config          {"gamepad_type": str, "deadzone": float, "inactivity_timeout": int, "mappings": {...}}
  POST /bt/estop_reset     → réarme après E-Stop (remet estop_active = False)
"""

from flask import Blueprint, request, jsonify
import master.registry as reg

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
