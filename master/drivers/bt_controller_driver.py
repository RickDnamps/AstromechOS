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
    # Audit reclass R4 2026-05-15: operator-configurable BT audio
    # button category. Default 'happy' preserves legacy behavior.
    'audio_category':     'happy',
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
    except (OSError, json.JSONDecodeError) as e:
        # Audit finding H-3 2026-05-15: bare `except Exception` here
        # hid corruption from genuine bugs (KeyError, MemoryError).
        # Narrow to the two cases we actually expect: missing-file
        # variants of OSError + JSON corruption.
        log.warning("bt_config.json unreadable (%s) — using defaults", e)
        return dict(_DEFAULT_CFG)


# B3/E1 fix 2026-05-16: module-level lock for cfg mutation+save.
# Was: update_cfg did self._cfg.update(...) + save_cfg without holding
# any lock. Two concurrent admins (web + Android) hitting /bt/config
# would race on the dict mutation AND on save_cfg's tmp+rename, losing
# the second writer's mappings silently. Now serialize both paths.
_cfg_save_lock = threading.Lock()


def save_cfg(cfg: dict) -> bool:
    # B-50 (audit 2026-05-15): atomic write — tmp + os.replace + fsync.
    # B10 fix 2026-05-16: chmod 0o600 per CLAUDE.md invariant
    # ("tout fichier disque écrit via tmp+os.replace+fsync+chmod 0o600").
    # bt_config.json doesn't hold secrets today but consistency +
    # defense-in-depth against future fields (BT PIN, MAC allowlist).
    try:
        os.makedirs(os.path.dirname(_CFG_PATH), exist_ok=True)
        tmp = _CFG_PATH + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, _CFG_PATH)
        try:
            os.chmod(_CFG_PATH, 0o600)
        except OSError:
            pass
        return True
    except OSError as e:
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
        # B3/E1 fix 2026-05-16: hold both the cross-process save lock
        # AND the instance lock around the mutation. Readers
        # (_handle_button, _handle_axis) snapshot the mappings dict via
        # .get(...) which is atomic, but the in-place .update() on the
        # mappings sub-dict could be observed mid-iteration if a future
        # caller adds .items() loop. Defense in depth.
        with _cfg_save_lock:
            with self._lock:
                self._cfg.update(patch)
                if 'mappings' in patch:
                    # Replace mappings dict atomically vs mutating it.
                    new_map = dict(self._cfg.get('mappings', {}))
                    new_map.update(patch['mappings'])
                    self._cfg['mappings'] = new_map
                snapshot = dict(self._cfg)
            return save_cfg(snapshot)

    def is_enabled(self) -> bool:
        return bool(self._cfg.get('enabled', True))

    def set_enabled(self, enabled: bool) -> None:
        # Audit finding L-4 2026-05-15: skip-if-unchanged. Each
        # save_cfg does a full tmp+rename+fsync — at 100ms keypress
        # repeats on the BT enable toggle that's fsync churn for no
        # state change. Only write if the value actually flips.
        if bool(self._cfg.get('enabled', True)) == bool(enabled):
            return
        self._cfg['enabled'] = enabled
        save_cfg(self._cfg)
        if not enabled:
            self._stop_motion()
        else:
            # B19 fix 2026-05-16: was leaving _last_input_t stale → re-
            # enabling after a long pause immediately tripped the
            # inactivity loop (time.time() - _last_input_t > timeout).
            # Operator saw "BT idle" the moment they re-enabled, had to
            # nudge the stick to clear it. Refresh the watermark.
            self._last_input_t = time.time()
            self._inactivity_pause = False
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
            # Audit finding BT M-1 2026-05-15: surface the inactivity
            # pause state so the UI can warn the operator.
            'bt_inactivity_pause':  bool(getattr(self, '_inactivity_pause', False)),
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
                    # B2 fix 2026-05-16: clear stale inactivity pause flag
                    # left over from previous session (operator powered
                    # down a paused controller — flag persisted across
                    # the disconnect → UI lied about "BT idle" after
                    # reconnect until next physical input timeout).
                    self._inactivity_pause = False
                    self._last_input_t = time.time()
                    log.info(f"Gamepad connected: {dev.name}")
                    self._poll_loop()   # blocking until disconnection
            self._stop_evt.wait(5)

    # ------------------------------------------------------------------
    # Read loop
    # ------------------------------------------------------------------

    # Audit finding BT L-1 2026-05-15: _find_hidraw was leftover dead
    # code from an abandoned RSSI-via-hidraw attempt. Removed — RSSI
    # now polled via _hw_poll_loop using bluetoothctl info <MAC>.

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
                # B7 fix 2026-05-16: was `if not is_enabled(): continue` here,
                # but _handle_button has a SAFETY branch (E-STOP) that must
                # fire even when the controller is "disabled" via UI toggle
                # (operator silenced a noisy controller during testing).
                # is_enabled() now gates only axes/non-safety buttons inside
                # _handle_axis / _handle_button — E-STOP always runs.
                self._last_input_t = time.time()
                enabled = self.is_enabled()

                if event.type == ecodes.EV_ABS:
                    if enabled:
                        self._handle_axis(event, abs_info)
                elif event.type == ecodes.EV_KEY:
                    # _handle_button itself checks is_enabled for non-E-STOP
                    self._handle_button(event)

        except Exception as e:
            log.warning(f"Gamepad disconnected: {e}")
        finally:
            with self._lock:
                # E4/E8 fix 2026-05-16: close device fd before nulling
                # so disconnect-during-pairing cycles don't leak fds.
                # After ~100 power-cycle cycles the leak exhausted fds.
                old_dev = self._device
                self._connected   = False
                self._device      = None
                self._device_name = '—'
                self._battery_pct = 0
                self._rssi        = None
                # E4 fix: clear stale last-drive so a ghost packet from
                # the keep-alive thread between disconnect and stop
                # can't emit one final M:L,R after the connection died.
                self._last_drive = (0.0, 0.0)
                self._last_dome  = 0.0
                self._drive_active = False
                self._dome_active  = False
            if old_dev is not None:
                try: old_dev.close()
                except Exception: pass
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
                # Audit finding H-2 2026-05-15: stow_in_progress
                # was checked indirectly via _do_drive but the
                # keep-alive still ran its bookkeeping (incremented
                # _ka_count, refreshed _last_input_t) on every cycle
                # — masking inactivity from the watchdog AND spamming
                # the log during the stow window. Bail before any of
                # that work happens.
                if getattr(reg, 'stow_in_progress', False):
                    continue
                # Same logic for the anti-tip safety ramp: while the
                # ramp is in flight nothing should re-feed the
                # watchdog from BT, the ramp's own writer owns the
                # propulsion bus for that ≤400ms window.
                try:
                    from master.safe_stop import is_drive_ramp_active, is_dome_ramp_active
                    if is_drive_ramp_active() or is_dome_ramp_active():
                        continue
                except ImportError:
                    pass
                # E2 fix 2026-05-16: split lock_mode==2 gate so dome
                # keep-alive still fires under Child Lock (per spec:
                # 'drive bloqué, dome/sounds/lights libres'). Was: this
                # 'continue' skipped BOTH drive AND dome keep-alives,
                # forcing BT operator to wiggle the stick to keep dome
                # turning. Per-section gate fixes it.
                child_locked = getattr(reg, 'lock_mode', 0) == 2
                if self._is_vesc_unsafe(reg):
                    continue
                # Snapshot drive + dome state under the instance lock. Without
                # this, the keep-alive could see `_drive_active=True` from an
                # earlier write while `_last_drive` still held the PREVIOUS
                # tick's value — atomic tuple-assignment in CPython prevents
                # tearing but not the cross-field ordering. With the lock,
                # writers always update active+last atomically together.
                with self._lock:
                    drive_active = self._drive_active and not child_locked
                    last_drive   = self._last_drive
                    dome_active  = self._dome_active
                    last_dome    = self._last_dome
                # Keep-alive for propulsion
                if drive_active:
                    left, right = last_drive
                    if abs(left) > 0.01 or abs(right) > 0.01:
                        # Audit finding A4-M4 2026-05-15: wrap to bound
                        # the counter. CPython ints don't overflow but
                        # an unbounded counter is sloppy — wrap at 1M
                        # (~83 hours of continuous drive at 300ms) so
                        # the log signal remains useful.
                        _ka_count = (_ka_count + 1) % 1_000_000
                        if _ka_count % 10 == 1:  # log every ~3s (10 × 300ms)
                            log.info("BT keepalive #%d: drive=(%.3f, %.3f)", _ka_count, left, right)
                        self._do_drive(left, right, reg)
                        # B-11: Sustained active drive counts as "input still
                        # happening" — bump _last_input_t so the inactivity
                        # watchdog doesn't cut motion mid-drive when evdev
                        # stops firing events (user holding the stick at a
                        # constant position generates no EV_ABS deltas).
                        self._last_input_t = time.time()
                # Keep-alive for dome
                if dome_active:
                    spd = last_dome
                    if abs(spd) > 0.01:
                        self._do_dome(spd, reg)
                        self._last_input_t = time.time()
            except (AttributeError, OSError, ImportError) as e:
                # Narrow catch — known transient errors (driver hot-swap,
                # serial port gone, ImportError during hot-reload).
                # Audit finding BT M-3 2026-05-15: ImportError used to
                # propagate and KILL the keep-alive thread → permanent
                # BT outage until daemon restart. Now caught + logged.
                log.warning("keepalive transient error: %s", e)
            except Exception:
                # Anything else → log with traceback but DON'T kill the
                # thread. A buggy callback shouldn't take down BT input
                # forever; daemon restart is too heavy.
                log.exception("keepalive unexpected error — continuing")

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
        except OSError:
            # Audit finding M-5 2026-05-15: narrowed from bare Exception
            # to OSError. Real device disconnects raise OSError mid-poll
            # (errno=19 ENODEV). Capability-mismatch or evdev-type bugs
            # used to be silently turned into "axis at rest" — now they
            # propagate so journalctl shows the actual crash.
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
        # Audit finding Motion H-3 + BT H-2 2026-05-15:
        #  - time.monotonic to match the producer in motion_bp (immune
        #    to NTP clock-skew jumps that would freeze BT for hours).
        #  - 1.0s window matches CLAUDE.md "BT yields to web for <1s"
        #    documentation. Previous 0.5s was shorter than the BT
        #    keep-alive cadence (300ms), producing motion jitter when
        #    both inputs were simultaneously active.
        if time.monotonic() - getattr(reg, 'web_last_drive_t', 0) < 1.0:
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

        # Update _last_drive + _drive_active together under the lock so the
        # keep-alive thread cannot see a mismatched (active=True, last=stale)
        # pair. The actual _do_drive/_do_stop calls happen OUTSIDE the lock
        # to avoid holding it during a UART round-trip.
        if abs(left) > 0.01 or abs(right) > 0.01:
            with self._lock:
                self._last_drive   = (left, right)
                self._drive_active = True
            self._do_drive(left, right, reg)
        else:
            was_active = self._drive_active
            with self._lock:
                self._last_drive   = (0.0, 0.0)
                self._drive_active = False
            if was_active:
                self._do_stop(reg)

    def _send_dome(self, val: float, reg) -> None:
        if getattr(reg, 'estop_active', False):
            return
        # B1/E5 fix 2026-05-16: was time.time() but producer
        # (motion_bp.dome_turn) writes time.monotonic(). The two clocks
        # have completely different scales (unix epoch vs uptime), so
        # the subtraction yielded a huge positive number → web-priority
        # gate NEVER fired → BT keep-alive overrode web dome commands
        # every 300ms. Match drive's monotonic + 1.0s window for parity.
        if time.monotonic() - getattr(reg, 'web_last_dome_t', 0) < 1.0:
            return
        if abs(val) > 0.01:
            with self._lock:
                self._last_dome   = val * 0.85
                self._dome_active = True
            self._do_dome(val * 0.85, reg)
        else:
            was_active = self._dome_active
            with self._lock:
                self._last_dome   = 0.0
                self._dome_active = False
            if was_active:
                self._do_dome(0.0, reg)

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

        # E-Stop — always processed even if controller is "disabled"
        # via UI toggle (B7 fix 2026-05-16: gate moved out of _poll_loop
        # so this branch can still fire).
        if _is(m.get('estop', 'BTN_MODE')):
            if pressed:
                self._trigger_estop(reg)
            return

        # B7 fix: all OTHER buttons (panels, audio) gated by is_enabled.
        if not self.is_enabled():
            return

        # If E-Stop active → ignore everything else
        if getattr(reg, 'estop_active', False):
            return

        # Dome panel (held = open, released = closed)
        if _is(m.get('panel_dome', 'BTN_WEST')):
            # Audit finding BT H-1 2026-05-15: guard FIRST so the
            # attribute lookup `reg.dome_servo.open` doesn't raise
            # AttributeError when dome_servo is None (would be
            # swallowed by the outer except Exception). Operator
            # presses panel → nothing happens silently.
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
            # Audit finding BT H-1 2026-05-15: guard reg.servo BEFORE
            # accessing .open/.close attribute.
            if (pressed or released) and reg.servo:
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
                # Audit reclass R4 2026-05-15: was hard-coded
                # 'happy' — operator could config their gamepad audio
                # button via mappings but always got happy category.
                # New bt_config key `audio_category` defaults to
                # 'happy' but operator can override (e.g. 'scared',
                # 'cantina'). Validated against _CATEGORY_NAME_RE
                # by bt_bp at save time.
                cat = self._cfg.get('audio_category', 'happy')
                log.info("BT: S:RANDOM:%s", cat)
                try: reg.uart.send('S', f'RANDOM:{cat}')
                except OSError as e: log.warning(f"audio send: {e}")

    def _trigger_estop(self, reg) -> None:
        """B4 fix 2026-05-16: delegate to the canonical /system/estop
        path. Was setting reg.estop_active + dome.freeze() + UART
        FREEZE directly — bypassed behavior engine pause + choreo
        abort hook. If a choreo was running when operator hit BT MODE,
        the choreo player kept emitting body servo events through UART
        until its next tick. Parity with /bt/estop_reset which already
        delegates to status_bp.system_estop_reset."""
        log.warning("E-STOP triggered from BT gamepad")
        try:
            from master.api.status_bp import system_estop
            system_estop()
        except Exception as e:
            log.warning("BT E-STOP fallback (system_estop failed: %s)", e)
            # Defense-in-depth: if the canonical path fails, do the
            # minimum freeze ourselves so the robot at least stops.
            reg.estop_active = True
            self._stop_motion()
            if reg.dome_servo:
                try: reg.dome_servo.freeze()
                except Exception: pass
            if reg.uart:
                try: reg.uart.send('FREEZE', '1')
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

    def clear_drive_state(self) -> None:
        """Reset keep-alive drive tracking. Called by MotionWatchdog after
        cutting drive so the next keep-alive tick won't re-fire the stale
        last command. Uses the instance lock for consistency with
        _send_drive / _stop_motion (B-10) — the keep-alive snapshots
        both fields under the same lock and would otherwise see a torn
        (active=True, last=(0,0)) state."""
        with self._lock:
            self._drive_active = False
            self._last_drive   = (0.0, 0.0)

    def clear_dome_state(self) -> None:
        """Same as clear_drive_state but for dome rotation."""
        with self._lock:
            self._dome_active = False
            self._last_dome   = 0.0

    def _do_drive(self, left: float, right: float, reg) -> None:
        from master.motion_watchdog import motion_watchdog
        from master.safe_stop import cancel_ramp, is_drive_ramp_active
        # Refuse to send drive commands while the anti-tip safety ramp is
        # in progress. The user joystick may resume immediately AFTER the
        # ramp completes (≤400ms) — that's the design intent. The gate
        # also prevents the keep-alive thread from re-feeding the watchdog
        # mid-ramp (which would re-arm it and resume the cut drive).
        if is_drive_ramp_active() or getattr(reg, 'stow_in_progress', False):
            return
        # Per-axis choreo gate (matches motion_bp._drive_gate). Only
        # blocks BT propulsion when the active choreo actually has a
        # 'propulsion' track. A panel/sound-only choreo leaves the
        # gamepad free so the operator can drive while it plays.
        if reg.choreo and reg.choreo.is_playing():
            st = reg.choreo.get_status() or {}
            if st.get('uses_propulsion'):
                return
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
        from master.safe_stop import is_dome_ramp_active
        if is_dome_ramp_active() or getattr(reg, 'stow_in_progress', False):
            return
        if reg.choreo and reg.choreo.is_playing():
            st = reg.choreo.get_status() or {}
            if st.get('uses_dome'):
                return
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
        # Narrow catch: registry import or driver call may fail transiently
        # (Slave reboot, USB unplug). Bare `except Exception` previously
        # swallowed every error including real bugs — per project rule
        # feedback_silent_import_swallow, catch ImportError for the import
        # and OSError/AttributeError for the driver calls. Anything else
        # propagates so it shows up in journalctl.
        try:
            import master.registry as reg
        except ImportError:
            log.exception("_stop_motion: registry unavailable")
            return
        try:
            if self._drive_active:
                self._do_stop(reg)
            if self._dome_active:
                self._do_dome(0.0, reg)
        except (AttributeError, OSError) as e:
            log.warning("_stop_motion: driver call failed: %s", e)
        # Clear state under the lock (B-10) so the keep-alive thread cannot
        # observe a torn (drive_active=True, but motion just stopped) state.
        with self._lock:
            self._drive_active = False
            self._dome_active  = False
            self._last_drive   = (0.0, 0.0)
            self._last_dome    = 0.0

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
                    # Audit finding BT M-1 2026-05-15: surface the
                    # event so the operator's UI can show "BT idle".
                    # Was logging only — operator saw "BT connected"
                    # pill but the robot quietly ignored input.
                    self._inactivity_pause = True
            else:
                # Resume — clear the pause flag so the UI reverts.
                if getattr(self, '_inactivity_pause', False):
                    log.info("BT input resumed after inactivity")
                    self._inactivity_pause = False
