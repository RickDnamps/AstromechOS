# Sequences Tab Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the SEQUENCES tab with categories (pill filter like Audio), custom emojis per sequence/category, inline rename, admin drag-to-pill category management, pill reordering, and animated playing state (pulse border + soundwave + progress bar).

**Architecture:** Backend adds `choreo_categories.json` for category definitions and 5 new endpoints to `choreo_bp.py`. Each `.chor` file gets 3 new `meta` fields (`category`, `emoji`, `label`). Frontend rewrites `ScriptEngine` in `app.js` to manage categories, pills (SortableJS for reorder), card rendering, long-press loop, pointer-based drag-to-pill, and an `EmojiPicker` component. CSS adds playing state F animations and admin card styles.

**Tech Stack:** Flask/Python (backend), Vanilla JS ES6 classes (frontend), SortableJS (already bundled at `/static/vendor/sortable.min.js`), CSS animations

---

## File Map

| File | Action | What changes |
|------|--------|--------------|
| `master/config/choreo_categories.json` | **Create** | Category definitions |
| `master/api/choreo_bp.py` | **Modify** | 5 new endpoints + enhanced `/choreo/list` |
| `master/choreographies/*.chor` | **Modify** (44 files) | Add `meta.category`, `meta.emoji`, `meta.label` |
| `master/templates/index.html` | **Modify** | Sequences tab HTML restructure |
| `master/static/css/style.css` | **Modify** | New card styles + playing state F + admin styles |
| `master/static/js/app.js` | **Modify** | Full `ScriptEngine` rewrite + `EmojiPicker` class |

---

## Task 1: Create `choreo_categories.json` and backend helpers

**Files:**
- Create: `master/config/choreo_categories.json`
- Modify: `master/api/choreo_bp.py` (top section — add helpers)

- [ ] **Step 1: Create the categories JSON file**

Create `master/config/choreo_categories.json`:
```json
[
  { "id": "performance", "label": "Performance", "emoji": "🎭", "order": 0 },
  { "id": "emotion",     "label": "Emotions",    "emoji": "😤", "order": 1 },
  { "id": "behavior",    "label": "Behavior",    "emoji": "🚶", "order": 2 },
  { "id": "dome",        "label": "Dome",        "emoji": "🔵", "order": 3 },
  { "id": "test",        "label": "Tests",       "emoji": "🔧", "order": 4 },
  { "id": "newchoreo",   "label": "New Choreo",  "emoji": "📦", "order": 5 }
]
```

- [ ] **Step 2: Add category helpers to `choreo_bp.py`**

After the existing `_CHOREO_DIR` line, add:

```python
_CATEGORIES_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'choreo_categories.json')
_SYSTEM_CATEGORY = 'newchoreo'


def _load_categories() -> list:
    """Load categories from JSON, creating defaults if missing."""
    if not os.path.exists(_CATEGORIES_PATH):
        defaults = [
            {"id": "performance", "label": "Performance", "emoji": "🎭", "order": 0},
            {"id": "emotion",     "label": "Emotions",    "emoji": "😤", "order": 1},
            {"id": "behavior",    "label": "Behavior",    "emoji": "🚶", "order": 2},
            {"id": "dome",        "label": "Dome",        "emoji": "🔵", "order": 3},
            {"id": "test",        "label": "Tests",       "emoji": "🔧", "order": 4},
            {"id": "newchoreo",   "label": "New Choreo",  "emoji": "📦", "order": 5},
        ]
        _save_categories(defaults)
        return defaults
    with open(_CATEGORIES_PATH, encoding='utf-8') as f:
        return json.load(f)


def _save_categories(cats: list) -> None:
    os.makedirs(os.path.dirname(_CATEGORIES_PATH), exist_ok=True)
    with open(_CATEGORIES_PATH, 'w', encoding='utf-8') as f:
        json.dump(cats, f, indent=2, ensure_ascii=False)


def _auto_emoji(name: str) -> str:
    """Derive emoji from sequence name — same logic as JS _emoji()."""
    n = name.lower()
    if any(x in n for x in ['cantina', 'tune', 'dance', 'disco', 'music', 'song']): return '🎵'
    if any(x in n for x in ['alert', 'alarm']): return '🚨'
    if 'scan' in n:       return '🔍'
    if any(x in n for x in ['celebrat', 'happy', 'cheer', 'joy']): return '🎉'
    if 'leia' in n:       return '📡'
    if any(x in n for x in ['patrol', 'stroll', 'walk']): return '🚶'
    if 'test' in n:       return '🔧'
    if any(x in n for x in ['fall', 'strike', 'multi']): return '⚡'
    if 'panel' in n:      return '🚪'
    if any(x in n for x in ['dome']): return '🔵'
    if any(x in n for x in ['excit', 'idea']): return '💬'
    if 'show' in n:       return '🎭'
    if 'birthday' in n:   return '🎂'
    if 'march' in n:      return '🎖️'
    if 'party' in n:      return '🥳'
    if 'startup' in n:    return '🤖'
    if 'scared' in n:     return '😱'
    if 'angry' in n:      return '😡'
    if 'evil' in n:       return '😈'
    if 'curious' in n:    return '🤔'
    if 'taunt' in n:      return '😏'
    if 'malfunction' in n: return '💥'
    if 'failure' in n:    return '⚡'
    if 'wolfwhistle' in n: return '🐺'
    if 'message' in n:    return '📨'
    if 'ripple' in n:     return '🌀'
    if 'flap' in n:       return '🚪'
    if 'hp_twitch' in n:  return '🔦'
    return '🎬'
```

- [ ] **Step 3: Commit**

```bash
git add master/config/choreo_categories.json master/api/choreo_bp.py
git commit -m "Feat: choreo categories JSON + backend helpers"
```

---

## Task 2: Migrate all `.chor` files — add meta fields

**Files:**
- Modify: `master/choreographies/*.chor` (44 files)

- [ ] **Step 1: Run migration script from PC dev**

Run this Python snippet in the terminal (from `J:/R2-D2_Build/software`):

