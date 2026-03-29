"""
Blueprint Flask — Choreography API
Routes: /choreo/play, /choreo/stop, /choreo/status,
        /choreo/list, /choreo/load, /choreo/save, /choreo/export_scr
"""
import json
import logging
import os

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
        return jsonify(json.load(f))


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
