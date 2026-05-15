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
Blueprint API Settings — Network configuration and AstromechOS parameters.

Endpoints:
  GET  /settings              → read current config (local.cfg + NM state)
  GET  /settings/wifi/scan    → scan available WiFi networks on wlan1
  POST /settings/wifi         → update wlan1 (local.cfg + nmcli reconnect)
  POST /settings/hotspot      → update hotspot credentials for wlan0
  POST /settings/config       → update general parameters (branch, slave, etc.)
"""

import configparser
import hmac
import logging
import os
import subprocess
import threading
import time
from flask import Blueprint, request, jsonify, send_from_directory
from master.config.config_loader import write_cfg_atomic
from master.api._admin_auth import require_admin
# B-102 / B-103 (audit 2026-05-15): consolidated all stdlib imports
# at the top instead of scattering `import threading as _threading_cfg`
# / `import threading as _th` / `import time as _t` at three function
# scopes. Aliases dropped — plain `threading` and `time` everywhere.

settings_bp = Blueprint('settings', __name__)
log = logging.getLogger(__name__)

from shared.paths import LOCAL_CFG, SLAVE_CFG as _SLAVE_CFG
# B-61 (audit 2026-05-15): read slave host from local.cfg [slave] host
# instead of hardcoding. The hardcode broke any installation that used
# a different IP / mDNS name (the user has hit this exact problem
# before — see feedback_no_hardcoded_install_values memory).
def _resolve_slave_ssh_target() -> str:
    """Return 'artoo@<host>' where <host> comes from local.cfg, or a
    sensible default if the config is missing."""
    host = _read_cfg().get('slave', 'host', fallback='r2-slave.local')
    return f'artoo@{host}'
_ICONS_DIR   = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'icons')
# User-reported 2026-05-15: post-B-82 the pre-shipped SVG icons
# (bb8.svg, c3po.svg, ig11.svg, k2so.svg, r2d2_blue.svg, r5d4.svg)
# disappeared from the picker. Split the allowed-extensions sets:
#
# _ALLOWED_LIST_EXT  — what /settings/icons GET returns + serves
#   Includes .svg for backward compat. Pre-shipped + admin-SCP'd
#   files are trusted (operator deliberately placed them).
#
# _ALLOWED_UPLOAD_EXT — what /settings/icons/upload accepts
#   Excludes .svg per B-82's threat model: an operator's web upload
#   is a potentially untrusted path (admin password could leak →
#   attacker uploads SVG with <script> → XSS via /icons/<path>
#   served same-origin). PNG/WEBP/etc. parse as raster images and
#   can't carry executable content.
_ALLOWED_LIST_EXT   = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'}
_ALLOWED_UPLOAD_EXT = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
# Backward-compat alias for old call sites that referenced _ALLOWED_EXT
_ALLOWED_EXT = _ALLOWED_UPLOAD_EXT
INTERNET_CON = 'r2d2-internet'
HOTSPOT_CON  = 'r2d2-hotspot'


# =============================================================================
# Helpers
# =============================================================================

def _safe_int(val: str, fallback: int) -> int:
    try:
        return max(0, min(100, int(val)))
    except (ValueError, TypeError):
        return fallback


# Serialize all read-modify-write cycles on local.cfg + slave.cfg so that
# concurrent saves (Settings tab + Android, two browser tabs, etc.) cannot
# interleave and lose keys.
_cfg_write_lock = threading.Lock()


def _read_cfg() -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    if os.path.exists(LOCAL_CFG):
        cfg.read(LOCAL_CFG)
    return cfg


def _write_key(section: str, key: str, value: str) -> None:
    """Writes or updates a key in local.cfg under the global write lock.

    B-57 (audit 2026-05-15): filter control characters from the value
    before persisting. ConfigParser writes \\n verbatim, so a value of
    'foo\\n[admin]\\npassword = pwn' would inject a fake [admin] section
    that the next _read_cfg() honours — promotion to admin from any
    endpoint that hits _write_key with user input. The fix strips \\n
    / \\r / \\x00 (kept simple — no escaping, just rejection)."""
    if value is None:
        value = ''
    safe = ''.join(c for c in str(value) if c not in '\n\r\x00')
    with _cfg_write_lock:
        cfg = _read_cfg()
        if not cfg.has_section(section):
            cfg.add_section(section)
        cfg.set(section, key, safe)
        write_cfg_atomic(cfg, LOCAL_CFG)


# B-63 (remaining tabs audit 2026-05-15): mtime-keyed cache for
# slave.cfg. GET /settings reads slave.cfg up to 3× per response;
# without caching that's 3 file parses per dashboard poll per client.
_SLAVE_CFG_CACHE: dict = {'mtime': 0.0, 'cfg': None}


def _read_slave_cfg() -> configparser.ConfigParser:
    try:
        mt = os.path.getmtime(_SLAVE_CFG)
    except OSError:
        mt = 0.0
    cached = _SLAVE_CFG_CACHE['cfg']
    if cached is not None and _SLAVE_CFG_CACHE['mtime'] == mt:
        return cached
    cfg = configparser.ConfigParser()
    if os.path.exists(_SLAVE_CFG):
        cfg.read(_SLAVE_CFG)
    _SLAVE_CFG_CACHE['cfg']   = cfg
    _SLAVE_CFG_CACHE['mtime'] = mt
    return cfg


def _sync_slave_hat_cfg(**kwargs) -> None:
    """Write i2c_servo_hats keys to slave.cfg, SCP to Slave, restart Slave service.

    B-59 / B-60 (audit 2026-05-15): SCP + restart run in a background
    daemon thread instead of synchronously in the Flask request thread.
    SCP can stall up to 8s on a flaky link → previously blocked the
    HTTP response. Restart now also fires ONLY when SCP succeeded
    (rc == 0); old code restarted regardless, leaving the Slave running
    the OLD slave.cfg if SCP silently failed.
    """
    with _cfg_write_lock:
        slave_cfg = _read_slave_cfg()
        if not slave_cfg.has_section('i2c_servo_hats'):
            slave_cfg.add_section('i2c_servo_hats')
        for key, value in kwargs.items():
            slave_cfg.set('i2c_servo_hats', key, str(value))
        try:
            # B-46: atomic write — tmp + os.replace.
            os.makedirs(os.path.dirname(_SLAVE_CFG), exist_ok=True)
            write_cfg_atomic(slave_cfg, _SLAVE_CFG)
            log.info("slave.cfg written: %s", kwargs)
        except OSError as e:
            log.warning("Failed to write slave.cfg: %s", e)
            return   # nothing to push if local write failed

    def _bg_sync_and_restart():
        target = _resolve_slave_ssh_target()
        try:
            r = subprocess.run(
                ['scp', _SLAVE_CFG, f'{target}:{_SLAVE_CFG}'],
                timeout=8, check=False, capture_output=True,
            )
        except (subprocess.TimeoutExpired, OSError) as e:
            log.error("SCP slave.cfg failed (%s) — skipping Slave restart", e)
            return
        if r.returncode != 0:
            log.error("SCP slave.cfg rc=%d stderr=%s — skipping restart",
                      r.returncode, r.stderr[:200] if r.stderr else '')
            return
        log.info("slave.cfg synced to Slave (hat config)")
        time.sleep(2)
        subprocess.run(['sudo', 'systemctl', 'restart', 'astromech-slave'], check=False)
        log.info("Slave service restart issued")

    threading.Thread(target=_bg_sync_and_restart, daemon=True,
                     name='slave-hat-sync').start()
    log.info("Slave HAT sync scheduled (background)")


def _run(cmd: list[str], timeout: int = 15) -> tuple[int, str, str]:
    """Runs a command, returns (returncode, stdout, stderr)."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return 1, '', 'timeout'
    except Exception as e:
        return 1, '', str(e)


