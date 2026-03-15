"""
Display Driver — RP2040 Touch LCD 1.28 via USB serial.
Envoie les commandes DISP: au RP2040 sur /dev/ttyACM2.
"""

import logging
import serial
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.base_driver import BaseDriver

log = logging.getLogger(__name__)

DISPLAY_PORT = "/dev/ttyACM2"
DISPLAY_BAUD = 115200


class DisplayDriver(BaseDriver):
    def __init__(self, port: str = DISPLAY_PORT, baud: int = DISPLAY_BAUD):
        self._port = port
        self._baud = baud
        self._serial: serial.Serial | None = None
        self._ready = False

    def setup(self) -> bool:
        try:
            self._serial = serial.Serial(self._port, self._baud, timeout=1)
            self._ready = True
            log.info(f"DisplayDriver ouvert: {self._port}")
            return True
        except serial.SerialException as e:
            log.error(f"Impossible d'ouvrir display {self._port}: {e}")
            return False

    def shutdown(self) -> None:
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._ready = False

    def is_ready(self) -> bool:
        return self._ready and self._serial is not None and self._serial.is_open

    # ------------------------------------------------------------------
    # Commandes d'état
    # ------------------------------------------------------------------

    def boot(self) -> bool:
        """Affiche l'écran de boot (splash R2-D2, fond blanc)."""
        return self._send("DISP:BOOT")

    def syncing(self, version: str = "") -> bool:
        """Spinner de synchronisation + versions (fond orange)."""
        if version:
            return self._send(f"DISP:SYNCING:{version}")
        return self._send("DISP:SYNCING")

    def ok(self, version: str = "") -> bool:
        """Validation OK — libère vers écran principal (fond vert)."""
        if version:
            return self._send(f"DISP:OK:{version}")
        return self._send("DISP:OK")

    def error(self, reason: str) -> bool:
        """Alerte bloquante (fond rouge)."""
        return self._send(f"DISP:ERROR:{reason}")

    def telemetry(self, voltage: float, temp: float) -> bool:
        """Jauge batterie + température (fond bleu)."""
        return self._send(f"DISP:TELEM:{voltage:.1f}V:{temp:.0f}C")

    def send_raw(self, cmd: str) -> bool:
        """Envoie une commande brute au RP2040 (ex: commande DISP: transférée via UART)."""
        return self._send(cmd)

    # ------------------------------------------------------------------
    # Interne
    # ------------------------------------------------------------------

    def _send(self, cmd: str) -> bool:
        if not self.is_ready():
            log.debug(f"DisplayDriver non prêt, commande ignorée: {cmd}")
            return False
        try:
            self._serial.write(f"{cmd}\n".encode('utf-8'))
            log.debug(f"Display TX: {cmd}")
            return True
        except serial.SerialException as e:
            log.error(f"Erreur display send: {e}")
            self._ready = False
            return False
