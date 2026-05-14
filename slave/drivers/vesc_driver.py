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
Slave VESC Driver — Phase 2.
Receives M: commands from the Master and drives the propulsion VESCs.
Sends TL:/TR: telemetry to the Master every 200ms.

Hardware topology (Flipsky Mini V6.7, firmware v6.05, Hardware 60):
  Pi → USB → VESC ID 1 (Master VESC) → CAN H/L → VESC ID 2 (Slave VESC)
  Single serial port: /dev/ttyACM0

  Commands to VESC ID 1 : sent directly via USB (pyvesc SetRPM)
  Commands to VESC ID 2 : wrapped with COMM_FORWARD_CAN (vesc_can.set_rpm_can)

  ⚠️  "Multiple ESC over CAN" must be DISABLED on both VESCs — each motor
      must receive independent ERPM commands for differential steering.

UART format received:
  M:LEFT,RIGHT:CRC      → differential drive (float [-1.0…+1.0])
  VCFG:scale:0.8:CRC   → power scale (0.1-1.0) — scales max ERPM
  VINV:L:CRC            → reverses left motor direction (software)
  VINV:R:CRC            → reverses right motor direction (software)
  CANSCAN:start:CRC     → scans CAN bus via VESC 1, replies CANFOUND:id1,id2

UART format sent (Slave → Master):
  TL:v_in:temp:curr:rpm:duty:fault:CRC  → left VESC telemetry  (VESC ID 1, USB)
  TR:v_in:temp:curr:rpm:duty:fault:CRC  → right VESC telemetry (VESC ID 2, CAN)

Phase 2 activation:
  1. Connect VESC ID 1 via USB (ttyACM0), VESC ID 2 via CAN bus only
  2. Uncomment the import in slave/main.py
  3. Call vesc.setup(uart) in main()
  4. uart.register_callback('M',       vesc.handle_uart)
  5. uart.register_callback('VCFG',    vesc.handle_config_uart)
  6. uart.register_callback('VINV',    vesc.handle_invert_uart)
  7. uart.register_callback('CANSCAN', vesc.handle_can_scan_uart)
