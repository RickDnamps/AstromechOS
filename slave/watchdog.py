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
Slave Watchdog — SAFETY CRITICAL.
Cuts the VESCs if no Master heartbeat is received within 500ms.
Must never be blocked.
"""

import logging
import threading
import time

log = logging.getLogger(__name__)

WATCHDOG_TIMEOUT_S = 0.500   # 500ms
CHECK_INTERVAL_S   = 0.050   # check every 50ms


class WatchdogController:
    def __init__(self, timeout_s: float = WATCHDOG_TIMEOUT_S):
        self._timeout = timeout_s
        self._last_heartbeat = time.monotonic()
        self._running = False
        self._triggered = False
        self._stop_callbacks: list = []
        self._resume_callbacks: list = []
        self._lock = threading.Lock()

    def register_stop_callback(self, cb) -> None:
        """Callback called when the watchdog triggers (cuts VESC)."""
        self._stop_callbacks.append(cb)

    def register_resume_callback(self, cb) -> None:
        """Callback called when heartbeat resumes after a cutoff."""
        self._resume_callbacks.append(cb)

    def feed(self) -> None:
        """Called on each received heartbeat. Thread-safe."""
        with self._lock:
            was_triggered = self._triggered
            self._last_heartbeat = time.monotonic()
            self._triggered = False
        if was_triggered:
            log.info("Watchdog: heartbeat resumed — re-enabling VESC")
            for cb in self._resume_callbacks:
                try:
                    cb()
                except Exception as e:
                    log.error(f"Error in resume_callback: {e}")

    def start(self) -> None:
        self._running = True
        threading.Thread(target=self._watch_loop, name="watchdog", daemon=True).start()
        log.info(f"Watchdog started (timeout={self._timeout*1000:.0f}ms)")

    def stop(self) -> None:
        self._running = False

    def _watch_loop(self) -> None:
        while self._running:
            time.sleep(CHECK_INTERVAL_S)
            with self._lock:
                elapsed = time.monotonic() - self._last_heartbeat
                should_trigger = elapsed > self._timeout and not self._triggered
                if should_trigger:
                    self._triggered = True

            if should_trigger:
                log.error(
                    f"WATCHDOG TRIGGERED: no heartbeat for {elapsed*1000:.0f}ms "
                    f"(threshold {self._timeout*1000:.0f}ms) — VESC CUTOFF"
                )
                for cb in self._stop_callbacks:
                    try:
                        cb()
                    except Exception as e:
                        log.error(f"Error in watchdog stop_callback: {e}")
