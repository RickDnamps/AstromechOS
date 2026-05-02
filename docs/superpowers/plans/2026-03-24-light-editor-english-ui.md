# Light Editor + Full English UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Light sequence editor (Teeces animations) to the Editor tab, expose all JawaLite T-codes, add `lseq` parallel command in regular sequences, and translate the entire UI to English.

**Architecture:** The Editor tab gains a type switcher (Sequences | Light). Light sequences are `.lseq` CSV files in `master/light_sequences/` — same format as `.scr` but Teeces+sleep only. A new `LightEditor` JS class mirrors `SequenceEditor`. Backend: new `light_bp.py` Flask blueprint. The `lseq` step in regular `.scr` sequences fires a background thread (parallel, like sound). All French strings in `index.html` and `app.js` are replaced with English.

**Tech Stack:** Python 3.10+, Flask blueprints, threading, JawaLite serial protocol, vanilla JS ES6 classes, SortableJS 1.15.3

---

## File Map

| File | Change |
|---|---|
| `master/templates/index.html` | English translation + editor type switcher + light editor HTML panel |
| `master/static/js/app.js` | English translation + `LightEditor` class + type switcher logic |
| `master/static/css/style.css` | Light editor palette item colors (teeces purple theme) |
| `master/teeces_controller.py` | Add `animation(mode)` and `send_raw(cmd)` methods |
| `master/api/teeces_bp.py` | Add `POST /teeces/animation` and `POST /teeces/raw` endpoints |
| `master/api/light_bp.py` | **NEW** — CRUD + run/stop for `.lseq` files |
| `master/flask_app.py` | Register `light_bp` |
| `master/script_engine.py` | Add `lseq` parallel command + `teeces,anim,N` + `teeces,raw,CMD` |
| `master/light_sequences/.gitkeep` | **NEW** — empty dir tracked by git |
| `android/app/src/main/assets/js/app.js` | Mirror of master/static/js/app.js |
| `android/app/src/main/assets/css/style.css` | Mirror of master/static/css/style.css |

---

## Task 1: English Translation

**Files:**
- Modify: `master/templates/index.html`
- Modify: `master/static/js/app.js`

- [ ] **Step 1: Translate index.html French strings**

Replace every French string in `master/templates/index.html`:

```
"ÉDITEUR"                                    → "EDITOR"
"Entrez le mot de passe pour accéder aux onglets SERVO / VESC / CONFIG / ÉDITEUR"
  → "Enter password to access SERVO / VESC / CONFIG / EDITOR tabs"
"Mot de passe" (placeholder)                 → "Password"
"ANNULER"                                    → "CANCEL"
"ACCÈS"                                      → "ACCESS"
"Mot de passe incorrect"                     → "Incorrect password"
"PASSER EN CHILD LOCK"                       → "ENABLE CHILD LOCK"
"COMMANDES"                                  → "COMMANDS"
"🔊 Son"                                     → "🔊 Sound"
"⏱ Pause"                                    → "⏱ Wait"
"💡 Lumières"                                → "💡 Lights"
"🔁 Dôme"                                    → "🔁 Dome"
"📋 Sous-séquence"                           → "📋 Sub-sequence"
"SÉQUENCES" (section label)                  → "SEQUENCES"
"+ Nouvelle"                                 → "+ New"
"▶ TESTER"                                   → "▶ TEST"
"▶ TESTER + 🚗"                              → "▶ TEST + 🚗"
"🗑 SUPPRIMER"                               → "🗑 DELETE"
"📋 DUPLIQUER"                               → "📋 DUPLICATE"
"💾 SAUVEGARDER"                             → "💾 SAVE"
"ÉTAPES"                                     → "STEPS"
"🔒 SÉQUENCE INTÉGRÉE — DUPLIQUER POUR MODIFIER"
  → "🔒 BUILT-IN SEQUENCE — DUPLICATE TO EDIT"
"↓ GLISSER UNE COMMANDE OU SOUS-SÉQUENCE ICI"
  → "↓ DRAG A COMMAND HERE"
"Séquences lumineuses programmées — à venir." (whole section placeholder)
  → remove this placeholder (Task 5 adds real content)
"Panneaux dôme" (BT config table)            → "Dome panels"
"Panneaux body"                              → "Body panels"
"Mode verrouillage (Kids / Child Lock)"      → "Lock mode (Kids / Child Lock)"
"Accès admin"                                → "Admin access"
"Générique / Autre" (controller option)      → "Generic / Other"
"Séquences lumineuses programmées — à venir." → remove placeholder
```

- [ ] **Step 2: Translate app.js French strings**

Replace all French user-facing strings:

```js
// LockManager
'Mode normal rétabli'               → 'Normal mode restored'
'Kids Mode activé — vitesse limitée' → 'Kids Mode — speed limited'
'Child Lock — déplacement bloqué'    → 'Child Lock — movement blocked'

// AdminGuard  (in _PROTECTED toast or alerts — check all alert/toast calls)

// SequenceEditor alerts/prompts
"Créez ou ouvrez une séquence d'abord."          → "Create or open a sequence first."
`Séquence "${name}" introuvable`                  → `Sequence "${name}" not found`
'Nom de la nouvelle séquence (lettres, chiffres, - et _ uniquement) :'
  → 'New sequence name (letters, digits, - and _ only):'
'Nom invalide. Utilisez lettres, chiffres, - et _ uniquement (max 64 caractères).'
  → 'Invalid name. Use letters, digits, - and _ only (max 64 chars).'
'Séquence intégrée — dupliquez-la pour modifier.' → 'Built-in sequence — duplicate to edit.'
'La séquence est vide.'              → 'Sequence is empty.'
`Erreur: ${err.error}`               → `Error: ${err.error}`
'Erreur réseau lors de la sauvegarde.' → 'Network error while saving.'
'Séquence intégrée — impossible de supprimer.' → 'Built-in sequence — cannot delete.'
`Supprimer "${this._openName}" ? Cette action est irréversible.`
  → `Delete "${this._openName}"? This cannot be undone.`
'Erreur lors de la duplication.'     → 'Error while duplicating.'
'Erreur réseau.'                     → 'Network error.'
'Nom pour la copie :'                → 'Name for the copy:'
`ÉTAPES — ${name} (nouveau)`         → `STEPS — ${name} (new)`
`ÉTAPES — ${name}`                   → `STEPS — ${name}`
'ÉTAPES'                             → 'STEPS'

// _stepFields labels
'Mode'        → 'Mode'  (already English)
'Catégorie'   → 'Category'
'Son'         → 'Sound'
'Aléatoire'   → 'Random'
'Durée (s) / Min' → 'Duration (s) / Min'
'Max (s)'         → 'Max (s)'
'Panneau'         → 'Panel'
'Action'          → 'Action'
'Angle (optionnel)' → 'Angle (optional)'
'Vitesse (1-10)'  → 'Speed (1-10)'
'Durée ms'        → 'Duration ms'
'Sous-séquence'   → 'Sub-sequence'

// canvas label when opening builtin
'ÉTAPES — ...' → 'STEPS — ...'
```

