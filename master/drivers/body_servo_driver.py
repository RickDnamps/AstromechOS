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
Master Body Servo Driver — Phase 2 (MG90S 180°).
Envoie les commandes de servos body au Slave via UART (message SRV:).
Le Slave exécute sur le PCA9685 I2C.

Format UART: SRV:NAME,ANGLE_DEG
  NAME      : nom du servo (ex: body_panel_1)
  ANGLE_DEG : float — angle cible en degrés (10–170°)

Le Slave applique : pulse_us = 500 + (angle_deg / 180.0) * 2000
Le servo MG90S maintient la position — pas de timer d'arrêt.
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
    """Lit l'angle calibré depuis local.cfg [servo_panels]. Fallback sur DEFAULT."""
    cfg = configparser.ConfigParser()
    for path in (_MAIN_CFG, _LOCAL_CFG):
        if os.path.exists(path):
            cfg.read(path)
    default = DEFAULT_OPEN_DEG if action == 'open' else DEFAULT_CLOSE_DEG
    try:
        return float(cfg.getint('servo_panels', f'{name}_{action}', fallback=int(default)))
    except Exception:
        return default

KNOWN_SERVOS = {
    'body_panel_1',  'body_panel_2',  'body_panel_3',
    'body_panel_4',  'body_panel_5',  'body_panel_6',
    'body_panel_7',  'body_panel_8',  'body_panel_9',
    'body_panel_10', 'body_panel_11',
}


class BodyServoDriver:
    """
    Couche d'abstraction servos body Master.
    Traduit les commandes haut niveau en messages UART SRV:.
    """

    def __init__(self, uart):
        self._uart  = uart
        self._ready = False

    def setup(self) -> bool:
        self._ready = True
        log.info("BodyServoDriver prêt (%d servos connus)", len(KNOWN_SERVOS))
        return True

    def shutdown(self) -> None:
        self.close_all()
        self._ready = False

    def is_ready(self) -> bool:
        return self._ready

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def open(self, name: str, angle_deg: float = None, speed: int = None) -> bool:
        if angle_deg is None:
            angle_deg = _calibrated_angle(name, 'open')
        return self._send(name, angle_deg)

    def close(self, name: str, angle_deg: float = None, speed: int = None) -> bool:
        if angle_deg is None:
            angle_deg = _calibrated_angle(name, 'close')
        return self._send(name, angle_deg)

    def move(self, name: str, position: float,
             angle_open: float = DEFAULT_OPEN_DEG,
             angle_close: float = DEFAULT_CLOSE_DEG) -> bool:
        """position 0.0=fermé … 1.0=ouvert — interpolé entre angle_close et angle_open."""
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
    # Interne
    # ------------------------------------------------------------------

    def _send(self, name: str, angle_deg: float) -> bool:
        if not self._ready:
            log.warning("BodyServoDriver non prêt — commande ignorée (%r)", name)
            return False
        if name not in KNOWN_SERVOS:
            log.warning("Servo inconnu: %r", name)
        ok = self._uart.send('SRV', f'{name},{angle_deg:.1f}')
        log.debug("Servo %s → %.1f°", name, angle_deg)
        return ok
