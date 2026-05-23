# AstromechOS — Roadmap & Feature Ideas

> Initial brainstorm 2026-03-22 — priorities and ideas for the upcoming phases.
> Phases 1–4 shipped (UART/audio/lights/display/deploy · VESC/servos · choreography engine · dashboard+API+Android+BT+safety+themes+backup). Phase 5 (vision / AI) in progress.

---

## ✅ Already in production

### Phase 1 — Plumbing & I/O
| Feature | Notes |
|---|---|
| UART Master↔Slave + CRC + watchdog | 3 independent safety layers (app 600ms→1.5s · drive 800ms · slave UART 500ms) |
| Audio — multi-category sounds | mpg123 on the Slave, cubic volume curve, random-per-category · auto-reconciled index |
| Teeces32 / AstroPixels+ FLD/RLD/PSI | JawaLite, live preview, hot-swappable lights backend (no reboot) |
| RP2040 LCD GC9A01 | BOOT/OP/LOCKED/NET/TELEM/BUS screens, dynamic ACM port |
| Auto deploy (Settings UI) | git pull + rsync to Slave + reboot in one click · rollback · `behind_count` before UPDATE |

### Phase 2 — Propulsion & servos
| Feature | Notes |
|---|---|
| VESC ×2 (USB + CAN), native CRC-16 | multiplicative power scale · per-side invert · duty/rpm mode · bench mode |
| Live VESC telemetry | v_in/temp/current/rpm/duty/fault every 200ms · per-cell thresholds (green/orange/red) |
| Dome servos (I2C PCA9685) + body (UART) | multi-HAT, editable labels, angle/speed calibration, config-aware arms sequence |
| E-STOP + RESET without restart | pure freeze (PWM holds position) · reset = slow anti-pinch stow |

### Phase 3 — Choreography engine & behaviors
| Feature | Notes |
|---|---|
| Event-driven ChoreoPlayer (TICK 50ms) | multichannel audio (12 tracks) · dome+body servo interpolation · hot-swappable latencies |
| 48 .chor choreographies | categorized, editable emoji/label, rename/delete with shortcuts cascade |
| ALIVE behavior engine | configurable idle behaviors · startup behavior · next-idle countdown |
| Per-axis lockout during choreo | propulsion / dome selectively locked, never everything at once |

### Phase 4 — Dashboard, control & safety
| Feature | Notes |
|---|---|
| Flask REST API + web dashboard | 14 blueprints · R2-D2 theme, mobile-first · cache-bust `?v=` |
| Android app for tablet + phone | WebView file picker (restore/upload) + DownloadManager (backup) + touch DnD (Pointer Events) |
| BT gamepad via evdev (Pi-native) | Shield/Xbox/PS · scan/pair/unpair from the UI · 300ms keep-alive · battery%+RSSI · extended timeout |
| **Custom BT button actions (per-MAC)** | bind any button → arms/panel/dome/choreo/sound/random · press-to-capture workflow |
| **VESC Safety Lock** | `vesc_safety.py` single source · refuses motion if a VESC is absent/faulted/stale · bench bypass · CAN liveness · Drive overlay pills |
| **3-tier lock modes** | Normal / Kids (speed cap) / Child Lock (drive blocked) · server-side unlock via `hmac.compare_digest` |
| **Two-password model** | admin (`X-Admin-Pw` hmac, 53+ endpoints) · WPA-PSK network · verify rate-limit 10/60s → lockout · "default password" banner |
| **Visual sequence editor** | drag & drop timeline, blocks color-coded by type, live preview, save/load/export `.scr`, touch-ready |
| Shortcuts (Drive-tab macros) | 12 max · arms/panel/dome/choreo/sound/random · per-type validation · rename/delete cascade |
| Full Cockpit Status Panel | topbar · HB/UART/BT/SLAVE pills · E-STOP overlay · mode pills (bench/kids/lock) · STATUS always up to date |
| HAT diagnostic + Diagnostics tab | Dome/Body/Motor HAT I2C probe · RP2040 Screen health · auto-refreshing logs/RTT/stats |
| USB camera autodetect | live MJPEG streaming · sysfs scan (no hardcoded `/dev/videoN`) · last-connect-wins · auto-reconnect |
| CSS theme system | 8 built-in themes + customizer with live preview + 7 fonts · **persisted server-side** (custom_themes.json) |
| **Full backup / restore** | `.bck` of all state · restore = full replacement + auto reboot · network preserved · hardened against zip-slip + RCE |
| **Graceful reboot / shutdown** | Master/Slave/both · service-only restart · countdown overlay + auto reconnect |
| **Per-robot hotspot SSID + live network** | unique `Astromech_Control_XXXX` · slave-first hotspot change (abort if Slave unreachable) · `sudo -n nmcli` |
| **Config-not-in-git (seed/working)** | robot-local state outside git · `*_default`/`.example` seeds copied at install · `git pull` never blocks |
| **Auto-reconciled audio index** | drops ghost entries · files unknown ones under `others` · at boot + on demand |

---

## 🔜 Phase 5 — Vision & AI *(in progress)*

> The camera has arrived and live streaming is in production. What remains is the intelligence on top.

- [x] **Live USB camera streaming** — MJPEG, autodetect, last-connect-wins, Drive-tab overlay
- [ ] **Person tracking** — the dome turns toward the detected visitor
- [ ] **Facial recognition** — greet by name, visitor memory (camera + ML model)
- [ ] **Snapshot / capture** on trigger (`/camera/snapshot` endpoint already present)

---

## 🟡 Still to do — leftovers from Phase 4

