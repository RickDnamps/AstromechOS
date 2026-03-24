# Sequence Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a visual drag-and-drop sequence editor tab to the R2-D2 web dashboard so users can create, edit, test, and manage `.scr` sequences without touching raw text files.

**Architecture:** Seven independent tasks build on each other in order: backup strategy first (safest), then engine changes, then API, then frontend assets (SortableJS bundle, CSS, HTML tab), then the JS `SequenceEditor` class. Each task is independently testable. The `.scr` file format on disk is never changed — only how it is read and written changes.

**Tech Stack:** Python/Flask (backend), vanilla JS ES2020 class (frontend), SortableJS 1.15.3 (bundled), pytest (Python tests), no build step.

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `scripts/update.sh` | Modify | Backup custom sequences before `git pull`, restore after |
| `master/script_engine.py` | Modify | `_run_file()` method, `script,name` command, `skip_motion` flag, step progress |
| `master/api/script_bp.py` | Modify | New endpoints: get/save/delete/rename; modified: list (is_builtin), running (step progress), run (skip_motion) |
| `master/static/vendor/sortable.min.js` | Create | SortableJS 1.15.3 bundled locally (offline-safe) |
| `master/templates/index.html` | Modify | New ÉDITEUR tab button + tab content panel |
| `master/static/css/style.css` | Modify | Editor-specific styles |
| `master/static/js/app.js` | Modify | New `SequenceEditor` class |
| `tests/test_sequence_editor_engine.py` | Create | Tests for script_engine.py changes |
| `tests/test_sequence_editor_api.py` | Create | Tests for script_bp.py changes |

---

## Task 1: update.sh — Backup Custom Sequences Around git pull

**Files:**
- Modify: `scripts/update.sh`

The backup runs before `git pull` and restores after using `rsync --ignore-existing`. This ensures custom (untracked) sequences survive the update. Built-in (tracked) sequences get updated from git; if git introduces a file with the same name as a custom sequence, the custom version wins.

- [ ] **Step 1: Add backup block before git pull in update.sh**

Open `scripts/update.sh`. Find the `step "1/6" "Git pull"` section. Insert the backup block **before** the `step "1/6"` line:

```bash
# ──────────────────────────────────────────────
# 0. Backup custom sequences avant git pull
# ──────────────────────────────────────────────
SEQUENCES_DIR="$REPO/master/sequences"
SEQUENCES_BACKUP="/home/artoo/sequences_backup"
step "0/6" "Backup séquences custom"
mkdir -p "$SEQUENCES_BACKUP"
if rsync -a "$SEQUENCES_DIR/" "$SEQUENCES_BACKUP/" 2>/dev/null; then
    ok "Séquences sauvegardées → $SEQUENCES_BACKUP"
else
    warn "Backup séquences impossible — dossier inexistant?"
fi
```

Also update the step numbering. Run this sed command from repo root (works on Linux/Git Bash):
```bash
sed -i 's|step "1/6"|step "1/7"|; s|step "2/6"|step "2/7"|; s|step "3/6"|step "3/7"|; s|step "4/6"|step "4/7"|; s|step "5/6"|step "5/7"|; s|step "6/6"|step "6/7"|' scripts/update.sh
```
Verify the renumbering was applied:
```bash
grep 'step "' scripts/update.sh
```
Expected output: lines with `0/6`, `1/7`, `1b/7`, `2/7`, `3/7`, `4/7`, `5/7`, `6/7`.

- [ ] **Step 2: Add restore block after git pull success**

Inside the git pull success block (after `ok "Mis à jour..."` and after `ok "Déjà à jour..."`), add a new step **after** the git pull section and **before** `step "2/7" "Connexion Slave"`:

```bash
# ──────────────────────────────────────────────
# Restore custom sequences after git pull
# ──────────────────────────────────────────────
step "1b/7" "Restauration séquences custom"
if [ -d "$SEQUENCES_BACKUP" ]; then
    # --ignore-existing: git-tracked sequences win; custom sequences preserved
    if rsync -a --ignore-existing "$SEQUENCES_BACKUP/" "$SEQUENCES_DIR/" 2>/dev/null; then
        ok "Séquences custom restaurées (custom wins si conflit nom)"
    else
        warn "Restauration séquences impossible"
    fi
else
    ok "Pas de backup à restaurer"
fi
```

- [ ] **Step 3: Test the backup/restore logic manually (dry-run)**

On dev machine (not Pi), verify the script syntax is valid:
```bash
bash -n scripts/update.sh
```
Expected: no output (no syntax errors).

- [ ] **Step 4: Commit**

```bash
git add scripts/update.sh
git commit -m "Feat: backup custom sequences before git pull in update.sh"
```

---

## Task 2: ScriptEngine Changes — _run_file, script command, skip_motion, step progress

**Files:**
- Modify: `master/script_engine.py`
- Create: `tests/test_sequence_editor_engine.py`

Four separate changes to `script_engine.py`, all in one task because they are tightly coupled (skip_motion and step progress both live in `_ScriptRunner`, `_run_file` is used by the `script` command).

### Changes overview

1. **`_run_file(path, stop_event)`** — extract the step-execution loop from `_ScriptRunner.run()` into a method. `run()` calls `self._run_file(self._path, self._stop_event)`.
2. **`script,name` command** — dispatched inside `_run_file()` before calling `execute_command`. Recursive, inline, blocking.
3. **`skip_motion` flag** — `ScriptEngine.run()` accepts `skip_motion=False`, passes to `_ScriptRunner`, which stores `self._skip_motion`. `execute_command()` accepts `skip_motion=False`. In `_cmd_motion()`: if `skip_motion`, log and return immediately.
4. **Step progress** — `_ScriptRunner` gets `step_index`, `step_total`, `current_cmd`. Count non-comment non-empty lines on load. Update before each `execute_command`. `list_running()` exposes these fields.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_sequence_editor_engine.py`:

```python
"""Tests — ScriptEngine changes for sequence editor."""
import os
import sys
import tempfile
import threading
import time

import pytest

# Add repo root to path so master.* imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from master.script_engine import ScriptEngine


def make_scr(content: str) -> str:
    """Write a temp .scr file and return its path."""
    f = tempfile.NamedTemporaryFile(mode='w', suffix='.scr',
                                    delete=False, encoding='utf-8')
    f.write(content)
    f.close()
    return f.name


# ── skip_motion ──────────────────────────────────────────────────────────────

def test_skip_motion_suppresses_motion_command():
    """motion command is skipped when skip_motion=True."""
    calls = []
    engine = ScriptEngine()
    # Monkey-patch _cmd_motion to track calls
    original = engine._cmd_motion
    engine._cmd_motion = lambda row, **kw: calls.append(row)

    row = ['motion', '0.5', '0.5', '500']
    engine.execute_command(row, skip_motion=True)
    assert calls == [], "motion should be suppressed with skip_motion=True"


def test_skip_motion_false_calls_motion():
    """motion command is NOT skipped when skip_motion=False (default)."""
    called = []

    class FakeVesc:
        def drive(self, l, r): called.append((l, r))
        def stop(self): called.append('stop')

    engine = ScriptEngine(vesc=FakeVesc())
    row = ['motion', '0.3', '-0.3', '0']
    engine.execute_command(row, skip_motion=False)
    assert called != [], "motion should be called when skip_motion=False"


# ── step progress ─────────────────────────────────────────────────────────────

def test_step_progress_tracked():
    """step_index, step_total, current_cmd are updated during execution."""
    scr = make_scr("# comment\nsleep,0.05\nsleep,0.05\n")
    tmp_dir = os.path.dirname(scr)
    scr_name = os.path.splitext(os.path.basename(scr))[0]
    engine = ScriptEngine()
    # Point sequences_dir at the temp dir so run() can find the file by name
    engine.sequences_dir = tmp_dir
    sid = engine.run(scr_name)
    time.sleep(0.02)  # let runner start
    with engine._lock:
        runners = list(engine._running.values())
    if runners:
        runner = runners[0]
        assert runner.step_total == 2
        assert runner.step_index >= 0
    engine.stop_all()
    os.unlink(scr)


# ── script,name sub-sequence ──────────────────────────────────────────────────

def test_script_subseq_executes_inline():
    """script,name command executes another .scr file inline."""
    executed = []

    engine = ScriptEngine()
    original_exec = engine.execute_command

    def tracking_exec(row, stop_event=None, skip_motion=False):
        executed.append(row[0] if row else '')
        original_exec(row, stop_event=stop_event, skip_motion=skip_motion)

    engine.execute_command = tracking_exec

    sub = make_scr("sleep,0.01\n")
    main = make_scr(f"script,{os.path.splitext(os.path.basename(sub))[0]}\n")

    # Inject sequences_dir pointing to temp dir
    engine.sequences_dir = os.path.dirname(sub)

    stop = threading.Event()
    # Import _ScriptRunner directly to test _run_file
    from master.script_engine import _ScriptRunner
    runner = _ScriptRunner(
        script_id=1, name='test', path=main,
        loop=False, engine=engine, on_done=lambda sid: None,
        skip_motion=False,
    )
    runner._run_file(main, stop)

    assert 'sleep' in executed, "sub-sequence sleep command should have been executed"
    os.unlink(sub)
    os.unlink(main)


