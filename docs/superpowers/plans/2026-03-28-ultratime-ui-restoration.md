# Ultratime UI Restoration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the Choreography tab to match the reference screenshot — single command bar, left panel with live FLD/RLD/PSI monitors (top) + block palette (bottom), palette drag-and-drop onto timeline lanes, and styled telemetry gauges with color thresholds.

**Architecture:** Pure frontend — HTML restructure, CSS overhaul, vanilla JS additions inside the existing `choreoEditor` IIFE. No new files, no backend changes. All IDs used by existing JS are preserved so existing functionality (play/stop/save/load/drag-resize/easing) continues to work.

**Tech Stack:** Vanilla JS, HTML5 drag-and-drop API, CSS custom properties (already defined in `:root`), `<canvas>` for FLD/RLD/PSI animation.

---

## File Map

| File | Lines | What Changes |
|------|-------|-------------|
| `master/templates/index.html` | 716–877 | Replace entire choreo tab div with new layout |
| `master/static/css/style.css` | 2495–2866 | Replace choreo CSS section: remove `.chor-header*`/`.chor-topbar`, add `.chor-command-bar`, `.chor-left-panel`, `.chor-monitors`, `.chor-palette`, `.chor-palette-item`, `.chor-psi-*` |
| `master/static/js/app.js` | 4086–4688 | Add `_drawPSI()`, `_initPalette()`, `_addDropToLanes()` inside `choreoEditor`; update `_startMonitor()` and `init()` |

---

## Task 1: HTML — New Choreo Tab Layout

**Files:**
- Modify: `master/templates/index.html` lines 716–877

### Step 1.1 — Replace choreo tab HTML

Find the block:
```
<!-- ================================================================
     TAB CHOREO: Choreography Timeline Editor — ULTRATIME EDITION
================================================================ -->
<div class="tab-content" id="tab-choreo">
```
through the closing `</div>` at line 877, and replace the entire content of `#tab-choreo` with:

```html
<!-- ================================================================
     TAB CHOREO: Choreography Timeline Editor — ULTRATIME EDITION
================================================================ -->
<div class="tab-content" id="tab-choreo">
  <div class="chor-layout">

    <!-- ── Single Command Bar ─────────────────────────────────────── -->
    <div class="chor-command-bar">
      <div class="chor-cmd-brand">R2-D2 — <span style="color:var(--cyan)">ULTRATIME</span></div>
      <div class="chor-cmd-timecode" id="chor-timecode">00:00.000</div>
      <div class="chor-cmd-sep"></div>
      <div class="chor-cmd-gauges">
        <span class="chor-cmd-gauge" id="chor-stat-battery" title="Battery voltage">—V</span>
        <span class="chor-cmd-gauge-sep">·</span>
        <span class="chor-cmd-gauge" id="chor-stat-temp" title="VESC temperature">—°C</span>
        <span class="chor-cmd-gauge-sep">·</span>
        <span class="chor-cmd-gauge" id="chor-stat-current" title="VESC current">—A</span>
        <span class="chor-cmd-gauge-sep">·</span>
        <span class="chor-cmd-gauge dim"><span id="chor-duration">—</span></span>
      </div>
      <div class="chor-cmd-sep"></div>
      <select id="chor-select" class="input-select-sm" style="width:150px">
        <option value="">— select —</option>
      </select>
      <button class="btn btn-sm" onclick="choreoEditor.newChor()">+ NEW</button>
      <div class="chor-cmd-sep"></div>
      <button class="btn btn-active btn-sm" id="chor-btn-play" onclick="choreoEditor.play()">▶ PLAY</button>
      <button class="btn btn-danger btn-sm" id="chor-btn-stop" onclick="choreoEditor.stop()">⏹ STOP</button>
      <div class="chor-cmd-sep"></div>
      <span class="chor-cmd-label">SNAP</span>
      <button class="chor-snap-btn active" id="chor-snap-01" onclick="choreoEditor.setSnap(0.1)">0.1s</button>
      <button class="chor-snap-btn" id="chor-snap-05" onclick="choreoEditor.setSnap(0.5)">0.5s</button>
      <button class="chor-snap-btn" id="chor-snap-off" onclick="choreoEditor.setSnap(0)">OFF</button>
      <div class="chor-cmd-sep"></div>
      <span class="chor-cmd-label">ZOOM</span>
      <button class="btn btn-sm" onclick="choreoEditor.zoom(-10)">−</button>
      <button class="btn btn-sm" onclick="choreoEditor.zoom(10)">+</button>
      <div style="margin-left:auto;display:flex;gap:6px;align-items:center">
        <button class="btn btn-sm" onclick="choreoEditor.save()">💾 SAVE</button>
        <button class="btn btn-sm" onclick="choreoEditor.exportScr()">📄 .SCR</button>
        <div class="chor-conn" id="chor-conn">● CONNECTED</div>
      </div>
    </div>

    <!-- ── Body ──────────────────────────────────────────────────── -->
    <div class="chor-body">

      <!-- LEFT PANEL: monitors (top) + palette (bottom) -->
      <div class="chor-left-panel" id="chor-monitor">

        <!-- Top half: Live Monitors (FLD / RLD / PSI) -->
        <div class="chor-monitors">
          <div class="chor-monitor-title">LIVE MONITOR</div>

          <div class="chor-monitor-section">
            <div class="chor-monitor-label">FLD</div>
            <canvas id="chor-fld-canvas" class="chor-pixel-canvas" width="108" height="44"></canvas>
          </div>

          <div class="chor-monitor-section">
            <div class="chor-monitor-label">RLD</div>
            <canvas id="chor-rld-canvas" class="chor-pixel-canvas" width="108" height="26"></canvas>
          </div>

          <div class="chor-monitor-section chor-psi-row">
            <div class="chor-psi-item">
              <div class="chor-monitor-label">PSI·F</div>
              <canvas id="chor-psi-f-canvas" class="chor-psi-canvas" width="24" height="24"></canvas>
            </div>
            <div class="chor-psi-item">
              <div class="chor-monitor-label">PSI·R</div>
              <canvas id="chor-psi-r-canvas" class="chor-psi-canvas" width="24" height="24"></canvas>
            </div>
          </div>
        </div><!-- /chor-monitors -->

        <!-- Bottom half: Block Palette -->
        <div class="chor-palette" id="chor-palette">
          <div class="chor-palette-title">PALETTE</div>
          <!-- Populated by choreoEditor._initPalette() -->
        </div>

      </div><!-- /chor-left-panel -->

      <!-- Track label column -->
      <div class="chor-labels" id="chor-labels">
        <div class="chor-label-spacer"></div>
        <div class="chor-track-label" data-track="audio">AUDIO</div>
        <div class="chor-track-label" data-track="lights">LIGHTS</div>
        <div class="chor-track-label chor-track-label-dome" data-track="dome">DOME °</div>
        <div class="chor-track-label" data-track="servos">SERVOS</div>
        <div class="chor-track-label" data-track="propulsion">PROPULSION</div>
      </div>

      <!-- Scrollable timeline -->
      <div class="chor-scroll-wrap" id="chor-scroll">
        <div class="chor-canvas" id="chor-canvas">
          <div class="chor-ruler" id="chor-ruler"></div>
          <div class="chor-lane chor-lane-audio" id="chor-lane-audio" data-track="audio">
            <canvas class="chor-waveform-canvas" id="chor-waveform-canvas"></canvas>
          </div>
          <div class="chor-lane" id="chor-lane-lights"     data-track="lights"></div>
          <div class="chor-lane chor-lane-dome" id="chor-lane-dome" data-track="dome"></div>
          <div class="chor-lane" id="chor-lane-servos"     data-track="servos"></div>
          <div class="chor-lane" id="chor-lane-propulsion" data-track="propulsion"></div>
          <div class="chor-playhead" id="chor-playhead">
            <div class="chor-playhead-head"></div>
          </div>
        </div>
      </div>

      <!-- Right: Properties + Telemetry -->
      <div class="chor-props" id="chor-props">

        <div class="chor-alarms" id="chor-alarms">
          <span class="chor-alarms-dot ok" id="chor-alarms-dot">●</span>
          <span id="chor-alarms-text" style="font-size:8px;letter-spacing:1.5px">NO ALARMS</span>
        </div>

        <div class="chor-telem-compact" id="chor-telem-section" style="display:none">
          <div class="chor-telem-row">
            <span class="chor-telem-key">VOLT</span>
            <div class="chor-telem-bar-wrap"><div class="chor-telem-bar" id="chor-telem-v-bar"></div></div>
            <span class="chor-telem-val" id="chor-telem-v">—</span>
          </div>
          <div class="chor-telem-row">
            <span class="chor-telem-key">TEMP</span>
            <div class="chor-telem-bar-wrap"><div class="chor-telem-bar" id="chor-telem-t-bar"></div></div>
            <span class="chor-telem-val" id="chor-telem-t">—</span>
          </div>
          <div class="chor-telem-row">
            <span class="chor-telem-key">CURR</span>
            <div class="chor-telem-bar-wrap"><div class="chor-telem-bar" id="chor-telem-c-bar"></div></div>
            <span class="chor-telem-val" id="chor-telem-c">—</span>
          </div>
        </div>

        <div class="chor-props-title">SELECTED BLOCK</div>
        <div id="chor-props-content" style="color:var(--text-dim);font-size:10px;padding:10px 8px">
          Select a block to inspect.
        </div>

        <div id="chor-easing-wrap" style="display:none;padding:0 8px 8px">
          <div class="chor-props-title" style="border:none;margin-bottom:4px">EASING</div>
          <canvas id="chor-easing-canvas" width="184" height="70"
            style="width:100%;border:1px solid var(--border);border-radius:3px;background:var(--bg3)"></canvas>
          <div style="display:flex;gap:4px;flex-wrap:wrap;margin-top:4px">
            <button class="chor-ease-btn" onclick="choreoEditor.setEasing('linear')">LINEAR</button>
            <button class="chor-ease-btn" onclick="choreoEditor.setEasing('ease-in')">EASE IN</button>
            <button class="chor-ease-btn" onclick="choreoEditor.setEasing('ease-out')">EASE OUT</button>
            <button class="chor-ease-btn" onclick="choreoEditor.setEasing('ease-in-out')">IN-OUT</button>
          </div>
        </div>

      </div><!-- /chor-props -->

    </div><!-- /chor-body -->

  </div><!-- /chor-layout -->
</div>
```

