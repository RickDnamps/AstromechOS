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
Diagnostics Blueprint — system logs, UART stats, slave ping.

  GET  /diagnostics/logs?filter=ALL|WARNING|ERROR  → last 50 master log lines
  GET  /diagnostics/stats                           → UART health + system metrics
  POST /diagnostics/ping_slave                      → HTTP round-trip to Slave port 5001
"""

import configparser
import re
import subprocess
import time
import logging
from flask import Blueprint, request, jsonify
import master.registry as reg
from master.api._admin_auth import require_admin
from master.app_watchdog import app_watchdog

log = logging.getLogger(__name__)

from shared.paths import MAIN_CFG as _MAIN_CFG, LOCAL_CFG as _LOCAL_CFG

diagnostics_bp = Blueprint('diagnostics', __name__)


def _slave_host() -> str:
    cfg = configparser.ConfigParser()
    cfg.read([_MAIN_CFG, _LOCAL_CFG])
    return cfg.get('slave', 'host', fallback='r2-slave.local')


@diagnostics_bp.get('/diagnostics/logs')
@require_admin
def diag_logs():
    """Last 50 lines of astromech-master journal, optionally filtered by severity.
    B-64 (audit 2026-05-15): admin-only. Journal lines can leak paths,
    MACs, IPs, serial numbers, and stack traces — not for guests."""
    # B-83 (audit 2026-05-15): tighter timeout (5s → 2s) so a stuck
    # journalctl doesn't pin a Flask worker thread. The 50-line read
    # finishes in <100ms on a healthy Pi; 2s covers the slow-disk case.
    # If a real outage drives journalctl beyond 2s, the user gets an
    # empty list and an error message rather than a hung tab.
    level = request.args.get('filter', 'ALL').upper()
    if level not in ('ALL', 'WARNING', 'ERROR'):
        level = 'ALL'   # B-64 reinforced: silent fallback on unknown filter
    cmd = ['journalctl', '-u', 'astromech-master', '-n', '50', '--no-pager', '--output=short-iso']
    if level == 'ERROR':
        cmd += ['--priority=err']
    elif level == 'WARNING':
        cmd += ['--priority=warning']
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
        lines = result.stdout.strip().splitlines()
        # Audit finding M-6 2026-05-15: defense-in-depth secret filter.
        # Admin-only endpoint AND no current log line includes
        # passwords today (verified by grep), but if a future driver
        # bug ever logs a config dump, redact before returning. Also
        # cap each line at 4KB so a misbehaving driver dumping data
        # can't balloon the response.
        _LINE_CAP = 4096
        _SECRET_RE = re.compile(
            r'(?i)(password|psk|x-admin-pw|secret|token|api[_-]?key)\s*[:=]\s*\S+',
        )
        cleaned = []
        for ln in lines:
            ln = _SECRET_RE.sub(r'\1=***REDACTED***', ln)
            if len(ln) > _LINE_CAP:
                ln = ln[:_LINE_CAP] + ' …[truncated]'
            cleaned.append(ln)
        return jsonify({'lines': cleaned, 'filter': level})
    except subprocess.TimeoutExpired:
        log.warning("journalctl timed out (>2s)")
        return jsonify({'lines': [], 'filter': level, 'error': 'journalctl timeout'}), 504
    except OSError as e:
        # Audit finding L-7 2026-05-15: str(e) on a ConnectionError /
        # FileNotFoundError leaks paths + LAN topology. Hard-code a
        # generic message + log the detail for operator debugging.
        log.warning("journalctl error: %s", e)
        return jsonify({'lines': [], 'filter': level, 'error': 'journalctl failed'}), 500


@diagnostics_bp.get('/diagnostics/stats')
@require_admin
def diag_stats():
    """UART health metrics from both Master and Slave."""
    slave_h = reg.slave_uart_health or {}
    uart    = reg.uart
    uart_serial = getattr(uart, '_serial', None)
    return jsonify({
        'master': {
            'uart_ready':  bool(uart_serial and uart_serial.is_open
                                and getattr(uart, '_running', False)),
            'crc_errors':  uart.crc_errors if uart else 0,
            'hb_age_ms':   round(app_watchdog.last_hb_age_ms),
        },
        'slave': {
            'reachable':   reg.slave_uart_health is not None,
            'health_pct':  slave_h.get('health_pct'),
            'total':       slave_h.get('total'),
            'errors':      slave_h.get('errors'),
            'window_s':    slave_h.get('window_s'),
            'cpu_temp':    slave_h.get('cpu_temp'),
            'cpu_pct':     slave_h.get('cpu_pct'),
        },
    })


@diagnostics_bp.post('/diagnostics/ping_slave')
@require_admin
def diag_ping_slave():
    """Measures HTTP round-trip time to Slave health server (port 5001)."""
    import requests as _http
    host = _slave_host()
    t0 = time.monotonic()
    try:
        r = _http.get(f'http://{host}:5001/uart_health', timeout=3)
        ms = round((time.monotonic() - t0) * 1000)
        if r.status_code == 200:
            return jsonify({'ok': True, 'ms': ms})
        return jsonify({'ok': False, 'ms': ms, 'error': f'HTTP {r.status_code}'})
    except Exception as e:
        ms = round((time.monotonic() - t0) * 1000)
        return jsonify({'ok': False, 'ms': ms, 'error': str(e)})


@diagnostics_bp.get('/diagnostics/uart_rtt')
@require_admin
def diag_uart_rtt():
    """UART round-trip stats for tuning body_servo_uart_lat.

    The heartbeat loop fires every 200ms and pairs each H send with its
    H:OK reply from the Slave. Stats are computed over a rolling window
    of the last 200 samples (≈40 seconds).

    Recommendation rule:
      The pyserial read loops on both sides use a 100ms timeout, which
      dominates the high-percentile RTT samples (when an ACK arrives just
      after a poll cycle, detection waits up to 100ms). The MEDIAN is the
      best estimator of steady-state physical latency.
        body_servo_uart_lat ≈ p50_ms / 2
      Clamped to [5..50]ms and rounded to the nearest 5ms for sane UX.
    """
    if not reg.uart:
        return jsonify({'error': 'UART not initialized'}), 503

    stats = reg.uart.get_rtt_stats()
    recommendation = None
    if stats['p50_ms'] is not None:
        # Use median to discount the 100ms read-timeout outliers; one-way
        # hop ≈ RTT/2; clamp+round to a stable, easy-to-reason-about value.
        one_way = stats['p50_ms'] / 2.0
        recommendation = max(5, min(50, int(round(one_way / 5.0) * 5)))

    return jsonify({
        **stats,
        'window_s': 40,
        'recommended_body_uart_lat_ms': recommendation,
        'current_body_uart_lat_ms': int(round(
            (reg.choreo._body_uart_lat * 1000) if reg.choreo else 25
        )),
    })


@diagnostics_bp.get('/diagnostics/i2c_scan')
@require_admin
def diag_i2c_scan():
    """W14 fix 2026-05-16: scan Master I2C bus and return detected addrs.
    Frontend uses this in the HATs panel ('SCAN I2C' button) so operator
    can detect physically-present HATs without SSH + i2cdetect.

    Runs i2cdetect -y 1 (Pi I2C bus 1), parses the grid output. Only
    addresses in 0x03-0x77 (i2cdetect default range) are returned.
    """
    import subprocess as _sp
    import re as _re
    try:
        r = _sp.run(['i2cdetect', '-y', '1'],
                    capture_output=True, text=True, timeout=5, check=False)
    except FileNotFoundError:
        return jsonify({'ok': False, 'error': 'i2cdetect not installed (apt install i2c-tools)'}), 503
    except _sp.TimeoutExpired:
        return jsonify({'ok': False, 'error': 'i2cdetect timeout (bus stuck?)'}), 503
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    if r.returncode != 0:
        err = (r.stderr or '').strip()[:200] or f'rc={r.returncode}'
        return jsonify({'ok': False, 'error': err}), 500
    # Parse the grid: lines like "40: 40 -- 42 -- -- -- -- -- ..."
    detected = []
    for line in r.stdout.splitlines():
        m = _re.match(r'^([0-9a-fA-F]{2}):\s*(.*)$', line)
        if not m:
            continue
        for cell in m.group(2).split():
            if _re.match(r'^[0-9a-fA-F]{2}$', cell):
                detected.append(int(cell, 16))
    return jsonify({'ok': True, 'detected': sorted(set(detected))})
