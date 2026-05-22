# Sequences Tab — Redesign Spec
**Date:** 2026-04-11
**Status:** Approved — ready for implementation

---

## Overview

Redesign the SEQUENCES tab to add categories (like the Audio tab), custom emojis per sequence and per category, sequence renaming, admin drag-and-drop category management, and a rich animated playing state.

---

## 1. Data Layer

### `master/config/choreo_categories.json`
New file, gitignored. Defines all categories with their display order.

```json
[
  { "id": "performance", "label": "Performance",  "emoji": "🎭", "order": 0 },
  { "id": "emotion",     "label": "Emotions",     "emoji": "😤", "order": 1 },
  { "id": "behavior",    "label": "Behavior",     "emoji": "🚶", "order": 2 },
  { "id": "dome",        "label": "Dome",         "emoji": "🔵", "order": 3 },
  { "id": "test",        "label": "Tests",        "emoji": "🔧", "order": 4 },
  { "id": "newchoreo",   "label": "New Choreo",   "emoji": "📦", "order": 5 }
]
```

- `"newchoreo"` is the system default category — cannot be deleted
- All other categories can be deleted (sequences move to `newchoreo` first)

### `.chor` file — new `meta` fields

```json
{
  "meta": {
    "name":     "cantina",
    "label":    "Cantina Band",
    "category": "performance",
    "emoji":    "🪗",
    "duration": 35.2
  }
}
```

| Field | Description | Fallback |
|-------|-------------|---------|
| `meta.label` | Display name shown in UI | Filename in UPPERCASE (e.g. `CANTINA`) |
| `meta.category` | Category ID | `"newchoreo"` |
| `meta.emoji` | Custom emoji for this sequence | Auto-derived from filename via regex |

**New choreo created in editor** → `category: "newchoreo"`, `emoji: ""`, `label: ""`

### Initial category assignments (migration)

| Category | Choreos |
|----------|---------|
| 🎭 Performance | cantina, leia, march, disco, birthday, party, celebrate, theme, r2kt, wolfwhistle |
| 😤 Emotions | angry, scared, curious, excited, evil, taunt |
| 🚶 Behavior | patrol, scan, startup, message, alert, failure, malfunction |
| 🔵 Dome | dome_dance, flap_dome, flap_dome_fast, flap_dome_side, ripple_dome, ripple_dome_fast, ripple_dome_side, hp_twitch, slow_open_close |
| 🔧 Tests | test, dome_test1, dome_test2, body_test, panel_test, looping_sounds, looping_sounds_quick |
| 📦 New Choreo | my_show2 + all user-created choreos without a category |

---

## 2. API

All new endpoints in `master/api/choreo_bp.py` (extend existing blueprint).

```
GET  /choreo/list
     Returns: [{name, label, category, emoji}]
     emoji = meta.emoji if set, else auto-derived from name
     label = meta.label if set, else name.upper().replace('_',' ')

GET  /choreo/categories
     Returns: [{id, label, emoji, order}] sorted by order

POST /choreo/categories          [admin]
     Body: {action, ...}
     action = "create"  → {id, label, emoji}
     action = "update"  → {id, emoji}           ← change emoji of a category
     action = "reorder" → {order: ["id1","id2",...]}
     action = "delete"  → {id}                  ← moves sequences to "newchoreo"

POST /choreo/set-category        [admin]
     Body: {name, category}
     Updates meta.category in the .chor file

POST /choreo/set-emoji           [admin]
     Body: {name, emoji}
     Updates meta.emoji in the .chor file
     Empty string → clears override (falls back to auto-derived)

POST /choreo/set-label           [admin]
     Body: {name, label}
     Updates meta.label in the .chor file
     Empty string → clears label (falls back to filename)
```

Admin endpoints require admin auth (same guard as choreo save/delete).

---

## 3. UI — Normal Mode

### Layout
Pills row at top → identical pattern to Audio tab.  
Grid of sequence cards below.

### Pills
- One pill per category, ordered by `choreo_categories.json`
- "ALL" pill first (shows all sequences regardless of category)
- Click pill → filters grid to that category
- Active pill highlighted in teal

### Sequence cards (normal mode)
```
┌──────────────┐
│           🔄 │  ← loop icon (only when looping, spinning)
│      😡      │  ← emoji (big, centered)
│    ANGRY     │  ← meta.label or filename fallback
└──────────────┘
```

**Interactions:**
| Gesture | Result |
|---------|--------|
| Tap | Play once |
| Long press 500ms | Play in loop mode |
| Tap running card | Stop |

### Playing state (Option F)
Triggered when any sequence starts playing:

1. **Border** — teal, pulsing animation (1.8s ease-in-out)
2. **Background** — subtle teal tint (#00ffea08)
3. **Label replaced** — animated soundwave bars (6 bars, staggered wave animation) while playing
4. **Progress bar** — 3px bar at bottom of card, teal→green gradient, animates across the duration
5. **Loop icon** — 🔄 appears top-right, spinning, only when in loop mode

### Loop mode
- Long press 500ms → `POST /scripts/run` with `{"loop": true}`
- 🔄 visible and spinning on card while loop is active
- Tap running card → stop (same as non-loop)

---

## 4. UI — Admin Mode

Admin mode is active when `adminGuard.unlocked === true`.

### Pills (admin additions)
- Pills are **draggable** (SortableJS, horizontal) to reorder categories
- On drop → `POST /choreo/categories` with `action: "reorder"`
- **Click emoji on pill** → emoji picker popup → select → `POST /choreo/categories {action:"update"}`
- **Pill `+`** → modal: enter label + pick emoji → `POST /choreo/categories {action:"create"}`
- **Pill `✕`** → appears on hover; if category has sequences → confirm dialog moves them to NewChoreo first; then `POST /choreo/categories {action:"delete"}`
- **Hint text** under pills (admin only):
  > `⠿ Drag les pills pour réordonner · Drag une carte sur une pill pour changer sa catégorie`

### Sequence cards (admin mode)
```
┌──────────────┐
│ ⠿         ▶ │  ← drag handle left, play button right
│      😡      │  ← emoji (tap → emoji picker)
│    ANGRY     │  ← label (tap → inline rename)
└──────────────┘
```

**Interactions (admin only):**
| Gesture | Zone | Result |
|---------|------|--------|
| Tap | Emoji | Open emoji picker |
| Tap | Name/label | Inline rename (input field, Enter to save) |
| Tap | ▶ button | Play sequence |
| Drag 300ms | Anywhere on card | Drag mode — pills illuminate as drop targets |
| Drop | On a pill | `POST /choreo/set-category` → updates category |

**Drag behavior:**
- SortableJS `delay: 300`, works on both mouse and touch
- While dragging: pills area highlights, each pill gets a drop-target glow
- Ghost card follows cursor/finger
- On drop: card moves to the selected category's filtered view

### Emoji picker (admin)
Triggered by tapping the emoji on a card OR the emoji on a pill.

- Popup (desktop) or bottom sheet (tablet/mobile)
- Search field at top
- ~100 emojis organized in 8 sections:
  - 😤 Émotions (24 emojis)
  - 🎵 Musique & Sons (16)
  - 🎭 Show & Fête (12)
  - 🏃 Mouvement & Danse (12)
  - ⚡ Actions & Alertes (12)
  - 🔧 Tech & Robot (12)
  - ⭐ Star Wars & Espace (16)
  - 🚪 Panneaux & Dôme (8)
- Footer: preview of selected emoji + Cancel + Apply buttons
- Apply → `POST /choreo/set-emoji` (card) or `POST /choreo/categories {action:"update"}` (pill)
- Empty emoji (clear button) → reverts to auto-derived

### Inline rename
- Tap the label text on a card (admin mode)
- Text becomes `<input>` pre-filled with current label
- Enter or blur → `POST /choreo/set-label`
- Escape → cancel

---

## 5. Tablet / Android

All touch targets minimum 44px height/width:
- Pills: `min-height: 44px`, larger font
- Card emojis: 34px font-size
- Drag handles: 30×30px touch target
- Play ▶ button: 30×30px

**Emoji picker on tablet:** bottom sheet instead of popup.
- Slides up from bottom of screen
- Has drag handle bar at top
- Scrollable emoji list
- Same sections as desktop

**SortableJS touch:** built-in touch support, no extra config needed.

---

## 6. Choreo Editor — Integration

- New choreo created → `meta.category = "newchoreo"`, `meta.emoji = ""`, `meta.label = ""`
- No category/emoji/label pickers in the editor — managed exclusively via the Sequences tab
- Editor saves category/emoji/label as-is when saving other changes

---

## 7. Playing State — Technical Notes

Progress bar duration: use `meta.duration` from the `.chor` file to set CSS animation duration.  
If duration unknown → progress bar animates at 5s default (loop).

Soundwave bars: 6 `<div>` elements with staggered `animation-delay`, `scaleY` animation.  
Replace the label text node only — card structure stays the same.

Multiple playing sequences: each card manages its own state independently via `_running Set` in `ScriptEngine`.

---

## 8. Files to Modify

| File | Changes |
|------|---------|
| `master/api/choreo_bp.py` | Add 5 new endpoints + enhance `/choreo/list` |
| `master/config/choreo_categories.json` | New file (create) |
| `master/choreographies/*.chor` | Add `meta.category`, `meta.emoji`, `meta.label` to all files |
| `master/templates/index.html` | Sequences tab HTML restructure |
| `master/static/js/app.js` | `ScriptEngine` full rewrite + SortableJS integration |
| `master/static/css/style.css` | New animations + card states + pill admin styles |

---

## 9. Out of Scope

- HUB/drone view update (separate future task)
- Sequence scheduling (in Settings brainstorm backlog)
- Sorting sequences within a category (drag-to-reorder within same category)
