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

The anchor is the OLDEST commit reachable from today's `main`. Any
operation that rewrites that commit (rebase, `git filter-repo`, branch
reset) changes its SHA and breaks the validator. `OFFICIAL_INITIAL_COMMIT`
MUST be updated in the SAME commit that lands the rewrite, otherwise the
validator will (correctly) reject every fork — including the operator's
own. The recovery procedure is detailed below.

#### Anchor history

| Date       | Old anchor (12-char prefix) | New anchor (12-char prefix) | Cause |
|------------|-----------------------------|------------------------------|-------|
| 2026-03-14 | (none — initial creation)   | `f01a9be5...`                | initial commit |
| 2026-05-22 | `f01a9be5...`               | `f7a2d1ef6271`               | history rewrite orphaned the chronological first commit (it now lives only on archived `claude/*` work branches) |
| 2026-05-29 | `f7a2d1ef6271`              | `5cd8937cc72b`               | `git filter-repo --path android/compiled --path Screenshots --invert-paths` purged ~150 MB of APK + screenshot blobs; both paths existed in the initial commit so its tree changed |

The current anchor in `shared/git_provenance.py:51` is:

```python
OFFICIAL_INITIAL_COMMIT = '5cd8937cc72bedfb3912233e738ddc370be472d0'
```

### Recovery procedure: history surgery (purge large blobs)

Use case: a path with large tracked binaries (APKs, screenshots, sample
media) has bloated `.git`. You want to drop it from all history.

#### Decision tree — does this surgery touch the anchor?

Before running anything, check whether the target path exists in the
current initial commit:

```bash
git ls-tree -r --name-only "$OFFICIAL_INITIAL_COMMIT" | grep -c "^<path>/"
```

| Result | Meaning | Anchor impact |
|--------|---------|---------------|
| `0`    | Path NOT in initial commit (added later in history) | **DNA-safe.** Surgery rewrites descendant commits only; initial commit tree unchanged → SHA unchanged → no anchor update needed |
| `>0`   | Path IS in initial commit | **Anchor-changing.** Surgery rewrites the initial commit too → new SHA → must update `OFFICIAL_INITIAL_COMMIT` in the same operation |

#### Full procedure (anchor-changing case)

This is the procedure used 2026-05-29 to purge `android/compiled/` +
`Screenshots/`. Generalisable to any future anchor-changing surgery.

```bash
# --- 0. Pre-flight on the dev PC ---
cd "$REPO_ROOT"
git status --short                # must be clean (commit or stash pending changes)
git tag pre-surgery-$(date +%F)   # safety reference

# --- 1. Surgery (rewrites every commit that touched the target paths) ---
# Install once: python -m pip install git-filter-repo
git filter-repo --path <path1> --path <path2> --invert-paths --force

# --- 2. New anchor ---
NEW_INITIAL=$(git rev-list --max-parents=0 HEAD)
echo "$NEW_INITIAL"

# --- 3. Update the constant in code ---
# shared/git_provenance.py:51
#   OFFICIAL_INITIAL_COMMIT = '<NEW_INITIAL>'

# --- 4. Stop future bleeding via .gitignore ---
# Add the purged path(s) to .gitignore so accidental re-tracks
# don't reintroduce the same blobs.

# --- 5. Verify DNA tests still pass ---
python -m pytest scripts/test_git_provenance.py -v
# Expected: 12/12 PASS — tests validate format, not value.

# --- 6. Commit + re-add origin (filter-repo strips it) ---
git add shared/git_provenance.py .gitignore
git commit -m "refactor(dna): re-anchor post-purge"
git remote add origin https://github.com/RickDnamps/AstromechOS.git
git push --force origin main      # force-push: history is rewritten

# --- 7. Reclaim local space (Windows note: `git gc` can fail with
#       "failed to run repack" — workaround is `prune` first) ---
git reflog expire --expire=now --all
git prune --expire=now            # drops orphan objects
git repack -a -d --depth=250 --window=250 --aggressive

# --- 8. Each existing live clone must do a one-time recovery ---
# `git pull --ff-only` will FAIL (history is rewritten, not fast-forward).
# On every Pi (or other clone):
ssh artoo@<pi-ip> 'cd ~/astromechos &&
    git fetch origin &&
    git reset --hard origin/main &&
    git gc --prune=now --aggressive'

# --- 9. Verify ---
# - Services up: systemctl is-active astromech-master astromech-monitor astromech-camera
# - Flask responds: curl -sS -m 3 http://127.0.0.1:5000/status -o /dev/null -w '%{http_code}\n'
# - MOTD renders: bash /etc/update-motd.d/99-astromechos | head
# - HEAD == origin/main on every clone
```

