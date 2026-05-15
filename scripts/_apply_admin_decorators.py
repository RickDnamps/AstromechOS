"""One-shot: add @require_admin decorator to every mutation endpoint
that should be admin-only. Settings audit 2026-05-15 batch CRITICAL.

Run from repo root. Idempotent — won't double-decorate."""
import re, pathlib, sys

# Files that need a new import line
ADD_IMPORT = [
    'master/api/vesc_bp.py',
    'master/api/bt_bp.py',
    'master/api/behavior_bp.py',
    'master/api/servo_bp.py',
    'master/api/camera_bp.py',
    'master/api/audio_bp.py',
    'master/api/status_bp.py',
]

# Function names → endpoint admin requirement
# True = needs @require_admin, False = NOT admin (safety/operational)
# Listing only the mutation endpoints touched by the Settings audit.
ADMIN_FUNCS = {
    # vesc_bp — all VESC config endpoints
    'master/api/vesc_bp.py': [
        'set_config', 'set_bench_mode', 'set_mode', 'invert_motor',
    ],
    # bt_bp — pair/scan/config; NOT estop_reset (safety recovery)
    'master/api/bt_bp.py': [
        'bt_enable', 'bt_config', 'bt_scan_start', 'bt_pair', 'bt_unpair',
    ],
    # behavior_bp — both endpoints
    'master/api/behavior_bp.py': [
        'set_alive', 'save_config',
    ],
    # servo_bp — config endpoints ONLY; panel moves stay open (guest can
    # open/close panels with R2 if not locked).
    'master/api/servo_bp.py': [
        'arms_config_save', 'servo_settings_save',
    ],
    # camera_bp — config only; take/release are operational
    'master/api/camera_bp.py': [
        'camera_config_set',
    ],
    # audio_bp — volume + upload + cat create + BT speaker config
    'master/api/audio_bp.py': [
        'set_volume', 'upload_sound', 'create_category',
        'bt_speaker_scan', 'bt_speaker_pair', 'bt_speaker_connect',
        'bt_speaker_disconnect', 'bt_speaker_remove', 'bt_speaker_volume',
    ],
    # status_bp — system mutations (NOT /heartbeat, NOT /system/estop*)
    'master/api/status_bp.py': [
        'system_update', 'lock_set', 'system_rollback',
        'system_resync_slave', 'system_reboot', 'system_reboot_slave',
        'system_reboot_both', 'system_shutdown_slave', 'system_shutdown_both',
        'system_shutdown',
    ],
}

# Find actual function names that might differ — let's grep them
total = 0
for fpath, funcs in ADMIN_FUNCS.items():
    p = pathlib.Path(fpath)
    src = p.read_text(encoding='utf-8')

    # Add the import line if missing
    if 'from master.api._admin_auth import require_admin' not in src:
        # Add after the first `from flask import` line
        new = re.sub(
            r'(from flask import [^\n]+\n)',
            r'\1from master.api._admin_auth import require_admin\n',
            src, count=1,
        )
        if new == src:
            print(f'WARN: no `from flask import` in {fpath} — manual import needed')
        else:
            src = new

    # Decorate each function
    for fn in funcs:
        # Match the @bp.post/put/delete line(s) directly above def <fn>(
        pattern = re.compile(
            r'((?:@\w+_bp\.(?:post|put|delete)\([^)]*\)\n)+)(def ' + re.escape(fn) + r'\()',
        )
        new_src, n = pattern.subn(r'\1@require_admin\n\2', src)
        if n == 0:
            print(f'WARN: did not find def {fn}( in {fpath}')
        elif '@require_admin\n@require_admin' in new_src:
            print(f'WARN: double-decorated {fn} in {fpath} — skipping')
        else:
            src = new_src
            total += 1
    p.write_text(src, encoding='utf-8')

print(f'decorated {total} endpoints across {len(ADMIN_FUNCS)} files')
