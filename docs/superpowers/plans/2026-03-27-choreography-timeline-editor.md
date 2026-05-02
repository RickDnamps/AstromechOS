# Choreography Timeline Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a multi-track choreography system for R2-D2: a `.chor` JSON format, a `ChoreoPlayer` Python backend with real-time event dispatch, a REST API, and a timeline editor tab in the dashboard.

**Architecture:** Events are stored as absolute timestamps in a `.chor` JSON file. `ChoreoPlayer` runs a single daemon thread (50ms tick, `time.monotonic()` clock) that fires events to existing drivers. The dashboard gets a new protected tab with vanilla-JS drag/drop block editing.

**Tech Stack:** Python 3.10+ stdlib only (`json`, `time`, `threading`), Flask (already installed), vanilla JS (no new dependencies), pytest for tests.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `master/choreo_player.py` | **Create** | ChoreoPlayer class + easing functions + SCR exporter |
| `master/api/choreo_bp.py` | **Create** | Flask blueprint: play/stop/status/list/save/load/export_scr |
| `master/choreographies/cantina_show.chor` | **Create** | Working example choreography |
| `tests/test_choreo_player.py` | **Create** | Unit tests: event queue, timing, easing, interpolation, export |
| `master/config/main.cfg` | **Modify** | Add `[choreo]` section |
| `master/registry.py` | **Modify** | Add `choreo: ChoreoPlayer | None = None` |
| `master/flask_app.py` | **Modify** | Register `choreo_bp` |
| `master/main.py` | **Modify** | Instantiate `ChoreoPlayer`, assign `reg.choreo` |
| `master/templates/index.html` | **Modify** | Add CHOREO tab button + `tab-choreo` content div |
| `master/static/css/style.css` | **Modify** | Add `.chor-*` timeline styles |
| `master/static/js/app.js` | **Modify** | Add `choreoEditor` object + `loadChoreoTab()` |
| `android/app/src/main/assets/js/app.js` | **Modify** | Sync from master |
| `android/app/src/main/assets/css/style.css` | **Modify** | Sync from master |

---

## Task 1: Config + scaffolding

**Files:**
- Modify: `master/config/main.cfg`
- Create: `master/choreographies/` (directory + example file)
- Modify: `master/registry.py`

- [ ] **Step 1: Add `[choreo]` section to `main.cfg`**

Add at end of `master/config/main.cfg`:
```ini
[choreo]
audio_latency = 0.10
```

- [ ] **Step 2: Create `master/choreographies/` directory with a placeholder**

```bash
mkdir -p master/choreographies
```

- [ ] **Step 3: Create `master/choreographies/cantina_show.chor`**

```json
{
  "meta": {
    "name": "cantina_show",
    "version": "1.0",
    "duration": 45.2,
    "bpm": 120,
    "created": "2026-03-27",
    "author": "R2-D2 Control"
  },
  "tracks": {
    "audio": [
      { "t": 0.0, "action": "play", "file": "CANTINA", "volume": 85 },
      { "t": 45.0, "action": "stop" }
    ],
    "lights": [
      { "t": 0.0,  "duration": 4.5,  "action": "mode", "mode": "leia" },
      { "t": 4.5,  "duration": 2.5,  "action": "mode", "mode": "random" },
      { "t": 8.0,  "duration": 4.5,  "action": "mode", "mode": "alarm",
        "psi": { "c1": "#ff3355", "c2": "#000000", "speed": "fast" } },
      { "t": 15.0, "duration": 10.0, "action": "mode", "mode": "disco" }
    ],
    "dome": [
      { "t": 0.0,  "angle": 0,   "easing": "linear" },
      { "t": 5.0,  "angle": 180, "easing": "ease-in-out" },
      { "t": 10.0, "angle": 90,  "easing": "ease-out" },
      { "t": 20.0, "angle": 360, "easing": "ease-in" },
      { "t": 30.0, "angle": 0,   "easing": "ease-in-out" }
    ],
    "servos": [
      { "t": 3.0,  "servo": "dome_panel_1", "action": "open",  "duration": 0.5 },
      { "t": 6.0,  "servo": "all_dome",     "action": "open",  "duration": 0.3 },
      { "t": 10.0, "servo": "utility_arm",  "action": "open",  "easing": "ease-out", "duration": 2.0 },
      { "t": 20.0, "servo": "all",          "action": "close", "duration": 0.5 }
    ],
    "propulsion": [
      { "t": 20.0, "duration": 2.0, "left": 0.3,  "right": 0.3 },
      { "t": 24.0, "duration": 2.0, "left": 0.3,  "right": -0.3 },
      { "t": 26.0, "duration": 0.5, "left": 0.0,  "right": 0.0 }
    ],
    "markers": [
      { "t": 10.0, "label": "FACE DETECT TRIGGER", "type": "trigger" },
      { "t": 20.0, "label": "SWITCH TO AUTONOMOUS", "type": "mode_switch" }
    ]
  }
}
```

- [ ] **Step 4: Add `choreo` to `master/registry.py`**

After the `engine` line, add:
```python
# In the TYPE_CHECKING block, add:
#   from master.choreo_player import ChoreoPlayer

# After engine line (~line 53):
choreo: 'ChoreoPlayer | None' = None
```

Exact edit — after `engine: 'ScriptEngine | None' = None`:
```python
engine:      'ScriptEngine | None'      = None
choreo:      'ChoreoPlayer | None'      = None
```

- [ ] **Step 5: Commit**

```bash
git add master/config/main.cfg master/choreographies/cantina_show.chor master/registry.py
git commit -m "Feat: choreo — scaffolding, config, example .chor, registry entry"
```

---

## Task 2: ChoreoPlayer — easing + interpolation (TDD)

**Files:**
- Create: `tests/test_choreo_player.py`
- Create: `master/choreo_player.py` (partial — module-level functions only)

- [ ] **Step 1: Write failing tests for easing and interpolation**

