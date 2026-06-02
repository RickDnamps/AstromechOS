"""Guard tests for admin UI password default migration.

Asserts that the shipped default is 'astropass' and that the
banner-allowlist still covers the transitional 'astro' and legacy
'deetoo' so operators get warned if they're still on an old default.
"""
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

class TestAdminPasswordDefaults(unittest.TestCase):

    def test_settings_bp_fallback_is_astropass(self):
        """master/api/settings_bp.py:_get_admin_password fallback = 'astropass'."""
        from master.api import settings_bp
        # Use an empty/missing cfg to force the fallback branch
        import configparser
        cfg = configparser.RawConfigParser()
        # Inject a stub _read_cfg
        original = settings_bp._read_cfg
        settings_bp._read_cfg = lambda: cfg
        try:
            self.assertEqual(settings_bp._get_admin_password(), 'astropass')
        finally:
            settings_bp._read_cfg = original

    def test_status_bp_allowlist_includes_astropass(self):
        """status_bp._DEFAULT_ADMIN_PASSWORDS must list 'astropass' as a known default."""
        from master.api import status_bp
        self.assertIn('astropass', status_bp._DEFAULT_ADMIN_PASSWORDS)

    def test_status_bp_allowlist_keeps_legacy_for_banner(self):
        """Transitional 'astro' and legacy 'deetoo' MUST stay so the banner
        warns operators still on an old default."""
        from master.api import status_bp
        self.assertIn('astro', status_bp._DEFAULT_ADMIN_PASSWORDS)
        self.assertIn('deetoo', status_bp._DEFAULT_ADMIN_PASSWORDS)

    def test_local_cfg_example_ships_astropass(self):
        """master/config/local.cfg.example must seed [admin] password = astropass."""
        example = REPO / 'master' / 'config' / 'local.cfg.example'
        text = example.read_text(encoding='utf-8')
        # Find the [admin] section, then within it the password line
        import re
        admin = re.search(r'\[admin\][^\[]*', text)
        self.assertIsNotNone(admin, "[admin] section not found in local.cfg.example")
        self.assertRegex(admin.group(0), r'password\s*=\s*astropass')


if __name__ == '__main__':
    unittest.main(verbosity=2)
