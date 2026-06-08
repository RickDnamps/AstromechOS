# Firstboot lifecycle — Imager ↔ AstromechOS contract

**This document is the binding contract between the sibling
`AstroMechOS_Imager` (C# / Python, runs on a Windows PC) and the
AstromechOS firstboot scripts (run as root at the first boot of a
freshly-imaged Pi).** It defines exactly **what the Imager MUST place
on the boot partition** and **where each AstromechOS script expects to
find it**. A new feature in either project should not ship without
updating this doc and (if the contract surface changes) the
`_self_validate()` self-check on the Imager side.

It is also the operator-facing companion to
[`DEPLOY_SECURITY.md`](DEPLOY_SECURITY.md) (security contract + COLD
rootfs surgery details) and the [`README.md`](../README.md) (day-to-day
use). Read this doc when you need to answer:

- *Why does the Pi rename its hotspot to `Astromech_Control_3A2B` after a
  few minutes?*
- *Where do master→slave SSH keys come from? Did I copy them?*
- *Why does `wlan1` already know my home WiFi password if I never typed
  it on the Pi?*
- *What is `/boot/firmware/astromech_role.json` and who reads it?*
- *Why is my admin password different on each robot?*
- *What if I want to use this repo without the C# Imager — does it still
  work?*
- *I'm writing a new Imager feature — what fields must I touch on the
  boot partition for AstromechOS to pick them up?*

---

## ⚡ Quick reference — Imager dev checklist

If you're building or extending the AstroMechOS_Imager, **every flashed
SD card MUST end up with these files on its FAT32 boot partition**
(`/boot/` on Bullseye, `/boot/firmware/` on Bookworm+). Order matters —
the trigger marker is written **LAST** so a half-baked bundle never
fires firstboot prematurely.

| # | File on `/boot/…` | Role | Mandatory? | AstromechOS consumer (file:line) |
|---|---|---|---|---|
| 1 | `astromech_secrets/` *(directory)* | container, chmod 0700 conceptually | **yes** | `firstboot_setup.sh:79` (`SECRETS_DIR`) |
| 2 | `astromech_secrets/init_config.json` | `{role, hostname, imager_version, flashed_at}` | **yes** | `firstboot_setup.sh:160-220` (parses `role` + `hostname`) |
| 3 | `astromech_secrets/authorized_keys` | OpenSSH pubkeys, one per line. **Slave's copy must contain the Master's pub** (or master→slave SSH fails post-boot) | **yes** | `firstboot_setup.sh:124-144` (atomic append + dedupe → `~/.ssh/authorized_keys`, chmod 0600) |
| 4 | `astromech_secrets/id_ed25519` | OpenSSH PEM private key, no passphrase, comment `astromech-master@imager` | **yes, MASTER only** | `firstboot_setup.sh:147-158` (cp → `~/.ssh/id_ed25519`, chmod 0600) |
| 5 | `astromech_secrets/id_ed25519.pub` | Public counterpart of #4 | **yes, MASTER only** | `firstboot_setup.sh:147-158` (cp → `~/.ssh/id_ed25519.pub`, chmod 0644) |
| 6 | `astromech_init.cfg` *(INI)* | Bootstrap config — see schema below | **yes** | `lib_config.sh::cfg_get` (every section of `firstboot_setup.sh`) |
| 7 | `hw_layout.json` | Per-side I2C HAT layout `{master.hats:[…], slave.hats:[…]}` | optional | `firstboot_setup.sh:254-262` (cp → `master/config/hw_layout.json` or `slave/config/`) |
| 8 | `astromech_wlan.conf` | Shell-sourceable `SSID=…` + `PSK=…` for wlan1 home WiFi | optional | `astromech_wlan_setup.sh` (separate systemd unit, runs post-firstboot, shreds on success) |
| 9 | `astromech_role.json` | `{role, project, version}` — identity marker | optional today, will be mandatory once the Imager `image_validator.py` pre-flash check ships | future Imager-side validator + future runtime tooling |
| 10 | **`ASTROMECH_FIRSTBOOT_READY` *(WRITE LAST — atomicity)*** | Empty trigger file | **yes** | `astromech-firstboot.service` `ConditionPathExists` |

**`astromech_init.cfg` schema** (INI format, parsed by
`lib_config.sh::cfg_get section key default`):

```ini
[system]
user      = <UID-1000 username posted by COLD rootfs surgery>   ; mandatory
hostname  = <astromech-master | astromech-slave-XXXX>          ; mandatory

[hotspot]                  ; optional — drives §4.7 hotspot bootstrap → handover
ssid      = <bootstrap SSID, same on both Pis>
password  = <WPA-PSK ≥8 chars>

[home_wifi]                ; optional — alt source for wlan1 creds when
ssid      = <home WiFi SSID>           ; astromech_wlan.conf is absent
password  = <WPA-PSK>

[admin]                    ; optional, MASTER only — Flask UI password
password  = <plaintext, persisted to local.cfg [admin] password>

[github]                   ; optional — DNA-validated repo URL switch
repo_url  = https://github.com/<fork>/AstromechOS.git
branch    = main           ; defaults to "main" if absent

[slave]                    ; optional — overrides default mDNS hostname
host      = astromech-slave.local
user      = <SSH user on slave, defaults to [system] user>
```

**Validation** (Imager-side `_self_validate()`,
[`customization.py:164-211`](../../AstroMechOS_Imager/astromechos_imager/core/customization.py))
refuses to flash if:
- Master is missing `id_ed25519` / `id_ed25519.pub`
- Slave is missing the Master's pubkey in `authorized_keys`
- Any required `init_config.json` field is missing

→ The Imager bundle is bilateral: an asymmetric pair (master + slave SDs
flashed in the same session) is guaranteed to be able to talk to each
other post-boot. **If you change the schema, update the validator AND
this doc in the same commit.**

The rest of this document explains, section by section, what each item
above **does** once firstboot starts consuming it.

---

## Table of contents

- [1. Two paths to provision a Pi](#1-two-paths-to-provision-a-pi)
- [2. The boot-partition contract (what the Imager writes)](#2-the-boot-partition-contract-what-the-imager-writes)
- [3. The trigger marker and the systemd unit](#3-the-trigger-marker-and-the-systemd-unit)
- [4. Firstboot script lifecycle (6 phases)](#4-firstboot-script-lifecycle-6-phases)
- [5. SSH key bilateral contract (master ↔ slave)](#5-ssh-key-bilateral-contract-master--slave)
- [6. Hotspot bootstrap → per-robot final SSID](#6-hotspot-bootstrap--per-robot-final-ssid)
- [7. Home WiFi on wlan1 (astromech-wlan-setup)](#7-home-wifi-on-wlan1-astromech-wlan-setup)
- [8. Role marker on the boot partition](#8-role-marker-on-the-boot-partition)
- [9. Hardware layout (HAT detection)](#9-hardware-layout-hat-detection)
- [10. Admin password for the Flask UI](#10-admin-password-for-the-flask-ui)
- [11. DNA-validated repo URL switch](#11-dna-validated-repo-url-switch)
- [12. Self-destruct + reboot](#12-self-destruct--reboot)
- [13. Username-agnostic invariant](#13-username-agnostic-invariant)
- [14. Idempotency and failure recovery](#14-idempotency-and-failure-recovery)
- [15. Manual install path (no Imager)](#15-manual-install-path-no-imager)
- [16. Troubleshooting cheat sheet](#16-troubleshooting-cheat-sheet)

---

## 1. Two paths to provision a Pi

There are **two supported paths** to get an AstromechOS Pi from a stock
Raspberry Pi OS image to operational:

| Path | What you do | What firstboot does |
|---|---|---|
| **Imager (Golden Image)** | Run the C# `AstroMechOS_Imager` on a Windows PC, pick role+hostname+hotspot creds, flash SD | Reads `/boot/astromech_secrets/*` + `/boot/astromech_init.cfg`, provisions everything in one shot, reboots into ready state |
| **Manual install** | Flash stock Pi OS, `git clone` repo, `bash scripts/setup_*.sh` interactively | If `/boot/astromech_init.cfg` is absent, every section that needs Imager data is a silent no-op. The operator runs `setup_ssh_keys.sh`, `setup_master_network.sh`, etc. by hand. |

This is the **dual-mode contract** locked-in at `firstboot_setup.sh:305-322`
(comment block). Every section below explains both paths.

---

## 2. The boot-partition contract (what the Imager writes)

The Imager's `FirstbootBundle.write_to(bp, role)`
([`AstroMechOS_Imager/astromechos_imager/core/customization.py:120-211`](../../AstroMechOS_Imager/astromechos_imager/core/customization.py))
writes these files to the FAT32 boot partition **before** flashing. Order
matters — the trigger marker is written **last** so a crashed flash
never leaves a half-baked bundle that fires firstboot prematurely.

| Path on `/boot/` (or `/boot/firmware/`) | Written by | Contents | Consumed by |
|---|---|---|---|
| `astromech_init.cfg` | `customization.py` (INI helper) | `[system] user/hostname` · `[hotspot] ssid/password` · `[github] repo_url/branch` · `[admin] password` · `[home_wifi] ssid/password` | `firstboot_setup.sh` via `lib_config.sh::cfg_get` (all sections) |
| `astromech_secrets/init_config.json` | `customization.py:137-139` | `{role, hostname, imager_version, flashed_at}` | `firstboot_setup.sh:160-220` (parse `role` + `hostname`) |
| `astromech_secrets/authorized_keys` | `customization.py:142-145` via `render_authorized_keys()` | OpenSSH pubkeys, one per line. Slave gets the Master's pub appended automatically. | `firstboot_setup.sh:124-144` (atomic append + dedupe to `~/.ssh/authorized_keys`) |
| `astromech_secrets/id_ed25519` | `customization.py:148` **(MASTER ONLY)** | OpenSSH private key (PEM, ed25519, no passphrase) | `firstboot_setup.sh:147-158` (cp to `~/.ssh/id_ed25519`, chmod 0600) |
| `astromech_secrets/id_ed25519.pub` | `customization.py:149` **(MASTER ONLY)** | Public counterpart with comment `astromech-master@imager` | `firstboot_setup.sh:147-158` (cp, chmod 0644) |
| `hw_layout.json` *(optional)* | `customization.py:154` | `{master.hats: [...], slave.hats: [...]}` — Imager-detected HAT addresses | `firstboot_setup.sh:230-262` (§4.5, wins over runtime scan) |
| `astromech_wlan.conf` *(optional)* | `customization.py:158` | Shell-sourceable: `SSID=…` + `PSK=…` for the home WiFi the operator wants on wlan1 | `astromech_wlan_setup.sh` (separate systemd service, runs after firstboot) |
| `ASTROMECH_FIRSTBOOT_READY` | `customization.py:162` **(WRITTEN LAST)** | Empty file. Trigger marker. | `astromech-firstboot.service` `ConditionPathExists` |

**Self-validation** (`customization.py:164-211` `_self_validate`) runs
before the bundle is sealed. It refuses to flash if:
- Master is missing `id_ed25519` or `id_ed25519.pub`
- Slave is missing the Master's pubkey in `authorized_keys`
- Any required init_config key is missing

So the operator can never produce a bundle that would silently brick a
robot.

**Dual-path** `/boot/` vs `/boot/firmware/`: Raspberry Pi OS Bookworm+
mounts the FAT32 boot partition at `/boot/firmware/`; Bullseye and
older mount it at `/boot/`. Both `firstboot_setup.sh:67-78` and
`astromech_wlan_setup.sh:46-50` detect this with the same pattern:

```bash
BOOT_DIR="/boot"
[ -d "/boot/firmware" ] && BOOT_DIR="/boot/firmware"
```

---

## 3. The trigger marker and the systemd unit

The Imager writes `/boot/ASTROMECH_FIRSTBOOT_READY` (empty file)
**after** all other boot files are flushed to disk. This is the only
trigger that fires `astromech-firstboot.service`. No other state, no
other env var, no other config.

**Service definition**:
[`master/services/astromech-firstboot.service.template`](../master/services/astromech-firstboot.service.template)

```ini
[Unit]
Description=AstromechOS first-boot provisioning (Imager bootstrap)
After=network-online.target
Wants=network-online.target
Before=astromech-master.service astromech-slave.service
ConditionPathExists=|/boot/ASTROMECH_FIRSTBOOT_READY
ConditionPathExists=|/boot/firmware/ASTROMECH_FIRSTBOOT_READY

[Service]
Type=oneshot
User=root
WorkingDirectory=__REPO_PATH__
ExecStart=/bin/bash __REPO_PATH__/scripts/firstboot_setup.sh
TimeoutStartSec=600
RemainAfterExit=yes
StandardOutput=journal+console
StandardError=journal+console
SyslogIdentifier=astromech-firstboot

[Install]
WantedBy=multi-user.target
```

Key properties:

- `User=root` — needed for `/etc/hostname`, `/etc/shadow`, `/var/log`,
  `/boot` writes, and `systemctl disable` at the end
- `Before=astromech-master.service astromech-slave.service` — provisioning
  finishes (and the Pi reboots) before the application services try to
  start, so they never see a half-configured state
- `TimeoutStartSec=600` — 10 min budget covers slow SD cards + first
  package install. Pair-sealing is now event-driven (separate
  `astromech-pair-sealing.path` unit) and does **not** consume any
  firstboot wall-clock budget — see §6.
- `ConditionPathExists=|...` — pipe-prefix = "OR semantics", so the unit
  only fires when the marker actually exists
- `__REPO_PATH__` — placeholder substituted by
  `scripts/lib_config.sh::install_service_template` at install time
  (this is part of the username-agnostic invariant, see §13)
- `After=network-online.target` **ONLY** — must **NEVER** chain
  `After=cloud-final.service` (see anti-recurrence callout below)

The unit `disable`s itself at the end of provisioning
(`firstboot_setup.sh:550`) — even if the trigger marker isn't cleanly
deleted, the service won't try to run again.

> ### ⚠️ Anti-recurrence — do NOT add `After=cloud-final.service`
>
> Commit `3065d6c` (since reverted by **`b8d2838`**, marathon
> 2026-06-02→07) added `After=cloud-final.service` to this unit to fix a
> race with cloud-init's `runcmd`. **It silently broke every Golden
> Image flash for 5 days.** Why: `cloud-final.service` declares
> `After=multi-user.target` on Pi OS Bookworm/Trixie, and this unit
> declares `WantedBy=multi-user.target`. That's a startup cycle.
> systemd resolves cycles by **silently dropping one of the edges** with
> only a `Found ordering cycle on …` message in the journal — the
> dropped edge can be ours, in which case firstboot is removed from the
> boot transaction entirely. Symptom: Pi boots clean, no `Astromech-XXXX`
> AP ever appears, no Flask, no servos.
>
> **Diagnostic**: `journalctl -b -1 -u astromech-firstboot.service` →
> look for `Found ordering cycle on astromech-firstboot.service/start`.
>
> The race with cloud-init's `runcmd` that motivated `3065d6c` was
> solved differently — by moving Imager-side wipes from `runcmd` to
> `bootcmd` (see §2 below). **Rule**: no `After=` clause on this unit
> may introduce a cycle with `multi-user.target`.

> ### ⚠️ Anti-recurrence — Imager uses `bootcmd:`, **NEVER `runcmd:`**
>
> cloud-init exposes two stages where Imager-baked shell can wipe stale
> NM profiles before firstboot stages its own:
>
> | Stage | cloud-init module | Fires at | Default scope |
> |---|---|---|---|
> | `runcmd:` | `cc_scripts_user` | uptime ~22s, in `cloud-config.target` | **per-always** (runs on every boot) |
> | `bootcmd:` | `cc_bootcmd` | uptime ~7s, in `cloud-init-local.service` | per-instance by default |
>
> **Why `runcmd:` is wrong** (marathon 2026-06-02→07 root cause): on
> Boot 1, `runcmd` (~22s) raced firstboot (~24s) and wiped firstboot's
> freshly-created NM profiles. On Boot 2+, `runcmd` re-fired and wiped
> the FINAL per-robot AP that pair-sealing had just installed — every
> reboot reset the robot to the bootstrap SSID.
>
> **The fix** (Imager-side commits `0be1fa7` + `f961378`): (a) marker-
> guard the wipe against re-runs (belt-and-suspenders), (b) move the
> wipe from `runcmd` to `bootcmd`. `bootcmd` runs in
> `cloud-init-local.service` **before NetworkManager is even started**,
> **before** firstboot can be scheduled — no race possible. The marker
> guard stays as belt-and-suspenders against future cloud-init module
> changes.
>
> **Rule**: any Imager-baked shell in `user-data` that mutates network
> state MUST live in `bootcmd:` AND be marker-guarded under
> `/var/lib/astromech/runcmd_done` (or equivalent). `clean_for_imager.sh`
> wipes this marker pre-DD so the wipe fires on the first boot of every
> flashed Pi (see CLAUDE.md §"🏗️ Golden Image build invariants").

---

## 4. Firstboot script lifecycle (6 phases)

[`scripts/firstboot_setup.sh`](../scripts/firstboot_setup.sh) (555 lines)
runs **as root** with `set -u` but **NOT `set -e`** (lines 51-53). This
is deliberate: if a sub-step fails, we want the operator to be able to
SSH in later and finish manually, not get locked out of a brick.

```
┌─────────────────────────────────────────────────────────────────────┐
│ Phase 1 — Trigger marker check (firstboot_setup.sh:66-73)           │
│   Bail if /boot/ASTROMECH_FIRSTBOOT_READY is absent (defensive).    │
├─────────────────────────────────────────────────────────────────────┤
│ Phase 2 — Identify TARGET_USER + TARGET_HOME (lines 85-110)         │
│   capture_user → /boot/astromech_init.cfg [system] user → $SUDO_USER│
│   → logname → fallback 'pi' / 'astromech' / 'astromech' legacy.         │
│   See §13 for the username-agnostic rule.                           │
├─────────────────────────────────────────────────────────────────────┤
│ Phase 3 — SSH key injection (lines 112-158)                         │
│   See §5. ~/.ssh/{authorized_keys, id_ed25519, id_ed25519.pub}      │
│   installed atomically with strict perms.                           │
├─────────────────────────────────────────────────────────────────────┤
│ Phase 4 — Identity (role + hostname)                                │
│   §4.0 (lines 160-228)  init_config.json → ROLE + HOSTNAME,         │
│                          set via hostnamectl, persist to local.cfg  │
│   §4.5 (lines 230-302)  HW layout — Imager override OR scan         │
│   §4.6 (lines 309-322)  Admin password (Master only, see §10)       │
│   §4.7 (lines 376-432)  Bootstrap AP + enable async pair-sealing    │
│                          .path unit (see §6 — event-driven, no      │
│                          synchronous wait loop)                     │
├─────────────────────────────────────────────────────────────────────┤
│ Phase 5 — DNA-validated repo switch (lines 491-518)                 │
│   See §11. Only swaps git origin if the candidate URL passes        │
│   validate_paternity (anchored at OFFICIAL_INITIAL_COMMIT).         │
├─────────────────────────────────────────────────────────────────────┤
│ Phase 6 — Self-destruct + reboot (lines 521-555)                    │
│   See §12. Shred secrets, delete trigger, disable own systemd       │
│   unit, sync, sleep 5, reboot.                                      │
└─────────────────────────────────────────────────────────────────────┘
```

All log output goes to `/var/log/astromech-firstboot.log` AND the
systemd journal (`journalctl -u astromech-firstboot`). `log_ok` / `log_warn`
/ `log_err` helpers tag every line.

---

## 5. SSH key bilateral contract (master ↔ slave)

The Imager generates an ed25519 keypair on the PC
([`AstroMechOS_Imager/astromechos_imager/core/keygen.py:17-35`](../../AstroMechOS_Imager/astromechos_imager/core/keygen.py))
and writes both halves to the master's boot partition. The slave's
`authorized_keys` is pre-populated with the master's public half.

**Resulting topology**:

```
   ┌──────────────────┐       master→slave SSH: passwordless via key
   │     MASTER       │           (used by scripts/update.sh, the
   │ ~/.ssh/          │            hotspot handover, runtime deploys)
   │   authorized_keys│
   │   id_ed25519     │ ────────────────► ┌──────────────────┐
   │   id_ed25519.pub │                   │      SLAVE       │
   └──────────────────┘                   │ ~/.ssh/          │
                                          │   authorized_keys│  ← contains
                                          │   (NO id_ed25519)│    master pub
                                          └──────────────────┘
       slave→master SSH: NOT enabled (intentional — slave is minimal,
       does not push deploys, does not need outbound auth)
```

**Permissions applied** (`firstboot_setup.sh:119-158`):

| Path | Owner | Mode |
|---|---|---|
| `~/.ssh/` | `$TARGET_USER:$TARGET_USER` | `0700` |
| `~/.ssh/authorized_keys` | `$TARGET_USER:$TARGET_USER` | `0600` |
| `~/.ssh/id_ed25519` *(master)* | `$TARGET_USER:$TARGET_USER` | `0600` |
| `~/.ssh/id_ed25519.pub` *(master)* | `$TARGET_USER:$TARGET_USER` | `0644` |

The `authorized_keys` install is **atomic + de-duplicating**: it copies
the current file to a tmp, appends the Imager-supplied keys (stripping
CR/blank lines), runs `awk '!seen[$0]++'` to preserve first-seen order
without duplicates, then `mv` to the final path. So a re-run never
double-adds keys, and an external key the operator already installed
manually is never clobbered.

**Manual install equivalent**:
[`scripts/setup_ssh_keys.sh`](../scripts/setup_ssh_keys.sh) — run from
the Master after `setup_master_network.sh` + `setup_slave_network.sh`
have brought both Pis on the same network. Generates a fresh keypair
if `~/.ssh/id_ed25519` doesn't exist, then `ssh-copy-id`'s the pub to
the Slave (one password prompt). Idempotent — re-running on an
already-paired pair is a no-op + a passwordless connectivity test.

**Runtime use** ([`scripts/update.sh:49-53`](../scripts/update.sh)):

```bash
. "$REPO/scripts/lib_config.sh"
SLAVE_HOST="${SLAVE_HOST:-$(slave_host)}"
SLAVE_USER="${SLAVE_USER:-$(slave_user)}"
SLAVE="$SLAVE_USER@$SLAVE_HOST"
SSH="ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10"
```

No `IdentityFile=` override → SSH uses `~/.ssh/id_ed25519` by default.
Zero password prompt.

---

## 6. Hotspot bootstrap → per-robot final SSID *(event-driven)*

This is the section that explains the *"my Pi renamed its hotspot to
`Astromech-3A2B`"* mystery.

**Goal**: each shipped robot gets a **unique hotspot SSID** so several
AstromechOS robots at the same convention don't collide on the same
network name.

> **Architecture rewrite — commit `9cc150b` (2026-06-05).** Previous
> builds had a **5-minute synchronous wait loop** inside
> `firstboot_setup.sh` that polled `ping + ssh BatchMode=yes` against the
> Slave and "gave up" if it didn't respond in time. With cloud-init
> race, Pi-clock drift, and dnsmasq settling, the Slave routinely joined
> just **after** the 5-min window — leaving the Master stuck on the
> bootstrap SSID and the operator forced to finish pairing manually via
> the Flask UI. **That loop is gone.** Pair-sealing is now a persistent,
> event-driven systemd .path unit that fires whenever a DHCP lease lands
> on the Master — seconds, minutes, or hours after firstboot completed.

**The new dance** (`firstboot_setup.sh:376-432`, §4.7, +
[`scripts/astromech_pair_sealing.sh`](../scripts/astromech_pair_sealing.sh)):

```
┌── Phase 1 — firstboot (Master) ─────────────────────────────────────┐
│                                                                     │
│ 1. Read BOOT_SSID + BOOT_PSK from /boot/astromech_init.cfg          │
│    [hotspot] section (Imager-baked, same on both Pis)               │
│                                                                     │
│ 2. Bring up bootstrap AP on wlan0 via                               │
│    bash scripts/setup_master_network.sh --non-interactive           │
│         --ssid $BOOT_SSID --psk $BOOT_PSK                           │
│                                                                     │
│ 3. Enable the persistent pair-sealing path unit:                    │
│    systemctl enable --now astromech-pair-sealing.path               │
│                                                                     │
│ 4. Exit. firstboot is DONE. NO synchronous wait. No 5-min budget.   │
│    Master is on bootstrap SSID, ready to host the Slave WHENEVER    │
│    the Slave shows up.                                              │
└─────────────────────────────────────────────────────────────────────┘

┌── Phase 1 — firstboot (Slave) ──────────────────────────────────────┐
│                                                                     │
│ 1. Read BOOT_SSID + BOOT_PSK from /boot/astromech_init.cfg          │
│                                                                     │
│ 2. Join bootstrap AP on wlan0 via                                   │
│    bash scripts/setup_slave_network.sh --non-interactive            │
│         --ssid $BOOT_SSID --psk $BOOT_PSK                           │
│                                                                     │
│ 3. Exit. The Master will rewrite our stored profile via SSH after   │
│    we get a DHCP lease — we'll auto-reconnect when it flips its AP. │
└─────────────────────────────────────────────────────────────────────┘

┌── Phase 2 — async pair-sealing (Master, event-driven) ──────────────┐
│                                                                     │
│ astromech-pair-sealing.path                                         │
│   ┃                                                                 │
│   ┃ Watches /var/lib/misc/dnsmasq.leases (PathChanged +             │
│   ┃ PathExistsGlob). Fires astromech-pair-sealing.service on        │
│   ┃ every lease change. ConditionPathExists=!/var/lib/astromech/    │
│   ┃ pair_sealed → once sealed, the .path stops triggering.          │
│   ┃ TriggerLimitIntervalSec=30 / TriggerLimitBurst=5 protects       │
│   ┃ against dnsmasq churn during boot.                              │
│   ▼                                                                 │
│ astromech-pair-sealing.service                                      │
│   ┃                                                                 │
│   ┃ Runs scripts/astromech_pair_sealing.sh as root, oneshot.        │
│   ┃ SuccessExitStatus=0 2 → exit 2 ("Slave not reachable yet")      │
│   ┃ is NOT a failure; the .path re-fires on the next lease.         │
│   ▼                                                                 │
│ scripts/astromech_pair_sealing.sh:                                  │
│   1. Re-check the marker (idempotent — no-op if already sealed).    │
│   2. Probe the Slave: ping -c 1 + ssh -o BatchMode=yes 'true'.      │
│      If unreachable → exit 2, .path will retry on next lease event. │
│   3. Generate the FINAL per-robot SSID via                          │
│      bash scripts/gen_hotspot_ssid.sh                               │
│      → Astromech-XXXX (4 hex from /proc/cpuinfo serial, fallback    │
│         wlan0 MAC, fallback random)                                 │
│   4. Push FINAL creds to the Slave FIRST over SSH+nmcli:            │
│        sudo -n nmcli connection modify <astromech-master-hotspot>   │
│             802-11-wireless.ssid '$FINAL_SSID'                      │
│             wifi-sec.psk '$FINAL_PSK'                               │
│      nmcli modify rewrites the stored profile WITHOUT dropping the  │
│      live connection — the Slave only switches when the Master flips│
│   5. Flip the Master's own AP to FINAL_SSID:                        │
│        nmcli connection modify astromech-hotspot ... && up          │
│      The Slave's NetworkManager auto-reconnects within seconds.     │
│   6. Persist FINAL creds to local.cfg [hotspot] for the Flask UI    │
│      to display + future deploys to use.                            │
│   7. Write /var/lib/astromech/pair_sealed → the .path unit will     │
│      never re-fire on this Pi.                                      │
└─────────────────────────────────────────────────────────────────────┘
```

**[`scripts/gen_hotspot_ssid.sh`](../scripts/gen_hotspot_ssid.sh)** — the
suffix generator:

```bash
# Source order: Pi serial (/proc/cpuinfo) → wlan0 MAC → random (4 hex).
# Output: <base>-<XXXX> with XXXX uppercase hex.
#
# Pipeline endings with `|| true` are CRITICAL — without them,
# `set -euo pipefail` would abort BEFORE the fallbacks on a grep
# no-match (Pi 5 / non-Pi without "Serial" line in /proc/cpuinfo).
# That bug would collapse every such robot to the bare base SSID
# (fixed SSID = collision again, defeats the whole point).
```

**Manual install equivalent (Path B)**: skip §4.7 entirely. The operator
runs `scripts/setup_master_network.sh` interactively, picks their own
SSID + PSK, runs `scripts/setup_slave_network.sh` on the Slave with the
same creds. No automatic per-robot rename, no pair-sealing service
enabled — Path B operators name their own hotspot at install time.

**Failure mode — Slave never shows up**: the `.path` unit stays armed
indefinitely. The Master keeps serving the bootstrap SSID; the Slave can
be powered on **at any later time** (an hour, a day, a week later) and
the handover will happen automatically the moment its DHCP lease lands.
If the operator wants to finish pairing manually (Slave is on a
different network, or the operator wants to pick a non-default SSID),
they can do so any time via the Flask UI → **Settings → Hotspot**. The
Pi is never bricked.

**Re-pairing after a sealed handover** (e.g. operator changed the SSID
in Settings, then re-flashed the Slave): delete
`/var/lib/astromech/pair_sealed`, re-enable `astromech-pair-sealing.path`,
the next Slave DHCP lease fires the dance again.

---

## 7. Home WiFi on wlan1 (astromech-wlan-setup)

**Why a separate service?** A USB WiFi dongle on `wlan1` might not be
plugged in at firstboot time. The Imager image might also predate the
wlan1 patch. So home WiFi provisioning is decoupled from the main
firstboot script.

**Service**: `astromech-wlan-setup.service` (installed by the same
installer that drops `astromech-firstboot.service`). Runs **after**
firstboot has settled.

**Script**: [`scripts/astromech_wlan_setup.sh`](../scripts/astromech_wlan_setup.sh)

**Credential source order** (lines 11-15):

1. `/boot/astromech_wlan.conf` (or `/boot/firmware/...`) — Imager-baked
   shell-sourceable file with `SSID=…` + `PSK=…`. **Shredded after
   successful consumption.**
2. `local.cfg [home_wifi] ssid + password` — persistent fallback, used
   when the operator types creds into the Flask Settings UI later

**Skip conditions** (no-op, always returns 0 so boot is never blocked):

- wlan1 is not plugged in
- NetworkManager profile `astromech-internet` already exists (already
  provisioned on a previous boot)
- Neither source provides creds

**Robustness rules** (line 13 comment block):

- `set -u` is fine, **`set -e` is forbidden** — same idea as firstboot:
  never lock the operator out of a working Pi
- shred-then-rm-fallback when wiping the boot creds file
- All logs to `/var/log/astromech-wlan-setup.log` AND journal

---

## 8. Role marker on the boot partition

**File**: `/boot/firmware/astromech_role.json` (or `/boot/` on Bullseye)

**Content**:

```json
{
  "role": "master",
  "project": "AstromechOS",
  "version": "2.0"
}
```

(or `"role": "slave"` for the Slave Pi)

**Who writes it**:

- **Today (manual)**: the operator (or a paramiko script — we wrote both
  on 2026-05-29). The file is identifies which Pi is which.
- **Going forward (Imager-side)**: the C# `AstroMechOS_Imager` will bake
  this file into the boot partition as part of the bundle. The Imager's
  `image_validator.py` (chantier in progress in the Imager repo) will
  also **inspect** this file in extracted .img files before flashing —
  if the image's role mismatches the user-selected slot, the flash is
  refused (hard block). See
  [`DEPLOY_SECURITY.md` §3](DEPLOY_SECURITY.md#3-the-astromechos-imager-workflow)
  for the validator spec.

**Who reads it**:

- The Imager's pre-flash validator (above)
- Future tooling that wants to detect "is this a Master or a Slave?"
  without scraping the hostname or asking `systemctl is-active`

**Permissions**: `chmod 644`, `chown root:root`. FAT32 doesn't really
store Unix perms, but the chmod is best-effort defense-in-depth.

---

## 9. Hardware layout (HAT detection)

**Goal**: `master/config/hw_layout.json` and `slave/config/hw_layout.json`
contain `{master.hats: [...], slave.hats: [...]}` — the I2C HAT layout
the runtime drivers + Cockpit Hardware Health widget rely on. See
[`UI_PATTERNS.md` § "SERVICES HAT health row"](UI_PATTERNS.md#-topbar--cockpit).

**Order of preference** (`firstboot_setup.sh:230-262`, §4.5):

1. **Imager-provided override** — if `/boot/hw_layout.json` exists, it
   wins. Copy verbatim, no scan. Useful when the operator already
   detected the bus on a known-good Pi and wants to replicate exactly.
2. **Read-only scan** — `python3 scripts/detect_hats.py --output ...
   --role master` probes the I2C bus via a `ReadOnlySMBus` wrapper
   (no write side-effects). Resilient: ignores missing `/dev/i2c-1`,
   missing `smbus2`, permission errors, bus lock by another process.
3. **Silent fallback** — no JSON written. Services boot in **DEGRADED
   mode**: HARDWARE HEALTH widget shows `⚠ DEGRADED — RESCAN`, drivers
   skip HAT-dependent features (servos, lights) but the rest stays up.

**Resilience philosophy** (comment at line 230): the firstboot script
**OBSERVES** (writes hw_layout.json) but never **DECIDES**. Bricking a
robot because one PCA9685 is unresponsive is unacceptable. The robot
boots in degraded mode; the operator fixes the HAT and clicks
**Settings → HATs → Rescan** when they're ready.

---

## 10. Admin password for the Flask UI

The Flask Settings UI requires a password to unlock editing
(`@require_admin` on 85+ endpoints — see
[`CLAUDE.md` §"Safety + Auth"](../CLAUDE.md)). This is **entirely separate
from the Linux SSH password** (memory `admin-password-vs-ssh-separation`).

**Default**: `astro` (was `astropass` on installs flashed before 2026-05-30),
hardcoded as the `fallback=` value in `settings_bp.py::_get_admin_password()`
since `master/config/main.cfg` has no `[admin]` section. Used by the
manual install path when the operator never overrides it. The Cockpit
SYSTEM banner flags **both** defaults as "still on the default — change
it" (`status_bp.py::_DEFAULT_ADMIN_PASSWORDS`), so a legacy Pi on
`astropass` doesn't go un-warned after the rename.

**Imager path** (`firstboot_setup.sh:309-322`, §4.6, master only):

1. Read `[admin] password` from `/boot/astromech_init.cfg`
2. If non-empty: persist to `local.cfg [admin] password` via
   `write_local_cfg` (atomic + chmod 0600)
3. If empty: silent no-op, Flask UI keeps the `main.cfg` default

This lets a fleet deploy (10 robots at a convention) bake a unique
random password per device into each SD card without manual config.
The operator gets the password printed at flash time + can rotate it
later via Settings.

---

## 11. DNA-validated repo URL switch

If the operator's fork of AstromechOS lives at a different GitHub URL,
they want the Pi to track THEIR fork — not the upstream `RickDnamps/...`.

**Mechanism** (`firstboot_setup.sh:491-518`, §5):

1. Read `[github] repo_url` + `[github] branch` from
   `/boot/astromech_init.cfg`
2. If the candidate URL differs from the current `git remote get-url
   origin`:
   1. Run `dna_validate $URL $BRANCH` (defined in `lib_config.sh`).
      This pulls the candidate, walks back to the **initial commit**,
      and checks it matches `OFFICIAL_INITIAL_COMMIT` from
      `shared/git_provenance.py:51` (`5cd8937c...`).
   2. If valid: `git remote set-url origin $URL` + `fetch` + `reset
      --hard origin/$BRANCH`.
   3. If invalid: log `DNA FAIL`, keep the current origin.

This is the paternity check that prevents a malicious URL in
`astromech_init.cfg` from pointing the Pi at attacker-controlled code
on the very first boot.

Full spec + recovery procedure for re-anchoring after a `git filter-repo`
surgery: [`DEPLOY_SECURITY.md` §1](DEPLOY_SECURITY.md#1-the-dna-paternity-check).

---

## 12. Self-destruct + reboot

Last phase, `firstboot_setup.sh:521-555`:

1. **Shred** then `rm -f` every file in `/boot/astromech_secrets/`
   (best-effort — FAT32 doesn't really wipe SD wear-leveled cells, but
   the on-disk bytes are at least unlinked and overwritten by `shred`)
2. `rm -rf /boot/astromech_secrets/` (the parent dir)
3. **Delete the trigger marker LAST** — if any prior step had failed
   catastrophically, the trigger would survive and let the next boot
   retry. Once the trigger is gone, the unit will refuse to re-fire.
4. `systemctl disable astromech-firstboot.service` — belt-and-suspenders;
   even if the trigger sneaks back, the unit won't auto-start
5. `sync` + `sleep 5` + `reboot`

The 5-second sleep lets the systemd journal flush so the operator's
post-mortem (`journalctl -u astromech-firstboot --boot=-1`) is
complete.

**After reboot**, `astromech-master.service` (or `astromech-slave.service`)
starts cleanly because:
- The SSH keys are in place → master can talk to slave
- The hostname is set → mDNS works
- The role + admin password are in `local.cfg`
- The hotspot is on its final SSID
- The git origin tracks the right fork

---

## 13. Username-agnostic invariant

**HARD RULE** locked-in 2026-05-29 (CLAUDE.md §"Code Standard"):
**no code/script/systemd unit in this repo may hardcode the username
`pi`, `astromech`, or any other literal**. Each robot the Imager flashes
gets a **different UID-1000 username** posted by the COLD rootfs
surgery (see [`DEPLOY_SECURITY.md` §3](DEPLOY_SECURITY.md#3-the-astromechos-imager-workflow)).

**The waterfall** (`firstboot_setup.sh:88-110`, `lib_config.sh::capture_user`):

```
1. /boot/astromech_init.cfg [system] user         (Imager-baked)
2. $SUDO_USER                                      (if firstboot ran via sudo)
3. logname                                         (process-effective user)
4. fallback: try 'pi', 'astromech', 'astromech' in order
5. abort with log_err if none of those exist
```

Sets `TARGET_USER` + `TARGET_HOME` (export). Every line that writes to
the operator's home, owns a file, or substitutes `User=` in a systemd
template uses these variables — never a literal.

**Pre-commit checklist** (CLAUDE.md §"Code Standard"):

```bash
grep -rn 'astromech@\|chown astromech\|/home/astromech\|User=astromech' <modified files>
```

Only acceptable hits: (a) docstrings/comments describing historical
context, (b) **last-resort fallback waterfalls** in `lib_config.sh:120`
and a handful of other gated locations. Every other hit is a
**username-agnostic regression** that must be fixed before commit.

systemd unit templates substitute `__USER__` / `__REPO_PATH__` /
`__UID__` / `__HOME__` placeholders at install time via
`install_service_template` (`lib_config.sh:165`).

---

## 14. Idempotency and failure recovery

The script is designed to **never brick the robot**. Every section is:

- **Guarded** — checks `[ -f $f ]` before reading, `[ -n $var ]` before
  using, etc.
- **Idempotent** — safe to re-run. Re-installing a key that's already
  in `authorized_keys` is a no-op (dedupe). Re-setting an already-set
  hostname is a no-op.
- **Non-aborting** — `set -e` is **forbidden** (lines 51-53). A
  sub-step failure logs `log_err` and the script keeps going.
- **Trigger-gated** — the marker is deleted **last** so a crashed run
  re-fires on the next boot. After the trigger is deleted, the systemd
  unit is `disable`d so it won't auto-fire even if the marker somehow
  reappears.

**Recovery scenarios**:

| Symptom | Diagnosis | Fix |
|---|---|---|
| Pi boots but services don't start | `astromech-firstboot.service` failed | `journalctl -u astromech-firstboot --boot=0` and look for `[ERR]` lines |
| `astromech_init.cfg` parsed but a key is missing | Imager bundle incomplete | Re-flash. The Imager's `_self_validate` should have caught this — file a bug |
| Hotspot stuck on bootstrap SSID | Slave hasn't shown up yet (or pair-sealing service refused) | `journalctl -u astromech-pair-sealing` to see why. If Slave is off, power it on — the `.path` unit will fire the moment its DHCP lease lands. If you want to force a manual handover: Flask **Settings → Hotspot**. |
| `git pull` fails after firstboot | Pi tracks the wrong remote / repo URL switch was a DNA fail | `cd ~/astromechos && git remote -v` to confirm, `git remote set-url origin <correct>` |
| `~/.ssh/authorized_keys` missing | `/boot/astromech_secrets/authorized_keys` was absent | Run `ssh-copy-id` from the laptop manually, or re-flash |

**Re-trigger by hand** (if the marker was deleted but you want to
re-run firstboot):

```bash
sudo touch /boot/firmware/ASTROMECH_FIRSTBOOT_READY
sudo systemctl enable astromech-firstboot.service
sudo reboot
```

**Forced manual mode** (skip firstboot entirely): just don't create
the trigger marker. `ConditionPathExists` will prevent the unit from
firing.

---

## 15. Manual install path (no Imager)

This is the path used by developers cloning the repo on an existing Pi:

```bash
# 1. Flash stock Raspberry Pi OS Lite (Bookworm 64-bit) to SD
# 2. Boot, configure SSH + a wired or known WiFi network
# 3. Clone the repo at the operator's home
cd ~
git clone https://github.com/RickDnamps/AstromechOS.git astromechos
cd astromechos
# 4. Run the role-specific installer
bash scripts/setup_master.sh    # or setup_slave.sh on the body Pi
# 5. On the Master after both Pis are on the same network:
bash scripts/setup_ssh_keys.sh
# 6. Configure home WiFi for the wlan1 dongle:
bash scripts/setup_master_network.sh  # interactive
```

`firstboot_setup.sh` will run **once** on the next boot (the installer
creates the service + marker) but every Imager-dependent section is a
silent no-op because `/boot/astromech_init.cfg` doesn't exist. See the
explicit IMAGER_MODE branch at `firstboot_setup.sh:305-322` and the
`cfg_get` fallback defaults everywhere.

The result is identical for the operator: services running, master ↔
slave key-based SSH working, hotspot up. The differences vs the Imager
path:

- **Hostname**: defaults from `main.cfg` (`astromech-master` /
  `astromech-slave`), not Imager-randomized
- **SSH keypair**: generated locally by `setup_ssh_keys.sh`, not
  Imager-baked
- **Admin password**: stays `astro` (or `astropass` on legacy installs, or
  whatever the operator types later in Settings)
- **Hotspot SSID**: whatever the operator typed at the interactive
  prompt, **NOT** auto-renamed to `Astromech_Control_XXXX`
- **Home WiFi**: not pre-configured. The operator types it later in
  Settings → Network.

Both paths support the same runtime behavior. The Imager path is just
*faster + safer* for fleet deploys (10 robots at a convention with
unique creds each).

---

## 16. Troubleshooting cheat sheet

| Question | Answer |
|---|---|
| Where do I look first when firstboot misbehaves? | `journalctl -u astromech-firstboot --boot=0` (everything) or `--boot=-1` (previous boot) |
| Did the trigger fire? | `ls /boot/firmware/ASTROMECH_FIRSTBOOT_READY` (should be **gone** if firstboot ran) |
| Did the Imager actually bake a bundle? | `ls /boot/astromech_init.cfg /boot/astromech_secrets/` (both should be **gone** if firstboot ran; **present** if pre-firstboot or if the script crashed before §6) |
| Is the master→slave SSH key in place? | On the master: `ls ~/.ssh/id_ed25519* && ssh -o BatchMode=yes $(scripts/lib_config.sh; echo "$(slave_user)@$(slave_host)") true && echo OK` |
| What hostname did firstboot set? | `cat /etc/hostname` or `hostnamectl` |
| What's the final hotspot SSID? | `nmcli connection show astromech-hotspot | grep ssid` or check Flask **Settings → Hotspot** |
| Has pair-sealing fired? | `ls /var/lib/astromech/pair_sealed` (present = sealed) and `journalctl -u astromech-pair-sealing --boot=0`. If never fired, check `systemctl status astromech-pair-sealing.path` is active + the Slave has a lease in `/var/lib/misc/dnsmasq.leases`. |
| Does the Pi know which role it is? | `cat /boot/firmware/astromech_role.json` (operator-visible) or `grep role $REPO_PATH/master/config/local.cfg` (firstboot-persisted, master only) |
| How do I re-run firstboot from scratch? | See **§14 — Re-trigger by hand** |
| How do I see what the Imager wrote without booting the Pi? | Mount the SD on the dev PC, look at the FAT32 partition's root |

**Related docs**:

- [`DEPLOY_SECURITY.md`](DEPLOY_SECURITY.md) — security contract,
  COLD rootfs surgery, DNA paternity check, threat model
- [`CLAUDE.md`](../CLAUDE.md) — project-wide conventions, including
  the username-agnostic HARD RULE and SSH safety chain
- [`UI_PATTERNS.md`](UI_PATTERNS.md) — Cockpit Hardware Health row
  (consumer of the `hw_layout.json` from §9)
- `bd memories astromech-deploy-adn-firstboot-chantier-2026-05-28` —
  the chantier that built this whole pipeline
- `bd memories astromech-imager-spec-2026-05-29-corrected-the` — the
  Imager-side COLD surgery spec