Create `tests/test_choreo_player.py`:
```python
"""Tests for ChoreoPlayer — easing, interpolation, event queue, export."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from master.choreo_player import _ease, _interpolate


# ── Easing functions ──────────────────────────────────────────────────────────

def test_ease_linear_endpoints():
    assert _ease(0.0, 'linear') == pytest.approx(0.0)
    assert _ease(1.0, 'linear') == pytest.approx(1.0)

def test_ease_linear_midpoint():
    assert _ease(0.5, 'linear') == pytest.approx(0.5)

def test_ease_in_midpoint():
    # t² at t=0.5 → 0.25
    assert _ease(0.5, 'ease-in') == pytest.approx(0.25)

def test_ease_out_midpoint():
    # 1-(1-t)² at t=0.5 → 0.75
    assert _ease(0.5, 'ease-out') == pytest.approx(0.75)

def test_ease_in_out_midpoint():
    # Must be exactly 0.5 at t=0.5 (symmetric)
    assert _ease(0.5, 'ease-in-out') == pytest.approx(0.5)

def test_ease_unknown_falls_back_to_linear():
    assert _ease(0.3, 'unknown-easing') == pytest.approx(0.3)

def test_ease_clamps_below_zero():
    assert _ease(-0.5, 'ease-in') == pytest.approx(0.0)

def test_ease_clamps_above_one():
    assert _ease(1.5, 'ease-out') == pytest.approx(1.0)


# ── Angle interpolation ───────────────────────────────────────────────────────

def test_interpolate_linear_midpoint():
    kf = [
        {'t': 0.0,  'angle': 0,   'easing': 'linear'},
        {'t': 10.0, 'angle': 180, 'easing': 'linear'},
    ]
    assert _interpolate(5.0, kf) == pytest.approx(90.0)

def test_interpolate_clamps_before_first_keyframe():
    kf = [
        {'t': 2.0, 'angle': 45,  'easing': 'linear'},
        {'t': 8.0, 'angle': 135, 'easing': 'linear'},
    ]
    assert _interpolate(0.0, kf) == pytest.approx(45.0)

def test_interpolate_clamps_after_last_keyframe():
    kf = [
        {'t': 0.0, 'angle': 0,   'easing': 'linear'},
        {'t': 5.0, 'angle': 180, 'easing': 'linear'},
    ]
    assert _interpolate(20.0, kf) == pytest.approx(180.0)

def test_interpolate_ease_out_first_half_faster():
    kf = [
        {'t': 0.0,  'angle': 0,   'easing': 'linear'},
        {'t': 10.0, 'angle': 100, 'easing': 'ease-out'},
    ]
    # ease-out: 1-(1-0.5)^2 = 0.75 → 75 degrees at t=5
    assert _interpolate(5.0, kf) == pytest.approx(75.0)

def test_interpolate_three_keyframes_selects_correct_segment():
    kf = [
        {'t': 0.0,  'angle': 0,   'easing': 'linear'},
        {'t': 5.0,  'angle': 100, 'easing': 'linear'},
        {'t': 10.0, 'angle': 200, 'easing': 'linear'},
    ]
    # t=7.5 is in second segment: 100 + (200-100)*0.5 = 150
    assert _interpolate(7.5, kf) == pytest.approx(150.0)
```

- [ ] **Step 2: Run tests — expect ImportError (module not created yet)**

```bash
cd J:/R2-D2_Build/software
python -m pytest tests/test_choreo_player.py::test_ease_linear_endpoints -v
```
Expected output: `ImportError: cannot import name '_ease' from 'master.choreo_player'` (or ModuleNotFoundError).

- [ ] **Step 3: Create `master/choreo_player.py` with easing + interpolation**

```python
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
```

- [ ] **Step 4: Run easing + interpolation tests — all must pass**

```bash
python -m pytest tests/test_choreo_player.py -v -k "ease or interpolate"
```
Expected: `14 passed`

- [ ] **Step 5: Commit**

```bash
git add master/choreo_player.py tests/test_choreo_player.py
git commit -m "Feat: choreo — easing functions + angle interpolation (TDD)"
```

---

## Task 3: ChoreoPlayer — event queue + audio latency (TDD)

**Files:**
- Modify: `tests/test_choreo_player.py` (add new tests)
- Modify: `master/choreo_player.py` (add `ChoreoPlayer` class + `_build_event_queue`)

- [ ] **Step 1: Add event queue tests to `tests/test_choreo_player.py`**

Append to the file:
```python
# ── ChoreoPlayer event queue ──────────────────────────────────────────────────

from master.choreo_player import ChoreoPlayer


def _make_player(latency=0.10):
    """Create a ChoreoPlayer with all drivers mocked as None."""
    return ChoreoPlayer(
        cfg=None, audio=None, teeces=None,
        dome_motor=None, dome_servo=None, body_servo=None,
        audio_latency=latency,
    )


def test_event_queue_sorted_by_time():
    player = _make_player()
    tracks = {
        'audio':      [{'t': 5.0, 'action': 'play', 'file': 'TEST'}],
        'lights':     [{'t': 2.0, 'duration': 3.0, 'action': 'mode', 'mode': 'random'}],
        'servos':     [{'t': 1.0, 'servo': 'dome_panel_1', 'action': 'open', 'duration': 0.5}],
        'propulsion': [],
    }
    events = player._build_event_queue(tracks)
    times = [e['t'] for e in events]
    assert times == sorted(times)


def test_audio_events_not_shifted():
    player = _make_player(latency=0.10)
    tracks = {
        'audio':      [{'t': 0.0, 'action': 'play', 'file': 'CANTINA'}],
        'lights':     [],
        'servos':     [],
        'propulsion': [],
    }
    events = player._build_event_queue(tracks)
    audio_events = [e for e in events if e['track'] == 'audio']
    assert audio_events[0]['t'] == pytest.approx(0.0)


def test_non_audio_events_shifted_by_latency():
    player = _make_player(latency=0.10)
    tracks = {
        'audio':      [],
        'lights':     [{'t': 2.0, 'duration': 3.0, 'action': 'mode', 'mode': 'random'}],
        'servos':     [{'t': 1.0, 'servo': 'dome_panel_1', 'action': 'open', 'duration': 0.5}],
        'propulsion': [],
    }
    events = player._build_event_queue(tracks)
    lights_ev = next(e for e in events if e['track'] == 'lights' and e.get('action') == 'mode')
    servo_ev  = next(e for e in events if e['track'] == 'servos')
    assert lights_ev['t'] == pytest.approx(2.10)
    assert servo_ev['t']  == pytest.approx(1.10)


def test_lights_block_gets_auto_restore_event():
    player = _make_player(latency=0.0)
    tracks = {
        'audio':      [],
        'lights':     [{'t': 5.0, 'duration': 3.0, 'action': 'mode', 'mode': 'alarm'}],
        'servos':     [],
        'propulsion': [],
    }
    events = player._build_event_queue(tracks)
    restore_events = [
        e for e in events
        if e['track'] == 'lights' and e.get('_auto_restore') is True
    ]
    assert len(restore_events) == 1
    assert restore_events[0]['t'] == pytest.approx(8.0)   # 5.0 + 3.0


def test_propulsion_block_gets_auto_stop():
    player = _make_player(latency=0.0)
    tracks = {
        'audio':      [],
        'lights':     [],
        'servos':     [],
        'propulsion': [{'t': 10.0, 'duration': 2.0, 'left': 0.3, 'right': 0.3}],
    }
    events = player._build_event_queue(tracks)
    stop_events = [
        e for e in events
        if e['track'] == 'propulsion' and e.get('action') == 'stop'
    ]
    assert len(stop_events) == 1
    assert stop_events[0]['t'] == pytest.approx(12.0)   # 10.0 + 2.0
```

