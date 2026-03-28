#!/usr/bin/env python3
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
Test servo Slave — PCA9685 @ 0x41, channel 0
Supports STANDARD and CONTINUOUS servo modes.

Usage: python3 scripts/test_servo_slave.py [standard|continu]
Default: continu

Standard servo  : 1000µs=0°  1500µs=90°  2000µs=180°
Continuous servo: 1500µs=STOP  <1500=dir1  >1500=dir2
"""

import sys, time

try:
    import board, busio
    from adafruit_pca9685 import PCA9685
except ImportError:
    print("ERREUR: pip install adafruit-circuitpython-pca9685")
    sys.exit(1)

MODE = sys.argv[1] if len(sys.argv) > 1 else "continu"

def us_to_duty(pulse_us):
    return int((pulse_us / 20000.0) * 65535)

i2c = busio.I2C(board.SCL, board.SDA)
pca = PCA9685(i2c, address=0x41)
pca.frequency = 50
print(f"PCA9685 @ 0x41 OK — mode: {MODE}")

def set_pulse(us):
    pca.channels[0].duty_cycle = us_to_duty(us)

def stop():
    set_pulse(1500)
    time.sleep(0.3)
    # Direct sleep mode via smbus2 — stops the oscillator without reset()
    import smbus2
    b = smbus2.SMBus(1)
    b.write_byte_data(0x41, 0x00, 0x10)
    b.close()
    print("STOP", flush=True)

try:
    if MODE == "continu":
        print("Servo continu — lent sens 1 → stop → lent sens 2 → stop (boucle)")
        print("Ctrl+C to stop")
        while True:
            print("  → slow clockwise (1600µs)")
            set_pulse(1600)
            time.sleep(2)
            print("  → STOP (1500µs)")
            set_pulse(1500)
            time.sleep(1)
            print("  → slow counter-clockwise (1400µs)")
            set_pulse(1400)
            time.sleep(2)
            print("  → STOP (1500µs)")
            set_pulse(1500)
            time.sleep(1)
    else:
        # SG90 : 500µs=0°  1500µs=90°  2500µs=180°
        # Test safe : 45°→135° (±45° du centre)
        US_MIN = 1000   # ~45°
        US_MAX = 2000   # ~135°
        STEPS  = 50
        DELAY  = 0.04
        print(f"SG90 — sweep 45°→135° loop (Ctrl+C to stop)")
        set_pulse(1500)  # centre d'abord
        time.sleep(0.5)
        while True:
            for i in range(STEPS + 1):
                set_pulse(US_MIN + i * (US_MAX - US_MIN) / STEPS)
                time.sleep(DELAY)
            for i in range(STEPS, -1, -1):
                set_pulse(US_MIN + i * (US_MAX - US_MIN) / STEPS)
                time.sleep(DELAY)

except KeyboardInterrupt:
    print("\nClean shutdown...")
    stop()
