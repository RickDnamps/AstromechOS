# ============================================================
#  ██████╗ ██████╗       ██████╗ ██████╗
#  ██╔══██╗╚════██╗      ██╔══██╗╚════██╗
#  ██████╔╝ █████╔╝      ██║  ██║ █████╔╝
#  ██╔══██╗██╔═══╝       ██║  ██║██╔═══╝
#  ██║  ██║███████╗      ██████╔╝███████╗
#  ╚═╝  ╚═╝╚══════╝      ╚═════╝ ╚══════╝
#
#  AstromechOS — Open control platform for astromech builders
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
UART Health Display tests — validates thresholds and display logic.

Verifies that the status API exposes the correct data and that the
degradation thresholds are properly defined (green/orange/red).

UI rules to validate:
  >= 95%      → ok    (green)  — normal
  70% - 94%   → warn  (orange) — minor interference
  < 70%       → error (red)    — bus seriously noisy
  Slave null  → grey / warn if Master CRC > 0

Usage : python -m pytest tests/test_uart_health_display.py -v
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, PropertyMock

# ── Mock hardware modules ────────────────────────────────────────────────────
import types
from unittest.mock import MagicMock

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Mock serial (pyserial not available on Windows dev PC)
_serial_mock = types.ModuleType('serial')
_serial_mock.Serial          = MagicMock()
_serial_mock.SerialException = type('SerialException', (Exception,), {})
sys.modules.setdefault('serial', _serial_mock)

# Mock master.registry only — do NOT mock the 'master' package itself
_registry_mod = types.ModuleType('master.registry')
_registry_mod.uart = None
sys.modules.setdefault('master.registry', _registry_mod)


# ─────────────────────────────────────────────────────────────────────────────
# Tests UARTController.crc_errors
# ─────────────────────────────────────────────────────────────────────────────

class TestUARTControllerCrcErrors(unittest.TestCase):
    """Verifies that UARTController properly exposes its CRC error counter."""

    def _make_uart(self):
        """Instantiates UARTController with a minimal mocked config."""
        import configparser
        cfg = configparser.ConfigParser()
        cfg.add_section('master')
        cfg.set('master', 'uart_port',             '/dev/ttyAMA0')
        cfg.set('master', 'uart_baud',             '115200')
        cfg.set('master', 'heartbeat_interval_ms', '200')

        # Mock serial to avoid opening the real port
        import master.uart_controller as uc_mod
        import serial as _serial
        with unittest.mock.patch.object(_serial, 'Serial'):
            from master.uart_controller import UARTController
            return UARTController(cfg)

    def test_crc_errors_initially_zero(self):
        """At startup, no CRC errors."""
        import configparser
        cfg = configparser.ConfigParser()
        cfg.add_section('master')
        cfg.set('master', 'uart_port', '/dev/ttyAMA0')
        cfg.set('master', 'uart_baud', '115200')
        cfg.set('master', 'heartbeat_interval_ms', '200')
        from master.uart_controller import UARTController
        uart = UARTController(cfg)
        self.assertEqual(uart.crc_errors, 0)

    def test_crc_errors_increments_on_invalid(self):
        """Each invalid message increments the counter."""
        import configparser
        cfg = configparser.ConfigParser()
        cfg.add_section('master')
        cfg.set('master', 'uart_port', '/dev/ttyAMA0')
        cfg.set('master', 'uart_baud', '115200')
        cfg.set('master', 'heartbeat_interval_ms', '200')
        from master.uart_controller import UARTController
        uart = UARTController(cfg)

        # Simulate 3 invalid messages (bad CRC)
        uart._process_line("H:1:ZZ")   # invalid checksum
        uart._process_line("M:bad:00") # invalid
        uart._process_line("GARBAGE")  # invalid
        self.assertEqual(uart.crc_errors, 3)

    def test_crc_errors_resets_on_valid_message(self):
        """A valid message resets the counter to 0."""
        import configparser
        cfg = configparser.ConfigParser()
        cfg.add_section('master')
        cfg.set('master', 'uart_port', '/dev/ttyAMA0')
        cfg.set('master', 'uart_baud', '115200')
        cfg.set('master', 'heartbeat_interval_ms', '200')
        from master.uart_controller import UARTController
        from shared.uart_protocol import build_msg
        uart = UARTController(cfg)

        # Some errors
        uart._process_line("GARBAGE1")
        uart._process_line("GARBAGE2")
        self.assertEqual(uart.crc_errors, 2)

        # Valid message — must reset the counter
        valid = build_msg('H', 'OK').strip()
        uart._process_line(valid)
        self.assertEqual(uart.crc_errors, 0)


# ─────────────────────────────────────────────────────────────────────────────
# Tests UI threshold logic (simulated in Python — mirror of JS logic)
# ─────────────────────────────────────────────────────────────────────────────

def _ui_uart_state(uart_ready: bool, health_pct: float | None, master_crc_errors: int = 0) -> str:
    """
    Mirror of the JS _setUartPill() logic.
    Returns: 'ok' | 'warn' | 'error' | 'grey'
    """
    if not uart_ready:
        return 'error'
    if health_pct is None:
        return 'warn' if master_crc_errors > 0 else 'ok'
    if health_pct >= 95:
        return 'ok'
    if health_pct >= 70:
        return 'warn'
    return 'error'