- [ ] **Step 2: Run new tests — expect AttributeError (class not defined yet)**

```bash
python -m pytest tests/test_choreo_player.py -v -k "queue or shifted or audio or lights or propulsion"
```
Expected: `ImportError` or `AttributeError: module has no attribute ChoreoPlayer`

- [ ] **Step 3: Add `ChoreoPlayer` class to `master/choreo_player.py`**

Append after `_interpolate`:
```python

# ── ChoreoPlayer ──────────────────────────────────────────────────────────────

class ChoreoPlayer:
    """
    Real-time choreography player. Reads .chor JSON and fires events to drivers.
    All driver args may be None (for testing or when hardware is absent).
    """

    def __init__(self, cfg, audio, teeces, dome_motor, dome_servo,
                 body_servo, vesc=None, audio_latency=None):
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

        self._stop_flag  = threading.Event()
        self._thread: threading.Thread | None = None
        self._status_lock = threading.Lock()
        self._status = {
            'playing':  False,
            'name':     None,
            't_now':    0.0,
            'duration': 0.0,
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

            # Update status
            with self._status_lock:
                self._status['t_now'] = round(t_now, 3)

            if t_now >= duration:
                log.info(f"Choreo '{name}' finished")
                break

            self._stop_flag.wait(timeout=TICK)

        with self._status_lock:
            self._status.update({'playing': False, 't_now': 0.0})
        self._safe_stop_all()

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
                    'random':  '0T1\r',
                    'leia':    '0T6\r',
                    'alarm':   '0T3\r',
                    'flash':   '0T2\r',
                    'disco':   '0T13\r',
                    'off':     '0T20\r',
                    'scream':  '0T5\r',
                    'imperial':'0T11\r',
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
                else:
                    self._vesc.drive(
                        float(ev.get('left', 0.0)),
                        float(ev.get('right', 0.0)),
                    )

        except Exception as e:
            log.error(f"Choreo dispatch error [{ev.get('track')} t={ev.get('t')}]: {e}")

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
```

- [ ] **Step 4: Run all player tests**

```bash
python -m pytest tests/test_choreo_player.py -v
```
Expected: `22 passed`

- [ ] **Step 5: Commit**

```bash
git add master/choreo_player.py tests/test_choreo_player.py
git commit -m "Feat: choreo — ChoreoPlayer class + event queue + latency shift (TDD)"
```

---

## Task 4: ChoreoPlayer — export to `.scr` (TDD)

**Files:**
- Modify: `tests/test_choreo_player.py` (add export tests)
- Modify: `master/choreo_player.py` (add `export_scr` method)

- [ ] **Step 1: Add export tests to `tests/test_choreo_player.py`**

Append:
```python
# ── Export to .scr ────────────────────────────────────────────────────────────

def test_export_scr_contains_header_comment():
    player = _make_player(latency=0.0)
    chor = {
        'meta': {'name': 'my_show', 'duration': 5.0},
        'tracks': {
            'audio': [], 'lights': [], 'dome': [],
            'servos': [], 'propulsion': [], 'markers': [],
        }
    }
    scr = player.export_scr(chor)
    assert '# Exported from my_show.chor' in scr
    assert '# WARNING' in scr


def test_export_scr_audio_play():
    player = _make_player(latency=0.0)
    chor = {
        'meta': {'name': 'test', 'duration': 5.0},
        'tracks': {
            'audio': [{'t': 0.0, 'action': 'play', 'file': 'CANTINA'}],
            'lights': [], 'dome': [], 'servos': [], 'propulsion': [], 'markers': [],
        }
    }
    lines = [l for l in player.export_scr(chor).splitlines() if l and not l.startswith('#')]
    assert 'sound,CANTINA' in lines


def test_export_scr_sleep_between_events():
    player = _make_player(latency=0.0)
    chor = {
        'meta': {'name': 'test', 'duration': 10.0},
        'tracks': {
            'audio': [{'t': 0.0, 'action': 'play', 'file': 'CANTINA'}],
            'lights': [],
            'dome': [],
            'servos': [{'t': 2.0, 'servo': 'dome_panel_1', 'action': 'open', 'duration': 0.5}],
            'propulsion': [], 'markers': [],
        }
    }
    lines = [l for l in player.export_scr(chor).splitlines() if l and not l.startswith('#')]
    assert lines[0] == 'sound,CANTINA'
    assert lines[1] == 'sleep,2.00'
    assert lines[2] == 'servo,dome_panel_1,open'


def test_export_scr_servo_close():
    player = _make_player(latency=0.0)
    chor = {
        'meta': {'name': 'test', 'duration': 5.0},
        'tracks': {
            'audio': [],
            'lights': [],
            'dome': [],
            'servos': [{'t': 1.0, 'servo': 'all', 'action': 'close', 'duration': 0.5}],
            'propulsion': [], 'markers': [],
        }
    }
    lines = [l for l in player.export_scr(chor).splitlines() if l and not l.startswith('#')]
    assert 'servo,all,close' in lines


def test_export_scr_lights_mode():
    player = _make_player(latency=0.0)
    chor = {
        'meta': {'name': 'test', 'duration': 5.0},
        'tracks': {
            'audio': [],
            'lights': [{'t': 0.0, 'duration': 5.0, 'action': 'mode', 'mode': 'disco'}],
            'dome': [], 'servos': [], 'propulsion': [], 'markers': [],
        }
    }
    lines = [l for l in player.export_scr(chor).splitlines() if l and not l.startswith('#')]
    assert 'teeces,anim,13' in lines


def test_export_scr_propulsion():
    player = _make_player(latency=0.0)
    chor = {
        'meta': {'name': 'test', 'duration': 10.0},
        'tracks': {
            'audio': [], 'lights': [], 'dome': [],
            'servos': [],
            'propulsion': [{'t': 3.0, 'duration': 2.0, 'left': 0.5, 'right': 0.5}],
            'markers': [],
        }
    }
    lines = [l for l in player.export_scr(chor).splitlines() if l and not l.startswith('#')]
    assert any('motion,0.5,0.5' in l for l in lines)
    assert 'motion,stop' in lines
```

- [ ] **Step 2: Run — expect AttributeError (export_scr not defined)**

```bash
python -m pytest tests/test_choreo_player.py -v -k "export"
```
Expected: `AttributeError: 'ChoreoPlayer' object has no attribute 'export_scr'`

- [ ] **Step 3: Add `export_scr` method to `ChoreoPlayer` class**

Append inside the `ChoreoPlayer` class (after `_safe_stop_all`):
```python
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
            cmd = _LIGHT_SCR.get(mode, f"teeces,anim,1")
            events.append((ev['t'], cmd))
            if 'duration' in ev:
                events.append((ev['t'] + ev['duration'], 'teeces,random'))

        for ev in tracks.get('dome', []):
            # Dome keyframes → discrete turn commands (best effort)
            events.append((ev['t'], f"dome,turn,0.3"))

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
```

