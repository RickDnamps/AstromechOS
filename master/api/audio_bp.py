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


def _slave_sftp_creds() -> dict:
    """Read slave SFTP credentials from cfg. Replaces the hardcoded
    `192.168.4.171 / artoo / deetoo` previously baked into _sftp_sync_*
    — that broke every install except the original one (violated project
    rule feedback_no_hardcoded_install_values).

    Returns a dict suitable for paramiko.SSHClient.connect():
      { 'hostname': str, 'username': str,
        'password': str | None, 'timeout': float }

    Falls back to the configured deploy.slave_user. Password is read
    from local.cfg [deploy] slave_password if set — kept OUT of main.cfg
    so it never ships to git. If no password is provided, paramiko falls
    back to key-based auth (the project's normal Pi-to-Pi SSH path)."""
    cfg = configparser.ConfigParser()
    cfg.read([_MAIN_CFG, _LOCAL_CFG])
    host = cfg.get('slave', 'host', fallback=None) \
        or cfg.get('deploy', 'slave_host', fallback='r2-slave.local')
    user = cfg.get('deploy', 'slave_user', fallback='artoo')
    pwd  = cfg.get('deploy', 'slave_password', fallback=None) or None
    creds = {'hostname': host, 'username': user, 'timeout': 8.0}
    if pwd:
        creds['password'] = pwd
    return creds


log = logging.getLogger(__name__)
_upload_lock = threading.Lock()
_play_timer: threading.Timer | None = None
# Protects _play_timer and _INDEX_CACHE writes against concurrent
# requests. Globals were previously assigned without any synchronisation
# (B-10) — two simultaneous /audio/play requests could orphan a timer or
# clobber the in-memory index mid-rebuild.
_audio_state_lock = threading.Lock()

# Strict filename allow-list — only the characters actually present in
# the existing 317 R2-D2 sound files. Excludes hyphen (the upload
# sanitizer collapses it to '_') so the validation here matches what
# the upload path produces. Length cap 80 chars: more than enough for
# the longest real name (PROCESS_SUCCESS_LONG = 19), bounded against
# filesystem absurdities.
_SOUND_NAME_RE = re.compile(r'^[A-Za-z0-9_]{1,80}$')
_CATEGORY_NAME_RE = re.compile(r'^[a-z0-9_]{1,32}$')


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
    """Reset the reg.audio_playing flag after duration_ms.

    B-10: serialized via _audio_state_lock so two near-simultaneous
    /audio/play requests can't orphan a timer (thread A reads is_alive()
    False, B sets a new timer, A overwrites — A's reset fires later
    while B's sound is still playing, flickering the UI badge off)."""
    global _play_timer
    with _audio_state_lock:
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
_SOUNDS_DIR_REAL = os.path.realpath(_SOUNDS_DIR)


