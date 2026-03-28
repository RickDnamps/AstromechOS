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
Flask Application Factory — Phase 4.
Creates and configures the R2-D2 Flask app with all blueprints.

Usage in master/main.py:
    from master.flask_app import create_app
    import master.registry as reg

    reg.uart   = uart
    reg.teeces = teeces
    reg.engine = engine
    # ... etc

    app = create_app()
    # Launch in a daemon thread:
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000,
                     use_reloader=False), daemon=True).start()
"""

import logging
import os
from flask import Flask, render_template, jsonify

log = logging.getLogger(__name__)


def create_app() -> Flask:
    """Creates and configures the Flask application."""
    template_dir = os.path.join(os.path.dirname(__file__), 'templates')
    static_dir   = os.path.join(os.path.dirname(__file__), 'static')

    app = Flask(__name__,
                template_folder=template_dir,
                static_folder=static_dir)

    app.config['JSON_SORT_KEYS'] = False

    # ------------------------------------------------------------------
    # Blueprints
    # ------------------------------------------------------------------
    from master.api.audio_bp    import audio_bp
    from master.api.motion_bp   import motion_bp
    from master.api.servo_bp    import servo_bp
    from master.api.script_bp   import script_bp
    from master.api.status_bp   import status_bp
    from master.api.teeces_bp   import teeces_bp
    from master.api.settings_bp import settings_bp
    from master.api.vesc_bp     import vesc_bp
    from master.api.bt_bp       import bt_bp
    from master.api.light_bp    import light_bp
    from master.api.choreo_bp   import choreo_bp

    app.register_blueprint(audio_bp)
    app.register_blueprint(motion_bp)
    app.register_blueprint(servo_bp)
    app.register_blueprint(script_bp)
    app.register_blueprint(status_bp)
    app.register_blueprint(teeces_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(vesc_bp)
    app.register_blueprint(bt_bp)
    app.register_blueprint(light_bp)
    app.register_blueprint(choreo_bp)

    # ------------------------------------------------------------------
    # Routes dashboard
    # ------------------------------------------------------------------
    @app.get('/')
    def index():
        return render_template('index.html')

    @app.get('/mobile')
    def mobile():
        return render_template('mobile.html')

    # ------------------------------------------------------------------
    # JSON error handling
    # ------------------------------------------------------------------
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'error': 'Not found'}), 404

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({'error': 'Internal server error'}), 500

    log.info("Flask app created — blueprints: audio, motion, servo, scripts, status, teeces, settings")
    return app
