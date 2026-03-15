"""
Blueprint API Audio — Phase 4.
Proxy les commandes audio vers le Slave via UART.

Endpoints:
  POST /audio/play          {"sound": "Happy001"}
  POST /audio/random        {"category": "happy"}
  POST /audio/stop
  GET  /audio/categories    → liste des catégories
"""

import json
import os
from flask import Blueprint, request, jsonify
import master.registry as reg

audio_bp = Blueprint('audio', __name__, url_prefix='/audio')

_INDEX_FILE = os.path.join(
    os.path.dirname(__file__), '..', '..', 'slave', 'sounds', 'sounds_index.json'
)


@audio_bp.get('/categories')
def get_categories():
    """Liste des catégories de sons disponibles."""
    try:
        with open(_INDEX_FILE, encoding='utf-8') as f:
            data = json.load(f)
        categories = {k: len(v) for k, v in data.get('categories', {}).items()}
        return jsonify({'categories': categories, 'total': data.get('total', 0)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@audio_bp.post('/play')
def play_sound():
    """Joue un son spécifique. Body: {"sound": "Happy001"}"""
    body = request.get_json(silent=True) or {}
    sound = body.get('sound', '').strip()
    if not sound:
        return jsonify({'error': 'Champ "sound" requis'}), 400
    if reg.uart:
        reg.uart.send('S', sound)
    return jsonify({'status': 'ok', 'sound': sound})


@audio_bp.post('/random')
def play_random():
    """Joue un son aléatoire. Body: {"category": "happy"}"""
    body = request.get_json(silent=True) or {}
    category = body.get('category', 'happy').strip().lower()
    if reg.uart:
        reg.uart.send('S', f'RANDOM:{category}')
    return jsonify({'status': 'ok', 'category': category})


@audio_bp.post('/stop')
def stop_audio():
    """Coupe le son en cours."""
    if reg.uart:
        reg.uart.send('S', 'STOP')
    return jsonify({'status': 'ok'})
