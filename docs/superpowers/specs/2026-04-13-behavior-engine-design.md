# Behavior Engine — Design Spec
**Date:** 2026-04-13
**Status:** Approved

---

## Goal

Make R2-D2 feel alive at conventions without human interaction. Two independent systems: a startup sequence played at boot, and idle reactions triggered after inactivity (Mode ALIVE).

---

## Architecture

New file: `master/behavior_engine.py` — a `BehaviorEngine` class with a background thread.
Initialized in `master/main.py` alongside existing services.
Config stored in `local.cfg [behavior]`.
`reg.last_activity` timestamp added to `master/registry.py`, updated via Flask `before_request` hook on every POST request.

---

## 1. Startup Sequence

When the Pi boots, after a configurable delay, `BehaviorEngine` plays a choreo via the existing `reg.choreo.play()` mechanism.

**Config (`local.cfg [behavior]`):**
```ini
[behavior]
startup_enabled  = true
startup_delay    = 5
startup_choreo   = startup.chor
```

**Behavior:**
- Waits `startup_delay` seconds after `BehaviorEngine.start()` is called
- Calls `reg.choreo.play(choreo_data)` if `startup_enabled = true` and the choreo file exists
- Silently skips if choreo file not found (logs a warning)
- Does not block the rest of the boot sequence (runs in background thread)

---

## 2. Idle Reactions (Mode ALIVE)

When `now - reg.last_activity > idle_timeout` and no choreo is currently playing (`not reg.choreo.is_running()`), `BehaviorEngine` triggers a reaction based on the configured mode.

**Config (`local.cfg [behavior]`):**
```ini
alive_enabled       = false
idle_timeout_min    = 10
idle_mode           = choreo
idle_audio_category = happy
idle_choreo_list    = patrol.chor,celebrate.chor,startup.chor
dome_auto_on_alive  = true
```

**Modes:**
| Value | What R2 does |
|-------|-------------|
| `sounds` | `POST /audio/random` with `idle_audio_category` |
| `sounds_lights` | Random audio + random lights animation |
| `lights` | Random lights animation only |
| `choreo` | Pick random choreo from `idle_choreo_list`, play via `reg.choreo.play()` |

**Activity tracking:**
- `reg.last_activity` = `time.monotonic()` updated on every Flask POST request via `before_request` hook in `flask_app.py`
- Reset also when ALIVE is toggled ON (prevents immediate trigger)

**Dome auto rotation:**
- When ALIVE is ON and `dome_auto_on_alive = true` → calls `POST /motion/dome/random {"enabled": true}`
- When ALIVE is toggled OFF → calls `POST /motion/dome/random {"enabled": false}`
- Dome auto state is NOT tracked separately — ALIVE owns it

**Guards:**
- Does not trigger if `reg.choreo.is_running()`
- Does not trigger if `reg.audio_playing` (for sounds/sounds_lights modes)
- Minimum 30s between idle triggers (prevents spam if idle reaction is short)
- ALIVE mode persisted to `local.cfg` so it survives service restart

---

## 3. ALIVE Toggle — Drive Tab

Replaces the existing "Dome Auto" button in the Drive tab header area.

**UI:**
- Button label: `ALIVE`
- Active state: teal/cyan glow (same style as other active Drive buttons)
- Inactive state: dimmed
- Clicking toggles `alive_enabled` in `local.cfg` + calls `BehaviorEngine.set_alive(bool)`

**API:**
```
POST /behavior/alive    {"enabled": true|false}
GET  /behavior/status   {alive_enabled, startup_enabled, idle_mode, idle_timeout_min, last_activity_ago_s}
```

---

## 4. Settings > Behavior Panel

New panel `🤖 Behavior` added to the Settings sidebar (between `🦾 Arms` and `🔧 Calibration`).

**Startup section:**
```
STARTUP SEQUENCE
  [✓] Enabled
  Delay:  [5] seconds
  Choreo: [startup.chor ▼]   (dropdown of all .chor files)
  [SAVE]
```

**Idle reactions section:**
```
IDLE REACTIONS (ALIVE MODE)
  [✓] Enabled
  Trigger after: [10] minutes of inactivity

  Mode:
  ( ) Sounds only        Category: [happy ▼]
  ( ) Sounds + Lights    Category: [happy ▼]
  ( ) Lights only
  (●) Choreo             [patrol.chor ×] [celebrate.chor ×] [+ Add choreo ▼]

  [✓] Dome auto-rotation when ALIVE is ON
  [SAVE]
```

**Choreo list (mode Choreo):**
- Pills showing selected choreos with × to remove
- Dropdown to add from existing .chor files
- Min 1 choreo required if mode = choreo

---

## 5. File Structure

| File | Change |
|------|--------|
| `master/behavior_engine.py` | New — `BehaviorEngine` class |
| `master/main.py` | Init + start `BehaviorEngine` |
| `master/registry.py` | Add `last_activity`, `behavior_engine` |
| `master/flask_app.py` | `before_request` hook to update `last_activity` |
| `master/api/behavior_bp.py` | New blueprint — `/behavior/alive`, `/behavior/status`, `/behavior/config` |
| `master/templates/index.html` | ALIVE button in Drive tab, Behavior panel in Settings sidebar |
| `master/static/js/app.js` | ALIVE toggle logic, Behavior settings panel JS |
| `master/static/css/style.css` | ALIVE button styles, Behavior panel styles |
| `local.cfg.example` | Add `[behavior]` section with defaults |

---

## 6. Persistence

All behavior config is read from / written to `local.cfg [behavior]` at runtime.
`BehaviorEngine` reads config on each idle cycle (no restart needed when settings change).
`alive_enabled` is persisted immediately on toggle so it survives service restart.

---

## Out of Scope

- Personality presets (Excited / Calm / Sneaky) — deferred
- Scheduler (time-based triggers) — separate future spec
- Sound profiles / excluded categories — separate spec
