"""Unit tests for the pure Backup/Restore + theme logic (no Flask/paramiko/FS)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from master.api.backup_core import (
    validate_theme, is_safe_member, classify_member,
    build_manifest, validate_manifest, BACKUP_FILESET, merge_local_cfg,
)


# ---- themes (B.0) — real frontend shape ----
def _good_theme(**over):
    t = {'id': 'custom_1', 'label': 'My Theme', 'swatch': '#00b4ff',
         '_pickerBg': '#101820', '_pickerTopbar': '#0a1015', '_pickerCard': '#1a2530',
         '_pickerAccent': '#00b4ff', '_pickerText': '#e0e0e0', '_pickerOk': '#33cc66',
         '_pickerWarn': '#ffaa44', '_pickerErr': '#ff4444', '_pickerFont': 'orbitron',
         'vars': {'--bg': '#101820', '--text-dim': 'rgba(76,80,90,0.5)',
                  '--font': "'Orbitron', 'Courier New', monospace"}}
    t.update(over)
    return t

def test_valid_theme():
    assert validate_theme(_good_theme())

def test_theme_bad_id():
    assert not validate_theme(_good_theme(id='../evil'))

def test_theme_bad_picker_color():
    assert not validate_theme(_good_theme(_pickerBg='red; }body{'))

def test_theme_label_capped():
    assert not validate_theme(_good_theme(label='x' * 41))

def test_theme_vars_css_injection_blocked():
    assert not validate_theme(_good_theme(vars={'--bg': '#fff; background:url(http://evil)'}))

def test_theme_vars_rgba_allowed():
    assert validate_theme(_good_theme(vars={'--x': 'rgba(0,180,255,0.18)'}))

def test_theme_font_system_ok():
    assert validate_theme(_good_theme(_pickerFont='system'))

def test_theme_font_bad():
    assert not validate_theme(_good_theme(_pickerFont='evil;font'))


# ---- manifest + fileset (B.1) ----
def test_manifest_roundtrip():
    m = build_manifest(astromech_version='abc1234', robot_name='R2-D2', files=['master/config/local.cfg'])
    assert m['format_version'] == 1 and m['robot_name'] == 'R2-D2'
    assert validate_manifest(m) is True

def test_validate_manifest_rejects_bad():
    assert validate_manifest({}) is False
    assert validate_manifest({'format_version': 999}) is False

def test_fileset_has_master_and_slave():
    assert any(p.startswith('master/') for p in BACKUP_FILESET['master'])
    assert any(p.startswith('slave/') for p in BACKUP_FILESET['slave'])


# ---- zip-slip + classify (B.2, security-critical) ----
def test_zipslip_safe(tmp_path):
    root = str(tmp_path)
    assert is_safe_member('master/config/local.cfg', root) is True
    assert is_safe_member('slave/sounds/A.mp3', root) is True

def test_zipslip_blocks_escape(tmp_path):
    root = str(tmp_path)
    assert is_safe_member('../etc/passwd', root) is False
    assert is_safe_member('/etc/passwd', root) is False
    assert is_safe_member('master/../../etc/x', root) is False
    assert is_safe_member('master/sounds/../../../x', root) is False
    assert is_safe_member('', root) is False

def test_classify_member():
    assert classify_member('master/config/local.cfg') == ('master', 'config/local.cfg')
    assert classify_member('slave/sounds/A.mp3') == ('slave', 'sounds/A.mp3')
    assert classify_member('manifest.json') == (None, None)
    assert classify_member('evil.sh') == (None, None)


# ---- local.cfg merge (B.2, network preservation) ----
def test_merge_local_cfg_preserves_network():
    backup = "[hotspot]\nssid = OLD_AP\npassword = oldpass\n[robot]\nname = R2-D2\n"
    live = "[hotspot]\nssid = LIVE_AP\npassword = livepass\n[robot]\nname = OldName\n"
    out = merge_local_cfg(backup, live)
    assert 'LIVE_AP' in out and 'livepass' in out       # network kept from LIVE
    assert 'OLD_AP' not in out and 'oldpass' not in out  # backup network dropped
    assert 'name = R2-D2' in out                         # content restored from backup
