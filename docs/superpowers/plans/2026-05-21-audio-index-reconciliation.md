# Audio Index Auto-Reconciliation + Transactional Upload — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `sounds_index.json` self-healing against the Slave's actual `.mp3` files, and make uploads transactional so a failed transfer never leaves a phantom index entry.

**Architecture:** Master stays authoritative for the index; the Slave is the truth on which files exist. A pure `reconcile_index()` function (dependency-free, unit-tested) corrects the index given the Slave's real file set. Orchestration in `audio_bp.py` SFTP-lists the Slave, applies the pure reconcile, persists atomically, pushes to the Slave + `SIDX:RELOAD`. Upload is reworked to verify the file on the Slave **before** indexing.

**Tech Stack:** Python 3 / Flask blueprint, paramiko SFTP, pytest, vanilla JS frontend.

**Spec:** `docs/superpowers/specs/2026-05-21-audio-index-reconciliation-design.md` · **Beads:** software-8n8

---

## File Structure

- **Create** `master/api/audio_reconcile.py` — pure reconcile logic, no I/O / Flask / paramiko. Unit-testable in isolation.
- **Create** `scripts/test_audio_reconcile.py` — pytest for the pure logic.
- **Modify** `master/api/audio_bp.py` — add `_list_slave_sound_stems`, `_reconcile_index_with_slave`, `POST /audio/reconcile`; rewrite `upload_sound` to be transactional (add `_sftp_put_sound_verified`).
- **Modify** `master/flask_app.py:115-127` — add a boot-time reconcile daemon thread next to the existing `cleanup_orphan_tmp_files` thread.
- **Modify** `master/static/js/app.js` + `master/templates/index.html` — "Vérifier les sons" button + XSS-safe report toast.
- **Sync** `android/app/src/main/assets/js/app.js` + `css/style.css` (edit in place; never overwrite the patched `index.html`).

---

## Task 1: Pure reconcile core (TDD)

**Files:**
- Create: `master/api/audio_reconcile.py`
- Test: `scripts/test_audio_reconcile.py`

- [ ] **Step 1: Write the failing tests**

```python
# scripts/test_audio_reconcile.py
"""Unit tests for the pure audio-index reconciliation logic."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from master.api.audio_reconcile import reconcile_index, should_abort_reconcile


def test_removes_ghost_entries():
    idx = {'categories': {'happy': ['A', 'GHOST'], 'sad': ['B']}}
    new, rep = reconcile_index(idx, {'A', 'B'})
    assert 'GHOST' not in new['categories']['happy']
    assert new['categories']['happy'] == ['A']
    assert rep['removed'] == ['GHOST']


def test_adds_orphans_to_others():
    idx = {'categories': {'happy': ['A']}}
    new, rep = reconcile_index(idx, {'A', 'ORPHAN1', 'ORPHAN2'})
    assert new['categories']['others'] == ['ORPHAN1', 'ORPHAN2']
    assert rep['added_to_others'] == ['ORPHAN1', 'ORPHAN2']


def test_preserves_multicategory_membership():
    idx = {'categories': {'scream': ['S1'], 'special': ['S1']}}
    new, _ = reconcile_index(idx, {'S1'})
    assert new['categories']['scream'] == ['S1']
    assert new['categories']['special'] == ['S1']


def test_no_change_when_consistent():
    idx = {'categories': {'happy': ['A', 'B']}}
    new, rep = reconcile_index(idx, {'A', 'B'})
    assert rep['removed'] == [] and rep['added_to_others'] == []


def test_idempotent():
    idx = {'categories': {'happy': ['A', 'GHOST']}}
    once, _ = reconcile_index(idx, {'A', 'NEW'})
    twice, rep2 = reconcile_index(once, {'A', 'NEW'})
    assert once == twice
    assert rep2['removed'] == [] and rep2['added_to_others'] == []


def test_recomputes_total():
    idx = {'categories': {'happy': ['A'], 'sad': ['B', 'C']}, 'total': 999}
    new, _ = reconcile_index(idx, {'A', 'B', 'C'})
    assert new['total'] == 3


def test_does_not_mutate_input():
    idx = {'categories': {'happy': ['A', 'GHOST']}}
    reconcile_index(idx, {'A'})
    assert idx['categories']['happy'] == ['A', 'GHOST']


def test_handles_non_list_category():
    idx = {'categories': {'happy': None}}
    new, _ = reconcile_index(idx, {'A'})
    assert new['categories']['others'] == ['A']


def test_abort_guard_empty_files_nonempty_index():
    idx = {'categories': {'happy': ['A']}}
    assert should_abort_reconcile(set(), idx, force=False) is True
    assert should_abort_reconcile(set(), idx, force=True) is False
    assert should_abort_reconcile({'A'}, idx, force=False) is False
    assert should_abort_reconcile(set(), {'categories': {}}, force=False) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest scripts/test_audio_reconcile.py -v`
