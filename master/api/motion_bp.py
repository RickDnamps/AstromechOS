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
Blueprint API Motion — Phase 4.
Contrôle la propulsion (VESC) et le moteur dôme.

Endpoints propulsion:
  POST /motion/drive        {"left": 0.5, "right": 0.5}
  POST /motion/arcade       {"throttle": 0.5, "steering": 0.0}
  POST /motion/stop
  GET  /motion/state

Endpoints dôme:
  POST /motion/dome/turn    {"speed": 0.3}
  POST /motion/dome/stop
  POST /motion/dome/random  {"enabled": true}
  GET  /motion/dome/state

Sécurité : chaque commande de mouvement alimente le MotionWatchdog.
Si aucune commande reçue pendant 800ms alors que le robot est en mouvement
→ arrêt automatique (perte de connexion contrôleur).
"""

import time
from flask import Blueprint, request, jsonify
import master.registry as reg
from master.motion_watchdog import motion_watchdog
from master.safe_stop import cancel_ramp

motion_bp = Blueprint('motion', __name__, url_prefix='/motion')


def _clamp(val: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, val))


# ------------------------------------------------------------------
# Propulsion
# ------------------------------------------------------------------

@motion_bp.post('/drive')
def drive():
    """Propulsion différentielle. Body: {"left": float, "right": float}"""
    if reg.lock_mode == 2:
        return jsonify({'status': 'blocked', 'reason': 'child_lock'}), 403

    body  = request.get_json(silent=True) or {}
    reg.web_last_drive_t = time.time()
    left  = _clamp(float(body.get('left',  0.0)))
    right = _clamp(float(body.get('right', 0.0)))

    cancel_ramp()                             # annule arrêt progressif si en cours
    motion_watchdog.feed_drive(left, right)   # alimente le watchdog

    if reg.vesc:
        reg.vesc.drive(left, right)
    elif reg.uart:
        reg.uart.send('M', f'{left:.3f},{right:.3f}')
    return jsonify({'status': 'ok', 'left': left, 'right': right})


@motion_bp.post('/arcade')
def arcade():
    """Arcade drive. Body: {"throttle": float, "steering": float}"""
    if reg.lock_mode == 2:
        return jsonify({'status': 'blocked', 'reason': 'child_lock'}), 403

    body     = request.get_json(silent=True) or {}
    reg.web_last_drive_t = time.time()
    throttle = _clamp(float(body.get('throttle', 0.0)))
    steering = _clamp(float(body.get('steering', 0.0)))

    left  = _clamp(throttle + steering)
    right = _clamp(throttle - steering)
    cancel_ramp()
    motion_watchdog.feed_drive(left, right)

    if reg.vesc:
        reg.vesc.arcade_drive(throttle, steering)
    return jsonify({'status': 'ok', 'throttle': throttle, 'steering': steering})


@motion_bp.post('/stop')
def stop_motion():
    """Arrêt propulsion."""
    motion_watchdog.clear_drive()             # stop explicite — pas un timeout
    if reg.vesc:
        reg.vesc.stop()
    elif reg.uart:
        reg.uart.send('M', '0.000,0.000')
    return jsonify({'status': 'ok'})


@motion_bp.get('/state')
def motion_state():
    """État courant propulsion."""
    state = reg.vesc.state if reg.vesc else {}
    return jsonify(state)


# ------------------------------------------------------------------
# Dôme
# ------------------------------------------------------------------

@motion_bp.post('/dome/turn')
def dome_turn():
    """Rotation dôme. Body: {"speed": float}"""
    body  = request.get_json(silent=True) or {}
    reg.web_last_dome_t = time.time()
    speed = _clamp(float(body.get('speed', 0.0)))

    motion_watchdog.feed_dome(speed)          # alimente le watchdog

    if reg.dome:
        reg.dome.turn(speed)
    elif reg.uart:
        reg.uart.send('D', f'{speed:.3f}')
    return jsonify({'status': 'ok', 'speed': speed})


@motion_bp.post('/dome/stop')
def dome_stop():
    """Arrêt rotation dôme."""
    motion_watchdog.clear_dome()
    if reg.dome:
        reg.dome.stop()
    elif reg.uart:
        reg.uart.send('D', '0.000')
    return jsonify({'status': 'ok'})


@motion_bp.post('/dome/random')
def dome_random():
    """Mode aléatoire dôme. Body: {"enabled": bool}"""
    body    = request.get_json(silent=True) or {}
    enabled = bool(body.get('enabled', False))
    if not enabled:
        motion_watchdog.clear_dome()
    if reg.dome:
        reg.dome.set_random(enabled)
    return jsonify({'status': 'ok', 'random': enabled})


@motion_bp.get('/dome/state')
def dome_state():
    """État courant dôme."""
    state = reg.dome.state if reg.dome else {}
    return jsonify(state)
