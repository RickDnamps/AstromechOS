#!/usr/bin/env python3
"""Unit tests for scripts/detect_hats.py.

No real I2C bus needed — every test injects a FakeSMBus that mimics the
smbus2 API. The fake counts and records every method call, so the suite
can spy on it and assert that NO write was ever issued by detect() — the
strict read-only contract from the chantier spec.

Runs cross-platform (Windows Git Bash dev, Pi Linux). No fcntl required;
tests bypass the I2CBusLock by calling detect() directly with the fake
bus rather than going through main().
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / 'scripts'))

import detect_hats as D  # noqa: E402


# ─────────────────────────────────────────────────────────────────────
# FakeSMBus — the test bus simulator
# ─────────────────────────────────────────────────────────────────────
class FakeSMBus:
    """Mimics smbus2.SMBus but is driven by a dict[addr][reg] = value.

    Any address not in the map raises OSError(EREMOTEIO) on read — the
    same error a real bus would raise when no device ACKs. Records every
    method call so tests can spy on the read pattern + assert that no
    write was ever attempted (defense in depth: ReadOnlySMBus wraps us
    and refuses writes, but we also catch any path that bypassed the
    wrapper by registering counters here)."""

    def __init__(self, mem: dict[int, dict[int, int]] | None = None):
        self.mem = mem or {}
        self.calls: list[tuple] = []
        self.closed = False

    # ── Reads ────────────────────────────────────────────────────────
    def read_byte_data(self, addr: int, reg: int) -> int:
        self.calls.append(('read_byte_data', addr, reg))
        device = self.mem.get(addr)
        if device is None:
            raise OSError(121, 'Remote I/O error')   # EREMOTEIO
        if reg not in device:
            # Real PCA9685 would return SOMETHING for any reg — model
            # that by returning 0 for unmapped regs of a present device.
            return 0
        return int(device[reg]) & 0xFF

    # ── Writes — should NEVER be called by detect_hats ───────────────
    # These are recorded so tests can assertEqual(count, 0). They DON'T
    # raise here; the test suite asserts separately. The ReadOnlySMBus
    # wrapper IS expected to raise AssertionError on these — that part
    # is tested independently below.
    def write_byte_data(self, addr, reg, val):
        self.calls.append(('write_byte_data', addr, reg, val))

    def write_byte(self, addr, val):
        self.calls.append(('write_byte', addr, val))

    def write_word_data(self, addr, reg, val):
        self.calls.append(('write_word_data', addr, reg, val))

    def write_block_data(self, addr, reg, vals):
        self.calls.append(('write_block_data', addr, reg, tuple(vals)))

    def write_i2c_block_data(self, addr, reg, vals):
        self.calls.append(('write_i2c_block_data', addr, reg, tuple(vals)))

    def close(self):
        self.closed = True


def _pca9685_default_regs() -> dict[int, int]:
    """Power-on defaults a fresh PCA9685 returns."""
    return {
        D.REG_MODE1:       0x11,   # SLEEP=1 + ALLCALL=1 (POR)
        D.REG_MODE2:       0x04,   # OUTDRV=1 (POR)
        D.REG_SUBADR1:     0xE2,
        D.REG_SUBADR2:     0xE4,
        D.REG_SUBADR3:     0xE8,
        D.REG_ALLCALLADR:  0xE0,
        D.REG_PRESCALE:    0x1E,   # POR
    }


def _pca9685_running_regs() -> dict[int, int]:
    """A PCA9685 that the project's own driver has initialised for 50 Hz."""
    r = _pca9685_default_regs()
    r[D.REG_MODE1]    = 0x00     # driver cleared SLEEP after RESTART
    r[D.REG_PRESCALE] = 0x79     # 121 = 50 Hz
    return r


