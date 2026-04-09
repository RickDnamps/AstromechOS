# R2-D2 Project — Claude Code Context

> Hardware, câblage, alimentation, I2C/GPIO → **[ELECTRONICS.md](ELECTRONICS.md)**

---

## 🔧 Workflow
- No confirmation prompts for standard code changes — make changes directly, summarize after
- Only ask if genuinely ambiguous or destructive

---

## ⚙️ Instructions Claude Code

- **Toujours committer + pusher après chaque modification**
- **Toujours terminer avec déploiement SSH (paramiko) :**
  ```python
  import paramiko, sys, io
  sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
  c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
  c.connect('192.168.2.104', username='artoo', password='deetoo', timeout=10)
  stdin, stdout, stderr = c.exec_command('cd /home/artoo/r2d2 && bash scripts/update.sh 2>&1')
  for line in stdout: print(line, end='')
  c.close()
  ```
  > ⚠️ `sshpass` non dispo sur Windows — toujours `paramiko`
  > ⚠️ Ne jamais git push depuis le Pi — toujours depuis le PC dev
  > ⚠️ IPs : Master=`192.168.2.104`, Slave=`192.168.4.171` (pas `.local` — mDNS capricieux)

- Fallback si SSH impossible : `cd /home/artoo/r2d2 && git pull && bash scripts/update.sh`
- Audio channels : Config tab → `local.cfg [audio] audio_channels` + SCP slave.cfg. Default 6, range 1–12.

---

## 🎯 Architecture

