# Seed + Working Directories — Untrack Runtime State from Git

> **Date:** 2026-05-21
> **Status:** Approved (design), pending implementation plan
> **Related:** follow-up to the audio-index reconciliation work (software-8n8)

## Problem

The running application writes files **inside its own git checkout** at runtime —
and several of those files are **tracked in git**. So operator actions in the web
UI create local modifications on the Master/Slave that:

1. **Block `git pull`** (`Please commit your changes… Aborting`). `update.sh` then
   silently ships the *old* code (it greps for "error/fatal", not "Aborting").
2. **Risk data loss** — a `git reset --hard` (used during repo recovery) reverts
   these tracked files, wiping operator edits. This already destroyed choreo
   labels (2026-05-14) and is the same class as the permanently-lost sounds.

Currently tracked but actually runtime state:
- `master/choreographies/*.chor` — **mixed**: shipped default animations
  (`dance`, `cantina`, `scan`…) **and** operator creations (`my_show*`).
- `slave/sounds/*.mp3` (~320) + `slave/sounds/sounds_index.json`.
- `master/config/choreo_categories.json`, `slave/config/slave.cfg`.

The project already solved this for a few files (`local.cfg` → `local.cfg.example`
+ gitignored; `dome_angles.json`/`servo_angles.json`/`shortcuts.json`/`bt_config.json`
gitignored). This spec applies the same principle uniformly.

## Goals

- Git tracks **only shipped content** (read-only seed). The robot's mutable state
  lives in **gitignored working dirs**.
- Pulls are never blocked by runtime drift.
- Operator uploads / edits / custom choreos survive `git reset --hard`.
- New shipped content (a future default sound/choreo) still reaches the robot on
  update — **without ever overwriting** the operator's working copy.
- Migrate the **already-tracked** files on the live Master+Slave **without losing**
  any current content.

## Non-Goals

- No change to where the app reads/writes at runtime — the working dirs keep their
  current paths (`slave/sounds/`, `master/choreographies/`,
  `slave/config/slave.cfg`, `master/config/choreo_categories.json`,
  `slave/sounds/sounds_index.json`). This keeps the application code essentially
  unchanged; the work is in git layout + install/deploy scripts.
- MP3s stay distributed via git (in the seed dir) — no separate sound-download
  mechanism. (~69 MB in git is acceptable; it makes `git clone` self-contained.)

## Design — "seed + working copy"

| Content | **Seed** (tracked, read-only, updated by pull) | **Working** (gitignored, app reads/writes) |
|---|---|---|
| Sounds | `slave/sounds_default/` (mp3s + `sounds_index.json`) | `slave/sounds/` |
| Choreos | `master/choreographies_default/` (default `.chor`) | `master/choreographies/` |
| Slave config | `slave/config/slave.cfg.example` | `slave/config/slave.cfg` |
| Choreo categories | `master/config/choreo_categories.json.example` | `master/config/choreo_categories.json` |

**Decisions (confirmed with operator):**
- Seed dir naming: `*_default/`.
- Update policy: **copy new only** — `rsync -a --ignore-existing seed/ working/`.
  New defaults arrive; operator files are never touched. Matches the existing
  `master/sequences/` restore in `update.sh`.

### First install + every update — populate working from seed

A single idempotent helper (used by `setup_slave.sh`, `setup_master.sh`, and
`update.sh`), run for each (seed, working) pair:

```bash
seed_to_working() {  # $1=seed dir, $2=working dir
    mkdir -p "$2"
    rsync -a --ignore-existing "$1/" "$2/"   # copy NEW files only
}
seed_to_working "$REPO/slave/sounds_default"        "$REPO/slave/sounds"          # Slave
seed_to_working "$REPO/master/choreographies_default" "$REPO/master/choreographies" # Master
# Config: create from template if absent (never overwrite)
cp -n "$REPO/slave/config/slave.cfg.example"            "$REPO/slave/config/slave.cfg"
cp -n "$REPO/master/config/choreo_categories.json.example" "$REPO/master/config/choreo_categories.json"
```

- On a **fresh** robot: working dirs are empty → full copy → robot has all defaults.
- On an **existing** robot: working files already exist → `--ignore-existing` /
  `cp -n` copy nothing → operator content untouched, but any **new** seed file is
  added.
- Sounds are copied **on the Slave** (both dirs live under `slave/`, present on the
  Slave after rsync). Choreos are copied **on the Master**.

### Deploy rsync changes (`update.sh`, `resync_slave.sh`)

Today: `rsync -az --delete --exclude='sounds/*.mp3' "$REPO/slave/" "$SLAVE:$REPO/slave/"`.
With the working `slave/sounds/` now gitignored, a `--delete` rsync whose source
lacks it **would wipe the Slave's working sounds**. So:

- **Exclude the working dirs** from the code rsync: `--exclude='sounds/'` (whole
  working dir, not just `*.mp3`). The Slave's `slave/sounds/` is robot-local and
  must never be touched by deploy.
- **Sync the seed** `slave/sounds_default/` normally (it's shipped content).
- After the rsync, run `seed_to_working` on the Slave (copy-new), then push the
  index / `SIDX:RELOAD` as today.

### Application code

Essentially unchanged — the working paths are the same:
- `audio_bp.py` `_INDEX_FILE` / `_SOUNDS_DIR` already point at `slave/sounds/`.
- Slave `AudioDriver` `_SOUNDS_DIR` already `slave/sounds/`.
- The reconcile feature already scans the working `slave/sounds/` — it now also
  naturally surfaces any seed-copied file. No change needed.
- `choreo_bp` already reads/writes `master/choreographies/`. Verify during impl.
- `config_loader` already reads `local.cfg` (creates from `.example`?) — verify and
  reuse the same create-if-missing path for `slave.cfg` / `choreo_categories.json`,
  or do it in the install/update scripts (preferred — keeps app startup simple).

### .gitignore additions

```
slave/sounds/
master/choreographies/
slave/config/slave.cfg
master/config/choreo_categories.json
slave/sounds/sounds_index.json   # (covered by slave/sounds/ above)
```
Keep tracked: `*_default/`, `*.example`, `main.cfg`, `servo_list.cfg`.

## Migration (the delicate part — must lose nothing on the live robot)

### Dev repo (this PC)
1. `git mv slave/sounds slave/sounds_default` (moves the 320 tracked mp3s +
   `sounds_index.json` into the seed).
2. `git mv master/choreographies master/choreographies_default`, then **split**:
   move the operator-created `.chor` (e.g. `my_show*`) back out of the seed —
   the seed should contain only genuine shipped defaults. (Decide the keeper list
   during impl; obvious tests like `my_show234234`, `__preview__` are dropped.)
3. `git mv slave/config/slave.cfg slave/config/slave.cfg.example`.
4. `git mv master/config/choreo_categories.json master/config/choreo_categories.json.example`.
5. Add the working paths to `.gitignore`.
6. Commit + push.

### Live Master + Slave (via deploy, must preserve current working content)
The robot's working dirs currently hold live content in **tracked** files. When the
migration commit (which `git mv`s them away) is pulled, git would try to move/delete
the operator's modified files → conflict / loss. Handle exactly like `update.sh`
already does for angle files:

1. **Backup** the live working content first (`slave/sounds/`, `master/choreographies/`,
   `slave.cfg`, `choreo_categories.json`, `sounds_index.json`) to `/home/artoo/*_backup`.
2. Get the working tree clean for the pull: since these paths become **gitignored**
   after the migration commit, the safe sequence is `git stash` the live drift →
   `git pull` → the working files are now untracked/gitignored → restore the backup
   into the (now gitignored) working dirs.
3. Verify the working dirs still hold the exact pre-migration content (count mp3s,
   choreos; diff configs), and that `git status` is clean (no tracked drift) so
   future pulls never block.

This is a **one-time** migration; afterward the working dirs are gitignored and the
problem cannot recur.

## Risks & safety

- **Data loss during migration** — mitigated by backup-first + restore + verify, and
  the robot is in dev (not in service). Never run `git clean -x` (would wipe the new
  gitignored working dirs).
- **rsync `--delete` wiping working sounds** — mitigated by excluding `sounds/`.
- **Disk** — seed + working duplicates ~69 MB on the Slave; 51 GB free. Fine.
- **`git reset --hard` after migration** — only reverts tracked (seed) files; working
  dirs (gitignored) are untouched. This is the whole point.

## Testing

- **Fresh-install simulation** (in a temp dir / second checkout): empty working →
  `seed_to_working` populates fully → counts match seed.
- **Existing-robot simulation**: working pre-populated with an extra "user" file →
  `seed_to_working` adds only a newly-introduced seed file, leaves the user file +
  all existing files untouched.
- **Deploy rsync**: confirm `slave/sounds/` on the Slave is untouched by a deploy
  (plant a marker file, deploy, marker still there) and the seed syncs.
- **Live migration**: backup → migrate → verify mp3/choreo counts + config contents
  identical pre/post, `git status` clean, a subsequent `git pull` is not blocked.
- **Post-migration `git reset --hard` drill** (on a throwaway checkout): working dirs
  survive.

## Rollout
Migration commit + push from the dev PC. Deploy with the backup/restore migration
step. Then a normal deploy must pull cleanly with no working-tree drift. Update the
CLAUDE.md architecture notes + a bd memory. Post-feature security/correctness review
of the script changes (path handling, rsync excludes, no destructive defaults).
