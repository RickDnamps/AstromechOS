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
Master Dome Motor Driver — Phase 2.
Controls the dome DC motor via UART:

  D:SPEED          → dome DC motor (sent to Slave → Syren10/Sabertooth)
  TEECES:cmd        → Teeces32 LEDs (local Master via TeecesController)

The Slave receives D: and drives the Syren10 on /dev/ttyUSB1 (or other port).

Phase 2 activation:
  1. Uncomment the import in master/main.py
  2. Call dome.setup() in main()
  3. Configure dome_port in main.cfg if needed
"""

import logging
import threading
import time
import random

log = logging.getLogger(__name__)

DEADZONE = 0.05
# Max speed for random rotation (fraction of 1.0)
RANDOM_SPEED_MAX = 0.4
# Delay between random rotations (seconds)
RANDOM_INTERVAL_MIN = 3.0
RANDOM_INTERVAL_MAX = 8.0


class DomeMotorDriver:
    """
    Controls the dome DC motor.
    Manual mode: dome.turn(speed)
    Random mode: dome.set_random(True) → rotates at intervals
    """

    def __init__(self, uart):
        self._uart = uart
        self._ready = False
        self._speed = 0.0
        self._random_mode = False
        self._random_thread: threading.Thread | None = None

    def setup(self) -> bool:
        self._ready = True
        log.info("DomeMotorDriver ready")
        return True

    def shutdown(self) -> None:
        self.set_random(False)
        self.stop()
        self._ready = False

    def is_ready(self) -> bool:
        return self._ready

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def turn(self, speed: float) -> bool:
        """
        Dome rotation.
        speed : float [-1.0 … +1.0]
          -1.0 = full left, +1.0 = full right, 0.0 = stop
        """
        if abs(speed) < DEADZONE:
            speed = 0.0
        self._speed = max(-1.0, min(1.0, speed))
        ok = self._uart.send('D', f"{self._speed:.3f}")
        log.debug(f"Dome turn: {self._speed:.3f}")
        return ok

    def stop(self) -> bool:
        """Stop dome rotation."""
        self._speed = 0.0
        return self._uart.send('D', '0.000')

    def center(self) -> bool:
        """Return to zero position (center)."""
        return self.stop()

    def set_random(self, enabled: bool) -> None:
        """Enable/disable random rotation mode."""
        self._random_mode = enabled
        if enabled and (self._random_thread is None or not self._random_thread.is_alive()):
            self._random_thread = threading.Thread(
                target=self._random_loop, name="dome-random", daemon=True
            )
            self._random_thread.start()
            log.info("Dome random mode enabled")
        elif not enabled:
            log.info("Dome random mode disabled")
            self.stop()

    @property
    def state(self) -> dict:
        return {'speed': self._speed, 'random': self._random_mode}

    # ------------------------------------------------------------------
    # Random thread (inspired by DomeThread r2_control)
    # ------------------------------------------------------------------

    def _random_loop(self) -> None:
        while self._random_mode:
            # Pause between movements
            pause = random.uniform(RANDOM_INTERVAL_MIN, RANDOM_INTERVAL_MAX)
            time.sleep(pause)
            if not self._random_mode:
                break

            # Choose direction and duration
            speed = random.uniform(-RANDOM_SPEED_MAX, RANDOM_SPEED_MAX)
            duration = random.uniform(0.5, 2.0)

            self.turn(speed)
            time.sleep(duration)
            self.stop()
