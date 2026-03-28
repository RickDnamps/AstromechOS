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
App Watchdog — Application heartbeat App → Master.

The application (Android / web browser) sends POST /heartbeat every 200ms.
If no heartbeat is received for TIMEOUT seconds after a connection has been
established → full emergency stop (propulsion + dome).

Same principle as the UART Master→Slave watchdog, but for the application layer.

Protects against:
  - Android app crash
  - Browser tab closed during an action
  - WiFi loss of the control device
  - Phone screen turned off (WebView paused)

Start: app_watchdog.start() in master/main.py
Feed:  app_watchdog.feed() in status_bp.py POST /heartbeat
"""

import logging
import threading
import time

import master.registry as reg
from master.safe_stop import stop_drive, stop_dome

log = logging.getLogger(__name__)

TIMEOUT_S   = 0.6   # 600ms — 3 missed HBs at 200ms = disconnection
CHECK_HZ    = 0.1   # check every 100ms


class AppWatchdog:
    """
    Monitors the control application heartbeat.
    If the heartbeat stops after being established → emergency stop.
    """

    def __init__(self):
        self._lock          = threading.Lock()
        self._last_hb_time  = 0.0
        self._connected     = False   # True once the first HB is received
        self._triggered     = False   # True after a timeout — reset on next HB
        self._running       = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        self._running = True
        threading.Thread(target=self._loop, daemon=True, name="app-wdog").start()
        log.info("AppWatchdog started (timeout=%.1fs)", TIMEOUT_S)

    def stop(self) -> None:
        self._running = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def feed(self) -> None:
        """Called on each heartbeat received from the application."""
        with self._lock:
            self._last_hb_time = time.monotonic()
            if self._triggered:
                log.info("AppWatchdog: connection restored — watchdog re-armed")
                self._triggered = False
            self._connected = True

    @property
    def is_connected(self) -> bool:
        """True si une app envoie activement des heartbeats."""
        with self._lock:
            return self._connected and not self._triggered

    @property
    def last_hb_age_ms(self) -> float:
        """Age of the last heartbeat in milliseconds."""
        with self._lock:
            if not self._connected:
                return -1.0
            return (time.monotonic() - self._last_hb_time) * 1000.0

    # ------------------------------------------------------------------
    # Internal loop
    # ------------------------------------------------------------------

    def _loop(self) -> None:
        while self._running:
            time.sleep(CHECK_HZ)
            with self._lock:
                if (not self._connected or
                        self._triggered or
                        time.monotonic() - self._last_hb_time <= TIMEOUT_S):
                    continue
                self._triggered = True
                self._connected = False

            # Outside the lock to avoid deadlock on drivers
            self._emergency_stop()

    def _emergency_stop(self) -> None:
        log.warning(
            "AppWatchdog: app heartbeat lost (>%.0fms) — gradual stop",
            TIMEOUT_S * 1000
        )
        stop_drive()   # proportional ramp — no abrupt braking
        stop_dome()


# Singleton global
app_watchdog = AppWatchdog()