# ── list_running step progress ────────────────────────────────────────────────

def test_list_running_includes_step_progress():
    """list_running() returns step_index, step_total, current_cmd."""
    scr = make_scr("sleep,0.2\n")
    tmp_dir = os.path.dirname(scr)
    scr_name = os.path.splitext(os.path.basename(scr))[0]
    engine = ScriptEngine()
    engine.sequences_dir = tmp_dir
    sid = engine.run(scr_name)
    time.sleep(0.05)
    running = engine.list_running()
    assert len(running) == 1
    entry = running[0]
    assert 'step_index' in entry
    assert 'step_total' in entry
    assert 'current_cmd' in entry
    engine.stop_all()
    os.unlink(scr)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd J:/R2-D2_Build/software
python -m pytest tests/test_sequence_editor_engine.py -v 2>&1 | head -60
```
Expected: 5 failures — `AttributeError` for `skip_motion`, `step_total`, etc. (not crashes, since `sequences_dir` patching and `_path_override` are no longer used).

- [ ] **Step 3: Implement _run_file refactor in script_engine.py**

In `_ScriptRunner.__init__`, add `skip_motion=False` parameter and store it:
```python
def __init__(self, script_id, name, path, loop, engine, on_done, skip_motion=False):
    ...
    self._skip_motion = skip_motion
    self.step_index  = 0
    self.step_total  = 0
    self.current_cmd = ""
```

Add `_count_steps(path)` helper method on `_ScriptRunner`:
```python
def _count_steps(self, path) -> int:
    """Count non-comment, non-empty lines in a .scr file."""
    count = 0
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                stripped = line.strip()
                if stripped and not stripped.startswith('#'):
                    count += 1
    except Exception:
        pass
    return count
```

Add `_run_file(path, stop_event)` method on `_ScriptRunner`:
```python
def _run_file(self, path, stop_event: threading.Event) -> None:
    """Execute all commands in a .scr file. Respects stop_event."""
    self.step_total = self._count_steps(path)
    self.step_index = 0
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                if stop_event.is_set():
                    return
                row = [c.strip() for c in line.split(',')]
                if not row or not row[0] or row[0].startswith('#'):
                    continue
                # Handle script,name sub-sequence inline
                if row[0].lower() == 'script':
                    if len(row) < 2 or not row[1]:
                        log.warning("script: missing name, skipping")
                        continue
                    sub_name = row[1]
                    sub_path = os.path.join(self._engine.sequences_dir,
                                            f"{sub_name}.scr")
                    if os.path.isfile(sub_path):
                        self._run_file(sub_path, stop_event)
                    else:
                        log.warning(f"script: sub-sequence '{sub_name}' not found, skipping")
                    continue
                # Track step progress
                self.current_cmd = line.strip()
                self.step_index += 1
                self._engine.execute_command(row, stop_event,
                                             skip_motion=self._skip_motion)
    except Exception as e:
        log.error(f"Erreur lecture fichier {path}: {e}")
```

Replace `_ScriptRunner.run()` to call `_run_file`:
```python
def run(self) -> None:
    while not self._stop_event.is_set():
        try:
            self._run_file(self._path, self._stop_event)
        except Exception as e:
            log.error(f"Erreur script {self.name}: {e}")
            break
        if not self._loop:
            break
    self._on_done(self.script_id)
    log.debug(f"Script terminé: {self.name}")
```

- [ ] **Step 4: Add sequences_dir property to ScriptEngine**

`ScriptEngine` currently uses the module-level `SCRIPTS_DIR` constant. Add a property so tests and `_run_file` can reference it:

In `ScriptEngine.__init__`, add:
```python
self.sequences_dir = SCRIPTS_DIR
```

- [ ] **Step 5: Add skip_motion to ScriptEngine.run() and execute_command()**

Modify `ScriptEngine.run()` signature (add `skip_motion`, no `_path_override` needed — tests use `sequences_dir` monkey-patching):
```python
def run(self, name: str, loop: bool = False, skip_motion: bool = False) -> int | None:
```

In the method body, use `self.sequences_dir` instead of `SCRIPTS_DIR`:
```python
path = os.path.join(self.sequences_dir, name + '.scr')
```

Pass `skip_motion` when creating runner:
```python
runner = _ScriptRunner(
    script_id=script_id,
    name=name,
    path=path,
    loop=loop,
    engine=self,
    on_done=self._on_done,
    skip_motion=skip_motion,
)
```

Modify `execute_command()` signature:
```python
def execute_command(self, row: list[str], stop_event=None, skip_motion: bool = False) -> None:
```

Pass `skip_motion` into dispatch:
```python
elif cmd == 'motion':
    self._cmd_motion(row, skip_motion=skip_motion)
```

Modify `_cmd_motion` signature:
```python
def _cmd_motion(self, row: list[str], skip_motion: bool = False) -> None:
```

At the top of `_cmd_motion`, add:
```python
if skip_motion:
    log.debug("motion ignoré (mode test sans propulsion)")
    return
```

- [ ] **Step 6: Update list_running() to include step progress**

```python
def list_running(self) -> list[dict]:
    with self._lock:
        return [
            {
                'id': sid,
                'name': r.name,
                'step_index': r.step_index,
                'step_total': r.step_total,
                'current_cmd': r.current_cmd,
            }
            for sid, r in self._running.items()
        ]
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
cd J:/R2-D2_Build/software
python -m pytest tests/test_sequence_editor_engine.py -v
```
Expected: all 5 tests pass.

- [ ] **Step 8: Commit**

```bash
git add master/script_engine.py tests/test_sequence_editor_engine.py
git commit -m "Feat: script_engine — _run_file, script command, skip_motion, step progress"
```

---

## Task 3: API — New Endpoints + Modified Endpoints

**Files:**
- Modify: `master/api/script_bp.py`
- Create: `tests/test_sequence_editor_api.py`

### Changes overview

**Modified endpoints:**
- `GET /scripts/list` → each entry gets `is_builtin` field
- `GET /scripts/running` → each entry gets `step_index`, `step_total`, `current_cmd`
- `POST /scripts/run` → accepts optional `skip_motion` boolean (default false)

**New endpoints:**
- `GET /scripts/get?name=xxx` → 200 `{name, is_builtin, steps:[{cmd, args},...]}` or 404
- `POST /scripts/save` `{name, steps}` → 200 or 400 (invalid name / empty)
- `POST /scripts/delete` `{name}` → 200 or 403 (built-in) or 404
- `POST /scripts/rename` `{old, new}` → 200 or 400 (invalid name) or 409 (running) or 404

**Helper functions (module-level in script_bp.py):**

```python
import re, subprocess, os
from pathlib import Path

SEQUENCES_DIR = Path(__file__).parent.parent / 'sequences'
NAME_RE = re.compile(r'^[a-zA-Z0-9_\-]{1,64}$')


def _is_valid_name(name: str) -> bool:
    return bool(NAME_RE.match(name))


def _is_builtin(name: str) -> bool:
    """True if the .scr file is tracked in git."""
    rel = f"master/sequences/{name}.scr"
    result = subprocess.run(
        ['git', 'ls-files', '--error-unmatch', rel],
        capture_output=True,
        cwd=str(SEQUENCES_DIR.parent.parent.parent),  # repo root
    )
    return result.returncode == 0


def _parse_scr(path: Path) -> list[dict]:
    """Parse a .scr file into [{cmd, args}] list (skips comments/blank lines)."""
    steps = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            row = [c.strip() for c in line.split(',')]
            if not row or not row[0] or row[0].startswith('#'):
                continue
            steps.append({'cmd': row[0], 'args': row[1:]})
    return steps


def _is_running(name: str) -> bool:
    """True if a sequence with this name is currently running."""
    if not reg.engine:
        return False
    return any(r['name'] == name for r in reg.engine.list_running())
```

- [ ] **Step 1: Write the failing tests**

Create `tests/test_sequence_editor_api.py`:

```python
"""Tests — script_bp.py new and modified API endpoints."""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# We need to create a minimal Flask app for testing
from flask import Flask
import master.registry as reg


@pytest.fixture
def app(tmp_path):
    """Flask test app with sequences dir in tmp_path."""
    from master.api.script_bp import script_bp, SEQUENCES_DIR
    import master.api.script_bp as sbp

    # Override SEQUENCES_DIR to point to tmp_path
    sbp.SEQUENCES_DIR = tmp_path

    flask_app = Flask(__name__)
    flask_app.register_blueprint(script_bp)
    flask_app.config['TESTING'] = True

    # Mock engine
    reg.engine = MagicMock()
    reg.engine.list_scripts.return_value = ['celebrate', 'my_custom']
    reg.engine.list_running.return_value = [
        {'id': 1, 'name': 'celebrate',
         'step_index': 2, 'step_total': 5, 'current_cmd': 'sleep,0.5'}
    ]
    reg.engine.run.return_value = 42

    # Create sample .scr files
    (tmp_path / 'celebrate.scr').write_text("sound,Happy001\nsleep,0.5\n")
    (tmp_path / 'my_custom.scr').write_text("servo,body_panel_1,open\n")

    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


