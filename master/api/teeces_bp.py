"""
Blueprint API Teeces — Phase 4.
Contrôle les LEDs Teeces32 (PSI, logics, FLD) via TeecesController local.

Endpoints:
  POST /teeces/random           → mode aléatoire
  POST /teeces/leia             → mode Leia
  POST /teeces/off              → tout éteindre
  POST /teeces/text             {"text": "HELLO"}
  POST /teeces/psi              {"mode": 1}
  GET  /teeces/state
"""

from flask import Blueprint, request, jsonify
import master.registry as reg

teeces_bp = Blueprint('teeces', __name__, url_prefix='/teeces')

_mode = 'random'


@teeces_bp.post('/random')
def teeces_random():
    """Active le mode animation aléatoire Teeces."""
    global _mode
    _mode = 'random'
    if reg.teeces:
        reg.teeces.random_mode()
    return jsonify({'status': 'ok', 'mode': 'random'})


@teeces_bp.post('/leia')
def teeces_leia():
    """Active le mode Leia (message holographique)."""
    global _mode
    _mode = 'leia'
    if reg.teeces:
        reg.teeces.leia_mode()
    return jsonify({'status': 'ok', 'mode': 'leia'})


@teeces_bp.post('/off')
def teeces_off():
    """Éteint toutes les LEDs Teeces."""
    global _mode
    _mode = 'off'
    if reg.teeces:
        reg.teeces.all_off()
    return jsonify({'status': 'ok', 'mode': 'off'})


@teeces_bp.post('/text')
def teeces_text():
    """Affiche un texte sur le FLD. Body: {"text": "HELLO"}"""
    body = request.get_json(silent=True) or {}
    text = body.get('text', '').strip()[:20]  # max 20 chars
    if reg.teeces:
        reg.teeces.fld_text(text)
    return jsonify({'status': 'ok', 'text': text})


@teeces_bp.post('/psi')
def teeces_psi():
    """Contrôle les PSI. Body: {"mode": 1}"""
    body = request.get_json(silent=True) or {}
    mode = int(body.get('mode', 1))
    if reg.teeces:
        reg.teeces.psi_mode(mode)
    return jsonify({'status': 'ok', 'mode': mode})


@teeces_bp.get('/state')
def teeces_state():
    """État courant des Teeces."""
    return jsonify({
        'mode':  _mode,
        'ready': bool(reg.teeces and reg.teeces.is_ready()),
    })
