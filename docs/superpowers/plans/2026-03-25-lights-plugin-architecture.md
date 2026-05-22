# Lights Plugin Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the lights/Teeces system into a plugin architecture so builders configure `[lights] backend = teeces|astropixels` in `local.cfg` and the correct driver loads at boot — plus a web UI to swap backends and hot-reload without Pi reboot.

**Architecture:** `BaseLightsController(BaseDriver)` defines the canonical interface and backward-compat aliases. `TeecesDriver` (JawaLite) and `AstroPixelsDriver` (AstroPixels+) implement it. A `load_driver(cfg)` factory in `master/lights/__init__.py` reads `[lights] backend` and returns the right instance. All existing callers continue using `reg.teeces` — the registry type changes but the name stays to avoid touching every call site. A new `POST /settings/lights` endpoint writes to `local.cfg` and hot-swaps `reg.teeces` without rebooting.

**Tech Stack:** Python 3.10+, pyserial, Flask blueprints, configparser, threading.Timer, unittest/MagicMock

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `master/lights/__init__.py` | Factory `load_driver(cfg)` |
| Create | `master/lights/base_controller.py` | Abstract `BaseLightsController` + backward-compat aliases |
| Create | `master/lights/teeces.py` | `TeecesDriver` — JawaLite serial |
| Create | `master/lights/astropixels.py` | `AstroPixelsDriver` — AstroPixels+ serial |
| Create | `tests/test_lights_plugin.py` | All unit tests (serial mocked) |
| Modify | `master/config/main.cfg` | Add `[lights] backend = teeces` |
| Modify | `master/main.py` | Use `load_driver()` instead of `TeecesController()` |
| Modify | `master/registry.py` | Type hint `reg.teeces` → `BaseLightsController` |
| Modify | `master/api/teeces_bp.py` | Use new interface; ANIMATIONS from base class |
| Modify | `master/script_engine.py` | Use new interface method names |
| Modify | `master/deploy_controller.py` | Use `system_error()` + `show_version()` |
| Modify | `master/api/settings_bp.py` | Add `lights.backend` to GET + `POST /settings/lights` |
| Modify | `master/templates/index.html` | "LIGHTS BACKEND" card in tab-config |
| Modify | `master/static/js/app.js` | `lightsSettings` JS object + Apply button |
| Modify | `android/app/src/main/assets/index.html` | Sync from templates/index.html |
| Modify | `android/app/src/main/assets/js/app.js` | Sync from static/js/app.js |

`master/teeces_controller.py` — **left as-is** (not imported by main.py after this refactor, but kept for reference).

---

## Task 1: Base Abstract Controller

**Files:**
- Create: `master/lights/__init__.py` (empty package marker)
- Create: `master/lights/base_controller.py`
- Create: `tests/test_lights_plugin.py`

- [ ] **Step 1.1: Write failing tests**

```python
# tests/test_lights_plugin.py
import sys, os, types, unittest
from unittest.mock import MagicMock, patch

# Stub serial so it imports without hardware
sys.modules.setdefault('serial', MagicMock())

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from master.lights.base_controller import BaseLightsController


class TestBaseController(unittest.TestCase):

    def test_cannot_instantiate_directly(self):
        """BaseLightsController is abstract."""
        import inspect
        self.assertTrue(inspect.isabstract(BaseLightsController))

    def test_required_abstract_methods(self):
        """All required methods are abstract."""
        abstract = BaseLightsController.__abstractmethods__
        for name in ('setup', 'shutdown', 'is_ready',
                     'random_mode', 'leia', 'off',
                     'text', 'animation', 'psi', 'raw',
                     'system_error', 'system_ok',
                     'slave_offline', 'uart_error'):
            self.assertIn(name, abstract, f"{name} must be abstract")

    def test_backward_compat_aliases_present(self):
        """Concrete aliases exist on the class for drop-in callers."""

        class _Concrete(BaseLightsController):
            ANIMATIONS = {}
            def setup(self):        return True
            def shutdown(self):     pass
            def is_ready(self):     return True
            def random_mode(self):  return True
            def leia(self):         return True
            def off(self):          return True
            def text(self, msg, target="both"): return True
            def animation(self, code): return True
            def psi(self, state):   return True
            def raw(self, cmd):     return True
            def system_error(self, msg=""): return True
            def system_ok(self, msg=""):    return True
            def slave_offline(self):        return True
            def uart_error(self):           return True
            def show_version(self, v):      return True
            def alert_error(self, c=""):    return True

        obj = _Concrete()
        # Backward-compat aliases — must not raise
        self.assertTrue(obj.all_off())
        self.assertTrue(obj.leia_mode())
        self.assertTrue(obj.psi_mode(1))
        self.assertTrue(obj.psi_random())
        self.assertTrue(obj.fld_text("X"))
        self.assertTrue(obj.rld_text("X"))
        self.assertTrue(obj.send_raw("0T1"))
        self.assertTrue(obj.alert_master_offline())

    def test_animations_dict_on_class(self):
        """ANIMATIONS class attribute has expected T-codes."""

        class _Concrete(BaseLightsController):
            def setup(self):        return True
            def shutdown(self):     pass
            def is_ready(self):     return True
            def random_mode(self):  return True
            def leia(self):         return True
            def off(self):          return True
            def text(self, msg, target="both"): return True
            def animation(self, code): return True
            def psi(self, state):   return True
            def raw(self, cmd):     return True
            def system_error(self, msg=""): return True
            def system_ok(self, msg=""):    return True
            def slave_offline(self):        return True
            def uart_error(self):           return True
            def show_version(self, v):      return True
            def alert_error(self, c=""):    return True

        obj = _Concrete()
        self.assertIn(1, obj.ANIMATIONS)   # Random
        self.assertIn(11, obj.ANIMATIONS)  # Imperial March
        self.assertIn(20, obj.ANIMATIONS)  # Off


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 1.2: Run — expect FAIL** (module not found)

```bash
cd J:/R2-D2_Build/software
python -m pytest tests/test_lights_plugin.py::TestBaseController -v
```

Expected: `ModuleNotFoundError: No module named 'master.lights'`

- [ ] **Step 1.3: Create `master/lights/__init__.py`** (empty for now)

```python
# master/lights/__init__.py
# Factory imported in Task 4
```

- [ ] **Step 1.4: Create `master/lights/base_controller.py`**

```python
# master/lights/base_controller.py
"""
Interface abstraite commune à tous les drivers lights.

Tous les drivers (TeecesDriver, AstroPixelsDriver, …) héritent de cette
classe et implémentent les méthodes marquées @abstractmethod.

Les méthodes non-abstraites sont des alias de rétro-compatibilité pour les
appelants qui utilisaient encore l'ancienne API TeecesController — ils
n'ont pas besoin d'être mis à jour immédiatement.
"""

from abc import ABC, abstractmethod
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.base_driver import BaseDriver


