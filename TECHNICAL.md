# AstromechOS — Technical Reference

> For installation and daily use → **[HOWTO.md](HOWTO.md)**
> For electronics, wiring and power → **[ELECTRONICS.md](ELECTRONICS.md)**

AstromechOS is an open control platform for astromech droids. This document describes the
software architecture; the reference build is an R2-D2, but nothing here is R2-specific.

---

## Why Two Raspberry Pi 4B?

The Master + Slave split is a deliberate design decision, not just a workaround for cable routing through the slip ring.

**The real-time problem.** An astromech has two physically separate worlds: the dome (servos, lights, Teeces, web server, Bluetooth) and the body (drive motors, body servos, audio, LCD). Putting everything on one Pi means a spike in Flask/Python GIL or a slow sequence could delay motor watchdog responses. With two Pis, the Slave's 500ms UART watchdog runs independently — even if the Master crashes, the Slave cuts the VESCs automatically.

**The future: AI and computer vision.** The main reason for choosing 4GB on the Master is headroom for what comes next:
- **Facial recognition** — detect and track a face, orient the dome toward the person
- **Gesture recognition** — respond to waves, pointing, specific poses
- **Behavioral AI** — generate contextually appropriate reactions based on what the droid perceives

These workloads run continuously in the background. Isolating them on the Master means they never interfere with real-time motor control on the Slave.

**Pi 5 upgrade path.** If AI inference becomes a bottleneck, only the Master needs upgrading — the Slave keeps its Pi 4B 2GB forever. The UART protocol between them doesn't change.

---

## UART Protocol Design

### Why a Real Protocol Was Needed

Most DIY robots use UART as a dumb serial pipe: send a string, hope it arrives intact. That works fine on a bench. It fails in a real robot.

An astromech's dome rotates continuously on a **slip ring** — a rotating electrical joint with physical brush contacts. Add 24V motor wiring, two VESC ESCs, a dome motor driver, and stepper coils all sharing the same chassis ground, and you have a textbook EMI environment. Commands get flipped, bytes get dropped, and corrupted packets translate directly into unwanted motor movements on a ~60kg robot.

The solution is a proper framed protocol with verified checksums on **every single message**, implemented in [`shared/uart_protocol.py`](shared/uart_protocol.py).

### Why a Sum-Based Checksum — Not XOR

Almost every tutorial uses XOR as a checksum. It's a single instruction and easy to implement. But XOR has a well-known blind spot:

> **Any two identical bytes cancel each other out.** If a burst error flips the same bit in two bytes, `byte_A XOR byte_A = 0x00` — the checksum doesn't change. The corrupted packet passes validation.

This is exactly the failure mode in a high-EMI environment: noise induced on a long cable tends to flip the same bit position across multiple bytes in a burst. XOR misses it.

An arithmetic sum doesn't have this property. Each byte adds its full value to a running total, so flipping any bit in any byte changes the final checksum — including symmetric errors that XOR would miss.

But a plain sum still has one hole: a **null byte (`0x00`) contributes nothing**, so an inserted `0x00` — exactly what a UART BREAK condition across a slip ring injects — would leave the checksum unchanged. AstromechOS closes that hole by **also adding the payload length**, so any inserted or dropped byte changes the result:

```python
# (sum of bytes + length) mod 256 — what AstromechOS uses
def calc_crc(payload: str) -> str:
    data = payload.encode('utf-8')
    return format((sum(data) + len(data)) % 256, '02X')
```

> One residual limitation: swapping two bytes whose values sum identically (e.g. `0xEE`↔`0xFF`) collides. This is acceptable for random EMI noise; a full polynomial CRC would eliminate it but costs more on the hot path.

### Message Frame

Every message on the bus follows the same structure — no exceptions:

```
TYPE:VALUE:CRC\n

Examples:
  H:1:B6             ← Heartbeat (Master → Slave, every 200ms)
  M:0.5,-0.3:0E      ← Drive left=0.5 right=-0.3
  S:CANTINA:94       ← Play audio file
  TL:15.2:42:8.3:12400:0.21:0:C4  ← VESC telemetry, left motor
```

- **TYPE** — single token identifying the command (`H`, `M`, `S`, `D`, `TL`, `TR`, `DISP`, `VCFG`, `VINV`, `FREEZE`, `SRV`, `REBOOT`…)
- **VALUE** — payload, may contain colons (only the last field is the CRC)
- **CRC** — 2-digit uppercase hex, `(sum(bytes) + length)` of `TYPE:VALUE` mod 256

