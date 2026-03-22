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
