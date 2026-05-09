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
Master UART Controller.
- Sends heartbeat H:1:CS every 200ms (CS = checksum sum mod 256)
- Reads Slave responses and dispatches via callbacks
- Alerts if 3 consecutive invalid checksums on heartbeat
"""

import logging
import threading
import time
import configparser
import serial
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from shared.uart_protocol import build_msg, parse_msg, HEARTBEAT_INTERVAL_MS

log = logging.getLogger(__name__)

MAX_INVALID_CRC_BEFORE_ALERT = 3
_MAX_BUFFER = 4096


class UARTController:
    def __init__(self, cfg: configparser.ConfigParser):
        self._port = cfg.get('master', 'uart_port')
        self._baud = cfg.getint('master', 'uart_baud')
        self._heartbeat_interval = cfg.getint('master', 'heartbeat_interval_ms') / 1000.0
        self._serial: serial.Serial | None = None
        self._running = False
        self._lock = threading.Lock()
        self._callbacks: dict[str, list] = {}
        self._invalid_crc_count = 0
        self._heartbeat_invalid_crc_count = 0
        # Tracks the wall-clock age of the last heartbeat ACK from the Slave.
        # None until the first ACK arrives. Lets us distinguish "Slave dead"
        # (no ACKs at all) from "Slave alive but TX corrupted" (CRC errors
        # without missing ACKs). Fed by the internal H callback registered
        # in start().
        self._last_hb_ack_t: float | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def setup(self) -> bool:
        try:
            self._serial = serial.Serial(
                self._port, self._baud,
                timeout=0.1,
                exclusive=True,
                rtscts=False,
                dsrdtr=False
            )
            log.info(f"UART opened: {self._port} @ {self._baud}")
            return True
        except serial.SerialException as e:
            log.error(f"Unable to open UART {self._port}: {e}")
            return False

    def start(self) -> None:
        self._running = True
        # Internal HB ACK tracker — registered before any external H callbacks
        # so we always observe ACKs regardless of caller registration order.
        self.register_callback('H', self._note_hb_ack)
        threading.Thread(target=self._heartbeat_loop, name="uart-hb", daemon=True).start()
        threading.Thread(target=self._read_loop, name="uart-rx", daemon=True).start()
        log.info("UARTController started")

    def _note_hb_ack(self, value: str) -> None:
        """Internal — records every H:OK / H:* reply from the Slave."""
        self._last_hb_ack_t = time.monotonic()

    def stop(self) -> None:
        self._running = False
        time.sleep(0.3)
        if self._serial and self._serial.is_open:
            self._serial.close()
        log.info("UARTController stopped")

    def send(self, msg_type: str, value: str) -> bool:
        """Sends a message with CRC. Thread-safe."""
        msg = build_msg(msg_type, value)
        try:
            with self._lock:
                if self._serial and self._serial.is_open:
                    self._serial.write(msg.encode('utf-8'))
                    return True
        except serial.SerialException as e:
            log.error(f"UART send error: {e}")
        return False

    def register_callback(self, msg_type: str, callback) -> None:
        """Registers a callback for a received message type."""
        self._callbacks.setdefault(msg_type, []).append(callback)

    @property
    def crc_errors(self) -> int:
        """Number of consecutive invalid CRC messages since the last valid message."""
        return self._invalid_crc_count

    @property
    def hb_ack_age_ms(self) -> int | None:
        """Milliseconds since the last heartbeat ACK from the Slave, or None
        if no ACK has been received since startup."""
        if self._last_hb_ack_t is None:
            return None
        return int((time.monotonic() - self._last_hb_ack_t) * 1000)

    # ------------------------------------------------------------------
    # Threads internes
    # ------------------------------------------------------------------

    def _heartbeat_loop(self) -> None:
        while self._running:
            start = time.monotonic()
            ok = self.send('H', '1')
            if not ok:
                log.warning("Failed to send heartbeat")
            elapsed = time.monotonic() - start
            sleep_time = self._heartbeat_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def _read_loop(self) -> None:
        buffer = ""
        while self._running:
            try:
                if not self._serial or not self._serial.is_open:
                    time.sleep(0.1)
                    continue
                data = self._serial.read(256)
                if not data:
                    continue
                buffer += data.decode('utf-8', errors='replace')
                if len(buffer) > _MAX_BUFFER:
                    # Keep the trailing 256 bytes — preserves the start of any
                    # in-flight frame instead of dropping ~350ms of bus data
                    # (which would silently swallow heartbeats and commands).
                    log.warning(f"Buffer UART overflow ({len(buffer)} bytes) — keeping last 256B")
                    buffer = buffer[-256:]
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    self._process_line(line)
            except serial.SerialException as e:
                log.error(f"UART read error: {e}")
                time.sleep(1)
            except Exception as e:
                log.error(f"Unexpected error in read_loop: {e}")

    def _process_line(self, line: str) -> None:
        result = parse_msg(line)
        if result is None:
            self._invalid_crc_count += 1
            # Invalid heartbeat checksum = noisy bus (motor interference / Tobsun)
            if line.startswith('H:'):
                self._heartbeat_invalid_crc_count += 1
                if self._heartbeat_invalid_crc_count >= MAX_INVALID_CRC_BEFORE_ALERT:
                    log.warning(
                        f"Noisy UART bus: {self._heartbeat_invalid_crc_count} "
                        "consecutive invalid heartbeat checksums"
                    )
            if self._invalid_crc_count >= MAX_INVALID_CRC_BEFORE_ALERT:
                log.warning(f"Alert: {self._invalid_crc_count} consecutive invalid checksum messages")
            return

        self._invalid_crc_count = 0
        self._heartbeat_invalid_crc_count = 0
        msg_type, value = result
        log.debug(f"UART RX: {msg_type}={value}")

        for cb in self._callbacks.get(msg_type, []):
            try:
                cb(value)
            except Exception as e:
                log.error(f"Callback error {msg_type}: {e}")
