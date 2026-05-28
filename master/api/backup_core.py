"""Pure helpers for Backup/Restore + custom themes.

No Flask, no paramiko, no filesystem side effects beyond path math — kept
dependency-free so it is unit-testable in isolation (see scripts/test_backup_core.py).
"""
from __future__ import annotations
import json
import math
import os
import posixpath
import re
import datetime

# ── Custom themes (B.0) ──────────────────────────────────────────────────────
# Theme object shape (from app.js _buildCustomVars / saveCustomTheme):
#   {id, label, swatch(#hex), _pickerBg/_pickerTopbar/_pickerCard/_pickerAccent/
#    _pickerText/_pickerOk/_pickerWarn/_pickerErr(#hex), _pickerFont(key|'system'),
#    vars{cssVar: value}}
_THEME_ID_RE = re.compile(r'^[A-Za-z0-9_-]{1,40}$')
_HEX_RE = re.compile(r'^#[0-9A-Fa-f]{3,8}$')
_FONT_KEY_RE = re.compile(r'^[A-Za-z0-9_]{1,20}$')
_PICKER_FIELDS = ('_pickerBg', '_pickerTopbar', '_pickerCard', '_pickerAccent',
                  '_pickerText', '_pickerOk', '_pickerWarn', '_pickerErr')
# Inline-style values legitimately contain rgba()/quotes/commas, so we allow '('
# ')' ',' "'" but block the chars/substrings that enable CSS/HTML injection.
_CSS_FORBIDDEN_CHARS = set(';{}<>')
_CSS_FORBIDDEN_SUBSTR = ('url(', 'expression', 'image-set', '/*', '*/', 'javascript:')


def _safe_css_value(v) -> bool:
    if not isinstance(v, str) or len(v) > 120:
        return False
    if _CSS_FORBIDDEN_CHARS & set(v):
        return False
    low = v.lower()
    return not any(s in low for s in _CSS_FORBIDDEN_SUBSTR)


def validate_theme(t) -> bool:
    """True if `t` is a well-formed, safe custom theme. Rejects bad ids
    (path/XSS), non-hex picker colors, unsafe fonts, and CSS-injecting `vars`."""
    if not isinstance(t, dict):
        return False
    if not isinstance(t.get('id'), str) or not _THEME_ID_RE.match(t['id']):
        return False
    if not isinstance(t.get('label'), str) or not (1 <= len(t['label']) <= 40):
        return False
    for fld in _PICKER_FIELDS + ('swatch',):
        v = t.get(fld)
        if not (isinstance(v, str) and _HEX_RE.match(v)):
            return False
    # v2: Input BG / Input Text / Button Text pickers are OPTIONAL
    # (older themes lack them). When present they must be valid hex.
    for fld in ('_pickerInputBg', '_pickerInputText', '_pickerBtnText'):
        v = t.get(fld)
        if v is not None and not (isinstance(v, str) and _HEX_RE.match(v)):
            return False
    font = t.get('_pickerFont')
    if font is not None and not (isinstance(font, str)
                                 and (font == 'system' or _FONT_KEY_RE.match(font))):
        return False
    vars_ = t.get('vars')
    if vars_ is not None:
        if not isinstance(vars_, dict) or len(vars_) > 60:
            return False
        for val in vars_.values():
            if not _safe_css_value(val):
                return False
    return True