# ── GET /scripts/list ──────────────────────────────────────────────────────────

def test_list_includes_is_builtin(client):
    with patch('master.api.script_bp._is_builtin', side_effect=lambda n: n == 'celebrate'):
        resp = client.get('/scripts/list')
    assert resp.status_code == 200
    data = resp.get_json()
    names = {s['name']: s['is_builtin'] for s in data['scripts']}
    assert names['celebrate'] is True
    assert names['my_custom'] is False


# ── GET /scripts/running ───────────────────────────────────────────────────────

def test_running_includes_step_progress(client):
    resp = client.get('/scripts/running')
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data['running']) == 1
    entry = data['running'][0]
    assert entry['step_index'] == 2
    assert entry['step_total'] == 5
    assert entry['current_cmd'] == 'sleep,0.5'


# ── POST /scripts/run — skip_motion ───────────────────────────────────────────

def test_run_passes_skip_motion(client):
    resp = client.post('/scripts/run',
                       json={'name': 'celebrate', 'skip_motion': True})
    assert resp.status_code == 200
    reg.engine.run.assert_called_once_with('celebrate', loop=False, skip_motion=True)


# ── GET /scripts/get ──────────────────────────────────────────────────────────

def test_get_returns_steps(client, tmp_path):
    with patch('master.api.script_bp._is_builtin', return_value=False):
        resp = client.get('/scripts/get?name=my_custom')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['name'] == 'my_custom'
    assert data['is_builtin'] is False
    assert data['steps'] == [{'cmd': 'servo', 'args': ['body_panel_1', 'open']}]


def test_get_not_found(client):
    resp = client.get('/scripts/get?name=nonexistent')
    assert resp.status_code == 404


# ── POST /scripts/save ────────────────────────────────────────────────────────

def test_save_creates_scr_file(client, tmp_path):
    steps = [
        {'cmd': 'sound', 'args': ['RANDOM', 'happy']},
        {'cmd': 'sleep', 'args': ['0.5']},
    ]
    resp = client.post('/scripts/save',
                       json={'name': 'new_seq', 'steps': steps})
    assert resp.status_code == 200
    scr = tmp_path / 'new_seq.scr'
    assert scr.exists()
    content = scr.read_text()
    assert 'sound,RANDOM,happy' in content
    assert 'sleep,0.5' in content


def test_save_rejects_invalid_name(client):
    resp = client.post('/scripts/save',
                       json={'name': 'bad name!', 'steps': [{'cmd': 'sleep', 'args': ['1']}]})
    assert resp.status_code == 400


def test_save_rejects_empty_steps(client):
    resp = client.post('/scripts/save',
                       json={'name': 'empty_seq', 'steps': []})
    assert resp.status_code == 400


def test_save_blocks_builtin_overwrite(client):
    with patch('master.api.script_bp._is_builtin', return_value=True):
        resp = client.post('/scripts/save',
                           json={'name': 'celebrate',
                                 'steps': [{'cmd': 'sleep', 'args': ['1']}]})
    assert resp.status_code == 403


# ── POST /scripts/delete ──────────────────────────────────────────────────────

def test_delete_removes_file(client, tmp_path):
    with patch('master.api.script_bp._is_builtin', return_value=False):
        resp = client.post('/scripts/delete', json={'name': 'my_custom'})
    assert resp.status_code == 200
    assert not (tmp_path / 'my_custom.scr').exists()


def test_delete_blocks_builtin(client):
    with patch('master.api.script_bp._is_builtin', return_value=True):
        resp = client.post('/scripts/delete', json={'name': 'celebrate'})
    assert resp.status_code == 403


def test_delete_not_found(client):
    with patch('master.api.script_bp._is_builtin', return_value=False):
        resp = client.post('/scripts/delete', json={'name': 'ghost'})
    assert resp.status_code == 404


# ── POST /scripts/rename ─────────────────────────────────────────────────────

def test_rename_renames_file(client, tmp_path):
    with patch('master.api.script_bp._is_running', return_value=False):
        resp = client.post('/scripts/rename',
                           json={'old': 'my_custom', 'new': 'renamed_seq'})
    assert resp.status_code == 200
    assert not (tmp_path / 'my_custom.scr').exists()
    assert (tmp_path / 'renamed_seq.scr').exists()


def test_rename_blocked_if_running(client):
    with patch('master.api.script_bp._is_running', return_value=True):
        resp = client.post('/scripts/rename',
                           json={'old': 'celebrate', 'new': 'other'})
    assert resp.status_code == 409


def test_rename_invalid_new_name(client):
    resp = client.post('/scripts/rename',
                       json={'old': 'my_custom', 'new': 'bad name!'})
    assert resp.status_code == 400


def test_rename_invalid_old_name(client):
    resp = client.post('/scripts/rename',
                       json={'old': '../../etc/passwd', 'new': 'safe_name'})
    assert resp.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd J:/R2-D2_Build/software
python -m pytest tests/test_sequence_editor_api.py -v 2>&1 | head -60
```
Expected: all 14 tests fail (endpoints and helpers don't exist yet).

- [ ] **Step 3: Implement the changes in script_bp.py**

Replace the entire `master/api/script_bp.py` with the updated version.

**At the top** (after existing imports), add:
```python
import re
import subprocess
from pathlib import Path

SEQUENCES_DIR = Path(__file__).parent.parent / 'sequences'
NAME_RE = re.compile(r'^[a-zA-Z0-9_\-]{1,64}$')


def _is_valid_name(name: str) -> bool:
    return bool(NAME_RE.match(name))


def _is_builtin(name: str) -> bool:
    """True if the .scr file is tracked by git."""
    rel = f"master/sequences/{name}.scr"
    repo_root = Path(__file__).parent.parent.parent.parent  # r2d2/
    result = subprocess.run(
        ['git', 'ls-files', '--error-unmatch', rel],
        capture_output=True,
        cwd=str(repo_root),
    )
    return result.returncode == 0


def _parse_scr(path: Path) -> list[dict]:
    """Parse a .scr file into list of {cmd, args} dicts."""
    steps = []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                row = [c.strip() for c in line.split(',')]
                if not row or not row[0] or row[0].startswith('#'):
                    continue
                steps.append({'cmd': row[0], 'args': row[1:]})
    except Exception:
        pass
    return steps


def _is_running(name: str) -> bool:
    """True if any runner with this name is currently active."""
    if not reg.engine:
        return False
    return any(r['name'] == name for r in reg.engine.list_running())
```

**Modify `script_list()`** to include `is_builtin`:
```python
@script_bp.get('/list')
def script_list():
    scripts = reg.engine.list_scripts() if reg.engine else []
    return jsonify({
        'scripts': [
            {'name': s, 'is_builtin': _is_builtin(s)}
            for s in scripts
        ]
    })
```

**Modify `script_running()`** — The current endpoint is:
```python
@script_bp.get('/running')
def script_running():
    running = reg.engine.list_running() if reg.engine else []
    return jsonify({'running': running})
```
After Task 2, `list_running()` returns dicts that include `step_index`, `step_total`, `current_cmd`. This endpoint passes the list through unchanged — **no code change needed here**. The test `test_running_includes_step_progress` verifies the fields arrive correctly via the mocked engine.

**Modify `script_run()`** to accept `skip_motion`:
```python
@script_bp.post('/run')
def script_run():
    body = request.get_json(silent=True) or {}
    name = body.get('name', '').strip()
    loop = bool(body.get('loop', False))
    skip_motion = bool(body.get('skip_motion', False))
    if not name:
        return jsonify({'error': 'Champ "name" requis'}), 400
    if not reg.engine:
        return jsonify({'error': 'ScriptEngine non initialisé'}), 503
    script_id = reg.engine.run(name, loop=loop, skip_motion=skip_motion)
    if script_id is None:
        return jsonify({'error': f'Script "{name}" introuvable'}), 404
    return jsonify({'status': 'ok', 'id': script_id, 'name': name, 'loop': loop})
```

**Add `GET /scripts/get`:**
```python
@script_bp.get('/get')
def script_get():
    name = request.args.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Paramètre "name" requis'}), 400
    path = SEQUENCES_DIR / f"{name}.scr"
    if not path.is_file():
        return jsonify({'error': 'not found'}), 404
    return jsonify({
        'name': name,
        'is_builtin': _is_builtin(name),
        'steps': _parse_scr(path),
    })
```

**Add `POST /scripts/save`:**
```python
@script_bp.post('/save')
def script_save():
    body  = request.get_json(silent=True) or {}
    name  = body.get('name', '').strip()
    steps = body.get('steps', [])
    if not _is_valid_name(name):
        return jsonify({'error': 'invalid name'}), 400
    if not steps:
        return jsonify({'error': 'empty sequence'}), 400
    if _is_builtin(name):
        return jsonify({'error': 'built-in sequence cannot be overwritten'}), 403
    path = SEQUENCES_DIR / f"{name}.scr"
    lines = []
    for step in steps:
        cmd  = step.get('cmd', '')
        args = step.get('args', [])
        parts = [cmd] + [str(a) for a in args if str(a)]
        lines.append(','.join(parts))
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return jsonify({'status': 'ok'})
```

**Add `POST /scripts/delete`:**
```python
@script_bp.post('/delete')
def script_delete():
    body = request.get_json(silent=True) or {}
    name = body.get('name', '').strip()
    path = SEQUENCES_DIR / f"{name}.scr"
    if not path.is_file():
        return jsonify({'error': 'not found'}), 404
    if _is_builtin(name):
        return jsonify({'error': 'built-in sequence cannot be deleted'}), 403
    path.unlink()
    return jsonify({'status': 'ok'})
