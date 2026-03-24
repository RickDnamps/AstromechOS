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
  GET  /scripts/list              → liste des scripts disponibles (avec is_builtin)
  GET  /scripts/running           → scripts en cours
  POST /scripts/run               {"name": "patrol", "loop": false, "skip_motion": false}
  POST /scripts/stop              {"id": 3}
  POST /scripts/stop_all
  GET  /scripts/get               ?name=xxx → steps d'une séquence
  POST /scripts/save              {"name": str, "steps": [{cmd, args}, ...]}
  POST /scripts/delete            {"name": str}
  POST /scripts/rename            {"old": str, "new": str}
"""

import re
import subprocess
from pathlib import Path

from flask import Blueprint, request, jsonify
import master.registry as reg

script_bp = Blueprint('scripts', __name__, url_prefix='/scripts')

SEQUENCES_DIR = Path(__file__).parent.parent / 'sequences'
NAME_RE = re.compile(r'^[a-zA-Z0-9_\-]{1,64}$')


def _is_valid_name(name: str) -> bool:
    return bool(NAME_RE.match(name))


def _is_builtin(name: str) -> bool:
    """True if the .scr file is tracked by git (i.e. a built-in sequence)."""
    rel = f"master/sequences/{name}.scr"
    repo_root = Path(__file__).parent.parent.parent.parent  # r2d2/
    result = subprocess.run(
        ['git', 'ls-files', '--error-unmatch', rel],
        capture_output=True,
        cwd=str(repo_root),
    )
    return result.returncode == 0


def _parse_scr(path: Path) -> list[dict]:
    """Parse a .scr file into list of {cmd, args} dicts (skips comments/blanks)."""
    steps = []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                row = [c.strip() for c in line.split(',')]
                if not row or not row[0] or row[0].startswith('#'):
                    continue
                steps.append({'cmd': row[0], 'args': row[1:]})
    except Exception:
        pass
    return steps


def _is_running(name: str) -> bool:
    """True if any runner with this name is currently active."""
    if not reg.engine:
        return False
    return any(r['name'] == name for r in reg.engine.list_running())


@script_bp.get('/list')
def script_list():
    """Liste des scripts .scr disponibles avec flag is_builtin."""
    scripts = reg.engine.list_scripts() if reg.engine else []
    return jsonify({
        'scripts': [
            {'name': s, 'is_builtin': _is_builtin(s)}
            for s in scripts
        ]
    })


@script_bp.get('/running')
def script_running():
    """Scripts en cours d'exécution."""
    running = reg.engine.list_running() if reg.engine else []
    return jsonify({'running': running})


@script_bp.post('/run')
def script_run():
    """Lance un script. Body: {"name": str, "loop": bool, "skip_motion": bool}"""
    body = request.get_json(silent=True) or {}
    name = body.get('name', '').strip()
    loop = bool(body.get('loop', False))
    skip_motion = bool(body.get('skip_motion', False))

    if not name:
        return jsonify({'error': 'Champ "name" requis'}), 400
    if not reg.engine:
        return jsonify({'error': 'ScriptEngine non initialisé'}), 503

    script_id = reg.engine.run(name, loop=loop, skip_motion=skip_motion)
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


@script_bp.get('/get')
def script_get():
    """Charge une séquence. Query: ?name=xxx"""
    name = request.args.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Paramètre "name" requis'}), 400
    path = SEQUENCES_DIR / f"{name}.scr"
    if not path.is_file():
        return jsonify({'error': 'not found'}), 404
    return jsonify({
        'name': name,
        'is_builtin': _is_builtin(name),
        'steps': _parse_scr(path),
    })


@script_bp.post('/save')
def script_save():
    """Sauvegarde une séquence. Body: {"name": str, "steps": [{cmd, args}, ...]}"""
    body  = request.get_json(silent=True) or {}
    name  = body.get('name', '').strip()
    steps = body.get('steps', [])
    if not _is_valid_name(name):
        return jsonify({'error': 'invalid name'}), 400
    if not steps:
        return jsonify({'error': 'empty sequence'}), 400
    if _is_builtin(name):
        return jsonify({'error': 'built-in sequence cannot be overwritten'}), 403
    path = SEQUENCES_DIR / f"{name}.scr"
    lines = []
    for step in steps:
        cmd  = step.get('cmd', '')
        args = step.get('args', [])
        parts = [cmd] + [str(a) for a in args if str(a)]
        lines.append(','.join(parts))
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return jsonify({'status': 'ok'})


@script_bp.post('/delete')
def script_delete():
    """Supprime une séquence. Body: {"name": str}"""
    body = request.get_json(silent=True) or {}
    name = body.get('name', '').strip()
    path = SEQUENCES_DIR / f"{name}.scr"
    if not path.is_file():
        return jsonify({'error': 'not found'}), 404
    if _is_builtin(name):
        return jsonify({'error': 'built-in sequence cannot be deleted'}), 403
    path.unlink()
    return jsonify({'status': 'ok'})


@script_bp.post('/rename')
def script_rename():
    """Renomme une séquence. Body: {"old": str, "new": str}"""
    body     = request.get_json(silent=True) or {}
    old_name = body.get('old', '').strip()
    new_name = body.get('new', '').strip()
    if not _is_valid_name(old_name):
        return jsonify({'error': 'invalid old name'}), 400
    if not _is_valid_name(new_name):
        return jsonify({'error': 'invalid name'}), 400
    old_path = SEQUENCES_DIR / f"{old_name}.scr"
    if not old_path.is_file():
        return jsonify({'error': 'not found'}), 404
    if _is_running(old_name):
        return jsonify({'error': 'sequence is running'}), 409
    new_path = SEQUENCES_DIR / f"{new_name}.scr"
    old_path.rename(new_path)
    return jsonify({'status': 'ok'})