- [ ] **Step 3: Verify no French remains visible to user**

Search for remaining French:
```bash
grep -n "é\|è\|à\|ê\|â\|ô\|û\|î\|ï\|ç\|œ" master/templates/index.html | grep -v "<!--\|class=\|id=\|href=\|url_for\|placeholder=\".*\"\|title=\""
grep -n "é\|è\|à\|ê\|ç" master/static/js/app.js | grep -v "//\|console\."
```
Fix any remaining visible French strings found.

- [ ] **Step 4: Sync to Android assets**

```bash
cp master/static/js/app.js android/app/src/main/assets/js/app.js
cp master/static/css/style.css android/app/src/main/assets/css/style.css
```

- [ ] **Step 5: Commit**

```bash
git add master/templates/index.html master/static/js/app.js android/app/src/main/assets/js/app.js
git commit -m "feat: translate full UI to English"
```

---

## Task 2: TeecesController — All T-Codes + API

**Files:**
- Modify: `master/teeces_controller.py`
- Modify: `master/api/teeces_bp.py`
- Modify: `master/script_engine.py`

### TeecesController additions

- [ ] **Step 1: Add `ANIMATIONS` dict + `animation()` + `send_raw()` to teeces_controller.py**

After the existing `show_version` method, add:

```python
# All known JawaLite T-code animations
ANIMATIONS: dict[int, str] = {
    1:  'Random',
    2:  'Flash',
    3:  'Alarm',
    4:  'Short Circuit',
    5:  'Scream',
    6:  'Leia Message',
    7:  'I Heart U',
    8:  'Panel Sweep',
    9:  'Pulse Monitor',
    10: 'Star Wars Scroll',
    11: 'Imperial March',
    12: 'Disco (timed)',
    13: 'Disco',
    14: 'Rebel Symbol',
    15: 'Knight Rider',
    16: 'Test White',
    17: 'Red On',
    18: 'Green On',
    19: 'Lightsaber',
    20: 'Off',
    21: 'VU Meter (timed)',
    92: 'VU Meter',
}

def animation(self, mode: int) -> bool:
    """Trigger a named animation by T-code. Ex: animation(11) → Imperial March."""
    return self.send_command(f"0T{int(mode)}\r")

def send_raw(self, cmd: str) -> bool:
    """Send a raw JawaLite command string. Ex: '1MHELLO\\r'"""
    if not cmd.endswith('\r'):
        cmd = cmd + '\r'
    return self.send_command(cmd)
```

- [ ] **Step 2: Add endpoints to teeces_bp.py**

After the `teeces_psi` route, add:

```python
@teeces_bp.get('/animations')
def teeces_animations():
    """List all known T-code animations."""
    from master.teeces_controller import TeecesController
    return jsonify({
        'animations': [
            {'mode': k, 'name': v}
            for k, v in TeecesController.ANIMATIONS.items()
        ]
    })


@teeces_bp.post('/animation')
def teeces_animation():
    """Trigger a T-code animation. Body: {"mode": 11}"""
    global _mode
    body = request.get_json(silent=True) or {}
    mode = int(body.get('mode', 1))
    _mode = f'anim:{mode}'
    if reg.teeces:
        reg.teeces.animation(mode)
    return jsonify({'status': 'ok', 'mode': mode,
                    'name': reg.teeces.ANIMATIONS.get(mode, f'T{mode}') if reg.teeces else ''})


@teeces_bp.post('/raw')
def teeces_raw():
    """Send raw JawaLite command. Body: {"cmd": "0T5"}"""
    body = request.get_json(silent=True) or {}
    cmd = body.get('cmd', '').strip()
    if not cmd:
        return jsonify({'error': 'field "cmd" required'}), 400
    if reg.teeces:
        reg.teeces.send_raw(cmd)
    return jsonify({'status': 'ok', 'cmd': cmd})
```

- [ ] **Step 3: Update `_cmd_teeces` in script_engine.py**

In the `_cmd_teeces` method, add two new branches before `return`:

```python
def _cmd_teeces(self, row: list[str]) -> None:
    if not self._teeces:
        return
    action = row[1].lower()
    if action == 'random':
        self._teeces.random_mode()
    elif action == 'leia':
        self._teeces.leia_mode()
    elif action == 'off':
        self._teeces.all_off()
    elif action == 'text':
        self._teeces.fld_text(row[2] if len(row) > 2 else '')
    elif action == 'psi':
        mode = int(row[2]) if len(row) > 2 else 0
        if mode == 0:
            self._teeces.psi_random()
        else:
            self._teeces.psi_mode(mode)
    elif action == 'anim':
        mode = int(row[2]) if len(row) > 2 else 1
        self._teeces.animation(mode)
    elif action == 'raw':
        self._teeces.send_raw(row[2] if len(row) > 2 else '')
```

- [ ] **Step 4: Test via curl**

```bash
# On the Pi:
curl -s -X POST http://localhost:5000/teeces/animation -H "Content-Type: application/json" -d '{"mode": 11}'
# Expected: {"status":"ok","mode":11,"name":"Imperial March"}

curl -s http://localhost:5000/teeces/animations | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d['animations']), 'animations')"
# Expected: 22 animations
```

- [ ] **Step 5: Commit**

```bash
git add master/teeces_controller.py master/api/teeces_bp.py master/script_engine.py
git commit -m "feat: TeecesController — all 22 T-code animations + raw JawaLite API"
```

---

## Task 3: Light Sequence Backend

**Files:**
- Create: `master/light_sequences/.gitkeep`
- Create: `master/api/light_bp.py`
- Modify: `master/flask_app.py`

- [ ] **Step 1: Create light_sequences directory**

```bash
mkdir -p master/light_sequences
touch master/light_sequences/.gitkeep
```

- [ ] **Step 2: Create master/api/light_bp.py**

Model exactly after `script_bp.py` but for `.lseq` files. The blueprint handles list/get/save/delete/run/stop for light sequences. Light sequences are NOT tracked by git (no builtin concept — all are user-created).

