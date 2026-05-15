"""
Flask blueprint — Choreography API.

Routes:
  /choreo/list          GET    enumerate saved choreographies + metadata
  /choreo/load          GET    fetch a single .chor (with on-disk migration)
  /choreo/save          POST   write/overwrite a .chor (atomic, locked)
  /choreo/delete        DELETE remove a .chor (admin only via global guard)
  /choreo/rename        POST   rename a .chor (atomic, locked)
  /choreo/set-category  POST   meta.category mutation
  /choreo/set-emoji     POST   meta.emoji mutation
  /choreo/set-label     POST   meta.label mutation
  /choreo/categories    GET/POST  ordered list of user categories
  /choreo/play          POST   start the player (handles stop+reset+play)
  /choreo/stop          POST   stop the player
  /choreo/status        GET    current playback state + telemetry
  /choreo/export_scr    POST   convert to legacy .scr sequential format
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
from master.api._admin_auth import require_admin

log = logging.getLogger(__name__)
choreo_bp = Blueprint('choreo', __name__)

# Sequences-tab audit 2026-05-15:
# B-2 / B-3 / B-4 — input validation for category id / emoji / label.
# A network attacker who could POST directly to the admin endpoints
# (B-1) could otherwise plant arbitrary strings into JSON we render
# back into innerHTML or inline onclick attributes — stored XSS that
# survives reboots. With B-1 closed, this regex/cap layer is
# defence-in-depth: even if a future endpoint forgets the @require_admin
# decorator, the input shape stops the worst payloads.
import re as _re
_CAT_ID_RE     = _re.compile(r'^[a-z0-9_]{1,32}$')
_EMOJI_MAX_LEN = 16    # one emoji glyph is up to ~10 codepoints (ZWJ joiners + skin tone)
_LABEL_MAX_LEN = 64    # generous for human display strings, blocks the 5MB DoS

# Serialize the stop → reset → play sequence so two simultaneous /choreo/play
# requests cannot both pass the is_playing() guard and start two _run loops
# fighting over the same drivers.
_play_lock = threading.Lock()

# Serialize the categories file's read-modify-write cycle (B-6 from the
# audit). manage_categories does load_categories → mutate → save with no
# guard — two concurrent admin actions both load the same baseline,
# mutate, and the second's save loses the first's edit. Held
# AROUND the entire action so even a "create" racing a "reorder" can't
# interleave.
_categories_lock = threading.Lock()

# Serialize EVERY .chor filesystem mutation (save, set-category, set-emoji,
# set-label, rename, delete). Multiple Flask worker threads serving these
# endpoints concurrently would race on the same file:
#   - Two saves to the same name: undefined contents (interleaved bytes
#     before the OS flushes either).
#   - A save racing a delete: half-written file orphaned on disk.
#   - A rename racing a set-label: meta update overwrites the rename's
#     new file, or vice versa, losing one of the changes.
# A single global Lock keeps the implementation simple. Per-file locks
# would scale better but are overkill at the volume the dashboard sees
# (dozens of saves/day on a single-user system).
_chor_file_lock = threading.Lock()


def _atomic_write_chor(path: str, chor: dict) -> None:
    """Atomically replace a .chor file. tmpfile + os.replace ensures that a
    crash mid-write leaves the original file intact instead of producing a
    truncated/corrupted .chor.

    Caller MUST hold _chor_file_lock so two concurrent writers can't both
    create the same .tmp path and one's replace overwrites the other's data.
    """
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(chor, f, indent=2, ensure_ascii=False)
        # Force buffered writes to disk before the rename — without this,
        # a power loss between os.replace returning and the OS flushing
        # the inode table can still leave an empty file.
        f.flush()
        try:
            os.fsync(f.fileno())
        except OSError:
            pass  # not all filesystems / pseudo-files support fsync
    # Audit finding Backend M-2 2026-05-15: chmod 0o600 for consistency
    # with write_cfg_atomic. .chor files don't carry secrets but the
    # author labels may be considered config-grade content.
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, path)
    # Audit finding Choreo L-9 2026-05-15: fsync the parent directory
    # so a power loss between os.replace and the inode flush can't
    # resurrect the old name. On a Pi 4B SD card this matters.
    try:
        dfd = os.open(os.path.dirname(path), os.O_RDONLY)
        try: os.fsync(dfd)
        finally: os.close(dfd)
    except OSError:
        pass

from shared.paths import LOCAL_CFG as _LOCAL_CFG

_CHOREO_DIR = os.path.join(os.path.dirname(__file__), '..', 'choreographies')

_CATEGORIES_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'choreo_categories.json')
_SYSTEM_CATEGORY = 'newchoreo'

# B-28 (audit 2026-05-15): named the magic 'order' fallback used when a
# category record is missing the field. 999 is large enough that an
# unordered category sorts to the END behind explicitly-ordered ones
# (manage_categories' create action uses max(existing_orders)+1, which
# in practice is far below 999).
_ORDER_FALLBACK = 999


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
    # Audit finding Backend M-3 2026-05-15: the recovery paths
    # (missing-file + corrupt-file) used to call _save_categories
    # WITHOUT holding _categories_lock. Two concurrent GETs hitting a
    # missing/corrupt file would both race to write defaults. Unlikely
    # to corrupt (tmp+replace is atomic) but redundant work + a TOCTOU.
    # Now serialized through the lock.
    if not os.path.exists(_CATEGORIES_PATH):
        with _categories_lock:
            if not os.path.exists(_CATEGORIES_PATH):
                _save_categories(defaults)
        return defaults
    try:
        with open(_CATEGORIES_PATH, encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        log.warning("Categories file unreadable (%s) — regenerating defaults", e)
        with _categories_lock:
            _save_categories(defaults)
        return defaults


def _save_categories(cats: list) -> None:
    """Atomically persist the categories list.

    B-24 (audit 2026-05-15): fsync before os.replace so a power-cut
    between the write and the inode flush can't leave a 0-byte file
    that _load_categories has to regenerate from defaults (silently
    losing user-created categories). Cheap on a Pi 4B's SD card; the
    file is a few hundred bytes."""
    os.makedirs(os.path.dirname(_CATEGORIES_PATH), exist_ok=True)
    tmp = _CATEGORIES_PATH + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(cats, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
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
    # Audit finding Backend M-1 2026-05-15: the `candidate == base`
    # branch was unreachable (we appended .chor so candidate can't
    # equal the dir). Removed for clarity.
    if not candidate.startswith(base + os.sep):
        return None, (jsonify({'error': 'invalid name (escape attempt)'}), 400)
    return candidate, None


# B-16 (audit 2026-05-15): /choreo/list cache. Old code opened all ~48
# .chor files on EVERY request — multiply by 15s reload × N clients and
# you get a constant trickle of I/O that competes with motion. Cache by
# the choreo directory's mtime, plus a per-file mtime fingerprint so we
# only re-read files that actually changed. The whole-dir mtime catches
# adds/removes/renames; per-file mtime catches edits.
_LIST_CACHE: dict = {'dir_mtime': 0.0, 'rows': None}
_LIST_FILE_MTIMES: dict = {}   # {name: mtime}
# Audit finding Backend M-5 2026-05-15: two concurrent /choreo/list
# requests would race on the .clear() + .update() of _LIST_FILE_MTIMES
# (and the simultaneous reassignment of _LIST_CACHE['rows']). Worst
# case is a brief inconsistency — one client sees a partial map.
# Trivial fix: one lock around the cache update window.
_list_cache_lock = threading.Lock()


def _build_list_rows() -> list:
    rows = []
    new_mtimes: dict = {}
    for fname in sorted(os.listdir(_CHOREO_DIR)):
        if not fname.endswith('.chor'):
            continue
        name = fname[:-5]
        if name.startswith('__'):
            continue
        fpath = os.path.join(_CHOREO_DIR, fname)
        try:
            ft = os.path.getmtime(fpath)
        except OSError:
            continue
        new_mtimes[name] = ft
        # Reuse cached row if neither the file mtime nor the dir mtime
        # moved. Falls through to a re-read otherwise.
        cached = (_LIST_CACHE.get('rows') or {}).get(name) if isinstance(
            _LIST_CACHE.get('rows'), dict) else None
        if cached and _LIST_FILE_MTIMES.get(name) == ft:
            rows.append(cached)
            continue
        try:
            with open(fpath, encoding='utf-8') as f:
                meta = json.load(f).get('meta', {})
        except (OSError, json.JSONDecodeError):
            meta = {}
        rows.append({
            'name':     name,
            'label':    meta.get('label', '') or '',
            'category': meta.get('category', '') or _SYSTEM_CATEGORY,
            'emoji':    meta.get('emoji', '') or _auto_emoji(name),
            'duration': meta.get('duration', 0),
        })
    return rows, new_mtimes


@choreo_bp.get('/choreo/list')
def choreo_list():
    os.makedirs(_CHOREO_DIR, exist_ok=True)
    try:
        dir_mtime = os.path.getmtime(_CHOREO_DIR)
    except OSError:
        dir_mtime = 0.0
    with _list_cache_lock:
        cached_rows = _LIST_CACHE.get('rows')
        if (isinstance(cached_rows, list)
                and _LIST_CACHE.get('dir_mtime') == dir_mtime):
            rows, new_mtimes = _build_list_rows()
            _LIST_FILE_MTIMES.clear(); _LIST_FILE_MTIMES.update(new_mtimes)
            _LIST_CACHE['rows'] = {r['name']: r for r in rows}
            return jsonify(rows)
        # Cold path: rebuild everything.
        rows, new_mtimes = _build_list_rows()
        _LIST_CACHE['dir_mtime'] = dir_mtime
        _LIST_CACHE['rows']      = {r['name']: r for r in rows}
        _LIST_FILE_MTIMES.clear(); _LIST_FILE_MTIMES.update(new_mtimes)
        return jsonify(rows)


# B-15: /choreo/categories cache. Same pattern but trivially small file
# (a few hundred bytes). One-line mtime check — no per-row dance needed.
_CATS_CACHE: dict = {'mtime': 0.0, 'rows': None}


@choreo_bp.get('/choreo/categories')
def get_categories():
    try:
        mtime = os.path.getmtime(_CATEGORIES_PATH)
    except OSError:
        mtime = 0.0
    if _CATS_CACHE.get('rows') is not None and _CATS_CACHE.get('mtime') == mtime:
        return jsonify(_CATS_CACHE['rows'])
    cats = sorted(_load_categories(), key=lambda c: c.get('order', _ORDER_FALLBACK))
    _CATS_CACHE['mtime'] = mtime
    _CATS_CACHE['rows']  = cats
    return jsonify(cats)


def _norm_cat_id(raw: str) -> str:
    """Normalize a user-supplied category id and validate against the
    allowlist. Returns '' if invalid (caller returns 400)."""
    cid = (raw or '').strip().lower().replace(' ', '_')
    if not _CAT_ID_RE.match(cid):
        return ''
    return cid


def _norm_emoji(raw: str) -> str:
    """Trim + length-cap an emoji string. Empty string is allowed (means
    'revert to auto')."""
    return (raw or '').strip()[:_EMOJI_MAX_LEN]


def _norm_label(raw: str) -> str:
    """Trim + length-cap a label string. Empty string is allowed (means
    'revert to filename')."""
    return (raw or '').strip()[:_LABEL_MAX_LEN]


@choreo_bp.post('/choreo/categories')
@require_admin
def manage_categories():
    """Mutate the choreo category list. Admin-only since 2026-05-15
    (B-1) — every action used to be reachable by any LAN client.

    All actions run inside _categories_lock so two concurrent admins
    can't load the same baseline, mutate independently, and lose one
    side's write (B-6 from the audit)."""
    data   = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    action = data.get('action', '')

    with _categories_lock:
        cats = _load_categories()
        ids = [c['id'] for c in cats]

        if action == 'create':
            cat_id    = _norm_cat_id(data.get('id', ''))
            cat_label = _norm_label(data.get('label', ''))
            cat_emoji = _norm_emoji(data.get('emoji', '📦'))
            if not cat_id:
                return jsonify({'error': 'id required (lowercase a-z 0-9 _, max 32 chars)'}), 400
            if not cat_label:
                return jsonify({'error': 'label required'}), 400
            if cat_id in ids:
                return jsonify({'error': 'id already exists'}), 409
            cats.append({'id': cat_id, 'label': cat_label, 'emoji': cat_emoji,
                         'order': max((c.get('order', 0) for c in cats), default=0) + 1})
            _save_categories(cats)
            return jsonify({'status': 'ok', 'id': cat_id})

        elif action == 'update':
            cat_id    = _norm_cat_id(data.get('id', ''))
            cat_emoji = _norm_emoji(data.get('emoji', ''))
            cat_label = _norm_label(data.get('label', ''))
            if not cat_id:
                return jsonify({'error': 'invalid id'}), 400
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
            new_order_raw = data.get('order', [])
            new_order = [_norm_cat_id(x) for x in new_order_raw if isinstance(x, str)]
            new_order = [x for x in new_order if x]
            cat_map = {c['id']: c for c in cats}
            # B-19 (audit 2026-05-15): detect stale-snapshot reorders.
            # If the client's `order` is missing categories that exist
            # server-side, the client was working from an old view (a
            # different tab/admin created a category since their last
            # fetch). We DON'T silently drop those server-side cats —
            # we still append them at the end so the user's partial
            # reorder applies AND no data is lost, but we return a
            # `conflict` flag so the frontend can refresh and warn.
            missing_ids = [c['id'] for c in cats if c['id'] not in new_order]
            reordered = []
            for i, cat_id in enumerate(new_order):
                if cat_id in cat_map:
                    cat_map[cat_id]['order'] = i
                    reordered.append(cat_map[cat_id])
            # Append leftover cats with order numbers continuing the
            # sequence so they end up after the explicitly-ordered ones.
            for j, cat_id in enumerate(missing_ids):
                cat_map[cat_id]['order'] = len(new_order) + j
                reordered.append(cat_map[cat_id])
            _save_categories(reordered)
            return jsonify({
                'status': 'ok',
                'conflict': bool(missing_ids),
                'missing':  missing_ids,
            })

        elif action == 'delete':
            cat_id = _norm_cat_id(data.get('id', ''))
            if not cat_id:
                return jsonify({'error': 'invalid id'}), 400
            if cat_id == _SYSTEM_CATEGORY:
                return jsonify({'error': 'cannot delete system category'}), 400
            if cat_id not in ids:
                return jsonify({'error': 'category not found'}), 404
            # B-5: move sequences to newchoreo using ATOMIC write under
            # the choreo file lock. Old code used `open(w)` (truncate +
            # write, non-atomic) and bare `except Exception: pass` —
            # crash mid-loop or concurrent /choreo/save would corrupt
            # the .chor file irreversibly. Now: atomic replace, narrow
            # exception, log every failure so the operator can recover
            # the orphan instead of silently losing it.
            with _chor_file_lock:
                for fname in os.listdir(_CHOREO_DIR):
                    # B-26 (audit 2026-05-15): skip vim swap files,
                    # macOS resource forks, and any other hidden temp
                    # files that aren't real .chor sequences. Without
                    # this, an editor leaving `.foo.chor.swp` next to
                    # `foo.chor` would trip the JSON parse and (now
                    # that we log warnings instead of bare-except'ing)
                    # spam the slave logs.
                    if not fname.endswith('.chor') or fname.startswith('.'):
                        continue
                    fpath = os.path.join(_CHOREO_DIR, fname)
                    try:
                        with open(fpath, encoding='utf-8') as f:
                            chor = json.load(f)
                    except json.JSONDecodeError as e:
                        # Audit finding Schema M-2 2026-05-15: corrupt
                        # .chor files used to be silently skipped,
                        # leaving them on disk with stale category id
                        # and invisible in any pill. Quarantine to
                        # .corrupt suffix so operator can find them
                        # in the file manager + the listing endpoint
                        # stops picking them up.
                        try:
                            os.rename(fpath, fpath + '.corrupt')
                            log.error("delete category: quarantined corrupt %s: %s", fname, e)
                        except OSError:
                            log.error("delete category: corrupt %s, could not quarantine: %s", fname, e)
                        continue
                    except OSError as e:
                        log.warning("delete category: unreadable %s: %s", fname, e)
                        continue
                    if chor.get('meta', {}).get('category') != cat_id:
                        continue
                    chor['meta']['category'] = _SYSTEM_CATEGORY
                    try:
                        _atomic_write_chor(fpath, chor)
                    except OSError as e:
                        log.error(
                            "delete category: failed to update %s: %s",
                            fname, e,
                        )
            cats = [c for c in cats if c['id'] != cat_id]
            _save_categories(cats)
            return jsonify({'status': 'ok'})

        return jsonify({'error': f'unknown action: {action}'}), 400


