# Audio Index Auto-Reconciliation + Transactional Upload — Design

> **Beads:** software-8n8
> **Date:** 2026-05-21
> **Status:** Approved (design), pending implementation plan

## Problem

`sounds_index.json` is not reconciled against the sound files that actually
exist on the Slave. Two failure modes result:

1. **Ghost entries** — the index lists a sound whose `.mp3` does not exist on
   the Slave (e.g. a failed upload, a deleted/lost file). Triggering it = silent
   no-op (`mpg123` file-not-found). Operators see a phantom in the UI.
2. **Orphan files** — a `.mp3` exists on the Slave but is in no category, so it
   is invisible/unplayable from the UI.
3. **Non-atomic upload** — `upload_sound` writes the index and returns
   `Saved ✓` *before* the background SFTP transfer to the Slave. A failed
   transfer leaves the index listing a sound the Slave never received. Code
   comment today: *"failures are logged but don't fail the upload"*.

A real incident on 2026-05-21 surfaced 6 ghost entries + 4 orphan files at once.

## Goals

- The index reflects what is **actually playable on the Slave**.
- A failed upload **never** produces a listed-but-missing sound.
- Orphan files are auto-surfaced (made playable) rather than lost.
- No data-loss risk: reconciliation must never wipe a healthy catalog because
  the Slave was momentarily unreachable.

## Non-Goals (YAGNI)

- No periodic background reconciliation loop (on-demand + boot is enough once
  upload/delete are transactional).
- No new Slave-side index authority — the Slave stays a "dumb player" (reuses
  the existing `SIDX:RELOAD` hot-reload). Reconcile lives entirely on the Master.
- No re-categorization UI changes beyond surfacing orphans in `others`.

## Design Decisions (confirmed with operator)

| Decision | Choice |
|---|---|
| Source of truth for *file presence* | **Slave** (it holds + plays the files) |
| Index/categorization authority | **Master** (verifies against Slave via SFTP) |
| Upload reliability | **Transactional/synchronous** — verify on Slave before indexing |
| Orphan handling | Auto-add to category **`others`** (playable immediately) |
| Ghost handling | **Remove** from all categories |
| Reconcile triggers | **On-demand button** + **Master boot** (skip if Slave offline) |

## Architecture

Single principle: **Slave = truth on which files exist; Master = truth on the
index.** Reconciliation reads the Slave's real `*.mp3` set and corrects the
Master index, then pushes it down + `SIDX:RELOAD`.

### Component 1 — `_reconcile_index_with_slave(force=False)` (master/api/audio_bp.py)

Pure-ish orchestration with a testable pure core.

1. SFTP `listdir` of `_SLAVE_SOUNDS` → `present_stems` (basename minus `.mp3`).
2. **Safety guards (non-negotiable):**
   - SFTP error / Slave unreachable → **abort, index untouched**, return
     `{ok: False, error: 'slave unreachable'}`.
   - Listing empty **and** index non-empty and not `force` → **abort + warn**
     (anti-wipe; protects the catalog if the Slave dir is temporarily
     unavailable/misconfigured).
3. **Pure reconcile** `reconcile_index(index, present_stems, others_cat='others')`:
   - `ghosts` = indexed names not in `present_stems` → removed from every category.
   - `orphans` = `present_stems` in no category → appended to `others`
     (category created if absent).
   - Multi-category membership preserved for present files (e.g. `SCREA001` in
     `scream`+`special` stays in both).
   - Recompute the (currently vestigial) top-level `total`.
   - Idempotent: running twice yields the same result.
   - Returns `(new_index, report={removed, added_to_others})`.
4. `_atomic_write_index(new_index)` + refresh in-memory cache (under
   `_audio_state_lock`).
5. SFTP atomic push of the index to the Slave + `reg.uart.send('SIDX','RELOAD')`.
6. Return report `{ok, removed:[...], added_to_others:[...], total:N}`.

### Component 2 — Transactional `upload_sound` rewrite (master/api/audio_bp.py)

New order of operations:

1. Validate (file present, `.mp3`, size 1KB–12MB, sanitize stem, category
   regex, realpath containment) — unchanged gates.
2. Under `_upload_lock`: read index, resolve a unique `final_stem` against disk
   + all categories (existing `_next_available_stem`). **Do not** add to index
   yet. Release lock.
