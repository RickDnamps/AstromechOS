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
"""
Slave VESC Driver — Phase 2.
Receives M: commands from the Master and drives the propulsion VESCs via pyvesc.
Sends TL:/TR: telemetry to the Master every 200ms.

UART format received:
  M:LEFT,RIGHT:CRC      → differential drive (float [-1.0…+1.0])
  VCFG:scale:0.8:CRC   → power scale (0.1-1.0) — reduces max duty cycle
  VINV:L:CRC            → reverses left motor direction (software)
  VINV:R:CRC            → reverses right motor direction (software)
  CANSCAN:start:CRC     → starts a CAN bus scan, replies CANFOUND:id1,id2

UART format sent (Slave → Master):
  TL:v_in:temp:curr:rpm:duty:fault:CRC  → left VESC telemetry
  TR:v_in:temp:curr:rpm:duty:fault:CRC  → right VESC telemetry

VESC connection:
  Dual USB mode (default):
    Left VESC  : /dev/ttyACM0
    Right VESC : /dev/ttyACM1

Phase 2 activation:
  1. Connect VESCs via USB
  2. Uncomment the import in slave/main.py
  3. Call vesc.setup(uart) in main()
  4. uart.register_callback('M',    vesc.handle_uart)
  5. uart.register_callback('VCFG', vesc.handle_config_uart)
  6. uart.register_callback('VINV', vesc.handle_invert_uart)
"""

import logging
import threading
import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.base_driver import BaseDriver

log = logging.getLogger(__name__)

VESC_PORT_LEFT  = "/dev/ttyACM0"
VESC_PORT_RIGHT = "/dev/ttyACM1"
VESC_BAUD       = 115200

# Hardware safety limit — never exceed
HARDWARE_SPEED_LIMIT = 0.85

# Telemetry interval (seconds)
TELEM_INTERVAL = 0.2   # 5 Hz


