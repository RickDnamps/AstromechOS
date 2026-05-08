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
Blueprint API Audio — Phase 4.
Proxies audio commands to the Slave via UART.

Endpoints:
  POST /audio/play          {"sound": "Happy001"}
  POST /audio/random        {"category": "happy"}
  POST /audio/stop
  GET  /audio/categories    → list of categories
"""

import configparser
import json
import logging
import os
import re
import threading
from pathlib import Path
from flask import Blueprint, request, jsonify, send_file, abort
import requests as _requests
import master.registry as reg

from shared.paths import MAIN_CFG as _MAIN_CFG, LOCAL_CFG as _LOCAL_CFG, SLAVE_SOUNDS as _SLAVE_SOUNDS


def _slave_host() -> str:
    cfg = configparser.ConfigParser()
    cfg.read([_MAIN_CFG, _LOCAL_CFG])
    return cfg.get('slave', 'host', fallback='r2-slave.local')

log = logging.getLogger(__name__)
_upload_lock = threading.Lock()
_play_timer: threading.Timer | None = None


def _get_sound_duration_ms(sound: str, fallback_ms: int = 60000) -> int:
    """Estimate MP3 duration from file size (assumes ~128 kbps CBR). Returns ms."""
    path = os.path.join(_SOUNDS_DIR, sound + '.mp3')
    if not os.path.isfile(path):
        return fallback_ms
    try:
        size = os.path.getsize(path)
        return int(size * 8 / 128) + 800   # 128 kbps + 800ms buffer
    except Exception:
        return fallback_ms


def _schedule_audio_reset(duration_ms: int) -> None:
    global _play_timer
    if _play_timer and _play_timer.is_alive():
        _play_timer.cancel()

    def _reset():
        reg.audio_playing = False
        reg.audio_current = ''

    _play_timer = threading.Timer(duration_ms / 1000.0, _reset)
    _play_timer.daemon = True
    _play_timer.start()

_SOUNDS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', '..', 'slave', 'sounds')
)

audio_bp = Blueprint('audio', __name__, url_prefix='/audio')

_INDEX_FILE = os.path.join(
    os.path.dirname(__file__), '..', '..', 'slave', 'sounds', 'sounds_index.json'
)

# Index loaded once at startup
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
    """List of categories with sound count."""
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
    """Returns the full index {categories: {cat: [sounds]}}."""
    return jsonify({'categories': _get_index().get('categories', {})})


@audio_bp.get('/sounds')
def get_sounds():
    """List of sounds for a category. Query: ?category=happy"""
    category = request.args.get('category', '').strip().lower()
    if not category:
        return jsonify({'error': 'Parameter "category" required'}), 400
    sounds = _get_index().get('categories', {}).get(category)
    if sounds is None:
        return jsonify({'error': f'Unknown category: {category}'}), 404
    return jsonify({'category': category, 'sounds': sounds})


@audio_bp.post('/play')
def play_sound():
    """Plays a specific sound. Body: {"sound": "Happy001"}"""
    body = request.get_json(silent=True) or {}
    sound = body.get('sound', '').strip()
    if not sound:
        return jsonify({'error': 'Field "sound" required'}), 400
    if not _valid_sound(sound):
        return jsonify({'error': f'Unknown sound: {sound}'}), 404
    if reg.uart:
        reg.uart.send('S', sound)
    reg.audio_playing = True
    reg.audio_current = sound
    _schedule_audio_reset(_get_sound_duration_ms(sound))
    return jsonify({'status': 'ok', 'sound': sound})


@audio_bp.post('/random')
def play_random():
    """Plays a random sound. Body: {"category": "happy"}"""
    body = request.get_json(silent=True) or {}
    category = body.get('category', 'happy').strip().lower()
    if not _valid_category(category):
        return jsonify({'error': f'Unknown category: {category}'}), 404
    if reg.uart:
        reg.uart.send('S', f'RANDOM:{category}')
    reg.audio_playing = True
    reg.audio_current = f'🎲 {category}'
    _schedule_audio_reset(60000)  # random duration unknown — 60s max
    return jsonify({'status': 'ok', 'category': category})


@audio_bp.get('/scan')
def scan_sounds():
    """Scan slave/sounds/ for all .mp3 files on disk — authoritative list regardless of index."""
    try:
        files = sorted(p.stem for p in Path(_SOUNDS_DIR).glob('*.mp3') if p.is_file())
        return jsonify({'sounds': files, 'count': len(files)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@audio_bp.get('/file/<sound>')
def stream_sound_file(sound):
    """Serve an MP3 from slave/sounds/ so the browser can read its duration.
    Only used by the Choreo editor — not for playback (playback goes through UART)."""
    if not sound.replace('_', '').replace('-', '').isalnum():
        abort(400)
    filepath = os.path.join(_SOUNDS_DIR, sound + '.mp3')
    if not os.path.isfile(filepath):
        abort(404)
    return send_file(filepath, mimetype='audio/mpeg', conditional=True)


@audio_bp.post('/stop')
def stop_audio():
    """Stops the current sound."""
    if _play_timer and _play_timer.is_alive():
        _play_timer.cancel()
    if reg.uart:
        reg.uart.send('S', 'STOP')
    reg.audio_playing = False
    reg.audio_current = ''
    return jsonify({'status': 'ok'})


@audio_bp.get('/volume')
def get_volume():
    """Returns the current volume (0-100)."""
    return jsonify({'volume': getattr(reg, 'audio_volume', 80)})


@audio_bp.post('/volume')
def set_volume():
    """Sets the volume. Body: {"volume": 75}  (0-100)"""
    body = request.get_json(silent=True) or {}
    try:
        vol = max(0, min(100, int(body.get('volume', 80))))
    except (TypeError, ValueError):
        return jsonify({'error': 'volume must be an integer 0-100'}), 400
    reg.audio_volume = vol
    if reg.uart:
        reg.uart.send('VOL', str(vol))
    return jsonify({'status': 'ok', 'volume': vol})


@audio_bp.post('/upload')
def upload_sound():
    """Upload an MP3 to a category.
    Form fields: file (MP3), category (str).
    Saves to slave/sounds/, updates sounds_index.json, syncs to slave via SFTP.
    """
    f = request.files.get('file')
    category = (request.form.get('category') or '').strip().lower()

    if not f or not f.filename:
        return jsonify({'ok': False, 'error': 'No file provided'}), 400
    if not category:
        return jsonify({'ok': False, 'error': 'No category provided'}), 400

    # Sanitize filename — uppercase, alphanumeric + underscore only
    stem = re.sub(r'[^A-Za-z0-9_]', '_', Path(f.filename).stem).strip('_')
    stem = re.sub(r'_+', '_', stem).upper()
    if not stem:
        return jsonify({'ok': False, 'error': 'Invalid filename'}), 400
    if not f.filename.lower().endswith('.mp3'):
        return jsonify({'ok': False, 'error': 'Only .mp3 files accepted'}), 400

    dest_path = os.path.join(_SOUNDS_DIR, stem + '.mp3')

    with _upload_lock:
        # Save file locally (slave/sounds/ is shared between PC dev and Pi via git-ignored)
        os.makedirs(_SOUNDS_DIR, exist_ok=True)
        f.save(dest_path)

        # Update sounds_index.json
        try:
            index = json.loads(Path(_INDEX_FILE).read_text(encoding='utf-8'))
        except Exception:
            index = {'categories': {}}
        cats = index.setdefault('categories', {})
        sounds = cats.setdefault(category, [])
        if stem not in sounds:
            sounds.append(stem)
            sounds.sort()
        Path(_INDEX_FILE).write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding='utf-8')
        global _INDEX_CACHE
        _INDEX_CACHE = index  # refresh in-memory cache

        # Sync to slave via SFTP
        _sftp_sync_sound(dest_path, stem, index)

    return jsonify({'ok': True, 'filename': stem, 'category': category})


@audio_bp.post('/category/create')
def create_category():
    """Create a new empty audio category. Body: {"name": "mycat"}"""
    body = request.get_json(silent=True) or {}
    name = (body.get('name') or '').strip().lower()
    if not name or not re.match(r'^[a-z0-9_]+$', name):
        return jsonify({'ok': False, 'error': 'Invalid category name'}), 400

    with _upload_lock:
        try:
            index = json.loads(Path(_INDEX_FILE).read_text(encoding='utf-8'))
        except Exception:
            index = {'categories': {}}
        cats = index.setdefault('categories', {})
        if name in cats:
            return jsonify({'ok': False, 'error': f'Category "{name}" already exists'}), 409
        cats[name] = []
        Path(_INDEX_FILE).write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding='utf-8')
        global _INDEX_CACHE
        _INDEX_CACHE = index
        # Sync index to slave
        _sftp_sync_index(index)

    return jsonify({'ok': True, 'name': name})


def _sftp_sync_index(index: dict) -> None:
    """Sync sounds_index.json to slave."""
    try:
        import paramiko, io
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect('192.168.4.171', username='artoo', password='deetoo', timeout=8)
        sftp = c.open_sftp()
        data = json.dumps(index, indent=2, ensure_ascii=False).encode('utf-8')
        sftp.putfo(io.BytesIO(data), f'{_SLAVE_SOUNDS}/sounds_index.json')
        sftp.close(); c.close()
    except Exception as e:
        log.warning(f'SFTP index sync failed: {e}')


def _sftp_sync_sound(local_mp3: str, stem: str, index: dict) -> None:
    """SFTP the new MP3 and updated index to the slave Pi."""
    try:
        import paramiko, io
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect('192.168.4.171', username='artoo', password='deetoo', timeout=8)
        sftp = c.open_sftp()
        remote_sounds = _SLAVE_SOUNDS
        sftp.put(local_mp3, f'{remote_sounds}/{stem}.mp3')
        data = json.dumps(index, indent=2, ensure_ascii=False).encode('utf-8')
        sftp.putfo(io.BytesIO(data), f'{remote_sounds}/sounds_index.json')
        sftp.close(); c.close()
        log.info(f'Audio upload: synced {stem}.mp3 to slave')
    except Exception as e:
        log.warning(f'Audio upload: SFTP sync failed — {e}. File saved locally only.')


# ── BT Speaker proxy (forwards to slave port 5001) ────────────────────────────

def _slave_bt(path: str, method: str = 'GET', body: dict | None = None):
    """Forward a BT request to the slave health server."""
    url = f'http://{_slave_host()}:5001{path}'
    try:
        if method == 'POST':
            r = _requests.post(url, json=body or {}, timeout=12)
        else:
            r = _requests.get(url, timeout=12)
        return r.json(), r.status_code
    except Exception as e:
        return {'ok': False, 'error': str(e)}, 503


@audio_bp.get('/bt/status')
def bt_speaker_status():
    data, code = _slave_bt('/audio/bt/status')
    return jsonify(data), code


@audio_bp.post('/bt/scan')
def bt_speaker_scan():
    data, code = _slave_bt('/audio/bt/scan', 'POST')
    return jsonify(data), code


@audio_bp.post('/bt/pair')
def bt_speaker_pair():
    body = request.get_json(silent=True) or {}
    data, code = _slave_bt('/audio/bt/pair', 'POST', body)
    return jsonify(data), code


@audio_bp.post('/bt/connect')
def bt_speaker_connect():
    body = request.get_json(silent=True) or {}
    data, code = _slave_bt('/audio/bt/connect', 'POST', body)
    return jsonify(data), code


@audio_bp.post('/bt/disconnect')
def bt_speaker_disconnect():
    body = request.get_json(silent=True) or {}
    data, code = _slave_bt('/audio/bt/disconnect', 'POST', body)
    return jsonify(data), code


@audio_bp.post('/bt/remove')
def bt_speaker_remove():
    body = request.get_json(silent=True) or {}
    data, code = _slave_bt('/audio/bt/remove', 'POST', body)
    return jsonify(data), code


@audio_bp.post('/bt/volume')
def bt_speaker_volume():
    body = request.get_json(silent=True) or {}
    data, code = _slave_bt('/audio/bt/volume', 'POST', body)
    return jsonify(data), code
