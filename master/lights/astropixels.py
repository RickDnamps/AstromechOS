# master/lights/astropixels.py
"""
AstroPixelsDriver — AstroPixelsPlus protocol via USB serial.

AstroPixels+ commands (@ prefix, \\r terminator):
  @0T{n}\\r     Logic animations (same T-code numbering as JawaLite)
  @1M{txt}\\r   FLD text only
  @2M{txt}\\r   RLD text only
  @3M{txt}\\r   FLD + RLD simultaneously (combined command — 1 write)
  @4S{n}\\r     PSI mode (0=off, 1=random, 2-8=colors)

Port and baud read from [teeces] in config (same section as TeecesDriver).
"""

import logging
import serial
import configparser
import threading
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from master.lights.base_controller import BaseLightsController

log = logging.getLogger(__name__)

_MAX_TEXT    = 32         # AstroPixels+ accepts up to 32 chars
_OK_DURATION = 3.0        # seconds before returning to random after system_ok

# AstroPixels+ text command prefixes (source-verified from MarcduinoLogics.h)
# @1M = FLD top row only    @2M = FLD bottom row only    @3M = RLD
# Color for @M text commands is always randomColor() in the firmware — not configurable via serial.
_TEXT_PREFIX = {
    "fld_top":    "@1M",
    "fld_bottom": "@2M",
    "rld":        "@3M",
}


class AstroPixelsDriver(BaseLightsController):
    """AstroPixels+ driver (@-prefixed commands)."""

    def __init__(self, cfg: configparser.ConfigParser):
        self._port   = cfg.get('teeces', 'port')
        self._baud   = cfg.getint('teeces', 'baud')
        self._serial: serial.Serial | None = None
        self._ready  = False
        self._ok_timer: threading.Timer | None = None

    # ------------------------------------------------------------------
    # BaseDriver
    # ------------------------------------------------------------------

    def setup(self) -> bool:
        try:
            self._serial = serial.Serial(self._port, self._baud, timeout=1)
            self._ready  = True
            log.info(f"AstroPixelsDriver opened: {self._port} @ {self._baud}")
            return True
        except Exception as e:
            log.error(f"AstroPixelsDriver unable to open {self._port}: {e}")
            self._ready = False
            return False

    def shutdown(self) -> None:
        self._cancel_ok_timer()
        self.off()
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._ready = False
        log.info("AstroPixelsDriver stopped")

    def is_ready(self) -> bool:
        return self._ready and self._serial is not None and self._serial.is_open

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------

    def _send(self, cmd: str) -> bool:
        if not self.is_ready():
            log.warning(f"AstroPixelsDriver not ready, ignored: {cmd!r}")
            return False
        try:
            self._serial.write(cmd.encode('ascii'))
            log.debug(f"AstroPixels+ TX: {cmd!r}")
            return True
        except Exception as e:
            log.error(f"AstroPixelsDriver send error: {e}")
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
        return self._send("@0T1\r")

    def leia(self) -> bool:
        return self._send("@0T6\r")

    def off(self) -> bool:
        return self._send("@0T20\r")

    def holo(self, target: str = "fhp", effect: str = "on") -> bool:
        """Control holo projectors via @HP passthrough (source: MarcduinoHolo.h).
        target: 'fhp' | 'rhp' | 'thp' | 'radar' | 'all'
        effect: 'on' | 'off' | 'pulse' | 'rainbow' | 'random_move' | 'wag' | 'nod'"""
        _TARGET = {'fhp': 'F', 'rhp': 'R', 'thp': 'T', 'radar': 'D', 'all': 'A'}
        _EFFECT = {
            'on':          '0040',
            'off':         '0000',
            'pulse':       '0030',
            'rainbow':     '006',
            'random_move': '104',
            'wag':         '105|5',
            'nod':         '106|5',
        }
        t = _TARGET.get(target.lower(), 'F')
        e = _EFFECT.get(effect.lower(), '0000')
        return self._send(f"@HP{t}{e}\r")

    def text(self, message: str, target: str = "fld_top", color: str = "") -> bool:
        """Send scrolling text to a logic display.
        target: 'fld_top' | 'fld_bottom' | 'fld_both' | 'rld' | 'all'
        color: ignored — AstroPixels+ firmware uses randomColor() for all @M text commands.
        @1M = FLD top row, @2M = FLD bottom row, @3M = RLD (source: MarcduinoLogics.h)"""
        msg = message[:_MAX_TEXT].upper()
        t   = target.lower()
        if t == 'fld_both':
            self._send(f"@1M{msg}\r")
            return self._send(f"@2M{msg}\r")
        if t == 'all':
            self._send(f"@1M{msg}\r")
            self._send(f"@2M{msg}\r")
            return self._send(f"@3M{msg}\r")
        prefix = _TEXT_PREFIX.get(t, "@1M")
        return self._send(f"{prefix}{msg}\r")

    def animation(self, code: int) -> bool:
        return self._send(f"@0T{int(code)}\r")

    def psi(self, state: int) -> bool:
        return self._send(f"@4S{max(0, int(state))}\r")

    def raw(self, cmd: str) -> bool:
        if not cmd.endswith('\r'):
            cmd = cmd + '\r'
        return self._send(cmd)

    def system_error(self, message: str = "") -> bool:
        self._cancel_ok_timer()
        label = f"ERROR {message}".strip()[:_MAX_TEXT]
        ok1   = self._send("@0T3\r")          # Alarm
        ok2   = self.text(label, "both")
        log.warning(f"AstroPixelsDriver system_error: {label!r}")
        return ok1 and ok2

    def system_ok(self, message: str = "") -> bool:
        self._cancel_ok_timer()
        label = (message or "OK")[:_MAX_TEXT].upper()
        ok1   = self._send("@0T18\r")         # Green On
        ok2   = self.text(label, "both")
        log.info(f"AstroPixelsDriver system_ok: {label!r}")

        def _restore():
            self._ok_timer = None
            self.random_mode()

        self._ok_timer = threading.Timer(_OK_DURATION, _restore)
        self._ok_timer.daemon = True
        self._ok_timer.start()
        return ok1 and ok2

    def slave_offline(self) -> bool:
        self._cancel_ok_timer()
        ok1 = self._send("@0T3\r")
        ok2 = self._send("@3MSLAVE DOWN\r")
        log.error("AstroPixelsDriver slave_offline")
        return ok1 and ok2

    def uart_error(self) -> bool:
        self._cancel_ok_timer()
        ok1 = self._send("@3MUART ERROR\r")
        ok2 = self._send("@0T2\r")            # Flash
        log.error("AstroPixelsDriver uart_error")
        return ok1 and ok2

    def show_version(self, version: str) -> bool:
        return self.text(f"VER {version}", "both")

    def alert_error(self, code: str = "") -> bool:
        label = f"ERROR {code}".strip()[:_MAX_TEXT]
        return self.text(label, "both")
