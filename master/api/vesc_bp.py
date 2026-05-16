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
Blueprint API VESC — Phase 2.
Exposes telemetry and configuration for the propulsion VESCs.

Endpoints:
  GET  /vesc/telemetry         → live telemetry for both VESCs
  POST /vesc/config            {"scale": 0.8}   → power scale (10-100%)
  POST /vesc/invert            {"side": "L"}    → invert motor L or R
  GET  /vesc/can/scan          → CAN bus scan via Slave (timeout 8s)
"""

import configparser
import os
import threading
from flask import Blueprint, request, jsonify
from master.api._admin_auth import require_admin
import master.registry as reg
from master.config.config_loader import write_cfg_atomic

from shared.paths import LOCAL_CFG as _LOCAL_CFG


# Serialize every read-modify-write of local.cfg [vesc]. Two concurrent
# POSTs (e.g. settings UI batched save: /vesc/config + /vesc/invert
# firing within the same Flask worker pool tick) would otherwise each
# read the on-disk state, mutate their own copy, and the second write
# would clobber the first. The lock holds for the brief duration of
# read+modify+atomic-write — typically <5ms — well below any user-
# perceptible latency.
#
# Audit finding H-2/H-4 2026-05-15: was using a vesc_bp-local
# threading.Lock(), violating the CLAUDE.md invariant "Toute nouvelle
# écriture de local.cfg DOIT importer et tenir settings_bp._cfg_write_lock."
# Concurrent /settings/config + /vesc/config would race on different
# sections of the SAME file. Now shares the single project-wide lock.


def _save_vesc_cfg(**kwargs) -> None:
    """Persist one or more keys to local.cfg [vesc] under the shared
    cross-blueprint cfg-write lock."""
    from master.api.settings_bp import _cfg_write_lock
    import logging as _logging
    _log = _logging.getLogger(__name__)
    with _cfg_write_lock:
        cfg = configparser.ConfigParser()
        if os.path.exists(_LOCAL_CFG):
            cfg.read(_LOCAL_CFG)
        if not cfg.has_section('vesc'):
            cfg.add_section('vesc')
        for k, v in kwargs.items():
            cfg.set('vesc', k, str(v))
        write_cfg_atomic(cfg, _LOCAL_CFG)
    # Audit finding L-3 2026-05-15: log every VESC config change so
    # journalctl carries an audit trail (who changed power_scale to
    # 0.3 at 14:32 — invaluable when debugging unexpected drive
    # behavior). Don't log the value itself if it's a secret, but
    # VESC settings aren't secrets.
    _log.info("VESC cfg saved: %s", kwargs)

vesc_bp = Blueprint('vesc', __name__, url_prefix='/vesc')

_FAULT_NAMES = {
    0:  'NONE',
    1:  'OVER_VOLTAGE',
    2:  'UNDER_VOLTAGE',
    3:  'DRV',
    4:  'ABS_OVER_CURRENT',
    5:  'OVER_TEMP_FET',
    6:  'OVER_TEMP_MOTOR',
    7:  'GATE_DRIVER_OVER_VOLTAGE',
    8:  'GATE_DRIVER_UNDER_VOLTAGE',
    9:  'MCU_UNDER_VOLTAGE',
    10: 'WATCHDOG_RESET',
    99: 'CAN_LOST',  # synthetic fault — Slave detected paired-side CAN failure
}


def _fault_str(code: int) -> str:
    return _FAULT_NAMES.get(code, f'FAULT_{code}')


@vesc_bp.get('/telemetry')
def get_telemetry():
    """Live telemetry for both VESCs + current power scale.

    B1 fix 2026-05-16: was using time.time() (wall-clock unix epoch
    ~1.7e9) to compare against telem['ts'] (time.monotonic — uptime
    seconds, typically <1e6). Difference always >>3s → endpoint
    ALWAYS returned L/R as null even when fresh telem was present
    → vescPanel always showed OFFLINE. Now delegates to canonical
    vesc_safety.fresh_telem_pair() (monotonic + 2s gate) per
    CLAUDE.md invariant 'JAMAIS lire reg.vesc_telem directement'.

    B4 fix 2026-05-16: also fixes the direct-read anti-pattern."""
    from master import vesc_safety
    pair  = vesc_safety.fresh_telem_pair(max_age=3.0)
    scale = getattr(reg, 'vesc_power_scale', 1.0)

    def _enrich(d):
        if d is None:
            return None
        return {**d, 'fault_str': _fault_str(d.get('fault', 0))}

    live_L = _enrich(pair.get('L'))
    live_R = _enrich(pair.get('R'))
    connected = (live_L is not None or live_R is not None)

    return jsonify({
        'connected':   connected,
        'power_scale': scale,
        'L': live_L,
        'R': live_R,
    })


@vesc_bp.post('/config')
@require_admin
def set_config():
    """Sets the power scale (0.1-1.0). Sent to Slave via UART VCFG:."""
    body = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    try:
        raw = float(body.get('scale', 1.0))
    except (TypeError, ValueError):
        return jsonify({'error': 'scale must be a float 0.1-1.0'}), 400
    # B-109 (audit 2026-05-15): NaN/Inf propagate through max/min — a
    # JSON body of {"scale": NaN} or {"scale": Infinity} would have
    # landed in local.cfg as 'nan' and the slave would interpret it
    # as 0 or fault. Explicit reject.
    import math
    if not math.isfinite(raw):
        return jsonify({'error': 'scale must be finite (no NaN/Inf)'}), 400
    scale = max(0.1, min(1.0, raw))

    reg.vesc_power_scale = scale
    _save_vesc_cfg(power_scale=f'{scale:.2f}')
    if reg.uart:
        reg.uart.send('VCFG', f'scale:{scale:.2f}')
    # Edge fix 2026-05-15: also push to the live Master VESC driver so
    # the in-memory clamp updates without a reboot. Previously
    # reg.vesc._speed_limit stayed at SPEED_LIMIT=1.0 until next boot,
    # which is why /status was reading stale 1.0 (see HW1 fix).
    if reg.vesc and hasattr(reg.vesc, 'set_speed_limit'):
        try: reg.vesc.set_speed_limit(scale)
        except Exception: pass
    return jsonify({'status': 'ok', 'power_scale': scale})


@vesc_bp.get('/config')
def get_config():
    """Returns current VESC configuration (power_scale + invert states + drive mode + bench_mode)."""
    return jsonify({
        'power_scale': getattr(reg, 'vesc_power_scale', 1.0),
        'invert_L':    getattr(reg, 'vesc_invert_L', False),
        'invert_R':    getattr(reg, 'vesc_invert_R', False),
        'duty_mode':   getattr(reg, 'vesc_duty_mode', False),
        'bench_mode':  getattr(reg, 'vesc_bench_mode', False),
    })


@vesc_bp.post('/bench_mode')
@require_admin
def set_bench_mode():
    """Enables/disables bench mode (bypasses VESC safety lock when no telem). Persisted to local.cfg.

    User-reported 2026-05-15: bench mode previously only bypassed the
    MASTER's safety gate (vesc_safety.is_drive_safe()). The SLAVE's
    vesc_driver.drive() has its own can_lost guard that refuses to
    send any drive command when one VESC is unreachable over CAN —
    which made bench-testing a single-VESC setup (e.g. only left USB)
    impossible. The Master now propagates bench mode to the slave via
    UART so vesc_driver can bypass its can_lost guard too.
    """
    body = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    # Audit finding L-4 2026-05-15: bool("false") is True in Python.
    # Use shared _coerce_bool helper (B2/B3 fix extended same pattern
    # to /mode and /invert in 2026-05-16 audit).
    enabled = _coerce_bool(body.get('enabled', False))
    reg.vesc_bench_mode = enabled
    _save_vesc_cfg(bench_mode='1' if enabled else '0')
    # Propagate to slave so vesc_driver.drive() can bypass _can_lost.
    if reg.uart:
        reg.uart.send('VCFG', f'bench:{"1" if enabled else "0"}')
    return jsonify({'status': 'ok', 'bench_mode': enabled})


def _coerce_bool(raw) -> bool:
    """B2/B3 fix 2026-05-16: parity with bench_mode L-4 — bool('false')
    is True (non-empty string). Accept genuine bools + common string
    forms. Misbehaving form/script POSTing {'duty':'false'} otherwise
    silently flipped to DUTY mode (dangerous open-loop direct PWM)."""
    if isinstance(raw, str):
        return raw.strip().lower() in ('1', 'true', 'yes', 'on')
    return bool(raw)


@vesc_bp.post('/mode')
@require_admin
def set_mode():
    """Switches drive mode. Body: {"duty": true/false}. Not persisted — resets on reboot."""
    body = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    duty = _coerce_bool(body.get('duty', False))
    reg.vesc_duty_mode = duty
    if reg.uart:
        reg.uart.send('VCFG', f'mode:{"duty" if duty else "rpm"}')
    return jsonify({'status': 'ok', 'duty_mode': duty})


@vesc_bp.post('/invert')
@require_admin
def invert_motor():
    """
    Sets motor direction. Body: {"side": "L", "state": true/false}.
    State is persisted to local.cfg and sent to Slave via UART VINV:L:1.
    """
    body = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    side = body.get('side', '').upper()
    if side not in ('L', 'R'):
        return jsonify({'error': 'side must be "L" or "R"'}), 400
    state = _coerce_bool(body.get('state', False))

    if side == 'L':
        reg.vesc_invert_L = state
    else:
        reg.vesc_invert_R = state

    _save_vesc_cfg(**{f'invert_{side.lower()}': '1' if state else '0'})

    if reg.uart:
        reg.uart.send('VINV', f'{side}:{"1" if state else "0"}')

    return jsonify({'status': 'ok', 'side': side, 'state': state})


@vesc_bp.get('/can/scan')
@require_admin
def can_scan():
    """
    Starts a CAN bus scan via UART → Slave → VESC 1 USB.
    Slave replies with CANFOUND:id1,id2 or CANFOUND:ERR.
    Timeout 8s — returns {'ids': [...], 'count': N}.
    """
    if not reg.uart:
        return jsonify({'error': 'UART not available'}), 503

    # Reset the previous scan state
    reg.vesc_can_scan_result = None
    reg.vesc_can_scan_event.clear()

    # Send the scan command to the Slave
    reg.uart.send('CANSCAN', 'start')

    # Wait for the response (max 8s — scan 11 IDs × ~0.12s + margin)
    got = reg.vesc_can_scan_event.wait(timeout=8.0)
    if not got:
        return jsonify({'error': 'Timeout — Slave not available or VESCs not connected via USB'}), 504

    result = reg.vesc_can_scan_result
    if result is None:
        return jsonify({'error': 'Scan failed — VescDriver not ready (Phase 2 not activated?)'}), 500

    return jsonify({'ids': result, 'count': len(result)})