class VescDriver(BaseDriver):
    """
    VESC driver for R2-D2 differential drive.
    - Controls left/right motors via pyvesc
    - GET_VALUES telemetry sent to Master via UART every 200ms
    - Power scale and invert configurable from the dashboard
    """

    def __init__(self, port_left: str = VESC_PORT_LEFT,
                 port_right: str = VESC_PORT_RIGHT):
        self._port_left   = port_left
        self._port_right  = port_right
        self._serial_left  = None
        self._serial_right = None
        self._pyvesc       = None
        self._ready        = False
        self._uart         = None          # UARTListener reference for telemetry
        self._lock         = threading.Lock()

        # Config adjustable from the dashboard
        self._power_scale   = 1.0          # 0.1 – 1.0 — reduces max duty
        self._invert_left   = False
        self._invert_right  = False

        self._telem_thread: threading.Thread | None = None
        self._running = False

    # ------------------------------------------------------------------
    # BaseDriver
    # ------------------------------------------------------------------

    def setup(self, uart=None) -> bool:
        """
        Initializes VESC connections.
        uart : UARTListener — optional, enables telemetry sending to Master.
        """
        self._uart = uart
        try:
            import pyvesc
            import serial as _serial

            self._serial_left  = _serial.Serial(self._port_left,  VESC_BAUD, timeout=0.05)
            self._serial_right = _serial.Serial(self._port_right, VESC_BAUD, timeout=0.05)
            self._pyvesc = pyvesc
            self._ready  = True
            log.info(f"VescDriver ready: L={self._port_left} R={self._port_right}")

            # Start telemetry loop
            self._running = True
            self._telem_thread = threading.Thread(
                target=self._telem_loop, name='vesc-telem', daemon=True
            )
            self._telem_thread.start()
            return True

        except ImportError:
            log.error("pyvesc not installed — sudo pip install pyvesc")
            return False
        except Exception as e:
            log.error(f"VESC init error: {e}")
            return False

    def shutdown(self) -> None:
        self._running = False
        self._stop_motors()
        if self._serial_left  and self._serial_left.is_open:
            self._serial_left.close()
        if self._serial_right and self._serial_right.is_open:
            self._serial_right.close()
        self._ready = False
        log.info("VescDriver stopped")

    def is_ready(self) -> bool:
        return self._ready

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def drive(self, left: float, right: float) -> None:
        """Differential drive command: left/right ∈ [-1.0, +1.0]."""
        if not self._ready:
            return
        # Apply power scale + hardware limits
        lim = HARDWARE_SPEED_LIMIT * self._power_scale
        left  = max(-lim, min(lim, left))
        right = max(-lim, min(lim, right))
        # Software inversion if configured
        if self._invert_left:  left  = -left
        if self._invert_right: right = -right
        with self._lock:
            self._set_duty(self._serial_left,  left)
            self._set_duty(self._serial_right, right)

    def stop(self) -> None:
        """Emergency stop — cuts both VESCs."""
        self._stop_motors()

    # ------------------------------------------------------------------
    # UART Callbacks (called by uart_listener)
    # ------------------------------------------------------------------

    def handle_uart(self, value: str) -> None:
        """M:LEFT,RIGHT — propulsion command."""
        try:
            parts = value.split(',')
            self.drive(float(parts[0]), float(parts[1]))
        except (ValueError, IndexError) as e:
            log.error(f"Invalid M: message {value!r}: {e}")

    def handle_config_uart(self, value: str) -> None:
        """
        VCFG:param:val — configuration from the dashboard.
        Supported parameters:
          scale:0.8   → power scale (0.1-1.0)
        """
        try:
            parts = value.split(':')
            param, val = parts[0], parts[1]
            if param == 'scale':
                self._power_scale = max(0.1, min(1.0, float(val)))
                log.info(f"VESC power scale: {self._power_scale:.2f}")
            else:
                log.warning(f"Unknown VCFG parameter: {param!r}")
        except (ValueError, IndexError) as e:
            log.error(f"Invalid VCFG message {value!r}: {e}")

    def handle_invert_uart(self, value: str) -> None:
        """VINV:L or VINV:R — reverses a motor direction."""
        side = value.strip().upper()
        if side == 'L':
            self._invert_left = not self._invert_left
            log.info(f"Invert left: {self._invert_left}")
        elif side == 'R':
            self._invert_right = not self._invert_right
            log.info(f"Invert right: {self._invert_right}")
        else:
            log.warning(f"VINV: unknown side {value!r}")

    def handle_can_scan_uart(self, value: str) -> None:
        """
        CANSCAN:start — scans the CAN bus via VESC 1 USB and sends CANFOUND: to Master.
        Launched in a thread to avoid blocking the UART listener.
        """
        if not self._ready or not self._serial_left:
            log.warning("CAN scan requested but left VESC not ready")
            if self._uart:
                self._uart.send('CANFOUND', 'ERR')
            return

        def _do_scan():
            try:
                from slave.drivers.vesc_can import scan_can_bus
                log.info("Starting CAN bus scan...")
                with self._lock:
                    found = scan_can_bus(self._serial_left)
                ids_str = ','.join(str(i) for i in found) if found else ''
                log.info(f"CAN scan complete: {found}")
                if self._uart:
                    self._uart.send('CANFOUND', ids_str)
            except Exception as e:
                log.error(f"CAN scan failed: {e}")
                if self._uart:
                    self._uart.send('CANFOUND', 'ERR')

        threading.Thread(target=_do_scan, name='can-scan', daemon=True).start()

    # ------------------------------------------------------------------
    # Telemetry
    # ------------------------------------------------------------------

    def _get_values(self, ser) -> dict | None:
        """Reads MC_VALUES from a VESC via pyvesc. Returns dict or None."""
        try:
            req = self._pyvesc.encode_request(self._pyvesc.GetValues)
            ser.reset_input_buffer()
            ser.write(req)
            time.sleep(0.04)   # wait for the response
            raw = ser.read(ser.in_waiting or 100)
            if not raw:
                return None
            msg, _ = self._pyvesc.decode(raw)
            if msg is None:
                return None
            return {
                'v_in':    round(float(msg.v_in),              2),
                'temp':    round(float(msg.temp_fet),          1),
                'current': round(float(msg.avg_motor_current), 2),
                'rpm':     int(msg.rpm),
                'duty':    round(float(msg.duty_cycle_now),    3),
                'fault':   int(msg.fault_code),
            }
        except Exception as e:
            log.debug(f"VESC telemetry unavailable: {e}")
            return None

    def _telem_loop(self) -> None:
        """Reads telemetry from both VESCs and sends it to Master via UART."""
        while self._running:
            if self._ready and self._uart:
                with self._lock:
                    vl = self._get_values(self._serial_left)
                    vr = self._get_values(self._serial_right)
                if vl:
                    self._uart.send('TL',
                        f"{vl['v_in']}:{vl['temp']}:{vl['current']}"
                        f":{vl['rpm']}:{vl['duty']}:{vl['fault']}"
                    )
                if vr:
                    self._uart.send('TR',
                        f"{vr['v_in']}:{vr['temp']}:{vr['current']}"
                        f":{vr['rpm']}:{vr['duty']}:{vr['fault']}"
                    )
            time.sleep(TELEM_INTERVAL)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _set_duty(self, ser, duty: float) -> None:
        try:
            msg = self._pyvesc.encode(self._pyvesc.SetDutyCycle(duty))
            ser.write(msg)
        except Exception as e:
            log.error(f"VESC command error: {e}")

    def _stop_motors(self) -> None:
        if not self._ready:
            return
        try:
            with self._lock:
                self._set_duty(self._serial_left,  0.0)
                self._set_duty(self._serial_right, 0.0)
        except Exception:
            pass
