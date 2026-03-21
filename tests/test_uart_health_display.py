"""
Tests UART Health Display — validation des seuils et de la logique d'affichage.

Vérifie que le status API expose les bonnes données et que les seuils
de dégradation sont correctement définis (vert/orange/rouge).

Les règles UI à valider :
  ≥ 95%       → ok    (vert)  — normal
  70% - 94%   → warn  (orange) — interférences légères
  < 70%       → error (rouge)  — bus sérieusement bruité
  Slave null  → gris / warn si CRC Master > 0

Usage : python -m pytest tests/test_uart_health_display.py -v
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, PropertyMock

# ── Mock modules hardware ────────────────────────────────────────────────────
import types
from unittest.mock import MagicMock

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Mock serial (pyserial non disponible sur PC dev Windows)
_serial_mock = types.ModuleType('serial')
_serial_mock.Serial          = MagicMock()
_serial_mock.SerialException = type('SerialException', (Exception,), {})
sys.modules.setdefault('serial', _serial_mock)

# Mock master.registry uniquement — ne PAS mocker le package 'master'
_registry_mod = types.ModuleType('master.registry')
_registry_mod.uart = None
sys.modules.setdefault('master.registry', _registry_mod)


# ─────────────────────────────────────────────────────────────────────────────
# Tests UARTController.crc_errors
# ─────────────────────────────────────────────────────────────────────────────

class TestUARTControllerCrcErrors(unittest.TestCase):
    """Vérifie que UARTController expose bien son compteur d'erreurs CRC."""

    def _make_uart(self):
        """Instancie UARTController avec config minimale mockée."""
        import configparser
        cfg = configparser.ConfigParser()
        cfg.add_section('master')
        cfg.set('master', 'uart_port',             '/dev/ttyAMA0')
        cfg.set('master', 'uart_baud',             '115200')
        cfg.set('master', 'heartbeat_interval_ms', '200')

        # Mock serial pour éviter ouverture réelle du port
        import master.uart_controller as uc_mod
        import serial as _serial
        with unittest.mock.patch.object(_serial, 'Serial'):
            from master.uart_controller import UARTController
            return UARTController(cfg)

    def test_crc_errors_initially_zero(self):
        """Au démarrage, aucune erreur CRC."""
        import configparser
        cfg = configparser.ConfigParser()
        cfg.add_section('master')
        cfg.set('master', 'uart_port', '/dev/ttyAMA0')
        cfg.set('master', 'uart_baud', '115200')
        cfg.set('master', 'heartbeat_interval_ms', '200')
        from master.uart_controller import UARTController
        uart = UARTController(cfg)
        self.assertEqual(uart.crc_errors, 0)

    def test_crc_errors_increments_on_invalid(self):
        """Chaque message invalide incrémente le compteur."""
        import configparser
        cfg = configparser.ConfigParser()
        cfg.add_section('master')
        cfg.set('master', 'uart_port', '/dev/ttyAMA0')
        cfg.set('master', 'uart_baud', '115200')
        cfg.set('master', 'heartbeat_interval_ms', '200')
        from master.uart_controller import UARTController
        uart = UARTController(cfg)

        # Simuler 3 messages invalides (CRC mauvais)
        uart._process_line("H:1:ZZ")   # checksum invalide
        uart._process_line("M:bad:00") # invalide
        uart._process_line("GARBAGE")  # invalide
        self.assertEqual(uart.crc_errors, 3)

    def test_crc_errors_resets_on_valid_message(self):
        """Un message valide remet le compteur à 0."""
        import configparser
        cfg = configparser.ConfigParser()
        cfg.add_section('master')
        cfg.set('master', 'uart_port', '/dev/ttyAMA0')
        cfg.set('master', 'uart_baud', '115200')
        cfg.set('master', 'heartbeat_interval_ms', '200')
        from master.uart_controller import UARTController
        from shared.uart_protocol import build_msg
        uart = UARTController(cfg)

        # Quelques erreurs
        uart._process_line("GARBAGE1")
        uart._process_line("GARBAGE2")
        self.assertEqual(uart.crc_errors, 2)

        # Message valide — doit reset le compteur
        valid = build_msg('H', 'OK').strip()
        uart._process_line(valid)
        self.assertEqual(uart.crc_errors, 0)


# ─────────────────────────────────────────────────────────────────────────────
# Tests logique seuils UI (simulés côté Python — miroir de la logique JS)
# ─────────────────────────────────────────────────────────────────────────────

def _ui_health_state(health_pct: float | None, master_crc_errors: int = 0) -> str:
    """
    Miroir de la logique JS _setHealthPill().
    Retourne : 'ok' | 'warn' | 'error' | 'grey'
    """
    if health_pct is None:
        return 'warn' if master_crc_errors > 0 else 'grey'
    if health_pct >= 95:
        return 'ok'
    if health_pct >= 70:
        return 'warn'
    return 'error'


def _ui_health_label(health_pct: float | None, master_crc_errors: int = 0) -> str:
    """Miroir du label JS."""
    if health_pct is None:
        return 'BUS ERR' if master_crc_errors > 0 else 'BUS ?%'
    return f'BUS {health_pct:.0f}%'


