# ============================================================
#  ██████╗ ██████╗       ██████╗ ██████╗
#  ██╔══██╗╚════██╗      ██╔══██╗╚════██╗
#  ██████╔╝ █████╔╝      ██║  ██║ █████╔╝
#  ██╔══██╗██╔═══╝       ██║  ██║██╔═══╝
#  ██║  ██║███████╗      ██████╔╝███████╗
#  ╚═╝  ╚═╝╚══════╝      ╚═════╝ ╚══════╝
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

import os as _os
import pwd as _pwd


def _artoo_env() -> dict:
    """Environment for commands that need the artoo user's pulseaudio session."""
    try:
        uid = _pwd.getpwnam('artoo').pw_uid
    except Exception:
        uid = _os.getuid()
    env = dict(_os.environ)
    env['XDG_RUNTIME_DIR'] = f'/run/user/{uid}'
    env['PULSE_RUNTIME_PATH'] = f'/run/user/{uid}/pulse'
    return env


def _bt_run(cmd: list, timeout: float = 10.0, pa_env: bool = False) -> tuple[bool, str]:
    try:
        env = _artoo_env() if pa_env else None
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    except Exception as e:
        return False, str(e)


def _bt_scan_worker(duration: float = 10.0) -> None:
    global _scan_active, _bt_cache
    _scan_active = True
    try:
        # Enable pairing mode so the adapter accepts incoming pair requests
        subprocess.run(['bluetoothctl', 'pairable', 'on'], capture_output=True, timeout=3)
        # --timeout N makes bluetoothctl scan non-interactively and exit cleanly
        subprocess.run(
            ['bluetoothctl', '--timeout', str(int(duration)), 'scan', 'on'],
            capture_output=True, timeout=duration + 5,
        )
        # Collect all devices discovered (both classic BT and BLE)
        ok, out = _bt_run(['bluetoothctl', 'devices'])
        seen: set = set()
        devs: list = []
        for line in out.splitlines():
            m = re.search(r'Device\s+([0-9A-Fa-f:]{17})\s+(.*)', line)
            if m:
                mac = m.group(1).upper()
                name = m.group(2).strip()
                # Skip unnamed random-address BLE devices (MAC starts with random bits)
                if mac not in seen and not _is_random_unnamed(mac, name):
                    seen.add(mac)
                    devs.append({'mac': mac, 'name': name})
        _bt_cache = devs
    except Exception as e:
        log.warning('BT scan error: %s', e)
    finally:
        _scan_active = False


def _is_random_unnamed(mac: str, name: str) -> bool:
    """Filter out unnamed BLE random-address devices (clutter in the list)."""
    if name and not re.match(r'^[0-9A-Fa-f]{2}[-:]', name):
        return False   # has a real name — keep it
    # Random private addresses: first octet high 2 bits = 11 (0xCx / 0xEx / etc.)
    first = int(mac.split(':')[0], 16)
    return (first & 0xC0) == 0xC0


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
    ok, sink = _bt_run(['pactl', 'get-default-sink'], timeout=3, pa_env=True)
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
            ok, out = _bt_run(['bluetoothctl', 'connect', mac], timeout=20)
            if ok:
                # Give A2DP profile time to negotiate before setting default sink
                time.sleep(3)
                mac_u = mac.replace(':', '_')
                # Try to find the actual bluez sink (profile suffix varies)
                _, sinks = _bt_run(['pactl', 'list', 'short', 'sinks'], pa_env=True)
                sink_name = None
                for line in sinks.splitlines():
                    if mac_u in line:
                        sink_name = line.split()[1] if len(line.split()) >= 2 else None
                        break
                if not sink_name:
                    sink_name = f'bluez_sink.{mac_u}.a2dp_sink'  # fallback
                _bt_run(['pactl', 'set-default-sink', sink_name], pa_env=True, timeout=5)
                out += f' | PA sink: {sink_name}'
            self._json({'ok': ok, 'output': out})

        elif self.path == '/audio/bt/disconnect':
            if not mac:
                self._json({'ok': False, 'error': 'mac required'}, 400)
                return
            ok, out = _bt_run(['bluetoothctl', 'disconnect', mac])
            # Explicitly restore ALSA jack as default so mpg123 doesn't stay silent
            _, sinks = _bt_run(['pactl', 'list', 'short', 'sinks'], pa_env=True)
            for line in sinks.splitlines():
                parts = line.split()
                if len(parts) >= 2 and 'bluez' not in parts[1]:
                    _bt_run(['pactl', 'set-default-sink', parts[1]], pa_env=True, timeout=5)
                    out += f' | restored sink: {parts[1]}'
                    break
            self._json({'ok': ok, 'output': out})

        elif self.path == '/audio/bt/remove':
            if not mac:
                self._json({'ok': False, 'error': 'mac required'}, 400)
                return
            ok, out = _bt_run(['bluetoothctl', 'remove', mac])
            self._json({'ok': ok, 'output': out})

        elif self.path == '/audio/bt/volume':
            try:
                vol = max(0, min(100, int(body.get('volume', 80))))
            except (TypeError, ValueError):
                self._json({'ok': False, 'error': 'volume must be 0-100'}, 400)
                return
            # Apply to current default sink (BT or ALSA, whichever is active)
            _, sink = _bt_run(['pactl', 'get-default-sink'], pa_env=True, timeout=3)
            sink = sink.strip()
            if sink:
                ok, out = _bt_run(
                    ['pactl', 'set-sink-volume', sink, f'{vol}%'],
                    pa_env=True, timeout=5,
                )
                self._json({'ok': ok, 'sink': sink, 'volume': vol, 'output': out})
            else:
                self._json({'ok': False, 'error': 'no default sink found'})

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
