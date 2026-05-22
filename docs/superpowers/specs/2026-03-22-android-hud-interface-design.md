# R2-D2 Android HUD Interface — Design Spec
**Date:** 2026-03-22
**Status:** Approved

---

## Context

The Android app currently loads `mobile.html` on phones (via `smallestScreenWidthDp < 600`). This spec replaces that interface with a drone-inspired HUD designed exclusively for landscape mode.

The existing web dashboard (`index.html`) and all Python backend code are unchanged. Only the Android WebView asset (`mobile.html`, `mobile.css`, `mobile.js`) is replaced.

---

## Overview

A single-screen HUD interface rendered in a WebView, locked to landscape orientation. A simulated camera feed fills the background. All controls are layered on top as semi-transparent overlays. Secondary controls (audio, sequences, lights) slide up from the bottom as a drawer — the drive view is never fully replaced.

**Minimum supported viewport height:** 400px (landscape on target device OnePlus 10 = ~412px). All positioning calculations assume ≥ 400px height.

---

## Architecture

### Screen Lock
- `AndroidManifest.xml`: `android:screenOrientation="landscape"` already present — no change needed
- `MainActivity.kt`: keep `smallestScreenWidthDp < 600` check — landscape-only means `loadDashboard()` always loads `mobile.html` on phones

### Files Modified
- `android/app/src/main/assets/mobile.html` — full rewrite
- `android/app/src/main/assets/css/mobile.css` — full rewrite
- `android/app/src/main/assets/js/mobile.js` — extend existing v2 (no regression on API calls)
- `master/templates/mobile.html` — kept in sync (Flask server version)
- `master/static/css/mobile.css` — kept in sync
- `master/static/js/mobile.js` — kept in sync

### Android Back Button
When the drawer is open: back button closes the drawer (JS `popstate` listener via `history.pushState` on drawer open, `history.back()` triggers `popstate` to close).
When drawer is closed: back button does nothing (consume event — prevent accidental app exit during robot control).

### Host Dialog
The status bar IP tap calls `showHostDialog()`. In WebView context this invokes `AndroidBridge.setHost()` via the existing native Android dialog in `MainActivity.kt`. The JS `window.prompt()` fallback remains for browser testing only.

---

## Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ [HB] [UART] [BT]    ·    ● KIDS MODE    ·    32°C  192.168.4.1 │  ← status bar (28px)
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  🔒                    ╔══════╗                                  │  ← lock btn (top-left)
│                        ║  HUD ║  corners                        │
│                        ╚══════╝                                  │
│                                                                  │
│  ┌──────┐                               ┌──────┐                │
│  │  JS  │      [E-STOP ⬡]              │  JS  │                │
│  │ LEFT │   [🔊 AUDIO][🎬 SEQ][💡]    │RIGHT │                │
│  └──────┘                               └──────┘                │
│   PROPULSION                               DÔME                 │
└─────────────────────────────────────────────────────────────────┘
```

**Joystick position:** `left/right: calc(22% - 65px)`, `top: calc(55% - 65px)` — thumb-natural zone. Ring diameter: 130px. At 400px viewport height, ring bottom = 55% of 400 + 65 = 285px. Drawer top edge = 400 − 160 = 240px. Clearance = 285 − 240 = 45px guaranteed.

**E-STOP:** centered horizontally, `top: 70px` (just below status bar + lock btn zone).

**Quick pills:** `top: 140px` (immediately below E-STOP). Three buttons: 🔊 AUDIO · 🎬 SEQ · 💡 LIGHTS.

**Joystick wrapper:** the outer `<div id="hud-drive">` carries the `data-lock` attribute used by CSS lock-mode selectors (replaces the former `#tab-drive` wrapper). All CSS rules of the form `#tab-drive[data-lock="N"] ...` are renamed to `#hud-drive[data-lock="N"] ...`.

---

## Background (Camera Placeholder)

Dark styled background using CSS gradients + scanlines + HUD corner brackets. Structured so that when a camera stream is available, it can be activated by adding a single `<img>` element as the background layer — no CSS or JS refactoring needed.

```html
<!-- Future camera injection point: uncomment when Pi camera stream is ready -->
<!-- <img id="cam-stream" src="http://192.168.4.1:8080/?action=stream"> -->
<div id="cam-bg"></div>  <!-- placeholder active until camera arrives -->
```

CSS: `#cam-stream { position:absolute; inset:0; width:100%; height:100%; object-fit:cover; z-index:0; }`
When `#cam-stream` is added to the DOM, `#cam-bg` can be hidden via `#cam-bg { display:none; }` in a one-line CSS edit.

---

## Bottom Drawer

A panel that slides up from the bottom of the screen over the camera background. The joysticks remain functional while the drawer is open.

**Open:** tap a quick pill only (swipe gesture deferred to future — conflicts with right joystick touch zone)
**Close:** tap ✕ button, tap the backdrop area above the drawer, or Android back button

**Height:** fixed 160px (≤ 40% of 400px minimum viewport). Drawer top edge sits at `viewport_height - 160px` ≥ 240px. Joystick rings bottom edge sits at `55% + 65px` = 285px on a 400px viewport — 45px clearance guaranteed. Drawer does not cover joysticks.

