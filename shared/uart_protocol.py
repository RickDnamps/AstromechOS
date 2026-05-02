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
Shared UART protocol Master <-> Slave.
Checksum = arithmetic sum of all payload bytes, modulo 256.
Format: TYPE:VALUE:CS\n  (CS = 2 hex chars, e.g. "B3")

Algorithm: (sum(bytes) + len(bytes)) % 256

Why not XOR?
  - XOR: two identical bytes cancel each other out → blind to periodic bursts
    (24V motors + Tobsun generate repetitive pulses)

Why sum + len instead of just sum?
  - sum alone: a null byte (0x00) contributes 0 → unchanged if inserted in the frame
    → a UART BREAK condition (slipring) injects 0x00 → would pass without len
  - sum + len: any inserted byte changes the length → checksum changes
  - Remaining limitation: byte-swap of two bytes with the same sum (e.g. 0xEE<->0xFF)
    → collision. Acceptable for random noise — a polynomial CRC would eliminate this.
"""

import logging

MSG_TERMINATOR = "\n"
MSG_SEPARATOR  = ":"
HEARTBEAT_INTERVAL_MS = 200
WATCHDOG_TIMEOUT_MS   = 500
BAUD_RATE = 115200


def calc_crc(payload: str) -> str:
    """
    Computes the checksum: (sum of bytes + length) mod 256.
    Returns 2 uppercase hex characters, e.g. 'B6'.
    +len(): a null byte inserted changes the length → checksum changes.
    Named 'calc_crc' for compatibility with the rest of the codebase.
    """
    data = payload.encode('utf-8')
    return format((sum(data) + len(data)) % 256, '02X')


def build_msg(msg_type: str, value: str) -> str:
    """Builds a message with checksum. E.g. build_msg('H', '1') → 'H:1:B3\\n'"""
    payload = f"{msg_type}:{value}"
    return f"{payload}:{calc_crc(payload)}\n"


def parse_msg(raw: str) -> tuple[str, str] | None:
    """
    Parses and validates a UART message with checksum.
    Returns (type, value) if checksum is valid, None otherwise (packet discarded).
    The last ':'-separated segment is always the checksum.
    """
    raw = raw.strip()
    if not raw:
        return None
    parts = raw.split(":")
    if len(parts) < 3:
        return None
    *payload_parts, received_cs = parts
    payload = ":".join(payload_parts)
    expected_cs = calc_crc(payload)
    if received_cs != expected_cs:
        logging.warning(f"Checksum mismatch: got {received_cs}, expected {expected_cs} for '{payload}'")
        return None
    msg_type = payload_parts[0]
    msg_value = ":".join(payload_parts[1:])
    return (msg_type, msg_value)