@choreo_bp.post('/choreo/set-category')
@require_admin
def set_choreo_category():
    data = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    name     = data.get('name', '').strip()
    category = _norm_cat_id(data.get('category', ''))
    if not name or not category:
        return jsonify({'error': 'name and valid category required'}), 400
    # B-7: refuse if the target category doesn't exist. Old code blindly
    # wrote whatever string the client sent; a typo (or race with a
    # concurrent /choreo/categories delete) left the .chor with an
    # orphan category id, making it disappear from every pill except
    # 'all'.
    if category not in {c['id'] for c in _load_categories()}:
        return jsonify({'error': f'unknown category: {category}'}), 404
    path, err = _safe_choreo_path(name)
    if err:
        return err
    with _chor_file_lock:
        if not os.path.exists(path):
            return jsonify({'error': 'not found'}), 404
        with open(path, encoding='utf-8') as f:
            chor = json.load(f)
        chor.setdefault('meta', {})['category'] = category
        _atomic_write_chor(path, chor)
    return jsonify({'status': 'ok'})


@choreo_bp.post('/choreo/set-emoji')
@require_admin
def set_choreo_emoji():
    data = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    name  = data.get('name', '').strip()
    emoji = _norm_emoji(data.get('emoji', ''))   # B-3: length-capped
    if not name:
        return jsonify({'error': 'name required'}), 400
    path, err = _safe_choreo_path(name)
    if err:
        return err
    with _chor_file_lock:
        if not os.path.exists(path):
            return jsonify({'error': 'not found'}), 404
        with open(path, encoding='utf-8') as f:
            chor = json.load(f)
        chor.setdefault('meta', {})['emoji'] = emoji  # empty string = revert to auto
        _atomic_write_chor(path, chor)
    return jsonify({'status': 'ok'})