- [ ] **Step 4: Run all tests**

```bash
python -m pytest tests/test_choreo_player.py -v
```
Expected: `29 passed`

- [ ] **Step 5: Commit**

```bash
git add master/choreo_player.py tests/test_choreo_player.py
git commit -m "Feat: choreo — export_scr() method (TDD)"
```

---

## Task 5: Flask API + registry + main.py integration

**Files:**
- Create: `master/api/choreo_bp.py`
- Modify: `master/flask_app.py`
- Modify: `master/main.py` (add `reg.choreo`)

- [ ] **Step 1: Create `master/api/choreo_bp.py`**

```python
"""
Blueprint Flask — Choreography API
Routes: /choreo/play, /choreo/stop, /choreo/status,
        /choreo/list, /choreo/load, /choreo/save, /choreo/export_scr
"""
import json
import logging
import os

from flask import Blueprint, jsonify, request
import master.registry as reg

log = logging.getLogger(__name__)
choreo_bp = Blueprint('choreo', __name__)

_CHOREO_DIR = os.path.join(os.path.dirname(__file__), '..', 'choreographies')


def _choreo_path(name: str) -> str:
    safe = os.path.basename(name).replace('..', '')
    if not safe.endswith('.chor'):
        safe += '.chor'
    return os.path.join(_CHOREO_DIR, safe)


@choreo_bp.get('/choreo/list')
def choreo_list():
    os.makedirs(_CHOREO_DIR, exist_ok=True)
    names = [
        f[:-5] for f in os.listdir(_CHOREO_DIR)
        if f.endswith('.chor')
    ]
    return jsonify(sorted(names))


@choreo_bp.get('/choreo/load')
def choreo_load():
    name = request.args.get('name', '')
    if not name:
        return jsonify({'error': 'name required'}), 400
    path = _choreo_path(name)
    if not os.path.exists(path):
        return jsonify({'error': 'not found'}), 404
    with open(path) as f:
        return jsonify(json.load(f))


@choreo_bp.post('/choreo/save')
def choreo_save():
    data = request.get_json(silent=True) or {}
    chor = data.get('chor')
    if not chor or 'meta' not in chor:
        return jsonify({'error': 'invalid chor'}), 400
    name = chor['meta'].get('name', 'untitled')
    os.makedirs(_CHOREO_DIR, exist_ok=True)
    with open(_choreo_path(name), 'w') as f:
        json.dump(chor, f, indent=2)
    log.info(f"Choreo saved: {name}")
    return jsonify({'status': 'ok', 'name': name})


@choreo_bp.post('/choreo/play')
def choreo_play():
    if not reg.choreo:
        return jsonify({'error': 'choreo player not available'}), 503
    data = request.get_json(silent=True) or {}
    name = data.get('name', '')
    if not name:
        return jsonify({'error': 'name required'}), 400
    path = _choreo_path(name)
    if not os.path.exists(path):
        return jsonify({'error': f'choreography not found: {name}'}), 404
    with open(path) as f:
        chor = json.load(f)
    ok = reg.choreo.play(chor)
    if not ok:
        return jsonify({'error': 'already playing'}), 409
    return jsonify({'status': 'ok', 'name': name, 'duration': chor['meta']['duration']})


@choreo_bp.post('/choreo/stop')
def choreo_stop():
    if reg.choreo:
        reg.choreo.stop()
    return jsonify({'status': 'ok'})


@choreo_bp.get('/choreo/status')
def choreo_status():
    if not reg.choreo:
        return jsonify({'playing': False, 'name': None, 't_now': 0.0, 'duration': 0.0})
    return jsonify(reg.choreo.get_status())


@choreo_bp.post('/choreo/export_scr')
def choreo_export_scr():
    if not reg.choreo:
        return jsonify({'error': 'choreo player not available'}), 503
    data = request.get_json(silent=True) or {}
    name = data.get('name', '')
    path = _choreo_path(name)
    if not os.path.exists(path):
        return jsonify({'error': 'not found'}), 404
    with open(path) as f:
        chor = json.load(f)
    scr = reg.choreo.export_scr(chor)
    return jsonify({'status': 'ok', 'name': name, 'scr': scr})
```

- [ ] **Step 2: Register blueprint in `master/flask_app.py`**

Add after `from master.api.light_bp import light_bp`:
```python
    from master.api.choreo_bp   import choreo_bp
```

Add after `app.register_blueprint(light_bp)`:
```python
    app.register_blueprint(choreo_bp)
```

- [ ] **Step 3: Instantiate ChoreoPlayer in `master/main.py`**

Find the section where other drivers are instantiated (after `ScriptEngine`). Add:

```python
from master.choreo_player import ChoreoPlayer

# Inside main() after engine is created:
reg.choreo = ChoreoPlayer(
    cfg=cfg,
    audio=reg.uart,          # audio commands go via UART to Slave
    teeces=reg.teeces,
    dome_motor=reg.dome,
    dome_servo=reg.dome_servo,
    body_servo=reg.servo,
    vesc=reg.vesc,
)
reg.choreo.setup()
```

- [ ] **Step 4: Verify Flask server starts without errors**

```bash
# On dev machine (Windows), from J:/R2-D2_Build/software:
python -m flask --app master.flask_app:create_app run --port 5000
```
Expected: Server starts, no ImportError. Visit `http://localhost:5000/choreo/list` → `[]`

- [ ] **Step 5: Commit**

```bash
git add master/api/choreo_bp.py master/flask_app.py master/main.py
git commit -m "Feat: choreo — Flask API blueprint (/choreo/play|stop|status|list|save|load|export_scr)"
```

---

## Task 6: Timeline Editor UI — HTML tab + CSS

**Files:**
- Modify: `master/templates/index.html`
- Modify: `master/static/css/style.css`

- [ ] **Step 1: Add CHOREO tab button to `index.html`**

In the tab bar, after the `editor` tab button (around line 137) and before `systems`:
```html
  <button class="tab tab-protected" data-tab="choreo">
    <svg width="14" height="14" viewBox="0 0 14 14" class="tab-icon">
      <rect x="1" y="3" width="12" height="8" rx="1" fill="none" stroke="currentColor" stroke-width="1.3"/>
      <line x1="1" y1="6" x2="13" y2="6" stroke="currentColor" stroke-width=".8"/>
      <rect x="3" y="7.5" width="3" height="2" rx=".5" fill="currentColor"/>
      <rect x="7" y="7.5" width="2" height="2" rx=".5" fill="currentColor" opacity=".6"/>
      <line x1="4" y1="4.5" x2="4" y2="5.5" stroke="currentColor" stroke-width="1.2"/>
    </svg>
    CHOREO
  </button>
```

- [ ] **Step 2: Add CHOREO tab content div to `index.html`**

