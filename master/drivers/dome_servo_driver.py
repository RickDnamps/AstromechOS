"""
Master Dome Servo Driver — Phase 2.
Pilote directement le PCA9685 I2C @ 0x40 (Servo Driver HAT sur le Master).
11 servos pour les panneaux du dôme, canaux 0–10.

Pulse: 1000µs (fermé) → 1500µs (ouvert ≈ 45°).
"""

import logging
import threading
import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.base_driver import BaseDriver

log = logging.getLogger(__name__)

PCA9685_ADDRESS = 0x40
PCA9685_FREQ_HZ = 50

# Servo continu (SG90 ou équivalent)
# 1500µs = STOP, < 1500 = sens fermeture, > 1500 = sens ouverture
PULSE_STOP_US   = 1500  # arrêt absolu
PULSE_OPEN_US   = 1600  # ouverture lente (ajuster si trop vite/lent)
PULSE_CLOSED_US = 1400  # fermeture lente (ajuster si trop vite/lent)

SERVO_MAP: dict[str, tuple[int, int, int]] = {
    'dome_panel_1':  (0,  PULSE_CLOSED_US, PULSE_OPEN_US),
    'dome_panel_2':  (1,  PULSE_CLOSED_US, PULSE_OPEN_US),
    'dome_panel_3':  (2,  PULSE_CLOSED_US, PULSE_OPEN_US),
    'dome_panel_4':  (3,  PULSE_CLOSED_US, PULSE_OPEN_US),
    'dome_panel_5':  (4,  PULSE_CLOSED_US, PULSE_OPEN_US),
    'dome_panel_6':  (5,  PULSE_CLOSED_US, PULSE_OPEN_US),
    'dome_panel_7':  (6,  PULSE_CLOSED_US, PULSE_OPEN_US),
    'dome_panel_8':  (7,  PULSE_CLOSED_US, PULSE_OPEN_US),
    'dome_panel_9':  (8,  PULSE_CLOSED_US, PULSE_OPEN_US),
    'dome_panel_10': (9,  PULSE_CLOSED_US, PULSE_OPEN_US),
    'dome_panel_11': (10, PULSE_CLOSED_US, PULSE_OPEN_US),
}


class DomeServoDriver(BaseDriver):

    def __init__(self, i2c_address: int = PCA9685_ADDRESS):
        self._address       = i2c_address
        self._pca           = None
        self._ready         = False
        self._lock          = threading.Lock()
        self._positions:     dict[str, float]          = {n: 0.0 for n in SERVO_MAP}
        self._current_pulse: dict[int, float]          = {}
        self._cancel_events: dict[int, threading.Event] = {}

    def setup(self) -> bool:
        try:
            import board
            import busio
            from adafruit_pca9685 import PCA9685

            i2c = busio.I2C(board.SCL, board.SDA)
            self._pca = PCA9685(i2c, address=self._address)
            self._pca.frequency = PCA9685_FREQ_HZ
            # Forcer FULL OFF sur tous les 16 canaux — efface les valeurs résiduelles
            # du chip (le PCA9685 garde ses registres PWM en mémoire entre les restarts
            # de service, sans power cycle). duty_cycle=0 active le bit FULL OFF.
            for ch in range(16):
                self._pca.channels[ch].duty_cycle = 0

            self._ready = True
            log.info(f"DomeServoDriver prêt — PCA9685 @ 0x{self._address:02X}, "
                     f"{len(SERVO_MAP)} panneaux dôme")
            return True
        except ImportError:
            log.error("adafruit-circuitpython-pca9685 non installé")
            return False
        except Exception as e:
            log.error(f"Erreur init PCA9685 dôme: {e}")
            return False

    def shutdown(self) -> None:
        # Annuler tous les mouvements en cours
        for evt in self._cancel_events.values():
            evt.set()
        if self._pca:
            for name in SERVO_MAP:
                self._set_pulse_raw(SERVO_MAP[name][0], float(PULSE_STOP_US))
            time.sleep(0.3)
            try:
                import smbus2
                b = smbus2.SMBus(1)
                b.write_byte_data(self._address, 0x00, 0x10)  # MODE1 SLEEP
                b.close()
            except Exception as e:
                log.warning(f"Erreur sleep PCA9685 dôme: {e}")
        self._ready = False

    def is_ready(self) -> bool:
        return self._ready

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def move(self, name: str, position: float, duration_ms: int = 500) -> bool:
        if not self._ready:
            return False
        if name not in SERVO_MAP:
            log.warning(f"Panneau dôme inconnu: {name!r}")
            return False

        position = max(0.0, min(1.0, position))
        self._positions[name] = position
        channel, pulse_min, pulse_max = SERVO_MAP[name]

        # Annuler le mouvement en cours sur ce canal
        if channel in self._cancel_events:
            self._cancel_events[channel].set()

        target_pulse  = pulse_min + (pulse_max - pulse_min) * position
        # Si position inconnue (premier mouvement), aller directement à la cible
        start_pulse   = self._current_pulse.get(channel, target_pulse)
        cancel_evt    = threading.Event()
        self._cancel_events[channel] = cancel_evt

        self._set_pulse_raw(channel, target_pulse)
        self._current_pulse[channel] = target_pulse
        if duration_ms > 0:
            threading.Thread(
                target=self._timed_stop,
                args=(channel, duration_ms, cancel_evt),
                daemon=True
            ).start()
        return True

    def open(self, name: str, duration_ms: int = 500) -> bool:
        return self.move(name, 1.0, duration_ms)

    def close(self, name: str, duration_ms: int = 500) -> bool:
        return self.move(name, 0.0, duration_ms)

    def open_all(self, duration_ms: int = 500) -> None:
        for name in SERVO_MAP:
            self.open(name, duration_ms)

    def close_all(self, duration_ms: int = 500) -> None:
        for name in SERVO_MAP:
            self.close(name, duration_ms)

    @property
    def state(self) -> dict:
        return dict(self._positions)

    # ------------------------------------------------------------------
    # Interne
    # ------------------------------------------------------------------

    def _set_pulse_raw(self, channel: int, pulse_us: float) -> None:
        tick = int((pulse_us / 20000.0) * 4096)
        with self._lock:
            try:
                self._pca.channels[channel].duty_cycle = tick << 4
            except Exception as e:
                log.error(f"Erreur PWM canal dôme {channel}: {e}")

    def _timed_stop(self, channel: int, duration_ms: int,
                    cancel_evt: threading.Event) -> None:
        """Attend duration_ms puis envoie STOP (1500µs) — servo continu."""
        time.sleep(duration_ms / 1000.0)
        if cancel_evt.is_set():
            return  # nouvelle commande arrivée — elle gère son propre stop
        self._set_pulse_raw(channel, float(PULSE_STOP_US))
        self._current_pulse[channel] = float(PULSE_STOP_US)