```python
import json, os, glob

CATEGORY_MAP = {
    # Performance
    'cantina': 'performance', 'cantina_show': 'performance', 'leia': 'performance',
    'march': 'performance', 'disco': 'performance', 'birthday': 'performance',
    'party': 'performance', 'celebrate': 'performance', 'theme': 'performance',
    'r2kt': 'performance', 'wolfwhistle': 'performance', 'dance': 'performance',
    # Emotions
    'angry': 'emotion', 'scared': 'emotion', 'curious': 'emotion',
    'excited': 'emotion', 'evil': 'emotion', 'taunt': 'emotion',
    # Behavior
    'patrol': 'behavior', 'scan': 'behavior', 'startup': 'behavior',
    'message': 'behavior', 'alert': 'behavior', 'failure': 'behavior',
    'malfunction': 'behavior',
    # Dome
    'dome_dance': 'dome', 'flap_dome': 'dome', 'flap_dome_fast': 'dome',
    'flap_dome_side': 'dome', 'ripple_dome': 'dome', 'ripple_dome_fast': 'dome',
    'ripple_dome_side': 'dome', 'hp_twitch': 'dome', 'slow_open_close': 'dome',
    # Tests
    'test': 'test', 'dome_test1': 'test', 'dome_test2': 'test',
    'body_test': 'test', 'panel_test': 'test', 'looping_sounds': 'test',
    'looping_sounds_quick': 'test',
}

for path in glob.glob('master/choreographies/*.chor'):
    with open(path, encoding='utf-8') as f:
        chor = json.load(f)
    name = chor['meta'].get('name', os.path.basename(path)[:-5])
    changed = False
    if 'category' not in chor['meta']:
        chor['meta']['category'] = CATEGORY_MAP.get(name, 'newchoreo')
        changed = True
    if 'emoji' not in chor['meta']:
        chor['meta']['emoji'] = ''
        changed = True
    if 'label' not in chor['meta']:
        chor['meta']['label'] = ''
        changed = True
    if changed:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(chor, f, indent=2, ensure_ascii=False)
        print(f"  Migrated: {name} → {chor['meta']['category']}")

print('Done.')
```

Run it:
```bash
cd "J:/R2-D2_Build/software"
python3 -c "$(cat <<'PYEOF'
import json, os, glob
# ... paste full script above ...
PYEOF
)"
```

Expected output: 44 lines like `Migrated: cantina → performance`

- [ ] **Step 2: Verify a sample file**

```bash
python3 -c "import json; d=json.load(open('master/choreographies/cantina.chor')); print(d['meta'])"
```

Expected: `{'name': 'cantina', ..., 'category': 'performance', 'emoji': '', 'label': ''}`

- [ ] **Step 3: Commit**

```bash
git add master/choreographies/
git commit -m "Feat: migrate .chor files — add category/emoji/label meta fields"
```

---

## Task 3: Backend — Enhance `/choreo/list` + add `/choreo/categories`

**Files:**
- Modify: `master/api/choreo_bp.py`

- [ ] **Step 1: Replace `choreo_list()` endpoint**

Replace the existing `@choreo_bp.get('/choreo/list')` function with:

```python
@choreo_bp.get('/choreo/list')
def choreo_list():
    os.makedirs(_CHOREO_DIR, exist_ok=True)
    result = []
    for fname in sorted(os.listdir(_CHOREO_DIR)):
        if not fname.endswith('.chor'):
            continue
        name = fname[:-5]
        try:
            with open(os.path.join(_CHOREO_DIR, fname), encoding='utf-8') as f:
                meta = json.load(f).get('meta', {})
        except Exception:
            meta = {}
        result.append({
            'name':     name,
            'label':    meta.get('label', '') or '',
            'category': meta.get('category', '') or _SYSTEM_CATEGORY,
            'emoji':    meta.get('emoji', '') or _auto_emoji(name),
            'duration': meta.get('duration', 0),
        })
    return jsonify(result)
```

- [ ] **Step 2: Add `GET /choreo/categories` endpoint**

Add after `choreo_list()`:

```python
@choreo_bp.get('/choreo/categories')
def get_categories():
    cats = sorted(_load_categories(), key=lambda c: c.get('order', 99))
    return jsonify(cats)
```

- [ ] **Step 3: Verify with curl (or browser)**

After deploying to Pi:
```bash
curl http://192.168.2.104:5000/choreo/list | python3 -m json.tool | head -30
curl http://192.168.2.104:5000/choreo/categories | python3 -m json.tool
```

`/choreo/list` must return objects `{name, label, category, emoji, duration}`, not plain strings.
`/choreo/categories` must return 6 category objects.

- [ ] **Step 4: Commit**

```bash
git add master/api/choreo_bp.py
git commit -m "Feat: enhance /choreo/list + add /choreo/categories endpoint"
```

---

## Task 4: Backend — Category management + sequence meta endpoints

**Files:**
- Modify: `master/api/choreo_bp.py`

- [ ] **Step 1: Add `POST /choreo/categories`**

```python
@choreo_bp.post('/choreo/categories')
def manage_categories():
    data = request.get_json(silent=True) or {}
    action = data.get('action', '')
    cats = _load_categories()
    ids = [c['id'] for c in cats]

    if action == 'create':
        cat_id    = data.get('id', '').strip().lower().replace(' ', '_')
        cat_label = data.get('label', '').strip()
        cat_emoji = data.get('emoji', '📦').strip()
        if not cat_id or not cat_label:
            return jsonify({'error': 'id and label required'}), 400
        if cat_id in ids:
            return jsonify({'error': 'id already exists'}), 409
        cats.append({'id': cat_id, 'label': cat_label, 'emoji': cat_emoji,
                     'order': max((c.get('order', 0) for c in cats), default=0) + 1})
        _save_categories(cats)
        return jsonify({'status': 'ok', 'id': cat_id})

    elif action == 'update':
        cat_id    = data.get('id', '')
        cat_emoji = data.get('emoji', '').strip()
        cat_label = data.get('label', '').strip()
        for c in cats:
            if c['id'] == cat_id:
                if cat_emoji:
                    c['emoji'] = cat_emoji
                if cat_label:
                    c['label'] = cat_label
                _save_categories(cats)
                return jsonify({'status': 'ok'})
        return jsonify({'error': 'category not found'}), 404

    elif action == 'reorder':
        new_order = data.get('order', [])
        cat_map = {c['id']: c for c in cats}
        reordered = []
        for i, cat_id in enumerate(new_order):
            if cat_id in cat_map:
                cat_map[cat_id]['order'] = i
                reordered.append(cat_map[cat_id])
        # Add any missing cats at end
        for c in cats:
            if c['id'] not in new_order:
                reordered.append(c)
        _save_categories(reordered)
        return jsonify({'status': 'ok'})

    elif action == 'delete':
        cat_id = data.get('id', '')
        if cat_id == _SYSTEM_CATEGORY:
            return jsonify({'error': 'cannot delete system category'}), 400
        # Move sequences in this category to newchoreo
        for fname in os.listdir(_CHOREO_DIR):
            if not fname.endswith('.chor'):
                continue
            fpath = os.path.join(_CHOREO_DIR, fname)
            try:
                with open(fpath, encoding='utf-8') as f:
                    chor = json.load(f)
                if chor.get('meta', {}).get('category') == cat_id:
                    chor['meta']['category'] = _SYSTEM_CATEGORY
                    with open(fpath, 'w', encoding='utf-8') as f:
                        json.dump(chor, f, indent=2, ensure_ascii=False)
            except Exception:
                pass
        cats = [c for c in cats if c['id'] != cat_id]
        _save_categories(cats)
        return jsonify({'status': 'ok'})

    return jsonify({'error': f'unknown action: {action}'}), 400
```

