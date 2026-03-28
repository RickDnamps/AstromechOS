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
Motion Watchdog — Safety for disconnected controller.

If no motion command (drive or dome) is received for TIMEOUT seconds
AND the robot is moving → automatic stop via UART.

Protects against:
  - WiFi loss of Android app / browser
  - Web interface crash
  - Network disconnection during an action

Timeout: 800ms — enough to absorb normal HTTP latency,
         short enough to stop the robot quickly.

Start: motion_watchdog.start() in master/main.py after UART init.
Feed:  motion_watchdog.feed_drive(l, r) / feed_dome(s) in motion_bp.py.
"""

import logging
import threading
import time

import master.registry as reg
from master.safe_stop import stop_drive, stop_dome, cancel_ramp

log = logging.getLogger(__name__)

TIMEOUT_S   = 0.8   # seconds without command → stop
CHECK_HZ    = 0.1   # check interval (100ms)
DEADZONE    = 0.05  # threshold to consider "in motion"


class MotionWatchdog:
    """
    Safety watchdog: stops propulsion and dome if the controller
    stops responding.
    """

    def __init__(self):
        self._lock            = threading.Lock()
        self._last_drive_time = 0.0
        self._last_dome_time  = 0.0
        self._drive_active    = False
        self._dome_active     = False
        self._running         = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        self._running = True
        threading.Thread(target=self._loop, daemon=True, name="motion-wdog").start()
        log.info("MotionWatchdog started (timeout=%.1fs)", TIMEOUT_S)

    def stop(self) -> None:
        self._running = False

    # ------------------------------------------------------------------
    # Feed — called on each received motion command
    # ------------------------------------------------------------------

    def feed_drive(self, left: float, right: float) -> None:
        """Signals a drive command received."""
        cancel_ramp()   # cancel any ongoing gradual stop
        with self._lock:
            self._last_drive_time = time.monotonic()
            self._drive_active    = abs(left) > DEADZONE or abs(right) > DEADZONE

    def feed_dome(self, speed: float) -> None:
        """Signals a dome command received."""
        with self._lock:
            self._last_dome_time = time.monotonic()
            self._dome_active    = abs(speed) > DEADZONE

    def clear_drive(self) -> None:
        """Signals an explicit propulsion stop (not a timeout)."""
        with self._lock:
            self._drive_active    = False
            self._last_drive_time = time.monotonic()

    def clear_dome(self) -> None:
        """Signals an explicit dome stop."""
        with self._lock:
            self._dome_active    = False
            self._last_dome_time = time.monotonic()

    # ------------------------------------------------------------------
    # Internal loop
    # ------------------------------------------------------------------

    def _loop(self) -> None:
        while self._running:
            time.sleep(CHECK_HZ)
            now = time.monotonic()
            with self._lock:
                drive_timeout = (self._drive_active and
                                 now - self._last_drive_time > TIMEOUT_S)
                dome_timeout  = (self._dome_active and
                                 now - self._last_dome_time  > TIMEOUT_S)

            if drive_timeout:
                self._stop_drive()
            if dome_timeout:
                self._stop_dome()

    def _stop_drive(self) -> None:
        with self._lock:
            self._drive_active = False
        log.warning("MotionWatchdog: command timeout — gradual propulsion stop")
        stop_drive()   # ramp proportional to current speed

    def _stop_dome(self) -> None:
        with self._lock:
            self._dome_active = False
        log.warning("MotionWatchdog: command timeout — gradual dome stop")
        stop_dome()


# Singleton global
motion_watchdog = MotionWatchdog()
