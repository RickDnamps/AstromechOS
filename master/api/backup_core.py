"""Pure helpers for Backup/Restore + custom themes.

No Flask, no paramiko, no filesystem side effects beyond path math — kept
dependency-free so it is unit-testable in isolation (see scripts/test_backup_core.py).
"""
from __future__ import annotations
import os
import posixpath
import re
import datetime

# ── Custom themes (B.0) ──────────────────────────────────────────────────────
ALLOWED_FONTS = {'orbitron', 'share_tech_mono', 'audiowide', 'electrolize',
                 'exo2', 'rajdhani', 'courier'}
_THEME_ID_RE = re.compile(r'^[A-Za-z0-9_-]{1,40}$')
_HEX_RE = re.compile(r'^#[0-9A-Fa-f]{3,8}$')


def validate_theme(t) -> bool:
    """True if `t` is a well-formed, safe custom theme. Rejects bad ids
    (XSS / path), non-hex colors (CSS injection), and unknown fonts."""
    if not isinstance(t, dict):
        return False
    if not isinstance(t.get('id'), str) or not _THEME_ID_RE.match(t['id']):
        return False
    if not isinstance(t.get('label'), str) or not (1 <= len(t['label']) <= 40):
        return False
    colors = t.get('colors')
    if not isinstance(colors, dict) or not colors or len(colors) > 20:
        return False
    for v in colors.values():
        if not (isinstance(v, str) and _HEX_RE.match(v)):
            return False
    font = t.get('font')
    if font is not None and font not in ALLOWED_FONTS:
        return False
    return True


# ── Backup manifest + fileset (B.1) ──────────────────────────────────────────
_SUPPORTED_FORMAT = 1

# Paths relative to repo root. Dirs end with '/'. Master collected locally;
# slave collected via SFTP. Excludes code / *_default seeds / *.example / VERSION.
BACKUP_FILESET = {
    'master': [
        'master/config/local.cfg', 'master/config/choreo_categories.json',
        'master/config/shortcuts.json', 'master/config/bt_config.json',
        'master/config/dome_angles.json', 'master/config/camera.env',
        'master/config/custom_themes.json',
        'master/choreographies/', 'master/light_sequences/', 'master/sequences/',
    ],
    'slave': [
        'slave/config/slave.cfg', 'slave/config/servo_angles.json', 'slave/sounds/',
    ],
}


def build_manifest(astromech_version: str, robot_name: str, files: list) -> dict:
    return {
        'format_version': _SUPPORTED_FORMAT,
        'created': datetime.datetime.now().isoformat(timespec='seconds'),
        'astromech_version': astromech_version,
        'robot_name': robot_name,
        'files': sorted(files),
    }


def validate_manifest(m) -> bool:
    return (isinstance(m, dict)
            and m.get('format_version') == _SUPPORTED_FORMAT
            and isinstance(m.get('files'), list))


# ── Restore safety: anti zip-slip + member classification (B.2) ──────────────
def is_safe_member(member_name: str, dest_root: str) -> bool:
    """Anti zip-slip: True only if extracting `member_name` resolves INSIDE
    dest_root. Rejects empty, absolute, and '..'-escaping paths."""
    if not member_name or member_name.startswith(('/', '\\')) or os.path.isabs(member_name):
        return False
    norm = posixpath.normpath(member_name.replace('\\', '/'))
    if norm == '..' or norm.startswith('../') or '/../' in norm:
        return False
    root = os.path.realpath(dest_root)
    target = os.path.realpath(os.path.join(root, *norm.split('/')))
    return target == root or target.startswith(root + os.sep)


def classify_member(member_name: str):
    """Return ('master'|'slave', relpath) for an allowed .bck member,
    else (None, None). Only the master/ and slave/ subtrees are allowed."""
    parts = member_name.replace('\\', '/').split('/')
    if len(parts) >= 2 and parts[0] in ('master', 'slave') and '..' not in parts:
        return parts[0], '/'.join(parts[1:])
    return None, None


# ── Network preservation on restore (B.2) ────────────────────────────────────
# These local.cfg sections are kept from the LIVE machine on restore (never the
# backup's) so a restore never severs master<->slave WiFi / SSH.
NETWORK_PRESERVE_SECTIONS = {'home_wifi', 'hotspot', 'deploy', 'slave', 'github'}


def merge_local_cfg(backup_text: str, live_text: str) -> str:
    """Return a local.cfg = backup content, but with NETWORK_PRESERVE_SECTIONS
    taken from the LIVE config. Pure string -> string."""
    import configparser
    import io
    bak = configparser.ConfigParser()
    bak.optionxform = str
    bak.read_string(backup_text)
    live = configparser.ConfigParser()
    live.optionxform = str
    live.read_string(live_text or '')
    for sec in NETWORK_PRESERVE_SECTIONS:
        if bak.has_section(sec):
            bak.remove_section(sec)
        if live.has_section(sec):
            bak.add_section(sec)
            for k, v in live.items(sec):
                bak.set(sec, k, v)
    out = io.StringIO()
    bak.write(out)
    return out.getvalue()
