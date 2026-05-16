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
import re
import subprocess
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
    # LOW-1 cleanup 2026-05-16 (review iter 2): 'audio_category' removed
    # — its only consumer (audio button branch in _handle_button) was
    # deleted by commit 912d8ea. Field is silently stripped from
    # bt_config.json at next save via _DEPRECATED_BT_CONFIG_KEYS.
    'mappings': {
        'throttle':   'ABS_Y',
        'steer':      'ABS_X',
        'dome':       'ABS_RX',
        # 'camera' = future feature (camera-on-servos tilt). Persisted
        # in bt_config.json so the operator's choice survives reboot,
        # but _handle_axis ignores this key until the hardware is
        # installed and the camera tilt servo channel is wired up.
        'camera':     'ABS_RY',
        # LOW-2 cleanup 2026-05-16: 'panel_dome'/'panel_body'/'audio'
        # removed from defaults — dispatch was deleted by commit 912d8ea.
        # See _DEPRECATED_BT_MAPPING_KEYS in bt_bp.py for silent strip.
        'estop':      'BTN_MODE',
        'turbo':      'BTN_TR',
    },
    # Per-MAC operator-defined custom button mappings.
    # Schema: {mac: {name, type, last_seen, custom_button_mappings: [...]}}
    # Populated by _ensure_device_profile() on each connect.
    'device_profiles': {},
}

_CFG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'bt_config.json')


