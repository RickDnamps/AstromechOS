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
Safety tests — simulates App/Android/UART disconnection scenarios.

Verifies the 3 watchdogs without hardware:
  - AppWatchdog    (600ms) : app crash / controller WiFi loss
  - MotionWatchdog (800ms) : drive command with no follow-up
  - WatchdogController Slave (500ms) : UART heartbeat loss

Usage : python -m pytest tests/test_watchdogs_safety.py -v
"""

import sys
import os
import time
import types
import unittest
from unittest.mock import MagicMock

# ── Mock sys.modules BEFORE any project code import ─────────────────────────
# Allows importing the watchdogs without Flask / connected hardware drivers.

_mock_stop_drive  = MagicMock(name='stop_drive')
_mock_stop_dome   = MagicMock(name='stop_dome')
_mock_cancel_ramp = MagicMock(name='cancel_ramp')

_registry_mod = types.ModuleType('master.registry')
_registry_mod.uart       = None
_registry_mod.vesc       = None
_registry_mod.dome       = None
_registry_mod.dome_servo = None
_registry_mod.servo      = None

_safe_stop_mod = types.ModuleType('master.safe_stop')
_safe_stop_mod.stop_drive  = _mock_stop_drive
_safe_stop_mod.stop_dome   = _mock_stop_dome
_safe_stop_mod.cancel_ramp = _mock_cancel_ramp

# Do NOT mock the 'master' package itself — let Python resolve it
# as a namespace package. Only mock sub-modules with hardware dependencies.
sys.modules.setdefault('master.registry',  _registry_mod)
sys.modules.setdefault('master.safe_stop', _safe_stop_mod)

# Add project root to Python path
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from master.app_watchdog    import AppWatchdog
from master.motion_watchdog import MotionWatchdog

# Slave watchdog — direct import to avoid naming conflicts
import importlib.util as _ilu
_slave_spec = _ilu.spec_from_file_location(
    'slave_watchdog',
    os.path.join(_PROJECT_ROOT, 'slave', 'watchdog.py')
)
_slave_mod = _ilu.module_from_spec(_slave_spec)
_slave_spec.loader.exec_module(_slave_mod)
WatchdogController = _slave_mod.WatchdogController


def _reset_mocks():
    _mock_stop_drive.reset_mock()
    _mock_stop_dome.reset_mock()
    _mock_cancel_ramp.reset_mock()


# ─────────────────────────────────────────────────────────────────────────────
# AppWatchdog — application heartbeat loss (Android / browser)
# ─────────────────────────────────────────────────────────────────────────────

class TestAppWatchdog(unittest.TestCase):
    """
    Scenario: the Android app or browser stops sending POST /heartbeat.
    Possible causes: app crash, WiFi lost, screen off (WebView paused).
    Expected: emergency stop after 600ms.
    """

    def setUp(self):
        _reset_mocks()
        self.wdog = AppWatchdog()
        self.wdog.start()

    def tearDown(self):
        self.wdog.stop()

    def test_initial_not_connected(self):
        """Before any heartbeat, is_connected must be False."""
        self.assertFalse(self.wdog.is_connected)

    def test_first_heartbeat_connects(self):
        """On the first heartbeat, is_connected switches to True."""
        self.wdog.feed()
        self.assertTrue(self.wdog.is_connected)

    def test_no_emergency_stop_without_first_heartbeat(self):
        """
        CRITICAL: if no app has ever connected,
        the emergency stop must NOT trigger (robot idle at boot).
        """
        time.sleep(1.0)  # wait > 600ms timeout
        _mock_stop_drive.assert_not_called()
        _mock_stop_dome.assert_not_called()

    def test_disconnect_triggers_emergency_stop(self):
        """
        CRITICAL: app connected → WiFi lost → emergency stop after 600ms.
        Simulates: Android crash / browser tab closed.
        """
        self.wdog.feed()
        self.assertTrue(self.wdog.is_connected)

        # Silence — no more heartbeats
        time.sleep(1.0)  # 600ms timeout + 400ms margin

        _mock_stop_drive.assert_called_once()
        _mock_stop_dome.assert_called_once()
        self.assertFalse(self.wdog.is_connected)

    def test_continuous_heartbeats_no_stop(self):
        """
        Regular heartbeats (every 150ms < 600ms timeout) → no stop.
        """
        for _ in range(6):
            self.wdog.feed()
            time.sleep(0.15)

        _mock_stop_drive.assert_not_called()
        _mock_stop_dome.assert_not_called()
        self.assertTrue(self.wdog.is_connected)

    def test_reconnect_rearms_watchdog(self):
        """
        After a timeout, the app reconnects → is_connected=True.
        A second disconnection triggers the stop again.
        """
        # Cycle 1 : disconnection
        self.wdog.feed()
        time.sleep(1.0)
        self.assertFalse(self.wdog.is_connected)

        _reset_mocks()

        # Reconnection
        self.wdog.feed()
        self.assertTrue(self.wdog.is_connected)

        # Cycle 2 : second disconnection
        time.sleep(1.0)
        _mock_stop_drive.assert_called_once()

    def test_emergency_stop_triggered_only_once_per_disconnect(self):
        """
        The emergency stop triggers exactly once per disconnection,
        not in a loop on every watchdog cycle.
        """
        self.wdog.feed()
        time.sleep(2.0)  # wait 2+ full cycles

        self.assertEqual(_mock_stop_drive.call_count, 1,
                         "stop_drive() must be called exactly once")
        self.assertEqual(_mock_stop_dome.call_count, 1,
                         "stop_dome() must be called exactly once")

    def test_hb_age_minus_one_before_first(self):
        """Before the first HB, last_hb_age_ms returns -1 (no data yet)."""
        self.assertEqual(self.wdog.last_hb_age_ms, -1.0)

    def test_hb_age_positive_after_heartbeat(self):
        """After a HB, the age is positive and below the timeout."""
        self.wdog.feed()
        time.sleep(0.1)
        age = self.wdog.last_hb_age_ms
        self.assertGreater(age, 0, "Age must be positive")
        self.assertLess(age, 600, "Age must not exceed the timeout")


# ─────────────────────────────────────────────────────────────────────────────
# MotionWatchdog — disconnection during active movement
# ─────────────────────────────────────────────────────────────────────────────

class TestMotionWatchdog(unittest.TestCase):
    """
    Scenario: the app sends a drive/dome command, then disconnects.
    Expected: automatic stop after 800ms with no new command.
    """

    def setUp(self):
        _reset_mocks()
        self.wdog = MotionWatchdog()
        self.wdog.start()

    def tearDown(self):
        self.wdog.stop()

    def test_no_command_no_stop(self):
        """Without a drive command, no stop must be triggered."""
        time.sleep(1.2)
        _mock_stop_drive.assert_not_called()

    def test_drive_timeout_triggers_stop(self):
        """
        CRITICAL: drive command received, then silence > 800ms → propulsion stop.
        Simulates: Android app crash while moving.
        """
        self.wdog.feed_drive(0.5, 0.5)
        time.sleep(1.2)
        _mock_stop_drive.assert_called()

    def test_dome_timeout_triggers_stop(self):
        """
        CRITICAL: active dome command, then silence > 800ms → dome stop.
        """
        self.wdog.feed_dome(0.3)
        time.sleep(1.2)
        _mock_stop_dome.assert_called()

    def test_continuous_drive_no_stop(self):
        """Continuous drive commands (every 150ms) → no stop."""
        for _ in range(6):
            self.wdog.feed_drive(0.5, 0.5)
            time.sleep(0.15)
        _mock_stop_drive.assert_not_called()

    def test_explicit_stop_no_watchdog_trigger(self):
        """
        Explicit stop via clear_drive() → watchdog does not trigger.
        The stop comes from the app, not a timeout.
        """
        self.wdog.feed_drive(0.5, 0.5)
        self.wdog.clear_drive()
        time.sleep(1.2)
        _mock_stop_drive.assert_not_called()

    def test_explicit_dome_stop_no_trigger(self):
        """Explicit dome stop → no watchdog trigger."""
        self.wdog.feed_dome(0.3)
        self.wdog.clear_dome()
        time.sleep(1.2)
        _mock_stop_dome.assert_not_called()

    def test_zero_speed_no_timeout(self):
        """
        Drive command with speed 0 (within deadzone) → no timeout.
        The robot is already stopped.
        """
        self.wdog.feed_drive(0.0, 0.0)
        time.sleep(1.2)
        _mock_stop_drive.assert_not_called()

    def test_cancel_ramp_on_new_drive_command(self):
        """
        New drive command → cancel_ramp() called to interrupt
        any ongoing gradual stop (e.g. app reconnected).
        """
        self.wdog.feed_drive(0.5, 0.5)
        _mock_cancel_ramp.assert_called()

    def test_drive_timeout_only_once(self):
        """Propulsion timeout triggered exactly once, not in a loop."""
        self.wdog.feed_drive(0.8, 0.8)
        time.sleep(2.0)
        self.assertEqual(_mock_stop_drive.call_count, 1)

    def test_dome_drive_independent_timeouts(self):
        """
        Dome timeout and propulsion timeout are independent.
        Explicit propulsion stop does not affect the dome timeout.
        """
        self.wdog.feed_drive(0.5, 0.5)
        self.wdog.clear_drive()       # explicit propulsion stop
        self.wdog.feed_dome(0.3)      # dome active

        time.sleep(1.2)

        _mock_stop_drive.assert_not_called()   # propulsion: explicit stop
        _mock_stop_dome.assert_called()        # dome: timeout

    def test_reverse_drive_timeout(self):
        """Reverse drive command also triggers the timeout."""
        self.wdog.feed_drive(-0.6, -0.6)
        time.sleep(1.2)
        _mock_stop_drive.assert_called()


# ─────────────────────────────────────────────────────────────────────────────
# WatchdogController (Slave) — UART heartbeat loss Master→Slave
# ─────────────────────────────────────────────────────────────────────────────

class TestSlaveWatchdog(unittest.TestCase):
    """
    Scenario: the UART link between Master and Slave is cut.
    Causes: slipring cable unplugged, Master crash, dome power lost.
    Expected: VESC cut off after 500ms without UART heartbeat.
    """

    def setUp(self):
        self.stop_cb   = MagicMock(name='stop_callback')
        self.resume_cb = MagicMock(name='resume_callback')
        self.wdog = WatchdogController(timeout_s=0.5)
        self.wdog.register_stop_callback(self.stop_cb)
        self.wdog.register_resume_callback(self.resume_cb)
        self.wdog.start()

    def tearDown(self):
        self.wdog.stop()

    def test_no_immediate_stop_at_startup(self):
        """
        At startup, the watchdog initialises the timer to now().
        No immediate trigger — allow time for the Master to boot.
        """
        time.sleep(0.2)
        self.stop_cb.assert_not_called()

    def test_no_hb_triggers_vesc_cutoff(self):
        """
        CRITICAL: no UART heartbeat since startup → VESC cutoff.
        Simulates: slipring cable unplugged before boot, or Master hung.
        """
        time.sleep(0.8)
        self.stop_cb.assert_called_once()

    def test_regular_hb_prevents_cutoff(self):
        """Regular heartbeats (every 150ms < 500ms) → no cutoff."""
        for _ in range(6):
            self.wdog.feed()
            time.sleep(0.15)
        self.stop_cb.assert_not_called()

    def test_resume_callback_on_uart_recovery(self):
        """
        UART cut → VESC cutoff → UART resumes → VESC re-enabled.
        Simulates: hot slipring reconnection.
        """
        time.sleep(0.8)  # trigger cutoff
        self.stop_cb.assert_called_once()

        # UART recovery
        self.wdog.feed()
        time.sleep(0.1)
        self.resume_cb.assert_called_once()

    def test_stop_triggered_only_once_per_cutoff(self):
        """
        VESC cutoff triggers exactly once per timeout,
        not in a loop (avoids VESC flickering).
        """
        time.sleep(1.5)
        self.assertEqual(self.stop_cb.call_count, 1,
                         "stop_callback must be called exactly once")

    def test_multiple_disconnect_reconnect_cycles(self):
        """
        Multiple disconnect/reconnect cycles → each disconnection
        triggers a cutoff, each reconnection triggers a resume.
        """
        # Cycle 1 : cutoff
        time.sleep(0.8)
        self.assertEqual(self.stop_cb.call_count, 1)

        # Reconnection
        self.wdog.feed()
        time.sleep(0.1)
        self.assertEqual(self.resume_cb.call_count, 1)

        # Cycle 2 : cutoff
        time.sleep(0.8)
        self.assertEqual(self.stop_cb.call_count, 2)

        # Reconnection 2
        self.wdog.feed()
        time.sleep(0.1)
        self.assertEqual(self.resume_cb.call_count, 2)

    def test_feed_clears_triggered_state(self):
        """After a trigger, feed() resets triggered to False."""
        time.sleep(0.8)
        self.assertTrue(self.wdog._triggered)
        self.wdog.feed()
        time.sleep(0.1)
        self.assertFalse(self.wdog._triggered)

    def test_callback_exception_does_not_crash_watchdog(self):
        """
        A callback that raises an exception must not crash the watchdog.
        The watchdog must remain functional.
        """
        crash_cb = MagicMock(side_effect=RuntimeError("simulated driver crash"))
        safe_cb  = MagicMock()

        wdog = WatchdogController(timeout_s=0.3)
        wdog.register_stop_callback(crash_cb)
        wdog.register_stop_callback(safe_cb)
        wdog.start()

        time.sleep(0.6)

        crash_cb.assert_called()
        safe_cb.assert_called()   # must be called despite the previous exception
        wdog.stop()

    def test_custom_timeout_respected(self):
        """The custom timeout is correctly honoured."""
        fast_wdog = WatchdogController(timeout_s=0.2)
        fast_cb = MagicMock()
        fast_wdog.register_stop_callback(fast_cb)
        fast_wdog.start()

        time.sleep(0.4)
        fast_cb.assert_called_once()
        fast_wdog.stop()


if __name__ == '__main__':
    unittest.main(verbosity=2)
