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
AstromechOS Master — Entry point.
Runs on Raspberry Pi 4B (dome).

Boot sequence:
1. Load config
2. Init logging
3. git pull if wlan1 is available
4. Start UARTController + TeecesController + DeployController
5. Phase 2: VescDriver + DomeMotorDriver + BodyServoDriver (uncomment to enable)
6. Flask API on port 5000, ChoreoPlayer, BehaviorEngine
"""

import logging
import configparser
import signal
import sys
import os
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from master.uart_controller import UARTController
from master import vesc_safety
from master.lights import load_driver
from master.deploy_controller import DeployController
from master.config.config_loader import load, is_auto_pull_enabled
import master.registry as reg

# ---- Phase 2 — Uncomment to enable ----
# from master.drivers.vesc_driver        import VescDriver
# from master.drivers.dome_motor_driver  import DomeMotorDriver
from master.drivers.body_servo_driver  import BodyServoDriver
from master.drivers.dome_servo_driver  import DomeServoDriver

# ---- Phase 4 — Uncomment to enable ----
from master.flask_app import create_app
from master.motion_watchdog import motion_watchdog
from master.app_watchdog import app_watchdog

from shared.paths import VERSION_FILE, DEBUG_DIR


def setup_logging(level_str: str) -> None:
    from logging.handlers import RotatingFileHandler
    level = getattr(logging, level_str.upper(), logging.INFO)
    fmt = logging.Formatter(
        '%(asctime)s [%(name)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    root = logging.getLogger()
    root.setLevel(level)
    # Console (journald)
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    root.addHandler(ch)
    # Persistent rotating file — survives reboots, gitignored (debug/)
    log_dir = DEBUG_DIR
    os.makedirs(log_dir, exist_ok=True)
    fh = RotatingFileHandler(
        os.path.join(log_dir, 'master.log'),
        maxBytes=5 * 1024 * 1024,   # 5 MB per file
        backupCount=3,               # master.log + master.log.1/2/3
        encoding='utf-8'
    )
    fh.setFormatter(fmt)
    root.addHandler(fh)


def _start_network_monitor() -> None:
    """Daemon thread — monitors wlan0/wlan1 every 30s and logs changes."""
    import subprocess
    log_net = logging.getLogger('network')

    def _iface_state(iface: str) -> tuple[bool, str]:
        try:
            r = subprocess.run(['ip', 'addr', 'show', iface],
                               capture_output=True, text=True, timeout=3)
            for line in r.stdout.splitlines():
                line = line.strip()
                if line.startswith('inet '):
                    return True, line.split()[1]
            return False, ''
        except Exception:
            return False, ''

    prev: dict[str, bool] = {}

    def _log_initial() -> None:
        for iface in ('wlan0', 'wlan1'):
            up, ip = _iface_state(iface)
            prev[iface] = up
            if up:
                log_net.info("%s connected at boot — IP: %s", iface, ip)
            else:
                log_net.warning("%s not available at boot", iface)

    def _monitor() -> None:
        while True:
            time.sleep(30)
            for iface in ('wlan0', 'wlan1'):
                up, ip = _iface_state(iface)
                if prev.get(iface) != up:
                    if up:
                        log_net.info("%s reconnected — IP: %s", iface, ip)
                    else:
                        log_net.warning("%s disconnected!", iface)
                    prev[iface] = up

    _log_initial()
    threading.Thread(target=_monitor, name='network-monitor', daemon=True).start()


def try_git_pull(cfg: configparser.ConfigParser) -> bool:
    """Attempt git pull at boot if wlan1 is connected and auto_pull is enabled."""
    import subprocess
    if not is_auto_pull_enabled(cfg):
        logging.info("auto_pull_on_boot disabled — skipping git pull")
        return False
    iface = cfg.get('network', 'internet_interface')
    repo = cfg.get('master', 'repo_path')

    try:
        result = subprocess.run(
            ["ip", "addr", "show", iface],
            capture_output=True, text=True, timeout=5
        )
        if "inet " not in result.stdout:
            logging.info(f"{iface} not available — skipping git pull")
            return False
    except Exception:
        return False

    try:
        result = subprocess.run(
            ["git", "pull"],
            cwd=repo,
            timeout=30,
            capture_output=True, text=True
        )
        if result.returncode == 0:
            rev = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=repo, capture_output=True, text=True
            )
            if rev.returncode == 0:
                try:
                    with open(VERSION_FILE, 'w') as f:
                        f.write(rev.stdout.strip())
                except OSError as e:
                    logging.warning(f"Failed to write VERSION file: {e}")
            logging.info("git pull succeeded at startup")
            return True
        else:
            logging.warning(f"git pull failed: {result.stderr.strip()}")
            return False
    except subprocess.TimeoutExpired:
        logging.warning("git pull timed out — starting without update")
        return False
    except Exception as e:
        logging.error(f"git pull error: {e}")
        return False


def main() -> None:
    cfg = load()
    setup_logging(cfg.get('master', 'log_level', fallback='INFO'))
    log = logging.getLogger(__name__)
    log.info("=== AstromechOS Master starting ===")
    _start_network_monitor()

    # Boot: attempt git pull
    try_git_pull(cfg)

    # Init Phase 1 components
    uart   = UARTController(cfg)
    teeces = load_driver(cfg)
    deploy = DeployController(cfg, uart, teeces)

    # Shared registry (accessible by Flask blueprints)
    reg.uart   = uart
    reg.teeces = teeces
    reg.deploy = deploy
    reg.vesc_power_scale = cfg.getfloat('vesc', 'power_scale', fallback=1.0)
    reg.vesc_invert_L    = cfg.getboolean('vesc', 'invert_l',    fallback=False)
    reg.vesc_invert_R    = cfg.getboolean('vesc', 'invert_r',    fallback=False)
    reg.vesc_bench_mode  = cfg.getboolean('vesc', 'bench_mode',  fallback=False)

    # ------------------------------------------------------------------
    # Phase 2 — Propulsion / dome / servo drivers
    # ------------------------------------------------------------------
    # vesc = VescDriver(uart)
    # dome = DomeMotorDriver(uart)
    # if vesc.setup(): reg.vesc = vesc
    # if dome.setup(): reg.dome = dome

    servo      = BodyServoDriver(uart)
    dome_servo = DomeServoDriver()
    if servo.setup():      reg.servo      = servo
    if dome_servo.setup(): reg.dome_servo = dome_servo

    from master.choreo_player import ChoreoPlayer
    from master.behavior_engine import BehaviorEngine
    reg.choreo = ChoreoPlayer(
        cfg=cfg,
        audio=uart,
        teeces=teeces,
        dome_motor=reg.dome,
        dome_servo=reg.dome_servo,
        body_servo=reg.servo,
        vesc=reg.vesc,
        # Use staleness-gated pair so a disconnected VESC's last frame
        # (often undervoltage if the battery was dying when the user
        # unplugged) doesn't trigger ChoreoPlayer's safety abort. None
        # for a side means "no recent telem" → ChoreoPlayer skips that
        # side instead of reading stale v_in. Reported 2026-05-15.
        telem_getter=vesc_safety.fresh_telem_pair,
    )
    reg.choreo.setup()

    behavior_engine = BehaviorEngine(cfg)
    reg.behavior_engine = behavior_engine

    from master.drivers.bt_controller_driver import BTControllerDriver

    bt_ctrl = BTControllerDriver()
    reg.bt_ctrl = bt_ctrl
    bt_ctrl.start()

    # Incoming UART callbacks
    def on_heartbeat_ack(value: str) -> None:
        log.debug(f"Heartbeat ACK Slave: {value}")

    def _parse_vesc_telem(value: str) -> dict | None:
        """Parse 'v_in:temp:curr:rpm:duty:fault' → dict."""
        try:
            v_in, temp, curr, rpm, duty, fault = value.split(':')
            return {
                'v_in':    float(v_in),
                'temp':    float(temp),
                'current': float(curr),
                'rpm':     int(rpm),
                'duty':    float(duty),
                'fault':   int(fault),
                'ts':      time.time(),
            }
        except Exception:
            return None

    def on_vesc_telem_left(value: str) -> None:
        d = _parse_vesc_telem(value)
        if d:
            reg.vesc_telem['L'] = d

    def on_vesc_telem_right(value: str) -> None:
        d = _parse_vesc_telem(value)
        if d:
            reg.vesc_telem['R'] = d

    def on_can_found(value: str) -> None:
        """CAN bus scan result received from Slave."""
        if value.strip() == 'ERR':
            reg.vesc_can_scan_result = None
        elif not value.strip():
            reg.vesc_can_scan_result = []
        else:
            try:
                reg.vesc_can_scan_result = [int(x) for x in value.split(',') if x.strip()]
            except ValueError:
                reg.vesc_can_scan_result = []
                log.warning(f"CANFOUND: invalid format {value!r}")
        reg.vesc_can_scan_event.set()
        log.info(f"CAN scan result: {reg.vesc_can_scan_result}")

    def on_version(value: str) -> None:
        if value == '?':
            try:
                with open(VERSION_FILE) as f:
                    version = f.read().strip()
            except Exception:
                version = "unknown"
            uart.send('V', version)
            log.debug(f"Version requested by Slave — reply: {version}")
        else:
            log.info(f"Slave version received: {value}")

    def on_slave_boot(value: str) -> None:
        """Slave reconnected/booted — re-push VESC config so it doesn't run on defaults."""
        log.info(f"Slave boot banner received ({value!r}) — resyncing VESC config")
        def _resync() -> None:
            time.sleep(0.5)  # give Slave drivers time to register their UART callbacks
            try:
                uart.send('VCFG', f'scale:{reg.vesc_power_scale:.2f}')
                uart.send('VINV', f"L:{1 if reg.vesc_invert_L else 0}")
                uart.send('VINV', f"R:{1 if reg.vesc_invert_R else 0}")
                log.info(
                    "VESC config resynced — scale=%.2f invert_L=%s invert_R=%s",
                    reg.vesc_power_scale, reg.vesc_invert_L, reg.vesc_invert_R
                )
            except Exception as exc:
                log.error("VESC resync failed: %s", exc)
        threading.Thread(target=_resync, name='vesc-resync', daemon=True).start()

    uart.register_callback('H',        on_heartbeat_ack)
    uart.register_callback('TL',       on_vesc_telem_left)
    uart.register_callback('TR',       on_vesc_telem_right)
    uart.register_callback('V',        on_version)
    uart.register_callback('CANFOUND', on_can_found)
    uart.register_callback('BOOT',     on_slave_boot)

    # Start hardware
    if not uart.setup():
        log.error("UART init failed — exiting")
        sys.exit(1)

    if not teeces.setup():
        log.warning("Teeces32 init failed — degraded mode (LEDs unavailable)")

    uart.start()
    teeces.random_mode()
    deploy.start()

    # ------------------------------------------------------------------
    # Phase 4 — Flask server (REST API + Web UI)
    # ------------------------------------------------------------------
    app        = create_app()
    flask_port = cfg.getint('master', 'flask_port', fallback=5000)
    flask_thread = threading.Thread(
        target=lambda: app.run(host='0.0.0.0', port=flask_port,
                               use_reloader=False, threaded=True),
        name='flask', daemon=True
    )
    flask_thread.start()
    log.info(f"Flask started on port {flask_port}")

    behavior_engine.start()
    log.info("BehaviorEngine started")

    # Safety watchdogs — start after Flask
    motion_watchdog.start()   # stop motors if no drive command within 800ms
    app_watchdog.start()      # stop motors if app heartbeat absent for 600ms

    # ------------------------------------------------------------------
    # Slave Health Poll — reads http://<slave_host>:5001/uart_health
    # every 5s via urllib (stdlib, no extra dependency).
    #
    # B-221 (remaining tabs audit 2026-05-15): slave host read from
    # local.cfg [slave] host. Was hardcoded `r2-slave.local`, which
    # silently broke any installation that switched to an IP (mDNS
    # `.local` is capricious on some networks — see project memory
    # feedback_no_hardcoded_install_values).
    # ------------------------------------------------------------------
    def _slave_health_poll() -> None:
        import urllib.request
        import json as _json
        slave_host = cfg.get('slave', 'host', fallback='r2-slave.local')
        url = f'http://{slave_host}:5001/uart_health'
        log.info("Slave health poll: %s", url)
        while True:
            try:
                with urllib.request.urlopen(url, timeout=1) as resp:
                    reg.slave_uart_health = _json.loads(resp.read())
            except Exception:
                reg.slave_uart_health = None
            time.sleep(5)

    threading.Thread(
        target=_slave_health_poll, name='slave-health-poll', daemon=True
    ).start()

    log.info("Master operational")

    # Clean shutdown handler
    def shutdown(sig, frame):
        log.info("Shutdown signal received")
        deploy.stop()
        uart.stop()
        teeces.shutdown()
        # Phase 2: if reg.vesc:  reg.vesc.shutdown()
        # Phase 2: if reg.dome:  reg.dome.shutdown()
        if reg.servo:      reg.servo.shutdown()
        if reg.dome_servo: reg.dome_servo.shutdown()
        if reg.bt_ctrl: reg.bt_ctrl.stop()
        if reg.behavior_engine: reg.behavior_engine.stop()
        log.info("Master shut down cleanly")
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    # Keep process alive
    signal.pause()


if __name__ == "__main__":
    main()
