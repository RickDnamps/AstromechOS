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
Master Body Servo Driver — Phase 2 (MG90S 180°).
Sends body servo commands to the Slave via UART (SRV: message).
The Slave executes on the PCA9685 I2C.

UART format: SRV:NAME,ANGLE_DEG
  NAME      : servo name (e.g. body_panel_1)
  ANGLE_DEG : float — target angle in degrees (10–170°)

The Slave applies: pulse_us = 500 + (angle_deg / 180.0) * 2000
MG90S servo holds position — no stop timer.
"""

import configparser
import logging
import os

log = logging.getLogger(__name__)

DEFAULT_OPEN_DEG  = 110
DEFAULT_CLOSE_DEG =  20

_MAIN_CFG  = '/home/artoo/r2d2/master/config/main.cfg'
_LOCAL_CFG = '/home/artoo/r2d2/master/config/local.cfg'


def _calibrated_angle(name: str, action: str) -> float:
    """Reads the calibrated angle from local.cfg [servo_panels]. Falls back to DEFAULT."""
    cfg = configparser.ConfigParser()
    for path in (_MAIN_CFG, _LOCAL_CFG):
        if os.path.exists(path):
            cfg.read(path)
    default = DEFAULT_OPEN_DEG if action == 'open' else DEFAULT_CLOSE_DEG
    try:
        return float(cfg.getint('servo_panels', f'{name}_{action}', fallback=int(default)))
    except Exception:
        return default

KNOWN_SERVOS = {f'Servo_S{i}' for i in range(16)}


class BodyServoDriver:
    """
    Master body servo abstraction layer.
    Translates high-level commands into UART SRV: messages.
    """

    def __init__(self, uart):
        self._uart  = uart
        self._ready = False

    def setup(self) -> bool:
        self._ready = True
        log.info("BodyServoDriver ready (%d known servos)", len(KNOWN_SERVOS))
        return True

    def shutdown(self) -> None:
        self.close_all()
        self._ready = False

    def is_ready(self) -> bool:
        return self._ready

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def open(self, name: str, angle_deg: float = None, speed: int = None) -> bool:
        if angle_deg is None:
            angle_deg = _calibrated_angle(name, 'open')
        if speed is None:
            speed = 10
        return self._send(name, angle_deg, speed)

    def close(self, name: str, angle_deg: float = None, speed: int = None) -> bool:
        if angle_deg is None:
            angle_deg = _calibrated_angle(name, 'close')
        if speed is None:
            speed = 10
        return self._send(name, angle_deg, speed)

    def move(self, name: str, position: float,
             angle_open: float = DEFAULT_OPEN_DEG,
             angle_close: float = DEFAULT_CLOSE_DEG) -> bool:
        """position 0.0=closed … 1.0=open — interpolated between angle_close and angle_open."""
        angle = angle_close + max(0.0, min(1.0, position)) * (angle_open - angle_close)
        return self._send(name, angle)

    def open_all(self, angle_deg: float = DEFAULT_OPEN_DEG) -> None:
        for name in KNOWN_SERVOS:
            self.open(name, angle_deg)

    def close_all(self, angle_deg: float = DEFAULT_CLOSE_DEG) -> None:
        for name in KNOWN_SERVOS:
            self.close(name, angle_deg)

    @property
    def state(self) -> dict:
        return {}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _send(self, name: str, angle_deg: float, speed: int = 10) -> bool:
        if not self._ready:
            log.warning("BodyServoDriver not ready — command ignored (%r)", name)
            return False
        if name not in KNOWN_SERVOS:
            log.warning("Unknown servo: %r", name)
        ok = self._uart.send('SRV', f'{name},{angle_deg:.1f},{speed}')
        log.debug("Servo %s → %.1f° speed=%d", name, angle_deg, speed)
        return ok