**Backdrop:** semi-transparent overlay behind drawer, above joystick layer — tap closes drawer. Joystick touch events pass through the backdrop only where the rings are (`pointer-events: none` on backdrop, `pointer-events: auto` on drawer panel itself).

**Three drawer modes (pill determines content):**

### AUDIO
- Category row: horizontal scroll of `cat-btn` pills (lazy-loaded on first open, cached)
- Sound grid: wrapping grid of `snd-btn` buttons (name without extension)
- Volume slider + stop button
- Random button per category

### SEQ (Séquences)
- Vertical scrollable list of sequence cards
- Each card: name · ▶ RUN · 🔁 LOOP · ⏹ STOP
- STOP ALL button at bottom

### LIGHTS
- LOGICS section: RANDOM · LEIA · OFF buttons + text input for FLD
- PSI section: OFF · RAND · ● (red) · ● (blue) swatches

**Drawer state:** one active drawer at a time. Opening a second pill closes the first and shows new content.

**Lazy initialization:** `_audioInit` and `_seqInit` flags (from mobile.js v2) are preserved. `loadCategories()` is called on first AUDIO drawer open; `loadSequences()` on first SEQ drawer open. Subsequent opens reuse cached DOM. `switchTab()` is removed — replaced by `openDrawer(tab)` / `closeDrawer()`.

**E-STOP while drawer open:** drawer stays open. `stopAllSeq()` is NOT called automatically — the user sees the current drawer state. The joysticks reset visually. This is intentional: the user may want to inspect the sequence list after an E-STOP.

---

## Z-Index Layers

| Layer | z-index | Elements |
|-------|---------|----------|
| Background | 0 | `#cam-bg`, `#cam-stream` |
| HUD base | 10 | HUD corners, joystick zone `#hud-drive` |
| Drawer backdrop | 20 | semi-transparent tap-to-close overlay |
| Drawer panel | 30 | `#bottom-drawer` |
| Status bar | 40 | `#status-bar` |
| Lock modal | 50 | `#lock-modal` |
| Toast | 60 | `#alert-toast` |

---

## Status Bar

Fixed at top, always visible, `z-index: 40`.

| Zone | Content |
|------|---------|
| Left | `[HB]` `[UART]` `[BT]` indicator pills — green=ok, red=err |
| Center | Mode badge: hidden (Normal) / `● KIDS MODE` orange pulse / `● CHILD LOCK` red pulse |
| Right | `32°C` · `192.168.4.1` (tappable → host dialog) |

**Battery:** removed from status bar. The `/status` API does not return a battery field and adding one would require backend changes (out of scope). No battery display.

---

## Lock System

Button 🔒 `position: absolute; top: 34px; left: 12px; z-index: 15` — above HUD, below drawer.

| Mode | lockMode | Badge | Propulsion | Dome | Button style |
|------|----------|-------|------------|------|-------------|
| Normal | 0 | hidden | 100% speed | free | neutral |
| Kids | 1 | KIDS MODE (orange pulse) | 20% speed | free | orange border |
| Child Lock | 2 | CHILD LOCK (red pulse) | blocked (`canStart=false`) | blocked | red border |

**Cycle:** Normal → Kids → Child Lock (tap lock button)
**Exit Child Lock:** tap lock button → password modal → password `deetoo` → back to Normal

**JS:** `cycleLockMode`, `_applyLockMode`, `MobileJoystick.canStart` unchanged from v2. One change: `_applyLockMode` reads `document.getElementById('hud-drive')` instead of `'tab-drive'`. All CSS selectors updated to `#hud-drive[data-lock="N"]`.

---

## E-STOP

- Permanent red pulse animation (`@keyframes pulse-estop`)
- On tap: all motion stops, joysticks reset, UI shows RESET button in place of E-STOP
- RESET button: calls `/system/estop_reset` + `/bt/estop_reset` (retain both calls from v2)
- Haptic feedback via `AndroidBridge.vibrate(400)`

---

## Animations & Visual Style

- **Color palette:** `#050a10` bg · `#00aaff` primary · `#00cc55` ok · `#ffaa00` warn · `#ff3344` danger
- **HUD corners:** CSS borders, 4 corners, `top: 28px` (below status bar)
- **Scanlines:** `repeating-linear-gradient` on `#cam-bg`
- **Joystick touch glow:** `.js-ring.touching { box-shadow: 0 0 22px rgba(0,120,255,.5); }`
- **Mode pulse:** `@keyframes pulse-warn` (orange, 2s) · `@keyframes pulse-danger` (red, 1.8s)
- **E-STOP pulse:** `@keyframes pulse-estop` (2.5s ease-in-out infinite)
- **Drawer open/close:** `transform: translateY(100%)` → `translateY(0)`, `transition: 250ms ease-out`

---

## API Compatibility

No backend changes. All existing `/audio/*`, `/motion/*`, `/scripts/*`, `/teeces/*`, `/system/*`, `/lock/*`, `/heartbeat`, `/status` endpoints used as-is. `/bt/estop_reset` retained from v2.

---

## Out of Scope

- Live camera stream (MJPEG/WebRTC) — architecture ready, implementation deferred
- Swipe-up gesture to open drawer — deferred (conflicts with joystick touch zones)
- Gamepad button mapping UI
- Tablet layout changes
