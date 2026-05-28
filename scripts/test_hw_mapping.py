#!/usr/bin/env python3
"""Unit tests for shared/hw_mapping.py."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import shared.hw_mapping as M  # noqa: E402


def _master_mapping():
    return {
        'schema_version': 1, 'host': 'master', 'updated_at': None,
        'hats': [
            {'id': 'Dome_HAT_A', 'role': 'servo_dome', 'address': '0x40',
             'channels': 16, 'alias_prefix': 'Servo_M', 'alias_base': 0},
            {'id': 'Dome_HAT_B', 'role': 'servo_dome', 'address': '0x42',
             'channels': 16, 'alias_prefix': 'Servo_M', 'alias_base': 16},
        ],
    }


def _slave_mapping():
    return {
        'schema_version': 1, 'host': 'slave', 'updated_at': None,
        'hats': [
            {'id': 'Motor_HAT_A', 'role': 'motor_drive', 'address': '0x40',
             'channels': 16, 'alias_prefix': None, 'alias_base': None},
            {'id': 'Body_HAT_A',  'role': 'servo_body', 'address': '0x41',
             'channels': 16, 'alias_prefix': 'Servo_S', 'alias_base': 0},
            {'id': 'Body_HAT_B',  'role': 'servo_body', 'address': '0x42',
             'channels': 16, 'alias_prefix': 'Servo_S', 'alias_base': 16},
        ],
    }


class TestLoadFor(unittest.TestCase):
    def test_missing_file(self):
        original = M._REPO
        try:
            M._REPO = Path(tempfile.mkdtemp())
            self.assertIsNone(M.load_for('master'))
        finally:
            M._REPO = original

    def test_malformed_json(self):
        original = M._REPO; td = tempfile.mkdtemp()
        try:
            M._REPO = Path(td)
            p = M._path_for('master')
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('not json', encoding='utf-8')
            self.assertIsNone(M.load_for('master'))
        finally:
            M._REPO = original

    def test_round_trip(self):
        original = M._REPO; td = tempfile.mkdtemp()
        try:
            M._REPO = Path(td)
            p = M._path_for('master')
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open('w', encoding='utf-8') as f:
                json.dump(_master_mapping(), f)
            loaded = M.load_for('master')
            self.assertIsNotNone(loaded)
            self.assertEqual(len(loaded['hats']), 2)
        finally:
            M._REPO = original


class TestValidation(unittest.TestCase):
    def test_normalise_addr(self):
        self.assertEqual(M._normalise_addr('0x40'), '0x40')
        self.assertEqual(M._normalise_addr('0X40'), '0x40')
        self.assertEqual(M._normalise_addr(0x41), '0x41')
        self.assertIsNone(M._normalise_addr('0x80'))    # out of range
        self.assertIsNone(M._normalise_addr('40'))      # missing 0x
        self.assertIsNone(M._normalise_addr('garbage'))
        self.assertIsNone(M._normalise_addr(None))

    def test_valid_hat_accepts_motor(self):
        h = {'id': 'Motor_HAT_A', 'role': 'motor_drive', 'address': '0x40',
             'channels': 16, 'alias_prefix': None, 'alias_base': None}
        self.assertTrue(M._valid_hat(h))

    def test_valid_hat_rejects_bad_id(self):
        h = {'id': 'not-a-valid-id', 'role': 'servo_dome', 'address': '0x40',
             'channels': 16, 'alias_prefix': 'Servo_M', 'alias_base': 0}
        self.assertFalse(M._valid_hat(h))

    def test_valid_hat_rejects_bad_role(self):
        h = {'id': 'Dome_HAT_A', 'role': 'rogue', 'address': '0x40',
             'channels': 16, 'alias_prefix': 'Servo_M', 'alias_base': 0}
        self.assertFalse(M._valid_hat(h))

    def test_malformed_entries_dropped(self):
        m = {'schema_version': 1, 'host': 'master',
             'hats': [
                 {'garbage': 'value'},
                 'not even a dict',
                 _master_mapping()['hats'][0],
             ]}
        self.assertEqual(len(M.all_hats(m)), 1)


class TestLookups(unittest.TestCase):
    def test_hat_by_id(self):
        m = _master_mapping()
        self.assertEqual(M.hat_by_id(m, 'Dome_HAT_A')['address'], '0x40')
        self.assertEqual(M.hat_by_id(m, 'Dome_HAT_B')['address'], '0x42')
        self.assertIsNone(M.hat_by_id(m, 'Dome_HAT_Z'))
        self.assertIsNone(M.hat_by_id(None, 'Dome_HAT_A'))

    def test_hat_by_address(self):
        m = _slave_mapping()
        self.assertEqual(M.hat_by_address(m, '0x40')['id'], 'Motor_HAT_A')
        self.assertEqual(M.hat_by_address(m, '0x41')['id'], 'Body_HAT_A')
        self.assertEqual(M.hat_by_address(m, '0X41')['id'], 'Body_HAT_A')
        self.assertEqual(M.hat_by_address(m, 0x41)['id'],  'Body_HAT_A')
        self.assertIsNone(M.hat_by_address(m, '0x99'))

    def test_channels_for(self):
        m = _master_mapping()
        self.assertEqual(M.channels_for(m, 'Dome_HAT_A'), 16)
        self.assertEqual(M.channels_for(m, 'Dome_HAT_Z'), 0)


class TestFlatNames(unittest.TestCase):
    def test_flat_name_master(self):
        m = _master_mapping()
        self.assertEqual(M.flat_name(m, 'Dome_HAT_A', 0),  'Servo_M0')
        self.assertEqual(M.flat_name(m, 'Dome_HAT_A', 15), 'Servo_M15')
        self.assertEqual(M.flat_name(m, 'Dome_HAT_B', 0),  'Servo_M16')
        self.assertEqual(M.flat_name(m, 'Dome_HAT_B', 15), 'Servo_M31')

    def test_flat_name_slave(self):
        m = _slave_mapping()
        self.assertEqual(M.flat_name(m, 'Body_HAT_A', 0),  'Servo_S0')
        self.assertEqual(M.flat_name(m, 'Body_HAT_B', 0),  'Servo_S16')

    def test_flat_name_motor_has_no_alias(self):
        m = _slave_mapping()
        self.assertIsNone(M.flat_name(m, 'Motor_HAT_A', 0))

    def test_flat_name_out_of_range(self):
        m = _master_mapping()
        self.assertIsNone(M.flat_name(m, 'Dome_HAT_A', 16))
        self.assertIsNone(M.flat_name(m, 'Dome_HAT_A', -1))


class TestIdentityFor(unittest.TestCase):
    def test_identity_for_master(self):
        m = _master_mapping()
        self.assertEqual(M.identity_for(m, 'Servo_M0'),  ('Dome_HAT_A', 0))
        self.assertEqual(M.identity_for(m, 'Servo_M15'), ('Dome_HAT_A', 15))
        self.assertEqual(M.identity_for(m, 'Servo_M16'), ('Dome_HAT_B', 0))
        self.assertEqual(M.identity_for(m, 'Servo_M31'), ('Dome_HAT_B', 15))

    def test_identity_for_slave(self):
        m = _slave_mapping()
        self.assertEqual(M.identity_for(m, 'Servo_S0'),  ('Body_HAT_A', 0))
        self.assertEqual(M.identity_for(m, 'Servo_S16'), ('Body_HAT_B', 0))

    def test_identity_for_garbage(self):
        m = _master_mapping()
        self.assertIsNone(M.identity_for(m, 'NotAServo'))
        self.assertIsNone(M.identity_for(m, 'Servo_X0'))
        self.assertIsNone(M.identity_for(m, 'Servo_M99'))   # out of range
        self.assertIsNone(M.identity_for(m, None))


class TestSynthesizeFromLayout(unittest.TestCase):
    def _write_cfg(self, td: str, role: str, kv: dict) -> str:
        p = os.path.join(td, f'{role}.cfg')
        with open(p, 'w', encoding='utf-8') as f:
            f.write('[i2c_servo_hats]\n')
            for k, v in kv.items():
                f.write(f'{k} = {v}\n')
        return p

    def test_master_single_hat(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = self._write_cfg(td, 'master', {'master_hats': '0x40'})
            m = M.synthesize_from_layout('master', cfg_paths=[cfg])
        self.assertEqual(len(m['hats']), 1)
        self.assertEqual(m['hats'][0]['id'], 'Dome_HAT_A')
        self.assertEqual(m['hats'][0]['address'], '0x40')
        self.assertEqual(m['hats'][0]['alias_base'], 0)
        self.assertTrue(m['synthesised'])

    def test_master_two_hats(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = self._write_cfg(td, 'master',
                                  {'master_hats': '0x40, 0x42'})
            m = M.synthesize_from_layout('master', cfg_paths=[cfg])
        ids = [h['id'] for h in m['hats']]
        self.assertEqual(ids, ['Dome_HAT_A', 'Dome_HAT_B'])
        self.assertEqual(m['hats'][1]['alias_base'], 16)

    def test_slave_motor_plus_body(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = self._write_cfg(td, 'slave',
                                  {'slave_motor_hat': '0x40',
                                   'slave_hats':      '0x41'})
            m = M.synthesize_from_layout('slave', cfg_paths=[cfg])
        # Motor first (alias_base=None sorts last), then Body_HAT_A.
        # all_hats() sorts by alias_base; motor (None → sentinel) goes last.
        hats = M.all_hats(m)
        ids  = [h['id'] for h in hats]
        self.assertIn('Motor_HAT_A', ids)
        self.assertIn('Body_HAT_A',  ids)
        self.assertEqual(M.hat_by_id(m, 'Body_HAT_A')['address'], '0x41')
        self.assertEqual(M.hat_by_id(m, 'Motor_HAT_A')['address'], '0x40')

    def test_synthesised_round_trips_lookup(self):
        # End-to-end: synthesise then resolve Servo_S0 → (Body_HAT_A, 0).
        with tempfile.TemporaryDirectory() as td:
            cfg = self._write_cfg(td, 'slave',
                                  {'slave_motor_hat': '0x40',
                                   'slave_hats':      '0x41'})
            m = M.synthesize_from_layout('slave', cfg_paths=[cfg])
        self.assertEqual(M.identity_for(m, 'Servo_S0'),  ('Body_HAT_A', 0))
        self.assertEqual(M.flat_name(m, 'Body_HAT_A', 0), 'Servo_S0')


if __name__ == '__main__':
    unittest.main(verbosity=2)