```python
"""
Blueprint API Light Sequences — R2-D2 Light Show.
CRUD + run/stop for .lseq files (Teeces/sleep sequences).

Endpoints:
  GET  /light/list              → list of .lseq files
  GET  /light/get               ?name=xxx → steps
  POST /light/save              {"name": str, "steps": [{cmd, args}]}
  POST /light/delete            {"name": str}
  POST /light/run               {"name": str, "loop": false}
  POST /light/stop              {"id": int}
  POST /light/stop_all
"""
import logging
import re
from pathlib import Path

from flask import Blueprint, request, jsonify
import master.registry as reg

log = logging.getLogger(__name__)

light_bp = Blueprint('light', __name__, url_prefix='/light')

LIGHT_DIR = Path(__file__).parent.parent / 'light_sequences'
NAME_RE   = re.compile(r'^[a-zA-Z0-9_\-]{1,64}$')


def _valid(name: str) -> bool:
    return bool(NAME_RE.match(name))


def _parse_lseq(path: Path) -> list[dict]:
    steps = []
    try:
        with open(path, encoding='utf-8') as f:
            for line in f:
                row = [c.strip() for c in line.split(',')]
                if not row or not row[0] or row[0].startswith('#'):
                    continue
                steps.append({'cmd': row[0], 'args': row[1:]})
    except Exception:
        pass
    return steps


@light_bp.get('/list')
def light_list():
    LIGHT_DIR.mkdir(exist_ok=True)
    names = sorted(p.stem for p in LIGHT_DIR.glob('*.lseq'))
    return jsonify({'sequences': names})


@light_bp.get('/get')
def light_get():
    name = request.args.get('name', '').strip()
    if not name or not _valid(name):
        return jsonify({'error': 'invalid name'}), 400
    path = LIGHT_DIR / f'{name}.lseq'
    if not path.is_file():
        return jsonify({'error': 'not found'}), 404
    return jsonify({'name': name, 'steps': _parse_lseq(path)})


@light_bp.post('/save')
def light_save():
    body  = request.get_json(silent=True) or {}
    name  = body.get('name', '').strip()
    steps = body.get('steps', [])
    if not _valid(name):
        return jsonify({'error': 'invalid name'}), 400
    if not steps:
        return jsonify({'error': 'empty sequence'}), 400
    LIGHT_DIR.mkdir(exist_ok=True)
    path  = LIGHT_DIR / f'{name}.lseq'
    lines = []
    for step in steps:
        cmd  = step.get('cmd', '')
        args = [str(a) for a in step.get('args', []) if str(a)]
        if cmd:
            lines.append(','.join([cmd] + args))
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    log.info('Light sequence saved: %s (%d steps)', name, len(lines))
    return jsonify({'status': 'ok', 'name': name})


@light_bp.post('/delete')
def light_delete():
    body = request.get_json(silent=True) or {}
    name = body.get('name', '').strip()
    if not _valid(name):
        return jsonify({'error': 'invalid name'}), 400
    path = LIGHT_DIR / f'{name}.lseq'
    if not path.is_file():
        return jsonify({'error': 'not found'}), 404
    path.unlink()
    return jsonify({'status': 'ok'})


@light_bp.post('/run')
def light_run():
    body = request.get_json(silent=True) or {}
    name = body.get('name', '').strip()
    loop = bool(body.get('loop', False))
    if not name:
        return jsonify({'error': 'field "name" required'}), 400
    if not reg.engine:
        return jsonify({'error': 'ScriptEngine not initialized'}), 503
    script_id = reg.engine.run_light(name, loop=loop)
    if script_id is None:
        return jsonify({'error': f'Light sequence "{name}" not found'}), 404
    return jsonify({'status': 'ok', 'id': script_id, 'name': name})


@light_bp.post('/stop')
def light_stop():
    body = request.get_json(silent=True) or {}
    sid  = body.get('id')
    if sid is None:
        return jsonify({'error': 'field "id" required'}), 400
    if reg.engine:
        ok = reg.engine.stop(int(sid))
        return jsonify({'status': 'ok' if ok else 'not_found'})
    return jsonify({'error': 'ScriptEngine not initialized'}), 503


@light_bp.post('/stop_all')
def light_stop_all():
    """Stop only light sequences — does NOT stop regular sequences or audio."""
    if reg.engine:
        reg.engine.stop_light_all()
    return jsonify({'status': 'ok'})
```

- [ ] **Step 3: Register light_bp in flask_app.py**

In `create_app()`, after the existing blueprint imports:
```python
from master.api.light_bp import light_bp
# ...
app.register_blueprint(light_bp)
```

- [ ] **Step 4: Test via curl (after Task 4 adds run_light)**

```bash
curl -s -X POST http://localhost:5000/light/save \
  -H "Content-Type: application/json" \
  -d '{"name":"test_light","steps":[{"cmd":"teeces","args":["anim","11"]},{"cmd":"sleep","args":["fixed","2.0"]},{"cmd":"teeces","args":["random"]}]}'
# Expected: {"status":"ok","name":"test_light"}

curl -s http://localhost:5000/light/list
# Expected: {"sequences":["test_light"]}

curl -s "http://localhost:5000/light/get?name=test_light"
# Expected: {"name":"test_light","steps":[...]}
```

- [ ] **Step 5: Note — Tasks 3 and 4 must be committed together before deploying**

`light_bp.py` calls `reg.engine.run_light()` and `reg.engine.stop_light_all()` which are added in Task 4. Deploy Task 3 + Task 4 commits together to avoid `AttributeError` at runtime.

- [ ] **Step 6: Commit**

```bash
git add master/light_sequences/.gitkeep master/api/light_bp.py master/flask_app.py
git commit -m "feat: light sequence backend — CRUD + run/stop API (/light/*)"
```

---

## Task 4: ScriptEngine — `lseq` Parallel Command + `run_light`

**Files:**
- Modify: `master/script_engine.py`

This task adds two things:
1. `run_light(name, loop)` — runs a `.lseq` file via the existing `_ScriptRunner` (teeces+sleep only, same engine)
2. `_cmd_lseq(row)` — fire & forget: starts a light sequence in background without blocking the main sequence

- [ ] **Step 1: Add LIGHT_DIR constant, `run_light`, and `stop_light_all` to ScriptEngine**

After the `SCRIPTS_DIR` constant at top of file:
```python
SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), 'sequences')
LIGHT_DIR   = os.path.join(os.path.dirname(__file__), 'light_sequences')
```

In `ScriptEngine.__init__`, add `self._light_ids: set[int] = set()` alongside `self._running`.

After the existing `run()` method, add `run_light()` and `stop_light_all()`.
**DO NOT modify `run()` — leave it exactly as-is.**

```python
def run_light(self, name: str, loop: bool = False) -> int | None:
    """
    Run a .lseq light sequence in parallel (does NOT stop other sequences,
    does NOT reset servos — light runs alongside regular sequences).
    """
    path = os.path.join(LIGHT_DIR, f'{name}.lseq')
    if not os.path.isfile(path):
        log.warning('run_light: not found: %s', path)
        return None
    with self._lock:
        script_id     = self._next_id
        self._next_id += 1
    runner = _ScriptRunner(
        script_id=script_id,
        name=name,
        path=path,
        loop=loop,
        engine=self,
        on_done=self._on_done,
        skip_motion=True,   # light sequences never drive motors
    )
    with self._lock:
        self._running[script_id] = runner
        self._light_ids.add(script_id)
    runner.start()
    log.info('Light sequence started: %s (id=%d)', name, script_id)
    return script_id

def stop_light_all(self) -> None:
    """Stop only light sequences — leaves regular sequences and audio untouched."""
    with self._lock:
        ids_to_stop = list(self._light_ids)
        self._light_ids.clear()
        runners = [self._running.pop(sid, None) for sid in ids_to_stop]
    for runner in runners:
        if runner:
            runner.stop()
    log.info('All light sequences stopped')
```

