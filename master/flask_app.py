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
Flask Application Factory.
Creates and configures the Flask application with all blueprints.
"""

import logging
import os
import time
from flask import Flask, render_template, jsonify, request, Response
import master.registry as reg
from shared.paths import VERSION_FILE

log = logging.getLogger(__name__)


def _read_version() -> str:
    try:
        with open(VERSION_FILE, encoding='utf-8') as f:
            return f.read().strip() or 'dev'
    except Exception:
        return 'dev'


def create_app() -> Flask:
    """Creates and configures the Flask application."""
    template_dir = os.path.join(os.path.dirname(__file__), 'templates')
    static_dir   = os.path.join(os.path.dirname(__file__), 'static')

    app = Flask(__name__,
                template_folder=template_dir,
                static_folder=static_dir)

    app.config['JSON_SORT_KEYS'] = False
    # Global upload size cap. Audit finding 2026-05-15: client-side
    # caps (10MB audio at AudioBoard, 2MB icon at iconPicker) were
    # bypassable via `curl` — admin-authenticated DoS could fill the
    # disk before any post-validation ran. WSGI rejects oversized
    # requests at the framework layer (413 Request Entity Too Large)
    # before they ever hit the blueprint. 16MB > biggest legit MP3
    # the project ships (320kbps × ~6min = ~14MB).
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

    # ------------------------------------------------------------------
    # Blueprints
    # ------------------------------------------------------------------
    from master.api.audio_bp    import audio_bp
    from master.api.motion_bp   import motion_bp
    from master.api.servo_bp    import servo_bp
    from master.api.status_bp   import status_bp
    from master.api.teeces_bp   import teeces_bp
    from master.api.settings_bp import settings_bp
    from master.api.vesc_bp     import vesc_bp
    from master.api.bt_bp       import bt_bp
    from master.api.choreo_bp   import choreo_bp
    from master.api.camera_bp   import camera_bp
    from master.api.behavior_bp     import behavior_bp
    from master.api.diagnostics_bp  import diagnostics_bp
    from master.api.shortcuts_bp    import shortcuts_bp

    app.register_blueprint(audio_bp)
    app.register_blueprint(motion_bp)
    app.register_blueprint(servo_bp)
    app.register_blueprint(status_bp)
    app.register_blueprint(teeces_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(vesc_bp)
    app.register_blueprint(bt_bp)
    app.register_blueprint(choreo_bp)
    app.register_blueprint(camera_bp)
    app.register_blueprint(behavior_bp)
    app.register_blueprint(diagnostics_bp)
    app.register_blueprint(shortcuts_bp)

    # ------------------------------------------------------------------
    # Activity tracking — update last_activity on user-driven POSTs.
    # /heartbeat fires every 200ms from the dashboard polling loop and would
    # otherwise keep last_activity perpetually fresh, defeating the inactivity
    # watchdog. The status poller is also excluded for the same reason.
    # ------------------------------------------------------------------
    _ACTIVITY_IGNORED_PATHS = ('/heartbeat', '/status')

    @app.before_request
    def _update_last_activity():
        if request.method == 'POST' and request.path not in _ACTIVITY_IGNORED_PATHS:
            reg.last_activity = time.monotonic()

    # ------------------------------------------------------------------
    # Routes dashboard
    # ------------------------------------------------------------------
    @app.get('/')
    def index():
        return render_template('index.html')

    @app.get('/mobile')
    def mobile():
        return render_template('mobile.html')

    # Serve user-uploaded robot icons from the project-level icons/ folder
    icons_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'icons')
    os.makedirs(icons_dir, exist_ok=True)

    @app.get('/icons/<path:filename>')
    def serve_icon(filename):
        from flask import send_from_directory
        return send_from_directory(icons_dir, filename)

    # Service worker: served dynamically so the CACHE name embeds the current
    # deploy commit. The static file ships with the placeholder '__VERSION__'
    # which we substitute at request time. This forces a cache flush on every
    # deploy instead of users running stale JS until manual reload.
    sw_path = os.path.join(static_dir, 'sw.js')

    @app.get('/static/sw.js')
    def serve_sw():
        try:
            with open(sw_path, encoding='utf-8') as f:
                body = f.read()
            body = body.replace('__VERSION__', _read_version())
            resp = Response(body, mimetype='application/javascript')
            resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            return resp
        except Exception:
            log.exception("Failed to serve sw.js")
            return Response('', mimetype='application/javascript', status=500)

    # ------------------------------------------------------------------
    # JSON error handling
    # ------------------------------------------------------------------
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'error': 'Not found'}), 404

    @app.errorhandler(500)
    def server_error(e):
        # Audit finding M-3 2026-05-15: without log.exception, an
        # unhandled blueprint exception turned into a silent generic
        # 500 — operator + journalctl saw nothing, debugging was
        # blind. Log the full traceback so genuine bugs surface.
        log.exception("Unhandled 500: %s", e)
        return jsonify({'error': 'Internal server error'}), 500

    log.info("Flask app created — blueprints: audio, motion, servo, status, teeces, settings, vesc, bt, choreo, camera, behavior, diagnostics")
    return app