def _non_pca_regs() -> dict[int, int]:
    """A non-PCA9685 device that ACKs reads but exposes a different
    register map (random values, no SUBADR signature)."""
    return {
        D.REG_MODE1:       0xAA,
        D.REG_MODE2:       0x55,
        D.REG_SUBADR1:     0x11,
        D.REG_SUBADR2:     0x22,
        D.REG_SUBADR3:     0x33,
        D.REG_ALLCALLADR:  0x44,
        D.REG_PRESCALE:    0xFF,
    }


# ─────────────────────────────────────────────────────────────────────
# Constants + helpers
# ─────────────────────────────────────────────────────────────────────
class TestConstants(unittest.TestCase):

    def test_pca9685_defaults_match_datasheet(self):
        self.assertEqual(D.PCA9685_DEFAULTS[D.REG_SUBADR1],    0xE2)
        self.assertEqual(D.PCA9685_DEFAULTS[D.REG_SUBADR2],    0xE4)
        self.assertEqual(D.PCA9685_DEFAULTS[D.REG_SUBADR3],    0xE8)
        self.assertEqual(D.PCA9685_DEFAULTS[D.REG_ALLCALLADR], 0xE0)

    def test_addr_range(self):
        self.assertEqual(D.DEFAULT_ADDR_START, 0x40)
        self.assertEqual(D.DEFAULT_ADDR_END,   0x47)


# ─────────────────────────────────────────────────────────────────────
# ReadOnlySMBus contract — every write must raise AssertionError
# ─────────────────────────────────────────────────────────────────────
class TestReadOnlyContract(unittest.TestCase):

    def setUp(self):
        self.inner = FakeSMBus({0x40: _pca9685_default_regs()})
        self.ro    = D.ReadOnlySMBus(self.inner)

    def test_read_passes_through(self):
        self.assertEqual(self.ro.read_byte_data(0x40, D.REG_MODE1), 0x11)

    def test_write_byte_data_raises(self):
        with self.assertRaises(AssertionError):
            self.ro.write_byte_data(0x40, 0x00, 0x00)

    def test_write_byte_raises(self):
        with self.assertRaises(AssertionError):
            self.ro.write_byte(0x40, 0x00)

    def test_write_word_data_raises(self):
        with self.assertRaises(AssertionError):
            self.ro.write_word_data(0x40, 0x00, 0x0000)

    def test_write_block_data_raises(self):
        with self.assertRaises(AssertionError):
            self.ro.write_block_data(0x40, 0x00, [0])

    def test_write_i2c_block_data_raises(self):
        with self.assertRaises(AssertionError):
            self.ro.write_i2c_block_data(0x40, 0x00, [0])

    def test_process_call_raises(self):
        with self.assertRaises(AssertionError):
            self.ro.process_call(0x40, 0x00, 0x0000)


