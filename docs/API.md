# AstromechOS — REST API Reference

Base URL: `http://192.168.2.104:5000`  
All POST endpoints accept and return `application/json`.

---

## Status

| Method | Path | Notes |
|--------|------|-------|
| GET | `/status` | Full system state — see fields below |
| GET | `/status/version` | `{master: VERSION}` (legacy) |
| GET | `/system/version` | `{version, commit, message, date}` — full git info (WOW polish I1, 2026-05-15) |
| GET | `/system/deploy_status` | admin · `{local_sha, remote_sha, remote_msg, behind_count}` — git fetch + remote compare, cached 60s (WOW polish I1) |
| POST | `/heartbeat` | App ↔ Master watchdog (every 200ms, 600ms timeout) |

**Key `/status` fields:** `robot_name` · `master_location` · `slave_location` · `version` · `uptime` · `temperature` · `heartbeat_ok` · `uart_ready` · `uart_health` (Slave stats or null) · `battery_voltage` · `vesc_ready` · `vesc_l_ok` · `vesc_r_ok` · `vesc_bench_mode` · `dome_servo_ready` · `servo_ready` · `choreo_playing` · `audio_playing` · `estop_active` · `stow_in_progress` · `drive_ramp_active` · `dome_ramp_active` · `lock_mode` · `kids_speed_limit` · `camera_found` · `camera_active` · `dome_hat_health [{addr,ok,errors}]` · `body_hat_health [{addr,ok,errors}]` · `motor_hat_health {addr,ok}` · `display_ready` · `display_port` · `bt_connected` · `bt_rssi` · `slave_temp` · `slave_cpu` · `master_wlan0` · `master_wlan1`

**WOW polish field additions (2026-05-15):**
- `stow_in_progress` — true during the ~3s safe-home stow after Reset E-STOP. Frontend swaps E-STOP button text to STOWING…
- `drive_ramp_active` / `dome_ramp_active` — true during anti-tip 400ms ramp. Frontend pulses joystick ring amber
- `kids_speed_limit` — float 0..1, current Kids mode speed cap. Frontend mode-kids pill shows "KIDS MODE X%"

---

## Audio

| Method | Path | Body |
|--------|------|------|
| POST | `/audio/play` | `{"sound":"Happy001"}` |
| POST | `/audio/random` | `{"category":"happy"}` |
| POST | `/audio/stop` | — |
| POST | `/audio/volume` | `{"volume":79}` |

---

## Motion

| Method | Path | Body |
|--------|------|------|
| POST | `/motion/drive` | `{"left":0.5,"right":0.5}` — float -1.0…1.0 |
| POST | `/motion/stop` | — |
| POST | `/motion/dome/turn` | `{"speed":0.3}` |
| POST | `/motion/dome/stop` | — |
| POST | `/motion/dome/random` | `{"enabled":true}` |

---

## Servos

| Method | Path | Body / Notes |
|--------|------|------|
| POST | `/servo/dome/open` | `{"name":"Servo_M0"}` |
| POST | `/servo/dome/close` | `{"name":"Servo_M0"}` |
| POST | `/servo/dome/open_all` | — |
| POST | `/servo/dome/close_all` | — |
| POST | `/servo/body/open` | `{"name":"Servo_S0"}` |
| POST | `/servo/body/close` | `{"name":"Servo_S0"}` |
| POST | `/servo/body/open_all` | arm-aware: panels → delay → arms in threads |
| POST | `/servo/body/close_all` | arm-aware: arms first → delay → panels |
| GET | `/servo/list` | All servo IDs |
| GET | `/servo/settings` | Calibration data (angles, speed, labels) |
| POST | `/servo/settings` | `{"panels":{"Servo_M0":{"label":"..","open":110,"close":20,"speed":10}}}` |
| GET | `/servo/arms` | `{count, servos, panels, delays}` |
| POST | `/servo/arms` | `{count:2, servos:[...], panels:[...], delays:[0.5,...]}` → local.cfg [arms] |

---

## Lights (Teeces / AstroPixels+)

| Method | Path | Body |
|--------|------|------|
| POST | `/teeces/random` | — |
| POST | `/teeces/leia` | — |
| POST | `/teeces/off` | — |
| POST | `/teeces/text` | `{"text":"HELLO"}` |
| POST | `/teeces/psi` | `{"mode":1}` |

---

## System

| Method | Path | Notes |
|--------|------|-------|
| POST | `/system/update` | git pull + rsync Slave + reboot Slave |
| POST | `/system/rollback` | git checkout HEAD^ + rsync Slave + reboot Slave |
| POST | `/system/reboot` | Reboot Master |
| POST | `/system/reboot_slave` | Reboot Slave via UART |
| POST | `/system/estop` | E-STOP — cut PWM, `_ready=False` Master+Slave |
| POST | `/system/estop_reset` | Clear E-STOP + safe-home (arms retract → panels close) |

---

## VESC

