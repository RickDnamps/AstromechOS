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
import time
from pathlib import Path
from flask import Blueprint, request, jsonify, send_file, abort
from master.api._admin_auth import require_admin
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

# E1 fix 2026-05-15: serialize SFTP sync threads so the remote
# sounds_index.json reflects the latest local state instead of a
# stale snapshot captured at upload-thread start. Two simultaneous
# uploads with the old code: thread A captures index{A}, thread B
# captures index{A+B}, both run SFTP in parallel, if A's SFTP
# finishes LAST the remote index reverts to {A only}. Now: SFTP
# threads acquire this lock + refetch the latest index inside it.
_sftp_lock = threading.Lock()


def cleanup_orphan_tmp_files() -> int:
    """E4 fix 2026-05-15: scan the Slave's sounds dir for orphan
    *.mp3.tmp files left by SFTP drops mid-upload. Called once at
    Master startup. Returns count removed (or -1 on error).

    These accumulate over multi-day events with flaky WiFi — each
    failed upload leaves a tmp behind that's never reaped.
    """
    try:
        import paramiko
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(**_slave_sftp_creds())
        sftp = c.open_sftp()
        try:
            count = 0
            for entry in sftp.listdir(_SLAVE_SOUNDS):
                if entry.endswith('.mp3.tmp'):
                    try:
                        sftp.remove(f'{_SLAVE_SOUNDS}/{entry}')
                        count += 1
                    except Exception:
                        pass
            return count
        finally:
            sftp.close()
            c.close()
    except Exception as e:
        log.warning('Orphan .tmp cleanup skipped: %s', e)
        return -1

# Strict filename allow-list — only the characters actually present in
# the existing 317 R2-D2 sound files. Excludes hyphen (the upload
# sanitizer collapses it to '_') so the validation here matches what
# the upload path produces. Length cap 80 chars: more than enough for
# the longest real name (PROCESS_SUCCESS_LONG = 19), bounded against
# filesystem absurdities.
_SOUND_NAME_RE = re.compile(r'^[A-Za-z0-9_]{1,80}$')
_CATEGORY_NAME_RE = re.compile(r'^[a-z0-9_]{1,32}$')

# Prefix used in reg.audio_current to tag random-category plays.
# Shared across audio_bp + shortcuts_bp + frontend so the
# "is-playing" indicator can attribute the playback to the right
# shortcut/category. Don't change this string without updating
# shortcutsRunner.updateFromStatus' parser in app.js.
RANDOM_PLAY_PREFIX = '🎲 '


# B-14: duration cache. _get_sound_duration_ms is called on every /play
# AND on every choreo audio block dispatch. Mutagen.MP3 walks the file
# frame-by-frame to compute exact duration (handles VBR, ID3v1/v2/APEv2,
# embedded album art, padding) — accurate to the millisecond. Cache by
# (path, mtime) so a re-encoded file invalidates automatically.
#
# 2026-05-14 user-reported bug: birthday.mp3 is 320 kbps CBR (39s real
# duration), the previous 192 kbps file-size approximation estimated 67s,
# the UI kept showing 'playing' for 28 extra seconds after mpg123 finished.
# 2026-05-15: switched primary source to mutagen for ms-accurate duration
# across the whole library (CBR, VBR, mixed bitrates). Header-parse
# fallback retained for the case where mutagen isn't installed yet.
_DURATION_CACHE: dict = {}   # {path: (mtime, ms)}

try:
    from mutagen.mp3 import MP3 as _MutagenMP3
    _HAVE_MUTAGEN = True
except ImportError:
    _MutagenMP3 = None
    _HAVE_MUTAGEN = False


# MPEG1 Layer III bitrate table (kbps). bitrate_idx 0 = free, 15 = invalid.
# Used only by the fallback estimator when mutagen is unavailable.
_MPEG1_L3_BITRATES = [0, 32, 40, 48, 56, 64, 80, 96, 112,
                       128, 160, 192, 224, 256, 320, 0]
# MPEG2 / MPEG2.5 Layer III (low-sample-rate variants — rare for R2 sounds).
_MPEG2_L3_BITRATES = [0, 8, 16, 24, 32, 40, 48, 56, 64,
                       80, 96, 112, 128, 144, 160, 0]