# ─────────────────────────────────────────────────────────────────────
# Per-address fingerprint
# ─────────────────────────────────────────────────────────────────────
class TestFingerprint(unittest.TestCase):

    def test_fresh_pca9685_high_confidence(self):
        bus = D.ReadOnlySMBus(FakeSMBus({0x40: _pca9685_default_regs()}))
        fp  = D.fingerprint_pca9685(bus, 0x40)
        self.assertTrue(fp['present'])
        self.assertEqual(fp['chip'], 'pca9685')
        self.assertEqual(fp['confidence'], 'high')
        self.assertEqual(fp['score'], 4)
        self.assertEqual(fp['evidence']['subadr1'], '0xE2')
        self.assertEqual(fp['evidence']['allcall'], '0xE0')

    def test_running_pca9685_still_high_confidence(self):
        # After our driver inits the chip, MODE1+PRESCALE change but
        # SUBADR+ALLCALL stay at the POR defaults.
        bus = D.ReadOnlySMBus(FakeSMBus({0x41: _pca9685_running_regs()}))
        fp  = D.fingerprint_pca9685(bus, 0x41)
        self.assertEqual(fp['chip'], 'pca9685')
        self.assertEqual(fp['confidence'], 'high')
        self.assertEqual(fp['evidence']['prescale'], '0x79')

    def test_absent_address(self):
        bus = D.ReadOnlySMBus(FakeSMBus({}))   # nothing on the bus
        fp  = D.fingerprint_pca9685(bus, 0x40)
        self.assertFalse(fp['present'])
        self.assertEqual(fp['chip'], 'absent')

    def test_non_pca_device(self):
        bus = D.ReadOnlySMBus(FakeSMBus({0x42: _non_pca_regs()}))
        fp  = D.fingerprint_pca9685(bus, 0x42)
        self.assertTrue(fp['present'])
        self.assertEqual(fp['chip'], 'unknown')
        self.assertEqual(fp['score'], 0)

    def test_partial_pca_signature_medium_confidence(self):
        # One SUBADR was customised by the operator — 3/4 match.
        regs = _pca9685_default_regs()
        regs[D.REG_SUBADR2] = 0xAA
        bus = D.ReadOnlySMBus(FakeSMBus({0x40: regs}))
        fp  = D.fingerprint_pca9685(bus, 0x40)
        self.assertEqual(fp['chip'], 'pca9685')
        self.assertEqual(fp['confidence'], 'medium')
        self.assertEqual(fp['score'], 3)


# ─────────────────────────────────────────────────────────────────────
# Role assignment + cfg override
# ─────────────────────────────────────────────────────────────────────
class TestRoleAssignment(unittest.TestCase):

    def test_master_any_addr_is_servo_dome(self):
        r, src = D.assign_role('master', 0x40, 'pca9685', None)
        self.assertEqual(r, 'servo_dome')
        self.assertIn('master', src)

    def test_slave_0x40_is_motor_drive_by_convention(self):
        r, src = D.assign_role('slave', 0x40, 'pca9685', None)
        self.assertEqual(r, 'motor_drive')
        self.assertIn('convention', src)

    def test_slave_0x41_is_servo_body(self):
        r, src = D.assign_role('slave', 0x41, 'pca9685', None)
        self.assertEqual(r, 'servo_body')

    def test_slave_motor_cfg_override(self):
        # If operator moved the motor HAT to 0x42, that wins.
        r, src = D.assign_role('slave', 0x42, 'pca9685', slave_motor_addr=0x42)
        self.assertEqual(r, 'motor_drive')
        self.assertEqual(src, 'cfg_override')
        # And 0x40 is no longer the motor → it's a servo HAT.
        r2, _ = D.assign_role('slave', 0x40, 'pca9685', slave_motor_addr=0x42)
        self.assertEqual(r2, 'servo_body')

    def test_unknown_chip_yields_unknown_role(self):
        r, _ = D.assign_role('master', 0x40, 'absent', None)
        self.assertEqual(r, 'unknown')