def _safe_sound_path(sound: str) -> str | None:
    """Validate a user-supplied sound name and resolve it to an absolute
    path inside _SOUNDS_DIR.

    Returns the resolved path on success, or None if the name fails
    validation. Defense layers:
      1. Strict ASCII allowlist via _SOUND_NAME_RE — rejects Unicode
         letters/digits that str.isalnum() previously accepted (B-1).
      2. realpath containment check — ensures the resolved file is
         actually inside _SOUNDS_DIR, even if some future path
         manipulation slips through layer 1.

    Used by /audio/file/<sound> (serve MP3 for browser preview), the
    upload destination check, and the index revalidation."""
    if not isinstance(sound, str) or not _SOUND_NAME_RE.match(sound):
        return None
    candidate = os.path.realpath(os.path.join(_SOUNDS_DIR, sound + '.mp3'))
    if not (candidate == _SOUNDS_DIR_REAL
            or candidate.startswith(_SOUNDS_DIR_REAL + os.sep)):
        return None
    return candidate


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
    Only used by the Choreo editor — not for playback (playback goes through UART).
    B-1: strict regex + realpath containment via _safe_sound_path."""
    filepath = _safe_sound_path(sound)
    if filepath is None:
        abort(400)
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

    if not f.filename.lower().endswith('.mp3'):
        return jsonify({'ok': False, 'error': 'Only .mp3 files accepted'}), 400

    # Sanitize filename — uppercase, alphanumeric + underscore only.
    stem = re.sub(r'[^A-Za-z0-9_]', '_', Path(f.filename).stem).strip('_')
    stem = re.sub(r'_+', '_', stem).upper()
    if not stem:
        return jsonify({'ok': False, 'error': 'Invalid filename'}), 400

    # B-2 layer 1: validate the sanitized stem against the same regex used
    # by /audio/file/<sound>. Belt-and-suspenders — sanitize already
    # produces a safe string, but if the regex above ever loosens we'd
    # silently let new chars through. Keep the gates aligned.
    if not _SOUND_NAME_RE.match(stem):
        return jsonify({'ok': False, 'error': 'Invalid filename after sanitization'}), 400

    # B-2 layer 2: validate category — protects the index from being
    # mutated for an arbitrary key.
    if not _CATEGORY_NAME_RE.match(category):
        return jsonify({'ok': False, 'error': 'Invalid category name'}), 400

    # B-2 layer 3: realpath containment — ensures the resolved write
    # destination is genuinely inside _SOUNDS_DIR. Mirrors _safe_sound_path
    # but for the create path (file doesn't exist yet, so we resolve the
    # parent dir).
    dest_path = os.path.realpath(os.path.join(_SOUNDS_DIR, stem + '.mp3'))
    if not dest_path.startswith(_SOUNDS_DIR_REAL + os.sep):
        return jsonify({'ok': False, 'error': 'Invalid filename (escape attempt)'}), 400

    with _upload_lock:
        # B-2 layer 4: refuse to overwrite an existing file — operator should
        # explicitly delete the old one first. Avoids silent clobbering of
        # the built-in 317 sounds.
        if os.path.exists(dest_path):
            return jsonify({
                'ok': False, 'error': f'"{stem}.mp3" already exists — delete it first',
            }), 409

        # Load the index BEFORE writing, so we can dedup against other
        # categories and reject duplicates at any tier.
        try:
            index = json.loads(Path(_INDEX_FILE).read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            # Narrow catch: missing file or corrupt JSON is recoverable.
            # Unknown exceptions propagate so they surface in journalctl.
            index = {'categories': {}}
        cats = index.setdefault('categories', {})

        # Cross-category dedup: a sound stem must live in EXACTLY one
        # category. Reject the upload if the stem is already indexed
        # somewhere else — prevents the "same file under two categories"
        # state that diverged the index from disk reality.
        for other_cat, sounds in cats.items():
            if stem in sounds and other_cat != category:
                return jsonify({
                    'ok': False,
                    'error': f'"{stem}" already exists in category "{other_cat}"',
                }), 409

        # Save the file to disk. By this point we've cleared every gate,
        # so f.save() is the first irreversible op.
        os.makedirs(_SOUNDS_DIR, exist_ok=True)
        f.save(dest_path)

        # Update sounds_index.json
        sounds = cats.setdefault(category, [])
        if stem not in sounds:
            sounds.append(stem)
            sounds.sort()
        Path(_INDEX_FILE).write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding='utf-8')
        with _audio_state_lock:
            global _INDEX_CACHE
            _INDEX_CACHE = index  # refresh in-memory cache

    # Sync to slave via SFTP — OUTSIDE the upload lock (B-9: SFTP can
    # take 5-30s on WiFi for a large MP3; holding _upload_lock blocked
    # every other audio API call). Daemon thread so the HTTP response
    # returns immediately; failures are logged but don't fail the upload
    # since the file is already on disk locally.
    threading.Thread(
        target=_sftp_sync_sound,
        args=(dest_path, stem, index),
        daemon=True,
        name=f'sftp-sync-{stem}',
    ).start()

    return jsonify({'ok': True, 'filename': stem, 'category': category})


@audio_bp.post('/category/create')
def create_category():
    """Create a new empty audio category. Body: {"name": "mycat"}"""
    body = request.get_json(silent=True) or {}
    name = (body.get('name') or '').strip().lower()
    if not _CATEGORY_NAME_RE.match(name):
        return jsonify({'ok': False, 'error': 'Invalid category name'}), 400

    with _upload_lock:
        try:
            index = json.loads(Path(_INDEX_FILE).read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            index = {'categories': {}}
        cats = index.setdefault('categories', {})
        if name in cats:
            return jsonify({'ok': False, 'error': f'Category "{name}" already exists'}), 409
        cats[name] = []
        Path(_INDEX_FILE).write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding='utf-8')
        with _audio_state_lock:
            global _INDEX_CACHE
            _INDEX_CACHE = index

    # Sync index to slave OUTSIDE the upload lock (B-9: SFTP can block
    # for seconds on WiFi). Daemon thread — failure logged, doesn't
    # affect the HTTP response.
    threading.Thread(
        target=_sftp_sync_index,
        args=(index,),
        daemon=True,
        name=f'sftp-cat-{name}',
    ).start()

    return jsonify({'ok': True, 'name': name})


def _sftp_atomic_put(sftp, remote_path: str, data_or_local) -> None:
    """Atomic remote write: upload to {path}.tmp then sftp.rename() it.

    B-4: the non-atomic sftp.put / putfo previously let mpg123 read a
    truncated MP3 if a `S:STEM` UART command landed mid-upload, and could
    leave sounds_index.json in a half-written state if the connection
    dropped. sftp.rename() is atomic on the slave's POSIX filesystem.

    `data_or_local` is either bytes (for the JSON index) or a local file
    path (for the MP3 file)."""
    tmp = remote_path + '.tmp'
    if isinstance(data_or_local, (bytes, bytearray)):
        import io as _io
        sftp.putfo(_io.BytesIO(data_or_local), tmp)
    else:
        sftp.put(data_or_local, tmp)
    # POSIX rename is atomic; an existing target is replaced in one step.
    # paramiko.SFTPClient.posix_rename ensures POSIX semantics — fall back
    # to .rename which removes-then-renames on protocols that don't
    # support posix-rename@openssh.com.
    try:
        sftp.posix_rename(tmp, remote_path)
    except (IOError, AttributeError):
        # paramiko exposes posix_rename only on recent versions / openssh
        # servers. Fall back to rename + delete (less atomic but the
        # window is microseconds vs the multi-second put).
        try:
            sftp.remove(remote_path)
        except IOError:
            pass
        sftp.rename(tmp, remote_path)


def _sftp_sync_index(index: dict) -> None:
    """Sync sounds_index.json to slave atomically.

    B-3: credentials read from cfg (deploy.slave_user / slave_password)
    instead of hardcoded 'artoo'/'deetoo'. Falls back to key-based auth
    when no password is configured."""
    try:
        import paramiko
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(**_slave_sftp_creds())
        sftp = c.open_sftp()
        try:
            data = json.dumps(index, indent=2, ensure_ascii=False).encode('utf-8')
            _sftp_atomic_put(sftp, f'{_SLAVE_SOUNDS}/sounds_index.json', data)
        finally:
            sftp.close()
            c.close()
    except (OSError, IOError) as e:
        # Narrow: paramiko raises paramiko.SSHException (subclass of OSError)
        # for connect failures and IOError for SFTP errors. Anything else
        # propagates so we see real bugs in journalctl.
        log.warning('SFTP index sync failed: %s', e)
    except ImportError:
        log.warning('SFTP index sync skipped: paramiko not installed')


def _sftp_sync_sound(local_mp3: str, stem: str, index: dict) -> None:
    """SFTP the new MP3 and updated index to the slave Pi atomically.

    B-3 + B-4: credentials from cfg, atomic put for both the MP3 and the
    index. mpg123 on the slave can never see a truncated MP3 or a
    half-written index file."""
    try:
        import paramiko
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(**_slave_sftp_creds())
        sftp = c.open_sftp()
        try:
            remote_sounds = _SLAVE_SOUNDS
            _sftp_atomic_put(sftp, f'{remote_sounds}/{stem}.mp3', local_mp3)
            data = json.dumps(index, indent=2, ensure_ascii=False).encode('utf-8')
            _sftp_atomic_put(sftp, f'{remote_sounds}/sounds_index.json', data)
        finally:
            sftp.close()
            c.close()
        log.info('Audio upload: synced %s.mp3 to slave (atomic)', stem)
    except (OSError, IOError) as e:
        log.warning(
            'Audio upload: SFTP sync failed — %s. File saved locally only.',
            e,
        )
    except ImportError:
        log.warning('Audio upload: paramiko not installed — file saved locally only')


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