def _parse_mp3_bitrate(path: str) -> int | None:
    """Fallback bitrate reader (no mutagen). Reads the first MPEG frame
    header and returns the bitrate in kbps. Skips any leading ID3v2 tag.
    CBR-accurate; VBR files report the first-frame bitrate which differs
    from the file average — that's why mutagen is the preferred path."""
    try:
        with open(path, 'rb') as f:
            head = f.read(10)
            if len(head) < 10:
                return None
            if head[:3] == b'ID3':
                size = ((head[6] & 0x7F) << 21) | ((head[7] & 0x7F) << 14) \
                     | ((head[8] & 0x7F) << 7)  | (head[9] & 0x7F)
                f.seek(10 + size)
            else:
                f.seek(0)
            buf = f.read(65536)
            for i in range(len(buf) - 4):
                if buf[i] == 0xFF and (buf[i + 1] & 0xE0) == 0xE0:
                    b1, b2 = buf[i + 1], buf[i + 2]
                    mpeg_ver    = (b1 >> 3) & 0x03
                    layer       = (b1 >> 1) & 0x03
                    bitrate_idx = (b2 >> 4) & 0x0F
                    if layer != 1 or bitrate_idx in (0, 15):
                        continue
                    table = _MPEG1_L3_BITRATES if mpeg_ver == 3 else _MPEG2_L3_BITRATES
                    return table[bitrate_idx]
            return None
    except OSError:
        return None


def _estimate_duration_ms(path: str, fallback_ms: int = 60000) -> int:
    """Returns the duration of an MP3 in ms.

    Primary: mutagen.MP3.info.length — frame-counted, ms-accurate, handles
    VBR + Xing/VBRI + ID3v1/v2/APEv2 + album art + padding. Adds the
    +500ms mpg123 cold-start tail used by the audio_playing flag.

    Fallback: header-parse + size/bitrate. Only hit if mutagen failed to
    install (Trixie apt didn't have python3-mutagen yet, or a corrupt
    file mutagen refuses)."""
    if _HAVE_MUTAGEN:
        try:
            info = _MutagenMP3(path).info
            if info and info.length > 0:
                return int(info.length * 1000) + 500
        except Exception:
            pass   # fall through to size-based fallback
    try:
        size = os.path.getsize(path)
    except OSError:
        return fallback_ms
    bitrate_kbps = _parse_mp3_bitrate(path) or 192
    return int(size * 8 / bitrate_kbps) + 500


_DURATION_CACHE_CAP = 2048   # P3 fix: bound the cache

def _get_sound_duration_ms(sound: str, fallback_ms: int = 60000) -> int:
    """Returns the cached duration in ms, refreshing on file mtime change.

    P3 fix 2026-05-15: cap _DURATION_CACHE at 2048 entries (FIFO
    eviction) so deleted-file entries don't accumulate over multi-day
    events. Also drop entries when stat raises OSError (deleted files).
    """
    path = os.path.join(_SOUNDS_DIR, sound + '.mp3')
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        # Drop stale entry if the file disappeared
        _DURATION_CACHE.pop(path, None)
        return fallback_ms
    cached = _DURATION_CACHE.get(path)
    if cached and cached[0] == mtime:
        return cached[1]
    dur_ms = _estimate_duration_ms(path, fallback_ms)
    # FIFO eviction if at cap (drop oldest insertion). dict iteration
    # order is insertion-order in 3.7+, so next(iter(...)) gives the
    # oldest key.
    if len(_DURATION_CACHE) >= _DURATION_CACHE_CAP:
        try: del _DURATION_CACHE[next(iter(_DURATION_CACHE))]
        except StopIteration: pass
    _DURATION_CACHE[path] = (mtime, dur_ms)
    return dur_ms


def _category_avg_duration_ms(category: str, fallback_ms: int = 8000) -> int:
    """Average duration of all sounds in a category. Used by /audio/random
    when the master can't predict which file the slave will pick — old
    code hard-coded 60s, which made auto-random rate-limited to ~1 sound
    per minute for short clips (F-4 of the audit). Now we estimate from
    the category's actual content. Fallback 8s ≈ typical R2 quote length."""
    sounds = _get_index().get('categories', {}).get(category, [])
    if not sounds:
        return fallback_ms
    durations = [_get_sound_duration_ms(s, fallback_ms) for s in sounds]
    if not durations:
        return fallback_ms
    return sum(durations) // len(durations)


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
    # L1 fix 2026-05-15: drop dead `candidate == _SOUNDS_DIR_REAL`
    # branch — candidate always ends in '.mp3', can never equal the
    # directory itself. The startswith check is the real containment.
    if not candidate.startswith(_SOUNDS_DIR_REAL + os.sep):
        return None
    return candidate


audio_bp = Blueprint('audio', __name__, url_prefix='/audio')

_INDEX_FILE = os.path.join(
    os.path.dirname(__file__), '..', '..', 'slave', 'sounds', 'sounds_index.json'
)

# Index cache, invalidated by mtime check on each access (B-8).
# Previously loaded ONCE and never refreshed, so an external edit
# (slave-side modification, SSH-edited JSON, sync-back from slave)
# would leave Flask serving stale data forever. Now we stat the file
# and reload when mtime moves forward — cheap (~5µs per call) compared
# to JSON parsing.
_INDEX_CACHE: dict = {}
_INDEX_MTIME: float = 0.0
# P4 fix 2026-05-15: TTL cache for the mtime stat itself. Called
# from /audio/play, /audio/random, choreo TICK every 50ms × 12
# channels = lots of os.path.getmtime. 250ms TTL is fast enough to
# catch new uploads (operator sees their new sound within 250ms)
# and saves the syscall when called rapidly during a choreo.
_INDEX_STAT_TS: float = 0.0
_INDEX_STAT_VAL: float = 0.0
_INDEX_STAT_TTL_S = 0.25


