#!/usr/bin/env python3
"""
R2-D2 Dashboard Preview — serveur local pour visualiser le dashboard sans Pi.
Utilise uniquement la librairie standard Python (pas de Flask requis).

Usage:
    python preview.py

Puis ouvrir http://localhost:5000 dans ton navigateur.
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
# Fausses données API — simule le Pi Master
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
        # Afficher seulement les requêtes non-statiques
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
        self.send_json({"ok": True, "message": "Preview mode — commande simulée"})

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
            # Simuler uptime dynamique
            FAKE_STATUS['uptime'] = int(time.time()) % 86400
            self.send_json(FAKE_STATUS)
        elif path == '/audio/categories':
            self.send_json(FAKE_CATEGORIES)
        elif path == '/servo/list':
            self.send_json(FAKE_SERVOS)
        elif path == '/servo/state':
            self.send_json(FAKE_SERVO_STATE)
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

        # Simuler quelques réponses spécifiques
        if path == '/audio/play':
            self.send_json({"ok": True, "playing": data.get("sound", "unknown")})
        elif path == '/audio/random':
            self.send_json({"ok": True, "playing": f"Random_{data.get('category','misc')}001"})
        elif path == '/motion/drive':
            self.send_json({"ok": True, "left": data.get("left", 0), "right": data.get("right", 0)})
        elif path == '/teeces/text':
            self.send_json({"ok": True, "text": data.get("text", "")})
        elif path in ('/system/reboot', '/system/shutdown', '/system/reboot_slave'):
            self.send_json({"ok": False, "message": "Preview mode — reboot désactivé"})
        else:
            self.send_ok()

    def serve_template(self):
        try:
            with open(TEMPLATE, 'r', encoding='utf-8') as f:
                html = f.read()

            # Remplacer les appels Flask url_for par des chemins directs
            html = re.sub(
                r"\{\{\s*url_for\(\s*'static'\s*,\s*filename\s*=\s*'([^']+)'\s*\)\s*\}\}",
                r'/static/\1',
                html
            )
            # Remplacer aussi les variables Jinja2 restantes par des valeurs vides
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
            msg = f"Fichier non trouvé: {TEMPLATE}".encode()
            self.wfile.write(msg)
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode())

    def serve_static(self, filepath):
        # Sécurité : pas de path traversal
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
    print(f"  Ouvre dans ton navigateur :")
    print(f"  → http://localhost:{port}")
    print()
    print("  (Ctrl+C pour arrêter)")
    print()

    server = HTTPServer(('localhost', port), PreviewHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Arrêté.")