def validate_ui_scale(v) -> float:
    """Coerce an editor text-size multiplier to a safe value.
    Accepts numeric input; non-numeric / NaN / inf -> 1.0. Clamps to
    [1.0, 1.4] and snaps to the nearest 0.1 step (slider positions
    1.0/1.1/1.2/1.3/1.4)."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 1.0
    if not math.isfinite(f):
        return 1.0
    f = max(1.0, min(1.4, f))
    return round(round(f * 10) / 10, 1)


# ── Backup manifest + fileset (B.1) ──────────────────────────────────────────
_SUPPORTED_FORMAT = 1

# Paths relative to repo root. Dirs end with '/'. Master collected locally;
# slave collected via SFTP. Excludes code / *_default seeds / *.example / VERSION.
BACKUP_FILESET = {
    'master': [
        'master/config/local.cfg', 'master/config/choreo_categories.json',
        'master/config/shortcuts.json', 'master/config/bt_config.json',
        'master/config/dome_angles.json', 'master/config/camera.env',
        'master/config/custom_themes.json', 'master/config/drive_layouts.json',
        # Phase G4 chantier 2026-05-28: HAT identity mapping. Anchor for
        # labels + calibrations across re-jumpering / hardware changes.
        # Restored alongside angles so the (identity, channel) keys in
        # the calibration JSON keep resolving to the same physical servos.
        'master/config/config_mapping.json',
        'master/choreographies/', 'master/light_sequences/',
    ],
    'slave': [
        'slave/config/slave.cfg', 'slave/config/servo_angles.json',
        # Phase G4: same rationale as master side.
        'slave/config/config_mapping.json',
        'slave/sounds/',
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


def validate_mapping_against_layout(mapping_path: str, layout_path: str) -> list:
    """Phase G4 chantier 2026-05-28 — compare a config_mapping.json file
    against an hw_layout.json file. Returns the list of HAT-identity
    mismatches.

    A mismatch happens when the backup was taken on hardware whose I2C
    addresses differ from the current robot — typical when the operator
    restores a backup onto a new SD card / new Pi after re-jumpering.
    The restore still succeeds (calibration data is preserved by HAT
    identity), but the operator needs to know they will land in
    DEGRADED mode for any HAT whose mapped address doesn't match a
    detected one — and that they should use the Settings -> HATs
    re-map wizard (Phase G6) to fix the assignment without touching
    the calibration JSON.

    Returns a list of warning dicts:
        [{
          'identity':       'Body_HAT_A',
          'role':           'servo_body',
          'expected_addr':  '0x41',  # from config_mapping
          'detected_addrs': ['0x42'], # from hw_layout
          'message':        'HAT identity Body_HAT_A expected at 0x41 ...'
        }, ...]
    Empty list = perfect match (or one of the two files absent, in which
    case validation is a no-op — restore continues silently). Never
    raises; backup_bp surfaces the list in the restore job status."""
    warnings: list = []
    if not (os.path.isfile(mapping_path) and os.path.isfile(layout_path)):
        return warnings   # one of them absent → skip validation, never warn
    try:
        with open(mapping_path, encoding='utf-8') as f:
            mapping = json.load(f)
        with open(layout_path, encoding='utf-8') as f:
            layout = json.load(f)
    except Exception:
        return warnings   # malformed → skip; the existing restore flow
                          # already handles bad JSON for these files

    detected = set()
    for h in (layout or {}).get('hats') or []:
        if not isinstance(h, dict):
            continue
        addr = (h.get('addr') or '').strip().lower()
        if addr.startswith('0x'):
            detected.add(addr)

    for h in (mapping or {}).get('hats') or []:
        if not isinstance(h, dict):
            continue
        ident   = h.get('id')
        expect  = (h.get('address') or '').strip().lower()
        role    = h.get('role')
        if not (isinstance(ident, str) and expect.startswith('0x')):
            continue
        if expect in detected:
            continue   # in sync
        warnings.append({
            'identity':       ident,
            'role':           role,
            'expected_addr':  expect,
            'detected_addrs': sorted(detected),
            'message': (
                f"HAT identity {ident} ({role}) expected at {expect} per "
                f"restored config_mapping.json, but the live I2C scan "
                f"detected {sorted(detected) or 'no HATs'}. The driver "
                f"will boot DEGRADED for this HAT. Use Settings -> HATs "
                f"to re-assign the address without losing calibration."
            ),
        })
    return warnings


def is_allowed_restore_member(side: str, rel: str) -> bool:
    """True if `rel` (relative to the side root, e.g. 'config/local.cfg') is an
    allowed restore target per BACKUP_FILESET. This is the defense the zip-slip
    check CANNOT provide: it stops a crafted .bck from overwriting CODE
    (e.g. master/main.py, api/*.py) — which, with the post-restore reboot,
    would be remote code execution. `side` is 'master' or 'slave'."""
    if side not in BACKUP_FILESET or '..' in rel.split('/'):
        return False
    prefix = side + '/'
    for entry in BACKUP_FILESET[side]:
        e = entry[len(prefix):] if entry.startswith(prefix) else entry
        if e.endswith('/'):
            if rel == e[:-1] or rel.startswith(e):
                return True
        elif rel == e:
            return True
    return False


def merge_local_cfg(backup_text: str, live_text: str) -> str:
    """Return a local.cfg = backup content, but with NETWORK_PRESERVE_SECTIONS
    taken from the LIVE config. Pure string -> string. Uses RawConfigParser so a
    '%' in a WiFi/admin password is preserved verbatim (BasicInterpolation would
    raise)."""
    import configparser
    import io
    bak = configparser.RawConfigParser()
    bak.optionxform = str
    bak.read_string(backup_text)
    live = configparser.RawConfigParser()
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
