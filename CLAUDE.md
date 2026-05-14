# AstromechOS — Claude Code Context

> Hardware, câblage, alimentation, I2C/GPIO → **[ELECTRONICS.md](ELECTRONICS.md)**
> API REST complète → **[docs/API.md](docs/API.md)**
> Gotchas d'implémentation détaillés → `bd memories <keyword>` (camera, choreo, js, rp2040, admin, settings…)

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
  stdin, stdout, stderr = c.exec_command('cd /home/artoo/astromechos && bash scripts/update.sh 2>&1')
  for line in stdout: print(line, end='')
  c.close()
  ```
  > ⚠️ `sshpass` non dispo sur Windows — toujours `paramiko`
  > ⚠️ Sur Windows, appeler `python` (pas `python3` — introuvable, exit 127)
  > ⚠️ Ne jamais git push depuis le Pi — toujours depuis le PC dev
  > ⚠️ IPs : Master=`192.168.2.104`, Slave=`192.168.4.171` (pas `.local` — mDNS capricieux)

- Fallback si SSH impossible : `cd /home/artoo/astromechos && git pull && bash scripts/update.sh`
- Audio channels : Config tab → `local.cfg [audio] audio_channels` + SCP slave.cfg. Default 6, range 1–12.

---

## 🎯 Architecture

**Master Pi 4B 4GB** (dôme, tourne avec slipring) — Flask API, chorégraphies, servos dôme, lights controller, déploiement. Future AI : face/voice recognition en local (Vosk/Whisper.cpp + OpenCV) — toujours sur le Master.
**Slave Pi 4B 2GB** (corps, fixe) — VESCs propulsion, servos body, audio mpg123, moteur dôme, RP2040 LCD. Délibérément léger (pas d'IA, pas de Flask) — réactivité temps-réel prioritaire.
UART physique 115200 baud à travers le slipring. Inspiré de [r2_control by dpoulson](https://github.com/dpoulson/r2_control).

```
master/
  main.py            boot + init services
  uart_controller.py heartbeat 200ms + CRC
  choreo_player.py   TICK=50ms, multichannel audio, VESC drive, servo interp
  behavior_engine.py idle alive behaviors
  registry.py        injection dépendances Flask
  flask_app.py       app factory + blueprints
  drivers/           dome_servo(PCA9685@0x40)  dome_motor  body_servo(UART)
  api/               blueprints audio/motion/servo/teeces/status/vesc/camera/choreo/behavior
  config/            main.cfg  local.cfg(gitignored)  dome_angles.json(gitignored)  choreo_categories.json
  choreographies/    48 fichiers .chor (timeline JSON)
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
SHUTDOWN:1:CRC shutdown Slave (sudo shutdown -h now, 3s delay)
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

## 🎵 Audio & Lights — Gotchas

**ALSA :** `amixer -c 0 cset numid=1 <vol>%` — seule commande qui marche sur Pi 4B.
Volume UI → courbe racine cubique : slider 50% → ALSA 79%. Lecture MP3 : `mpg123 -q`.

**JawaLite + AstroPixels+ serial commands** → `ELECTRONICS.md §7` (tables complètes)

**Sons spéciaux :** `Theme001` `Theme002` `CANTINA` `LEIA` `FAILURE` `WOLFWSTL` `Gangnam` `SWDiscoShort` `birthday`

---

## 🦾 Servos — IDs + Labels

`Servo_M0`–`M15` = HAT 1 Master PCA9685 (dome) · `Servo_M16`–`M31` = HAT 2 · etc.
`Servo_S0`–`S15` = HAT 1 Slave PCA9685 (body)  · `Servo_S16`–`S31` = HAT 2 · etc.
ID hardware immuable. Label éditable, sauvé dans `dome_angles.json` / `servo_angles.json`.