### Step 1.2 — Verify all element IDs survived the rewrite

Confirm these IDs still exist (used by existing JS):
- `chor-timecode`, `chor-duration`, `chor-conn`
- `chor-stat-battery`, `chor-stat-temp`, `chor-stat-current`
- `chor-select`, `chor-btn-play`, `chor-btn-stop`
- `chor-snap-01`, `chor-snap-05`, `chor-snap-off`
- `chor-monitor` (used by `_startMonitor` guard)
- `chor-fld-canvas`, `chor-rld-canvas`
- `chor-labels`, `chor-scroll`, `chor-canvas`, `chor-ruler`
- `chor-lane-audio`, `chor-lane-lights`, `chor-lane-dome`, `chor-lane-servos`, `chor-lane-propulsion`
- `chor-waveform-canvas`, `chor-playhead`
- `chor-props`, `chor-alarms`, `chor-alarms-dot`, `chor-alarms-text`
- `chor-telem-section`, `chor-telem-v-bar`, `chor-telem-v`, `chor-telem-t-bar`, `chor-telem-t`, `chor-telem-c-bar`, `chor-telem-c`
- `chor-props-content`, `chor-easing-wrap`, `chor-easing-canvas`
- `chor-psi-f-canvas`, `chor-psi-r-canvas` (new, used by Task 3)
- `chor-palette` (new, used by Task 3)

### Step 1.3 — Commit Task 1

```bash
cd J:/R2-D2_Build/software
git add master/templates/index.html
git commit -m "Feat: choreo — Ultratime HTML layout (single command bar, left panel split)"
```

---

## Task 2: CSS — Command Bar + Left Panel + Palette Styles

**Files:**
- Modify: `master/static/css/style.css` lines 2495–2866

### Step 2.1 — Replace the entire choreo CSS section

Find the block starting with:
```css
/* ================================================================
   CHOREO TAB — Ultratime Edition
================================================================ */
```
and ending at the last `.chor-ease-btn` rule (end of file / end of section at line 2866).

Replace the entire choreo CSS section with:

```css
/* ================================================================
   CHOREO TAB — Ultratime Edition
================================================================ */

/* ── Layout ──────────────────────────────────────────────────── */
.chor-layout {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

/* ── Single Command Bar ──────────────────────────────────────── */
.chor-command-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 10px;
  height: 38px;
  flex-shrink: 0;
  border-bottom: 1px solid rgba(0,170,255,.12);
  background: rgba(4,10,22,.95);
  overflow: hidden;
}
.chor-cmd-brand {
  font-size: 8px;
  letter-spacing: 2.5px;
  color: rgba(0,170,255,.55);
  text-transform: uppercase;
  white-space: nowrap;
  flex-shrink: 0;
}
.chor-cmd-timecode {
  font-family: 'Courier New', monospace;
  font-size: 18px;
  color: #00ffea;
  text-shadow: 0 0 10px rgba(0,255,234,.45);
  letter-spacing: 2px;
  flex-shrink: 0;
  min-width: 90px;
}
.chor-cmd-gauges {
  display: flex;
  align-items: center;
  gap: 3px;
  flex-shrink: 0;
}
.chor-cmd-gauge {
  font-family: 'Courier New', monospace;
  font-size: 9px;
  letter-spacing: 1px;
  color: #00cc88;
  transition: color .4s;
}
.chor-cmd-gauge.dim { color: rgba(0,170,255,.4); }
.chor-cmd-gauge.warn { color: var(--amber); }
.chor-cmd-gauge.crit { color: var(--red); text-shadow: 0 0 6px var(--red); }
.chor-cmd-gauge-sep { color: rgba(0,170,255,.3); font-size: 9px; }
.chor-cmd-sep {
  width: 1px;
  height: 18px;
  background: rgba(0,170,255,.12);
  flex-shrink: 0;
}
.chor-cmd-label {
  font-size: 8px;
  letter-spacing: 1.5px;
  color: var(--text-dim);
  flex-shrink: 0;
}
.chor-conn {
  font-family: 'Courier New', monospace;
  font-size: 8px;
  letter-spacing: 1.5px;
  color: #00ff88;
  white-space: nowrap;
}
.chor-conn.offline { color: var(--red); }

/* ── Snap buttons (used inside command bar) ──────────────────── */
.chor-snap-btn {
  font-size: 8px;
  letter-spacing: 1px;
  padding: 2px 6px;
  background: none;
  border: 1px solid rgba(0,170,255,.15);
  border-radius: 2px;
  color: var(--text-dim);
  cursor: pointer;
  font-family: 'Courier New', monospace;
}
.chor-snap-btn.active,
.chor-snap-btn:hover {
  background: rgba(0,170,255,.12);
  border-color: var(--blue);
  color: var(--blue);
}

/* ── Body ─────────────────────────────────────────────────────── */
.chor-body {
  display: flex;
  flex: 1;
  overflow: hidden;
}

/* ── Left Panel: monitors (top) + palette (bottom) ───────────── */
.chor-left-panel {
  width: 132px;
  flex-shrink: 0;
  border-right: 1px solid rgba(0,170,255,.1);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Top half — Live Monitors */
.chor-monitors {
  flex: 1;
  padding: 6px;
  overflow: hidden;
  border-bottom: 1px solid rgba(0,170,255,.1);
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.chor-monitor-title {
  font-size: 7px;
  letter-spacing: 2.5px;
  color: rgba(0,170,255,.35);
  text-transform: uppercase;
  flex-shrink: 0;
}
.chor-monitor-section {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  flex-shrink: 0;
}
.chor-monitor-label {
  font-size: 7px;
  letter-spacing: 1.5px;
  color: var(--text-dim);
  margin-bottom: 2px;
}
.chor-pixel-canvas {
  border-radius: 2px;
  image-rendering: pixelated;
  max-width: 120px;
}

/* PSI row within monitors */
.chor-psi-row {
  flex-direction: row !important;
  align-items: center;
  gap: 12px;
  justify-content: flex-start;
}
.chor-psi-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}
.chor-psi-canvas {
  border-radius: 50%;
  image-rendering: pixelated;
}

/* Bottom half — Block Palette */
.chor-palette {
  flex-shrink: 0;
  padding: 6px;
  overflow-y: auto;
  min-height: 90px;
  max-height: 45%;
}
.chor-palette-title {
  font-size: 7px;
  letter-spacing: 2px;
  color: rgba(0,170,255,.35);
  text-transform: uppercase;
  margin-bottom: 4px;
}
.chor-palette-section-label {
  display: block;
  font-size: 6px;
  letter-spacing: 1px;
  color: rgba(0,170,255,.25);
  margin-top: 5px;
  margin-bottom: 2px;
  text-transform: uppercase;
}
.chor-palette-item {
  display: inline-block;
  font-size: 7px;
  letter-spacing: .8px;
  padding: 2px 5px;
  border: 1px solid;
  border-radius: 2px;
  cursor: grab;
  margin: 1px;
  font-family: 'Courier New', monospace;
  user-select: none;
  transition: opacity .15s;
}
.chor-palette-item:active { cursor: grabbing; opacity: .7; }
.chor-palette-item[data-track="audio"]      { color:#00ccff; border-color:rgba(0,200,255,.4);  background:rgba(0,200,255,.08); }
.chor-palette-item[data-track="lights"]     { color:#ffb800; border-color:rgba(255,180,0,.4);  background:rgba(255,180,0,.08); }
.chor-palette-item[data-track="dome"]       { color:#cc44ff; border-color:rgba(200,60,255,.4); background:rgba(200,60,255,.06); }
.chor-palette-item[data-track="servos"]     { color:#00ff88; border-color:rgba(0,255,120,.4);  background:rgba(0,255,120,.06); }
.chor-palette-item[data-track="propulsion"] { color:#ff8800; border-color:rgba(255,120,0,.4);  background:rgba(255,120,0,.08); }

/* Palette drop-target highlight */
.chor-lane.drag-over {
  background: rgba(0,170,255,.06);
  outline: 1px dashed rgba(0,170,255,.3);
  outline-offset: -1px;
}

/* ── Track labels ─────────────────────────────────────────────── */
.chor-labels {
  width: 88px;
  flex-shrink: 0;
  border-right: 1px solid rgba(0,170,255,.1);
  display: flex;
  flex-direction: column;
}
.chor-label-spacer { height: 28px; border-bottom: 1px solid rgba(0,170,255,.1); flex-shrink: 0; }
.chor-track-label {
  height: 44px;
  padding: 0 8px;
  display: flex;
  align-items: center;
  font-size: 8px;
  letter-spacing: 1.5px;
  color: var(--text-dim);
  border-bottom: 1px solid rgba(0,170,255,.07);
  flex-shrink: 0;
}
.chor-track-label-dome { height: 64px; }

/* ── Scrollable timeline ──────────────────────────────────────── */
.chor-scroll-wrap {
  flex: 1;
  overflow-x: auto;
  overflow-y: hidden;
  position: relative;
}
.chor-canvas {
  position: relative;
  min-width: 100%;
  height: 100%;
}

/* ── Ruler ────────────────────────────────────────────────────── */
.chor-ruler {
  height: 28px;
  background: #060910;
  border-bottom: 1px solid rgba(0,170,255,.12);
  position: relative;
  flex-shrink: 0;
}
.chor-tick {
  position: absolute;
  top: 0; bottom: 0;
  width: 1px;
  background: rgba(0,170,255,.1);
  font-size: 7px;
  color: rgba(0,170,255,.3);
  padding-top: 3px;
  padding-left: 2px;
  font-family: 'Courier New', monospace;
}
.chor-tick.major { border-left-color: rgba(0,170,255,.25); color: rgba(0,200,255,.7); }

/* ── Track lanes ──────────────────────────────────────────────── */
.chor-lane {
  height: 44px;
  position: relative;
  border-bottom: 1px solid rgba(0,170,255,.07);
  overflow: visible;
}
.chor-lane-audio { height: 44px; }
.chor-lane-dome  { height: 64px; }

/* Waveform canvas (behind blocks in audio lane) */
.chor-waveform-canvas {
  position: absolute;
  top: 0; left: 0;
  pointer-events: none;
  opacity: .45;
}

/* ── Blocks ───────────────────────────────────────────────────── */
.chor-block {
  position: absolute;
  top: 5px; bottom: 5px;
  min-width: 20px;
  border: 1px solid;
  border-radius: 3px;
  font-size: 8px;
  letter-spacing: .8px;
  font-family: 'Courier New', monospace;
  display: flex;
  align-items: center;
  padding: 0 6px;
  cursor: grab;
  overflow: hidden;
  white-space: nowrap;
  z-index: 2;
  transition: box-shadow .1s;
}
.chor-block:active { cursor: grabbing; }
.chor-block.selected {
  outline: 2px solid #00eeff;
  outline-offset: 1px;
  box-shadow: 0 0 10px rgba(0,238,255,.4);
}
.chor-block[data-track="audio"]      { background:rgba(0,200,255,.2);  color:#00ccff; border-color:rgba(0,200,255,.5); }
.chor-block[data-track="lights"]     { background:rgba(255,180,0,.18); color:#ffb800; border-color:rgba(255,180,0,.45); }
.chor-block[data-track="lights"][data-mode="alarm"] { background:rgba(255,40,80,.22); color:#ff2855; border-color:rgba(255,40,80,.55); }
.chor-block[data-track="lights"][data-mode="disco"] { background:rgba(160,80,255,.22); color:#b055ff; border-color:rgba(160,80,255,.55); }
.chor-block[data-track="servos"]     { background:rgba(0,255,120,.16); color:#00ff88; border-color:rgba(0,255,120,.4); }
.chor-block[data-track="propulsion"] { background:rgba(255,120,0,.2);  color:#ff8800; border-color:rgba(255,120,0,.5); }
.chor-block[data-track="dome"]       { background:rgba(200,60,255,.16); color:#cc44ff; border-color:rgba(200,60,255,.4); }

/* Block resize handle */
.chor-block-resize {
  position: absolute;
  right: 0; top: 0; bottom: 0;
  width: 8px;
  cursor: col-resize;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,.06));
}

/* ── Markers ──────────────────────────────────────────────────── */
.chor-marker { position:absolute; top:0; bottom:0; width:1px; background:var(--amber); opacity:.6; pointer-events:none; z-index:5; }
.chor-marker-label { position:absolute; top:2px; left:3px; font-size:7px; color:var(--amber); letter-spacing:.8px; white-space:nowrap; }

/* ── Playhead — high visibility ───────────────────────────────── */
.chor-playhead {
  position: absolute;
  top: 28px;
  bottom: 0;
  width: 2px;
  background: linear-gradient(180deg, #ff2244, rgba(255,180,0,.6));
  z-index: 10;
  pointer-events: none;
  left: 0;
}
.chor-playhead-head {
  position: absolute;
  top: -7px;
  left: -5px;
  width: 12px;
  height: 12px;
  clip-path: polygon(50% 100%, 0 0, 100% 0);
  background: #ff2244;
  box-shadow: 0 0 8px #ff2244;
}

/* ── Right: Properties panel ──────────────────────────────────── */
.chor-props {
  width: 210px;
  flex-shrink: 0;
  border-left: 1px solid rgba(0,170,255,.1);
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  background: rgba(4,10,22,.7);
}

/* Alarms indicator */
.chor-alarms {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-bottom: 1px solid rgba(0,170,255,.08);
  flex-shrink: 0;
}
.chor-alarms-dot { font-size: 10px; transition: color .3s; }
.chor-alarms-dot.ok   { color: #00cc66; text-shadow: 0 0 6px #00cc66; }
.chor-alarms-dot.warn { color: var(--amber); text-shadow: 0 0 8px var(--amber); }
.chor-alarms-dot.crit { color: var(--red); text-shadow: 0 0 10px var(--red); animation: blink .4s step-end infinite; }
@keyframes blink { 50% { opacity: 0; } }

/* VESC telemetry rows */
.chor-telem-compact {
  padding: 6px 10px;
  border-bottom: 1px solid rgba(0,170,255,.08);
  flex-shrink: 0;
}
.chor-telem-row {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-bottom: 5px;
}
.chor-telem-row:last-child { margin-bottom: 0; }
.chor-telem-key { font-size: 7px; letter-spacing: 1px; color: rgba(0,170,255,.4); width: 28px; flex-shrink: 0; font-family: 'Courier New', monospace; }
.chor-telem-bar-wrap { flex: 1; height: 4px; background: rgba(0,170,255,.1); border-radius: 2px; overflow: hidden; }
.chor-telem-bar { height: 100%; width: 0%; background: var(--green); border-radius: 2px; transition: width .4s, background .4s; }
.chor-telem-val { font-size: 9px; font-family: 'Courier New', monospace; color: var(--blue); min-width: 38px; text-align: right; }

/* Properties content */
.chor-props-title {
  font-size: 8px;
  letter-spacing: 3px;
  color: rgba(0,170,255,.5);
  padding: 6px 10px;
  border-bottom: 1px solid rgba(0,170,255,.08);
  flex-shrink: 0;
}
.chor-prop-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 10px;
  border-bottom: 1px solid rgba(0,170,255,.04);
}
.chor-prop-key { color: rgba(0,170,255,.4); font-size: 7px; letter-spacing: 1px; font-family: 'Courier New', monospace; }
.chor-prop-val { color: #00ccff; font-family: 'Courier New', monospace; font-size: 10px; }
.chor-prop-input {
  background: rgba(0,170,255,.06);
  border: 1px solid rgba(0,170,255,.2);
  border-radius: 2px;
  color: #00ccff;
  font-family: 'Courier New', monospace;
  font-size: 10px;
  padding: 2px 4px;
  width: 70px;
  text-align: right;
  outline: none;
}
.chor-prop-input:focus { border-color: var(--blue); background: rgba(0,170,255,.1); }

/* Easing buttons */
.chor-ease-btn {
  font-size: 7px;
  letter-spacing: .8px;
  padding: 2px 6px;
  background: none;
  border: 1px solid rgba(0,170,255,.2);
  border-radius: 2px;
  color: var(--text-dim);
  cursor: pointer;
  font-family: 'Courier New', monospace;
  transition: all .15s;
}
.chor-ease-btn:hover,
.chor-ease-btn.active { border-color: var(--blue); color: var(--blue); background: rgba(0,170,255,.1); }

/* ── Abort modal — full-screen high-priority overlay ─────────── */
#modal-chor-abort.admin-modal {
  background: rgba(255,20,40,.18);
  backdrop-filter: blur(4px);
}
#modal-chor-abort .admin-modal-card {
  border-color: var(--red) !important;
  box-shadow: 0 0 40px rgba(255,34,68,.5), 0 0 80px rgba(255,34,68,.2);
  animation: abort-pulse 1s ease-in-out infinite alternate;
}
@keyframes abort-pulse {
  from { box-shadow: 0 0 30px rgba(255,34,68,.4), 0 0 60px rgba(255,34,68,.15); }
  to   { box-shadow: 0 0 60px rgba(255,34,68,.7), 0 0 120px rgba(255,34,68,.3); }
}
```