Also update `_on_done` (called when a runner finishes) to clean `_light_ids`:

Find the existing `_on_done` method and add one line:
```python
def _on_done(self, script_id: int) -> None:
    with self._lock:
        self._running.pop(script_id, None)
        self._light_ids.discard(script_id)   # ← add this line
```

- [ ] **Step 2: Add `_cmd_lseq` to ScriptEngine**

In `execute_command`, add after the `elif cmd == 'teeces':` branch:

```python
elif cmd == 'lseq':
    self._cmd_lseq(row)
```

Add the method:
```python
def _cmd_lseq(self, row: list[str]) -> None:
    """Fire-and-forget: start a light sequence in background (parallel like sound)."""
    if len(row) < 2 or not row[1]:
        log.warning('lseq: missing name')
        return
    name = row[1].strip()
    # Run in a daemon thread so the main sequence continues immediately
    t = threading.Thread(
        target=self.run_light,
        args=(name,),
        daemon=True,
        name=f'lseq-{name}',
    )
    t.start()
    log.debug('lseq: launched %s in background', name)
```

- [ ] **Step 3: Test via curl**

First deploy (Task 5 does this), then:
```bash
# Save a test light sequence
curl -s -X POST http://localhost:5000/light/save \
  -H "Content-Type: application/json" \
  -d '{"name":"disco","steps":[{"cmd":"teeces","args":["anim","13"]},{"cmd":"sleep","args":["fixed","5.0"]},{"cmd":"teeces","args":["random"]}]}'

# Run it
curl -s -X POST http://localhost:5000/light/run \
  -H "Content-Type: application/json" \
  -d '{"name":"disco"}'
# Expected: {"status":"ok","id":1,"name":"disco"}
```

- [ ] **Step 4: Update script_engine.py docstring** to document the new commands:

Add to the format docstring at top of file:
```
  lseq,name                    → run light sequence in parallel (fire & forget)
  teeces,anim,11               → trigger T-code animation (Imperial March)
  teeces,raw,0T5               → send raw JawaLite command
```

- [ ] **Step 5: Commit**

```bash
git add master/script_engine.py
git commit -m "feat: ScriptEngine — lseq parallel command + run_light + teeces anim/raw"
```

---

## Task 5: Light Editor Frontend

**Files:**
- Modify: `master/templates/index.html`
- Modify: `master/static/js/app.js`
- Modify: `master/static/css/style.css`

This task adds the type switcher to the Editor tab and a new `LightEditor` JS class.

### 5a — HTML changes

- [ ] **Step 1: Add type switcher to editor tab header in index.html**

The editor tab toolbar (around line 395–430) currently starts with name input and action buttons. Add a type switcher row BEFORE the existing toolbar content:

```html
<!-- Editor type switcher -->
<div id="editor-type-bar" style="display:flex;align-items:center;gap:4px;padding:6px 14px 0;background:#060e1a;border-bottom:1px solid #0d1e35">
  <button class="editor-type-btn active" data-type="sequence" onclick="editorSwitchType('sequence')">📋 SEQUENCES</button>
  <button class="editor-type-btn" data-type="light" onclick="editorSwitchType('light')">💡 LIGHT</button>
</div>

<!-- Sequence editor panel (existing content, wrapped in a div) -->
<div id="editor-panel-sequence">
  <!-- existing toolbar + status strip + two-column layout -->
</div>

<!-- Light editor panel (new) -->
<div id="editor-panel-light" style="display:none">
  <!-- toolbar -->
  <div style="display:flex;align-items:center;gap:6px;padding:6px 14px;background:#060e1a;border-bottom:1px solid #0d1e35;flex-wrap:wrap">
    <input type="text" id="light-name-input" class="editor-name-input" placeholder="light sequence name…" readonly>
    <div style="width:1px;height:22px;background:#1e3a5f;margin:0 4px"></div>
    <div style="display:flex;align-items:center;gap:6px">
      <button id="light-btn-test" class="btn-editor-action" data-color="green" onclick="lightEditor.runTest()">▶ TEST</button>
    </div>
    <div style="width:1px;height:22px;background:#1e3a5f;margin:0 4px"></div>
    <button id="light-btn-stop" class="btn-editor-action" data-color="red" onclick="lightEditor.stopAll()">⏹ STOP</button>
    <div style="flex:1"></div>
    <div style="display:flex;align-items:center;gap:6px">
      <button id="light-btn-delete" class="btn-editor-action" data-color="dim" onclick="lightEditor.deleteSequence()">🗑 DELETE</button>
      <button id="light-btn-duplicate" class="btn-editor-action" data-color="blue" onclick="lightEditor.duplicateSequence()">📋 DUPLICATE</button>
      <button id="light-btn-save" class="btn-editor-action" data-color="solid-blue" onclick="lightEditor.saveSequence()">💾 SAVE</button>
    </div>
  </div>
  <!-- status strip -->
  <div style="padding:5px 14px;background:#060e1a;border-bottom:1px solid #0d1e35;display:flex;align-items:center;gap:8px;min-height:24px">
    <span id="light-status-dot" style="width:7px;height:7px;border-radius:50%;background:#2a4a6a;display:inline-block"></span>
    <span id="light-status-text" style="font-size:8px;color:#2a4a6a;letter-spacing:.1em">—</span>
  </div>
  <!-- two-column layout -->
  <div style="display:grid;grid-template-columns:190px 1fr;min-height:calc(100vh - 210px)">
    <!-- Left: animation palette + sequence list -->
    <div id="light-left" style="background:#070f1c;border-right:1px solid #1e3a5f;overflow-y:auto">
      <div style="padding:10px 8px">
        <div class="editor-section-label">ANIMATIONS</div>
        <div id="light-palette" style="display:flex;flex-direction:column;gap:5px">
          <!-- populated by LightEditor._initPalette() -->
        </div>
      </div>
      <div style="padding:0 8px 10px">
        <div class="editor-section-label" style="border-top:1px solid #1e3a5f;padding-top:10px">LIGHT SEQUENCES</div>
        <button id="light-btn-new" class="btn-editor-new" onclick="lightEditor.newSequence()">+ New</button>
        <div id="light-seq-list" style="display:flex;flex-direction:column;gap:3px;margin-top:6px"></div>
      </div>
    </div>
    <!-- Right: canvas -->
    <div id="light-canvas-wrap" style="padding:12px 14px;overflow-y:auto;min-height:100%">
      <div id="light-canvas-label" style="font-size:8px;color:#4a6a8a;letter-spacing:.12em;margin-bottom:10px">STEPS</div>
      <div id="light-steps" style="display:flex;flex-direction:column;gap:6px"></div>
      <div id="light-dropzone" style="margin-top:8px;border:2px dashed #1e3a5f;border-radius:5px;padding:12px;text-align:center;color:#2a4a6a;font-size:9px;letter-spacing:.1em">
        ↓ DRAG AN ANIMATION HERE
      </div>
    </div>
  </div>
</div>
```

