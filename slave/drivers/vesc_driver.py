"""
Slave VESC Driver — Phase 2.
Reçoit les commandes M: du Master et pilote les VESC de propulsion via pyvesc.

Format UART reçu: M:LEFT,RIGHT
  LEFT, RIGHT : float [-1.0 … +1.0]

Connexion VESC:
  VESC gauche : /dev/ttyACM0 (ou configuré dans main.cfg)
  VESC droit  : /dev/ttyACM1

Note: Les deux VESC sont connectés directement au Pi Slave 4B via USB.
      Chaque VESC reçoit sa commande de duty cycle indépendamment.

Activation Phase 2:
  1. Brancher les VESC sur USB
  2. Décommenter l'import dans slave/main.py
  3. Appeler vesc.setup() dans main()
  4. uart.register_callback('M', vesc.handle_uart)
"""

import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.base_driver import BaseDriver

log = logging.getLogger(__name__)

VESC_PORT_LEFT  = "/dev/ttyACM0"
VESC_PORT_RIGHT = "/dev/ttyACM1"
VESC_BAUD       = 115200

# Limite matérielle de sécurité — ne jamais dépasser
HARDWARE_SPEED_LIMIT = 0.85


class VescDriver(BaseDriver):
    """
    Pilote VESC pour la propulsion différentielle R2-D2.
    Utilise pyvesc pour communiquer avec les contrôleurs VESC.
    """

    def __init__(self, port_left: str = VESC_PORT_LEFT,
                 port_right: str = VESC_PORT_RIGHT):
        self._port_left  = port_left
        self._port_right = port_right
        self._vesc_left  = None
        self._vesc_right = None
        self._ready      = False

    def setup(self) -> bool:
        try:
            import pyvesc
            import serial as _serial

            self._serial_left  = _serial.Serial(self._port_left,  VESC_BAUD, timeout=0.1)
            self._serial_right = _serial.Serial(self._port_right, VESC_BAUD, timeout=0.1)
            self._pyvesc = pyvesc
            self._ready = True
            log.info(f"VescDriver prêt: L={self._port_left} R={self._port_right}")
            return True
        except ImportError:
            log.error("pyvesc non installé — installer: pip install pyvesc")
            return False
        except Exception as e:
            log.error(f"Erreur init VESC: {e}")
            return False

    def shutdown(self) -> None:
        self._stop_motors()
        if hasattr(self, '_serial_left') and self._serial_left.is_open:
            self._serial_left.close()
        if hasattr(self, '_serial_right') and self._serial_right.is_open:
            self._serial_right.close()
        self._ready = False
        log.info("VescDriver arrêté")

    def is_ready(self) -> bool:
        return self._ready

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def drive(self, left: float, right: float) -> None:
        """Commande différentielle directe."""
        if not self._ready:
            return
        left  = max(-HARDWARE_SPEED_LIMIT, min(HARDWARE_SPEED_LIMIT, left))
        right = max(-HARDWARE_SPEED_LIMIT, min(HARDWARE_SPEED_LIMIT, right))
        self._set_duty(self._serial_left,  left)
        self._set_duty(self._serial_right, right)

    def stop(self) -> None:
        """Arrêt d'urgence — coupe les deux VESC."""
        self._stop_motors()

    def handle_uart(self, value: str) -> None:
        """
        Callback UART pour message M:LEFT,RIGHT.
        Appelé par uart_listener quand M: est reçu.
        """
        try:
            parts = value.split(',')
            left  = float(parts[0])
            right = float(parts[1])
            self.drive(left, right)
        except (ValueError, IndexError) as e:
            log.error(f"Message M: invalide {value!r}: {e}")

    # ------------------------------------------------------------------
    # Interne
    # ------------------------------------------------------------------

    def _set_duty(self, ser, duty: float) -> None:
        """Envoie une commande SetDutyCycle à un VESC."""
        try:
            msg = self._pyvesc.encode(self._pyvesc.SetDutyCycle(duty))
            ser.write(msg)
        except Exception as e:
            log.error(f"Erreur commande VESC: {e}")

    def _stop_motors(self) -> None:
        if not self._ready:
            return
        try:
            self._set_duty(self._serial_left,  0.0)
            self._set_duty(self._serial_right, 0.0)
        except Exception:
            pass