### Step 2.2 — Commit Task 2

```bash
git add master/static/css/style.css
git commit -m "Feat: choreo — Ultratime CSS (command bar, left panel, palette, PSI styles)"
```

---

## Task 3: JS — PSI Canvas, Palette Init, Drag-and-Drop

**Files:**
- Modify: `master/static/js/app.js` — inside `choreoEditor` IIFE (lines 4086–4688)

### Step 3.1 — Add `_drawPSI(t)` function

Insert after `_drawDomeCompass()` (after line ~4256, before `// ── Audio waveform`):

```js
  // PSI canvases — front (cyan) + rear (amber)
  function _drawPSI(t) {
    function drawOne(id, c1, c2, phase) {
      const canvas = document.getElementById(id);
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      const W = canvas.width, H = canvas.height;
      const cx = W / 2, cy = H / 2, r = Math.min(W, H) / 2 - 1;
      ctx.clearRect(0, 0, W, H);
      const blink = Math.sin(t * 0.12 + phase) > 0;
      const color = blink ? c1 : c2;
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.fillStyle = blink ? color + '33' : 'rgba(0,0,0,.5)';
      ctx.fill();
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.5;
      ctx.shadowBlur = blink ? 8 : 2;
      ctx.shadowColor = color;
      ctx.stroke();
      ctx.shadowBlur = 0;
      // inner glow dot
      ctx.beginPath();
      ctx.arc(cx, cy, r * 0.45, 0, Math.PI * 2);
      ctx.fillStyle = blink ? color : 'rgba(0,0,0,0)';
      ctx.shadowBlur = blink ? 6 : 0;
      ctx.shadowColor = color;
      ctx.fill();
      ctx.shadowBlur = 0;
    }
    drawOne('chor-psi-f-canvas', '#00ffea', 'rgba(0,80,60,.3)', 0);
    drawOne('chor-psi-r-canvas', '#ffaa00', 'rgba(80,40,0,.3)', Math.PI * 0.7);
  }
```

