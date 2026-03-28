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


def _interpolate(t_now: float, keyframes: list) -> float:
    """Interpolate angle from keyframe list at time t_now."""
    if not keyframes:
        return 0.0
    if t_now <= keyframes[0]['t']:
        return float(keyframes[0]['angle'])
    if t_now >= keyframes[-1]['t']:
        return float(keyframes[-1]['angle'])
    for i in range(len(keyframes) - 1):
        kf0, kf1 = keyframes[i], keyframes[i + 1]
        if kf0['t'] <= t_now <= kf1['t']:
            span = kf1['t'] - kf0['t']
            if span <= 0:
                return float(kf1['angle'])
            progress = _ease((t_now - kf0['t']) / span, kf1.get('easing', 'linear'))
            return kf0['angle'] + (kf1['angle'] - kf0['angle']) * progress
    return float(keyframes[-1]['angle'])


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

        self._audio      = audio
        self._teeces     = teeces
        self._dome_motor = dome_motor
        self._dome_servo = dome_servo
        self._body_servo = body_servo
        self._vesc       = vesc
        self._telem_getter = telem_getter

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
        self._safe_stop_all()
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

        # Audio — NOT shifted (audio fires first, everything else follows)
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

        # Servos — shifted
        for ev in tracks.get('servos', []):
            events.append({**ev, 'track': 'servos', 't': ev['t'] + lat})

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
        dome_kf  = tracks.get('dome', [])

        ev_idx      = 0
        last_angle  = float(dome_kf[0]['angle']) if dome_kf else 0.0
        last_dome_t = 0.0

        with self._status_lock:
            self._status.update({'playing': True, 'name': name, 'duration': duration, 't_now': 0.0})

        t_start = time.monotonic()

        while not self._stop_flag.is_set():
            t_now = time.monotonic() - t_start

            # Fire all discrete events whose time has arrived
            while ev_idx < len(events) and events[ev_idx]['t'] <= t_now:
                self._dispatch(events[ev_idx])
                ev_idx += 1

            # Update dome (continuous interpolation → motor speed)
            if dome_kf:
                target = _interpolate(t_now, dome_kf)
                dt = t_now - last_dome_t
                if dt > 0:
                    delta = target - last_angle
                    if abs(delta) > 0.5:
                        speed = max(-1.0, min(1.0, (delta / 360.0) / dt))
                        if self._dome_motor:
                            try:
                                self._dome_motor.set_speed(speed)
                            except Exception as e:
                                log.warning(f"Choreo dome error: {e}")
                    elif abs(delta) < 0.2 and self._dome_motor:
                        try:
                            self._dome_motor.set_speed(0.0)
                        except Exception:
                            pass
                last_angle  = target
                last_dome_t = t_now

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
                    self._audio.play(ev['file'])
                elif ev['action'] == 'stop':
                    self._audio.stop()

            elif track == 'lights':
                if not self._teeces:
                    return
                mode = ev.get('mode') or ev.get('name', 'random')
                _LIGHT_CMDS = {
                    'random':   '0T1\r',
                    'leia':     '0T6\r',
                    'alarm':    '0T3\r',
                    'flash':    '0T2\r',
                    'disco':    '0T13\r',
                    'off':      '0T20\r',
                    'scream':   '0T5\r',
                    'imperial': '0T11\r',
                }
                cmd = _LIGHT_CMDS.get(mode, '0T1\r')
                self._teeces.send_command(cmd)

            elif track == 'servos':
                action = ev.get('action', 'open')
                servo  = ev.get('servo', '')
                if not self._dome_servo and not self._body_servo:
                    return
                if servo in ('all', 'all_dome') and self._dome_servo:
                    if action == 'open':
                        self._dome_servo.open_all()
                    else:
                        self._dome_servo.close_all()
                elif self._dome_servo:
                    if action == 'open':
                        self._dome_servo.open(servo)
                    else:
                        self._dome_servo.close(servo)

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
        for fn in [
            lambda: self._audio.stop() if self._audio else None,
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