# ─────────────────────────────────────────────────────────────────────
# End-to-end detect() — with the write spy
# ─────────────────────────────────────────────────────────────────────
class TestDetectEndToEnd(unittest.TestCase):

    def test_master_with_one_servo_hat(self):
        inner = FakeSMBus({0x40: _pca9685_default_regs()})
        bus   = D.ReadOnlySMBus(inner)
        result = D.detect(bus, host='master')
        self.assertEqual(result['host'], 'master')
        self.assertEqual(len(result['hats']), 1)
        h = result['hats'][0]
        self.assertEqual(h['addr'], '0x40')
        self.assertEqual(h['role'], 'servo_dome')
        self.assertEqual(h['chip'], 'pca9685')
        self.assertEqual(h['confidence'], 'high')
        # NO writes were ever attempted on the underlying bus.
        write_calls = [c for c in inner.calls if c[0].startswith('write')]
        self.assertEqual(write_calls, [],
                         f"detect() must be read-only, got {write_calls!r}")

    def test_slave_with_motor_and_servo(self):
        inner = FakeSMBus({
            0x40: _pca9685_default_regs(),     # motor HAT
            0x41: _pca9685_running_regs(),     # servo HAT (initialised)
        })
        bus    = D.ReadOnlySMBus(inner)
        result = D.detect(bus, host='slave')
        self.assertEqual(len(result['hats']), 2)
        roles = {h['addr']: h['role'] for h in result['hats']}
        self.assertEqual(roles['0x40'], 'motor_drive')
        self.assertEqual(roles['0x41'], 'servo_body')
        # Spy: still zero writes.
        self.assertEqual([c for c in inner.calls if c[0].startswith('write')], [])

    def test_empty_bus(self):
        inner  = FakeSMBus({})
        bus    = D.ReadOnlySMBus(inner)
        result = D.detect(bus, host='master')
        self.assertEqual(result['hats'], [])
        # Spy: zero writes even when nothing acks.
        self.assertEqual([c for c in inner.calls if c[0].startswith('write')], [])

    def test_atomic_json_write_roundtrip(self):
        inner = FakeSMBus({0x40: _pca9685_default_regs()})
        bus   = D.ReadOnlySMBus(inner)
        result = D.detect(bus, host='master')
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, 'hw_layout.json')
            D.write_layout(result, p)
            self.assertTrue(os.path.exists(p))
            with open(p, encoding='utf-8') as f:
                loaded = json.load(f)
            self.assertEqual(loaded['hats'][0]['addr'], '0x40')
            self.assertEqual(loaded['schema_version'], D.SCHEMA_VERSION)

    def test_full_addr_range_scanned(self):
        # Ensure every address from --start to --end is at least probed
        # — empty addresses contribute nothing to hats[] but the probe
        # SHOULD have hit them (so we know we covered the range).
        inner = FakeSMBus({})  # no devices
        bus   = D.ReadOnlySMBus(inner)
        D.detect(bus, host='master', addr_start=0x40, addr_end=0x47)
        probed = sorted({c[1] for c in inner.calls
                         if c[0] == 'read_byte_data' and c[2] == D.REG_MODE1})
        self.assertEqual(probed, list(range(0x40, 0x48)))

    def test_cfg_motor_hat_override_carries_through(self):
        # Operator moved motor HAT to 0x43 via local.cfg.
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, 'local.cfg')
            with open(cfg, 'w', encoding='utf-8') as f:
                f.write('[i2c_servo_hats]\nslave_motor_hat = 0x43\n')
            inner = FakeSMBus({
                0x41: _pca9685_default_regs(),
                0x43: _pca9685_default_regs(),
            })
            bus = D.ReadOnlySMBus(inner)
            result = D.detect(bus, host='slave', cfg_paths=[cfg])
            roles = {h['addr']: h['role'] for h in result['hats']}
            self.assertEqual(roles['0x43'], 'motor_drive')
            self.assertEqual(roles['0x41'], 'servo_body')


# ─────────────────────────────────────────────────────────────────────
# Host role resolution
# ─────────────────────────────────────────────────────────────────────
class TestHostRoleResolve(unittest.TestCase):

    def test_explicit_wins(self):
        self.assertEqual(D.resolve_host_role(explicit='master'), 'master')
        self.assertEqual(D.resolve_host_role(explicit='slave'),  'slave')

    def test_cfg_system_role(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, 'local.cfg')
            with open(cfg, 'w', encoding='utf-8') as f:
                f.write('[system]\nrole = slave\n')
            self.assertEqual(D.resolve_host_role(cfg_paths=[cfg]), 'slave')

    def test_falls_through_to_unknown(self):
        # No explicit, no cfg, and the dev machine hostname doesn't
        # contain master/slave → expect 'unknown' (or master/slave if
        # the test runner happens to be on a Pi).
        r = D.resolve_host_role(cfg_paths=['/__nope__.cfg'])
        self.assertIn(r, ('master', 'slave', 'unknown'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