After the closing `</div>` of `tab-editor` (search for `id="tab-editor"`), add the complete tab content. Insert before `<!-- TAB 5: SYSTEMS -->`:

```html
<!-- ================================================================
     TAB CHOREO: Choreography Timeline Editor
================================================================ -->
<div class="tab-content" id="tab-choreo">
  <div class="chor-layout">

    <!-- Top bar: choreo selector + transport -->
    <div class="chor-topbar">
      <select id="chor-select" class="input-select-sm" style="width:180px">
        <option value="">— select choreography —</option>
      </select>
      <button class="btn btn-sm" onclick="choreoEditor.newChor()">+ NEW</button>
      <div style="width:1px;height:20px;background:var(--border);margin:0 8px"></div>
      <button class="btn btn-active btn-sm" id="chor-btn-play"  onclick="choreoEditor.play()">▶ PLAY</button>
      <button class="btn btn-danger btn-sm" id="chor-btn-stop"  onclick="choreoEditor.stop()">⏹ STOP</button>
      <div style="margin-left:auto;display:flex;gap:8px;align-items:center">
        <span id="chor-timecode" style="font-family:monospace;font-size:13px;color:var(--blue);letter-spacing:2px">00:00.000</span>
        <span style="font-size:8px;color:var(--text-dim);letter-spacing:1.5px">/</span>
        <span id="chor-duration" style="font-family:monospace;font-size:11px;color:var(--text-dim)">00:00.000</span>
        <button class="btn btn-sm" onclick="choreoEditor.save()" style="margin-left:8px">💾 SAVE</button>
        <button class="btn btn-sm" onclick="choreoEditor.exportScr()">📄 .SCR</button>
      </div>
    </div>

    <!-- Timeline body -->
    <div class="chor-body">

      <!-- Track label column -->
      <div class="chor-labels" id="chor-labels">
        <div class="chor-label-spacer"></div><!-- ruler height -->
        <div class="chor-track-label" data-track="audio">🎵 AUDIO</div>
        <div class="chor-track-label" data-track="lights">💡 LIGHTS</div>
        <div class="chor-track-label chor-track-label-dome" data-track="dome">🔄 DOME °</div>
        <div class="chor-track-label" data-track="servos">⚙️ SERVOS</div>
        <div class="chor-track-label" data-track="propulsion">🚀 PROPULSION</div>
      </div>

      <!-- Scrollable timeline canvas -->
      <div class="chor-scroll-wrap" id="chor-scroll">
        <div class="chor-canvas" id="chor-canvas">
          <!-- Ruler -->
          <div class="chor-ruler" id="chor-ruler"></div>
          <!-- Track lanes -->
          <div class="chor-lane" id="chor-lane-audio"       data-track="audio"></div>
          <div class="chor-lane" id="chor-lane-lights"      data-track="lights"></div>
          <div class="chor-lane chor-lane-dome" id="chor-lane-dome" data-track="dome"></div>
          <div class="chor-lane" id="chor-lane-servos"      data-track="servos"></div>
          <div class="chor-lane" id="chor-lane-propulsion"  data-track="propulsion"></div>
          <!-- Playhead -->
          <div class="chor-playhead" id="chor-playhead">
            <div class="chor-playhead-head"></div>
          </div>
        </div>
      </div>

    </div><!-- /chor-body -->

    <!-- Properties panel -->
    <div class="chor-props" id="chor-props">
      <div class="chor-props-title">PROPERTIES</div>
      <div id="chor-props-content" style="color:var(--text-dim);font-size:10px;padding:10px">
        Select a block to edit its properties.
      </div>
    </div>

  </div><!-- /chor-layout -->
</div>
```

- [ ] **Step 3: Add CSS to `master/static/css/style.css`**

Append at end of file:
```css
/* ================================================================
   CHOREO TAB — Timeline Editor
================================================================ */

.chor-layout {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  background: var(--bg);
}

.chor-topbar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-card);
  flex-shrink: 0;
}

.chor-body {
  display: flex;
  flex: 1;
  overflow: hidden;
}

/* Track label column */
.chor-labels {
  width: 120px;
  flex-shrink: 0;
  border-right: 1px solid var(--border);
  background: var(--bg-card);
  display: flex;
  flex-direction: column;
}
.chor-label-spacer { height: 28px; border-bottom: 1px solid var(--border); flex-shrink: 0; }
.chor-track-label {
  height: 36px;
  padding: 0 10px;
  display: flex;
  align-items: center;
  font-size: 9px;
  letter-spacing: 1.5px;
  color: var(--text-dim);
  border-bottom: 1px solid rgba(0,170,255,.07);
  flex-shrink: 0;
  gap: 5px;
  cursor: default;
}
.chor-track-label-dome { height: 60px; }

/* Scrollable timeline */
.chor-scroll-wrap {
  flex: 1;
  overflow-x: auto;
  overflow-y: hidden;
  position: relative;
}

.chor-canvas {
  position: relative;
  min-width: 100%;
  height: 100%;
}

/* Ruler */
.chor-ruler {
  height: 28px;
  background: var(--bg3);
  border-bottom: 1px solid var(--border);
  position: relative;
  flex-shrink: 0;
}
.chor-tick {
  position: absolute;
  top: 0; bottom: 0;
  border-left: 1px solid var(--border2);
  padding: 4px 3px 0;
  font-size: 8px;
  color: var(--text-dim);
  white-space: nowrap;
  pointer-events: none;
}
.chor-tick.major { border-left-color: var(--border); color: var(--text); }

/* Track lanes */
.chor-lane {
  height: 36px;
  position: relative;
  border-bottom: 1px solid rgba(0,170,255,.07);
  background: var(--bg2);
  overflow: visible;
}
.chor-lane-dome { height: 60px; }

/* Blocks */
.chor-block {
  position: absolute;
  top: 4px; bottom: 4px;
  border-radius: 4px;
  border: 1px solid rgba(255,255,255,.1);
  padding: 0 8px;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: .8px;
  display: flex;
  align-items: center;
  cursor: grab;
  user-select: none;
  overflow: hidden;
  white-space: nowrap;
  min-width: 20px;
  box-sizing: border-box;
}
.chor-block:active { cursor: grabbing; }
.chor-block.selected { outline: 2px solid var(--blue); outline-offset: 1px; }

.chor-block[data-track="audio"]       { background: rgba(0,170,255,.18); color:#00aaff; border-color:rgba(0,170,255,.4); }
.chor-block[data-track="lights"]      { background: rgba(255,179,0,.16);  color:#ffb300; border-color:rgba(255,179,0,.4); }
.chor-block[data-track="lights"][data-mode="alarm"]  { background:rgba(255,51,85,.2);   color:#ff3355; border-color:rgba(255,51,85,.5); }
.chor-block[data-track="lights"][data-mode="disco"]  { background:rgba(170,85,255,.2);  color:#aa55ff; border-color:rgba(170,85,255,.5); }
.chor-block[data-track="servos"]      { background: rgba(0,255,136,.14);  color:#00ff88; border-color:rgba(0,255,136,.35); }
.chor-block[data-track="propulsion"]  { background: rgba(255,119,0,.18);  color:#ff7700; border-color:rgba(255,119,0,.4); }

/* Block resize handle */
.chor-block-resize {
  position: absolute;
  right: 0; top: 0; bottom: 0;
  width: 7px;
  cursor: ew-resize;
  background: rgba(255,255,255,.08);
  border-radius: 0 3px 3px 0;
  flex-shrink: 0;
}

/* Markers */
.chor-marker {
  position: absolute;
  top: 0; bottom: 0;
  width: 1px;
  background: var(--amber);
  opacity: .7;
  pointer-events: none;
  z-index: 5;
}
.chor-marker-label {
  position: absolute;
  top: 2px;
  left: 3px;
  font-size: 7px;
  color: var(--amber);
  letter-spacing: .8px;
  white-space: nowrap;
  text-shadow: 0 0 6px var(--amber);
}

/* Playhead */
.chor-playhead {
  position: absolute;
  top: 28px; /* below ruler */
  bottom: 0;
  width: 2px;
  background: var(--red);
  box-shadow: 0 0 8px var(--red);
  z-index: 10;
  pointer-events: none;
  left: 0;
}
.chor-playhead-head {
  position: absolute;
  top: -6px;
  left: -5px;
  width: 12px;
  height: 6px;
  background: var(--red);
  clip-path: polygon(0 0, 100% 0, 50% 100%);
}

/* Properties panel */
.chor-props {
  width: 200px;
  flex-shrink: 0;
  border-left: 1px solid var(--border);
  background: var(--bg-card);
  overflow-y: auto;
}
.chor-props-title {
  font-size: 9px;
  letter-spacing: 3px;
  color: var(--blue);
  padding: 8px 10px 6px;
  border-bottom: 1px solid var(--border);
}
.chor-prop-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 5px 10px;
  border-bottom: 1px solid rgba(0,170,255,.06);
  font-size: 10px;
}
.chor-prop-key { color: var(--text-dim); font-size: 8px; letter-spacing: 1px; }
.chor-prop-val { color: var(--blue); font-family: monospace; font-size: 11px; }
.chor-prop-input {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 3px;
  color: var(--blue);
  font-family: monospace;
  font-size: 11px;
  padding: 2px 6px;
  width: 80px;
  text-align: right;
}
```

