# Audio Multi-Channel Design Spec

## Goal

Expand the R2-D2 audio system from 2 hardcoded channels to N configurable channels (default 6), with a priority-based eviction scheduler in ChoreoPlayer and matching editor validation in the CHOREO timeline.

---

## Background — Current State

| Item | Current |
|---|---|
| Simultaneous channels | 2 (hardcoded) |
| UART types | `S:` (ch0), `S2:` (ch1) |
| AudioDriver slots | `_procs: list = [None, None]` |
| ChoreoPlayer | dispatches ch0 or ch1 based on `"ch"` field |
| Priority system | None |
| Config | None |

---

## Architecture

### Principle

All scheduling intelligence lives on the **Master** (`ChoreoPlayer`). The **Slave** (`AudioDriver`) stays passive — it receives `Sn:filename` and plays on slot `n`. No eviction logic on the Slave side.

### Components changed

| File | Change |
|---|---|
| `master/config/main.cfg` | Add `audio_channels = 6` |
| `slave/drivers/audio_driver.py` | Dynamic slot pool (N slots), register N callbacks |
| `slave/main.py` | Register callbacks `S`, `S2` … `Sn` dynamically |
| `master/choreo_player.py` | Slot scheduler + priority eviction |
| `master/api/status_bp.py` | Expose `audio_channels` in `GET /status` |
| `master/static/js/app.js` | Priority picker in inspector + timeline validation + compatibility banner |
| `.chor` schema | Add `"priority"` on audio events, `"audio_channels_required"` in meta |

---

## Configuration

Two config files — one per Pi (update.sh syncs `slave/` but not `master/`):

`master/config/main.cfg` — read by `ChoreoPlayer` and the Master Flask app:
```ini
[audio]
audio_channels = 6
```

`slave/config/slave.cfg` *(new file, synced via update.sh rsync slave/)* — read by `slave/main.py`:
```ini
[audio]
audio_channels = 6
```

Both default to `6` if the key is absent. The user sets both to the same value. Documented in CLAUDE.md.

---

## UART Protocol

Current message types `S:` and `S2:` are extended to `S:`, `S2:`, `S3:` … `Sn:` following the same pattern. No format change — only the number of registered types grows.

The Slave registers one callback per channel at startup:
```python
for i in range(audio_channels):
    msg_type = 'S' if i == 0 else f'S{i + 1}'
    uart.register_callback(msg_type, audio.make_channel_handler(i))
```

`make_channel_handler(ch)` returns a closure that routes to `_handle_channel(value, ch)` — same logic as today's `handle_uart` / `handle_uart2`.

---

## AudioDriver Changes

`slave/drivers/audio_driver.py`:

```python
# Before
_procs: list[Popen | None] = [None, None]

# After
def __init__(self, channels: int = 6):
    self._channels = channels
    self._procs: list[Popen | None] = [None] * channels

def make_channel_handler(self, ch: int):
    def handler(value: str):
        self._handle_channel(value, ch)
    return handler
```

All existing logic (`_handle_channel`, `_launch`, `stop`) is unchanged — only the slot count is dynamic.

---

## ChoreoPlayer — Slot Scheduler

### Slot table

```python
# Each entry:
_audio_slots: list[dict | None] = [None] * audio_channels
# dict = { "sound": str, "started_at": float, "priority": str, "duration": float | None }
```

### Priority levels

| Value | Meaning |
|---|---|
| `"high"` | Never evicted |
| `"normal"` | Default — evicted after `"low"` slots |
| `"low"` | Evicted first |

### Eviction algorithm (called when all slots are busy)

```
1. Find all slots with priority "low"  → pick oldest by started_at
2. If none: find all slots with "normal" → pick oldest by started_at
3. If none: all slots are "high" → log WARNING, drop new sound, return None
```

### Slot lifecycle

- **Slot assigned:** on audio event dispatch, scheduler picks free or evicted slot, sends `Sn:filename` via UART. A `threading.Timer` is stored alongside the slot entry.
- **Slot released naturally:** when `event.duration` is known, the timer fires at `started_at + duration` and sets the slot to `None`.
- **Slot released early (eviction):** the existing timer is cancelled (`timer.cancel()`) before the slot is reassigned.
- **Slot released on stop:** `ChoreoPlayer.stop()` cancels all pending timers and resets `_audio_slots` to `[None] * N`.
- **Duration absent:** slot remains occupied until overwritten by eviction — no timer is created.

---

## .chor Schema Changes

### Audio event — new `priority` field

```json
{
  "t": 2.5,
  "action": "play",
  "file": "CANTINA",
  "duration": 62.0,
  "priority": "high"
}
```

`priority` defaults to `"normal"` if absent. Existing `.chor` files are fully backward-compatible.

### Meta — new `audio_channels_required` field

```json
"meta": {
  "name": "cantina",
  "duration": 65.0,
  "audio_channels_required": 3,
  ...
}
```

Computed automatically by the editor at save time: peak number of simultaneously active audio events across the full timeline. Updated every save.

---

## ChoreoPlayer — Runtime Compatibility Check

At choreo load time:
```python
required = meta.get("audio_channels_required", 1)
configured = self._audio_channels
if required > configured:
    log.warning(
        "Choreo '%s' requires %d audio channels but system has %d — some sounds will be dropped.",
        name, required, configured
    )
```

Behavior: plays the first N channels worth of audio; eviction handles the rest per the priority algorithm. No crash, no abort.

---

## CHOREO Editor — JS Validation

### Priority picker in inspector

When an audio block is selected, the inspector shows a `<select>` for priority:
```
Priority: [ Low | Normal ▼ | High ]
```
Default: `Normal`. Stored as `"priority"` on the event.

### Real-time timeline validation

On every audio event add/edit/move, the JS runs a simulation:

```
simulate(events, audio_channels):
  for each millisecond T with at least one active audio event:
    count active High-priority events at T
    if count > audio_channels:
      flag all events overlapping T as "overflow"
```

Overflow events get a red badge on the timeline block and an inspector warning:
> *"All High-priority slots full at this point — sound will be dropped at runtime."*

### Compatibility banner

The editor fetches `audio_channels` from `GET /status` at tab load. On open/save of a choreo file, if `meta.audio_channels_required > audio_channels_config`:

> ⚠ *"This choreo requires 8 audio channels — your system is configured for 6. Some sounds may be dropped."*

Banner is yellow, dismissible, reappears on next load.

---

## API Change

`GET /status` adds:
```json
"audio_channels": 6
```

No new endpoint required.

---

## Backward Compatibility

| Scenario | Behavior |
|---|---|
| Old `.chor` without `priority` field | Treated as `"normal"` — identical to today |
| Old `.chor` without `audio_channels_required` | No banner shown, no warning |
| System with `audio_channels = 2` (legacy) | Works exactly as today — 2 slots, same UART types |
| `.chor` manually edited with 7 High events on a 6-channel system | First 6 respected, 7th dropped + WARNING log |

---

## Out of Scope

- Priority on `.scr` sequences (script_engine always uses ch0, unchanged)
- Audio queue / deferral (sounds not played are dropped, not queued)
- Per-category priority defaults
- Visualization of channel occupancy during playback