- [ ] **Step 2: Add `POST /choreo/set-category`**

```python
@choreo_bp.post('/choreo/set-category')
def set_choreo_category():
    data = request.get_json(silent=True) or {}
    name     = data.get('name', '').strip()
    category = data.get('category', '').strip()
    if not name or not category:
        return jsonify({'error': 'name and category required'}), 400
    path = _choreo_path(name)
    if not os.path.exists(path):
        return jsonify({'error': 'not found'}), 404
    with open(path, encoding='utf-8') as f:
        chor = json.load(f)
    chor.setdefault('meta', {})['category'] = category
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(chor, f, indent=2, ensure_ascii=False)
    return jsonify({'status': 'ok'})
```

- [ ] **Step 3: Add `POST /choreo/set-emoji`**

```python
@choreo_bp.post('/choreo/set-emoji')
def set_choreo_emoji():
    data = request.get_json(silent=True) or {}
    name  = data.get('name', '').strip()
    emoji = data.get('emoji', '').strip()
    if not name:
        return jsonify({'error': 'name required'}), 400
    path = _choreo_path(name)
    if not os.path.exists(path):
        return jsonify({'error': 'not found'}), 404
    with open(path, encoding='utf-8') as f:
        chor = json.load(f)
    chor.setdefault('meta', {})['emoji'] = emoji  # empty string = revert to auto
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(chor, f, indent=2, ensure_ascii=False)
    return jsonify({'status': 'ok'})
```

- [ ] **Step 4: Add `POST /choreo/set-label`**

```python
@choreo_bp.post('/choreo/set-label')
def set_choreo_label():
    data = request.get_json(silent=True) or {}
    name  = data.get('name', '').strip()
    label = data.get('label', '').strip()
    if not name:
        return jsonify({'error': 'name required'}), 400
    path = _choreo_path(name)
    if not os.path.exists(path):
        return jsonify({'error': 'not found'}), 404
    with open(path, encoding='utf-8') as f:
        chor = json.load(f)
    chor.setdefault('meta', {})['label'] = label  # empty string = revert to filename
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(chor, f, indent=2, ensure_ascii=False)
    return jsonify({'status': 'ok'})
```

- [ ] **Step 5: Commit**

```bash
git add master/api/choreo_bp.py
git commit -m "Feat: category/emoji/label management endpoints for choreo"
```

---

## Task 5: HTML — Sequences tab restructure

**Files:**
- Modify: `master/templates/index.html`

- [ ] **Step 1: Replace the entire sequences tab content**

Find and replace the block:
```html
<div class="tab-content" id="tab-sequences">
  <div class="sequences-layout">
    ...
  </div>
</div>
```

Replace with:
```html
<div class="tab-content" id="tab-sequences">
  <div class="sequences-layout">

    <!-- Category pills (like Audio tab) -->
    <div class="seq-pills-wrap">
      <div class="seq-pills" id="seq-pills">
        <!-- generated by JS -->
      </div>
      <div class="seq-admin-hint hidden" id="seq-admin-hint">
        ⠿ Drag les pills pour réordonner &nbsp;·&nbsp; Drag une carte sur une pill pour changer sa catégorie
      </div>
    </div>

    <!-- Sequence cards grid -->
    <div class="seq-grid" id="seq-grid">
      <!-- generated by JS -->
    </div>

    <!-- Running status bar -->
    <div class="running-list-wrap">
      <strong class="section-title-sm">ACTIVE:</strong>
      <span id="running-scripts" class="running-list">—</span>
    </div>

  </div>
</div>
```

- [ ] **Step 2: Add emoji picker modal (before closing `</body>`)**

Add before `<div id="toast"`:
```html
<!-- Emoji picker shared modal -->
<div id="emoji-picker-overlay" class="emoji-picker-overlay hidden" onclick="emojiPicker.onOverlayClick(event)">
  <div class="emoji-picker-popup" id="emoji-picker-popup">
    <div class="emoji-picker-header">
      <input class="emoji-picker-search" id="emoji-picker-search"
             placeholder="🔍  Search..." oninput="emojiPicker.filter(this.value)">
    </div>
    <div class="emoji-picker-scroll" id="emoji-picker-scroll">
      <!-- sections generated by JS -->
    </div>
    <div class="emoji-picker-footer">
      <span class="emoji-picker-preview" id="emoji-picker-preview">?</span>
      <div class="emoji-picker-actions">
        <button class="btn btn-sm" onclick="emojiPicker.cancel()">Cancel</button>
        <button class="btn btn-primary btn-sm" onclick="emojiPicker.confirm()">✓ Apply</button>
      </div>
    </div>
  </div>
</div>
```

- [ ] **Step 3: Commit**

```bash
git add master/templates/index.html
git commit -m "Feat: sequences tab HTML — pills + grid + emoji picker overlay"
```

---

## Task 6: CSS — Card styles, playing state F, admin styles

**Files:**
- Modify: `master/static/css/style.css`

- [ ] **Step 1: Add new keyframe animations**

Find the existing `@keyframes seq-pulse` block and add after it:

```css
@keyframes seq-border-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(0,255,234,0.3), 0 0 8px rgba(0,255,234,0.15); border-color: var(--teal); }
  50%       { box-shadow: 0 0 0 6px rgba(0,255,234,0), 0 0 22px rgba(0,255,234,0.45); border-color: rgba(0,255,234,0.85); }
}
@keyframes seq-wave {
  0%, 100% { transform: scaleY(0.35); }
  50%       { transform: scaleY(1.0); }
}
@keyframes seq-progress {
  from { width: 0%; }
  to   { width: 100%; }
}
@keyframes seq-loop-spin {
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
}
```

- [ ] **Step 2: Add sequence card styles (replace old `.seq-btn` usage for new cards)**

Add after the existing `.seq-btn` block:

```css
/* ── Sequences tab — pill row ── */
.seq-pills-wrap {
  margin-bottom: 14px;
}
.seq-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.seq-pill {
  display: flex;
  align-items: center;
  gap: 5px;
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 5px 12px;
  font-size: 12px;
  color: var(--text-dim);
  cursor: pointer;
  user-select: none;
  transition: all .15s;
  min-height: 34px;
  position: relative;
}
.seq-pill:hover        { border-color: var(--blue); color: var(--blue); }
.seq-pill.active       { background: rgba(0,170,255,0.12); border-color: var(--blue); color: var(--blue); }
.seq-pill.drop-target  { background: rgba(0,255,234,0.15); border-color: var(--teal); color: var(--teal); transform: scale(1.07); box-shadow: 0 0 12px rgba(0,255,234,0.3); }
.seq-pill.pill-add     { border-style: dashed; color: #444; }
.seq-pill.pill-add:hover { color: var(--teal); border-color: var(--teal); }
.seq-pill-emoji        { font-size: 15px; cursor: text; }
.seq-pill.admin-mode .seq-pill-emoji { border-bottom: 1px dashed rgba(0,255,234,0.5); }
.seq-pill-close        { display: none; margin-left: 4px; font-size: 10px; color: #444; cursor: pointer; }
.seq-pill-close:hover  { color: #ff4444; }
.seq-pill.admin-mode:hover .seq-pill-close { display: inline; }
.seq-admin-hint {
  margin-top: 7px;
  font-size: 10px;
  color: rgba(0,255,234,0.5);
  font-style: italic;
  letter-spacing: 0.3px;
}

/* ── Sequence card grid ── */
.seq-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(90px, 1fr));
  gap: 8px;
}
.seq-card {
  position: relative;
  background: rgba(10,20,40,0.7);
  border: 2px solid var(--border);
  border-radius: 10px;
  padding: 12px 8px 10px;
  text-align: center;
  cursor: pointer;
  user-select: none;
  transition: border-color .2s, background .2s;
  overflow: hidden;
  min-height: 80px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
}
.seq-card:hover      { border-color: var(--blue); background: rgba(0,170,255,0.06); }
.seq-card-emoji      { font-size: 26px; line-height: 1; display: block; }
.seq-card-label      { font-size: 10px; font-weight: 600; letter-spacing: 0.4px; color: var(--text-dim); line-height: 1.2; }

/* Admin mode card extras */
.seq-card-handle {
  display: none;
  position: absolute;
  top: 5px; left: 5px;
  font-size: 11px; color: #444;
  cursor: grab;
  width: 20px; height: 20px;
  align-items: center; justify-content: center;
}
.seq-card-play {
  display: none;
  position: absolute;
  top: 4px; right: 4px;
  font-size: 10px; color: #555;
  background: rgba(0,255,234,0.08);
  border: 1px solid #333;
  border-radius: 4px;
  width: 22px; height: 22px;
  align-items: center; justify-content: center;
  cursor: pointer;
}
.seq-card-play:hover { color: var(--teal); border-color: var(--teal); }
.seq-card-loop {
  display: none;
  position: absolute;
  top: 4px; right: 4px;
  font-size: 11px;
  animation: seq-loop-spin 2s linear infinite;
}

/* Admin mode card reveals */
.admin-unlocked .seq-card .seq-card-handle { display: flex; }
.admin-unlocked .seq-card .seq-card-play   { display: flex; }
.admin-unlocked .seq-card .seq-card-emoji  { cursor: pointer; border-bottom: 2px dashed rgba(0,255,234,0.4); }
.admin-unlocked .seq-card .seq-card-label  { cursor: pointer; border-bottom: 1px dashed rgba(0,255,234,0.3); }

/* Dragging state */
.seq-card.dragging { opacity: 0.4; }

/* ── Playing state F ── */
.seq-card.running {
  border-color: var(--teal);
  background: rgba(0,255,234,0.06);
  animation: seq-border-pulse 1.8s ease-in-out infinite;
}
.seq-card.running .seq-card-loop { display: block; }
.seq-card.running.looping .seq-card-loop { display: block; }
.seq-card:not(.looping) .seq-card-loop { display: none; }

/* Soundwave (replaces label while running) */
.seq-card.running .seq-card-label { display: none; }
.seq-card.running .seq-card-wave  { display: flex; }
.seq-card-wave {
  display: none;
  align-items: flex-end;
  justify-content: center;
  gap: 2px;
  height: 16px;
}
.seq-card-wave span {
  display: block;
  width: 3px;
  background: var(--teal);
  border-radius: 2px;
  animation: seq-wave 0.6s ease-in-out infinite;
}
.seq-card-wave span:nth-child(1) { height: 6px;  animation-delay: 0s; }
.seq-card-wave span:nth-child(2) { height: 14px; animation-delay: 0.1s; }
.seq-card-wave span:nth-child(3) { height: 10px; animation-delay: 0.2s; }
.seq-card-wave span:nth-child(4) { height: 16px; animation-delay: 0.3s; }
.seq-card-wave span:nth-child(5) { height: 8px;  animation-delay: 0.15s; }
.seq-card-wave span:nth-child(6) { height: 12px; animation-delay: 0.25s; }

/* Progress bar */
.seq-card-progress {
  position: absolute;
  bottom: 0; left: 0; right: 0;
  height: 3px;
  background: rgba(255,255,255,0.05);
  display: none;
}
.seq-card-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--teal), #00ff88);
  border-radius: 0 2px 2px 0;
  width: 0%;
}
.seq-card.running .seq-card-progress       { display: block; }

/* ── Emoji picker ── */
.emoji-picker-overlay {
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.6);
  z-index: 2000;
  display: flex; align-items: center; justify-content: center;
}
.emoji-picker-overlay.hidden { display: none; }
.emoji-picker-popup {
  background: #13131f;
  border: 1px solid var(--border);
  border-radius: 14px;
  width: 320px;
  max-height: 80vh;
  display: flex; flex-direction: column;
  box-shadow: 0 16px 48px rgba(0,0,0,0.8);
}
.emoji-picker-header { padding: 12px 12px 8px; }
.emoji-picker-search {
  width: 100%;
  background: #0a0a12; border: 1px solid #333; border-radius: 7px;
  color: var(--text); font-size: 13px; padding: 7px 12px; outline: none;
  box-sizing: border-box;
}
.emoji-picker-search:focus { border-color: rgba(0,255,234,0.5); }
.emoji-picker-scroll { flex: 1; overflow-y: auto; padding: 4px 12px 8px; }
.emoji-picker-scroll::-webkit-scrollbar { width: 4px; }
.emoji-picker-scroll::-webkit-scrollbar-thumb { background: #333; border-radius: 2px; }
.emoji-picker-section-label {
  font-size: 9px; font-weight: 700; letter-spacing: 1.5px;
  color: #555; margin: 10px 0 5px;
}
.emoji-picker-grid { display: flex; flex-wrap: wrap; gap: 2px; margin-bottom: 4px; }
.emoji-picker-btn {
  width: 36px; height: 36px;
  display: flex; align-items: center; justify-content: center;
  font-size: 20px; border-radius: 7px; cursor: pointer;
  border: 1px solid transparent;
  transition: background .1s, transform .1s;
}
.emoji-picker-btn:hover { background: rgba(0,255,234,0.15); border-color: rgba(0,255,234,0.3); transform: scale(1.2); }
.emoji-picker-btn.selected { background: rgba(0,255,234,0.2); border-color: var(--teal); }
.emoji-picker-footer {
  padding: 10px 12px;
  border-top: 1px solid var(--border);
  display: flex; align-items: center; justify-content: space-between;
}
.emoji-picker-preview { font-size: 26px; }
.emoji-picker-actions { display: flex; gap: 8px; }

/* ── Tablet responsive ── */
@media (max-width: 600px) {
  .seq-grid { grid-template-columns: repeat(auto-fill, minmax(80px, 1fr)); gap: 6px; }
  .seq-pill  { min-height: 44px; padding: 6px 14px; font-size: 13px; }
  .seq-card  { min-height: 88px; }
  .seq-card-emoji { font-size: 30px; }
  .seq-card-handle { width: 30px; height: 30px; }
  .seq-card-play   { width: 28px; height: 28px; font-size: 12px; }
  .emoji-picker-popup { width: 100%; max-width: 100%; border-radius: 14px 14px 0 0; position: fixed; bottom: 0; }
  .emoji-picker-overlay { align-items: flex-end; }
  .emoji-picker-btn { width: 44px; height: 44px; font-size: 22px; }
}
```