# B-62 (remaining tabs audit 2026-05-15): TTL cache around _nm_field.
# GET /settings calls nmcli FOUR times per response (wlan0 state +
# wlan1 state/conn/ip). Each call forks subprocess.run + waits up to
# 2s. With multiple polling clients that's a real Master CPU + latency
# tax. 3s TTL is short enough that operator-visible state changes
# (connect/disconnect) appear within one poll while keeping the
# subprocess fork rate bounded.
_NM_CACHE: dict = {}   # {(device, field): (expiry, value)}
_NM_TTL_S = 3.0


def _nm_field(device: str, field: str) -> str:
    """Reads an nmcli field for a device. Cached for _NM_TTL_S seconds."""
    now = time.monotonic()
    cached = _NM_CACHE.get((device, field))
    if cached is not None and cached[0] > now:
        return cached[1]
    rc, out, _ = _run(['nmcli', '-g', field, 'device', 'show', device])
    val = out if rc == 0 else ''
    _NM_CACHE[(device, field)] = (now + _NM_TTL_S, val)
    return val


_lights_reload_lock = threading.Lock()


def _read_fresh_cfg() -> configparser.ConfigParser:
    """Re-reads main.cfg + local.cfg from disk (for hot-reload)."""
    from master.config.config_loader import MAIN_CFG, LOCAL_CFG
    cfg = configparser.ConfigParser()
    cfg.read([MAIN_CFG, LOCAL_CFG])
    return cfg


def _reload_lights_driver(backend: str) -> dict:
    """
    Loads the new driver and, only on success, swaps it into reg.teeces.
    The old driver is shut down after the swap to avoid a None window.
    Thread-safe via _lights_reload_lock (Flask runs with threaded=True).
    """
    import master.registry as reg
    from master.lights import load_driver

    with _lights_reload_lock:
        old_driver = reg.teeces

        cfg = _read_fresh_cfg()
        try:
            new_driver = load_driver(cfg)
        except ValueError as e:
            log.error(f"Invalid lights backend: {e}")
            return {'ok': False, 'error': str(e)}

        if not new_driver.setup():
            log.error(f"Lights driver setup failed ({backend})")
            return {'ok': False, 'error': f"Setup {backend} failed (port unavailable?)"}

        reg.teeces = new_driver   # atomic swap — no None window
        new_driver.random_mode()

    # Shut down old driver AFTER lock released (avoids deadlock if shutdown is slow).
    # Brief sleep lets any in-flight request that holds a local ref to old_driver finish.
    if old_driver:
        time.sleep(0.1)
        try:
            old_driver.shutdown()
        except Exception as e:
            log.warning(f"Shutdown of previous lights driver: {e}")

    log.info(f"Lights driver reloaded: {backend}")
    return {'ok': True}


