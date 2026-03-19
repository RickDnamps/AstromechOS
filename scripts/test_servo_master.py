#!/usr/bin/env python3
"""
Test servo Master — PCA9685 @ 0x40, canal 0
Supporte servo STANDARD et servo CONTINU.

Usage: python3 scripts/test_servo_master.py [standard|continu]
Par défaut: continu

Servo standard  : 1000µs=0°  1500µs=90°  2000µs=180°
Servo continu   : 1500µs=STOP  <1500=sens1  >1500=sens2
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
pca = PCA9685(i2c, address=0x40)
pca.frequency = 50
print(f"PCA9685 @ 0x40 OK — mode: {MODE}")

def set_pulse(us):
    pca.channels[0].duty_cycle = us_to_duty(us)

def stop():
    set_pulse(1500)
    time.sleep(0.3)
    pca.deinit()
    print("STOP")

try:
    if MODE == "continu":
        print("Servo continu — lent sens 1 → stop → lent sens 2 → stop (boucle)")
        print("Ctrl+C pour arrêter")
        while True:
            print("  → sens horaire lent (1600µs)")
            set_pulse(1600)
            time.sleep(2)
            print("  → STOP (1500µs)")
            set_pulse(1500)
            time.sleep(1)
            print("  → sens anti-horaire lent (1400µs)")
            set_pulse(1400)
            time.sleep(2)
            print("  → STOP (1500µs)")
            set_pulse(1500)
            time.sleep(1)
    else:
        print("Servo standard — sweep 60°→120° en boucle")
        print("Ctrl+C pour arrêter")
        STEPS = 50
        while True:
            for i in range(STEPS + 1):
                us = 1166 + i * (1666 - 1166) / STEPS  # 60°→120°
                set_pulse(us)
                time.sleep(0.04)
            for i in range(STEPS, -1, -1):
                us = 1166 + i * (1666 - 1166) / STEPS
                set_pulse(us)
                time.sleep(0.04)

except KeyboardInterrupt:
    print("\nArrêt propre...")
    stop()
