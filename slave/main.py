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
R2-D2 Slave — Entry point.
Runs on Raspberry Pi 4B 2GB (body).

Boot sequence:
1. Init display RP2040 — starts diagnostic sequence (BOOT:START)
2. Init UART listener  → DISP:BOOT:OK:UART  or FAIL
3. Init Watchdog (priority — safety)
4. Init Audio          → DISP:BOOT:OK:AUDIO or FAIL
5. Phase 2: Init VESC L/R, Dome, Servos → DISP:BOOT:OK/FAIL for each
6. Version check with Master
7. If all OK → DISP:READY (green screen 3s then READY)
"""

import configparser
import logging
import signal
import subprocess
import sys
import os
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from slave.uart_listener import UARTListener
from slave.uart_health_server import start_health_server
from slave.wifi_watchdog import WiFiWatchdog
from slave.watchdog import WatchdogController
from slave.version_check import VersionChecker
from slave.drivers.display_driver import DisplayDriver
from slave.drivers.audio_driver   import AudioDriver

# ---- Phase 2 — Uncomment to enable ----
# from slave.drivers.vesc_driver        import VescDriver   # enables M: VCFG: VINV: CANSCAN: callbacks
from slave.drivers.body_servo_driver  import BodyServoDriver
# from slave.drivers.dome_motor_driver  import DomeMotorDriver  # to create Phase 2

_SLAVE_CFG = '/home/artoo/r2d2/slave/config/slave.cfg'

def _read_audio_channels() -> int:
    """Reads audio_channels from slave.cfg. Defaults to 6 if absent."""
    cfg = configparser.ConfigParser()
    try:
        cfg.read(_SLAVE_CFG)
    except Exception:
        pass
    return cfg.getint('audio', 'audio_channels', fallback=6)

UART_PORT = "/dev/ttyAMA0"
UART_BAUD = 115200
LOG_LEVEL = "INFO"
VERSION_FILE = "/home/artoo/r2d2/VERSION"


def setup_logging(level_str: str) -> None:
    level = getattr(logging, level_str.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def emergency_stop_vesc() -> None:
    """Emergency VESC cutoff — called by the watchdog."""
    log = logging.getLogger("watchdog.stop")
    log.error("VESC CUTOFF — watchdog timeout")
    # Phase 2: vesc_g.stop() + vesc_d.stop()


def resume_vesc() -> None:
    """VESC re-enable after heartbeat resumes."""
    log = logging.getLogger("watchdog.resume")
    log.info("VESC re-enabled — heartbeat resumed")
    # Phase 2: vesc_g.resume() + vesc_d.resume()


def handle_reboot(value: str) -> None:
    """REBOOT command received from Master — run in a thread to avoid blocking UART."""
    logging.getLogger(__name__).info("REBOOT command received — rebooting in 3s")
    def _do_reboot():
        time.sleep(3)
        subprocess.run(['sudo', 'reboot'], check=False)
    threading.Thread(target=_do_reboot, daemon=True).start()


def main() -> None:
    setup_logging(LOG_LEVEL)
    log = logging.getLogger(__name__)
    log.info("=== R2-D2 Slave starting ===")

    # ------------------------------------------------------------------
    # RP2040 diagnostic screen — starts the boot sequence
    # ------------------------------------------------------------------
    display = DisplayDriver()
    if not display.setup():
        log.warning("DisplayDriver unavailable — degraded display mode")

    display.boot_start()   # RP2040: reset all items → orange

    # Redefine with closures on display
    def emergency_stop_vesc() -> None:
        log.error("VESC CUTOFF — watchdog timeout")
        display.system_locked()
        # Phase 2: vesc_g.stop() + vesc_d.stop()

    def resume_vesc() -> None:
        log.info("VESC re-enabled — heartbeat resumed")
        try:
            with open(VERSION_FILE) as f:
                v = f.read().strip()
        except Exception:
            v = ""
        display.ok(v)   # system already operational — go directly to STATE_OK
        # Phase 2: vesc_g.resume() + vesc_d.resume()

    # ------------------------------------------------------------------
    # UART Listener — connection to Master via slipring
    # ------------------------------------------------------------------
    display.boot_item('UART')
    uart = UARTListener(UART_PORT, UART_BAUD)
    if not uart.setup():
        log.error("UART init failed — shutting down")
        display.boot_fail('UART')
        display.error("UART_ERROR")
        sys.exit(1)
    display.boot_ok('UART')

    # ------------------------------------------------------------------
    # Watchdog — CRITICAL, start immediately after UART
    # ------------------------------------------------------------------
    watchdog = WatchdogController()
    watchdog.register_stop_callback(emergency_stop_vesc)
    watchdog.register_resume_callback(resume_vesc)
    watchdog.start()

    uart.register_callback('H',      lambda v: watchdog.feed())
    uart.register_callback('REBOOT', handle_reboot)
    uart.register_callback('DISP',   lambda v: display.send_raw(f"DISP:{v}"))

    # ------------------------------------------------------------------
    # Audio — native 3.5mm jack Pi 4B
    # ------------------------------------------------------------------
    display.boot_item('AUDIO')
    _audio_channels = _read_audio_channels()
    audio = AudioDriver(channels=_audio_channels)
    if audio.setup():
        for _i in range(_audio_channels):
            _msg_type = 'S' if _i == 0 else f'S{_i + 1}'
            uart.register_callback(_msg_type, audio.make_channel_handler(_i))
        uart.register_callback('VOL', audio.handle_volume)
        log.info("Audio: %d channels registered (S: … S%d:)", _audio_channels, _audio_channels)
        display.boot_ok('AUDIO')
    else:
        log.warning("AudioDriver unavailable — audio disabled")
        display.boot_fail('AUDIO')

    # ------------------------------------------------------------------
    # Phase 2 — VESC + Dome motor (not connected — mark as disabled)
    # Uncomment entire block when VESCs are connected via USB:
    # ------------------------------------------------------------------
    # vesc = VescDriver()
    # if vesc.setup(uart=uart):
    #     uart.register_callback('M',       vesc.handle_uart)
    #     uart.register_callback('VCFG',    vesc.handle_config_uart)
    #     uart.register_callback('VINV',    vesc.handle_invert_uart)
    #     uart.register_callback('CANSCAN', vesc.handle_can_scan_uart)
    #     display.boot_ok('VESC_G')
    #     display.boot_ok('VESC_D')
    # else:
    #     display.boot_fail('VESC_G')
    #     display.boot_fail('VESC_D')
    display.boot_fail('VESC_G')   # not connected Phase 1
    display.boot_fail('VESC_D')   # not connected Phase 1
    display.boot_fail('DOME')     # not connected Phase 1
    display.boot_fail('BT_CTRL')  # optional Phase 4

    # ------------------------------------------------------------------
    # Phase 2 — Body servos (PCA9685 I2C 0x41)
    # ------------------------------------------------------------------
    display.boot_item('SERVOS')
    servo = BodyServoDriver()
    if servo.setup():
        uart.register_callback('SRV', servo.handle_uart)
        display.boot_ok('SERVOS')
    else:
        log.warning("BodyServoDriver unavailable")
        display.boot_fail('SERVOS')

    # ------------------------------------------------------------------
    # Health Monitor — HTTP port 5001, exposes UART stats to Master
    # ------------------------------------------------------------------
    start_health_server(uart)

    # ------------------------------------------------------------------
    # Start UART listener (thread)
    # ------------------------------------------------------------------
    uart.start()

    # ------------------------------------------------------------------
    # WiFi Watchdog — automatic wlan0 reconnection
    # ------------------------------------------------------------------
    wifi_watchdog = WiFiWatchdog(display)
    wifi_watchdog.start()

    # ------------------------------------------------------------------
    # Bus Health push — sends UART health % + OK state to RP2040 every 10s
    # Re-sends DISP:OK periodically so the RP2040 can re-sync
    # even if it missed the initial DISP:READY (USB reconnect, late start).
    # ------------------------------------------------------------------
    _display_version     = ['']   # list to allow modification inside the closure
    _display_operational = [False]

    def _bus_health_push():
        while True:
            time.sleep(10)
            # Automatic reconnection if RP2040 was unplugged/replugged
            if not display.is_ready():
                log.info("RP2040 disconnected — attempting reconnection")
                if display.reconnect():
                    log.info("RP2040 reconnected")
            stats = uart.get_health_stats()
            display.bus_health(stats['health_pct'])
            if _display_operational[0]:
                display.ok(_display_version[0])

    threading.Thread(
        target=_bus_health_push,
        name='bus-health-push',
        daemon=True,
    ).start()

    # ------------------------------------------------------------------
    # Version check with Master (displays syncing on RP2040)
    # ------------------------------------------------------------------
    checker = VersionChecker(uart, display)
    degraded = not checker.run()
    if degraded:
        log.warning("Degraded mode — application started with local version")
        # In degraded mode, read the local version for periodic refreshes
        try:
            with open(VERSION_FILE) as f:
                _display_version[0] = f.read().strip()
        except Exception:
            pass
        _display_operational[0] = True
        display.ok(_display_version[0])   # show OK even in degraded mode
    else:
        log.info("Version validated — normal startup")
        try:
            with open(VERSION_FILE) as f:
                _display_version[0] = f.read().strip()
        except Exception:
            pass
        _display_operational[0] = True

    log.info("Slave operational")

    # ------------------------------------------------------------------
    # Clean shutdown handling
    # ------------------------------------------------------------------
    def shutdown(sig, frame):
        log.info("Shutdown signal received")
        wifi_watchdog.stop()
        watchdog.stop()
        uart.stop()
        audio.shutdown()
        # Phase 2:
        # if vesc_g.is_ready():  vesc_g.shutdown()
        # if vesc_d.is_ready():  vesc_d.shutdown()
        # if dome.is_ready():    dome.shutdown()
        if servo.is_ready(): servo.shutdown()
        display.shutdown()
        log.info("Slave stopped cleanly")
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    signal.pause()


if __name__ == "__main__":
    main()