### Step 3.2 — Update `_startMonitor()` to call `_drawPSI`

Find in `choreoEditor`:
```js
  function _startMonitor() {
    if (_monitorRaf) return;
    const tick = () => {
      _monitorTick++;
      _drawFLD(_monitorTick);
      _drawRLD(_monitorTick);
      _drawBattery(_lastTelem);
      _drawDomeCompass(_monitorTick);
      _monitorRaf = requestAnimationFrame(tick);
    };
    _monitorRaf = requestAnimationFrame(tick);
  }
```

Replace with:
```js
  function _startMonitor() {
    if (_monitorRaf) return;
    const tick = () => {
      _monitorTick++;
      _drawFLD(_monitorTick);
      _drawRLD(_monitorTick);
      _drawPSI(_monitorTick);
      _drawBattery(_lastTelem);
      _drawDomeCompass(_monitorTick);
      _monitorRaf = requestAnimationFrame(tick);
    };
    _monitorRaf = requestAnimationFrame(tick);
  }
```

### Step 3.3 — Add palette definitions constant

Insert before `// ── Snap helper` (near top of `choreoEditor` IIFE, after the `let` state declarations):

```js
  // Block palette templates — one entry per draggable item
  const _PALETTE = [
    { track:'audio',      label:'PLAY',     tpl:{ action:'play',  file:'',   volume:85,  duration:5   } },
    { track:'audio',      label:'STOP',     tpl:{ action:'stop',             duration:0.5 } },
    { track:'lights',     label:'RANDOM',   tpl:{ mode:'random',             duration:4   } },
    { track:'lights',     label:'LEIA',     tpl:{ mode:'leia',               duration:6   } },
    { track:'lights',     label:'ALARM',    tpl:{ mode:'alarm',              duration:3   } },
    { track:'lights',     label:'DISCO',    tpl:{ mode:'disco',              duration:5   } },
    { track:'lights',     label:'OFF',      tpl:{ mode:'off',                duration:2   } },
    { track:'dome',       label:'KF',       tpl:{ angle:0, easing:'linear'               } },
    { track:'servos',     label:'OPEN',     tpl:{ servo:'', action:'open',   duration:1   } },
    { track:'servos',     label:'CLOSE',    tpl:{ servo:'', action:'close',  duration:1   } },
    { track:'propulsion', label:'DRIVE',    tpl:{ left:0.5, right:0.5,      duration:3   } },
    { track:'propulsion', label:'STOP',     tpl:{ left:0,   right:0,        duration:0.5 } },
  ];
```

