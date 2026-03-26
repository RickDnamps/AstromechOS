# tests/test_lights_plugin.py
import sys, os, types, unittest
import configparser
from unittest.mock import MagicMock, patch

# Stub serial so it imports without hardware
sys.modules.setdefault('serial', MagicMock())

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from master.lights.teeces import TeecesDriver


def _teeces_cfg(port='/dev/ttyUSB0', baud=9600, backend='teeces') -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    cfg.add_section('teeces')
    cfg.set('teeces', 'port', port)
    cfg.set('teeces', 'baud', str(baud))
    cfg.add_section('lights')
    cfg.set('lights', 'backend', backend)
    return cfg

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
                     'slave_offline', 'uart_error',
                     'show_version', 'alert_error'):
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
        d._serial = mock_serial
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
        self.assertFalse(d.is_ready())

    def test_setup_fail_returns_false(self):
        cfg = _teeces_cfg()
        with patch('master.lights.teeces.serial.Serial', side_effect=Exception("no port")):
            d = TeecesDriver(cfg)
            result = d.setup()
        self.assertFalse(result)
        self.assertFalse(d.is_ready())

    def test_backward_compat_all_off(self):
        d, ser = self._make_driver()
        d.all_off()
        ser.write.assert_called_with(b'0T20\r')

    def test_show_version(self):
        d, ser = self._make_driver()
        d.show_version("abc1234")
        calls = b''.join(c.args[0] for c in ser.write.call_args_list)
        self.assertIn(b'VER', calls)


if __name__ == '__main__':
    unittest.main()
