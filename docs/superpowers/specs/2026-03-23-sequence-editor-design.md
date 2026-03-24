# R2-D2 Sequence Editor — Design Spec
**Date:** 2026-03-23
**Status:** Approved

---

## Context

R2-D2 has 40 behavioural sequences (`.scr` files) stored in `master/sequences/`. These are hand-edited CSV text files. The goal is a visual drag-and-drop editor in the web dashboard that lets the user create, edit, test, and organise sequences without touching raw text — while keeping the `.scr` format intact on disk.

---

## Overview

A new **ÉDITEUR** tab in the web dashboard (`index.html`). Not in the Android HUD — editing is a desktop/tablet activity.

Left panel: sequence list + command palette + available sub-sequences.
Right panel: drag-and-drop step canvas for the open sequence.
Top bar: sequence name, test controls, save/delete/duplicate.

---

## Architecture

### Files Modified / Created

| File | Change |
|------|--------|
| `master/templates/index.html` | New "ÉDITEUR" tab (7th tab) |
| `master/static/js/app.js` | New `SequenceEditor` class |
| `master/static/css/style.css` | Editor styles |
| `master/static/vendor/sortable.min.js` | SortableJS bundled locally (offline-safe, version 1.15.3) |
| `master/api/script_bp.py` | New endpoints: `get`, `save`, `delete`, `rename` |
| `master/script_engine.py` | New command `script,<name>` + `_run_file` refactor + `skip_motion` flag + step progress tracking |
| `scripts/update.sh` | Backup custom sequences before `git pull` |

### Sequence Storage

- **Built-in sequences** (tracked in git, detected via `git ls-files`): opened **read-only** in the editor. User must duplicate to modify.
- **Custom sequences** (untracked): created/edited freely via editor, stored in `master/sequences/`.
- **Conflict rule**: if `git pull` introduces a file with the same name as an existing custom sequence, the custom version wins (`--ignore-existing`). This is intentional and documented.
- **Last-write-wins**: if a `.scr` file is modified on disk externally while open in the editor, the editor will overwrite it silently on save. No conflict detection in v1.

---

## Layout

```
┌──────────────────────────────────────────────────────────┐
│ NOM: [Bras-Extension_retract____] ▶TESTER  ▶TESTER+🚗  ⏹STOP │  ← top bar
│                          📋DUPLIQUER  🗑SUPPRIMER  💾SAUVEGARDER│
├──────────────────────┬───────────────────────────────────┤
│ SÉQUENCES            │ ÉTAPES — Bras-Extension_retract   │
│ ─────────────────── │ ──────────────────────────────────│
│ + Nouvelle           │ 1  🦾 servo  body_panel_1  open ⋮ │
│ ─────────────────── │ 2  🦾 servo  body_panel_2  open ⋮ │
│ 🔒 celebrate         │ 3  ⏱ sleep  0.5s            ⋮ │
│ ● Bras-Extension (✏) │ 4  📋 Bras-Extension_retract ⋮   │
│   alert              │ 5  🔊 sound  RANDOM happy    ⋮ │
│   …                  │                                   │
│ ─────────────────── │ [ + glisser une commande ici ]    │
│ COMMANDES            │                                   │
│ 🔊 Son               │                                   │
│ ⏱ Pause              │                                   │
│ 🦾 Servo             │                                   │
│ 🚗 Propulsion        │                                   │
│ 💡 Lumières          │                                   │
│ 🔁 Dôme              │                                   │
│ 📋 Sous-séquence     │                                   │
└──────────────────────┴───────────────────────────────────┘
│ Status: EN COURS — étape 3/6 · servo body_panel_2 open   │
└──────────────────────────────────────────────────────────┘
```

---

## Command Palette

Each drag-and-drop block maps to one `.scr` command line:

| Block | Icon | .scr output | Parameters |
|-------|------|-------------|------------|
| Son | 🔊 | `sound,NAME` or `sound,RANDOM,cat` | fichier ou random+catégorie |
| Pause | ⏱ | `sleep,N` or `sleep,random,min,max` | secondes fixes ou random |
| Servo | 🦾 | `servo,name,open[,angle,speed]` | panneau, action, angle optionnel, vitesse optionnelle |
| Propulsion | 🚗 | `motion,left,right,duration` | gauche, droite (-1..1), durée ms |
| Lumières | 💡 | `teeces,mode[,arg]` | random/leia/off/text/psi |
| Dôme | 🔁 | `dome,turn,speed` or `dome,stop` | vitesse ou stop |
| Sous-séquence | 📋 | `script,name` | nom d'une séquence existante |