- [ ] **Step 4: Verify tab appears (no JS yet)**

Open dashboard in browser, unlock protected mode, click CHOREO tab. Should show the empty timeline skeleton — labels on left, empty lanes, properties panel on right.

- [ ] **Step 5: Commit**

```bash
git add master/templates/index.html master/static/css/style.css
git commit -m "Feat: choreo — CHOREO tab HTML structure + CSS timeline styles"
```

---

## Task 7: choreoEditor JS — render + playhead polling

**Files:**
- Modify: `master/static/js/app.js`

- [ ] **Step 1: Add `choreoEditor` object to `app.js`**

Find the `// ================================================================` comment that separates major sections (near the end of the file, before `function setSpeed`). Add before that section:

```javascript
// ================================================================
// CHOREO EDITOR — Timeline multi-track editor
// ================================================================
const choreoEditor = (() => {
  const PX_PER_SEC_DEFAULT = 30;

  let _chor       = null;   // current .chor object
  let _pxPerSec   = PX_PER_SEC_DEFAULT;
  let _selected   = null;   // { track, index } of selected block
  let _pollTimer  = null;
  let _dirty      = false;  // unsaved changes

  // ── Helpers ─────────────────────────────────────────────────────────────

  function _px(sec)  { return sec * _pxPerSec; }
  function _sec(px)  { return px  / _pxPerSec; }
  function _fmtTime(s) {
    const m = Math.floor(s / 60);
    const sec = (s % 60).toFixed(3).padStart(6, '0');
    return `${String(m).padStart(2,'0')}:${sec}`;
  }

  function _lane(track) { return document.getElementById(`chor-lane-${track}`); }

  // ── Render ruler ─────────────────────────────────────────────────────────

  function _renderRuler(duration) {
    const ruler = document.getElementById('chor-ruler');
    if (!ruler) return;
    ruler.innerHTML = '';
    const total = Math.ceil(duration) + 5;
    for (let s = 0; s <= total; s++) {
      const major = s % 5 === 0;
      const tick = document.createElement('div');
      tick.className = 'chor-tick' + (major ? ' major' : '');
      tick.style.left = _px(s) + 'px';
      if (major) tick.textContent = s + 's';
      ruler.appendChild(tick);
    }
    // Set canvas width
    const canvas = document.getElementById('chor-canvas');
    if (canvas) canvas.style.width = (_px(total) + 100) + 'px';
  }

  // ── Render all tracks ────────────────────────────────────────────────────

  function _renderAllTracks() {
    if (!_chor) return;
    ['audio', 'lights', 'dome', 'servos', 'propulsion'].forEach(t => _renderTrack(t));
    _renderMarkers();
    _renderRuler(_chor.meta.duration);
    el('chor-duration') && (el('chor-duration').textContent = _fmtTime(_chor.meta.duration));
  }

  function _renderTrack(track) {
    const lane = _lane(track);
    if (!lane) return;
    // Remove existing blocks
    lane.querySelectorAll('.chor-block').forEach(b => b.remove());

    const items = _chor.tracks[track] || [];
    items.forEach((item, idx) => {
      if (track === 'dome') return; // dome rendered as SVG keyframe line
      const block = _makeBlock(track, item, idx);
      lane.appendChild(block);
    });

    if (track === 'dome') _renderDomeLane(items);
  }

  function _makeBlock(track, item, idx) {
    const block = document.createElement('div');
    block.className = 'chor-block';
    block.dataset.track = track;
    block.dataset.idx   = idx;
    if (item.mode) block.dataset.mode = item.mode;

    const t   = item.t        || 0;
    const dur = item.duration || (track === 'audio' ? (_chor.meta.duration - t) : 2);
    block.style.left  = _px(t) + 'px';
    block.style.width = _px(dur) + 'px';

    const label = _blockLabel(track, item);
    block.innerHTML = `<span style="pointer-events:none;overflow:hidden;text-overflow:ellipsis">${label}</span>
                       <div class="chor-block-resize" data-resize="true"></div>`;

    _attachBlockEvents(block, track, idx);
    return block;
  }

  function _blockLabel(track, item) {
    if (track === 'audio')      return `🎵 ${item.file || '?'}`;
    if (track === 'lights')     return `💡 ${(item.mode || item.name || '?').toUpperCase()}`;
    if (track === 'servos')     return `⚙️ ${item.servo || '?'} ${item.action || ''}`;
    if (track === 'propulsion') return `🚀 L${item.left||0} R${item.right||0}`;
    return '?';
  }

  function _renderDomeLane(keyframes) {
    const lane = _lane('dome');
    if (!lane) return;
    lane.innerHTML = '';
    if (keyframes.length < 2) return;

    const W = _px(_chor.meta.duration + 5);
    const H = 52;  // lane height minus padding
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('width', W);
    svg.setAttribute('height', H);
    svg.style.position = 'absolute';
    svg.style.top = '4px';
    svg.style.left = '0';

    // Draw curve through keyframes
    const pts = keyframes.map(kf => ({
      x: _px(kf.t),
      y: H - (kf.angle / 360) * (H - 4) - 2,
    }));

    let d = `M ${pts[0].x} ${pts[0].y}`;
    for (let i = 1; i < pts.length; i++) {
      const cp = (pts[i].x - pts[i-1].x) / 2;
      d += ` C ${pts[i-1].x + cp} ${pts[i-1].y} ${pts[i].x - cp} ${pts[i].y} ${pts[i].x} ${pts[i].y}`;
    }

    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', d);
    path.setAttribute('fill', 'none');
    path.setAttribute('stroke', '#aa55ff');
    path.setAttribute('stroke-width', '1.5');
    svg.appendChild(path);

    // Keyframe dots
    pts.forEach((p, i) => {
      const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      circle.setAttribute('cx', p.x);
      circle.setAttribute('cy', p.y);
      circle.setAttribute('r', '4');
      circle.setAttribute('fill', '#aa55ff');
      circle.setAttribute('stroke', '#0d1826');
      circle.setAttribute('stroke-width', '1.5');
      circle.style.cursor = 'pointer';
      circle.addEventListener('click', () => _selectDomeKF(i));
      svg.appendChild(circle);
    });

    lane.appendChild(svg);
  }

  function _renderMarkers() {
    // Draw markers on all lanes
    document.querySelectorAll('.chor-lane').forEach(lane => {
      lane.querySelectorAll('.chor-marker').forEach(m => m.remove());
    });
    const markers = _chor.tracks.markers || [];
    const firstLane = _lane('audio');
    if (!firstLane) return;
    markers.forEach(m => {
      const marker = document.createElement('div');
      marker.className = 'chor-marker';
      marker.style.left = _px(m.t) + 'px';
      const label = document.createElement('div');
      label.className = 'chor-marker-label';
      label.textContent = m.label;
      marker.appendChild(label);
      firstLane.appendChild(marker);
    });
  }

  // ── Block drag + resize ──────────────────────────────────────────────────

  function _attachBlockEvents(block, track, idx) {
    block.addEventListener('mousedown', e => {
      if (e.target.dataset.resize) {
        _startResize(e, block, track, idx);
      } else {
        _startDrag(e, block, track, idx);
      }
      _selectBlock(track, idx);
      e.preventDefault();
    });
  }

  function _startDrag(e, block, track, idx) {
    const startX    = e.clientX;
    const startLeft = parseFloat(block.style.left) || 0;

    function onMove(e2) {
      const dx    = e2.clientX - startX;
      const newLeft = Math.max(0, startLeft + dx);
      block.style.left = newLeft + 'px';
      // Snap to 0.1s
      const newT = Math.round(_sec(newLeft) * 10) / 10;
      _chor.tracks[track][idx].t = newT;
      _dirty = true;
      _updatePropsPanel(track, idx);
    }
    function onUp() {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      // Snap block to final t
      block.style.left = _px(_chor.tracks[track][idx].t) + 'px';
    }
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }

  function _startResize(e, block, track, idx) {
    const startX   = e.clientX;
    const startW   = parseFloat(block.style.width) || 60;

    function onMove(e2) {
      const dx   = e2.clientX - startX;
      const newW = Math.max(20, startW + dx);
      block.style.width = newW + 'px';
      const newDur = Math.round(_sec(newW) * 10) / 10;
      _chor.tracks[track][idx].duration = newDur;
      _dirty = true;
      _updatePropsPanel(track, idx);
    }
    function onUp() {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    }
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }

  // ── Selection + properties panel ─────────────────────────────────────────

  function _selectBlock(track, idx) {
    document.querySelectorAll('.chor-block').forEach(b => b.classList.remove('selected'));
    const block = document.querySelector(`.chor-block[data-track="${track}"][data-idx="${idx}"]`);
    if (block) block.classList.add('selected');
    _selected = { track, idx };
    _updatePropsPanel(track, idx);
  }

  function _selectDomeKF(idx) {
    _selected = { track: 'dome', idx };
    _updatePropsPanel('dome', idx);
  }

  function _updatePropsPanel(track, idx) {
    const panel = document.getElementById('chor-props-content');
    if (!panel || !_chor) return;
    const item = _chor.tracks[track]?.[idx];
    if (!item) return;

    const rows = [
      ['TRACK', track.toUpperCase()],
      ['START', (item.t || 0).toFixed(2) + 's'],
      ['DURATION', item.duration ? item.duration.toFixed(2) + 's' : '—'],
    ];
    if (track === 'lights') rows.push(['MODE', (item.mode || item.name || '?').toUpperCase()]);
    if (track === 'dome')   rows.push(['ANGLE', (item.angle || 0) + '°'], ['EASING', item.easing || 'linear']);
    if (track === 'servos') rows.push(['SERVO', item.servo || '?'], ['ACTION', item.action || '?']);
    if (track === 'propulsion') rows.push(['LEFT', item.left || 0], ['RIGHT', item.right || 0]);

    panel.innerHTML = rows.map(([k, v]) => `
      <div class="chor-prop-row">
        <span class="chor-prop-key">${k}</span>
        <span class="chor-prop-val">${v}</span>
      </div>`).join('');
  }

  // ── Playhead polling ─────────────────────────────────────────────────────

  function _startPolling() {
    _stopPolling();
    _pollTimer = setInterval(async () => {
      const status = await api('/choreo/status');
      if (!status) return;
      const ph = document.getElementById('chor-playhead');
      if (ph) ph.style.left = _px(status.t_now || 0) + 'px';
      const tc = document.getElementById('chor-timecode');
      if (tc) tc.textContent = _fmtTime(status.t_now || 0);
      if (!status.playing) _stopPolling();
    }, 200);
  }

  function _stopPolling() {
    if (_pollTimer) { clearInterval(_pollTimer); _pollTimer = null; }
  }

  // ── Public API ───────────────────────────────────────────────────────────

  return {

    async init() {
      // Load list of choreographies into selector
      const names = await api('/choreo/list');
      const sel = document.getElementById('chor-select');
      if (!sel || !names) return;
      sel.innerHTML = '<option value="">— select choreography —</option>' +
        names.map(n => `<option value="${n}">${n}</option>`).join('');
      sel.onchange = () => this.load(sel.value);
    },

    async load(name) {
      if (!name) return;
      const chor = await api(`/choreo/load?name=${encodeURIComponent(name)}`);
      if (!chor) { toast('Failed to load choreography', 'error'); return; }
      _chor = chor;
      _dirty = false;
      _selected = null;
      _renderAllTracks();
      toast(`Loaded: ${name}`, 'ok');
    },

    newChor() {
      const name = prompt('Choreography name:', 'my_show');
      if (!name) return;
      _chor = {
        meta: { name, version: '1.0', duration: 30.0, created: new Date().toISOString().slice(0,10), author: 'R2-D2 Control' },
        tracks: { audio: [], lights: [], dome: [
          { t: 0, angle: 0, easing: 'linear' },
          { t: 30, angle: 0, easing: 'linear' }
        ], servos: [], propulsion: [], markers: [] }
      };
      _dirty = true;
      _renderAllTracks();
      const sel = document.getElementById('chor-select');
      if (sel) {
        const opt = document.createElement('option');
        opt.value = name; opt.textContent = name; opt.selected = true;
        sel.appendChild(opt);
      }
      toast(`New choreography: ${name}`, 'ok');
    },

    async play() {
      if (!_chor) { toast('No choreography loaded', 'error'); return; }
      if (_dirty) await this.save();
      const result = await api('/choreo/play', 'POST', { name: _chor.meta.name });
      if (result) { toast(`Playing: ${_chor.meta.name}`, 'ok'); _startPolling(); }
    },

    async stop() {
      await api('/choreo/stop', 'POST');
      _stopPolling();
      const ph = document.getElementById('chor-playhead');
      if (ph) ph.style.left = '0px';
      const tc = document.getElementById('chor-timecode');
      if (tc) tc.textContent = '00:00.000';
      toast('Choreo stopped', 'ok');
    },

    async save() {
      if (!_chor) return;
      const result = await api('/choreo/save', 'POST', { chor: _chor });
      if (result) { _dirty = false; toast(`Saved: ${_chor.meta.name}`, 'ok'); }
    },

    async exportScr() {
      if (!_chor) { toast('No choreography loaded', 'error'); return; }
      if (_dirty) await this.save();
      const result = await api('/choreo/export_scr', 'POST', { name: _chor.meta.name });
      if (!result) return;
      // Download as file
      const blob = new Blob([result.scr], { type: 'text/plain' });
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href = url; a.download = _chor.meta.name + '.scr'; a.click();
      URL.revokeObjectURL(url);
      toast('SCR exported', 'ok');
    },
  };
})();
```