The CRC is computed over the human-readable payload string, not raw bytes — open any serial monitor, read the messages directly, and verify checksums by hand if needed. `build_msg('H', '1')` produces exactly `H:1:B6\n`.

### Failure Handling

Corrupted messages are **silently discarded** — no retry, no error state. This is intentional:

- The heartbeat fires every 200ms. One dropped packet is invisible.
- Drive commands are rate-limited to ~60/s. A single corrupted packet is overwritten in ~17ms.
- The **Slave UART watchdog (500ms)** counts *consecutive* failures: 3 in a row triggers a safe stop, not a single anomaly. This prevents false stops from a momentary burst while still catching true disconnection.

Result: zero false stops in operation, zero motor jolts from EMI, and bus health stays above 99% even while the dome is spinning at full speed.

### Three Independent Watchdogs

Safety does not depend on a single timer. Three watchdogs run at different layers, each able to cut motion on its own:

| Watchdog | Timeout | Layer | Action on trip |
|----------|---------|-------|----------------|
| **App heartbeat** (`master/app_watchdog.py`) | 1.5s | Browser/tablet → Master HTTP `/heartbeat` | Engages E-STOP if the controlling client goes silent (~7 missed 200ms beats) |
| **Drive watchdog** (`master/motion_watchdog.py`) | 800ms | Master drive command → driver | Stops drive/dome if no fresh drive command arrives |
| **Slave UART watchdog** (`slave/watchdog.py`) | 500ms | Master → Slave UART heartbeat | Cuts both VESCs independently of the Master |

### Bus Health Monitoring

The Slave tracks the valid-vs-total packet ratio and reports it back via telemetry. The RP2040 LCD's OPERATIONAL screen shows a color-coded percentage bar with a single threshold at 80%:

- **≥ 80% valid** → green — nominal
- **< 80% valid** → orange — `INTERFERENCE DETECTED` warning (check wiring, slip ring contact, or ground loops)

---

## 💡 Lights — Plugin Architecture

The lights system uses a **driver plugin architecture** — swap hardware without touching application code.

| Driver | Protocol | Hardware |
|--------|----------|---------|
| **Teeces32** | JawaLite serial 9600 baud | `/dev/ttyUSB0` |
| **AstroPixels+** | `@`-prefixed commands, `\r` terminator | USB serial |

Switch drivers **hot** from the Config tab — no reboot, no SSH. The old driver shuts down cleanly, the new one initializes in random mode.

### 22 Built-in T-code Animations

| # | Animation | # | Animation |
|---|-----------|---|-----------|
| 1 | Random | 12 | Disco (timed) |
| 2 | Flash | 13 | Disco |
| 3 | Alarm | 14 | Rebel Symbol |
| 4 | Short Circuit | 15 | Knight Rider |
| 5 | Scream | 16 | Test White |
| 6 | Leia Message | 17 | Red On |
| 7 | I Heart U | 18 | Green On |
| 8 | Panel Sweep | 19 | Lightsaber |
| 9 | Pulse Monitor | 20 | Off |
| 10 | Star Wars Scroll | 21 | VU Meter (timed) |
| 11 | Imperial March | 92 | VU Meter |

> **AstroPixels+ note:** Only 8 T-codes are supported via serial (`@0T`): T1, T2, T3, T4, T5, T6, T11, T20. All 22 work on Teeces32. The UI shows only supported codes for the connected hardware.

**Text display** — send scrolling text to `fld_top`, `fld_bottom`, `fld_both`, `rld`, or `all`.

**PSI control** — target (`both/fpsi/rpsi`) + sequence (`normal/flash/alarm/failure/redalert/leia/march`). PSI is independent of T-code animations on AstroPixels+.

---

## 📺 RP2040 Diagnostic LCD

The Slave drives a 240×240 GC9A01 round display via MicroPython firmware (`rp2040/firmware/display.py`). Six distinct screen renderers, all driven remotely by UART `DISP:` commands from the Master:

| Screen | Ring | Content |
|--------|------|---------|
| **STARTING UP** (`draw_booting`) | 🟠 Orange thick | Spinner + "STARTING UP" |
| **OPERATIONAL** (`draw_ok`) | 🟢/🟠 thin | "SYSTEM STATUS: OPERATIONAL" · version · UART bus health bar — ring + bar turn orange with "INTERFERENCE DETECTED" when bus health < 80% |
| **NETWORK** (`draw_net`) | 🔵/🟠 | SCANNING (master AP) · CONNECTING · HOME WIFI ACTIVE + IP · RECONNECTED |
| **SYSTEM LOCKED** (`draw_locked`) | 🔴 Flashing | "WATCHDOG TRIGGERED · MOTORS STOPPED" |
| **TELEMETRY** (`draw_telemetry`) | 🔵 Blue | Voltage + LiPo % · Temperature bar *(swipe from OPERATIONAL)* |
| **ERROR** (`draw_error`) | 🔴 Red | Error code (e.g. SYNC failure) |