3. Save MP3 to a local staging path on the Master.
4. **SFTP the MP3 to the Slave + verify** the remote file size == local size
   (under `_sftp_lock`). On any failure: remove partial remote file, remove
   local staging, return `{ok: False, error}` (HTTP 502/503) — **index never
   touched**.
5. On verified success: re-acquire `_upload_lock`, re-check the name is still
   free (concurrent upload guard), append `final_stem` to the category, sort,
   `_atomic_write_index`, push index + `SIDX:RELOAD`, return `Saved ✓`.

The HTTP request now blocks for the transfer (~5–30s on WiFi). The frontend
`withSaveFeedback` spinner (Saving… → Saved ✓ / red shake) already supports
this; the response is honest.

### Component 3 — `POST /audio/reconcile` endpoint (admin-gated)

`@require_admin`. Body optional `{force: bool}`. Calls
`_reconcile_index_with_slave(force)`. Returns the report. JSON body guard via
`get_json_object()`.

### Component 4 — Boot reconcile (master/main.py)

After services are up, spawn a daemon thread that attempts one reconcile.
Skips silently (logs) if the Slave is not yet reachable — non-fatal. Catches
the drift from reboots / manual SSH file changes.

### Component 5 — Frontend (static/js/app.js + templates/index.html)

- **"Vérifier les sons"** button in Settings → Audio panel.
- Calls `POST /audio/reconcile` via `api()` (admin header attached), wrapped in
  `withSaveFeedback`.
- Result rendered XSS-safe (`createElement` + `textContent`, **never**
  `innerHTML` with interpolation) as a toast: e.g. *"Retiré 2 fantômes · ajouté
  4 dans others"*.
- Sync `app.js` + `style.css` to `android/app/src/main/assets/` (relative
  paths, edit in place — never overwrite the patched `index.html`).

### Slave

**No changes.** Reuses the existing `SIDX:RELOAD` UART handler +
`AudioDriver` hot-reload (`audio_driver.py`). Verify the handler is registered
during implementation.

## Error Handling

| Failure | Behavior |
|---|---|
| Slave unreachable during reconcile | Abort, index untouched, error returned |
| Empty Slave listing + non-empty index (no force) | Abort + warn (anti-wipe) |
| Upload transfer/verify fails | No index change, partial remote cleaned, real error |
| `sounds_index.json` corrupted | Existing fail-closed behavior preserved |
| Concurrent upload taking same stem | Re-check under lock after transfer |
| `SIDX:RELOAD` send fails | Logged, non-fatal (index already on disk + pushed) |

## Security checklist (CLAUDE.md post-feature audit — to verify after impl)

- **Admin auth**: `/audio/reconcile` + `/audio/upload` require `@require_admin`.
- **Path traversal**: every Slave/remote path built from the `present_stems`
  list or upload stem must pass the strict name regex (`_SOUND_NAME_RE`) +
  realpath containment (`_SOUNDS_DIR_REAL`). SFTP remote paths built only from
  validated stems, never raw listdir names without re-validation.
- **Atomic write**: index via `_atomic_write_index` (tmp+fsync+os.replace+.bak).
- **Locks**: `_upload_lock` for index RMW, `_audio_state_lock` for cache,
  `_sftp_lock` serializing SFTP.
- **XSS**: reconcile report rendered via `createElement`/`textContent`.
- **JSON body guard**: `get_json_object()` / `isinstance(..., dict)`.
- **Listdir hygiene**: ignore non-`.mp3`, ignore names failing `_SOUND_NAME_RE`
  (don't index a maliciously-named remote file).

## Testing

- **Pytest (pure logic)** `reconcile_index(index, present_stems)`:
  ghosts removed; orphans → `others`; multi-category preserved; idempotent;
  empty-set + non-empty index requires force; `total` recomputed.
- **Live on Pi** (after deploy), with **snapshot + restore** of the index
  (never destroy real state — try/finally):
  - reconcile no-op when already consistent (0 removed / 0 added);
  - upload happy path → file on Slave + indexed + playable;
  - upload failure path (point at unreachable Slave / inject) → index untouched
    + error returned;
  - reconcile after manually planting an orphan file → lands in `others`.
- `node --check master/static/js/app.js` before commit.

## Rollout

Commit + push + SSH deploy (`scripts/update.sh` via paramiko) per CLAUDE.md.
Then dedicated security audit (review agent) over the changed files.
