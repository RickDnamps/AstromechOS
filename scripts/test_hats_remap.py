#!/usr/bin/env python3
"""Unit tests for the G6 POST /hats/remap validation logic.

We don't spin up a full Flask app — instead we exercise the same
validation rules at the data layer by emulating the endpoint via a
simple wrapper. This catches all the rule violations without needing
the Flask test client (which would also need to mock @require_admin
+ master.registry)."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import shared.hw_mapping as M


def _master_mapping():
    return {
        'schema_version': 1, 'host': 'master', 'updated_at': None,
        'synthesised': False,
        'hats': [
            {'id': 'Dome_HAT_A', 'role': 'servo_dome', 'address': '0x40',
             'channels': 16, 'alias_prefix': 'Servo_M', 'alias_base': 0},
            {'id': 'Dome_HAT_B', 'role': 'servo_dome', 'address': '0x42',
             'channels': 16, 'alias_prefix': 'Servo_M', 'alias_base': 16},
        ],
    }


def _validate_remap(current_map, body):
    """Mirror of hats_bp.hats_remap validation logic for testing.
    Returns (status, message_or_new_mapping)."""
    host = body.get('host')
    if host not in ('master', 'slave'):
        return 400, "host must be 'master' or 'slave'"
    submitted = body.get('hats')
    if not isinstance(submitted, list) or not submitted:
        return 400, "'hats' must be a non-empty array"
    current_by_id = {h['id']: h for h in M.all_hats(current_map)}
    seen_addrs: set = set()
    new_hats = []
    for entry in submitted:
        if not isinstance(entry, dict):
            return 400, 'each hats[] entry must be an object'
        ident = entry.get('id')
        addr  = entry.get('address')
        if not isinstance(ident, str) or ident not in current_by_id:
            return 400, f'unknown HAT identity {ident!r}'
        addr_norm = M._normalise_addr(addr)
        if addr_norm is None:
            return 400, f'invalid address {addr!r}'
        if addr_norm in seen_addrs:
            return 400, f'address {addr_norm} assigned to more than one HAT'
        seen_addrs.add(addr_norm)
        prev = current_by_id[ident]
        new_hats.append({
            'id':           prev['id'],
            'role':         prev['role'],
            'address':      addr_norm,
            'channels':     prev.get('channels', 16),
            'alias_prefix': prev.get('alias_prefix'),
            'alias_base':   prev.get('alias_base'),
        })
    return 200, {'schema_version': 1, 'host': host,
                 'synthesised': False, 'hats': new_hats}


class TestRemapHappyPath(unittest.TestCase):

    def test_swap_two_addresses(self):
        m = _master_mapping()
        # Operator re-jumpered: A is now at 0x42, B is now at 0x40.
        status, result = _validate_remap(m, {
            'host': 'master',
            'hats': [
                {'id': 'Dome_HAT_A', 'address': '0x42'},
                {'id': 'Dome_HAT_B', 'address': '0x40'},
            ],
        })
        self.assertEqual(status, 200)
        addr_by_id = {h['id']: h['address'] for h in result['hats']}
        self.assertEqual(addr_by_id['Dome_HAT_A'], '0x42')
        self.assertEqual(addr_by_id['Dome_HAT_B'], '0x40')
        # Calibration metadata preserved.
        a = next(h for h in result['hats'] if h['id'] == 'Dome_HAT_A')
        self.assertEqual(a['alias_prefix'], 'Servo_M')
        self.assertEqual(a['alias_base'], 0)
        self.assertEqual(a['role'], 'servo_dome')

    def test_single_address_change(self):
        m = _master_mapping()
        status, result = _validate_remap(m, {
            'host': 'master',
            'hats': [
                {'id': 'Dome_HAT_A', 'address': '0x40'},
                {'id': 'Dome_HAT_B', 'address': '0x43'},
            ],
        })
        self.assertEqual(status, 200)


class TestRemapValidation(unittest.TestCase):

    def test_bad_host(self):
        m = _master_mapping()
        status, msg = _validate_remap(m, {'host': 'rogue', 'hats': [{'id':'X'}]})
        self.assertEqual(status, 400)
        self.assertIn("host must be", msg)

    def test_empty_hats(self):
        m = _master_mapping()
        status, msg = _validate_remap(m, {'host': 'master', 'hats': []})
        self.assertEqual(status, 400)

    def test_unknown_identity(self):
        m = _master_mapping()
        status, msg = _validate_remap(m, {
            'host': 'master',
            'hats': [{'id': 'Dome_HAT_Z', 'address': '0x40'}],
        })
        self.assertEqual(status, 400)
        self.assertIn('unknown HAT identity', msg)

    def test_invalid_address(self):
        m = _master_mapping()
        status, msg = _validate_remap(m, {
            'host': 'master',
            'hats': [{'id': 'Dome_HAT_A', 'address': '0xZZ'}],
        })
        self.assertEqual(status, 400)
        self.assertIn('invalid address', msg)

    def test_out_of_range_address(self):
        m = _master_mapping()
        status, msg = _validate_remap(m, {
            'host': 'master',
            'hats': [{'id': 'Dome_HAT_A', 'address': '0x80'}],
        })
        self.assertEqual(status, 400)

    def test_duplicate_address(self):
        m = _master_mapping()
        status, msg = _validate_remap(m, {
            'host': 'master',
            'hats': [
                {'id': 'Dome_HAT_A', 'address': '0x42'},
                {'id': 'Dome_HAT_B', 'address': '0x42'},
            ],
        })
        self.assertEqual(status, 400)
        self.assertIn('more than one HAT', msg)


class TestRemapPreservesMetadata(unittest.TestCase):

    def test_role_channels_alias_unchanged(self):
        m = _master_mapping()
        status, result = _validate_remap(m, {
            'host': 'master',
            'hats': [
                {'id': 'Dome_HAT_A', 'address': '0x47'},
                {'id': 'Dome_HAT_B', 'address': '0x46'},
            ],
        })
        self.assertEqual(status, 200)
        for new in result['hats']:
            orig = next(h for h in m['hats'] if h['id'] == new['id'])
            self.assertEqual(new['role'],         orig['role'])
            self.assertEqual(new['channels'],     orig['channels'])
            self.assertEqual(new['alias_prefix'], orig['alias_prefix'])
            self.assertEqual(new['alias_base'],   orig['alias_base'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
