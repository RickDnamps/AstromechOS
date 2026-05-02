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
Blueprint API Status — Phase 4.
Reports R2-D2 system state in real time.

Endpoints:
  GET  /status              → full JSON state
  GET  /status/version      → Master + Slave versions
  POST /system/reboot       → reboot Master
  POST /system/reboot_slave → reboot Slave (via UART)
"""

import configparser
import datetime
import os
import subprocess
import threading
import time as _time
from flask import Blueprint, request, jsonify
import master.registry as reg
from master.app_watchdog import app_watchdog

_MAIN_CFG  = '/home/artoo/r2d2/master/config/main.cfg'
_LOCAL_CFG = '/home/artoo/r2d2/master/config/local.cfg'


def _slave_host() -> str:
    cfg = configparser.ConfigParser()
    cfg.read([_MAIN_CFG, _LOCAL_CFG])
    return cfg.get('slave', 'host', fallback='r2-slave.local')


def _mem_info() -> dict | None:
    try:
        info = {}
        with open('/proc/meminfo') as f:
            for line in f:
                k, v = line.split(':', 1)
                info[k.strip()] = int(v.strip().split()[0])
        total     = info.get('MemTotal', 0)
        available = info.get('MemAvailable', 0)
        used      = total - available
        return {
            'used_mb':  round(used / 1024),
            'total_mb': round(total / 1024),
            'free_mb':  round(available / 1024),
        }
    except Exception:
        return None


def _disk_info() -> dict | None:
    try:
        st = os.statvfs('/')
        total = st.f_blocks * st.f_frsize
        free  = st.f_bavail * st.f_frsize
        used  = total - free
        return {
            'used_gb':  round(used  / 1024**3, 1),
            'total_gb': round(total / 1024**3, 1),
            'free_gb':  round(free  / 1024**3, 1),
        }
    except Exception:
        return None


_cpu_prev: tuple[int, int] | None = None  # (idle, total) from last call


def _cpu_pct() -> float | None:
    global _cpu_prev
    try:
        with open('/proc/stat') as f:
            parts = f.readline().split()
        vals  = [int(x) for x in parts[1:]]
        idle  = vals[3] + (vals[4] if len(vals) > 4 else 0)  # idle + iowait
        total = sum(vals)
        if _cpu_prev is None:
            _cpu_prev = (idle, total)
            return None
        d_idle, d_total = idle - _cpu_prev[0], total - _cpu_prev[1]
        _cpu_prev = (idle, total)
        if d_total == 0:
            return 0.0
        return round((1 - d_idle / d_total) * 100, 1)
    except Exception:
        return None

try:
    from master.api import camera_bp as _cam_bp
except Exception:
    _cam_bp = None

status_bp = Blueprint('status', __name__)

VERSION_FILE = '/home/artoo/r2d2/VERSION'


def _read_version() -> str:
    try:
        with open(VERSION_FILE, encoding='utf-8') as f:
            return f.read().strip()
    except Exception:
        return 'unknown'


def _uptime() -> str:
    try:
        with open('/proc/uptime', 'r') as f:
            seconds = float(f.readline().split()[0])
        return str(datetime.timedelta(seconds=int(seconds)))
    except Exception:
        return 'unknown'


def _cpu_temp() -> float | None:
    try:
        with open('/sys/class/thermal/thermal_zone0/temp') as f:
            return round(int(f.read().strip()) / 1000, 1)
    except Exception:
        return None


def _vesc_side_ok(telem, max_age: float = 2.0) -> bool:
    """True = drive allowed for this VESC side.
    bench_mode ON  → None telem = allow (no VESC hardware).
    bench_mode OFF → None telem = block (full safety check).
    Stale (>max_age s) or fault ≠ 0 always blocks."""
    if telem is None:
        return bool(getattr(reg, 'vesc_bench_mode', False))
    if _time.time() - telem.get('ts', 0) > max_age:
        return False
    return telem.get('fault', 0) == 0


@status_bp.get('/status')
def get_status():
    """Full R2-D2 system state."""
    _uart_serial = getattr(reg.uart, '_serial', None)
    uart_ready   = bool(_uart_serial and _uart_serial.is_open
                        and getattr(reg.uart, '_running', False))
    # HB  = application heartbeat App ↔ Master (AppWatchdog)
    # UART = serial link Master ↔ Slave
    heartbeat_ok = app_watchdog.is_connected
    # BT controller status
    bt_status = reg.bt_ctrl.get_status() if reg.bt_ctrl else {}
    return jsonify({
        'version':      _read_version(),
        'uptime':       _uptime(),
        'temperature':  _cpu_temp(),
        'heartbeat_ok': heartbeat_ok,   # App ↔ Master
        'uart_ready':   uart_ready,     # Master ↔ Slave UART
        'app_hb_age_ms': app_watchdog.last_hb_age_ms,
        'battery_voltage':  next(
            (t['v_in'] for t in [reg.vesc_telem.get('L'), reg.vesc_telem.get('R')]
             if t and t.get('v_in')), None
        ),
        'vesc_temp': max(
            (t['temp'] for t in [reg.vesc_telem.get('L'), reg.vesc_telem.get('R')]
             if t and t.get('temp') is not None), default=None
        ),
        'vesc_duty': max(
            (abs(t['duty']) for t in [reg.vesc_telem.get('L'), reg.vesc_telem.get('R')]
             if t and t.get('duty') is not None), default=None
        ),
        'teeces_ready':     bool(reg.teeces     and reg.teeces.is_ready()),
        'vesc_ready':       bool(reg.vesc       and reg.vesc.is_ready()),
        'dome_ready':       bool(reg.dome       and reg.dome.is_ready()),
        'servo_ready':      bool(reg.servo      and reg.servo.is_ready()),
        'dome_servo_ready': bool(reg.dome_servo and reg.dome_servo.is_ready()),
        'scripts_running': reg.engine.list_running() if reg.engine else [],
        'choreo_playing':  bool(reg.choreo and reg.choreo.is_playing()),
        'choreo_name':     (reg.choreo.get_status().get('name') if reg.choreo and reg.choreo.is_playing() else None),
        'uart_health':       reg.slave_uart_health,          # None si Slave injoignable
        'uart_crc_errors':   reg.uart.crc_errors if reg.uart else 0,  # consecutive invalid CRC on Master side
        'audio_playing':     reg.audio_playing,
        'audio_current':     reg.audio_current,
        'lock_mode':         reg.lock_mode,
        'estop_active':      reg.estop_active,
        'lights_backend':    type(reg.teeces).__name__.replace('Driver', '').lower() if reg.teeces else 'none',
        'vesc_l_ok':         _vesc_side_ok(reg.vesc_telem.get('L')),
        'vesc_r_ok':         _vesc_side_ok(reg.vesc_telem.get('R')),
        'vesc_drive_safe':   _vesc_side_ok(reg.vesc_telem.get('L')) and _vesc_side_ok(reg.vesc_telem.get('R')),
        'vesc_bench_mode':   bool(reg.vesc_bench_mode),
        'camera_active':     bool(_cam_bp and _cam_bp._active_token > 0),
        'vesc_l_temp':       (reg.vesc_telem.get('L') or {}).get('temp'),
        'vesc_r_temp':       (reg.vesc_telem.get('R') or {}).get('temp'),
        'alive_enabled':     bool(reg.behavior_engine and reg.behavior_engine._cfg.getboolean('behavior', 'alive_enabled', fallback=False)),
        'slave_host':        _slave_host(),
        'master_mem':        _mem_info(),
        'master_cpu':        _cpu_pct(),
        'master_disk':       _disk_info(),
        'slave_temp':        (reg.slave_uart_health or {}).get('cpu_temp'),
        'slave_mem':         (reg.slave_uart_health or {}).get('mem'),
        'slave_disk':        (reg.slave_uart_health or {}).get('disk'),
        **bt_status,
    })


@status_bp.get('/status/version')
def get_version():
    """Master and Slave versions."""
    return jsonify({'master': _read_version()})


@status_bp.post('/system/update')
def system_update():
    """Forces git pull + rsync Slave + reboot Slave (same as the dome button)."""
    if not reg.deploy:
        return jsonify({'error': 'DeployController not available'}), 503
    import threading
    threading.Thread(target=reg.deploy.update_and_deploy, daemon=True).start()
    return jsonify({'status': 'ok', 'message': 'Update in progress...'})


@status_bp.post('/lock/set')
def lock_set():
    """Sets the lock mode: 0=Normal, 1=Kids, 2=ChildLock."""
    body = request.get_json(silent=True) or {}
    mode = int(body.get('mode', 0))
    if mode not in (0, 1, 2):
        return jsonify({'error': 'invalid mode'}), 400
    reg.lock_mode = mode
    if 'kids_speed_limit' in body:
        reg.kids_speed_limit = max(0.0, min(1.0, float(body.get('kids_speed_limit', 0.5))))
    return jsonify({'status': 'ok', 'mode': mode})


@status_bp.post('/system/resync_slave')
def system_resync_slave():
    """
    Rsync + service install + restart Slave only.
    Called automatically by the Slave via HTTP when it detects a version mismatch at boot.
    """
    def do_resync():
        subprocess.run(
            ['bash', '/home/artoo/r2d2/scripts/resync_slave.sh'],
            check=False
        )
    threading.Thread(target=do_resync, daemon=True).start()
    return jsonify({'status': 'resync_triggered'})


@status_bp.post('/system/reboot')
def system_reboot():
    """Reboots the Master (dome Pi)."""
    threading.Thread(
        target=lambda: subprocess.run(['sudo', 'reboot'], check=False),
        daemon=True
    ).start()
    return jsonify({'status': 'rebooting'})


@status_bp.post('/system/reboot_slave')
def system_reboot_slave():
    """Sends a reboot command to the Slave via UART."""
    if reg.uart:
        reg.uart.send('REBOOT', '1')
        return jsonify({'status': 'ok'})
    return jsonify({'error': 'UART not available'}), 503


@status_bp.post('/system/shutdown')
def system_shutdown():
    """Shuts down the Master."""
    threading.Thread(
        target=lambda: subprocess.run(['sudo', 'shutdown', '-h', 'now'], check=False),
        daemon=True
    ).start()
    return jsonify({'status': 'shutting_down'})


@status_bp.post('/heartbeat')
def app_heartbeat():
    """
    Application heartbeat — App → Master, every 200ms.
    If this heartbeat stops for >600ms → emergency stop (AppWatchdog).
    Ultra-lightweight endpoint: just a timestamp update.
    """
    app_watchdog.feed()
    return '', 204   # No Content — minimal response


@status_bp.post('/system/estop')
def system_estop():
    """Emergency stop servos — cuts PWM PCA9685 Master (0x40) + Slave (0x41) via smbus2."""
    # Cut via active drivers if available
    if reg.dome_servo:
        try:
            reg.dome_servo.shutdown()
        except Exception:
            pass
    if reg.servo:
        try:
            reg.servo.shutdown()
        except Exception:
            pass
    reg.estop_active = True
    # Guaranteed fallback: estop.py directly via subprocess
    threading.Thread(
        target=lambda: subprocess.run(
            ['python3', '/home/artoo/r2d2/scripts/estop.py'], check=False
        ),
        daemon=True
    ).start()
    return jsonify({'status': 'estop_sent'})


@status_bp.post('/system/estop_reset')
def system_estop_reset():
    """Re-arms servo drivers after an E-STOP — reinitializes PCA9685 without restarting the service."""
    import logging
    log = logging.getLogger(__name__)
    reg.estop_active = False
    results = {}
    if reg.dome_servo:
        ok = reg.dome_servo.setup()
        results['dome_servo'] = 'ok' if ok else 'error'
        log.info("estop_reset: dome_servo setup → %s", results['dome_servo'])
    if reg.servo:
        ok = reg.servo.setup()
        results['body_servo'] = 'ok' if ok else 'error'
        log.info("estop_reset: body_servo setup → %s", results['body_servo'])
    return jsonify({'status': 'reset', 'drivers': results})