The bus-health warning is the OPERATIONAL screen recoloring itself, not a separate screen. Swipe left/right navigates between OPERATIONAL and TELEMETRY; all other states block navigation until cleared.

Flash firmware manually via `mpremote` (only after hardware replacement or firmware reset):

```bash
python3 -m mpremote connect /dev/ttyACM0 rm :display.py
python3 -m mpremote connect /dev/ttyACM0 cp /home/artoo/astromechos/rp2040/firmware/display.py :display.py
```

---

## 🚀 Deployment System

`master/deploy_controller.py` drives deployment from either the dome button or the web UI:

```
Dome button — short press  →  git pull (if internet) + rsync Slave + reboot
Dome button — long press   →  rollback to previous commit + rsync + reboot
Dome button — double press →  display current git short hash on Teeces LEDs
```

**`scripts/update.sh`** — the same full update cycle from SSH:
1. Back up servo angle calibrations (`dome_angles.json` / `servo_angles.json`) as a safety net
2. `git pull --ff-only` (skipped if `wlan1` has no internet — falls back to local version)
3. Restore the angle calibrations **only if** the live files went missing
4. Verify the Slave is reachable over SSH
5. `rsync slave/ + shared/ + scripts/ + rp2040/ + VERSION` → Slave (working sounds & `slave.cfg` preserved via `--ignore-existing`)
6. Restart `astromech-slave.service`
7. Restart `astromech-master.service` (+ monitor)
8. Verify both services healthy + API responding

The Slave checks its version on boot (`slave/version_check.py`) — if it mismatches the Master's, it requests a resync automatically.

> **Hostnames.** On the LAN the two Pis advertise as `astromech-master` and `astromech-slave`; the install scripts default `MASTER_HOST`/`SLAVE_HOST` to `astromech-master.local` / `astromech-slave.local`. Robot-specific addressing (the live Slave IP) is read from `local.cfg [slave] host` — never hardcoded.

---

## 📁 Repository Structure

> Robot-local state (`local.cfg`, `dome_angles.json`, `servo_angles.json`, working
> `choreographies/`, `sounds/`, …) is **gitignored**. Defaults ship as `*_default/`
> seed dirs and `*.example`/`*.cfg` templates, copied into the gitignored working
> paths at install time (`rsync --ignore-existing`). That is why the tree below shows
> `choreographies_default/` and `sounds_default/`, not the live working dirs.

