# ============================================================
#   █████╗  ██████╗ ███████╗
#  ██╔══██╗██╔═══██╗██╔════╝
#  ███████║██║   ██║███████╗
#  ██╔══██║██║   ██║╚════██║
#  ██║  ██║╚██████╔╝███████║
#  ╚═╝  ╚═╝ ╚═════╝ ╚══════╝
#
#  AstromechOS — Open control platform for astromech builders
# ============================================================
#  Copyright (C) 2025 RickDnamps
#  https://github.com/RickDnamps/AstromechOS
#
#  This file is part of AstromechOS.
#
#  AstromechOS is free software: you can redistribute it
#  and/or modify it under the terms of the GNU General
#  Public License as published by the Free Software
#  Foundation, either version 2 of the License, or
#  (at your option) any later version.
#
#  AstromechOS is distributed in the hope that it will be
#  useful, but WITHOUT ANY WARRANTY; without even the implied
#  warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
#  PURPOSE. See the GNU General Public License for details.
#
#  You should have received a copy of the GNU GPL along with
#  AstromechOS. If not, see <https://www.gnu.org/licenses/>.
# ============================================================
"""
Blueprint API Light Sequences — R2-D2 Light Show.
CRUD + run/stop for .lseq files (Teeces/sleep sequences).

Endpoints:
  GET  /light/list              → list of .lseq files
  GET  /light/get               ?name=xxx → steps
  POST /light/save              {"name": str, "steps": [{cmd, args}]}
  POST /light/delete            {"name": str}
  POST /light/run               {"name": str, "loop": false}
  POST /light/stop              {"id": int}
  POST /light/stop_all
"""
import logging
import re
from pathlib import Path

from flask import Blueprint, request, jsonify
import master.registry as reg

log = logging.getLogger(__name__)

light_bp = Blueprint('light', __name__, url_prefix='/light')

LIGHT_DIR = Path(__file__).parent.parent / 'light_sequences'
NAME_RE   = re.compile(r'^[a-zA-Z0-9_\-]{1,64}$')


def _valid(name: str) -> bool:
    return bool(NAME_RE.match(name))


def _parse_lseq(path: Path) -> list[dict]:
    steps = []
    try:
        with open(path, encoding='utf-8') as f:
            for line in f:
                row = [c.strip() for c in line.split(',')]
                if not row or not row[0] or row[0].startswith('#'):
                    continue
                steps.append({'cmd': row[0], 'args': row[1:]})
    except Exception:
        pass
    return steps


@light_bp.get('/list')
def light_list():
    LIGHT_DIR.mkdir(exist_ok=True)
    names = sorted(p.stem for p in LIGHT_DIR.glob('*.lseq'))
    return jsonify({'sequences': names})


@light_bp.get('/get')
def light_get():
    name = request.args.get('name', '').strip()
    if not name or not _valid(name):
        return jsonify({'error': 'invalid name'}), 400
    path = LIGHT_DIR / f'{name}.lseq'
    if not path.is_file():
        return jsonify({'error': 'not found'}), 404
    return jsonify({'name': name, 'steps': _parse_lseq(path)})


@light_bp.post('/save')
def light_save():
    body  = request.get_json(silent=True) or {}
    name  = body.get('name', '').strip()
    steps = body.get('steps', [])
    if not _valid(name):
        return jsonify({'error': 'invalid name'}), 400
    if not steps:
        return jsonify({'error': 'empty sequence'}), 400
    LIGHT_DIR.mkdir(exist_ok=True)
    path  = LIGHT_DIR / f'{name}.lseq'
    lines = []
    for step in steps:
        cmd  = step.get('cmd', '')
        args = [str(a) for a in step.get('args', []) if str(a)]
        if cmd:
            lines.append(','.join([cmd] + args))
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    log.info('Light sequence saved: %s (%d steps)', name, len(lines))
    return jsonify({'status': 'ok', 'name': name})


@light_bp.post('/delete')
def light_delete():
    body = request.get_json(silent=True) or {}
    name = body.get('name', '').strip()
    if not _valid(name):
        return jsonify({'error': 'invalid name'}), 400
    path = LIGHT_DIR / f'{name}.lseq'
    if not path.is_file():
        return jsonify({'error': 'not found'}), 404
    path.unlink()
    return jsonify({'status': 'ok'})


@light_bp.post('/run')
def light_run():
    body = request.get_json(silent=True) or {}
    name = body.get('name', '').strip()
    loop = bool(body.get('loop', False))
    if not name:
        return jsonify({'error': 'field "name" required'}), 400
    if not reg.engine:
        return jsonify({'error': 'ScriptEngine not initialized'}), 503
    script_id = reg.engine.run_light(name, loop=loop)
    if script_id is None:
        return jsonify({'error': f'Light sequence "{name}" not found'}), 404
    return jsonify({'status': 'ok', 'id': script_id, 'name': name})


@light_bp.post('/stop')
def light_stop():
    body = request.get_json(silent=True) or {}
    sid  = body.get('id')
    if sid is None:
        return jsonify({'error': 'field "id" required'}), 400
    if reg.engine:
        ok = reg.engine.stop(int(sid))
        return jsonify({'status': 'ok' if ok else 'not_found'})
    return jsonify({'error': 'ScriptEngine not initialized'}), 503


@light_bp.post('/stop_all')
def light_stop_all():
    """Stop only light sequences — does NOT stop regular sequences or audio."""
    if reg.engine:
        reg.engine.stop_light_all()
    return jsonify({'status': 'ok'})
