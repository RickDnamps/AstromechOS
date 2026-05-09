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
Bluetooth Controller Driver — Master Pi (evdev).
Reads inputs from a BT gamepad connected to the Pi via evdev.

Applies: Lock Mode (Kids limited speed / Child Lock blocked),
         E-Stop, inactivity timeout, web/Android priority.

Persistent config: master/config/bt_config.json
"""

import json
import logging
import os
import threading
import time

log = logging.getLogger(__name__)

try:
    import evdev
    from evdev import InputDevice, ecodes, list_devices
    EVDEV_OK = True
except ImportError:
    EVDEV_OK = False
    log.warning("evdev not available — BTControllerDriver disabled (pip install evdev)")

# Keywords to identify a gamepad among evdev devices
_GAMEPAD_KEYWORDS = [
    'xbox', 'ps4', 'ps5', 'dualshock', 'dualsense', 'wireless controller',
    'pro controller', 'switch', 'shield', 'gamepad', 'joystick', 'joypad',
    'controller', '8bitdo',
]

# Default config
_DEFAULT_CFG = {
    'enabled':            True,
    'gamepad_type':       'ps',
    'deadzone':           0.10,
    'inactivity_timeout': 30,
    'mappings': {
        'throttle':   'ABS_Y',
        'steer':      'ABS_X',
        'dome':       'ABS_RX',
        'panel_dome': 'BTN_WEST',
        'panel_body': 'BTN_NORTH',
        'audio':      'BTN_EAST',
        'estop':      'BTN_MODE',
        'turbo':      'BTN_TR',
    },
}

_CFG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'bt_config.json')


def _load_cfg() -> dict:
    try:
        with open(_CFG_PATH, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        # Merge with defaults for missing keys
        merged = dict(_DEFAULT_CFG)
        merged['mappings'] = dict(_DEFAULT_CFG['mappings'])
        merged.update({k: v for k, v in cfg.items() if k != 'mappings'})
        if 'mappings' in cfg:
            merged['mappings'].update(cfg['mappings'])
        return merged
    except FileNotFoundError:
        return dict(_DEFAULT_CFG)
    except Exception as e:
        log.warning(f"bt_config.json unreadable: {e}")
        return dict(_DEFAULT_CFG)


def save_cfg(cfg: dict) -> bool:
    try:
        os.makedirs(os.path.dirname(_CFG_PATH), exist_ok=True)
        with open(_CFG_PATH, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        log.error(f"Error saving bt_config: {e}")
        return False


class BTControllerDriver:
    """
    Bluetooth gamepad driver via evdev.
    Runs in background — auto-reconnects every 5s if disconnected.
    """

    def __init__(self):
        self._cfg          = _load_cfg()
        self._device       = None
        self._stop_evt     = threading.Event()
        self._lock         = threading.Lock()
        self._connected    = False
        self._device_name  = '—'
        self._battery_pct  = 0
        self._last_input_t = time.time()
        self._drive_active = False
        self._dome_active  = False
        self._prev_btns    = {}
        self._rssi         = None
        self._last_drive   = (0.0, 0.0)   # last computed (left, right) for keep-alive
        self._last_dome    = 0.0           # last dome speed for keep-alive

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        if not EVDEV_OK:
            return
        self._stop_evt.clear()
        threading.Thread(target=self._reconnect_loop,    name='bt-reconnect',   daemon=True).start()
        threading.Thread(target=self._inactivity_loop,   name='bt-inactivity',  daemon=True).start()
        threading.Thread(target=self._drive_keepalive_loop, name='bt-keepalive', daemon=True).start()
        log.info("BTControllerDriver started")

    def stop(self) -> None:
        self._stop_evt.set()
        dev = self._device
        if dev:
            try:
                dev.close()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------

    def reload_cfg(self) -> None:
        self._cfg = _load_cfg()

    def get_cfg(self) -> dict:
        return dict(self._cfg)

    def update_cfg(self, patch: dict) -> bool:
        self._cfg.update(patch)
        if 'mappings' in patch:
            self._cfg['mappings'].update(patch['mappings'])
        return save_cfg(self._cfg)

    def is_enabled(self) -> bool:
        return bool(self._cfg.get('enabled', True))

    def set_enabled(self, enabled: bool) -> None:
        self._cfg['enabled'] = enabled
        save_cfg(self._cfg)
        if not enabled:
            self._stop_motion()
        log.info(f"BT controller {'enabled' if enabled else 'disabled'}")

    def get_status(self) -> dict:
        return {
            'bt_connected':         self._connected,
            'bt_enabled':           self.is_enabled(),
            'bt_name':              self._device_name,
            'bt_battery':           self._battery_pct,
            'bt_gamepad_type':      self._cfg.get('gamepad_type', 'ps'),
            'bt_inactivity_timeout': int(self._cfg.get('inactivity_timeout', 30)),
            'bt_rssi':               self._rssi,
        }

    # ------------------------------------------------------------------
    # Device detection
    # ------------------------------------------------------------------

    def _find_gamepad(self):
        if not EVDEV_OK:
            return None
        try:
            paths = list_devices()
        except Exception:
            return None
        for path in paths:
            try:
                dev = InputDevice(path)
                if any(kw in dev.name.lower() for kw in _GAMEPAD_KEYWORDS):
                    caps = dev.capabilities()
                    if ecodes.EV_ABS in caps:
                        log.info(f"BT gamepad found: {dev.name} ({path})")
                        return dev
                dev.close()
            except Exception:
                continue
        return None

    # ------------------------------------------------------------------
    # Automatic reconnection
    # ------------------------------------------------------------------

    def _reconnect_loop(self) -> None:
        while not self._stop_evt.is_set():
            if not self._connected:
                dev = self._find_gamepad()
                if dev:
                    with self._lock:
                        self._device      = dev
                        self._connected   = True
                        self._device_name = dev.name[:32]
                        self._prev_btns   = {}
                    log.info(f"Gamepad connected: {dev.name}")
                    self._poll_loop()   # blocking until disconnection
            self._stop_evt.wait(5)

    # ------------------------------------------------------------------
    # Read loop
    # ------------------------------------------------------------------

    def _find_hidraw(self, dev) -> str | None:
        """Find the /dev/hidrawN path corresponding to this evdev device."""
        import glob as _glob, os as _os
        vid = f'{dev.info.vendor:04x}'
        pid = f'{dev.info.product:04x}'
        for hr_sys in sorted(_glob.glob('/sys/class/hidraw/hidraw*')):
            try:
                uevent = open(_os.path.join(hr_sys, 'device', 'uevent')).read().lower()
                if vid in uevent and pid in uevent:
                    name = _os.path.basename(hr_sys)
                    return f'/dev/{name}'
            except Exception:
                pass
        hids = sorted(_glob.glob('/dev/hidraw*'))
        return hids[0] if hids else None

    def _poll_loop(self) -> None:
        try:
            dev  = self._device
            caps = dev.capabilities()
            abs_info = {info[0]: info[1] for info in caps.get(ecodes.EV_ABS, [])}

            # Start background thread to poll RSSI + battery every 30s
            threading.Thread(target=self._hw_poll_loop, daemon=True,
                             name='bt-hw-poll').start()

            for event in dev.read_loop():
                if self._stop_evt.is_set():
                    break
                if not self.is_enabled():
                    continue
                self._last_input_t = time.time()

                if event.type == ecodes.EV_ABS:
                    self._handle_axis(event, abs_info)
                elif event.type == ecodes.EV_KEY:
                    self._handle_button(event)

        except Exception as e:
            log.warning(f"Gamepad disconnected: {e}")
        finally:
            with self._lock:
                self._connected   = False
                self._device      = None
                self._device_name = '—'
                self._battery_pct = 0
                self._rssi        = None
            self._stop_motion()

    def _hw_poll_loop(self) -> None:
        """Polls RSSI and battery level every 30s via upower/sysfs.

        Battery reporting works for PS4 / PS5 / Xbox controllers which expose
        a standard Linux HID battery interface. The NVIDIA Shield controller
        uses a proprietary protocol and does not expose battery via upower or
        sysfs — battery will remain 0% for that device.
        """
        import subprocess, re, glob as _glob
        while self._connected and not self._stop_evt.is_set():
            dev = self._device
            mac_colon = (dev.uniq or '').upper() if dev else ''
            rssi    = None
            battery = 0

            if mac_colon:
                # RSSI via hcitool
                try:
                    out = subprocess.run(
                        ['hcitool', 'rssi', mac_colon],
                        capture_output=True, text=True, timeout=2,
                    )
                    m = re.search(r'(-?\d+)', out.stdout)
                    if m:
                        rssi = int(m.group(1))
                except Exception:
                    pass

                # Battery via sysfs HID power_supply (PS4, PS5, Xbox)
                mac_lower = mac_colon.lower().replace(':', '_')
                for path in _glob.glob(f'/sys/class/power_supply/hid-{mac_lower}-battery/capacity'):
                    try:
                        battery = int(open(path).read().strip())
                        log.debug(f"BT battery (sysfs): {battery}%")
                        break
                    except Exception:
                        pass

                # Fallback: upower (covers some controllers not in sysfs)
                if battery == 0:
                    try:
                        enum_out = subprocess.run(
                            ['upower', '-e'],
                            capture_output=True, text=True, timeout=2,
                        ).stdout
                        mac_up = mac_colon.lower().replace(':', '_')
                        for line in enum_out.splitlines():
                            if 'hid' in line and mac_up in line.lower():
                                info_out = subprocess.run(
                                    ['upower', '-i', line.strip()],
                                    capture_output=True, text=True, timeout=2,
                                ).stdout
                                pct_m = re.search(r'percentage:\s*(\d+)', info_out, re.I)
                                if pct_m:
                                    battery = int(pct_m.group(1))
                                    log.debug(f"BT battery (upower): {battery}%")
                                break
                    except Exception:
                        pass

            with self._lock:
                self._rssi        = rssi
                self._battery_pct = battery
            log.debug("BT hw-poll: rssi=%s dBm  battery=%d%%", rssi, battery)
            self._stop_evt.wait(30)

    def _drive_keepalive_loop(self) -> None:
        """Re-sends the last drive/dome command every 300ms while the joystick is held.

        evdev only fires EV_ABS events on value CHANGE — holding still sends nothing.
        Without this, MotionWatchdog (800ms timeout) would cut propulsion after <1s.
        """
        INTERVAL = 0.30  # seconds — well under the 800ms watchdog timeout
        _ka_count = 0
        while not self._stop_evt.wait(INTERVAL):
            if not self._connected or not self.is_enabled():
                continue
            try:
                import master.registry as reg
                if getattr(reg, 'estop_active', False):
                    continue
                if getattr(reg, 'lock_mode', 0) == 2:
                    continue
                if self._is_vesc_unsafe(reg):
                    continue
                # Keep-alive for propulsion
                if self._drive_active:
                    left, right = self._last_drive
                    if abs(left) > 0.01 or abs(right) > 0.01:
                        _ka_count += 1
                        if _ka_count % 10 == 1:  # log every ~3s (10 × 300ms)
                            log.info("BT keepalive #%d: drive=(%.3f, %.3f)", _ka_count, left, right)
                        self._do_drive(left, right, reg)
                # Keep-alive for dome
                if self._dome_active:
                    spd = self._last_dome
                    if abs(spd) > 0.01:
                        self._do_dome(spd, reg)
            except Exception as e:
                log.warning("keepalive error: %s", e)

    # ------------------------------------------------------------------
    # Axes
    # ------------------------------------------------------------------

    def _norm(self, value: int, info) -> float:
        """Normalizes a raw axis value → -1.0..1.0."""
        lo, hi = info.min, info.max
        mid  = (lo + hi) / 2.0
        half = (hi - lo) / 2.0
        return (value - mid) / half if half else 0.0

    def _handle_axis(self, event, abs_info) -> None:
        import master.registry as reg

        code_name = ecodes.ABS.get(event.code)
        if not code_name:
            return
        info = abs_info.get(event.code)
        if not info:
            return
        val = self._norm(event.value, info)

        m         = self._cfg.get('mappings', {})
        dz        = float(self._cfg.get('deadzone', 0.10))
        throttle_c = m.get('throttle', 'ABS_Y')
        steer_c    = m.get('steer',    'ABS_X')
        dome_c     = m.get('dome',     'ABS_RX')

        if code_name in (throttle_c, steer_c):
            self._send_drive(abs_info, m, reg)
        elif code_name == dome_c:
            dome_val = val if abs(val) > dz else 0.0
            self._send_dome(dome_val, reg)

    def _read_axis_val(self, device, code_name: str, abs_info: dict, dz: float) -> float:
        """Reads the current value of an axis by name (e.g. 'ABS_Y')."""
        try:
            code = getattr(ecodes, code_name, None)
            if code is None:
                return 0.0
            ai = device.absinfo(code)
            info = abs_info.get(code)
            if not info:
                return 0.0
            val = self._norm(ai.value, info)
            return val if abs(val) > dz else 0.0
        except Exception:
            return 0.0

    def _send_drive(self, abs_info: dict, m: dict, reg) -> None:
        """Compute and send drive command from current axes."""
        # Child Lock — block propulsion
        if getattr(reg, 'lock_mode', 0) == 2:
            if self._drive_active:
                self._do_stop(reg)
                self._drive_active = False
            return

        # VESC safety — block if any VESC is stale or faulted
        if self._is_vesc_unsafe(reg):
            if self._drive_active:
                self._do_stop(reg)
                self._drive_active = False
            return

        # E-Stop active — ignore
        if getattr(reg, 'estop_active', False):
            return

        # Web/Android priority — yield if recent web command (<500ms)
        if time.time() - getattr(reg, 'web_last_drive_t', 0) < 0.5:
            return

        dev = self._device
        if not dev:
            return
        dz        = float(self._cfg.get('deadzone', 0.10))
        thr_raw   = -self._read_axis_val(dev, m.get('throttle', 'ABS_Y'), abs_info, dz)
        str_raw   =  self._read_axis_val(dev, m.get('steer',    'ABS_X'), abs_info, dz)

        # Max speed — Kids mode
        spd = 1.0
        if getattr(reg, 'lock_mode', 0) == 1:
            spd = float(getattr(reg, 'kids_speed_limit', 0.5))

        throttle = thr_raw * spd
        steering = str_raw * spd * 0.55
        left     = max(-1.0, min(1.0, throttle + steering))
        right    = max(-1.0, min(1.0, throttle - steering))

        if abs(left) > 0.01 or abs(right) > 0.01:
            self._last_drive = (left, right)
            self._do_drive(left, right, reg)
            self._drive_active = True
        elif self._drive_active:
            self._last_drive = (0.0, 0.0)
            self._do_stop(reg)
            self._drive_active = False

    def _send_dome(self, val: float, reg) -> None:
        if getattr(reg, 'estop_active', False):
            return
        # Web/Android priority for dome
        if time.time() - getattr(reg, 'web_last_dome_t', 0) < 0.5:
            return
        if abs(val) > 0.01:
            self._last_dome = val * 0.85
            self._do_dome(val * 0.85, reg)
            self._dome_active = True
        elif self._dome_active:
            self._last_dome = 0.0
            self._do_dome(0.0, reg)
            self._dome_active = False

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------

    def _handle_button(self, event) -> None:
        import master.registry as reg

        # ecodes.BTN may return a list of aliases for the same code
        # e.g.: BTN_EAST (305) → ['BTN_B', 'BTN_EAST'] on Shield/Xbox
        raw = ecodes.KEY.get(event.code) or ecodes.BTN.get(event.code)
        if not raw:
            return
        code_names = list(raw) if isinstance(raw, (list, tuple)) else [raw]

        def _is(target: str) -> bool:
            return target in code_names

        pressed  = (event.value == 1)
        released = (event.value == 0)
        m        = self._cfg.get('mappings', {})

        log.debug(f"BTN codes={code_names} pressed={pressed} released={released}")

        # E-Stop — always processed even if disabled
        if _is(m.get('estop', 'BTN_MODE')):
            if pressed:
                self._trigger_estop(reg)
            return

        # If E-Stop active → ignore everything else
        if getattr(reg, 'estop_active', False):
            return

        # Dome panel (held = open, released = closed)
        if _is(m.get('panel_dome', 'BTN_WEST')):
            if (pressed or released) and reg.dome_servo:
                direction = 'open' if pressed else 'close'
                log.info("BT: %s_all dome_servo (config-aware)", direction)
                try:
                    from master.api.servo_bp import _read_panels_cfg, DOME_SERVOS, _panel_angle, _panel_speed
                    cfg    = _read_panels_cfg()
                    method = reg.dome_servo.open if pressed else reg.dome_servo.close
                    threads = [
                        threading.Thread(
                            target=method,
                            args=(n, _panel_angle(n, direction, cfg), _panel_speed(n, cfg)),
                            daemon=True,
                        )
                        for n in DOME_SERVOS
                    ]
                    for t in threads:
                        t.start()
                except Exception as e:
                    log.warning("dome %s_all: %s", direction, e)

        # Body panel (held = open, released = closed)
        elif _is(m.get('panel_body', 'BTN_NORTH')):
            if pressed or released:
                direction = 'open' if pressed else 'close'
                log.info("BT: %s_all body_servo (config-aware)", direction)
                try:
                    from master.api.servo_bp import _read_panels_cfg, BODY_SERVOS, _panel_angle, _panel_speed
                    cfg    = _read_panels_cfg()
                    method = reg.servo.open if pressed else reg.servo.close
                    if reg.servo:
                        for n in BODY_SERVOS:
                            method(n, _panel_angle(n, direction, cfg), _panel_speed(n, cfg))
                    elif reg.uart:
                        for n in BODY_SERVOS:
                            reg.uart.send('SRV', f'{n},{_panel_angle(n, direction, cfg)},{_panel_speed(n, cfg)}')
                except Exception as e:
                    log.warning("body %s_all: %s", direction, e)

        # Random sound (rising edge)
        elif _is(m.get('audio', 'BTN_EAST')):
            if pressed and reg.uart:
                log.info("BT: S:RANDOM:happy")
                try: reg.uart.send('S', 'RANDOM:happy')
                except Exception as e: log.warning(f"audio send: {e}")

    def _trigger_estop(self, reg) -> None:
        log.warning("E-STOP triggered from BT gamepad")
        reg.estop_active = True
        self._stop_motion()
        # Freeze servos in place rather than shutdown() — shutdown() puts the
        # PCA9685 to SLEEP and cuts PWM, which makes servos go limp and droop
        # under load. freeze() keeps PWM at the last commanded angle so panels
        # stay where they are with full holding torque.
        if reg.dome_servo:
            try: reg.dome_servo.freeze()
            except Exception: pass
        if reg.uart:
            try: reg.uart.send('FREEZE', '1')   # body servos on Slave
            except Exception: pass

    # ------------------------------------------------------------------
    # Motion helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_vesc_unsafe(reg) -> bool:
        """True if drive must be blocked. Delegates to the shared safety helper.

        Bench mode bypasses the check (developer test mode). Otherwise both
        VESC sides must have fresh, fault-free telemetry — a missing telemetry
        side is treated as unsafe."""
        from master.vesc_safety import is_drive_safe
        return not is_drive_safe()

    def _do_drive(self, left: float, right: float, reg) -> None:
        from master.motion_watchdog import motion_watchdog
        from master.safe_stop import cancel_ramp
        cancel_ramp()
        motion_watchdog.feed_drive(left, right)
        if reg.vesc:
            reg.vesc.drive(left, right)
        elif reg.uart:
            reg.uart.send('M', f'{left:.3f},{right:.3f}')

    def _do_stop(self, reg) -> None:
        from master.motion_watchdog import motion_watchdog
        motion_watchdog.clear_drive()
        if reg.vesc:
            reg.vesc.stop()
        elif reg.uart:
            reg.uart.send('M', '0.000,0.000')

    def _do_dome(self, speed: float, reg) -> None:
        from master.motion_watchdog import motion_watchdog
        if abs(speed) > 0.01:
            motion_watchdog.feed_dome(speed)
            if reg.dome:
                reg.dome.turn(speed)
            elif reg.uart:
                reg.uart.send('D', f'{speed:.3f}')
        else:
            motion_watchdog.clear_dome()
            if reg.dome:
                reg.dome.stop()
            elif reg.uart:
                reg.uart.send('D', '0.000')

    def _stop_motion(self) -> None:
        try:
            import master.registry as reg
            if self._drive_active:
                self._do_stop(reg)
            if self._dome_active:
                self._do_dome(0.0, reg)
        except Exception:
            pass
        self._drive_active = False
        self._dome_active  = False

    # ------------------------------------------------------------------
    # Inactivity watchdog
    # ------------------------------------------------------------------

    def _inactivity_loop(self) -> None:
        while not self._stop_evt.wait(2):
            if not self._connected or not self.is_enabled():
                continue
            timeout = float(self._cfg.get('inactivity_timeout', 30))
            if timeout <= 0:
                continue
            if time.time() - self._last_input_t > timeout:
                if self._drive_active or self._dome_active:
                    log.info(f"BT inactivity >{timeout:.0f}s — stopping movement")
                    self._stop_motion()
