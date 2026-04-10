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

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        if not EVDEV_OK:
            return
        self._stop_evt.clear()
        threading.Thread(target=self._reconnect_loop,    name='bt-reconnect',   daemon=True).start()
        threading.Thread(target=self._inactivity_loop,   name='bt-inactivity',  daemon=True).start()
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

    def _poll_loop(self) -> None:
        try:
            dev  = self._device
            caps = dev.capabilities()
            abs_info = {info[0]: info[1] for info in caps.get(ecodes.EV_ABS, [])}

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
            self._stop_motion()

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
            self._do_drive(left, right, reg)
            self._drive_active = True
        elif self._drive_active:
            self._do_stop(reg)
            self._drive_active = False

    def _send_dome(self, val: float, reg) -> None:
        if getattr(reg, 'estop_active', False):
            return
        # Web/Android priority for dome
        if time.time() - getattr(reg, 'web_last_dome_t', 0) < 0.5:
            return
        if abs(val) > 0.01:
            self._do_dome(val * 0.85, reg)
            self._dome_active = True
        elif self._dome_active:
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
        if reg.dome_servo:
            try: reg.dome_servo.shutdown()
            except Exception: pass
        if reg.servo:
            try: reg.servo.shutdown()
            except Exception: pass

    # ------------------------------------------------------------------
    # Motion helpers
    # ------------------------------------------------------------------

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