class BaseLightsController(BaseDriver, ABC):
    """Interface canonique pour tous les drivers lights R2-D2."""

    # Catalogue d'animations — numérotation T-code commune à tous les drivers
    ANIMATIONS: dict[int, str] = {
        1:  'Random',
        2:  'Flash',
        3:  'Alarm',
        4:  'Short Circuit',
        5:  'Scream',
        6:  'Leia Message',
        7:  'I Heart U',
        8:  'Panel Sweep',
        9:  'Pulse Monitor',
        10: 'Star Wars Scroll',
        11: 'Imperial March',
        12: 'Disco (timed)',
        13: 'Disco',
        14: 'Rebel Symbol',
        15: 'Knight Rider',
        16: 'Test White',
        17: 'Red On',
        18: 'Green On',
        19: 'Lightsaber',
        20: 'Off',
        21: 'VU Meter (timed)',
        92: 'VU Meter',
    }

    # ------------------------------------------------------------------
    # Interface canonique (à implémenter dans chaque driver)
    # ------------------------------------------------------------------

    @abstractmethod
    def setup(self) -> bool:
        """Ouvre le port série. Retourne False si échec."""

    @abstractmethod
    def shutdown(self) -> None:
        """Arrêt propre — éteint les LEDs et ferme le port."""

    @abstractmethod
    def is_ready(self) -> bool:
        """True si le port est ouvert et opérationnel."""

    @abstractmethod
    def random_mode(self) -> bool:
        """Mode animations aléatoires (mode normal R2)."""

    @abstractmethod
    def leia(self) -> bool:
        """Mode hologramme Leia."""

    @abstractmethod
    def off(self) -> bool:
        """Éteint toutes les LEDs."""

    @abstractmethod
    def text(self, message: str, target: str = "both") -> bool:
        """
        Texte défilant sur les logics.
        target: "fld" | "rld" | "both"
        """

    @abstractmethod
    def animation(self, code: int) -> bool:
        """Déclenche une animation par T-code (voir ANIMATIONS)."""

    @abstractmethod
    def psi(self, state: int) -> bool:
        """Contrôle les PSI. 0=off, 1=random, 2-8=couleurs."""

    @abstractmethod
    def raw(self, cmd: str) -> bool:
        """Envoie une commande brute (protocole natif du driver)."""

    @abstractmethod
    def system_error(self, message: str = "") -> bool:
        """Alerte visuelle erreur système."""

    @abstractmethod
    def system_ok(self, message: str = "") -> bool:
        """Confirmation visuelle succès (vert 3s puis retour random)."""

    @abstractmethod
    def slave_offline(self) -> bool:
        """Alerte visuelle Slave hors ligne."""

    @abstractmethod
    def uart_error(self) -> bool:
        """Alerte visuelle erreur UART."""

    @abstractmethod
    def show_version(self, version: str) -> bool:
        """Affiche la version sur les logics."""

    @abstractmethod
    def alert_error(self, code: str = "") -> bool:
        """Affiche un code d'erreur sur les logics."""

    # ------------------------------------------------------------------
    # Aliases de rétro-compatibilité (non-abstraits — hérités gratuitement)
    # Les appelants (script_engine, teeces_bp, deploy_controller) qui
    # utilisaient l'ancienne API TeecesController continuent de fonctionner
    # le temps d'être mis à jour.
    # ------------------------------------------------------------------

    def all_off(self) -> bool:
        return self.off()

    def leia_mode(self) -> bool:
        return self.leia()

    def psi_mode(self, mode: int) -> bool:
        return self.psi(mode)

    def psi_random(self) -> bool:
        return self.psi(1)

    def fld_text(self, message: str) -> bool:
        return self.text(message, "fld")

    def rld_text(self, message: str) -> bool:
        return self.text(message, "rld")

    def send_raw(self, cmd: str) -> bool:
        return self.raw(cmd)

    def alert_master_offline(self) -> bool:
        return self.slave_offline()
```

- [ ] **Step 1.5: Run — expect PASS**

```bash
python -m pytest tests/test_lights_plugin.py::TestBaseController -v
```

Expected: `4 passed`

- [ ] **Step 1.6: Commit**

```bash
git add master/lights/__init__.py master/lights/base_controller.py tests/test_lights_plugin.py
git commit -m "Feat: lights plugin — BaseLightsController abstract interface"
```

---

## Task 2: TeecesDriver

**Files:**
- Create: `master/lights/teeces.py`
- Extend: `tests/test_lights_plugin.py`

- [ ] **Step 2.1: Append failing tests to `tests/test_lights_plugin.py`**

```python
# Append to tests/test_lights_plugin.py (after TestBaseController class)

from master.lights.teeces import TeecesDriver
import configparser


def _teeces_cfg(port='/dev/ttyUSB0', baud=9600, backend='teeces') -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    cfg.add_section('teeces')
    cfg.set('teeces', 'port', port)
    cfg.set('teeces', 'baud', str(baud))
    cfg.add_section('lights')
    cfg.set('lights', 'backend', backend)
    return cfg


class TestTeecesDriver(unittest.TestCase):

    def _make_driver(self):
        """Driver avec serial mocké, port déjà ouvert."""
        cfg = _teeces_cfg()
        with patch('serial.Serial') as mock_cls:
            mock_serial = MagicMock()
            mock_serial.is_open = True
            mock_cls.return_value = mock_serial
            d = TeecesDriver(cfg)
            d.setup()
        d._serial = mock_serial  # accès direct pour assertions
        d._ready  = True
        return d, mock_serial

    def test_random_mode(self):
        d, ser = self._make_driver()
        d.random_mode()
        ser.write.assert_called_with(b'0T1\r')

    def test_leia(self):
        d, ser = self._make_driver()
        d.leia()
        ser.write.assert_called_with(b'0T6\r')

    def test_off(self):
        d, ser = self._make_driver()
        d.off()
        ser.write.assert_called_with(b'0T20\r')

    def test_text_fld(self):
        d, ser = self._make_driver()
        d.text("HELLO", "fld")
        ser.write.assert_called_with(b'1MHELLO\r')

    def test_text_rld(self):
        d, ser = self._make_driver()
        d.text("HELLO", "rld")
        ser.write.assert_called_with(b'2MHELLO\r')

    def test_text_both_sends_two_writes(self):
        d, ser = self._make_driver()
        d.text("HELLO", "both")
        calls = [c.args[0] for c in ser.write.call_args_list]
        self.assertIn(b'1MHELLO\r', calls)
        self.assertIn(b'2MHELLO\r', calls)

    def test_text_uppercase_truncated(self):
        d, ser = self._make_driver()
        d.text("hello world this is way too long for display", "fld")
        written = ser.write.call_args[0][0].decode()
        # Must be uppercase and ≤ max_len + "1M" + "\r"
        self.assertTrue(written.startswith('1M'))
        self.assertTrue(written[2:-1].isupper())

    def test_animation(self):
        d, ser = self._make_driver()
        d.animation(11)
        ser.write.assert_called_with(b'0T11\r')

    def test_psi(self):
        d, ser = self._make_driver()
        d.psi(3)
        ser.write.assert_called_with(b'4S3\r')

    def test_psi_clamped_negative(self):
        d, ser = self._make_driver()
        d.psi(-5)
        ser.write.assert_called_with(b'4S0\r')

    def test_raw_appends_cr(self):
        d, ser = self._make_driver()
        d.raw("0T5")
        ser.write.assert_called_with(b'0T5\r')

    def test_raw_no_double_cr(self):
        d, ser = self._make_driver()
        d.raw("0T5\r")
        ser.write.assert_called_with(b'0T5\r')

    def test_slave_offline(self):
        d, ser = self._make_driver()
        d.slave_offline()
        calls = b''.join(c.args[0] for c in ser.write.call_args_list)
        self.assertIn(b'SLAVE DOWN', calls)

    def test_uart_error(self):
        d, ser = self._make_driver()
        d.uart_error()
        calls = b''.join(c.args[0] for c in ser.write.call_args_list)
        self.assertIn(b'UART ERROR', calls)

    def test_system_error(self):
        d, ser = self._make_driver()
        d.system_error("SYNC")
        calls = b''.join(c.args[0] for c in ser.write.call_args_list)
        self.assertIn(b'SYNC', calls)

    def test_is_subclass_of_base(self):
        from master.lights.base_controller import BaseLightsController
        self.assertTrue(issubclass(TeecesDriver, BaseLightsController))

    def test_not_ready_when_serial_closed(self):
        cfg = _teeces_cfg()
        d = TeecesDriver(cfg)
        # setup() never called → not ready
        self.assertFalse(d.is_ready())

    def test_setup_fail_returns_false(self):
        import serial as ser_mod
        cfg = _teeces_cfg()
        with patch('serial.Serial', side_effect=ser_mod.SerialException("no port")):
            d = TeecesDriver(cfg)
            result = d.setup()
        self.assertFalse(result)
        self.assertFalse(d.is_ready())

    def test_backward_compat_all_off(self):
        d, ser = self._make_driver()
        d.all_off()  # inherited alias → off() → 0T20
        ser.write.assert_called_with(b'0T20\r')

    def test_show_version(self):
        d, ser = self._make_driver()
        d.show_version("abc1234")
        calls = b''.join(c.args[0] for c in ser.write.call_args_list)
        self.assertIn(b'VER', calls)