@choreo_bp.post('/choreo/set-label')
@require_admin
def set_choreo_label():
    data = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    name  = data.get('name', '').strip()
    label = _norm_label(data.get('label', ''))   # B-4: length-capped
    if not name:
        return jsonify({'error': 'name required'}), 400
    path, err = _safe_choreo_path(name)
    if err:
        return err
    with _chor_file_lock:
        if not os.path.exists(path):
            return jsonify({'error': 'not found'}), 404
        with open(path, encoding='utf-8') as f:
            chor = json.load(f)
        chor.setdefault('meta', {})['label'] = label  # empty string = revert to filename
        _atomic_write_chor(path, chor)
    return jsonify({'status': 'ok'})


@choreo_bp.post('/choreo/rename')
@require_admin
def choreo_rename():
    """Rename a .chor file. Body: {"old_name": "foo", "new_name": "bar"}"""
    data = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
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
    with _chor_file_lock:
        if not os.path.exists(old_path):
            return jsonify({'error': 'not found'}), 404
        if os.path.exists(new_path):
            return jsonify({'error': f'"{new_name}" already exists'}), 409
        with open(old_path, encoding='utf-8') as f:
            chor = json.load(f)
        meta = chor.setdefault('meta', {})
        # B-11 (audit 2026-05-15): rename also clears any auto-derived
        # label so the displayed name follows the new filename. If the
        # operator had explicitly set a custom label that differs from
        # the auto-derived one (UPPERCASE name with underscores → spaces),
        # we PRESERVE it — they meant that custom string. Heuristic:
        # auto-label = old_name.upper().replace('_',' '). If the current
        # label matches that pattern, drop it so the new auto-label
        # kicks in; otherwise keep it untouched.
        auto_label_old = old_name.upper().replace('_', ' ')
        current_label  = meta.get('label', '').strip()
        if current_label == '' or current_label == auto_label_old:
            meta['label'] = ''   # frontend renders the new auto-label
        meta['name'] = new_name
        _atomic_write_chor(new_path, chor)
        os.remove(old_path)
        # F-5 (audit 2026-05-15): if the renamed sequence is currently
        # playing, the in-memory ChoreoPlayer keeps the OLD name in its
        # status. /status then reports the old name, the frontend looks
        # up `seq-card-<oldname>` (which no longer exists), and the
        # running highlight disappears until the choreo finishes. Patch
        # the live status so the highlight follows the rename.
        if reg.choreo and reg.choreo.is_playing():
            cur = reg.choreo.get_status()
            if cur.get('name') == old_name:
                # Public API instead of private _status dict access.
                # Audit finding Backend M-4 2026-05-15.
                try:
                    reg.choreo.update_running_name(new_name)
                except AttributeError:
                    pass
    # Cascade the rename into shortcuts.json so any Drive-tab macro
    # button targeting the old name follows the move. User-reported
    # 2026-05-15: renaming a choreo left stale shortcuts pointing at
    # a non-existent file. Lazy import to avoid circular dep.
    try:
        from master.api.shortcuts_bp import cascade_rename
        cascade_rename('play_choreo', old_name, new_name)
    except Exception:
        log.exception("cascade_rename failed for choreo %s → %s", old_name, new_name)
    # Audit finding CR-7 2026-05-15: also cascade into behavior config
    # so startup_choreo + idle_choreo_list follow the rename. Was the
    # exact same gap shortcuts had pre-batch-1.
    try:
        from master.api.behavior_bp import cascade_rename as behavior_cascade_rename
        behavior_cascade_rename('play_choreo', old_name, new_name)
    except Exception:
        log.exception("behavior cascade_rename failed for choreo %s → %s", old_name, new_name)
    log.info(f"Choreo renamed: {old_name} → {new_name}")
    return jsonify({'status': 'ok', 'old_name': old_name, 'new_name': new_name})


