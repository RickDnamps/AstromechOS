#!/usr/bin/env python3
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
# Emergency stop — halts VESCs and dome motor via UART.
# Servos are NOT touched: they hold their current position.
# This script is the guaranteed low-level fallback when the
# Flask process is unavailable.
import serial, time

UART_PORT = '/dev/ttyAMA0'
BAUD      = 115200

def crc(payload: str) -> str:
    return format(sum(payload.encode()) % 256, '02X')

def send(ser, msg_type: str, value: str) -> None:
    payload = f"{msg_type}:{value}"
    ser.write(f"{payload}:{crc(payload)}\n".encode())

try:
    ser = serial.Serial(UART_PORT, BAUD, timeout=1)
    time.sleep(0.05)
    send(ser, 'M', '0.0,0.0')   # stop VESCs
    send(ser, 'D', '0.0')        # stop dome motor
    ser.close()
    print("Estop UART — VESCs + dome stopped, servos held")
except Exception as e:
    print(f"Estop UART — {e}")

print("Estop complete")