- [ ] **Step 3: Commit**

```bash
git add master/static/css/style.css
git commit -m "Feat: sequences tab CSS — cards, playing state F, emoji picker, tablet"
```

---

## Task 7: JS — EmojiPicker class + ScriptEngine rewrite (core)

**Files:**
- Modify: `master/static/js/app.js`

- [ ] **Step 1: Add `EmojiPicker` class before `ScriptEngine`**

Find `// Script Engine` comment and insert before it:

```javascript
// ================================================================
// EmojiPicker — shared emoji picker component
// ================================================================

const EMOJI_SECTIONS = [
  { label: '😤 Émotions', emojis: ['😡','🤬','😤','😠','😱','😨','😰','😮','😲','🥹','🤩','😎','🥳','😏','🤔','🥸','😴','🤯','🫡','😈','👻','💀','🤖','👾'] },
  { label: '🎵 Musique & Sons', emojis: ['🎵','🎶','🎸','🎺','🪗','🥁','🎤','🎼','🪩','💿','📻','🔊','🔔','🎹','🎻','🎷'] },
  { label: '🎭 Show & Fête', emojis: ['🎭','🎉','🎊','🎂','🎈','🪅','🎆','🎇','🏆','🥇','🎖️','👑'] },
  { label: '🏃 Mouvement & Danse', emojis: ['🏃','🚶','💃','🕺','🌀','💫','🔄','↩️','🎯','🏹','👋','🫳'] },
  { label: '⚡ Actions & Alertes', emojis: ['⚡','🚨','🔴','🟠','🟡','🟢','💥','🔥','❄️','💣','🧨','☢️'] },
  { label: '🔧 Tech & Robot', emojis: ['🔧','⚙️','🔬','📡','🔍','💡','🔋','📱','🖥️','🎮','🕹️','🔌'] },
  { label: '⭐ Star Wars & Espace', emojis: ['⭐','🌟','✨','🚀','🛸','🌙','🪐','☄️','⚔️','🗡️','🔫','🐺','🦅','🏜️','🌌','👁️'] },
  { label: '🚪 Panneaux & Dôme', emojis: ['🚪','🔵','🟣','⭕','🔘','🪞','🎪','🎠'] },
];

class EmojiPicker {
  constructor() {
    this._selected   = '';
    this._callback   = null;
    this._allEmojis  = EMOJI_SECTIONS.flatMap(s => s.emojis);
    this._buildSections();
  }

  _buildSections() {
    const scroll = el('emoji-picker-scroll');
    if (!scroll) return;
    scroll.innerHTML = EMOJI_SECTIONS.map(sec => `
      <div class="emoji-picker-section-label">${sec.label}</div>
      <div class="emoji-picker-grid">
        ${sec.emojis.map(e =>
          `<div class="emoji-picker-btn" data-emoji="${e}" onclick="emojiPicker._pick('${e}')">${e}</div>`
        ).join('')}
      </div>`
    ).join('');
  }

  open(currentEmoji, callback) {
    this._selected = currentEmoji || '';
    this._callback = callback;
    el('emoji-picker-preview').textContent = this._selected || '?';
    el('emoji-picker-search').value = '';
    this._highlightSelected();
    el('emoji-picker-overlay').classList.remove('hidden');
    el('emoji-picker-search').focus();
  }

  _highlightSelected() {
    document.querySelectorAll('.emoji-picker-btn').forEach(b => {
      b.classList.toggle('selected', b.dataset.emoji === this._selected);
      b.style.display = '';
    });
    document.querySelectorAll('.emoji-picker-section-label').forEach(l => l.style.display = '');
  }

  _pick(emoji) {
    this._selected = emoji;
    el('emoji-picker-preview').textContent = emoji;
    document.querySelectorAll('.emoji-picker-btn').forEach(b =>
      b.classList.toggle('selected', b.dataset.emoji === emoji));
  }

  filter(query) {
    const q = query.trim().toLowerCase();
    document.querySelectorAll('.emoji-picker-btn').forEach(b => {
      b.style.display = (!q || b.dataset.emoji.includes(q)) ? '' : 'none';
    });
  }

  confirm() {
    if (this._callback) this._callback(this._selected);
    this.cancel();
  }

  cancel() {
    el('emoji-picker-overlay').classList.add('hidden');
    this._callback = null;
  }

  onOverlayClick(e) {
    if (e.target === el('emoji-picker-overlay')) this.cancel();
  }
}

const emojiPicker = new EmojiPicker();
```

