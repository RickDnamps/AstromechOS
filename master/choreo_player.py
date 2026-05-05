"""
ChoreoPlayer — R2-D2 Choreography Timeline Engine.
Reads .chor JSON files and dispatches events to drivers in real time.
"""
import configparser
import json
import logging
import os
import re as _re
import threading
import time

log = logging.getLogger(__name__)

TICK = 0.05  # 50ms loop — smooth enough for dome interpolation

_DOME_ANGLES_PATH = '/home/artoo/r2d2/master/config/dome_angles.json'
_BODY_ANGLES_PATH = '/home/artoo/r2d2/slave/config/servo_angles.json'
_LOCAL_CFG        = '/home/artoo/r2d2/master/config/local.cfg'

_SERVO_SPECIAL = ('all', 'all_dome', 'all_body')

# Delay between body panel open and arm extension (and between arm close and panel close)
_ARM_PANEL_DELAY = 0.5


def _read_arm_entries() -> list:
    """Returns ordered list of (arm_servo_id, panel_servo_id_or_None, delay_s) for all configured arm slots."""
    cfg = configparser.ConfigParser()
    cfg.read(_LOCAL_CFG)
    count = cfg.getint('arms', 'count', fallback=0)
    result = []
    for i in range(1, count + 1):
        arm   = cfg.get('arms', f'arm_{i}',   fallback='').strip()
        panel = cfg.get('arms', f'panel_{i}', fallback='').strip()
        delay = max(0.1, min(5.0, cfg.getfloat('arms', f'delay_{i}', fallback=_ARM_PANEL_DELAY)))
        if arm:
            result.append((arm, panel or None, delay))
    return result


def _read_arm_panel_map() -> dict:
    """Returns {arm_servo_id: panel_servo_id} — backward compat for legacy .chor events with servo: field."""
    return {arm: panel for arm, panel, _delay in _read_arm_entries() if panel}


def _normalise_label(s: str) -> str:
    """Lower-case, replace spaces/hyphens with underscores."""
    return _re.sub(r'[\s\-]+', '_', s.strip().lower())


def _build_label_map() -> dict:
    """
    Returns { normalised_label -> servo_id } for all configured servos.
    Used to resolve legacy label-based Choreo references.
    """
    result: dict = {}
    for path in (_DOME_ANGLES_PATH, _BODY_ANGLES_PATH):
        try:
            import json as _json
            with open(path) as f:
                data = _json.load(f)
            for servo_id, cfg in data.items():
                label = cfg.get('label', '')
                if label:
                    result[_normalise_label(label)] = servo_id
                # Also map the ID itself so both forms resolve
                result[_normalise_label(servo_id)] = servo_id
        except Exception as e:
            log.warning("ChoreoPlayer: could not load label map from %s: %s", path, e)
    return result

# ── Easing functions ─────────────────────────────────────────────────────────

_EASINGS = {
    'linear':      lambda t: t,
    'ease-in':     lambda t: t * t,
    'ease-out':    lambda t: 1.0 - (1.0 - t) ** 2,
    'ease-in-out': lambda t: 4 * t**3 if t < 0.5 else 1.0 - (-2 * t + 2)**3 / 2,
}


def _ease(t: float, name: str) -> float:
    """Apply named easing to progress value t ∈ [0, 1]. Clamps input."""
    t = max(0.0, min(1.0, t))
    return _EASINGS.get(name, _EASINGS['linear'])(t)



# ── ChoreoPlayer ──────────────────────────────────────────────────────────────