- [ ] **Step 2: Wrap existing sequence editor content**

The existing sequence editor content (toolbar div + status strip div + two-column grid div inside `#tab-editor`) must be wrapped in `<div id="editor-panel-sequence">…</div>`.

- [ ] **Step 3: Add CSS for editor type buttons in style.css**

```css
.editor-type-btn {
  font-size: 9px;
  letter-spacing: .1em;
  padding: 4px 12px;
  border-radius: 4px;
  border: 1px solid #1e3a5f;
  background: transparent;
  color: #4a6a8a;
  cursor: pointer;
  transition: all .15s;
}
.editor-type-btn.active {
  background: #001a2e;
  border-color: #00aaff;
  color: #00aaff;
}
.editor-type-btn:hover { filter: brightness(1.2); }
```

### 5b — JavaScript: `LightEditor` class

- [ ] **Step 4: Add `LIGHT_ANIMATIONS` constant and `LightEditor` class to app.js**

Add after the `SequenceEditor` class (around end of file, before the `const seqEditor = ...` instantiation):

```js
// ─── Light animations registry ───────────────────────────────────────────────
const LIGHT_ANIMATIONS = [
  { mode:  1, label: 'Random',           icon: '✨', dur: '∞' },
  { mode:  2, label: 'Flash',            icon: '⚡', dur: '4s' },
  { mode:  3, label: 'Alarm',            icon: '🚨', dur: '4s' },
  { mode:  4, label: 'Short Circuit',    icon: '💥', dur: '10s' },
  { mode:  5, label: 'Scream',           icon: '😱', dur: '4s' },
  { mode:  6, label: 'Leia',             icon: '🌀', dur: '34s' },
  { mode:  7, label: 'I ♥ U',           icon: '❤️', dur: '10s' },
  { mode:  8, label: 'Panel Sweep',      icon: '↔️', dur: '7s' },
  { mode:  9, label: 'Pulse Monitor',    icon: '💓', dur: '∞' },
  { mode: 10, label: 'Star Wars Scroll', icon: '⭐', dur: '15s' },
  { mode: 11, label: 'Imperial March',   icon: '🎵', dur: '47s' },
  { mode: 12, label: 'Disco (timed)',    icon: '🪩', dur: '4s' },
  { mode: 13, label: 'Disco',            icon: '🪩', dur: '∞' },
  { mode: 14, label: 'Rebel Symbol',     icon: '✊', dur: '5s' },
  { mode: 15, label: 'Knight Rider',     icon: '🚗', dur: '20s' },
  { mode: 16, label: 'Test White',       icon: '⬜', dur: '∞' },
  { mode: 17, label: 'Red On',           icon: '🔴', dur: '∞' },
  { mode: 18, label: 'Green On',         icon: '🟢', dur: '∞' },
  { mode: 19, label: 'Lightsaber',       icon: '⚔️', dur: '∞' },
  { mode: 20, label: 'Off',              icon: '⬛', dur: '—' },
  { mode: 21, label: 'VU Meter (timed)', icon: '📊', dur: '4s' },
  { mode: 92, label: 'VU Meter',         icon: '📊', dur: '∞' },
];

// ─── LightEditor ─────────────────────────────────────────────────────────────
class LightEditor {
  constructor() {
    this._sequence   = [];       // [{cmd, args}]
    this._openName   = null;
    this._editingIdx = null;
    this._seqNames   = [];
    this._runId      = null;     // currently running sequence id

    this._nameInput   = el('light-name-input');
    this._canvasLabel = el('light-canvas-label');
    this._steps       = el('light-steps');
    this._dropzone    = el('light-dropzone');
    this._canvasWrap  = el('light-canvas-wrap');

    this._initPalette();
    this._initDrop();
  }

  // ── Palette ────────────────────────────────────────────────────────────────

  _initPalette() {
    const palette = el('light-palette');
    palette.innerHTML = '';

    // Animation items
    LIGHT_ANIMATIONS.forEach(anim => {
      const item = document.createElement('div');
      item.className = 'editor-palette-item light-palette-item';
      item.draggable = true;
      item.dataset.cmd  = 'teeces';
      item.dataset.args = JSON.stringify(['anim', String(anim.mode)]);
      item.innerHTML = `${anim.icon} <span style="flex:1">${anim.label}</span><span style="font-size:8px;color:#4a6a8a">${anim.dur}</span>`;
      item.style.display = 'flex';
      item.style.alignItems = 'center';
      item.style.gap = '4px';

      let _dragged = false;
      item.addEventListener('dragstart', () => { _dragged = true; });
      item.addEventListener('dragend',   () => { setTimeout(() => { _dragged = false; }, 50); });
      item.addEventListener('click', () => {
        if (_dragged) return;
        if (!this._openName) { alert('Create or open a sequence first.'); return; }
        this._addStep('teeces', ['anim', String(anim.mode)]);
      });
      palette.appendChild(item);
    });

    // FLD Text
    const txtItem = document.createElement('div');
    txtItem.className = 'editor-palette-item light-palette-item';
    txtItem.draggable = true;
    txtItem.dataset.cmd  = 'teeces';
    txtItem.dataset.args = JSON.stringify(['text', 'HELLO']);
    txtItem.textContent = '💬 FLD Text';
    let _txtDragged = false;
    txtItem.addEventListener('dragstart', () => { _txtDragged = true; });
    txtItem.addEventListener('dragend',   () => { setTimeout(() => { _txtDragged = false; }, 50); });
    txtItem.addEventListener('click', () => {
      if (_txtDragged) return;
      if (!this._openName) { alert('Create or open a sequence first.'); return; }
      this._addStep('teeces', ['text', 'HELLO']);
    });
    palette.appendChild(txtItem);

    // PSI
    const psiItem = document.createElement('div');
    psiItem.className = 'editor-palette-item light-palette-item';
    psiItem.draggable = true;
    psiItem.dataset.cmd  = 'teeces';
    psiItem.dataset.args = JSON.stringify(['psi', '1']);
    psiItem.textContent = '💠 PSI';
    let _psiDragged = false;
    psiItem.addEventListener('dragstart', () => { _psiDragged = true; });
    psiItem.addEventListener('dragend',   () => { setTimeout(() => { _psiDragged = false; }, 50); });
    psiItem.addEventListener('click', () => {
      if (_psiDragged) return;
      if (!this._openName) { alert('Create or open a sequence first.'); return; }
      this._addStep('teeces', ['psi', '1']);
    });
    palette.appendChild(psiItem);

    // Raw JawaLite
    const rawItem = document.createElement('div');
    rawItem.className = 'editor-palette-item light-palette-item';
    rawItem.draggable = true;
    rawItem.dataset.cmd  = 'teeces';
    rawItem.dataset.args = JSON.stringify(['raw', '0T1']);
    rawItem.textContent = '⚙️ Raw JawaLite';
    let _rawDragged = false;
    rawItem.addEventListener('dragstart', () => { _rawDragged = true; });
    rawItem.addEventListener('dragend',   () => { setTimeout(() => { _rawDragged = false; }, 50); });
    rawItem.addEventListener('click', () => {
      if (_rawDragged) return;
      if (!this._openName) { alert('Create or open a sequence first.'); return; }
      this._addStep('teeces', ['raw', '0T1']);
    });
    palette.appendChild(rawItem);

    // Wait (sleep)
    const waitItem = document.createElement('div');
    waitItem.className = 'editor-palette-item light-palette-item';
    waitItem.draggable = true;
    waitItem.dataset.cmd  = 'sleep';
    waitItem.dataset.args = JSON.stringify(['fixed', '1.0']);
    waitItem.textContent = '⏱ Wait';
    let _waitDragged = false;
    waitItem.addEventListener('dragstart', () => { _waitDragged = true; });
    waitItem.addEventListener('dragend',   () => { setTimeout(() => { _waitDragged = false; }, 50); });
    waitItem.addEventListener('click', () => {
      if (_waitDragged) return;
      if (!this._openName) { alert('Create or open a sequence first.'); return; }
      this._addStep('sleep', ['fixed', '1.0']);
    });
    palette.appendChild(waitItem);
  }

  // ── Drag & drop ────────────────────────────────────────────────────────────

  _initDrop() {
    this._canvasWrap.addEventListener('dragover', e => {
      e.preventDefault();
      this._dropzone.style.borderColor = '#00aaff';
    });
    this._canvasWrap.addEventListener('dragleave', e => {
      if (!this._canvasWrap.contains(e.relatedTarget))
        this._dropzone.style.borderColor = '';
    });
    this._canvasWrap.addEventListener('drop', e => {
      e.preventDefault();
      this._dropzone.style.borderColor = '';
      const cmd  = e.dataTransfer.getData('text/cmd');
      const args = JSON.parse(e.dataTransfer.getData('text/args') || '[]');
      if (cmd) this._addStep(cmd, args);
    });

    // Make palette items provide drag data
    el('light-palette').addEventListener('dragstart', e => {
      const item = e.target.closest('[data-cmd]');
      if (!item) return;
      e.dataTransfer.setData('text/cmd',  item.dataset.cmd);
      e.dataTransfer.setData('text/args', item.dataset.args || '[]');
    });

    // SortableJS for reordering steps
    if (typeof Sortable !== 'undefined') {
      Sortable.create(this._steps, {
        animation: 150,
        handle: '.editor-step-handle',
        onEnd: evt => {
          const [moved] = this._sequence.splice(evt.oldIndex, 1);
          this._sequence.splice(evt.newIndex, 0, moved);
        },
      });
    }
  }

  // ── Sequence list ──────────────────────────────────────────────────────────

  async loadSequenceList() {
    try {
      const resp = await fetch('/light/list');
      const data = await resp.json();
      this._renderSeqList(data.sequences || []);
    } catch (e) { console.error('LightEditor: loadSequenceList', e); }
  }

  _renderSeqList(names) {
    this._seqNames = names;
    const list = el('light-seq-list');
    list.innerHTML = '';
    names.forEach(name => {
      const item = document.createElement('div');
      item.className = 'editor-seq-item' + (name === this._openName ? ' active' : '');
      item.textContent = name;
      item.addEventListener('click', () => this.openSequence(name));
      list.appendChild(item);
    });
  }

  async openSequence(name) {
    try {
      const resp = await fetch(`/light/get?name=${encodeURIComponent(name)}`);
      if (!resp.ok) { alert(`Sequence "${name}" not found`); return; }
      const data = await resp.json();
      this._openName   = data.name;
      this._sequence   = data.steps;
      this._editingIdx = null;
      this._nameInput.value    = data.name;
      this._nameInput.readOnly = true;
      this._canvasLabel.textContent = `STEPS — ${data.name}`;
      this._renderSteps();
      await this.loadSequenceList();
    } catch (e) { console.error('LightEditor: openSequence', e); }
  }

  // ── Steps rendering ────────────────────────────────────────────────────────

  _renderSteps() {
    this._steps.innerHTML = '';
    this._sequence.forEach((step, idx) => {
      this._steps.appendChild(this._renderStep(step, idx));
    });
  }

  _stepLabel(step) {
    if (step.cmd === 'sleep') return `⏱ ${step.args[1] || step.args[0] || '1'}s`;
    if (step.cmd !== 'teeces') return step.cmd;
    const action = (step.args[0] || '').toLowerCase();
    if (action === 'anim') {
      const mode = parseInt(step.args[1]);
      const a = LIGHT_ANIMATIONS.find(x => x.mode === mode);
      return a ? `${a.icon} ${a.label}` : `T${mode}`;
    }
    if (action === 'text')  return `💬 "${step.args[1] || ''}"`;
    if (action === 'psi')   return `💠 PSI ${step.args[1] || ''}`;
    if (action === 'raw')   return `⚙️ ${step.args[1] || ''}`;
    if (action === 'random') return '✨ Random';
    if (action === 'leia')   return '🌀 Leia';
    if (action === 'off')    return '⬛ Off';
    return `💡 ${step.args.join(' ')}`;
  }

  _renderStep(step, idx) {
    const row  = document.createElement('div');
    row.className = 'editor-step-row';
    row.id = 'light-step-row-' + idx;

    const num = document.createElement('div');
    num.className = 'editor-step-num';
    num.textContent = idx + 1;

    const card = document.createElement('div');
    card.className = 'editor-step-card';
    card.style.borderLeftColor = step.cmd === 'sleep' ? '#ffaa00' : '#aa44ff';

    const summary = document.createElement('div');
    summary.style.cssText = 'display:flex;align-items:center;gap:8px';

    const label = document.createElement('span');
    label.style.cssText = 'font-size:10px;color:#c0a0e0;flex:1';
    label.textContent = this._stepLabel(step);

    const actions = document.createElement('span');
    actions.style.cssText = 'font-size:9px;color:#4a6a8a;margin-left:auto;display:flex;align-items:center;gap:6px';

    const btnEdit = document.createElement('span');
    btnEdit.textContent = '✏️'; btnEdit.style.cursor = 'pointer'; btnEdit.title = 'Edit';
    btnEdit.addEventListener('click', e => { e.stopPropagation(); this._toggleEdit(idx); });

    const btnDel = document.createElement('span');
    btnDel.textContent = '🗑'; btnDel.style.cursor = 'pointer'; btnDel.title = 'Delete';
    btnDel.addEventListener('click', e => { e.stopPropagation(); this._removeStep(idx); });

    actions.appendChild(btnEdit);
    actions.appendChild(btnDel);
    summary.appendChild(label);
    summary.appendChild(actions);
    card.appendChild(summary);

    if (this._editingIdx === idx) card.appendChild(this._renderStepForm(step, idx));

    const handle = document.createElement('div');
    handle.className = 'editor-step-handle';
    handle.textContent = '⋮⋮';

    row.appendChild(num);
    row.appendChild(card);
    row.appendChild(handle);
    return row;
  }

  _renderStepForm(step, idx) {
    const form = document.createElement('div');
    form.className = 'editor-step-form';
    form.style.marginTop = '6px';

    let fields = [];
    const args = step.args;
    const action = args[0] ? args[0].toLowerCase() : '';

    if (step.cmd === 'sleep') {
      const isRand = action === 'random';
      fields = [
        { label:'Mode', value: isRand ? 'random':'fixed', options:['fixed','random'] },
        { label:'Duration (s)', value: isRand?(args[1]||'1'):(action==='fixed'?(args[1]||'1'):(action||'1')), type:'number', placeholder:'1.0' },
        { label:'Max (s)', value: args[2]||'3', type:'number', placeholder:'3.0', hidden: !isRand },
      ];
    } else if (step.cmd === 'teeces') {
      if (action === 'anim') {
        fields = [{ label:'Animation', value: args[1]||'1',
          options: LIGHT_ANIMATIONS.map(a => `${a.mode}:${a.icon} ${a.label}`) }];
        // value options shown as "N:label" but value stored as N
      } else if (action === 'text') {
        fields = [{ label:'FLD Text (max 20)', value: args[1]||'', type:'text', placeholder:'HELLO' }];
      } else if (action === 'psi') {
        fields = [{ label:'PSI Mode', value: args[1]||'1', options:['0','1','2','3','4','5','6','7','8','9'] }];
      } else if (action === 'raw') {
        fields = [{ label:'JawaLite command', value: args[1]||'', type:'text', placeholder:'0T5' }];
      } else {
        fields = [{ label:'Action', value: action, options:['random','leia','off','anim','text','psi','raw'] }];
      }
    }

    const inputs = [];
    const wraps  = [];
    fields.forEach(f => {
      const wrap = document.createElement('div');
      wrap.style.cssText = 'display:flex;flex-direction:column;gap:3px;flex:1;min-width:80px';
      if (f.hidden) wrap.style.display = 'none';
      const lbl = document.createElement('label');
      lbl.textContent = f.label;
      let inp;
      if (f.options) {
        inp = document.createElement('select');
        f.options.forEach(o => {
          const opt = document.createElement('option');
          // Support "N:label" format for animation dropdown
          const [val, ...rest] = o.split(':');
          opt.value = val; opt.textContent = rest.length ? rest.join(':') : val;
          if (val === f.value) opt.selected = true;
          inp.appendChild(opt);
        });
      } else {
        inp = document.createElement('input');
        inp.type = f.type || 'text';
        inp.value = f.value !== undefined ? f.value : '';
        inp.placeholder = f.placeholder || '';
      }
      inputs.push(inp);
      wraps.push(wrap);
      wrap.appendChild(lbl);
      wrap.appendChild(inp);
      form.appendChild(wrap);
    });

    // Sleep mode toggle
    if (step.cmd === 'sleep' && inputs[0] && wraps[2]) {
      inputs[0].addEventListener('change', () => {
        wraps[2].style.display = inputs[0].value === 'random' ? '' : 'none';
      });
    }

    const ok = document.createElement('button');
    ok.textContent = '✓ OK';
    ok.className = 'btn-editor-action';
    ok.dataset.color = 'green';
    ok.style.cssText = 'margin-top:4px;flex-basis:100%';
    ok.addEventListener('click', () => {
      let newArgs;
      if (step.cmd === 'sleep') {
        if (inputs[0].value === 'fixed') {
          newArgs = ['fixed', inputs[1].value || '1'];
        } else {
          newArgs = ['random', inputs[1].value || '1', inputs[2]?.value || '3'];
        }
      } else if (step.cmd === 'teeces') {
        const a = action || 'anim';
        if (a === 'anim')  newArgs = ['anim',  inputs[0].value];
        else if (a === 'text') newArgs = ['text', inputs[0].value.substring(0, 20).toUpperCase()];
        else if (a === 'psi')  newArgs = ['psi',  inputs[0].value];
        else if (a === 'raw')  newArgs = ['raw',  inputs[0].value];
        else newArgs = [inputs[0].value];
      } else {
        newArgs = inputs.map(i => i.value.trim()).filter(Boolean);
      }
      this._sequence[idx].args = newArgs;
      this._editingIdx = null;
      this._renderSteps();
    });
    form.appendChild(ok);
    return form;
  }

  _toggleEdit(idx) {
    this._editingIdx = this._editingIdx === idx ? null : idx;
    this._renderSteps();
  }

  _addStep(cmd, args) {
    if (!this._openName) { alert('Create or open a sequence first.'); return; }
    this._sequence.push({ cmd, args: [...args] });
    this._editingIdx = this._sequence.length - 1;
    this._renderSteps();
  }

  _removeStep(idx) {
    this._sequence.splice(idx, 1);
    if (this._editingIdx === idx) this._editingIdx = null;
    this._renderSteps();
  }

  // ── CRUD ───────────────────────────────────────────────────────────────────

  newSequence() {
    const name = prompt('New light sequence name (letters, digits, - and _ only):');
    if (!name) return;
    if (!/^[a-zA-Z0-9_\-]{1,64}$/.test(name)) {
      alert('Invalid name. Use letters, digits, - and _ only (max 64 chars).');
      return;
    }
    this._openName   = name;
    this._sequence   = [];
    this._editingIdx = null;
    this._nameInput.value    = name;
    this._nameInput.readOnly = false;
    this._nameInput.style.borderColor = '#00aaff';
    this._canvasLabel.textContent = `STEPS — ${name} (new)`;
    this._renderSteps();
  }

  async saveSequence() {
    const name = this._nameInput.value.trim();
    if (!name || !/^[a-zA-Z0-9_\-]{1,64}$/.test(name)) { alert('Invalid name.'); return; }
    if (this._sequence.length === 0) { alert('Sequence is empty.'); return; }
    try {
      const resp = await fetch('/light/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, steps: this._sequence }),
      });
      if (!resp.ok) { const e = await resp.json(); alert(`Error: ${e.error}`); return; }
      this._openName = name;
      this._nameInput.readOnly = true;
      this._nameInput.style.borderColor = '';
      this._canvasLabel.textContent = `STEPS — ${name}`;
      await this.loadSequenceList();
      toast('Light sequence saved', 'success');
    } catch (e) { alert('Network error while saving.'); }
  }

  async deleteSequence() {
    if (!this._openName) return;
    if (!confirm(`Delete "${this._openName}"? This cannot be undone.`)) return;
    try {
      const resp = await fetch('/light/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: this._openName }),
      });
      if (!resp.ok) { const e = await resp.json(); alert(`Error: ${e.error}`); return; }
      this._openName   = null;
      this._sequence   = [];
      this._nameInput.value = '';
      this._canvasLabel.textContent = 'STEPS';
      this._renderSteps();
      await this.loadSequenceList();
    } catch (e) { alert('Network error.'); }
  }

  async duplicateSequence() {
    const newName = prompt('Name for the copy:');
    if (!newName) return;
    if (!/^[a-zA-Z0-9_\-]{1,64}$/.test(newName)) { alert('Invalid name.'); return; }
    try {
      const resp = await fetch('/light/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newName, steps: this._sequence }),
      });
      if (!resp.ok) { alert('Error while duplicating.'); return; }
      await this.openSequence(newName);
    } catch (e) { alert('Network error.'); }
  }

  async runTest() {
    if (!this._openName) { alert('Create or open a sequence first.'); return; }
    await this.saveSequence();
    try {
      const resp = await fetch('/light/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: this._openName }),
      });
      const data = await resp.json();
      if (resp.ok) { this._runId = data.id; this._updateStatus('running'); }
      else alert(`Error: ${data.error}`);
    } catch (e) { alert('Network error.'); }
  }

  async stopAll() {
    this._runId = null;
    this._updateStatus('stopped');
    try { await fetch('/light/stop_all', { method: 'POST' }); } catch (e) {}
  }

  _updateStatus(state) {
    const dot  = el('light-status-dot');
    const text = el('light-status-text');
    if (state === 'running') {
      dot.style.background  = '#00cc55';
      text.style.color      = '#00cc55';
      text.textContent      = `▶ RUNNING — ${this._openName}`;
    } else {
      dot.style.background  = '#2a4a6a';
      text.style.color      = '#2a4a6a';
      text.textContent      = '—';
    }
  }
}
```