- [ ] **Step 2: Replace the entire `ScriptEngine` class**

Find the block from `// Script Engine` down to `async function loadScripts()` and replace with:

```javascript
// ================================================================
// ScriptEngine — Sequences tab with categories
// ================================================================

class ScriptEngine {
  constructor() {
    this._scripts    = [];   // [{name, label, category, emoji, duration}]
    this._categories = [];   // [{id, label, emoji, order}]
    this._running    = new Set();
    this._looping    = new Set();
    this._activeCategory = 'all';
    this._pillSortable   = null;
    this._longPressTimer = null;
    this._dragCard       = null;  // card being dragged
  }

  // ── Data loading ─────────────────────────────────────────────

  async load() {
    const [scripts, cats] = await Promise.all([
      api('/choreo/list'),
      api('/choreo/categories'),
    ]);
    this._scripts    = scripts    || [];
    this._categories = (cats || []).slice().sort((a, b) => (a.order || 0) - (b.order || 0));
    this._renderPills();
    this._renderGrid();
    this._syncAdminMode();
  }

  // ── Pills ─────────────────────────────────────────────────────

  _renderPills() {
    const container = el('seq-pills');
    if (!container) return;
    const isAdmin = adminGuard.unlocked;
    const cats = this._categories;

    const allPill = `<div class="seq-pill${this._activeCategory === 'all' ? ' active' : ''}"
        data-cat="all" onclick="scriptEngine.selectCategory('all')">
        <span>🌐</span> ALL
      </div>`;

    const catPills = cats.map(c => `
      <div class="seq-pill${this._activeCategory === c.id ? ' active' : ''}${isAdmin ? ' admin-mode' : ''}"
           data-cat="${c.id}" onclick="scriptEngine.selectCategory('${c.id}')">
        <span class="seq-pill-emoji" ${isAdmin ? `onclick="scriptEngine.onPillEmojiClick(event,'${c.id}')"` : ''}
        >${c.emoji}</span>
        ${escapeHtml(c.label)}
        ${isAdmin && c.id !== 'newchoreo'
          ? `<span class="seq-pill-close" onclick="scriptEngine.deleteCategory(event,'${c.id}')">✕</span>`
          : ''}
      </div>`).join('');

    const addPill = isAdmin
      ? `<div class="seq-pill pill-add" onclick="scriptEngine.createCategory()">+ Cat</div>`
      : '';

    container.innerHTML = allPill + catPills + addPill;

    // SortableJS for pill reordering (admin only)
    if (this._pillSortable) { this._pillSortable.destroy(); this._pillSortable = null; }
    if (isAdmin) {
      this._pillSortable = Sortable.create(container, {
        animation: 150,
        filter: '[data-cat="all"], .pill-add',
        onEnd: () => this._savePillOrder(),
      });
    }

    // Show/hide admin hint
    const hint = el('seq-admin-hint');
    if (hint) hint.classList.toggle('hidden', !isAdmin);
  }

  _savePillOrder() {
    const pills = el('seq-pills').querySelectorAll('.seq-pill[data-cat]');
    const order = [...pills].map(p => p.dataset.cat).filter(id => id !== 'all');
    api('/choreo/categories', 'POST', { action: 'reorder', order });
  }

  selectCategory(catId) {
    this._activeCategory = catId;
    this._renderPills();
    this._renderGrid();
  }

  onPillEmojiClick(event, catId) {
    event.stopPropagation();
    const cat = this._categories.find(c => c.id === catId);
    if (!cat) return;
    emojiPicker.open(cat.emoji, async (emoji) => {
      if (!emoji) return;
      await api('/choreo/categories', 'POST', { action: 'update', id: catId, emoji });
      await this.load();
    });
  }

  async createCategory() {
    const label = prompt('Category name:');
    if (!label) return;
    const id = label.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, '');
    emojiPicker.open('📦', async (emoji) => {
      await api('/choreo/categories', 'POST', { action: 'create', id, label, emoji: emoji || '📦' });
      await this.load();
    });
  }

  async deleteCategory(event, catId) {
    event.stopPropagation();
    const cat = this._categories.find(c => c.id === catId);
    const count = this._scripts.filter(s => s.category === catId).length;
    const msg = count > 0
      ? `Delete "${cat.label}"? ${count} sequence(s) will move to New Choreo.`
      : `Delete "${cat.label}"?`;
    if (!confirm(msg)) return;
    await api('/choreo/categories', 'POST', { action: 'delete', id: catId });
    if (this._activeCategory === catId) this._activeCategory = 'all';
    await this.load();
  }

  // ── Grid ──────────────────────────────────────────────────────

  _renderGrid() {
    const grid = el('seq-grid');
    if (!grid) return;
    const isAdmin = adminGuard.unlocked;
    const scripts = this._activeCategory === 'all'
      ? this._scripts
      : this._scripts.filter(s => s.category === this._activeCategory);

    grid.innerHTML = scripts.map(s => {
      const isRunning = this._running.has(s.name);
      const isLooping = this._looping.has(s.name);
      const label = s.label || s.name.toUpperCase().replace(/_/g, ' ');
      return `
        <div class="seq-card${isRunning ? ' running' : ''}${isLooping ? ' looping' : ''}"
             id="seq-card-${s.name}"
             data-name="${s.name}"
             data-duration="${s.duration || 5}">
          ${isAdmin ? `<div class="seq-card-handle">⠿</div>` : ''}
          <span class="seq-card-loop">🔄</span>
          <span class="seq-card-emoji">${s.emoji}</span>
          <div class="seq-card-wave"><span></span><span></span><span></span><span></span><span></span><span></span></div>
          <span class="seq-card-label">${escapeHtml(label)}</span>
          <div class="seq-card-progress"><div class="seq-card-progress-fill" id="seq-prog-${s.name}"></div></div>
          ${isAdmin ? `<div class="seq-card-play" onclick="scriptEngine.play(event,'${s.name}')">▶</div>` : ''}
        </div>`;
    }).join('');

    this._attachCardEvents(grid, isAdmin);
  }

  _attachCardEvents(grid, isAdmin) {
    grid.querySelectorAll('.seq-card').forEach(card => {
      const name = card.dataset.name;

      if (isAdmin) {
        // Tap emoji → emoji picker
        const emojiEl = card.querySelector('.seq-card-emoji');
        emojiEl.addEventListener('click', (e) => {
          e.stopPropagation();
          const s = this._scripts.find(x => x.name === name);
          emojiPicker.open(s.emoji, async (emoji) => {
            await api('/choreo/set-emoji', 'POST', { name, emoji });
            await this.load();
          });
        });

        // Tap label → inline rename
        const labelEl = card.querySelector('.seq-card-label');
        labelEl.addEventListener('click', (e) => {
          e.stopPropagation();
          this._startRename(card, name);
        });

        // Drag (pointer events)
        this._attachDrag(card, name);

      } else {
        // Normal mode: tap = play/stop, long press = loop
        card.addEventListener('pointerdown', (e) => this._onPointerDown(e, name));
        card.addEventListener('pointerup',   (e) => this._onPointerUp(e, name));
        card.addEventListener('pointermove', (e) => this._onPointerMove(e));
        card.addEventListener('pointercancel', () => this._clearLongPress());
      }
    });
  }

  // ── Long press (normal mode) ──────────────────────────────────

  _onPointerDown(e, name) {
    this._longPressTimer = setTimeout(() => {
      this._longPressTimer = null;
      this.play(e, name, true);
    }, 500);
  }

  _onPointerUp(e, name) {
    if (this._longPressTimer) {
      clearTimeout(this._longPressTimer);
      this._longPressTimer = null;
      // Short tap = play/stop
      if (this._running.has(name)) this.stop(name);
      else this.play(e, name, false);
    }
  }

  _onPointerMove(e) {
    if (this._longPressTimer) {
      clearTimeout(this._longPressTimer);
      this._longPressTimer = null;
    }
  }

  _clearLongPress() {
    if (this._longPressTimer) { clearTimeout(this._longPressTimer); this._longPressTimer = null; }
  }

  // ── Admin drag to pill ────────────────────────────────────────

  _attachDrag(card, name) {
    let dragging = false;
    let startX = 0, startY = 0;
    let ghost = null;

    card.addEventListener('pointerdown', (e) => {
      startX = e.clientX; startY = e.clientY;
      card.setPointerCapture(e.pointerId);
    });

    card.addEventListener('pointermove', (e) => {
      const dx = Math.abs(e.clientX - startX);
      const dy = Math.abs(e.clientY - startY);
      if (!dragging && (dx > 8 || dy > 8)) {
        dragging = true;
        card.classList.add('dragging');
        // Illuminate pills
        document.querySelectorAll('.seq-pill[data-cat]:not([data-cat="all"])').forEach(p => {
          if (p.dataset.cat !== 'all') p.classList.add('drop-target');
        });
        // Create ghost
        ghost = document.createElement('div');
        ghost.style.cssText = `position:fixed;pointer-events:none;z-index:9999;opacity:0.8;font-size:28px;`;
        ghost.textContent = card.querySelector('.seq-card-emoji').textContent;
        document.body.appendChild(ghost);
      }
      if (dragging && ghost) {
        ghost.style.left = (e.clientX - 16) + 'px';
        ghost.style.top  = (e.clientY - 16) + 'px';
      }
    });

    card.addEventListener('pointerup', async (e) => {
      if (!dragging) {
        // Was a tap in admin mode — play
        if (this._running.has(name)) this.stop(name);
        else this.play(e, name, false);
        return;
      }
      dragging = false;
      card.classList.remove('dragging');
      if (ghost) { ghost.remove(); ghost = null; }
      document.querySelectorAll('.seq-pill').forEach(p => p.classList.remove('drop-target'));

      // Find pill under pointer
      const target = document.elementFromPoint(e.clientX, e.clientY);
      const pill = target?.closest('.seq-pill[data-cat]');
      if (pill && pill.dataset.cat !== 'all') {
        const newCat = pill.dataset.cat;
        await api('/choreo/set-category', 'POST', { name, category: newCat });
        toast(`Moved to ${newCat}`, 'ok');
        await this.load();
      }
    });

    card.addEventListener('pointercancel', () => {
      dragging = false;
      card.classList.remove('dragging');
      if (ghost) { ghost.remove(); ghost = null; }
      document.querySelectorAll('.seq-pill').forEach(p => p.classList.remove('drop-target'));
    });
  }

  // ── Inline rename ─────────────────────────────────────────────

  _startRename(card, name) {
    const labelEl = card.querySelector('.seq-card-label');
    const current = labelEl.textContent;
    const input = document.createElement('input');
    input.className = 'input-text';
    input.style.cssText = 'width:100%;font-size:10px;padding:2px 4px;text-align:center;';
    input.value = current;
    labelEl.replaceWith(input);
    input.focus(); input.select();

    const save = async () => {
      const newLabel = input.value.trim();
      await api('/choreo/set-label', 'POST', { name, label: newLabel });
      await this.load();
    };
    input.addEventListener('keydown', e => { if (e.key === 'Enter') save(); if (e.key === 'Escape') this.load(); });
    input.addEventListener('blur', save);
  }

  // ── Playback ──────────────────────────────────────────────────

  play(event, name, loop = false) {
    if (event && event.stopPropagation) event.stopPropagation();
    this._running.add(name);
    if (loop) this._looping.add(name); else this._looping.delete(name);
    const card = el(`seq-card-${name}`);
    if (card) {
      card.classList.add('running');
      card.classList.toggle('looping', loop);
      this._startProgress(card, name);
    }
    api('/choreo/play', 'POST', { name }).then(d => {
      if (!d) {
        this._running.delete(name);
        this._looping.delete(name);
        if (card) { card.classList.remove('running', 'looping'); }
      } else {
        toast(`${loop ? '🔄 ' : '▶ '}${(name).toUpperCase()} playing`, 'ok');
        poller.poll();
      }
    });
  }

  stop(name) {
    api('/choreo/stop', 'POST').then(() => {
      this._running.delete(name);
      this._looping.delete(name);
      const card = el(`seq-card-${name}`);
      if (card) { card.classList.remove('running', 'looping'); }
      toast(`${name.toUpperCase()} stopped`, 'ok');
    });
  }

  stopAll() {
    api('/choreo/stop', 'POST').then(() => {
      this._running.clear();
      this._looping.clear();
      document.querySelectorAll('.seq-card').forEach(c => c.classList.remove('running', 'looping'));
      const list = el('running-scripts');
      if (list) list.textContent = '—';
      toast('Sequences stopped', 'ok');
    });
  }

  _startProgress(card, name) {
    const fill = el(`seq-prog-${name}`);
    if (!fill) return;
    const dur = parseFloat(card.dataset.duration) || 5;
    fill.style.transition = 'none';
    fill.style.width = '0%';
    requestAnimationFrame(() => {
      fill.style.transition = `width ${dur}s linear`;
      fill.style.width = '100%';
    });
  }

  updateRunning(running) {
    const names = new Set(running.map(s => s.name));
    this._running = names;
    document.querySelectorAll('.seq-card').forEach(card => {
      const name = card.dataset.name;
      const isRunning = names.has(name);
      card.classList.toggle('running', isRunning);
      if (!isRunning) {
        this._looping.delete(name);
        card.classList.remove('looping');
        const fill = el(`seq-prog-${name}`);
        if (fill) { fill.style.transition = 'none'; fill.style.width = '0%'; }
      }
    });
    const list = el('running-scripts');
    if (list) list.textContent = running.length ? running.map(s => s.name).join(', ') : '—';
  }

  _syncAdminMode() {
    this._renderPills();
    this._renderGrid();
  }
}

const scriptEngine = new ScriptEngine();

async function loadScripts() { await scriptEngine.load(); }
```

