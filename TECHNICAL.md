# R2-D2 — Technical Reference

> For installation and daily use → **[HOWTO.md](HOWTO.md)**
> For electronics, wiring and power → **[ELECTRONICS.md](ELECTRONICS.md)**

---

## Why Two Raspberry Pi 4B?

The Master + Slave split is a deliberate design decision, not just a workaround for cable routing through the slip ring.

**The real-time problem.** R2-D2 has two physically separate worlds: the dome (servos, lights, Teeces, web server, Bluetooth) and the body (drive motors, body servos, audio, LCD). Putting everything on one Pi means a spike in Flask/Python GIL or a slow sequence could delay motor watchdog responses. With two Pis, the Slave's 500ms UART watchdog runs independently — even if the Master crashes, the Slave cuts the VESCs automatically.

**The future: AI and computer vision.** The main reason for choosing 4GB on the Master is headroom for what comes next:
- **Facial recognition** — detect and track a face, orient the dome toward the person
- **Gesture recognition** — respond to waves, pointing, specific poses
- **Behavioral AI** — generate contextually appropriate reactions based on what R2 perceives

These workloads run continuously in the background. Isolating them on the Master means they never interfere with real-time motor control on the Slave.

**Pi 5 upgrade path.** If AI inference becomes a bottleneck, only the Master needs upgrading — the Slave keeps its Pi 4B 2GB forever. The UART protocol between them doesn't change.

---

## UART Protocol Design

### Why a Real Protocol Was Needed

Most DIY robots use UART as a dumb serial pipe: send a string, hope it arrives intact. That works fine on a bench. It fails in a real robot.

R2-D2's dome rotates continuously on a **slip ring** — a rotating electrical joint with physical brush contacts. Add 24V motor wiring, two VESC ESCs, a dome motor driver, and stepper coils all sharing the same chassis ground, and you have a textbook EMI environment. Commands get flipped, bytes get dropped, and corrupted packets translate directly into unwanted motor movements on a 60kg robot.

The solution is a proper framed protocol with verified checksums on **every single message**, implemented in [`shared/uart_protocol.py`](shared/uart_protocol.py).

### Why Arithmetic Sum mod 256 — Not XOR

Almost every tutorial uses XOR as a checksum. It's a single instruction and easy to implement. But XOR has a well-known blind spot:

> **Any two identical bytes cancel each other out.** If a burst error flips the same bit in two bytes, `byte_A XOR byte_A = 0x00` — the checksum doesn't change. The corrupted packet passes validation.

This is exactly the failure mode in a high-EMI environment: noise induced on a long cable tends to flip the same bit position across multiple bytes in a burst. XOR misses it.

Arithmetic sum mod 256 doesn't have this property. Each byte adds its full value to a running total, so flipping any bit in any byte changes the final checksum — including symmetric errors that XOR would miss.

```python
# Arithmetic sum mod 256 — what R2-D2 uses
def calc_crc(payload: str) -> str:
    return format(sum(payload.encode('utf-8')) % 256, '02X')
```

### Message Frame

Every message on the bus follows the same structure — no exceptions:

```
TYPE:VALUE:CRC\n

Examples:
  H:1:B3             ← Heartbeat (Master → Slave, every 200ms)
  M:0.5,-0.3:XX      ← Drive left=0.5 right=-0.3
  S:CANTINA:XX       ← Play audio file
  TL:15.2:42:8.3:12400:0.21:0:XX  ← VESC telemetry left motor
```

- **TYPE** — single token identifying the command (`H`, `M`, `S`, `D`, `TL`, `TR`, `DISP`, `REBOOT`…)
- **VALUE** — payload, may contain colons (only the last field is the CRC)
- **CRC** — 2-digit uppercase hex, arithmetic sum of `TYPE:VALUE` mod 256

The CRC is computed over the human-readable payload string, not raw bytes — open any serial monitor, read the messages directly, and verify checksums by hand if needed.

### Failure Handling

Corrupted messages are **silently discarded** — no retry, no error state. This is intentional:

- The heartbeat fires every 200ms. One dropped packet is invisible.
- Drive commands are rate-limited to 60/s. A single corrupted packet is overwritten in 17ms.
- The **500ms UART watchdog** counts *consecutive* failures: 3 in a row triggers a safe stop, not a single anomaly. This prevents false stops from a momentary burst while still catching true disconnection.

Result: zero false stops in operation, zero motor jolts from EMI, and bus health stays above 99% even while the dome is spinning at full speed.

### Bus Health Monitoring

The Slave counts every received packet (valid + invalid) over a rolling 60-second window and reports the ratio back via telemetry. The RP2040 LCD shows a color-coded bar:

- **≥ 80% valid** → green — nominal
- **50–79% valid** → orange — `PARASITES DETECTES` warning
- **< 50% valid** → red — check wiring, slip ring contact, or ground loops

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

The Slave drives a 240×240 GC9A01 round display via MicroPython firmware. Six distinct screens, all controlled remotely by UART `DISP:` commands from the Master:

| Screen | Ring | Content |
|--------|------|---------|
| **STARTING UP** | 🟠 Orange thick | Spinner + "STARTING UP" |
| **OPERATIONAL** | 🟢 Green thin | "SYSTEM STATUS: OPERATIONAL" · version · UART bus health bar |
| **BUS WARNING** | 🟠 Orange thin | Same + "PARASITES DETECTES" when CRC health < 80% |
| **NETWORK** | 🔵/🟠 | SCANNING · CONNECTING · HOME WIFI ACTIVE + IP |
| **SYSTEM LOCKED** | 🔴 Flashing | "WATCHDOG TRIGGERED · MOTORS STOPPED" |
| **TELEMETRY** | 🔵 Blue | Voltage + LiPo % · Temperature bar *(swipe from OPERATIONAL)* |

Swipe left/right navigates between OPERATIONAL and TELEMETRY. All other states block navigation until cleared.

Flash firmware manually via `mpremote` (only after hardware replacement or firmware reset):

```bash
python3 -m mpremote connect /dev/ttyACM0 rm :display.py
python3 -m mpremote connect /dev/ttyACM0 cp /home/artoo/astromechos/rp2040/firmware/display.py :display.py
```

---

## 🚀 Deployment System

```
Dome button — short press  →  git pull (if internet) + rsync Slave + reboot
Dome button — long press   →  rollback to previous commit + rsync + reboot
Dome button — double press →  display current git hash on Teeces LEDs
```

**`update.sh`** — the same full update cycle from SSH:
1. Backup custom sequences
2. `git pull` (skipped if wlan1 not available)
3. Restore custom sequences
4. Verify Slave is reachable
5. `rsync slave/ + shared/ + scripts/ + rp2040/ + VERSION` → Slave
6. Restart Slave service
7. Restart Master service
8. Verify both services healthy + API responding

The Slave checks version on boot — if it mismatches, it requests a resync automatically.

---

## 📁 Repository Structure

