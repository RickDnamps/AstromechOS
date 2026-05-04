# ============================================================
#   █████╗  ██████╗ ███████╗
#  ██╔══██╗██╔═══██╗██╔════╝
#  ███████║██║   ██║███████╗
#  ██╔══██║██║   ██║╚════██║
#  ██║  ██║╚██████╔╝███████║
#  ╚═╝  ╚═╝ ╚═════╝ ╚══════╝
#
#  AstromechOS — Open control platform for astromech builders
# ============================================================
#  Copyright (C) 2026 RickDnamps
#  https://github.com/RickDnamps/AstromechOS
#
#  This file is part of AstromechOS.
#
#  AstromechOS is free software: you can redistribute it
#  and/or modify it under the terms of the GNU General
#  Public License as published by the Free Software
#  Foundation, either version 2 of the License, or
#  (at your option) any later version.
#
#  AstromechOS is distributed in the hope that it will be
#  useful, but WITHOUT ANY WARRANTY; without even the implied
#  warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
#  PURPOSE. See the GNU General Public License for details.
#
#  You should have received a copy of the GNU GPL along with
#  AstromechOS. If not, see <https://www.gnu.org/licenses/>.
# ============================================================
"""
Master Dome Servo Driver — Phase 2 (MG90S 180°).
Drives one or more PCA9685 HATs via smbus2.
HAT addresses come from local.cfg [i2c_servo_hats] master_hats (default: 0x40).
Each HAT covers 16 channels: HAT1 → Servo_M0..M15, HAT2 → Servo_M16..M31, etc.

MG90S 180° servo: pulse_us = 500 + (angle_deg / 180.0) * 2000
12-bit formula: tick = int((pulse_us / 20000.0) * 4096)
"""

import configparser
import json
import logging
import threading
import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.base_driver import BaseDriver

log = logging.getLogger(__name__)

DOME_ANGLES_FILE = '/home/artoo/r2d2/master/config/dome_angles.json'
_MAIN_CFG        = '/home/artoo/r2d2/master/config/main.cfg'
_LOCAL_CFG       = '/home/artoo/r2d2/master/config/local.cfg'

PCA9685_FREQ_HZ = 50
MODE1_REG       = 0x00
PRE_SCALE_REG   = 0xFE
PRE_SCALE_50HZ  = 121

DEFAULT_OPEN_DEG  = 110
DEFAULT_CLOSE_DEG =  20
ANGLE_MIN_DEG     =  10
ANGLE_MAX_DEG     = 170


def _read_master_hat_addresses() -> list:
    """Returns list of I2C addresses for Master servo HATs from local.cfg."""
    cfg = configparser.ConfigParser()
    cfg.read([_MAIN_CFG, _LOCAL_CFG])
    raw = cfg.get('i2c_servo_hats', 'master_hats', fallback='0x40')
    result = []
    for p in raw.split(','):
        p = p.strip()
        if p:
            try:
                result.append(int(p, 16) if p.startswith('0x') else int(p))
            except ValueError:
                pass
    return result or [0x40]


def _angle_to_pulse(angle_deg: float) -> float:
    angle_deg = max(ANGLE_MIN_DEG, min(ANGLE_MAX_DEG, angle_deg))
    return 500.0 + (angle_deg / 180.0) * 2000.0


def _pulse_to_tick(pulse_us: float) -> int:
    return max(0, min(4095, int(pulse_us / 20000.0 * 4096)))


