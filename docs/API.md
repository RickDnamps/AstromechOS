# AstromechOS — REST API Reference

Base URL: `http://astromech-master:5000` (replace with your Master Pi's IP/hostname; the example droid here is R2-D2).
All POST endpoints accept and return `application/json`.

> **Auth:** mutating endpoints are admin-gated (`X-Admin-Pw` header, `hmac.compare_digest`). Safety endpoints (`/system/estop`, `/bt/estop_reset`) and `/heartbeat` are intentionally LAN-open. Operator controls (audio play/volume, motion, dome, shortcuts trigger, keyless lock escalation) are LAN-open by design. Anything marked **admin** below needs the header.
> This is a curated summary of the most-used routes — not an exhaustive dump. Every endpoint listed is real.

---

## Status

| Method | Path | Notes |
|--------|------|-------|
| GET | `/status` | Full system state — see fields below |
| GET | `/status/version` | `{master: VERSION}` (legacy) |
| GET | `/system/version` | `{version, commit, message, date}` — full git info (WOW polish I1, 2026-05-15) |
| GET | `/system/deploy_status` | admin · `{local_sha, remote_sha, remote_msg, behind_count}` — git fetch + remote compare, cached 60s (WOW polish I1) |
| POST | `/heartbeat` | App → Master watchdog (every 200ms). `AppWatchdog.TIMEOUT_S = 1.5s` → gradual stop + freeze if lost. Returns `204 No Content` (ultra-light) |

**Key `/status` fields** (single source for the StatusPoller — see `status_bp.py::get_status`):
- **Identity / system:** `robot_name` · `robot_icon` · `master_location` · `slave_location` · `version` · `uptime` · `temperature` (Master CPU °C) · `admin_pwd_is_default`
- **Links:** `heartbeat_ok` (App↔Master) · `app_hb_age_ms` · `uart_ready` (Master↔Slave) · `uart_health` (Slave stats or null) · `uart_crc_errors` · `slave_hb_age_ms` · `slave_host`
- **Drive / VESC:** `vesc_ready` · `vesc_l_ok` · `vesc_r_ok` · `vesc_drive_safe` · `vesc_bench_mode` · `power_scale` · `battery_voltage` · `battery_cells` · `battery_chemistry` · `vesc_temp` · `vesc_duty` · per-side `vesc_l_temp`/`vesc_r_temp`/`vesc_l_curr`/`vesc_r_curr`/`vesc_l_duty`/`vesc_r_duty`/`vesc_l_rpm`/`vesc_r_rpm`
- **Motion gating:** `estop_active` · `stow_in_progress` · `drive_ramp_active` · `dome_ramp_active` · `lock_mode` · `kids_speed_limit` · `child_dome_speed_limit`
- **Servos / lights:** `servo_ready` · `dome_servo_ready` · `dome_ready` · `teeces_ready` · `teeces_mode` · `lights_backend`
- **Choreo:** `choreo_playing` · `choreo_name` · `choreo_uses_propulsion` · `choreo_uses_dome` · `choreo_uses_lights` · `choreo_abort_reason`
- **Audio / behavior / shortcuts:** `audio_playing` · `audio_current` · `alive_enabled` · `next_idle_in_s` · `shortcut_states`
- **Camera:** `camera_found` · `camera_active`
- **HATs / display:** `dome_hat_health [{addr,ok,errors}]` · `body_hat_health [{addr,ok,errors}]` · `motor_hat_health {addr,ok}` · `display_ready` · `display_port`
- **Master/Slave vitals:** `master_wlan0` · `master_wlan1` · `master_mem` · `master_cpu` · `master_disk` · `slave_temp` · `slave_cpu` · `slave_mem` · `slave_disk`
- **BT** (spread from `BTControllerDriver.get_status()`): `bt_connected` · `bt_enabled` · `bt_name` · `bt_battery` · `bt_rssi` · `bt_gamepad_type` · `active_device_mac` · …

**WOW polish field additions (2026-05-15):**
- `stow_in_progress` — true during the ~3s safe-home stow after Reset E-STOP. Frontend swaps E-STOP button text to STOWING…
- `drive_ramp_active` / `dome_ramp_active` — true during anti-tip 400ms ramp. Frontend pulses joystick ring amber
- `kids_speed_limit` — float 0..1, current Kids mode speed cap. Frontend mode-kids pill shows "KIDS MODE X%"
- `choreo_abort_reason` — when a playing choreo aborts (uart_loss/undervoltage/overheat/overcurrent), this carries the reason. Global StatusPoller surfaces a toast on the `playing:true→false WITH reason` transition. `estop_active`/`stow_in_progress` are pre-flight rejects, filtered out of the toast (operator already saw the 503).

---

## Audio

| Method | Path | Body / Notes |
|--------|------|------|
| POST | `/audio/play` | `{"sound":"Happy001"}` — LAN-open |
| POST | `/audio/random` | `{"category":"happy"}` — LAN-open, 409 if category empty |
| POST | `/audio/stop` | LAN-open |
| POST | `/audio/volume` | `{"volume":79}` — LAN-open (2026-05-15 fix: was admin-gated, but volume is a basic operator control like play) |
| POST | `/audio/upload` | admin · multipart MP3 file · 12MB per-file cap · rejects <1KB · sanitizes filename · auto-resolves name collisions · SFTP-syncs to Slave + sends `SIDX:RELOAD` UART |
| DELETE | `/audio/sound/<name>` | admin · removes from sounds_index.json + local + remote (SFTP) · cascades `play_sound` shortcuts to action='none' · NOT cascaded into choreo audio tracks (intentional: re-upload same name restores) |
| GET | `/audio/index` | `{categories: {cat_name: [sound1, sound2, …]}}` — single source for both category names and per-category sound lists. Frontend prefers this (counts derived client-side) over `/audio/categories` to save a round-trip |
| GET | `/audio/categories` | `{categories:[{name, count}, …], total}` — sorted alphabetically (deterministic pill order) |
| GET | `/audio/sounds?category=happy` | `{category, sounds:[…]}` · 404 on unknown category |
| POST | `/audio/category/create` | admin · `{"name":"mycat"}` — creates an empty category (max 64) · SFTP-syncs index to Slave |
| GET | `/audio/file/<sound>` | streams the raw MP3 (used by the in-UI player preview) |
| POST | `/audio/reconcile` | admin · reconciles `sounds_index.json` with the files actually present on the Slave (drops ghosts, files unknown ones under `others`) · returns `{ok, total, removed, added_to_others}` · also runs once on boot (`audio_reconcile.py` thread) so a failed upload never leaves a phantom in the index |
| POST | `/settings/audio/profile/apply` | admin · `{"profile":"convention\|maison\|exterieur"}` — applies the cubic-curve transform `_sliderToAlsa` so saved profile matches master slider physical volume (2026-05-15 fix: was raw, profiles sounded different from slider position they were saved at) |

---

## Motion

| Method | Path | Body |
|--------|------|------|
| POST | `/motion/drive` | `{"left":0.5,"right":0.5}` — float -1.0…1.0 · runs the full safety/kids/watchdog chain |
| POST | `/motion/arcade` | `{"throttle":0.5,"steering":0.2}` — ratio-preserving normalize + same safety chain |
| POST | `/motion/stop` | — |
| GET | `/motion/state` | current propulsion state |
| POST | `/motion/dome/turn` | `{"speed":0.3}` |
| POST | `/motion/dome/stop` | — |
| POST | `/motion/dome/random` | `{"enabled":true}` |
| GET | `/motion/dome/state` | current dome state |

All drive/dome paths are LAN-open (operator control) but pass the gating chain: `estop_active` 403 → `stow_in_progress` 503 → choreo per-axis lock 503 → safety ramp 503 → `lock_mode==2` 403 → `vesc_safety.is_drive_safe()` 503 → kids cap → watchdog feed.

---

## Servos

| Method | Path | Body / Notes |
|--------|------|------|
| POST | `/servo/dome/open` | `{"name":"Servo_M0"}` — angle/speed read from config |
| POST | `/servo/dome/close` | `{"name":"Servo_M0"}` |
| POST | `/servo/dome/move` | `{"name":"Servo_M0","angle":90}` — direct angle |
| POST | `/servo/dome/open_all` · `/servo/dome/close_all` | — |
| GET | `/servo/dome/list` · `/servo/dome/state` | dome servo IDs / current state |
| POST | `/servo/body/open` | `{"name":"Servo_S0"}` |
| POST | `/servo/body/close` | `{"name":"Servo_S0"}` |
| POST | `/servo/body/move` | `{"name":"Servo_S0","angle":90}` |
| POST | `/servo/body/open_all` | arm-aware: panels → delay → arms in threads |
| POST | `/servo/body/close_all` | arm-aware: arms first → delay → panels |
| GET | `/servo/body/list` · `/servo/body/state` | body servo IDs / current state |
| GET | `/servo/list` · `/servo/state` | all servo IDs / state |
| POST | `/servo/open_all` · `/servo/close_all` | every panel (dome + body) |
| GET | `/servo/settings` | Calibration (angles, speed, labels) + `dome_hats`/`body_hats` HAT map · returns `X-Servo-Version` header (optimistic concurrency) |
| POST | `/servo/settings` | admin · `{"Servo_M0":{"label":"..","open":110,"close":20,"speed":10}, …}` · honors optional `If-Match` header → 409 on conflict |
| GET | `/servo/arms` | `{count, servos, panels, delays}` |
| POST | `/servo/arms` | admin · `{count:2, servos:[...], panels:[...], delays:[0.5,...]}` → local.cfg [arms] |
| GET | `/servo/sync_status` | slave servo-HAT config sync state |

---

## Lights (Teeces / AstroPixels+)

| Method | Path | Body |
|--------|------|------|
| POST | `/teeces/random` | — |
| POST | `/teeces/leia` | — |
| POST | `/teeces/off` | — |
| POST | `/teeces/text` | `{"text":"HELLO"}` |
| POST | `/teeces/psi` | `{"mode":1}` |
| POST | `/teeces/psi_seq` | run a PSI sequence |
| POST | `/teeces/animation` | `{"id":"…"}` — named JawaLite animation |
| GET | `/teeces/animations` | list of available animations |
| POST | `/teeces/raw` | `{"command":"…"}` — raw JawaLite/AstroPixels serial command |
| GET | `/teeces/state` | current lights mode (also surfaced as `teeces_mode` in `/status`) |

---

## System

| Method | Path | Notes |
|--------|------|-------|
| POST | `/system/update` | admin · git pull + rsync Slave + reboot Slave + restart Master (refuses if motion in flight) |
| POST | `/system/rollback` | admin · git checkout HEAD^ + rsync Slave + reboot Slave |
| POST | `/system/resync_slave` | admin · re-push VCFG/VINV to Slave over UART |
| POST | `/system/reboot` | admin · reboot Master |
| POST | `/system/reboot_slave` | admin · reboot Slave via UART |
| POST | `/system/reboot_both` | admin · reboot Slave then Master |
| POST | `/system/restart_master` | admin · restart the Flask service only (no full reboot) |
| POST | `/system/shutdown` | admin · graceful power-off Master |
| POST | `/system/shutdown_slave` | admin · graceful power-off Slave via UART |
| POST | `/system/shutdown_both` | admin · power-off Slave then Master |
| POST | `/system/estop` | **LAN-open** · E-STOP — freeze servos (PWM holds), cut propulsion + dome + abort choreo |
| POST | `/system/estop_reset` | admin · clear E-STOP + slow safe-home stow (arms retract → panels close) |

---

## VESC

| Method | Path | Body / Notes |
|--------|------|------|
| GET | `/vesc/telemetry` | `{connected, power_scale, L:{v_in,temp,current,rpm,duty,fault,fault_str}, R:…}` |
| GET | `/vesc/config` | `{power_scale, invert_L, invert_R}` |
| POST | `/vesc/config` | admin · `{"scale":0.8}` → persisted `local.cfg [vesc]` |
| POST | `/vesc/invert` | admin · `{"side":"L","state":true}` → persisted + UART `VINV:L:1` |
| POST | `/vesc/bench_mode` | admin · `{"enabled":true}` → persisted + propagated to Slave via `VCFG:bench:1` (bypasses both Master + Slave VESC safety) |
| POST | `/vesc/mode` | admin · `{"duty":true}` → duty vs rpm mode (NOT persisted, resets on reboot) |
| GET | `/vesc/can/scan` | CAN bus scan via VESC1 USB (timeout 8s) |

---

## Camera

| Method | Path | Notes |
|--------|------|-------|
| POST | `/camera/take` | Claim MJPEG stream → `{token}` · LAN-open, per-IP rate-limit (10 / 10s → 429) |
| GET | `/camera/stream?t=TOKEN` | MJPEG proxy — last-connect-wins (evicted client → STREAM TAKEN overlay) · 403 if token isn't the active one |
| GET | `/camera/status` | `{active_token}` |
| POST | `/camera/release` | release the active stream slot |
| GET | `/camera/snapshot` | single JPEG frame |
| GET | `/camera/config` | `{resolution, fps, bitrate, …}` |
| POST | `/camera/config` | admin · update camera settings (restarts the stream) |

---

## Choreographies

| Method | Path | Body / Notes |
|--------|------|------|
| GET | `/choreo/list` | `[{name, label, category, emoji, duration, audio_count, dome_count, body_count, lights_count, uses_propulsion, uses_dome}, …]` — objects, NOT strings. `uses_propulsion`/`uses_dome` drive the frontend's optimistic joystick lock on Play click. |
| POST | `/choreo/play` | `{"name":"foo","loop":true}` → `{status, name, duration}` · 503 if busy/already playing |
| POST | `/choreo/stop` | — · 503 if no player wired |
| GET | `/choreo/status` | `{playing, name, t_now, duration, abort_reason, uses_propulsion, uses_dome, uses_lights, telem}` |
| GET | `/choreo/categories` | `[{id, label, emoji, order}, …]` — also returns `X-Categories-Version` header (mtime as float) used by reorder POSTs as `If-Match` for optimistic concurrency |
| POST | `/choreo/categories` | admin · create / update / reorder / delete categories. Supports optional `If-Match` header on `reorder` action — server returns 409 'version conflict' if it doesn't match current mtime (prevents 2 admins silently overwriting each other's drag). Backwards-compat: header is optional, legacy clients without it pass through. |
| POST | `/choreo/set-category` | admin · `{"name":"foo.chor","category":"emotion"}` · 404 if category unknown |
| POST | `/choreo/set-emoji` | admin · `{"name":"foo.chor","emoji":"🎭"}` · empty = revert to auto |
| POST | `/choreo/set-label` | admin · `{"name":"foo.chor","label":"My Label"}` · empty = revert to filename |
| POST | `/choreo/rename` | admin · `{"old_name":"foo","new_name":"bar"}` — cascades to shortcuts |
| GET | `/choreo/load?name=foo` | full timeline JSON for the editor |
| POST | `/choreo/save` | admin · save a timeline (atomic write) · invalidates the list cache |
| POST | `/choreo/export_scr` | admin · export a `.chor` to legacy `.scr` format |
| DELETE | `/choreo/<name>` | admin · refuses if currently playing · cascades shortcuts → action:'none' |