These initial ideas are **partially shipped** or intentionally deferred:

- **Performance gamepad** — custom per-button actions and sequence triggering are shipped. The **Drive Mode ↔ Performance Mode switch** via combo and the analog L2/R2 triggers (real-time volume / dome speed) are still to do.
- **VESC Safety Lock** — ✅ shipped (see the Phase 4 table). Single-VESC bench mode remains available and is explicitly flagged.

---

## 🔥 Priority 2 — Progressive battery protection

> The robot will never die on a flat battery without warning.

- [x] **Real-time dashboard** — voltage, motor temps, current, rpm, duty per side + aggregated (`/status`, `/vesc/telemetry`)
- [x] **Per-cell thresholds** — green ≥3.8V · orange ≥3.6V · red <3.6V · configurable 4S/6S/7S/8S chemistry
- [x] **ChoreoPlayer cutoff** under critical voltage — abort if `cells×3.5V` / 80°C / 30A
- [ ] **Historical graph** — consumption over the session
- [ ] **Automatic progressive alerts** (beyond the existing cutoff threshold)
  - 30% → proc sound (gentle warning)
  - 15% → alarm sound + RP2040 red LED
  - 10% → automatic power-save mode (speed -50%, sounds off)
  - 5% → motor shutdown + shutdown sequence
- [ ] **Refuse to start** if voltage is too low at boot
- [ ] Voltage display on the RP2040 LCD (TELEMETRY screen already planned)

---

## ✅ Priority 4 — Visual sequence editor *(shipped)*

> Any builder can create their own sequences without touching a text file. **Shipped** (`choreoEditor`/`scriptEngine`, endpoints `/choreo/load`·`/choreo/save`·`/choreo/export_scr`).

- [x] **Drag & drop timeline** in the dashboard — blocks color-coded by type (sound/servo/dome/lights/pause), parallel lanes
- [x] **Real-time preview** — plays the sequence while you build it
- [x] **Library** — save, name, categorize, rename
- [x] **.scr export** — compatible with the existing format
- [x] **Touch-ready** — DnD migrated to Pointer Events (tested on Xiaomi Pad 6)

---

## 🟡 Priority 5 — Self-Test & Diagnostics *(partially shipped)*

> Head off to a convention confident that everything works.

- [x] **Diagnostics tab** in the dashboard — live logs (ALL/WARN/ERROR filter), UART RTT, CRC/health stats, Slave ping, I2C scan
- [x] **Per-subsystem health** — HB/UART/BT/SLAVE cockpit pills + HAT health (Dome/Body/Motor) + RP2040 Screen, green/orange/red
- [ ] **Self-test at boot** (optional) — tests each servo, plays a sound, rotates the dome, checks UART + RP2040 + Teeces · result shown on the LCD
- [ ] **Individual component test** triggered on demand
- [ ] **Overall health score** displayed permanently in the header

---

## 🔥 Priority 6 — Show Mode / Smart autonomy

> The droid "comes alive" when you want, goes quiet when you want. The ALIVE engine (idle behaviors) lays the groundwork; the coordinated Show Mode is still to do.

- [ ] **"Show Mode" toggle** in the UI + a dedicated gamepad shortcut
- [ ] **Smart random mood** — a weighted pool of sequences + sounds + panels + dome with natural pauses that vary, never repetitive
- [ ] **Show scheduler** — timeline in the UI
  - "At 0:00 play startup, every 5 min a random sequence, at 1:00 play cantina"
  - Export/import of show programs (.json)
  - Ideal for conventions with a precise schedule

---

## 🌱 Priority 7 — Small sensors, big impact (~$15 hardware)

> Without a mic or camera, R2 can already react to its physical environment.

- [ ] **HC-SR04 ultrasonic sensor** on the Slave (GPIO)
  - Someone approaches within <1m → dome turns toward them + "curious" sound
  - Can be disabled in silent mode
- [ ] **MPU6050 accelerometer** on the Slave (I2C)
  - R2 gets bumped → "surprised" sound
  - R2 gets tilted → "alarm" sound + stabilization sequence

---

## 🔮 Future phase

> These features require extra hardware or are highly complex (beyond Phase 5 vision).

| Feature | Hardware required | Complexity |
|---|---|---|
| 🎙️ **Mic in the dome** — emotional context, voice commands, ambiance response | USB audio dongle ~$8 or TRRS jack on Master | ⭐⭐⭐ |
| 👁️ **Facial recognition** — greet by name, visitor memory (see Phase 5) | Camera + ML model | ⭐⭐⭐⭐⭐ |
| 🏷️ **NFC/RFID** — tap a badge to trigger a sequence | NFC module ~$8 | ⭐⭐ |
| 👥 **Multi-gamepad** — driver + operator (sounds/sequences) | 2nd BT gamepad | ⭐⭐ |
| 🌐 **External API / webhooks** — trigger the robot from IFTTT, Home Assistant, etc. | None | ⭐⭐ |

---

## 🧠 Master Pi architecture vision

The **Master Pi (dome) = central brain**:
- Flask API, sequences, dome servos, lights ← shipped
- BT gamepad via evdev (+ custom per-button actions) ← shipped
- **USB camera** (Phase 5) ← live streaming shipped · vision/AI in progress
- **USB mic** (future phase) ← listens to the ambiance
- **Show Mode** (Priority 6) ← coordinates everything autonomously

The Slave Pi (body) stays focused on the physical hardware: propulsion, body servos, audio, sensors.

---

*Last updated: 2026-05-23 (generic hostnames `astromech-master`/`astromech-slave` · R2-D2 = example droid)*