Expected: FAIL — `ModuleNotFoundError: master.api.audio_reconcile`

- [ ] **Step 3: Implement the pure module**

```python
# master/api/audio_reconcile.py
"""Pure reconciliation logic for sounds_index.json against the set of .mp3
stems that actually exist on the Slave. No I/O, no Flask, no paramiko — kept
dependency-free so it is unit-testable in isolation.

A 'stem' is a filename without its .mp3 extension. Index shape:
{'categories': {category_name: [stem, ...]}, 'total': int}.
"""
from __future__ import annotations
import copy


def reconcile_index(index: dict, present_stems, others_cat: str = 'others'):
    """Return (new_index, report) reconciling `index` against `present_stems`.

    - Ghosts (indexed stem with no file) removed from every category.
    - Orphans (file with no index entry) appended to `others_cat`, sorted.
    - Multi-category membership preserved for present stems.
    - Top-level 'total' recomputed = number of (category, stem) pairs.
    - Idempotent. Does not mutate `index`.
    """
    present = set(present_stems)
    new_index = copy.deepcopy(index) if isinstance(index, dict) else {}
    cats = new_index.setdefault('categories', {})

    removed_set = set()
    for cat_name, stems in list(cats.items()):
        if not isinstance(stems, list):
            cats[cat_name] = []
            continue
        kept = []
        for s in stems:
            if s in present:
                kept.append(s)
            else:
                removed_set.add(s)
        cats[cat_name] = kept

    indexed = {s for stems in cats.values() for s in stems}
    orphans = sorted(present - indexed)
    if orphans:
        bucket = cats.setdefault(others_cat, [])
        for s in orphans:
            if s not in bucket:
                bucket.append(s)
        bucket.sort()

    new_index['total'] = sum(len(v) for v in cats.values())
    return new_index, {'removed': sorted(removed_set), 'added_to_others': orphans}


def should_abort_reconcile(present_stems, index: dict, force: bool = False) -> bool:
    """Anti-wipe guard: refuse to reconcile against an empty file set when the
    index still holds sounds (Slave dir probably temporarily unavailable),
    unless force=True. The orchestration MUST also abort when the SFTP listing
    itself failed — that I/O concern is handled by the caller, not here."""
    if force:
        return False
    has_files = len(set(present_stems)) > 0
    cats = index.get('categories', {}) if isinstance(index, dict) else {}
    has_index = any(isinstance(v, list) and v for v in cats.values())
    return (not has_files) and has_index
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest scripts/test_audio_reconcile.py -v`
Expected: PASS (9 passed)

- [ ] **Step 5: Commit**

```bash
git add master/api/audio_reconcile.py scripts/test_audio_reconcile.py
git commit -m "Feat: pure audio-index reconcile logic + tests (software-8n8)"
```

---

## Task 2: Reconcile orchestration + endpoint

**Files:**
- Modify: `master/api/audio_bp.py` (add helpers + endpoint; import the pure module)