"""

import logging
import threading
import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.base_driver import BaseDriver
from slave.drivers.vesc_can import (
    set_rpm_can, set_rpm_direct,
    set_duty_direct, set_duty_can,
    get_values_direct, get_values_can,
)

log = logging.getLogger(__name__)

# USB ports to try in order — VESC takes the first available ACM
# that is not already claimed by the RP2040 display driver.
VESC_PORTS = ["/dev/ttyACM0", "/dev/ttyACM1", "/dev/ttyACM2"]
VESC_BAUD  = 115200

# CAN IDs — validated hardware configuration (Flipsky Mini V6.7, fw v6.05)
VESC_ID_USB = 1   # Master VESC — Pi connected via USB
VESC_ID_CAN = 2   # Slave VESC  — reached via CAN forwarding through VESC 1

# Max electrical RPM — scale to [-MAX_ERPM, +MAX_ERPM] from [-1.0, +1.0]
# Tune for your motors (pole pairs × max mechanical RPM).
# Conservative default: 50 000 ERPM.  Override via VCFG:erpm:<value>
MAX_ERPM = 50_000

# Hardware safety limit applied on top of power_scale
HARDWARE_SPEED_LIMIT = 0.85

# Telemetry interval (seconds)
TELEM_INTERVAL = 0.2   # 5 Hz


class VescDriver(BaseDriver):
    """
    VESC driver for robot differential drive.

    Topology: single USB to VESC ID 1, CAN forwarding to VESC ID 2.
    - Controls left/right motors via ERPM commands (closed-loop speed control)
    - Left motor  → VESC ID 1 via USB  (set_rpm_direct)
    - Right motor → VESC ID 2 via CAN  (set_rpm_can with COMM_FORWARD_CAN)
    - GET_VALUES telemetry sent to Master via UART every 200ms
    - Power scale and invert configurable from the dashboard
    """

    def __init__(self, ports: list[str] | None = None):
        self._ports   = ports if ports is not None else VESC_PORTS
        self._port    = None   # resolved at setup()
        self._serial  = None
        self._ready   = False
        self._uart    = None          # UARTListener reference for telemetry
        self._lock    = threading.Lock()

        # Config (adjustable at runtime)
        self._power_scale = 1.0        # 0.1 – 1.0 — scales max ERPM / duty
        self._max_erpm    = MAX_ERPM   # adjustable via VCFG:erpm:<value>
        self._invert_left  = False
        self._invert_right = False
        self._duty_mode    = False     # VCFG:mode:duty → use COMM_SET_DUTY (bench testing)

        self._telem_thread: threading.Thread | None = None
        self._running = False

        # Paired-side liveness: when right VESC (CAN ID 2) goes silent for
        # _FAIL_THRESHOLD consecutive reads while the left side keeps responding,
        # the Slave refuses further drive commands and emits synthetic TR
        # telemetry with fault=99 so Master sees the failure immediately
        # (instead of waiting for the 2s staleness check).
        self._can_lost = False
        self._SYNTHETIC_FAULT_CAN_LOST = 99

    # ------------------------------------------------------------------
    # BaseDriver
    # ------------------------------------------------------------------

    def setup(self, uart=None) -> bool:
        """
        Opens the single USB serial port to VESC ID 1.
        uart : UARTListener — optional, enables telemetry forwarding to Master.

        Returns True if the driver is alive — either connected NOW, or
        running its reconnect loop ready to pick the VESC up as soon as
        it appears. Returns False only on hard initialisation errors
        (e.g. pyserial missing).

        Previously: if the initial port-open failed (VESC USB not yet
        enumerated by the kernel, brief power glitch during boot, etc.),
        setup() returned False, the telem thread was never started, and
        the built-in 2s reconnect loop never ran. Propulsion stayed
        disabled until the next slave reboot — even after the VESC USB
        was plugged in and powered. Bug reported 2026-05-14.

        Fix: always start the telem thread. The reconnect loop runs
        every 2s when _ready=False and brings the driver online as soon
        as a port responds. drive() gates on _ready internally so safety
        is preserved during the degraded window.
        """
        self._uart = uart
        try:
            import serial as _serial

            opened = False
            for port in self._ports:
                try:
                    self._serial = _serial.Serial(port, VESC_BAUD, timeout=0.05)
                    self._port   = port
                    opened = True
                    break
                except _serial.SerialException:
                    continue

            if opened:
                self._ready = True
                log.info(
                    f"VescDriver ready: port={self._port}  "
                    f"USB_ID={VESC_ID_USB}  CAN_ID={VESC_ID_CAN}  "
                    f"max_erpm={self._max_erpm}"
                )
            else:
                self._ready = False
                log.warning(
                    "VescDriver: no VESC found on ports %s at startup — "
                    "telem loop will keep retrying every 2s",
                    self._ports,
                )

            # Start telemetry / reconnect loop unconditionally.
            self._running = True
            self._telem_thread = threading.Thread(
                target=self._telem_loop, name='vesc-telem', daemon=True
            )
            self._telem_thread.start()
            return True

        except Exception as e:
            log.error(f"VESC init error: {e}")
            return False

    def shutdown(self) -> None:
        self._running = False
        self._stop_motors()
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._ready = False
        log.info("VescDriver stopped")

    def is_ready(self) -> bool:
        return self._ready

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def drive(self, left: float, right: float) -> None:
        """
        Differential drive command: left/right ∈ [-1.0, +1.0].

        Converts normalised speed to ERPM then sends both commands
        back-to-back within the same lock acquisition (synchronous):
          - Left  → VESC ID 1 via USB  (direct SetRPM)
          - Right → VESC ID 2 via CAN  (COMM_FORWARD_CAN + SetRPM)

        Paired-side guard: if the right VESC (CAN) is unreachable, refuse the
        command outright instead of running on one wheel.
        """
        if not self._ready:
            return
        if self._can_lost:
            # One wheel only would spin the robot in place — refuse the command.
            # The Slave has already stopped the motors and is emitting synthetic
            # TR fault telemetry; Master's safety gate will block further input.
            return
        # Multiplicative scaling: power_scale is a true ceiling multiplier.
        # Drive speed × power_scale = effective power (e.g. 50% × 50% = 25%).
        # HARDWARE_SPEED_LIMIT is an absolute safety cap applied after.
        left  = left  * self._power_scale
        right = right * self._power_scale
        left  = max(-HARDWARE_SPEED_LIMIT, min(HARDWARE_SPEED_LIMIT, left))
        right = max(-HARDWARE_SPEED_LIMIT, min(HARDWARE_SPEED_LIMIT, right))
        # Software inversion if configured
        if self._invert_left:  left  = -left
        if self._invert_right: right = -right
        with self._lock:
            if self._duty_mode:
                # Duty mode: command is applied directly — useful for bench testing without motor
                set_duty_direct(self._serial, left)
                set_duty_can(   self._serial, VESC_ID_CAN, right)
            else:
                # RPM mode: closed-loop speed control (default)
                set_rpm_direct(self._serial, int(left  * self._max_erpm))
                set_rpm_can(   self._serial, VESC_ID_CAN, int(right * self._max_erpm))

    def stop(self) -> None:
        """Emergency stop — sends ERPM 0 to both VESCs."""
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
          scale:0.8      → power scale (0.1-1.0) — scales max ERPM
          erpm:60000     → override max ERPM ceiling
        """
        try:
            parts = value.split(':')
            param, val = parts[0], parts[1]
            if param == 'scale':
                # 0.0 = drive disabled (motors stopped); 1.0 = full power.
                # Used to be clamped at 0.1 floor which silently coerced
                # "disable propulsion" into "10% power" — confusing UX.
                requested = float(val)
                self._power_scale = max(0.0, min(1.0, requested))
                if requested != self._power_scale:
                    log.warning("VESC power scale clamped: requested %.2f → %.2f", requested, self._power_scale)
                log.info(f"VESC power scale: {self._power_scale:.2f}")
            elif param == 'erpm':
                self._max_erpm = max(1000, int(float(val)))
                log.info(f"VESC max ERPM: {self._max_erpm}")
            elif param == 'mode':
                self._duty_mode = (val.lower() == 'duty')
                log.info(f"VESC drive mode: {'DUTY' if self._duty_mode else 'RPM'}")
            else:
                log.warning(f"Unknown VCFG parameter: {param!r}")
        except (ValueError, IndexError) as e:
            log.error(f"Invalid VCFG message {value!r}: {e}")

    def handle_invert_uart(self, value: str) -> None:
        """VINV:L:0/1 — sets motor direction explicitly (0=normal, 1=inverted)."""
        parts = value.strip().upper().split(':')
        side  = parts[0]
        state = (parts[1] == '1') if len(parts) > 1 else None
        if side == 'L':
            self._invert_left  = state if state is not None else (not self._invert_left)
            log.info(f"Invert left: {self._invert_left}")
        elif side == 'R':
            self._invert_right = state if state is not None else (not self._invert_right)
            log.info(f"Invert right: {self._invert_right}")
        else:
            log.warning(f"VINV: unknown side {value!r}")

    def handle_can_scan_uart(self, value: str) -> None:
        """
        CANSCAN:start — scans the CAN bus via VESC ID 1 (USB) and sends CANFOUND: to Master.
        Launched in a thread to avoid blocking the UART listener.
        """
        if not self._ready or not self._serial:
            log.warning("CAN scan requested but VESC not ready")
            if self._uart:
                self._uart.send('CANFOUND', 'ERR')
            return

        def _do_scan():
            try:
                from slave.drivers.vesc_can import scan_can_bus
                log.info("Starting CAN bus scan...")
                with self._lock:
                    found = scan_can_bus(self._serial)
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

    def _telem_loop(self) -> None:
        """
        Reads telemetry from both VESCs and sends it to Master via UART.
          TL → VESC ID 1 (USB direct via get_values_direct)
          TR → VESC ID 2 (CAN forwarding via get_values_can)
        Auto-reconnects if the serial port is lost (e.g. USB unplug/replug).
        get_values_direct() swallows exceptions and returns None — so we count
        consecutive None responses to detect a lost connection.
        """
        import serial as _serial
        _FAIL_THRESHOLD     = 5   # consecutive Nones before declaring disconnected (~1s)
        # Hysteresis for clearing _can_lost: require this many CONSECUTIVE
        # successful right-VESC reads before re-enabling drive. Without it,
        # one lucky read during a flickering CAN bus would unlock drive for
        # one tick (and the false window can sneak a stale drive command
        # through). 3 reads ≈ 600ms at 200ms telem interval — short enough
        # for legit recovery, long enough to filter flicker.
        _RECOVER_THRESHOLD  = 3
        _fail_left      = 0      # left VESC (USB) consecutive failures → triggers reconnect
        _fail_right     = 0      # right VESC (CAN) consecutive failures → warning only
        _right_recover  = 0      # right VESC (CAN) consecutive successes → clears _can_lost
        _right_warned   = False  # suppress repeated right-VESC log spam

        while self._running:
            # --- Reconnect if not ready ---
            if not self._ready:
                time.sleep(2.0)
                log.info("VescDriver: attempting reconnect...")
                opened = False
                for port in self._ports:
                    try:
                        ser = _serial.Serial(port, VESC_BAUD, timeout=0.05)
                        with self._lock:
                            if self._serial:
                                try:
                                    self._serial.close()
                                except Exception:
                                    pass
                            self._serial = ser
                            self._port   = port
                        self._ready    = True
                        _fail_left     = 0
                        _fail_right    = 0
                        _right_recover = 0
                        _right_warned  = False
                        self._can_lost = False
                        opened = True
                        log.info(f"VescDriver reconnected on {port}")
                        break
                    except _serial.SerialException:
                        continue
                if not opened:
                    log.debug("VescDriver: no VESC found on any port, retrying...")
                continue

            # --- Normal telemetry read ---
            # Split into two separate lock acquisitions so a drive() call
            # arriving at 60 Hz can interleave between the direct read and
            # the CAN read. Old single-lock block held _lock for ~120ms
            # (60ms time.sleep inside each get_values_* call), making drive
            # frames pile up in the UART listener queue and risking
            # slave-watchdog timeout (500ms) under heavy telem traffic.
            # Worst case now: drive waits ~60-70ms for one of the two reads
            # to finish — half the old contention.
            vl = vr = None
            try:
                with self._lock:
                    vl = get_values_direct(self._serial)
            except Exception as e:
                log.warning(f"VescDriver: serial exception (direct read) — forcing reconnect: {e}")
                _fail_left = _FAIL_THRESHOLD   # trigger reconnect immediately
            else:
                # Release the lock between reads — drive() can interleave here.
                try:
                    with self._lock:
                        vr = get_values_can(self._serial, VESC_ID_CAN)
                except Exception as e:
                    log.warning(f"VescDriver: serial exception (CAN read): {e}")
                    vr = None

            if vl is None:
                _fail_left += 1
                if _fail_left >= _FAIL_THRESHOLD:
                    log.warning(
                        f"VescDriver: {_fail_left} consecutive read failures "
                        f"on {self._port} — marking disconnected"
                    )
                    with self._lock:
                        try:
                            if self._serial and self._serial.is_open:
                                self._serial.close()
                        except Exception:
                            pass
                        self._serial = None
                    self._ready = False
                    _fail_left = 0
            else:
                _fail_left = 0
                if vr is None:
                    _fail_right += 1
                    _right_recover = 0   # reset recovery streak on any failure
                    if _fail_right >= _FAIL_THRESHOLD and not self._can_lost:
                        log.error(
                            "VescDriver: right VESC (CAN ID %d) lost — stopping motors and "
                            "emitting synthetic fault=%d",
                            VESC_ID_CAN, self._SYNTHETIC_FAULT_CAN_LOST,
                        )
                        self._can_lost = True
                        self._stop_motors()
                else:
                    # Recovery hysteresis: require N consecutive successful reads
                    # before clearing _can_lost. A single lucky read during a
                    # genuinely-flickering CAN link would otherwise unlock drive
                    # for one tick, only to relock 3 reads later — and during
                    # the False window a stale drive command can sneak through
                    # the Master safety gate. Hold the lockout until the link
                    # has been stable for at least _RECOVER_THRESHOLD ticks.
                    _right_recover += 1
                    if self._can_lost and _right_recover >= _RECOVER_THRESHOLD:
                        log.info(
                            "VescDriver: right VESC (CAN ID %d) recovered after %d stable reads",
                            VESC_ID_CAN, _right_recover,
                        )
                        self._can_lost = False
                        _fail_right = 0
                        _right_warned = False
                    elif not self._can_lost:
                        # Steady state — no can_lost, no need to count
                        _fail_right = 0
                        _right_warned = False
                if self._uart:
                    self._uart.send('TL',
                        f"{vl['v_in']}:{vl['temp']}:{vl['current']}"
                        f":{vl['rpm']}:{vl['duty']}:{vl['fault']}"
                    )
                if vr and self._uart:
                    self._uart.send('TR',
                        f"{vr['v_in']}:{vr['temp']}:{vr['current']}"
                        f":{vr['rpm']}:{vr['duty']}:{vr['fault']}"
                    )
                elif self._can_lost and self._uart:
                    # Push a synthetic fault frame so Master's safety gate trips
                    # on the next telemetry tick (no waiting for staleness).
                    self._uart.send('TR',
                        f"{vl['v_in']}:0.0:0.0:0:0.0:{self._SYNTHETIC_FAULT_CAN_LOST}"
                    )

            time.sleep(TELEM_INTERVAL)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _stop_motors(self) -> None:
        if not self._ready:
            return
        try:
            with self._lock:
                set_rpm_direct(self._serial, 0)
                set_rpm_can(   self._serial, VESC_ID_CAN, 0)
        except Exception:
            pass