#### Companion sparse-checkout (optional working-tree slim-down)

Independent of the history surgery: master Pi runs a sparse-checkout
configured to skip non-runtime paths (`docs/`, `tests/`, `android/`,
top-level `*.md`, `LICENSE`, `preview.py`, etc.). See the live config
at `.git/info/sparse-checkout` on the master, and the rationale at
`bd memories astromech-sparse-checkout-master-2026-05-29` (~32 MB
working-tree reduction; does NOT affect `.git` size — only `git gc`
+ history surgery do).

#### Future-proofing rule

After 2026-05-29, the initial commit `5cd8937cc72b` no longer contains
`android/compiled/` or `Screenshots/`. Any FUTURE re-accumulation of
these paths (new APK builds, new doc screenshots) can be purged again
with the same `filter-repo` command **without touching the anchor** —
the decision tree above will return `0` for both. The check costs one
`git ls-tree` call; do it before every future surgery.

#### Lessons learned — 2026-05-29 run (the actual surgery)

These are the empirical observations from running the procedure live on
this repo. Anything noted here was painful enough to write down so that
future-me (or another maintainer) doesn't re-discover it.

| Observation | Why it matters | Action |
|-------------|----------------|--------|
| `git filter-repo` strips the `origin` remote by default | Push fails silently if forgotten | Step 6 in the procedure re-adds origin BEFORE push |
| `git filter-repo` also rewrites tag SHAs (any tag pointing into the rewritten range gets its target SHA updated) | The "safety tag" still points to the SAME commit content but at the new SHA — it's still useful as "this is the state before re-anchor", but it does NOT preserve the pre-rewrite SHAs | Don't rely on safety tags for SHA preservation; rely on a separate clone or repo backup |
| `git gc --aggressive --prune=now` on Windows fails with `fatal: failed to run repack` after a fresh `filter-repo` | The repack hangs or aborts mid-operation; loose objects pile up; `.git` doesn't shrink even though history is clean | Use `git prune --expire=now` first (drops orphan blobs from old history), THEN `git repack -a -d --depth=250 --window=250`. This is what dropped dev PC from 910 MB → 111 MB on 2026-05-29 |
| `git pull --ff-only` (used by `scripts/update.sh:108`) ALWAYS fails after a force-push of rewritten history | First update.sh after surgery aborts before rsync-to-slave runs | One-time recovery on EVERY existing clone: `git fetch origin && git reset --hard origin/main` BEFORE running update.sh |
| Sparse-checkout config (`.git/info/sparse-checkout`) survives `git reset --hard origin/main` | Working tree excludes stay in effect post-recovery; no need to re-apply | Verify after recovery with `ls -1` at repo root |
| DNA unit tests in `scripts/test_git_provenance.py` validate the FORMAT of `OFFICIAL_INITIAL_COMMIT` (40 hex chars), not the value | Re-anchoring with a new valid SHA is safe; tests stay green | Always run `python -m pytest scripts/test_git_provenance.py -v` after the constant update; 12/12 must PASS |
| The new initial commit's SHA can be read with `git rev-list --max-parents=0 HEAD` | This is the only authoritative source of the post-surgery anchor | Pipe directly into the constant update; never copy-paste a SHA you guessed |
| `.beads/issues.jsonl` may contain references to old commit SHAs in narrative text | Those references are historical fact, not load-bearing; filter-repo does NOT touch data files in the working tree | Leave them alone; old SHAs in memory text become dangling references but cause no breakage |

