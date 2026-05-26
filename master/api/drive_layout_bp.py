"""Per-device Drive-tab layout persistence (Custom Drive Layout feature).

Mirrors the custom-themes pattern: a single JSON file keyed by deviceKey, with
localStorage acting as the client-side mirror. GET is LAN-open (read); POST is
admin-gated. Coordinates are percentages (0..100) of the .drive-main box.

SAFETY: this only ever stores positions for elements *inside* .drive-main (the two
joysticks + individual shortcut buttons). The .drive-bottom-bar (E-STOP, Speed,
ALIVE, Camera, Lock, Bluetooth) is never represented here — it is fixed by design.
"""
import os
import re
import json
import math
import tempfile

from flask import Blueprint, jsonify

from master.api._admin_auth import require_admin, get_json_object

drive_layout_bp = Blueprint('drive_layout', __name__)

# master/config/drive_layouts.json — sits next to this file's parent (master/).
_CFG = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'drive_layouts.json')

_KEY_RE = re.compile(r'^[A-Za-z0-9_]{1,40}$')    # e.g. touch_834x1194
_SID_RE = re.compile(r'^[A-Za-z0-9_\-]{1,32}$')   # shortcut slot id
_MAX_DEVICES = 64
_MAX_SHORTCUTS = 24


def _valid_device_key(k):
    return isinstance(k, str) and bool(_KEY_RE.match(k))


def _clamp_pt(p):
    """Return {'x','y'} clamped to 0..100, or None if not a finite numeric point."""
    if not isinstance(p, dict):
        return None
    try:
        x = float(p.get('x'))
        y = float(p.get('y'))
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(x) and math.isfinite(y)):
        return None
    return {"x": min(100.0, max(0.0, x)), "y": min(100.0, max(0.0, y))}


def _sanitize_layout(raw):
    """Validate + clamp one device's layout. Returns a clean dict, or None if the
    top-level shape is wrong (so the caller can 400 instead of writing garbage)."""
    if not isinstance(raw, dict):
        return None
    out = {}
    for slot in ('propulsion', 'dome'):
        pt = _clamp_pt(raw.get(slot))
        if pt:
            out[slot] = pt
    out['shortcuts'] = {}
    scs = raw.get('shortcuts')
    if isinstance(scs, dict):
        for sid, pt in list(scs.items())[:_MAX_SHORTCUTS]:
            if isinstance(sid, str) and _SID_RE.match(sid):
                cpt = _clamp_pt(pt)
                if cpt:
                    out['shortcuts'][sid] = cpt
    # Camera panel size (Custom Drive Layout) — width/height as % of .drive-main,
    # clamped 25..100 (top-left anchored). Absent = default full size.
    cam = raw.get('cam')
    if isinstance(cam, dict):
        try:
            w = float(cam.get('w'))
            h = float(cam.get('h'))
            if math.isfinite(w) and math.isfinite(h):
                out['cam'] = {'w': min(100.0, max(25.0, w)),
                              'h': min(100.0, max(25.0, h))}
        except (TypeError, ValueError):
            pass
    return out


def _read_all():
    try:
        with open(_CFG, 'r', encoding='utf-8') as f:
            d = json.load(f)
            return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _atomic_write(data):
    d = os.path.dirname(_CFG)
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, _CFG)
        try:
            os.chmod(_CFG, 0o600)
        except OSError:
            pass
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


@drive_layout_bp.route('/drive/layouts', methods=['GET'])
def get_layouts():
    """Return the full {deviceKey: layout, ...} object (LAN-open read)."""
    return jsonify(_read_all())


@drive_layout_bp.route('/drive/layouts', methods=['POST'])
@require_admin
def post_layout():
    """Upsert one device's layout, or remove it when layout is null (Reset)."""
    body = get_json_object()
    if body is None:
        return jsonify({"error": "expected JSON object"}), 400
    key = body.get('deviceKey')
    if not _valid_device_key(key):
        return jsonify({"error": "bad deviceKey"}), 400
    all_ = _read_all()
    layout = body.get('layout')
    if layout is None:
        all_.pop(key, None)                       # Reset → remove this device's entry
    else:
        clean = _sanitize_layout(layout)
        if clean is None:
            return jsonify({"error": "bad layout"}), 400
        if key not in all_ and len(all_) >= _MAX_DEVICES:
            return jsonify({"error": "too many devices"}), 400
        all_[key] = clean
    _atomic_write(all_)
    return jsonify({"status": "ok"})
