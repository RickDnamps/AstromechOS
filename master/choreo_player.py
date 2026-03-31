"""
ChoreoPlayer — R2-D2 Choreography Timeline Engine.
Reads .chor JSON files and dispatches events to drivers in real time.
"""
import json
import logging
import os
import threading
import time

log = logging.getLogger(__name__)

TICK = 0.05  # 50ms loop — smooth enough for dome interpolation

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
                 body_servo, vesc=None, telem_getter=None, audio_latency=None,
                 engine=None):
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

        self._audio      = audio
        self._teeces     = teeces
        self._dome_motor = dome_motor
        self._dome_servo = dome_servo
        self._body_servo = body_servo
        self._vesc       = vesc
        self._telem_getter = telem_getter
        self._engine     = engine

        # Threshold config
        if cfg is not None:
            self._telem_check_interval = cfg.getfloat('choreo', 'telem_check_interval', fallback=0.5)
            self._uart_fail_threshold  = cfg.getint('choreo',   'uart_fail_threshold',  fallback=3)
            self._vesc_min_voltage     = cfg.getfloat('choreo', 'vesc_min_voltage',     fallback=20.0)
            self._vesc_max_temp        = cfg.getfloat('choreo', 'vesc_max_temp',        fallback=80.0)
            self._vesc_max_current     = cfg.getfloat('choreo', 'vesc_max_current',     fallback=30.0)
        else:
            self._telem_check_interval = 0.5
            self._uart_fail_threshold  = 3
            self._vesc_min_voltage     = 20.0
            self._vesc_max_temp        = 80.0
            self._vesc_max_current     = 30.0

        # Runtime state — reset on each play()
        self._drive_fail_count: int       = 0
        self._abort_reason: str | None    = None
        self._last_telem: dict | None     = None
        self._last_telem_check: float     = 0.0

        self._stop_flag  = threading.Event()
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

    def play(self, chor: dict) -> bool:
        """Start playback of a chor dict. Returns False if already playing."""
        if self.is_playing():
            log.warning("ChoreoPlayer: already playing, stop first")
            return False
        self._drive_fail_count = 0
        self._abort_reason     = None
        self._last_telem       = None
        self._last_telem_check = 0.0
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

        # Audio tracks — NOT shifted (audio fires first, everything else follows)
        for ev in tracks.get('audio', []):
            events.append({**ev, 'track': 'audio'})
        for ev in tracks.get('audio2', []):
            events.append({**ev, 'track': 'audio2'})

        # Lights — shifted; auto-restore to random at end of each block
        for ev in tracks.get('lights', []):
            events.append({**ev, 'track': 'lights', 't': ev['t'] + lat})
            if 'duration' in ev:
                events.append({
                    'track': 'lights', 't': ev['t'] + ev['duration'] + lat,
                    'action': 'mode', 'mode': 'random', '_auto_restore': True,
                })

        # Dome — shifted; auto-stop always injected after duration (ms → seconds)
        # Fail-safe: events without a valid duration get a 50ms burst to prevent infinite rotation
        for ev in tracks.get('dome', []):
            events.append({**ev, 'track': 'dome', 't': ev['t'] + lat})
            dur_ms = ev.get('duration', 0)
            if not dur_ms or dur_ms <= 0:
                dur_ms = 50   # fail-safe burst — no open-ended motor command
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

    def _dispatch(self, ev: dict) -> None:
        try:
            track = ev['track']

            if track == 'audio':
                if not self._audio:
                    return
                if ev['action'] == 'play':
                    self._audio.send('S', ev.get('file', ''))
                elif ev['action'] == 'stop':
                    self._audio.send('S', 'STOP')

            elif track == 'audio2':
                if not self._audio:
                    return
                if ev['action'] == 'play':
                    self._audio.send('S2', ev.get('file', ''))
                elif ev['action'] == 'stop':
                    self._audio.send('S2', 'STOP')

            elif track == 'dome':
                if not self._dome_motor:
                    return
                power_val = float(ev.get('power', 0.0))
                speed = max(-1.0, min(1.0, power_val / 100.0))
                self._dome_motor.set_speed(speed)

            elif track == 'lights':
                mode = ev.get('mode') or ev.get('name', 'random')

                # Text mode — send scrolling message to FLD/RLD via JawaLite
                if mode == 'text' and self._teeces:
                    text_val = ev.get('text', '')[:20].upper()
                    display  = ev.get('display', 'fld')
                    if display in ('fld', 'both'):
                        self._teeces.fld_text(text_val)
                    if display in ('rld', 'both'):
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
                        log.debug(f"Choreo lights: unknown mode '{mode}' — trying as .lseq")
                        if self._engine:
                            try:
                                self._engine.run_light(mode, loop=False)
                            except Exception as e:
                                log.warning(f"Choreo lights .lseq '{mode}': {e}")
                elif self._engine:
                    try:
                        self._engine.run_light(mode, loop=False)
                    except Exception as e:
                        log.warning(f"Choreo lights .lseq '{mode}': {e}")

            elif track == 'servos':
                action  = ev.get('action', 'open')
                servo   = ev.get('servo', '')
                target  = ev.get('target')
                dur_s   = float(ev.get('duration', 0) or 0)
                easing  = ev.get('easing', 'ease-in-out')

                is_body     = servo.startswith('body_')
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
            lambda: self._audio.send('S', 'STOP') if self._audio else None,
            lambda: self._audio.send('S2', 'STOP') if self._audio else None,
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
            if mode == 'text':
                text_val = ev.get('text', '')[:20].upper()
                display  = ev.get('display', 'fld')
                cmd = f"teeces,text,{text_val},{display}"
            else:
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
