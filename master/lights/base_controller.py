# master/lights/base_controller.py
"""
Common abstract interface for all lights drivers.

All drivers (TeecesDriver, AstroPixelsDriver, ...) inherit from this
class and implement the methods marked @abstractmethod.

Non-abstract methods are backward-compatibility aliases for callers
that still used the old TeecesController API.
"""

from abc import ABC, abstractmethod
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.base_driver import BaseDriver


class BaseLightsController(BaseDriver, ABC):
    """Interface canonique pour tous les drivers lights R2-D2."""

    # Animation catalogue — T-code numbering shared by all drivers
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

    # ------------------------------------------------------------------
    # Canonical interface (must be implemented in each driver)
    # ------------------------------------------------------------------

    @abstractmethod
    def setup(self) -> bool:
        """Opens the serial port. Returns False on failure."""

    @abstractmethod
    def shutdown(self) -> None:
        """Clean shutdown — turns off LEDs and closes the port."""

    @abstractmethod
    def is_ready(self) -> bool:
        """True if the port is open and operational."""

    @abstractmethod
    def random_mode(self) -> bool:
        """Random animation mode (normal R2 mode)."""

    @abstractmethod
    def leia(self) -> bool:
        """Leia hologram mode."""

    @abstractmethod
    def off(self) -> bool:
        """Turn off all LEDs."""

    @abstractmethod
    def text(self, message: str, target: str = "both") -> bool:
        """Scrolling text on the logics. target: 'fld' | 'rld' | 'both'"""

    @abstractmethod
    def animation(self, code: int) -> bool:
        """Trigger an animation by T-code (see ANIMATIONS)."""

    @abstractmethod
    def psi(self, state: int) -> bool:
        """Control the PSIs. 0=off, 1=random, 2-8=colors."""

    @abstractmethod
    def raw(self, cmd: str) -> bool:
        """Send a raw command (driver's native protocol)."""

    @abstractmethod
    def system_error(self, message: str = "") -> bool:
        """Visual system error alert."""

    @abstractmethod
    def system_ok(self, message: str = "") -> bool:
        """Visual success confirmation (green 3s then back to random)."""

    @abstractmethod
    def slave_offline(self) -> bool:
        """Visual alert: Slave offline."""

    @abstractmethod
    def uart_error(self) -> bool:
        """Visual alert: UART error."""

    @abstractmethod
    def show_version(self, version: str) -> bool:
        """Display the version on the logics."""

    @abstractmethod
    def alert_error(self, code: str = "") -> bool:
        """Display an error code on the logics."""

    # ------------------------------------------------------------------
    # Backward-compatibility aliases (non-abstract — inherited for free)
    # ------------------------------------------------------------------

    def all_off(self) -> bool:
        return self.off()

    def leia_mode(self) -> bool:
        return self.leia()

    def psi_mode(self, mode: int) -> bool:
        return self.psi(mode)

    def psi_random(self) -> bool:
        return self.psi(1)

    def fld_text(self, message: str) -> bool:
        return self.text(message, "fld")

    def rld_text(self, message: str) -> bool:
        return self.text(message, "rld")

    def send_raw(self, cmd: str) -> bool:
        return self.raw(cmd)

    def alert_master_offline(self) -> bool:
        # Historical alias: called when Master goes offline, alerts via lights
        return self.slave_offline()