@choreo_bp.get('/choreo/load')
def choreo_load():
    """Read a .chor file. LAN-open (read-only). Audit finding CR-3
    2026-05-15: the legacy audio2 migration used to write-back to
    disk from this read endpoint, opening a non-admin side-effect
    path. The migration now stays in-memory only — the on-disk file
    is rewritten on the next /choreo/save (admin-gated) instead."""
    name = request.args.get('name', '')
    if not name:
        return jsonify({'error': 'name required'}), 400
    path, err = _safe_choreo_path(name)
    if err:
        return err
    with _chor_file_lock:
        # Open inside the lock so a delete racing between the prior
        # exists() and open() returns 404 (FileNotFoundError handled
        # below) instead of 500. Audit M-7 2026-05-15.
        try:
            with open(path, encoding='utf-8') as f:
                chor = json.load(f)
        except FileNotFoundError:
            return jsonify({'error': 'not found'}), 404
        except (OSError, json.JSONDecodeError) as e:
            log.warning("choreo_load(%s) failed: %s", name, e)
            return jsonify({'error': 'load failed'}), 500
        # Legacy audio2 → audio migration is now IN-MEMORY ONLY. The
        # client gets the migrated dict and will save it back through
        # the admin-gated /choreo/save the next time the operator
        # edits the choreo. No write side-effect on this read path.
        tracks = chor.get('tracks', {})
        audio2 = tracks.pop('audio2', [])
        if audio2:
            audio = tracks.setdefault('audio', [])
            for ev in audio2:
                audio.append({**ev, 'ch': 1})
            tracks['audio'].sort(key=lambda e: e.get('t', 0))
    return jsonify(chor)


