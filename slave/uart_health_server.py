# ============================================================
#  ██████╗ ██████╗       ██████╗ ██████╗
#  ██╔══██╗╚════██╗      ██╔══██╗╚════██╗
#  ██████╔╝ █████╔╝      ██║  ██║ █████╔╝
#  ██╔══██╗██╔═══╝       ██║  ██║██╔═══╝
#  ██║  ██║███████╗      ██████╔╝███████╗
#  ╚═╝  ╚═╝╚══════╝      ╚═════╝ ╚══════╝
#
#  R2-D2 Control System — Distributed Robot Controller
# ============================================================
#  Copyright (C) 2025 RickDnamps
#  https://github.com/RickDnamps/R2D2_Control
#
#  This file is part of R2D2_Control.
#
#  R2D2_Control is free software: you can redistribute it
#  and/or modify it under the terms of the GNU General
#  Public License as published by the Free Software
#  Foundation, either version 2 of the License, or
#  (at your option) any later version.
#
#  R2D2_Control is distributed in the hope that it will be
#  useful, but WITHOUT ANY WARRANTY; without even the implied
#  warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
#  PURPOSE. See the GNU General Public License for details.
#
#  You should have received a copy of the GNU GPL along with
#  R2D2_Control. If not, see <https://www.gnu.org/licenses/>.
# ============================================================
"""
Lightweight HTTP server — Slave health stats + BT speaker management.
Port 5001

  GET  /uart_health          → UART stats JSON
  GET  /audio/bt/status      → BT devices + connection state
  POST /audio/bt/scan        → start 8-second BT scan (async)
  POST /audio/bt/pair        → {"mac": "AA:BB:CC:DD:EE:FF"}
  POST /audio/bt/connect     → {"mac": "..."} connect + set PA default sink
  POST /audio/bt/disconnect  → {"mac": "..."}
  POST /audio/bt/remove      → {"mac": "..."}
"""

import json
import logging
import re
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

log = logging.getLogger(__name__)

_DEFAULT_PORT = 5001

# BT scan state (module-level — shared across requests)
_scan_active = False
_bt_cache: list = []   # devices discovered during last scan


# ── BT helpers ────────────────────────────────────────────────────────────────

def _bt_run(cmd: list, timeout: float = 10.0) -> tuple[bool, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    except Exception as e:
        return False, str(e)


def _bt_scan_worker(duration: float = 8.0) -> None:
    global _scan_active, _bt_cache
    _scan_active = True
    try:
        p = subprocess.Popen(
            ['bluetoothctl'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True,
        )
        p.stdin.write('scan on\n'); p.stdin.flush()
        time.sleep(duration)
        p.stdin.write('devices\nscan off\nquit\n'); p.stdin.flush()
        out, _ = p.communicate(timeout=5)
        seen: set = set()
        devs: list = []
        for line in out.splitlines():
            m = re.search(r'Device\s+([0-9A-Fa-f:]{17})\s+(.*)', line)
            if m:
                mac = m.group(1).upper()
                if mac not in seen:
                    seen.add(mac)
                    devs.append({'mac': mac, 'name': m.group(2).strip()})
        _bt_cache = devs
    except Exception as e:
        log.warning('BT scan error: %s', e)
    finally:
        _scan_active = False


def _bt_status() -> dict:
    # Paired devices with connection info
    _, out = _bt_run(['bluetoothctl', 'devices', 'Paired'])
    paired: list = []
    for line in out.splitlines():
        m = re.search(r'Device\s+([0-9A-Fa-f:]{17})\s+(.*)', line)
        if m:
            mac = m.group(1).upper()
            _, info = _bt_run(['bluetoothctl', 'info', mac])
            paired.append({
                'mac':       mac,
                'name':      m.group(2).strip(),
                'connected': 'Connected: yes' in info,
                'trusted':   'Trusted: yes' in info,
            })

    # Discovered but not yet paired (from last scan)
    paired_macs = {d['mac'] for d in paired}
    discovered = [d for d in _bt_cache if d['mac'] not in paired_macs]

    # Default pulseaudio sink
    ok, sink = _bt_run(['pactl', 'get-default-sink'], timeout=3)
    default_sink = sink.strip() if ok else None

    return {
        'scanning':     _scan_active,
        'paired':       paired,
        'discovered':   discovered,
        'default_sink': default_sink,
    }


# ── HTTP handler ──────────────────────────────────────────────────────────────

class _HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path == '/uart_health':
            self._json(self.server.uart_listener.get_health_stats())
        elif self.path == '/audio/bt/status':
            self._json(_bt_status())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length).decode()) if length else {}
        mac = (body.get('mac') or '').strip().upper()

        if self.path == '/audio/bt/scan':
            global _scan_active
            if _scan_active:
                self._json({'status': 'already_scanning'})
            else:
                threading.Thread(target=_bt_scan_worker, daemon=True).start()
                self._json({'status': 'scanning'})

        elif self.path == '/audio/bt/pair':
            if not mac:
                self._json({'ok': False, 'error': 'mac required'}, 400)
                return
            ok, out = _bt_run(['bluetoothctl', 'pair', mac])
            _bt_run(['bluetoothctl', 'trust', mac])   # auto-trust for convenience
            self._json({'ok': ok, 'output': out})

        elif self.path == '/audio/bt/connect':
            if not mac:
                self._json({'ok': False, 'error': 'mac required'}, 400)
                return
            ok, out = _bt_run(['bluetoothctl', 'connect', mac])
            if ok:
                # Set as default pulseaudio A2DP sink
                pa_sink = 'bluez_sink.' + mac.replace(':', '_') + '.a2dp_sink'
                _bt_run(['pactl', 'set-default-sink', pa_sink], timeout=3)
            self._json({'ok': ok, 'output': out})

        elif self.path == '/audio/bt/disconnect':
            if not mac:
                self._json({'ok': False, 'error': 'mac required'}, 400)
                return
            ok, out = _bt_run(['bluetoothctl', 'disconnect', mac])
            self._json({'ok': ok, 'output': out})

        elif self.path == '/audio/bt/remove':
            if not mac:
                self._json({'ok': False, 'error': 'mac required'}, 400)
                return
            ok, out = _bt_run(['bluetoothctl', 'remove', mac])
            self._json({'ok': ok, 'output': out})

        else:
            self.send_response(404)
            self.end_headers()

    def _json(self, data: dict, code: int = 200) -> None:
        body = json.dumps(data).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass   # suppress access logs


def start_health_server(uart_listener, port: int = _DEFAULT_PORT) -> None:
    """Start the HTTP health + BT server as a daemon thread (non-blocking)."""
    server = HTTPServer(('', port), _HealthHandler)
    server.uart_listener = uart_listener
    threading.Thread(
        target=server.serve_forever,
        name='uart-health-http',
        daemon=True,
    ).start()
    log.info("UARTHealthServer started on port %d", port)