**Config multi-HAT** (comma-separated) — éditable via Settings → System → Hardware :
```ini
# local.cfg (Master) — dome servo HATs
[i2c_servo_hats]
master_hats = 0x40           # ajouter ex: 0x40, 0x42 pour 32 servos dôme

# slave/config/slave.cfg — body servo HATs + motor HAT
[i2c_servo_hats]
slave_hats      = 0x41       # ajouter ex: 0x41, 0x42 pour 32 servos body
slave_motor_hat = 0x40       # ⚠️ guard — ne JAMAIS mettre cette adresse dans slave_hats
```
`slave_hats` + `slave_motor_hat` lus/écrits depuis `slave.cfg` via `_sync_slave_hat_cfg()` → SCP + restart Slave auto.
`master_hats` dans `local.cfg` → reboot Master requis.
BODY_SERVOS / DOME_SERVOS calculés une fois à l'import → reboot après changement.
Adresses PCA9685 : 0x40 (défaut) · 0x41 (A0) · 0x42 (A1) · 0x43 (A0+A1) · etc. via solder jumpers.
Voir ELECTRONICS.md §6 pour la table complète des adresses et le câblage.

**Arms config (`local.cfg [arms]`) :**
```ini
count = 2
arm_1 = Servo_S0
arm_2 = Servo_S1
panel_1 = Servo_S5    # body panel à ouvrir avant l'extension du bras 1
panel_2 = Servo_S6
delay_1 = 0.5         # secondes entre ouverture panel et extension bras (default 0.5)
delay_2 = 0.5
```
Panel optionnel — si absent, le bras s'ouvre directement sans attente.
Séquence open : `open panel → sleep(delay) → open arm` · close : `close arm → sleep(delay) → close panel`.
Chaque bras tourne dans son propre daemon thread — le Flask répond immédiatement.

**Auto-label** (save dans Arms Settings) : assigne automatiquement `Arm1`, `Arm1_panel`, etc.
Préserve les suffixes custom : `Arm1_Pince` reste inchangé si le label commence déjà par `Arm1`.
Réinitialise au servo ID uniquement si le servo est retiré de la config arms.

```json
{"Servo_M0": {"label":"Dome_Panel_1","open":110,"close":20,"speed":10}}
```

`pulse_us = 500 + (angle/180)*2000` · ramp : step 2°, delay=(10-speed)×3ms/step
Override choreo : `servo,Servo_M0,open,40,8` — `Servo_M*` → dome driver · `Servo_S*` → body driver.

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
| 3 | 40 séquences comportementales → migrées .chor | ✅ |
| 4 | API REST + dashboard web + Android | ✅ |
| 4+ | BT gamepad + CHOREO timeline + VESC diagnostic | ✅ |
| 4++ | Caméra USB autodetect + BT battery/RSSI + keepalive + admin timers | ✅ |
| 4+++ | Choreo admin guard · Arms body-panel auto-dispatch · Settings sidebar refonte · Choreo toolbar/footer | ✅ |
| 4++++ | Sequences tab redesign : catégories + emoji + pills/grid · Behavior engine ALIVE | ✅ |
| 4+++++ | Arms : séquence panel→delay→arm · all_body arm-aware · labels Calibration dans Choreo · auto-label prefix-safe | ✅ |
| 4++++++ | GPIO dome button retiré · Rollback web UI · Hardware config UI (HATs + uart_lat) · repo_url éditable | ✅ |
| 4+++++++ | CSS variable system · 8 built-in themes · Blueprint light · theme customizer with live preview · sci-fi fonts | ✅ |
| 4++++++++ | Topbar clean · Cockpit pills HB/UART/BT · pill SLAVE · E-STOP red overlay · STATUS button toujours à jour | ✅ |
| 4+++++++++ | Cockpit SERVICES diagnostic : Dome/Body Servo HATs · Motor HAT I2C probe · RP2040 Screen health | ✅ |
| 4++++++++++ | Slave Motor HAT addr configurable UI · SHUTDOWN UART cmd · system buttons 2×3 grid (Reboot/Shutdown × Master/Slave/Both) | ✅ |
| 4+++++++++++ | Rebrand R2D2→AstromechOS · dossier Pi `/home/artoo/astromechos` · services `astromech-*` · cache SW versionné par commit | ✅ |
| 4++++++++++++ | VESC safety helper unifié (`master/vesc_safety.py`) · slave boot banner + auto-resync VCFG/VINV · paired-side CAN liveness · telemetry key fix curr→current | ✅ |
| 4+++++++++++++ | E-STOP freeze · Reset stow lent (slew=3) · ChoreoPlayer event-driven scheduler · arm Timers respectent stop_flag · loop reset complet · /choreo/play locked | ✅ |
| 4+++++++++++++++++ | E-STOP servo freeze pattern (driver `_frozen` flag + UART `FREEZE:1/0`) · UI `emergencyStop()` ne race plus close_all contre le freeze · Reset E-STOP utilise `DOME_SERVOS` (fix ImportError silencieux) | ✅ |
| 4++++++++++++++ | Heartbeat ACK age tracking · UART buffer keep-trailing 256B · /status local.cfg cache TTL · StatusPoller in-flight · heartbeat visibility-aware | ✅ |
| 4+++++++++++++++ | UART RTT histogramme + `/diagnostics/uart_rtt` + bouton MEASURE/APPLY dans Settings · hot-swap `body_servo_uart_lat` (no reboot) | ✅ |
| 4++++++++++++++++ | Choreo full audit (2026-05-13, 33 items): scroll fix · path traversal · XSS escape · atomic .chor write · audio race lock · parallel servo reset (14× faster) · newChor schema · listener leaks · 11 patterns. Commits `31886ff..d38cf0f` | ✅ |
| 4+++++++++++++++++ | Drive full audit (2026-05-14, 44 items): estop_active gate · uncancellable safety ramp · BT keep-alive clear · Pointer Events joystick · multi-touch pointerId · NaN guard · vesc_safety atomic snapshot · CAN recovery hysteresis · stow_in_progress gate · arcade ratio normalize · kids cap server-side · HUD rAF batching · 17 patterns. Commits `98c7e16..ceb0d96` | ✅ |
| 5 | Caméra USB stream ✅ · caméra permanente commandée · suivi personne AI | 📋 |