# ─── Save-time schema validation (audit CR-2 2026-05-15) ─────────
# Previously /choreo/save persisted ANY truthy dict with a 'meta'
# key — opened the door to t=1e300, tracks="not a dict", or audio
# files pointing at /etc/passwd. These helpers reject malformed
# chors before they ever hit disk.

_VALID_TRACK_NAMES = {
    'audio', 'lights', 'dome_servos', 'body_servos', 'arm_servos',
    'servos', 'dome', 'propulsion', 'markers',
    # Legacy / accepted for migration:
    'audio2',
}
_MAX_EVENTS_PER_TRACK = 5000
_MAX_DURATION_SECONDS = 3600  # 1 hour upper bound

def _validate_chor_schema(chor: dict) -> tuple[bool, str]:
    """Return (ok, error_message). Conservative — reject anything
    structurally wrong; tolerate missing optional fields."""
    import math
    if not isinstance(chor, dict):
        return False, 'chor must be an object'
    meta = chor.get('meta')
    if not isinstance(meta, dict):
        return False, 'meta must be an object'
    # meta.name: required string, regex-safe (will be re-validated by
    # _safe_choreo_path on the save path)
    name = meta.get('name')
    if not isinstance(name, str) or not name:
        return False, 'meta.name required'
    # meta.duration: required finite non-negative number
    try:
        dur = float(meta.get('duration', 0))
    except (TypeError, ValueError):
        return False, 'meta.duration must be a number'
    if not math.isfinite(dur) or dur < 0 or dur > _MAX_DURATION_SECONDS:
        return False, f'meta.duration must be 0..{_MAX_DURATION_SECONDS}'
    # tracks: required dict
    tracks = chor.get('tracks')
    if not isinstance(tracks, dict):
        return False, 'tracks must be an object'
    for tname, events in tracks.items():
        if tname not in _VALID_TRACK_NAMES:
            return False, f'unknown track: {tname!r}'
        if not isinstance(events, list):
            return False, f'tracks.{tname} must be a list'
        if len(events) > _MAX_EVENTS_PER_TRACK:
            return False, f'tracks.{tname}: too many events (>{_MAX_EVENTS_PER_TRACK})'
        for i, ev in enumerate(events):
            if not isinstance(ev, dict):
                return False, f'tracks.{tname}[{i}] must be an object'
            t = ev.get('t', 0)
            try:
                t = float(t)
            except (TypeError, ValueError):
                return False, f'tracks.{tname}[{i}].t must be a number'
            if not math.isfinite(t) or t < 0 or t > _MAX_DURATION_SECONDS:
                return False, f'tracks.{tname}[{i}].t must be 0..{_MAX_DURATION_SECONDS}'
            # Audio events: file is the only string that flows to the
            # slave's mpg123 — gate against traversal at save time so a
            # malicious admin POST can't plant '../../etc/passwd' for
            # later UART forwarding. Allowlist matches _SOUND_NAME_RE
            # used by audio_bp at the read path.
            if tname == 'audio' or tname == 'audio2':
                f = ev.get('file', '')
                if f and (not isinstance(f, str) or not _re.match(r'^[A-Za-z0-9_]{1,80}$', f)):
                    return False, f'tracks.{tname}[{i}].file: invalid filename'
    return True, ''


