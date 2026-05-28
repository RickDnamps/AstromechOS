# AstromechOS — Deploy Security & First-Boot Architecture

> Canonical reference for the **Git DNA paternity check** + **AstromechOS
> Imager** + **firstboot bootstrap** chain. Read this before touching
> any of `shared/git_provenance.py`, `master/api/deploy_bp.py`,
> `scripts/firstboot_setup.sh`, or `scripts/lib_config.sh` paternity
> helpers.

---

## The threat model

AstromechOS lets the operator point `origin` at a Git URL of their choice
(forks, mirrors, dev branches). Two attack surfaces:

1. **Typo or mistake** — operator pastes `WordPress/WordPress.git` into
   the Deploy panel. Without a check, the next `/system/update` runs
   `git pull` against a totally unrelated repo, lobotomising the robot
   on the next reboot.
2. **Malicious AstromechOS Imager bootstrap** — a tampered SD-card image
   ships with `/boot/astromech_init.cfg` pointing at a hostile fork.
   Without a check, first boot silently swaps the remote and the robot
   pulls arbitrary code.

The DNA check defends against both with the same primitive.

---

## 1. The DNA paternity check

### What it is

The official AstromechOS repo's current `main` branch traces back to a
specific commit. Any **legitimate fork** of that repo, made at any point
since, has that commit in its ancestry by definition. An **unrelated
repo** (WordPress, a fresh `git init`, an attacker's project) does not.

Module: `shared/git_provenance.py`. Frozen constant in code (NOT
configurable):

```python
OFFICIAL_INITIAL_COMMIT = 'f7a2d1ef62714ded6ad4ba0600fc398ac7f2a6a0'
OFFICIAL_REPO_URL       = 'https://github.com/RickDnamps/AstromechOS.git'
```

### How it runs

```
validate_paternity(repo_path, url, branch='main')
  1. validate_remote_exists(url)          ← git ls-remote --heads <url>
  2. git fetch --no-tags <url> <branch>   ← into FETCH_HEAD (no merge,
                                            no tracking, no --depth —
                                            shallow grafts would
                                            break ancestor check)
  3. Ensure anchor is in local objects    ← cat-file -e <ANCHOR>;
                                            else fetch official main
  4. git merge-base --is-ancestor         ← <ANCHOR> FETCH_HEAD
                                            → exit 0 = PASS
                                            → exit 1 = FAIL (unrelated repo)
                                            → exit 2 = error
```

Returns `(ok: bool, reason: str)`. The caller MUST abort the change on
`ok=False` and leave `origin` untouched ("never half-swap").

### Why the anchor is hard-coded

If `OFFICIAL_INITIAL_COMMIT` were a cfg value, anyone who can write
`local.cfg` could substitute their own anchor and neutralise the
check. Hard-coded in the Python module = part of the code review +
git signature surface.

### Edge case: history rewrite

The original chronological first commit of AstromechOS (`f01a9be5...`,
2026-03-14) was orphaned by a history rewrite on 2026-05-22. It now
exists only on archived `claude/*` work branches and is **not** an
ancestor of today's `main` HEAD. The current anchor is the OLDEST
commit reachable from today's `main`. If `main` is ever rebased again,
`OFFICIAL_INITIAL_COMMIT` MUST be updated in the same commit as the
rebase, otherwise the validator will (correctly) reject every fork —
including the operator's own. See the docstring in
`shared/git_provenance.py` for the recovery procedure.

### Tests

`scripts/test_git_provenance.py` — 12 unit tests using temp git repos
(no network). Cover:

- Constants format + presence
- URL scheme rejection (empty, non-string, `javascript:`, ...)
- `git ls-remote` reachability + non-Git URL handling
- Legitimate fork PASS (`file://` of local `.git`)
- Unrelated tmp repo REJECT
- Bad branch names rejected (`--upload-pack=...`)
- Non-repo path rejected

Run: `python scripts/test_git_provenance.py`.

---

## 2. The Deploy API surface

### Endpoints

All admin-gated (`X-Admin-Pw` header).

| Method | Route | What it does | Underlying handler |
|---|---|---|---|
| `GET`  | `/api/deploy/status` | Returns `{local_sha, remote_sha, remote_msg, behind_count}`. Cached 60 s. | `status_bp.system_deploy_status` |
| `POST` | `/api/deploy/save-config` | Persist `github.repo_url`, `github.branch`, `github.auto_pull_on_boot`, `slave.host`. **Runs DNA check on repo_url change.** Rejects unrelated keys (400). | `settings_bp.set_config` |
| `POST` | `/api/deploy/update` | `git pull` + rsync to Slave + reboot Slave + restart Master. Gated by `_deploy_safety_check` (E-STOP / stow / choreo / motion ramp). | `status_bp.system_update` |
| `POST` | `/api/deploy/rollback` | `git checkout HEAD^` + rsync + reboot Slave + restart Master. Same safety gate. | `status_bp.system_rollback` |

`deploy_bp.py` is a thin alias layer — the canonical implementations
still live in `status_bp` and `settings_bp` (no duplicated logic). The
historical `/system/deploy_status` + `/system/update` + `/system/rollback`
+ `/settings/config` routes continue to work; the Settings → Deploy UI
panel uses them and is unchanged.

### DNA gate in `/settings/config`

When a POST changes `github.repo_url`, the validator runs **before**
any cfg write:

```
set_config(POST {github.repo_url: candidate})
  ├── _normalise(candidate)            ← scheme + length checks
  ├── read current cfg [github] repo_url
  ├── if candidate != current:
  │     validate_paternity(...)
  │       ├── DNA OK   → continue to write
  │       └── DNA FAIL → return 400 + reason, origin untouched
  └── (write loop runs only on DNA OK)
```

Properties:

- **Atomic-w.r.t.-state**: if DNA fails, nothing was written.
- **Cheap when unchanged**: a save that doesn't touch `repo_url`
  incurs zero `git fetch` cost.
- **Fail-closed offline**: a Pi without internet can't reach the
  candidate remote → validator returns FAIL → save refused.

---

## 3. The AstromechOS Imager workflow

The Imager is a PC application (planned — separate codebase) that
prepares an SD card before flashing. Its job: drop the right files on
the boot partition so the Pi self-provisions on first boot, **no
human interaction, no Wi-Fi connection by hand, no SSH login**.

### SD-card boot partition layout

```
/boot/ASTROMECH_FIRSTBOOT_READY        ← trigger marker (presence = run)
/boot/astromech_init.cfg               ← cfg-style bootstrap, consumed
                                          by lib_config.sh::cfg_get
                                          (already wired in commits
                                          fdf8c75 → 7674f62)
/boot/astromech_secrets/  (chmod 0700)
    init_config.json                   ← {"role": "master|slave",
                                          "hostname": "...", ...}
    authorized_keys                    ← OpenSSH pubkeys, one/line
                                          (PC public key, plus any
                                          friends the operator wants
                                          to grant access to)
    id_ed25519 + id_ed25519.pub        ← optional outbound keypair
                                          (Master only — for the
                                          Master→Slave ssh-copy-id)
```

`/boot/astromech_init.cfg` example the Imager would write:

```ini
[system]
user        = pi
home        = /home/pi
repo_path   = /home/pi/astromechos
service_uid = 1000

[github]
repo_url          = https://github.com/RickDnamps/AstromechOS.git
branch            = main
auto_pull_on_boot = true

[home_wifi]
ssid     = TonWifiMaison
password = changeme

[hotspot]
ssid     = R2D2_Eric
password = solo1977
```

### First-boot script flow

`scripts/firstboot_setup.sh` is fired by the oneshot systemd unit
`astromech-firstboot.service`. Both are installed by `setup_master.sh`
or by the Imager itself.

```
firstboot_setup.sh
  1. ConditionPathExists guard           ← skip if no trigger marker
  2. source lib_config.sh + capture_user → TARGET_USER / TARGET_HOME
  3. Inject /boot/astromech_secrets/authorized_keys
        atomic append to $TARGET_HOME/.ssh/authorized_keys
        dedupe, chmod 0600, chown TARGET_USER
        copy optional id_ed25519* keypair
  4. Parse /boot/astromech_secrets/init_config.json
        → role (master|slave)            → write_local_cfg [system] role
        → hostname                       → hostnamectl + /etc/hosts
                                              (RFC-1123 charset filter)
  4.5 I2C HAT layout detection (read-only, never bricks boot):
        /boot/hw_layout.json exists  →  cp verbatim (Imager wins)
        else                         →  detect_hats.py --output ...
                                          (smbus2, READ-ONLY, locked)
        on failure                   →  log WARN + continue
                                          (services boot DEGRADED)
  5. If [github] repo_url differs from current `origin`:
        dna_validate  → DNA OK   → git remote set-url + fetch + reset --hard
                     → DNA FAIL → KEEP origin pointing at the official URL,
                                   log the rejection, continue boot
  6. shred + rm /boot/astromech_secrets/
     rm /boot/ASTROMECH_FIRSTBOOT_READY
     systemctl disable astromech-firstboot.service
     sync + reboot
```

Idempotency: every sub-step is safe to re-run. The marker is only
deleted in step 6, so a crashed run can be retried by rebooting.

All output is logged to `/var/log/astromech-firstboot.log` AND the
systemd journal (`journalctl -u astromech-firstboot`).

### Why the marker is the trigger

- `ConditionPathExists` in the systemd unit means the service is
  **skipped entirely** on a boot where the marker isn't present —
  zero overhead on the running R2-D2.
- Once the script runs successfully, it removes the marker. Next
  boot: condition fails → service skipped → done.
- If the script crashes mid-way (rare — disk full, SD corruption),
  the marker remains → next boot retries automatically.

---

## 3.5. Hardware layout detection — `scripts/detect_hats.py`

> Chantier: `e40e376` (core + tests) → `0ec59df` (firstboot wiring).
> Module: `scripts/detect_hats.py` (~470 LOC) + `scripts/test_detect_hats.py`
> (28 tests, all green). Output: `master/config/hw_layout.json` (gitignored)
> or `slave/config/hw_layout.json`. Imager override at `/boot/hw_layout.json`.

### Why a separate detection pass

Every prior chantier in the deploy security stack defends the SOFTWARE supply
chain (Git DNA, signed Imager bootstrap, SSH key injection). This pass defends
the HARDWARE side — what HATs are physically attached, in what role.

The Settings → HATs panel in the existing UI takes the operator's word for
which I2C address is a servo controller vs a motor controller. The cfg
validator (`master/api/settings_bp.py:_parse_hat_addr/_parse_hat_list`)
checks ranges + uniqueness but not the actual hardware. A typo (`slave_hats
= 0x40` collides with `slave_motor_hat`) ships PWM commands to the TB6612
motor inputs and damages the H-bridge. `detect_hats.py` closes that gap by
observing the bus and emitting a JSON record of what's actually there.

### Read-only safety contract

The hardware is allowed to be in any state when we scan — including mid-PWM,
servos under tension, a live choreography. THREE independent layers enforce
that detect_hats can never glitch a live PCA9685:

1. **`ReadOnlySMBus` wrapper** (`detect_hats.py:114`). Wraps an `smbus2.SMBus`
   and refuses every write API with `AssertionError` — `write_byte_data`,
   `write_byte`, `write_word_data`, `write_block_data`, `write_i2c_block_data`,
   `process_call`, `block_process_call`. The detection code literally cannot
   write through this object.
2. **`/run/astromech-i2c.lock`** (fcntl flock, non-blocking by default).
   Coordinates with the in-process `_i2c_scan_lock` in
   `master/api/diagnostics_bp.py` so a parallel `/diagnostics/i2c_scan`
   request, or a live PCA9685 PWM burst from the dome driver, cannot race
   the scan. `--no-lock` available for emergency bypass.
3. **Test-suite spy**. Every `detect()` test asserts that the underlying
   `FakeSMBus.calls` contains zero `write_*` entries. A future regression
   that bypasses the wrapper would still trip this spy.

Live evidence (commit `0ec59df` deploy): the test ran against the production
Master Pi WHILE `astromech-master.service` was active and holding the dome
panels in their closed positions. Bus read of 0x40 returned the expected
PCA9685 signature (`prescale=0x79`=50 Hz, `subadr1=0xE2`/`subadr2=0xE4`/
`subadr3=0xE8`/`allcall=0xE0` POR defaults intact). Zero glitches, zero
service log errors.

### Algorithm — 4 layers, fail-closed

```
detect()
  Layer A (best-effort)  /proc/device-tree/hat/{vendor,product}
                         /sys/bus/i2c/devices/0-0050/eeprom
                         → almost always absent (Waveshare clones don't
                           ship the Pi HAT spec EEPROM); recorded as
                           context for the operator but not load-bearing

  Layer B (presence)     for addr in 0x40..0x47:
                              read_byte_data(addr, REG_MODE1)
                         → ACK = device present
                         → NACK / EREMOTEIO = empty slot

  Layer C (fingerprint)  for each present address, sweep:
                              MODE1, MODE2, SUBADR1, SUBADR2,
                              SUBADR3, ALLCALLADR, PRESCALE
                         Score 0..4 against PCA9685 power-on defaults
                         (SUBADR1=0xE2, SUBADR2=0xE4, SUBADR3=0xE8,
                          ALLCALLADR=0xE0 — survive our driver init).
                         4/4 → high confidence,  3/4 → medium,
                         1-2 → low (matched MODE2 default),
                         0   → "unknown" chip

  Layer D (role)         host = master  → every PCA9685 = servo_dome
                         host = slave   → 0x40 = motor_drive (Waveshare
                                                 convention from ELECTRONICS.md)
                                          0x41+ = servo_body
                         If [i2c_servo_hats] slave_motor_hat is set in cfg,
                         that wins over the 0x40 convention default.
```

`detect()` writes a JSON dictionary (`schema_version: 1`) with an entry per
detected HAT — `addr`, `chip`, `role`, `confidence`, `evidence` (the per-
register hex values that justified the decision), `score`, and `source`
(the inference trail, e.g. `"fingerprint+master-convention"`).

### Imager workflow — `/boot/hw_layout.json` override

The PC Imager that prepares an SD card knows the hardware layout BEFORE
the Pi ever boots (the operator picks "R2-D2 Master with 1 servo HAT at
0x40" in the GUI, or scans the Imager's own HAT inventory). It can drop a
pre-filled `hw_layout.json` into `/boot/`:

```
/boot/hw_layout.json     ← Imager-provided, wins over a fresh scan
```

`scripts/firstboot_setup.sh` step 4.5:

1. If `/boot/hw_layout.json` exists → `cp` verbatim to
   `<repo>/master/config/hw_layout.json` (or `slave/config/hw_layout.json`
   depending on role), `chmod 0644`, `chown TARGET_USER`. **No scan runs.**
2. Else: `python3 scripts/detect_hats.py --output <path> --role $ROLE
   --verbose`, output tee'd to the firstboot log.
3. On failure: log a precise WARN with the exit-code translation, **never
   abort**. The boot must not brick because a single HAT is unresponsive.

### Failure modes table

| Symptom | Detected as | Behaviour |
|---|---|---|
| `/dev/i2c-1` missing | exit code 3 | WARN `/dev/i2c-1 missing (enable I2C in raspi-config)`; services boot DEGRADED. |
| `smbus2` not installed | exit code 2 | WARN `smbus2 not installed (apt install python3-smbus)`. |
| Permission denied on `/dev/i2c-1` | exit code 4 | WARN `permission denied (user not in i2c group?)`. |
| Lock held by another process | exit code 5 | WARN `bus lock held (master.service running?)`. Operator can retry with `--no-lock` after stopping the service. |
| Empty bus (no HATs) | exit code 0, `hats: []` | JSON written with empty array; services log "DEGRADED: no HATs detected" at startup. |
| Non-PCA9685 device at 0x40-0x47 | `chip: "unknown"` | JSON records the read evidence; role still assigned by convention; services treat as best-effort. |
| Bus jammed mid-scan | `errors: [{addr, error}]` | Per-address error captured in JSON; remaining addresses still scanned. |

### Read-only contract enforcement summary

Every layer of the chain is closed:
- The scanner (`detect_hats.py`) cannot write — the wrapper class refuses.
- The firstboot caller (`firstboot_setup.sh`) cannot bypass — it invokes
  the same Python script, same wrapper.
- The Imager (eventual PC tool) cannot inject writes — the JSON it drops at
  `/boot/hw_layout.json` is parsed-only, never executed.
- The service consumers (`master/drivers/*`, planned commits) READ the JSON
  and decide to operate or to enter degraded mode — they do not delegate
  writes to the detection code.

The principle: **detection observes; services decide**. A missing HAT
becomes a logged degradation, not a crash.

---

## 4. Mapping persistence layer (chantier G, 2026-05-28)

> Once a HAT is detected, the **identity layer** (Phase G of the chantier
> series) makes calibration data immune to address changes. This is the
> dedicated companion to `docs/MAPPING.md` — read that first, this
> section recaps the security-relevant aspects only.

### What the mapping layer adds to deploy security

- `config_mapping.json` (`master/config/` + `slave/config/`, gitignored)
  is **included in the `.bck` archive** alongside `dome_angles.json` and
  `servo_angles.json`. A backup now carries the entire HAT identity
  binding so a restore can be aligned with arbitrary hardware.
- Restore flow runs `validate_mapping_against_layout` between the
  staged mapping and the live `hw_layout.json` BEFORE moving files
  into place. Each address mismatch becomes a warning entry attached
  to the restore job state — visible to the operator at the Restore
  panel, never silently lost.
- Labels and calibrations are keyed by stable HAT identity
  (`Body_HAT_A`), not by I2C address. Restoring onto hardware whose
  jumpers are wired differently leaves data 100 % intact; the
  operator clicks Settings → HATs → RE-MAP to align the identities
  with the new physical addresses, then the driver hot-reloads.

### `POST /hats/remap` — the only address-mutation surface

```
POST /hats/remap                @require_admin
{ "host": "master" | "slave",
  "hats": [{"id": "Body_HAT_A", "address": "0x42"}, ...] }
```

Server-side rules (defense-in-depth alongside the UI guard):

1. Host enum (`master` | `slave`).
2. Every identity must **already exist** in the current mapping. No
   create / no rename via this endpoint — those are an Imager-UI job.
3. Every address must be in `0x40..0x77` (the validator range from
   `master/api/settings_bp.py:_PCA9685_MIN/MAX`).
4. **Address uniqueness within the side** — no two identities at the
   same physical address. The atomic refusal returns HTTP 400 with
   `"address 0xNN assigned to more than one HAT; each physical
   address must be unique"`.

On success: atomic tmp + `os.replace` write of `config_mapping.json` +
in-process driver `_mapping` swap + `.reload()` so the change takes
effect without a service restart. The legacy `/settings/config`
endpoint **rejects** any `i2c_servo_hats.*` key — that namespace is
zero-config now, the only mutation path is `/hats/remap`.

### UI guard — the three-layer anti-collision

| Layer | What it does | Failure mode |
|---|---|---|
| **Dropdown filtering** | Only addresses actually detected by the live scan appear in the dropdown. Operator literally cannot pick a fictional address. | Stale UI → falls through to layer 2. |
| **Live collision check** | `_checkRemapCollisions` runs on every dropdown change AND at panel open; duplicate selections highlight red + SAVE button disabled + pulsing red banner `Collision d'adresse détectée`. | Operator bypasses disabled button → falls through to layer 3. |
| **Backend refusal** | `seen_addrs` set check in `/hats/remap` returns HTTP 400 atomically. No partial write possible. | (none — atomic write only after every check passes) |

### Files added / changed under deploy security

```
shared/hw_mapping.py                                  ← NEW (G1)
master/config/config_mapping.json.example             ← NEW (schema doc)
slave/config/config_mapping.json.example              ← NEW
master/api/backup_core.py                             ← + import json (latent bug fix)
                                                        + config_mapping in BACKUP_FILESET
                                                        + validate_mapping_against_layout
master/api/backup_bp.py                               ← restore validation hook
master/api/hats_bp.py                                 ← POST /hats/remap
master/api/servo_bp.py                                ← HardwareOfflineError
scripts/detect_hats.py                                ← --write-mapping flag + atomic sync
```

Architecture, all 6 phases, operator workflow, tests inventory →
**[docs/MAPPING.md](MAPPING.md)**.

---

## 4.5. I2C troubleshooting — Dépannage des conflits d'adresses

When two HATs respond at the same I2C address, the bus electrically goes
into contention: both devices ACK the address byte, both attempt to drive
SDA on read, and the master sees a merged value that doesn't correspond
to either device's actual state. PWM commands meant for the dome servos
might also drive the motor HAT's TB6612 inputs — destructive. This
section documents how `detect_hats.py` surfaces the problem and how to
fix it physically.

### How collisions are detected

`detect_hats.py` runs a **multi-read consistency check** on every address
that ACKs the initial presence probe. For each candidate PCA9685 it reads
MODE1, SUBADR1, SUBADR2, and ALLCALLADR five times each. A single healthy
PCA9685 returns the same value on every read (registers are stateless,
no internal mutation). Two devices fighting on the bus produce arbitrary
SDA dominance per read → inconsistent values across samples.

```
collision check (per address):
  for reg in [MODE1, SUBADR1, SUBADR2, ALLCALLADR]:
      seen = { read_byte_data(addr, reg) for _ in range(5) }
      if len(seen) >= 2:
          → ADDRESS_COLLISION flagged for this addr
          → JSON entry: {addr: '0x40', collision: true,
                         error: 'ADDRESS_COLLISION', ...}
```

The check is **best-effort, not bulletproof**. Two identical PCA9685s
freshly powered up (both at POR defaults, both untouched by any
driver init) may return the same value on every read because they
literally have the same internal state. The check catches the most
common real-world case: one running HAT vs one fresh HAT at the same
address, where prescale / MODE1 differ. False negatives default to
the DEGRADED mode (driver init proceeds and may glitch — investigation
prompt: weird servo behaviour after a recent hardware swap).

### Service behaviour on collision

When the master/slave driver loads `hw_layout.json` and sees a HAT
entry with `collision: true`, the driver refuses to initialise that
HAT and emits a CRITICAL log:

```
CRITICAL: I2C Address Conflict at 0x40. Check hardware jumpers
(A0/A1/A2 — solder pads on the back of the PCA9685 board).
Detection ran <N> reads; values diverged across samples.
The driver will NOT operate any servo on 0x40 until the conflict
is resolved.
```

This is **distinct from DEGRADED mode** (HAT simply absent). DEGRADED
lets other subsystems run; CRITICAL on a conflict refuses the whole
HAT because operating against a conflicted bus produces unpredictable
hardware behaviour — a servo command might fire a motor PWM, a "close"
might "open", etc.

### Physical resolution — how to fix the jumpers

PCA9685 / Waveshare HAT boards have solder pads labelled A0–A5 on the
back. Each pad is a 1-bit address selector. The chip's I2C address is:

```
base address = 0x40
final address = 0x40 + (A5*32 + A4*16 + A3*8 + A2*4 + A1*2 + A0*1)
```

Factory ships every board at 0x40 (A0–A5 all open / pulled LOW). To
move a second HAT to 0x41, **solder the A0 pad closed** (jumper SHORT).
0x42 → solder A1. 0x43 → solder A0 + A1. Etc.

| Desired addr | Pads to solder closed (jumper SHORT) |
|---|---|
| 0x40 | none (factory default) |
| 0x41 | A0 |
| 0x42 | A1 |
| 0x43 | A0 + A1 |
| 0x44 | A2 |
| 0x45 | A0 + A2 |
| 0x46 | A1 + A2 |
| 0x47 | A0 + A1 + A2 |

> ⚠️ **Don't** solder ALL pads — the upper range 0x70-0x77 is reserved
> by the PCA9685 spec for All-Call / Sub-Address replies. The cfg
> validator (`master/api/settings_bp.py:_PCA9685_MAX = 0x77`) accepts
> them anyway because some clones permit it, but it's discouraged.

### After a physical fix — operator workflow

1. Power the robot OFF (UPS / 12 V bench supply). Never re-jumper a
   live HAT — you can short Vcc to GND on the PCA9685 supply pin and
   destroy the regulator.
2. Solder the appropriate A0/A1/A2 pads per the table above.
3. Power back ON. The master service comes up, the dome servo driver
   loads `hw_layout.json`. If the JSON is stale (still reflects the
   pre-fix collision), the driver will still log CRITICAL.
4. Re-run detection — either:
   - Stop the master service: `sudo systemctl stop astromech-master`
   - Run: `python3 scripts/detect_hats.py --role auto --verbose`
   - Start it back up: `sudo systemctl start astromech-master`
5. Verify in the journal:
   `journalctl -u astromech-master -n 50 | grep -i hat`
   Look for `DomeServoDriver ready — N HAT(s) ...` (READY state) instead
   of `CRITICAL: I2C Address Conflict ...`.

### When the conflict comes from the cfg, not the hardware

A different failure mode the validator already catches: the operator
sets `slave_motor_hat = 0x40` AND `slave_hats = 0x40` (typo). The
Master `/settings/config` POST returns HTTP 400 with
`"slave_motor_hat 0x40 cannot also be in slave_hats — motor + servo
at same I2C address corrupts both."` — see
`master/api/settings_bp.py` collision check. This kicks in before
the change ever lands in `slave.cfg`. The cfg-side guard fires
PRE-write; the hardware-side guard documented here fires POST-write
(when the operator manually edits the cfg via SSH or restores a
backup with a conflict, etc.).

---

## 4. Failure modes & operator UX

| What happens | UX | Recovery |
|---|---|---|
| Operator types a bad URL in the Deploy panel | 400 with `error: "Repository validation failed (paternity check)" + detail + hint`. Settings panel surfaces the error toast. `origin` untouched. | Retype URL or revert to official. |
| Imager wrote an unrelated URL in `/boot/astromech_init.cfg` | First boot completes provisioning EXCEPT the remote swap. `origin` stays at the official URL. Log in `/var/log/astromech-firstboot.log` + journal. | Operator fixes via Deploy panel later. |
| Pi has no internet at first boot | DNA check fails ("`git ls-remote failed`"). Same as above — `origin` untouched, log preserved. | Connect Wi-Fi, retry via Deploy panel. |
| Operator wants to genuinely use a fork | DNA validates against the fork's `main`. If fork was made from RickDnamps/AstromechOS at any point, the anchor is in its history → PASS → write proceeds. | Just save the URL. |
| Eric rebases `main` upstream | After the rebase, the old anchor is no longer reachable from new main → every fork would now fail DNA. | Update `OFFICIAL_INITIAL_COMMIT` in `shared/git_provenance.py` to the new oldest reachable commit, in the same rebase commit. |

---

## 5. Files touched by the chantier (commits `5a0faa7 → 34f7a9e`)

```
shared/git_provenance.py                            ← NEW
scripts/test_git_provenance.py                      ← NEW (12 tests)
scripts/lib_config.sh                               ← + write_local_cfg
                                                       + dna_validate
                                                       + _python helper
master/api/settings_bp.py                           ← DNA gate in set_config
master/api/deploy_bp.py                             ← NEW (/api/deploy/*)
master/flask_app.py                                 ← register deploy_bp
scripts/firstboot_setup.sh                          ← NEW
master/services/astromech-firstboot.service.template← NEW (oneshot)
scripts/setup_master.sh                             ← install firstboot.service
```

---

## 6. Related references

- `shared/git_provenance.py` — module docstring contains the
  authoritative algorithm description.
- `scripts/test_git_provenance.py` — runnable specification.
- `bd memories astromech-deploy-adn-firstboot-chantier-2026-05-28`
- The previous portability chantier
  (`astromech-portability-chantier-2026-05-28`) is the foundation
  this builds on — without `shared/identity.py` + `lib_config.sh`,
  none of this is portable.