def _load_dome_angles() -> dict:
    try:
        with open(DOME_ANGLES_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


class DomeServoDriver(BaseDriver):

    def __init__(self):
        self._addresses  = _read_master_hat_addresses()
        self._buses      = [None] * len(self._addresses)
        self._ready      = False
        self._lock       = threading.Lock()
        self._error_cnt  = [0] * len(self._addresses)
        self._angles     = {}
        self._pos        = {}
        # servo_name → (hat_idx, channel)
        self._servo_map  = {
            f'Servo_M{hat * 16 + ch}': (hat, ch)
            for hat in range(len(self._addresses))
            for ch in range(16)
        }

    def _get_angle(self, name: str, key: str, default: float) -> float:
        return float(self._angles.get(name, {}).get(key, default))

    def _get_close_angle(self, name: str) -> float:
        return self._get_angle(name, 'close', DEFAULT_CLOSE_DEG)

    def setup(self) -> bool:
        try:
            import smbus2
            self._angles = _load_dome_angles()
            bus = smbus2.SMBus(1)
            # Share one SMBus instance — I2C bus is shared, addresses differ
            for i, addr in enumerate(self._addresses):
                self._buses[i] = bus
                self._init_chip(i)
            self._ready = True
            log.info("DomeServoDriver ready — %d HAT(s) %s, %d servos",
                     len(self._addresses),
                     [hex(a) for a in self._addresses],
                     len(self._servo_map))
            return True
        except Exception as e:
            log.error("Error initializing dome PCA9685: %s", e)
            return False

    def shutdown(self) -> None:
        for hat_idx, addr in enumerate(self._addresses):
            bus = self._buses[hat_idx]
            if not bus:
                continue
            for name, (hi, ch) in self._servo_map.items():
                if hi == hat_idx:
                    self._set_pulse(hat_idx, ch, _angle_to_pulse(self._get_close_angle(name)))
            time.sleep(0.3)
            try:
                bus.write_byte_data(addr, MODE1_REG, 0x10)
            except Exception:
                pass
        try:
            if self._buses and self._buses[0]:
                self._buses[0].close()
        except Exception:
            pass
        self._buses  = [None] * len(self._addresses)
        self._ready  = False

    def is_ready(self) -> bool:
        return self._ready

    def reload(self) -> None:
        self._angles = _load_dome_angles()
        log.info("DomeServoDriver: angles reloaded (%d entries)", len(self._angles))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def open(self, name: str, angle_deg: float = None, speed: int = None) -> bool:
        if angle_deg is None:
            angle_deg = self._get_angle(name, 'open', DEFAULT_OPEN_DEG)
        if speed is None:
            speed = int(self._get_angle(name, 'speed', 10))
        return self._move_ramp(name, angle_deg, speed)

    def close(self, name: str, angle_deg: float = None, speed: int = None) -> bool:
        if angle_deg is None:
            angle_deg = self._get_close_angle(name)
        if speed is None:
            speed = int(self._get_angle(name, 'speed', 10))
        return self._move_ramp(name, angle_deg, speed)

    def open_all(self) -> None:
        threads = []
        for name in self._servo_map:
            angle = self._get_angle(name, 'open', DEFAULT_OPEN_DEG)
            speed = int(self._get_angle(name, 'speed', 10))
            t = threading.Thread(target=self._move_ramp, args=(name, angle, speed), daemon=True)
            threads.append(t); t.start()
        for t in threads: t.join()

    def close_all(self) -> None:
        threads = []
        for name in self._servo_map:
            angle = self._get_close_angle(name)
            speed = int(self._get_angle(name, 'speed', 10))
            t = threading.Thread(target=self._move_ramp, args=(name, angle, speed), daemon=True)
            threads.append(t); t.start()
        for t in threads: t.join()

    def move(self, name: str, position: float,
             angle_open: float = DEFAULT_OPEN_DEG,
             angle_close: float = DEFAULT_CLOSE_DEG) -> bool:
        angle = angle_close + max(0.0, min(1.0, position)) * (angle_open - angle_close)
        return self._move(name, angle)

    @property
    def state(self) -> dict:
        return {n: 'unknown' for n in self._servo_map}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _init_chip(self, hat_idx: int) -> None:
        addr = self._addresses[hat_idx]
        bus  = self._buses[hat_idx]
        bus.write_byte_data(addr, MODE1_REG, 0x00)
        time.sleep(0.005)
        bus.write_byte_data(addr, MODE1_REG, 0x10)
        time.sleep(0.005)
        bus.write_byte_data(addr, PRE_SCALE_REG, PRE_SCALE_50HZ)
        bus.write_byte_data(addr, MODE1_REG, 0x00)
        time.sleep(0.005)
        bus.write_byte_data(addr, MODE1_REG, 0x80)
        time.sleep(0.005)
        servo_channels = {ch for (hi, ch) in self._servo_map.values() if hi == hat_idx}
        for ch in range(16):
            if ch not in servo_channels:
                self._full_off(hat_idx, ch)
        for name, (hi, ch) in self._servo_map.items():
            if hi == hat_idx:
                close_a = self._get_close_angle(name)
                self._set_pulse(hat_idx, ch, _angle_to_pulse(close_a))
                self._pos[name] = close_a
        log.info("PCA9685 @ 0x%02X initialized 50Hz — servos → calibrated close_angle", addr)

    def _ensure_awake(self, hat_idx: int) -> None:
        addr = self._addresses[hat_idx]
        bus  = self._buses[hat_idx]
        try:
            mode1 = bus.read_byte_data(addr, MODE1_REG)
            if mode1 & 0x10:
                bus.write_byte_data(addr, MODE1_REG, mode1 & ~0x10)
                time.sleep(0.002)
                log.info("PCA9685 @ 0x%02X woken up", addr)
        except Exception as e:
            log.warning("_ensure_awake 0x%02X: %s", addr, e)

    def _full_off(self, hat_idx: int, channel: int) -> None:
        addr = self._addresses[hat_idx]
        bus  = self._buses[hat_idx]
        base = 0x06 + 4 * channel
        bus.write_byte_data(addr, base,     0x00)
        bus.write_byte_data(addr, base + 1, 0x00)
        bus.write_byte_data(addr, base + 2, 0x00)
        bus.write_byte_data(addr, base + 3, 0x10)

    def _try_reinit(self, hat_idx: int) -> None:
        try:
            import smbus2
            if self._buses[hat_idx]:
                try:
                    self._buses[hat_idx].close()
                except Exception:
                    pass
            self._buses[hat_idx] = smbus2.SMBus(1)
            self._init_chip(hat_idx)
            self._error_cnt[hat_idx] = 0
            log.info("PCA9685 @ 0x%02X reinitialized", self._addresses[hat_idx])
        except Exception as e:
            log.error("Failed to reinitialize PCA9685 @ 0x%02X: %s", self._addresses[hat_idx], e)

    def _set_pulse(self, hat_idx: int, channel: int, pulse_us: float) -> None:
        tick = _pulse_to_tick(pulse_us)
        addr = self._addresses[hat_idx]
        bus  = self._buses[hat_idx]
        base = 0x06 + 4 * channel
        with self._lock:
            try:
                bus.write_byte_data(addr, base,     0x00)
                bus.write_byte_data(addr, base + 1, 0x00)
                bus.write_byte_data(addr, base + 2, tick & 0xFF)
                bus.write_byte_data(addr, base + 3, tick >> 8)
                self._error_cnt[hat_idx] = 0
            except Exception as e:
                self._error_cnt[hat_idx] += 1
                log.error("smbus2 error HAT%d ch%d: %s (consecutive: %d)",
                           hat_idx, channel, e, self._error_cnt[hat_idx])
                if self._error_cnt[hat_idx] >= 3:
                    log.warning("PCA9685 @ 0x%02X — 3 I2C errors, reinitializing...", addr)
                    self._try_reinit(hat_idx)

    def _move(self, name: str, angle_deg: float) -> bool:
        if not self._ready:
            log.warning("DomeServoDriver not ready — command ignored (%r)", name)
            return False
        if name not in self._servo_map:
            log.warning("Unknown dome panel: %r", name)
            return False
        hat_idx, channel = self._servo_map[name]
        pulse_us = _angle_to_pulse(angle_deg)
        self._ensure_awake(hat_idx)
        self._set_pulse(hat_idx, channel, pulse_us)
        self._pos[name] = angle_deg
        log.info("Dome servo %r HAT%d ch%d → %.1f°", name, hat_idx, channel, angle_deg)
        return True

    def _move_ramp(self, name: str, target: float, speed: int = 10) -> bool:
        speed = max(1, min(10, int(speed)))
        if speed >= 10:
            return self._move(name, target)
        current   = self._pos.get(name, self._get_close_angle(name))
        step      = 2.0
        delay     = (10 - speed) * 0.003
        direction = 1.0 if target > current else -1.0
        angle     = current
        while True:
            angle += direction * step
            if direction > 0 and angle >= target:
                angle = target
            elif direction < 0 and angle <= target:
                angle = target
            self._move(name, angle)
            if delay > 0:
                time.sleep(delay)
            if angle == target:
                break
        return True