```

- [ ] **Step 2.2: Run — expect FAIL** (TeecesDriver not found)

```bash
python -m pytest tests/test_lights_plugin.py::TestTeecesDriver -v
```

Expected: `ImportError: cannot import name 'TeecesDriver'`

- [ ] **Step 2.3: Create `master/lights/teeces.py`**

```python
# master/lights/teeces.py
"""
TeecesDriver — Protocole JawaLite via USB série (Teeces32 board).

Commandes JawaLite :
  0T{n}\r      Animations logics (0T1=random, 0T6=leia, 0T20=off)
  1M{txt}\r    Texte FLD (Front Logic Display)
  2M{txt}\r    Texte RLD (Rear Logic Display)
  4S{n}\r      Mode PSI (0=off, 1=random, 2-8=couleurs)

Port et baud lus dans [teeces] du config (port=/dev/ttyUSB0, baud=9600).
"""

import logging
import serial
import configparser
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from master.lights.base_controller import BaseLightsController

log = logging.getLogger(__name__)

_MAX_TEXT = 20          # max chars JawaLite (hardware limit Teeces32)
_OK_DURATION = 3.0      # secondes d'affichage system_ok avant retour random


class TeecesDriver(BaseLightsController):
    """Driver JawaLite pour la carte Teeces32."""

    def __init__(self, cfg: configparser.ConfigParser):
        self._port   = cfg.get('teeces', 'port')
        self._baud   = cfg.getint('teeces', 'baud')
        self._serial: serial.Serial | None = None
        self._ready  = False
        self._ok_timer = None

    # ------------------------------------------------------------------
    # BaseDriver
    # ------------------------------------------------------------------

    def setup(self) -> bool:
        try:
            self._serial = serial.Serial(self._port, self._baud, timeout=1)
            self._ready  = True
            log.info(f"TeecesDriver ouvert: {self._port} @ {self._baud}")
            return True
        except serial.SerialException as e:
            log.error(f"TeecesDriver impossible d'ouvrir {self._port}: {e}")
            self._ready = False
            return False

    def shutdown(self) -> None:
        self._cancel_ok_timer()
        self.off()
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._ready = False
        log.info("TeecesDriver arrêté")

    def is_ready(self) -> bool:
        return self._ready and self._serial is not None and self._serial.is_open

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------

    def _send(self, cmd: str) -> bool:
        if not self.is_ready():
            log.warning(f"TeecesDriver non prêt, ignoré: {cmd!r}")
            return False
        try:
            self._serial.write(cmd.encode('ascii'))
            log.debug(f"Teeces TX: {cmd!r}")
            return True
        except serial.SerialException as e:
            log.error(f"TeecesDriver erreur send: {e}")
            self._ready = False
            return False

    def _cancel_ok_timer(self) -> None:
        if self._ok_timer is not None:
            self._ok_timer.cancel()
            self._ok_timer = None

    # ------------------------------------------------------------------
    # Interface canonique
    # ------------------------------------------------------------------

    def random_mode(self) -> bool:
        return self._send("0T1\r")

    def leia(self) -> bool:
        return self._send("0T6\r")

    def off(self) -> bool:
        return self._send("0T20\r")

    def text(self, message: str, target: str = "both") -> bool:
        msg = message[:_MAX_TEXT].upper()
        t   = target.lower()
        if t == "fld":
            return self._send(f"1M{msg}\r")
        if t == "rld":
            return self._send(f"2M{msg}\r")
        # "both" — JawaLite n'a pas de commande combinée
        ok1 = self._send(f"1M{msg}\r")
        ok2 = self._send(f"2M{msg}\r")
        return ok1 and ok2

    def animation(self, code: int) -> bool:
        return self._send(f"0T{int(code)}\r")

    def psi(self, state: int) -> bool:
        return self._send(f"4S{max(0, int(state))}\r")

    def raw(self, cmd: str) -> bool:
        if not cmd.endswith('\r'):
            cmd = cmd + '\r'
        return self._send(cmd)

    def system_error(self, message: str = "") -> bool:
        self._cancel_ok_timer()
        label = f"ERROR {message}".strip()[:_MAX_TEXT]
        ok1   = self._send("0T3\r")          # Alarm animation
        ok2   = self.text(label, "both")
        log.warning(f"TeecesDriver system_error: {label!r}")
        return ok1 and ok2

    def system_ok(self, message: str = "") -> bool:
        import threading
        self._cancel_ok_timer()
        label = (message or "OK")[:_MAX_TEXT].upper()
        ok1   = self._send("0T18\r")         # Green On
        ok2   = self.text(label, "both")
        log.info(f"TeecesDriver system_ok: {label!r}")

        def _restore():
            self._ok_timer = None
            self.random_mode()

        self._ok_timer = threading.Timer(_OK_DURATION, _restore)
        self._ok_timer.daemon = True
        self._ok_timer.start()
        return ok1 and ok2

    def slave_offline(self) -> bool:
        self._cancel_ok_timer()
        ok1 = self._send("0T3\r")
        ok2 = self.text("SLAVE DOWN", "both")
        log.error("TeecesDriver slave_offline")
        return ok1 and ok2

    def uart_error(self) -> bool:
        self._cancel_ok_timer()
        ok1 = self.text("UART ERROR", "both")
        ok2 = self._send("0T2\r")            # Flash
        log.error("TeecesDriver uart_error")
        return ok1 and ok2

    def show_version(self, version: str) -> bool:
        return self.text(f"VER {version}", "both")

    def alert_error(self, code: str = "") -> bool:
        label = f"ERREUR {code}".strip()[:_MAX_TEXT]
        return self.text(label, "both")
