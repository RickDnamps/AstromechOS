"""
Blueprint API Scripts — Phase 4.
Lance, arrête et liste les scripts de séquence R2-D2.

Endpoints:
  GET  /scripts/list              → liste des scripts disponibles
  GET  /scripts/running           → scripts en cours
  POST /scripts/run               {"name": "patrol", "loop": false}
  POST /scripts/stop              {"id": 3}
  POST /scripts/stop_all
"""

from flask import Blueprint, request, jsonify
import master.registry as reg

script_bp = Blueprint('scripts', __name__, url_prefix='/scripts')


@script_bp.get('/list')
def script_list():
    """Liste des scripts .scr disponibles."""
    scripts = reg.engine.list_scripts() if reg.engine else []
    return jsonify({'scripts': scripts})


@script_bp.get('/running')
def script_running():
    """Scripts en cours d'exécution."""
    running = reg.engine.list_running() if reg.engine else []
    return jsonify({'running': running})


@script_bp.post('/run')
def script_run():
    """Lance un script. Body: {"name": str, "loop": bool}"""
    body = request.get_json(silent=True) or {}
    name = body.get('name', '').strip()
    loop = bool(body.get('loop', False))

    if not name:
        return jsonify({'error': 'Champ "name" requis'}), 400
    if not reg.engine:
        return jsonify({'error': 'ScriptEngine non initialisé'}), 503

    script_id = reg.engine.run(name, loop=loop)
    if script_id is None:
        return jsonify({'error': f'Script "{name}" introuvable'}), 404
    return jsonify({'status': 'ok', 'id': script_id, 'name': name, 'loop': loop})


@script_bp.post('/stop')
def script_stop():
    """Arrête un script. Body: {"id": int}"""
    body      = request.get_json(silent=True) or {}
    script_id = body.get('id')
    if script_id is None:
        return jsonify({'error': 'Champ "id" requis'}), 400
    if reg.engine:
        ok = reg.engine.stop(int(script_id))
        return jsonify({'status': 'ok' if ok else 'not_found'})
    return jsonify({'error': 'ScriptEngine non initialisé'}), 503


@script_bp.post('/stop_all')
def script_stop_all():
    """Arrête tous les scripts en cours."""
    if reg.engine:
        reg.engine.stop_all()
    return jsonify({'status': 'ok'})
