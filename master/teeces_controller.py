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
Teeces32 Controller — Protocole JawaLite via USB /dev/ttyUSB0.
Gère les LED logics FLD/RLD/PSI sur le dôme.
"""

import logging
import serial
import configparser
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from shared.base_driver import BaseDriver

log = logging.getLogger(__name__)


class TeecesController(BaseDriver):
    # All known JawaLite T-code animations
    ANIMATIONS: dict[int, str] = {
        1:  'Random',
        2:  'Flash',
        3:  'Alarm',
        4:  'Short Circuit',
        5:  'Scream',
        6:  'Leia Message',
        7:  'I Heart U',
        8:  'Panel Sweep',
        9:  'Pulse Monitor',
        10: 'Star Wars Scroll',
        11: 'Imperial March',
        12: 'Disco (timed)',
        13: 'Disco',
        14: 'Rebel Symbol',
        15: 'Knight Rider',
        16: 'Test White',
        17: 'Red On',
        18: 'Green On',
        19: 'Lightsaber',
        20: 'Off',
        21: 'VU Meter (timed)',
        92: 'VU Meter',
    }

    def __init__(self, cfg: configparser.ConfigParser):
        self._port = cfg.get('teeces', 'port')
        self._baud = cfg.getint('teeces', 'baud')
        self._serial: serial.Serial | None = None
        self._ready = False

    def setup(self) -> bool:
        try:
            self._serial = serial.Serial(self._port, self._baud, timeout=1)
            self._ready = True
            log.info(f"Teeces32 ouvert: {self._port} @ {self._baud}")
            return True
        except serial.SerialException as e:
            log.error(f"Impossible d'ouvrir Teeces32 {self._port}: {e}")
            self._ready = False
            return False

    def shutdown(self) -> None:
        self.all_off()
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._ready = False
        log.info("Teeces32 arrêté")

    def is_ready(self) -> bool:
        return self._ready and self._serial is not None and self._serial.is_open

    def send_command(self, cmd: str) -> bool:
        """Envoie une commande JawaLite brute. Ex: '0T1\r'"""
        if not self.is_ready():
            log.warning(f"Teeces32 non prêt, commande ignorée: {cmd!r}")
            return False
        try:
            self._serial.write(cmd.encode('ascii'))
            log.debug(f"Teeces TX: {cmd!r}")
            return True
        except serial.SerialException as e:
            log.error(f"Erreur Teeces32 send: {e}")
            self._ready = False
            return False

    # ------------------------------------------------------------------
    # Commandes préfabriquées
    # ------------------------------------------------------------------

    def random_mode(self) -> bool:
        """Mode animations aléatoires (mode normal)."""
        return self.send_command("0T1\r")

    def all_off(self) -> bool:
        """Éteint toutes les LEDs."""
        return self.send_command("0T20\r")

    def leia_mode(self) -> bool:
        """Mode Leia."""
        return self.send_command("0T6\r")

    def psi_random(self) -> bool:
        """PSI animations aléatoires."""
        return self.send_command("4S1\r")

    def psi_mode(self, mode: int) -> bool:
        """Contrôle PSI avec mode spécifique. 1=aléatoire, 0=éteint."""
        mode = max(0, int(mode))
        return self.send_command(f"4S{mode}\r")

    def fld_text(self, text: str) -> bool:
        """Texte défilant sur Front Logic Display. Max ~20 chars."""
        text = text[:20].upper()
        return self.send_command(f"1M{text}\r")

    def rld_text(self, text: str) -> bool:
        """Texte défilant sur Rear Logic Display. Max ~20 chars."""
        text = text[:20].upper()
        return self.send_command(f"2M{text}\r")

    def alert_master_offline(self) -> bool:
        """Alerte visuelle Master hors ligne."""
        return self.send_command("1MMASTER OFFLINE\r")

    def alert_error(self, code: str = "") -> bool:
        """Alerte visuelle erreur."""
        msg = f"ERREUR {code}"[:20] if code else "ERREUR"
        return self.send_command(f"1M{msg}\r")

    def show_version(self, version: str) -> bool:
        """Affiche la version courante sur FLD."""
        return self.fld_text(f"VER {version}")

    def animation(self, mode: int) -> bool:
        """Trigger a named animation by T-code. Ex: animation(11) → Imperial March."""
        return self.send_command(f"0T{int(mode)}\r")

    def send_raw(self, cmd: str) -> bool:
        """Send a raw JawaLite command string. Ex: '1MHELLO\\r'"""
        if not cmd.endswith('\r'):
            cmd = cmd + '\r'
        return self.send_command(cmd)