```

- [ ] **Step 2.4: Run — expect PASS**

```bash
python -m pytest tests/test_lights_plugin.py::TestTeecesDriver -v
```

Expected: all `TestTeecesDriver` tests pass.

- [ ] **Step 2.5: Commit**

```bash
git add master/lights/teeces.py tests/test_lights_plugin.py
git commit -m "Feat: lights plugin — TeecesDriver (JawaLite)"
```

---

## Task 3: AstroPixelsDriver

**Files:**
- Create: `master/lights/astropixels.py`
- Extend: `tests/test_lights_plugin.py`

- [ ] **Step 3.1: Append failing tests**

```python
# Append to tests/test_lights_plugin.py

from master.lights.astropixels import AstroPixelsDriver


class TestAstroPixelsDriver(unittest.TestCase):

    def _make_driver(self):
        cfg = _teeces_cfg()
        with patch('serial.Serial') as mock_cls:
            mock_serial = MagicMock()
            mock_serial.is_open = True
            mock_cls.return_value = mock_serial
            d = AstroPixelsDriver(cfg)
            d.setup()
        d._serial = mock_serial
        d._ready  = True
        return d, mock_serial

    def _all_written(self, ser):
        return b''.join(c.args[0] for c in ser.write.call_args_list)

    def test_random_mode(self):
        d, ser = self._make_driver()
        d.random_mode()
        ser.write.assert_called_with(b'@0T1\r')

    def test_leia(self):
        d, ser = self._make_driver()
        d.leia()
        ser.write.assert_called_with(b'@0T6\r')

    def test_off(self):
        d, ser = self._make_driver()
        d.off()
        ser.write.assert_called_with(b'@0T20\r')

    def test_text_fld(self):
        d, ser = self._make_driver()
        d.text("HELLO", "fld")
        ser.write.assert_called_with(b'@1MHELLO\r')

    def test_text_rld(self):
        d, ser = self._make_driver()
        d.text("HELLO", "rld")
        ser.write.assert_called_with(b'@2MHELLO\r')

    def test_text_both_single_command(self):
        """AstroPixels+ a @3M — un seul write pour both."""
        d, ser = self._make_driver()
        d.text("HELLO", "both")
        self.assertEqual(ser.write.call_count, 1)
        ser.write.assert_called_with(b'@3MHELLO\r')

    def test_text_uppercase_truncated(self):
        d, ser = self._make_driver()
        d.text("hello world this is way too long for display", "both")
        written = ser.write.call_args[0][0].decode()
        self.assertTrue(written.startswith('@3M'))
        self.assertTrue(written[3:-1].isupper())

    def test_animation(self):
        d, ser = self._make_driver()
        d.animation(11)
        ser.write.assert_called_with(b'@0T11\r')

    def test_psi(self):
        d, ser = self._make_driver()
        d.psi(3)
        ser.write.assert_called_with(b'@4S3\r')

    def test_psi_clamped_negative(self):
        d, ser = self._make_driver()
        d.psi(-1)
        ser.write.assert_called_with(b'@4S0\r')

    def test_raw_appends_cr(self):
        d, ser = self._make_driver()
        d.raw("@0T5")
        ser.write.assert_called_with(b'@0T5\r')

    def test_slave_offline(self):
        d, ser = self._make_driver()
        d.slave_offline()
        data = self._all_written(ser)
        self.assertIn(b'SLAVE DOWN', data)
        self.assertIn(b'@3M', data)

    def test_uart_error(self):
        d, ser = self._make_driver()
        d.uart_error()
        data = self._all_written(ser)
        self.assertIn(b'UART ERROR', data)
        self.assertIn(b'@3M', data)

    def test_system_error(self):
        d, ser = self._make_driver()
        d.system_error("DB FAIL")
        data = self._all_written(ser)
        self.assertIn(b'DB FAIL', data)

    def test_is_subclass_of_base(self):
        from master.lights.base_controller import BaseLightsController
        self.assertTrue(issubclass(AstroPixelsDriver, BaseLightsController))

    def test_setup_fail_returns_false(self):
        import serial as ser_mod
        cfg = _teeces_cfg()
        with patch('serial.Serial', side_effect=ser_mod.SerialException("no port")):
            d = AstroPixelsDriver(cfg)
            result = d.setup()
        self.assertFalse(result)
        self.assertFalse(d.is_ready())

    def test_backward_compat_fld_text(self):
        """fld_text() alias routes to text(..., 'fld')."""
        d, ser = self._make_driver()
        d.fld_text("TEST")
        ser.write.assert_called_with(b'@1MTEST\r')
```

- [ ] **Step 3.2: Run — expect FAIL**

```bash
python -m pytest tests/test_lights_plugin.py::TestAstroPixelsDriver -v
```

Expected: `ImportError: cannot import name 'AstroPixelsDriver'`

- [ ] **Step 3.3: Create `master/lights/astropixels.py`**

```python
# master/lights/astropixels.py
"""
AstroPixelsDriver — Protocole AstroPixelsPlus via USB série.

Commandes AstroPixels+ (@ prefix, \r terminateur) :
  @0T{n}\r     Animations logics (identiques T-codes JawaLite)
  @1M{txt}\r   Texte FLD uniquement
  @2M{txt}\r   Texte RLD uniquement
  @3M{txt}\r   Texte FLD + RLD simultané (commande combinée)
  @4S{n}\r     Mode PSI (0=off, 1=random, 2-8=couleurs)

Port et baud lus dans [teeces] du config (même section que Teeces).
"""

import logging
import serial
import configparser
import threading
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from master.lights.base_controller import BaseLightsController

log = logging.getLogger(__name__)

_MAX_TEXT    = 32         # AstroPixels+ accepte jusqu'à 32 chars
_OK_DURATION = 3.0        # secondes avant retour random après system_ok

_TEXT_PREFIX = {
    "fld":  "@1M",
    "rld":  "@2M",
    "both": "@3M",
}


