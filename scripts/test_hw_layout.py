#!/usr/bin/env python3
"""Unit tests for shared/hw_layout.py."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import shared.hw_layout as H  # noqa: E402


def _make_layout(hats: list[dict]) -> dict:
    return {
        'schema_version': 1,
        'host':           'master',
        'bus':            1,
        'scanned_at':     '2026-05-28T00:00:00Z',
        'method':         'test',
        'source':         'scan',
        'eeprom':         {'present': False},
        'hats':           hats,
        'errors':         [],
    }


def _write_layout(role: str, layout: dict) -> Path:
    p = H._layout_path_for(role)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('w', encoding='utf-8') as f:
        json.dump(layout, f)
    return p


class TestLoadFor(unittest.TestCase):

    def test_missing_file_returns_none(self):
        original_repo = H._REPO
        try:
            H._REPO = Path(tempfile.mkdtemp())
            self.assertIsNone(H.load_for('master'))
        finally:
            H._REPO = original_repo

    def test_malformed_json_returns_none(self):
        original_repo = H._REPO
        td = tempfile.mkdtemp()
        try:
            H._REPO = Path(td)
            p = H._layout_path_for('master')
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('not json at all', encoding='utf-8')
            self.assertIsNone(H.load_for('master'))
        finally:
            H._REPO = original_repo

    def test_missing_hats_key_returns_none(self):
        original_repo = H._REPO
        td = tempfile.mkdtemp()
        try:
            H._REPO = Path(td)
            p = H._layout_path_for('master')
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('{"schema_version": 1}', encoding='utf-8')
            self.assertIsNone(H.load_for('master'))
        finally:
            H._REPO = original_repo

    def test_valid_layout_loads(self):
        original_repo = H._REPO
        td = tempfile.mkdtemp()
        try:
            H._REPO = Path(td)
            _write_layout('master', _make_layout([
                {'addr': '0x40', 'chip': 'pca9685', 'role': 'servo_dome',
                 'confidence': 'high', 'collision': False},
            ]))
            layout = H.load_for('master')
            self.assertIsNotNone(layout)
            self.assertEqual(len(layout['hats']), 1)
        finally:
            H._REPO = original_repo


class TestDetectedAddresses(unittest.TestCase):

    def test_none_layout(self):
        self.assertEqual(H.detected_addresses(None), set())

    def test_one_hat(self):
        layout = _make_layout([
            {'addr': '0x40', 'chip': 'pca9685', 'collision': False},
        ])
        self.assertEqual(H.detected_addresses(layout), {0x40})

    def test_collision_excluded(self):
        layout = _make_layout([
            {'addr': '0x40', 'chip': 'collision', 'collision': True},
            {'addr': '0x41', 'chip': 'pca9685',  'collision': False},
        ])
        # 0x40 in collision → excluded from detected set.
        self.assertEqual(H.detected_addresses(layout), {0x41})

    def test_malformed_entries_skipped(self):
        layout = _make_layout([
            {'addr': 'garbage'},
            'not a dict',
            {'addr': '0x40', 'chip': 'pca9685', 'collision': False},
            {'addr': '0xFF'},   # out of accepted range
        ])
        self.assertEqual(H.detected_addresses(layout), {0x40})


class TestCollisionAddresses(unittest.TestCase):

    def test_none_layout(self):
        self.assertEqual(H.collision_addresses(None), set())

    def test_collision_chip(self):
        layout = _make_layout([
            {'addr': '0x40', 'chip': 'collision'},
        ])
        self.assertEqual(H.collision_addresses(layout), {0x40})

    def test_collision_flag(self):
        layout = _make_layout([
            {'addr': '0x40', 'chip': 'pca9685', 'collision': True},
        ])
        self.assertEqual(H.collision_addresses(layout), {0x40})


class TestHatStatus(unittest.TestCase):

    def test_no_layout_is_degraded(self):
        self.assertEqual(H.hat_status(None, 0x40), H.STATUS_DEGRADED)

    def test_present_clean_is_ready(self):
        layout = _make_layout([
            {'addr': '0x40', 'chip': 'pca9685', 'collision': False},
        ])
        self.assertEqual(H.hat_status(layout, 0x40), H.STATUS_READY)

    def test_collision_is_critical(self):
        layout = _make_layout([
            {'addr': '0x40', 'chip': 'collision', 'collision': True},
        ])
        self.assertEqual(H.hat_status(layout, 0x40), H.STATUS_CRITICAL)

    def test_absent_is_degraded(self):
        layout = _make_layout([
            {'addr': '0x41', 'chip': 'pca9685'},
        ])
        # 0x40 not in layout → DEGRADED.
        self.assertEqual(H.hat_status(layout, 0x40), H.STATUS_DEGRADED)


class TestLogMessages(unittest.TestCase):

    def test_critical_message_actionable(self):
        m = H.critical_log_message(0x40)
        self.assertIn('CRITICAL', m)
        self.assertIn('0x40', m)
        self.assertIn('Address Conflict', m)
        self.assertIn('A0/A1/A2', m)
        self.assertIn('DEPLOY_SECURITY', m)

    def test_degraded_message_actionable(self):
        m = H.degraded_log_message(0x41)
        self.assertIn('WARNING', m)
        self.assertIn('0x41', m)
        self.assertIn('DEGRADED', m)
        self.assertIn('detect_hats', m)


if __name__ == '__main__':
    unittest.main(verbosity=2)