def _sync_audio_channels(channels: int) -> None:
    """
    Write audio_channels to slave/config/slave.cfg locally,
    SCP it to the Slave, then restart both services (delayed to let
    the HTTP response complete first).
    """
    slave_cfg_path = _SLAVE_CFG
    slave_host     = _resolve_slave_ssh_target()   # B-61: from cfg, not hardcoded

    # Write slave.cfg on Master filesystem
    slave_cfg = configparser.ConfigParser()
    if os.path.exists(slave_cfg_path):
        slave_cfg.read(slave_cfg_path)
    if not slave_cfg.has_section('audio'):
        slave_cfg.add_section('audio')
    slave_cfg.set('audio', 'audio_channels', str(channels))
    try:
        # B-47: atomic write — same hardening as B-46.
        os.makedirs(os.path.dirname(slave_cfg_path), exist_ok=True)
        write_cfg_atomic(slave_cfg, slave_cfg_path)
        log.info("slave.cfg written: audio_channels=%d", channels)
    except OSError as e:
        log.warning("Failed to write slave.cfg: %s", e)

    # SCP to Slave
    try:
        subprocess.run(
            ['scp', slave_cfg_path, f'{slave_host}:{slave_cfg_path}'],
            timeout=8, check=False, capture_output=True,
        )
        log.info("slave.cfg synced to Slave")
    except Exception as e:
        log.warning("Failed to SCP slave.cfg: %s", e)

    # Delayed restart (2s) — lets the HTTP response reach the client first
    def _delayed_restart():
        time.sleep(2)
        subprocess.run(['sudo', 'systemctl', 'restart', 'astromech-slave'], check=False)
        time.sleep(1)
        subprocess.run(['sudo', 'systemctl', 'restart', 'astromech-master'], check=False)

    threading.Thread(target=_delayed_restart, daemon=True).start()
    log.info("Services scheduled to restart in 2s (audio_channels=%d)", channels)


# =============================================================================
# Endpoints
# =============================================================================

@settings_bp.get('/settings')
def get_settings():
    """Returns the full configuration (local.cfg + network state)."""
    cfg = _read_cfg()

    # wlan1 state
    wlan1_state = _nm_field('wlan1', 'GENERAL.STATE')
    wlan1_conn  = _nm_field('wlan1', 'GENERAL.CONNECTION')
    wlan1_ip    = _nm_field('wlan1', 'IP4.ADDRESS[1]')

    # wlan0 state (hotspot)
    wlan0_state = _nm_field('wlan0', 'GENERAL.STATE')

    return jsonify({
        'wifi': {
            'ssid':       cfg.get('home_wifi', 'ssid',     fallback=''),
            'connected':  '100' in wlan1_state,
            'connection': wlan1_conn,
            'ip':         wlan1_ip.split('/')[0] if wlan1_ip else '',
        },
        'hotspot': {
            'ssid':         cfg.get('hotspot', 'ssid', fallback='AstromechOS'),
            'password_set': bool(cfg.get('hotspot', 'password', fallback='')),
            'ip':           '192.168.4.1',
            'active':       '100' in wlan0_state,
        },
        'github': {
            'repo_url':          cfg.get('github', 'repo_url',          fallback=''),
            'branch':            cfg.get('github', 'branch',            fallback='main'),
            'auto_pull_on_boot': cfg.getboolean('github', 'auto_pull_on_boot', fallback=True),
        },
        'slave': {
            'host': cfg.get('slave', 'host', fallback='r2-slave.local'),
        },
        'hardware': {
            'master_hats':       cfg.get('i2c_servo_hats', 'master_hats', fallback='0x40'),
            'slave_hats':        _read_slave_cfg().get('i2c_servo_hats', 'slave_hats',       fallback='0x41'),
            'slave_motor_hat':   _read_slave_cfg().get('i2c_servo_hats', 'slave_motor_hat',  fallback='0x40'),
            'body_uart_lat_ms':  round(cfg.getfloat('choreo', 'body_servo_uart_lat', fallback=0.025) * 1000),
        },
        'lights': {
            'backend':   cfg.get('lights', 'backend', fallback='teeces'),
            'available': ['teeces', 'astropixels'],
        },
        'audio': {
            'channels': cfg.getint('audio', 'audio_channels', fallback=6),
            'profiles': {
                'convention': _safe_int(cfg.get('audio', 'profile_convention', fallback='70'), 70),
                'maison':     _safe_int(cfg.get('audio', 'profile_maison',     fallback='85'), 85),
                'exterieur':  _safe_int(cfg.get('audio', 'profile_exterieur',  fallback='95'), 95),
            },
        },
        'battery': {
            'cells':     cfg.getint('battery', 'cells',     fallback=4),
            'chemistry': cfg.get(   'battery', 'chemistry', fallback='liion').strip().lower(),
        },
    })


