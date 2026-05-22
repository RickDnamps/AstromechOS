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
Slave UART Listener.
Reads the UART bus from the Master and dispatches commands.
- H → watchdog feed + ACK
- M → propulsion (VESC)
- D → dome DC motor
- SRV → body servos
- S → audio
- V → version sync
- DISP → RP2040 display
- REBOOT → reboot Slave
"""

import logging
import threading
import time
import traceback
import os
import sys
from collections import deque

import serial

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from shared.uart_protocol import parse_msg, build_msg

log = logging.getLogger(__name__)

MAX_INVALID_CRC_BEFORE_ALERT = 3
_MAX_BUFFER = 4096
_HEALTH_WINDOW_S = 60   # sliding window for UART health calculation


def _cpu_temp() -> float | None:
    try:
        with open('/sys/class/thermal/thermal_zone0/temp') as f:
            return round(int(f.read().strip()) / 1000, 1)
    except Exception:
        return None


def _disk_info() -> dict | None:
    try:
        import os as _os
        st = _os.statvfs('/')
        total = st.f_blocks * st.f_frsize
        free  = st.f_bavail * st.f_frsize
        used  = total - free
        return {
            'used_gb':  round(used  / 1024**3, 1),
            'total_gb': round(total / 1024**3, 1),
            'free_gb':  round(free  / 1024**3, 1),
        }
    except Exception:
        return None


def _mem_info() -> dict | None:
    try:
        info = {}
        with open('/proc/meminfo') as f:
            for line in f:
                k, v = line.split(':', 1)
                info[k.strip()] = int(v.strip().split()[0])
        total     = info.get('MemTotal', 0)
        available = info.get('MemAvailable', 0)
        used      = total - available
        return {
            'used_mb':  round(used / 1024),
            'total_mb': round(total / 1024),
            'free_mb':  round(available / 1024),
        }
    except Exception:
        return None


_cpu_prev: tuple[int, int] | None = None


def _cpu_pct() -> float | None:
    global _cpu_prev
    try:
        with open('/proc/stat') as f:
            parts = f.readline().split()
        vals  = [int(x) for x in parts[1:]]
        idle  = vals[3] + (vals[4] if len(vals) > 4 else 0)
        total = sum(vals)
        if _cpu_prev is None:
            _cpu_prev = (idle, total)
            return None
        d_idle, d_total = idle - _cpu_prev[0], total - _cpu_prev[1]
        _cpu_prev = (idle, total)
        if d_total == 0:
            return 0.0
        return round((1 - d_idle / d_total) * 100, 1)
    except Exception:
        return None


class UARTListener:
    def __init__(self, port: str, baud: int):
        self._port = port
        self._baud = baud
        self._serial: serial.Serial | None = None
        self._running = False
        self._lock = threading.Lock()
        self._callbacks: dict[str, list] = {}
        self._invalid_crc_count = 0
        # UART health — 60s sliding window: (timestamp, is_valid)
        self._health_lock  = threading.Lock()
        self._health_window: deque = deque()

    def setup(self) -> bool:
        try:
            self._serial = serial.Serial(
                self._port, self._baud,
                timeout=0.1,
                exclusive=True,
                rtscts=False,
                dsrdtr=False
            )
            log.info(f"Slave UART opened: {self._port} @ {self._baud}")
            return True
        except serial.SerialException as e:
            log.error(f"Failed to open UART {self._port}: {e}")
            return False

    def start(self) -> None:
        self._running = True
        threading.Thread(target=self._read_loop, name="uart-slave-rx", daemon=True).start()
        log.info("UARTListener started")

    def stop(self) -> None:
        self._running = False
        if self._serial and self._serial.is_open:
            self._serial.close()

    def send(self, msg_type: str, value: str) -> bool:
        """Sends a message to the Master. Thread-safe."""
        msg = build_msg(msg_type, value)
        try:
            with self._lock:
                if self._serial and self._serial.is_open:
                    self._serial.write(msg.encode('utf-8'))
                    return True
        except serial.SerialException as e:
            log.error(f"Slave UART send error: {e}")
        return False

    def register_callback(self, msg_type: str, callback) -> None:
        self._callbacks.setdefault(msg_type, []).append(callback)

    # ------------------------------------------------------------------
    # Internal thread
    # ------------------------------------------------------------------

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
                    # in-flight frame instead of dropping ~350ms of bus data.
                    log.warning(f"Slave UART buffer overflow ({len(buffer)} bytes) — keeping last 256B")
                    buffer = buffer[-256:]
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    self._process_line(line.strip())
            except serial.SerialException as e:
                log.error(f"Slave UART read error: {e}")
                time.sleep(1)
            except Exception as e:
                log.error("Unexpected error in Slave read_loop: %s\n%s",
                          e, traceback.format_exc())
                time.sleep(0.1)

    def get_health_stats(self) -> dict:
        """Returns UART health stats + system vitals (temp, RAM).
        Thread-safe — called from the HTTP health server (port 5001).
        """
        now = time.monotonic()
        cutoff = now - _HEALTH_WINDOW_S
        with self._health_lock:
            while self._health_window and self._health_window[0][0] < cutoff:
                self._health_window.popleft()
            total  = len(self._health_window)
            errors = sum(1 for _, valid in self._health_window if not valid)
        health_pct = round((total - errors) / total * 100, 1) if total > 0 else 100.0
        return {
            'total':      total,
            'errors':     errors,
            'health_pct': health_pct,
            'window_s':   _HEALTH_WINDOW_S,
            'cpu_temp':   _cpu_temp(),
            'cpu_pct':    _cpu_pct(),
            'mem':        _mem_info(),
            'disk':       _disk_info(),
        }


    def _process_line(self, line: str) -> None:
        if not line:
            return
        result = parse_msg(line)

        # UART health — every non-empty line counts as a read attempt
        now = time.monotonic()
        with self._health_lock:
            self._health_window.append((now, result is not None))
            cutoff = now - _HEALTH_WINDOW_S
            while self._health_window and self._health_window[0][0] < cutoff:
                self._health_window.popleft()

        if result is None:
            self._invalid_crc_count += 1
            if self._invalid_crc_count >= MAX_INVALID_CRC_BEFORE_ALERT:
                log.warning(f"Alert: {self._invalid_crc_count} consecutive invalid checksum messages (motor interference?)")
            return

        self._invalid_crc_count = 0
        msg_type, value = result
        log.debug(f"UART Slave RX: {msg_type}={value}")

        # Heartbeat: immediate ACK
        if msg_type == 'H':
            self.send('H', 'OK')

        for cb in self._callbacks.get(msg_type, []):
            try:
                cb(value)
            except Exception as e:
                log.error(f"Slave callback error {msg_type}: {e}")
