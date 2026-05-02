# ChoreoPlayer — VESC Telemetry & Fail-Safe Integration
**Date:** 2026-03-28
**Status:** Approved
**Approach:** A — `telem_getter` injectable + in-loop threshold monitoring

---

## Context

`ChoreoPlayer` (`master/choreo_player.py`) already dispatches to `master/drivers/vesc_driver.py`
via `self._vesc.drive(left, right)`. The master `VescDriver` translates this to `M:LEFT,RIGHT:CRC`
over UART → Slave → pyvesc → VESC hardware.

Slave telemetry (`TL:`/`TR:`) already flows back to the Master and is stored in `reg.vesc_telem`
every 200ms. The Slave watchdog already cuts VESC power on heartbeat loss (500ms timeout).

**Gap:** ChoreoPlayer has no access to telemetry and ignores `drive()` return values, leaving two
safety holes: UART loss and hardware overload go undetected at the application layer.

---

## Scope

Modify **`master/choreo_player.py` only**. No new files. No changes to `VescDriver`, `UARTController`,
or `.chor` format.

---

## Constructor Change

```python
ChoreoPlayer(
    cfg, audio, teeces, dome_motor, dome_servo, body_servo,
    vesc=None,
    telem_getter=None,   # callable() → {'L': {...}, 'R': {...}} | None
    audio_latency=None,
)
```

`telem_getter` is a zero-argument callable, typically `lambda: reg.vesc_telem`.
If `None`, all telemetry logic is silently skipped — full backward compatibility.

---

## Configuration (`[choreo]` section in `main.cfg`)

| Key | Default | Description |
|-----|---------|-------------|
| `telem_check_interval` | `0.5` | Seconds between telemetry reads in the run loop |
| `uart_fail_threshold` | `3` | Consecutive `drive()` failures before abort |
| `vesc_min_voltage` | `20.0` | V — abort if either VESC drops below this |
| `vesc_max_temp` | `80.0` | °C — abort if either MOSFET exceeds this |
| `vesc_max_current` | `30.0` | A — abort if either motor current exceeds this |

All values are read at `__init__` time. `None` cfg → defaults apply.

---

## Fail-Safe 1 — UART Loss Detection

`_dispatch()` currently ignores the return value of `self._vesc.drive()`. The fix:

- New counter `_drive_fail_count: int = 0` (instance variable, reset on each `play()`)
- In `_dispatch()` for the `propulsion` track:
  - `drive()` returns `True` → reset `_drive_fail_count = 0`
  - `drive()` returns `False` → increment counter
  - If counter ≥ `uart_fail_threshold`:
    - `log.error("ChoreoPlayer: UART lost — N consecutive failures — ABORT [choreo=name]")`
    - Set `_abort_reason = "uart_loss"`
    - `_stop_flag.set()` — triggers clean loop exit
- `_safe_stop_all()` (already called on loop exit) handles audio + lights + dome + VESC stop

---

## Fail-Safe 2 — Threshold Monitoring

Checked every `telem_check_interval` seconds inside `_run()` (not every TICK, telemetry updates at 5Hz):

```
_last_telem_check = 0.0   # instance variable, reset on each play()

In _run() loop, after event dispatch:
    if telem_getter and (t_now - _last_telem_check) >= telem_check_interval:
        _check_telem()
        _last_telem_check = t_now
```

`_check_telem()` logic:
1. Call `telem_getter()` → dict with keys `'L'` and `'R'` (either may be `None`)
2. For each side that is not `None`:
   - `v_in < vesc_min_voltage` → abort with `reason="undervoltage"`, log which side + value
   - `temp > vesc_max_temp` → abort with `reason="overheat"`, log which side + value
   - `abs(current) > vesc_max_current` → abort with `reason="overcurrent"`, log which side + value
3. Abort = set `_abort_reason` + `_stop_flag.set()`
4. Store last good telem snapshot in `_last_telem: dict`

Only the **first** triggered condition is recorded as `abort_reason`. Subsequent checks short-circuit once `_stop_flag` is set.

---

## `get_status()` Response

```json
{
  "playing": true,
  "name": "patrol",
  "t_now": 3.250,
  "duration": 12.0,
  "abort_reason": null,
  "telem": {
    "L": {"v_in": 23.4, "temp": 42.1, "current": 8.3, "rpm": 1200, "duty": 0.35, "fault": 0},
    "R": {"v_in": 23.4, "temp": 41.8, "current": 8.1, "rpm": 1198, "duty": 0.34, "fault": 0}
  }
}
```

- `telem` is `null` when `telem_getter` is `None` or no data has been received yet
- `abort_reason` is one of: `null`, `"uart_loss"`, `"undervoltage"`, `"overheat"`, `"overcurrent"`
- `abort_reason` persists in status until the next `play()` call (useful for dashboard display)

---

## State Reset on `play()`

When `play()` is called, reset:
- `_drive_fail_count = 0`
- `_abort_reason = None`
- `_last_telem = None`
- `_last_telem_check = 0.0`

---

## Backward Compatibility

- All existing tests pass unchanged (`telem_getter` defaults to `None`)
- `vesc=None` path unchanged — telemetry logic only runs if both `vesc` and `telem_getter` are set
- `.chor` format unchanged — `propulsion` track keeps `left`/`right` duty cycle fields

---

## Files Changed

| File | Change |
|------|--------|
| `master/choreo_player.py` | Add `telem_getter`, threshold config, fail counters, `_check_telem()`, enrich `get_status()` |
| `master/config/main.cfg` | Add `[choreo]` threshold keys with defaults |
| `tests/test_choreo_player.py` | Add tests for UART fail-safe + each threshold abort |

---

## Out of Scope

- Queue for propulsion commands (rejected: hurts timing precision, UART writes are already <1ms)
- RPM mode in `.chor` (not requested, duty cycle sufficient)
- UI / timeline editor (separate brainstorm — Tasks 6-7)