```
software/
├── master/                          — Dome Pi 4B 4GB: Flask API, choreo, dome servos, lights
│   ├── main.py                      — Boot sequence + service orchestration
│   ├── flask_app.py                 — App factory, registers all 14 blueprints
│   ├── registry.py                  — Dependency-injection registry for Flask handlers
│   ├── uart_controller.py           — 200ms heartbeat + CRC, Master→Slave link
│   ├── choreo_player.py             — Choreography playback engine (TICK=50ms, event-driven)
│   ├── behavior_engine.py           — Idle + startup behaviors
│   ├── vesc_safety.py               — Single source of VESC safety + fresh_telem_pair()
│   ├── safe_stop.py                 — Anti-tip drive/dome ramp-down on stop
│   ├── teeces_controller.py         — Lights controller front-end (drives lights/ plugins)
│   ├── deploy_controller.py         — Dome-button + web deploy / rollback orchestration
│   ├── app_watchdog.py              — App-layer heartbeat watchdog (1.5s → E-STOP)
│   ├── motion_watchdog.py           — Drive command watchdog (800ms → stop)
│   ├── requirements.txt
│   ├── lights/                      — Plugin driver system
│   │   ├── base_controller.py       — Abstract interface (22-entry T-code catalogue)
│   │   ├── teeces.py                — Teeces32 JawaLite driver
│   │   └── astropixels.py           — AstroPixels+ @-command driver
│   ├── drivers/
│   │   ├── dome_servo_driver.py     — PCA9685 (default 0x40, multi-HAT), speed ramp, per-panel calibration
│   │   ├── body_servo_driver.py     — Body panels via UART SRV: commands
│   │   ├── dome_motor_driver.py     — Dome rotation via UART D: commands
│   │   ├── bt_controller_driver.py  — Linux evdev BT gamepad, Kids/Child Lock
│   │   └── vesc_driver.py           — Master-side VESC telemetry parsing
│   ├── api/                         — 14 Flask blueprints (160+ endpoints)
│   │   ├── _admin_auth.py           — @require_admin decorator + X-Admin-Pw + get_json_object()
│   │   ├── audio_bp.py              — Sounds (317 seed files), categories, volume
│   │   ├── audio_reconcile.py       — Reconciles sounds_index.json with files on Slave
│   │   ├── motion_bp.py             — Drive + dome + lock mode enforcement
│   │   ├── servo_bp.py              — Panel open/close + calibration save
│   │   ├── status_bp.py             — System status, e-stop, lock, reboot, /heartbeat
│   │   ├── settings_bp.py           — WiFi, hotspot, config, lights hot-swap
│   │   ├── vesc_bp.py               — VESC telemetry, power scale, CAN scan
│   │   ├── bt_bp.py                 — Bluetooth gamepad + custom button actions
│   │   ├── choreo_bp.py             — Choreography CRUD + safe_play/stop
│   │   ├── camera_bp.py             — OTG UVC camera stream + settings
│   │   ├── behavior_bp.py           — Idle/startup behavior config + status
│   │   ├── diagnostics_bp.py        — Logs, UART RTT calibration, health
│   │   ├── shortcuts_bp.py          — Drive-tab macro shortcuts (shortcuts.json)
│   │   ├── teeces_bp.py             — Lights control + animation trigger
│   │   ├── backup_bp.py             — Backup/restore (.bck) + custom themes
│   │   └── backup_core.py           — Pure backup/restore logic (unit-tested)
│   ├── choreographies_default/      — 48 built-in behavioral sequences (.chor JSON seed)
│   ├── light_sequences/             — Light-sequence working dir (gitignored)
│   ├── config/
│   │   ├── main.cfg                 — Default configuration (tracked)
│   │   ├── local.cfg.example        — Template for local overrides
│   │   ├── servo_list.cfg           — Servo label/index definitions
│   │   ├── config_loader.py         — write_cfg_atomic() + cfg merge helpers
│   │   ├── choreo_categories.json.example — Category list template
│   │   ├── local.cfg                — Local overrides (gitignored, seeded)
│   │   └── dome_angles.json         — Per-panel calibration (gitignored, seeded)
│   ├── services/                    — systemd units (master, camera, monitor)
│   ├── templates/index.html         — Web dashboard
│   └── static/                      — css/ (style + mobile) · js/ (app + mobile) · icons/ · vendor/ · sw.js · manifest.json
├── slave/                           — Body Pi 4B 2GB: VESCs, body servos, audio, RP2040 LCD
│   ├── main.py                      — Registers UART callbacks per channel
│   ├── uart_listener.py             — Parses CRC + dispatches to callbacks
│   ├── watchdog.py                  — UART heartbeat watchdog → cuts VESCs at 500ms
│   ├── wifi_watchdog.py             — Re-joins hotspot/home WiFi on drop
│   ├── uart_health_server.py        — Port 5001 HAT/screen health for Master cockpit
│   ├── version_check.py             — Compares version on boot, requests resync on mismatch
│   ├── requirements.txt
│   ├── drivers/
│   │   ├── audio_driver.py          — mpg123 + sounds_index.json, multichannel
│   │   ├── vesc_driver.py           — VESC ERPM propulsion + paired-side CAN liveness
│   │   ├── vesc_can.py              — Native CRC-16/CCITT (no pyvesc)
│   │   ├── body_servo_driver.py     — PCA9685 (default 0x41, multi-HAT)
│   │   └── display_driver.py        — RP2040 GC9A01 LCD via /dev/ttyACM*
│   ├── services/                    — systemd units (slave, version)
│   ├── config/
│   │   ├── slave.cfg.example        — Template (working slave.cfg gitignored)
│   │   └── servo_angles.json        — Body servo calibration (gitignored, seeded)
│   └── sounds_default/              — 317 seed MP3s (working sounds/ gitignored)
├── shared/
│   ├── uart_protocol.py             — calc_crc(), build_msg(), parse_msg()
│   ├── base_driver.py               — Shared driver base class
│   └── paths.py                     — Repo path helpers
├── rp2040/
│   ├── firmware/                    — MicroPython GC9A01: display.py · gc9a01py.py · main.py · touch.py
│   └── test/                        — test_display.py
├── android/                         — WebView control app
│   ├── app/src/main/assets/         — Bundled web assets (index.html + mobile.html, offline-capable)
│   └── compiled/AstroMech_Control.apk — Ready to install
├── tools/
│   ├── scr_to_chor.py               — Legacy .scr → .chor converter (one-shot, not used at runtime)
│   └── stress_joystick.py           — Joystick load-test utility
├── scripts/
│   ├── setup_master.sh              — Full Master install
│   ├── setup_slave.sh               — Full Slave install
│   ├── setup_master_network.sh      — Master WiFi/hotspot bring-up
│   ├── setup_slave_network.sh       — Slave network bring-up
│   ├── gen_hotspot_ssid.sh          — Per-robot hotspot SSID (Astromech_Control_XXXX)
│   ├── deploy.sh                    — First Slave deploy (--first-install)
│   ├── update.sh                    — Ongoing updates (git pull + rsync + restart)
│   ├── deploy_rp2040.sh             — Flash RP2040 firmware
│   ├── resync_slave.sh              — Force Slave resync
│   └── test_*.py / test_*.sh        — Unit + live tests (backup, checksum, servos, wifi…)
├── docs/                            — API.md · AUDIT_HISTORY.md · ROADMAP.md · wiring/mockup HTML
├── README.md · HOWTO.md · HOWTO_FR.md · ELECTRONICS.md · CLAUDE.md · AGENTS.md · TECHNICAL.md · LICENSE · VERSION
```

