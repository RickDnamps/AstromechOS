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
Safe Stop — Arrêt progressif des moteurs de propulsion.

Au lieu d'envoyer M:0,0 brutalement (risque de basculement du robot),
on rampe la commande de la vitesse courante vers 0 sur une durée
proportionnelle à la vitesse.

Paramètres (ajustables) :
  RAMP_MAX_MS : durée d'arrêt à vitesse maximale (1.0) = 400ms
  RAMP_STEP_MS: intervalle entre deux mises à jour VESC      = 20ms
  DEADZONE    : en dessous → arrêt immédiat (inutile de ramper)

Exemples de durées effectives :
  Vitesse 1.0  → 400ms  (~20 steps à 20ms)
  Vitesse 0.5  → 200ms  (~10 steps)
  Vitesse 0.3  → 120ms  (6 steps)
  Vitesse 0.1  → arrêt immédiat (deadzone)

Usage dans les watchdogs :
  safe_stop.stop_drive(vesc, uart)
  safe_stop.stop_dome(dome, uart)
"""

import logging
import threading
import time

import master.registry as reg

log = logging.getLogger(__name__)

RAMP_MAX_MS  = 400    # durée ms à vitesse = 1.0
RAMP_STEP_MS = 20     # step VESC en ms (~50Hz)
DEADZONE     = 0.08   # en dessous → arrêt immédiat

# Event global pour annuler une ramp en cours (ex: app reconnecte)
_cancel_drive = threading.Event()
_cancel_dome  = threading.Event()


def cancel_ramp():
    """Annule toute ramp en cours — appelé quand l'app renvoie une commande."""
    _cancel_drive.set()
    _cancel_dome.set()


def stop_drive(vesc=None, uart=None) -> None:
    """
    Arrêt progressif de la propulsion.
    Rampe de la vitesse courante vers 0.
    Lance dans un thread daemon pour ne pas bloquer le watchdog.
    """
    v = vesc or reg.vesc
    u = uart or reg.uart

    # Lire la vitesse courante depuis le driver si dispo
    left  = getattr(v, '_left',  0.0) if v else 0.0
    right = getattr(v, '_right', 0.0) if v else 0.0

    max_speed = max(abs(left), abs(right))

    if max_speed < DEADZONE:
        # Déjà quasi arrêté — juste confirmer M:0,0
        _send_drive(v, u, 0.0, 0.0)
        return

    _cancel_drive.clear()
    duration_ms = int(max_speed * RAMP_MAX_MS)
    steps       = max(3, duration_ms // RAMP_STEP_MS)
    interval    = duration_ms / 1000.0 / steps

    log.warning(
        "SafeStop drive: %.2f,%.2f → 0 en %dms (%d steps)",
        left, right, duration_ms, steps
    )

    def _ramp():
        for i in range(1, steps + 1):
            if _cancel_drive.is_set():
                log.info("SafeStop drive: ramp annulée (nouvelle commande reçue)")
                return
            factor = 1.0 - (i / steps)   # 1.0 → 0.0
            l = left  * factor
            r = right * factor
            _send_drive(v, u, l, r)
            time.sleep(interval)
        # Arrêt final garanti
        _send_drive(v, u, 0.0, 0.0)
        log.info("SafeStop drive: arrêt progressif terminé")

    threading.Thread(target=_ramp, daemon=True, name="safe-stop-drive").start()


def stop_dome(dome=None, uart=None) -> None:
    """
    Arrêt progressif du moteur dôme.
    Même logique que stop_drive mais pour la rotation dôme.
    """
    d = dome or reg.dome
    u = uart or reg.uart

    speed = getattr(d, '_speed', 0.0) if d else 0.0
    if abs(speed) < DEADZONE:
        _send_dome(d, u, 0.0)
        return

    _cancel_dome.clear()
    duration_ms = int(abs(speed) * RAMP_MAX_MS)
    steps       = max(3, duration_ms // RAMP_STEP_MS)
    interval    = duration_ms / 1000.0 / steps

    log.warning("SafeStop dome: %.2f → 0 en %dms", speed, duration_ms)

    def _ramp():
        for i in range(1, steps + 1):
            if _cancel_dome.is_set():
                return
            _send_dome(d, u, speed * (1.0 - i / steps))
            time.sleep(interval)
        _send_dome(d, u, 0.0)

    threading.Thread(target=_ramp, daemon=True, name="safe-stop-dome").start()


# ------------------------------------------------------------------
# Helpers bas niveau
# ------------------------------------------------------------------

def _send_drive(vesc, uart, left: float, right: float) -> None:
    try:
        if vesc:
            vesc.drive(left, right)
        elif uart:
            uart.send('M', f'{left:.3f},{right:.3f}')
    except Exception as e:
        log.error("SafeStop _send_drive: %s", e)


def _send_dome(dome, uart, speed: float) -> None:
    try:
        if dome:
            dome.turn(speed)
        elif uart:
            uart.send('D', f'{speed:.3f}')
    except Exception as e:
        log.error("SafeStop _send_dome: %s", e)
