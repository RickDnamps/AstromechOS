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

**Master Pi 4B 4GB** (dôme, tourne avec slipring) — Flask API, séquences, servos dôme, Teeces32, déploiement. Future AI : face/voice recognition en local (Vosk/Whisper.cpp + OpenCV) — toujours sur le Master.
**Slave Pi 4B 2GB** (corps, fixe) — VESCs propulsion, servos body, audio mpg123, moteur dôme, RP2040 LCD. Délibérément léger (pas d'IA, pas de Flask) — réactivité temps-réel prioritaire.
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
  api/               blueprints audio/motion/servo/script/teeces/status/vesc/camera/choreo
  config/            main.cfg  local.cfg(gitignored)  dome_angles.json(gitignored)  choreo_categories.json
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

GET  /servo/arms                {count, servos:["Servo_S0",...], panels:["Servo_S5",...]}
POST /servo/arms                {count:2, servos:["Servo_S0","Servo_S1"], panels:["Servo_S5","Servo_S6"]}
  → local.cfg [arms] count/arm_1..arm_N/panel_1..panel_N

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

GET  /choreo/list               [{name, label, category, emoji, duration}, …]  ← retourne objets, PAS strings
POST /choreo/play               {"name":"foo","loop":true}
POST /choreo/stop
GET  /choreo/status             {running, name, progress, loop, abort_reason}
GET  /choreo/categories         [{id, label, emoji, order}, …]
POST /choreo/categories         create/update/reorder/delete categories
POST /choreo/category           {"name":"foo.chor","category":"emotion"}
POST /choreo/emoji              {"name":"foo.chor","emoji":"🎭"}
POST /choreo/label              {"name":"foo.chor","label":"My Label"}
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
`Servo_S0`–`S11` = canaux 0–11 Slave PCA9685 @ 0x41 (body).
ID hardware immuable. Label éditable, sauvé dans `dome_angles.json` / `servo_angles.json`.

**Arms config (`local.cfg [arms]`) :**
```ini
count = 2
arm_1 = Servo_S0
arm_2 = Servo_S1
panel_1 = Servo_S5    # body panel à ouvrir avant l'extension du bras 1
panel_2 = Servo_S6
```
Les panels body (S0–S11 seulement, pas S12–S15) sont optionnels — si non défini, le bras s'ouvre directement.

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
- **Keep-alive :** evdev n'envoie `EV_ABS` que sur CHANGEMENT de valeur. Joystick maintenu immobile = aucun event = MotionWatchdog fire à 800ms. Solution : thread `bt-keepalive` renvoie le dernier `(left, right)` toutes les 300ms pendant que `_drive_active=True`.
- **Panneaux config-aware :** les boutons dome/body utilisent `_read_panels_cfg()` / `_panel_angle()` / `_panel_speed()` de `master.api.servo_bp` pour respecter les angles calibrés.
- **Batterie + RSSI :** thread `bt-hw-poll` toutes les 30s — batterie via `/sys/class/power_supply/hid-<mac>-battery/capacity` · RSSI via `hcitool rssi <mac>`.
- **Timeout inactivity :** slider 0-600s + champ numérique 0-3600s dans le Config tab.

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
| 4++ | Caméra USB autodetect + BT battery/RSSI + keepalive + admin timers | ✅ |
| 4+++ | Choreo admin guard · Arms body-panel auto-dispatch · Settings sidebar refonte · Choreo toolbar/footer | ✅ |
| 4++++ | Sequences tab redesign : catégories + emoji + pills/grid + drag-to-pill + loop + playing state · Choreo body servo inspector filtre les arm servos | ✅ |
| 5 | Caméra USB stream ✅ (temp webcam) · caméra permanente commandée · suivi personne AI | 📋 |

**Watchdogs :** app 600ms · drive 800ms · slave UART 500ms → coupe VESCs
**E-STOP :** toggle unique ARMED/TRIPPED → coupe PCA9685 Master+Slave (`_ready=False`). Bouton UI uniquement — le raccourci clavier Space a été retiré.
**Joystick throttle :** 60 req/s max (visuel immédiat, seuls les POST HTTP sont throttlés).
**WASD** = propulsion · **Arrow keys** = dome rotation (séparés).
**Drive tab** : camera MJPEG proxy last-connect-wins · auto-reconnect après restart service · USB autodetect via sysfs · speed arc HUD · direction arrow HUD.
**Caméra permanente commandée :** 3.6mm lens OTG UVC 720/1080P 30FPS, drive-free, Linux plug-and-play. Assez petite pour loger dans le holo projector. Sort du MJPEG hardware-compressé nativement → zéro charge CPU Pi 4B, autodetectée par le scan sysfs existant sans aucun changement de code.
**VESC tab** : barres temp/current/duty · Power(W) · symétrie L/R · session peaks · fault log.
**Header** : `#temp-label` min-width fixe — pas de layout shift sur changement de valeur.

**RP2040 flash (manuel) :**
```bash
python3 -m mpremote connect /dev/ttyACM1 rm :display.py
python3 -m mpremote connect /dev/ttyACM1 cp /home/artoo/r2d2/rp2040/firmware/display.py :display.py
```
> ⚠️ Toujours `rm` avant `cp` — mpremote compare timestamps, pas contenu.
> VERSION file : `update.sh` écrit toujours le hash git — si périmé → RP2040 affiche `SYNC FAILED`.

**Admin inactivity :** tous les onglets trackés via `_activeTabId` (set dans `onTabSwitch()`) · `pointerdown` au lieu de `click` (Choreo editor bloque `click` via `preventDefault()`).

**Choreo Admin Guard :**
- Save / Delete / Export / Import → protégés par mot de pass admin
- New / Play / Stop / Load → libres (pas de auth)
- `_choreoUnlocked` flag de session : mis à `true` après première auth dans CHOREO tab, reset à `false` en quittant l'onglet
- `adminGuard._pendingCallback` : callback stocké dans `showModal()`, exécuté dans `_unlock()` après auth réussie
- `choreoEditor.save({ requireAuth: false })` — contourne la garde pour les auto-saves internes (ex: play sur fichier modifié)

**Settings menu (iPad-style sidebar) :**
12 panneaux : Bluetooth · Lock Mode · Arms · Calibration (ex-Servos) · VESC · Lights · Battery · Audio · Camera · Network · Deploy · System
`switchSettingsPanel(panelId)` → lazy-load par panneau · `if (panelId === 'arms') armsConfig.load()`

**Choreo toolbar layout :**
- Dropdown + NEW + DELETE → groupe gauche
- `chor-cmd-gap` (margin: 0 20px = 41px) entre DELETE et PLAY
- Timecode + durée déplacés dans `chor-footer` (barre 26px en bas de la timeline)

**Sequences tab (pills + grid layout) :**
- `master/config/choreo_categories.json` — 6 catégories persistantes : `performance/emotion/behavior/dome/test/newchoreo`. Écriture atomique via `.tmp` + `os.replace()`.
- `/choreo/list` retourne **objets** `{name, label, category, emoji, duration}` (plus des strings) — backward-compat dans le dropdown choreo editor via `n.name || n`.
- `ScriptEngine` JS : `_renderPills()` (catégories) + `_renderGrid()` (cartes) + `_attachCardEvents()` + `_attachDrag()` + `_startRename()`.
- **Loop mode :** `choreo_player.py` — `self._loop` flag, `play(loop=)` param, restart de `t_start`/`ev_idx` quand `t_now >= duration` dans `_run()`.
- **Body servo inspector filtering :** `choreoEditor` — quand `armsConfig._count > 0`, les servo IDs de bras sont exclus du dropdown `body_servos`. Si count=0, tous les servos apparaissent.

**Gotchas JS critiques :**
- `.hidden` n'est PAS une classe utilitaire globale — seulement définie pour sélecteurs spécifiques. Utiliser `style.display` ou ajouter une règle CSS dédiée.
- `setPointerCapture` dans `pointerdown` = casse tous les clicks enfants. Doit être appelé uniquement dans `pointermove` APRÈS le seuil de drag (8px).
- `--teal` n'existait PAS dans `:root` (seulement `--cyan`). Ajouter une variable CSS custom nécessite de vérifier sa définition dans `:root`.
- Quand git pull échoue sur le Pi (local changes non committées) → `git stash` puis pull.

**Backlog :** AstroPixels+ 17 séquences manquantes (bloqué hardware) · DiagnosticMonitor Teeces
**Backlog futur :** AS5600 encoder I2C absolu magnétique pour position dôme (0–360° absolu, pas de dérive) · VESC safety lock si VESC absent/fault · IP Pi sur RP2040 LCD au boot

---

## 💡 ChoreoPlayer — Gotchas

**File :** `master/choreo_player.py` — TICK=50ms
**Audio multichannel :** jusqu'à 12 tracks simultanés. Si slots pleins → preempt le plus ancien.
**Drive blocks :** `vesc.drive(left,right)` discret aux timestamps. Pas de software ramping — VESC firmware gère accélération. `0,0` = stop explicite.
**Servo interp :** dome (I2C) = easing+slew. Body (UART) avancé de `body_servo_uart_lat`=25ms.
**Abort :** `cells×3.5V` min · 80°C · 30A · 3 UART fails → `GET /choreo/status` retourne `abort_reason`.
**Loop :** `play(chor, loop=True)` → `self._loop=True` → en fin de sequence dans `_run()`, reset `t_start = time.monotonic()` et `ev_idx = 0` sans sortir du loop si `not self._stop_flag.is_set()`.

**Arms — auto-dispatch panel body :**
- `_ARM_PANEL_DELAY = 0.5` secondes entre panel open et arm extension (et entre arm close et panel close)
- `_read_arm_panel_map()` lit `local.cfg [arms]` au début de chaque `_run()` → retourne `{arm_servo_id: panel_servo_id}`
- Si bras a un panel associé : open arm → ouvre panel → attend 0.5s → ouvre bras. Close arm → ferme bras → attend 0.5s → ferme panel.
- `threading.Timer` non-bloquant, daemon=True

**Durée playback vs durée visuelle :**
- `_calcTotalDuration()` = max(last_event_end + 2.0, 5.0) → canvas/ruler (padding visuel)
- `_calcPlaybackDuration()` = max(last_event_end + 0.1, 1.0) → `meta.duration` envoyé au Pi
- Pi s'arrête 100ms après le dernier event (plus les 2s de silence d'avant)

---

## 🌐 Code Standard

All new code → **English** comments/docstrings/logs. Existing French acceptable in untouched files.
Commits : `Feat:` · `Fix:` · `Config:` · `Docs:` · `Refactor:` · `ci:`

**⚠️ NEVER hardcode installation-specific values** (IPs, hostnames, ports) in Python source.
Always read from `local.cfg` via `configparser`. Pattern used everywhere:
```python
cfg = configparser.ConfigParser()
cfg.read([MAIN_CFG, LOCAL_CFG])
host = cfg.get('slave', 'host', fallback='r2-slave.local')
```
> The mDNS `.local` caveat in the network section applies to the **dev Windows PC → Pi** path.
> Pi-to-Pi (Master → Slave) uses `.local` OR the configured IP — never a hardcoded literal.
> Incident: `servo_bp` had `artoo@192.168.4.171` hardcoded → broke all other installations.

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


<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:ca08a54f -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

## Session Completion

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd dolt push
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
<!-- END BEADS INTEGRATION -->