---

## 🎬 Sequence Format (.chor)

Behavioral sequences are **`.chor` files** — a multi-track JSON timeline in `master/choreographies/`, authored visually in the **CHOREO tab** (drag blocks onto lanes, set timing, live preview). Two top-level keys:

- **`meta`** — `label`, `emoji`, `category`, `duration`, `audio_channels_required`, `author`, `version`…
- **`tracks`** — keyed by lane, each an array of time-stamped events (field `t` = seconds from start):
  - `audio` — multichannel sound (channel `ch`, `file` or `RANDOM:<category>`, `volume`, `priority`)
  - `propulsion` (drive L/R) · `dome` (dome rotation)
  - `dome_servos` · `body_servos` · `arm_servos` — panel & arm open/close angles + speed
  - `lights` — Teeces / AstroPixels+ animations & text

```json
{
  "meta": { "label": "Curious", "emoji": "🤔", "category": "emotion",
            "duration": 12.92, "audio_channels_required": 2 },
  "tracks": {
    "audio": [
      { "t": 0,   "action": "play", "ch": 0, "file": "RANDOM:proc", "volume": 85 },
      { "t": 2.8, "action": "play", "ch": 0, "file": "RANDOM:ooh",  "volume": 85 }
    ]
  }
}
```

The event-driven **ChoreoPlayer** (50 ms tick) schedules every track in sync — body-servo (UART) events are advanced slightly ahead of dome-servo (I2C) events to absorb the serial-link latency (tunable via the UART RTT calibration tool). Servo events use per-panel calibrated angles automatically — calibrate once in the Servo tab, every sequence respects it.

> **Lineage — why it feels familiar:** the `.chor` format was **inspired by the `.scr` CSV script format** from [dpoulson's r2_control](https://github.com/dpoulson/r2_control). The bundled sequences were auto-converted from the original `.scr` files (you'll still see `"source": "curious.scr"` / `"author": "scr_to_chor converter"` in their `meta`), but **`.scr` is no longer used at runtime** — everything is `.chor` now, edited in the visual timeline.

---

## REST API — Port 5000

160+ endpoints across 14 Flask blueprints. The full reference is in [docs/API.md](docs/API.md);
Flask binds `0.0.0.0:5000` by default (`[master] flask_port`). Key endpoints:

```
GET  /status                    full JSON system state
POST /motion/drive              {"left":0.5,"right":0.5}
POST /audio/play                {"sound":"Happy001"}
POST /choreo/play               {"name":"foo","loop":true}
GET  /vesc/telemetry            {connected, L:{v_in,temp,current,rpm}, R:…}
POST /system/estop              hard-cut all PWM
POST /system/update             git pull + rsync + restart
```

**Auth.** Every state-mutating endpoint is gated by `@require_admin` (`X-Admin-Pw` header,
constant-time compared). The safety endpoints `/system/estop*` and `/heartbeat` are
intentionally LAN-open so an E-STOP never depends on holding a token.