def _get_index() -> dict:
    """Returns the sounds index. Auto-refreshes when the on-disk file
    has been modified since the last read.

    B-12: narrow exception clauses — OSError for file-not-found /
    permission, JSONDecodeError for malformed JSON. Anything else
    propagates so a real bug surfaces in journalctl instead of
    silently degrading to an empty index.

    Audit finding M-3 2026-05-15: _INDEX_CACHE + _INDEX_MTIME were
    written outside the lock. A reader could see the new MTIME with
    the OLD CACHE (or vice versa) for a tick. Both writes now happen
    under _audio_state_lock as a single critical section."""
    global _INDEX_CACHE, _INDEX_MTIME, _INDEX_STAT_TS, _INDEX_STAT_VAL
    # P4 fix: TTL-cache the stat result. Choreo TICK can call
    # _get_index hundreds of times per second; the file rarely
    # changes (only on upload). 250ms is operator-imperceptible.
    now = time.monotonic()
    if now - _INDEX_STAT_TS < _INDEX_STAT_TTL_S and _INDEX_STAT_VAL > 0:
        mtime = _INDEX_STAT_VAL
    else:
        try:
            mtime = os.path.getmtime(_INDEX_FILE)
            _INDEX_STAT_VAL = mtime
            _INDEX_STAT_TS  = now
        except OSError:
            # File missing — keep whatever we have cached (possibly empty).
            return _INDEX_CACHE
    if mtime > _INDEX_MTIME or not _INDEX_CACHE:
        with _audio_state_lock:
            # Re-check under the lock — another thread may have just
            # refreshed it while we were waiting.
            if mtime > _INDEX_MTIME or not _INDEX_CACHE:
                try:
                    with open(_INDEX_FILE, encoding='utf-8') as f:
                        _INDEX_CACHE = json.load(f)
                    _INDEX_MTIME = mtime
                except (OSError, json.JSONDecodeError) as e:
                    log.warning('_get_index: failed to reload — %s', e)
                    if not _INDEX_CACHE:
                        _INDEX_CACHE = {}
    return _INDEX_CACHE


def _atomic_write_index(index: dict) -> None:
    """Atomically replace sounds_index.json: tmp + fsync + os.replace.

    Audit finding M-2 2026-05-15: Path(_INDEX_FILE).write_text used
    open-truncate-write, so a crash mid-write left a half-written
    file → next /audio/upload silently rebuilt the index empty,
    losing the entire catalog (the documented 'recovery procedures'
    scenario in CLAUDE.md). This helper is the same pattern as
    write_cfg_atomic / _atomic_write_chor."""
    tmp = _INDEX_FILE + '.tmp'
    # User-reported 2026-05-16: rotate .bak before write
    from master.config.config_loader import rotate_backup as _rotate
    _rotate(_INDEX_FILE)
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
        f.flush()
        try:
            os.fsync(f.fileno())
        except OSError:
            pass   # not all FS support fsync
    os.replace(tmp, _INDEX_FILE)


def _valid_sound(sound: str) -> bool:
    cats = _get_index().get('categories', {})
    return any(sound in sounds for sounds in cats.values())


def _valid_category(cat: str) -> bool:
    return cat in _get_index().get('categories', {})



