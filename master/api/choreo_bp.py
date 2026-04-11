"""
Blueprint Flask — Choreography API
Routes: /choreo/play, /choreo/stop, /choreo/status,
        /choreo/list, /choreo/load, /choreo/save, /choreo/export_scr
"""
import json
import logging
import os
import time

from flask import Blueprint, jsonify, request
import master.registry as reg

log = logging.getLogger(__name__)
choreo_bp = Blueprint('choreo', __name__)

_CHOREO_DIR = os.path.join(os.path.dirname(__file__), '..', 'choreographies')


def _choreo_path(name: str) -> str:
    safe = os.path.basename(name).replace('..', '')
    if not safe.endswith('.chor'):
        safe += '.chor'
    return os.path.join(_CHOREO_DIR, safe)


@choreo_bp.get('/choreo/list')
def choreo_list():
    os.makedirs(_CHOREO_DIR, exist_ok=True)
    names = [
        f[:-5] for f in os.listdir(_CHOREO_DIR)
        if f.endswith('.chor')
    ]
    return jsonify(sorted(names))


@choreo_bp.get('/choreo/load')
def choreo_load():
    name = request.args.get('name', '')
    if not name:
        return jsonify({'error': 'name required'}), 400
    path = _choreo_path(name)
    if not os.path.exists(path):
        return jsonify({'error': 'not found'}), 404
    with open(path) as f:
        chor = json.load(f)
    # Migrate legacy audio2 track → unified audio track with ch=1
    tracks = chor.get('tracks', {})
    audio2 = tracks.pop('audio2', [])
    if audio2:
        audio = tracks.setdefault('audio', [])
        for ev in audio2:
            audio.append({**ev, 'ch': 1})
        tracks['audio'].sort(key=lambda e: e.get('t', 0))
    return jsonify(chor)


@choreo_bp.post('/choreo/save')
def choreo_save():
    data = request.get_json(silent=True) or {}
    chor = data.get('chor')
    if not chor or 'meta' not in chor:
        return jsonify({'error': 'invalid chor'}), 400
    name = chor['meta'].get('name', 'untitled')
    os.makedirs(_CHOREO_DIR, exist_ok=True)
    with open(_choreo_path(name), 'w') as f:
        json.dump(chor, f, indent=2)
    log.info(f"Choreo saved: {name}")
    return jsonify({'status': 'ok', 'name': name})


@choreo_bp.delete('/choreo/<name>')
def choreo_delete(name: str):
    """Delete a choreography file by name."""
    path = _choreo_path(name)
    if not os.path.exists(path):
        return jsonify({'error': 'not found'}), 404
    try:
        os.remove(path)
        log.info(f"Choreo deleted: {name}")
        return jsonify({'status': 'ok', 'name': name})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


_ARM_SERVOS   = ['Servo_S12', 'Servo_S13', 'Servo_S14', 'Servo_S15']
_BODY_PANELS  = [f'Servo_S{i}' for i in range(12)]   # S0–S11 — body panels only

# How long to wait (seconds) for servos to physically reach closed position
_SERVO_RESET_DELAY = 1.5


def _reset_servos():
    """Close arms + body panels (S0–S11) + dome panels before starting a new choreo."""
    from master.api.servo_bp import (
        _read_panels_cfg, _panel_angle, _panel_speed, DOME_SERVOS
    )
    cfg = _read_panels_cfg()

    # Close arm servos first (arms must retract before body panels move)
    for name in _ARM_SERVOS:
        angle = _panel_angle(name, 'close', cfg)
        speed = _panel_speed(name, cfg)
        if reg.servo:
            reg.servo.close(name, angle, speed)
        elif reg.uart:
            reg.uart.send('SRV', f'{name},{angle},{speed}')

    # Close body panels S0–S11 (not arms)
    for name in _BODY_PANELS:
        angle = _panel_angle(name, 'close', cfg)
        speed = _panel_speed(name, cfg)
        if reg.servo:
            reg.servo.close(name, angle, speed)
        elif reg.uart:
            reg.uart.send('SRV', f'{name},{angle},{speed}')

    # Close all dome panels
    if reg.dome_servo:
        for name in DOME_SERVOS:
            angle = _panel_angle(name, 'close', cfg)
            speed = _panel_speed(name, cfg)
            reg.dome_servo.close(name, angle, speed)


@choreo_bp.post('/choreo/play')
def choreo_play():
    if not reg.choreo:
        return jsonify({'error': 'choreo player not available'}), 503
    data = request.get_json(silent=True) or {}
    name = data.get('name', '')
    if not name:
        return jsonify({'error': 'name required'}), 400
    path = _choreo_path(name)
    if not os.path.exists(path):
        return jsonify({'error': f'choreography not found: {name}'}), 404
    with open(path) as f:
        chor = json.load(f)

    # If a choreo is already playing: stop it, reset all servos, then start the new one
    if reg.choreo.is_playing():
        log.info("Choreo already playing — stopping and resetting servos before starting '%s'", name)
        reg.choreo.stop()
        try:
            _reset_servos()
        except Exception:
            log.exception("Servo reset failed — continuing with choreo start anyway")
        time.sleep(_SERVO_RESET_DELAY)

    ok = reg.choreo.play(chor)
    if not ok:
        return jsonify({'error': 'already playing'}), 409
    return jsonify({'status': 'ok', 'name': name, 'duration': chor['meta']['duration']})


@choreo_bp.post('/choreo/stop')
def choreo_stop():
    if reg.choreo:
        reg.choreo.stop()
    return jsonify({'status': 'ok'})


@choreo_bp.get('/choreo/status')
def choreo_status():
    if not reg.choreo:
        return jsonify({'playing': False, 'name': None, 't_now': 0.0, 'duration': 0.0})
    return jsonify(reg.choreo.get_status())


@choreo_bp.post('/choreo/export_scr')
def choreo_export_scr():
    if not reg.choreo:
        return jsonify({'error': 'choreo player not available'}), 503
    data = request.get_json(silent=True) or {}
    name = data.get('name', '')
    path = _choreo_path(name)
    if not os.path.exists(path):
        return jsonify({'error': 'not found'}), 404
    with open(path) as f:
        chor = json.load(f)
    scr = reg.choreo.export_scr(chor)
    return jsonify({'status': 'ok', 'name': name, 'scr': scr})
