"""
Protocole UART partagé Master ↔ Slave.
CRC XOR sur tous les bytes du payload.
Format: TYPE:VALEUR:CRC\n
"""

import logging

MSG_TERMINATOR = "\n"
MSG_SEPARATOR  = ":"
HEARTBEAT_INTERVAL_MS = 200
WATCHDOG_TIMEOUT_MS   = 500
BAUD_RATE = 115200


def calc_crc(payload: str) -> str:
    """Calcule le CRC XOR de tous les bytes du payload. Retourne hex 2 chars."""
    crc = 0
    for byte in payload.encode("utf-8"):
        crc ^= byte
    return format(crc, '02X')


def build_msg(msg_type: str, value: str) -> str:
    """Construit un message avec CRC. Ex: build_msg('M', '50') → 'M:50:7F\n'"""
    payload = f"{msg_type}:{value}"
    return f"{payload}:{calc_crc(payload)}\n"


def parse_msg(raw: str) -> tuple[str, str] | None:
    """
    Parse et valide un message UART avec CRC.
    Retourne (type, value) si CRC valide, None sinon.
    """
    raw = raw.strip()
    if not raw:
        return None
    parts = raw.split(":")
    if len(parts) < 3:
        return None
    *payload_parts, received_crc = parts
    payload = ":".join(payload_parts)
    expected_crc = calc_crc(payload)
    if received_crc != expected_crc:
        logging.warning(f"CRC mismatch: got {received_crc}, expected {expected_crc} for '{payload}'")
        return None
    msg_type = payload_parts[0]
    msg_value = ":".join(payload_parts[1:])
    return (msg_type, msg_value)