### Step 3.4 — Add `_initPalette()` function

Insert after `_drawPSI()`:

```js
  // Populate the block palette and attach dragstart handlers
  function _initPalette() {
    const container = document.getElementById('chor-palette');
    if (!container) return;
    // Clear existing items (keep title)
    container.querySelectorAll('.chor-palette-section-label, .chor-palette-item').forEach(el => el.remove());

    const tracks = ['audio', 'lights', 'dome', 'servos', 'propulsion'];
    tracks.forEach(track => {
      const items = _PALETTE.filter(p => p.track === track);
      if (!items.length) return;
      const lbl = document.createElement('span');
      lbl.className = 'chor-palette-section-label';
      lbl.textContent = track.toUpperCase();
      container.appendChild(lbl);
      items.forEach(def => {
        const chip = document.createElement('div');
        chip.className = 'chor-palette-item';
        chip.dataset.track = track;
        chip.textContent = def.label;
        chip.draggable = true;
        chip.addEventListener('dragstart', e => {
          e.dataTransfer.effectAllowed = 'copy';
          e.dataTransfer.setData('application/json', JSON.stringify({ track: def.track, tpl: def.tpl }));
        });
        container.appendChild(chip);
      });
    });
  }
```

### Step 3.5 — Add `_addDropToLanes()` function

Insert after `_initPalette()`:

```js
  // Wire HTML5 drop targets on all timeline lanes
  function _addDropToLanes() {
    document.querySelectorAll('.chor-lane').forEach(lane => {
      lane.addEventListener('dragover', e => {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'copy';
        lane.classList.add('drag-over');
      });
      lane.addEventListener('dragleave', () => lane.classList.remove('drag-over'));
      lane.addEventListener('drop', e => {
        e.preventDefault();
        lane.classList.remove('drag-over');
        if (!_chor) { toast('Load a choreography first', 'error'); return; }
        let data;
        try { data = JSON.parse(e.dataTransfer.getData('application/json')); } catch { return; }
        const { track, tpl } = data;
        const laneTrack = lane.dataset.track;
        if (laneTrack !== track) { toast(`Drop a ${track} block on the ${track} lane`, 'error'); return; }
        const scroll = document.getElementById('chor-scroll');
        const scrollLeft = scroll ? scroll.scrollLeft : 0;
        const rect = lane.getBoundingClientRect();
        const t = _snap(_sec(Math.max(0, e.clientX - rect.left + scrollLeft)));
        const newItem = { ...tpl, t };
        if (!_chor.tracks[track]) _chor.tracks[track] = [];
        _chor.tracks[track].push(newItem);
        _chor.tracks[track].sort((a, b) => a.t - b.t);
        _dirty = true;
        _renderTrack(track);
        const idx = _chor.tracks[track].indexOf(newItem);
        if (track !== 'dome') _selectBlock(track, idx);
        toast(`${track} block → ${t.toFixed(2)}s`, 'ok');
      });
    });
  }
```

### Step 3.6 — Update `_updateTelem()` to drive command bar gauges

Find `_updateTelem(telem)` and update the top-gauge updates (add after existing `_setBar` calls):