#### Before every future cleanup — checklist

```
[ ] 1. git ls-tree -r --name-only $(grep ^OFFICIAL_INITIAL_COMMIT shared/git_provenance.py | cut -d"'" -f2) \
       | grep -c "^<path>/"
       → 0  = DNA-safe, no anchor update needed
       → >0 = anchor change required, follow full procedure
[ ] 2. git tag pre-surgery-$(date +%F)         # safety reference
[ ] 3. git status --short                       # must be clean
[ ] 4. Confirm no other live clones besides the master Pi (or plan their recovery)
[ ] 5. Read the latest `docs/DEPLOY_SECURITY.md` (this file) for any new edge cases
```

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

### SD-card layout — BOOT partition (FAT32) + ROOTFS (ext4) cold edits

AstromechOS is shipped as a **Golden Image**: the rootfs already contains
a configured Linux user (UID 1000), the Python venv, all apt deps, the
`/home/<user>/astromechos/` checkout, systemd units, NetworkManager
profiles, and udev rules. The Imager NEVER touches the FAT-32 boot file
`userconf.txt` for user provisioning — Pi OS only honours that file on a
**virgin** image and silently ignores it on an image that already has UID
1000, so writing it would do nothing AND would create a false sense of
"changed credentials" on flash.

Instead the Imager performs a **cold edit of the rootfs partition** before
flashing the SD card. On Linux it uses libguestfs / loopback mount; on
Windows it uses libext2fs (Ext2Fsd / `ext2fsprogs` port) so the C# tool can
read/write ext4 without going through WSL.

```
/  (rootfs, ext4)               EDITED by the C# Imager BEFORE flash
├── etc/passwd                  rename the UID-1000 row (username + GECOS + home)
├── etc/shadow                  replace the UID-1000 row's hash with the new one
├── etc/group                   rename the UID-1000 user-private group + every
│                               supplementary group that lists the old name
├── etc/gshadow                 same rename (rows that reference the old name)
├── etc/sudoers.d/*             rename if the old username appears verbatim
├── etc/ssh/sshd_config.d/*     rename AllowUsers/AllowGroups directives
├── home/<old_user>             rename directory to /home/<new_user>
└── home/<new_user>/.config/    rewrite any XDG path with the new $HOME

/boot/  (FAT-32)                ADDED by the C# Imager BEFORE flash
├── ASTROMECH_FIRSTBOOT_READY   trigger marker (presence = run firstboot)
├── astromech_init.cfg          cfg-style bootstrap, consumed by
│                               lib_config.sh::cfg_get during firstboot;
│                               [system] user/home MUST match the new
│                               username + /home/<new_user> the rootfs
│                               edits installed.
├── hw_layout.json              optional HAT layout override (wins over
│                               the read-only smbus2 scan; see §3.5).
└── astromech_secrets/  (0700)
    ├── init_config.json        {"role": "master|slave", "hostname": "..."}
    ├── authorized_keys         operator pubkey + (on slave) Master pubkey
    └── id_ed25519 + .pub       Master-only outbound keypair for Master→Slave
                                SSH (matched by .pub in the Slave's
                                authorized_keys on its own SD card).
```

`userconf.txt` is **never** written by the AstromechOS Imager. If the
operator wants to keep the existing username (just rotate the password),
the Imager edits ONLY `/etc/shadow` and leaves `/etc/passwd` + `/etc/group`
+ `/home/<user>` untouched.

### Linux user provisioning — cold rootfs surgery (the C# Imager's job)

The Golden Image ships with a known UID-1000 user (today: `artoo`). The
Imager renames + repasswords that account at burn time so each robot ends
up with a unique credential pair. AstromechOS firstboot doesn't care which
username it inherits — `firstboot_setup.sh::capture_user` reads
`[system] user` from `astromech_init.cfg` first and falls through to
`$SUDO_USER` / `pi` / `astromech` / `artoo` if absent. So the Imager's job
is to keep the rootfs and the `astromech_init.cfg` in sync.

