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
