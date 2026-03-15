"""
Blueprint API Servo — Phase 4.
Contrôle les servos body via le Slave.

Endpoints:
  POST /servo/move          {"name": "utility_arm_left", "position": 1.0, "duration": 500}
  POST /servo/open          {"name": "utility_arm_left"}
  POST /servo/close         {"name": "utility_arm_left"}
  POST /servo/open_all
  POST /servo/close_all
  GET  /servo/list          → liste des servos connus
  GET  /servo/state         → positions courantes
"""

from flask import Blueprint, request, jsonify
import master.registry as reg

servo_bp = Blueprint('servo', __name__, url_prefix='/servo')

# Servos connus (identiques à body_servo_driver.py)
KNOWN_SERVOS = [
    'utility_arm_left', 'utility_arm_right',
    'panel_front_top',  'panel_front_bottom',
    'panel_rear_top',   'panel_rear_bottom',
    'charge_bay',       'dome_hatch',
]


@servo_bp.get('/list')
def servo_list():
    """Liste des servos disponibles."""
    return jsonify({'servos': KNOWN_SERVOS})


@servo_bp.get('/state')
def servo_state():
    """Positions courantes des servos."""
    state = reg.servo.state if reg.servo else {}
    return jsonify(state)


@servo_bp.post('/move')
def servo_move():
    """Déplace un servo. Body: {"name": str, "position": float, "duration": int}"""
    body     = request.get_json(silent=True) or {}
    name     = body.get('name', '')
    position = float(body.get('position', 0.0))
    duration = int(body.get('duration', 500))

    if not name:
        return jsonify({'error': 'Champ "name" requis'}), 400

    if reg.servo:
        reg.servo.move(name, position, duration)
    elif reg.uart:
        reg.uart.send('SRV', f'{name},{position:.3f},{duration}')
    return jsonify({'status': 'ok', 'name': name, 'position': position})


@servo_bp.post('/open')
def servo_open():
    """Ouvre un servo. Body: {"name": str, "duration": int}"""
    body     = request.get_json(silent=True) or {}
    name     = body.get('name', '')
    duration = int(body.get('duration', 500))
    if not name:
        return jsonify({'error': 'Champ "name" requis'}), 400
    if reg.servo:
        reg.servo.open(name, duration)
    elif reg.uart:
        reg.uart.send('SRV', f'{name},1.000,{duration}')
    return jsonify({'status': 'ok', 'name': name})


@servo_bp.post('/close')
def servo_close():
    """Ferme un servo. Body: {"name": str, "duration": int}"""
    body     = request.get_json(silent=True) or {}
    name     = body.get('name', '')
    duration = int(body.get('duration', 500))
    if not name:
        return jsonify({'error': 'Champ "name" requis'}), 400
    if reg.servo:
        reg.servo.close(name, duration)
    elif reg.uart:
        reg.uart.send('SRV', f'{name},0.000,{duration}')
    return jsonify({'status': 'ok', 'name': name})


@servo_bp.post('/open_all')
def servo_open_all():
    """Ouvre tous les servos."""
    duration = int((request.get_json(silent=True) or {}).get('duration', 500))
    if reg.servo:
        reg.servo.open_all(duration)
    return jsonify({'status': 'ok'})


@servo_bp.post('/close_all')
def servo_close_all():
    """Ferme tous les servos."""
    duration = int((request.get_json(silent=True) or {}).get('duration', 500))
    if reg.servo:
        reg.servo.close_all(duration)
    return jsonify({'status': 'ok'})
