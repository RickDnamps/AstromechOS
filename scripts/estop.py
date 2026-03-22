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
# Arrêt d'urgence servos
# Envoie 1500µs (neutre = STOP pour servo continu) puis coupe PWM
# Master : PCA9685 @ 0x40 via I2C local
# Slave  : PCA9685 @ 0x41 via SSH
import smbus2, time, subprocess

SLAVE = "artoo@r2-slave.local"
MODE1 = 0x00

def stop_pca(bus, addr):
    """Envoie 1500µs sur tous les canaux puis met en sleep."""
    bus.write_byte_data(addr, MODE1, 0x00)
    time.sleep(0.01)
    tick = int((1500 / 20000.0) * 4096)  # 1500µs = neutre
    for ch in range(16):
        base = 0x06 + 4 * ch
        bus.write_byte_data(addr, base,     0x00)
        bus.write_byte_data(addr, base + 1, 0x00)
        bus.write_byte_data(addr, base + 2, tick & 0xFF)
        bus.write_byte_data(addr, base + 3, tick >> 8)
    time.sleep(0.3)
    bus.write_byte_data(addr, MODE1, 0x10)  # sleep

# --- Master : 0x40 ---
try:
    bus = smbus2.SMBus(1)
    stop_pca(bus, 0x40)
    bus.close()
    print("Master PCA9685 @ 0x40 — STOP OK")
except Exception as e:
    print(f"Master PCA9685 @ 0x40 — {e}")

# --- Slave : 0x41 via SSH ---
slave_cmd = (
    "python3 -c '"
    "import smbus2,time;"
    "b=smbus2.SMBus(1);"
    "b.write_byte_data(0x41,0,0);"
    "time.sleep(0.01);"
    "t=int((1500/20000)*4096);"
    "[b.write_byte_data(0x41,6+4*c+i,v) for c in range(16) for i,v in enumerate([0,0,t&0xFF,t>>8])];"
    "time.sleep(0.3);"
    "b.write_byte_data(0x41,0,0x10);"
    "b.close();"
    "print(\"Slave PCA9685 @ 0x41 — STOP OK\")'"
)
result = subprocess.run(
    ["ssh", "-o", "ConnectTimeout=5", SLAVE, slave_cmd],
    capture_output=True, text=True
)
print(result.stdout.strip() if result.stdout else f"Slave — SSH échoué ou hors ligne")

print("Estop terminé")