```js
  function _updateTelem(telem) {
    _lastTelem = telem;
    const section = document.getElementById('chor-telem-section');
    if (!section) return;
    if (!telem || (!telem.L && !telem.R)) { section.style.display = 'none'; return; }
    section.style.display = 'block';

    const vVals = [telem.L && telem.L.v_in,      telem.R && telem.R.v_in     ].filter(Boolean);
    const tVals = [telem.L && telem.L.temp,       telem.R && telem.R.temp     ].filter(Boolean);
    const cVals = [telem.L && Math.abs(telem.L.current), telem.R && Math.abs(telem.R.current)].filter(Boolean);

    if (vVals.length) {
      const vMin = Math.min(...vVals);
      const vPct = Math.max(0, Math.min(100, ((vMin - 20) / 9.4) * 100));
      const vCol = vPct < 20 ? 'var(--red)' : vPct < 50 ? 'var(--amber)' : 'var(--green)';
      _setBar('chor-telem-v-bar', 'chor-telem-v', vPct, vMin.toFixed(1) + 'V', vCol);
      const el = document.getElementById('chor-stat-battery');
      if (el) { el.textContent = vMin.toFixed(1) + 'V'; el.className = 'chor-cmd-gauge' + (vPct < 20 ? ' crit' : vPct < 50 ? ' warn' : ''); }
    }
    if (tVals.length) {
      const tMax = Math.max(...tVals);
      const tPct = Math.max(0, Math.min(100, (tMax / 80) * 100));
      const tCol = tPct > 87 ? 'var(--red)' : tPct > 62 ? 'var(--amber)' : 'var(--green)';
      _setBar('chor-telem-t-bar', 'chor-telem-t', tPct, tMax.toFixed(0) + '°C', tCol);
      const el = document.getElementById('chor-stat-temp');
      if (el) { el.textContent = tMax.toFixed(0) + '°C'; el.className = 'chor-cmd-gauge' + (tPct > 87 ? ' crit' : tPct > 62 ? ' warn' : ''); }
    }
    if (cVals.length) {
      const cMax = Math.max(...cVals);
      const cPct = Math.max(0, Math.min(100, (cMax / 30) * 100));
      const cCol = cPct > 87 ? 'var(--red)' : cPct > 62 ? 'var(--amber)' : 'var(--green)';
      _setBar('chor-telem-c-bar', 'chor-telem-c', cPct, cVals.map(v => v.toFixed(1) + 'A').join('/'), cCol);
      const el = document.getElementById('chor-stat-current');
      if (el) { el.textContent = cMax.toFixed(1) + 'A'; el.className = 'chor-cmd-gauge' + (cPct > 87 ? ' crit' : cPct > 62 ? ' warn' : ''); }
    }
  }
```

### Step 3.7 — Update `init()` to call palette + drop setup

Find the `init()` method in the public API:
```js
    async init() {
      _startMonitor();
      _syncSnapUI();
      const names = await api('/choreo/list');
      ...
    },
```

Replace with:
```js
    async init() {
      _startMonitor();
      _syncSnapUI();
      _initPalette();
      _addDropToLanes();
      const names = await api('/choreo/list');
      const sel = document.getElementById('chor-select');
      if (!sel || !names) return;
      sel.innerHTML = '<option value="">— select —</option>' +
        names.map(n => `<option value="${n}">${n}</option>`).join('');
      sel.onchange = () => this.load(sel.value);
    },
```

### Step 3.8 — Commit Task 3

```bash
git add master/static/js/app.js
git commit -m "Feat: choreo — PSI canvas, block palette, drag-drop lanes, telem command bar"
```

---

## Task 4: Android Sync + Final Push

**Files:**
- Modify: `android/app/src/main/assets/js/app.js`
- Modify: `android/app/src/main/assets/css/style.css`

### Step 4.1 — Sync assets

```bash
cp master/static/js/app.js android/app/src/main/assets/js/app.js
cp master/static/css/style.css android/app/src/main/assets/css/style.css
```

### Step 4.2 — Commit + push

```bash
git add android/app/src/main/assets/js/app.js android/app/src/main/assets/css/style.css
git commit -m "ci: sync Android assets — Ultratime command bar + palette"
git push
```

### Step 4.3 — Deploy to Pi

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

## Self-Review

**Spec coverage:**

| Requirement | Task |
|-------------|------|
| Single header row (merge redundant bars) | Task 1 + 2 |
| FLD/RLD monitors (left panel top) | Task 1 (canvas IDs preserved) + Task 3 (`_drawPSI`) |
| PSI monitors in left panel | Task 1 (chor-psi-f/r-canvas) + Task 3 Step 3.1 |
| Block palette (left panel bottom) | Task 1 HTML + Task 2 CSS + Task 3 Steps 3.3–3.5 |
| Drag-and-drop from palette to lanes | Task 3 Steps 3.4–3.5 |
| Snap to grid 0.1s/0.5s | Preserved (same IDs/JS) |
| Audio waveform | Preserved (canvas ID unchanged) |
| High-visibility playhead | Preserved + CSS Task 2 |
| Easing curve inspector | Preserved (same IDs/JS) |
| Telemetry gauges (v_in, temp, current) | Task 3 Step 3.6 |
| Color thresholds 20V/80°C/30A | Task 3 Step 3.6 |
| Abort modal high-priority overlay | Task 2 CSS (`#modal-chor-abort` override) |
| English only | All code in English |
| Git commit per task | Each task ends with a commit |
| Android sync | Task 4 |
| Deploy to Pi | Task 4 Step 4.3 |

**Placeholder scan:** No TBD, no TODO, no "implement later" — all steps have complete code.

**Type consistency:** All function names, element IDs, and CSS classes used in later steps match definitions in earlier steps. `chor-psi-f-canvas` defined in Task 1 HTML, drawn in Task 3 `_drawPSI()`. `_initPalette()` and `_addDropToLanes()` defined in Task 3 Steps 3.4/3.5, called in Task 3 Step 3.7. `chor-stat-current` added to HTML in Task 1, driven by `_updateTelem()` in Task 3 Step 3.6.
