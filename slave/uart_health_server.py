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
Serveur HTTP léger — expose les statistiques de santé UART du Slave.
Port 5001  —  GET /uart_health  →  JSON

    {"total": 312, "errors": 6, "health_pct": 98.1, "window_s": 60}

Zéro dépendance externe (http.server stdlib).
Démarré en thread daemon depuis slave/main.py.
"""

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

log = logging.getLogger(__name__)

_DEFAULT_PORT = 5001


class _HealthHandler(BaseHTTPRequestHandler):
    """Handler HTTP minimal — GET /uart_health uniquement."""

    def do_GET(self):
        if self.path != '/uart_health':
            self.send_response(404)
            self.end_headers()
            return
        stats = self.server.uart_listener.get_health_stats()
        body = json.dumps(stats).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass   # Silence les logs HTTP access (trop verbeux en prod)


def start_health_server(uart_listener, port: int = _DEFAULT_PORT) -> None:
    """Démarre le serveur HTTP health en thread daemon. Non-bloquant."""
    server = HTTPServer(('', port), _HealthHandler)
    server.uart_listener = uart_listener
    threading.Thread(
        target=server.serve_forever,
        name='uart-health-http',
        daemon=True,
    ).start()
    log.info("UARTHealthServer démarré sur port %d", port)
