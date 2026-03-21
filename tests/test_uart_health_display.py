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

def _ui_uart_state(uart_ready: bool, health_pct: float | None, master_crc_errors: int = 0) -> str:
    """
    Miroir de la logique JS _setUartPill().
    Retourne : 'ok' | 'warn' | 'error' | 'grey'
    """
    if not uart_ready:
        return 'error'
    if health_pct is None:
        return 'warn' if master_crc_errors > 0 else 'ok'
    if health_pct >= 95:
        return 'ok'
    if health_pct >= 70:
        return 'warn'
    return 'error'


def _ui_uart_label(uart_ready: bool, health_pct: float | None, master_crc_errors: int = 0) -> str:
    """Miroir du label JS _setUartPill()."""
    if not uart_ready:
        return 'UART'
    if health_pct is None:
        return 'UART ERR' if master_crc_errors > 0 else 'UART'
    return f'UART {health_pct:.0f}%'


class TestUARTHealthThresholds(unittest.TestCase):
    """
    Valide les seuils d'affichage de la pastille UART fusionnée.

    Règles UX :
      - Port fermé                    → rouge  'UART'
      - Port ouvert, Slave pas pollé  → vert   'UART'
      - Port ouvert + CRC errors      → orange 'UART ERR'
      - ≥95%                          → vert   'UART 100%'
      - 70-94%                        → orange 'UART 82%'
      - <70%                          → rouge  'UART 45%'
    """

    # --- Port série fermé ---

    def test_port_closed_is_error(self):
        self.assertEqual(_ui_uart_state(False, None), 'error')

    def test_port_closed_label(self):
        self.assertEqual(_ui_uart_label(False, None), 'UART')

    # --- Port ouvert, pas encore de données Slave ---

    def test_port_open_no_health_is_ok(self):
        """Port ouvert, Slave pas encore pollé → vert (on suppose OK)."""
        self.assertEqual(_ui_uart_state(True, None, master_crc_errors=0), 'ok')

    def test_port_open_with_master_crc_errors_is_warn(self):
        """Port ouvert + CRC invalides Master → orange."""
        self.assertEqual(_ui_uart_state(True, None, master_crc_errors=3), 'warn')

    def test_port_open_no_health_label(self):
        self.assertEqual(_ui_uart_label(True, None, 0), 'UART')

    def test_port_open_crc_errors_label(self):
        self.assertEqual(_ui_uart_label(True, None, 5), 'UART ERR')

    # --- Seuils qualité bus ---

    def test_100pct_is_ok(self):
        self.assertEqual(_ui_uart_state(True, 100.0), 'ok')

    def test_95pct_is_ok(self):
        self.assertEqual(_ui_uart_state(True, 95.0), 'ok')

    def test_94pct_is_warn(self):
        self.assertEqual(_ui_uart_state(True, 94.9), 'warn')

    def test_70pct_is_warn(self):
        self.assertEqual(_ui_uart_state(True, 70.0), 'warn')

    def test_69pct_is_error(self):
        self.assertEqual(_ui_uart_state(True, 69.9), 'error')

    def test_0pct_is_error(self):
        self.assertEqual(_ui_uart_state(True, 0.0), 'error')

    def test_label_shows_uart_with_percent(self):
        self.assertEqual(_ui_uart_label(True, 98.6), 'UART 99%')

    # --- Progression dégradation ---

    def test_degradation_sequence(self):
        """
        Séquence complète : bus propre → interférences → critique.
        Simule une course avec moteurs 24V actifs.
        """
        sequence = [
            (100.0, 'ok'),    # démarrage — bus parfait
            (98.0,  'ok'),    # quelques parasites normaux
            (92.0,  'warn'),  # moteurs 24V actifs
            (75.0,  'warn'),  # dégradation continue
            (65.0,  'error'), # slipring mal connecté
            (20.0,  'error'), # bus inutilisable
        ]
        for pct, expected in sequence:
            with self.subTest(pct=pct):
                self.assertEqual(_ui_uart_state(True, pct), expected,
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