def _ui_uart_label(uart_ready: bool, health_pct: float | None, master_crc_errors: int = 0) -> str:
    """Mirror of the JS _setUartPill() label."""
    if not uart_ready:
        return 'UART'
    if health_pct is None:
        return 'UART ERR' if master_crc_errors > 0 else 'UART'
    return f'UART {health_pct:.0f}%'


class TestUARTHealthThresholds(unittest.TestCase):
    """
    Validates the display thresholds for the merged UART pill indicator.

    UX rules:
      - Port closed                   → red    'UART'
      - Port open, Slave not polled   → green  'UART'
      - Port open + CRC errors        → orange 'UART ERR'
      - >=95%                         → green  'UART 100%'
      - 70-94%                        → orange 'UART 82%'
      - <70%                          → red    'UART 45%'
    """

    # --- Serial port closed ---

    def test_port_closed_is_error(self):
        self.assertEqual(_ui_uart_state(False, None), 'error')

    def test_port_closed_label(self):
        self.assertEqual(_ui_uart_label(False, None), 'UART')

    # --- Port open, no Slave data yet ---

    def test_port_open_no_health_is_ok(self):
        """Port open, Slave not yet polled → green (assumed OK)."""
        self.assertEqual(_ui_uart_state(True, None, master_crc_errors=0), 'ok')

    def test_port_open_with_master_crc_errors_is_warn(self):
        """Port open + invalid Master CRC → orange."""
        self.assertEqual(_ui_uart_state(True, None, master_crc_errors=3), 'warn')

    def test_port_open_no_health_label(self):
        self.assertEqual(_ui_uart_label(True, None, 0), 'UART')

    def test_port_open_crc_errors_label(self):
        self.assertEqual(_ui_uart_label(True, None, 5), 'UART ERR')

    # --- Bus quality thresholds ---

    def test_100pct_is_ok(self):
        self.assertEqual(_ui_uart_state(True, 100.0), 'ok')

    def test_95pct_is_ok(self):
        self.assertEqual(_ui_uart_state(True, 95.0), 'ok')

    def test_94pct_is_warn(self):
        self.assertEqual(_ui_uart_state(True, 94.9), 'warn')

    def test_70pct_is_warn(self):
        self.assertEqual(_ui_uart_state(True, 70.0), 'warn')

    def test_69pct_is_error(self):
        self.assertEqual(_ui_uart_state(True, 69.9), 'error')

    def test_0pct_is_error(self):
        self.assertEqual(_ui_uart_state(True, 0.0), 'error')

    def test_label_shows_uart_with_percent(self):
        self.assertEqual(_ui_uart_label(True, 98.6), 'UART 99%')

    # --- Degradation progression ---

    def test_degradation_sequence(self):
        """
        Full sequence: clean bus → interference → critical.
        Simulates a run with 24V motors active.
        """
        sequence = [
            (100.0, 'ok'),    # startup — perfect bus
            (98.0,  'ok'),    # a few normal glitches
            (92.0,  'warn'),  # 24V motors active
            (75.0,  'warn'),  # ongoing degradation
            (65.0,  'error'), # slipring poorly connected
            (20.0,  'error'), # bus unusable
        ]
        for pct, expected in sequence:
            with self.subTest(pct=pct):
                self.assertEqual(_ui_uart_state(True, pct), expected,
                                 f"{pct}% should display '{expected}'")


# ─────────────────────────────────────────────────────────────────────────────
# Tests status API — uart_crc_errors field exposed
# ─────────────────────────────────────────────────────────────────────────────

class TestStatusApiUartErrors(unittest.TestCase):
    """
    Verifies that /status correctly exposes uart_crc_errors from UARTController.
    """

    def setUp(self):
        """Mocks the registry to simulate different UART states."""
        import configparser
        from master.uart_controller import UARTController
        cfg = configparser.ConfigParser()
        cfg.add_section('master')
        cfg.set('master', 'uart_port', '/dev/ttyAMA0')
        cfg.set('master', 'uart_baud', '115200')
        cfg.set('master', 'heartbeat_interval_ms', '200')
        self.uart = UARTController(cfg)

    def test_uart_crc_errors_zero_when_no_errors(self):
        """No CRC errors → uart_crc_errors = 0."""
        self.assertEqual(self.uart.crc_errors, 0)

    def test_uart_crc_errors_reflects_consecutive_invalids(self):
        """Consecutive errors → reflected in crc_errors."""
        for _ in range(5):
            self.uart._process_line("BAD:MSG:ZZ")
        self.assertEqual(self.uart.crc_errors, 5)

    def test_uart_crc_errors_resets_on_recovery(self):
        """After recovery, crc_errors goes back to 0."""
        from shared.uart_protocol import build_msg
        self.uart._process_line("BAD")
        self.uart._process_line("BAD")
        valid = build_msg('H', 'OK').strip()
        self.uart._process_line(valid)
        self.assertEqual(self.uart.crc_errors, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