**Hash format for `/etc/shadow`** — exactly the same digest Pi OS accepts
for `useradd -p`: `$id$salt$hash`. `$6$` = SHA-512 crypt (portable, Bullseye
+ Bookworm + Trixie); `$y$` = yescrypt (Bookworm+). Use `$6$` for maximum
portability across Pi OS releases.

The canonical generator on the Imager host:

```bash
echo "$PASSWORD" | openssl passwd -6 -stdin
# → $6$<random-16-char-salt>$<86-char-base64-hash>
```

**Per-device Imager flow** (C# pseudo-code; the real tool uses libext2fs
to mount ext4 read/write without WSL):

```csharp
// per SD card (master OR slave):
string newUser     = "r2d2_eric";                              // operator picks
string newPw       = SecretsGen.UrlSafe(12);                   // 16-char random
string shadowHash  = ProcessRunner.Run(                         // $6$...$...
    "openssl", "passwd -6 -stdin", stdin: newPw);

using (var fs = Ext2.Mount(sdCardRootfsPartition, readWrite: true))
{
    // 1. /etc/passwd : rewrite the UID-1000 line.
    Etc.Passwd.RenameUid(fs, uid: 1000, newName: newUser,
                         newHome: $"/home/{newUser}");

    // 2. /etc/shadow : replace the hash field for that user.
    Etc.Shadow.SetHash(fs, user: newUser, hash: shadowHash);

    // 3. /etc/group : rename the user-private group (default Pi OS) +
    //    rewrite the member list in every group that referenced the
    //    old name (sudo, dialout, gpio, i2c, spi, video, netdev, …).
    Etc.Group.RenameUser(fs, oldName: "artoo", newName: newUser);
    Etc.GShadow.RenameUser(fs, oldName: "artoo", newName: newUser);

    // 4. Rename the home directory in-place.
    fs.Rename("/home/artoo", $"/home/{newUser}");

    // 5. Sweep config files that hardcoded the old username.
    foreach (var path in new[] { "/etc/sudoers", "/etc/sudoers.d/",
                                 "/etc/ssh/sshd_config",
                                 "/etc/ssh/sshd_config.d/" })
        TextSubstitute.RewriteUsername(fs, path, "artoo", newUser);
}

// 6. astromech_init.cfg on the BOOT partition must match the rootfs edits.
File.WriteAllText(sdCardBootPath / "astromech_init.cfg",
    $@"[system]
       user = {newUser}
       home = /home/{newUser}
       repo_path = /home/{newUser}/astromechos
       service_uid = 1000
       ... ([github], [home_wifi], [hotspot], [admin] follow)");

// 7. Record (sd_serial, host_role, newUser, newPw) in the fleet inventory.
```

⚠ **Pair convention**: same `(newUser, newPw)` for BOTH cards of a paired
master/slave (operator memorises one credential per robot), but distinct
across robots so a stolen SD doesn't yield blanket access to the fleet.

The rootfs path `/home/<new_user>/astromechos/` is the install location of
the AstromechOS repo. The Imager does NOT need to re-checkout git — the
Golden Image already has it; only the parent path needs renaming so the
running services find their code.

⚠ **systemd unit templates** in the Golden Image must use `%U`/`%h` or
`${TARGET_USER}`-style placeholders (NOT a hardcoded `artoo`). The Imager's
rename will break any unit that has a literal `artoo` in `ExecStart=`,
`User=`, `WorkingDirectory=`, or `Environment=`. See
`master/services/*.service.template` and `slave/services/*.service.template`
— they are templated and processed at install time by `update.sh` /
`install_service_template_remote`.

### `/boot/astromech_init.cfg` — AstromechOS-specific bootstrap