class TestUARTHealthThresholds(unittest.TestCase):
    """
    Valide les seuils d'affichage UART health sur l'interface web.

    Ces tests documentent et protègent les règles UX :
      - Vert  (ok)    : bus propre, ≥95%
      - Orange (warn) : interférences légères, 70-94%
      - Rouge (error) : bus très bruité, <70%
    """

    # --- Seuils état ok ---

    def test_100pct_is_ok(self):
        self.assertEqual(_ui_health_state(100.0), 'ok')

    def test_95pct_is_ok(self):
        self.assertEqual(_ui_health_state(95.0), 'ok')

    def test_label_shows_integer_percent(self):
        self.assertEqual(_ui_health_label(98.6), 'BUS 99%')

    # --- Seuil ok/warn = 95% ---

    def test_94pct_is_warn(self):
        """94.9% → orange, juste sous le seuil ok."""
        self.assertEqual(_ui_health_state(94.9), 'warn')

    def test_80pct_is_warn(self):
        self.assertEqual(_ui_health_state(80.0), 'warn')

    def test_70pct_is_warn(self):
        """70% → encore orange (limite basse)."""
        self.assertEqual(_ui_health_state(70.0), 'warn')

    # --- Seuil warn/error = 70% ---

    def test_69pct_is_error(self):
        """69.9% → rouge, juste sous le seuil warn."""
        self.assertEqual(_ui_health_state(69.9), 'error')

    def test_50pct_is_error(self):
        self.assertEqual(_ui_health_state(50.0), 'error')

    def test_10pct_is_error(self):
        """Bus catastrophique → rouge."""
        self.assertEqual(_ui_health_state(10.0), 'error')

    def test_0pct_is_error(self):
        self.assertEqual(_ui_health_state(0.0), 'error')

    # --- Slave injoignable ---

    def test_slave_null_no_master_errors_is_grey(self):
        """Slave injoignable + Master OK → gris (on ne sait pas encore)."""
        self.assertEqual(_ui_health_state(None, master_crc_errors=0), 'grey')

    def test_slave_null_with_master_errors_is_warn(self):
        """Slave injoignable + Master voit des CRC invalides → orange (signal mauvais)."""
        self.assertEqual(_ui_health_state(None, master_crc_errors=3), 'warn')

    def test_slave_null_label_no_errors(self):
        self.assertEqual(_ui_health_label(None, 0), 'BUS ?%')

    def test_slave_null_label_with_errors(self):
        self.assertEqual(_ui_health_label(None, 5), 'BUS ERR')

    # --- Progression dégradation ---

    def test_degradation_sequence(self):
        """
        Séquence complète de dégradation : bus propre → interférences → critique.
        Simule ce que l'interface afficherait pendant une course avec moteurs bruyants.
        """
        sequence = [
            (100.0, 'ok'),    # démarrage — bus parfait
            (98.0,  'ok'),    # quelques parasites normaux
            (92.0,  'warn'),  # moteurs 24V actifs — interférences
            (75.0,  'warn'),  # dégradation continue
            (65.0,  'error'), # slipring mal connecté ou parasites sévères
            (20.0,  'error'), # bus inutilisable
        ]
        for pct, expected in sequence:
            with self.subTest(pct=pct):
                self.assertEqual(_ui_health_state(pct), expected,
                                 f"{pct}% devrait afficher '{expected}'")


# ─────────────────────────────────────────────────────────────────────────────
# Tests status API — champ uart_crc_errors exposé
# ─────────────────────────────────────────────────────────────────────────────

class TestStatusApiUartErrors(unittest.TestCase):
    """
    Vérifie que /status expose bien uart_crc_errors depuis UARTController.
    """

    def setUp(self):
        """Mock le registry pour simuler différents états UART."""
        import configparser
        from master.uart_controller import UARTController
        cfg = configparser.ConfigParser()
        cfg.add_section('master')
        cfg.set('master', 'uart_port', '/dev/ttyAMA0')
        cfg.set('master', 'uart_baud', '115200')
        cfg.set('master', 'heartbeat_interval_ms', '200')
        self.uart = UARTController(cfg)

    def test_uart_crc_errors_zero_when_no_errors(self):
        """Aucune erreur CRC → uart_crc_errors = 0."""
        self.assertEqual(self.uart.crc_errors, 0)

    def test_uart_crc_errors_reflects_consecutive_invalids(self):
        """Erreurs consécutives → reflétées dans crc_errors."""
        for _ in range(5):
            self.uart._process_line("BAD:MSG:ZZ")
        self.assertEqual(self.uart.crc_errors, 5)

    def test_uart_crc_errors_resets_on_recovery(self):
        """Après récupération, crc_errors repasse à 0."""
        from shared.uart_protocol import build_msg
        self.uart._process_line("BAD")
        self.uart._process_line("BAD")
        valid = build_msg('H', 'OK').strip()
        self.uart._process_line(valid)
        self.assertEqual(self.uart.crc_errors, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