@settings_bp.get('/settings/wifi/scan')
def wifi_scan():
    """Scans available WiFi networks on wlan1."""
    # Trigger a rescan (non-blocking, error ignored if wlan1 is absent)
    _run(['nmcli', 'device', 'wifi', 'rescan', 'ifname', 'wlan1'], timeout=5)

    rc, out, _ = _run(
        ['nmcli', '-t', '-f', 'SSID,SIGNAL,SECURITY', 'device', 'wifi', 'list', 'ifname', 'wlan1'],
        timeout=10
    )

    networks = []
    if rc == 0:
        for line in out.splitlines():
            # nmcli -t: escapes ':' in SSID as '\:'
            # split from the right to isolate SIGNAL and SECURITY
            parts = line.rsplit(':', 2)
            if len(parts) == 3:
                ssid     = parts[0].replace('\\:', ':')
                signal   = int(parts[1]) if parts[1].isdigit() else 0
                security = parts[2]
                if ssid:
                    networks.append({'ssid': ssid, 'signal': signal, 'security': security})

        # Deduplicate (keep strongest signal) and sort
        seen: dict[str, dict] = {}
        for n in networks:
            if n['ssid'] not in seen or n['signal'] > seen[n['ssid']]['signal']:
                seen[n['ssid']] = n
        networks = sorted(seen.values(), key=lambda x: -x['signal'])

    return jsonify({'networks': networks})


@settings_bp.post('/settings/wifi')
@require_admin
def set_wifi():
    """Updates wlan1 credentials and attempts to connect."""
    data = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    ssid     = data.get('ssid', '').strip()
    password = data.get('password', '').strip()

    if not ssid:
        return jsonify({'error': 'SSID required'}), 400
    # B-45 (audit 2026-05-15): argv passing avoids shell injection but
    # nmcli treats leading '-' as an option flag. An SSID like
    # '--auto-connect=no' would be parsed as nmcli args. Reject any
    # SSID/password starting with `-` to be safe; real SSIDs never do.
    if ssid.startswith('-') or (password and password.startswith('-')):
        return jsonify({'error': 'SSID/password cannot start with "-"'}), 400
    # B-57 also bites here — ConfigParser writes newlines verbatim; a
    # SSID containing \n would inject a fake [section] on next read.
    if any(c in ssid for c in '\n\r\x00') or any(c in password for c in '\n\r\x00'):
        return jsonify({'error': 'SSID/password contains illegal control char'}), 400

    # B-73 (remaining tabs audit 2026-05-15): snapshot existing
    # ssid/password BEFORE persisting so we can roll back local.cfg if
    # nmcli rejects the new config. Without this, a typo or rejected
    # SSID left local.cfg pointing at the bad creds even though wlan1
    # was still on the OLD connection in NM — boot would then pick up
    # the bad creds.
    _old_cfg = _read_cfg()
    prev_ssid = _old_cfg.get('home_wifi', 'ssid', fallback='')
    prev_pwd  = _old_cfg.get('home_wifi', 'password', fallback='')

    # Save to local.cfg
    _write_key('home_wifi', 'ssid', ssid)
    if password:
        _write_key('home_wifi', 'password', password)

    # Reconfigure NetworkManager
    _run(['nmcli', 'connection', 'delete', INTERNET_CON])

    cmd = ['nmcli', 'connection', 'add',
           'type', 'wifi', 'ifname', 'wlan1',
           'con-name', INTERNET_CON,
           'ssid', ssid,
           'connection.autoconnect', 'yes',
           'connection.autoconnect-priority', '10']
    if password:
        cmd += ['wifi-sec.key-mgmt', 'wpa-psk', 'wifi-sec.psk', password]

    rc, _, err = _run(cmd)
    if rc != 0:
        log.error(f"nmcli add wlan1 failed: {err} — rolling back local.cfg")
        # B-73: restore the previous values so reboot doesn't pick up
        # the half-baked config. Best effort — _write_key swallows
        # internal errors so the rollback is naturally idempotent.
        _write_key('home_wifi', 'ssid', prev_ssid)
        _write_key('home_wifi', 'password', prev_pwd)
        return jsonify({'error': f'nmcli error: {err}', 'rolled_back': True}), 500

    rc2, _, _ = _run(['nmcli', 'connection', 'up', INTERNET_CON])
    connected = rc2 == 0

    log.info(f"WiFi wlan1 updated: ssid={ssid}, connected={connected}")
    return jsonify({'status': 'ok', 'connected': connected,
                    'message': 'Connected ✓' if connected else 'Config saved — will connect on next boot'})


@settings_bp.post('/settings/hotspot')
@require_admin
def set_hotspot():
    """Updates hotspot credentials for wlan0 and restarts the hotspot."""
    data = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    ssid     = data.get('ssid', '').strip()
    password = data.get('password', '').strip()

    if not ssid:
        return jsonify({'error': 'SSID required'}), 400
    if password and len(password) < 8:
        return jsonify({'error': 'Hotspot password: minimum 8 characters (WPA2)'}), 400

    # Save
    _write_key('hotspot', 'ssid', ssid)
    if password:
        _write_key('hotspot', 'password', password)

    # Update the NM connection
    modify_cmd = ['nmcli', 'connection', 'modify', HOTSPOT_CON, 'ssid', ssid]
    if password:
        modify_cmd += ['wifi-sec.psk', password]
    _run(modify_cmd)

    # Restart the hotspot (clients disconnect then reconnect)
    _run(['nmcli', 'connection', 'down', HOTSPOT_CON])
    rc, _, err = _run(['nmcli', 'connection', 'up', HOTSPOT_CON])

    log.info(f"Hotspot updated: ssid={ssid}")
    return jsonify({
        'status': 'ok' if rc == 0 else 'partial',
        'warning': 'WiFi clients must reconnect with the new credentials',
    })


