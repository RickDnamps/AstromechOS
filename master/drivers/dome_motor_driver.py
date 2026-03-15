"""
Master Dome Motor Driver — Phase 2.
Contrôle le moteur DC du dôme via deux canaux UART:

  D:SPEED          → moteur DC dôme (envoyé au Slave → Syren10/Sabertooth)
  TEECES:cmd        → LEDs Teeces32 (local Master via TeecesController)

Le Slave reçoit D: et pilote le Syren10 sur /dev/ttyUSB1 (ou autre port).

Activation Phase 2:
  1. Décommenter l'import dans master/main.py
  2. Appeler dome.setup() dans main()
  3. Configurer dome_port dans main.cfg si nécessaire
"""

import logging
import threading
import time
import random

log = logging.getLogger(__name__)

DEADZONE = 0.05
# Vitesse max rotation aléatoire (fraction de 1.0)
RANDOM_SPEED_MAX = 0.4
# Délai entre rotations aléatoires (secondes)
RANDOM_INTERVAL_MIN = 3.0
RANDOM_INTERVAL_MAX = 8.0


class DomeMotorDriver:
    """
    Contrôle le moteur DC du dôme.
    En mode manuel : dome.turn(speed)
    En mode aléatoire : dome.set_random(True) → tourne par intervals
    """

    def __init__(self, uart):
        self._uart = uart
        self._ready = False
        self._speed = 0.0
        self._random_mode = False
        self._random_thread: threading.Thread | None = None

    def setup(self) -> bool:
        self._ready = True
        log.info("DomeMotorDriver prêt")
        return True

    def shutdown(self) -> None:
        self.set_random(False)
        self.stop()
        self._ready = False

    def is_ready(self) -> bool:
        return self._ready

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def turn(self, speed: float) -> bool:
        """
        Rotation dôme.
        speed : float [-1.0 … +1.0]
          -1.0 = gauche max, +1.0 = droite max, 0.0 = arrêt
        """
        if abs(speed) < DEADZONE:
            speed = 0.0
        self._speed = max(-1.0, min(1.0, speed))
        ok = self._uart.send('D', f"{self._speed:.3f}")
        log.debug(f"Dôme turn: {self._speed:.3f}")
        return ok

    def stop(self) -> bool:
        """Arrêt rotation dôme."""
        self._speed = 0.0
        return self._uart.send('D', '0.000')

    def center(self) -> bool:
        """Retour position zéro (centre)."""
        return self.stop()

    def set_random(self, enabled: bool) -> None:
        """Active/désactive le mode rotation aléatoire."""
        self._random_mode = enabled
        if enabled and (self._random_thread is None or not self._random_thread.is_alive()):
            self._random_thread = threading.Thread(
                target=self._random_loop, name="dome-random", daemon=True
            )
            self._random_thread.start()
            log.info("Dôme mode aléatoire activé")
        elif not enabled:
            log.info("Dôme mode aléatoire désactivé")
            self.stop()

    @property
    def state(self) -> dict:
        return {'speed': self._speed, 'random': self._random_mode}

    # ------------------------------------------------------------------
    # Thread aléatoire (inspiré de DomeThread r2_control)
    # ------------------------------------------------------------------

    def _random_loop(self) -> None:
        while self._random_mode:
            # Pause entre mouvements
            pause = random.uniform(RANDOM_INTERVAL_MIN, RANDOM_INTERVAL_MAX)
            time.sleep(pause)
            if not self._random_mode:
                break

            # Choisir direction et durée
            speed = random.uniform(-RANDOM_SPEED_MAX, RANDOM_SPEED_MAX)
            duration = random.uniform(0.5, 2.0)

            self.turn(speed)
            time.sleep(duration)
            self.stop()