### Step JSON format (in-memory only, not stored)

```json
{ "cmd": "servo",  "args": ["body_panel_1", "open", "110", "4"] }
{ "cmd": "sound",  "args": ["RANDOM", "happy"] }
{ "cmd": "sleep",  "args": ["0.5"] }
{ "cmd": "script", "args": ["Bras-Extension_retract"] }
```

`save` endpoint serialises to CSV lines: `servo,body_panel_1,open,110,4\n`

---

## Step Canvas

- Vertical list, each step is a draggable row (`⋮⋮` handle on the right)
- SortableJS (bundled at `master/static/vendor/sortable.min.js` v1.15.3) handles reordering
- Click **✏️** on a step → inline edit form expands below (no modal)
- Click **🗑** → remove step
- **Sub-sequence block** shows a collapsible preview of its steps (read-only, loaded from `GET /scripts/get`)
- Drop zone at the bottom: drag from palette or from sub-sequence list

---

## Sequence List (left panel)

- Loaded from `GET /scripts/list` which now includes `is_builtin` per entry
- **Built-in** (`is_builtin: true`) shown with lock icon 🔒 — opens read-only, editor shows "DUPLIQUER POUR MODIFIER" banner
- **Custom** shown normally — fully editable
- **+ Nouvelle** button: prompt for name → validates name → creates empty canvas
- Click sequence name → loads it in canvas (`GET /scripts/get?name=xxx`)

---

## Top Bar

### Name field

- Editable text input, validated on blur
- **Valid name pattern:** `^[a-zA-Z0-9_\-]+$` (alphanumeric, underscore, hyphen — no spaces, slashes, dots)
- Max length: 64 characters
- Filename on disk: `{name}.scr`
- Rename = `POST /scripts/rename` — **blocked (409) if the sequence is currently running**

### Test buttons

| Button | Behaviour |
|--------|-----------|
| ▶ TESTER | `POST /scripts/run {"name":"…","loop":false,"skip_motion":true}` — motion commands silently skipped |
| ▶ TESTER + 🚗 | `POST /scripts/run {"name":"…","loop":false}` — full execution |
| ⏹ STOP | `POST /scripts/stop_all` — cuts all running sequences immediately |

- Status strip polls `GET /scripts/running` every 500ms
- Response now includes `step_index`, `step_total`, `current_cmd` fields (see API section)

### Save / Duplicate / Delete

- **💾 SAUVEGARDER**: `POST /scripts/save` → serialised to `.scr`
- **📋 DUPLIQUER**: opens name prompt → validates → saves copy → loads copy in editor
- **🗑 SUPPRIMER**: confirm dialog → `POST /scripts/delete` — **blocked (403) if `is_builtin`**

---

## New and Modified API Endpoints

### New endpoints in `master/api/script_bp.py`

```
GET  /scripts/get?name=xxx
  → 200: {"name":"xxx","is_builtin":true,"steps":[{"cmd":"servo","args":["dome_panel_1","open"]},...]}
  → 404: {"error":"not found"}

POST /scripts/save   {"name":"xxx","steps":[...]}
  → 200: {"status":"ok"}
  → 400: {"error":"invalid name"} if name fails pattern
  → 400: {"error":"empty sequence"}

POST /scripts/delete {"name":"xxx"}
  → 200: {"status":"ok"}
  → 403: {"error":"built-in sequence cannot be deleted"}
  → 404: {"error":"not found"}

POST /scripts/rename {"old":"xxx","new":"yyy"}
  → 200: {"status":"ok"}
  → 400: {"error":"invalid name"}
  → 409: {"error":"sequence is running"}
  → 404: {"error":"not found"}
```

### Modified: `GET /scripts/list`

Now returns `is_builtin` per entry:

```json
{
  "scripts": [
    {"name": "celebrate", "is_builtin": true},
    {"name": "Bras-Extension_retract", "is_builtin": false}
  ]
}
```

**Built-in detection:** `git ls-files --error-unmatch master/sequences/{name}.scr` — exit 0 = built-in, exit non-zero = custom.

### Modified: `GET /scripts/running`