@settings_bp.post('/settings/config')
@require_admin
def set_config():
    """Updates general parameters in local.cfg."""
    data = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))

    # Allowed keys (section.key)
    _SLAVE_HAT_KEYS = {'i2c_servo_hats.slave_hats', 'i2c_servo_hats.slave_motor_hat'}
    allowed = {
        'github.branch', 'github.auto_pull_on_boot', 'github.repo_url',
        'slave.host',
        'i2c_servo_hats.master_hats', 'i2c_servo_hats.slave_hats', 'i2c_servo_hats.slave_motor_hat',
        'choreo.body_servo_uart_lat',
        # B-58 (audit 2026-05-15): audio_startup_lat was checked in the
        # hot-swap branch below but never included here, so the key
        # was rejected silently and the hot-swap was dead code. Add it
        # to the allowed set so the Settings UI / future caller can
        # actually persist the value AND benefit from the hot-swap.
        'choreo.audio_startup_lat',
        'lights.backend',
        'audio.channels',
        'audio.profile_convention', 'audio.profile_maison', 'audio.profile_exterieur',
        'battery.cells', 'battery.chemistry',
    }

    # B-78 / B-79 / B-80 (audit 2026-05-15): validate values per-key
    # BEFORE persisting. Old code wrote whatever string the client sent,
    # then clamped/normalised at read time — meaning the file held
    # bogus values like 'cells=99' until next save, and `slave.host=''`
    # would lock the deploy chain. Per-key normalisers below return the
    # validated string OR None to reject with 400.
    _VALID_CELLS  = {'4', '6', '7', '8'}
    _VALID_CHEM   = {'liion', 'lifepo4', 'lipo'}

    def _normalise(dotkey, raw):
        s = str(raw if raw is not None else '').strip()
        if dotkey == 'audio.channels':
            try:
                n = max(1, min(12, int(s)))
                return str(n)
            except ValueError:
                return None
        if dotkey in ('audio.profile_convention', 'audio.profile_maison',
                      'audio.profile_exterieur'):
            try:
                return str(max(0, min(100, int(s))))
            except ValueError:
                return None
        if dotkey == 'battery.cells':
            return s if s in _VALID_CELLS else None
        if dotkey == 'battery.chemistry':
            return s.lower() if s.lower() in _VALID_CHEM else None
        if dotkey == 'slave.host':
            # Audit finding M-8 2026-05-15: was just length-capped,
            # let through 'host;rm -rf /' or 'host with space'. Tighter
            # regex now — alphanumeric + dot + hyphen, RFC-1123-ish.
            # Argv-passing already blocks shell injection, this is
            # defense-in-depth + early reject of garbage values.
            import re as _re_h
            if not s or len(s) > 253:
                return None
            if not _re_h.match(r'^[A-Za-z0-9](?:[A-Za-z0-9.\-]*[A-Za-z0-9])?$', s):
                return None
            return s
        if dotkey == 'github.repo_url':
            # Light validation — must look like a URL (http/https/git@)
            if not s:
                return None
            if not (s.startswith('http://') or s.startswith('https://') or s.startswith('git@')):
                return None
            return s if len(s) <= 512 else None
        if dotkey == 'github.branch':
            # No spaces, no slashes-of-doom; up to 64 chars.
            if not s or len(s) > 64 or any(c in s for c in ' \t\n\r'):
                return None
            return s
        if dotkey == 'github.auto_pull_on_boot':
            return 'true' if s.lower() in ('true', '1', 'yes', 'on') else 'false'
        if dotkey == 'choreo.body_servo_uart_lat':
            try:
                return str(max(0.0, min(1.0, float(s))))
            except ValueError:
                return None
        if dotkey == 'choreo.audio_startup_lat':
            try:
                return str(max(0.0, min(1.0, float(s))))
            except ValueError:
                return None
        if dotkey == 'lights.backend':
            return s if s in ('astropixels', 'teeces', 'none') else None
        # I2C HAT keys handled separately below; pass through.
        return s

    # Audit finding H-1 2026-05-15: Slave-HAT keys used to skip
    # _normalise entirely and pass raw operator input straight into
    # slave.cfg via ConfigParser. A POST like
    # `{"i2c_servo_hats.slave_hats": "0x41\n[admin]\npassword=pwn"}`
    # injected a fake [admin] section into slave.cfg at the next
    # write. Now validate as comma-separated 0xNN hex addresses with
    # control chars stripped, before letting them through.
    import re as _re_hat
    _HAT_LIST_RE = _re_hat.compile(r'^0x[0-9a-fA-F]{2}(\s*,\s*0x[0-9a-fA-F]{2})*$')
    _HAT_SINGLE_RE = _re_hat.compile(r'^0x[0-9a-fA-F]{2}$')

    updated = []
    rejected = []
    for dotkey, value in data.items():
        if dotkey not in allowed:
            continue
        if dotkey in _SLAVE_HAT_KEYS:
            # Strip newlines + leading/trailing whitespace before regex
            # so the inject-via-newline trick can't bypass.
            raw = str(value).replace('\r', '').replace('\n', '').replace('\x00', '').strip()
            # slave_motor_hat is single address; slave_hats is list.
            key_short = dotkey.split('.', 1)[1]
            ok = (_HAT_SINGLE_RE.match(raw) if key_short == 'slave_motor_hat'
                  else _HAT_LIST_RE.match(raw))
            if not ok:
                rejected.append(dotkey)
                continue
            data[dotkey] = raw   # canonicalise for the sync step below
            updated.append(dotkey)
            continue
        norm = _normalise(dotkey, value)
        if norm is None:
            rejected.append(dotkey)
            continue
        section, key = dotkey.split('.', 1)
        _write_key(section, key, norm)
        updated.append(dotkey)
    if rejected:
        log.warning("set_config rejected invalid values for: %s", rejected)
        return jsonify({'error': f'invalid value(s): {", ".join(rejected)}'}), 400

    # Slave HAT keys go to slave.cfg (not local.cfg) and trigger a Slave
    # restart — but ONLY if the new values genuinely differ from what the
    # Slave already has. Defends against clients that POST the whole hardware
    # form even when the user only edited an unrelated field (the JS frontend
    # now diffs before sending, but other callers — Android, scripts, future
    # code — should not trigger a needless Slave restart either).
    slave_hat_updates = {k.split('.', 1)[1]: str(data[k]) for k in updated if k in _SLAVE_HAT_KEYS}
    if slave_hat_updates:
        scfg = _read_slave_cfg()
        current = {
            'slave_hats':      scfg.get('i2c_servo_hats', 'slave_hats',      fallback='0x41'),
            'slave_motor_hat': scfg.get('i2c_servo_hats', 'slave_motor_hat', fallback='0x40'),
        }
        actually_changed = {k: v for k, v in slave_hat_updates.items() if current.get(k) != v}
        if actually_changed:
            merged = {**current, **actually_changed}
            _sync_slave_hat_cfg(**merged)
            log.info("Slave HAT updates applied: %s", actually_changed)
        else:
            log.info("Slave HAT keys submitted but values unchanged — skipping SCP+restart")

    if 'audio.channels' in updated:
        try:
            channels = max(1, min(12, int(data.get('audio.channels', 6))))
            _sync_audio_channels(channels)
        except (ValueError, TypeError) as e:
            log.warning("Invalid audio.channels value: %s", e)

    # Hot-swap choreo timing parameters so the user does not need to reboot
    # the Master to see the new latency values applied. Takes effect at the
    # next play() / next loop iteration.
    if ('choreo.body_servo_uart_lat' in updated
            or 'choreo.audio_startup_lat' in updated):
        import master.registry as reg
        if 'choreo.body_servo_uart_lat' in updated and reg.choreo:
            try:
                reg.choreo.set_body_uart_lat(float(data['choreo.body_servo_uart_lat']))
            except Exception as e:
                log.warning("Hot-swap body_servo_uart_lat failed: %s", e)
        if 'choreo.audio_startup_lat' in updated and reg.choreo:
            try:
                reg.choreo.set_audio_startup_lat(float(data['choreo.audio_startup_lat']))
            except Exception as e:
                log.warning("Hot-swap audio_startup_lat failed: %s", e)

    return jsonify({'status': 'ok', 'updated': updated})


