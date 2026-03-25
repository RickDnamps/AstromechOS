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

# Index chargé une seule fois au démarrage
_INDEX_CACHE: dict = {}


def _get_index() -> dict:
    global _INDEX_CACHE
    if not _INDEX_CACHE:
        try:
            with open(_INDEX_FILE, encoding='utf-8') as f:
                _INDEX_CACHE = json.load(f)
        except Exception:
            _INDEX_CACHE = {}
    return _INDEX_CACHE


def _valid_sound(sound: str) -> bool:
    cats = _get_index().get('categories', {})
    return any(sound in sounds for sounds in cats.values())


def _valid_category(cat: str) -> bool:
    return cat in _get_index().get('categories', {})


@audio_bp.get('/categories')
def get_categories():
    """Liste des catégories avec nombre de sons."""
    try:
        cats = _get_index().get('categories', {})
        return jsonify({
            'categories': [{'name': k, 'count': len(v)} for k, v in cats.items()],
            'total': sum(len(v) for v in cats.values())
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@audio_bp.get('/index')
def get_index():
    """Retourne l'index complet {categories: {cat: [sounds]}}."""
    return jsonify({'categories': _get_index().get('categories', {})})


@audio_bp.get('/sounds')
def get_sounds():
    """Liste des sons d'une catégorie. Query: ?category=happy"""
    category = request.args.get('category', '').strip().lower()
    if not category:
        return jsonify({'error': 'Paramètre "category" requis'}), 400
    sounds = _get_index().get('categories', {}).get(category)
    if sounds is None:
        return jsonify({'error': f'Catégorie inconnue: {category}'}), 404
    return jsonify({'category': category, 'sounds': sounds})


@audio_bp.post('/play')
def play_sound():
    """Joue un son spécifique. Body: {"sound": "Happy001"}"""
    body = request.get_json(silent=True) or {}
    sound = body.get('sound', '').strip()
    if not sound:
        return jsonify({'error': 'Champ "sound" requis'}), 400
    if not _valid_sound(sound):
        return jsonify({'error': f'Son inconnu: {sound}'}), 404
    if reg.uart:
        reg.uart.send('S', sound)
    reg.audio_playing = True
    reg.audio_current = sound
    return jsonify({'status': 'ok', 'sound': sound})


@audio_bp.post('/random')
def play_random():
    """Joue un son aléatoire. Body: {"category": "happy"}"""
    body = request.get_json(silent=True) or {}
    category = body.get('category', 'happy').strip().lower()
    if not _valid_category(category):
        return jsonify({'error': f'Catégorie inconnue: {category}'}), 404
    if reg.uart:
        reg.uart.send('S', f'RANDOM:{category}')
    reg.audio_playing = True
    reg.audio_current = f'🎲 {category}'
    return jsonify({'status': 'ok', 'category': category})


@audio_bp.post('/stop')
def stop_audio():
    """Coupe le son en cours."""
    if reg.uart:
        reg.uart.send('S', 'STOP')
    reg.audio_playing = False
    reg.audio_current = ''
    return jsonify({'status': 'ok'})


@audio_bp.get('/volume')
def get_volume():
    """Retourne le volume actuel (0-100)."""
    return jsonify({'volume': getattr(reg, 'audio_volume', 80)})


@audio_bp.post('/volume')
def set_volume():
    """Règle le volume. Body: {"volume": 75}  (0-100)"""
    body = request.get_json(silent=True) or {}
    try:
        vol = max(0, min(100, int(body.get('volume', 80))))
    except (TypeError, ValueError):
        return jsonify({'error': 'volume doit être un entier 0-100'}), 400
    reg.audio_volume = vol
    if reg.uart:
        reg.uart.send('VOL', str(vol))
    return jsonify({'status': 'ok', 'volume': vol})
