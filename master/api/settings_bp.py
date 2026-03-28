# ============================================================
#  ██████╗ ██████╗       ██████╗ ██████╗
#  ██╔══██╗╚════██╗      ██╔══██╗╚════██╗
#  ██████╔╝ █████╔╝      ██║  ██║ █████╔╝
#  ██╔══██╗██╔═══╝       ██║  ██║██╔═══╝
#  ██║  ██║███████╗      ██████╔╝███████╗
#  ╚═╝  ╚═╝╚══════╝      ╚═════╝ ╚══════╝
#
#  R2-D2 Control System — Distributed Robot Controller
# ============================================================
#  Copyright (C) 2025 RickDnamps
#  https://github.com/RickDnamps/R2D2_Control
#
#  This file is part of R2D2_Control.
#
#  R2D2_Control is free software: you can redistribute it
#  and/or modify it under the terms of the GNU General
#  Public License as published by the Free Software
#  Foundation, either version 2 of the License, or
#  (at your option) any later version.
#
#  R2D2_Control is distributed in the hope that it will be
#  useful, but WITHOUT ANY WARRANTY; without even the implied
#  warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
#  PURPOSE. See the GNU General Public License for details.
#
#  You should have received a copy of the GNU GPL along with
#  R2D2_Control. If not, see <https://www.gnu.org/licenses/>.
# ============================================================
"""
Blueprint API Settings — Network configuration and R2-D2 parameters.

Endpoints:
  GET  /settings              → read current config (local.cfg + NM state)
  GET  /settings/wifi/scan    → scan available WiFi networks on wlan1
  POST /settings/wifi         → update wlan1 (local.cfg + nmcli reconnect)
  POST /settings/hotspot      → update hotspot credentials for wlan0
  POST /settings/config       → update general parameters (branch, slave, etc.)
"""

import configparser
import logging
import os
import subprocess
from flask import Blueprint, request, jsonify

settings_bp = Blueprint('settings', __name__)
log = logging.getLogger(__name__)

LOCAL_CFG    = '/home/artoo/r2d2/master/config/local.cfg'
INTERNET_CON = 'r2d2-internet'
HOTSPOT_CON  = 'r2d2-hotspot'


# =============================================================================
# Helpers
# =============================================================================

def _read_cfg() -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    if os.path.exists(LOCAL_CFG):
        cfg.read(LOCAL_CFG)
    return cfg


def _write_key(section: str, key: str, value: str) -> None:
    """Writes or updates a key in local.cfg."""
    cfg = _read_cfg()
    if not cfg.has_section(section):
        cfg.add_section(section)
    cfg.set(section, key, value)
    with open(LOCAL_CFG, 'w', encoding='utf-8') as f:
        cfg.write(f)


def _run(cmd: list[str], timeout: int = 15) -> tuple[int, str, str]:
    """Runs a command, returns (returncode, stdout, stderr)."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return 1, '', 'timeout'
    except Exception as e:
        return 1, '', str(e)


def _nm_field(device: str, field: str) -> str:
    """Reads an nmcli field for a device."""
    rc, out, _ = _run(['nmcli', '-g', field, 'device', 'show', device])
    return out if rc == 0 else ''


import threading as _threading
_lights_reload_lock = _threading.Lock()


def _read_fresh_cfg() -> configparser.ConfigParser:
    """Re-reads main.cfg + local.cfg from disk (for hot-reload)."""
    from master.config.config_loader import MAIN_CFG, LOCAL_CFG
    cfg = configparser.ConfigParser()
    cfg.read([MAIN_CFG, LOCAL_CFG])
    return cfg


def _reload_lights_driver(backend: str) -> dict:
    """
    Shuts down the current driver, loads the new one, updates reg.teeces.
    Thread-safe via _lights_reload_lock (Flask runs with threaded=True).
    """
    import master.registry as reg
    from master.lights import load_driver

    with _lights_reload_lock:
        if reg.teeces:
            try:
                reg.teeces.shutdown()
            except Exception as e:
                log.warning(f"Shutdown of previous lights driver: {e}")
            reg.teeces = None   # guard during swap

        cfg = _read_fresh_cfg()
        try:
            new_driver = load_driver(cfg)
        except ValueError as e:
            log.error(f"Invalid lights backend: {e}")
            return {'ok': False, 'error': str(e)}

        if not new_driver.setup():
            log.error(f"Lights driver setup failed ({backend})")
            return {'ok': False, 'error': f"Setup {backend} failed (port unavailable?)"}

        reg.teeces = new_driver
        new_driver.random_mode()

    log.info(f"Lights driver reloaded: {backend}")
    return {'ok': True}


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
            'ssid':         cfg.get('hotspot', 'ssid', fallback='R2D2_Control'),
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
        'deploy': {
            'button_pin': cfg.getint('deploy', 'button_pin', fallback=17),
        },
        'lights': {
            'backend':   cfg.get('lights', 'backend', fallback='teeces'),
            'available': ['teeces', 'astropixels'],
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
def set_wifi():
    """Updates wlan1 credentials and attempts to connect."""
    data = request.get_json() or {}
    ssid     = data.get('ssid', '').strip()
    password = data.get('password', '').strip()

    if not ssid:
        return jsonify({'error': 'SSID required'}), 400

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
        log.error(f"nmcli add wlan1 failed: {err}")
        return jsonify({'error': f'nmcli error: {err}'}), 500

    rc2, _, _ = _run(['nmcli', 'connection', 'up', INTERNET_CON])
    connected = rc2 == 0

    log.info(f"WiFi wlan1 updated: ssid={ssid}, connected={connected}")
    return jsonify({'status': 'ok', 'connected': connected,
                    'message': 'Connected ✓' if connected else 'Config saved — will connect on next boot'})


@settings_bp.post('/settings/hotspot')
def set_hotspot():
    """Updates hotspot credentials for wlan0 and restarts the hotspot."""
    data = request.get_json() or {}
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
def set_config():
    """Updates general parameters in local.cfg."""
    data = request.get_json() or {}

    # Allowed keys (section.key)
    allowed = {
        'github.branch', 'github.auto_pull_on_boot',
        'slave.host', 'deploy.button_pin',
        'lights.backend',
    }

    updated = []
    for dotkey, value in data.items():
        if dotkey in allowed:
            section, key = dotkey.split('.', 1)
            _write_key(section, key, str(value))
            updated.append(dotkey)

    return jsonify({'status': 'ok', 'updated': updated})


@settings_bp.post('/settings/lights')
def set_lights_backend():
    """Changes the lights driver at runtime (no reboot). Body: {\"backend\": \"astropixels\"}"""
    data    = request.get_json() or {}
    backend = data.get('backend', '').strip().lower()
    if backend not in {'teeces', 'astropixels'}:
        return jsonify({'error': 'invalid backend. Values: teeces, astropixels'}), 400
    _write_key('lights', 'backend', backend)
    result = _reload_lights_driver(backend)
    if not result['ok']:
        return jsonify({'status': 'error', **result}), 500
    return jsonify({'status': 'ok', 'backend': backend,
                    'message': f'Lights driver reloaded: {backend}'})