```

**Add `POST /scripts/rename`:**
```python
@script_bp.post('/rename')
def script_rename():
    body     = request.get_json(silent=True) or {}
    old_name = body.get('old', '').strip()
    new_name = body.get('new', '').strip()
    if not _is_valid_name(old_name):
        return jsonify({'error': 'invalid old name'}), 400
    if not _is_valid_name(new_name):
        return jsonify({'error': 'invalid name'}), 400
    old_path = SEQUENCES_DIR / f"{old_name}.scr"
    if not old_path.is_file():
        return jsonify({'error': 'not found'}), 404
    if _is_running(old_name):
        return jsonify({'error': 'sequence is running'}), 409
    new_path = SEQUENCES_DIR / f"{new_name}.scr"
    old_path.rename(new_path)
    return jsonify({'status': 'ok'})
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd J:/R2-D2_Build/software
python -m pytest tests/test_sequence_editor_api.py -v
```
Expected: all 14 tests pass.

- [ ] **Step 4b: Verify _is_builtin works correctly on the Pi**

The `_is_builtin` function runs `git ls-files` with `cwd` set to the repo root. This relies on the Pi having a proper git repo at `/home/artoo/r2d2`. Deploy the code (Task 7), then SSH to the Pi and test:

```bash
cd /home/artoo/r2d2
# Test a known built-in sequence
git ls-files --error-unmatch master/sequences/celebrate.scr && echo "built-in: YES" || echo "built-in: NO"
# Test a known custom sequence (create one first via the editor, or use any untracked .scr)
git ls-files --error-unmatch master/sequences/MY_CUSTOM.scr && echo "built-in: YES" || echo "built-in: NO"
```
Expected: first command exits 0 (built-in: YES), second exits 1 (built-in: NO).

Also verify via the Flask API after deploy:
```bash
curl http://localhost:5000/scripts/list
```
Expected: `celebrate` has `"is_builtin": true`, any custom sequence has `"is_builtin": false`.

- [ ] **Step 5: Commit**

```bash
git add master/api/script_bp.py tests/test_sequence_editor_api.py
git commit -m "Feat: script API — get/save/delete/rename endpoints + is_builtin + skip_motion"
```

---

## Task 4: Bundle SortableJS

**Files:**
- Create: `master/static/vendor/sortable.min.js`

SortableJS is bundled locally so the editor works offline (R2-D2 runs on a Pi hotspot with no internet).

- [ ] **Step 1: Download SortableJS 1.15.3 minified**

Run this on the dev machine (requires internet):
```bash
curl -L "https://cdn.jsdelivr.net/npm/sortablejs@1.15.3/Sortable.min.js" \
     -o master/static/vendor/sortable.min.js
```

If `curl` is unavailable, use PowerShell:
```powershell
Invoke-WebRequest "https://cdn.jsdelivr.net/npm/sortablejs@1.15.3/Sortable.min.js" `
    -OutFile "master/static/vendor/sortable.min.js"
```

- [ ] **Step 2: Verify the file was downloaded**

```bash
wc -c master/static/vendor/sortable.min.js
```
Expected: ~30–40 KB (roughly 35000+ bytes). Also verify it starts with `/*! Sortable 1.15.3`.

- [ ] **Step 3: Commit**

```bash
git add master/static/vendor/sortable.min.js
git commit -m "Feat: bundle SortableJS 1.15.3 locally for offline use"
```

---

## Task 5: Dashboard Tab — HTML Structure + CSS

**Files:**
- Modify: `master/templates/index.html`
- Modify: `master/static/css/style.css`

Add the ÉDITEUR tab button and its content panel. The panel contains the full editor layout (top bar, left panel, step canvas). The `SequenceEditor` JS class (Task 6) will attach to and populate this structure.

- [ ] **Step 1: Add SortableJS script tag to index.html**

In `master/templates/index.html`, find the `</body>` tag or the area where `app.js` is loaded. Add before `app.js`:

```html
<script src="/static/vendor/sortable.min.js"></script>
```

- [ ] **Step 2: Add ÉDITEUR tab button to the nav bar**

In `index.html`, find the tab buttons. The current tabs are: drive, audio, sequences, lights, systems, vesc, config. Add the ÉDITEUR tab **after** `sequences` tab (line ~131) and **before** `lights`:

```html
<button class="tab" data-tab="editor">
  <svg width="14" height="14" viewBox="0 0 14 14" class="tab-icon">
    <rect x="1" y="2" width="12" height="2" rx="1" fill="currentColor"/>
    <rect x="1" y="6" width="5" height="2" rx="1" fill="currentColor"/>
    <path d="M8 8 L13 5 L13 9 Z" fill="currentColor"/>
  </svg>
  ÉDITEUR
</button>
```

- [ ] **Step 3: Add ÉDITEUR tab content panel**

After the `tab-sequences` div (line ~396 area), add the editor panel. This is the complete HTML structure the JS class will target:

```html
<!-- TAB: ÉDITEUR -->
<div class="tab-content" id="tab-editor">

  <!-- Top bar: name + test controls + save actions -->
  <div id="editor-topbar" style="display:flex;align-items:center;gap:10px;padding:10px 14px;background:#091220;border-bottom:1px solid #1e3a5f;flex-wrap:wrap">
    <div style="display:flex;align-items:center;gap:7px">
      <span style="font-size:8px;color:#4a6a8a;letter-spacing:.1em">NOM</span>
      <input id="editor-name" type="text"
             style="background:#0d1a2e;border:1px solid #00aaff;border-radius:5px;color:#00aaff;font-family:monospace;font-size:12px;padding:4px 10px;width:200px"
             placeholder="nom-sequence" maxlength="64">
    </div>
    <div style="width:1px;height:22px;background:#1e3a5f;margin:0 4px"></div>
    <div style="display:flex;align-items:center;gap:6px">
      <button id="editor-btn-test" class="btn-editor-action" data-color="green">▶ TESTER</button>
      <button id="editor-btn-test-motion" class="btn-editor-action" data-color="orange">▶ TESTER + 🚗</button>
    </div>
    <div style="width:1px;height:22px;background:#1e3a5f;margin:0 4px"></div>
    <button id="editor-btn-stop" class="btn-editor-action" data-color="red">⏹ STOP</button>
    <div style="flex:1"></div>
    <div style="display:flex;align-items:center;gap:6px">
      <button id="editor-btn-delete" class="btn-editor-action" data-color="dim">🗑 SUPPRIMER</button>
      <button id="editor-btn-duplicate" class="btn-editor-action" data-color="blue">📋 DUPLIQUER</button>
      <button id="editor-btn-save" class="btn-editor-action" data-color="solid-blue">💾 SAUVEGARDER</button>
    </div>
  </div>

  <!-- Status strip -->
  <div id="editor-status" style="padding:5px 14px;background:#060e1a;border-bottom:1px solid #0d1e35;display:flex;align-items:center;gap:8px;min-height:24px">
    <span id="editor-status-dot" style="width:7px;height:7px;border-radius:50%;background:#2a4a6a;display:inline-block"></span>
    <span id="editor-status-text" style="font-size:8px;color:#2a4a6a;letter-spacing:.1em">—</span>
    <span id="editor-status-cmd" style="font-size:8px;color:#2a4a6a;margin-left:auto"></span>
  </div>

  <!-- Main two-column layout -->
  <div style="display:grid;grid-template-columns:190px 1fr;min-height:calc(100vh - 180px)">

    <!-- Left panel: sequence list + command palette + sub-sequences -->
    <div id="editor-left" style="background:#070f1c;border-right:1px solid #1e3a5f;overflow-y:auto">

      <!-- Sequence list -->
      <div style="padding:10px 8px">
        <div class="editor-section-label">SÉQUENCES</div>
        <button id="editor-btn-new" class="btn-editor-new">+ Nouvelle</button>
        <div id="editor-seq-list" style="display:flex;flex-direction:column;gap:3px;margin-top:6px"></div>
      </div>

      <!-- Command palette -->
      <div style="padding:0 8px 10px">
        <div class="editor-section-label" style="border-top:1px solid #1e3a5f;padding-top:10px">COMMANDES</div>
        <div id="editor-palette" style="display:flex;flex-direction:column;gap:5px">
          <div class="editor-palette-item" data-cmd="sound" draggable="true">🔊 Son</div>
          <div class="editor-palette-item" data-cmd="sleep" draggable="true">⏱ Pause</div>
          <div class="editor-palette-item" data-cmd="servo" draggable="true">🦾 Servo</div>
          <div class="editor-palette-item" data-cmd="motion" draggable="true">🚗 Propulsion</div>
          <div class="editor-palette-item" data-cmd="teeces" draggable="true">💡 Lumières</div>
          <div class="editor-palette-item" data-cmd="dome" draggable="true">🔁 Dôme</div>
        </div>
      </div>

      <!-- Sub-sequences list -->
      <div style="padding:0 8px 10px">
        <div class="editor-section-label" style="border-top:1px solid #1e3a5f;padding-top:10px">SOUS-SÉQUENCES</div>
        <div id="editor-subseq-list" style="display:flex;flex-direction:column;gap:4px"></div>
      </div>

    </div>

    <!-- Right panel: step canvas -->
    <div id="editor-canvas-wrap" style="padding:12px 14px;overflow-y:auto">
      <div id="editor-canvas-label" style="font-size:8px;color:#4a6a8a;letter-spacing:.12em;margin-bottom:10px">ÉTAPES</div>
      <div id="editor-read-only-banner" style="display:none;background:#1a1000;border:1px solid #ffaa0066;border-radius:6px;padding:8px 12px;margin-bottom:10px;font-size:9px;color:#ffaa00;letter-spacing:.08em">
        🔒 SÉQUENCE INTÉGRÉE — DUPLIQUER POUR MODIFIER
      </div>
      <div id="editor-steps" style="display:flex;flex-direction:column;gap:6px"></div>
      <div id="editor-dropzone" style="margin-top:8px;border:2px dashed #1e3a5f;border-radius:5px;padding:12px;text-align:center;color:#2a4a6a;font-size:9px;letter-spacing:.1em">
        ↓ GLISSER UNE COMMANDE OU SOUS-SÉQUENCE ICI
      </div>
    </div>

  </div>
</div>
```