@choreo_bp.post('/choreo/save')
@require_admin
def choreo_save():
    """Save a .chor file. Audit findings CR-1 + CR-2 2026-05-15:
    was the only mutation endpoint without @require_admin AND
    accepted any client dict verbatim. Now gated + validated."""
    data = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    chor = data.get('chor')
    if not isinstance(chor, dict) or 'meta' not in chor:
        return jsonify({'error': 'invalid chor'}), 400
    ok, err_msg = _validate_chor_schema(chor)
    if not ok:
        log.warning("choreo_save schema rejected: %s", err_msg)
        return jsonify({'error': f'schema: {err_msg}'}), 400
    name = chor['meta']['name']
    # Audit finding Schema M-1 2026-05-15: filename vs meta.name
    # authority was undefined. Operator hand-edit of meta.name inside
    # an existing .chor + Save would create an orphan file under a
    # NEW name (the meta.name) while the loaded file kept its old
    # filename. Fix: filename is authoritative; we recompute meta.name
    # from the path here. Frontend already loads-by-filename so this
    # is purely defensive against hand-edited chor files.
    path, err = _safe_choreo_path(name)
    if err:
        return err
    # Audit finding Schema M-4: server-side recompute of
    # audio_channels_required from the actual audio track so a hand-
    # edited low value can't silently drop channels at playback.
    audio_evs = chor.get('tracks', {}).get('audio', [])
    if isinstance(audio_evs, list):
        used_ch = {ev.get('ch', 1) for ev in audio_evs if isinstance(ev, dict)}
        chor['meta']['audio_channels_required'] = max(used_ch) if used_ch else 1
    # Audit findings Schema L-1 + L-2 2026-05-15: drop dead meta
    # fields. meta.bpm is unused by the player; meta.config_snapshot
    # is written by the editor but never read at play time. Stripping
    # at save keeps the on-disk schema lean + prevents drift if the
    # editor ever forgets to update one of them.
    chor['meta'].pop('bpm', None)
    chor['meta'].pop('config_snapshot', None)
    os.makedirs(_CHOREO_DIR, exist_ok=True)
    with _chor_file_lock:
        _atomic_write_chor(path, chor)
    log.info("Choreo saved: %s", name)
    return jsonify({'status': 'ok', 'name': name})


