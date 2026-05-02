# ============================================================
#  ██████╗ ██████╗       ██████╗ ██████╗
#  ██╔══██╗╚════██╗      ██╔══██╗╚════██╗
#  ██████╔╝ █████╔╝      ██║  ██║ █████╔╝
#  ██╔══██╗██╔═══╝       ██║  ██║██╔═══╝
#  ██║  ██║███████╗      ██████╔╝███████╗
#  ╚═╝  ╚═╝╚══════╝      ╚═════╝ ╚══════╝
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
Blueprint API Teeces — Phase 4.
Controls Teeces32 LEDs (PSI, logics, FLD) via local TeecesController.

Endpoints:
  POST /teeces/random           → random mode
  POST /teeces/leia             → Leia mode
  POST /teeces/off              → turn everything off
  POST /teeces/text             {"text": "HELLO"}
  POST /teeces/psi              {"mode": 1}
  GET  /teeces/animations       → list all known T-codes
  POST /teeces/animation        {"mode": 11}
  POST /teeces/raw              {"cmd": "0T5"}
  GET  /teeces/state
"""

from flask import Blueprint, request, jsonify
import master.registry as reg

teeces_bp = Blueprint('teeces', __name__, url_prefix='/teeces')

_mode = 'random'


@teeces_bp.post('/random')
def teeces_random():
    """Activates Teeces random animation mode."""
    global _mode
    _mode = 'random'
    if reg.teeces:
        reg.teeces.random_mode()
    return jsonify({'status': 'ok', 'mode': 'random'})


@teeces_bp.post('/leia')
def teeces_leia():
    """Activates Leia mode (holographic message)."""
    global _mode
    _mode = 'leia'
    if reg.teeces:
        reg.teeces.leia()
    return jsonify({'status': 'ok', 'mode': 'leia'})


@teeces_bp.post('/off')
def teeces_off():
    """Turns off all Teeces LEDs."""
    global _mode
    _mode = 'off'
    if reg.teeces:
        reg.teeces.off()
    return jsonify({'status': 'ok', 'mode': 'off'})


@teeces_bp.post('/text')
def teeces_text():
    """Displays text on FLD, RLD, or both. Body: {"text": "HELLO", "display": "fld"}"""
    body    = request.get_json(silent=True) or {}
    text    = body.get('text', '').strip()[:20]
    display = body.get('display', 'fld').lower()
    if reg.teeces:
        reg.teeces.text(text, display)
    return jsonify({'status': 'ok', 'text': text, 'display': display})


@teeces_bp.post('/psi')
def teeces_psi():
    """Controls the PSIs. Body: {"mode": 1}"""
    body = request.get_json(silent=True) or {}
    mode = int(body.get('mode', 1))
    if reg.teeces:
        reg.teeces.psi(mode)
    return jsonify({'status': 'ok', 'mode': mode})


@teeces_bp.post('/psi_seq')
def teeces_psi_seq():
    """PSI sequence control. Body: {"target": "both", "sequence": "normal"}
    target: both | fpsi | rpsi
    sequence: normal | flash | alarm | failure | redalert | leia | march
    """
    body     = request.get_json(silent=True) or {}
    target   = body.get('target',   'both').lower()
    sequence = body.get('sequence', 'normal').lower()
    if reg.teeces:
        if hasattr(reg.teeces, 'psi_seq'):
            reg.teeces.psi_seq(target, sequence)
        else:
            _TEECES_MAP = {'normal':1,'flash':1,'alarm':3,'redalert':3,'leia':1,'failure':1,'march':1}
            reg.teeces.psi(_TEECES_MAP.get(sequence, 1))
    return jsonify({'status': 'ok', 'target': target, 'sequence': sequence})


@teeces_bp.get('/animations')
def teeces_animations():
    """List all known T-code animations."""
    from master.lights.base_controller import BaseLightsController
    return jsonify({
        'animations': [
            {'mode': k, 'name': v}
            for k, v in BaseLightsController.ANIMATIONS.items()
        ]
    })


@teeces_bp.post('/animation')
def teeces_animation():
    """Trigger a T-code animation. Body: {"mode": 11}"""
    body = request.get_json(silent=True) or {}
    try:
        mode = int(body.get('mode', 1))
    except (TypeError, ValueError):
        return jsonify({'error': 'mode must be an integer'}), 400
    if reg.teeces:
        reg.teeces.animation(mode)
    from master.lights.base_controller import BaseLightsController
    name = BaseLightsController.ANIMATIONS.get(mode, f'T{mode}')
    return jsonify({'status': 'ok', 'mode': mode, 'name': name})


@teeces_bp.post('/raw')
def teeces_raw():
    """Send raw JawaLite command. Body: {"cmd": "0T5"}"""
    body = request.get_json(silent=True) or {}
    cmd = body.get('cmd', '').strip()
    if not cmd:
        return jsonify({'error': 'field "cmd" required'}), 400
    if reg.teeces:
        reg.teeces.raw(cmd)
    return jsonify({'status': 'ok', 'cmd': cmd})


@teeces_bp.get('/state')
def teeces_state():
    """Current Teeces state."""
    backend = type(reg.teeces).__name__.replace('Driver', '').lower() if reg.teeces else 'none'
    return jsonify({
        'mode':    _mode,
        'ready':   bool(reg.teeces and reg.teeces.is_ready()),
        'backend': backend,
    })
