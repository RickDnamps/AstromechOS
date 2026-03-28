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
Display Driver — RP2040 Touch LCD 1.28 via USB serial.
Sends DISP: commands to the RP2040 on /dev/ttyACM2.
"""

import logging
import serial
import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.base_driver import BaseDriver

log = logging.getLogger(__name__)

DISPLAY_BAUD  = 115200
# Ports to try in order — the RP2040 takes the first available ACM
# If VESCs are not connected, the RP2040 is on ttyACM0
DISPLAY_PORTS = ["/dev/ttyACM0", "/dev/ttyACM1", "/dev/ttyACM2"]


class DisplayDriver(BaseDriver):
    def __init__(self, port: str = "auto", baud: int = DISPLAY_BAUD):
        self._port_config = port   # original config for reconnections
        self._port   = port
        self._baud   = baud
        self._serial: serial.Serial | None = None
        self._ready  = False
        self._last_cmd: str = ""

    def setup(self) -> bool:
        ports = DISPLAY_PORTS if self._port == "auto" else [self._port]
        for port in ports:
            try:
                self._serial = serial.Serial(port, self._baud, timeout=1)
                self._port  = port
                self._ready = True
                time.sleep(0.5)  # allow USB/RP2040 to stabilize before first send
                log.info(f"DisplayDriver opened: {port}")
                return True
            except serial.SerialException:
                continue
        log.error(f"DisplayDriver: no port available among {ports}")
        return False

    def reconnect(self) -> bool:
        """Closes the existing connection and retries all ACM ports.
        Called automatically when the RP2040 is unplugged/replugged."""
        if self._serial:
            try:
                self._serial.close()
            except Exception:
                pass
            self._serial = None
        self._ready = False
        self._port  = self._port_config   # reset to retry all ports
        return self.setup()

    def shutdown(self) -> None:
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._ready = False

    def is_ready(self) -> bool:
        return self._ready and self._serial is not None and self._serial.is_open

    # ------------------------------------------------------------------
    # State commands
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Diagnostic boot sequence
    # ------------------------------------------------------------------

    def boot_start(self) -> bool:
        """Starts the diagnostic sequence — resets all items."""
        return self._send("DISP:BOOT:START")

    def boot_item(self, name: str) -> bool:
        """Item 'name' currently starting (orange)."""
        return self._send(f"DISP:BOOT:ITEM:{name}")

    def boot_ok(self, name: str) -> bool:
        """Item 'name' started successfully (green)."""
        return self._send(f"DISP:BOOT:OK:{name}")

    def boot_fail(self, name: str) -> bool:
        """Item 'name' in error state (red)."""
        return self._send(f"DISP:BOOT:FAIL:{name}")

    def ready(self, version: str = "") -> bool:
        """All OK — shows green OPERATIONAL screen for 3s then READY."""
        if version:
            return self._send(f"DISP:READY:{version}")
        return self._send("DISP:READY")

    def bt_connected(self, name: str = "") -> bool:
        """Bluetooth controller connected."""
        if name:
            return self._send(f"DISP:BT:CONNECTED:{name}")
        return self._send("DISP:BT:CONNECTED")

    def bt_none(self) -> bool:
        """No controller connected (informational, not an error)."""
        return self._send("DISP:BT:NONE")

    # ------------------------------------------------------------------
    # Operational states
    # ------------------------------------------------------------------

    def ok(self, version: str = "") -> bool:
        """Normal operational screen (green border)."""
        if version:
            return self._send(f"DISP:OK:{version}")
        return self._send("DISP:OK")

    def syncing(self, version: str = "") -> bool:
        """Version synchronization in progress — stays on the diagnostic screen."""
        if version:
            return self._send(f"DISP:SYNCING:{version}")
        return self._send("DISP:SYNCING")

    def error(self, code: str) -> bool:
        """
        Error with readable code (red border).
        Codes: MASTER_OFFLINE, VESC_TEMP_HIGH, VESC_FAULT, BATTERY_LOW,
               UART_ERROR, SYNC_FAILED, WATCHDOG, AUDIO_FAIL,
               SERVO_FAIL, VESC_L_FAIL, VESC_R_FAIL, I2C_ERROR
        """
        return self._send(f"DISP:ERROR:{code}")

    def telemetry(self, voltage: float, temp: float) -> bool:
        """Battery gauge + temperature."""
        return self._send(f"DISP:TELEM:{voltage:.1f}V:{temp:.0f}C")

    # ------------------------------------------------------------------
    # WiFi Watchdog network states
    # ------------------------------------------------------------------

    def net_scanning(self, attempt: int) -> bool:
        """WiFi scan — attempting reconnection to Master hotspot (Level 1)."""
        return self._send(f"DISP:NET:SCANNING:{attempt}")

    def net_connecting_ap(self, attempt: int) -> bool:
        """Connecting to Master hotspot."""
        return self._send(f"DISP:NET:AP:{attempt}")

    def net_home_try(self) -> bool:
        """Switching to home WiFi (Level 2)."""
        return self._send("DISP:NET:HOME_TRY")

    def net_home_ok(self, ip: str) -> bool:
        """Connected to home WiFi — displays the obtained IP."""
        return self._send(f"DISP:NET:HOME:{ip}")

    def net_ok(self) -> bool:
        """Master connection restored."""
        return self._send("DISP:NET:OK")

    def bus_health(self, pct: float) -> bool:
        """UART bus health — updated every 10s."""
        return self._send(f"DISP:BUS:{pct:.1f}")

    def system_locked(self) -> bool:
        """Red padlock — VESC watchdog triggered."""
        return self._send("DISP:LOCKED")

    def send_raw(self, cmd: str) -> bool:
        """Raw command (e.g. DISP: forwarded from Master UART)."""
        return self._send(cmd)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _send(self, cmd: str) -> bool:
        if not self.is_ready():
            log.debug(f"DisplayDriver not ready, command ignored: {cmd}")
            return False
        try:
            self._serial.write(f"{cmd}\n".encode('utf-8'))
            log.debug(f"Display TX: {cmd}")
            self._last_cmd = cmd
            return True
        except serial.SerialException as e:
            log.error(f"Display send error: {e}")
            self._ready = False
            return False