### 5c — Wire up type switcher

- [ ] **Step 5: Add `editorSwitchType` function and initialization to app.js**

After the `LightEditor` class, add:

```js
// ─── Editor type switcher ─────────────────────────────────────────────────────
function editorSwitchType(type) {
  el('editor-panel-sequence').style.display = type === 'sequence' ? '' : 'none';
  el('editor-panel-light').style.display    = type === 'light'    ? '' : 'none';
  document.querySelectorAll('.editor-type-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.type === type);
  });
  if (type === 'light') lightEditor.loadSequenceList();
  if (type === 'sequence') seqEditor.loadSequenceList();
}

// Instantiation (add lightEditor after seqEditor)
const lightEditor = new LightEditor();
```

Also update the `switchTab` function — when switching to `editor`, also load the light list if light mode active:

In the existing `switchTab` function, the line:
```js
if (tabId === 'editor' && typeof seqEditor !== 'undefined') seqEditor.loadSequenceList();
```
Replace with:
```js
if (tabId === 'editor') {
  if (typeof seqEditor !== 'undefined') seqEditor.loadSequenceList();
  if (typeof lightEditor !== 'undefined') lightEditor.loadSequenceList();
}
```

- [ ] **Step 6: Add `lseq` step to regular SequenceEditor palette and _stepFields**

