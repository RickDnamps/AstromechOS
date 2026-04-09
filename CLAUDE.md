# R2-D2 Project — Claude Code Context

> Hardware complet, câblage, alimentation, I2C/GPIO → **[ELECTRONICS.md](ELECTRONICS.md)**

---

## 🔧 Workflow preferences
- No confirmation prompts for standard code changes
- Make changes directly and summarize after
- Only ask if genuinely ambiguous or destructive (delete entire module, force-push, etc.)

---

## ⚙️ Instructions Claude Code
- **Toujours committer et pusher sur GitHub après chaque modification**
- Ne jamais laisser des changements non commités en fin de session
- **Toujours terminer avec le déploiement SSH direct** via paramiko :
  ```python
  import paramiko, sys, io
  sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
  c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
  c.connect('192.168.2.104', username='artoo', password='deetoo', timeout=10)
  stdin, stdout, stderr = c.exec_command('cd /home/artoo/r2d2 && bash scripts/update.sh 2>&1')
  for line in stdout: print(line, end='')
  c.close()
  ```
  > ⚠️ `sshpass` non disponible sur Windows Git Bash — toujours utiliser `paramiko`
  > ⚠️ Ne jamais git commit/push depuis le Pi — toujours depuis le PC de dev
  > ⚠️ IPs réelles : Master=`192.168.2.104`, Slave=`192.168.4.171` — ne pas utiliser `.local` (mDNS capricieux sur Windows)

- Si déploiement SSH impossible, une seule commande sur le Master :
  ```bash
  cd /home/artoo/r2d2 && git pull && bash scripts/update.sh
  ```

- **Audio channels** — configurable in Config tab (web UI) → writes `master/config/local.cfg` `[audio] audio_channels` + SCPs `slave/config/slave.cfg` + restarts services.
  Default: 6. Range: 1–12.

---