- [ ] **Step 1: Import the pure module** (near the top imports, after line 54)

```python
from master.api.audio_reconcile import reconcile_index, should_abort_reconcile
```

- [ ] **Step 2: Add the Slave listing helper** (place after `cleanup_orphan_tmp_files`, ~line 138)

```python
def _list_slave_sound_stems():
    """SFTP listdir of the Slave's sounds dir → set of validated .mp3 stems.
    Returns None on connection/listing failure — the caller MUST abort then
    (never reconcile against an unknown file set)."""
    try:
        import paramiko
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(**_slave_sftp_creds())
        try:
            sftp = c.open_sftp()
            try:
                entries = sftp.listdir(_SLAVE_SOUNDS)
            finally:
                sftp.close()
        finally:
            c.close()
    except (OSError, IOError) as e:
        log.warning('Reconcile: slave listdir failed: %s', e)
        return None
    except ImportError:
        log.warning('Reconcile: paramiko not installed')
        return None
    stems = set()
    for name in entries:
        if not name.lower().endswith('.mp3'):
            continue
        stem = name[:-4]
        # Security: only accept names matching the strict allow-list. An
        # oddly/maliciously named remote file is ignored, never indexed.
        if _SOUND_NAME_RE.match(stem):
            stems.add(stem)
    return stems
```

- [ ] **Step 3: Add the reconcile orchestrator** (after `_list_slave_sound_stems`)

```python
def _reconcile_index_with_slave(force: bool = False) -> dict:
    """Master-authoritative reconcile: correct the index against the Slave's
    real .mp3 files, persist atomically, push to Slave + SIDX:RELOAD.
    Returns a report dict with 'ok' True/False."""
    present = _list_slave_sound_stems()
    if present is None:
        return {'ok': False, 'error': 'slave unreachable — index unchanged'}

    with _upload_lock:
        try:
            index = json.loads(Path(_INDEX_FILE).read_text(encoding='utf-8'))
        except FileNotFoundError:
            index = {'categories': {}}
        except (OSError, json.JSONDecodeError) as e:
            log.error('Reconcile: index unreadable: %s', e)
            return {'ok': False, 'error': 'sound index corrupted — run scripts/fix_slave_sounds_index.py first'}

        if should_abort_reconcile(present, index, force):
            log.warning('Reconcile aborted: slave reports 0 files but index non-empty (force=true to override)')
            return {'ok': False, 'error': 'slave reports no sound files — aborted to protect catalog'}

        new_index, report = reconcile_index(index, present)
        _atomic_write_index(new_index)
        with _audio_state_lock:
            global _INDEX_CACHE, _INDEX_MTIME
            _INDEX_CACHE = new_index
            try:
                _INDEX_MTIME = os.path.getmtime(_INDEX_FILE)
            except OSError:
                pass

    _sftp_sync_index(new_index)
    try:
        if reg.uart:
            reg.uart.send('SIDX', 'RELOAD')
    except Exception:
        pass

    report['ok'] = True
    report['total'] = new_index.get('total', 0)
    log.info('Reconcile: removed %d ghost(s), added %d orphan(s) to others',
             len(report['removed']), len(report['added_to_others']))
    return report
```

- [ ] **Step 4: Add the endpoint** (place near `create_category`, e.g. after line 1024)

```python
@audio_bp.post('/reconcile')
@require_admin
def reconcile_sounds():
    """Reconcile sounds_index.json against the Slave's actual .mp3 files.
    Body (optional): {"force": bool}. Admin-gated."""
    from master.api._admin_auth import get_json_object
    body = get_json_object()
    force = bool(body.get('force', False)) if isinstance(body, dict) else False
    report = _reconcile_index_with_slave(force=force)
    return jsonify(report), (200 if report.get('ok') else 503)
```

- [ ] **Step 5: Syntax check + commit**