---

## Shortcuts (Drive-tab macro buttons)

| Method | Path | Body / Notes |
|--------|------|------|
| GET | `/shortcuts` | `{count, max, shortcuts:[…], states:{id:'on'\|'off'}}` |
| POST | `/shortcuts` | admin · `{shortcuts:[{label, icon, color, action:{type, target}}, …]}` · server assigns `id` · validates per action type |
| POST | `/shortcuts/<id>/trigger` | LAN-open · returns `{state:'on'\|'off'\|'fired'}` · re-press kills active choreo/sound |

**Action types**: `arms_toggle` · `body_panel_toggle` · `dome_panel_toggle` · `play_choreo` · `play_sound` · `play_random_audio` · `none`. Target validation per type (range / allowlist / on-disk file / category membership). Max 12 shortcuts.

---

## BT Gamepad (evdev controller)

| Method | Path | Body / Notes |
|--------|------|------|
| GET | `/bt/status` | `{bt_connected, bt_enabled, bt_name, bt_battery, bt_rssi, bt_gamepad_type, bt_inactivity_timeout, bt_inactivity_pause, active_device_mac, device_profiles:{MAC:{name, last_seen, custom_button_mappings:[…]}}}` · LAN-open |
| POST | `/bt/enable` | admin · `{enabled:bool}` · disables motion if false |
| POST | `/bt/config` | admin · `{gamepad_type, deadzone, inactivity_timeout, mappings:{…}}` — preset button mappings + axes |
| POST | `/bt/estop_reset` | LAN-open · clears E-STOP from gamepad button (safety endpoint) |
| POST | `/bt/scan/start` | admin · starts 8s `bluetoothctl --timeout 8 scan on` |
| GET | `/bt/scan/devices` | admin · returns scan results (cached for the panel) |
| POST | `/bt/pair` | admin · `{mac}` — pair + trust + connect |
| POST | `/bt/unpair` | admin · `{mac}` — remove from bluetoothctl |