class AstroPixelsDriver(BaseLightsController):
    """Driver AstroPixels+ (commandes @-préfixées)."""

    def __init__(self, cfg: configparser.ConfigParser):
        self._port   = cfg.get('teeces', 'port')
        self._baud   = cfg.getint('teeces', 'baud')
        self._serial: serial.Serial | None = None
        self._ready  = False
        self._ok_timer: threading.Timer | None = None

    # ------------------------------------------------------------------
    # BaseDriver
    # ------------------------------------------------------------------

    def setup(self) -> bool:
        try:
            self._serial = serial.Serial(self._port, self._baud, timeout=1)
            self._ready  = True
            log.info(f"AstroPixelsDriver ouvert: {self._port} @ {self._baud}")
            return True
        except serial.SerialException as e:
            log.error(f"AstroPixelsDriver impossible d'ouvrir {self._port}: {e}")
            self._ready = False
            return False

    def shutdown(self) -> None:
        self._cancel_ok_timer()
        self.off()
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._ready = False
        log.info("AstroPixelsDriver arrêté")

    def is_ready(self) -> bool:
        return self._ready and self._serial is not None and self._serial.is_open

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------

    def _send(self, cmd: str) -> bool:
        if not self.is_ready():
            log.warning(f"AstroPixelsDriver non prêt, ignoré: {cmd!r}")
            return False
        try:
            self._serial.write(cmd.encode('ascii'))
            log.debug(f"AstroPixels+ TX: {cmd!r}")
            return True
        except serial.SerialException as e:
            log.error(f"AstroPixelsDriver erreur send: {e}")
            self._ready = False
            return False

    def _cancel_ok_timer(self) -> None:
        if self._ok_timer is not None:
            self._ok_timer.cancel()
            self._ok_timer = None

    # ------------------------------------------------------------------
    # Interface canonique
    # ------------------------------------------------------------------

    def random_mode(self) -> bool:
        return self._send("@0T1\r")

    def leia(self) -> bool:
        return self._send("@0T6\r")

    def off(self) -> bool:
        return self._send("@0T20\r")

    def text(self, message: str, target: str = "both") -> bool:
        msg    = message[:_MAX_TEXT].upper()
        prefix = _TEXT_PREFIX.get(target.lower(), "@3M")
        return self._send(f"{prefix}{msg}\r")

    def animation(self, code: int) -> bool:
        return self._send(f"@0T{int(code)}\r")

    def psi(self, state: int) -> bool:
        return self._send(f"@4S{max(0, int(state))}\r")

    def raw(self, cmd: str) -> bool:
        if not cmd.endswith('\r'):
            cmd = cmd + '\r'
        return self._send(cmd)

    def system_error(self, message: str = "") -> bool:
        self._cancel_ok_timer()
        label = f"ERROR {message}".strip()[:_MAX_TEXT]
        ok1   = self._send("@0T3\r")          # Alarm
        ok2   = self.text(label, "both")
        log.warning(f"AstroPixelsDriver system_error: {label!r}")
        return ok1 and ok2

    def system_ok(self, message: str = "") -> bool:
        self._cancel_ok_timer()
        label = (message or "OK")[:_MAX_TEXT].upper()
        ok1   = self._send("@0T18\r")         # Green On
        ok2   = self.text(label, "both")
        log.info(f"AstroPixelsDriver system_ok: {label!r}")

        def _restore():
            self._ok_timer = None
            self.random_mode()

        self._ok_timer = threading.Timer(_OK_DURATION, _restore)
        self._ok_timer.daemon = True
        self._ok_timer.start()
        return ok1 and ok2

    def slave_offline(self) -> bool:
        self._cancel_ok_timer()
        ok1 = self._send("@0T3\r")
        ok2 = self._send("@3MSLAVE DOWN\r")
        log.error("AstroPixelsDriver slave_offline")
        return ok1 and ok2

    def uart_error(self) -> bool:
        self._cancel_ok_timer()
        ok1 = self._send("@3MUART ERROR\r")
        ok2 = self._send("@0T2\r")            # Flash
        log.error("AstroPixelsDriver uart_error")
        return ok1 and ok2

    def show_version(self, version: str) -> bool:
        return self.text(f"VER {version}", "both")

    def alert_error(self, code: str = "") -> bool:
        label = f"ERREUR {code}".strip()[:_MAX_TEXT]
        return self.text(label, "both")
```

- [ ] **Step 3.4: Run — expect PASS**

```bash
python -m pytest tests/test_lights_plugin.py::TestAstroPixelsDriver -v
```

- [ ] **Step 3.5: Full suite still green**

```bash
python -m pytest tests/test_lights_plugin.py -v
```

- [ ] **Step 3.6: Commit**

```bash
git add master/lights/astropixels.py tests/test_lights_plugin.py
git commit -m "Feat: lights plugin — AstroPixelsDriver (@-protocol)"
```

---

## Task 4: Factory `load_driver()`

**Files:**
- Modify: `master/lights/__init__.py`
- Extend: `tests/test_lights_plugin.py`

- [ ] **Step 4.1: Append failing factory tests**

```python
# Append to tests/test_lights_plugin.py

from master.lights import load_driver


class TestLoadDriverFactory(unittest.TestCase):

    def _cfg(self, backend: str) -> configparser.ConfigParser:
        cfg = _teeces_cfg()
        cfg.set('lights', 'backend', backend)
        return cfg

    def test_teeces_backend(self):
        self.assertIsInstance(load_driver(self._cfg('teeces')), TeecesDriver)

    def test_astropixels_backend(self):
        self.assertIsInstance(load_driver(self._cfg('astropixels')), AstroPixelsDriver)

    def test_unknown_backend_raises(self):
        with self.assertRaises(ValueError):
            load_driver(self._cfg('magic_led'))

    def test_default_fallback_is_teeces(self):
        """Si [lights] absent du config → TeecesDriver par défaut."""
        cfg = configparser.ConfigParser()
        cfg.add_section('teeces')
        cfg.set('teeces', 'port', '/dev/ttyUSB0')
        cfg.set('teeces', 'baud', '9600')
        # Pas de section [lights]
        self.assertIsInstance(load_driver(cfg), TeecesDriver)

    def test_returned_driver_is_base_subclass(self):
        from master.lights.base_controller import BaseLightsController
        d = load_driver(self._cfg('teeces'))
        self.assertIsInstance(d, BaseLightsController)
```

- [ ] **Step 4.2: Run — expect FAIL**

```bash
python -m pytest tests/test_lights_plugin.py::TestLoadDriverFactory -v
```

Expected: `ImportError` — `load_driver` not in `__init__.py`

- [ ] **Step 4.3: Implement factory in `master/lights/__init__.py`**

```python
# master/lights/__init__.py
"""
Factory lights — charge le bon driver selon [lights] backend dans config.

Usage dans main.py :
    from master.lights import load_driver
    lights = load_driver(cfg)   # TeecesDriver ou AstroPixelsDriver
"""

import configparser


def load_driver(cfg: configparser.ConfigParser):
    """
    Retourne l'instance du driver lights configuré.

    Config (main.cfg ou local.cfg) :
        [lights]
        backend = teeces          # ou astropixels

    Lève ValueError si le backend est inconnu.
    Fallback = teeces si la section [lights] est absente.
    """
    backend = cfg.get('lights', 'backend', fallback='teeces').strip().lower()

    if backend == 'teeces':
        from master.lights.teeces import TeecesDriver
        return TeecesDriver(cfg)

    if backend == 'astropixels':
        from master.lights.astropixels import AstroPixelsDriver
        return AstroPixelsDriver(cfg)

    raise ValueError(
        f"Backend lights inconnu: {backend!r}. "
        f"Valeurs valides: teeces, astropixels"
    )
