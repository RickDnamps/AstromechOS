#!/bin/bash
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
# Emergency servo stop — cut PWM Master (0x40) + Slave (0x41)
REPO="$(cd "$(dirname "$0")/.." && pwd)"
SLAVE=artoo@r2-slave.local

pkill -9 -f test_servo 2>/dev/null
ssh $SLAVE "pkill -9 -f test_servo 2>/dev/null; true"

python3 -c "
import board, busio
from adafruit_pca9685 import PCA9685
pca = PCA9685(busio.I2C(board.SCL, board.SDA), address=0x40)
for ch in pca.channels: ch.duty_cycle = 0
pca.deinit()
print('Master servos OFF')
"

ssh $SLAVE "python3 -c \"
import board, busio
from adafruit_pca9685 import PCA9685
pca = PCA9685(busio.I2C(board.SCL, board.SDA), address=0x41)
for ch in pca.channels: ch.duty_cycle = 0
pca.deinit()
print('Slave servos OFF')
\""
