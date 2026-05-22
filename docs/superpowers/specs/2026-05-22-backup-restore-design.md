# Backup / Restore + Server-Side Custom Themes — Design (Chantier B)

> **Date:** 2026-05-22
> **Status:** Approved (design), pending implementation plan
> **Beads:** software-uhl (Backup & Restore — full config + choreo export/import)
> **Builds on:** Chantier A (seed + working dirs) — the gitignored "working" set IS the backup scope.

## Problem / Goal

A full operator workflow for disaster recovery: **"SD card dies → reinstall AstromechOS → Restore a `.bck` → the droid is back exactly as it was."** Today there is no way to back up the robot's runtime state off-device. Custom themes can't even be backed up (they live only in the browser's localStorage).

Deliver a Backup/Restore tool in **Settings → System** with a real progress bar, producing a downloadable `AstromechOS_Backup_YYYYMMDD_HHMMSS.bck` (a standard ZIP renamed to `.bck`), and a Restore that replaces all state and reboots.

## Decisions (confirmed with operator)

| Decision | Choice |
|---|---|
| Progress | **Real % bar** — async job + status polling |
| Restore | **Total replacement + automatic reboot** (no selective restore) |
| Network config on restore | **PRESERVED** — live network/infra sections of `local.cfg` are kept (never severs master↔slave WiFi); only content sections are restored |
| Format | **Standard ZIP**, renamed to `.bck` (`AstromechOS_Backup_<date>.bck`) |
| Custom themes | **Persist server-side** (precursor) so they're multi-device + backup-able |
| Backup scope | All robot runtime state; NOT code / seed / `*.example` / VERSION |

## Backup scope — what goes in the `.bck`

**Master** (`master/`):
- `config/local.cfg` · `config/choreo_categories.json` · `config/shortcuts.json` ·
  `config/bt_config.json` · `config/dome_angles.json` · `config/camera.env` ·
  `config/custom_themes.json` (new, from B.0)
- `choreographies/` (working) · `light_sequences/` · `sequences/`

**Slave** (`slave/`, pulled via SFTP):
- `config/slave.cfg` · `config/servo_angles.json`
- `sounds/` (working, ~69 MB — all `.mp3` + `sounds_index.json`)

**Excluded** (reconstructed from git/install): all code, `*_default/` seeds, `main.cfg`,
`servo_list.cfg`, `*.example`, `VERSION`, `__pycache__`, `vendor/`, `*.bak[0-9]`.

`.bck` layout: `manifest.json` at root + `master/…` + `slave/…` mirroring the paths above.
`manifest.json`: `{format_version:1, created:<iso>, astromech_version:<commit>, robot_name, files:[…]}`.

---

## B.0 — Server-side custom themes (precursor)

**Files:** new `master/api/themes_bp.py` (or extend an existing bp) + `master/config/custom_themes.json` (gitignored — add to `.gitignore`); `master/static/js/app.js` (theme store).

- **Storage**: `custom_themes.json` = `{themes:[{id,label,colors,font},…]}`. Atomic write
  (`write_cfg_atomic` pattern), chmod 0600 not needed (not secret), under a `_themes_lock`.
- **API**:
  - `GET /themes/custom` → list (LAN-open read, like other read endpoints).
  - `POST /themes/custom` (`@require_admin`) → add/update one theme. Validate: `id`/`label`
    length-capped + char-allowlisted; `colors` must be hex strings; `font` from the known
    font allowlist. Cap at `_CUSTOM_THEMES_MAX = 16` (same as today).
  - `DELETE /themes/custom/<id>` (`@require_admin`).
- **Frontend** (`saveCustomTheme`/`_saveCustomThemesStore`/`_loadCustomThemes`): save to the
  server via `api()`; keep localStorage as an **offline cache** (write-through). On first load,
  if the server list is empty but localStorage has themes, **migrate** them up (one-shot POST),
  then treat the server as source of truth. Render via `createElement`/`textContent` (XSS — theme
  labels are user input).
- Now themes are multi-device and included in the backup.

---

## B.1 — Backup (async job + real % bar)

**Files:** new `master/api/backup_bp.py`; frontend Settings→System panel + handler.

- **Single-job model**: a module-level `_backup_job = {id, pct, phase, done, error, path}` under
  `_backup_lock`. Reject a new backup if one is running (`409`).
- `POST /backup/start` (`@require_admin`) → spawn a daemon thread, return `{job_id}`.
- **Job phases** (update `pct`/`phase` as it goes):
  1. *Collecting master* — copy the master file set into a temp staging dir.
  2. *Collecting slave (X/N)* — SFTP-get `slave/config/*` + every `slave/sounds/*` file;
     `pct` tracks files fetched (the long phase, ~69 MB).
  3. *Compressing* — `zipfile` the staging dir → `/tmp/astromech_backup_<ts>.bck`.
  4. *Ready* — set `done=true`, `path=<bck>`.
- `GET /backup/status` (`@require_admin`) → `{pct, phase, done, error}`. Frontend polls ~1 s,
  animates the bar.
- `GET /backup/download` (`@require_admin`) → `send_file` the `.bck` with
  `Content-Disposition: attachment; filename=AstromechOS_Backup_<ts>.bck`, then delete the temp
  (and clear the job) in a `@after_this_request` / finally.
- **Frontend**: "Create backup" button → POST start → poll → bar → on `done`, trigger the browser
  download of `/backup/download` → success toast. Errors surface in the bar + toast.

---

## B.2 — Restore (total replacement + reboot)

**Files:** `master/api/backup_bp.py` (restore endpoints); frontend confirm modal + progress.

- **Large upload** (the `.bck` is ~70 MB > the global `MAX_CONTENT_LENGTH = 16 MB`): the restore
  upload endpoint must NOT use Werkzeug form parsing (which enforces the global cap). Instead
  **stream `request.stream` in chunks** to a temp file with its own size cap (e.g. 200 MB),
  bypassing the 16 MB form limit without raising it globally.
- `POST /restore/upload` (`@require_admin`) → stream to `/tmp/restore_<ts>.bck`, return `{token}`.
- **Confirmation**: frontend modal — "This OVERWRITES all current sounds, choreos, configs and
  calibration, then reboots. Continue?" (typed/explicit confirm). The current state should ideally
  be auto-backed-up first (offer "download a safety backup before restoring").
- `POST /restore/apply` (`@require_admin`, body `{token}`) → spawn a job that:
  1. **Validate** the ZIP: parse `manifest.json` (format_version supported?); warn (don't block)
     if `astromech_version` differs.
  2. **Anti zip-slip** (CRITICAL): for every member, compute the real target path and assert it
     stays within the allowed root (`master/` or `slave/` under `$REPO`); reject the whole archive
     on any escape (`..`, absolute, symlink). Never extract before this passes.
  3. Extract to a temp dir, then **distribute** (order matters to avoid losing the slave):
     - **Slave files first, while the network is still up**: SFTP the slave's `sounds/` + `config/`
       into `$REPO/slave/…`, then send the slave a `REBOOT` over **UART** (UART is network-independent
       and always works). The slave reboots and rejoins the *unchanged* AP.
     - **Master files**: atomic writes into `$REPO/master/…`. **`local.cfg` is MERGED, not replaced**
       (see network preservation below).
     - Track `pct`.
  4. **Reboot the master** (`systemctl reboot`). Frontend shows the existing reboot-countdown overlay
     → reconnect → reload. Master comes up on the *same* AP → slave (already rebooted, same AP) is there.

  **Network preservation (the master↔slave-safety invariant).** `master/config/local.cfg` holds BOTH
  content and network/infra. On restore, `local.cfg` is rebuilt as: **backup's content sections +
  the LIVE machine's network/infra sections** (never the backup's). Preserved-from-live sections:
  `_NETWORK_PRESERVE_SECTIONS = {home_wifi, hotspot, deploy, slave, github}` — i.e. the AP the slave
  joins, the home-WiFi creds, the SSH/deploy creds, the slave host, and the repo URL. Everything else
  (`admin`, `robot`, `arms`, `i2c_servo_hats`, `behavior`, `vesc`, `security`, `audio`, …) is restored
  from the backup. The slave's OWN network config lives at OS level (NetworkManager) and is **not in
  the backup**, so it is never touched. Net effect: neither side's network identity changes → WiFi
  (and the UART control link, always) stay up across the restore. nmcli is **not** re-applied by the
  restore (NetworkManager already holds the live AP, which matches the preserved `local.cfg`).
- `GET /restore/status` → `{pct, phase, done, error}` for the bar (until reboot).

---

## B.3 — Security (post-feature audit required)

- **Admin auth** on every mutating endpoint (`/backup/start`, `/backup/download`,
  `/backup/status`, `/restore/upload`, `/restore/apply`, `/themes/custom` POST/DELETE).
- **Anti zip-slip** on restore — the headline risk. Validate each archive member's resolved path
  is contained in its target root before extraction; reject symlinks and absolute/`..` paths.
- **Path containment** for every write/SFTP target (realpath within `$REPO/master` or the slave's
  `$REPO/slave`).
- **Atomic writes** for master config files (`write_cfg_atomic`); SFTP atomic put for slave files.
- **Theme validation** (B.0) — labels XSS-safe, colors hex-validated, font allowlisted.
- **Resource bounds** — restore upload size cap (200 MB), single-job locks, temp cleanup in `finally`.
- **No secret leak** — `local.cfg` (WiFi/admin password) is inside the `.bck`; the file downloads to
  the operator's machine (acceptable — it's their backup) but document that the `.bck` contains
  secrets and should be kept private.

## B.4 — Testing

- **Round-trip on the robot** (with the chantier-A safety backups in place): create a backup →
  change something (add a sound entry / edit a config) → restore → verify state matches the backup
  (counts + key file checksums) — done before the reboot step in the test, or verify post-reboot.
- **Zip-slip test**: craft a `.bck` with a `../../etc/x` member → `/restore/apply` must reject it,
  nothing written outside the targets.
- **Theme round-trip**: create a custom theme → backup → delete it → restore → theme back.
- **Large-upload path**: a ~70 MB `.bck` uploads via `/restore/upload` without hitting the 16 MB cap.
- Pure-logic units where possible (manifest parse, zip-slip path check) via pytest, like
  `audio_reconcile`.

## Rollout
B.0 → B.1 → B.2, each committed + deployed. Migration: none (new files created on first use).
Post-feature security audit (review agent) focused on zip-slip + path containment + admin auth +
the large-upload streaming. Update CLAUDE.md + a bd memory.