**Master Pi** (dôme) — Flask API, séquences, servos dôme, Teeces32, déploiement.
**Slave Pi** (corps) — VESCs propulsion, servos body, audio, moteur dôme, RP2040 LCD.
UART physique 115200 baud à travers le slipring. Inspiré de [r2_control by dpoulson](https://github.com/dpoulson/r2_control).

```
master/
  main.py            boot + init services
  uart_controller.py heartbeat 200ms + CRC
  choreo_player.py   TICK=50ms, multichannel audio, VESC drive, servo interp
  script_engine.py   exécuteur séquences .scr
  registry.py        injection dépendances Flask
  flask_app.py       app factory + blueprints
  drivers/           dome_servo(PCA9685@0x40)  dome_motor  body_servo(UART)
  api/               blueprints audio/motion/servo/script/teeces/status/vesc/camera
  config/            main.cfg  local.cfg(gitignored)  dome_angles.json(gitignored)
slave/
  uart_listener.py   parse CRC + callbacks
  watchdog.py        coupe VESC si heartbeat >500ms
  drivers/           audio(mpg123)  display(RP2040/ACM*)  vesc_driver  vesc_can  body_servo(PCA9685@0x41)
  config/            servo_angles.json(gitignored)
shared/uart_protocol.py   CRC somme mod 256
rp2040/firmware/          MicroPython GC9A01 display
android/                  WebView app + APK compilé
```

---

## 📡 Protocole UART — Checksum (somme mod 256)

```python
def calc_crc(payload: str) -> str:
    return format(sum(payload.encode('utf-8')) % 256, '02X')
# build_msg("H","1") → "H:1:B3\n"   parse_msg strips last field as CRC
```

> ⚠️ Somme arithmétique — PAS XOR. Messages sans checksum rejetés. Hex majuscule 2 chars.

**Types de messages UART :**
```
H:1:CRC        heartbeat Master→Slave 200ms      H:OK:CRC ACK
M:L,R:CRC      drive float [-1.0…1.0]
D:SPEED:CRC    dome motor [-1.0…1.0]
S:FILE:CRC     audio play   S:RANDOM:CAT:CRC   S:STOP:CRC
DISP:CMD:CRC   RP2040 display
VCFG:scale:X   power scale   VCFG:erpm:N   MAX_ERPM override
VINV:L:0/1     motor direction explicit (0=normal 1=inverted)
TL/TR:v:t:c:rpm:duty:fault   VESC telemetry Slave→Master
REBOOT:1:CRC   reboot Slave
```

---

## 🌐 API REST Flask — port 5000

```
GET  /status                    état JSON complet
POST /heartbeat                 watchdog 600ms

POST /audio/play                {"sound":"Happy001"}
POST /audio/random              {"category":"happy"}
POST /audio/stop
POST /audio/volume              {"volume":79}

POST /motion/drive              {"left":0.5,"right":0.5}
POST /motion/stop
POST /motion/dome/turn          {"speed":0.3}
POST /motion/dome/stop
POST /motion/dome/random        {"enabled":true}

POST /servo/dome/open|close     {"name":"Servo_M0"}
POST /servo/dome/open_all|close_all
POST /servo/body/open|close     {"name":"Servo_S0"}
POST /servo/body/open_all|close_all
GET  /servo/list
GET  /servo/settings
POST /servo/settings            {"panels":{"Servo_M0":{"label":"..","open":110,"close":20,"speed":10}}}

POST /scripts/run               {"name":"patrol","loop":false}
POST /scripts/stop_all
GET  /scripts/list

POST /teeces/random|leia|off
POST /teeces/text               {"text":"HELLO"}
POST /teeces/psi                {"mode":1}

POST /system/update|reboot|reboot_slave
POST /system/estop              coupe PWM PCA9685 Master+Slave, _ready=False
POST /system/estop_reset        réarme drivers sans restart

GET  /vesc/telemetry            {connected,power_scale,L:{v_in,temp,current,rpm,duty,fault,fault_str},R:…}
GET  /vesc/config               {power_scale,invert_L,invert_R}
POST /vesc/config               {"scale":0.8}  → persisted local.cfg [vesc]
POST /vesc/invert               {"side":"L","state":true}  → persisted local.cfg [vesc]
GET  /vesc/can/scan             CAN bus scan via VESC1 USB (timeout 8s)

POST /camera/take               claim MJPEG stream → {token}
GET  /camera/stream?t=TOKEN     proxy last-connect-wins (evicted client → STREAM TAKEN overlay)
GET  /camera/status             {active_token}
```

---

## 🚗 VESC — Gotchas

**Hardware :** 2× Flipsky Mini V6.7, fw v6.05, HW60. ID1=USB `/dev/ttyACM1`, ID2=CAN.
RP2040 occupe ACM0 — détection auto via `display.used_port`.

**Pas de pyvesc** — CRC-16/CCITT natif dans `vesc_can.py` (pip confond PyCRC/pycrc sur Py3.13).

**ERPM :** RPM mécanique × pôles. MAX_ERPM=50000 default. Override : `VCFG:erpm:<N>`.

**Power scale :** multiplicatif — `effective = input × power_scale` (pas un clamp).
Drive 50% × Power 50% = 25% ERPM. `HARDWARE_SPEED_LIMIT=0.85` = safety cap absolu après.
Sauvegardé `local.cfg [vesc] power_scale`, relu au boot.

**Direction :** `VINV:L:1/0` état explicite (plus toggle aveugle). Sauvegardé `local.cfg [vesc] invert_l/r`.
`reg.vesc_invert_L/R` dans registry, init depuis cfg au boot.

**⚠️ "Multiple ESC over CAN" = DÉSACTIVÉ** sur les deux VESCs — sinon même commande → impossible de tourner.

**Télémétrie :** `TL/TR:v_in:temp:curr:rpm:duty:fault:CRC` toutes les 200ms.
Abort thresholds ChoreoPlayer : `cells×3.5V` min voltage · 80°C temp · 30A current · 3 UART failures.

**Batterie :** 4S/6S/7S/8S via Config tab. Seuils par cellule : ≥3.8V vert · ≥3.6V orange · <3.6V rouge.
Tous les indicateurs : `BatteryGauge.voltToColor(v)` / `voltToPct(v)`.

---

## 🎵 Audio & Teeces — Gotchas

**ALSA :** `amixer -c 0 cset numid=1 <vol>%` — seule commande qui marche sur Pi 4B.
Volume UI → courbe racine cubique : slider 50% → ALSA 79%. Lecture MP3 : `mpg123 -q`.

**JawaLite (Teeces32, /dev/ttyUSB0 @ 9600) :**
`0T1\r`=random · `0T20\r`=off · `0T6\r`=Leia · `1MTEXTE\r`=FLD text · `4S1\r`=PSI random

**AstroPixels+ serial (`@`-prefix, `\r` terminator) :**
```
@0T{n}\r          FLD+RLD animation   (T-codes valides: T1,T2,T3,T4,T5,T6,T11,T20 seulement)
@{1|2|3}M{text}\r FLD top/bottom/RLD text
@{0|1|2}P{n}\r    PSI sequence (0=both 1=front 2=rear)
@HP{target}{fx}\r holo projectors
```
T-codes n'affectent QUE FLD+RLD. PSI séparé. Text targets : `fld_top|fld_bottom|fld_both|rld|all`.
PSI sequences : `normal|flash|alarm|failure|redalert|leia|march`.

**Sons spéciaux :** `Theme001` `Theme002` `CANTINA` `LEIA` `FAILURE` `WOLFWSTL` `Gangnam` `SWDiscoShort` `birthday`

---

## 🦾 Servos — IDs + Labels

`Servo_M0`–`M10` = canaux 0–10 Master PCA9685 @ 0x40 (dome).
`Servo_S0`–`S10` = canaux 0–10 Slave PCA9685 @ 0x41 (body).
ID hardware immuable. Label éditable, sauvé dans `dome_angles.json` / `servo_angles.json`.

```json
{"Servo_M0": {"label":"Dome_Panel_1","open":110,"close":20,"speed":10}}
```

`pulse_us = 500 + (angle/180)*2000` · ramp : step 2°, delay=(10-speed)×3ms/step
Override séquence : `servo,Servo_M0,open,40,8`
script_engine route : `Servo_M*` → dome driver · `Servo_S*` → body driver.

---

## 📦 Réseau & Dépendances

```
Master  192.168.2.104 (WiFi) / 192.168.4.1 (hotspot)
Slave   192.168.4.171
SSH     artoo / deetoo
```

**UART Pi 4B Trixie :** `dtoverlay=miniuart-bt` (miniuart-bt = BT reste fonctionnel, pas disable-bt).

**bgscan wlan1 désactivé** via `/etc/NetworkManager/dispatcher.d/99-disable-bgscan` :
`wpa_cli -i wlan1 set_network 0 bgscan ""` — micro-coupures joystick sinon.

**Dépendances Master :** `flask pyserial RPi.GPIO adafruit-pca9685 paramiko requests` + `python3-evdev` (apt only)
**Dépendances Slave :** `pyserial smbus2 adafruit-pca9685 RPi.GPIO mpg123 python3-smbus` (apt)
> ⚠️ pyvesc = NE PAS installer (conflit PyCRC/pycrc Python 3.13)

**Manette BT (evdev) :**
- `apt install python3-evdev` (pas pip — Trixie externally-managed)
- `ecodes.KEY.get(code)` retourne un tuple quand plusieurs alias → `isinstance(raw, (list,tuple))`
- Shield : B=BTN_EAST(305), X=BTN_NORTH(307), Y=BTN_WEST(308), Home=BTN_MODE
- Config : `bt_config.json` · mappings : `audio`→E, `panel_dome`→W, `panel_body`→N, `estop`→MODE

**MP3 :** 317 fichiers dans `slave/sounds/` sur Slave Pi uniquement (gitignorés). Restaurer via paramiko+sftp si Slave réinstallé.

---

## 🚀 État actuel

| Phase | Description | État |
|-------|-------------|------|
| 1 | UART + watchdog + audio + Teeces + RP2040 + déploiement | ✅ |
| 2 | VESCs + moteur dôme + servos MG90S | ✅ |
| 3 | 40 séquences comportementales .scr | ✅ |
| 4 | API REST + dashboard web + Android | ✅ |
| 4+ | BT gamepad + CHOREO timeline + VESC diagnostic | ✅ |
| 5 | Caméra USB + suivi personne | 📋 |

**Watchdogs :** app 600ms · drive 800ms · slave UART 500ms → coupe VESCs
**E-STOP :** toggle unique ARMED/TRIPPED → coupe PCA9685 Master+Slave (`_ready=False`).
**Joystick throttle :** 60 req/s max (visuel immédiat, seuls les POST HTTP sont throttlés).
**WASD** = propulsion · **Arrow keys** = dome rotation (séparés).
**Drive tab** : camera MJPEG proxy last-connect-wins · speed arc HUD · direction arrow HUD.
**VESC tab** : barres temp/current/duty · Power(W) · symétrie L/R · session peaks · fault log.
**Header** : `#temp-label` min-width fixe — pas de layout shift sur changement de valeur.

**RP2040 flash (manuel) :**
```bash
python3 -m mpremote connect /dev/ttyACM1 rm :display.py
python3 -m mpremote connect /dev/ttyACM1 cp /home/artoo/r2d2/rp2040/firmware/display.py :display.py
```
> ⚠️ Toujours `rm` avant `cp` — mpremote compare timestamps, pas contenu.
> VERSION file : `update.sh` écrit toujours le hash git — si périmé → RP2040 affiche `SYNC FAILED`.

**Backlog :** AstroPixels+ 17 séquences manquantes (bloqué hardware) · DiagnosticMonitor Teeces

---

## 💡 ChoreoPlayer — Gotchas

**File :** `master/choreo_player.py` — TICK=50ms
**Audio multichannel :** jusqu'à 12 tracks simultanés. Si slots pleins → preempt le plus ancien.
**Drive blocks :** `vesc.drive(left,right)` discret aux timestamps. Pas de software ramping — VESC firmware gère accélération. `0,0` = stop explicite.
**Servo interp :** dome (I2C) = easing+slew. Body (UART) avancé de `body_servo_uart_lat`=25ms.
**Abort :** `cells×3.5V` min · 80°C · 30A · 3 UART fails → `GET /choreo/status` retourne `abort_reason`.

---

## 🌐 Code Standard

All new code → **English** comments/docstrings/logs. Existing French acceptable in untouched files.
Commits : `Feat:` · `Fix:` · `Config:` · `Docs:` · `Refactor:` · `ci:`

---

## 🐙 GitHub & Déploiement

```
Repo : https://github.com/RickDnamps/R2D2_Control.git   Branch : main
```

**Bouton dôme :** court = git pull + rsync + reboot Slave · long = rollback HEAD^

---

## 📱 Build Android

```bash
powershell.exe -Command "& { \$env:JAVA_HOME='C:/Program Files/Android/Android Studio/jbr'; Set-Location 'J:/R2-D2_Build/software/android'; ./gradlew.bat assembleDebug }"
cp android/app/build/outputs/apk/debug/app-debug.apk android/compiled/R2-D2_Control.apk
"C:/Users/erict/AppData/Local/Android/Sdk/platform-tools/adb.exe" install -r android/compiled/R2-D2_Control.apk
```

> ⚠️ Sync assets si `master/static/` change :
> `cp master/static/js/app.js android/app/src/main/assets/js/app.js`
> `cp master/static/css/style.css android/app/src/main/assets/css/style.css`
