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
VESC CAN Bus Utilities.
Implémente COMM_FORWARD_CAN pour atteindre les VESCs connectés via CAN bus.

Architecture:
  Pi → USB → VESC 1 (CAN ID configurable) → CAN H/L → VESC 2 (CAN ID configurable)

VESC 1 acts as USB↔CAN bridge. All commands to VESC 2 go through it.

⚠️ IMPORTANT: Never enable "Multiple ESC over CAN" — it would synchronize
   both motors and prevent differential steering.
   Each VESC must receive INDEPENDENT commands.
"""

import struct
import time
import logging

log = logging.getLogger(__name__)

# VESC command IDs (firmware source: commands.h)
COMM_FW_VERSION   = 0
COMM_GET_VALUES   = 4
COMM_SET_DUTY     = 5
COMM_SET_RPM      = 8
COMM_GET_APP_CONF = 14
COMM_SET_APP_CONF = 15
COMM_TERMINAL_CMD = 16
COMM_REBOOT       = 29
COMM_FORWARD_CAN  = 33

# Minimum length of a COMM_GET_VALUES reply payload that contains every
# field we read — temp_fet, current, duty, rpm, v_in, fault.
# Layout (Flipsky Mini V6.7 firmware v6.05, see commands.c::send_values):
#   1  byte   COMM_GET_VALUES marker
#   2  bytes  temp_fet (×10)
#   2  bytes  temp_motor               ← skipped
#   4  bytes  avg_motor_current (×100)
#   4  bytes  avg_input_current        ← skipped
#   8  bytes  id, iq                   ← skipped
#   2  bytes  duty (×1000)
#   4  bytes  rpm
#   2  bytes  v_in (×10)
#  24  bytes  amp_h, amp_h_charge, watt_h, watt_h_charge, tachometer×2 ← skipped
#   1  byte   fault                    ← @ index 53
# Total minimum: 54 bytes. Newer firmware appends fields AFTER fault
# (pid_pos, controller_id, …) which is fine — we just slice less than the
# full payload. If a future firmware reorders fields BEFORE fault, the
# parser will read garbage; the safe response in that case is to bump
# this constant and re-derive the offsets from commands.c.
_MIN_GET_VALUES_PAYLOAD_LEN = 54


# ------------------------------------------------------------------
# Packet building
# ------------------------------------------------------------------

def _crc16(data: bytes) -> int:
    """CRC-16/CCITT-FALSE — identique au firmware VESC."""
    crc = 0
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def _build_packet(payload: bytes) -> bytes:
    """Encapsule un payload dans un paquet VESC (start byte + length + CRC + stop byte)."""
    length = len(payload)
    crc = _crc16(payload)
    crc_bytes = bytes([crc >> 8, crc & 0xFF])
    if length < 256:
        return bytes([0x02, length]) + payload + crc_bytes + bytes([0x03])
    return bytes([0x03, length >> 8, length & 0xFF]) + payload + crc_bytes + bytes([0x03])


def _can_forward_packet(can_id: int, inner_payload: bytes) -> bytes:
    """
    Wraps inner_payload dans une enveloppe COMM_FORWARD_CAN.
    VESC 1 reçoit ce paquet et le forward au VESC avec l'ID can_id via CAN bus.
    """
    payload = bytes([COMM_FORWARD_CAN, can_id]) + inner_payload
    return _build_packet(payload)


def _extract_payload(raw: bytes) -> bytes | None:
    """Extrait le payload d'un paquet VESC brut. Retourne None si invalide."""
    if len(raw) < 5:
        return None
    if raw[0] == 0x02:
        length = raw[1]
        if len(raw) < length + 4:
            return None
        payload = raw[2:2 + length]
        crc = (raw[2 + length] << 8) | raw[3 + length]
        if _crc16(payload) != crc:
            return None
        return payload
    if raw[0] == 0x03:
        length = (raw[1] << 8) | raw[2]
        if len(raw) < length + 5:
            return None
        payload = raw[3:3 + length]
        crc = (raw[3 + length] << 8) | raw[4 + length]
        if _crc16(payload) != crc:
            return None
        return payload
    return None


# ------------------------------------------------------------------
# CAN operations
# ------------------------------------------------------------------

