# R2-D2 Choreography Timeline Editor — Design Spec
**Date:** 2026-03-27
**Status:** Approved
**Scope:** Points 1, 2, 3 only (dome motor + VESC integration deferred to hardware arrival)

---

## Context

The existing `.scr` format is purely sequential (CSV steps + `sleep`). It cannot express parallel actions (e.g., audio playing while dome rotates while panels open). This spec introduces a new parallel choreography system built on three components:

1. **`.chor` file format** — JSON, absolute timestamps, multi-track
2. **`ChoreoPlayer`** — Python backend that reads `.chor` and fires events in real time
3. **Timeline Editor UI** — New dashboard tab (tab 8) for visual editing

The `.scr` format is **not replaced**. It remains the primary format for simple sequences. `.chor` is additive.

---

## 1. File Format — `.chor` (JSON)

### Storage location
`master/choreographies/` (new directory, alongside `master/sequences/`)

### Schema

```json
{
  "meta": {
    "name": "cantina_show",
    "version": "1.0",
    "duration": 45.2,
    "bpm": 120,
    "created": "2026-03-27",
    "author": "string"
  },
  "tracks": {
    "audio":      [ /* AudioEvent[] */ ],
    "lights":     [ /* LightEvent[] */ ],
    "dome":       [ /* DomeKeyframe[] */ ],
    "servos":     [ /* ServoEvent[] */ ],
    "propulsion": [ /* PropEvent[] */ ],
    "markers":    [ /* Marker[] */ ]
  }
}
```

### Track schemas

**AudioEvent**
```json
{ "t": 0.0, "action": "play|stop", "file": "CANTINA", "volume": 85 }
```

**LightEvent**
```json
{
  "t": 8.0, "duration": 4.5,
  "action": "mode|lseq",
  "mode": "alarm|disco|random|leia|off",
  "name": "my_lseq_name",
  "psi": { "c1": "#ff3355", "c2": "#000000", "speed": "slow|med|fast" }
}
```
- `action: "lseq"` → play a saved `.lseq` light sub-sequence by name
- `action: "mode"` → call a Teeces T-code mode
- `psi` is optional; omit to leave PSI unchanged

**DomeKeyframe** (continuous interpolation, not discrete events)
```json
{ "t": 5.0, "angle": 180, "easing": "linear|ease-in|ease-out|ease-in-out" }
```
- Angles in degrees [0–360]
- Player derives motor speed from derivative of interpolated curve
- At least 2 keyframes required. First keyframe must have `"t": 0`

**ServoEvent**
```json
{
  "t": 10.0, "servo": "utility_arm|dome_panel_1|all_dome|all",
  "action": "open|close",
  "duration": 2.0,
  "easing": "ease-out"
}
```
- `duration` maps to the existing servo speed ramp (speed = f(duration))
- `easing` is visual-only in v1 (servo driver uses its own speed ramp)

**PropEvent**
```json
{ "t": 20.0, "duration": 2.0, "left": 0.3, "right": 0.3, "easing": "ease-in-out" }
```
- `left` / `right` in [-1.0, 1.0]
- Player auto-inserts a stop event at `t + duration`
- `easing` not applied in v1 (deferred until VESC arrives)

**Marker**
```json
{ "t": 10.0, "label": "FACE DETECT TRIGGER", "type": "trigger|mode_switch|note" }
```
- Markers are metadata only — no runtime effect in v1

---

## 2. Backend — `ChoreoPlayer`

### File: `master/choreo_player.py`

**Pattern:** Same as `ScriptEngine` — standalone class, passed drivers at construction.

**Timing approach:** `time.monotonic()` as absolute reference + `threading.Event.wait(timeout=TICK)` as interruptible sleep. **No asyncio**, no extra pip packages.

```
TICK = 0.05s (50ms) — sufficient for smooth dome interpolation
```

**Audio latency compensation:**
All non-audio events are shifted by `AUDIO_LATENCY` seconds (default `0.10`). Configurable in `master/config/main.cfg` under `[choreo]`:
```ini
[choreo]
audio_latency = 0.10
```

**Easing functions (Python stdlib only):**
```
linear, ease-in (t²), ease-out (1-(1-t)²), ease-in-out (cubic)
```

**Dome motor control:**
Speed = `(Δangle / 360°) / Δt`, clamped to [-1.0, 1.0].
Motor stop threshold: `|Δangle| < 0.5°`

**Thread safety:** Single daemon thread. `threading.Event` for stop signal. All driver calls are fire-and-forget (non-blocking).

**Error handling:** Each `_dispatch()` call is wrapped in `try/except`. One bad event does not stop playback. Errors logged at WARNING level.

### API Blueprint: `master/api/choreo_bp.py`