```bash
python -c "import ast; ast.parse(open('master/api/audio_bp.py',encoding='utf-8').read())"
git add master/api/audio_bp.py
git commit -m "Feat: /audio/reconcile endpoint + slave-listing orchestration (software-8n8)"
```

Note: live behavior (real SFTP) is verified in Task 6 — no unit test here (needs a Slave).

---

## Task 3: Transactional upload rewrite

**Files:**
- Modify: `master/api/audio_bp.py` — add `_sftp_put_sound_verified`; rewrite the tail of `upload_sound` (currently lines ~801-854) and remove the background `_sftp_sync_sound` thread for the upload path.

- [ ] **Step 1: Add the verified-put helper** (place near `_sftp_sync_sound`, ~line 1087)

```python
def _sftp_put_sound_verified(local_mp3: str, stem: str) -> bool:
    """Atomically SFTP the MP3 to the Slave and verify the remote size matches
    the local size. Returns True only on verified success. On any failure the
    partial remote file is removed and False is returned. The index is NOT
    touched here — the caller indexes the sound only after this returns True."""
    local_size = os.path.getsize(local_mp3)
    remote = f'{_SLAVE_SOUNDS}/{stem}.mp3'
    with _sftp_lock:
        try:
            import paramiko
            c = paramiko.SSHClient()
            c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c.connect(**_slave_sftp_creds())
            try:
                sftp = c.open_sftp()
                try:
                    _sftp_atomic_put(sftp, remote, local_mp3)
                    remote_size = sftp.stat(remote).st_size
                    if remote_size != local_size:
                        log.warning('Upload verify: size mismatch for %s (local %d, remote %d)',
                                    stem, local_size, remote_size)
                        try:
                            sftp.remove(remote)
                        except IOError:
                            pass
                        return False
                    return True
                finally:
                    sftp.close()
            finally:
                c.close()
        except (OSError, IOError) as e:
            log.warning('Upload SFTP failed for %s: %s', stem, e)
            return False
        except ImportError:
            log.warning('Upload SFTP skipped: paramiko not installed')
            return False
```

- [ ] **Step 2: Rewrite the upload tail.** Replace the block from `# Save the file to disk.` (line ~801) through the `return jsonify({...})` at line ~854 with:

```python
        # Save to a local staging copy first (source for the SFTP transfer).
        os.makedirs(_SOUNDS_DIR, exist_ok=True)
        f.save(dest_path)
        # NOTE: index is NOT mutated yet — only after the Slave confirms.

    # Transfer to the Slave + verify, OUTSIDE _upload_lock (plays are not
    # affected; only other admin upload/delete ops serialize on the lock).
    if not _sftp_put_sound_verified(dest_path, final_stem):
        # Failed transfer: remove the local staging copy, leave the index
        # untouched, return a real error. Nothing phantom is ever listed.
        try:
            if os.path.exists(dest_path):
                os.remove(dest_path)
        except OSError:
            pass
        return jsonify({
            'ok': False,
            'error': 'Transfer to robot failed — sound NOT added (try again)',
        }), 502

    # Verified on the Slave. Now commit to the index + push it.
    with _upload_lock:
        try:
            index = json.loads(Path(_INDEX_FILE).read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            index = {'categories': {}}
        cats = index.setdefault('categories', {})
        sounds = cats.setdefault(category, [])
        _SOUNDS_PER_CAT_MAX = 512
        if final_stem not in sounds:
            if len(sounds) >= _SOUNDS_PER_CAT_MAX:
                return jsonify({
                    'ok': False,
                    'error': f'Category "{category}" full (max {_SOUNDS_PER_CAT_MAX} sounds)',
                }), 400
            sounds.append(final_stem)
            sounds.sort()
        _atomic_write_index(index)
        with _audio_state_lock:
            global _INDEX_CACHE, _INDEX_MTIME
            _INDEX_CACHE = index
            try:
                _INDEX_MTIME = os.path.getmtime(_INDEX_FILE)
            except OSError:
                pass

    # Push the freshly-updated index + hot-reload the Slave's AudioDriver.
    _sftp_sync_index(index)
    try:
        if reg.uart:
            reg.uart.send('SIDX', 'RELOAD')
    except Exception:
        pass

    return jsonify({
        'ok':       True,
        'filename': final_stem,
        'category': category,
        'original': stem,
        'renamed':  final_stem != stem,
    })
```