| Method | Path | Body / Notes |
|--------|------|------|
| GET | `/vesc/telemetry` | `{connected, power_scale, L:{v_in,temp,current,rpm,duty,fault,fault_str}, R:…}` |
| GET | `/vesc/config` | `{power_scale, invert_L, invert_R}` |
| POST | `/vesc/config` | `{"scale":0.8}` → persisted `local.cfg [vesc]` |
| POST | `/vesc/invert` | `{"side":"L","state":true}` → persisted |
| GET | `/vesc/can/scan` | CAN bus scan via VESC1 USB (timeout 8s) |

---

## Camera

| Method | Path | Notes |
|--------|------|-------|
| POST | `/camera/take` | Claim MJPEG stream → `{token}` |
| GET | `/camera/stream?t=TOKEN` | Proxy — last-connect-wins (evicted client → STREAM TAKEN overlay) |
| GET | `/camera/status` | `{active_token}` |

---

## Choreographies

| Method | Path | Body / Notes |
|--------|------|------|
| GET | `/choreo/list` | `[{name, label, category, emoji, duration}, …]` — objects, NOT strings |
| POST | `/choreo/play` | `{"name":"foo","loop":true}` |
| POST | `/choreo/stop` | — |
| GET | `/choreo/status` | `{running, name, progress, loop, abort_reason}` |
| GET | `/choreo/categories` | `[{id, label, emoji, order}, …]` |
| POST | `/choreo/categories` | Create / update / reorder / delete categories |
| POST | `/choreo/category` | `{"name":"foo.chor","category":"emotion"}` |
| POST | `/choreo/emoji` | `{"name":"foo.chor","emoji":"🎭"}` |
| POST | `/choreo/label` | `{"name":"foo.chor","label":"My Label"}` |
| POST | `/choreo/rename` | `{"old_name":"foo","new_name":"bar"}` — cascades to shortcuts |
| DELETE | `/choreo/<name>` | refuses if currently playing · cascades shortcuts → action:'none' |

---

## Shortcuts (Drive-tab macro buttons)

| Method | Path | Body / Notes |
|--------|------|------|
| GET | `/shortcuts` | `{count, max, shortcuts:[…], states:{id:'on'\|'off'}}` |
| POST | `/shortcuts` | admin · `{shortcuts:[{label, icon, color, action:{type, target}}, …]}` · server assigns `id` · validates per action type |
| POST | `/shortcuts/<id>/trigger` | LAN-open · returns `{state:'on'\|'off'\|'fired'}` · re-press kills active choreo/sound |

**Action types**: `arms_toggle` · `body_panel_toggle` · `dome_panel_toggle` · `play_choreo` · `play_sound` · `play_random_audio` · `none`. Target validation per type (range / allowlist / on-disk file / category membership). Max 12 shortcuts.

---

## Lock Mode

| Method | Path | Body / Notes |
|--------|------|------|
| POST | `/lock/set` | admin · `{mode:0\|1\|2, kids_speed_limit:0..1}` · persists `local.cfg [security]` |
| POST | `/lock/unlock` | LAN-open · `{password, mode:0}` · server-side `hmac.compare_digest` vs admin password · operator-facing unlock from Kids/Child Lock |

Mode 0 = Normal · Mode 1 = Kids (capped via `kids_speed_limit`) · Mode 2 = Child Lock (drive forbidden, dome/sounds/lights free).

---

## Behavior Engine

| Method | Path | Notes |
|--------|------|-------|
| GET  | `/behavior/status` | `{alive_enabled, startup_enabled, idle_mode, idle_timeout_min, last_activity_ago_s, next_idle_in_s, ...}` |
| POST | `/behavior/config` | admin · full behavior config save to `local.cfg [behavior]` |
| POST | `/behavior/alive` | admin · `{enabled:true\|false}` — toggle alive mode |

**WOW polish H4 (2026-05-15):** `next_idle_in_s` computed as `last_activity + idle_timeout_min - now`. `null` when `alive_enabled=false`. Frontend renders a live ticking countdown pill "Next idle reaction in 9:58".

---

## Diagnostics

| Method | Path | Notes |
|--------|------|-------|
| GET | `/diagnostics/logs?filter=ALL\|WARNING\|ERROR` | admin · master log tail |
| GET | `/diagnostics/uart_stats` | UART CRC/health/heartbeat metrics |
| GET | `/diagnostics/uart_rtt` | rolling 200-sample RTT stats (~40s window) |
| GET | `/diagnostics/ping_slave` | admin · TCP ping → port 5001 |

Frontend `diagPanel` auto-refreshes stats every 5s while panel visible. TAIL mode auto-refreshes logs every 2s + scroll-locks to bottom (WOW polish I8).

---

## Slave Health (port 5001)

Served by `slave/uart_health_server.py` — queried by Master every poll cycle.

| Method | Path | Notes |
|--------|------|-------|
| GET | `/uart_health` | UART stats + HAT health + display status |
| GET | `/audio/bt/status` | BT devices + connection state |
| POST | `/audio/bt/scan` | Start 8s BT scan |
| POST | `/audio/bt/pair` | `{"mac":"AA:BB:CC:DD:EE:FF"}` |
| POST | `/audio/bt/connect` | `{"mac":"..."}` — connect + set PA default sink |
| POST | `/audio/bt/disconnect` | `{"mac":"..."}` |
| POST | `/audio/bt/remove` | `{"mac":"..."}` |