- [ ] **Step 2: Wire up `loadChoreoTab()` — called when tab is switched**

Find the tab switch handler in `app.js`. The existing pattern calls a function like `loadLightSequences()` when the lights tab is selected. Add similar logic for `choreo`:

In the `switchTab` function (search for `data-tab` or `tab-content`), add:
```javascript
if (tabId === 'choreo') choreoEditor.init();
```

- [ ] **Step 3: Verify in browser**

1. Open dashboard, unlock, click CHOREO tab
2. Selector should load list from `/choreo/list`
3. Select `cantina_show` → blocks appear on tracks
4. Drag a block → its `t` updates in the properties panel
5. Click ▶ PLAY → playhead animates

- [ ] **Step 4: Commit**

```bash
git add master/static/js/app.js
git commit -m "Feat: choreo — choreoEditor JS (render, drag, resize, playhead polling)"
```

---

## Task 8: Android sync + deploy

**Files:**
- Modify: `android/app/src/main/assets/js/app.js`
- Modify: `android/app/src/main/assets/css/style.css`

- [ ] **Step 1: Sync assets to Android**

```bash
cp master/static/js/app.js android/app/src/main/assets/js/app.js
cp master/static/css/style.css android/app/src/main/assets/css/style.css
```

- [ ] **Step 2: Final commit + push**

