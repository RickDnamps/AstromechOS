# Seed + Working Directories — Implementation Plan (Chantier A)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (recommended here — the migration is a sequenced ops procedure, not parallelizable). Steps use checkbox (`- [ ]`) syntax.

**Goal:** Stop tracking robot runtime state in git so `git pull` is never blocked and operator content survives `git reset --hard`. Ship defaults in `*_default/` seed dirs; the app reads/writes gitignored working dirs.

**Architecture:** Move the currently-tracked sounds/choreos/config into seed dirs (`slave/sounds_default/`, `master/choreographies_default/`, `*.example`); gitignore the working paths the app already uses (`slave/sounds/`, `master/choreographies/`, `slave/config/slave.cfg`, `master/config/choreo_categories.json`). Install/update scripts copy seed→working with `rsync --ignore-existing` (copy-new-only). A one-time backup→pull→restore migration converts the live robot without losing data.

**Tech Stack:** git, bash (update.sh / resync_slave.sh / setup_*.sh), paramiko (migration), rsync.

**Spec:** `docs/superpowers/specs/2026-05-21-seed-and-working-dirs-design.md`

---

## File Structure

- **Move (git mv)**: `slave/sounds/` → `slave/sounds_default/` · `master/choreographies/` → `master/choreographies_default/` · `slave/config/slave.cfg` → `slave/config/slave.cfg.example` · `master/config/choreo_categories.json` → `master/config/choreo_categories.json.example`.
- **Modify**: `.gitignore` (add working paths) · `scripts/update.sh` (seed_to_working + rsync excludes + pull-failure detection) · `scripts/resync_slave.sh` (rsync excludes + seed_to_working on slave) · `scripts/setup_slave.sh` + `scripts/setup_master.sh` (call seed_to_working on first install).
- **App code**: unchanged — working paths are the same the app already uses.

---

## Task 1: Dev-repo restructure (git mv + .example + .gitignore)

**Files:** moves listed above; modify `.gitignore`.

- [ ] **Step 1: Move sounds into the seed dir**

```bash
cd "J:/R2-D2_Build/software"
git mv slave/sounds slave/sounds_default
```
This moves all ~320 tracked `.mp3` + `sounds_index.json` into the seed (one rename, no deletion).

- [ ] **Step 2: Move choreos into the seed dir**

