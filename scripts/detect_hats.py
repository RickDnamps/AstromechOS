#!/usr/bin/env python3
"""scripts/detect_hats.py — read-only I2C HAT discovery + role assignment.

Scans the I2C bus (addresses 0x40-0x47 by default), fingerprints each
responding device against the PCA9685 register signature, and assigns
a ROLE (servo_dome / servo_body / motor_drive / unknown) using the
AstromechOS convention documented in ELECTRONICS.md:
  - Master Pi : every PCA9685 = servo HAT (dome).
  - Slave Pi  : 0x40 = motor drive HAT (Waveshare Motor Driver),
                0x41+ = servo HAT (body).
The current cfg [i2c_servo_hats] slave_motor_hat overrides the
convention (operator-set wins).

Output: an atomic JSON write to <repo>/master/config/hw_layout.json
(or the path passed via --output). Consumed by firstboot_setup.sh
(commit 2 of this chantier) and by the deploy / cfg sync logic.

Strict safety contract:
  * Pure-Python smbus2 only — NO shell out to i2cdetect / i2c-tools.
  * READ-ONLY on the bus: the SMBus wrapper class refuses every
    write_* call with an AssertionError. The test suite spies on
    that contract.
  * File lock at /run/astromech-i2c.lock (fcntl flock, non-blocking
    by default) — coordinates with the diagnostics_bp i2c_scan
    in-process lock so a parallel /diagnostics/i2c_scan request or
    a live PCA9685 PWM write does not race us.
  * Every I2C call wrapped in try/except: a missing /dev/i2c-1, a
    NACK from an empty address, or a driver hold of the bus all
    surface as ok=False entries — never as exceptions that crash
    firstboot.
  * Cross-platform import-safe: smbus2 and fcntl are POSIX-only
    and guarded so the module imports cleanly on Windows dev for
    the test suite (which uses a mock bus).

CLI:
    python3 scripts/detect_hats.py
        --output <path>     defaults to <repo>/master/config/hw_layout.json
        --role master|slave|auto    auto = derive from local.cfg [system] role
                                    or /etc/hostname (astromech-master/-slave)
        --bus N             defaults to 1 (Pi 4B I2C bus)
        --start 0x40 --end 0x47    address range (inclusive)
        --dry-run           print JSON to stdout, do not write the file

The module is also importable: `from detect_hats import detect`.
"""
from __future__ import annotations

import argparse
import configparser
import errno
import json
import logging
import os
import socket
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ─── POSIX-only stdlib modules — guarded for Windows dev tests ───────
try:
    import fcntl as _fcntl
except ImportError:
    _fcntl = None  # type: ignore[assignment]

# smbus2 is NEVER imported at module top — only inside detect() when a
# real bus is needed. Tests inject a FakeSMBus that has the same
# read_byte_data signature; the module never names smbus2 directly
# elsewhere. Keeps imports clean on Windows.

log = logging.getLogger('detect_hats')


# ─────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────
# PCA9685 register addresses (datasheet NXP PCA9685, §7.3.1).
REG_MODE1       = 0x00
REG_MODE2       = 0x01
REG_SUBADR1     = 0x02
REG_SUBADR2     = 0x03
REG_SUBADR3     = 0x04
REG_ALLCALLADR  = 0x05
REG_PRESCALE    = 0xFE

# PCA9685 power-on / reset defaults. The SUBADR + ALLCALL set is the
# strongest fingerprint because:
#   - they are writable but no sane firmware customises them
#   - our own dome/body servo drivers never write them (verified by
#     inspection of master/drivers/dome_servo_driver.py + slave/
#     drivers/body_servo_driver.py — they only touch MODE1+PRESCALE)
#   - they form a unique 4-byte signature 0xE2/0xE4/0xE8/0xE0 that no
#     other common I2C chip in the AstromechOS hardware list has.
PCA9685_DEFAULTS = {
    REG_SUBADR1:    0xE2,
    REG_SUBADR2:    0xE4,
    REG_SUBADR3:    0xE8,
    REG_ALLCALLADR: 0xE0,
}
# MODE2 power-on = 0x04 (OUTDRV=1 totem-pole, INVRT=0, OCH=0). Survives
# our driver init too — used as a weaker (secondary) signal.
PCA9685_MODE2_DEFAULT = 0x04
# MODE1 may be 0x00 (running) or 0x10 (SLEEP) or 0x11 (power-on AI=0
# SLEEP=1 ALLCALL=1). Don't use as a strong signal — too variable.