def _load_cfg() -> dict:
    try:
        with open(_CFG_PATH, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        # Merge with defaults for missing keys
        merged = dict(_DEFAULT_CFG)
        merged['mappings'] = dict(_DEFAULT_CFG['mappings'])
        merged['device_profiles'] = {}
        merged.update({k: v for k, v in cfg.items() if k not in ('mappings', 'device_profiles')})
        if 'mappings' in cfg:
            merged['mappings'].update(cfg['mappings'])
        # device_profiles: replace wholesale (per-MAC dict, no per-key merge
        # makes sense — operator may have removed a profile intentionally).
        if isinstance(cfg.get('device_profiles'), dict):
            merged['device_profiles'] = dict(cfg['device_profiles'])
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
        # Custom mappings (per-MAC operator-defined button bindings)
        self._active_device_mac: str | None = None
        self._capture_mode = False
        self._capture_result: str | None = None
        self._capture_expires_at = 0.0
        # H1 fix 2026-05-16 (security review): lock around all capture
        # state reads/writes. Three threads touch these fields — Flask
        # poll thread, evdev poll thread (_handle_button), Timer reaper
        # — and prior unlocked access could race two admin tabs OR
        # produce 'captured' vs 'expired' inconsistency mid-mutation.
        self._capture_lock = threading.Lock()
        # Per-mapping-id debounce + lock — mirrors shortcuts B5/P2 pattern.
        self._custom_last_ts: dict = {}
        self._custom_locks: dict = {}

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
        # AND the instance lock around the mutation.
        # M2 fix 2026-05-16 (security review): smart-merge `device_profiles`
        # per-MAC instead of wholesale replace. Was: concurrent _ensure_
        # device_profile (reconnect thread updating last_seen) and admin
        # upsert via /bt/custom_mapping raced — last writer wins, the
        # other's mutation lost. Now per-MAC merge: each MAC's profile
        # patch updates ONLY the fields it provides, preserving others.
        with _cfg_save_lock:
            with self._lock:
                self._cfg.update(patch)
                if 'mappings' in patch:
                    new_map = dict(self._cfg.get('mappings', {}))
                    new_map.update(patch['mappings'])
                    self._cfg['mappings'] = new_map
                if 'device_profiles' in patch:
                    # Per-MAC merge: caller may pass {mac: new_full_profile}
                    # or {mac: {field_to_update: value}}. We merge at the
                    # per-MAC level (replace the whole profile is intended
                    # behavior — admins delete profiles via DELETE endpoint
                    # which sends {device_profiles: <without that mac>}).
                    new_profiles = dict(self._cfg.get('device_profiles', {}) or {})
                    incoming = patch['device_profiles'] or {}
                    # If incoming has FEWER macs than current → it's a
                    # full-replace (delete intent). If same set of macs +
                    # at least one with fewer fields → per-MAC merge.
                    if set(incoming.keys()) >= set(new_profiles.keys()):
                        # Same or more MACs → merge per-MAC field-by-field
                        for mac, profile_patch in incoming.items():
                            existing = new_profiles.get(mac, {})
                            if isinstance(existing, dict) and isinstance(profile_patch, dict):
                                merged = dict(existing)
                                merged.update(profile_patch)
                                new_profiles[mac] = merged
                            else:
                                new_profiles[mac] = profile_patch
                    else:
                        # Fewer MACs → full replace (operator deleted a profile)
                        new_profiles = dict(incoming)
                    self._cfg['device_profiles'] = new_profiles
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
    # Custom mappings — per-device profiles
    # ------------------------------------------------------------------

    def _ensure_device_profile(self, mac: str, name: str) -> None:
        """Idempotently create a profile entry for this MAC if absent.
        Updates last_seen on every call. Persists via update_cfg (atomic
        write + lock). Safe to call from the reconnect thread."""
        if not mac:
            return
        now = int(time.time())
        # Snapshot current profiles dict under no lock — update_cfg takes
        # both locks anyway. The read can race with a concurrent
        # update_cfg writer but in the worst case we end up writing a
        # slightly-stale snapshot — update_cfg's own merge in mappings
        # path doesn't apply to device_profiles so we replace wholesale.
        profiles = dict(self._cfg.get('device_profiles', {}) or {})
        existing = profiles.get(mac) or {}
        # Preserve operator-defined custom mappings + label across reconnects.
        custom = existing.get('custom_button_mappings', [])
        if not isinstance(custom, list):
            custom = []
        profile_type = existing.get('type') or self._cfg.get('gamepad_type', 'ps')
        # Only update name if we got a usable one — avoid overwriting a
        # nicely-typed BT name with an empty string from evdev.
        profile_name = (name or existing.get('name') or '')[:64]
        profiles[mac] = {
            'name': profile_name,
            'type': profile_type,
            'last_seen': now,
            'custom_button_mappings': custom,
        }
        self.update_cfg({'device_profiles': profiles})

    def get_active_device_mac(self) -> str | None:
        """Returns the MAC (uppercase, colon-separated) of the currently
        connected controller, or None if no device is connected."""
        return self._active_device_mac

    def get_device_profiles(self) -> dict:
        """Returns a shallow copy of all known device profiles. Caller
        must not mutate the returned dict in place."""
        return dict(self._cfg.get('device_profiles', {}) or {})

    def enter_capture_mode(self, duration_s: float = 10.0) -> bool:
        """Begin a button-capture window for the operator to press a
        button on the connected controller, latching its code name for
        binding to a custom mapping.

        Returns True if capture started, False if already in flight or
        BT is disabled (no buttons would arrive).
        H1 fix 2026-05-16: all capture state under _capture_lock."""
        with self._capture_lock:
            if self._capture_mode:
                return False
            if not self.is_enabled():
                return False
            self._capture_mode = True
            self._capture_result = None
            self._capture_expires_at = time.monotonic() + float(duration_s)
        log.info("BT capture mode: listening for %.1fs", duration_s)
        return True

    def get_capture_state(self) -> dict:
        """Returns the current capture state for polling from the UI.
        Side effect: transitions from 'listening' to 'expired' when the
        deadline passes — polling drives the state machine forward.
        H1 fix 2026-05-16: atomic snapshot under _capture_lock so two
        admin tabs can't observe inconsistent state mid-mutation."""
        with self._capture_lock:
            if self._capture_result is not None:
                return {'state': 'captured', 'button': self._capture_result, 'remaining_ms': 0}
            if not self._capture_mode:
                return {'state': 'idle', 'button': None, 'remaining_ms': 0}
            remaining = max(0.0, self._capture_expires_at - time.monotonic())
            if remaining <= 0:
                self._capture_mode = False
                return {'state': 'expired', 'button': None, 'remaining_ms': 0}
            return {'state': 'listening', 'button': None, 'remaining_ms': int(remaining * 1000)}

    def cancel_capture(self) -> None:
        """Operator pressed Cancel in the UI — drop the capture window.
        H1 fix 2026-05-16: under _capture_lock."""
        with self._capture_lock:
            self._capture_mode = False
            self._capture_result = None

    # ------------------------------------------------------------------
    # Device detection
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_device_mac(dev) -> str | None:
        """Best-effort MAC resolution for an evdev gamepad.

        Order: dev.uniq (HID descriptor) → bluetoothctl Connected name
        match. Many controllers (NVIDIA Shield, several 8BitDo models)
        don't expose uniq via evdev, so the bluetoothctl fallback is
        what keeps per-device profiles stable across reconnects.

        Returns canonical uppercase colon-separated MAC, or None.
        """
        _MAC_RE = re.compile(r'([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})')
        # Path 1: HID-advertised uniq (PS4/PS5 + most Xbox One BT firmwares)
        uniq = (getattr(dev, 'uniq', '') or '').strip()
        m = _MAC_RE.fullmatch(uniq) if uniq else None
        if m:
            return m.group(1).upper()
        # Path 2: bluetoothctl Connected list, match by device name
        try:
            out = subprocess.run(
                ['bluetoothctl', 'devices', 'Connected'],
                capture_output=True, text=True, timeout=2
            ).stdout or ''
        except Exception:
            out = ''
        dev_name = (getattr(dev, 'name', '') or '').strip()
        if not dev_name:
            return None
        candidates: list[tuple[str, str]] = []
        for line in out.splitlines():
            parts = line.split(None, 2)
            if len(parts) >= 3 and parts[0] == 'Device':
                mac = parts[1].upper()
                name = parts[2].strip()
                if _MAC_RE.fullmatch(mac) and (
                    name == dev_name or name.startswith(dev_name[:24])
                ):
                    candidates.append((mac, name))
        if len(candidates) == 1:
            return candidates[0][0]
        # Multiple matches — prefer exact name equality (audit LOW 2026-05-16:
        # two same-model controllers connected at once would otherwise bind
        # to the first listed MAC, swapping per-device profiles).
        exact = [c for c in candidates if c[1] == dev_name]
        if len(exact) == 1:
            return exact[0][0]
        if candidates:
            log.warning(
                "BT MAC resolve ambiguous for %r: %s — per-device profile "
                "won't bind until disambiguated", dev_name,
                [c[0] for c in candidates]
            )
        return None

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
                    # Resolve MAC BEFORE acquiring self._lock — bluetoothctl
                    # subprocess can block up to 2s, and self._lock is the
                    # same lock held by _do_drive / keep-alive / motion
                    # snapshot. MotionWatchdog cuts drive at 800ms — keeping
                    # subprocess inside the lock could race-cut a live drive
                    # session on a slow BlueZ stack. dev is not yet published
                    # to other threads, so resolution is safe outside.
                    # (Audit MEDIUM 2026-05-16: lock-held subprocess fix.)
                    mac = self._resolve_device_mac(dev)
                    with self._lock:
                        self._device      = dev
                        self._connected   = True
                        self._device_name = dev.name[:32]
                        self._prev_btns   = {}
                        # Per-device profile dict key — stable across
                        # reconnects via uniq (PS/Xbox) or bluetoothctl
                        # name-match fallback (NVIDIA Shield, 8BitDo).
                        self._active_device_mac = mac
                    # B2 fix 2026-05-16: clear stale inactivity pause flag
                    # left over from previous session (operator powered
                    # down a paused controller — flag persisted across
                    # the disconnect → UI lied about "BT idle" after
                    # reconnect until next physical input timeout).
                    self._inactivity_pause = False
                    self._last_input_t = time.time()
                    # Idempotently create/refresh the device profile so the
                    # UI's "known devices" list reflects this controller
                    # even before the operator binds anything.
                    if self._active_device_mac:
                        try:
                            self._ensure_device_profile(self._active_device_mac, dev.name)
                        except Exception:
                            log.exception("ensure_device_profile failed")
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

            # H6 fix 2026-05-16: generation tracking — flaky controller
            # reconnects spawned cumulative _hw_poll_loop threads (each
            # sleeping 30s between subprocess calls). Old threads now
            # exit when self._hw_poll_gen != their captured gen.
            self._hw_poll_gen = getattr(self, '_hw_poll_gen', 0) + 1
            my_gen = self._hw_poll_gen
            threading.Thread(target=self._hw_poll_loop, args=(my_gen,),
                             daemon=True, name=f'bt-hw-poll-{my_gen}').start()

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
                # Custom mappings: drop active MAC so post-disconnect
                # _handle_button paths can't index a stale profile.
                # Cancel any in-flight button-capture session — the
                # controller it was listening to is gone.
                self._active_device_mac = None
                self._capture_mode = False
                self._capture_result = None
            if old_dev is not None:
                try: old_dev.close()
                except Exception: pass
            self._stop_motion()

    def _hw_poll_loop(self, my_gen: int = 0) -> None:
        """Polls RSSI and battery level every 30s via upower/sysfs.

        H6 fix 2026-05-16: my_gen param — old generations exit when
        a newer reconnect spawns a fresh poll loop. Prevents thread
        accumulation across flaky controller reconnect cycles."""
        import subprocess, re, glob as _glob
        while (self._connected and not self._stop_evt.is_set()
               and (my_gen == 0 or my_gen == getattr(self, '_hw_poll_gen', 0))):
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

        # CAPTURE MODE — operator is binding a button to a custom mapping.
        # H1 fix 2026-05-16: under _capture_lock so concurrent get_capture_state
        # from a Flask thread observes consistent state.
        # M1 fix 2026-05-16: alias-aware E-STOP filter — evdev returns alias
        # tuples (e.g. ['BTN_B','BTN_EAST']). If estop_code is ANYWHERE in
        # the tuple, refuse to capture (don't just check code_names[0]).
        # Prevents dead-button footgun on controllers that emit E-STOP as
        # an aliased keycode.
        if self._capture_mode and pressed and event.type == ecodes.EV_KEY:
            estop_code = m.get('estop', 'BTN_MODE')
            with self._capture_lock:
                if self._capture_mode and code_names and estop_code not in code_names:
                    self._capture_result = code_names[0]
                    self._capture_mode = False
                    log.info("BT capture: latched %s", code_names[0])
            return  # consume — do NOT fall through to action dispatch

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

        # CUSTOM MAPPINGS — operator-defined per-device. Only action
        # dispatch path remaining since 2026-05-16 (legacy panel_dome /
        # panel_body / audio branches removed — operator binds those
        # via 🎯 CAPTURE NEW BUTTON instead). Rising-edge only.
        if pressed and self._active_device_mac:
            profile = (self._cfg.get('device_profiles', {}) or {}).get(self._active_device_mac, {})
            custom = profile.get('custom_button_mappings', []) or []
            for cm in custom:
                if not isinstance(cm, dict):
                    continue
                bound = cm.get('button')
                if bound and bound in code_names:
                    self._fire_custom_mapping(cm, reg)
                    return  # consume — do NOT fall through to legacy dispatch

        # Legacy fixed-action branches (panel_dome / panel_body / audio)
        # removed 2026-05-16. All actions now go through Custom Button
        # Mappings (per-MAC, configured via 🎯 CAPTURE NEW BUTTON in
        # the BT Gamepad panel). E-STOP remains the only hardcoded
        # action — see the _is(estop) branch above. The legacy mapping
        # KEYS in self._cfg['mappings'] are kept for backward compat
        # but no longer dispatched here.

    def _fire_custom_mapping(self, cm: dict, reg) -> None:
        """Dispatch a custom mapping via the shared dispatch_action helper.

        Uses the cm['id'] as a synthetic 'sid' for per-id debounce parity
        with Shortcuts (B5/P2 pattern). Each mapping gets its own lock so
        rapid autorepeats / re-press cannot double-fire while a previous
        dispatch is in flight (some controllers send a key-down twice on
        bouncy buttons).

        Lazy-imports dispatch_action to avoid a circular import at module
        load (shortcuts_bp transitively imports registry which constructs
        BTControllerDriver during boot)."""
        sid = f"btmap:{cm.get('id', 'unknown')}"
        action = cm.get('action', {}) or {}
        a_type = action.get('type', 'none')
        a_target = action.get('target', '') or ''

        # Per-id debounce — mirrors shortcuts B5/P2. 150ms is well under
        # any reasonable operator double-tap but eats hardware bounce.
        now = time.monotonic()
        last = self._custom_last_ts.get(sid, 0.0)
        if (now - last) < 0.15:
            return
        self._custom_last_ts[sid] = now

        # Per-id non-blocking lock — if a previous dispatch is still
        # running, drop this press. Prevents double-fire on autorepeat
        # without serializing all custom-mapping presses behind one lock.
        lk = self._custom_locks.setdefault(sid, threading.Lock())
        if not lk.acquire(blocking=False):
            return
        try:
            # Lazy import to dodge circular import at module load time.
            from master.api.shortcuts_bp import dispatch_action
            new_state, err, _http = dispatch_action(sid, a_type, a_target)
            if err:
                log.warning("BT custom mapping refused: %s (%s/%s)",
                            err, a_type, a_target)
            else:
                log.info("BT custom mapping fired: %s/%s → %s",
                         a_type, a_target, new_state)
        except Exception:
            log.exception("BT custom mapping dispatch crashed")
        finally:
            lk.release()

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
            # B7 fix 2026-05-16: use _do_estop() helper instead of
            # system_estop() — the latter calls jsonify() which raises
            # RuntimeError outside Flask app context. The old fallback
            # only froze dome + sent FREEZE; it did NOT stop choreo,
            # audio, or lights — making BT-triggered E-STOP functionally
            # weaker than the HTTP path.
            from master.api.status_bp import _do_estop
            _do_estop()
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
        # Batch 3 fix 2026-05-16: apply per-mode dome speed cap to keep
        # BT input parity with web /motion/dome/turn (uses _dome_cap()).
        # Kids = kids_speed_limit · Child = child_dome_speed_limit (slower).
        mode = getattr(reg, 'lock_mode', 0)
        if mode == 1:
            cap = float(getattr(reg, 'kids_speed_limit', 0.5))
            speed = max(-1.0, min(1.0, speed * cap))
        elif mode == 2:
            cap = float(getattr(reg, 'child_dome_speed_limit', 0.3))
            speed = max(-1.0, min(1.0, speed * cap))
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
