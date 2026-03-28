#!/usr/bin/env python3
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
R2-D2 Dashboard Preview — local server to visualise the dashboard without a Pi.
Uses only the Python standard library (no Flask required).

Usage:
    python preview.py

Then open http://localhost:5000 in your browser.
"""

import sys
import os
import json
import re
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

BASE     = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(BASE, 'master', 'templates', 'index.html')
STATIC   = os.path.join(BASE, 'master', 'static')

# ---------------------------------------------------------------------------
# Fake API data — simulates the Pi Master
# ---------------------------------------------------------------------------

FAKE_STATUS = {
    "version":        "abc1234",
    "uptime":         3725,
    "heartbeat_ok":   True,
    "uart_ready":     True,
    "teeces_ready":   True,
    "vesc_ready":     False,
    "dome_ready":     False,
    "servo_ready":    False,
    "bt_controller":  None,
    "battery_voltage": 24.5,
    "temperature":    38.0,
    "scripts_running": []
}

FAKE_CATEGORIES = {
    "categories": [
        {"name": "happy",   "count": 20},
        {"name": "sad",     "count": 20},
        {"name": "alarm",   "count": 11},
        {"name": "misc",    "count": 36},
        {"name": "hum",     "count": 25},
        {"name": "quote",   "count": 47},
        {"name": "razz",    "count": 23},
        {"name": "scream",  "count":  4},
        {"name": "whistle", "count": 25},
        {"name": "ooh",     "count":  7},
        {"name": "special", "count": 53},
    ]
}

FAKE_SERVOS = {
    "servos": [
        {"name": "utility_arm_left",  "label": "Utility Arm L",  "position": 0.0},
        {"name": "utility_arm_right", "label": "Utility Arm R",  "position": 0.0},
        {"name": "panel_top_left",    "label": "Panel Top L",    "position": 0.0},
        {"name": "panel_top_right",   "label": "Panel Top R",    "position": 0.0},
        {"name": "charge_bay",        "label": "Charge Bay",     "position": 0.0},
        {"name": "data_port",         "label": "Data Port",      "position": 0.0},
    ]
}

FAKE_SERVO_STATE = {
    "state": {
        "utility_arm_left":  0.0,
        "utility_arm_right": 0.0,
        "panel_top_left":    0.0,
        "panel_top_right":   0.0,
        "charge_bay":        0.0,
        "data_port":         0.0,
    }
}

FAKE_SCRIPTS = {
    "scripts": ["patrol", "celebrate", "cantina", "leia"]
}

# Simulated sounds — real names taken from sounds_index.json (patterns CLAUDE.md)
FAKE_SOUNDS = {
    "happy":   [f"Happy{i:03d}" for i in range(1, 21)],
    "sad":     [f"Sad__{i:03d}" for i in range(1, 21)],
    "alarm":   [f"ALARM{i:03d}" for i in range(1, 12)],
    "misc":    [f"MISC_{i:03d}" for i in range(1, 37)],
    "hum":     [f"HUM__{i:03d}" for i in range(1, 26)],
    "quote":   [f"Quote{i:03d}" for i in range(1, 48)],
    "razz":    [f"RAZZ_{i:03d}" for i in range(1, 24)],
    "scream":  [f"SCREA{i:03d}" for i in range(1, 5)],
    "whistle": [f"WHIST{i:03d}" for i in range(1, 26)],
    "ooh":     [f"OOH__{i:03d}" for i in range(1, 8)],
    "special": ["Cantina", "ImperialMarch", "StarWars", "R2Beeps",
                "Startup", "Shutdown", "Processing", "Searching",
                "Found", "Alert", "Excited", "Sad_Long",
                "Chat001", "Chat002", "Chat003", "Giggle",
                "Whisper", "Sneeze", "Yawn", "Burp",
                "Fart001", "Fart002", "Scream_Long", "Cry001",
                "Happy_Long", "Processing2", "Booting", "Ready"],
}

FAKE_MOTION_STATE = {
    "left": 0.0, "right": 0.0, "dome": 0.0, "dome_auto": False
}

FAKE_TEECES_STATE = {
    "mode": "random", "ready": True
}

FAKE_WIFI_NETWORKS = {
    "networks": [
        {"ssid": "R2D2_Control", "signal": -45, "security": "WPA2"},
        {"ssid": "MonWifi",      "signal": -65, "security": "WPA2"},
        {"ssid": "Voisin_5G",   "signal": -78, "security": "WPA2"},
    ]
}

# ---------------------------------------------------------------------------

class PreviewHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        # Display only non-static requests
        if not self.path.startswith('/static'):
            print(f"  {self.command:4s} {self.path}")

    def send_json(self, data, status=200):
        body = json.dumps(data, indent=2).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def send_ok(self):
        self.send_json({"ok": True, "message": "Preview mode — simulated command"})

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        path = self.path.split('?')[0]

        if path in ('/', '/index.html'):
            self.serve_template()
        elif path.startswith('/static/'):
            self.serve_static(path[len('/static/'):])
        elif path == '/status':
            # Simulate dynamic uptime
            FAKE_STATUS['uptime'] = int(time.time()) % 86400
            self.send_json(FAKE_STATUS)
        elif path == '/audio/categories':
            self.send_json(FAKE_CATEGORIES)
        elif path == '/servo/list':
            self.send_json(FAKE_SERVOS)
        elif path == '/servo/state':
            self.send_json(FAKE_SERVO_STATE)
        elif path == '/audio/sounds':
            from urllib.parse import urlparse, parse_qs
            params = parse_qs(urlparse(self.path).query)
            cat = params.get('category', ['happy'])[0].lower()
            sounds = FAKE_SOUNDS.get(cat, [f"{cat.upper()}001"])
            self.send_json({'category': cat, 'sounds': sounds})
        elif path == '/scripts/list':
            self.send_json(FAKE_SCRIPTS)
        elif path == '/scripts/running':
            self.send_json({"running": []})
        elif path == '/motion/state':
            self.send_json(FAKE_MOTION_STATE)
        elif path == '/teeces/state':
            self.send_json(FAKE_TEECES_STATE)
        elif path == '/status/version':
            self.send_json({"version": "abc1234"})
        elif path == '/system/wifi/scan':
            self.send_json(FAKE_WIFI_NETWORKS)
        else:
            self.send_response(404)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"Preview: {path} not found"}).encode())

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)
        path = self.path.split('?')[0]

        try:
            data = json.loads(body) if body else {}
        except Exception:
            data = {}

        # Simulate a few specific responses
        if path == '/audio/play':
            self.send_json({"ok": True, "playing": data.get("sound", "unknown")})
        elif path == '/audio/random':
            self.send_json({"ok": True, "playing": f"Random_{data.get('category','misc')}001"})
        elif path == '/motion/drive':
            self.send_json({"ok": True, "left": data.get("left", 0), "right": data.get("right", 0)})
        elif path == '/teeces/text':
            self.send_json({"ok": True, "text": data.get("text", "")})
        elif path in ('/system/reboot', '/system/shutdown', '/system/reboot_slave'):
            self.send_json({"ok": False, "message": "Preview mode — reboot disabled"})
        else:
            self.send_ok()

    def serve_template(self):
        try:
            with open(TEMPLATE, 'r', encoding='utf-8') as f:
                html = f.read()

            # Replace Flask url_for calls with direct paths
            html = re.sub(
                r"\{\{\s*url_for\(\s*'static'\s*,\s*filename\s*=\s*'([^']+)'\s*\)\s*\}\}",
                r'/static/\1',
                html
            )
            # Also replace remaining Jinja2 variables with empty values
            html = re.sub(r"\{\{[^}]+\}\}", '', html)
            html = re.sub(r"\{%[^%]+%\}", '', html)

            body = html.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', len(body))
            self.end_headers()
            self.wfile.write(body)

        except FileNotFoundError:
            self.send_response(500)
            self.end_headers()
            msg = f"File not found: {TEMPLATE}".encode()
            self.wfile.write(msg)
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode())

    def serve_static(self, filepath):
        # Security: no path traversal
        filepath = filepath.replace('..', '').lstrip('/')
        full = os.path.join(STATIC, filepath.replace('/', os.sep))

        if not os.path.exists(full) or not os.path.isfile(full):
            self.send_response(404)
            self.end_headers()
            return

        ext = os.path.splitext(full)[1].lower()
        content_types = {
            '.css':  'text/css',
            '.js':   'application/javascript',
            '.png':  'image/png',
            '.jpg':  'image/jpeg',
            '.ico':  'image/x-icon',
            '.svg':  'image/svg+xml',
            '.woff': 'font/woff',
            '.woff2':'font/woff2',
        }
        ct = content_types.get(ext, 'text/plain')

        with open(full, 'rb') as f:
            body = f.read()

        self.send_response(200)
        self.send_header('Content-Type', ct)
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)


if __name__ == '__main__':
    port = 5000
    print()
    print("  ╔══════════════════════════════════╗")
    print("  ║   R2-D2 Dashboard — Preview      ║")
    print("  ╚══════════════════════════════════╝")
    print()
    print(f"  Open in your browser:")
    print(f"  → http://localhost:{port}")
    print()
    print("  (Ctrl+C to stop)")
    print()

    server = HTTPServer(('localhost', port), PreviewHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopped.")