# Scan range. Matches master/api/settings_bp.py::_PCA9685_MIN / MAX.
DEFAULT_ADDR_START = 0x40
DEFAULT_ADDR_END   = 0x47   # inclusive; project never uses 0x48+

# Number of consecutive reads used for collision detection. A single
# PCA9685 returns the same byte on every read (stateless registers; no
# internal mutation on read). Two devices fighting at the same address
# cause bus arbitration to elect different responders per sample → divergent
# values. 5 strikes a balance between sensitivity and scan duration
# (~5 × 4 × ~1ms ≈ 20ms extra per ACK'd address).
COLLISION_PROBE_READS = 5
COLLISION_PROBE_REGS  = (REG_MODE1, REG_SUBADR1, REG_SUBADR2, REG_ALLCALLADR)

# Default I2C bus on Raspberry Pi 4B / 5.
DEFAULT_BUS = 1

# File lock path — coordinates with master/api/diagnostics_bp.py
# (in-process _i2c_scan_lock) so a parallel /diagnostics/i2c_scan or
# a live driver write does not race us.
I2C_LOCK_PATH = '/run/astromech-i2c.lock'

# Schema version of the emitted JSON. Bump when keys are added/renamed.
SCHEMA_VERSION = 1


# ─────────────────────────────────────────────────────────────────────
# Read-only SMBus wrapper — defense in depth
# ─────────────────────────────────────────────────────────────────────
class ReadOnlySMBus:
    """Tiny adapter around an SMBus object that refuses every write.

    The detection script could be written with `bus.read_byte_data(...)`
    directly and "just not call writes", but a defense-in-depth wrapper
    means an accidental future edit can't slip a write in: the wrapper
    raises AssertionError on any write_* / process_call attempt.

    Tests inject a FakeSMBus into the constructor — same shape, same
    contract; the test's spy verifies no write was ever even attempted.
    """

    def __init__(self, inner: Any):
        # `inner` is either a real smbus2.SMBus(bus_num) or a test fake.
        # We do NOT type-check it (duck typing): all that's required is
        # a `read_byte_data(addr, reg)` method.
        self._inner = inner

    def read_byte_data(self, addr: int, reg: int) -> int:
        return self._inner.read_byte_data(addr, reg)

    # Explicitly poison every write API so a stray call fails loudly.
    def write_byte_data(self, *a, **kw):
        raise AssertionError(
            f"detect_hats.ReadOnlySMBus refuses write_byte_data{a} — "
            "the detection script is strictly read-only on the I2C bus."
        )

    def write_byte(self, *a, **kw):
        raise AssertionError("ReadOnlySMBus refuses write_byte")

    def write_word_data(self, *a, **kw):
        raise AssertionError("ReadOnlySMBus refuses write_word_data")

    def write_block_data(self, *a, **kw):
        raise AssertionError("ReadOnlySMBus refuses write_block_data")

    def write_i2c_block_data(self, *a, **kw):
        raise AssertionError("ReadOnlySMBus refuses write_i2c_block_data")

    def process_call(self, *a, **kw):
        raise AssertionError("ReadOnlySMBus refuses process_call")

    def block_process_call(self, *a, **kw):
        raise AssertionError("ReadOnlySMBus refuses block_process_call")

    def close(self) -> None:
        try:
            self._inner.close()
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────
# I2C bus lock (fcntl flock — Linux only; no-op on Windows / dev)
# ─────────────────────────────────────────────────────────────────────
class I2CBusLock:
    """Non-blocking fcntl flock on I2C_LOCK_PATH.

    Coordinates with any future shared lock the master.service may
    publish. Today, master.api.diagnostics_bp owns an in-process
    threading.Lock named _i2c_scan_lock; we add a file-level lock so
    that an out-of-process detect_hats invocation also serialises.

    On Windows (no fcntl) the lock degrades to a no-op so the dev test
    suite runs without privilege errors. In that mode it's the caller's
    responsibility to not run detect() against a real bus.
    """

    def __init__(self, path: str = I2C_LOCK_PATH, blocking: bool = False,
                 timeout: float = 10.0):
        self.path = path
        self.blocking = blocking
        self.timeout = timeout
        self._fd: Optional[int] = None

    def __enter__(self):
        if _fcntl is None:
            log.debug("fcntl unavailable — I2C lock is a no-op (Windows dev?)")
            return self
        try:
            # 0o644: readable by all, writable by owner — coordinates
            # well even if a future caller runs as a non-root service user.
            self._fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o644)
        except OSError as e:
            log.warning("Cannot open %s: %s — proceeding without file lock",
                        self.path, e)
            return self
        if self.blocking:
            t0 = time.monotonic()
            while True:
                try:
                    _fcntl.flock(self._fd, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() - t0 > self.timeout:
                        os.close(self._fd); self._fd = None
                        raise TimeoutError(
                            f'I2C lock {self.path} held > {self.timeout}s'
                        )
                    time.sleep(0.1)
        else:
            try:
                _fcntl.flock(self._fd, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
            except BlockingIOError:
                os.close(self._fd); self._fd = None
                raise BlockingIOError(
                    f'I2C bus is busy — another process holds {self.path}. '
                    'Retry once the other I2C consumer is done.'
                )
        return self

    def __exit__(self, *exc):
        if self._fd is not None and _fcntl is not None:
            try:
                _fcntl.flock(self._fd, _fcntl.LOCK_UN)
            except Exception:
                pass
            try:
                os.close(self._fd)
            except Exception:
                pass
            self._fd = None


# ─────────────────────────────────────────────────────────────────────
# Per-address fingerprint
# ─────────────────────────────────────────────────────────────────────
def _safe_read(bus: ReadOnlySMBus, addr: int, reg: int) -> Optional[int]:
    """One read_byte_data call wrapped to return None on any I/O error.

    A NACK from an empty I2C address materialises as OSError errno EIO
    or EREMOTEIO depending on the kernel/driver — both must be treated
    as "no device", never propagated."""
    try:
        return int(bus.read_byte_data(addr, reg)) & 0xFF
    except (OSError, IOError, TimeoutError) as e:
        log.debug("read 0x%02X reg 0x%02X failed: %s", addr, reg, e)
        return None
    except AssertionError:
        # ReadOnlySMBus write-guard fired — propagate (it's a programming bug).
        raise
    except Exception as e:
        log.warning("Unexpected error reading 0x%02X reg 0x%02X: %s",
                    addr, reg, e)
        return None


def probe_present(bus: ReadOnlySMBus, addr: int) -> bool:
    """Return True if SOMETHING ACKs at <addr>. The cheapest possible
    presence probe — one MODE1 read. Same pattern as the existing
    slave.uart_health_server._probe_motor_hat helper."""
    return _safe_read(bus, addr, REG_MODE1) is not None


def detect_collision(bus: ReadOnlySMBus, addr: int,
                     n_reads: int = COLLISION_PROBE_READS,
                     ) -> tuple[bool, dict[str, Any]]:
    """Best-effort I2C address collision detection.

    Read each of COLLISION_PROBE_REGS `n_reads` times. A healthy single
    PCA9685 returns the same byte on every read (registers are stateless;
    no state mutates from a read). Two devices fighting at the same
    address cause bus arbitration to randomly elect different responders
    per sample, producing divergent register values across reads.

    Returns (collision_detected, evidence) where evidence is a dict of
    {register_name: [val1, val2, ...]} for every register that showed
    divergence — empty when no collision was detected. The evidence dict
    is recorded in the JSON output so the operator can see WHY the
    detection fired (and pass it back to a maintainer for diagnosis).

    Limitations — false negatives possible when:
      - Both devices have IDENTICAL internal state (both fresh POR, both
        untouched by any driver init). Reads merge cleanly to the same
        byte, indistinguishable from a single device.
      - Bus arbitration consistently elects the same responder (one HAT
        has stronger pull-ups). Divergence requires occasional swaps.
    Such edge cases fall through to DEGRADED-style handling — driver
    will boot and may glitch, prompting the operator to investigate.
    """
    evidence: dict[str, Any] = {}
    detected = False
    reg_to_name = {
        REG_MODE1:      'mode1',
        REG_SUBADR1:    'subadr1',
        REG_SUBADR2:    'subadr2',
        REG_ALLCALLADR: 'allcall',
    }
    for reg in COLLISION_PROBE_REGS:
        samples: list[int] = []
        for _ in range(n_reads):
            v = _safe_read(bus, addr, reg)
            if v is None:
                # Device dropped mid-scan — that's an unstable device, not
                # a collision. Bail with no collision signal; the caller's
                # fingerprint will record absent/low-confidence anyway.
                return False, {'aborted_at': reg_to_name[reg]}
            samples.append(v)
        unique = set(samples)
        if len(unique) > 1:
            detected = True
            evidence[reg_to_name[reg]] = [f'0x{v:02X}' for v in samples]
    return detected, evidence


def fingerprint_pca9685(bus: ReadOnlySMBus, addr: int) -> dict[str, Any]:
    """Read the PCA9685 register signature at <addr> and score the
    match against the chip's power-on defaults.

    Returns:
        {
          'present':    bool,
          'chip':       'pca9685' | 'unknown' | 'absent',
          'confidence': 'high' | 'medium' | 'low' | 'none',
          'evidence':   { 'mode1': '0x11', ... } (hex strings, only
                                                  keys that read OK),
          'score':      int (0..4, how many SUBADR+ALLCALL defaults
                              matched),
        }
    """
    out: dict[str, Any] = {
        'present':    False,
        'chip':       'absent',
        'confidence': 'none',
        'evidence':   {},
        'score':      0,
        'collision':  False,
    }

    mode1 = _safe_read(bus, addr, REG_MODE1)
    if mode1 is None:
        return out
    out['present'] = True
    out['evidence']['mode1'] = f'0x{mode1:02X}'

    # Collision check BEFORE the rest of the fingerprint — a contested
    # bus invalidates EVERY register value (we can't trust SUBADR / MODE2
    # / PRESCALE when two devices fight per-read), so we return early
    # with chip='collision' to signal "do not use this HAT, drivers must
    # refuse to initialise". This is intentionally distinct from
    # chip='absent' (DEGRADED mode, driver continues without this HAT)
    # vs chip='collision' (CRITICAL mode, driver refuses to start).
    collision, collision_evidence = detect_collision(bus, addr)
    if collision:
        out['chip']       = 'collision'
        out['confidence'] = 'none'
        out['collision']  = True
        out['evidence']['collision_samples'] = collision_evidence
        return out

    mode2 = _safe_read(bus, addr, REG_MODE2)
    if mode2 is not None:
        out['evidence']['mode2'] = f'0x{mode2:02X}'

    score = 0
    for reg in (REG_SUBADR1, REG_SUBADR2, REG_SUBADR3, REG_ALLCALLADR):
        val = _safe_read(bus, addr, reg)
        if val is None:
            continue
        key = {
            REG_SUBADR1: 'subadr1',
            REG_SUBADR2: 'subadr2',
            REG_SUBADR3: 'subadr3',
            REG_ALLCALLADR: 'allcall',
        }[reg]
        out['evidence'][key] = f'0x{val:02X}'
        if val == PCA9685_DEFAULTS[reg]:
            score += 1
    out['score'] = score

    prescale = _safe_read(bus, addr, REG_PRESCALE)
    if prescale is not None:
        out['evidence']['prescale'] = f'0x{prescale:02X}'

    # Scoring rules. Tuned so a default-or-running PCA9685 (which our
    # drivers leave untouched on SUBADR+ALLCALL) always reads 4/4.
    if score == 4:
        out['chip'] = 'pca9685'
        out['confidence'] = 'high'
    elif score == 3:
        out['chip'] = 'pca9685'
        out['confidence'] = 'medium'
    elif score >= 1 or (mode2 is not None and mode2 == PCA9685_MODE2_DEFAULT):
        # Secondary signal: at least one SUBADR matched OR MODE2 = the
        # POR default. Could still be a PCA9685 with customised SUBADR.
        out['chip'] = 'pca9685'
        out['confidence'] = 'low'
    else:
        out['chip'] = 'unknown'
        out['confidence'] = 'low'
    return out


# ─────────────────────────────────────────────────────────────────────
# Pi HAT EEPROM probe (best effort — most clones don't ship it)
# ─────────────────────────────────────────────────────────────────────
def read_hat_eeprom() -> dict[str, Any]:
    """Look for the Raspberry Pi HAT spec EEPROM at /sys/bus/i2c/devices/
    0-0050/eeprom OR the parsed device-tree node /proc/device-tree/hat/.

    Almost certainly absent on Waveshare clones (verified empirically:
    /proc/device-tree/hat/ does not exist on the live R2-D2 Master Pi).
    This is a best-effort layer — when present, it's the most authoritative
    source; when absent, we fall through to PCA9685 fingerprinting +
    role convention.
    """
    out: dict[str, Any] = {'present': False, 'vendor': None,
                           'product': None, 'source': None}
    dt = Path('/proc/device-tree/hat')
    if dt.is_dir():
        out['present'] = True
        out['source'] = 'device-tree'
        for k, fname in (('vendor', 'vendor'), ('product', 'product')):
            f = dt / fname
            try:
                if f.is_file():
                    out[k] = f.read_text(errors='replace').rstrip('\x00').strip()
            except Exception as e:
                log.debug("HAT EEPROM read %s failed: %s", f, e)
        return out
    eeprom = Path('/sys/bus/i2c/devices/0-0050/eeprom')
    if eeprom.is_file():
        out['present'] = True
        out['source'] = 'sysfs-eeprom'
        try:
            raw = eeprom.read_bytes()
            # The HAT spec EEPROM is a structured format we don't fully
            # parse here. Just record the size and a hex preview.
            out['raw_size'] = len(raw)
            out['raw_head_hex'] = raw[:32].hex()
        except Exception as e:
            log.debug("HAT EEPROM bytes read failed: %s", e)
    return out


# ─────────────────────────────────────────────────────────────────────
# Role assignment heuristic
# ─────────────────────────────────────────────────────────────────────
def resolve_host_role(explicit: Optional[str] = None,
                      cfg_paths: Optional[list[str]] = None) -> str:
    """Return 'master' | 'slave' | 'unknown'.

    Priority:
      1. Explicit caller value (e.g. CLI --role master).
      2. local.cfg [system] role (written by firstboot or setup_*).
      3. /etc/hostname starts-with-match: 'astromech-master' / '-slave'.
      4. socket.gethostname() same matching.
      5. 'unknown' (caller's choice what to do with that).
    """
    if explicit in ('master', 'slave'):
        return explicit
    if cfg_paths:
        try:
            c = configparser.ConfigParser()
            c.read(cfg_paths)
            r = c.get('system', 'role', fallback='').strip().lower()
            if r in ('master', 'slave'):
                return r
        except Exception as e:
            log.debug("cfg [system] role lookup failed: %s", e)
    for src in ('/etc/hostname', None):
        try:
            if src:
                hn = Path(src).read_text().strip().lower()
            else:
                hn = socket.gethostname().lower()
            if 'master' in hn:
                return 'master'
            if 'slave' in hn:
                return 'slave'
        except Exception:
            continue
    return 'unknown'


def _read_cfg_motor_hat_addr(cfg_paths: list[str]) -> Optional[int]:
    """Read the operator-set slave_motor_hat addr from cfg, if any.
    Returns int (0x40..) or None on absent/invalid."""
    try:
        c = configparser.ConfigParser()
        c.read(cfg_paths)
        raw = c.get('i2c_servo_hats', 'slave_motor_hat', fallback='').strip()
        if not raw:
            return None
        if raw.startswith('0x') or raw.startswith('0X'):
            return int(raw, 16)
        return int(raw)
    except Exception:
        return None


def assign_role(host: str, addr: int, chip: str,
                slave_motor_addr: Optional[int]) -> tuple[str, str]:
    """Map (host, addr, fingerprinted chip) → (role, source-string).

    ELECTRONICS.md convention:
      Master Pi  : every PCA9685 = servo_dome.
      Slave Pi   : addr == slave_motor_hat → motor_drive
                   addr != slave_motor_hat → servo_body
                   (default slave_motor_hat = 0x40, slave_hats start 0x41)
    Operator override: any explicit slave_motor_hat value in
    [i2c_servo_hats] wins over the 0x40 convention default.

    Returns (role, source) where source is a short tag like
    'convention' or 'cfg_override' for the JSON evidence trail.
    """
    if chip not in ('pca9685', 'unknown'):
        return ('unknown', 'no-chip')

    if host == 'master':
        return ('servo_dome', 'master-convention')

    if host == 'slave':
        motor = slave_motor_addr if slave_motor_addr is not None else 0x40
        if addr == motor:
            return ('motor_drive',
                    'cfg_override' if slave_motor_addr is not None
                                   else 'slave-convention')
        return ('servo_body', 'slave-convention')

    return ('unknown', 'host-unknown')


# ─────────────────────────────────────────────────────────────────────
# Top-level detect()
# ─────────────────────────────────────────────────────────────────────
def detect(bus: ReadOnlySMBus, *,
           host: str,
           bus_num: int = DEFAULT_BUS,
           addr_start: int = DEFAULT_ADDR_START,
           addr_end:   int = DEFAULT_ADDR_END,
           cfg_paths:  Optional[list[str]] = None,
           ) -> dict[str, Any]:
    """Run the full discovery + fingerprint + role mapping on the
    supplied <bus> (ReadOnlySMBus around either a real SMBus or a
    test fake). Returns the JSON-serialisable result dict; does NOT
    write to disk (the caller / CLI does)."""
    motor_override = _read_cfg_motor_hat_addr(cfg_paths or [])

    out: dict[str, Any] = {
        'schema_version': SCHEMA_VERSION,
        'host':           host,
        'bus':            bus_num,
        'scanned_at':     datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'method':         'smbus_probe+pca9685_fingerprint+role_heuristic',
        'source':         'scan',
        'eeprom':         read_hat_eeprom(),
        'hats':           [],
        'errors':         [],
    }

    for addr in range(addr_start, addr_end + 1):
        try:
            fp = fingerprint_pca9685(bus, addr)
        except AssertionError:
            raise  # write-guard tripped — let it surface in tests
        except Exception as e:
            out['errors'].append({'addr': f'0x{addr:02X}', 'error': str(e)})
            continue
        if not fp['present']:
            continue
        # ADDRESS_COLLISION: distinct from absent. Surface in BOTH the
        # per-hat entry (chip='collision') AND the top-level errors list
        # so an operator scanning the JSON sees the alarm at a glance.
        if fp.get('collision'):
            out['errors'].append({
                'addr':   f'0x{addr:02X}',
                'error':  'ADDRESS_COLLISION',
                'detail': 'Two or more devices respond at this address. '
                          'Check hardware jumpers (A0/A1/A2 on PCA9685 boards). '
                          'Drivers will refuse to initialise this HAT.',
                'evidence': fp['evidence'].get('collision_samples', {}),
            })
            out['hats'].append({
                'addr':       f'0x{addr:02X}',
                'chip':       'collision',
                'role':       'unknown',
                'evidence':   fp['evidence'],
                'confidence': 'none',
                'score':      0,
                'collision':  True,
                'source':     'collision-check',
            })
            continue
        role, role_src = assign_role(host, addr, fp['chip'], motor_override)
        out['hats'].append({
            'addr':       f'0x{addr:02X}',
            'chip':       fp['chip'],
            'role':       role,
            'evidence':   fp['evidence'],
            'confidence': fp['confidence'],
            'score':      fp['score'],
            'collision':  False,
            'source':     f'fingerprint+{role_src}',
        })
    return out


# ─────────────────────────────────────────────────────────────────────
# Atomic JSON write
# ─────────────────────────────────────────────────────────────────────
def write_layout(layout: dict[str, Any], path: str) -> None:
    """tmp file + os.replace, chmod 0o644 (no secrets in this JSON)."""
    p = Path(path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix='.hwlayout.')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(layout, f, indent=2, sort_keys=False)
            f.write('\n')
        os.replace(tmp, str(p))
        try:
            os.chmod(str(p), 0o644)
        except Exception:
            pass
    except Exception:
        try:
            os.unlink(tmp)
        except Exception:
            pass
        raise


# ─────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────
def _default_output_path() -> str:
    repo = Path(__file__).resolve().parent.parent
    return str(repo / 'master' / 'config' / 'hw_layout.json')


def _default_cfg_paths() -> list[str]:
    repo = Path(__file__).resolve().parent.parent
    return [str(repo / 'master' / 'config' / 'main.cfg'),
            str(repo / 'master' / 'config' / 'local.cfg')]


def _open_real_bus(bus_num: int):
    """Open smbus2.SMBus(bus_num) — only imported on demand so the
    module stays import-safe on Windows."""
    import smbus2  # type: ignore[import-not-found]
    return smbus2.SMBus(bus_num)


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Read-only I2C HAT detection for AstromechOS.")
    ap.add_argument('--output', default=_default_output_path(),
                    help="JSON output path (default: master/config/hw_layout.json)")
    ap.add_argument('--role', choices=('master', 'slave', 'auto'),
                    default='auto',
                    help="Host role — auto = derive from cfg + hostname")
    ap.add_argument('--bus', type=int, default=DEFAULT_BUS,
                    help="I2C bus number (default: 1)")
    ap.add_argument('--start', type=lambda s: int(s, 0),
                    default=DEFAULT_ADDR_START,
                    help="First address to scan, inclusive (default 0x40)")
    ap.add_argument('--end',   type=lambda s: int(s, 0),
                    default=DEFAULT_ADDR_END,
                    help="Last address to scan, inclusive (default 0x47)")
    ap.add_argument('--dry-run', action='store_true',
                    help="Print JSON to stdout, do not write the file")
    ap.add_argument('--no-lock', action='store_true',
                    help="Skip the /run/astromech-i2c.lock acquisition "
                         "(use only when the master service is stopped)")
    # Phase G2 (chantier 2026-05-28): if config_mapping.json is absent for
    # the role, synthesise one from the legacy cfg + the freshly-detected
    # layout and write it atomically. Default ON; use --no-write-mapping
    # in tests or when the operator wants to keep the file under manual
    # control without auto-generation.
    ap.add_argument('--write-mapping',
                    dest='write_mapping', action='store_true',
                    default=True,
                    help="When config_mapping.json is absent, synthesise + write it "
                         "(default: enabled).")
    ap.add_argument('--no-write-mapping',
                    dest='write_mapping', action='store_false',
                    help="Skip the config_mapping.json synthesis even if the file is absent.")
    ap.add_argument('-v', '--verbose', action='store_true')
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    )

    cfg_paths = _default_cfg_paths()
    host = resolve_host_role(
        explicit=None if args.role == 'auto' else args.role,
        cfg_paths=cfg_paths,
    )
    if host == 'unknown':
        log.warning("Host role could not be auto-detected — JSON will carry "
                    "host='unknown' and HATs will have role='unknown'. "
                    "Pass --role master|slave to override.")

    # Acquire bus lock + open smbus.
    try:
        lock_ctx = (I2CBusLock(blocking=False) if not args.no_lock
                    else _NullCtx())
        with lock_ctx:
            try:
                raw_bus = _open_real_bus(args.bus)
            except ImportError:
                log.error("smbus2 not installed — install via apt "
                          "(`apt install python3-smbus`) or pip.")
                return 2
            except FileNotFoundError:
                log.error("/dev/i2c-%d not found — enable I2C via raspi-config",
                          args.bus)
                return 3
            except PermissionError:
                log.error("Permission denied opening /dev/i2c-%d — add the user "
                          "to the i2c group (`usermod -aG i2c $USER`) or run as root",
                          args.bus)
                return 4
            bus = ReadOnlySMBus(raw_bus)
            try:
                layout = detect(bus, host=host, bus_num=args.bus,
                                addr_start=args.start, addr_end=args.end,
                                cfg_paths=cfg_paths)
            finally:
                bus.close()
    except BlockingIOError as e:
        log.error("%s", e)
        return 5

    if args.dry_run:
        print(json.dumps(layout, indent=2))
    else:
        write_layout(layout, args.output)
        log.info("Wrote %s (host=%s, %d HAT%s detected)",
                 args.output, host, len(layout['hats']),
                 '' if len(layout['hats']) == 1 else 's')
        # Phase G2: also synthesise config_mapping.json when absent.
        # The operator's existing file is never overwritten — only a
        # brand-new install (or one whose mapping file was deleted) gets
        # the auto-synthesised version. Subsequent re-mapping is done
        # via the Settings UI (Phase G6 — separate chantier).
        if args.write_mapping and host in ('master', 'slave'):
            _maybe_write_mapping(host, cfg_paths, args.output)
    return 0


def _maybe_write_mapping(role: str, cfg_paths: list[str],
                         layout_output: str) -> None:
    """Synthesise + write <repo>/{role}/config/config_mapping.json IF the
    file does not already exist. Uses shared.hw_mapping to build the
    skeleton from the legacy cfg [i2c_servo_hats] section; the operator
    can then edit it via the Settings UI later (Phase G6).

    Atomic write via the same tmp+os.replace pattern as write_layout(),
    so a crash mid-write never leaves a half-formed file. Never raises
    — failure to write a mapping is non-fatal (services fall back to
    the synthesise-from-layout in-memory path)."""
    # When invoked via `python3 scripts/detect_hats.py …`, only the
    # scripts/ dir is on sys.path by default — the repo root must be
    # injected manually so `from shared import …` resolves. Idempotent.
    _repo_root = str(Path(__file__).resolve().parent.parent)
    if _repo_root not in sys.path:
        sys.path.insert(0, _repo_root)
    try:
        from shared import hw_mapping as _hwm
    except Exception as e:
        log.warning("config_mapping: hw_mapping import failed (%s) — skipping", e)
        return

    # Derive output path next to the layout file for parity.
    # <repo>/{master|slave}/config/config_mapping.json
    repo = Path(__file__).resolve().parent.parent
    out_path = repo / role / 'config' / 'config_mapping.json'

    if out_path.is_file():
        log.info("config_mapping: %s already exists — leaving operator's file untouched", out_path)
        return

    try:
        mapping = _hwm.synthesize_from_layout(role, cfg_paths=cfg_paths)
    except Exception as e:
        log.warning("config_mapping: synthesis failed (%s) — skipping write", e)
        return

    # Stamp the timestamp so it's not None on disk.
    mapping['updated_at'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    # The 'synthesised' flag is informational — kept so the UI can show
    # "auto-generated, please review" if it wants.

    # Atomic write via tmpfile + os.replace + chmod 0o644 — same pattern
    # as write_layout(). Never leaves a half-formed file even on crash.
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(out_path.parent),
                                   prefix='.config_mapping.')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(mapping, f, indent=2, sort_keys=False)
                f.write('\n')
            os.replace(tmp, str(out_path))
            try:
                os.chmod(str(out_path), 0o644)
            except Exception:
                pass
            log.info("Wrote %s (synthesised from cfg, %d HAT(s))",
                     out_path, len(mapping.get('hats', [])))
        except Exception:
            try:
                os.unlink(tmp)
            except Exception:
                pass
            raise
    except Exception as e:
        log.warning("config_mapping: write %s failed (%s) — non-fatal", out_path, e)


class _NullCtx:
    def __enter__(self): return self
    def __exit__(self, *a): pass


if __name__ == '__main__':
    sys.exit(main())
