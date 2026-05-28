#!/usr/bin/env python3
"""Unit tests for backup_core.validate_mapping_against_layout (Phase G4)."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from master.api.backup_core import (validate_mapping_against_layout,
                                    BACKUP_FILESET)


def _write_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f)


def _mapping(hats: list[dict]) -> dict:
    return {'schema_version': 1, 'host': 'master',
            'updated_at': '2026-05-28T00:00:00Z',
            'synthesised': False, 'hats': hats}


def _layout(addrs: list[str]) -> dict:
    return {'schema_version': 1, 'host': 'master', 'bus': 1,
            'method': 'test', 'source': 'scan', 'eeprom': {'present': False},
            'hats': [{'addr': a, 'chip': 'pca9685', 'role': 'servo_dome',
                      'collision': False} for a in addrs],
            'errors': []}


class TestBackupFilesetIncludesMapping(unittest.TestCase):
    """Sanity: config_mapping.json must be a restore target on both sides
    so the backup chain actually includes the file we're validating."""

    def test_master_includes_config_mapping(self):
        self.assertIn('master/config/config_mapping.json',
                      BACKUP_FILESET['master'])

    def test_slave_includes_config_mapping(self):
        self.assertIn('slave/config/config_mapping.json',
                      BACKUP_FILESET['slave'])


class TestValidationNoMismatch(unittest.TestCase):

    def test_addresses_match(self):
        with tempfile.TemporaryDirectory() as td:
            mp = os.path.join(td, 'mapping.json')
            lp = os.path.join(td, 'layout.json')
            _write_json(mp, _mapping([
                {'id': 'Dome_HAT_A', 'role': 'servo_dome', 'address': '0x40',
                 'channels': 16, 'alias_prefix': 'Servo_M', 'alias_base': 0},
            ]))
            _write_json(lp, _layout(['0x40']))
            self.assertEqual(validate_mapping_against_layout(mp, lp), [])

    def test_case_insensitive_match(self):
        # Mapping says '0x40', layout reports '0X40' (uppercase X).
        with tempfile.TemporaryDirectory() as td:
            mp = os.path.join(td, 'mapping.json')
            lp = os.path.join(td, 'layout.json')
            _write_json(mp, _mapping([
                {'id': 'Dome_HAT_A', 'role': 'servo_dome', 'address': '0x40',
                 'channels': 16, 'alias_prefix': 'Servo_M', 'alias_base': 0},
            ]))
            _write_json(lp, _layout(['0X40']))
            self.assertEqual(validate_mapping_against_layout(mp, lp), [])


class TestValidationMismatchCases(unittest.TestCase):

    def test_single_address_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            mp = os.path.join(td, 'mapping.json')
            lp = os.path.join(td, 'layout.json')
            _write_json(mp, _mapping([
                {'id': 'Body_HAT_A', 'role': 'servo_body', 'address': '0x41',
                 'channels': 16, 'alias_prefix': 'Servo_S', 'alias_base': 0},
            ]))
            _write_json(lp, _layout(['0x42']))   # operator re-jumpered
            warnings = validate_mapping_against_layout(mp, lp)
            self.assertEqual(len(warnings), 1)
            w = warnings[0]
            self.assertEqual(w['identity'], 'Body_HAT_A')
            self.assertEqual(w['role'], 'servo_body')
            self.assertEqual(w['expected_addr'], '0x41')
            self.assertEqual(w['detected_addrs'], ['0x42'])
            self.assertIn('Body_HAT_A', w['message'])
            self.assertIn('Settings -> HATs', w['message'])

    def test_multiple_mismatches(self):
        with tempfile.TemporaryDirectory() as td:
            mp = os.path.join(td, 'mapping.json')
            lp = os.path.join(td, 'layout.json')
            _write_json(mp, _mapping([
                {'id': 'Dome_HAT_A', 'role': 'servo_dome', 'address': '0x40',
                 'channels': 16, 'alias_prefix': 'Servo_M', 'alias_base': 0},
                {'id': 'Dome_HAT_B', 'role': 'servo_dome', 'address': '0x42',
                 'channels': 16, 'alias_prefix': 'Servo_M', 'alias_base': 16},
            ]))
            _write_json(lp, _layout(['0x44']))  # nothing matches
            warnings = validate_mapping_against_layout(mp, lp)
            self.assertEqual(len(warnings), 2)

    def test_empty_layout_all_mismatch(self):
        # Live scan came up empty (HAT physically missing).
        with tempfile.TemporaryDirectory() as td:
            mp = os.path.join(td, 'mapping.json')
            lp = os.path.join(td, 'layout.json')
            _write_json(mp, _mapping([
                {'id': 'Dome_HAT_A', 'role': 'servo_dome', 'address': '0x40',
                 'channels': 16, 'alias_prefix': 'Servo_M', 'alias_base': 0},
            ]))
            _write_json(lp, _layout([]))
            warnings = validate_mapping_against_layout(mp, lp)
            self.assertEqual(len(warnings), 1)
            self.assertEqual(warnings[0]['detected_addrs'], [])


class TestValidationGracefulFailures(unittest.TestCase):
    """Validation must NEVER raise — silent skip on absent / malformed."""

    def test_mapping_absent(self):
        with tempfile.TemporaryDirectory() as td:
            lp = os.path.join(td, 'layout.json')
            _write_json(lp, _layout(['0x40']))
            self.assertEqual(
                validate_mapping_against_layout(os.path.join(td, 'nope.json'), lp),
                [])

    def test_layout_absent(self):
        with tempfile.TemporaryDirectory() as td:
            mp = os.path.join(td, 'mapping.json')
            _write_json(mp, _mapping([
                {'id': 'Dome_HAT_A', 'role': 'servo_dome', 'address': '0x40',
                 'channels': 16, 'alias_prefix': 'Servo_M', 'alias_base': 0},
            ]))
            self.assertEqual(
                validate_mapping_against_layout(mp, os.path.join(td, 'nope.json')),
                [])

    def test_malformed_mapping(self):
        with tempfile.TemporaryDirectory() as td:
            mp = os.path.join(td, 'mapping.json')
            lp = os.path.join(td, 'layout.json')
            with open(mp, 'w') as f:
                f.write('not json')
            _write_json(lp, _layout(['0x40']))
            self.assertEqual(validate_mapping_against_layout(mp, lp), [])

    def test_malformed_layout(self):
        with tempfile.TemporaryDirectory() as td:
            mp = os.path.join(td, 'mapping.json')
            lp = os.path.join(td, 'layout.json')
            _write_json(mp, _mapping([
                {'id': 'Dome_HAT_A', 'role': 'servo_dome', 'address': '0x40',
                 'channels': 16, 'alias_prefix': 'Servo_M', 'alias_base': 0},
            ]))
            with open(lp, 'w') as f:
                f.write('garbage')
            self.assertEqual(validate_mapping_against_layout(mp, lp), [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
