"""
Blueprint Flask — Choreography API
Routes: /choreo/play, /choreo/stop, /choreo/status,
        /choreo/list, /choreo/load, /choreo/save, /choreo/export_scr
"""
import configparser
import json
import logging
import os
import re
import threading
import time

from flask import Blueprint, jsonify, request
import master.registry as reg

log = logging.getLogger(__name__)
choreo_bp = Blueprint('choreo', __name__)

# Serialize the stop → reset → play sequence so two simultaneous /choreo/play
# requests cannot both pass the is_playing() guard and start two _run loops
# fighting over the same drivers.
_play_lock = threading.Lock()

from shared.paths import LOCAL_CFG as _LOCAL_CFG

_CHOREO_DIR = os.path.join(os.path.dirname(__file__), '..', 'choreographies')

_CATEGORIES_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'choreo_categories.json')
_SYSTEM_CATEGORY = 'newchoreo'


def _load_categories() -> list:
    """Load categories from JSON, creating defaults if missing."""
    defaults = [
        {"id": "performance", "label": "Performance", "emoji": "🎭", "order": 0},
        {"id": "emotion",     "label": "Emotions",    "emoji": "😤", "order": 1},
        {"id": "behavior",    "label": "Behavior",    "emoji": "🚶", "order": 2},
        {"id": "dome",        "label": "Dome",        "emoji": "🔵", "order": 3},
        {"id": "test",        "label": "Tests",       "emoji": "🔧", "order": 4},
        {"id": "newchoreo",   "label": "New Choreo",  "emoji": "📦", "order": 5},
    ]
    if not os.path.exists(_CATEGORIES_PATH):
        _save_categories(defaults)
        return defaults
    try:
        with open(_CATEGORIES_PATH, encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return defaults


def _save_categories(cats: list) -> None:
    os.makedirs(os.path.dirname(_CATEGORIES_PATH), exist_ok=True)
    tmp = _CATEGORIES_PATH + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(cats, f, indent=2, ensure_ascii=False)
    os.replace(tmp, _CATEGORIES_PATH)


def _auto_emoji(name: str) -> str:
    """Derive emoji from sequence name — same logic as JS _emoji()."""
    n = name.lower()
    if any(x in n for x in ['cantina', 'tune', 'dance', 'disco', 'music', 'song']): return '🎵'
    if any(x in n for x in ['alert', 'alarm']): return '🚨'
    if 'scan' in n:       return '🔍'
    if any(x in n for x in ['celebrat', 'happy', 'cheer', 'joy']): return '🎉'
    if 'leia' in n:       return '📡'
    if any(x in n for x in ['patrol', 'stroll', 'walk']): return '🚶'
    if 'test' in n:       return '🔧'
    if any(x in n for x in ['fall', 'strike', 'multi']): return '⚡'
    if 'panel' in n:      return '🚪'
    if any(x in n for x in ['dome']): return '🔵'
    if any(x in n for x in ['excit', 'idea']): return '💬'
    if 'show' in n:       return '🎭'
    if 'birthday' in n:   return '🎂'
    if 'march' in n:      return '🎖️'
    if 'party' in n:      return '🥳'
    if 'startup' in n:    return '🤖'
    if 'scared' in n:     return '😱'
    if 'angry' in n:      return '😡'
    if 'evil' in n:       return '😈'
    if 'curious' in n:    return '🤔'
    if 'taunt' in n:      return '😏'
    if 'malfunction' in n: return '💥'
    if 'failure' in n:    return '⚡'
    if 'wolfwhistle' in n: return '🐺'
    if 'message' in n:    return '📨'
    if 'ripple' in n:     return '🌀'
    if 'flap' in n:       return '🚪'
    if 'hp_twitch' in n:  return '🔦'
    return '🎬'


# Strict allowlist for user-supplied choreo names: letters, digits, and a
# small set of separators. Excludes path separators (`/`, `\`), traversal
# sequences (`..`), wildcards, and any non-ASCII / control characters.
_CHOREO_NAME_RE = re.compile(r'^[A-Za-z0-9_.\- ]+$')


def _safe_choreo_path(name):
    """Validate a user-supplied choreo name and resolve it to an absolute
    path inside ``_CHOREO_DIR``.

    Returns ``(path, None)`` on success, or ``(None, (response, code))``
    where ``response`` is a Flask JSON 400 error — callers can do::

        path, err = _safe_choreo_path(name)
        if err:
            return err

    Layers of defense:
      1. Reject non-strings, empty / whitespace-only input.
      2. Strict regex allowlist (``[A-Za-z0-9_.- ]``) — blocks path
         separators, traversal, wildcards, NUL bytes, etc.
      3. Reject the ``__`` prefix reserved for internal sentinels
         (e.g. ``__preview__.chor``) so users can't shadow them.
      4. Reject the literal ``.`` and ``..`` names.
      5. Resolve via ``os.path.realpath`` and verify the result is
         contained in ``_CHOREO_DIR`` — defense-in-depth against
         symlink shenanigans or locale-quirk edge cases.
    """
    if not isinstance(name, str):
        return None, (jsonify({'error': 'invalid name (not a string)'}), 400)
    raw = name.strip()
    if not raw:
        return None, (jsonify({'error': 'invalid name (empty)'}), 400)
    if raw.endswith('.chor'):
        raw = raw[:-5]
    if raw in ('.', '..') or raw.startswith('__'):
        return None, (jsonify({'error': 'invalid name (reserved)'}), 400)
    if not _CHOREO_NAME_RE.match(raw):
        return None, (jsonify(
            {'error': 'invalid name (allowed chars: A-Z a-z 0-9 _ . - space)'}
        ), 400)
    candidate = os.path.realpath(os.path.join(_CHOREO_DIR, raw + '.chor'))
    base      = os.path.realpath(_CHOREO_DIR)
    # Containment check: candidate must equal base (impossible since we
    # appended .chor) or live strictly inside it.
    if not (candidate == base or candidate.startswith(base + os.sep)):
        return None, (jsonify({'error': 'invalid name (escape attempt)'}), 400)
    return candidate, None


@choreo_bp.get('/choreo/list')
def choreo_list():
    os.makedirs(_CHOREO_DIR, exist_ok=True)
    result = []
    for fname in sorted(os.listdir(_CHOREO_DIR)):
        if not fname.endswith('.chor'):
            continue
        name = fname[:-5]
        if name.startswith('__'):
            continue  # skip temp/preview files (e.g. __preview__)
        try:
            with open(os.path.join(_CHOREO_DIR, fname), encoding='utf-8') as f:
                meta = json.load(f).get('meta', {})
        except Exception:
            meta = {}
        result.append({
            'name':     name,
            'label':    meta.get('label', '') or '',
            'category': meta.get('category', '') or _SYSTEM_CATEGORY,
            'emoji':    meta.get('emoji', '') or _auto_emoji(name),
            'duration': meta.get('duration', 0),
        })
    return jsonify(result)


@choreo_bp.get('/choreo/categories')
def get_categories():
    cats = sorted(_load_categories(), key=lambda c: c.get('order', 99))
    return jsonify(cats)


@choreo_bp.post('/choreo/categories')
def manage_categories():
    data = request.get_json(silent=True) or {}
    action = data.get('action', '')
    cats = _load_categories()
    ids = [c['id'] for c in cats]

    if action == 'create':
        cat_id    = data.get('id', '').strip().lower().replace(' ', '_')
        cat_label = data.get('label', '').strip()
        cat_emoji = data.get('emoji', '📦').strip()
        if not cat_id or not cat_label:
            return jsonify({'error': 'id and label required'}), 400
        if cat_id in ids:
            return jsonify({'error': 'id already exists'}), 409
        cats.append({'id': cat_id, 'label': cat_label, 'emoji': cat_emoji,
                     'order': max((c.get('order', 0) for c in cats), default=0) + 1})
        _save_categories(cats)
        return jsonify({'status': 'ok', 'id': cat_id})

    elif action == 'update':
        cat_id    = data.get('id', '')
        cat_emoji = data.get('emoji', '').strip()
        cat_label = data.get('label', '').strip()
        for c in cats:
            if c['id'] == cat_id:
                if cat_emoji:
                    c['emoji'] = cat_emoji
                if cat_label:
                    c['label'] = cat_label
                _save_categories(cats)
                return jsonify({'status': 'ok'})
        return jsonify({'error': 'category not found'}), 404

    elif action == 'reorder':
        new_order = data.get('order', [])
        cat_map = {c['id']: c for c in cats}
        reordered = []
        for i, cat_id in enumerate(new_order):
            if cat_id in cat_map:
                cat_map[cat_id]['order'] = i
                reordered.append(cat_map[cat_id])
        # Add any missing cats at end
        for c in cats:
            if c['id'] not in new_order:
                reordered.append(c)
        _save_categories(reordered)
        return jsonify({'status': 'ok'})

    elif action == 'delete':
        cat_id = data.get('id', '')
        if cat_id == _SYSTEM_CATEGORY:
            return jsonify({'error': 'cannot delete system category'}), 400
        if cat_id not in ids:
            return jsonify({'error': 'category not found'}), 404
        # Move sequences in this category to newchoreo
        for fname in os.listdir(_CHOREO_DIR):
            if not fname.endswith('.chor'):
                continue
            fpath = os.path.join(_CHOREO_DIR, fname)
            try:
                with open(fpath, encoding='utf-8') as f:
                    chor = json.load(f)
                if chor.get('meta', {}).get('category') == cat_id:
                    chor['meta']['category'] = _SYSTEM_CATEGORY
                    with open(fpath, 'w', encoding='utf-8') as f:
                        json.dump(chor, f, indent=2, ensure_ascii=False)
            except Exception:
                pass
        cats = [c for c in cats if c['id'] != cat_id]
        _save_categories(cats)
        return jsonify({'status': 'ok'})

    return jsonify({'error': f'unknown action: {action}'}), 400


@choreo_bp.post('/choreo/set-category')
def set_choreo_category():
    data = request.get_json(silent=True) or {}
    name     = data.get('name', '').strip()
    category = data.get('category', '').strip()
    if not name or not category:
        return jsonify({'error': 'name and category required'}), 400
    path, err = _safe_choreo_path(name)
    if err:
        return err
    if not os.path.exists(path):
        return jsonify({'error': 'not found'}), 404
    with open(path, encoding='utf-8') as f:
        chor = json.load(f)
    chor.setdefault('meta', {})['category'] = category
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(chor, f, indent=2, ensure_ascii=False)
    return jsonify({'status': 'ok'})


@choreo_bp.post('/choreo/set-emoji')
def set_choreo_emoji():
    data = request.get_json(silent=True) or {}
    name  = data.get('name', '').strip()
    emoji = data.get('emoji', '').strip()
    if not name:
        return jsonify({'error': 'name required'}), 400
    path, err = _safe_choreo_path(name)
    if err:
        return err
    if not os.path.exists(path):
        return jsonify({'error': 'not found'}), 404
    with open(path, encoding='utf-8') as f:
        chor = json.load(f)
    chor.setdefault('meta', {})['emoji'] = emoji  # empty string = revert to auto
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(chor, f, indent=2, ensure_ascii=False)
    return jsonify({'status': 'ok'})


@choreo_bp.post('/choreo/set-label')
def set_choreo_label():
    data = request.get_json(silent=True) or {}
    name  = data.get('name', '').strip()
    label = data.get('label', '').strip()
    if not name:
        return jsonify({'error': 'name required'}), 400
    path, err = _safe_choreo_path(name)
    if err:
        return err
    if not os.path.exists(path):
        return jsonify({'error': 'not found'}), 404
    with open(path, encoding='utf-8') as f:
        chor = json.load(f)
    chor.setdefault('meta', {})['label'] = label  # empty string = revert to filename
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(chor, f, indent=2, ensure_ascii=False)
    return jsonify({'status': 'ok'})


@choreo_bp.post('/choreo/rename')
def choreo_rename():
    """Rename a .chor file. Body: {"old_name": "foo", "new_name": "bar"}"""
    data = request.get_json(silent=True) or {}
    old_name = data.get('old_name', '').strip()
    new_name = data.get('new_name', '').strip()
    if not old_name or not new_name:
        return jsonify({'error': 'old_name and new_name required'}), 400
    if old_name == new_name:
        return jsonify({'status': 'ok', 'name': new_name})
    old_path, err = _safe_choreo_path(old_name)
    if err:
        return err
    new_path, err = _safe_choreo_path(new_name)
    if err:
        return err
    if not os.path.exists(old_path):
        return jsonify({'error': 'not found'}), 404
    if os.path.exists(new_path):
        return jsonify({'error': f'"{new_name}" already exists'}), 409
    with open(old_path, encoding='utf-8') as f:
        chor = json.load(f)
    chor.setdefault('meta', {})['name'] = new_name
    with open(new_path, 'w', encoding='utf-8') as f:
        json.dump(chor, f, indent=2, ensure_ascii=False)
    os.remove(old_path)
    log.info(f"Choreo renamed: {old_name} → {new_name}")
    return jsonify({'status': 'ok', 'old_name': old_name, 'new_name': new_name})


@choreo_bp.get('/choreo/load')
def choreo_load():
    name = request.args.get('name', '')
    if not name:
        return jsonify({'error': 'name required'}), 400
    path, err = _safe_choreo_path(name)
    if err:
        return err
    if not os.path.exists(path):
        return jsonify({'error': 'not found'}), 404
    with open(path, encoding='utf-8') as f:
        chor = json.load(f)
    # Migrate legacy audio2 track → unified audio track with ch=1
    tracks = chor.get('tracks', {})
    audio2 = tracks.pop('audio2', [])
    if audio2:
        audio = tracks.setdefault('audio', [])
        for ev in audio2:
            audio.append({**ev, 'ch': 1})
        tracks['audio'].sort(key=lambda e: e.get('t', 0))
    return jsonify(chor)


@choreo_bp.post('/choreo/save')
def choreo_save():
    data = request.get_json(silent=True) or {}
    chor = data.get('chor')
    if not chor or 'meta' not in chor:
        return jsonify({'error': 'invalid chor'}), 400
    name = chor['meta'].get('name', 'untitled')
    path, err = _safe_choreo_path(name)
    if err:
        return err
    os.makedirs(_CHOREO_DIR, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(chor, f, indent=2, ensure_ascii=False)
    log.info(f"Choreo saved: {name}")
    return jsonify({'status': 'ok', 'name': name})


@choreo_bp.delete('/choreo/<name>')
def choreo_delete(name: str):
    """Delete a choreography file by name."""
    path, err = _safe_choreo_path(name)
    if err:
        return err
    if not os.path.exists(path):
        return jsonify({'error': 'not found'}), 404
    try:
        os.remove(path)
        log.info(f"Choreo deleted: {name}")
        return jsonify({'status': 'ok', 'name': name})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


_BODY_PANELS = [f'Servo_S{i}' for i in range(12)]   # S0–S11 — body panels only (arms excluded)

# Safety buffer after every close-dispatch thread has joined. The arm/body
# UART path is non-blocking (the driver send() returns once the bytes hit
# the wire) so when the threads finish, the Slave may still be processing
# the SRV queue. The dome path joins fully (close() blocks on the I2C
# ramp), so this buffer mostly covers the body/arm UART tail.
_SERVO_RESET_TAIL = 0.4
# Per-thread join timeout — a single stuck servo cannot hold the choreo
# play request open indefinitely.
_SERVO_RESET_JOIN_TIMEOUT = 3.0


def _get_arm_servos() -> list:
    """Read arm servo IDs from local.cfg [arms]. Returns empty list if not configured."""
    cfg = configparser.ConfigParser()
    cfg.read(_LOCAL_CFG)
    count = cfg.getint('arms', 'count', fallback=0)
    servos = []
    for i in range(1, count + 1):
        s = cfg.get('arms', f'arm_{i}', fallback='').strip()
        if s:
            servos.append(s)
    return servos


def _reset_servos():
    """Close arms + body panels (S0–S11) + dome panels in parallel before
    starting a new choreo.

    Why parallel? The OLD sequential implementation took ~7s on a typical
    install:
      - arm closes (UART): ~10 × 30ms                =  300ms
      - body closes (UART): ~12 × 30ms               =  360ms
      - dome closes (I2C blocking ramp): 11 × 500ms  = 5500ms
      - hard sleep buffer:                            = 1500ms
                                                       ≈ 7660ms

    Parallelizing brings dome ramps from sequential (5500ms) to
    concurrent (≈700ms — longest single ramp). Body/arm UART sends
    still serialize at the wire, but Python no longer waits between
    them. Total ≈2s — about 5s saved every time the user starts a
    new choreo while one is already playing.

    The dome driver protects its per-servo PWM writes with its own
    _lock, so spawning a thread per servo is safe. Body driver
    send() is also thread-safe (UARTController has an internal lock).
    """
    from master.api.servo_bp import (
        _read_panels_cfg, _panel_angle, _panel_speed, DOME_SERVOS
    )
    panels_cfg = _read_panels_cfg()
    arm_servos = _get_arm_servos()

    def _close_body(name, angle, speed):
        try:
            if reg.servo:
                reg.servo.close(name, angle, speed)
            elif reg.uart:
                reg.uart.send('SRV', f'{name},{angle},{speed}')
        except Exception:
            log.exception("reset_servos: body close failed: %s", name)

    def _close_dome(name, angle, speed):
        try:
            reg.dome_servo.close(name, angle, speed)
        except Exception:
            log.exception("reset_servos: dome close failed: %s", name)

    threads = []
    # Arm servos + body panels share the UART path on the Slave — fast send,
    # then Slave processes them serially. Spawning threads doesn't speed up
    # the UART wire but keeps the dispatch pipeline non-blocking from this
    # function's caller perspective.
    for name in arm_servos + _BODY_PANELS:
        angle = _panel_angle(name, 'close', panels_cfg)
        speed = _panel_speed(name, panels_cfg)
        t = threading.Thread(
            target=_close_body, args=(name, angle, speed),
            daemon=True, name=f'reset-{name}',
        )
        t.start()
        threads.append(t)

    # Dome servos run blocking I2C ramps on the Master — true parallelism
    # here saves the most time. Each dome thread holds its own per-servo
    # lock inside the driver, so they don't serialize against each other.
    if reg.dome_servo:
        for name in DOME_SERVOS:
            angle = _panel_angle(name, 'close', panels_cfg)
            speed = _panel_speed(name, panels_cfg)
            t = threading.Thread(
                target=_close_dome, args=(name, angle, speed),
                daemon=True, name=f'reset-{name}',
            )
            t.start()
            threads.append(t)

    # Wait for every dispatch to finish — but cap per-thread so one stuck
    # servo can't pin the play request indefinitely.
    for t in threads:
        t.join(timeout=_SERVO_RESET_JOIN_TIMEOUT)
        if t.is_alive():
            log.warning("reset_servos: thread %s exceeded %.1fs join timeout",
                        t.name, _SERVO_RESET_JOIN_TIMEOUT)


@choreo_bp.post('/choreo/play')
def choreo_play():
    if not reg.choreo:
        return jsonify({'error': 'choreo player not available'}), 503
    data = request.get_json(silent=True) or {}
    name = data.get('name', '')
    if not name:
        return jsonify({'error': 'name required'}), 400
    path, err = _safe_choreo_path(name)
    if err:
        return err
    if not os.path.exists(path):
        return jsonify({'error': f'choreography not found: {name}'}), 404
    with open(path, encoding='utf-8') as f:
        chor = json.load(f)

    # Coalesce concurrent play requests: a second request waits for the first
    # to finish stopping/starting before deciding what to do.
    if not _play_lock.acquire(timeout=5.0):
        return jsonify({'error': 'play queue busy'}), 503
    try:
        # If a choreo is already playing: stop it, reset all servos, then start the new one
        if reg.choreo.is_playing():
            log.info("Choreo already playing — stopping and resetting servos before starting '%s'", name)
            reg.choreo.stop()
            try:
                _reset_servos()  # parallel dispatch — joins internally per thread
            except Exception:
                log.exception("Servo reset failed — continuing with choreo start anyway")
            # Short tail buffer — the dome joins fully but the body/arm UART
            # queue on the Slave may still be draining when our threads
            # returned. Keep this tight so we don't undo the parallelization
            # gains. Was 1.5s on top of the old ~6s sequential reset.
            time.sleep(_SERVO_RESET_TAIL)

        loop = bool(data.get('loop', False))
        ok = reg.choreo.play(chor, loop=loop)
        if not ok:
            return jsonify({'error': 'already playing'}), 409
        return jsonify({'status': 'ok', 'name': name, 'duration': chor['meta']['duration']})
    finally:
        _play_lock.release()


@choreo_bp.post('/choreo/stop')
def choreo_stop():
    if reg.choreo:
        reg.choreo.stop()
    return jsonify({'status': 'ok'})


@choreo_bp.get('/choreo/status')
def choreo_status():
    if not reg.choreo:
        return jsonify({'playing': False, 'name': None, 't_now': 0.0, 'duration': 0.0})
    return jsonify(reg.choreo.get_status())


@choreo_bp.post('/choreo/export_scr')
def choreo_export_scr():
    if not reg.choreo:
        return jsonify({'error': 'choreo player not available'}), 503
    data = request.get_json(silent=True) or {}
    name = data.get('name', '')
    if not name:
        return jsonify({'error': 'name required'}), 400
    path, err = _safe_choreo_path(name)
    if err:
        return err
    if not os.path.exists(path):
        return jsonify({'error': 'not found'}), 404
    with open(path, encoding='utf-8') as f:
        chor = json.load(f)
    scr = reg.choreo.export_scr(chor)
    return jsonify({'status': 'ok', 'name': name, 'scr': scr})
