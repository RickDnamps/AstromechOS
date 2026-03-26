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