```

- [ ] **Step 4.4: Run — expect PASS**

```bash
python -m pytest tests/test_lights_plugin.py -v
```

Expected: tous les tests passent.

- [ ] **Step 4.5: Commit**

```bash
git add master/lights/__init__.py tests/test_lights_plugin.py
git commit -m "Feat: lights plugin — factory load_driver()"
```

---

## Task 5: Wire — Config + `main.py` + `registry.py`

**Files:**
- Modify: `master/config/main.cfg` (ajouter section `[lights]`)
- Modify: `master/main.py` (utiliser `load_driver()`)
- Modify: `master/registry.py` (type hint)

- [ ] **Step 5.1: Ajouter `[lights]` dans `master/config/main.cfg`**

Ajouter après la section `[teeces]` :

```ini
[lights]
# Driver lights actif : teeces | astropixels
backend = teeces
```

- [ ] **Step 5.2: Modifier `master/main.py`**

Remplacer les lignes suivantes :

```python
# AVANT (ligne ~55)
from master.teeces_controller import TeecesController
# ...
# AVANT (ligne ~210)
teeces = TeecesController(cfg)
```

Par :

```python
# APRÈS
from master.lights import load_driver
# ...
# APRÈS
teeces = load_driver(cfg)
```

Aussi dans la fonction `shutdown()` (ligne ~367), la ligne `teeces.shutdown()` reste identique — `BaseLightsController` a `shutdown()`.

Vérification : rechercher dans `main.py` toute référence directe à `TeecesController` — il ne doit plus en rester après ce changement.

- [ ] **Step 5.3: Modifier `master/registry.py`**

Remplacer le bloc TYPE_CHECKING :

```python
# AVANT
if TYPE_CHECKING:
    from master.teeces_controller    import TeecesController
    ...
teeces:      'TeecesController | None'  = None
```

Par :

```python
# APRÈS
if TYPE_CHECKING:
    from master.lights.base_controller import BaseLightsController
    ...
teeces:      'BaseLightsController | None' = None
```

- [ ] **Step 5.4: Vérifier la suite de tests**

```bash
python -m pytest tests/test_lights_plugin.py -v
```

Expected: tous passent (on n'a pas touché aux drivers).

- [ ] **Step 5.5: Commit**

```bash
git add master/config/main.cfg master/main.py master/registry.py
git commit -m "Feat: lights plugin — wiring factory dans main.py + registry"
```

---

## Task 6: Mettre à jour les appelants

`teeces_bp.py`, `script_engine.py`, `deploy_controller.py` utilisaient les vieilles méthodes de `TeecesController`. Les alias dans `BaseLightsController` garantissent que rien ne casse, mais on nettoie pour utiliser l'API canonique.

**Files:**
- Modify: `master/api/teeces_bp.py`
- Modify: `master/script_engine.py`
- Modify: `master/deploy_controller.py`

- [ ] **Step 6.1: Modifier `master/api/teeces_bp.py`**

Trois changements :

**a)** Remplacer `leia_mode()` par `leia()` et `all_off()` par `off()` dans les endpoints :

```python
# teeces_leia() — ligne ~70
reg.teeces.leia()          # était: reg.teeces.leia_mode()

# teeces_off() — ligne ~80
reg.teeces.off()           # était: reg.teeces.all_off()
```

**b)** Dans `teeces_text()`, remplacer le bloc `fld_text` / `rld_text` par l'appel unifié `text()` :

```python
# AVANT (lignes 90-97)
if display == 'rld':
    reg.teeces.rld_text(text)
elif display == 'both':
    reg.teeces.fld_text(text)
    reg.teeces.rld_text(text)
else:
    reg.teeces.fld_text(text)

# APRÈS
reg.teeces.text(text, display)   # 'fld' | 'rld' | 'both'
```

**c)** Remplacer les deux imports `from master.teeces_controller import TeecesController` (lignes 114 et 133) par un import de la base :

```python
# AVANT
from master.teeces_controller import TeecesController
return jsonify({'animations': [{'mode': k, 'name': v}
                for k, v in TeecesController.ANIMATIONS.items()]})

# APRÈS — ANIMATIONS est sur BaseLightsController (et donc sur reg.teeces)
from master.lights.base_controller import BaseLightsController
return jsonify({'animations': [{'mode': k, 'name': v}
                for k, v in BaseLightsController.ANIMATIONS.items()]})
```

Idem pour l'endpoint `/animation` :

```python
# AVANT
from master.teeces_controller import TeecesController
name = TeecesController.ANIMATIONS.get(mode, f'T{mode}')

# APRÈS
from master.lights.base_controller import BaseLightsController
name = BaseLightsController.ANIMATIONS.get(mode, f'T{mode}')
```

**d)** Dans `/raw`, remplacer `send_raw` par `raw` :

```python
# AVANT
reg.teeces.send_raw(cmd)
# APRÈS
reg.teeces.raw(cmd)
```

- [ ] **Step 6.2: Modifier `master/script_engine.py`**

Remplacer **l'intégralité** de `_cmd_teeces()` (lignes 371–401) par :

```python
def _cmd_teeces(self, row: list[str]) -> None:
    if not self._teeces:
        return
    action = row[1].lower()
    if action == 'random':
        self._teeces.random_mode()
    elif action == 'leia':
        self._teeces.leia()                                  # était leia_mode()
    elif action == 'off':
        self._teeces.off()                                   # était all_off()
    elif action == 'text':
        text    = row[2] if len(row) > 2 else ''
        display = row[3].lower() if len(row) > 3 else 'fld'
        self._teeces.text(text, display)                     # unifié — était 3 branches fld/rld/both
    elif action == 'psi':
        mode = int(row[2]) if len(row) > 2 else 0
        # mode=0 dans le .scr signifie "random" (héritage de psi_random())
        # → on traduit en psi(1) pour conserver la sémantique
        self._teeces.psi(1 if mode == 0 else mode)          # était: psi_random() / psi_mode(mode)
    elif action == 'anim':
        mode = int(row[2]) if len(row) > 2 else 1
        self._teeces.animation(mode)
    elif action == 'raw':
        self._teeces.raw(row[2] if len(row) > 2 else '')    # était send_raw()
```

> ⚠️ La ligne `psi(1 if mode == 0 else mode)` est critique : dans les séquences `.scr`,
> `teeces,psi` sans argument (mode=0) signifie "aléatoire" — pas "éteint".
> Un simple `psi(mode)` appellerait `psi(0)` = éteindre, ce qui est incorrect.

- [ ] **Step 6.3: Modifier `master/deploy_controller.py`**

```python
# _show_version() — déjà correct (show_version est abstract dans la base)
self._teeces.show_version(version)    # rien à changer