```bash
git add master/ android/ tests/
git commit -m "Feat: Choreography Timeline Editor — ChoreoPlayer + API + UI v1"
git push
```

- [ ] **Step 3: Deploy to Pi**

```python
import paramiko, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.2.104', username='artoo', password='deetoo', timeout=10)
stdin, stdout, stderr = c.exec_command('cd /home/artoo/r2d2 && bash scripts/update.sh 2>&1')
for line in stdout: print(line, end='')
c.close()
```

- [ ] **Step 4: Smoke test on Pi**

```bash
# From dev machine:
curl http://192.168.2.104:5000/choreo/list
# Expected: ["cantina_show"]

curl http://192.168.2.104:5000/choreo/status
# Expected: {"playing": false, "name": null, "t_now": 0.0, "duration": 0.0}

curl -X POST http://192.168.2.104:5000/choreo/play \
  -H "Content-Type: application/json" \
  -d '{"name": "cantina_show"}'
# Expected: {"status": "ok", "name": "cantina_show", "duration": 45.2}

# After a few seconds:
curl http://192.168.2.104:5000/choreo/status
# Expected: {"playing": true, "name": "cantina_show", "t_now": ~3.5, "duration": 45.2}

curl -X POST http://192.168.2.104:5000/choreo/stop
# Expected: {"status": "ok"}
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|-----------------|------|
| `.chor` JSON format with all 5 track types | Task 1 |
| `audio_latency` in `main.cfg` | Task 1 |
| `_ease()` easing functions | Task 2 |
| `_interpolate()` angle from keyframes | Task 2 |
| `ChoreoPlayer` class + `_build_event_queue` | Task 3 |
| Non-audio events shifted by latency | Task 3 |
| Auto-stop events for propulsion/lights | Task 3 |
| Playback loop with 50ms tick | Task 3 |
| Dome motor speed from keyframe derivative | Task 3 |
| `export_scr()` method | Task 4 |
| SCR export limitations documented | Task 4 |
| Flask blueprint all 6 endpoints | Task 5 |
| `reg.choreo` in registry | Task 1 + 5 |
| CHOREO tab (9th, protected) | Task 6 |
| Industrial/dark CSS matching existing theme | Task 6 |
| Drag blocks to update `t` | Task 7 |
| Resize blocks to update `duration` | Task 7 |
| Playhead animation via polling | Task 7 |
| Properties panel for selected block | Task 7 |
| Save `.chor` | Task 7 |
| Export `.scr` download | Task 7 |
| Unit tests for easing + interpolation | Task 2 |
| Unit tests for event queue + latency | Task 3 |
| Unit tests for export | Task 4 |

**No placeholders found.** All steps contain complete code.

**Type consistency verified:**
- `_ease(t, name)` and `_interpolate(t_now, keyframes)` used consistently
- `_chor.tracks.audio|lights|dome|servos|propulsion` matches schema in Task 1
- `reg.choreo` matches declaration in registry
- `choreoEditor.init/load/play/stop/save/exportScr` — no discrepancies