- [ ] **Step 3: Hook admin mode changes to re-render sequences**

Find the `_unlock()` method in `AdminGuard` and add after the existing callback logic:

```javascript
scriptEngine._syncAdminMode();
```

Find the `lock()` method in `AdminGuard` and add at the end:

```javascript
scriptEngine._syncAdminMode();
```

- [ ] **Step 4: Commit**

```bash
git add master/static/js/app.js
git commit -m "Feat: ScriptEngine rewrite — categories, pills, cards, drag-to-pill, emoji picker, rename, loop"
```

---

## Task 8: Deploy and verify

- [ ] **Step 1: Commit + push + deploy**

```bash
git add -A
git push
```

Then deploy via paramiko:
```python
import paramiko, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.2.104', username='artoo', password='deetoo', timeout=10)
stdin, stdout, stderr = c.exec_command('cd /home/artoo/r2d2 && bash scripts/update.sh 2>&1')
for line in stdout: print(line, end='')
c.close()
```

- [ ] **Step 2: Verify on Pi — categories JSON exists**

```python
_, out, _ = c.exec_command('cat /home/artoo/r2d2/master/config/choreo_categories.json')
print(out.read().decode())
```

Expected: 6 categories printed as JSON.

- [ ] **Step 3: Verify endpoints**