# rsync_to_slave() ligne ~244 — changement INTENTIONNEL de comportement :
# alert_error("SYNC") → uniquement texte FLD
# system_error("SYNC") → alarme visuelle (animation 0T3) + texte FLD+RLD
# → plus visible lors d'un échec de sync, c'est voulu
self._teeces.system_error("SYNC")    # était: self._teeces.alert_error("SYNC")
```

- [ ] **Step 6.4: Run suite de tests complète**

```bash
python -m pytest tests/ -v
```

Expected: tous les tests existants passent (pas de régression).

- [ ] **Step 6.5: Commit**

```bash
git add master/api/teeces_bp.py master/script_engine.py master/deploy_controller.py
git commit -m "Feat: lights plugin — mise à jour appelants vers nouvelle API"
```

---

## Task 7: API — Sélection du backend + hot-reload

Ajouter dans `settings_bp.py` :
- `GET /settings` → inclure `lights.backend`
- `POST /settings/lights` → écrire dans `local.cfg` + swapper `reg.teeces`

**Files:**
- Modify: `master/api/settings_bp.py`

- [ ] **Step 7.1: Ajouter les tests API (en s'appuyant sur le pattern des tests existants)**

Ajouter à `tests/test_lights_plugin.py` :

```python
# Append to tests/test_lights_plugin.py

# Stubs Flask
sys.modules.setdefault('flask', MagicMock())
flask_mock = sys.modules['flask']
flask_mock.Blueprint.return_value = MagicMock()
flask_mock.request = MagicMock()
flask_mock.jsonify = lambda x: x   # retourne le dict directement

import master.registry as _reg_mod


class TestLightsSettingsApi(unittest.TestCase):

    def test_load_driver_called_on_reload(self):
        """POST /settings/lights swaps reg.teeces avec le nouveau driver."""
        # Arrange
        old_driver = MagicMock()
        old_driver.is_ready.return_value = True
        _reg_mod.teeces = old_driver

        cfg_fresh = _teeces_cfg(backend='astropixels')

        with patch('master.api.settings_bp._write_key') as mock_write, \
             patch('master.api.settings_bp._read_fresh_cfg', return_value=cfg_fresh), \
             patch('master.lights.load_driver') as mock_factory:

            new_driver = MagicMock()
            new_driver.setup.return_value = True
            mock_factory.return_value = new_driver

            # Import et appel direct à la fonction helper (pas via HTTP)
            from master.api.settings_bp import _reload_lights_driver
            result = _reload_lights_driver('astropixels')

        # Assert
        old_driver.shutdown.assert_called_once()
        new_driver.setup.assert_called_once()
        self.assertEqual(_reg_mod.teeces, new_driver)
        self.assertTrue(result['ok'])

    def test_reload_unknown_backend_returns_error(self):
        """_reload_lights_driver avec backend inconnu ne crash pas."""
        _reg_mod.teeces = MagicMock()

        cfg_bad = _teeces_cfg()
        cfg_bad.set('lights', 'backend', 'baddriver')

        with patch('master.api.settings_bp._read_fresh_cfg', return_value=cfg_bad), \
             patch('master.lights.load_driver', side_effect=ValueError("unknown")):
            from master.api.settings_bp import _reload_lights_driver
            result = _reload_lights_driver('baddriver')

        self.assertFalse(result['ok'])
        self.assertIn('error', result)
```

- [ ] **Step 7.2: Run — expect FAIL** (fonctions absentes)

```bash
python -m pytest tests/test_lights_plugin.py::TestLightsSettingsApi -v
```

- [ ] **Step 7.3: Modifier `master/api/settings_bp.py`**

**a)** Ajouter les helpers privés après `_nm_field()` (~ligne 91) :

> ⚠️ Flask tourne en `threaded=True` — le swap de `reg.teeces` doit être atomique.
> Un `threading.Lock` protège la séquence shutdown → instantiate → setup → assign
> pour qu'aucune requête concurrent ne tombe sur un driver à moitié initialisé.

```python
# Ajouter après _nm_field() (~ligne 91)
import threading as _threading
_lights_reload_lock = _threading.Lock()


def _read_fresh_cfg() -> configparser.ConfigParser:
    """Relit main.cfg + local.cfg depuis le disque (pour hot-reload).
    Utilise les constantes de config_loader pour éviter la duplication de chemin."""
    from master.config.config_loader import MAIN_CFG, LOCAL_CFG
    cfg = configparser.ConfigParser()
    cfg.read([MAIN_CFG, LOCAL_CFG])
    return cfg


def _reload_lights_driver(backend: str) -> dict:
    """
    Éteint le driver courant, charge le nouveau, met à jour reg.teeces.
    Thread-safe : protégé par _lights_reload_lock.
    Retourne {'ok': True} ou {'ok': False, 'error': '...'}.
    """
    import master.registry as reg
    from master.lights import load_driver

    with _lights_reload_lock:
        # Shutdown propre du driver actuel
        if reg.teeces:
            try:
                reg.teeces.shutdown()
            except Exception as e:
                log.warning(f"Shutdown ancien driver lights: {e}")
            reg.teeces = None   # guard: évite tout appel pendant le swap

        # Charger le nouveau depuis config fraîche
        cfg = _read_fresh_cfg()
        try:
            new_driver = load_driver(cfg)
        except ValueError as e:
            log.error(f"Backend lights invalide: {e}")
            return {'ok': False, 'error': str(e)}

        if not new_driver.setup():
            log.error(f"Setup du nouveau driver lights échoué ({backend})")
            return {'ok': False, 'error': f"Setup {backend} échoué (port indisponible ?)"}

        reg.teeces = new_driver
        new_driver.random_mode()

    log.info(f"Driver lights rechargé: {backend}")
    return {'ok': True}
```

**b)** Dans `get_settings()`, ajouter `lights` au JSON retourné :

```python
# Dans get_settings() — ajouter dans le dict retourné
'lights': {
    'backend': cfg.get('lights', 'backend', fallback='teeces'),
    'available': ['teeces', 'astropixels'],
},
```

**c)** Ajouter dans `set_config()` la clé autorisée `lights.backend` :

```python
# Dans la liste allowed
allowed = {
    'github.branch', 'github.auto_pull_on_boot',
    'slave.host', 'deploy.button_pin',
    'lights.backend',                             # ← ajouter
}
```

**d)** Ajouter le nouvel endpoint `POST /settings/lights` :

```python
@settings_bp.post('/settings/lights')
def set_lights_backend():
    """
    Change le backend lights et hot-reload le driver.
    Body: {"backend": "astropixels"}
    """
    data    = request.get_json() or {}
    backend = data.get('backend', '').strip().lower()
    allowed = {'teeces', 'astropixels'}

    if backend not in allowed:
        return jsonify({'error': f'backend invalide. Valeurs: {", ".join(sorted(allowed))}'}), 400

    _write_key('lights', 'backend', backend)
    result = _reload_lights_driver(backend)

    if not result['ok']:
        return jsonify({'status': 'error', **result}), 500

    return jsonify({'status': 'ok', 'backend': backend,
                    'message': f'Driver lights rechargé: {backend}'})