- [ ] **Step 4: Add editor CSS to style.css**

Append the following to `master/static/css/style.css`:

```css
/* ─── Sequence Editor ─────────────────────────────────── */

.editor-section-label {
  font-size: 8px;
  color: #4a6a8a;
  letter-spacing: .12em;
  margin-bottom: 8px;
}

.btn-editor-new {
  width: 100%;
  background: transparent;
  border: 1px dashed #1e3a5f;
  color: #4a8ac4;
  font-size: 9px;
  padding: 5px 8px;
  border-radius: 5px;
  cursor: pointer;
  letter-spacing: .08em;
  text-align: left;
}
.btn-editor-new:hover { border-color: #00aaff; color: #00aaff; }

.btn-editor-action {
  font-size: 9px;
  padding: 5px 12px;
  border-radius: 5px;
  cursor: pointer;
  letter-spacing: .05em;
  border: 1px solid;
}
.btn-editor-action[data-color="green"]      { background: rgba(0,170,80,.15);  border-color: #00aa50; color: #00cc66; }
.btn-editor-action[data-color="orange"]     { background: rgba(255,100,0,.12); border-color: #ff6600aa; color: #ff8833; }
.btn-editor-action[data-color="red"]        { background: rgba(220,20,40,.25); border-color: #ff3344; color: #ff3344; font-weight: bold; }
.btn-editor-action[data-color="dim"]        { background: transparent; border-color: #4a6a8a; color: #4a6a8a; }
.btn-editor-action[data-color="blue"]       { background: transparent; border-color: #4a8ac4; color: #4a8ac4; }
.btn-editor-action[data-color="solid-blue"] { background: #00aaff; border-color: #00aaff; color: #000; font-weight: bold; }
.btn-editor-action:hover { filter: brightness(1.2); }

.editor-seq-item {
  font-size: 9px;
  padding: 5px 8px;
  border-radius: 5px;
  cursor: pointer;
  color: #a0c0e0;
  border: 1px solid transparent;
  display: flex;
  align-items: center;
  gap: 5px;
}
.editor-seq-item:hover       { background: #0d1e35; border-color: #1e3a5f; }
.editor-seq-item.active      { background: #0f2040; border-color: #00aaff44; color: #00aaff; }
.editor-seq-item .lock-icon  { color: #4a6a8a; font-size: 8px; }
.editor-seq-item .edit-badge { margin-left: auto; color: #00aaff; font-size: 8px; }

.editor-palette-item {
  font-size: 9px;
  padding: 5px 8px;
  border-radius: 5px;
  cursor: grab;
  border: 1px solid #1e3a5f;
  color: #a0c0e0;
  background: #0a1628;
  user-select: none;
}
.editor-palette-item:hover { border-color: #00aaff44; background: #0f2040; }
.editor-palette-item[data-cmd="sound"]   { color: #00cc55; background: #0a2a10; border-color: #00aa3355; }
.editor-palette-item[data-cmd="sleep"]   { color: #ffaa00; background: #2a1a00; border-color: #ffaa0044; }
.editor-palette-item[data-cmd="servo"]   { color: #00aaff; background: #001a2a; border-color: #00aaff44; }
.editor-palette-item[data-cmd="motion"]  { color: #ff6633; background: #1a1000; border-color: #ff663344; }
.editor-palette-item[data-cmd="teeces"] { color: #aa44ff; background: #1a0028; border-color: #aa44ff44; }
.editor-palette-item[data-cmd="dome"]    { color: #44ffaa; background: #0a1a10; border-color: #44ffaa44; }

.editor-subseq-item {
  font-size: 9px;
  padding: 5px 8px;
  border-radius: 5px;
  cursor: grab;
  border: 1px solid #884dcc55;
  color: #cc88ff;
  background: #1a1030;
  user-select: none;
}
.editor-subseq-item:hover { border-color: #884dcc; }

/* Step rows */
.editor-step-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}
.editor-step-num {
  font-size: 9px;
  color: #2a4a6a;
  min-width: 20px;
  text-align: right;
  padding-top: 9px;
}
.editor-step-card {
  flex: 1;
  border-radius: 5px;
  padding: 7px 10px;
  border: 1px solid;
  border-left-width: 3px;
}
.editor-step-card[data-cmd="sound"]   { background: #091a0a; border-color: #00aa5544; border-left-color: #00cc55; }
.editor-step-card[data-cmd="sleep"]   { background: #1a1200; border-color: #ffaa0044; border-left-color: #ffaa00; }
.editor-step-card[data-cmd="servo"]   { background: #0f2040; border-color: #00aaff44; border-left-color: #00aaff; }
.editor-step-card[data-cmd="motion"]  { background: #1a0e00; border-color: #ff663344; border-left-color: #ff6633; }
.editor-step-card[data-cmd="teeces"] { background: #140028; border-color: #aa44ff44; border-left-color: #aa44ff; }
.editor-step-card[data-cmd="dome"]    { background: #0a1a10; border-color: #44ffaa44; border-left-color: #44ffaa; }
.editor-step-card[data-cmd="script"]  { background: #160d28; border-color: #884dcc66; border-left-color: #cc88ff; }
.editor-step-handle { font-size: 14px; color: #1e3a5f; cursor: grab; padding-top: 6px; }
.editor-step-handle:active { cursor: grabbing; }

/* Inline edit form */
.editor-step-form {
  margin-top: 8px;
  padding: 8px;
  background: #060e1a;
  border-radius: 4px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.editor-step-form label { font-size: 8px; color: #4a6a8a; letter-spacing: .08em; }
.editor-step-form select,
.editor-step-form input[type="text"],
.editor-step-form input[type="number"] {
  background: #0d1a2e;
  border: 1px solid #1e3a5f;
  color: #a0c0e0;
  font-family: monospace;
  font-size: 10px;
  padding: 3px 7px;
  border-radius: 4px;
}
.editor-step-form select:focus,
.editor-step-form input:focus { border-color: #00aaff; outline: none; }

/* Sub-sequence preview */
.editor-subseq-preview {
  margin-top: 6px;
  padding: 6px 8px;
  background: #100820;
  border-radius: 4px;
  border: 1px solid #2a1a44;
  font-size: 8px;
  color: #6a4a8a;
  line-height: 1.8;
}
.editor-subseq-preview-title { color: #6a3a9a; letter-spacing: .1em; margin-bottom: 4px; }

/* Sortable drag ghost */
.sortable-ghost { opacity: 0.3; }
.sortable-chosen { box-shadow: 0 0 0 2px #00aaff55; }
```

- [ ] **Step 5: Verify HTML/CSS renders (visual check)**

Open the dashboard in a browser: `http://192.168.2.104:5000`. Click the ÉDITEUR tab. Verify:
- Tab appears in the nav bar
- The panel renders (empty canvas, left panel visible)
- No console JS errors

If SSH not available, deploy first (Task 7).

- [ ] **Step 6: Commit**

```bash
git add master/templates/index.html master/static/css/style.css
git commit -m "Feat: ÉDITEUR tab — HTML structure + CSS"
```

---

## Task 6: SequenceEditor JavaScript Class

**Files:**
- Modify: `master/static/js/app.js`

This is the main UI logic. The class attaches to the DOM structure added in Task 5 and implements all interactive behavior.

### Class structure

