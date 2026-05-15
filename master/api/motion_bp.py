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
Flask blueprint — Motion API.

Controls propulsion (VESCs) and dome rotation. Every motion command
passes through the safety chain:
  - E-STOP gate          (reg.estop_active)
  - Stow-in-progress gate (reg.stow_in_progress, set during estop_reset)
  - Safety-ramp gate     (safe_stop._drive_ramp_active / _dome_ramp_active)
  - Child Lock gate      (reg.lock_mode == 2)
  - VESC safety gate     (vesc_safety.is_drive_safe — drive only)
  - Kids speed cap       (reg.kids_speed_limit when lock_mode == 1)
  - Watchdog feed        (motion_watchdog.feed_drive/dome)

Propulsion endpoints:
  POST /motion/drive    {"left": float, "right": float}    differential
  POST /motion/arcade   {"throttle": float, "steering": float} normalised
  POST /motion/stop                                          explicit stop
  GET  /motion/state                                         current state

Dome endpoints:
  POST /motion/dome/turn    {"speed": float}    [-1, 1] turn speed
  POST /motion/dome/stop                         explicit dome stop
  POST /motion/dome/random  {"enabled": bool}    random dome mode
  GET  /motion/dome/state                        current dome state

Watchdog: if no /motion/drive or /motion/dome/turn is received for 800 ms
while the robot is in motion, MotionWatchdog launches the anti-tip
safety ramp via safe_stop. The ramp is uncancellable (B-2/B-12).
"""

import math
import time
from flask import Blueprint, request, jsonify
import master.registry as reg
from master.motion_watchdog import motion_watchdog
from master.safe_stop import cancel_ramp, is_drive_ramp_active, is_dome_ramp_active
from master.vesc_safety import is_drive_safe, block_reason

motion_bp = Blueprint('motion', __name__, url_prefix='/motion')


def _clamp(val: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, val))


def _safe_float(val, default: float = 0.0) -> float:
    """Parse a JSON-body float, rejecting NaN / Inf / non-numeric.

    Without this, `float('NaN')` returns nan, _clamp(nan) returns nan,
    and the slave receives M:nan,nan → set_rpm_direct(int(nan*50000))
    raises ValueError inside the UART callback, potentially killing
    the listener thread or producing log spam at 60 Hz.
    """
    try:
        f = float(val)
    except (TypeError, ValueError):
        return default
    if math.isnan(f) or math.isinf(f):
        return default
    return f


def _drive_gate():
    """Centralised refuse-motion check for the propulsion endpoints.

    Returns a Flask response tuple to short-circuit with, or None if
    motion is allowed. Order matters — estop is the most severe so it
    short-circuits first.
    """
    if reg.estop_active:
        return jsonify({'status': 'blocked', 'reason': 'estop'}), 403
    if getattr(reg, 'stow_in_progress', False):
        return jsonify({'status': 'blocked', 'reason': 'stow_in_progress'}), 503
    if reg.choreo and reg.choreo.is_playing():
        # Per-axis gate: a choreo only blocks PROPULSION when its
        # 'propulsion' track has events. A panel/sound/light-only
        # choreo (e.g. Angry → dome panels + sounds) leaves the
        # propulsion joystick free so the operator can drive around
        # while the show plays. User-refined 2026-05-15.
        st = reg.choreo.get_status() or {}
        if st.get('uses_propulsion'):
            return jsonify({'status': 'blocked', 'reason': 'choreo_active'}), 503
    if is_drive_ramp_active():
        return jsonify({'status': 'blocked', 'reason': 'safety_ramp'}), 503
    if reg.lock_mode == 2:
        return jsonify({'status': 'blocked', 'reason': 'child_lock'}), 403
    if not is_drive_safe():
        return jsonify({'status': 'blocked', 'reason': block_reason() or 'vesc_unsafe'}), 503
    return None


def _dome_gate():
    """Same as _drive_gate but for dome rotation. Skips the VESC safety
    check (dome motor is independent of propulsion VESCs) and uses the
    dome-specific safety ramp flag."""
    if reg.estop_active:
        return jsonify({'status': 'blocked', 'reason': 'estop'}), 403
    if getattr(reg, 'stow_in_progress', False):
        return jsonify({'status': 'blocked', 'reason': 'stow_in_progress'}), 503
    if reg.choreo and reg.choreo.is_playing():
        # Same per-axis logic for dome rotation. Note: only HORIZONTAL
        # dome rotation is gated. Vertical (Y-axis) is reserved for
        # the camera control planned in v2 — frontend already routes
        # Y to a different endpoint, so this gate is correct.
        st = reg.choreo.get_status() or {}
        if st.get('uses_dome'):
            return jsonify({'status': 'blocked', 'reason': 'choreo_active'}), 503
    if is_dome_ramp_active():
        return jsonify({'status': 'blocked', 'reason': 'safety_ramp'}), 503
    if reg.lock_mode == 2:
        return jsonify({'status': 'blocked', 'reason': 'child_lock'}), 403
    return None


# ------------------------------------------------------------------
# Propulsion
# ------------------------------------------------------------------

def _kids_cap(left: float, right: float) -> tuple:
    """Apply Kids Mode speed cap (B-25). When lock_mode==1, scale both
    sides by kids_speed_limit so the kid drives the robot slowly. This
    was previously only enforced on the BT controller path —
    /motion/drive and /motion/arcade ran at full speed regardless of
    Kids mode, which contradicted the three-tier lock model documented
    on lockMgr._applyMode."""
    if getattr(reg, 'lock_mode', 0) == 1:
        # Audit finding Motion H-bonus 2026-05-15: re-clamp cap at
        # read time. status_bp validates kids_speed_limit at write,
        # but a poisoned registry value (e.g. set to 2.0 by a buggy
        # plug-in) would silently make Kids Mode FASTER than normal.
        # Defense in depth — also math.isfinite to reject NaN/Inf.
        cap = float(getattr(reg, 'kids_speed_limit', 0.5))
        if not math.isfinite(cap):
            cap = 0.5
        cap = max(0.0, min(1.0, cap))
        return left * cap, right * cap
    return left, right


@motion_bp.post('/drive')
def drive():
    """Differential drive. Body: {"left": float, "right": float}"""
    blocked = _drive_gate()
    if blocked is not None:
        return blocked

    body  = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    reg.web_last_drive_t = time.monotonic()
    left  = _clamp(_safe_float(body.get('left',  0.0)))
    right = _clamp(_safe_float(body.get('right', 0.0)))

    left, right = _kids_cap(left, right)

    cancel_ramp()                             # cancel any ongoing ramp-down
    motion_watchdog.feed_drive(left, right)   # feed the watchdog

    if reg.vesc:
        reg.vesc.drive(left, right)
    elif reg.uart:
        reg.uart.send('M', f'{left:.3f},{right:.3f}')
    return jsonify({'status': 'ok', 'left': left, 'right': right})


@motion_bp.post('/arcade')
def arcade():
    """Arcade drive. Body: {"throttle": float, "steering": float}"""
    blocked = _drive_gate()
    if blocked is not None:
        return blocked

    body     = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    reg.web_last_drive_t = time.monotonic()
    throttle = _clamp(_safe_float(body.get('throttle', 0.0)))
    steering = _clamp(_safe_float(body.get('steering', 0.0)))

    # B-20: normalize left/right ratio when the unclamped sum exceeds 1.
    # Old `_clamp(throttle + steering)` truncated the larger side and
    # left the smaller untouched — at the edges the robot pivoted harder
    # than the user asked for. Mirror what VescDriver.arcade_drive does:
    # divide both by max(abs, 1) so the ratio between sides is preserved.
    raw_l = throttle + steering
    raw_r = throttle - steering
    max_v = max(abs(raw_l), abs(raw_r), 1.0)
    left  = raw_l / max_v
    right = raw_r / max_v

    left, right = _kids_cap(left, right)

    cancel_ramp()
    motion_watchdog.feed_drive(left, right)

    if reg.vesc:
        # Pass the already-normalised+capped left/right directly so the
        # driver doesn't re-derive them from throttle/steering and we keep
        # a single ratio + cap pipeline.
        reg.vesc.drive(left, right)
    elif reg.uart:
        reg.uart.send('M', f'{left:.3f},{right:.3f}')
    return jsonify({'status': 'ok', 'throttle': throttle, 'steering': steering, 'left': left, 'right': right})


@motion_bp.post('/stop')
def stop_motion():
    """Stop propulsion."""
    motion_watchdog.clear_drive()             # explicit stop — not a timeout
    if reg.vesc:
        reg.vesc.stop()
    elif reg.uart:
        reg.uart.send('M', '0.000,0.000')
    return jsonify({'status': 'ok'})


@motion_bp.get('/state')
def motion_state():
    """Current propulsion state."""
    state = reg.vesc.state if reg.vesc else {}
    return jsonify(state)


# ------------------------------------------------------------------
# Dome
# ------------------------------------------------------------------

@motion_bp.post('/dome/turn')
def dome_turn():
    """Dome rotation. Body: {"speed": float}"""
    blocked = _dome_gate()
    if blocked is not None:
        return blocked

    body  = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    reg.web_last_dome_t = time.monotonic()
    speed = _clamp(_safe_float(body.get('speed', 0.0)))

    # Audit finding Safety H-2 2026-05-15: parity with /motion/drive
    # which calls cancel_ramp() to wake a stalled dome ramp on
    # operator resume. Without this, a re-press during the 400ms
    # ramp was silently 503'd (gate refuses while ramp active) and
    # the operator's intent was dropped.
    cancel_ramp()
    motion_watchdog.feed_dome(speed)          # feed the watchdog

    if reg.dome:
        reg.dome.turn(speed)
    elif reg.uart:
        reg.uart.send('D', f'{speed:.3f}')
    return jsonify({'status': 'ok', 'speed': speed})


@motion_bp.post('/dome/stop')
def dome_stop():
    """Stop dome rotation."""
    motion_watchdog.clear_dome()
    if reg.dome:
        reg.dome.stop()
    elif reg.uart:
        reg.uart.send('D', '0.000')
    return jsonify({'status': 'ok'})


@motion_bp.post('/dome/random')
@require_admin
def dome_random():
    """Dome random mode. Body: {"enabled": bool}.
    Audit finding L-5 2026-05-15: enabling random dome motion now
    runs through _dome_gate() — was bypassing E-STOP / stow /
    choreo lockout entirely. Disabling is always allowed (operator
    needs an off-switch even from a blocked state)."""
    body    = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    enabled = bool(body.get('enabled', False))
    if enabled:
        gate = _dome_gate()
        if gate is not None:
            return gate
    else:
        motion_watchdog.clear_dome()
    if reg.dome:
        reg.dome.set_random(enabled)
    return jsonify({'status': 'ok', 'random': enabled})


@motion_bp.get('/dome/state')
def dome_state():
    """Current dome state."""
    state = reg.dome.state if reg.dome else {}
    return jsonify(state)
