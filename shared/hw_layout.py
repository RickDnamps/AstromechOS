"""shared/hw_layout.py — driver-side reader for `hw_layout.json`.

The detection script (`scripts/detect_hats.py`) OBSERVES the I2C bus
and writes a JSON record. This module is the DECISION-side companion:
master/slave drivers import it at startup, look up their target HAT
address, and pick one of three states per HAT:

    READY     — HAT present, signature clean, no collision
                → driver initialises normally
    DEGRADED  — no JSON yet, or HAT absent from JSON
                → driver logs WARNING + suspends I2C calls for THIS
                  HAT only (other subsystems boot normally — the
                  robot must not brick on a single missing HAT)
    CRITICAL  — JSON flagged this address as ADDRESS_COLLISION
                → driver REFUSES to initialise the HAT and logs
                  CRITICAL with explicit jumper-troubleshooting
                  guidance. Operating against a contested bus
                  produces unpredictable hardware behaviour (PWM
                  to motor inputs, etc.) — refusal is safer than
                  best-effort.

Strict separation of concerns: this module reads JSON; it never
touches I2C, never spawns threads, never logs ERROR/WARN on its own
behalf (callers do their own logging — we just return state). Tested
in isolation by `scripts/test_hw_layout.py`.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger('hw_layout')

# Resolved at import time; tests override via H._REPO = Path(...).
_REPO = Path(__file__).resolve().parent.parent

# Three possible per-HAT states (constants, used by callers in match).
STATUS_READY    = 'ready'
STATUS_DEGRADED = 'degraded'
STATUS_CRITICAL = 'critical'


def _layout_path_for(role: str) -> Path:
    """Return the on-disk JSON path for <role>. master/slave only.
    Default to master path for any unknown role string (defensive)."""
    sub = 'slave' if role == 'slave' else 'master'
    return _REPO / sub / 'config' / 'hw_layout.json'


def load_for(role: str) -> Optional[dict]:
    """Load and validate hw_layout.json for <role>.

    Returns the parsed dict on success, OR None when:
      - the file does not exist (no scan ran yet — DEGRADED globally)
      - the file is unreadable / malformed JSON
      - the JSON is missing the load-bearing `hats` key

    Never raises. Callers treat None as "no layout known" — the
    fallback behaviour is preserved-as-today (driver uses the cfg
    addresses and tries to init; existing exception handler still
    works as the last line of defence)."""
    p = _layout_path_for(role)
    if not p.is_file():
        log.info("hw_layout: no file at %s (driver will use cfg only)", p)
        return None
    try:
        with p.open('r', encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        log.warning("hw_layout: %s unreadable (%s) — ignoring", p, e)
        return None
    if not isinstance(data, dict) or 'hats' not in data \
            or not isinstance(data['hats'], list):
        log.warning("hw_layout: %s missing 'hats' list — ignoring", p)
        return None
    return data


def _parse_addr(raw: Any) -> Optional[int]:
    """Parse a '0x40' / 64 / etc. into an int in [0x40..0x77]."""
    try:
        if isinstance(raw, int):
            n = raw
        elif isinstance(raw, str):
            s = raw.strip()
            n = int(s, 16) if s.startswith(('0x', '0X')) else int(s)
        else:
            return None
    except (ValueError, TypeError):
        return None
    if 0x40 <= n <= 0x77:
        return n
    return None


def detected_addresses(layout: Optional[dict]) -> set[int]:
    """Set of addresses whose HAT was confidently detected (NOT
    collision, NOT absent). Used by the driver to decide whether
    its cfg-target HAT is healthy enough to initialise."""
    if not layout:
        return set()
    out: set[int] = set()
    for h in layout.get('hats', []):
        if not isinstance(h, dict):
            continue
        if h.get('collision') or h.get('chip') == 'collision':
            continue
        addr = _parse_addr(h.get('addr'))
        if addr is not None:
            out.add(addr)
    return out


def collision_addresses(layout: Optional[dict]) -> set[int]:
    """Set of addresses flagged ADDRESS_COLLISION by the detector.
    A driver targeting any of these MUST refuse to initialise."""
    if not layout:
        return set()
    out: set[int] = set()
    for h in layout.get('hats', []):
        if not isinstance(h, dict):
            continue
        if h.get('collision') or h.get('chip') == 'collision':
            addr = _parse_addr(h.get('addr'))
            if addr is not None:
                out.add(addr)
    return out


def worst_status(layout: Optional[dict]) -> str:
    """Return the highest-priority status across all HATs in <layout>.

    Priority: STATUS_CRITICAL > STATUS_DEGRADED > STATUS_READY.

    Used by hats_bp's /hats/layout aggregator + /status enrichment to
    present a single "is the hardware healthy?" badge in the UI.
    Empty / missing layout → STATUS_DEGRADED (no detection run yet).

    Single helper so the master's hats_bp and the cockpit poller never
    re-implement the priority logic — guaranteed consistent ranking
    across the codebase."""
    if not layout:
        return STATUS_DEGRADED
    hats = layout.get('hats') or []
    if not hats:
        # JSON exists but reports no HATs → the bus is empty, which is
        # degraded (no hardware to operate) — distinct from collision.
        return STATUS_DEGRADED
    has_critical = False
    has_degraded = False
    has_ready    = False
    for h in hats:
        if not isinstance(h, dict):
            continue
        if h.get('collision') or h.get('chip') == 'collision':
            has_critical = True
        elif h.get('chip') == 'pca9685':
            has_ready = True
        else:
            # 'unknown' / 'absent' / anything else → degraded.
            has_degraded = True
    if has_critical:
        return STATUS_CRITICAL
    if has_degraded:
        return STATUS_DEGRADED
    if has_ready:
        return STATUS_READY
    return STATUS_DEGRADED


def hat_status(layout: Optional[dict], addr: int) -> str:
    """Return STATUS_READY | STATUS_DEGRADED | STATUS_CRITICAL for <addr>.

    Decision matrix:
      layout=None         → DEGRADED (no scan run yet; driver will
                                       try cfg + degrade on failure)
      addr in collisions  → CRITICAL (refuse net)
      addr in detected    → READY    (initialise normally)
      otherwise           → DEGRADED (HAT absent from JSON)
    """
    if layout is None:
        return STATUS_DEGRADED
    if addr in collision_addresses(layout):
        return STATUS_CRITICAL
    if addr in detected_addresses(layout):
        return STATUS_READY
    return STATUS_DEGRADED


def critical_log_message(addr: int) -> str:
    """Canonical CRITICAL message every driver uses on a collision.

    Same wording across master + slave + future drivers so the
    operator can grep journalctl on either Pi and get a stable
    troubleshooting string. Single source of truth → updates only
    have to happen here."""
    return (
        f"CRITICAL: I2C Address Conflict at 0x{addr:02X}. "
        f"Check hardware jumpers (A0/A1/A2 — solder pads on the back "
        f"of the PCA9685 board). "
        f"The driver will NOT operate any HAT on 0x{addr:02X} until "
        f"the conflict is resolved. "
        f"See docs/DEPLOY_SECURITY.md §4.5 for jumper truth table."
    )


def degraded_log_message(addr: int) -> str:
    """Canonical WARNING message for a HAT that the cfg expects
    but the scan did NOT detect. Driver enters DEGRADED mode for
    this HAT — other HATs continue normally."""
    return (
        f"WARNING: HAT @ 0x{addr:02X} missing — DEGRADED mode active "
        f"for this HAT. Other subsystems unaffected. "
        f"Re-run `python3 scripts/detect_hats.py` after fixing the "
        f"hardware (check power, ribbon cable, I2C wiring)."
    )
