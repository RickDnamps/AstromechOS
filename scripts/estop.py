#!/usr/bin/env python3
# Arrêt d'urgence servos
# Envoie 1500µs (neutre = STOP pour servo continu) puis coupe PWM
import smbus2, time

ADDRESSES = [0x40, 0x41]
bus = smbus2.SMBus(1)

MODE1    = 0x00
PRESCALE = 0xFE
LED0_ON_L  = 0x06  # registre canal 0

def set_pulse_us(bus, addr, channel, pulse_us):
    """Envoie un pulse en µs sur un canal PCA9685 (50Hz)."""
    tick = int((pulse_us / 20000.0) * 4096)
    base = LED0_ON_L + 4 * channel
    bus.write_byte_data(addr, base,     0x00)
    bus.write_byte_data(addr, base + 1, 0x00)
    bus.write_byte_data(addr, base + 2, tick & 0xFF)
    bus.write_byte_data(addr, base + 3, tick >> 8)

for addr in ADDRESSES:
    try:
        # S'assurer que le chip est éveillé
        bus.write_byte_data(addr, MODE1, 0x00)
        time.sleep(0.01)
        # Envoyer 1500µs sur tous les canaux (neutre = stop servo continu)
        for ch in range(16):
            set_pulse_us(bus, addr, ch, 1500)
        time.sleep(0.3)
        # Mettre en sleep (coupe PWM)
        bus.write_byte_data(addr, MODE1, 0x10)
        print(f"PCA9685 @ 0x{addr:02X} — neutre envoyé + SLEEP OK")
    except Exception as e:
        print(f"PCA9685 @ 0x{addr:02X} — {e}")

bus.close()
print("Tous les servos arrêtés")
