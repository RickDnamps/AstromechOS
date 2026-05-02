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
Safe Stop — Gradual motor stop for propulsion.

Instead of brutally sending M:0,0 (risk of robot tipping),
we ramp the command from current speed to 0 over a duration
proportional to speed.

Parameters (adjustable):
  RAMP_MAX_MS : stop duration at maximum speed (1.0) = 400ms
  RAMP_STEP_MS: interval between VESC updates           = 20ms
  DEADZONE    : below this → immediate stop (no ramp needed)

Effective duration examples:
  Speed 1.0  → 400ms  (~20 steps at 20ms)
  Speed 0.5  → 200ms  (~10 steps)
  Speed 0.3  → 120ms  (6 steps)
  Speed 0.1  → immediate stop (deadzone)

Usage in watchdogs:
  safe_stop.stop_drive(vesc, uart)
  safe_stop.stop_dome(dome, uart)
"""

import logging
import threading
import time

import master.registry as reg

log = logging.getLogger(__name__)

RAMP_MAX_MS  = 400    # duration ms at speed = 1.0
RAMP_STEP_MS = 20     # VESC step in ms (~50Hz)
DEADZONE     = 0.08   # below this → immediate stop

# Global event to cancel an ongoing ramp (e.g. app reconnects)
_cancel_drive = threading.Event()
_cancel_dome  = threading.Event()


def cancel_ramp():
    """Cancel any ongoing ramp — called when the app sends a new command."""
    _cancel_drive.set()
    _cancel_dome.set()


def stop_drive(vesc=None, uart=None) -> None:
    """
    Gradual propulsion stop.
    Ramps current speed down to 0.
    Runs in a daemon thread to avoid blocking the watchdog.
    """
    v = vesc or reg.vesc
    u = uart or reg.uart

    # Read current speed from the driver if available
    left  = getattr(v, '_left',  0.0) if v else 0.0
    right = getattr(v, '_right', 0.0) if v else 0.0

    max_speed = max(abs(left), abs(right))

    if max_speed < DEADZONE:
        # Already nearly stopped — just confirm M:0,0
        _send_drive(v, u, 0.0, 0.0)
        return

    _cancel_drive.clear()
    duration_ms = int(max_speed * RAMP_MAX_MS)
    steps       = max(3, duration_ms // RAMP_STEP_MS)
    interval    = duration_ms / 1000.0 / steps

    log.warning(
        "SafeStop drive: %.2f,%.2f → 0 in %dms (%d steps)",
        left, right, duration_ms, steps
    )

    def _ramp():
        for i in range(1, steps + 1):
            if _cancel_drive.is_set():
                log.info("SafeStop drive: ramp cancelled (new command received)")
                return
            factor = 1.0 - (i / steps)   # 1.0 → 0.0
            l = left  * factor
            r = right * factor
            _send_drive(v, u, l, r)
            time.sleep(interval)
        # Final guaranteed stop
        _send_drive(v, u, 0.0, 0.0)
        log.info("SafeStop drive: gradual stop complete")

    threading.Thread(target=_ramp, daemon=True, name="safe-stop-drive").start()


def stop_dome(dome=None, uart=None) -> None:
    """
    Gradual dome motor stop.
    Same logic as stop_drive but for dome rotation.
    """
    d = dome or reg.dome
    u = uart or reg.uart

    speed = getattr(d, '_speed', 0.0) if d else 0.0
    if abs(speed) < DEADZONE:
        _send_dome(d, u, 0.0)
        return

    _cancel_dome.clear()
    duration_ms = int(abs(speed) * RAMP_MAX_MS)
    steps       = max(3, duration_ms // RAMP_STEP_MS)
    interval    = duration_ms / 1000.0 / steps

    log.warning("SafeStop dome: %.2f → 0 in %dms", speed, duration_ms)

    def _ramp():
        for i in range(1, steps + 1):
            if _cancel_dome.is_set():
                return
            _send_dome(d, u, speed * (1.0 - i / steps))
            time.sleep(interval)
        _send_dome(d, u, 0.0)

    threading.Thread(target=_ramp, daemon=True, name="safe-stop-dome").start()


# ------------------------------------------------------------------
# Low-level helpers
# ------------------------------------------------------------------

def _send_drive(vesc, uart, left: float, right: float) -> None:
    try:
        if vesc:
            vesc.drive(left, right)
        elif uart:
            uart.send('M', f'{left:.3f},{right:.3f}')
    except Exception as e:
        log.error("SafeStop _send_drive: %s", e)


def _send_dome(dome, uart, speed: float) -> None:
    try:
        if dome:
            dome.turn(speed)
        elif uart:
            uart.send('D', f'{speed:.3f}')
    except Exception as e:
        log.error("SafeStop _send_dome: %s", e)