Notes for the implementer:
- Move the `_SOUNDS_PER_CAT_MAX` capacity check to the post-transfer block (above). The pre-transfer block now only resolves `final_stem` and saves the staging file; it must NOT append to the index.
- The earlier `_next_available_stem` resolution (lines ~792-799) stays under the first `_upload_lock`. Keep it.
- Concurrent upload of the *same* base name by two clients is out of scope (single-operator R2); the post-transfer `if final_stem not in sounds` keeps the index idempotent if it happens.

- [ ] **Step 3: Syntax check + commit**

```bash
python -c "import ast; ast.parse(open('master/api/audio_bp.py',encoding='utf-8').read())"
git add master/api/audio_bp.py
git commit -m "Feat: transactional upload — verify on slave before indexing (software-8n8)"
```

---

## Task 4: Boot-time reconcile

**Files:**
- Modify: `master/flask_app.py` (after the `cleanup_orphan_tmp_files` thread block, ~line 127)

- [ ] **Step 1: Add the boot reconcile thread**

```python
    # Boot reconcile: correct the index against the Slave's real files once
    # at startup (catches drift from reboots / manual file changes). Skips
    # silently if the Slave isn't reachable yet — non-fatal.
    try:
        import threading as _thr_recon
        from master.api.audio_bp import _reconcile_index_with_slave
        def _boot_reconcile():
            rep = _reconcile_index_with_slave()
            if rep.get('ok'):
                log.info("Boot reconcile: removed %d ghost(s), added %d orphan(s)",
                         len(rep.get('removed', [])), len(rep.get('added_to_others', [])))
            else:
                log.info("Boot reconcile skipped: %s", rep.get('error'))
        _thr_recon.Thread(target=_boot_reconcile, name='audio-boot-reconcile', daemon=True).start()
    except Exception:
        log.exception("boot reconcile failed to start")
```

- [ ] **Step 2: Syntax check + commit**

```bash
python -c "import ast; ast.parse(open('master/flask_app.py',encoding='utf-8').read())"
git add master/flask_app.py
git commit -m "Feat: reconcile sounds index at master boot (software-8n8)"
```

---

## Task 5: Frontend button + toast + Android sync

**Files:**
- Modify: `master/templates/index.html` (Settings → Audio panel)
- Modify: `master/static/js/app.js` (handler)
- Sync: `android/app/src/main/assets/js/app.js`

- [ ] **Step 1: Add the button in the Audio settings panel** (find the Audio panel in `index.html`; add inside it). Reuse existing button classes — grep for `btn-` classes already used in Settings before writing.

```html
<button id="btn-reconcile-sounds" class="btn-secondary">Vérifier les sons</button>
<div class="settings-note">Compare l'index aux fichiers réellement présents sur le robot : retire les sons manquants, range les nouveaux dans « others ».</div>
```

- [ ] **Step 2: Add the handler in app.js** (near other Settings→Audio handlers; reuse `withSaveFeedback`, `api`, `showToast`)

```javascript
const _btnReconcile = document.getElementById('btn-reconcile-sounds');
if (_btnReconcile) {
  _btnReconcile.addEventListener('click', () => {
    withSaveFeedback(_btnReconcile, async () => {
      const r = await api('/audio/reconcile', { method: 'POST', body: JSON.stringify({}) });
      const data = await r.json();
      if (!r.ok || !data.ok) throw new Error((data && data.error) || 'Échec');
      const removed = (data.removed || []).length;
      const added = (data.added_to_others || []).length;
      showToast(`Sons vérifiés — ${removed} retiré(s), ${added} ajouté(s) dans others`, 'ok');
      if (typeof loadCategories === 'function') loadCategories();
    });
  });
}
```

