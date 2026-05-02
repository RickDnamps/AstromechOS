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
Master VESC Driver — Phase 2.
Sends propulsion commands to the Slave via UART (M: message).
The Slave executes the commands on the physical VESCs.

UART format: M:LEFT,RIGHT
  LEFT, RIGHT : float [-1.0 … +1.0]
  -1.0 = full reverse, +1.0 = full forward

Phase 2 activation:
  1. Uncomment the import in master/main.py
  2. Call vesc.setup() in main()
  3. Wire up gamepad callbacks
"""

import logging
import time

log = logging.getLogger(__name__)

# Software speed limit (0.0 to 1.0)
SPEED_LIMIT = 1.0
# Joystick deadzone threshold
DEADZONE = 0.05


class VescDriver:
    """
    Master propulsion abstraction layer.
    Converts joystick inputs into UART M: commands.
    """

    def __init__(self, uart):
        """
        Parameters
        ----------
        uart : UARTController
            Active instance of the Master UART controller.
        """
        self._uart = uart
        self._ready = False
        self._left = 0.0
        self._right = 0.0
        self._speed_limit = SPEED_LIMIT

    def setup(self) -> bool:
        self._ready = True
        log.info(f"VescDriver ready (speed_limit={self._speed_limit:.2f})")
        return True

    def shutdown(self) -> None:
        self.stop()
        self._ready = False

    def is_ready(self) -> bool:
        return self._ready

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def drive(self, left: float, right: float) -> bool:
        """
        Differential drive command.

        Parameters
        ----------
        left  : float [-1.0 … +1.0]
        right : float [-1.0 … +1.0]
        """
        left  = self._clamp(left)
        right = self._clamp(right)

        # Deadzone
        if abs(left)  < DEADZONE: left  = 0.0
        if abs(right) < DEADZONE: right = 0.0

        self._left  = left
        self._right = right

        value = f"{left:.3f},{right:.3f}"
        ok = self._uart.send('M', value)
        if ok:
            log.debug(f"VESC drive: L={left:.3f} R={right:.3f}")
        return ok

    def stop(self) -> bool:
        """Emergency stop propulsion."""
        self._left = 0.0
        self._right = 0.0
        return self._uart.send('M', '0.000,0.000')

    def arcade_drive(self, throttle: float, steering: float) -> bool:
        """
        Arcade → differential conversion.
        throttle : [-1.0 … +1.0] forward/backward
        steering : [-1.0 … +1.0] left/right
        """
        left  = throttle + steering
        right = throttle - steering
        # Normalize if outside [-1, 1]
        max_val = max(abs(left), abs(right), 1.0)
        return self.drive(left / max_val, right / max_val)

    def set_speed_limit(self, limit: float) -> None:
        """Dynamic speed limit (0.0 to 1.0)."""
        self._speed_limit = max(0.0, min(1.0, limit))
        log.info(f"Speed limit: {self._speed_limit:.0%}")

    @property
    def state(self) -> dict:
        return {'left': self._left, 'right': self._right, 'limit': self._speed_limit}

    # ------------------------------------------------------------------
    def _clamp(self, v: float) -> float:
        return max(-self._speed_limit, min(self._speed_limit, v))