```
r2d2/
├── master/
│   ├── main.py                    — Boot sequence + service orchestration
│   ├── script_engine.py           — Multi-threaded sequence runner
│   ├── choreo_player.py           — Choreography playback engine (TICK=50ms)
│   ├── lights/                    — Plugin driver system
│   │   ├── base_controller.py     — Abstract interface (22 animations)
│   │   ├── teeces.py              — Teeces32 JawaLite driver
│   │   └── astropixels.py         — AstroPixels+ @ command driver
│   ├── drivers/
│   │   ├── dome_servo_driver.py   — PCA9685 @ 0x40, speed ramp, per-panel calibration
│   │   ├── body_servo_driver.py   — Body panels via UART SRV: commands
│   │   ├── dome_motor_driver.py   — Dome rotation via UART D: commands
│   │   └── bt_controller_driver.py — Linux evdev BT gamepad, Kids/Child Lock
│   ├── api/                       — 8 Flask blueprints (60+ endpoints)
│   │   ├── audio_bp.py            — 317 sounds, categories, volume
│   │   ├── motion_bp.py           — Drive + dome + lock mode enforcement
│   │   ├── script_bp.py           — Sequences CRUD + run/stop
│   │   ├── choreo_bp.py           — Choreography CRUD + play/stop
│   │   ├── teeces_bp.py           — Lights control + animation trigger
│   │   ├── servo_bp.py            — 22 panels open/close + calibration save
│   │   ├── settings_bp.py         — WiFi, hotspot, config, lights hot-swap
│   │   ├── status_bp.py           — System status, e-stop, lock, reboot
│   │   └── vesc_bp.py             — VESC telemetry, power scale, CAN scan
│   ├── sequences/                 — 40 built-in behavioral sequences (.scr)
│   ├── config/
│   │   ├── main.cfg               — Default configuration
│   │   ├── local.cfg              — Local overrides (gitignored)
│   │   └── dome_angles.json       — Per-panel calibration (gitignored)
│   ├── templates/index.html       — Web dashboard (6 public + 2 admin tabs)
│   └── static/                    — CSS + JS (same files bundled in Android app)
├── slave/
│   ├── main.py
│   ├── watchdog.py                — UART heartbeat watchdog → cuts VESCs at 500ms
│   └── drivers/
│       ├── audio_driver.py        — mpg123 + sounds_index.json (317 sounds)
│       ├── vesc_driver.py         — VESC ERPM propulsion (native CRC-16, no pyvesc)
│       ├── body_servo_driver.py   — PCA9685 @ 0x41
│       └── display_driver.py      — RP2040 GC9A01 LCD via /dev/ttyACM*
├── shared/
│   └── uart_protocol.py           — CRC checksum, build_msg(), parse_msg()
├── rp2040/firmware/               — MicroPython: 6-screen GC9A01 display
├── android/
│   ├── app/src/main/assets/       — Bundled web assets (offline-capable)
│   └── compiled/AstroMech_Control.apk — Ready to install
└── scripts/
    ├── setup_master.sh            — Full Master install (one curl command)
    ├── setup_slave.sh             — Full Slave install (one curl command)
    ├── deploy.sh                  — First Slave deploy + --first-install
    └── update.sh                  — Ongoing updates (git pull + rsync + restart)
```

---

## 📜 Sequence Format (.scr)

Plain CSV files in `master/sequences/` — easy to read, write, and share. The **CHOREO tab** is the primary authoring tool for new content; `.scr` files remain for legacy behavioral sequences.

```
# Full sequence example
sound,RANDOM,happy                     # random happy sound
servo,Servo_M0,open,40,8             # open Dome_Panel_1 to 40° at speed 8
teeces,anim,11                         # Imperial March animation
sleep,1.5                              # wait 1.5 seconds
servo,all,open                         # all dome panels simultaneously
sleep,random,0.5,2.0                   # random pause 0.5–2s
teeces,text,R2-D2,fld_both            # scroll text on FLD top + bottom
servo,all,close                        # close everything
motion,STOP                            # ensure motors stopped
```

**Servo IDs:** `Servo_M0`–`Servo_M10` = Master HAT channels 0–10 (dome). `Servo_S0`–`Servo_S10` = Slave HAT channels 0–10 (body).

Available commands: `sleep` · `sound` · `servo` · `dome` · `motion` · `teeces`

Sequences use per-panel calibrated angles automatically — calibrate once in the Servo tab, every sequence respects it.

---

## REST API — Port 5000

Full endpoint reference is in [CLAUDE.md](CLAUDE.md) (developer context file). Key endpoints:

```
GET  /status                    full JSON system state
POST /motion/drive              {"left":0.5,"right":0.5}
POST /audio/play                {"sound":"Happy001"}
POST /choreo/play               {"name":"foo","loop":true}
GET  /vesc/telemetry            {connected, L:{v_in,temp,current,rpm}, R:…}
POST /system/estop              hard-cut all PWM
POST /system/update             git pull + rsync + restart
```