In `index.html`, add to the sequence palette:
```html
<div class="editor-palette-item" data-cmd="lseq" draggable="true">💡 Light Seq</div>
```

In `app.js` `_defaultArgs`:
```js
lseq: [''],
```

In `app.js` `_stepFields`, add case:
```js
case 'lseq':
  return this._seqNames.length || this._lseqNames.length
    ? [{ label: 'Light Sequence', value: args[0] || this._lseqNames[0] || '',
         options: this._lseqNames }]
    : [{ label: 'Light Sequence', value: args[0] || '', placeholder: 'name' }];
```

Add `this._lseqNames = []` to `SequenceEditor` constructor, and add `_loadLightSeqNames()`:
```js
async _loadLightSeqNames() {
  try {
    const resp = await fetch('/light/list');
    const data = await resp.json();
    this._lseqNames = data.sequences || [];
  } catch (e) {}
}
```
Call it in the constructor alongside `_loadSoundIndex()`.

In `_cmdIcon` and `_cmdColor` / `_cmdBg`, add `lseq` entry:
```js
_cmdIcon:  lseq: '💡'
_cmdColor: lseq: '#ffdd44'
_cmdBg:    lseq: '#1a1a00'
```

- [ ] **Step 7: Sync Android assets (JS + CSS + patched index.html)**

