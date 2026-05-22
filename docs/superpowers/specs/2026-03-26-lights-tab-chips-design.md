# Lights Tab — Colored Animation Chips Design

> **Approved by user:** 2026-03-26 via brainstorm session (Option A selected)

## Goal

Replace the current flat `.anim-btn` rectangular buttons in the ANIMATIONS card with **colored pill chips** — each animation gets its own color accent matching its personality. Add a live **mode status badge** showing the currently active mode. Keep all other structure (3 cards, FLD preview, PSI, text input, swatches, sequences) identical.

## Architecture

Pure CSS + JS change. No backend changes needed. The color data already lives in `LIGHT_ANIMATIONS` array in `app.js` — we extend it with a `color` field per animation. CSS gets a new `.anim-chip` class replacing `.anim-btn`. A `#mode-status-badge` element shows current active mode.

## Files Modified

- `master/static/css/style.css` — add `.anim-chip`, `.anim-chip.active`, mode badge styles
- `master/static/js/app.js` — add `color` field to `LIGHT_ANIMATIONS`, update `loadLightSequences()` to render chips, update `playAnimation()` to highlight active chip, add mode status update
- `master/templates/index.html` — add `#mode-status-badge` element in LIGHTS CONTROL card
- `master/static/css/style.css` + `android/app/src/main/assets/` — sync Android assets

## Design Details

### Color mapping per animation

| Animation | Color |
|-----------|-------|
| Random | `#00aaff` (blue) |
| Flash | `#ffcc00` (yellow) |
| Alarm | `#ff3355` (red) |
| Short Circuit | `#ff8800` (orange) |
| Scream | `#00ffea` (cyan) |
| Leia | `#aa66ff` (purple) |
| I ♥ U | `#ff66cc` (pink) |
| Panel Sweep | `#00aaff` (blue) |
| Pulse Monitor | `#00cc66` (green) |
| Star Wars Scroll | `#ffdd00` (gold) |
| Imperial March | `#ff8800` (orange) |
| Disco (timed) | `#ff66cc` (pink) |
| Disco | `#ff66cc` (pink) |
| Rebel Symbol | `#ff3355` (red) |
| Knight Rider | `#ff3300` (red-orange) |
| Test White | `#ddeeff` (white) |
| Red On | `#ff2244` (red) |
| Green On | `#00cc66` (green) |
| Lightsaber | `#44ff88` (green glow) |
| Off | `#445566` (dim) |
| VU Meter (timed) | `#00cc66` (green) |
| VU Meter | `#00cc66` (green) |

### Mode status badge

- Located between PSI swatches and the ANIMATIONS card
- Shows: `● {ICON} {MODE NAME}` with the mode's color
- Updates when: animation chip clicked, Random/Off buttons pressed, poller data arrives
- Animated with subtle pulse glow

### Chip layout

- `display: flex; flex-wrap: wrap; gap: 6px`
- Pill shape: `border-radius: 20px; padding: 5px 11px`
- Font: 9px monospace, letter-spacing 0.4px
- Border + background use the animation's color with opacity
- `:hover` → `filter: brightness(1.3)`
- `.active` → `filter: brightness(1.5); box-shadow: 0 0 10px currentColor`

## What Does NOT Change

- 3-card structure
- FLD preview (3×10 dots, CSS animations)
- PSI dots + swatches
- RANDOM / OFF buttons
- Text input + FLD/RLD/BOTH selector
- LIGHT SEQUENCES card
- All backend APIs

## Testing

- Open Lights tab → chips render with colors
- Click each chip → active highlight + mode badge updates
- Click RANDOM / OFF → mode badge updates
- Poller updates → mode badge stays in sync
- Mobile: chips wrap correctly on small screen
- Android: assets synced, APK rebuilt