def ping_can_id(ser, can_id: int, timeout: float = 0.1) -> bool:
    """
    Envoie GetFwVersion au CAN ID et vérifie si une réponse arrive.
    Retourne True si le VESC existe sur le bus.
    """
    pkt = _can_forward_packet(can_id, bytes([COMM_FW_VERSION]))
    try:
        ser.reset_input_buffer()
        ser.write(pkt)
        time.sleep(timeout)
        data = ser.read(ser.in_waiting or 20)
        return len(data) > 3
    except Exception as e:
        log.debug(f"ping_can CAN ID {can_id}: {e}")
        return False


def scan_can_bus(ser, id_range: range = range(0, 11)) -> list[int]:
    """
    Scanne les CAN IDs et retourne la liste des IDs qui répondent.
    Ignore l'ID 0 si c'est le VESC USB lui-même (évite l'auto-forward).
    """
    found = []
    for can_id in id_range:
        if ping_can_id(ser, can_id):
            log.info(f"VESC trouvé sur CAN ID {can_id}")
            found.append(can_id)
        time.sleep(0.02)  # petit délai entre les pings
    return found


def get_fw_version_can(ser, can_id: int) -> dict | None:
    """Lit la version firmware d'un VESC via CAN forwarding."""
    pkt = _can_forward_packet(can_id, bytes([COMM_FW_VERSION]))
    try:
        ser.reset_input_buffer()
        ser.write(pkt)
        time.sleep(0.1)
        raw = ser.read(ser.in_waiting or 50)
        payload = _extract_payload(raw)
        if payload is None or len(payload) < 3 or payload[0] != COMM_FW_VERSION:
            return None
        major = payload[1]
        minor = payload[2]
        return {'fw': f'{major}.{minor}', 'can_id': can_id}
    except Exception as e:
        log.debug(f"get_fw_version_can CAN ID {can_id}: {e}")
        return None


def get_values_direct(ser) -> dict | None:
    """
    Reads MC_VALUES from the USB-connected VESC (no CAN forwarding).
    Native implementation — does not require pyvesc.
    """
    pkt = _build_packet(bytes([COMM_GET_VALUES]))
    try:
        ser.reset_input_buffer()
        ser.write(pkt)
        time.sleep(0.06)
        raw = ser.read(ser.in_waiting or 100)
        if not raw:
            return None
        payload = _extract_payload(raw)
        if payload is None or len(payload) < _MIN_GET_VALUES_PAYLOAD_LEN or payload[0] != COMM_GET_VALUES:
            return None
        p = 1
        temp_fet = struct.unpack_from('>H', payload, p)[0] / 10.0;  p += 2
        p += 2   # temp_motor
        curr_m   = struct.unpack_from('>i', payload, p)[0] / 100.0; p += 4
        p += 4   # curr_in
        p += 8   # id, iq
        duty     = struct.unpack_from('>h', payload, p)[0] / 1000.0; p += 2
        rpm      = struct.unpack_from('>i', payload, p)[0];           p += 4
        v_in     = struct.unpack_from('>H', payload, p)[0] / 10.0;    p += 2
        p += 24  # amp_hours×2 (8B) + watt_hours×2 (8B) + tachometer×2 (8B)
        fault    = payload[p] if p < len(payload) else 0
        return {
            'v_in':    round(v_in, 2),
            'temp':    round(temp_fet, 1),
            'current': round(curr_m, 2),
            'rpm':     int(rpm),
            'duty':    round(duty, 3),
            'fault':   int(fault),
        }
    except Exception as e:
        log.debug(f"get_values_direct: {e}")
        return None


