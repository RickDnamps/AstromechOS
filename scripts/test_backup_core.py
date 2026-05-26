"""Unit tests for the pure Backup/Restore + theme logic (no Flask/paramiko/FS)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from master.api.backup_core import (
    validate_theme, is_safe_member, classify_member,
    build_manifest, validate_manifest, BACKUP_FILESET, merge_local_cfg,
    validate_ui_scale, is_allowed_restore_member,
)


def test_drive_layouts_in_fileset_and_allowed():
    # Custom Drive Layout: drive_layouts.json must be backed up AND pass the
    # anti-RCE restore allow-list (rel is relative to the side root).
    assert 'master/config/drive_layouts.json' in BACKUP_FILESET['master']
    assert is_allowed_restore_member('master', 'config/drive_layouts.json')
    # Code paths must still be rejected by the allow-list (regression guard).
    assert not is_allowed_restore_member('master', 'main.py')


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

def test_merge_local_cfg_percent_in_password():
    # A '%' in a WiFi/admin password must not raise (RawConfigParser, no interp).
    backup = "[robot]\nname = R2-D2\n"
    live = "[hotspot]\nssid = AP\npassword = pa%ss\n"
    out = merge_local_cfg(backup, live)
    assert 'pa%ss' in out


# ---- restore allow-list (B.2, anti-RCE) ----
def test_restore_allowlist():
    from master.api.backup_core import is_allowed_restore_member as ok
    assert ok('master', 'config/local.cfg')
    assert ok('master', 'choreographies/dance.chor')
    assert ok('slave', 'sounds/A.mp3')
    assert ok('slave', 'config/servo_angles.json')
    # CODE must be rejected (RCE vector via a crafted .bck + auto-reboot)
    assert not ok('master', 'main.py')
    assert not ok('master', 'api/backup_bp.py')
    assert not ok('slave', 'main.py')
    assert not ok('master', 'config/../../etc/x')


# ---- UI scale (v2 readability) ----
def test_ui_scale_valid_steps():
    for v in (1.0, 1.1, 1.2, 1.3, 1.4):
        assert validate_ui_scale(v) == v

def test_ui_scale_clamps_high():
    assert validate_ui_scale(99) == 1.4

def test_ui_scale_clamps_low():
    assert validate_ui_scale(0.2) == 1.0

def test_ui_scale_rounds_to_step():
    assert validate_ui_scale(1.23) == 1.2
    assert validate_ui_scale(1.26) == 1.3

def test_ui_scale_non_numeric_defaults_to_1():
    assert validate_ui_scale('big') == 1.0
    assert validate_ui_scale(None) == 1.0
    assert validate_ui_scale(float('nan')) == 1.0


# ---- theme v2: optional input/button-text pickers (rk2) ----
def test_theme_new_pickers_valid():
    assert validate_theme(_good_theme(
        _pickerInputBg='#ffffff', _pickerInputText='#101418', _pickerBtnText='#0a1840'))

def test_theme_new_pickers_absent_still_valid():
    # back-compat: existing themes have none of the new fields
    t = _good_theme()
    assert '_pickerInputBg' not in t
    assert validate_theme(t)

def test_theme_new_picker_bad_hex_rejected():
    assert not validate_theme(_good_theme(_pickerInputBg='white; }body{'))
    assert not validate_theme(_good_theme(_pickerBtnText='nothex'))


# ---- local.cfg [ui] backup/restore coverage (Task 3 / rk2) ----
from master.api.backup_core import NETWORK_PRESERVE_SECTIONS

def test_local_cfg_in_backup_fileset():
    # [ui] scales live in local.cfg -> must ship in every .bck
    assert 'master/config/local.cfg' in BACKUP_FILESET['master']

def test_ui_section_not_network_preserved():
    # [ui] must be RESTORED from the backup (not kept from live machine)
    assert 'ui' not in NETWORK_PRESERVE_SECTIONS

def test_merge_local_cfg_restores_ui_section():
    backup = '[ui]\ninspector_scale = 1.4\ntimeline_scale = 1.2\n[home_wifi]\nssid = FROM_BACKUP\n'
    live   = '[ui]\ninspector_scale = 1.0\ntimeline_scale = 1.0\n[home_wifi]\nssid = LIVE_NET\n'
    merged = merge_local_cfg(backup, live)
    # Re-parse for format-tolerance (RawConfigParser.write() uses 'key = value' spacing,
    # but we verify intent via re-parse rather than string contains to be robust).
    import configparser
    p = configparser.RawConfigParser()
    p.optionxform = str
    p.read_string(merged)
    # [ui] must come from backup
    assert p.get('ui', 'inspector_scale') == '1.4'
    assert p.get('ui', 'timeline_scale') == '1.2'
    # [home_wifi] must come from live (network preserved)
    assert p.get('home_wifi', 'ssid') == 'LIVE_NET'
    # Backup's network value must not appear
    assert 'FROM_BACKUP' not in merged
