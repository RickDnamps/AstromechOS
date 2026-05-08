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
import subprocess
import time
import logging
from flask import Blueprint, request, jsonify
import master.registry as reg
from master.app_watchdog import app_watchdog

log = logging.getLogger(__name__)

from shared.paths import MAIN_CFG as _MAIN_CFG, LOCAL_CFG as _LOCAL_CFG

diagnostics_bp = Blueprint('diagnostics', __name__)


def _slave_host() -> str:
    cfg = configparser.ConfigParser()
    cfg.read([_MAIN_CFG, _LOCAL_CFG])
    return cfg.get('slave', 'host', fallback='r2-slave.local')


@diagnostics_bp.get('/diagnostics/logs')
def diag_logs():
    """Last 50 lines of r2d2-master journal, optionally filtered by severity."""
    level = request.args.get('filter', 'ALL').upper()
    cmd = ['journalctl', '-u', 'r2d2-master', '-n', '50', '--no-pager', '--output=short-iso']
    if level == 'ERROR':
        cmd += ['--priority=err']
    elif level == 'WARNING':
        cmd += ['--priority=warning']
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        lines = result.stdout.strip().splitlines()
        return jsonify({'lines': lines, 'filter': level})
    except Exception as e:
        log.warning("journalctl error: %s", e)
        return jsonify({'lines': [], 'filter': level, 'error': str(e)}), 500


@diagnostics_bp.get('/diagnostics/stats')
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