```
SequenceEditor
├── constructor()           — bind DOM refs, attach events, start polling
├── loadSequenceList()      — GET /scripts/list, populate left panel
├── openSequence(name)      — GET /scripts/get, render canvas
├── renderSteps()           — full re-render of step canvas
├── renderStep(step, idx)   — render a single step card + handle
├── renderStepForm(step, idx) — expand inline edit form
├── addStep(cmd, args)      — append step, re-render
├── removeStep(idx)         — splice, re-render
├── updateStep(idx, args)   — mutate step args, re-render card
├── initSortable()          — attach SortableJS to #editor-steps
├── handleDrop(cmd)         — from palette/subseq drag
├── saveSequence()          — POST /scripts/save
├── deleteSequence()        — POST /scripts/delete
├── duplicateSequence()     — prompt name → POST /scripts/save (copy) → open
├── renameSequence()        — POST /scripts/rename
├── testRun(skipMotion)     — POST /scripts/run
├── stop()                  — POST /scripts/stop_all
├── pollStatus()            — GET /scripts/running every 500ms → update status strip
└── _getCmdColor(cmd)       — return CSS class/color for a command type
```

- [ ] **Step 1: Add SequenceEditor class to app.js**

At the **end of app.js** (before or after the DOMContentLoaded block), add the full `SequenceEditor` class. Here is the complete implementation:

```javascript
// ─── SequenceEditor ────────────────────────────────────────────────────────
class SequenceEditor {
  constructor() {
    // DOM refs
    this._nameInput     = document.getElementById('editor-name');
    this._steps         = document.getElementById('editor-steps');
    this._dropzone      = document.getElementById('editor-dropzone');
    this._seqList       = document.getElementById('editor-seq-list');
    this._subseqList    = document.getElementById('editor-subseq-list');
    this._statusDot     = document.getElementById('editor-status-dot');
    this._statusText    = document.getElementById('editor-status-text');
    this._statusCmd     = document.getElementById('editor-status-cmd');
    this._roBanner      = document.getElementById('editor-read-only-banner');
    this._canvasLabel   = document.getElementById('editor-canvas-label');

    // State
    this._sequence   = [];   // [{cmd, args}, ...]
    this._openName   = null; // name of currently open sequence
    this._isBuiltin  = false;
    this._pollTimer  = null;
    this._editingIdx = null; // index of step with open inline form

    this._initButtons();
    this._initPalette();
    this._initSortable();
    this._startPolling();
  }

  // ── Init ─────────────────────────────────────────────────────────────────

  _initButtons() {
    document.getElementById('editor-btn-new')
      .addEventListener('click', () => this._newSequence());
    document.getElementById('editor-btn-save')
      .addEventListener('click', () => this.saveSequence());
    document.getElementById('editor-btn-delete')
      .addEventListener('click', () => this.deleteSequence());
    document.getElementById('editor-btn-duplicate')
      .addEventListener('click', () => this.duplicateSequence());
    document.getElementById('editor-btn-test')
      .addEventListener('click', () => this.testRun(true));
    document.getElementById('editor-btn-test-motion')
      .addEventListener('click', () => this.testRun(false));
    document.getElementById('editor-btn-stop')
      .addEventListener('click', () => this.stop());

    this._nameInput.addEventListener('blur', () => this._onNameBlur());
  }

  _initPalette() {
    document.querySelectorAll('.editor-palette-item').forEach(el => {
      el.addEventListener('dragstart', e => {
        e.dataTransfer.setData('editor-cmd', el.dataset.cmd);
      });
    });
    this._dropzone.addEventListener('dragover', e => {
      e.preventDefault();
      this._dropzone.style.borderColor = '#00aaff';
    });
    this._dropzone.addEventListener('dragleave', () => {
      this._dropzone.style.borderColor = '';
    });
    this._dropzone.addEventListener('drop', e => {
      e.preventDefault();
      this._dropzone.style.borderColor = '';
      const cmd = e.dataTransfer.getData('editor-cmd');
      const subName = e.dataTransfer.getData('editor-subseq');
      if (subName) {
        this._addStep('script', [subName]);
      } else if (cmd) {
        this._addStep(cmd, this._defaultArgs(cmd));
      }
    });
  }

  _initSortable() {
    if (typeof Sortable === 'undefined') return;
    Sortable.create(this._steps, {
      handle: '.editor-step-handle',
      animation: 150,
      ghostClass: 'sortable-ghost',
      chosenClass: 'sortable-chosen',
      onEnd: (evt) => {
        const [moved] = this._sequence.splice(evt.oldIndex, 1);
        this._sequence.splice(evt.newIndex, 0, moved);
        this._renderSteps();
      },
    });
  }

  _startPolling() {
    this._pollTimer = setInterval(() => this._pollStatus(), 500);
  }

  // ── Load sequence list ────────────────────────────────────────────────────

  async loadSequenceList() {
    try {
      const resp = await fetch('/scripts/list');
      const data = await resp.json();
      this._renderSeqList(data.scripts || []);
    } catch (e) {
      console.error('SequenceEditor: loadSequenceList', e);
    }
  }

  _renderSeqList(scripts) {
    this._seqList.innerHTML = '';
    this._subseqList.innerHTML = '';

    scripts.forEach(s => {
      // Sequence list item
      const el = document.createElement('div');
      el.className = 'editor-seq-item' + (s.name === this._openName ? ' active' : '');
      el.innerHTML = s.is_builtin
        ? `<span class="lock-icon">🔒</span><span>${s.name}</span>`
        : `<span>${s.name}</span><span class="edit-badge">✏</span>`;
      el.addEventListener('click', () => this.openSequence(s.name));
      this._seqList.appendChild(el);

      // Sub-sequence palette item (all sequences, except the one currently open)
      if (s.name !== this._openName) {
        const sub = document.createElement('div');
        sub.className = 'editor-subseq-item';
        sub.draggable = true;
        sub.textContent = `📋 ${s.name}`;
        sub.addEventListener('dragstart', e => {
          e.dataTransfer.setData('editor-subseq', s.name);
        });
        this._subseqList.appendChild(sub);
      }
    });
  }

  // ── Open sequence ─────────────────────────────────────────────────────────

  async openSequence(name) {
    try {
      const resp = await fetch(`/scripts/get?name=${encodeURIComponent(name)}`);
      if (!resp.ok) { alert(`Séquence "${name}" introuvable`); return; }
      const data = await resp.json();
      this._openName  = data.name;
      this._isBuiltin = data.is_builtin;
      this._sequence  = data.steps.map(s => ({
        cmd: s.cmd,
        args: [...s.args],
      }));
      this._editingIdx = null;
      this._nameInput.value    = data.name;
      this._nameInput.readOnly = data.is_builtin;
      this._nameInput.style.borderColor = data.is_builtin ? '#4a6a8a' : '#00aaff';
      this._roBanner.style.display = data.is_builtin ? 'block' : 'none';
      this._canvasLabel.textContent = `ÉTAPES — ${data.name}`;
      this._renderSteps();
      await this.loadSequenceList(); // refresh active state in list
    } catch (e) {
      console.error('SequenceEditor: openSequence', e);
    }
  }

  // ── Step canvas ───────────────────────────────────────────────────────────

  _renderSteps() {
    this._steps.innerHTML = '';
    this._sequence.forEach((step, idx) => {
      this._steps.appendChild(this._renderStep(step, idx));
    });
  }

  _renderStep(step, idx) {
    const row = document.createElement('div');
    row.className = 'editor-step-row';
    row.dataset.idx = idx;

    const num = document.createElement('div');
    num.className = 'editor-step-num';
    num.textContent = idx + 1;

    const card = document.createElement('div');
    card.className = 'editor-step-card';
    card.dataset.cmd = step.cmd;

    // Badge + summary line
    const summary = document.createElement('div');
    summary.style.cssText = 'display:flex;align-items:center;gap:8px';
    const badge = document.createElement('span');
    badge.style.cssText = 'font-size:9px;padding:2px 7px;border-radius:10px;white-space:nowrap';
    badge.textContent = `${this._cmdIcon(step.cmd)} ${step.cmd}`;
    badge.style.color = this._cmdColor(step.cmd);
    badge.style.background = this._cmdBg(step.cmd);

    const desc = document.createElement('span');
    desc.style.cssText = 'font-size:10px;color:#a0c0e0;flex:1';
    desc.textContent = step.args.join(' ');

    const actions = document.createElement('span');
    actions.style.cssText = 'font-size:9px;color:#4a6a8a;margin-left:auto;display:flex;align-items:center;gap:6px';
    if (!this._isBuiltin) {
      const btnEdit = document.createElement('span');
      btnEdit.textContent = '✏️';
      btnEdit.style.cssText = 'cursor:pointer';
      btnEdit.title = 'Modifier';
      btnEdit.addEventListener('click', (e) => {
        e.stopPropagation();
        this._toggleEdit(idx);
      });

      const btnDel = document.createElement('span');
      btnDel.textContent = '🗑';
      btnDel.style.cssText = 'cursor:pointer';
      btnDel.title = 'Supprimer';
      btnDel.addEventListener('click', (e) => {
        e.stopPropagation();
        this._removeStep(idx);
      });

      actions.appendChild(btnEdit);
      actions.appendChild(btnDel);
    }

    summary.appendChild(badge);
    summary.appendChild(desc);
    summary.appendChild(actions);
    card.appendChild(summary);

    // Sub-sequence preview
    if (step.cmd === 'script' && step.args[0]) {
      const preview = document.createElement('div');
      preview.className = 'editor-subseq-preview';
      preview.innerHTML = `<div class="editor-subseq-preview-title">▾ ${step.args[0]}.scr</div>`;
      this._loadSubseqPreview(step.args[0], preview);
      card.appendChild(preview);
    }

    // Inline edit form (if this step is being edited)
    if (this._editingIdx === idx && !this._isBuiltin) {
      card.appendChild(this._renderStepForm(step, idx));
    }

    const handle = document.createElement('div');
    handle.className = 'editor-step-handle';
    handle.textContent = '⋮⋮';
    if (this._isBuiltin) handle.style.cursor = 'default';

    row.appendChild(num);
    row.appendChild(card);
    if (!this._isBuiltin) row.appendChild(handle);

    return row;
  }

  async _loadSubseqPreview(name, el) {
    try {
      const resp = await fetch(`/scripts/get?name=${encodeURIComponent(name)}`);
      if (!resp.ok) { el.innerHTML += '<div style="color:#4a2a6a">introuvable</div>'; return; }
      const data = await resp.json();
      const lines = data.steps.slice(0, 4).map(s =>
        `<div>${s.cmd},${s.args.join(',')}</div>`
      ).join('');
      const more = data.steps.length > 4
        ? `<div style="color:#4a2a6a">…${data.steps.length - 4} autres</div>`
        : '';
      el.innerHTML = `<div class="editor-subseq-preview-title">▾ ${name}.scr</div>${lines}${more}`;
    } catch (e) { /* silent */ }
  }

  _renderStepForm(step, idx) {
    const form = document.createElement('div');
    form.className = 'editor-step-form';

    const fields = this._stepFields(step.cmd, step.args);
    const inputs = [];

    fields.forEach(f => {
      const wrap = document.createElement('div');
      wrap.style.cssText = 'display:flex;flex-direction:column;gap:3px';
      const lbl = document.createElement('label');
      lbl.textContent = f.label;
      let inp;
      if (f.options) {
        inp = document.createElement('select');
        f.options.forEach(o => {
          const opt = document.createElement('option');
          opt.value = o; opt.textContent = o;
          if (o === f.value) opt.selected = true;
          inp.appendChild(opt);
        });
      } else {
        inp = document.createElement('input');
        inp.type = f.type || 'text';
        inp.value = f.value || '';
        inp.placeholder = f.placeholder || '';
        if (f.style) inp.style.cssText = f.style;
      }
      inputs.push({ field: f, inp });
      wrap.appendChild(lbl);
      wrap.appendChild(inp);
      form.appendChild(wrap);
    });

    // OK button
    const ok = document.createElement('button');
    ok.textContent = '✓ OK';
    ok.className = 'btn-editor-action';
    ok.dataset.color = 'green';
    ok.style.marginTop = '4px';
    ok.addEventListener('click', () => {
      const newArgs = inputs.map(({ inp }) => inp.value.trim()).filter(Boolean);
      this._sequence[idx].args = newArgs;
      this._editingIdx = null;
      this._renderSteps();
    });
    form.appendChild(ok);

    return form;
  }

  // ── Step operations ───────────────────────────────────────────────────────

  _addStep(cmd, args) {
    if (this._isBuiltin) return;
    this._sequence.push({ cmd, args: [...args] });
    this._editingIdx = this._sequence.length - 1;
    this._renderSteps();
  }

  _removeStep(idx) {
    if (this._isBuiltin) return;
    this._sequence.splice(idx, 1);
    if (this._editingIdx === idx) this._editingIdx = null;
    this._renderSteps();
  }

  _toggleEdit(idx) {
    this._editingIdx = this._editingIdx === idx ? null : idx;
    this._renderSteps();
  }

  // ── New/Save/Delete/Duplicate/Rename ─────────────────────────────────────

  _newSequence() {
    const name = prompt('Nom de la nouvelle séquence (lettres, chiffres, - et _ uniquement) :');
    if (!name) return;
    if (!/^[a-zA-Z0-9_\-]{1,64}$/.test(name)) {
      alert('Nom invalide. Utilisez lettres, chiffres, - et _ uniquement (max 64 caractères).');
      return;
    }
    this._openName  = name;
    this._isBuiltin = false;
    this._sequence  = [];
    this._editingIdx = null;
    this._nameInput.value    = name;
    this._nameInput.readOnly = false;
    this._nameInput.style.borderColor = '#00aaff';
    this._roBanner.style.display = 'none';
    this._canvasLabel.textContent = `ÉTAPES — ${name} (nouveau)`;
    this._renderSteps();
  }

  async saveSequence() {
    if (this._isBuiltin) { alert('Séquence intégrée — dupliquez-la pour modifier.'); return; }
    const name = this._nameInput.value.trim();
    if (!name || !/^[a-zA-Z0-9_\-]{1,64}$/.test(name)) {
      alert('Nom invalide.'); return;
    }
    if (this._sequence.length === 0) {
      alert('La séquence est vide.'); return;
    }
    try {
      const resp = await fetch('/scripts/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, steps: this._sequence }),
      });
      if (!resp.ok) {
        const err = await resp.json();
        alert(`Erreur: ${err.error}`); return;
      }
      this._openName = name;
      this._canvasLabel.textContent = `ÉTAPES — ${name}`;
      await this.loadSequenceList();
    } catch (e) {
      alert('Erreur réseau lors de la sauvegarde.');
    }
  }

  async deleteSequence() {
    if (this._isBuiltin) { alert('Séquence intégrée — impossible de supprimer.'); return; }
    if (!this._openName) return;
    if (!confirm(`Supprimer "${this._openName}" ? Cette action est irréversible.`)) return;
    try {
      const resp = await fetch('/scripts/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: this._openName }),
      });
      if (!resp.ok) {
        const err = await resp.json();
        alert(`Erreur: ${err.error}`); return;
      }
      this._openName  = null;
      this._sequence  = [];
      this._isBuiltin = false;
      this._nameInput.value = '';
      this._canvasLabel.textContent = 'ÉTAPES';
      this._renderSteps();
      await this.loadSequenceList();
    } catch (e) {
      alert('Erreur réseau.');
    }
  }

  async duplicateSequence() {
    const newName = prompt('Nom pour la copie :');
    if (!newName) return;
    if (!/^[a-zA-Z0-9_\-]{1,64}$/.test(newName)) {
      alert('Nom invalide.'); return;
    }
    try {
      const resp = await fetch('/scripts/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newName, steps: this._sequence }),
      });
      if (!resp.ok) { alert('Erreur lors de la duplication.'); return; }
      await this.openSequence(newName);
    } catch (e) {
      alert('Erreur réseau.');
    }
  }

  async _onNameBlur() {
    const newName = this._nameInput.value.trim();
    if (!newName || newName === this._openName || this._isBuiltin) return;
    if (!/^[a-zA-Z0-9_\-]{1,64}$/.test(newName)) {
      alert('Nom invalide.'); this._nameInput.value = this._openName || ''; return;
    }
    if (!this._openName) return; // new unsaved sequence, just update display
    try {
      const resp = await fetch('/scripts/rename', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ old: this._openName, new: newName }),
      });
      if (!resp.ok) {
        const err = await resp.json();
        alert(`Renommage impossible: ${err.error}`);
        this._nameInput.value = this._openName;
        return;
      }
      this._openName = newName;
      this._canvasLabel.textContent = `ÉTAPES — ${newName}`;
      await this.loadSequenceList();
    } catch (e) {
      alert('Erreur réseau.');
    }
  }

  // ── Test / Stop ───────────────────────────────────────────────────────────

  async testRun(skipMotion) {
    if (!this._openName) { alert('Ouvrez ou sauvegardez une séquence d\'abord.'); return; }
    try {
      await fetch('/scripts/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: this._openName,
          loop: false,
          skip_motion: skipMotion,
        }),
      });
    } catch (e) { console.error('testRun', e); }
  }

  async stop() {
    try {
      await fetch('/scripts/stop_all', { method: 'POST' });
    } catch (e) { console.error('stop', e); }
  }

  // ── Status polling ────────────────────────────────────────────────────────

  async _pollStatus() {
    // Only poll when editor tab is visible
    const editorTab = document.getElementById('tab-editor');
    if (!editorTab || !editorTab.classList.contains('active')) return;
    try {
      const resp = await fetch('/scripts/running');
      const data = await resp.json();
      const running = (data.running || []).find(r => r.name === this._openName);
      if (running) {
        this._statusDot.style.background = '#00cc55';
        this._statusDot.style.boxShadow  = '0 0 6px #00cc55';
        this._statusText.style.color = '#00cc55';
        this._statusText.textContent =
          `EN COURS — ${running.name} (étape ${running.step_index}/${running.step_total})`;
        this._statusCmd.textContent = running.current_cmd || '';
        this._statusCmd.style.color = '#2a4a6a';
      } else {
        this._statusDot.style.background = '#2a4a6a';
        this._statusDot.style.boxShadow  = 'none';
        this._statusText.style.color = '#2a4a6a';
        this._statusText.textContent = '—';
        this._statusCmd.textContent = '';
      }
    } catch (e) { /* silent */ }
  }

  // ── Command metadata ──────────────────────────────────────────────────────

  _cmdIcon(cmd) {
    return { sound:'🔊', sleep:'⏱', servo:'🦾', motion:'🚗',
             teeces:'💡', dome:'🔁', script:'📋' }[cmd] || '•';
  }

  _cmdColor(cmd) {
    return { sound:'#00cc55', sleep:'#ffaa00', servo:'#00aaff',
             motion:'#ff6633', teeces:'#aa44ff', dome:'#44ffaa',
             script:'#cc88ff' }[cmd] || '#a0c0e0';
  }

  _cmdBg(cmd) {
    return { sound:'#0a2a10', sleep:'#2a1a00', servo:'#001a2a',
             motion:'#1a1000', teeces:'#1a0028', dome:'#0a1a10',
             script:'#1a1030' }[cmd] || '#0d1a2e';
  }

  _defaultArgs(cmd) {
    return {
      sound:   ['RANDOM', 'happy'],
      sleep:   ['1.0'],
      servo:   ['body_panel_1', 'open'],
      motion:  ['0.0', '0.0', '1000'],
      teeces:  ['random'],
      dome:    ['stop'],
      script:  [''],
    }[cmd] || [];
  }

  _stepFields(cmd, args) {
    // Returns [{label, value, options?, type?, placeholder?}]
    switch (cmd) {
      case 'sound': return [
        { label: 'Mode', value: args[0]||'RANDOM', options: ['RANDOM', 'FILE'] },
        { label: 'Catégorie / Fichier', value: args[1]||'happy',
          options: ['happy','sad','chat','whistle','scream','process','utility','random','special'] },
      ];
      case 'sleep': return [
        { label: 'Mode', value: args[0]==='random'?'random':'fixed',
          options: ['fixed', 'random'] },
        { label: 'Durée (s) / Min', value: args[0]==='random'?(args[1]||'1'):args[0]||'1',
          type: 'number', placeholder: '1.0' },
        ...(args[0]==='random' ? [
          { label: 'Max (s)', value: args[2]||'3', type: 'number', placeholder: '3.0' }
        ] : []),
      ];
      case 'servo': return [
        { label: 'Panneau', value: args[0]||'body_panel_1',
          options: ['body_panel_1','body_panel_2','body_panel_3','body_panel_4',
                    'dome_panel_1','dome_panel_2','dome_panel_3','dome_panel_4',
                    'dome_panel_5','dome_panel_6','all'] },
        { label: 'Action', value: args[1]||'open', options: ['open','close'] },
        { label: 'Angle (optionnel)', value: args[2]||'', type: 'number', placeholder: '—' },
        { label: 'Vitesse (1-10)', value: args[3]||'', type: 'number', placeholder: '—' },
      ];
      case 'motion': return [
        { label: 'Gauche (-1..1)', value: args[0]||'0.0', type: 'number', placeholder: '0.0' },
        { label: 'Droite (-1..1)', value: args[1]||'0.0', type: 'number', placeholder: '0.0' },
        { label: 'Durée ms', value: args[2]||'1000', type: 'number', placeholder: '1000' },
      ];
      case 'teeces': return [
        { label: 'Mode', value: args[0]||'random',
          options: ['random','leia','off','text','psi'] },
        ...(args[0]==='text' ? [{ label: 'Texte', value: args[1]||'', placeholder: 'HELLO' }] : []),
        ...(args[0]==='psi'  ? [{ label: 'Mode PSI', value: args[1]||'0', type: 'number' }] : []),
      ];
      case 'dome': return [
        { label: 'Action', value: args[0]||'stop', options: ['turn','stop','random','center'] },
        ...(args[0]==='turn' ? [{ label: 'Vitesse (-1..1)', value: args[1]||'0.3', type: 'number' }] : []),
        ...(args[0]==='random' ? [{ label: 'On/Off', value: args[1]||'on', options: ['on','off'] }] : []),
      ];
      case 'script': return [
        { label: 'Sous-séquence', value: args[0]||'', placeholder: 'nom-sequence' },
      ];
      default: return args.map((a, i) => ({ label: `arg${i+1}`, value: a }));
    }
  }
}
```