@settings_bp.post('/settings/audio/profile/apply')
@require_admin
def apply_audio_profile():
    """Applies a saved volume profile immediately. Body: {"profile": "convention"}"""
    import master.registry as reg
    data = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    name = data.get('profile', '').strip().lower()
    _defaults = {'convention': 70, 'maison': 85, 'exterieur': 95}
    if name not in _defaults:
        return jsonify({'error': 'Unknown profile — use convention, maison, or exterieur'}), 400
    cfg = _read_cfg()
    vol = _safe_int(cfg.get('audio', f'profile_{name}', fallback=str(_defaults[name])), _defaults[name])
    reg.audio_volume = vol
    if reg.uart:
        reg.uart.send('VOL', str(vol))
    log.info("Audio profile applied: %s → %d%%", name, vol)
    return jsonify({'status': 'ok', 'profile': name, 'volume': vol})


def _get_admin_password() -> str:
    """Returns the current admin password from local.cfg (default: deetoo)."""
    return _read_cfg().get('admin', 'password', fallback='deetoo')


# B-53 (audit 2026-05-15): rate-limit /settings/admin/verify to defeat
# brute-force. Simple per-IP token bucket — 10 attempts per 60s, then
# 5-min cooldown. In-memory; resets on Master restart (acceptable).
import hmac as _hmac
import time as _time_rate
_verify_attempts: dict = {}   # {ip: [timestamps]}
_VERIFY_WINDOW_S  = 60
_VERIFY_MAX_TRIES = 10
_VERIFY_LOCKOUT_S = 300


