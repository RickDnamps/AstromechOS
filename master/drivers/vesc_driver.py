"""
Master VESC Driver — Phase 2.
Envoie les commandes de propulsion au Slave via UART (message M:).
Le Slave exécute les commandes sur les VESC physiques.

Format UART: M:LEFT,RIGHT
  LEFT, RIGHT : float [-1.0 … +1.0]
  -1.0 = pleine marche arrière, +1.0 = pleine marche avant

Activation Phase 2:
  1. Décommenter l'import dans master/main.py
  2. Appeler vesc.setup() dans main()
  3. Brancher les callbacks du gamepad
"""

import logging
import time

log = logging.getLogger(__name__)

# Limite de vitesse logicielle (0.0 à 1.0)
SPEED_LIMIT = 1.0
# Seuil de deadzone joystick
DEADZONE = 0.05


class VescDriver:
    """
    Couche d'abstraction propulsion Master.
    Convertit les entrées joystick en commandes UART M:.
    """

    def __init__(self, uart):
        """
        Parameters
        ----------
        uart : UARTController
            Instance active du contrôleur UART Master.
        """
        self._uart = uart
        self._ready = False
        self._left = 0.0
        self._right = 0.0
        self._speed_limit = SPEED_LIMIT

    def setup(self) -> bool:
        self._ready = True
        log.info(f"VescDriver prêt (speed_limit={self._speed_limit:.2f})")
        return True

    def shutdown(self) -> None:
        self.stop()
        self._ready = False

    def is_ready(self) -> bool:
        return self._ready

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def drive(self, left: float, right: float) -> bool:
        """
        Commande de propulsion différentielle.

        Parameters
        ----------
        left  : float [-1.0 … +1.0]
        right : float [-1.0 … +1.0]
        """
        left  = self._clamp(left)
        right = self._clamp(right)

        # Deadzone
        if abs(left)  < DEADZONE: left  = 0.0
        if abs(right) < DEADZONE: right = 0.0

        self._left  = left
        self._right = right

        value = f"{left:.3f},{right:.3f}"
        ok = self._uart.send('M', value)
        if ok:
            log.debug(f"VESC drive: L={left:.3f} R={right:.3f}")
        return ok

    def stop(self) -> bool:
        """Arrêt d'urgence propulsion."""
        self._left = 0.0
        self._right = 0.0
        return self._uart.send('M', '0.000,0.000')

    def arcade_drive(self, throttle: float, steering: float) -> bool:
        """
        Conversion arcade → différentielle.
        throttle : [-1.0 … +1.0] avant/arrière
        steering : [-1.0 … +1.0] gauche/droite
        """
        left  = throttle + steering
        right = throttle - steering
        # Normaliser si hors [-1, 1]
        max_val = max(abs(left), abs(right), 1.0)
        return self.drive(left / max_val, right / max_val)

    def set_speed_limit(self, limit: float) -> None:
        """Limite dynamique de vitesse (0.0 à 1.0)."""
        self._speed_limit = max(0.0, min(1.0, limit))
        log.info(f"Limite vitesse: {self._speed_limit:.0%}")

    @property
    def state(self) -> dict:
        return {'left': self._left, 'right': self._right, 'limit': self._speed_limit}

    # ------------------------------------------------------------------
    def _clamp(self, v: float) -> float:
        return max(-self._speed_limit, min(self._speed_limit, v))
