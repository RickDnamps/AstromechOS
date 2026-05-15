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
#  Copyright (C) 2026 RickDnamps
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

import re
from flask import Blueprint, request, jsonify
import master.registry as reg
from master.api._admin_auth import require_admin

teeces_bp = Blueprint('teeces', __name__, url_prefix='/teeces')

_mode = 'random'

# Strip every control char that JawaLite/AstroPixels interprets as a
# frame delimiter or escape — without this, `text="HI\r0T20"` would
# embed a fresh command in the middle of the FLD scroll buffer
# (audit finding H-3 2026-05-15). Whitelist printable ASCII only;
# the firmware doesn't support extended chars and Unicode raises
# anyway.
_TEECES_TEXT_RE = re.compile(r'[^ -~]')

# /teeces/raw command allowlist. Real JawaLite commands look like
# `<addr>T<mode>` or `<addr>M<text>` etc. The firmware Teeces also
# uses # for setup. Bound to the universe the lights/teeces module
# actually sends. (Audit finding H-2 2026-05-15.)
_TEECES_RAW_RE = re.compile(r'^[A-Za-z0-9 ,@#%&+*/.=:;_-]{1,32}$')


def _sanitize_text(raw: str) -> str:
    """Strip control characters + cap length 20 (FLD line max)."""
    return _TEECES_TEXT_RE.sub('', str(raw))[:20]


@teeces_bp.post('/random')
@require_admin
def teeces_random():
    """Activates Teeces random animation mode."""
    global _mode
    _mode = 'random'
    if reg.teeces:
        reg.teeces.random_mode()
    return jsonify({'status': 'ok', 'mode': 'random'})


@teeces_bp.post('/leia')
@require_admin
def teeces_leia():
    """Activates Leia mode (holographic message)."""
    global _mode
    _mode = 'leia'
    if reg.teeces:
        reg.teeces.leia()
    return jsonify({'status': 'ok', 'mode': 'leia'})


@teeces_bp.post('/off')
@require_admin
def teeces_off():
    """Turns off all Teeces LEDs."""
    global _mode
    _mode = 'off'
    if reg.teeces:
        reg.teeces.off()
    return jsonify({'status': 'ok', 'mode': 'off'})


@teeces_bp.post('/text')
@require_admin
def teeces_text():
    """Displays text on FLD, RLD, or both. Body: {"text": "HELLO", "display": "fld"}
    Control characters (\\r, \\n, \\x00) are stripped before the
    command is built — without this, an embedded \\r terminates the
    FLD frame early and the rest of the operator's string runs as a
    fresh JawaLite command (audit H-3 2026-05-15)."""
    body    = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    text    = _sanitize_text(body.get('text', ''))
    display = str(body.get('display', 'fld')).lower()
    if display not in ('fld', 'rld', 'both'):
        return jsonify({'error': "display must be 'fld', 'rld', or 'both'"}), 400
    if reg.teeces:
        reg.teeces.text(text, display)
    return jsonify({'status': 'ok', 'text': text, 'display': display})


@teeces_bp.post('/psi')
@require_admin
def teeces_psi():
    """Controls the PSIs. Body: {"mode": 1}"""
    body = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    try:
        mode = int(body.get('mode', 1))
    except (TypeError, ValueError):
        return jsonify({'error': 'mode must be an integer'}), 400
    if reg.teeces:
        reg.teeces.psi(mode)
    return jsonify({'status': 'ok', 'mode': mode})


@teeces_bp.post('/psi_seq')
@require_admin
def teeces_psi_seq():
    """PSI sequence control. Body: {"target": "both", "sequence": "normal"}
    target: both | fpsi | rpsi
    sequence: normal | flash | alarm | failure | redalert | leia | march
    """
    body     = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    target   = str(body.get('target',   'both')).lower()
    sequence = str(body.get('sequence', 'normal')).lower()
    if target not in ('both', 'fpsi', 'rpsi'):
        return jsonify({'error': "target must be 'both', 'fpsi', or 'rpsi'"}), 400
    if sequence not in ('normal', 'flash', 'alarm', 'failure', 'redalert', 'leia', 'march'):
        return jsonify({'error': 'unknown sequence'}), 400
    if reg.teeces:
        if hasattr(reg.teeces, 'psi_seq'):
            reg.teeces.psi_seq(target, sequence)
        else:
            _TEECES_MAP = {'normal':1,'flash':1,'alarm':3,'redalert':3,'leia':1,'failure':1,'march':1}
            reg.teeces.psi(_TEECES_MAP.get(sequence, 1))
    return jsonify({'status': 'ok', 'target': target, 'sequence': sequence})


@teeces_bp.get('/animations')
def teeces_animations():
    """List all known T-code animations. LAN-open: read-only metadata."""
    from master.lights.base_controller import BaseLightsController
    return jsonify({
        'animations': [
            {'mode': k, 'name': v}
            for k, v in BaseLightsController.ANIMATIONS.items()
        ]
    })


@teeces_bp.post('/animation')
@require_admin
def teeces_animation():
    """Trigger a T-code animation. Body: {"mode": 11}"""
    body = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    try:
        mode = int(body.get('mode', 1))
    except (TypeError, ValueError):
        return jsonify({'error': 'mode must be an integer'}), 400
    from master.lights.base_controller import BaseLightsController
    if mode not in BaseLightsController.ANIMATIONS:
        return jsonify({'error': f'unknown animation mode {mode}'}), 400
    if reg.teeces:
        reg.teeces.animation(mode)
    name = BaseLightsController.ANIMATIONS.get(mode, f'T{mode}')
    return jsonify({'status': 'ok', 'mode': mode, 'name': name})


@teeces_bp.post('/raw')
@require_admin
def teeces_raw():
    """Send raw JawaLite command. Body: {"cmd": "0T5"}
    Admin-only + strict allowlist regex + 32-char cap. Without these,
    a POST `{"cmd": "0T1\\r0T999\\r..."}` would inject an unbounded
    command stream into the serial bus (audit H-2 2026-05-15)."""
    body = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    cmd = str(body.get('cmd', '')).strip()
    if not cmd:
        return jsonify({'error': 'field "cmd" required'}), 400
    if not _TEECES_RAW_RE.match(cmd):
        return jsonify({'error': 'invalid cmd — alphanumeric + JawaLite operators only, ≤32 chars'}), 400
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
