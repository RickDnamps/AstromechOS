# ============================================================
#  ██████╗ ██████╗       ██████╗ ██████╗
#  ██╔══██╗╚════██╗      ██╔══██╗╚════██╗
#  ██████╔╝ █████╔╝      ██║  ██║ █████╔╝
#  ██╔══██╗██╔═══╝       ██║  ██║██╔═══╝
#  ██║  ██║███████╗      ██████╔╝███████╗
#  ╚═╝  ╚═╝╚══════╝      ╚═════╝ ╚══════╝
#
#  AstromechOS — Open control platform for astromech builders
# ============================================================
#  Copyright (C) 2025 RickDnamps
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
Receives SRV: commands from the Master and drives the PCA9685 I2C @ 0x41 via smbus2.

MG90S 180° servo: pulse_us = 500 + (angle_deg / 180.0) * 2000
open()  → moves to open_angle_deg and holds position (no timer)
close() → moves to close_angle_deg and holds position

12-bit formula (PCA9685 hardware registers):
    tick = int((pulse_us / 20000.0) * 4096)
"""

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

PCA9685_ADDRESS = 0x41
PCA9685_FREQ_HZ = 50
MODE1_REG       = 0x00
PRE_SCALE_REG   = 0xFE
PRE_SCALE_50HZ  = 121

DEFAULT_OPEN_DEG  = 110   # MG90S open angle (0–180°)
DEFAULT_CLOSE_DEG =  20   # MG90S close angle (0–180°)
ANGLE_MIN_DEG     =  10   # hardware safety limit
ANGLE_MAX_DEG     = 170   # hardware safety limit

SERVO_MAP: dict[str, int] = {
    'Servo_S0':   0,
    'Servo_S1':   1,
    'Servo_S2':   2,
    'Servo_S3':   3,
    'Servo_S4':   4,
    'Servo_S5':   5,
    'Servo_S6':   6,
    'Servo_S7':   7,
    'Servo_S8':   8,
    'Servo_S9':   9,
    'Servo_S10': 10,
    'Servo_S11': 11,
    'Servo_S12': 12,
    'Servo_S13': 13,
    'Servo_S14': 14,
    'Servo_S15': 15,
}


def _angle_to_pulse(angle_deg: float) -> float:
    """Converts an MG90S angle to µs for PCA9685."""
    angle_deg = max(ANGLE_MIN_DEG, min(ANGLE_MAX_DEG, angle_deg))
    return 500.0 + (angle_deg / 180.0) * 2000.0


def _pulse_to_tick(pulse_us: float) -> int:
    """Converts µs to 12-bit PCA9685 value (hardware registers)."""
    return max(0, min(4095, int(pulse_us / 20000.0 * 4096)))


def _load_servo_angles() -> dict:
    """Loads calibrated angles from slave/config/servo_angles.json."""
    try:
        with open(SERVO_ANGLES_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


class BodyServoDriver(BaseDriver):

    def __init__(self, i2c_address: int = PCA9685_ADDRESS):
        self._address = i2c_address
        self._bus     = None
        self._ready   = False
        self._lock    = threading.Lock()
        self._angles  = {}   # calibrated angles loaded at setup()
        self._pos     = {}   # last commanded angle per servo

    def _get_angle(self, name: str, key: str, default: float) -> float:
        return float(self._angles.get(name, {}).get(key, default))

    def _get_close_angle(self, name: str) -> float:
        return self._get_angle(name, 'close', DEFAULT_CLOSE_DEG)

    def setup(self) -> bool:
        try:
            import smbus2
            self._angles = _load_servo_angles()
            self._bus = smbus2.SMBus(1)
            self._init_chip()
            self._ready = True
            log.info("BodyServoDriver ready — smbus2 @ 0x%02X, %d servos",
                     self._address, len(SERVO_MAP))
            return True
        except Exception as e:
            log.error("PCA9685 body init error: %s", e)
            return False

    def shutdown(self) -> None:
        if self._bus:
            # Close each panel with its calibrated angle
            for name, ch in SERVO_MAP.items():
                self._set_pulse(ch, _angle_to_pulse(self._get_close_angle(name)))
            time.sleep(0.3)
            try:
                self._bus.write_byte_data(self._address, MODE1_REG, 0x10)  # SLEEP
            except Exception:
                pass
            try:
                self._bus.close()
            except Exception:
                pass
        self._bus   = None
        self._ready = False

    def is_ready(self) -> bool:
        return self._ready

    def reload(self) -> None:
        """Reloads calibrated angles from servo_angles.json without restarting the driver."""
        self._angles = _load_servo_angles()
        log.info("BodyServoDriver: angles reloaded from disk (%d entries)", len(self._angles))

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
        """position 0.0=closed … 1.0=open — interpolated between angle_close and angle_open."""
        angle = angle_close + max(0.0, min(1.0, position)) * (angle_open - angle_close)
        self._move(name, angle)

    def open_all(self) -> None:
        threads = []
        for name in SERVO_MAP:
            angle = self._get_angle(name, 'open', DEFAULT_OPEN_DEG)
            speed = int(self._get_angle(name, 'speed', 10))
            t = threading.Thread(target=self._move_ramp, args=(name, angle, speed), daemon=True)
            threads.append(t); t.start()
        for t in threads: t.join()

    def close_all(self) -> None:
        threads = []
        for name in SERVO_MAP:
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
        return {n: 'unknown' for n in SERVO_MAP}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _init_chip(self) -> None:
        """Initializes the PCA9685 at 50Hz frequency.
        Servo channels go directly to calibrated close_angle — no intermediate _full_off()
        which would cause torque loss and a jerk at boot."""
        self._bus.write_byte_data(self._address, MODE1_REG, 0x00)
        time.sleep(0.005)
        self._bus.write_byte_data(self._address, MODE1_REG, 0x10)
        time.sleep(0.005)
        self._bus.write_byte_data(self._address, PRE_SCALE_REG, PRE_SCALE_50HZ)
        self._bus.write_byte_data(self._address, MODE1_REG, 0x00)
        time.sleep(0.005)
        self._bus.write_byte_data(self._address, MODE1_REG, 0x80)
        time.sleep(0.005)
        # Non-servo channels → full_off (no load)
        servo_channels = set(SERVO_MAP.values())
        for ch in range(16):
            if ch not in servo_channels:
                self._full_off(ch)
        # Servo channels → calibrated closed position directly, without full_off
        for name, ch in SERVO_MAP.items():
            close_a = self._get_close_angle(name)
            self._set_pulse(ch, _angle_to_pulse(close_a))
            self._pos[name] = close_a
        log.info("PCA9685 @ 0x%02X initialized 50Hz — servos → calibrated close_angle", self._address)

    def _ensure_awake(self) -> None:
        """Wakes the chip if it is sleeping (e.g. after estop.py)."""
        try:
            mode1 = self._bus.read_byte_data(self._address, MODE1_REG)
            if mode1 & 0x10:
                self._bus.write_byte_data(self._address, MODE1_REG, mode1 & ~0x10)
                time.sleep(0.002)
                log.info("PCA9685 @ 0x%02X woken up (was sleeping)", self._address)
        except Exception as e:
            log.warning("_ensure_awake 0x%02X: %s", self._address, e)

    def _full_off(self, channel: int) -> None:
        base = 0x06 + 4 * channel
        self._bus.write_byte_data(self._address, base,     0x00)
        self._bus.write_byte_data(self._address, base + 1, 0x00)
        self._bus.write_byte_data(self._address, base + 2, 0x00)
        self._bus.write_byte_data(self._address, base + 3, 0x10)

    def _set_pulse(self, channel: int, pulse_us: float) -> None:
        tick = _pulse_to_tick(pulse_us)
        base = 0x06 + 4 * channel
        with self._lock:
            try:
                self._bus.write_byte_data(self._address, base,     0x00)
                self._bus.write_byte_data(self._address, base + 1, 0x00)
                self._bus.write_byte_data(self._address, base + 2, tick & 0xFF)
                self._bus.write_byte_data(self._address, base + 3, tick >> 8)
            except Exception as e:
                log.error("smbus2 body channel %d error: %s", channel, e)

    def _move(self, name: str, angle_deg: float) -> None:
        if not self._ready:
            log.warning("BodyServoDriver not ready — command ignored (%r)", name)
            return
        if name not in SERVO_MAP:
            log.warning("Unknown servo: %r", name)
            return
        channel  = SERVO_MAP[name]
        pulse_us = _angle_to_pulse(angle_deg)
        self._ensure_awake()
        self._set_pulse(channel, pulse_us)
        self._pos[name] = angle_deg
        log.info("Body servo %r ch%d → %.1f° (%.0fµs)", name, channel, angle_deg, pulse_us)

    def _move_ramp(self, name: str, target: float, speed: int = 10) -> None:
        """Moves the servo with an optional ramp (speed 1=slow … 10=instant)."""
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
