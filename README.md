<div align="center">

# 🤖 R2D2_Control

**Full-scale R2-D2 replica — distributed control system on two Raspberry Pi 4B**

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Raspberry%20Pi%204B-C51A4A?logo=raspberry-pi&logoColor=white)](https://www.raspberrypi.com/)
[![Phase](https://img.shields.io/badge/Phase-Alpha-orange)](ELECTRONICS.md)
[![Android](https://img.shields.io/badge/Android-App%20included-3DDC84?logo=android&logoColor=white)](android/compiled/)

*Master/Slave architecture · UART through slip ring · Web dashboard · Android app · 317 R2-D2 sounds · 40 expressive sequences*

</div>

---

> ⚠️ **Early Alpha — Work in Progress** — Software is fully functional and actively tested on bench. Physical assembly (3D-printed parts, slip ring, final wiring) is still in progress. No camera stream yet.

---

## What is this?

A **complete, production-grade control system** for a 1:1 scale R2-D2 replica — not a toy project. Two Raspberry Pi 4B communicate over a **physical UART through the dome slip ring**, with layered safety watchdogs, a REST API, an Android app, and 40 expressive behavioral sequences that give R2-D2 a real personality.

- **Master Pi** (dome, rotates) — web server, dome servos, LED logics, script engine, deploy system
- **Slave Pi** (body, fixed) — drive motors, body servos, dome rotation motor, audio, diagnostic LCD
- If the link drops, the drive motors **cut immediately** — no runaway robot

The dashboard runs on the Master and is reachable from any phone or browser on the local Wi-Fi hotspot. An Android app wraps the same interface with native offline detection and network auto-discovery.

---

## Screenshots

<table>
<tr>
<td align="center" width="50%">

### 🕹️ Drive
Dual joystick · WASD keyboard · Emergency stop · Live battery gauge

![Drive Interface](Screenshots/Drive_web_interface.jpg)

</td>
<td align="center" width="50%">

### 🔊 Audio
317 R2-D2 sounds · 14 mood categories · Random or specific track

![Audio Interface](Screenshots/Audio_web_interface.jpg)

</td>
</tr>
<tr>
<td align="center" width="50%">

### 🎬 Sequences
40 behavioral sequences · Loop mode · Emotions, Star Wars themes, patrol…

![Sequences Interface](Screenshots/Sequences_web_interface.jpg)

</td>
<td align="center" width="50%">

### ⚙️ Systems — Panels & Bluetooth
MG90S 180° servos · Per-panel O° / C° / S calibration · BT controller mapping

![Systems Interface](Screenshots/Systems_TemporaryServos_web_interface.jpg)

</td>
</tr>
<tr>
<td align="center" width="50%">

### 💡 Lights
Teeces32 FLD/RLD/PSI · Live preview · Scrolling text · PSI color picker · *(light sequences coming)*

</td>
<td align="center" width="50%">

### 🔧 Configuration
Wi-Fi hotspot · Auto-deploy · Git branch · System reboot/shutdown

![Config Interface](Screenshots/Config_web_interface.jpg)

</td>
</tr>
</table>

---

## Features

### 🎭 Expressive Behavioral Sequences

This is where R2-D2 comes alive. 40 sequences combine sounds, servo panels, dome rotation, and lights into **coordinated emotional performances**:

| Sequence | What R2 does |
|----------|-------------|
| `scared` | Panels **tremble** at small angles (35°, speed 8) — nervous micro-movements, not full open |
| `excited` | Panels **snap open and shut** at speed 9, rapid alternating combos, triumphant slow wide open |
| `curious` | Panels **creep open slowly** (speed 2, ~50°) while dome turns — deliberate, peeking |
| `angry` | Panels **slam** instantaneously (speed 10), aggressive clack-clack, then slow menacing close (speed 3) |
| `celebrate` | Dramatic **wave** across panels (speed 4), body + dome panels flowing in sequence |
| `patrol` | Dome wanders randomly, panels peek, random sounds — R2 feels alive on its own |
| `leia` | Full Leia mode (Teeces + iconic sound) |
| `cantina` | Full Cantina Band sequence |
| + 32 more | `march`, `evil`, `malfunction`, `birthday`, `disco`, `dance`, `taunt`, `scan`… |

**Sequences use per-panel calibrated angles automatically** — no magic numbers in the scripts. You calibrate once in the UI, every sequence respects it. And you can override angle and speed inline for mood-specific movement:

```
servo,dome_panel_1,open,40,8    # open to 40° at speed 8 — nervous peek
servo,dome_panel_1,close,20,9   # snap shut at speed 9
servo,dome_panel_2,open         # use calibrated angle + speed from settings
```

---

### 🦾 Per-Panel Servo Calibration with Speed Ramp

Every one of the 22 servo panels (11 dome + 11 body) has three independent parameters:

| Field | Description |
|-------|-------------|
| **O°** | Open angle (10–170°) |
| **C°** | Close angle (10–170°) |
| **S**  | Speed 1–10 (1 = slow sweep ~1.2s, 10 = instant) |

The speed ramp is implemented in software — the driver steps 2° at a time with a configurable delay, giving smooth, cinematic movement. `open_all()` / `close_all()` run all panels **in parallel threads** so a full-dome open happens simultaneously, not sequentially.

Settings are saved to two JSON files (`master/config/dome_angles.json` and `slave/config/servo_angles.json`) — each Pi reads its own file at boot, independently of the other. No dependency on network sync at startup.

---

### 🕹️ Control

- **Web dashboard** — dark blue R2-D2 theme, 6 tabs, mobile-first responsive layout
- **Android app** — native offline banner, IP auto-discovery (mDNS → saved IP → 192.168.4.1 → subnet scan), haptic feedback
- **WASD / arrow keys** — full keyboard driving from any browser
- **Bluetooth controller** — configurable button/axis mapping, deadzone, three speed modes

---

### 🔊 Audio

- **317 R2-D2 sounds** in 14 emotional categories — happy, sad, razz, proc, hum, whistle, alarm, scream, ooh, sent, quote, special, extra…
- Playback via `mpg123` on the Pi's native 3.5mm jack
- Volume control with a **perceptual cubic curve** — 50% slider = 79% ALSA (sounds natural, not logarithmic)
- Random-by-category or specific track, STOP command, all controllable from sequences

---

### 💡 Lights

- **Teeces32** FLD / RLD / PSI LED logics — JawaLite protocol over USB
- **Live FLD preview** in the dashboard — animated dot grid, scrolling text, PSI color swatches
- **RP2040 round LCD** (240×240, GC9A01) — MicroPython firmware showing:
  - `SYSTEM STATUS: OPERATIONAL` with UART bus health bar
  - `STARTING UP` spinner during boot
  - `MOTORS STOPPED` on watchdog lock
  - `NETWORK` status with antenna icon
  - Telemetry screen (battery %, temperature)
- Dedicated **LIGHTS tab** in dashboard — separated from Systems for future light sequence programming

---

### 🛡️ Safety — Three Independent Watchdog Layers + E-STOP

No single point of failure can leave the robot moving uncontrolled:

| Layer | Timeout | Triggers when |
|-------|---------|---------------|
| **App watchdog** | 600 ms | Browser closed, phone screen off, Wi-Fi drop |
| **Drive timeout** | 800 ms | No drive command while moving |
| **UART watchdog** | 500 ms | Master crash, slip ring disconnected |

All three trigger a **graceful decel ramp** — velocity proportional to current speed (max 400 ms at full speed), never an abrupt stop that could tip the robot.

**Emergency Stop button** (always visible, Space bar shortcut) instantly cuts all servo PWM by putting both PCA9685 chips to SLEEP. A **RESET E-STOP** button re-arms the drivers without restarting the service — servos are operational again in under a second.

---

### 🚀 Deployment System

```
Dome button short press  →  git pull + rsync Slave + reboot
Dome button long press   →  git rollback (HEAD^) + rsync + reboot
Double press             →  display current version on Teeces + RP2040
```

On boot, the Slave requests the Master's git hash over UART and re-syncs if there's a mismatch. The whole two-Pi update cycle is fully automatic and requires no SSH access.

---

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  📱 Phone / PC  ←── Wi-Fi (192.168.4.1:5000) ──→  🎩 MASTER Pi  │
│                                                                  │
│  R2-MASTER (Dome — rotates)          R2-SLAVE (Body — fixed)    │
│  ├─ Flask REST API :5000             ├─ UART listener            │
│  ├─ Script engine (40 sequences)     ├─ Watchdog 500ms → VESCs  │
│  ├─ Dome servos   I2C 0x40          ├─ Body servos  I2C 0x41   │
│  ├─ Teeces32 LEDs USB               ├─ Dome motor   I2C 0x40   │
│  └─ Deploy controller               ├─ Drive VESCs  USB ×2     │
│                                     ├─ Audio        3.5mm jack  │
│         UART 115200 baud            └─ RP2040 LCD   USB        │
│    ←─── through slip ring ────►                                 │
│    (heartbeat every 200ms + CRC checksum)                       │
└─────────────────────────────────────────────────────────────────┘
```

### Hardware at a glance

| | **Master Pi 4B 4GB** (Dome) | **Slave Pi 4B 2GB** (Body) |
|---|---|---|
| **Servos** | 11 dome panels — MG90S 180° — PCA9685 @ 0x40 | 11 body panels — MG90S 180° — PCA9685 @ 0x41 |
| **Motors** | — | 2× 250W hub motors via 2× FSESC Mini 6.7 PRO |
| **Dome motor** | — | DC motor via TB6612 HAT @ I2C 0x40 |
| **LEDs** | Teeces32 FLD/RLD/PSI via USB | — |
| **Audio** | — | 317 sounds, 3.5mm jack, mpg123 |
| **Diagnostic display** | — | RP2040 Waveshare 1.28" 240×240 round LCD |
| **Power** | 5V/10A Tobsun buck → GPIO 2&4 | 5V/10A + 12V/10A Tobsun bucks |
| **Battery** | ← 24V via slip ring (3 wires parallel) | 6S LiPo 22.2V — XT90-S anti-spark |

📐 **[Full electronics diagrams, power wiring & protocol reference →](ELECTRONICS.md)**

---

## Quick Start

### Prerequisites
- 2× Raspberry Pi 4B (username: `artoo` — configure in Raspberry Pi Imager)
- Both running **Raspberry Pi OS Trixie** (64-bit)
- USB Wi-Fi dongle for the Master Pi (internet while hosting hotspot)

### Installation

```bash
# On Master Pi — configure hotspot + internet Wi-Fi
bash scripts/setup_master_network.sh

# On Slave Pi — connect to Master's hotspot
bash scripts/setup_slave_network.sh

# On Master Pi — set up passwordless SSH (required for auto-deploy)
bash scripts/setup_ssh_keys.sh

# Enable systemd services
sudo systemctl enable r2d2-master.service r2d2-monitor.service
# On Slave Pi:
sudo systemctl enable r2d2-slave.service
```

Access the dashboard at **`http://192.168.4.1:5000`** or **`http://r2-master.local:5000`**

📖 **[Full installation guide (English) →](HOWTO_EN.md)** · [Guide d'installation (Français) →](HOWTO.md)

### Android App

Download [`android/compiled/R2-D2_Control.apk`](android/compiled/R2-D2_Control.apk), enable *Install from unknown sources*, install and launch. The app auto-discovers the Master Pi — tries mDNS first, then saved IP, then scans the subnet.

---

## Repository Structure

```
r2d2/
├── master/
│   ├── main.py              — Boot sequence + service init
│   ├── script_engine.py     — Sequence runner (background threads)
│   ├── drivers/             — DomeServoDriver, DomeMotorDriver (speed ramp, I2C smbus2)
│   ├── api/                 — Flask blueprints: audio, motion, servo, sequences, lights, status
│   ├── sequences/           — 40 behavioral sequences (.scr CSV format)
│   ├── config/
│   │   ├── dome_angles.json — Per-panel open/close/speed — read at boot, written by web UI
│   │   └── main.cfg / local.cfg
│   ├── templates/           — Web dashboard (dark blue R2-D2 theme)
│   └── static/              — CSS + JavaScript (same files bundled in Android app)
├── slave/
│   ├── main.py
│   ├── watchdog.py          — UART heartbeat watchdog → cuts VESCs at 500ms
│   ├── drivers/             — BodyServoDriver (speed ramp), VescDriver, AudioDriver, DisplayDriver
│   ├── config/
│   │   └── servo_angles.json — Body panel open/close/speed — independent from Master
│   └── sounds/              — sounds_index.json (317 MP3 files gitignored — stored on Pi)
├── shared/
│   └── uart_protocol.py     — CRC checksum, build_msg(), parse_msg()
├── rp2040/firmware/         — MicroPython: GC9A01 display, OPERATIONAL/LOCKED/TELEM screens
├── android/
│   ├── app/src/main/assets/ — Bundled web assets (works offline from file://)
│   └── compiled/            — R2-D2_Control.apk ← ready to install
└── scripts/                 — setup_*.sh, deploy.sh, update.sh
```

---

## Sequence Format

Sequences are plain `.scr` CSV files in `master/sequences/` — easy to read, write, and share:

```
# This is a comment
sound,RANDOM,happy                       # random sound from a category
sound,Theme001                           # specific sound file
servo,dome_panel_1,open                  # use calibrated angle + speed
servo,dome_panel_1,open,40,8            # override angle (40°) and speed (8)
servo,dome_panel_1,close,20,9           # close to 20° at speed 9
servo,all,open                           # all panels simultaneously (parallel)
dome,turn,0.5                            # dome rotation -1.0…+1.0
dome,random,on                           # autonomous dome wander
teeces,random                            # Teeces32 random animations
teeces,text,HELLO WORLD                  # FLD scrolling text
teeces,psi,1                             # PSI mode
sleep,1.5                                # pause (seconds, float)
sleep,random,0.5,2.0                     # random pause between min and max
motion,STOP                              # emergency stop propulsion
```

---

## Development Roadmap

| Phase | Description | Status |
|-------|-------------|--------|
| **1** | Infrastructure: UART + CRC, heartbeat watchdog, audio, Teeces32, RP2040 display, auto-deploy | ✅ Complete |
| **2** | Propulsion: VESCs, dome motor, MG90S servo panels with speed ramp | 🔧 Code complete — hardware assembly in progress |
| **3** | Script engine: 40 expressive behavioral sequences | ✅ Active |
| **4** | REST API + Web dashboard (6 tabs) + Android app | ✅ Active |
| **4+** | Per-panel servo calibration (O/C/S), LIGHTS tab, expressive sequences | ✅ Active |
| **5** | Vision: USB camera stream, person tracking | 📋 Planned |

> Physical assembly in progress — 3D parts printing, slip ring ordered. All testing currently on bench with direct BCM14/15 UART wiring.

---

## Credits & Inspiration

- Sound library and `.scr` script format inspired by **[r2_control by dpoulson](https://github.com/dpoulson/r2_control)** — 306 R2-D2 sounds + the original script thread concept
- R2-D2 Builders Club community for hardware knowledge and dome geometry

## License

**GNU GPL v3** — see [LICENSE](LICENSE).
Free to use, modify and share — keep it open source.

---

<div align="center">

*May the Force be with you.* 🌟

</div>