Example the Imager writes (everything is OPTIONAL — firstboot skips any
section it doesn't find):

```ini
[system]
user        = artoo
home        = /home/artoo
repo_path   = /home/artoo/astromechos
service_uid = 1000

[github]
repo_url          = https://github.com/RickDnamps/AstromechOS.git
branch            = main
auto_pull_on_boot = true

[home_wifi]
# Optional — usually handled by Pi OS wpa_supplicant.conf at the boot-
# partition root. Repeated here only if you want AstromechOS to take
# over the wlan1 USB-dongle path explicitly.
ssid     = TonWifiMaison
password = changeme

[hotspot]
# REQUIRED for auto-pairing master/slave at firstboot. Imager bakes the
# SAME (ssid, password) pair into BOTH SD cards of a paired set; unique
# across robots so 20 R2-D2 at a convention never collide.
# Master at firstboot creates the bootstrap AP on this SSID; Slave joins
# it; Master then regenerates a serial-derived FINAL SSID and pushes the
# swap. See §4.7 below.
ssid     = Astromech_Pair_A3F8B142
password = solo1977randoma3

[admin]
# Flask UI admin password (separate from the Linux SSH password above).
# Default in main.cfg is 'deetoo' if absent here. firstboot §4.6 persists
# this into local.cfg [admin].
password = boo3pic7lock22
```

**Imager generation snippet** for `[hotspot]` + `[admin]` per pair:

```python
import secrets
pair_ssid = "Astromech_Pair_" + secrets.token_hex(4).upper()
pair_psk  = secrets.token_urlsafe(12)
admin_pw  = secrets.token_urlsafe(12)
# write the SAME [hotspot] block into BOTH cards of a pair.
# write the SAME [admin] password into BOTH cards (only master honours it).
```

### First-boot script flow

`scripts/firstboot_setup.sh` is fired by the oneshot systemd unit
`astromech-firstboot.service`. Both are installed by `setup_master.sh`
or by the Imager itself.

```
firstboot_setup.sh
  1. ConditionPathExists guard           ← skip if no trigger marker
  2. source lib_config.sh + capture_user → TARGET_USER / TARGET_HOME
                                            (Pi OS userconf.txt already
                                             created the account)
  3. Inject /boot/astromech_secrets/authorized_keys
        atomic append to $TARGET_HOME/.ssh/authorized_keys
        dedupe, chmod 0600, chown TARGET_USER
        copy optional id_ed25519* keypair (for Master → Slave SSH)
  4. Parse /boot/astromech_secrets/init_config.json
        → role (master|slave)            → write_local_cfg [system] role
        → hostname                       → hostnamectl + /etc/hosts
                                              (RFC-1123 charset filter)
                                              default: astromech-<role>
  4.5 I2C HAT layout detection (read-only, never bricks boot):
        /boot/hw_layout.json exists  →  cp verbatim (Imager wins)
        else                         →  detect_hats.py --output ...
                                          (smbus2, READ-ONLY, locked)
        on failure                   →  log WARN + continue
                                          (services boot DEGRADED)
  4.6 Admin password (Master only):
        cfg_get admin password       →  write_local_cfg admin password
                                          (Flask UI unlocked with Imager-
                                          baked value; absent → main.cfg
                                          default 'deetoo' applies)
  4.7 Hotspot bootstrap + handover (the chicken-and-egg solver):
        Master role →  setup_master_network.sh --non-interactive
                          --ssid BOOT_SSID --psk BOOT_PSK
                       → wait ≤5 min for Slave on astromech-slave.local
                       → gen_hotspot_ssid.sh → FINAL serial-derived SSID
                       → ssh slave 'sudo -n nmcli connection modify ...'
                          (mirrors _push_slave_hotspot_creds in
                           settings_bp.py:772)
                       → nmcli modify own AP + nmcli connection up
                       → sed local.cfg [hotspot] with final creds
                          (pair sealed for life)
        Slave  role →  setup_slave_network.sh --non-interactive
                          --ssid BOOT_SSID --psk BOOT_PSK
                          (Master rewrites this profile over SSH a few
                           seconds later — NM transparently rejoins
                           the FINAL SSID on the next AP cycle)
        Failure modes: every step log_err and falls through. firstboot
                       NEVER aborts on networking; operator can finish
                       via Flask UI → Settings → Hotspot.
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
