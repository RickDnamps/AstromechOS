# ============================================================
#  ██████╗ ██████╗       ██████╗ ██████╗
#  ██╔══██╗╚════██╗      ██╔══██╗╚════██╗
#  ██████╔╝ █████╔╝      ██║  ██║ █████╔╝
#  ██╔══██╗██╔═══╝       ██║  ██║██╔═══╝
#  ██║  ██║███████╗      ██████╔╝███████╗
#  ╚═╝  ╚═╝╚══════╝      ╚═════╝ ╚══════╝
#
#  R2-D2 Control System — Distributed Robot Controller
# ============================================================
#  Copyright (C) 2025 RickDnamps
#  https://github.com/RickDnamps/R2D2_Control
#
#  This file is part of R2D2_Control.
#
#  R2D2_Control is free software: you can redistribute it
#  and/or modify it under the terms of the GNU General
#  Public License as published by the Free Software
#  Foundation, either version 2 of the License, or
#  (at your option) any later version.
#
#  R2D2_Control is distributed in the hope that it will be
#  useful, but WITHOUT ANY WARRANTY; without even the implied
#  warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
#  PURPOSE. See the GNU General Public License for details.
#
#  You should have received a copy of the GNU GPL along with
#  R2D2_Control. If not, see <https://www.gnu.org/licenses/>.
# ============================================================
"""
Master Dome Servo Driver — Phase 2 (MG90S 180°).
Drives the PCA9685 I2C @ 0x40 directly via smbus2 (hardware registers).
11 dome panel servos, channels 0–10.

MG90S 180° servo: pulse_us = 500 + (angle_deg / 180.0) * 2000
open()  → moves to open_angle_deg and holds position
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

DOME_ANGLES_FILE = '/home/artoo/r2d2/master/config/dome_angles.json'

PCA9685_ADDRESS = 0x40
PCA9685_FREQ_HZ = 50
MODE1_REG       = 0x00
PRE_SCALE_REG   = 0xFE
PRE_SCALE_50HZ  = 121

DEFAULT_OPEN_DEG  = 110   # MG90S open angle (0–180°)
DEFAULT_CLOSE_DEG =  20   # MG90S close angle (0–180°)
ANGLE_MIN_DEG     =  10   # hardware safety limit
ANGLE_MAX_DEG     = 170   # hardware safety limit

SERVO_MAP: dict[str, int] = {
    'dome_panel_1':   0,
    'dome_panel_2':   1,
    'dome_panel_3':   2,
    'dome_panel_4':   3,
    'dome_panel_5':   4,
    'dome_panel_6':   5,
    'dome_panel_7':   6,
    'dome_panel_8':   7,
    'dome_panel_9':   8,
    'dome_panel_10':  9,
    'dome_panel_11': 10,
}


def _angle_to_pulse(angle_deg: float) -> float:
    """Converts an MG90S angle to µs for PCA9685."""
    angle_deg = max(ANGLE_MIN_DEG, min(ANGLE_MAX_DEG, angle_deg))
    return 500.0 + (angle_deg / 180.0) * 2000.0


def _pulse_to_tick(pulse_us: float) -> int:
    """Converts µs to 12-bit PCA9685 value (hardware registers)."""
    return max(0, min(4095, int(pulse_us / 20000.0 * 4096)))


def _load_dome_angles() -> dict:
    """Loads calibrated angles from master/config/dome_angles.json."""
    try:
        with open(DOME_ANGLES_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


class DomeServoDriver(BaseDriver):

    def __init__(self, i2c_address: int = PCA9685_ADDRESS):
        self._address     = i2c_address
        self._bus         = None
        self._ready       = False
        self._lock        = threading.Lock()
        self._error_count = 0
        self._angles      = {}
        self._pos         = {}   # last commanded angle per servo

    def _get_angle(self, name: str, key: str, default: float) -> float:
        return float(self._angles.get(name, {}).get(key, default))

    def _get_close_angle(self, name: str) -> float:
        return self._get_angle(name, 'close', DEFAULT_CLOSE_DEG)

    def setup(self) -> bool:
        try:
            import smbus2
            self._angles = _load_dome_angles()
            self._bus = smbus2.SMBus(1)
            self._init_chip()
            self._ready = True
            log.info("DomeServoDriver ready — smbus2 @ 0x%02X, %d panels",
                     self._address, len(SERVO_MAP))
            return True
        except Exception as e:
            log.error("Error initializing dome PCA9685: %s", e)
            return False

    def shutdown(self) -> None:
        if self._bus:
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

    def move(self, name: str, position: float,
             angle_open: float = DEFAULT_OPEN_DEG,
             angle_close: float = DEFAULT_CLOSE_DEG) -> bool:
        """position 0.0=closed … 1.0=open — interpolated between angle_close and angle_open."""
        angle = angle_close + max(0.0, min(1.0, position)) * (angle_open - angle_close)
        return self._move(name, angle)

    @property
    def state(self) -> dict:
        return {n: 'unknown' for n in SERVO_MAP}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _init_chip(self) -> None:
        """Initialize the PCA9685 at 50Hz.
        Servo channels go directly to calibrated close_angle — no intermediate _full_off()
        that would cause torque loss and jerk at boot."""
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
        # Servo channels → calibrated close position directly, without full_off
        for name, ch in SERVO_MAP.items():
            close_a = self._get_close_angle(name)
            self._set_pulse(ch, _angle_to_pulse(close_a))
            self._pos[name] = close_a
        log.info("PCA9685 @ 0x%02X initialized at 50Hz — servos → calibrated close_angle", self._address)

    def _ensure_awake(self) -> None:
        """Wake the chip if it is in sleep mode (e.g., after estop.py)."""
        try:
            mode1 = self._bus.read_byte_data(self._address, MODE1_REG)
            if mode1 & 0x10:
                self._bus.write_byte_data(self._address, MODE1_REG, mode1 & ~0x10)
                time.sleep(0.002)
                log.info("PCA9685 @ 0x%02X woken up (was in sleep)", self._address)
        except Exception as e:
            log.warning("_ensure_awake 0x%02X: %s", self._address, e)

    def _full_off(self, channel: int) -> None:
        """Fully disable a channel (FULL_OFF bit)."""
        base = 0x06 + 4 * channel
        self._bus.write_byte_data(self._address, base,     0x00)
        self._bus.write_byte_data(self._address, base + 1, 0x00)
        self._bus.write_byte_data(self._address, base + 2, 0x00)
        self._bus.write_byte_data(self._address, base + 3, 0x10)

    def _try_reinit(self) -> None:
        """Close and reopen the I2C bus and reinitialize the PCA9685 after repeated errors."""
        try:
            if self._bus:
                try:
                    self._bus.close()
                except Exception:
                    pass
            import smbus2
            self._bus = smbus2.SMBus(1)
            self._init_chip()
            self._error_count = 0
            log.info("PCA9685 @ 0x%02X reinitialized after I2C errors", self._address)
        except Exception as e:
            log.error("Failed to reinitialize PCA9685 @ 0x%02X: %s", self._address, e)

    def _set_pulse(self, channel: int, pulse_us: float) -> None:
        tick = _pulse_to_tick(pulse_us)
        base = 0x06 + 4 * channel
        with self._lock:
            try:
                self._bus.write_byte_data(self._address, base,     0x00)
                self._bus.write_byte_data(self._address, base + 1, 0x00)
                self._bus.write_byte_data(self._address, base + 2, tick & 0xFF)
                self._bus.write_byte_data(self._address, base + 3, tick >> 8)
                self._error_count = 0
            except Exception as e:
                self._error_count += 1
                log.error("smbus2 error on dome channel %d: %s (consecutive: %d)",
                           channel, e, self._error_count)
                if self._error_count >= 3:
                    log.warning("PCA9685 @ 0x%02X — %d I2C errors, reinitializing...",
                                self._address, self._error_count)
                    self._try_reinit()

    def _move(self, name: str, angle_deg: float) -> bool:
        if not self._ready:
            log.warning("DomeServoDriver not ready — command ignored (%r)", name)
            return False
        if name not in SERVO_MAP:
            log.warning("Unknown dome panel: %r", name)
            return False
        channel  = SERVO_MAP[name]
        pulse_us = _angle_to_pulse(angle_deg)
        self._ensure_awake()
        self._set_pulse(channel, pulse_us)
        self._pos[name] = angle_deg
        log.info("Dome servo %r ch%d → %.1f° (%.0fµs)", name, channel, angle_deg, pulse_us)
        return True

    def _move_ramp(self, name: str, target: float, speed: int = 10) -> bool:
        """Move servo with optional ramp (speed 1=slow … 10=instant)."""
        speed = max(1, min(10, int(speed)))
        if speed >= 10:
            return self._move(name, target)
        current   = self._pos.get(name, self._get_close_angle(name))
        step      = 2.0
        delay     = (10 - speed) * 0.003   # 3ms per speed unit, per step
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
