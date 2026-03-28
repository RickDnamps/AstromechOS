# master/lights/teeces.py
"""
TeecesDriver — JawaLite protocol via USB serial (Teeces32 board).

JawaLite commands:
  0T{n}\\r      Logic animations (0T1=random, 0T6=leia, 0T20=off)
  1M{txt}\\r    FLD text (Front Logic Display)
  2M{txt}\\r    RLD text (Rear Logic Display)
  4S{n}\\r      PSI mode (0=off, 1=random, 2-8=colors)

Port and baud read from [teeces] in config (port=/dev/ttyUSB0, baud=9600).
"""

import logging
import serial
import configparser
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from master.lights.base_controller import BaseLightsController

log = logging.getLogger(__name__)

_MAX_TEXT = 20          # max chars JawaLite (Teeces32 hardware limit)
_OK_DURATION = 3.0      # seconds to display system_ok before returning to random


class TeecesDriver(BaseLightsController):
    """JawaLite driver for the Teeces32 board."""

    def __init__(self, cfg: configparser.ConfigParser):
        self._port   = cfg.get('teeces', 'port')
        self._baud   = cfg.getint('teeces', 'baud')
        self._serial: serial.Serial | None = None
        self._ready  = False
        self._ok_timer = None

    # ------------------------------------------------------------------
    # BaseDriver
    # ------------------------------------------------------------------

    def setup(self) -> bool:
        try:
            self._serial = serial.Serial(self._port, self._baud, timeout=1)
            self._ready  = True
            log.info(f"TeecesDriver opened: {self._port} @ {self._baud}")
            return True
        except Exception as e:
            log.error(f"TeecesDriver unable to open {self._port}: {e}")
            self._ready = False
            return False

    def shutdown(self) -> None:
        self._cancel_ok_timer()
        self.off()
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._ready = False
        log.info("TeecesDriver stopped")

    def is_ready(self) -> bool:
        return self._ready and self._serial is not None and self._serial.is_open

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------

    def _send(self, cmd: str) -> bool:
        if not self.is_ready():
            log.warning(f"TeecesDriver not ready, ignored: {cmd!r}")
            return False
        try:
            self._serial.write(cmd.encode('ascii'))
            log.debug(f"Teeces TX: {cmd!r}")
            return True
        except serial.SerialException as e:
            log.error(f"TeecesDriver send error: {e}")
            self._ready = False
            return False

    def _cancel_ok_timer(self) -> None:
        if self._ok_timer is not None:
            self._ok_timer.cancel()
            self._ok_timer = None

    # ------------------------------------------------------------------
    # Interface canonique
    # ------------------------------------------------------------------

    def random_mode(self) -> bool:
        return self._send("0T1\r")

    def leia(self) -> bool:
        return self._send("0T6\r")

    def off(self) -> bool:
        return self._send("0T20\r")

    def text(self, message: str, target: str = "both") -> bool:
        msg = message[:_MAX_TEXT].upper()
        t   = target.lower()
        if t == "fld":
            return self._send(f"1M{msg}\r")
        if t == "rld":
            return self._send(f"2M{msg}\r")
        # "both" — JawaLite has no combined command
        ok1 = self._send(f"1M{msg}\r")
        ok2 = self._send(f"2M{msg}\r")
        return ok1 and ok2

    def animation(self, code: int) -> bool:
        return self._send(f"0T{int(code)}\r")

    def psi(self, state: int) -> bool:
        return self._send(f"4S{max(0, int(state))}\r")

    def raw(self, cmd: str) -> bool:
        if not cmd.endswith('\r'):
            cmd = cmd + '\r'
        return self._send(cmd)

    def system_error(self, message: str = "") -> bool:
        self._cancel_ok_timer()
        label = f"ERROR {message}".strip()[:_MAX_TEXT]
        ok1   = self._send("0T3\r")          # Alarm animation
        ok2   = self.text(label, "both")
        log.warning(f"TeecesDriver system_error: {label!r}")
        return ok1 and ok2

    def system_ok(self, message: str = "") -> bool:
        import threading
        self._cancel_ok_timer()
        label = (message or "OK")[:_MAX_TEXT].upper()
        ok1   = self._send("0T18\r")         # Green On
        ok2   = self.text(label, "both")
        log.info(f"TeecesDriver system_ok: {label!r}")

        def _restore():
            self._ok_timer = None
            self.random_mode()

        self._ok_timer = threading.Timer(_OK_DURATION, _restore)
        self._ok_timer.daemon = True
        self._ok_timer.start()
        return ok1 and ok2

    def slave_offline(self) -> bool:
        self._cancel_ok_timer()
        ok1 = self._send("0T3\r")
        ok2 = self.text("SLAVE DOWN", "both")
        log.error("TeecesDriver slave_offline")
        return ok1 and ok2

    def uart_error(self) -> bool:
        self._cancel_ok_timer()
        ok1 = self.text("UART ERROR", "both")
        ok2 = self._send("0T2\r")            # Flash
        log.error("TeecesDriver uart_error")
        return ok1 and ok2

    def show_version(self, version: str) -> bool:
        return self.text(f"VER {version}", "both")

    def alert_error(self, code: str = "") -> bool:
        label = f"ERROR {code}".strip()[:_MAX_TEXT]
        return self.text(label, "both")