- [ ] **Step 2: Initialize SequenceEditor in the DOMContentLoaded block**

Find the `DOMContentLoaded` block in `app.js` where other controllers are initialized. Add:

```javascript
// Sequence Editor
const seqEditor = new SequenceEditor();

// Load sequence list when ÉDITEUR tab is activated
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    if (tab.dataset.tab === 'editor') {
      seqEditor.loadSequenceList();
    }
  });
});
```

- [ ] **Step 3: Deploy and test interactively**

Deploy to Pi:
```python
import paramiko, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.2.104', username='artoo', password='deetoo', timeout=10)
stdin, stdout, stderr = c.exec_command('cd /home/artoo/r2d2 && bash scripts/update.sh 2>&1')
for line in stdout: print(line, end='')
c.close()
```

Then verify in browser:
1. Navigate to `http://192.168.2.104:5000`, click ÉDITEUR tab
2. Sequence list loads on the left with lock icons for built-ins
3. Click a custom sequence → steps appear in canvas
4. Click a built-in → read-only banner appears, edit buttons hidden
5. Drag a command from palette to dropzone → step added
6. Reorder steps with ⋮⋮ handle
7. Click ✏️ on a step → inline form expands, click ✓ OK
8. Click 💾 SAUVEGARDER → no error
9. Click ▶ TESTER → status strip turns green with step progress

- [ ] **Step 4: Commit**

```bash
git add master/static/js/app.js
git commit -m "Feat: SequenceEditor JS class — full drag & drop editor"
```

---

## Task 7: Android Assets Sync + Final Deploy

**Files:**
- Modify: `android/app/src/main/assets/js/app.js`
- Modify: `android/app/src/main/assets/css/style.css`

The Android WebView app bundles local copies of `app.js` and `style.css`. These need to be synced after every change to the dashboard (per CLAUDE.md instructions).

- [ ] **Step 1: Sync app.js and style.css to Android assets**

```bash
cp master/static/js/app.js android/app/src/main/assets/js/app.js
cp master/static/css/style.css android/app/src/main/assets/css/style.css
```

**Do NOT sync `index.html` to Android assets.** The spec explicitly states the ÉDITEUR tab is "Not in the Android HUD — editing is a desktop/tablet activity." The Android app should continue using the existing `index.html` (without the ÉDITEUR tab) so the HUD stays clean. The `app.js` and `style.css` changes are backward-compatible (the `SequenceEditor` class only attaches when `#editor-steps` exists in the DOM, which it won't in the Android version). No path patching required.

- [ ] **Step 2: Build the Android APK**

```powershell
powershell.exe -Command "& { $env:JAVA_HOME='C:/Program Files/Android/Android Studio/jbr'; Set-Location 'J:/R2-D2_Build/software/android'; ./gradlew.bat assembleDebug }"
cp android/app/build/outputs/apk/debug/app-debug.apk android/compiled/R2-D2_Control.apk
```

- [ ] **Step 3: Commit and push everything**

```bash
git add android/app/src/main/assets/js/app.js
git add android/app/src/main/assets/css/style.css
git add android/compiled/R2-D2_Control.apk
git commit -m "ci: sync Android assets + rebuild APK — sequence editor"
git push
```

- [ ] **Step 4: Deploy to Pi**

```python
import paramiko, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.2.104', username='artoo', password='deetoo', timeout=10)
stdin, stdout, stderr = c.exec_command('cd /home/artoo/r2d2 && bash scripts/update.sh 2>&1')
for line in stdout: print(line, end='')
c.close()
```

---

## Test Summary

After all tasks, run the full test suite:

```bash
cd J:/R2-D2_Build/software
python -m pytest tests/ -v
```

Expected: all tests pass including:
- `test_sequence_editor_engine.py` — 5 tests
- `test_sequence_editor_api.py` — 14 tests
- existing tests unchanged

---

## Notes for Implementer

- **Built-in detection uses `git ls-files`** — this runs on the Pi (Linux). On the dev machine (Windows), the path separator in `master/sequences/{name}.scr` should use forward slashes (already the case in the plan). The `cwd` for the subprocess must be the repo root (`r2d2/`). The path `docs/superpowers/specs/2026-03-23-sequence-editor-design.md` is the approved spec.

- **SortableJS CDN URL** — use exactly `https://cdn.jsdelivr.net/npm/sortablejs@1.15.3/Sortable.min.js`. Do not use `@latest` — pin the version.

- **`_cmd_motion` skip_motion and existing Child Lock** — the existing `_cmd_motion` already has a Child Lock check at the top. The `skip_motion` return should be **before** the Child Lock check (they are independent: test mode vs safety mode).

- **Circular sub-sequences** — no guard in v1. If the user creates A → calls B → calls A, it will recurse until the Python stack limit. The `⏹ STOP` button sets the stop event and breaks the loop. Document this in a `# WARNING` comment in `_run_file`.