### Custom Button Actions (per-MAC profiles)

| Method | Path | Body / Notes |
|--------|------|------|
| POST | `/bt/capture/start` | admin · enters press-to-capture mode for 10s (driver fills `_capture_result` on next button press, under `_capture_lock`) |
| GET | `/bt/capture/poll` | admin · `{state:'listening'\|'captured'\|'expired'\|'cancelled', button:'BTN_A'\|null, remaining_ms}` — always HTTP 200, the `state` field is the truth · frontend polls every 200ms while editor open |
| POST | `/bt/capture/cancel` | admin · drops the capture window |
| POST | `/bt/custom_mapping` | admin · `{mac, action:'add'\|'update'\|'remove', mapping:{id, button, action:{type, target}, icon?, label?}}` — atomic save under cfg lock |
| DELETE | `/bt/custom_mapping/<id>` | admin · remove a single custom button mapping |
| DELETE | `/bt/device_profile/<mac>` | admin · forget a per-MAC controller profile |

**Action types**: `arms_toggle` · `body_panel_toggle` · `dome_panel_toggle` · `play_choreo` · `play_sound` · `play_random_audio` · `none`. Validation per type at save AND at trigger (defense-in-depth). Profile auto-created via `_ensure_device_profile(MAC, name)` on first controller connect. MAC resolution: `evdev.uniq` → `bluetoothctl devices Connected` name-match fallback (NVIDIA Shield et al don't populate uniq).

---

## Lock Mode

| Method | Path | Body / Notes |
|--------|------|------|
| POST | `/lock/set` | LAN-open · `{mode:0\|1\|2}` — **keyless ESCALATION only** (toward a stricter mode; relaxing requires `/lock/unlock`). `kids_speed_limit:0..1` is only honored with an admin token (Settings slider). Persists `local.cfg [security]` |
| POST | `/lock/unlock` | LAN-open · `{password, mode:0}` · server-side `hmac.compare_digest` vs admin password · operator-facing unlock (relaxation) from Kids/Child Lock |

Mode 0 = Normal · Mode 1 = Kids (capped via `kids_speed_limit`) · Mode 2 = Child Lock (drive forbidden, dome/sounds/lights free).

---

## Behavior Engine

| Method | Path | Notes |
|--------|------|-------|
| GET  | `/behavior/status` | `{alive_enabled, startup_enabled, startup_delay, startup_choreo, idle_mode, idle_mode_ready, idle_timeout_min, idle_audio_category, idle_choreo_list, dome_auto_on_alive, last_idle_choreo, last_activity_ago_s, next_idle_in_s, ...}` |
| POST | `/behavior/config` | admin · full behavior config save to `local.cfg [behavior]` |
| POST | `/behavior/alive` | admin · `{enabled:true\|false}` — toggle alive mode |
| POST | `/behavior/test_trigger` | admin · fire an idle reaction now (test) |
| POST | `/behavior/test_startup` | admin · fire the startup behavior now (test) |

**WOW polish H4 (2026-05-15):** `next_idle_in_s` computed as `last_activity + idle_timeout_min - now`. `null` when `alive_enabled=false`. Frontend renders a live ticking countdown pill "Next idle reaction in 9:58".

---

## Diagnostics

| Method | Path | Notes |
|--------|------|-------|
| GET | `/diagnostics/logs?filter=ALL\|WARNING\|ERROR` | admin · last 50 `astromech-master` journal lines (secrets redacted, payload-capped) → `{lines, filter}` |
| GET | `/diagnostics/stats` | admin · `{master:{uart_ready, crc_errors, hb_age_ms}, slave:{reachable, health_pct, total, errors, …}}` |
| GET | `/diagnostics/uart_rtt` | admin · rolling 200-sample RTT stats (~40s window) + recommended `body_servo_uart_lat` |
| POST | `/diagnostics/ping_slave` | admin · HTTP round-trip to Slave health server (port 5001) → `{ok, ms}` |
| GET | `/diagnostics/i2c_scan` | admin · probe the I2C bus for HAT addresses |

Frontend `diagPanel` auto-refreshes stats every 5s while panel visible. TAIL mode auto-refreshes logs every 2s + scroll-locks to bottom (WOW polish I8).

---

## Settings & Network

| Method | Path | Body / Notes |
|--------|------|------|
| GET | `/settings` | admin · current config snapshot (network, deploy, robot identity, lights backend, latencies, …) |
| POST | `/settings/config` | admin · diff-based config save → `local.cfg` (skip-if-unchanged; some keys live, some reboot-required) |
| GET | `/settings/wifi/scan` | admin · `nmcli` scan of nearby networks (SVG signal-bar data) |
| POST | `/settings/wifi` | admin · `{ssid, psk}` — join a home WiFi (live wlan1 SSID re-read after) |
| POST | `/settings/hotspot` | admin · `{ssid, psk}` — change the Master AP. **Slave-first**: pushes creds to the Slave's `r2d2-master-hotspot` profile by SSH before switching (503 abort if Slave unreachable → no orphan) |
| POST | `/settings/audio/profile/apply` | admin · `{"profile":"convention\|maison\|exterieur"}` — applies the cubic-curve volume transform |
| GET | `/settings/slave_hat_sync_status` | admin · last Slave servo-HAT config push result |
| POST | `/settings/admin/verify` | **LAN-open** · `{password}` → `{ok}` · `hmac.compare_digest` · per-IP rate-limit 10/60s → 5-min lockout (429) |
| POST | `/settings/admin/password` | admin · `{current, new}` — change admin password (rate-limited, rejects new==current) |
| GET | `/settings/icons` | admin · list of available header icons |
| POST | `/settings/icons/upload` | admin · multipart icon upload (no `.svg` — XSS guard) |
| POST | `/settings/icons/delete` | admin · `{name}` — remove an uploaded icon |
| POST | `/settings/robot_icon` | admin · `{"icon":"img:foo.png"}` or emoji or `""` to reset (validated, ≤128 chars) |
| POST | `/settings/robot_name` | admin · `{"name":"R2-D2"}` — char allowlist (no `:` `<` `>` `/`), ≤32 chars |
| POST | `/settings/robot_locations` | admin · `{master_location, slave_location}` — display labels (e.g. "Dome"/"Body") |
| POST | `/settings/lights` | admin · `{"backend":"teeces\|astropixels"}` — hot-swap lights driver (no reboot) |

> All hostnames/IPs come from `local.cfg` (e.g. `[slave] host`) via `_resolve_slave_ssh_target()` — never hardcoded. `nmcli` mutations run via `sudo -n nmcli` (Flask runs as a non-root user).

---

## Slave Health (port 5001)

Served by `slave/uart_health_server.py` (a stdlib `BaseHTTPRequestHandler`, not Flask) — queried by Master every poll cycle. These `/audio/bt/*` routes manage the **BT audio speaker** on the Slave, distinct from the BT **gamepad** under `/bt/*` on the Master.

| Method | Path | Notes |
|--------|------|-------|
| GET | `/uart_health` | UART stats + HAT health + display status |
| GET | `/audio/bt/status` | BT speaker devices + connection state |
| POST | `/audio/bt/scan` | Start 8s BT scan |
| POST | `/audio/bt/pair` | `{"mac":"AA:BB:CC:DD:EE:FF"}` |
| POST | `/audio/bt/connect` | `{"mac":"..."}` — connect + set PulseAudio default sink |
| POST | `/audio/bt/disconnect` | `{"mac":"..."}` |
| POST | `/audio/bt/remove` | `{"mac":"..."}` |
| POST | `/audio/bt/volume` | `{"volume":…}` — BT speaker volume |

> Note: the Master also exposes a thin proxy of these under `/audio/bt/*` (in `audio_bp.py`) that forwards to the Slave's port 5001 — the dashboard talks to the Master, which relays to the Slave.

---

## Custom Themes

Server-side persistence so a custom theme survives reboots / device changes and is included in backups. Stored in `master/config/custom_themes.json` (gitignored, atomic write). `localStorage` mirrors them as a cache.

| Method | Path | Body / Notes |
|--------|------|------|
| GET | `/themes/custom` | LAN-open · `{themes: [ {id, label, swatch, _picker*, _pickerFont, vars}, … ]}` |
| POST | `/themes/custom` | admin · `{theme: {…}}` — validated by `validate_theme` (id regex, hex pickers, CSS-injection guard on `vars`: allows `rgba()`, blocks `;{}<>`/`url(`/`expression`/`javascript:`) · upsert by `id` |
| DELETE | `/themes/custom/<id>` | admin · `id` validated `[A-Za-z0-9_-]{1,40}` |

---

## Backup / Restore

Full robot-state backup → a `.bck` (a ZIP, renamed, `chmod 0600` — it contains WiFi + admin secrets). Restore = **total replacement + automatic reboot**. Network sections are preserved from the live machine so master↔slave never lose each other.

| Method | Path | Body / Notes |
|--------|------|------|
| POST | `/backup/start` | admin · starts the async backup job (collects master files locally + slave via SFTP, builds manifest, zips) |
| GET | `/backup/status` | admin · `{running, pct, phase, done, error, path?}` — drives the real progress bar |
| GET | `/backup/download` | admin · streams the `.bck` (then deletes the server-side temp) · `Content-Disposition` filename `AstromechOS_Backup_<date>.bck` |
| POST | `/restore/upload` | admin · raw `.bck` as the request body (read straight from `wsgi.input` to bypass the 16 MB `MAX_CONTENT_LENGTH`; 200 MB cap) · returns `{ok, token, bytes}` |
| POST | `/restore/apply` | admin · `{token}` — validates the token, then runs the restore job: **validate-everything-before-any-write** (manifest + anti zip-slip + allow-list anti-RCE + 2 GB zip-bomb cap), master files first then slave SFTP, `local.cfg` merged (network preserved), then reboots slave (UART) + master |
| GET | `/restore/status` | admin · `{running, pct, phase, done, error}` |

> **Security:** the restore allow-list (`is_allowed_restore_member`) rejects any archive member outside `BACKUP_FILESET` — a crafted `.bck` cannot overwrite code (which, with the post-restore reboot, would be RCE). Verified live: a `.bck` containing `master/main.py` + `../../tmp/evil` is rejected during validation with nothing written.