```bash
curl http://192.168.2.104:5000/choreo/categories
curl http://192.168.2.104:5000/choreo/list | python3 -m json.tool | head -20
```

`/choreo/list` must return objects with `name`, `label`, `category`, `emoji` fields.

- [ ] **Step 4: Browser test — normal mode**

Open `http://192.168.2.104:5000` → SEQUENCES tab:
- Pills show: ALL · 🎭 Performance · 😤 Emotions · 🚶 Behavior · 🔵 Dome · 🔧 Tests · 📦 New Choreo
- Click "🎭 Performance" → grid shows cantina, leia, march etc.
- Click "😤 Emotions" → grid shows angry, scared, curious etc.
- Click a card → it plays, border pulses teal, soundwave appears, progress bar advances
- Long press a card → plays with 🔄 spinning in corner
- Tap running card → stops

- [ ] **Step 5: Browser test — admin mode**

Log in as admin → go to SEQUENCES tab:
- Admin hint appears under pills
- Cards show ⠿ handle and ▶ button
- Tap emoji on card → emoji picker opens → select → emoji changes on card
- Tap label on card → becomes input → type new name → Enter → saves
- Drag card → pills illuminate teal → drop on different pill → card moves to new category
- Drag pills → reorders them
- Click emoji on pill → emoji picker opens → select → pill emoji updates
- Click "+ Cat" → create new category
- Click ✕ on category pill → confirm → category deleted, sequences move to New Choreo

- [ ] **Step 6: Tablet/Android test**

Open on tablet or Android app:
- Touch targets comfortable (pills and cards tall enough)
- Emoji picker appears as bottom sheet
- Drag to pill works with touch

- [ ] **Step 7: Sync Android assets if needed**

```bash
cp master/static/js/app.js android/app/src/main/assets/js/app.js
cp master/static/css/style.css android/app/src/main/assets/css/style.css
```

Then rebuild APK if needed.

- [ ] **Step 8: Final commit**

```bash
git add -A
git commit -m "Feat: sequences tab redesign — categories, emoji picker, drag-to-pill, playing state F"
git push
```

---

## Self-Review

**Spec coverage check:**
- ✅ `choreo_categories.json` with 6 default categories — Task 1
- ✅ `.chor` migration (category/emoji/label) — Task 2
- ✅ `/choreo/list` returns objects — Task 3
- ✅ `/choreo/categories` GET — Task 3
- ✅ `POST /choreo/categories` create/update/reorder/delete — Task 4
- ✅ `POST /choreo/set-category` — Task 4
- ✅ `POST /choreo/set-emoji` — Task 4
- ✅ `POST /choreo/set-label` — Task 4
- ✅ Pills like Audio tab — Task 5 + 7
- ✅ Admin drag-to-pill — Task 7 (`_attachDrag`)
- ✅ Pill reorder (SortableJS) — Task 7 (`_pillSortable`)
- ✅ Pill emoji edit → picker — Task 7 (`onPillEmojiClick`)
- ✅ Create category — Task 7 (`createCategory`)
- ✅ Delete category — Task 7 (`deleteCategory`)
- ✅ Admin hint text — Task 5 HTML + Task 7 (`_renderPills`)
- ✅ Tap emoji on card → picker — Task 7
- ✅ Tap label → inline rename — Task 7 (`_startRename`)
- ✅ ▶ button in admin — Task 7 + Task 6 CSS
- ✅ Normal mode: tap = play, long press = loop — Task 7 (`_onPointerDown/Up`)
- ✅ Playing state F: pulse border + soundwave + progress bar — Task 6 CSS + Task 7 (`_startProgress`)
- ✅ 🔄 loop indicator — Task 6 CSS + Task 7
- ✅ Emoji picker: ~100 emojis, 8 sections, search — Task 7 (`EmojiPicker`)
- ✅ Tablet: 44px targets, bottom sheet picker — Task 6 CSS (`@media`)
- ✅ New choreo defaults to "newchoreo" — Task 4 (`_SYSTEM_CATEGORY`) + enforced by `/choreo/save`
- ✅ Admin mode re-renders when unlocked/locked — Task 7 (`_syncAdminMode`)
- ✅ Android asset sync — Task 8 Step 7

**No placeholders found.**

**Type consistency:** `scriptEngine` used consistently, `emojiPicker` consistent, `api()` used throughout matching existing pattern.
