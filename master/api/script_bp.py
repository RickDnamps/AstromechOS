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