```bash
git mv master/choreographies master/choreographies_default
```
All `.chor` (built-ins + the operator's `my_show*`) go to the seed. **No removal** — this keeps every existing choreo in git (so they stay backed up on GitHub). Curating out personal `my_show*` from the seed is an OPTIONAL later cleanup, not part of this migration (avoids any data-loss risk).

- [ ] **Step 3: Convert the two config files to templates**

```bash
git mv slave/config/slave.cfg slave/config/slave.cfg.example
git mv master/config/choreo_categories.json master/config/choreo_categories.json.example
```

- [ ] **Step 4: Add working paths to `.gitignore`**

Append to `.gitignore` (after the existing `slave/config/servo_angles.json` block):

```gitignore
# ------------------------------------------------------------
# Runtime "working" dirs — robot-local state. The app reads/writes
# here; defaults ship in the *_default/ seed dirs and *.example
# templates, copied in on install (copy-new-only, never overwrites).
# Keeps git pull from ever blocking on operator edits + survives reset.
# ------------------------------------------------------------
slave/sounds/
master/choreographies/
slave/config/slave.cfg
master/config/choreo_categories.json
```

- [ ] **Step 5: Verify the restructure**

```bash
git status --short
git ls-files slave/sounds_default/ | wc -l          # expect ~321 (mp3s + index)
git ls-files master/choreographies_default/ | wc -l # expect ~47
git ls-files slave/config/ master/config/           # expect slave.cfg.example + choreo_categories.json.example (no bare slave.cfg / choreo_categories.json)
git check-ignore slave/sounds master/choreographies slave/config/slave.cfg master/config/choreo_categories.json  # all 4 must print (ignored)
```
Expected: working paths are ignored; seed dirs + `.example` are tracked; nothing deleted.

- [ ] **Step 6: Commit + push**

```bash
git add -A
git commit -m "Refactor: seed + working dirs — untrack runtime state (chantier A)"
git push origin main
```

---

## Task 2: `seed_to_working` helper + create-if-missing config

**Files:** `scripts/update.sh`, `scripts/resync_slave.sh`, `scripts/setup_slave.sh`, `scripts/setup_master.sh`. Test: `scripts/test_seed_to_working.sh`.

- [ ] **Step 1: Write a failing bash test for copy-new-only**

Create `scripts/test_seed_to_working.sh`:

```bash
#!/bin/bash
# Test: seed_to_working copies NEW files only, never overwrites working.
set -e
seed_to_working() {  # $1=seed dir, $2=working dir
    mkdir -p "$2"
    rsync -a --ignore-existing "$1/" "$2/"
}
TMP=$(mktemp -d)
mkdir -p "$TMP/seed" "$TMP/work"
echo "shipped-v1" > "$TMP/seed/a.txt"
echo "shipped-v1" > "$TMP/seed/b.txt"
echo "operator-edit" > "$TMP/work/a.txt"   # operator already changed a.txt
seed_to_working "$TMP/seed" "$TMP/work"
# a.txt must keep the operator's content (not overwritten)
[ "$(cat "$TMP/work/a.txt")" = "operator-edit" ] || { echo "FAIL: a.txt overwritten"; exit 1; }
# b.txt is new → must be copied
[ "$(cat "$TMP/work/b.txt")" = "shipped-v1" ] || { echo "FAIL: b.txt not copied"; exit 1; }
echo "PASS"
rm -rf "$TMP"
```

- [ ] **Step 2: Run it (it passes immediately — it tests the helper inline)**

Run (Git Bash / WSL / on the Pi): `bash scripts/test_seed_to_working.sh`
Expected: `PASS`. (This validates the copy-new semantics we rely on.)

- [ ] **Step 3: Add the helper + calls to `update.sh`**

In `scripts/update.sh`, after the `1c/7` runtime-deps step (~line 179), add a new step:

```bash
# ──────────────────────────────────────────────
# 1d. Populate working dirs from seed (copy-new-only)
# ──────────────────────────────────────────────
step "1d/7" "Seed → working (master)"
seed_to_working() {  # $1=seed, $2=working
    [ -d "$1" ] || return 0
    mkdir -p "$2"
    rsync -a --ignore-existing "$1/" "$2/" 2>/dev/null
}
seed_to_working "$REPO/master/choreographies_default" "$REPO/master/choreographies"
[ -f "$REPO/master/config/choreo_categories.json" ] || \
    cp "$REPO/master/config/choreo_categories.json.example" "$REPO/master/config/choreo_categories.json"
ok "Master working dirs ready"
```

- [ ] **Step 4: Add slave-side seed_to_working to `resync_slave.sh`**

In `scripts/resync_slave.sh`, after the rsync block (post Task 3 edits), before the restart, add (runs the copy ON the slave over SSH):

```bash
# Populate the slave's working dirs from the seed (copy-new-only).
$SSH $SLAVE "mkdir -p $REPO/slave/sounds && rsync -a --ignore-existing $REPO/slave/sounds_default/ $REPO/slave/sounds/ && \
    ([ -f $REPO/slave/config/slave.cfg ] || cp $REPO/slave/config/slave.cfg.example $REPO/slave/config/slave.cfg)" 2>/dev/null \
    && ok "Slave working dirs ready" || warn "Slave seed→working failed"
```

- [ ] **Step 5: Add first-install seed_to_working to setup scripts**

In `scripts/setup_slave.sh` STEP 4 (after `mkdir -p "$REPO_PATH/slave"`, ~line 134) the deploy from the master handles population, so add a comment only (no-op — `deploy.sh --first-install` / `update.sh` runs seed_to_working). In `scripts/setup_master.sh`, add the same `seed_to_working` block as update.sh step 1d so a master-only setup also populates. (If `setup_master.sh` already sources update.sh, skip.)

- [ ] **Step 6: Commit**

```bash
git add scripts/update.sh scripts/resync_slave.sh scripts/setup_slave.sh scripts/setup_master.sh scripts/test_seed_to_working.sh
git commit -m "Feat: seed_to_working copy-new-only on install/update (chantier A)"
```

---

## Task 3: Deploy rsync excludes (don't wipe working sounds)

**Files:** `scripts/update.sh` (~line 197-204), `scripts/resync_slave.sh` (~line 55-59).

- [ ] **Step 1: Update the slave rsync in `update.sh`**

Replace the `slave/` rsync (currently `--exclude='sounds/*.mp3'`) with one that excludes the **whole working dirs** and lets the seed sync normally:

```bash
rsync -az --delete \
    -e "$SSH" \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='sounds/' \
    --exclude='config/slave.cfg' \
    --exclude='vendor/' \
    "$REPO/slave/" "$SLAVE:$REPO/slave/" 2>&1 \
    && ok "slave/ synced (working sounds + slave.cfg preserved)" || fail "rsync slave/ failed"
```
`--exclude='sounds/'` protects the Slave's working `slave/sounds/`; `slave/sounds_default/` (not excluded) syncs the seed. `--exclude='config/slave.cfg'` protects the live slave config.

- [ ] **Step 2: Apply the same excludes in `resync_slave.sh`**

In `scripts/resync_slave.sh` change the `slave/` rsync (line ~55-59) identically:

```bash
rsync -az --delete -e "$SSH" \
    --exclude='__pycache__' --exclude='*.pyc' \
    --exclude='sounds/' --exclude='config/slave.cfg' --exclude='vendor/' \
    "$REPO/slave/" "$SLAVE:$REPO/slave/" 2>&1 \
    && ok "slave/ synced" || fail "rsync slave/ failed"
```

- [ ] **Step 3: Commit**

```bash
git add scripts/update.sh scripts/resync_slave.sh
git commit -m "Fix: deploy rsync excludes working dirs, syncs seed instead (chantier A)"
```

---

## Task 4: Fix `update.sh` git-pull-failure detection

**Files:** `scripts/update.sh` (~line 109-120).

- [ ] **Step 1: Make pull-failure detection catch "Aborting" / non-fast-forward**

Replace the detection block:

```bash
    OUTPUT=$(git pull --ff-only 2>&1)
    if echo "$OUTPUT" | grep -qiE "error|fatal|aborting|would be overwritten|not possible to fast-forward|needs merge"; then
        fail "git pull failed (working tree dirty or non-ff?): $OUTPUT"
        warn "Resolve local changes on the Master, then re-run. Code NOT updated."
    else
        git rev-parse --short HEAD > "$VERSION_FILE"
        if echo "$OUTPUT" | grep -q "Already up to date"; then
            ok "Already up to date — $(cat $VERSION_FILE)"
        else
            ok "Updated → version: $(cat $VERSION_FILE)"
        fi
    fi
```
Now a blocked pull surfaces as an error instead of silently shipping stale code. After chantier A, the working tree won't drift on tracked files, so this should rarely trigger.

- [ ] **Step 2: Commit**

```bash
git add scripts/update.sh
git commit -m "Fix: update.sh detects blocked/aborted git pull (no more silent stale deploy)"
git push origin main
```

---

## Task 5: Live migration (Master + Slave) — **HIGH-RISK, backups first**

**This is an ops procedure, not a code change. Run via paramiko. The robot holds the only live copy of operator content — back up everything before touching git.**

- [ ] **Step 1: Snapshot/backup live working content (Master)**

Via paramiko on the Master (`192.168.2.104`):
```bash
TS=$(date +%Y%m%d_%H%M%S); B=/home/artoo/migration_backup_$TS
mkdir -p $B
cp -a /home/artoo/astromechos/slave/sounds $B/sounds 2>/dev/null
cp -a /home/artoo/astromechos/master/choreographies $B/choreographies 2>/dev/null
cp -a /home/artoo/astromechos/slave/config/slave.cfg $B/ 2>/dev/null
cp -a /home/artoo/astromechos/master/config/choreo_categories.json $B/ 2>/dev/null
echo "backup at $B"; ls -la $B
```

- [ ] **Step 2: Backup the Slave's live sounds (the only full copy of the 4 orphan mp3s)**

Via the master→slave SSH hop:
```bash
ssh artoo@192.168.4.171 "TS=$(date +%Y%m%d_%H%M%S); cp -a /home/artoo/astromechos/slave/sounds /home/artoo/sounds_premigration_$TS && ls /home/artoo/sounds_premigration_$TS/*.mp3 | wc -l"
```
Confirm the count (expect 321).

- [ ] **Step 3: Get the Master's working tree clean for the pull, then pull**

On the Master:
```bash
cd /home/artoo/astromechos
git stash push -u -m migration-pre-A      # -u: also stash untracked (the working dirs become gitignored after pull)
git pull --ff-only origin main            # brings the restructure commit
git rev-parse --short HEAD                 # confirm = the chantier-A HEAD
```
Note: the migration commit moves `slave/sounds`→`slave/sounds_default` etc. and gitignores the working paths. After the pull, the working paths are gitignored. **Do NOT `git stash pop`** for the moved paths — instead restore from the Step 1/2 backups (next step), because the stash references the old tracked paths.

- [ ] **Step 4: Restore live working content into the now-gitignored working dirs**

On the Master:
```bash
cd /home/artoo/astromechos
mkdir -p slave/sounds master/choreographies
rsync -a $B/sounds/ slave/sounds/
rsync -a $B/choreographies/ master/choreographies/
cp -a $B/slave.cfg slave/config/slave.cfg
cp -a $B/choreo_categories.json master/config/choreo_categories.json
# also pull in any NEW seed files (copy-new-only)
rsync -a --ignore-existing master/choreographies_default/ master/choreographies/
rsync -a --ignore-existing slave/sounds_default/ slave/sounds/
git status --short    # MUST be clean (working paths gitignored, no tracked drift)
```
On the Slave: its working `slave/sounds/` was preserved by the rsync excludes (Task 3); a deploy's `seed_to_working` (Task 2) tops up new seed files. Verify in Step 6.

- [ ] **Step 5: Re-run the deploy (now unblocked) to land the new scripts + restart**

```bash
cd /home/artoo/astromechos && bash scripts/update.sh 2>&1 | tail -25
```
Expect `Already up to date` (no block), seed→working steps OK, services active.

- [ ] **Step 6: Verify nothing was lost + pulls no longer block**

- Master `git status --short` → clean (or only legitimately-untracked baks).
- Slave: `ssh artoo@192.168.4.171 "ls /home/artoo/astromechos/slave/sounds/*.mp3 | wc -l"` → 321.
- `curl -s -X POST -H "X-Admin-Pw: deetoo" -d {} http://127.0.0.1:5000/audio/reconcile` (on master) → `{ok:true, total:322, removed:[], added_to_others:[]}` (index consistent, all sounds present).
- Choreos load (`curl -s http://127.0.0.1:5000/choreo/list` count matches working dir).
- A second `git pull` on the master → "Already up to date", **not blocked**.
- Keep `migration_backup_$TS` until the operator confirms all good.

---

## Task 6: Fresh-install simulation (no live robot at risk)

- [ ] **Step 1:** In a throwaway clone, delete the working dirs, run `seed_to_working` (master + simulate slave), confirm working dirs are fully populated from seed (counts match). Confirm `cp -n` creates `slave.cfg` + `choreo_categories.json` from `.example`. This proves a clean reinstall reproduces the full default robot.

---

## Task 7: Security / correctness audit

- [ ] Dispatch a review agent (operator requires it) over the changed scripts: `update.sh`, `resync_slave.sh`, `setup_slave.sh`, `setup_master.sh`, `.gitignore`. Focus: the `--delete` rsync excludes truly protect the Slave's working sounds (no path that could wipe them), no destructive default in `seed_to_working` (only `--ignore-existing` / `cp -n`, never overwrite), the migration restores byte-identical content (count + spot-diff), and the pull-failure detection can't false-negative. Fix findings, re-verify on the robot, document.

---

## Self-Review

- **Spec coverage:** seed/working split (T1) ✓ · `.example` config (T1) ✓ · gitignore working (T1) ✓ · copy-new-only install/update (T2) ✓ · rsync excludes working + sync seed (T3) ✓ · pull-failure detection fix (T4, also closes the filed bug) ✓ · safe live migration backup→pull→restore (T5) ✓ · fresh-install verification (T6) ✓ · audit (T7) ✓.
- **Placeholders:** none — exact commands in every step. The choreo "keeper-list" curation is deliberately deferred (move-all-to-seed is the safe choice; curation is optional, flagged).
- **Consistency:** `seed_to_working` signature (`$1=seed, $2=working`, `rsync -a --ignore-existing`) identical across T2 and T6; working paths (`slave/sounds/`, `master/choreographies/`, `slave/config/slave.cfg`, `master/config/choreo_categories.json`) identical across `.gitignore`, rsync excludes, and migration.