```
POST /choreo/play    {"name": "cantina_show"}  → {"status": "ok", "name": "...", "duration": 45.2}
POST /choreo/stop    → {"status": "ok"}
GET  /choreo/status  → {"playing": true, "name": "...", "t_now": 12.5, "duration": 45.2}
GET  /choreo/list    → ["cantina_show", "march_parade"]
POST /choreo/save    {"name": "...", "chor": {...}}  → {"status": "ok"}
POST /choreo/export_scr  {"name": "..."}  → {"scr": "sound,CANTINA\nsleep,0.4\n..."}
```

### Registry integration (`master/registry.py`)
`ChoreoPlayer` added as `reg.choreo`. Constructed in `main.py` alongside other drivers. `setup()` returns `True` always (no hardware needed).

---

## 3. Export to `.scr`

**Converter:** `ChoreoPlayer.export_scr(chor: dict) -> str`

**Algorithm:**
1. Flatten all track events into a single list sorted by `t`
2. For each event, emit the corresponding `.scr` command
3. Between consecutive events, emit `sleep,<delta_t>` (rounded to 2 decimal places)
4. Events at the same timestamp are emitted consecutively with no sleep between

**Known limitations (documented in export output as a comment):**
- Dome keyframe interpolation → **not expressible** in `.scr` (only discrete `dome,turn,speed` + `dome,stop` at each keyframe)
- Servo easing → **not expressible** (servo speed ramp is the closest approximation)
- Parallel tracks → **collapsed** to sequential (race conditions possible for very tight timings)
- PSI custom blink → **not expressible** (PSI mode number sent instead)

Example output for cantina_show:
```
# Exported from cantina_show.chor — 2026-03-27
# WARNING: Dome interpolation and servo easing not preserved
sound,CANTINA
sleep,3.00
servo,dome_panel_1,open
sleep,3.00
servo,all_dome,open
sleep,2.00
teeces,anim,3
...
```

---

## 4. Timeline Editor UI

### Integration
- 9th tab in `master/templates/index.html` (current count: drive, audio, sequences, lights, editor, systems, vesc, config)
- Inserted between `editor` and `systems` (both protected tabs)
- Tab label: `🎬 CHOREO`, class `tab-protected` (requires unlock like Systems/VESC)
- No new JS files in v1 — code added to `master/static/js/app.js` in a new `choreoEditor` object (same pattern as `lightEditor`)

### Visual design
Matches the mockup: dark industrial / aerospace aesthetic. Cyan (#00f2ff) + Amber (#ffb300) accents. Consistent with existing dashboard theme.

### Track rendering
- `<div>`-based tracks with `position: absolute` blocks (not `<canvas>`)
- Each block: `left = t * PX_PER_SEC`, `width = duration * PX_PER_SEC`
- Default `PX_PER_SEC = 30` (configurable via zoom slider)

### Interactions (v1)
| Interaction | Behavior |
|-------------|----------|
| Click block | Select → show properties in right panel |
| Drag block | Update `t` value, snap to grid (1s / 0.5s / 0.1s) |
| Drag right edge | Update `duration` |
| Double-click track | Add new block at clicked position |
| Right-click block | Context menu: Duplicate / Delete |
| Playhead drag | Scrub timeline (no live preview in v1) |

### Playhead animation during playback
- `GET /choreo/status` polled every 200ms
- Playhead position = `t_now * PX_PER_SEC`
- Live LED simulation (FLD/RLD/PSI) updated from status response

### Deferred to v2
- Graphical keyframe editor on dome track (v1: keyframes editable via properties panel only)
- Real audio waveform display (v1: solid color block with filename label)
- Ghosting / onion skinning
- VESC propulsion easing

---

## 5. File layout changes

```
master/
├── choreo_player.py          ← NEW
├── choreographies/           ← NEW directory
│   └── cantina_show.chor     ← example
├── api/
│   └── choreo_bp.py          ← NEW
├── config/
│   └── main.cfg              ← ADD [choreo] section
├── templates/index.html      ← ADD tab 8
└── static/js/app.js          ← ADD choreoEditor object
```

---

## 6. Out of scope (this spec)

- Dome motor keyframe → speed command (requires dome motor hardware)
- VESC propulsion easing (requires VESCs)
- Audio waveform extraction (requires `librosa` or `ffmpeg` — too heavy for Pi)
- Multi-user / conflict resolution
- Undo/redo history
- Cloud sync

---

## 7. Testing strategy

Since hardware is not available, all testing is done without a connected Pi:

| Test | How |
|------|-----|
| `.chor` parsing | Unit test: load JSON, verify event queue order |
| Event timing | Unit test: mock `time.monotonic()`, assert dispatch order |
| Audio latency offset | Unit test: assert all non-audio events shifted by `AUDIO_LATENCY` |
| Export `.scr` | Unit test: compare output string to expected |
| UI drag/drop | Manual test in browser |
| API endpoints | `curl` / Postman against running Flask dev server |

Test files: `tests/test_choreo_player.py`, `tests/test_choreo_export.py`