## 🎯 Vision
Système de contrôle distribué pour une réplique R2-D2 grandeur nature.
**Master Pi** (dôme) — Flask API, séquences, servos dôme, Teeces32, déploiement.
**Slave Pi** (corps) — VESCs propulsion, servos body, audio, moteur dôme, RP2040 LCD.
Communication via UART physique 115200 baud à travers le slipring.
Inspiré de [r2_control by dpoulson](https://github.com/dpoulson/r2_control).

---

## 🏗️ Structure du repo

```
r2d2/
├── master/
│   ├── main.py                  ← boot + init services
│   ├── uart_controller.py       ← heartbeat 200ms + CRC
│   ├── teeces_controller.py     ← JawaLite (random/leia/off/text/psi)
│   ├── deploy_controller.py     ← git pull + rsync + bouton dôme
│   ├── script_engine.py         ← exécuteur séquences .scr
│   ├── app_watchdog.py          ← heartbeat App↔Master 600ms
│   ├── motion_watchdog.py       ← timeout drive 800ms
│   ├── safe_stop.py             ← ramp vitesse → 0
│   ├── registry.py              ← injection dépendances Flask
│   ├── flask_app.py             ← app factory
│   ├── drivers/
│   │   ├── dome_servo_driver.py ← PCA9685 @ 0x40, speed ramp, open/close par angle
│   │   ├── dome_motor_driver.py ← envoie D: via UART
│   │   └── body_servo_driver.py ← envoie SRV: via UART
│   ├── api/                     ← Flask blueprints (audio/motion/servo/script/teeces/status)
│   ├── sequences/               ← 40 séquences .scr (CSV)
│   ├── config/
│   │   ├── dome_angles.json     ← calibrations servos dôme (gitignored — propre au robot)
│   │   ├── main.cfg             ← config principale
│   │   └── local.cfg            ← credentials WiFi/hotspot (gitignored)
│   ├── templates/index.html     ← dashboard web (6 onglets)
│   └── static/                  ← CSS + JS
├── slave/
│   ├── main.py
│   ├── uart_listener.py         ← parse CRC + callbacks
│   ├── watchdog.py              ← coupe VESC si heartbeat >500ms
│   ├── drivers/
│   │   ├── audio_driver.py      ← mpg123 + sounds_index.json
│   │   ├── display_driver.py    ← RP2040 via /dev/ttyACM* (dynamique — ACM0/ACM1/ACM2 selon boot)
│   │   ├── vesc_driver.py       ← VESC ERPM propulsion (native CRC-16, no pyvesc)
│   │   ├── vesc_can.py          ← COMM_FORWARD_CAN, set_rpm_can/direct, get_values_can/direct
│   │   └── body_servo_driver.py ← PCA9685 @ 0x41
│   ├── config/
│   │   └── servo_angles.json    ← calibrations servos body (gitignored — propre au robot)
│   └── sounds/sounds_index.json ← 317 sons, 14 catégories (MP3 gitignorés)
├── shared/
│   └── uart_protocol.py         ← CRC somme mod 256, build_msg(), parse_msg()
├── rp2040/firmware/             ← MicroPython : GC9A01 display, écrans BOOT/OP/LOCKED
├── android/                     ← WebView app + APK compilé
├── tools/
│   └── stress_joystick.py       ← stress test joystick + monitor WiFi/CPU/latence via SSH
└── scripts/                     ← setup_*.sh, deploy.sh, update.sh
```

---

## 📡 Protocole UART — Checksum (somme mod 256)

**Algorithme obligatoire sur tous les messages** — bus UART traverse slipring + parasites 24V.

```python
def calc_crc(payload: str) -> str:
    return format(sum(payload.encode('utf-8')) % 256, '02X')

def build_msg(type: str, value: str) -> str:
    payload = f"{type}:{value}"
    return f"{payload}:{calc_crc(payload)}\n"

def parse_msg(raw: str) -> tuple[str, str] | None:
    parts = raw.strip().split(":")
    if len(parts) < 3: return None
    *payload_parts, received_cs = parts
    payload = ":".join(payload_parts)
    if received_cs != calc_crc(payload): return None
    return (payload_parts[0], ":".join(payload_parts[1:]))

# Exemples : build_msg("H","1") → "H:1:B3\n"  |  build_msg("M","50") → "M:50:EC\n"
```

> ⚠️ Somme arithmétique mod 256 — PAS XOR (deux octets identiques s'annulent avec XOR)
> Messages sans checksum = rejetés. Hex majuscule 2 chars (`00`–`FF`).

**Types de messages :**
```
H:1:CRC          Master→Slave heartbeat (200ms)      H:OK:CRC  ACK
M:L,R:CRC        Drive float [-1.0…1.0]
D:SPEED:CRC      Dome motor [-1.0…1.0]
S:FILE:CRC       Audio play   S:RANDOM:CAT:CRC   S:STOP:CRC
V:?:CRC          Version request    V:hash:CRC   reply
DISP:CMD:CRC     RP2040 display (BOOT/OK/ERROR/TELEM)
REBOOT:1:CRC     Reboot Slave
```

---

## 🌐 API REST Flask — port 5000

```
GET  /status                    → état JSON complet
POST /heartbeat                 ← app JS toutes les 200ms (watchdog 600ms)

POST /audio/play                {"sound": "Happy001"}
POST /audio/random              {"category": "happy"}
POST /audio/stop
POST /audio/volume              {"volume": 79}

POST /motion/drive              {"left": 0.5, "right": 0.5}
POST /motion/stop
POST /motion/dome/turn          {"speed": 0.3}
POST /motion/dome/stop
POST /motion/dome/random        {"enabled": true}

POST /servo/dome/open           {"name": "Servo_M0"}
POST /servo/dome/close          {"name": "Servo_M0"}
POST /servo/dome/open_all  /servo/dome/close_all
POST /servo/body/open           {"name": "Servo_S0"}
POST /servo/body/close          {"name": "Servo_S0"}
POST /servo/body/open_all  /servo/body/close_all
GET  /servo/list
POST /servo/settings            {"panels": {"Servo_M0": {"label":"Dome_Panel_1","open":110,"close":20,"speed":10}}}
GET  /servo/settings            → {panels: {Servo_M0: {label, open, close, speed}, ...}}

POST /scripts/run               {"name": "patrol", "loop": false}
POST /scripts/stop_all
GET  /scripts/list

POST /teeces/random  /teeces/leia  /teeces/off
POST /teeces/text               {"text": "HELLO"}
POST /teeces/psi                {"mode": 1}

POST /system/update             → git pull + rsync Slave + reboot
POST /system/reboot  /system/reboot_slave
POST /system/estop              → coupe PWM PCA9685 Master (0x40) + Slave (0x41), _ready=False
POST /system/estop_reset        → réarme les drivers servo (setup()) sans restart service
```

---

## 🚗 VESC Propulsion — Topology & Gotchas

**Hardware (2026-04-08) :** 2× Flipsky Mini V6.7, firmware v6.05, Hardware 60.
**Connexion :** Pi Slave → USB → **VESC ID 1** → CAN H/L → **VESC ID 2**
Un seul port série `/dev/ttyACM1` (ACM0 occupé par RP2040 — détection automatique via `display.used_port`).

```
Pi USB → VESC ID1 : set_rpm_direct(ser, erpm)
Pi USB → VESC ID2 : set_rpm_can(ser, can_id=2, erpm)  # COMM_FORWARD_CAN (0x21) + COMM_SET_RPM (0x08)
```

**Pas de pyvesc** — implémentation native CRC-16/CCITT dans `vesc_can.py`.
Raison : pip traite `PyCRC` et `pycrc` comme identiques (insensible casse) sur Python 3.13 → mauvais paquet installé.

**ERPM** (Electrical RPM) = RPM mécanique × nombre de pôles. Default MAX_ERPM = 50 000.
Override runtime : `VCFG:erpm:<valeur>` via UART depuis le Master.

**⚠️ "Multiple ESC over CAN" = DÉSACTIVÉ** sur les deux VESCs obligatoirement.
Si activé → les deux moteurs reçoivent la même commande → R2-D2 ne peut pas tourner.

**Limites hardware :** 25A courant moteur configuré dans VESC Tool (pas dans le code).

**Télémétrie :** VESC1 via `GET_VALUES` direct, VESC2 via `COMM_FORWARD_CAN` + `GET_VALUES`.
Envoyé au Master toutes les 200ms : `TL:v_in:temp:curr:rpm:duty:fault:CRC` et `TR:...`

**Batterie :** configurable dans Config tab (4S/6S/7S/8S). Défaut actuel = 4S (test).
Jauge : ≥3.8V/cell vert · ≥3.6V orange · <3.6V rouge. Tous les indicateurs utilisent `BatteryGauge.voltToColor(v)`.

---

## 🎵 Audio & Teeces — Gotchas

**ALSA sur Pi 4B :**
```bash
amixer -c 0 cset numid=1 <vol>%   # ✅ seule commande qui marche
# ❌ Ne PAS utiliser : amixer sset 'Master' / sset 'PCM Playback Volume'
```
Volume UI → courbe racine cubique (exposant 1/3) : slider 50% → ALSA 79%.
**Lecture MP3 :** `mpg123 -q` — `aplay` supporte uniquement WAV/PCM.

**JawaLite (Teeces32 via /dev/ttyUSB0 @ 9600 baud) :**
```python
"0T1\r"   # animations aléatoires    "0T20\r"  # tout éteint
"0T6\r"   # mode Leia                "1MTEXTE\r" # texte FLD (max ~20 chars)
"4S1\r"   # PSI random
```

**Sons spéciaux (catégorie `special`) :** `Theme001` `Theme002` `CANTINA` `LEIA` `FAILURE` `WOLFWSTL` `Gangnam` `SWDiscoShort` `birthday`

---

## 🦾 Servos — Hardware IDs + Labels

**Naming convention (effective 2026-03-31):**
- `Servo_M0`–`Servo_M10` : canaux 0–10 du HAT Master (PCA9685 @ 0x40, dome)
- `Servo_S0`–`Servo_S10` : canaux 0–10 du HAT Slave  (PCA9685 @ 0x41, body)

L'ID hardware est immuable (lié au canal physique). Chaque servo a un **label éditable** affiché dans l'UI et la timeline CHOREO.

**JSON schema (`dome_angles.json` / `servo_angles.json`) :**
```json
{
  "Servo_M0": {"label": "Dome_Panel_1", "open": 110, "close": 20, "speed": 10},
  "Servo_M1": {"label": "Dome_Panel_2", "open": 110, "close": 20, "speed": 10}
}
```

Label sauvegardé via `POST /servo/settings` — inclus dans le payload panels.
Drivers (`dome_servo_driver.py`, `slave/body_servo_driver.py`) utilisent les IDs hardware.
Script_engine route : `Servo_M*` → dome driver, `Servo_S*` → body driver.

```python
pulse_us = 500 + (angle / 180.0) * 2000   # MG90S 180°
# Speed ramp : step 2°, delay = (10 - speed) * 3ms/step
# speed 10 = instant | speed 1 ≈ 1.2s pour 90°
```

Commande séquence avec override angle+vitesse : `servo,Servo_M0,open,40,8`

---

## 🛠️ Directives de codage

1. **Python 3.10+** — `try/except` sur tout I/O (UART, I2C, USB)
2. **Watchdog prioritaire** — ne jamais bloquer le thread watchdog
3. **Drivers isolés** — un fichier par périphérique, interface `BaseDriver`
4. **systemd** — `Restart=always`, `RestartSec=3`
5. **Logging** Python standard — INFO prod, DEBUG dev
6. **Config par .cfg** — jamais de hardcoding adresses/pins

---

## 📦 Réseau & Dépendances

**Hostnames / IPs :**
```
R2-Master → r2-master.local / 192.168.4.1 (hotspot) / 192.168.2.104 (WiFi maison)
R2-Slave  → r2-slave.local  / 192.168.4.171
SSH user  : artoo   Password : deetoo
```

**UART Pi 4B Trixie** — libérer ttyAMA0 du Bluetooth :
```bash
echo "dtoverlay=miniuart-bt" | sudo tee -a /boot/firmware/config.txt
# ✅ miniuart-bt = BT reste fonctionnel   ❌ disable-bt = BT coupé (plus de manettes)
```

**bgscan wlan1 désactivé** — le scan WiFi background causait des micro-coupures pendant le joystick.
Désactivé via dispatcher NM : `/etc/NetworkManager/dispatcher.d/99-disable-bgscan`
```bash
# S'exécute automatiquement à chaque connexion wlan1 :
wpa_cli -i wlan1 set_network 0 bgscan ""
```

**Dépendances Master :** `flask` `pyserial` `RPi.GPIO` `adafruit-pca9685` `paramiko` `python3-evdev` (apt uniquement — pas pip)
**Dépendances Slave :** `pyserial` `smbus2` `adafruit-pca9685` `RPi.GPIO` + `mpg123` `python3-smbus` (apt)
> ⚠️ **pyvesc NOT required** — VESC communication uses native CRC-16/CCITT in `vesc_can.py`.
> pyvesc conflicts with wrong `pycrc` package on Python 3.13 (pip case-insensitive). Do NOT add it back.

**Manette BT (evdev) :**
- `python3-evdev` doit être installé via `apt install python3-evdev` — PAS pip (Trixie externally-managed)
- Config persistante dans `master/config/bt_config.json`
- `ecodes.KEY.get(code)` / `ecodes.BTN.get(code)` retourne un **tuple** quand plusieurs alias (ex: `('BTN_B', 'BTN_EAST')`), pas une liste → toujours utiliser `isinstance(raw, (list, tuple))` pour normaliser
- Shield controller : B=BTN_EAST(305), X=BTN_NORTH(307), Y=BTN_WEST(308), Home=BTN_MODE
- Jumelage BT via l'UI web (scan/pair/unpair) — pas besoin de SSH
- `bt_config.json` mappings : `audio`→BTN_EAST, `panel_dome`→BTN_WEST, `panel_body`→BTN_NORTH, `estop`→BTN_MODE

**MP3 sons — attention :** Les 317 MP3 sont dans `slave/sounds/` sur le Slave Pi uniquement (gitignorés). Si le Slave est réinstallé ou les fichiers perdus, les restaurer depuis le PC de dev :
```python
# Tunnel SSH Master → Slave via paramiko + sftp.put()
# Les fichiers sont dans J:/R2-D2_Build/software/slave/sounds/*.mp3
# update.sh rsync a --exclude='sounds/*.mp3' mais les fichiers doivent exister initialement
```

---

## 🚀 Phases — État actuel

| Phase | Description | État |
|-------|-------------|------|
| 1 | UART + watchdog + audio + Teeces + RP2040 + déploiement | ✅ Complet |
| 2 | VESCs + moteur dôme + servos MG90S | ✅ Actif — VESC ID1 USB + CAN→ID2, ERPM natif |
| 3 | 40 séquences comportementales .scr | ✅ Actif |
| 4 | API REST + dashboard web (6 onglets) + Android | ✅ Actif |
| 4+ | Manette BT (evdev) + jumelage UI + mapping configurable | ✅ Actif |
| 5 | Caméra USB + suivi personne | 📋 Planifié |

**3 watchdogs actifs :** `app_watchdog.py` 600ms · `motion_watchdog.py` 800ms · `slave/watchdog.py` 500ms → coupe VESCs

**E-STOP :** bouton rouge dans l'UI → coupe tous les servos (PCA9685 SLEEP + `_ready=False`).
Bouton vert **RESET E-STOP** → `POST /system/estop_reset` → réarme les drivers sans restart.

**Joystick throttle :** `VirtualJoystick._move()` limité à 60 req/s (`performance.now()` throttle).
Visuel du knob reste immédiat — seuls les POST HTTP sont throttlés.

**RP2040 firmware flash** — `update.sh` synce maintenant `rp2040/` vers le Slave. Mais flasher le RP2040 reste manuel :
```bash
# Sur le Slave Pi — trouver le bon port (ACM* dynamique selon boot)
ls /dev/ttyACM*
sudo systemctl stop r2d2-slave
# Toujours effacer avant de copier (mpremote "Up to date" compare timestamps, pas le contenu)
python3 -m mpremote connect /dev/ttyACM1 rm :display.py
python3 -m mpremote connect /dev/ttyACM1 cp /home/artoo/r2d2/rp2040/firmware/display.py :display.py
python3 -m mpremote connect /dev/ttyACM1 reset
sudo systemctl start r2d2-slave
```
> ⚠️ `mpremote cp` dit "Up to date" si le timestamp device ≥ fichier source — TOUJOURS `rm :file` avant `cp` pour forcer la mise à jour.

**RP2040 design** — Écrans définis dans `docs/rp2040-mockup.html`. Écran OK = `SYSTEM STATUS: / OPERATIONAL` + barre bus health verte/orange (<80%). Pas de full redraw sur chaque update BUS (incremental via `full=True/False`).

**VERSION file** — `update.sh` écrit toujours `git rev-parse --short HEAD` dans `VERSION` (même si "already up to date"). Si ce fichier est périmé, le Slave voit un mismatch au boot → RP2040 affiche `SYNC FAILED`.

**Backlog :** DiagnosticMonitor (Teeces Show↔Diagnostic) · AstroPixels+ firmware extension (17 missing sequences — blocked on hardware)

---

## 💡 Lights tab — AstroPixels+ notes

**AstroPixels+ serial commands** (`@`-prefix, `\r` terminator) :
```
@0T{n}\r     FLD+RLD animation (T-codes — see below)
@{1|2|3}M{text}\r   FLD top / FLD bottom / RLD scrolling text
@{0|1|2}P{n}\r   PSI sequence (0=both, 1=front, 2=rear)
@4S{n}\r     PSI mode legacy (0=off, 1–8=colors)
@HP{target}{effect}\r   Holo projectors
```

**T-codes valides sur AstroPixels+** (8 sur 22 JawaLite) :
`T1`=Random, `T2`=Flash, `T3`=Alarm, `T4`=Short Circuit, `T5`=Scream, `T6`=Leia, `T11`=Imperial March, `T20`=Off.
Les autres T-codes (T7-T10, T12-T19, T21, T92) sont Teeces32-only — silently ignored par AstroPixels+.

**T-codes n'affectent QUE FLD+RLD** — PSI est contrôlé séparément via `@0P{n}`.

**Text targets** (`/teeces/text`) : `fld_top` | `fld_bottom` | `fld_both` | `rld` | `all`
Color non configurable via serial — firmware utilise `randomColor()`.

**PSI sequences** (`/teeces/psi_seq`) : `normal` | `flash` | `alarm` | `failure` | `redalert` | `leia` | `march`
7 séquences accessibles via serial sur 24 présentes dans le firmware (les autres = boutons physiques seulement).

**Lights tab** (onglet LIGHT) :
- Animations : 22 chips one-click (8 réels sur AstroPixels+, 22 sur Teeces32) + STOP ALL (`/teeces/off`)
- Text : display selector `fld_top/fld_bottom/fld_both/rld/all` + champ texte
- PSI : target `both/fpsi/rpsi` + sequence selector + SET PSI / RESET PSI
- La section "Light Sequences" a été retirée de l'onglet (les `.lseq` restent dans le backend)
- Light Editor admin tab a été retiré du dashboard

---

## 🌐 Code Language Standard (effective 2026-03-28)

**All new code must use English** for comments, docstrings, log messages, and error strings.
This applies to every file going forward. Existing French in untouched files is acceptable until refactored.

**Commit convention additions:** `Feat:` · `Fix:` · `Config:` · `Docs:` · `Refactor:`

---

## ✅ Implementation Status

### ChoreoPlayer VESC Telemetry (2026-03-28) — commit `2287eec`
UART fail-safe, telemetry thresholds (20V/80°C/30A), `GET /choreo/status` returns `abort_reason` + `telem`.

### Choreo Timeline UI — Sprint 6.3 (2026-03-28 → 2026-03-31)
| Feature | Status |
|---------|--------|
| Liquid timeline fill + multiplicative zoom + dynamic ruler | ✅ |
| Block labels: TEXT/HOLO/PSI show mode prefix | ✅ |
| Choreo dropdown preserved on tab switch | ✅ |
| Lights tab: STOP ALL → `/teeces/off`, Light Sequences section removed | ✅ |
| AstroPixels+ text/PSI controls fixed (correct targets, real PSI sequences) | ✅ |
| PSI simulation independent of T-code animations (per firmware) | ✅ |
| AstroPixels+ ANIMATIONS override (8 valid T-codes only) | ✅ |
| Choreo font sizes standardized (blocks 10px, labels 9px, ruler 9px) | ✅ |

### VESC Phase 2 Activation (2026-04-08) — commit `921e257`
| Feature | Status |
|---------|--------|
| Single USB topology: VESC ID1 via `/dev/ttyACM1`, VESC ID2 via `COMM_FORWARD_CAN` (ID 33) | ✅ |
| Native CRC-16/CCITT packet building — pyvesc removed (PyCRC/pycrc conflict on Py 3.13) | ✅ |
| ERPM commands: `set_rpm_direct()` + `set_rpm_can()` — synchronous in same lock | ✅ |
| Telemetry: VESC1 via `get_values_direct()`, VESC2 via `get_values_can()` → TL:/TR: UART | ✅ |
| Port detection: RP2040 (`display.used_port`) excluded from VESC ACM candidate list | ✅ |
| `VCFG:erpm:<value>` — runtime MAX_ERPM override (default 50 000) | ✅ |
| Watchdog callbacks wired: `vesc.stop()` on UART timeout, `vesc.shutdown()` on SIGTERM | ✅ |

**Hardware validé :** Flipsky Mini V6.7, firmware v6.05 (Hardware 60), ID1=USB, ID2=CAN.
**ERPM par défaut :** 50 000 — à calibrer selon moteurs (pôles × RPM mécanique max).
**"Multiple ESC over CAN" doit être DÉSACTIVÉ** sur les deux VESCs — sinon même commande sur les deux → impossible de tourner.

### Battery Gauge — Configurable Cell Count (2026-04-08) — commit `d9a06cc`
| Feature | Status |
|---------|--------|
| `GET /settings` + `POST /settings/config` support `battery.cells` (stored in `local.cfg [battery]`) | ✅ |
| Config tab BATTERY section — 4S/6S/7S/8S selector, APPLY sans restart | ✅ |
| `BatteryGauge.setCells(n)` — recalcule MIN_V/MAX_V (3.5V/cell → 4.2V/cell) | ✅ |
| `BatteryGauge.voltToColor(v)` — seuils par cellule : ≥3.8V vert, ≥3.6V orange, <3.6V rouge | ✅ |
| `BatteryGauge.voltToPct(v)` — pourcentage selon pack configuré | ✅ |
| Tous les indicateurs utilisent ces helpers : header arc, drive arc, VESC tab bar, ChoreoPlayer | ✅ |
| `GET /status` retourne `battery_voltage` (v_in de VESC L ou R) | ✅ |
| Défaut : 4S (batterie de test). Batterie finale prévue : 6S. | ✅ |

### Servo Hardware IDs + Labels (2026-03-31) — commit `ba0a802`
| Feature | Status |
|---------|--------|
| `dome_panel_N` → `Servo_M{N-1}`, `body_panel_N` → `Servo_S{N-1}` | ✅ |
| Editable label field per servo, saved in JSON config | ✅ |
| Labels displayed in CHOREO timeline blocks + inspector dropdown | ✅ |
| 29 .scr + 30 .chor files migrated | ✅ |
| Servo tab layout full-width (1fr 1fr) | ✅ |

---

## 🐙 GitHub & Déploiement

```
Repo : https://github.com/RickDnamps/R2D2_Control.git   Branch : main
```

**Workflow :** `git add <fichiers> && git commit -m "Phase X.Y: desc" && git push`
→ `scripts/update.sh` sur Master déploie automatiquement (rsync slave/ + reboot Slave)

**Bouton dôme :** court = git pull + rsync + reboot Slave | long = rollback HEAD^

**Conventions commit :** `Phase X.Y:` · `Fix:` · `Config:` · `Docs:` · `ci:`

---

## 📱 Build Android

```bash
# Build APK
powershell.exe -Command "& { \$env:JAVA_HOME='C:/Program Files/Android/Android Studio/jbr'; Set-Location 'J:/R2-D2_Build/software/android'; ./gradlew.bat assembleDebug }"
cp android/app/build/outputs/apk/debug/app-debug.apk android/compiled/R2-D2_Control.apk
git add android/compiled/R2-D2_Control.apk && git commit -m "ci: update APK [skip ci]" && git push

# Installer via ADB
"C:/Users/erict/AppData/Local/Android/Sdk/platform-tools/adb.exe" install -r android/compiled/R2-D2_Control.apk
```

> ⚠️ Sync assets Android si `master/static/` ou `templates/index.html` change :
> `cp master/static/js/app.js android/app/src/main/assets/js/app.js`
> `cp master/static/css/style.css android/app/src/main/assets/css/style.css`
> `index.html` : patcher `/static/` → chemins relatifs + désactiver Service Worker