class ChoreoPlayer:
    """
    Real-time choreography player. Reads .chor JSON and fires events to drivers.
    All driver args may be None (for testing or when hardware is absent).
    """

    def __init__(self, cfg, audio, teeces, dome_motor, dome_servo,
                 body_servo, vesc=None, telem_getter=None, audio_latency=None):
        # Resolve audio latency: explicit arg > cfg > default
        if audio_latency is not None:
            self._latency = float(audio_latency)
        elif cfg is not None:
            self._latency = cfg.getfloat('choreo', 'audio_latency', fallback=0.10)
        else:
            self._latency = 0.10

        # Body servo UART compensation: advance body servo events by this amount
        # so the command arrives at the Slave in sync with dome servo I2C pulses.
        self._body_uart_lat = (
            cfg.getfloat('choreo', 'body_servo_uart_lat', fallback=0.025)
            if cfg is not None else 0.025
        )

        # Audio slot scheduler
        self._audio_channels: int = (
            cfg.getint('audio', 'audio_channels', fallback=6) if cfg is not None else 6
        )
        self._audio_slots: list[dict | None]             = [None] * self._audio_channels
        self._audio_timers: list[threading.Timer | None] = [None] * self._audio_channels

        self._audio      = audio
        self._teeces     = teeces
        self._dome_motor = dome_motor
        self._dome_servo = dome_servo
        self._body_servo = body_servo
        self._vesc       = vesc
        self._telem_getter = telem_getter
        self._label_map: dict = _build_label_map()
        self._resolved_logged: set = set()

        # Threshold config
        if cfg is not None:
            self._telem_check_interval = cfg.getfloat('choreo', 'telem_check_interval', fallback=0.5)
            self._uart_fail_threshold  = cfg.getint('choreo',   'uart_fail_threshold',  fallback=3)
            # vesc_min_voltage: derive from battery cell count (3.5V/cell) unless overridden in cfg
            _cells = cfg.getint('battery', 'cells', fallback=4)
            _default_min_v = _cells * 3.5
            self._vesc_min_voltage     = cfg.getfloat('choreo', 'vesc_min_voltage',     fallback=_default_min_v)
            self._vesc_max_temp        = cfg.getfloat('choreo', 'vesc_max_temp',        fallback=80.0)
            self._vesc_max_current     = cfg.getfloat('choreo', 'vesc_max_current',     fallback=30.0)
        else:
            self._telem_check_interval = 0.5
            self._uart_fail_threshold  = 3
            self._vesc_min_voltage     = 14.0   # 4S default (3.5V × 4); set [battery] cells in cfg for other packs
            self._vesc_max_temp        = 80.0
            self._vesc_max_current     = 30.0

        # Runtime state — reset on each play()
        self._drive_fail_count: int       = 0
        self._abort_reason: str | None    = None
        self._last_telem: dict | None     = None
        self._last_telem_check: float     = 0.0

        self._stop_flag  = threading.Event()
        self._loop       = False
        self._thread: threading.Thread | None = None
        self._servo_pos: dict[str, float] = {}   # last commanded angle per servo (for slew start)
        self._status_lock = threading.Lock()
        self._status = {
            'playing':      False,
            'name':         None,
            't_now':        0.0,
            'duration':     0.0,
            'abort_reason': None,
            'telem':        None,
        }

    def _resolve_servo_id(self, name: str) -> str:
        """
        Resolve a servo reference to a hardware ID.
        Accepts: hardware ID ('Servo_M0'), normalised label ('dome_panel_1'),
                 or special keywords ('all', 'all_dome', 'all_body').
        Returns the hardware ID, or the original string if unresolvable.
        """
        if name in _SERVO_SPECIAL:
            return name
        try:
            from master.drivers.dome_servo_driver import SERVO_MAP as _DOME_MAP
        except ImportError:
            _DOME_MAP = {f'Servo_M{i}': i for i in range(11)}
        try:
            from slave.drivers.body_servo_driver import SERVO_MAP as _BODY_MAP
        except ImportError:
            _BODY_MAP = {f'Servo_S{i}': i for i in range(11)}
        if name in _DOME_MAP or name in _BODY_MAP:
            return name
        resolved = self._label_map.get(_normalise_label(name))
        if resolved:
            if name not in self._resolved_logged:
                log.info("ChoreoPlayer: resolved servo label %r → %r", name, resolved)
                self._resolved_logged.add(name)
            return resolved
        log.warning("ChoreoPlayer: unknown servo ref %r — label map has no match", name)
        return name

    # ── Public API ────────────────────────────────────────────────────────────

    def setup(self) -> bool:
        """No hardware required — always succeeds."""
        return True

    def shutdown(self) -> None:
        self.stop()

    def is_playing(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def get_status(self) -> dict:
        with self._status_lock:
            return dict(self._status)

    def play(self, chor: dict, loop: bool = False) -> bool:
        """Start playback of a chor dict. Returns False if already playing."""
        if self.is_playing():
            log.warning("ChoreoPlayer: already playing, stop first")
            return False

        meta = chor.get('meta', {})
        required = meta.get('audio_channels_required', 0)
        if required > self._audio_channels:
            log.warning(
                "Choreo '%s' requires %d audio channels but system has %d — some sounds may be dropped.",
                meta.get('name', '?'), required, self._audio_channels,
            )

        self._loop             = loop
        self._drive_fail_count = 0
        self._abort_reason     = None
        self._last_telem       = None
        self._last_telem_check = 0.0
        self._audio_slots  = [None] * self._audio_channels
        self._audio_timers = [None] * self._audio_channels
        self._stop_flag.clear()
        self._thread = threading.Thread(
            target=self._run, args=(chor,),
            daemon=True, name="choreo-player",
        )
        self._thread.start()
        log.info(f"Choreo started: {chor['meta']['name']}")
        return True

    def stop(self) -> None:
        self._stop_flag.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        with self._status_lock:
            self._status.update({'playing': False, 't_now': 0.0})

    # ── Event queue ───────────────────────────────────────────────────────────

    def _build_event_queue(self, tracks: dict) -> list:
        """
        Flatten all track events into a sorted list.
        Non-audio events are shifted forward by self._latency seconds
        so the sound and actions are perceived as simultaneous.
        Auto-stop/restore events are inserted for blocks with 'duration'.
        """
        events = []
        lat = self._latency

        # Audio track — NOT shifted (audio fires first, everything else follows)
        # All blocks live in 'audio'; ch=0 → S: (primary), ch=1 → S2: (secondary)
        for ev in tracks.get('audio', []):
            events.append({**ev, 'track': 'audio'})

        # Lights — shifted; auto-restore to random at end of each block
        for ev in tracks.get('lights', []):
            events.append({**ev, 'track': 'lights', 't': ev['t'] + lat})
            if 'duration' in ev:
                events.append({
                    'track': 'lights', 't': ev['t'] + ev['duration'] + lat,
                    'action': 'mode', 'mode': 'random', '_auto_restore': True,
                })

        # Dome — shifted; auto-stop always injected after duration (ms → seconds)
        # Overlap guard: cap each event's duration to the start of the next dome
        # event so two commands never run simultaneously (defensive — works even
        # if the .chor file was authored with overlapping timestamps).
        # Fail-safe: events without a valid duration get a 50ms burst to prevent
        # infinite rotation.
        dome_evs = tracks.get('dome', [])
        for i, ev in enumerate(dome_evs):
            events.append({**ev, 'track': 'dome', 't': ev['t'] + lat})
            dur_ms = ev.get('duration', 0)
            if not dur_ms or dur_ms <= 0:
                dur_ms = 50   # fail-safe burst — no open-ended motor command
            # Cap duration to avoid overlapping with the next dome event
            if i + 1 < len(dome_evs):
                gap_ms = (dome_evs[i + 1]['t'] - ev['t']) * 1000.0
                if 0 < gap_ms < dur_ms:
                    dur_ms = gap_ms
                    log.debug('Dome overlap clamped: ev[%d] t=%.3fs dur capped to %.0fms', i, ev['t'], dur_ms)
            events.append({
                'track': 'dome', 'power': 0.0,
                't': ev['t'] + (dur_ms / 1000.0) + lat,
                '_auto_stop': True,
            })

        # Servos — shifted
        # dome_servos: direct I2C on Master → no extra compensation
        # body_servos / arm_servos: travel via UART to Slave → fire early by body_uart_lat
        # legacy 'servos' track: detect by servo name prefix
        body_adv = self._body_uart_lat
        for ev in tracks.get('dome_servos', []):
            events.append({**ev, 'track': 'servos', 't': ev['t'] + lat})
        for ev in tracks.get('body_servos', []):
            events.append({**ev, 'track': 'servos', 't': max(0.0, ev['t'] + lat - body_adv)})
        for ev in tracks.get('arm_servos', []):
            events.append({**ev, 'track': 'servos', 't': max(0.0, ev['t'] + lat - body_adv)})
        for ev in tracks.get('servos', []):
            is_body = ev.get('servo', '').startswith('body_') or ev.get('servo', '').startswith('arm_')
            shift = body_adv if is_body else 0.0
            events.append({**ev, 'track': 'servos', 't': max(0.0, ev['t'] + lat - shift)})

        # Propulsion — shifted; auto-stop at end of each block
        for ev in tracks.get('propulsion', []):
            events.append({**ev, 'track': 'propulsion', 't': ev['t'] + lat})
            if 'duration' in ev:
                events.append({
                    'track': 'propulsion', 't': ev['t'] + ev['duration'] + lat,
                    'action': 'stop',
                })

        return sorted(events, key=lambda e: e['t'])

    # ── Playback loop ─────────────────────────────────────────────────────────

    def _run(self, chor: dict):
        tracks   = chor['tracks']
        name     = chor['meta']['name']
        duration = float(chor['meta']['duration'])
        events   = self._build_event_queue(tracks)
        # Read arm→panel associations once per playback (picks up Settings changes)
        self._arm_panel_map = _read_arm_panel_map()

        ev_idx = 0

        with self._status_lock:
            self._status.update({'playing': True, 'name': name, 'duration': duration, 't_now': 0.0})

        t_start = time.monotonic()

        while not self._stop_flag.is_set():
            t_now = time.monotonic() - t_start

            # Fire all discrete events whose time has arrived
            while ev_idx < len(events) and events[ev_idx]['t'] <= t_now:
                self._dispatch(events[ev_idx])
                ev_idx += 1

            # Check telemetry thresholds
            if self._telem_getter and not self._stop_flag.is_set():
                if t_now - self._last_telem_check >= self._telem_check_interval:
                    self._check_telem()
                    self._last_telem_check = t_now

            # Update status
            with self._status_lock:
                self._status['t_now'] = round(t_now, 3)
                self._status['telem'] = self._last_telem

            if t_now >= duration:
                if self._loop and not self._stop_flag.is_set():
                    log.info(f"Choreo '{name}' looping")
                    t_start = time.monotonic()
                    ev_idx  = 0
                    continue
                log.info(f"Choreo '{name}' finished")
                break

            self._stop_flag.wait(timeout=TICK)

        self._safe_stop_all()
        with self._status_lock:
            self._status.update({
                'playing':      False,
                't_now':        0.0,
                'abort_reason': self._abort_reason,
                'telem':        self._last_telem,
            })

    def _release_slot(self, i: int) -> None:
        """Cancel the release timer and mark slot i as free."""
        if 0 <= i < len(self._audio_timers) and self._audio_timers[i]:
            self._audio_timers[i].cancel()
            self._audio_timers[i] = None
        if 0 <= i < len(self._audio_slots):
            self._audio_slots[i] = None

    def _assign_audio_slot(self, priority: str) -> int | None:
        """
        Return a free slot index, evicting the best candidate if all slots are busy.
        Eviction order: low (oldest first) → normal (oldest first) → never high.
        Returns None if all slots are high-priority (new sound is dropped).
        """
        # 1. Free slot
        for i, s in enumerate(self._audio_slots):
            if s is None:
                return i
        # 2. Evict by priority
        for evict_pri in ('low', 'normal'):
            candidates = [
                (i, s) for i, s in enumerate(self._audio_slots)
                if s is not None and s['priority'] == evict_pri
            ]
            if candidates:
                i, _ = min(candidates, key=lambda x: x[1]['started_at'])
                cmd = 'S' if i == 0 else f'S{i + 1}'
                if self._audio:
                    self._audio.send(cmd, 'STOP')
                self._release_slot(i)
                return i
        # 3. All high — drop
        log.warning(
            "ChoreoPlayer: all %d audio slots are High-priority — sound dropped",
            self._audio_channels,
        )
        return None

    def _dispatch(self, ev: dict) -> None:
        try:
            track = ev['track']

            if track == 'audio':
                if not self._audio:
                    return
                if ev['action'] == 'play':
                    priority = ev.get('priority', 'normal').lower()
                    slot = self._assign_audio_slot(priority)
                    if slot is None:
                        return  # all slots High — sound dropped
                    cmd = 'S' if slot == 0 else f'S{slot + 1}'
                    volume = ev.get('volume')
                    file_val = ev.get('file', '')
                    if volume is not None:
                        file_val = f"{file_val}:{int(volume)}"
                    self._audio.send(cmd, file_val)
                    duration = ev.get('duration')
                    self._audio_slots[slot] = {
                        'sound':      ev.get('file', ''),
                        'started_at': time.monotonic(),
                        'priority':   priority,
                        'duration':   duration,
                    }
                    if duration:
                        t = threading.Timer(float(duration), self._release_slot, args=(slot,))
                        t.daemon = True
                        self._audio_timers[slot] = t
                        t.start()
                elif ev['action'] == 'stop':
                    file_to_stop = ev.get('file')
                    for i, s in enumerate(self._audio_slots):
                        if s is None:
                            continue
                        if file_to_stop is None or s['sound'] == file_to_stop:
                            cmd = 'S' if i == 0 else f'S{i + 1}'
                            self._audio.send(cmd, 'STOP')
                            self._release_slot(i)

            elif track == 'dome':
                if not self._dome_motor:
                    return
                power_val = float(ev.get('power', 0.0))
                speed = max(-1.0, min(1.0, power_val / 100.0))
                self._dome_motor.set_speed(speed)

            elif track == 'lights':
                mode = ev.get('mode') or ev.get('name', 'random')

                # PSI mode — FPSI/RPSI sequence control
                if mode == 'psi':
                    target   = ev.get('target', 'both')
                    sequence = ev.get('sequence', 'normal')
                    if self._teeces and hasattr(self._teeces, 'psi_seq'):
                        self._teeces.psi_seq(target, sequence)
                    elif self._teeces and hasattr(self._teeces, 'psi'):
                        # Teeces32 fallback: map to numeric mode
                        _TEECES_MAP = {'normal':1,'flash':1,'alarm':3,'redalert':3,'leia':1,'failure':1,'march':1}
                        self._teeces.psi(_TEECES_MAP.get(sequence, 1))
                    return

                # Holo projector mode — FHP/RHP/THP via @HP passthrough (AstroPixels+ only)
                if mode == 'holo':
                    if self._teeces and hasattr(self._teeces, 'holo'):
                        self._teeces.holo(ev.get('target', 'fhp'), ev.get('effect', 'on'))
                    return

                # Text mode — scrolling message to logic displays
                # display targets: fld_top | fld_bottom | fld_both | rld | all
                if mode == 'text' and self._teeces:
                    text_val = ev.get('text', '')[:20].upper()
                    display  = ev.get('display', 'fld_top')
                    if hasattr(self._teeces, 'text'):
                        # AstroPixels+: full target support
                        self._teeces.text(text_val, display)
                    else:
                        # Teeces32: no top/bottom split, map to fld/rld
                        if display in ('fld_top', 'fld_bottom', 'fld_both', 'all'):
                            self._teeces.fld_text(text_val)
                        if display in ('rld', 'all'):
                            self._teeces.rld_text(text_val)
                    return

                # Named → T-code lookup (backward compat for old .chor files)
                _NAMED_CODES: dict[str, int] = {
                    'random': 1,  'flash': 2,       'alarm': 3,   'short_circuit': 4,
                    'scream': 5,  'leia': 6,         'i_heart_u': 7, 'panel_sweep': 8,
                    'pulse_monitor': 9, 'star_wars': 10, 'imperial': 11, 'disco_timed': 12,
                    'disco': 13,  'rebel': 14,       'knight_rider': 15, 'test_white': 16,
                    'red_on': 17, 'green_on': 18,   'lightsaber': 19, 'off': 20,
                    'vu_timed': 21, 'vu': 92,
                }
                if self._teeces:
                    # Preferred format: 't1'..'t21', 't92'
                    if mode.startswith('t') and mode[1:].isdigit():
                        self._teeces.animation(int(mode[1:]))
                    elif mode in _NAMED_CODES:
                        self._teeces.animation(_NAMED_CODES[mode])
                    else:
                        log.warning(f"Choreo lights: unknown mode '{mode}' — ignored")

            elif track == 'servos':
                action  = ev.get('action', 'open')
                servo   = self._resolve_servo_id(ev.get('servo', ''))
                target  = ev.get('target')
                dur_s   = float(ev.get('duration', 0) or 0)
                easing  = ev.get('easing', 'ease-in-out')
                group   = ev.get('group', '')

                # Arm servo dispatch — new format uses arm index, old format uses servo ID
                if group == 'arms' and self._body_servo:
                    arm_idx = ev.get('arm')
                    if arm_idx is not None:
                        # New format: resolve arm slot index → servo + panel + delay
                        arm_entries = _read_arm_entries()
                        if arm_idx < 1 or arm_idx > len(arm_entries):
                            log.warning("Arm %d not configured (only %d arm(s) — skipping event)", arm_idx, len(arm_entries))
                            return
                        servo, panel, arm_delay = arm_entries[arm_idx - 1]
                    else:
                        # Legacy format: servo ID + panel from arm_panel_map, default delay
                        panel     = getattr(self, '_arm_panel_map', {}).get(servo)
                        arm_delay = _ARM_PANEL_DELAY

                    if panel:
                        if action == 'open':
                            try:
                                self._body_servo.open(panel)
                            except Exception:
                                log.exception("Arm panel open failed: %s", panel)
                            arm_servo  = servo
                            arm_driver = self._body_servo
                            def _delayed_arm_open(drv=arm_driver, s=arm_servo):
                                try:
                                    drv.open(s)
                                except Exception:
                                    log.exception("Delayed arm open failed: %s", s)
                            t = threading.Timer(arm_delay, _delayed_arm_open)
                            t.daemon = True
                            t.start()
                            return
                        elif action == 'close':
                            try:
                                self._body_servo.close(servo)
                            except Exception:
                                log.exception("Arm close failed: %s", servo)
                            def _delayed_panel_close(drv=self._body_servo, s=panel):
                                try:
                                    drv.close(s)
                                except Exception:
                                    log.exception("Delayed panel close failed: %s", s)
                            t = threading.Timer(arm_delay, _delayed_panel_close)
                            t.daemon = True
                            t.start()
                            return
                    # No panel — fall through to normal servo dispatch (arm only, no panel)

                is_body     = servo.startswith('body_') or servo.startswith('arm_') or servo.startswith('Servo_S')
                is_all_dome = servo in ('all', 'all_dome')
                is_all_body = servo == 'all_body'

                driver = self._body_servo if is_body else self._dome_servo
                if not driver:
                    return

                # Bulk dispatch — no slewing
                if is_all_dome and self._dome_servo:
                    if action == 'open':
                        self._dome_servo.open_all()
                    else:
                        self._dome_servo.close_all()
                    return
                if is_all_body:
                    return   # no open_all on body servo yet

                # Resolve target angle for 'degree' action or explicit target
                if target is not None:
                    angle = max(10.0, min(170.0, float(target)))
                else:
                    angle = None   # driver uses calibrated open/close angle

                # Duration-based slewing — runs in daemon thread, does not block event loop
                if dur_s > 0 and angle is not None:
                    start_a = float(self._servo_pos.get(servo, 20.0))
                    self._servo_pos[servo] = angle

                    def _slew(drv, name, a0, a1, dur, ease):
                        steps = max(3, int(dur * 25))   # ~40ms per step at 25 steps/s
                        for i in range(steps + 1):
                            prog = _ease(i / steps, ease)
                            a    = a0 + (a1 - a0) * prog
                            try:
                                drv.open(name, angle_deg=a, speed=10)
                            except Exception:
                                pass
                            if i < steps:
                                time.sleep(dur / steps)

                    threading.Thread(
                        target=_slew,
                        args=(driver, servo, start_a, angle, dur_s, easing),
                        daemon=True,
                    ).start()
                    return

                # Instant dispatch (no duration or no explicit angle)
                if angle is not None:
                    driver.open(servo, angle_deg=angle)
                    self._servo_pos[servo] = angle
                elif action == 'open':
                    driver.open(servo)
                else:
                    driver.close(servo)

            elif track == 'propulsion':
                if not self._vesc:
                    return
                if ev.get('action') == 'stop':
                    self._vesc.drive(0.0, 0.0)
                    self._drive_fail_count = 0
                else:
                    ok = self._vesc.drive(
                        float(ev.get('left', 0.0)),
                        float(ev.get('right', 0.0)),
                    )
                    if ok:
                        self._drive_fail_count = 0
                    else:
                        self._drive_fail_count += 1
                        if self._drive_fail_count >= self._uart_fail_threshold:
                            log.error(
                                f"ChoreoPlayer: UART lost — {self._drive_fail_count} consecutive "
                                f"failures — ABORT [{self._status.get('name')}]"
                            )
                            self._abort_reason = 'uart_loss'
                            self._stop_flag.set()

        except Exception as e:
            log.error(f"Choreo dispatch error [{ev.get('track')} t={ev.get('t')}]: {e}")

    def _check_telem(self) -> None:
        """Read telemetry and abort if any threshold is exceeded."""
        try:
            telem = self._telem_getter()
        except Exception as e:
            log.warning(f"ChoreoPlayer: telem_getter error: {e}")
            return

        if telem is None:
            return

        self._last_telem = telem

        for side in ('L', 'R'):
            data = telem.get(side)
            if data is None:
                continue

            v_in    = data.get('v_in', 999.0)
            temp    = data.get('temp', 0.0)
            current = abs(data.get('current', 0.0))

            if v_in < self._vesc_min_voltage:
                log.error(
                    f"ChoreoPlayer: ABORT — undervoltage VESC {side}: "
                    f"{v_in}V < {self._vesc_min_voltage}V"
                )
                self._abort_reason = 'undervoltage'
                self._stop_flag.set()
                return

            if temp > self._vesc_max_temp:
                log.error(
                    f"ChoreoPlayer: ABORT — overheat VESC {side}: "
                    f"{temp}°C > {self._vesc_max_temp}°C"
                )
                self._abort_reason = 'overheat'
                self._stop_flag.set()
                return

            if current > self._vesc_max_current:
                log.error(
                    f"ChoreoPlayer: ABORT — overcurrent VESC {side}: "
                    f"{current}A > {self._vesc_max_current}A"
                )
                self._abort_reason = 'overcurrent'
                self._stop_flag.set()
                return

    def _safe_stop_all(self) -> None:
        # NOTE: self._audio is UARTController — use send(), NEVER .stop() (that closes serial)
        for fn in [
            *[
                (lambda cmd=('S' if i == 0 else f'S{i+1}'): self._audio.send(cmd, 'STOP') if self._audio else None)
                for i in range(self._audio_channels)
            ],
            lambda: [self._release_slot(i) for i in range(self._audio_channels)],
            lambda: self._teeces.all_off() if self._teeces else None,
            lambda: self._dome_motor.set_speed(0.0) if self._dome_motor else None,
            lambda: self._vesc.drive(0.0, 0.0) if self._vesc else None,
        ]:
            try:
                fn()
            except Exception:
                pass

    # ── SCR export ────────────────────────────────────────────────────────────

    def export_scr(self, chor: dict) -> str:
        """
        Convert a .chor dict to a sequential .scr string.
        Limitations (documented in output):
        - Dome keyframe interpolation → discrete dome,turn commands only
        - Servo easing → not preserved
        - Parallel tracks → collapsed to sequential
        """
        from datetime import date
        name = chor['meta']['name']
        tracks = chor['tracks']
        lines = [
            f"# Exported from {name}.chor — {date.today()}",
            "# WARNING: dome interpolation and servo easing not preserved in .scr format",
            "# Parallel tracks have been collapsed to sequential execution",
        ]

        _LIGHT_SCR = {
            'random':   'teeces,random',
            'leia':     'teeces,leia',
            'alarm':    'teeces,anim,3',
            'flash':    'teeces,anim,2',
            'disco':    'teeces,anim,13',
            'off':      'teeces,off',
            'scream':   'teeces,anim,5',
            'imperial': 'teeces,anim,11',
        }

        # Build flat event list (no latency shift for .scr — it's sequential)
        events = []
        for ev in tracks.get('audio', []):
            if ev.get('action') == 'play':
                events.append((ev['t'], f"sound,{ev['file']}"))
            elif ev.get('action') == 'stop':
                events.append((ev['t'], 'audio,stop'))

        for ev in tracks.get('audio2', []):
            if ev.get('action') == 'play':
                events.append((ev['t'], f"sound2,{ev['file']}"))
            elif ev.get('action') == 'stop':
                events.append((ev['t'], 'audio2,stop'))

        for ev in tracks.get('lights', []):
            mode = ev.get('mode', 'random')
            cmd = _LIGHT_SCR.get(mode, 'teeces,anim,1')
            events.append((ev['t'], cmd))
            if 'duration' in ev:
                events.append((ev['t'] + ev['duration'], 'teeces,random'))

        for ev in tracks.get('dome', []):
            # Dome keyframes → discrete turn commands (best effort)
            events.append((ev['t'], 'dome,turn,0.3'))

        for ev in tracks.get('servos', []):
            servo  = ev.get('servo', 'all')
            action = ev.get('action', 'open')
            events.append((ev['t'], f"servo,{servo},{action}"))

        for ev in tracks.get('propulsion', []):
            left  = ev.get('left', 0.0)
            right = ev.get('right', 0.0)
            dur_ms = int(ev.get('duration', 1.0) * 1000)
            events.append((ev['t'], f"motion,{left},{right},{dur_ms}"))
            if 'duration' in ev:
                events.append((ev['t'] + ev['duration'], 'motion,stop'))

        events.sort(key=lambda x: x[0])

        # Emit with sleep between events
        prev_t = 0.0
        for t, cmd in events:
            delta = round(t - prev_t, 2)
            if delta > 0.01:
                lines.append(f"sleep,{delta:.2f}")
            lines.append(cmd)
            prev_t = t

        return '\n'.join(lines) + '\n'
