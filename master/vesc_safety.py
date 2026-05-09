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
# ============================================================
"""
Single source of truth for VESC drive safety.

Bench mode bypasses all checks (developer test mode without VESC hardware).
Otherwise drive is allowed only if BOTH sides have fresh, fault-free telemetry.

Used by every code path that can command propulsion:
  - master/api/motion_bp.py        (web/Android joystick)
  - master/api/status_bp.py        (UI status pill)
  - master/drivers/bt_controller_driver.py  (Bluetooth gamepad)
  - master/choreo_player.py        (choreography drive blocks)
"""

import time
import master.registry as reg


_DEFAULT_MAX_AGE = 2.0  # seconds — telemetry older than this counts as stale


def is_drive_safe(max_age: float = _DEFAULT_MAX_AGE) -> bool:
    """True if drive is allowed.

    Rules:
      - bench_mode ON  → always True (developer override).
      - bench_mode OFF → both VESC sides must have telemetry younger than
        max_age and a fault code of 0.
      - Missing telemetry (None) is treated as unsafe in non-bench mode.
    """
    if bool(getattr(reg, 'vesc_bench_mode', False)):
        return True
    return _side_ok('L', max_age) and _side_ok('R', max_age)


def block_reason(max_age: float = _DEFAULT_MAX_AGE) -> str | None:
    """Returns a stable token describing why drive is blocked, or None if safe.

    Tokens:
      vesc_l_offline / vesc_r_offline   no telemetry ever received
      vesc_l_stale   / vesc_r_stale     telemetry older than max_age
      vesc_l_fault   / vesc_r_fault     non-zero fault code
    """
    if bool(getattr(reg, 'vesc_bench_mode', False)):
        return None
    for side in ('L', 'R'):
        telem = (getattr(reg, 'vesc_telem', {}) or {}).get(side)
        if telem is None:
            return f'vesc_{side.lower()}_offline'
        if time.time() - telem.get('ts', 0) > max_age:
            return f'vesc_{side.lower()}_stale'
        if telem.get('fault', 0) != 0:
            return f'vesc_{side.lower()}_fault'
    return None


def _side_ok(side: str, max_age: float) -> bool:
    telem = (getattr(reg, 'vesc_telem', {}) or {}).get(side)
    if telem is None:
        return False
    if time.time() - telem.get('ts', 0) > max_age:
        return False
    return telem.get('fault', 0) == 0