```

- [ ] **Step 7.4: Run — expect PASS**

```bash
python -m pytest tests/test_lights_plugin.py::TestLightsSettingsApi -v
```

- [ ] **Step 7.5: Full suite**

```bash
python -m pytest tests/ -v
```

- [ ] **Step 7.6: Commit**

```bash
git add master/api/settings_bp.py tests/test_lights_plugin.py
git commit -m "Feat: lights plugin — API hot-reload POST /settings/lights"
```

---

## Task 8: UI Web — Dropdown backend + bouton Apply

Ajouter une card "LIGHTS BACKEND" dans l'onglet `tab-config` de l'index.html, et le handler JS correspondant dans `app.js`.

**Files:**
- Modify: `master/templates/index.html`
- Modify: `master/static/js/app.js`

- [ ] **Step 8.1: Ajouter la card dans `master/templates/index.html`**

Localiser la section `<div class="tab-content" id="tab-config">` (ligne ~808). Insérer une nouvelle `<section>` avant la card BT Controller (c'est la première card en pleine largeur, on place Lights juste avant) :

```html
<!-- Lights Backend — ajout avant la card BT Controller -->
<section class="card settings-card">
  <h2 class="card-title">LIGHTS BACKEND</h2>
  <div class="settings-status" id="lights-backend-status">Loading...</div>
  <div class="form-group">
    <label>Driver actif</label>
    <select id="lights-backend-select" class="input-text">
      <option value="teeces">Teeces32 (JawaLite)</option>
      <option value="astropixels">AstroPixels+ (@-protocol)</option>
    </select>
  </div>
  <div class="settings-note">
    Hot-reload — aucun redémarrage du Pi requis.
    Le port série reste /dev/ttyUSB0 (configuré dans main.cfg).
  </div>
  <button class="btn btn-warn" onclick="lightsSettings.apply()">
    APPLY &amp; RESTART LIGHTS
  </button>
</section>
```

- [ ] **Step 8.2: Ajouter `lightsSettings` dans `master/static/js/app.js`**

Localiser la section Settings dans `app.js` (chercher `applyHotspot` ou `saveConfig`). Ajouter un objet `lightsSettings` à proximité :

```javascript
// ── Lights Backend Settings ─────────────────────────────────────────
const lightsSettings = {
  _statusEl:  () => document.getElementById('lights-backend-status'),
  _selectEl:  () => document.getElementById('lights-backend-select'),

  load(backend) {
    const sel = this._selectEl();
    if (sel && backend) sel.value = backend;
    const st = this._statusEl();
    if (st) st.textContent = `Active: ${backend ?? '…'}`;
  },

  async apply() {
    const backend = this._selectEl()?.value;
    if (!backend) return;
    const st = this._statusEl();
    if (st) st.textContent = 'Reloading…';
    try {
      const r = await fetch('/settings/lights', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({backend}),
      });
      const d = await r.json();
      if (st) st.textContent = r.ok ? `✓ ${d.message}` : `✗ ${d.error}`;
    } catch (e) {
      if (st) st.textContent = `✗ Erreur réseau: ${e.message}`;
    }
  },
};
```

**Intégrer `lightsSettings.load()` dans le chargement existant des settings :**

Trouver la fonction qui peuple la tab Config (elle appelle `GET /settings`). Ajouter dans le callback :

```javascript
// Dans le bloc qui traite la réponse de GET /settings
if (data.lights) {
  lightsSettings.load(data.lights.backend);
}
```

- [ ] **Step 8.3: Vérifier manuellement**

Ouvrir le dashboard → onglet Config → vérifier que la card "LIGHTS BACKEND" apparaît avec le dropdown. Changer le backend et cliquer Apply — vérifier le message de retour dans le status label.

- [ ] **Step 8.4: Commit**

```bash
git add master/templates/index.html master/static/js/app.js
git commit -m "Feat: lights plugin — UI dropdown backend + Apply & Restart"
```

---

## Task 9: Sync Android assets

Après chaque modification de `master/templates/index.html` ou `master/static/js/app.js`, les assets Android doivent être synchronisés. **Ne pas copier `index.html` directement** — les chemins `/static/` doivent être patchés en chemins relatifs.

**Files:**
- Modify: `android/app/src/main/assets/index.html`
- Modify: `android/app/src/main/assets/js/app.js`

- [ ] **Step 9.1: Copier `app.js`** (copie directe, pas de patch nécessaire)

```bash
cp master/static/js/app.js android/app/src/main/assets/js/app.js
```

- [ ] **Step 9.2: Patcher et copier `index.html`**

La nouvelle card `LIGHTS BACKEND` ne contient pas de chemins `/static/` → pas de patch de chemin sur ce fragment. Mais le fichier index.html entier doit subir les patches habituels avant copie :

1. Remplacer `/static/css/` → `css/`
2. Remplacer `/static/js/` → `js/`
3. Désactiver le Service Worker (chercher `serviceWorker` et commenter l'enregistrement) — requis par CLAUDE.md

Vérifier avec diff après copie que la section `<section class="card settings-card">` contenant `LIGHTS BACKEND` est bien présente dans `android/app/src/main/assets/index.html`.

- [ ] **Step 9.3: Commit**

```bash
git add android/app/src/main/assets/index.html android/app/src/main/assets/js/app.js
git commit -m "ci: sync Android assets — lights backend UI"
```

---

## Task 10: Déploiement final

- [ ] **Step 10.1: Run suite complète**

```bash
python -m pytest tests/ -v
```

Expected: zéro échec.

- [ ] **Step 10.2: Push + deploy**

```bash
git push
```

Puis déployer sur le Pi :

```python
import paramiko, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.2.104', username='artoo', password='deetoo', timeout=10)
stdin, stdout, stderr = c.exec_command('cd /home/artoo/r2d2 && bash scripts/update.sh 2>&1')
for line in stdout: print(line, end='')
c.close()
```

- [ ] **Step 10.3: Vérifier dans les logs Pi**

```bash
# Sur le Master Pi
journalctl -u r2d2-master -f
```

Chercher dans les logs : `TeecesDriver ouvert` (ou `AstroPixelsDriver ouvert`) selon le backend configuré.

- [ ] **Step 10.4: Test hot-reload**

Dans le dashboard → Config → LIGHTS BACKEND → changer `astropixels` → Apply & Restart.
Vérifier dans les logs : `AstroPixelsDriver ouvert` sans reboot du Pi.

---

## Résumé des dépendances entre tâches

```
Task 1 (base_controller)
  └─ Task 2 (teeces.py)
  └─ Task 3 (astropixels.py)
       └─ Task 4 (factory __init__.py)
            └─ Task 5 (wiring main.py)
                 └─ Task 6 (update callers)
                      └─ Task 7 (settings API)
                           └─ Task 8 (UI)
                                └─ Task 9 (Android sync)
                                     └─ Task 10 (deploy)
```

Tasks 2 et 3 peuvent être faites en parallèle. Tasks 8 et 9 sont indépendantes de 7 (on peut faire l'UI avant l'API si on stubhe le fetch).
