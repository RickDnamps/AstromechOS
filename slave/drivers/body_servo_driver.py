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
Slave Body Servo Driver — Phase 2 (MG90S 180°).
Drives one or more PCA9685 HATs via smbus2.
HAT addresses come from slave.cfg [i2c_servo_hats] slave_hats (default: 0x41).
Each HAT covers 16 channels: HAT1 → Servo_S0..S15, HAT2 → Servo_S16..S31, etc.

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

SERVO_ANGLES_FILE = '/home/artoo/r2d2/slave/config/servo_angles.json'
_SLAVE_CFG        = '/home/artoo/r2d2/slave/config/slave.cfg'

PCA9685_FREQ_HZ = 50
MODE1_REG       = 0x00
PRE_SCALE_REG   = 0xFE
PRE_SCALE_50HZ  = 121

DEFAULT_OPEN_DEG  = 110
DEFAULT_CLOSE_DEG =  20
ANGLE_MIN_DEG     =  10
ANGLE_MAX_DEG     = 170


def _read_slave_hat_addresses() -> list:
    """Returns list of I2C addresses for Slave servo HATs from slave.cfg.
    Warns if the motor HAT address is accidentally listed as a servo HAT.
    """
    cfg = configparser.ConfigParser()
    cfg.read([_SLAVE_CFG])
    raw = cfg.get('i2c_servo_hats', 'slave_hats', fallback='0x41')
    result = []
    for p in raw.split(','):
        p = p.strip()
        if p:
            try:
                result.append(int(p, 16) if p.startswith('0x') else int(p))
            except ValueError:
                pass
    addresses = result or [0x41]
    # Safety check — warn if motor HAT address is in the servo HAT list
    motor_raw = cfg.get('i2c_servo_hats', 'slave_motor_hat', fallback='0x40')
    try:
        motor_addr = int(motor_raw.strip(), 16) if motor_raw.strip().startswith('0x') else int(motor_raw.strip())
        if motor_addr in addresses:
            log.error(
                "CONFIGURATION ERROR: Motor HAT address 0x%02X is listed as a servo HAT in slave.cfg! "
                "This will damage your Motor HAT. Fix slave_hats to exclude 0x%02X.",
                motor_addr, motor_addr
            )
    except ValueError:
        pass
    return addresses


def _angle_to_pulse(angle_deg: float) -> float:
    angle_deg = max(ANGLE_MIN_DEG, min(ANGLE_MAX_DEG, angle_deg))
    return 500.0 + (angle_deg / 180.0) * 2000.0


def _pulse_to_tick(pulse_us: float) -> int:
    return max(0, min(4095, int(pulse_us / 20000.0 * 4096)))


def _load_servo_angles() -> dict:
    try:
        with open(SERVO_ANGLES_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


class BodyServoDriver(BaseDriver):

    def __init__(self, i2c_address: int = None):
        # i2c_address param kept for backward compat but ignored — config-driven
        self._addresses = _read_slave_hat_addresses()
        self._buses     = [None] * len(self._addresses)
        self._ready     = False
        self._lock      = threading.Lock()
        self._angles    = {}
        self._pos       = {}
        # servo_name → (hat_idx, channel)
        self._servo_map = {
            f'Servo_S{hat * 16 + ch}': (hat, ch)
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
            self._angles = _load_servo_angles()
            bus = smbus2.SMBus(1)
            for i, addr in enumerate(self._addresses):
                self._buses[i] = bus
                self._init_chip(i)
            self._ready = True
            log.info("BodyServoDriver ready — %d HAT(s) %s, %d servos",
                     len(self._addresses),
                     [hex(a) for a in self._addresses],
                     len(self._servo_map))
            return True
        except Exception as e:
            log.error("PCA9685 body init error: %s", e)
            return False

    def shutdown(self) -> None:
        for hat_idx in range(len(self._addresses)):
            bus = self._buses[hat_idx]
            if not bus:
                continue
            for name, (hi, ch) in self._servo_map.items():
                if hi == hat_idx:
                    self._set_pulse(hat_idx, ch, _angle_to_pulse(self._get_close_angle(name)))
            time.sleep(0.3)
            try:
                bus.write_byte_data(self._addresses[hat_idx], MODE1_REG, 0x10)
            except Exception:
                pass
        try:
            if self._buses and self._buses[0]:
                self._buses[0].close()
        except Exception:
            pass
        self._buses = [None] * len(self._addresses)
        self._ready = False

    def is_ready(self) -> bool:
        return self._ready

    def reload(self) -> None:
        self._angles = _load_servo_angles()
        log.info("BodyServoDriver: angles reloaded (%d entries)", len(self._angles))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def open(self, name: str, angle_deg: float = None, speed: int = None) -> None:
        if angle_deg is None:
            angle_deg = self._get_angle(name, 'open', DEFAULT_OPEN_DEG)
        if speed is None:
            speed = int(self._get_angle(name, 'speed', 10))
        self._move_ramp(name, angle_deg, speed)

    def close(self, name: str, angle_deg: float = None, speed: int = None) -> None:
        if angle_deg is None:
            angle_deg = self._get_close_angle(name)
        if speed is None:
            speed = int(self._get_angle(name, 'speed', 10))
        self._move_ramp(name, angle_deg, speed)

    def move(self, name: str, position: float,
             angle_open: float = DEFAULT_OPEN_DEG,
             angle_close: float = DEFAULT_CLOSE_DEG) -> None:
        angle = angle_close + max(0.0, min(1.0, position)) * (angle_open - angle_close)
        self._move(name, angle)

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

    def handle_uart(self, value: str) -> None:
        """Callback UART — SRV:NAME,ANGLE_DEG[,SPEED] or SRV:RELOAD"""
        if value == 'RELOAD':
            self.reload()
            return
        try:
            parts = value.split(',')
            speed = int(parts[2]) if len(parts) >= 3 else 10
            self._move_ramp(parts[0], float(parts[1]), speed)
        except (ValueError, IndexError) as e:
            log.error("Invalid SRV message %r: %s", value, e)

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
            except Exception as e:
                log.error("smbus2 body HAT%d ch%d error: %s", hat_idx, channel, e)

    def _move(self, name: str, angle_deg: float) -> None:
        if not self._ready:
            log.warning("BodyServoDriver not ready — command ignored (%r)", name)
            return
        if name not in self._servo_map:
            log.warning("Unknown servo: %r", name)
            return
        hat_idx, channel = self._servo_map[name]
        pulse_us = _angle_to_pulse(angle_deg)
        self._ensure_awake(hat_idx)
        self._set_pulse(hat_idx, channel, pulse_us)
        self._pos[name] = angle_deg
        log.info("Body servo %r HAT%d ch%d → %.1f°", name, hat_idx, channel, angle_deg)

    def _move_ramp(self, name: str, target: float, speed: int = 10) -> None:
        speed = max(1, min(10, int(speed)))
        if speed >= 10:
            self._move(name, target); return
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