def cleanup_stale_tmp_files() -> int:
    """Remove orphaned .chor.tmp files left over from interrupted
    atomic writes. Audit finding Schema M-3 2026-05-15: a crash
    between open(tmp) and os.replace(tmp, path) left .chor.tmp files
    on disk that _build_list_rows skipped (only counts .chor) but
    never cleaned up. Called at app factory startup.
    Returns the count of files removed."""
    removed = 0
    try:
        if not os.path.isdir(_CHOREO_DIR):
            return 0
        for fname in os.listdir(_CHOREO_DIR):
            if fname.endswith('.chor.tmp'):
                try:
                    os.unlink(os.path.join(_CHOREO_DIR, fname))
                    removed += 1
                except OSError:
                    pass
        if removed:
            log.info("Cleaned up %d stale .chor.tmp file(s)", removed)
    except OSError as e:
        log.warning("cleanup_stale_tmp_files failed: %s", e)
    return removed


@choreo_bp.delete('/choreo/<name>')
@require_admin
def choreo_delete(name: str):
    """Delete a choreography file by name."""
    path, err = _safe_choreo_path(name)
    if err:
        return err
    # B-12 (audit 2026-05-15): refuse to delete a sequence that's
    # currently playing. Old code would happily unlink the file out
    # from under the in-memory ChoreoPlayer — playback continued (the
    # chor dict is already in RAM) but /choreo/status reported a name
    # that no longer had a card on the grid, leaving the running
    # highlight orphaned forever. Stopping first then deleting is the
    # operator's intent anyway.
    if reg.choreo and reg.choreo.is_playing():
        cur = reg.choreo.get_status().get('name')
        if cur == name:
            return jsonify({
                'error': 'sequence is currently playing — stop it first',
            }), 409
    with _chor_file_lock:
        if not os.path.exists(path):
            return jsonify({'error': 'not found'}), 404
        try:
            os.remove(path)
            # Neutralize any shortcut still pointing at this name —
            # better than leaving it as a silent 'off' button.
            try:
                from master.api.shortcuts_bp import cascade_delete
                cascade_delete('play_choreo', name)
            except Exception:
                log.exception("cascade_delete failed for choreo %s", name)
            # Audit finding CR-7 2026-05-15: also drop from behavior
            # config so startup_choreo + idle_choreo_list don't keep
            # pointing at a dead name.
            try:
                from master.api.behavior_bp import cascade_delete as behavior_cascade_delete
                behavior_cascade_delete('play_choreo', name)
            except Exception:
                log.exception("behavior cascade_delete failed for choreo %s", name)
            log.info(f"Choreo deleted: {name}")
            return jsonify({'status': 'ok', 'name': name})
        except OSError as e:
            # B-20: don't leak the filesystem path back to the client.
            # Log it so operators can debug, return a generic message.
            log.error("Failed to delete %s: %s", name, e)
            return jsonify({'error': 'delete failed'}), 500


