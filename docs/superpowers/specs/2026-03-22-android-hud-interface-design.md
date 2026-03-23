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

---

## Architecture

### Screen Lock
- `AndroidManifest.xml`: `android:screenOrientation="landscape"` on `MainActivity`
- `MainActivity.kt`: keep `smallestScreenWidthDp < 600` check — landscape-only means `loadDashboard()` always loads `mobile.html` on phones, but the check remains correct for tablets

### Files Modified
- `android/app/src/main/assets/mobile.html` — full rewrite
- `android/app/src/main/assets/css/mobile.css` — full rewrite
- `android/app/src/main/assets/js/mobile.js` — extend existing v2 (no regression on API calls)
- `master/templates/mobile.html` — kept in sync (Flask server version)
- `master/static/css/mobile.css` — kept in sync
- `master/static/js/mobile.js` — kept in sync

---

## Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ [HB] [UART] [BT]    ·    ● KIDS MODE    ·    🔋87%  32°C  IP  │  ← status bar (28px)
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

**Joystick position:** `left/right: calc(22% - 65px)`, `top: calc(60% - 65px)` — thumb-natural zone for landscape two-hand grip. Ring diameter: 130px.

**E-STOP:** `position: absolute; left: 50%; transform: translateX(-50%); top: ~80px` — centered between joysticks.

**Quick pills:** `top: ~150px` (immediately below E-STOP), centered. Three buttons: 🔊 AUDIO · 🎬 SEQ · 💡 LIGHTS.

---

## Background (Camera Placeholder)

Dark styled background using CSS gradients + scanlines + HUD corner brackets. Structured so that when a camera stream is available, it can be activated by adding a single `<img>` or `<video>` element as the background layer — no CSS or JS refactoring needed.

```html
<!-- Future camera injection point -->
<!-- <img id="cam-stream" src="http://192.168.4.1:8080/?action=stream"> -->
<div id="cam-bg"></div>  <!-- placeholder active until camera arrives -->
```

The `#cam-bg` element switches to `display: none` when `#cam-stream` is present.

---

## Bottom Drawer

A panel that slides up from the bottom of the screen over the camera background. The joysticks remain functional while the drawer is open.

**Open:** tap a quick pill or swipe up from bottom edge
**Close:** tap ✕, tap outside the drawer, or swipe down

**Height:** ~45% of screen height (fits comfortably without covering joysticks)

**Three drawer modes (pill determines content):**

### AUDIO
- Category row: horizontal scroll of `cat-btn` pills
- Sound grid: wrapping grid of `snd-btn` buttons (name without extension)
- Volume slider + stop button
- Random button per category

### SEQ (Séquences)
- Vertical list of sequence cards
- Each card: name · ▶ RUN · 🔁 LOOP · ⏹ STOP
- STOP ALL button at bottom

### LIGHTS
- LOGICS section: RANDOM · LEIA · OFF buttons + text input for FLD
- PSI section: OFF · RAND · ● (red) · ● (blue) swatches

**Drawer state:** one active drawer at a time. Opening a second pill closes the first.

---

## Status Bar

Fixed at top, always visible, `z-index` above everything.

| Zone | Content |
|------|---------|
| Left | `[HB]` `[UART]` `[BT]` indicator pills — green=ok, red=err |
| Center | Mode badge: hidden (Normal) / `● KIDS MODE` orange pulse / `● CHILD LOCK` red pulse |
| Right | `🔋 87%` · `32°C` · `192.168.4.1` (tappable → host dialog) |

---

## Lock System

Button 🔒 top-left of screen (outside status bar, over HUD).

| Mode | lockMode | Badge | Propulsion | Dome | Button style |
|------|----------|-------|------------|------|-------------|
| Normal | 0 | hidden | 100% speed | free | neutral |
| Kids | 1 | KIDS MODE (orange pulse) | 20% speed | free | orange border |
| Child Lock | 2 | CHILD LOCK (red pulse) | blocked (canStart=false) | blocked | red border |

**Cycle:** Normal → Kids → Child Lock (tap lock button)
**Exit Child Lock:** tap lock button → password modal → password `deetoo` → back to Normal

JS implementation unchanged from mobile.js v2 (`cycleLockMode`, `_applyLockMode`, `MobileJoystick.canStart`).

---

## E-STOP

- Permanent red pulse animation
- On tap: all motion stops, joysticks reset, UI shows RESET button
- RESET button replaces E-STOP button until status poll confirms `estop_active: false`
- Haptic feedback via `AndroidBridge.vibrate(400)`

---

## Animations & Visual Style

- **Color palette:** `#050a10` bg · `#00aaff` primary · `#00ff80` ok · `#ffaa00` warn · `#ff3344` danger
- **HUD corners:** CSS borders, 4 corners, always visible
- **Scanlines:** `repeating-linear-gradient` on cam-bg
- **Joystick touch glow:** `.js-ring.touching { box-shadow: 0 0 22px rgba(0,120,255,.5); }`
- **Mode pulse animations:** `@keyframes pulse-warn` (orange, 2s) · `@keyframes pulse-danger` (red, 1.8s)
- **E-STOP pulse:** `@keyframes pulse-estop` (2.5s)
- **Drawer:** CSS `transform: translateY()` transition, 250ms ease-out

---

## API Compatibility

No backend changes. All existing `/audio/*`, `/motion/*`, `/scripts/*`, `/teeces/*`, `/system/*` endpoints used as-is. Heartbeat, status polling, and lock API calls unchanged.

---

## Out of Scope

- Live camera stream (MJPEG/WebRTC) — architecture ready, implementation deferred
- Gamepad button mapping UI
- Tablet layout changes