@audio_bp.get('/categories')
def get_categories():
    """List of categories with sound count.
    L-4: sorted alphabetically so the UI pill order is deterministic
    across Master reboots (was dict-insertion-order: depended on the
    write order of sounds_index.json, surprising after manual edits)."""
    try:
        cats = _get_index().get('categories', {})
        return jsonify({
            'categories': [{'name': k, 'count': len(cats[k])}
                           for k in sorted(cats.keys())],
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
    body = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
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
    body = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    category = body.get('category', 'happy').strip().lower()
    if not _valid_category(category):
        return jsonify({'error': f'Unknown category: {category}'}), 404
    # L-3: refuse empty categories. Without this, the slave gets
    # `S:RANDOM:emptycat`, scans an empty file list, and silently no-ops
    # — UI flips to 'playing' for a second then back to idle with no
    # error, which is worse UX than a clear 409.
    if not _get_index().get('categories', {}).get(category):
        return jsonify({'error': f'Category "{category}" has no sounds'}), 409
    if reg.uart:
        reg.uart.send('S', f'RANDOM:{category}')
    reg.audio_playing = True
    reg.audio_current = f'{RANDOM_PLAY_PREFIX}{category}'
    # B-14 / F-4: use the category's average duration instead of the
    # 60s default — auto-random UI was rate-limited to one sound per
    # minute for short categories because audio_playing stayed True for
    # the whole 60s even when the actual mpg123 sound ended in 3s.
    _schedule_audio_reset(_category_avg_duration_ms(category) + 500)
    return jsonify({'status': 'ok', 'category': category})


# B-16: scan cache. Path(_SOUNDS_DIR).glob() walks the dir every call —
# fine for 317 files but the choreo editor opens this on every Choreo tab
# switch, and the call rate adds up. Cache by SOUNDS_DIR mtime.
_SCAN_CACHE: dict = {'mtime': 0.0, 'files': []}


@audio_bp.get('/scan')
def scan_sounds():
    """Scan slave/sounds/ for all .mp3 files on disk — authoritative list regardless of index."""
    try:
        dir_mtime = os.path.getmtime(_SOUNDS_DIR)
    except OSError:
        return jsonify({'sounds': [], 'count': 0})
    if _SCAN_CACHE['mtime'] != dir_mtime:
        try:
            files = sorted(p.stem for p in Path(_SOUNDS_DIR).glob('*.mp3') if p.is_file())
            _SCAN_CACHE['mtime'] = dir_mtime
            _SCAN_CACHE['files'] = files
        except OSError as e:
            return jsonify({'error': str(e)}), 500
    return jsonify({'sounds': _SCAN_CACHE['files'], 'count': len(_SCAN_CACHE['files'])})


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
    """Stops the current sound. L-1: timer cancel under _audio_state_lock
    so a concurrent /play can't replace _play_timer between is_alive() and
    cancel() — would otherwise leave the new timer running while we
    clear audio_playing here, then the timer's _reset would fire later
    and re-clear (already cleared, no-op) — minor but the lock makes the
    state transition atomic."""
    global _play_timer
    with _audio_state_lock:
        if _play_timer and _play_timer.is_alive():
            _play_timer.cancel()
        _play_timer = None
        reg.audio_playing = False
        reg.audio_current = ''
    if reg.uart:
        reg.uart.send('S', 'STOP')
    return jsonify({'status': 'ok'})


# L-2: volume persistence. reg.audio_volume was in-memory only; without
# this, every Master reboot would show the slider at 80 even if the
# operator had set it to 30 yesterday. Stored under [audio] volume in
# local.cfg alongside the existing audio_channels / profile_* keys.
def _read_persisted_volume() -> int | None:
    """Return last-saved volume from local.cfg [audio] volume, or None."""
    try:
        cfg = configparser.ConfigParser()
        cfg.read(_LOCAL_CFG, encoding='utf-8')
        if cfg.has_option('audio', 'volume'):
            return max(0, min(100, cfg.getint('audio', 'volume')))
    except (OSError, ValueError):
        pass
    return None


def _persist_volume(vol: int) -> None:
    """Write vol to local.cfg [audio] volume so it survives reboots.

    Audit finding H-2 2026-05-15: previously used `open(_LOCAL_CFG, 'w')`
    direct, violating BOTH project invariants:
      - Cross-blueprint cfg lock (settings_bp._cfg_write_lock)
      - Atomic write (write_cfg_atomic: tmp + replace + fsync + chmod 0600)
    A concurrent /settings/config save would race on the same file,
    AND the open-truncate-write sequence left a half-written cfg
    visible to other readers mid-flush. The direct open() also dropped
    the 0600 permission bit that protects [admin] password.
    """
    try:
        from master.api.settings_bp import _cfg_write_lock
        from master.config.config_loader import write_cfg_atomic
        with _cfg_write_lock:
            cfg = configparser.ConfigParser()
            cfg.read(_LOCAL_CFG, encoding='utf-8')
            if not cfg.has_section('audio'):
                cfg.add_section('audio')
            cfg.set('audio', 'volume', str(vol))
            write_cfg_atomic(cfg, _LOCAL_CFG)
    except (OSError, configparser.Error) as e:
        # L6 fix 2026-05-15: log instead of silent swallow. Next
        # /volume will retry, but the operator needs to see this in
        # journalctl if cfg is corrupted (broader catch than just
        # OSError — configparser.Error catches malformed local.cfg).
        log.warning("_persist_volume failed: %s", e)


# Hydrate reg.audio_volume at module import so any /audio/play arriving
# before the first /audio/volume GET still uses the operator's last
# setting rather than the 80 default.
if not hasattr(reg, 'audio_volume'):
    _persisted = _read_persisted_volume()
    reg.audio_volume = _persisted if _persisted is not None else 80


@audio_bp.get('/volume')
def get_volume():
    """Returns the current volume (0-100)."""
    return jsonify({'volume': getattr(reg, 'audio_volume', 80)})


@audio_bp.post('/volume')
def set_volume():
    """Sets the volume. Body: {"volume": 75}  (0-100)
    L-2: persists to local.cfg so the slider position survives a Master
    reboot. The cfg write happens after the UART push so the audible
    change isn't blocked by FS sync latency.

    2026-05-15 fix: LAN-open like /audio/play|random|stop — operator
    user-reported the Drive bottom slider 'did nothing' because they
    weren't admin-unlocked and the @require_admin made requests 401
    silently. Volume is a basic operator control, not a config mutation
    that needs auth. Same trust model as the rest of /audio/*."""
    body = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    try:
        vol = max(0, min(100, int(body.get('volume', 80))))
    except (TypeError, ValueError):
        return jsonify({'error': 'volume must be an integer 0-100'}), 400
    reg.audio_volume = vol
    if reg.uart:
        reg.uart.send('VOL', str(vol))
    _persist_volume(vol)
    return jsonify({'status': 'ok', 'volume': vol})


def _next_available_stem(base: str, cats: dict) -> str:
    """Return base if nothing else uses it, else base_2, base_3, … up to
    base_999. Considers BOTH disk presence (slave/sounds/<stem>.mp3) AND
    every category in the index. Used by /audio/upload to auto-resolve
    name collisions instead of rejecting the upload.

    User feedback 2026-05-15: 'quand on upload un son il faudrait au
    moins que le système s'assure que le nouveau son n'a pas le même nom
    qu'un son existant déjà si oui il renomme en ajoutant un chiffre'.

    **Case-insensitive collision check.** New uploads are uppercased by
    the sanitizer, but the built-in library has mixed-case filenames
    (birthday.mp3, Theme003.mp3, ALARM001.mp3). Linux treats those as
    different files so a naive case-sensitive check let `BIRTHDAY` upload
    next to existing `birthday.mp3`, leaving the operator with two
    files they perceive as the same sound. Comparing in lower-case
    catches that.

    Why both disk + index? Files in slave/sounds/ that aren't indexed
    (orphans from a deleted category, or built-ins not yet registered)
    must still block the name — overwriting them would break behaviors
    that reference them by stem."""
    # Index reservations (case-insensitive).
    indexed_lower: set[str] = set()
    for sounds in cats.values():
        indexed_lower.update(s.lower() for s in sounds)
    # Disk reservations (case-insensitive). Single listdir is cheaper
    # than os.path.exists per candidate when the loop iterates.
    disk_lower: set[str] = set()
    try:
        for entry in os.listdir(_SOUNDS_DIR):
            if entry.lower().endswith('.mp3'):
                disk_lower.add(Path(entry).stem.lower())
    except OSError:
        pass

    for n in range(1, 1000):
        candidate = base if n == 1 else f'{base}_{n}'
        # Stay within the same regex the rest of the pipeline enforces —
        # base already passed it, so candidate will too unless n produces
        # a string >80 chars (impossible: base ≤80, _999 = 4 chars).
        if not _SOUND_NAME_RE.match(candidate):
            return base
        cand_lower = candidate.lower()
        if cand_lower not in disk_lower and cand_lower not in indexed_lower:
            return candidate
    # Ridiculously unlikely fallback (1000 collisions on the same stem).
    return f'{base}_OVERFLOW'


@audio_bp.post('/upload')
@require_admin
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

    # L2 fix 2026-05-15: per-file 12MB server cap. Flask global
    # MAX_CONTENT_LENGTH is 16MB, frontend UI rejects at 10MB. A
    # curl/script client could push 10-16MB; clamp at 12MB so the
    # server enforces what the UI promises (with a 2MB buffer).
    if request.content_length and request.content_length > 12 * 1024 * 1024:
        return jsonify({'ok': False, 'error': 'File too large (max 12MB)'}), 413

    # E6 fix 2026-05-15: reject empty / near-empty MP3 (≤1KB = not a
    # real audio file). mpg123 would exit instantly + the index would
    # carry a 'sound' that's silence.
    if request.content_length and request.content_length < 1024:
        return jsonify({'ok': False, 'error': 'File too small to be a valid MP3'}), 400

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
        # Load the index BEFORE writing, so we can resolve name collisions
        # against both disk presence AND any category in the index.
        # Audit finding M-1 2026-05-15: silently substituting an empty
        # index on parse failure caused upload to REBUILD it with only
        # the new file — losing the entire pre-corruption catalog.
        # Fail-closed: refuse the upload, point operator at the recovery
        # script. The catalog is too valuable to silently overwrite.
        try:
            index = json.loads(Path(_INDEX_FILE).read_text(encoding='utf-8'))
        except FileNotFoundError:
            index = {'categories': {}}
        except (OSError, json.JSONDecodeError) as e:
            log.error("Upload refused: sounds_index.json corrupted: %s", e)
            return jsonify({
                'ok': False,
                'error': 'sound index corrupted — run scripts/fix_slave_sounds_index.py first',
            }), 503
        cats = index.setdefault('categories', {})

        # Auto-rename on collision (user feedback 2026-05-15: prefer
        # auto-resolution over outright rejection — operator dragging in
        # a folder of new sounds shouldn't have to manually fix every
        # name clash). Helper picks BASE, BASE_2, BASE_3 … so the chosen
        # name is unique against both disk and ALL categories in the
        # index. Replaces the previous two 409 paths (overwrite + cross-
        # category dedup) which both wanted manual intervention.
        final_stem = _next_available_stem(stem, cats)
        if final_stem != stem:
            log.info('Upload collision: %s → %s', stem, final_stem)
        dest_path = os.path.realpath(os.path.join(_SOUNDS_DIR, final_stem + '.mp3'))
        # Re-verify containment for the resolved name — defense in depth
        # in case _next_available_stem ever produces something exotic.
        if not dest_path.startswith(_SOUNDS_DIR_REAL + os.sep):
            return jsonify({'ok': False, 'error': 'Invalid filename (escape attempt)'}), 400

        # Save the file to disk. By this point we've cleared every gate,
        # so f.save() is the first irreversible op.
        os.makedirs(_SOUNDS_DIR, exist_ok=True)
        f.save(dest_path)

        # Update sounds_index.json with the FINAL stem.
        sounds = cats.setdefault(category, [])
        # Audit finding A2-L3 2026-05-15: cap per-category sound count.
        # 512 covers the biggest legit collection by a wide margin
        # (R2-D2 ships with 324 across all 14 cats). Caps stop a
        # runaway script from bloating the index.
        _SOUNDS_PER_CAT_MAX = 512
        if final_stem not in sounds:
            if len(sounds) >= _SOUNDS_PER_CAT_MAX:
                return jsonify({
                    'ok': False,
                    'error': f'Category "{category}" full (max {_SOUNDS_PER_CAT_MAX} sounds)',
                }), 400
            sounds.append(final_stem)
            sounds.sort()
        _atomic_write_index(index)
        with _audio_state_lock:
            global _INDEX_CACHE, _INDEX_MTIME
            _INDEX_CACHE = index  # refresh in-memory cache
            # Bump mtime tracker so _get_index() doesn't immediately
            # reload from disk and read what we just wrote (no-op but
            # wasteful).
            try:
                _INDEX_MTIME = os.path.getmtime(_INDEX_FILE)
            except OSError:
                pass

    # Sync to slave via SFTP — OUTSIDE the upload lock (B-9: SFTP can
    # take 5-30s on WiFi for a large MP3; holding _upload_lock blocked
    # every other audio API call). Daemon thread so the HTTP response
    # returns immediately; failures are logged but don't fail the upload
    # since the file is already on disk locally.
    threading.Thread(
        target=_sftp_sync_sound,
        args=(dest_path, final_stem, index),
        daemon=True,
        name=f'sftp-sync-{final_stem}',
    ).start()

    return jsonify({
        'ok':       True,
        'filename': final_stem,
        'category': category,
        # Tell the UI when we auto-renamed so it can surface that fact
        # to the operator (e.g. "happy.mp3 → HAPPY_2"). When no rename
        # happened both fields are equal and the UI just shows the name.
        'original': stem,
        'renamed':  final_stem != stem,
    })


@audio_bp.route('/sound/<sound>', methods=['DELETE'])
@require_admin
def delete_sound(sound):
    """L3-W feature 2026-05-16: per-sound delete with cascade.

    Removes the sound from:
      - sounds_index.json (master, atomic write under _upload_lock)
      - local slave/sounds/<stem>.mp3 file
      - remote slave filesystem (via SFTP, serialized via _sftp_lock)
      - any shortcut targeting it (cascade_delete from shortcuts_bp
        switches the shortcut's action to 'none' so the operator sees
        the dead button and can reconfigure)

    NOT cascaded (intentional): choreo audio tracks. A choreo block
    referencing a deleted sound is preserved so the operator can
    re-upload a replacement under the same name without re-editing
    the choreo. The choreo dispatch will silently no-op if the
    sound is missing at play time.
    """
    if not isinstance(sound, str) or not _SOUND_NAME_RE.match(sound):
        return jsonify({'ok': False, 'error': 'Invalid sound name'}), 400
    local_mp3 = _safe_sound_path(sound)
    if not local_mp3:
        return jsonify({'ok': False, 'error': 'Sound path resolution failed'}), 400

    with _upload_lock:
        index = _get_index()
        cats = index.get('categories', {})
        # Remove from EVERY category that contains it (defensive — a
        # sound could be listed in multiple cats if the index was
        # hand-edited).
        found_in = []
        for cat_name, sounds in cats.items():
            if isinstance(sounds, list) and sound in sounds:
                cats[cat_name] = [s for s in sounds if s != sound]
                found_in.append(cat_name)
        if not found_in:
            return jsonify({'ok': False, 'error': 'Sound not in index'}), 404
        _atomic_write_index(index)

    # Local MP3 delete (best-effort — index removal is authoritative)
    try:
        if os.path.exists(local_mp3):
            os.remove(local_mp3)
            log.info("Deleted local MP3: %s", local_mp3)
    except OSError as e:
        log.warning("Failed to delete local MP3 %s: %s", local_mp3, e)

    # SFTP delete + index sync to Slave (serialized via _sftp_lock).
    # Same threading pattern as upload — don't block the HTTP response.
    threading.Thread(
        target=_sftp_delete_sound, args=(sound,),
        daemon=True, name=f'sftp-delete-{sound}',
    ).start()

    # Cascade: any shortcut pointing at this sound becomes 'none'
    cascaded = 0
    try:
        from master.api.shortcuts_bp import cascade_delete
        cascaded = cascade_delete('play_sound', sound)
    except Exception as e:
        log.warning("cascade_delete for sound %s failed: %s", sound, e)

    # BT custom mappings cascade — same soft-delete semantics as
    # shortcuts. Any device profile with a custom button bound to this
    # sound has its action neutralized to 'none' (preserves label/icon
    # so the operator notices and can rebind).
    bt_cascaded = 0
    try:
        from master.api.bt_bp import cascade_delete_in_bt
        bt_cascaded = cascade_delete_in_bt('play_sound', sound)
    except Exception as e:
        log.warning("BT cascade_delete for sound %s failed: %s", sound, e)

    return jsonify({
        'ok': True, 'sound': sound,
        'removed_from_cats': found_in,
        'shortcuts_neutralized': cascaded,
        'bt_mappings_neutralized': bt_cascaded,
    })


def _sftp_delete_sound(sound: str) -> None:
    """L3-W support 2026-05-16: SFTP-delete a sound from the Slave +
    re-sync the freshly-updated index. Serialized via _sftp_lock so
    it can't race with concurrent uploads."""
    with _sftp_lock:
        try:
            with open(_SOUNDS_INDEX, 'rb') as f:
                fresh_index = json.loads(f.read().decode('utf-8'))
        except (OSError, json.JSONDecodeError):
            log.warning("SFTP delete: index read failed for %s", sound)
            return
        try:
            import paramiko
            c = paramiko.SSHClient()
            c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c.connect(**_slave_sftp_creds())
            sftp = c.open_sftp()
            try:
                # Remove remote MP3 (ignore if already missing)
                try:
                    sftp.remove(f'{_SLAVE_SOUNDS}/{sound}.mp3')
                except IOError:
                    pass
                # Sync the index
                data = json.dumps(fresh_index, indent=2, ensure_ascii=False).encode('utf-8')
                _sftp_atomic_put(sftp, f'{_SLAVE_SOUNDS}/sounds_index.json', data)
                # Reload Slave in-memory index
                try:
                    if reg.uart:
                        reg.uart.send('SIDX', 'RELOAD')
                except Exception:
                    pass
            finally:
                sftp.close()
                c.close()
            log.info("SFTP deleted %s.mp3 + synced index", sound)
        except (OSError, IOError) as e:
            log.warning("SFTP delete failed for %s: %s", sound, e)
        except ImportError:
            log.warning("SFTP delete skipped (paramiko not installed): %s", sound)


@audio_bp.post('/category/create')
@require_admin
def create_category():
    """Create a new empty audio category. Body: {"name": "mycat"}"""
    body = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
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
        # Audit finding A2-L3 2026-05-15: hard cap on category count.
        # Admin-protected but a typo'd script could create thousands
        # before anyone notices, ballooning the index file.
        _CAT_COUNT_MAX = 64
        if len(cats) >= _CAT_COUNT_MAX:
            return jsonify({'ok': False, 'error': f'Too many categories (max {_CAT_COUNT_MAX})'}), 400
        cats[name] = []
        _atomic_write_index(index)
        with _audio_state_lock:
            global _INDEX_CACHE, _INDEX_MTIME
            _INDEX_CACHE = index
            try:
                _INDEX_MTIME = os.path.getmtime(_INDEX_FILE)
            except OSError:
                pass

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
    half-written index file.

    E1 fix 2026-05-15: serialize via _sftp_lock + refetch the LATEST
    index inside the lock instead of using the captured snapshot.
    Two simultaneous uploads no longer can clobber each other's entry
    in the remote sounds_index.json.
    """
    with _sftp_lock:
        # Refetch fresh index — captured `index` arg may be stale if
        # another upload has landed in the meantime.
        try:
            with open(_SOUNDS_INDEX, 'rb') as f:
                fresh_index = json.loads(f.read().decode('utf-8'))
        except (OSError, json.JSONDecodeError):
            fresh_index = index   # fall back to caller's snapshot
        try:
            import paramiko
            c = paramiko.SSHClient()
            c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c.connect(**_slave_sftp_creds())
            sftp = c.open_sftp()
            try:
                remote_sounds = _SLAVE_SOUNDS
                _sftp_atomic_put(sftp, f'{remote_sounds}/{stem}.mp3', local_mp3)
                data = json.dumps(fresh_index, indent=2, ensure_ascii=False).encode('utf-8')
                _sftp_atomic_put(sftp, f'{remote_sounds}/sounds_index.json', data)
                # E3 fix: tell Slave to reload its in-memory index so
                # the new sound is immediately playable without a
                # service restart.
                try:
                    if reg.uart:
                        reg.uart.send('SIDX', 'RELOAD')
                except Exception:
                    pass
            finally:
                sftp.close()
                c.close()
            log.info('Audio upload: synced %s.mp3 to slave (atomic)', stem)
        except (OSError, IOError) as e:
            log.warning('Audio upload: SFTP sync failed — %s. File saved locally only.', e)
        except ImportError:
            log.warning('Audio upload: paramiko not installed — file saved locally only')


# ── BT Speaker proxy (forwards to slave port 5001) ────────────────────────────

def _slave_bt(path: str, method: str = 'GET', body: dict | None = None):
    """Forward a BT request to the slave health server.

    B-67 (remaining tabs audit 2026-05-15): GET timeout dropped 12s→4s.
    Status reads are admin-only now but operator still WAITS for the
    HTTP response; 4s covers a healthy slave round-trip with margin.
    POST stays at 12s because BT pair/connect operations legitimately
    take that long on the Slave side."""
    url = f'http://{_slave_host()}:5001{path}'
    try:
        if method == 'POST':
            r = _requests.post(url, json=body or {}, timeout=12)
        else:
            r = _requests.get(url, timeout=4)
        return r.json(), r.status_code
    except Exception as e:
        return {'ok': False, 'error': str(e)}, 503


@audio_bp.get('/bt/status')
def bt_speaker_status():
    data, code = _slave_bt('/audio/bt/status')
    return jsonify(data), code


@audio_bp.post('/bt/scan')
@require_admin
def bt_speaker_scan():
    data, code = _slave_bt('/audio/bt/scan', 'POST')
    return jsonify(data), code


# Strict MAC regex shared by every endpoint that forwards a MAC to
# bluetoothctl on the Slave. Audit finding H-3 2026-05-15: the
# value was passed unvalidated, opening BT control to argument-style
# injection (--help, etc.) and reaching bluetoothctl with garbage
# strings that would only error opaquely.
import re as _re_bt_mac
_BT_MAC_RE = _re_bt_mac.compile(r'^[0-9A-F]{2}(:[0-9A-F]{2}){5}$')


def _validated_mac_body(body: dict, want_volume: bool = False):
    """Return (clean_body, error_response_or_None). MAC required;
    optional integer volume clamped 0..100."""
    if not isinstance(body, dict):
        return None, (jsonify({'error': 'expected JSON object'}), 400)
    mac = str(body.get('mac', '')).strip().upper()
    if not _BT_MAC_RE.match(mac):
        return None, (jsonify({'error': 'invalid MAC (expected AA:BB:CC:DD:EE:FF)'}), 400)
    clean = {'mac': mac}
    if want_volume:
        try:
            vol = int(body.get('volume', 80))
        except (TypeError, ValueError):
            return None, (jsonify({'error': 'volume must be an integer 0..100'}), 400)
        clean['volume'] = max(0, min(100, vol))
    return clean, None


@audio_bp.post('/bt/pair')
@require_admin
def bt_speaker_pair():
    body = request.get_json(silent=True)
    clean, err = _validated_mac_body(body)
    if err: return err
    data, code = _slave_bt('/audio/bt/pair', 'POST', clean)
    return jsonify(data), code


@audio_bp.post('/bt/connect')
@require_admin
def bt_speaker_connect():
    body = request.get_json(silent=True)
    clean, err = _validated_mac_body(body)
    if err: return err
    data, code = _slave_bt('/audio/bt/connect', 'POST', clean)
    return jsonify(data), code


@audio_bp.post('/bt/disconnect')
@require_admin
def bt_speaker_disconnect():
    body = request.get_json(silent=True)
    clean, err = _validated_mac_body(body)
    if err: return err
    data, code = _slave_bt('/audio/bt/disconnect', 'POST', clean)
    return jsonify(data), code


@audio_bp.post('/bt/remove')
@require_admin
def bt_speaker_remove():
    body = request.get_json(silent=True)
    clean, err = _validated_mac_body(body)
    if err: return err
    data, code = _slave_bt('/audio/bt/remove', 'POST', clean)
    return jsonify(data), code


@audio_bp.post('/bt/volume')
@require_admin
def bt_speaker_volume():
    body = request.get_json(silent=True)
    clean, err = _validated_mac_body(body, want_volume=True)
    if err: return err
    data, code = _slave_bt('/audio/bt/volume', 'POST', clean)
    return jsonify(data), code