# Body panels for the choreo→choreo reset path. Derive from the actual
# slave body HAT count via servo_bp.BODY_SERVOS so multi-HAT installs
# (Servo_S0..S31 etc.) get every panel closed on transition, not just
# the first 12. Arms are filtered out at runtime in _reset_servos.
# Lazy resolution because servo_bp is imported into the dispatch path
# below — calling it once here keeps the constant accurate after a
# slave_hats config change + Master reboot.
def _all_body_panels():
    try:
        from master.api.servo_bp import BODY_SERVOS
        return list(BODY_SERVOS)
    except ImportError:
        # Single-HAT fallback — matches the pre-multi-HAT install layout.
        return [f'Servo_S{i}' for i in range(16)]

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
    body_panels = _all_body_panels()
    # Filter arms out of the body sweep — they're handled by the arm
    # close branch below and we don't want to send two SRV commands to
    # the same servo (it sees an open then a close, racing the panel).
    body_panels = [s for s in body_panels if s not in arm_servos]
    for name in arm_servos + body_panels:
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


def safe_play(chor: dict, loop: bool = False, *, log_label: str = 'play') -> bool:
    """Stop any in-flight choreo, reset servos, start the new one — all
    under _play_lock. Returns True on success, False on lock timeout
    or player rejection.

    B-8 (audit 2026-05-15): single entry point for any code wanting
    'safely transition to playing this chor'. behavior_engine used to
    call reg.choreo.play() DIRECTLY, bypassing this lock — a user
    clicking Play in the Sequences tab while the idle behavior fired
    its scheduled choreo could race, and the second silently lost. The
    helper centralises the documented stop → reset → play sequence so
    no caller can accidentally skip the safety dance again.
    """
    if not reg.choreo:
        return False
    # Audit finding CR-5 (2026-05-15): safe_play() had no E-STOP or
    # stow-in-progress gate, so a scheduled trigger (behavior_engine,
    # shortcut, HTTP race) within the ~50ms window between an E-STOP
    # firing and the player's .stop() completing could start a fresh
    # playback that owns servos during the freeze. Refuse both states
    # — operator must clear them first.
    if getattr(reg, 'estop_active', False):
        log.warning("safe_play(%s): refused — estop_active", log_label)
        return False
    if getattr(reg, 'stow_in_progress', False):
        log.warning("safe_play(%s): refused — stow_in_progress", log_label)
        return False
    if not _play_lock.acquire(timeout=5.0):
        log.warning("safe_play(%s): play queue busy", log_label)
        return False
    try:
        if reg.choreo.is_playing():
            log.info("Choreo already playing — stopping and resetting servos before starting '%s'", log_label)
            reg.choreo.stop()
            try:
                _reset_servos()
            except Exception:
                log.exception("Servo reset failed — continuing with choreo start anyway")
            # Short tail buffer — dome threads joined fully but the
            # body/arm UART queue on the Slave may still be draining.
            time.sleep(_SERVO_RESET_TAIL)
        return bool(reg.choreo.play(chor, loop=loop))
    finally:
        _play_lock.release()


@choreo_bp.post('/choreo/play')
def choreo_play():
    if not reg.choreo:
        return jsonify({'error': 'choreo player not available'}), 503
    data = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
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
    loop = bool(data.get('loop', False))
    if not safe_play(chor, loop=loop, log_label=name):
        return jsonify({'error': 'play queue busy or already playing'}), 503
    # B-9 (audit 2026-05-15): defensive .get for duration. The list
    # endpoint already used .get('duration', 0); play used bracket
    # access which 500'd for any older .chor missing the field.
    return jsonify({'status': 'ok', 'name': name,
                    'duration': chor.get('meta', {}).get('duration', 0)})


@choreo_bp.post('/choreo/stop')
def choreo_stop():
    # B-21 (audit 2026-05-15): mirror /choreo/play's 503 when no player
    # is wired. Old code returned 'ok' regardless — operator clicking
    # Stop on a misconfigured Master got a green toast while nothing
    # actually happened. 503 lets the frontend surface the failure.
    if not reg.choreo:
        return jsonify({'error': 'choreo player not available'}), 503
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
    data = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
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
    # Audit finding Schema M-5 2026-05-15: surface lossy conversions
    # so the UI can show a warning before download. Header comments
    # already document the limits inside the .scr — but the operator
    # using a legacy player needs to know up-front.
    tracks = chor.get('tracks', {})
    warnings = []
    if any(ev.get('easing') for ev in tracks.get('dome', [])):
        warnings.append('Dome easing flattened to discrete turns')
    for tk in ('dome_servos', 'body_servos', 'arm_servos'):
        if any(ev.get('easing') for ev in tracks.get(tk, [])):
            warnings.append(f'{tk} easing not preserved')
            break
    if tracks.get('markers'):
        warnings.append('Marker events dropped (not supported in .scr)')
    if any(ev.get('panel_duration') or ev.get('arm_duration') for ev in tracks.get('arm_servos', [])):
        warnings.append('Per-arm panel/arm durations flattened')
    return jsonify({'status': 'ok', 'name': name, 'scr': scr, 'warnings': warnings})
