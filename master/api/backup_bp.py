# ============================================================
#  AstromechOS — Backup / Restore + server-side custom themes
# ============================================================
"""Blueprint: server-side custom themes (B.0) + full Backup/Restore (B.1/B.2).

Themes were browser-localStorage only; persisting them here makes them
multi-device + included in the backup.
"""
import json
import logging
import os
import threading

from flask import Blueprint, request, jsonify
from master.api._admin_auth import require_admin, get_json_object
from master.api.backup_core import validate_theme

log = logging.getLogger(__name__)
backup_bp = Blueprint('backup', __name__)

_CONFIG_DIR = os.path.join(os.path.dirname(__file__), '..', 'config')
_THEMES_FILE = os.path.join(_CONFIG_DIR, 'custom_themes.json')
_themes_lock = threading.Lock()
_CUSTOM_THEMES_MAX = 16


def _read_themes() -> list:
    try:
        with open(_THEMES_FILE, encoding='utf-8') as f:
            d = json.load(f)
        return d.get('themes', []) if isinstance(d, dict) else []
    except (OSError, json.JSONDecodeError):
        return []


def _write_themes(themes: list) -> None:
    """Atomic write: tmp + fsync + os.replace (same pattern as the sounds index)."""
    tmp = _THEMES_FILE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump({'themes': themes}, f, indent=2, ensure_ascii=False)
        f.flush()
        try:
            os.fsync(f.fileno())
        except OSError:
            pass
    os.replace(tmp, _THEMES_FILE)


@backup_bp.get('/themes/custom')
def themes_list():
    """List custom themes (LAN-open read, like other read endpoints)."""
    return jsonify({'themes': _read_themes()})


@backup_bp.post('/themes/custom')
@require_admin
def themes_save():
    """Add or update one custom theme (validated server-side)."""
    body = get_json_object()
    theme = body.get('theme') if isinstance(body, dict) else None
    if not validate_theme(theme):
        return jsonify({'ok': False, 'error': 'invalid theme'}), 400
    with _themes_lock:
        themes = [t for t in _read_themes() if t.get('id') != theme['id']]
        if len(themes) >= _CUSTOM_THEMES_MAX:
            return jsonify({'ok': False, 'error': f'max {_CUSTOM_THEMES_MAX} themes'}), 400
        themes.append(theme)
        _write_themes(themes)
    return jsonify({'ok': True})


@backup_bp.route('/themes/custom/<tid>', methods=['DELETE'])
@require_admin
def themes_delete(tid):
    """Delete one custom theme by id."""
    with _themes_lock:
        themes = [t for t in _read_themes() if t.get('id') != tid]
        _write_themes(themes)
    return jsonify({'ok': True})