Implementer: confirm the exact names of `api`, `withSaveFeedback`, `showToast`, and the category-refresh function by grepping app.js; adapt the calls to match. Render any list of names via `textContent`/`createElement` only — never `innerHTML` with interpolation.

- [ ] **Step 3: Validate JS + sync Android + commit**

```bash
node --check master/static/js/app.js
cp master/static/js/app.js android/app/src/main/assets/js/app.js
git add master/templates/index.html master/static/js/app.js android/app/src/main/assets/js/app.js
git commit -m "Feat: 'Vérifier les sons' reconcile button + report toast (software-8n8)"
```

---

## Task 6: Deploy + live verification (with snapshot/restore)

- [ ] **Step 1: Deploy** via paramiko `scripts/update.sh` (CLAUDE.md deploy pattern).

- [ ] **Step 2: Snapshot the live index** (SFTP read master `slave/sounds/sounds_index.json` → keep bytes in memory for restore in a `try/finally`).

- [ ] **Step 3: Reconcile no-op check** — `POST /audio/reconcile` on a consistent system → expect `removed: [], added_to_others: []`, HTTP 200.

- [ ] **Step 4: Orphan recovery** — SFTP-plant a tiny valid `ZZTEST_RECON.mp3` on the Slave, `POST /audio/reconcile` → expect `ZZTEST_RECON` in `added_to_others` and in category `others`; verify the Slave AudioDriver hot-reloaded (journal `index reloaded`). Then delete the planted file + reconcile → expect it removed. **Restore the original index in `finally`.**

- [ ] **Step 5: Upload failure path** — temporarily point `[deploy] slave_host` at an unreachable IP (or stop the slave SSH), `POST /audio/upload` a small MP3 → expect HTTP 502 + `ok:false`, and confirm the index did NOT gain the entry. Restore config.

- [ ] **Step 6: Upload happy path** — upload a small valid MP3 → expect `ok:true`, file present on the Slave (`sftp.stat`), entry in the index, playable via `/audio/play`.

---

## Task 7: Security audit (REQUIRED — operator-requested)

- [ ] Dispatch a code-review subagent (`superpowers:requesting-code-review` / review agent) scoped to the changed files: `master/api/audio_reconcile.py`, `master/api/audio_bp.py`, `master/flask_app.py`, `master/static/js/app.js`, `master/templates/index.html`. Focus: **path traversal** (remote/local paths built only from `_SOUND_NAME_RE`-validated stems + realpath containment), admin auth on new endpoint, atomic writes, lock discipline (`_upload_lock`/`_audio_state_lock`/`_sftp_lock`), XSS in the new UI, JSON body guard, and the anti-wipe guard. Fix findings, re-deploy, document in the commit + `docs/AUDIT_HISTORY.md`.

---

## Self-Review

- **Spec coverage:** reconcile core (T1) ✓ · ghosts/orphans/others (T1) ✓ · anti-wipe guard (T1+T2) ✓ · slave-unreachable abort (T2) ✓ · endpoint+button trigger (T2,T5) ✓ · boot trigger (T4) ✓ · transactional upload (T3) ✓ · slave unchanged/`SIDX:RELOAD` (T2,T3) ✓ · tests (T1,T6) ✓ · security checklist (T7) ✓.
- **Placeholders:** none — full code in every code step; T5 leaves frontend helper-name confirmation to the implementer (deliberate: those names must be grepped, not guessed).
- **Type/name consistency:** `reconcile_index`, `should_abort_reconcile`, `_list_slave_sound_stems`, `_reconcile_index_with_slave`, `_sftp_put_sound_verified`, `_INDEX_FILE`, `_SLAVE_SOUNDS`, `_sftp_sync_index`, `_atomic_write_index`, `_SOUND_NAME_RE` — used consistently across tasks and match the existing `audio_bp.py` names.
