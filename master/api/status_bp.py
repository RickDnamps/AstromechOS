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
Blueprint API Status — Phase 4.
Remonte l'état système R2-D2 en temps réel.

Endpoints:
  GET  /status              → état complet JSON
  GET  /status/version      → versions Master + Slave
  POST /system/reboot       → reboot Master
  POST /system/reboot_slave → reboot Slave (via UART)
"""

import datetime
import os
import subprocess
import threading
from flask import Blueprint, request, jsonify
import master.registry as reg
from master.app_watchdog import app_watchdog

status_bp = Blueprint('status', __name__)

VERSION_FILE = '/home/artoo/r2d2/VERSION'


def _read_version() -> str:
    try:
        with open(VERSION_FILE, encoding='utf-8') as f:
            return f.read().strip()
    except Exception:
        return 'unknown'


def _uptime() -> str:
    try:
        with open('/proc/uptime', 'r') as f:
            seconds = float(f.readline().split()[0])
        return str(datetime.timedelta(seconds=int(seconds)))
    except Exception:
        return 'unknown'


def _cpu_temp() -> float | None:
    try:
        with open('/sys/class/thermal/thermal_zone0/temp') as f:
            return round(int(f.read().strip()) / 1000, 1)
    except Exception:
        return None


@status_bp.get('/status')
def get_status():
    """État complet du système R2-D2."""
    _uart_serial = getattr(reg.uart, '_serial', None)
    uart_ready   = bool(_uart_serial and _uart_serial.is_open
                        and getattr(reg.uart, '_running', False))
    # HB  = heartbeat applicatif App ↔ Master (AppWatchdog)
    # UART = lien série Master ↔ Slave
    heartbeat_ok = app_watchdog.is_connected
    # BT controller status
    bt_status = reg.bt_ctrl.get_status() if reg.bt_ctrl else {}
    return jsonify({
        'version':      _read_version(),
        'uptime':       _uptime(),
        'temperature':  _cpu_temp(),
        'heartbeat_ok': heartbeat_ok,   # App ↔ Master
        'uart_ready':   uart_ready,     # Master ↔ Slave UART
        'app_hb_age_ms': app_watchdog.last_hb_age_ms,
        'teeces_ready':     bool(reg.teeces     and reg.teeces.is_ready()),
        'vesc_ready':       bool(reg.vesc       and reg.vesc.is_ready()),
        'dome_ready':       bool(reg.dome       and reg.dome.is_ready()),
        'servo_ready':      bool(reg.servo      and reg.servo.is_ready()),
        'dome_servo_ready': bool(reg.dome_servo and reg.dome_servo.is_ready()),
        'scripts_running': reg.engine.list_running() if reg.engine else [],
        'uart_health':       reg.slave_uart_health,          # None si Slave injoignable
        'uart_crc_errors':   reg.uart.crc_errors if reg.uart else 0,  # CRC invalides consécutifs côté Master
        'audio_playing':     reg.audio_playing,
        'audio_current':     reg.audio_current,
        'lock_mode':         reg.lock_mode,
        'estop_active':      reg.estop_active,
        'lights_backend':    type(reg.teeces).__name__.replace('Driver', '').lower() if reg.teeces else 'none',
        **bt_status,
    })


@status_bp.get('/status/version')
def get_version():
    """Versions Master et Slave."""
    return jsonify({'master': _read_version()})


@status_bp.post('/system/update')
def system_update():
    """Force git pull + rsync Slave + reboot Slave (même chose que le bouton dôme)."""
    if not reg.deploy:
        return jsonify({'error': 'DeployController non disponible'}), 503
    import threading
    threading.Thread(target=reg.deploy.update_and_deploy, daemon=True).start()
    return jsonify({'status': 'ok', 'message': 'Update en cours...'})


@status_bp.post('/lock/set')
def lock_set():
    """Définit le mode de verrouillage : 0=Normal, 1=Kids, 2=ChildLock."""
    body = request.get_json(silent=True) or {}
    mode = int(body.get('mode', 0))
    if mode not in (0, 1, 2):
        return jsonify({'error': 'mode invalide'}), 400
    reg.lock_mode = mode
    if 'kids_speed_limit' in body:
        reg.kids_speed_limit = max(0.0, min(1.0, float(body.get('kids_speed_limit', 0.5))))
    return jsonify({'status': 'ok', 'mode': mode})


@status_bp.post('/system/resync_slave')
def system_resync_slave():
    """
    Rsync + service install + restart Slave uniquement.
    Appelé automatiquement par le Slave via HTTP quand il détecte un version mismatch au boot.
    """
    def do_resync():
        subprocess.run(
            ['bash', '/home/artoo/r2d2/scripts/resync_slave.sh'],
            check=False
        )
    threading.Thread(target=do_resync, daemon=True).start()
    return jsonify({'status': 'resync_triggered'})


@status_bp.post('/system/reboot')
def system_reboot():
    """Reboot le Master (Pi dôme)."""
    threading.Thread(
        target=lambda: subprocess.run(['sudo', 'reboot'], check=False),
        daemon=True
    ).start()
    return jsonify({'status': 'rebooting'})


@status_bp.post('/system/reboot_slave')
def system_reboot_slave():
    """Envoie une commande reboot au Slave via UART."""
    if reg.uart:
        reg.uart.send('REBOOT', '1')
        return jsonify({'status': 'ok'})
    return jsonify({'error': 'UART non disponible'}), 503


@status_bp.post('/system/shutdown')
def system_shutdown():
    """Éteint le Master."""
    threading.Thread(
        target=lambda: subprocess.run(['sudo', 'shutdown', '-h', 'now'], check=False),
        daemon=True
    ).start()
    return jsonify({'status': 'shutting_down'})


@status_bp.post('/heartbeat')
def app_heartbeat():
    """
    Heartbeat applicatif — App → Master, toutes les 200ms.
    Si ce heartbeat s'arrête pendant >600ms → arrêt d'urgence (AppWatchdog).
    Endpoint ultra-léger : juste un timestamp update.
    """
    app_watchdog.feed()
    return '', 204   # No Content — réponse minimale


@status_bp.post('/system/estop')
def system_estop():
    """Arrêt d'urgence servos — coupe PWM PCA9685 Master (0x40) + Slave (0x41) via smbus2."""
    # Coupe via drivers actifs si disponibles
    if reg.dome_servo:
        try:
            reg.dome_servo.shutdown()
        except Exception:
            pass
    if reg.servo:
        try:
            reg.servo.shutdown()
        except Exception:
            pass
    reg.estop_active = True
    # Fallback garanti : estop.py direct via subprocess
    threading.Thread(
        target=lambda: subprocess.run(
            ['python3', '/home/artoo/r2d2/scripts/estop.py'], check=False
        ),
        daemon=True
    ).start()
    return jsonify({'status': 'estop_sent'})


@status_bp.post('/system/estop_reset')
def system_estop_reset():
    """Réarme les drivers servo après un E-STOP — réinitialise PCA9685 sans redémarrer le service."""
    import logging
    log = logging.getLogger(__name__)
    reg.estop_active = False
    results = {}
    if reg.dome_servo:
        ok = reg.dome_servo.setup()
        results['dome_servo'] = 'ok' if ok else 'erreur'
        log.info("estop_reset: dome_servo setup → %s", results['dome_servo'])
    if reg.servo:
        ok = reg.servo.setup()
        results['body_servo'] = 'ok' if ok else 'erreur'
        log.info("estop_reset: body_servo setup → %s", results['body_servo'])
    return jsonify({'status': 'reset', 'drivers': results})