Now returns step progress:

```json
{
  "running": [
    {
      "id": 3,
      "name": "Bras-Extension_retract",
      "step_index": 2,
      "step_total": 6,
      "current_cmd": "servo,body_panel_2,open"
    }
  ]
}
```

### Modified: `POST /scripts/run`

New optional field `skip_motion` (default `false`):

```json
{"name": "celebrate", "loop": false, "skip_motion": true}
```

---

## Script Engine Changes (`master/script_engine.py`)

### 1. `_run_file` refactor

Extract the step-execution loop from `_ScriptRunner.run()` into a method on `_ScriptRunner`:

```python
def _run_file(self, path: Path, stop_event: threading.Event):
    """Execute all commands in a .scr file. Respects stop_event."""
    with open(path) as f:
        for line in f:
            if stop_event.is_set(): return
            row = [c.strip() for c in line.split(',')]
            if not row or row[0].startswith('#'): continue
            self._engine.execute_command(row, stop_event, skip_motion=self._skip_motion)
```

The existing `run()` method on `_ScriptRunner` calls `self._run_file(self._path, self._stop_event)`.

### 2. `script,name` sub-sequence command

Dispatched inside `_ScriptRunner._run_file()` **before** calling `execute_command`, since `self` is the runner and `_run_file` is already in scope:

```python
# Inside _ScriptRunner._run_file(), per-line loop:
if row[0] == 'script':
    sub_name = row[1]
    sub_path = Path(self._engine.sequences_dir) / f"{sub_name}.scr"
    if sub_path.exists():
        self._run_file(sub_path, stop_event)   # recursive, inline, blocking
    else:
        logging.warning(f"script: sub-sequence '{sub_name}' not found, skipping")
    continue   # don't pass to execute_command
self._engine.execute_command(row, stop_event, skip_motion=self._skip_motion)
```

This keeps `execute_command` on `ScriptEngine` clean (no runner reference needed).

**Note on circular sub-sequences:** No guard in v1. A circular reference (A calls B calls A) will cause infinite recursion until `stop_event` is set or the Python stack limit is hit. User responsibility. The `⏹ STOP` button sets `stop_event` and will break the loop.

### 3. `skip_motion` flag

- `ScriptEngine.run()` accepts `skip_motion=False` kwarg, passes it to `_ScriptRunner`
- `_ScriptRunner` stores `self._skip_motion`
- `execute_command()` accepts `skip_motion=False` kwarg
- In `_cmd_motion()`: if `skip_motion` is `True`, log "motion skipped (test mode)" and return immediately

### 4. Step progress tracking

`_ScriptRunner` tracks:

```python
self.step_index = 0    # current step (0-based)
self.step_total = 0    # total steps in file (counted on load)
self.current_cmd = ""  # last executed command line (raw string)
```

`step_total` is counted by reading the file once before execution (count non-comment non-empty lines). Updated before each `execute_command` call. `ScriptEngine.list_running()` reads these fields from each active runner.

---

## Sequence Persistence / Backup in update.sh

**Backup runs BEFORE `git pull`. Restore runs AFTER.**

```bash
# Step 0: Backup sequences BEFORE git pull (custom sequences survive update)
mkdir -p /home/artoo/sequences_backup
rsync -a /home/artoo/r2d2/master/sequences/ /home/artoo/sequences_backup/

# Step 1: Git pull (may update built-in sequences, won't touch untracked files)
git pull

# After pull: restore custom sequences
# --ignore-existing: built-ins get updated from git, customs are preserved
# Conflict rule: if git introduces a file with same name as a custom, custom wins
rsync -a --ignore-existing /home/artoo/sequences_backup/ /home/artoo/r2d2/master/sequences/
```

---

## Servo Naming

For v1: servo names are raw (`body_panel_1`, `dome_panel_1`, etc.) — the editor shows them as-is in dropdowns. A future `servo_names.json` config will map raw names to friendly names ("Pie Panel 1", "Dome Panel 1"). The data model is forwards-compatible: stored `.scr` files always use raw names.

---

## Out of Scope (v1)

- Servo friendly name config UI (added later with naming system)
- Loop control per-step
- Parallel step execution
- Mobile/Android editor
- Version history of sequences
- Recursion guard for sub-sequences (user uses ⏹ STOP if needed)
- Conflict detection when file changed externally while editor is open (last-write-wins)