```bash
cp master/static/js/app.js android/app/src/main/assets/js/app.js
cp master/static/css/style.css android/app/src/main/assets/css/style.css
```

For `index.html`, patch `/static/` paths to relative before copying (per CLAUDE.md requirement):
```bash
# Read android/app/src/main/assets/index.html to see existing patch pattern, then apply:
# Replace {{ url_for('static', filename='...') }} → relative paths
# Replace /static/js/ → js/
# Replace /static/css/ → css/
# Disable Service Worker registration if present
# Copy the result to android/app/src/main/assets/index.html
```
Use the existing `android/app/src/main/assets/index.html` as reference for the exact patch applied previously.

- [ ] **Step 8: Commit**

```bash
git add master/templates/index.html master/static/js/app.js master/static/css/style.css \
        android/app/src/main/assets/js/app.js android/app/src/main/assets/css/style.css
git commit -m "feat: Light Editor UI — type switcher, LightEditor class, all 22 T-code animations"
```

---

## Final: Deploy + Verify

- [ ] **Deploy**

```bash
git push
python3 -c "
import paramiko, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.2.104', username='artoo', password='deetoo', timeout=10)
stdin, stdout, stderr = c.exec_command('cd /home/artoo/r2d2 && bash scripts/update.sh 2>&1')
for line in stdout: print(line, end='')
c.close()
"
```

- [ ] **Verify checklist**
  - All tabs in English ✓
  - Editor tab shows `[ SEQUENCES ] [ LIGHT ]` switcher ✓
  - SEQUENCES mode: existing editor works unchanged ✓
  - LIGHT mode: 22 animation palette items visible ✓
  - Creating/saving/deleting a light sequence works ✓
  - `lseq,name` step available in sequence editor ✓
  - `GET /light/list` returns sequences ✓
  - `POST /light/run` starts a light sequence ✓
  - `GET /teeces/animations` returns 22 animations ✓