**Watchdogs :** app 600ms · drive 800ms · slave UART 500ms → coupe VESCs
**E-STOP :** **freeze pur** — coupe propulsion+dôme+choreo, **aucun mouvement servo** (bras/panneaux gardent leur position).
- `DomeServoDriver._frozen` (Master) + UART `FREEZE:1` → `BodyServoDriver._frozen` (Slave). `_move_ramp` checke le flag à chaque step ET à l'entrée → in-flight ramps abort, nouvelles SRV rejetées. PWM tient la dernière position (full torque, pas de `shutdown()` qui mettrait PCA9685 en SLEEP = drooping).
- Frontend `emergencyStop()` ne doit JAMAIS envoyer `/servo/*/close_all` — uniquement `/system/estop`. Sinon les commandes close_all racent contre le freeze et les panneaux ramp vers close.

**Reset E-STOP :** stow lent à `_SAFE_SLEW_SPEED=3` (~1s/90°), réutilise les helpers `servo_bp` (`_read_arms_cfg`, `_panel_angle`, `BODY_SERVOS`, `DOME_SERVOS`).
- Séquence : (1) bras se rétractent en parallèle · (2) après leur `delay`, leur panneau se ferme · (3) tous les autres body panels en parallèle · (4) tous les dome panels en parallèle.
- ⚠️ Utiliser `DOME_SERVOS` de `servo_bp.py` (PAS `from dome_servo_driver import SERVO_MAP` qui n'existe pas — `_servo_map` est un attribut d'instance). Bug 2026-05-08 : ImportError silencieusement swallowée → step 4 skippé → dome panels jamais fermés.
**VESC safety :** `master/vesc_safety.py` source unique. `is_drive_safe()` utilisé par motion_bp / bt_controller / choreo_player (None telem = block sauf bench mode). `block_reason()` retourne tokens stables (`vesc_l_offline`, `vesc_r_stale`, `vesc_l_fault`).
**Slave reboot resync :** Slave envoie `BOOT:READY:CRC` à `uart.start()`. Master register `BOOT` callback → re-push `VCFG:scale` + `VINV:L/R`. Pas de drift de config après reboot Slave.
**Paired-side CAN liveness :** si VESC2 (CAN ID 2) silencieux N reads consécutifs, Slave set `_can_lost=True` → `drive()` refuse + envoie synthetic `TR:fault=99` (CAN_LOST) → safety gate Master trip immédiatement (pas d'attente staleness 2s).
**Joystick :** throttle 60 req/s · **WASD** = propulsion · **Arrow keys** = dome rotation (séparés). Built on Pointer Events + `setPointerCapture(pointerId)` so drag-out-of-window can't strand the keep-alive at full deflection; per-joystick `_pointerId` disambiguates multi-touch (one finger per ring). `window.blur` force-releases both + clears `_keys{}`. `_postMotion()` single-in-flight slot prevents stale arcade POSTs landing after `driveStop`.

**Lock modes (3-tier) :**
- **Mode 0 — Normal** : full drive at user speed slider.
- **Mode 1 — Kids Mode** : drive enabled, capped at `kids_speed_limit` (default 0.5). Dome + sounds free.
- **Mode 2 — Child Lock** : drive blocked. Dome + sounds + lights **intentionally still free** — hand the tablet to a young child so they can play with sounds/dome/lights without risking the 30kg+ chassis. The right joystick has no lock check by design (audit F-8 reclassed as non-bug 2026-05-14).
- Kids cap applied server-side in `motion_bp._kids_cap()` so web/Android/BT paths all enforce it (was BT-only before audit).

**Drive safety chain (every motion endpoint):**
`/motion/drive`, `/motion/arcade`, `/motion/dome/turn` pass through `_drive_gate()`/`_dome_gate()` in `motion_bp.py` which checks (in order): `reg.estop_active` → 403 · `reg.stow_in_progress` → 503 · `safe_stop.is_drive_ramp_active()` / `is_dome_ramp_active()` → 503 · `reg.lock_mode == 2` → 403 · `vesc_safety.is_drive_safe()` (drive only) → 503 · then `_kids_cap()` → watchdog feed → driver. Input parsed via `_safe_float()` (rejects NaN/Inf/non-numeric → 0.0).

**Safety ramp (anti-tip) :** `safe_stop.stop_drive()/stop_dome()` set `_drive_ramp_active`/`_dome_ramp_active` events BEFORE the ramp thread starts. `cancel_ramp()` is a no-op while either is set. New /motion/drive POSTs and BT `_do_drive` calls are refused during the ramp (≤400ms) so a stale joystick command can't abort the anti-tip deceleration. The ramp itself is intentional (NOT a hard cut — hard cut would tip the 30kg robot forward).
**Caméra :** MJPEG proxy last-connect-wins · `astromech-camera.service` Restart=always + watchdog `/dev/videoN` dans `scripts/camera-start.sh`. (`bd memories camera` pour détails)
**Service worker cache :** `astromech-<commit>` injecté dynamiquement par Flask `/static/sw.js` → cache invalidé à chaque deploy.
**Heartbeat UI :** désactivé quand tab hidden (visibilitychange) — AppWatchdog cut motion proprement, plus d'incertitude liée au throttling browser.

**Backlog :** `bd list --status=open`

---

## 🔬 UART RTT Calibration

**Endpoint :** `GET /diagnostics/uart_rtt` — stats sur fenêtre glissante 200 samples (~40s)
```json
{
  "count": 162, "min_ms": 10, "avg_ms": 48, "max_ms": 110,
  "p50_ms": 45, "p95_ms": 108, "p99_ms": 109,
  "current_body_uart_lat_ms": 15,
  "recommended_body_uart_lat_ms": 25,
  "window_s": 40
}
```

**Algo recommandation :** `p50_ms / 2` (one-way hop), arrondi à 5ms près, clampé `[5..50]ms`.
**Pourquoi p50 et pas p95 :** `pyserial.read(timeout=0.1s)` domine les samples high-percentile → p95 sur-estime. p50 reflète la latence physique steady-state.

**UI :** Settings → System → Hardware → bouton **MEASURE** + indicateur de fit (vert/orange/rouge selon écart current vs recommended) + bouton **APPLY RECOMMENDATION** (copie dans le slider · l'utilisateur clique SAVE pour persister).

**Conditions de mesure :** robot idle (pas de choreo en cours, sinon SRV traffic pollue les samples heartbeat).

**Hot-swap :** `body_servo_uart_lat` et `audio_startup_lat` sont **hot-swappables** — `ChoreoPlayer.set_body_uart_lat()` / `set_audio_startup_lat()` appelés depuis `settings_bp.set_config()`. La nouvelle valeur prend effet à `play()` suivant (ou prochaine itération de loop). Pas de reboot Master requis.

⚠️ **Master HAT addresses** (servos dôme) : reste reboot-required car `DOME_SERVOS` est calculé une fois à l'import du module.

---

## 💡 ChoreoPlayer — Gotchas

**File :** `master/choreo_player.py` — TICK=50ms (upper bound; scheduler is event-driven)
**Scheduler :** `wait(min(TICK, next_event_dt))` — events fire <1ms après leur timestamp authored, pas demi-tick de jitter.
**Audio multichannel :** jusqu'à 12 tracks simultanés. Si slots pleins → preempt le plus ancien.
**Audio offset :** `choreo.audio_startup_lat` (default 50ms) — events audio shiftés EN AVANT pour compenser cold-start mpg123.
**Drive blocks :** `vesc.drive(left,right)` discret aux timestamps. Pas de software ramping — VESC firmware gère accélération. `0,0` = stop explicite. **Gate de sécurité** : `_dispatch` propulsion vérifie `is_drive_safe()` avant d'envoyer — abort sequence avec `block_reason()` si VESC unsafe.
**Servo interp :** dome (I2C) = easing+slew. Body (UART) avancé de `body_servo_uart_lat` (default 25ms, **hot-swappable** via Settings).
**Abort :** `cells×3.5V` min · 80°C · 30A · 3 UART fails · `is_drive_safe()` → `GET /choreo/status` retourne `abort_reason`.
**Loop :** `play(chor, loop=True)` → reset complet via `_reset_loop_state()` : audio_timers cancelled + slots cleared + `_drive_fail_count` reset + `_servo_pos` cleared + `_arm_panel_map` re-read + events queue rebuilt. Spin guard `wait(max(TICK, 0.01))` avant ré-entrée pour éviter 100% CPU sur séquence vide.
**Stop semantics :** `stop()` cancel TOUS les arm Timers trackés (`_arm_timers` list + `_arm_timers_lock`). Slew threads check `_stop_flag.wait(step_dur)` au lieu de `time.sleep` → exit dans le step suivant au lieu de continuer jusqu'à la fin.
**Lock /choreo/play :** module-level `_play_lock` autour de la séquence stop→reset→play empêche deux requêtes simultanées de démarrer deux `_run` loops sur les mêmes drivers.

**Arm blocks (track `arm_servos`) :**
Format JSON : `{"arm": 1, "action": "open", "duration": 1, "group": "arms"}` — slot number, PAS servo ID.
⚠️ `_initPalette()` lit le template depuis `btn.dataset.tpl` dans le HTML (pas la constante JS `_PALETTE`).
Si `data-tpl` contient `"servo":""` (ancien format) → avertissement "Legacy event" à chaque drop.
Séquence correcte assurée par ChoreoPlayer : panel open → Timer(delay) → arm open (thread daemon).

**Commandes bulk (`all_body` / `all_dome`) :**
`all_body` : ouvre/ferme tous les body panels sauf bras → lance les séquences bras en threads.
`all_dome` : appelle `dome_servo.open_all()` / `close_all()` directement.
Dans le Choreo timeline : Dome Servo track → seulement `ALL DOME` · Body Servo track → seulement `ALL BODY`.

**Bulk + duration (depuis 2026-05-09) :**
- `dur_s > 0` sur un block `all_dome` ou `all_body` → tous les servos (sauf arms en `all_body`) slewent en parallèle sur `dur_s` secondes vers leur angle calibré, easing appliqué.
- `dur_s == 0` → fast path historique (`open_all()` / per-servo `open(speed=...)` à vitesse calibrée).
- ⚠️ **`all_body` + duration NE propage PAS la durée aux arms** (panels d'arms et arm extensions). Les arms restent à vitesse calibrée + `delay_N` du Settings → Arms. Limitation **intentionnelle** : `_launch_arm_sequences` est partagée avec les boutons UI manuels et le safe-home Reset E-STOP qui veulent vraiment la vitesse calibrée. Pour un bulk open lent INCLUANT les arms, drop des blocks `arm_servos` séparés (avec PANEL DURATION / DELAY / ARM DURATION explicites).

**Per-arm block (`arm_servos` track) — 3 champs indépendants :**
- `panel_duration` (s) — temps que le panneau prend
- `delay` (s) — gap entre panneau et bras (override le `delay_N` global de Settings)
- `arm_duration` (s) — temps que le bras prend
- Largeur visuelle du block sur la timeline = `panel_duration + delay + arm_duration` (auto via `_armBlockTotalDur`)
- Backend `_dispatch` : open = panel slew → wait (panel_duration + delay) → arm slew · close = arm slew → wait (arm_duration + delay) → panel slew
- Migration auto des vieux blocks `duration:N` → `panel_duration=N, arm_duration=N, delay=0.5` (via `scripts/migrate_arm_blocks.py`, idempotent, déjà passé en prod le 2026-05-09).

**Labels servos dans Choreo :** ARM SLOT dropdown + block label utilisent le label de Calibration
(lu depuis `_servoSettings` via `GET /servo/settings`). `armsConfig` rechargé à chaque `choreoEditor.init()`.

---

## 🖥️ Topbar & Cockpit Status Panel — Gotchas

**Topbar (clean):** brand · `pill-offline` (hidden, Master unreachable) · `pill-slave` (hidden, Slave offline/UART down) · `cockpit-btn` STATUS · battery arc · temp + clock. No uptime, no HB/UART/BT/Version pills.

**pill-slave logic:** visible when `!uart_ready || uart_health == null`. Hidden when offline (pill-offline takes over).

**Cockpit pills row (`#cockpit-panel .cockpit-pills-row`):**
- `ck-pill-hb` — green `heartbeat_ok`, red `!heartbeat_ok`
- `ck-pill-uart` — green ≥95% · orange 70–94% · red <70% or DOWN. Updated every poll via `_setCockpitUartPill()` in `StatusPoller`
- `ck-pill-bt` — green connected · orange RSSI ≤ -75 dBm · dim disconnected. Updated via `btController._updatePill()` (targets `ck-pill-bt` / `ck-pill-bt-label`)

**STATUS button color:** updated every poll via `cockpitPanel.updateBtn(data)` — does NOT wait for panel to be open. Bench mode = orange (intentional warning, user chose it).

**E-STOP overlay (`#estop-overlay`):** `position:fixed; inset:0; pointer-events:none; z-index:9999`. Class `active` triggers red pulsing border animation. Set in `_setEstopUI(tripped)`. Synced from `data.estop_active` on every poll → survives page reload.

**SERVICES panel HAT health:**
- Dome Servo HATs: `DomeServoDriver.hat_health()` — `[{addr, ok, errors}]` — Master-side, always available
- Body Servo HATs + Motor HAT + Screen: via `slave/uart_health_server.py` port 5001 → `reg.slave_uart_health`
  - `body_hat_health`: from `BodyServoDriver.hat_health()` (Slave)
  - `motor_hat_health`: I2C probe of `slave_motor_hat` addr at each `/uart_health` request — `{addr, ok}`
  - `display_ready` + `display_port`: from `DisplayDriver.is_ready()` / `.used_port`
- Row labels use `data.master_location` / `data.slave_location` (from `local.cfg [robot]`) — not hardcoded
- Fallback to generic row if HAT arrays empty (driver not ready or Slave unreachable)

**JS syntax rule:** `StatusPoller` is a `class` — methods use NO trailing comma. `cockpitPanel` is an object literal — methods use trailing comma. Mixing them causes silent syntax error that breaks the entire page. Always run `node --check master/static/js/app.js` before committing.

---

## 🎨 Theme System — Gotchas

**Files :** `master/static/css/style.css` · `master/static/js/app.js` · `master/templates/index.html`

**CSS variable architecture :**
- `:root` defines all defaults (dark R2-D2 style, Orbitron + Share Tech Mono fonts)
- Themes override by setting inline `style` on `document.documentElement`
- `--blue-rgb: R, G, B` pattern — all opacity variants derived: `rgba(var(--blue-rgb), 0.18)` → borders/glows/overlays all auto-update when accent changes
- `root.removeAttribute('style')` **before** applying new theme — clears previous overrides, prevents stale vars

**Theme objects (`_THEMES` in app.js) :**
- `default: { vars: {} }` — empty, `:root` CSS applies, nothing overridden
- All themes only need to override what differs from `:root` defaults
- `light: true` flag on light themes (affects swatch gradient rendering in picker)

**Custom themes :** stored in `localStorage` key `astromech-custom-themes` as JSON array
- Each entry: `{ id, label, swatch, vars, _pickerBg, _pickerTopbar, _pickerCard, _pickerAccent, _pickerText, _pickerOk, _pickerWarn, _pickerErr, _pickerFont }`
- `_picker*` fields = raw hex values to re-populate all 8 pickers on re-edit
- `applyTheme(id)` checks `_THEMES` first, then `_loadCustomThemes()` — handles both
- Clicking a custom theme button opens the editor (not just applies) — edit in place

**Theme customizer — 8 color pickers :**
- **INTERFACE**: BG · Topbar · Card
- **ACCENT & TEXT**: Accent · Text
- **STATUS**: OK · Warn · Error (shown live on the preview pills)
- Font picker: Courier New · Orbitron · Share Tech Mono · Audiowide · Electrolize · Exo 2 · Rajdhani

**Live preview :** right side of editor, fills available width dynamically
- Mini: 900×850px native, `_fitPreview()` calculates `scale = clipWidth/900` and sets clip height
- Called on open (setTimeout), every color change, and window resize
- Preview shows: topbar · tabs · status pills · audio · VESC telemetry · drive + E-STOP · sequences

**Font vars :**
- `--font` = UI labels, buttons, tabs (default: Orbitron)
- `--font-data` = telemetry values, code, inputs, **topbar status elements** (default: Share Tech Mono)
- Topbar status pills, temp, uptime, battery % forced to `var(--font-data)` — prevents layout shift when numbers change (monospace = fixed-width digits)
- Available font options: Orbitron · Share Tech Mono · Audiowide · Electrolize · Exo 2 · Rajdhani · Courier New (system)

**Built-in themes :** default · r2d2 · r2d2_light (Blueprint) · r5d4 · bb8 · chopper · r2q5
**Theme customizer UI :** Settings → Interface → `+ NEW THEME` (or click any custom theme to edit)

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
Repo : https://github.com/RickDnamps/AstromechOS.git   Branch : main
```

**Bouton dôme :** retiré (sécurité conventions). Deploy et Rollback accessibles via l'UI web → onglet Settings → Deploy.

---

## 📱 Build Android

```bash
powershell.exe -Command "& { \$env:JAVA_HOME='C:/Program Files/Android/Android Studio/jbr'; Set-Location 'J:/R2-D2_Build/software/android'; ./gradlew.bat assembleDebug }"
cp android/app/build/outputs/apk/debug/app-debug.apk android/compiled/AstroMech_Control.apk
"C:/Users/erict/AppData/Local/Android/Sdk/platform-tools/adb.exe" install -r android/compiled/AstroMech_Control.apk
```

> ⚠️ Sync assets si `master/static/` change :
> `cp master/static/js/app.js android/app/src/main/assets/js/app.js`
> `cp master/static/css/style.css android/app/src/main/assets/css/style.css`
>
> ⚠️ `index.html` doit utiliser des chemins **relatifs** (pas `/static/`). Le fichier `android/app/src/main/assets/index.html` est déjà patché — ne PAS écraser avec `master/templates/index.html` directement (les paths `/static/` cassent en contexte `file://`).


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