def get_values_can(ser, can_id: int) -> dict | None:
    """
    Reads MC_VALUES from a VESC reached via CAN forwarding through the
    USB-connected VESC. Native parser — does NOT use pyvesc (which conflicts
    with PyCRC/pycrc on Python 3.13 — see CLAUDE.md gotchas).
    """
    pkt = _can_forward_packet(can_id, bytes([COMM_GET_VALUES]))
    try:
        ser.reset_input_buffer()
        ser.write(pkt)
        time.sleep(0.06)
        raw = ser.read(ser.in_waiting or 100)
        if not raw:
            return None

        payload = _extract_payload(raw)
        if payload is None or len(payload) < _MIN_GET_VALUES_PAYLOAD_LEN or payload[0] != COMM_GET_VALUES:
            return None
        p = 1
        temp_fet = struct.unpack_from('>H', payload, p)[0] / 10.0;  p += 2
        p += 2   # temp_motor
        curr_m   = struct.unpack_from('>i', payload, p)[0] / 100.0; p += 4
        p += 4   # curr_in
        p += 8   # id, iq
        duty     = struct.unpack_from('>h', payload, p)[0] / 1000.0; p += 2
        rpm      = struct.unpack_from('>i', payload, p)[0];          p += 4
        v_in     = struct.unpack_from('>H', payload, p)[0] / 10.0;   p += 2
        p += 24  # amp_hours×2 (8B) + watt_hours×2 (8B) + tachometer×2 (8B)
        fault    = payload[p] if p < len(payload) else 0
        return {
            'v_in':    round(v_in, 2),
            'temp':    round(temp_fet, 1),
            'current': round(curr_m, 2),
            'rpm':     int(rpm),
            'duty':    round(duty, 3),
            'fault':   int(fault),
        }
    except Exception as e:
        log.debug(f"get_values_can CAN ID {can_id}: {e}")
        return None


def check_multi_esc(ser, can_id: int) -> bool | None:
    """
    Check if 'Multiple ESC over CAN' is enabled (DANGEROUS).
    If True → both motors receive the same command → cannot steer.
    Returns True=enabled(danger), False=disabled(ok), None=unknown.
    Note: requires full AppConf read — future implementation.
    """
    # TODO: implémenter via COMM_GET_APP_CONF + désérialisation AppConf
    # Pour l'instant, retourner None (inconnu) — avertissement affiché dans le dashboard
    log.debug(f"check_multi_esc CAN ID {can_id}: non implémenté (AppConf requis)")
    return None


def set_rpm_direct(ser, erpm: int) -> None:
    """Sends COMM_SET_RPM directly to the USB-connected VESC."""
    pkt = _build_packet(bytes([COMM_SET_RPM]) + struct.pack('>i', int(erpm)))
    ser.write(pkt)


def set_duty_direct(ser, duty: float) -> None:
    """
    Sends COMM_SET_DUTY directly to the USB-connected VESC.
    duty: -1.0 to +1.0 (mapped to -100000 to +100000 per VESC protocol).
    Useful for bench testing without a motor — duty is directly visible in telemetry.
    """
    val = int(duty * 100000)
    pkt = _build_packet(bytes([COMM_SET_DUTY]) + struct.pack('>i', val))
    ser.write(pkt)


def set_duty_can(ser, can_id: int, duty: float) -> None:
    """Sends COMM_SET_DUTY to a VESC via CAN forwarding."""
    val = int(duty * 100000)
    inner = bytes([COMM_SET_DUTY]) + struct.pack('>i', val)
    ser.write(_can_forward_packet(can_id, inner))


def set_rpm_can(ser, can_id: int, erpm: int) -> None:
    """
    Sends a SetRPM (ERPM) command to a VESC via CAN forwarding.
    VESC 1 relays the inner payload to can_id over the CAN bus.

    Args:
        ser     : open serial.Serial connected to VESC 1 (USB)
        can_id  : target CAN ID (e.g. 2 for Slave VESC)
        erpm    : electrical RPM — negative = reverse
    """
    inner = bytes([COMM_SET_RPM]) + struct.pack('>i', int(erpm))
    pkt = _can_forward_packet(can_id, inner)
    ser.write(pkt)




def set_can_id(ser_local, current_can_id: int, new_can_id: int) -> bool:
    """
    Change le CAN ID d'un VESC distant via CAN forwarding + SetAppConf.
    ⚠️  Nécessite la désérialisation complète de AppConf — à implémenter
        lorsque les VESCs seront disponibles pour tester.
    Pour l'instant: utiliser VESC Tool pour cette opération.
    """
    # TODO: implémenter GetAppConf → modifier controller_id → SetAppConf
    log.warning(f"set_can_id: non implémenté — utiliser VESC Tool pour changer CAN ID {current_can_id} → {new_can_id}")
    return False
