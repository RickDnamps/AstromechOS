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


def _snapshot():
    """Capture (telem_dict, bench_mode, now) atomically.

    `reg.vesc_telem` is replaced wholesale by the TL/TR UART callbacks
    (`reg.vesc_telem['L'] = {...}`), but is_drive_safe()/block_reason()
    were previously doing TWO independent `getattr(reg, 'vesc_telem')`
    lookups (one per side). Between the two lookups, the callback can
    swap one side's dict — leaving `is_drive_safe` and `block_reason`
    reading inconsistent state and disagreeing about why drive was
    blocked. The snapshot captures both side references at the same
    moment so every downstream check sees a coherent view.
    """
    telem = getattr(reg, 'vesc_telem', None) or {}
    return {
        'L':     telem.get('L'),
        'R':     telem.get('R'),
        'bench': bool(getattr(reg, 'vesc_bench_mode', False)),
        'now':   time.time(),
    }


def _side_ok_snap(snap: dict, side: str, max_age: float) -> bool:
    telem = snap[side]
    if telem is None:
        return False
    if snap['now'] - telem.get('ts', 0) > max_age:
        return False
    return telem.get('fault', 0) == 0


def is_drive_safe(max_age: float = _DEFAULT_MAX_AGE) -> bool:
    """True if drive is allowed.

    Rules:
      - bench_mode ON  → always True (developer override).
      - bench_mode OFF → both VESC sides must have telemetry younger than
        max_age and a fault code of 0.
      - Missing telemetry (None) is treated as unsafe in non-bench mode.
    """
    snap = _snapshot()
    if snap['bench']:
        return True
    return _side_ok_snap(snap, 'L', max_age) and _side_ok_snap(snap, 'R', max_age)


def block_reason(max_age: float = _DEFAULT_MAX_AGE) -> str | None:
    """Returns a stable token describing why drive is blocked, or None if safe.

    Tokens:
      vesc_l_offline / vesc_r_offline   no telemetry ever received
      vesc_l_stale   / vesc_r_stale     telemetry older than max_age
      vesc_l_fault   / vesc_r_fault     non-zero fault code
    """
    snap = _snapshot()
    if snap['bench']:
        return None
    for side in ('L', 'R'):
        telem = snap[side]
        if telem is None:
            return f'vesc_{side.lower()}_offline'
        if snap['now'] - telem.get('ts', 0) > max_age:
            return f'vesc_{side.lower()}_stale'
        if telem.get('fault', 0) != 0:
            return f'vesc_{side.lower()}_fault'
    return None


def status(max_age: float = _DEFAULT_MAX_AGE) -> tuple[bool, str | None]:
    """Single-snapshot atomic check: returns (is_safe, reason_or_None).

    Prefer this over calling is_drive_safe() then block_reason() — the
    two-call pattern can race against the TL/TR callback and produce
    `safe=False` with `reason=None` (or vice-versa). Callers that need
    BOTH values should use this helper.
    """
    snap = _snapshot()
    if snap['bench']:
        return True, None
    for side in ('L', 'R'):
        telem = snap[side]
        if telem is None:
            return False, f'vesc_{side.lower()}_offline'
        if snap['now'] - telem.get('ts', 0) > max_age:
            return False, f'vesc_{side.lower()}_stale'
        if telem.get('fault', 0) != 0:
            return False, f'vesc_{side.lower()}_fault'
    return True, None


# Legacy alias kept for callers that haven't migrated to the snapshot API.
# New code should call status() or _snapshot() + _side_ok_snap() directly.
def _side_ok(side: str, max_age: float) -> bool:
    return _side_ok_snap(_snapshot(), side, max_age)
