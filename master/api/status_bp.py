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
Blueprint API Status — Phase 4.
Reports AstromechOS system state in real time.

Endpoints:
  GET  /status              → full JSON state
  GET  /status/version      → Master + Slave versions
  POST /system/reboot       → reboot Master
  POST /system/reboot_slave → reboot Slave (via UART)
"""

import configparser
import datetime
import glob
import logging
import os
import subprocess
import threading
import time as _time
from flask import Blueprint, request, jsonify
import master.registry as reg
from master.app_watchdog import app_watchdog
from master.vesc_safety import is_drive_safe

from shared.paths import MAIN_CFG as _MAIN_CFG, LOCAL_CFG as _LOCAL_CFG, VERSION_FILE, SCRIPTS_DIR

log = logging.getLogger(__name__)


def _iface_ip(iface: str) -> str | None:
    try:
        import socket, struct, fcntl
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        raw = fcntl.ioctl(s.fileno(), 0x8915, struct.pack('256s', iface[:15].encode()))
        return socket.inet_ntoa(raw[20:24])
    except Exception:
        return None


def _slave_host() -> str:
    cfg = configparser.ConfigParser()
    cfg.read([_MAIN_CFG, _LOCAL_CFG])
    return cfg.get('slave', 'host', fallback='r2-slave.local')


def _battery_cells() -> int:
    cfg = configparser.ConfigParser()
    cfg.read([_MAIN_CFG, _LOCAL_CFG])
    return cfg.getint('battery', 'cells', fallback=4)


def _robot_name() -> str:
    cfg = configparser.ConfigParser()
    cfg.read([_MAIN_CFG, _LOCAL_CFG])
    return cfg.get('robot', 'name', fallback='R2-D2')


def _robot_icon() -> str:
    cfg = configparser.ConfigParser()
    cfg.read([_MAIN_CFG, _LOCAL_CFG])
    return cfg.get('robot', 'icon', fallback='')


def _robot_location(key: str, fallback: str) -> str:
    cfg = configparser.ConfigParser()
    cfg.read([_MAIN_CFG, _LOCAL_CFG])
    return cfg.get('robot', key, fallback=fallback)


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
    bench = bool(getattr(reg, 'vesc_bench_mode', False))
    if telem is None:
        return bench
    if _time.time() - telem.get('ts', 0) > max_age:
        return bench  # bench mode bypasses stale check too
    return telem.get('fault', 0) == 0


@status_bp.get('/status')
def get_status():
    """Full AstromechOS system state."""
    _uart_serial = getattr(reg.uart, '_serial', None)
    uart_ready   = bool(_uart_serial and _uart_serial.is_open
                        and getattr(reg.uart, '_running', False))
    # HB  = application heartbeat App ↔ Master (AppWatchdog)
    # UART = serial link Master ↔ Slave
    heartbeat_ok = app_watchdog.is_connected
    # BT controller status
    bt_status = reg.bt_ctrl.get_status() if reg.bt_ctrl else {}
    return jsonify({
        'robot_name':        _robot_name(),
        'robot_icon':        _robot_icon(),
        'master_location':   _robot_location('master_location', 'Dome'),
        'slave_location':    _robot_location('slave_location',  'Body'),
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
        'vesc_drive_safe':   is_drive_safe(),
        'vesc_bench_mode':   bool(reg.vesc_bench_mode),
        'camera_active':     bool(_cam_bp and _cam_bp._active_token > 0),
        'camera_found':      len(glob.glob('/dev/video*')) > 0,
        'dome_hat_health':   reg.dome_servo.hat_health() if reg.dome_servo and reg.dome_servo.is_ready() else [],
        'body_hat_health':   (reg.slave_uart_health or {}).get('body_hat_health', []),
        'motor_hat_health':  (reg.slave_uart_health or {}).get('motor_hat_health'),
        'display_ready':     (reg.slave_uart_health or {}).get('display_ready'),
        'display_port':      (reg.slave_uart_health or {}).get('display_port'),
        'vesc_l_temp':       (reg.vesc_telem.get('L') or {}).get('temp'),
        'vesc_r_temp':       (reg.vesc_telem.get('R') or {}).get('temp'),
        'vesc_l_curr':       (reg.vesc_telem.get('L') or {}).get('current'),
        'vesc_r_curr':       (reg.vesc_telem.get('R') or {}).get('current'),
        'vesc_l_duty':       (reg.vesc_telem.get('L') or {}).get('duty'),
        'vesc_r_duty':       (reg.vesc_telem.get('R') or {}).get('duty'),
        'vesc_l_rpm':        (reg.vesc_telem.get('L') or {}).get('rpm'),
        'vesc_r_rpm':        (reg.vesc_telem.get('R') or {}).get('rpm'),
        'battery_cells':     _battery_cells(),
        'alive_enabled':     bool(reg.behavior_engine and reg.behavior_engine._cfg.getboolean('behavior', 'alive_enabled', fallback=False)),
        'slave_host':        _slave_host(),
        'master_wlan0':      _iface_ip('wlan0'),
        'master_wlan1':      _iface_ip('wlan1'),
        'master_mem':        _mem_info(),
        'master_cpu':        _cpu_pct(),
        'master_disk':       _disk_info(),
        'slave_temp':        (reg.slave_uart_health or {}).get('cpu_temp'),
        'slave_cpu':         (reg.slave_uart_health or {}).get('cpu_pct'),
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


@status_bp.post('/system/rollback')
def system_rollback():
    """Rolls back to the previous git commit + rsync Slave + reboot Slave."""
    if not reg.deploy:
        return jsonify({'error': 'DeployController not available'}), 503
    import threading
    threading.Thread(target=reg.deploy.rollback, daemon=True).start()
    return jsonify({'status': 'ok', 'message': 'Rollback in progress...'})


@status_bp.post('/system/resync_slave')
def system_resync_slave():
    """
    Rsync + service install + restart Slave only.
    Called automatically by the Slave via HTTP when it detects a version mismatch at boot.
    """
    def do_resync():
        subprocess.run(
            ['bash', f'{SCRIPTS_DIR}/resync_slave.sh'],
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


@status_bp.post('/system/reboot_both')
def system_reboot_both():
    """Reboots Slave first (via UART), then Master after a short delay."""
    if reg.uart:
        reg.uart.send('REBOOT', '1')
    def _reboot_master():
        import time as _t
        _t.sleep(1)
        subprocess.run(['sudo', 'reboot'], check=False)
    threading.Thread(target=_reboot_master, daemon=True).start()
    return jsonify({'status': 'rebooting'})


@status_bp.post('/system/shutdown_slave')
def system_shutdown_slave():
    """Sends a shutdown command to the Slave via UART."""
    if reg.uart:
        reg.uart.send('SHUTDOWN', '1')
        return jsonify({'status': 'ok'})
    return jsonify({'error': 'UART not available'}), 503


@status_bp.post('/system/shutdown_both')
def system_shutdown_both():
    """Shuts down Slave first (via UART), then Master after a short delay."""
    if reg.uart:
        reg.uart.send('SHUTDOWN', '1')
    def _shutdown_master():
        import time as _t
        _t.sleep(1)
        subprocess.run(['sudo', 'shutdown', '-h', 'now'], check=False)
    threading.Thread(target=_shutdown_master, daemon=True).start()
    return jsonify({'status': 'shutting down'})


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


# Slew speed used by the Reset E-STOP safe-home sequence.
# The body/dome servo drivers accept speed ∈ [1..10] where 10 is fastest
# (delay = (10-speed)×3ms per 2° step). 3 yields ≈1s for a 90° travel —
# slow enough to avoid pinch hazards with kids around without dragging on.
_SAFE_SLEW_SPEED = 3


@status_bp.post('/system/estop')
def system_estop():
    """Emergency stop — freeze the robot.

    Cuts propulsion + dome motor + aborts any running choreography. Servos
    are left exactly where they are (arms extended, panels open, etc.) so
    nothing moves while the user secures the area. Cleanup is a separate
    operation triggered by /system/estop_reset.
    """
    # Stop propulsion
    if reg.vesc:
        try:
            reg.vesc.stop()
        except Exception:
            pass
    # Stop dome rotation
    if reg.dome:
        try:
            reg.dome.stop()
        except Exception:
            pass
    # Abort any running choreography (this freezes its event dispatch but
    # does NOT command servos — held positions stay held).
    if reg.choreo:
        try:
            reg.choreo.stop()
        except Exception:
            pass
    # Send explicit drive-stop over UART in case VESC driver is unavailable
    if reg.uart:
        try:
            reg.uart.send('M', '0.0,0.0')
            reg.uart.send('D', '0.0')
        except Exception:
            pass
    reg.estop_active = True
    return jsonify({'status': 'estop_sent'})


@status_bp.post('/system/estop_reset')
def system_estop_reset():
    """Clear E-STOP and stow the robot at a safe slew rate.

    Sequence (mirrors the Choreo arm dependency logic but at a slow speed):
      1. Retract each utility arm (parallel) — speed=_SAFE_SLEW_SPEED
      2. Wait the per-arm delay, then close its panel — speed=_SAFE_SLEW_SPEED
      3. Close every remaining body servo (excluding arm-managed ones)
         in parallel — speed=_SAFE_SLEW_SPEED
      4. Close every dome servo in parallel — speed=_SAFE_SLEW_SPEED

    All driver calls are wrapped in try/except so a single failed servo
    cannot abort the rest of the cleanup.
    """
    reg.estop_active = False

    def _safe_home():
        # Lazy import to avoid a circular dependency between the two blueprints.
        from master.api.servo_bp import (
            _read_arms_cfg, _read_panels_cfg, _arm_servo_set,
            _panel_angle, BODY_SERVOS,
        )

        panels_cfg = _read_panels_cfg()
        arms_cfg   = _read_arms_cfg()
        arm_set    = _arm_servo_set()

        # ── Step 1+2: arm-then-panel sequences in parallel ──
        def _close_arm_then_panel(arm: str, panel: str, delay: float) -> None:
            if arm and reg.servo:
                try:
                    reg.servo.close(arm,
                                    _panel_angle(arm, 'close', panels_cfg),
                                    _SAFE_SLEW_SPEED)
                except Exception:
                    log.exception("Safe-home: arm close failed: %s", arm)
            if panel:
                # Hold off until the arm has had time to fully retract before
                # the panel starts moving — same dependency the Choreo player
                # honours during arm sequences.
                _time.sleep(max(0.1, min(5.0, float(delay))))
                if reg.servo:
                    try:
                        reg.servo.close(panel,
                                        _panel_angle(panel, 'close', panels_cfg),
                                        _SAFE_SLEW_SPEED)
                    except Exception:
                        log.exception("Safe-home: arm panel close failed: %s", panel)

        arm_threads = []
        for i in range(arms_cfg['count']):
            arm   = arms_cfg['servos'][i]
            panel = arms_cfg['panels'][i]
            delay = arms_cfg['delays'][i]
            if not arm:
                continue
            t = threading.Thread(
                target=_close_arm_then_panel,
                args=(arm, panel, delay),
                name=f'safehome-arm-{i+1}',
                daemon=True,
            )
            arm_threads.append(t)
            t.start()
        # Wait for all arm sequences before continuing — guarantees panels do
        # not start retracting until the arms they shield are fully home.
        for t in arm_threads:
            t.join(timeout=10.0)

        # ── Step 3: remaining body servos (skip arm-managed ones) in parallel ──
        if reg.servo:
            body_threads = []
            for name in BODY_SERVOS:
                if name in arm_set:
                    continue
                def _close_body(n=name):
                    try:
                        reg.servo.close(n,
                                        _panel_angle(n, 'close', panels_cfg),
                                        _SAFE_SLEW_SPEED)
                    except Exception:
                        log.exception("Safe-home: body close failed: %s", n)
                bt = threading.Thread(target=_close_body, name=f'safehome-body-{name}',
                                      daemon=True)
                body_threads.append(bt)
                bt.start()
            for bt in body_threads:
                bt.join(timeout=5.0)

        # ── Step 4: dome servos in parallel ──
        if reg.dome_servo:
            try:
                from master.drivers.dome_servo_driver import SERVO_MAP as _DOME_MAP
                dome_names = list(_DOME_MAP.keys())
            except Exception:
                dome_names = []
            dome_threads = []
            for name in dome_names:
                def _close_dome(n=name):
                    try:
                        reg.dome_servo.close(n, speed=_SAFE_SLEW_SPEED)
                    except Exception:
                        log.exception("Safe-home: dome close failed: %s", n)
                dt = threading.Thread(target=_close_dome, name=f'safehome-dome-{name}',
                                      daemon=True)
                dome_threads.append(dt)
                dt.start()
            for dt in dome_threads:
                dt.join(timeout=5.0)

    threading.Thread(target=_safe_home, name='safehome', daemon=True).start()
    return jsonify({'status': 'reset'})
