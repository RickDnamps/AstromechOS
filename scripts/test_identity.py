#!/usr/bin/env python3
"""
Unit tests for shared/identity.py — the runtime identity / SSH-target
helper. Pure-Python, no Pi hardware required, runs cross-platform
(Windows dev OK — pwd is guarded inside identity.py).

Run: python scripts/test_identity.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

# Make the repo root importable
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from shared import identity as I   # noqa: E402


class TestProcessIdentity(unittest.TestCase):
    """current_user / current_uid / current_home — basic invariants."""

    def test_current_user_returns_non_empty_string(self):
        u = I.current_user()
        self.assertIsInstance(u, str)
        self.assertTrue(len(u) > 0, "current_user() must return a non-empty name")

    def test_current_uid_returns_int(self):
        self.assertIsInstance(I.current_uid(), int)
        # On POSIX uid >= 0; on Windows we return -1 (no UID concept).
        self.assertGreaterEqual(I.current_uid(), -1)

    def test_current_home_is_absolute_or_drive(self):
        h = I.current_home()
        self.assertIsInstance(h, str)
        self.assertTrue(len(h) > 0)
        # Unix absolute path OR Windows drive letter
        ok = h.startswith('/') or (len(h) >= 3 and h[1:3] == ':\\')
        self.assertTrue(ok, f"home '{h}' must be absolute")


class TestBootInitHook(unittest.TestCase):
    """The reserved /boot/astromech_init.cfg lookup must never raise."""

    def test_boot_init_returns_none_on_dev_box(self):
        # No /boot/astromech_init.cfg on a Windows / non-Pi dev machine.
        self.assertIsNone(I.boot_init_path())


class TestSlaveTarget(unittest.TestCase):
    """slave_user / slave_host / slave_ssh_target composition + waterfall."""

    def setUp(self):
        # Save original _cfg_paths so we can monkey-patch per test
        self._orig = I._cfg_paths

    def tearDown(self):
        I._cfg_paths = self._orig

    def _set_cfg(self, body: str) -> None:
        """Point _cfg_paths at a temp local.cfg containing `body`."""
        td = tempfile.mkdtemp()
        cfg = Path(td) / 'local.cfg'
        cfg.write_text(body)
        I._cfg_paths = lambda: ('/__nope__/main.cfg', str(cfg))

    def test_ssh_target_composes_user_at_host(self):
        t = I.slave_ssh_target()
        self.assertIn('@', t)
        u, _, h = t.partition('@')
        self.assertEqual(u, I.slave_user())
        self.assertEqual(h, I.slave_host())
        self.assertTrue(len(u) > 0 and len(h) > 0)

    def test_slave_user_equals_current_user(self):
        """AstromechOS rule: slave SSH user ALWAYS matches the Master's
        current process user. [deploy] slave_user + [system] user cfg
        keys are intentionally ignored (same user enforced by design)."""
        self._set_cfg(
            '[system]\nuser = totallydifferent\n\n'
            '[deploy]\nslave_user = anotheruser\n'
            'slave_host = test-slave.local\n'
        )
        self.assertEqual(I.slave_user(), I.current_user())
        self.assertNotEqual(I.slave_user(), 'totallydifferent')
        self.assertNotEqual(I.slave_user(), 'anotheruser')
        # slave_host is still cfg-driven (different concern: same user,
        # but distinct hosts on the network).
        self.assertEqual(I.slave_host(), 'test-slave.local')

    def test_slave_host_canonical_key_wins(self):
        """[slave] host beats [deploy] slave_host."""
        self._set_cfg(
            '[slave]\nhost = canonical.local\n\n'
            '[deploy]\nslave_host = legacy.local\n'
        )
        self.assertEqual(I.slave_host(), 'canonical.local')

    def test_empty_cfg_falls_through_to_current_user(self):
        """No cfg sections → current_user() is used (NOT the legacy literal)."""
        self._set_cfg('')   # empty cfg file
        # On a dev box / Pi, current_user() returns the real OS user.
        # On Windows it may return $USERNAME. Either way: NOT 'astromech'
        # unless the dev happens to be named astromech.
        if I.current_user():
            self.assertEqual(I.slave_user(), I.current_user())

    def test_empty_cfg_falls_back_to_mdns_default_host(self):
        self._set_cfg('')
        self.assertEqual(I.slave_host(), 'astromech-slave.local')

    def test_slave_password_none_when_absent(self):
        self._set_cfg('[deploy]\nslave_host = x.local\n')
        self.assertIsNone(I.slave_password())

    def test_slave_password_read_from_cfg_when_present(self):
        self._set_cfg('[deploy]\nslave_password = topsecret\n')
        self.assertEqual(I.slave_password(), 'topsecret')


class TestRepoPaths(unittest.TestCase):
    """system_repo_path / slave_repo_path default to $HOME/astromechos."""

    def setUp(self):
        self._orig = I._cfg_paths

    def tearDown(self):
        I._cfg_paths = self._orig

    def test_system_repo_path_defaults_to_home_astromechos(self):
        # Empty cfg → default
        td = tempfile.mkdtemp()
        (Path(td) / 'local.cfg').write_text('')
        I._cfg_paths = lambda: ('/__nope__/main.cfg', str(Path(td) / 'local.cfg'))
        p = I.system_repo_path()
        self.assertTrue(p.endswith('astromechos') or p.endswith('astromechos/'))

    def test_system_repo_path_reads_cfg_when_present(self):
        td = tempfile.mkdtemp()
        cfg = Path(td) / 'local.cfg'
        cfg.write_text('[system]\nrepo_path = /opt/custom/install\n')
        I._cfg_paths = lambda: ('/__nope__/main.cfg', str(cfg))
        self.assertEqual(I.system_repo_path(), '/opt/custom/install')

    def test_slave_repo_path_prefers_deploy_slave_path(self):
        td = tempfile.mkdtemp()
        cfg = Path(td) / 'local.cfg'
        cfg.write_text(
            '[system]\nrepo_path = /home/pi/astromechos\n\n'
            '[deploy]\nslave_path = /opt/slave/install\n'
        )
        I._cfg_paths = lambda: ('/__nope__/main.cfg', str(cfg))
        self.assertEqual(I.slave_repo_path(), '/opt/slave/install')


if __name__ == '__main__':
    unittest.main(verbosity=2)