def _verify_rate_check(ip: str) -> tuple[bool, float]:
    """Return (allowed, retry_after_seconds). Drops attempts older than
    window. If MAX_TRIES exceeded, all caller's attempts get the
    lockout extension."""
    now = _time_rate.monotonic()
    bucket = _verify_attempts.get(ip, [])
    bucket = [t for t in bucket if now - t < _VERIFY_WINDOW_S]
    if len(bucket) >= _VERIFY_MAX_TRIES:
        # locked — return retry-after from the oldest attempt
        retry = _VERIFY_LOCKOUT_S - (now - bucket[0])
        _verify_attempts[ip] = bucket   # keep the bucket
        return (False, max(retry, 0.0))
    bucket.append(now)
    _verify_attempts[ip] = bucket
    return (True, 0.0)


@settings_bp.post('/settings/admin/verify')
def admin_verify():
    """Verifies the admin password. Body: {\"password\": \"...\"}

    B-52 (audit 2026-05-15): hmac.compare_digest to defeat timing
    attacks. == leaks the byte-prefix match length through response
    timing; on a fast LAN the channel is too noisy to exploit but the
    fix is free and matches the require_admin decorator's pattern.

    B-53: rate-limited per-IP to defeat brute-force. After 10 failed
    attempts in 60s the IP gets a 5-min lockout (429 Too Many
    Requests). Resets across Master reboots.
    """
    # Audit finding M-3 2026-05-15: trusting X-Forwarded-For let any
    # attacker bypass the rate limit by spoofing a new IP per request.
    # AstromechOS runs Flask directly on the LAN (no reverse proxy),
    # so remote_addr is authoritative and X-Forwarded-For should be
    # ignored. If a proxy is ever introduced, the gateway sets the
    # header and the proxy itself must enforce the limit upstream.
    ip = request.remote_addr or 'unknown'
    allowed, retry = _verify_rate_check(ip)
    if not allowed:
        log.warning("admin verify rate-limited: %s (retry in %.0fs)", ip, retry)
        return jsonify({
            'ok': False,
            'error': 'too many attempts',
            'retry_after_s': int(retry),
        }), 429
    data = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    pwd  = (data.get('password', '') or '').encode()
    expected = _get_admin_password().encode()
    # compare_digest needs equal-length operands; pad to expected len
    # to avoid the length-difference timing side channel.
    if pwd and _hmac.compare_digest(pwd, expected):
        # Clear this IP's bucket on success so a legit operator who
        # mistyped once doesn't sit in a half-full bucket.
        _verify_attempts.pop(ip, None)
        return jsonify({'ok': True})
    return jsonify({'ok': False}), 401


@settings_bp.post('/settings/admin/password')
@require_admin
def admin_change_password():
    """Changes the admin password. Body: {\"current\": \"...\", \"new\": \"...\"}"""
    data    = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    current = data.get('current', '')
    new_pwd = data.get('new', '').strip()

    if current != _get_admin_password():
        return jsonify({'error': 'Incorrect current password'}), 401
    if len(new_pwd) < 4:
        return jsonify({'error': 'New password must be at least 4 characters'}), 400
    # Audit finding M-4 2026-05-15: cap at 128 chars. Without this a
    # 1 MB password bloats local.cfg and every admin call compares
    # against a multi-megabyte string. 128 chars is plenty for any
    # human-typeable secret + leaves room for paste-from-manager.
    if len(new_pwd) > 128:
        return jsonify({'error': 'New password too long (max 128 chars)'}), 400

    _write_key('admin', 'password', new_pwd)
    log.info("Admin password changed")
    return jsonify({'ok': True})


@settings_bp.get('/settings/icons')
def list_icons():
    """Returns list of image files available in the icons/ folder.
    B-81 (audit 2026-05-15): skip dotfiles. A planted '.hidden.png'
    used to surface in the picker; this matches upload_icon's reject
    of leading-dot filenames."""
    os.makedirs(_ICONS_DIR, exist_ok=True)
    # B-82 follow-up: list both the upload-allowed formats AND any
    # pre-shipped / SCP'd .svg files. Upload itself stays restricted.
    files = sorted(
        f for f in os.listdir(_ICONS_DIR)
        if not f.startswith('.')
        and os.path.splitext(f)[1].lower() in _ALLOWED_LIST_EXT
    )
    return jsonify({'icons': files})


# Magic-bytes signatures for each accepted image format. Verified
# after Werkzeug's content-type parsing but BEFORE writing to disk —
# audit finding M-6 2026-05-15: extension-only allowlist let an
# attacker upload a 500MB PHP/HTML/binary file pretending to be PNG.
# No PHP interpreter on the Pi so not directly exploitable, but
# defense-in-depth + blocks the disk-fill DoS via lying extensions.
_IMAGE_MAGIC = {
    '.png':  [b'\x89PNG\r\n\x1a\n'],
    '.jpg':  [b'\xff\xd8\xff'],
    '.jpeg': [b'\xff\xd8\xff'],
    '.gif':  [b'GIF87a', b'GIF89a'],
    '.webp': [b'RIFF'],   # followed by 4 bytes size + b'WEBP' at offset 8
}


def _verify_magic_bytes(ext: str, head: bytes) -> bool:
    """Return True if the first bytes match the extension's signature."""
    sigs = _IMAGE_MAGIC.get(ext, [])
    if not sigs:
        return False
    for sig in sigs:
        if head.startswith(sig):
            # WebP needs the secondary check at offset 8
            if ext == '.webp':
                return len(head) >= 12 and head[8:12] == b'WEBP'
            return True
    return False


# ASCII-only filename regex. Audit finding M-5 2026-05-15: the
# isalnum() char filter accepted unicode (RTL marks, homoglyphs)
# which makes for confusing filenames on Windows shares mounted by
# other admins. Force ASCII alphanumerics + dot/hyphen/underscore.
import re as _re_icon
_ICON_FILENAME_RE = _re_icon.compile(r'^[A-Za-z][A-Za-z0-9._-]{0,63}$')


@settings_bp.post('/settings/icons/upload')
@require_admin
def upload_icon():
    """Uploads a new image to the icons/ folder. Multipart form: file=<image>."""
    if 'file' not in request.files:
        return jsonify({'error': 'no file'}), 400
    f = request.files['file']
    fname = f.filename or ''
    ext = os.path.splitext(fname)[1].lower()
    if ext not in _ALLOWED_UPLOAD_EXT:
        return jsonify({
            'error': f'unsupported format (allowed: {", ".join(sorted(_ALLOWED_UPLOAD_EXT))}). '
                     f'SVG uploads blocked for security — convert to PNG.'
        }), 400

    # Sanitize filename: strip path, drop non-ASCII, lower case, regex check.
    raw = os.path.basename(fname).strip().rstrip('.')
    safe = ''.join(c for c in raw if c.isascii() and (c.isalnum() or c in '._-'))
    if not _ICON_FILENAME_RE.match(safe):
        return jsonify({
            'error': 'invalid filename (ASCII letters/digits/.-_ only, must start with a letter, ≤64 chars)',
        }), 400

    # Magic bytes verification — read up to 12 bytes then rewind.
    head = f.stream.read(12)
    f.stream.seek(0)
    if not _verify_magic_bytes(ext, head):
        return jsonify({'error': f'file content does not match {ext} format'}), 400

    os.makedirs(_ICONS_DIR, exist_ok=True)
    dest = os.path.realpath(os.path.join(_ICONS_DIR, safe))
    icons_real = os.path.realpath(_ICONS_DIR)
    if not dest.startswith(icons_real + os.sep):
        return jsonify({'error': 'invalid filename (escape attempt)'}), 400
    f.save(dest)
    log.info("Icon uploaded: %s", safe)
    return jsonify({'status': 'ok', 'filename': safe})


@settings_bp.post('/settings/icons/delete')
@require_admin
def delete_icon():
    """Deletes an icon file. Body: {\"filename\": \"foo.png\"}"""
    data = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    fname = os.path.basename(data.get('filename', ''))
    if not fname or fname.startswith('.'):
        return jsonify({'error': 'filename required'}), 400
    # B-56 (audit 2026-05-15): realpath containment — basename() strips
    # `..` but a symlink in _ICONS_DIR (planted by another path) could
    # redirect the delete outside the icons dir. Resolve + verify.
    path = os.path.realpath(os.path.join(_ICONS_DIR, fname))
    icons_real = os.path.realpath(_ICONS_DIR)
    if not path.startswith(icons_real + os.sep):
        return jsonify({'error': 'escape attempt'}), 400
    if not os.path.exists(path):
        return jsonify({'error': 'not found'}), 404
    os.remove(path)
    log.info("Icon deleted: %s", fname)
    return jsonify({'status': 'ok'})


@settings_bp.post('/settings/robot_icon')
@require_admin
def set_robot_icon():
    """Saves robot header icon to local.cfg. Body: {\"icon\": \"img:foo.png\"} or {\"icon\": \"🤖\"} or {\"icon\": \"\"} to reset."""
    data = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    icon = data.get('icon', '').strip()
    _write_key('robot', 'icon', icon)
    return jsonify({'status': 'ok', 'icon': icon})


@settings_bp.post('/settings/robot_locations')
@require_admin
def set_robot_locations():
    """Saves master/slave display location names. Body: {\"master_location\":\"Dome\",\"slave_location\":\"Body\"}"""
    data   = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    master = data.get('master_location', '').strip()[:20]
    slave  = data.get('slave_location',  '').strip()[:20]
    if master: _write_key('robot', 'master_location', master)
    if slave:  _write_key('robot', 'slave_location',  slave)
    return jsonify({'status': 'ok', 'master_location': master, 'slave_location': slave})


@settings_bp.post('/settings/robot_name')
@require_admin
def set_robot_name():
    """Saves robot display name to local.cfg. Body: {\"name\": \"R2-D2\"}"""
    data = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    if len(name) > 32:
        return jsonify({'error': 'name too long (max 32 chars)'}), 400
    _write_key('robot', 'name', name)
    return jsonify({'status': 'ok', 'name': name})


@settings_bp.post('/settings/lights')
@require_admin
def set_lights_backend():
    """Changes the lights driver at runtime (no reboot). Body: {\"backend\": \"astropixels\"}"""
    data    = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    backend = data.get('backend', '').strip().lower()
    if backend not in {'teeces', 'astropixels'}:
        return jsonify({'error': 'invalid backend. Values: teeces, astropixels'}), 400
    _write_key('lights', 'backend', backend)
    result = _reload_lights_driver(backend)
    if not result['ok']:
        return jsonify({'status': 'error', **result}), 500
    return jsonify({'status': 'ok', 'backend': backend,
                    'message': f'Lights driver reloaded: {backend}'})
