# Android HUD Interface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the mobile WebView interface with a drone-inspired HUD — camera placeholder background, thumb-positioned joysticks, bottom drawer for Audio/Seq/Lights, lock system, E-STOP.

**Architecture:** Single HTML page, no tab panes. All controls absolutely positioned over the camera background. Secondary controls live in a bottom drawer (160px, slides up). JS extends mobile.js v2 — `switchTab` replaced by `openDrawer`/`closeDrawer`, all API calls unchanged.

**Tech Stack:** HTML5 / CSS3 / vanilla JS (no framework), Android WebView, ADB for deploy.

**Spec:** `docs/superpowers/specs/2026-03-22-android-hud-interface-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `android/app/src/main/assets/mobile.html` | Rewrite | HUD structure, drawer HTML, lock modal |
| `android/app/src/main/assets/css/mobile.css` | Rewrite | All visual styles, z-index layers, animations |
| `android/app/src/main/assets/js/mobile.js` | Rewrite | Drawer logic, joysticks, lock, E-STOP, API calls |
| `master/templates/mobile.html` | Sync from assets | Flask server version (change css/js paths only) |
| `master/static/css/mobile.css` | Sync from assets | Identical to Android version |
| `master/static/js/mobile.js` | Sync from assets | Identical to Android version |

---

## Task 1: HTML Structure

**Files:**
- Rewrite: `android/app/src/main/assets/mobile.html`

- [ ] **Step 1: Write mobile.html**

```html
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0,
               maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
  <title>R2-D2</title>
  <link rel="stylesheet" href="css/mobile.css">
</head>
<body>

  <!-- ── Status bar ─────────────────────────────── -->
  <div id="status-bar">
    <div id="status-indicators">
      <span class="ind" id="ind-hb">HB</span>
      <span class="ind" id="ind-uart">UART</span>
      <span class="ind" id="ind-bt">BT</span>
      <span id="uart-pct"></span>
    </div>
    <div id="mode-badge" class="hidden"></div>
    <div id="status-host" onclick="showHostDialog()">192.168.4.1</div>
  </div>

  <!-- ── Alert toast ────────────────────────────── -->
  <div id="alert-toast" class="hidden"></div>

  <!-- ── HUD ────────────────────────────────────── -->
  <div id="hud-drive">

    <!-- Camera background (placeholder) -->
    <!-- Future: <img id="cam-stream" src="http://192.168.4.1:8080/?action=stream"> -->
    <div id="cam-bg"></div>

    <!-- HUD corner brackets -->
    <div class="hud-corner tl"></div>
    <div class="hud-corner tr"></div>
    <div class="hud-corner bl"></div>
    <div class="hud-corner br"></div>

    <!-- Lock button -->
    <button id="lock-btn" onclick="cycleLockMode()">🔒</button>

    <!-- E-STOP -->
    <button id="estop-btn" onclick="triggerEstop()">⬡ E-STOP</button>
    <button id="estop-reset-btn" onclick="resetEstop()" class="hidden">▶ RESET</button>

    <!-- Quick pills (below E-STOP) -->
    <div id="quick-pills">
      <button class="pill-btn" id="pill-audio"  onclick="openDrawer('audio')">🔊 AUDIO</button>
      <button class="pill-btn" id="pill-seq"    onclick="openDrawer('seq')">🎬 SEQ</button>
      <button class="pill-btn" id="pill-lights" onclick="openDrawer('lights')">💡 LIGHTS</button>
    </div>

    <!-- Joystick — Propulsion (left thumb) -->
    <div class="js-wrap" id="js-left-wrap">
      <div class="js-label">PROPULSION</div>
      <div class="joystick" id="js-left">
        <div class="js-ring"><div class="js-knob"></div></div>
      </div>
    </div>

    <!-- Joystick — Dôme (right thumb) -->
    <div class="js-wrap" id="js-right-wrap">
      <div class="js-label">DÔME</div>
      <div class="joystick" id="js-right">
        <div class="js-ring"><div class="js-knob"></div></div>
      </div>
    </div>

    <!-- Temperature (top-right corner of HUD) -->
    <div id="hud-temp"></div>

  </div><!-- /hud-drive -->

  <!-- ── Password modal (Child Lock) ───────────── -->
  <div id="lock-modal" class="hidden" onclick="if(event.target===this)closeLockModal()">
    <div id="lock-modal-box">
      <div id="lock-modal-title">CHILD LOCK ACTIF</div>
      <input type="password" id="lock-pwd" placeholder="Mot de passe"
             onkeydown="if(event.key==='Enter')submitLockPwd()">
      <div id="lock-pwd-err" class="hidden">Mot de passe incorrect</div>
      <div id="lock-modal-btns">
        <button onclick="closeLockModal()">ANNULER</button>
        <button onclick="submitLockPwd()">UNLOCK</button>
      </div>
    </div>
  </div>

  <!-- ── Drawer backdrop ────────────────────────── -->
  <div id="drawer-backdrop" class="hidden" onclick="closeDrawer()"></div>

  <!-- ── Bottom drawer ──────────────────────────── -->
  <div id="bottom-drawer" class="hidden">
    <div id="drawer-header">
      <span id="drawer-title"></span>
      <button id="drawer-close" onclick="closeDrawer()">✕</button>
    </div>
    <div id="drawer-body">

      <!-- AUDIO content -->
      <div id="drawer-audio" class="drawer-pane hidden">
        <div id="volume-bar">
          <span>🔈</span>
          <input type="range" id="vol-slider" min="0" max="100" value="79"
                 oninput="setVolume(this.value)">
          <span id="vol-pct">79%</span>
          <button onclick="stopAudio()">⏹</button>
        </div>
        <div id="cat-list"></div>
        <div id="sound-grid"></div>
      </div>

      <!-- SEQ content -->
      <div id="drawer-seq" class="drawer-pane hidden">
        <div id="seq-list"></div>
        <button id="stop-all-btn" onclick="stopAllSeq()">⏹ STOP ALL</button>
      </div>

      <!-- LIGHTS content -->
      <div id="drawer-lights" class="drawer-pane hidden">
        <div class="light-section">
          <div class="section-title">LOGICS — FLD / RLD</div>
          <div class="btn-row">
            <button class="btn-light" onclick="teecesMode('random')">RANDOM</button>
            <button class="btn-light" onclick="teecesMode('leia')">LEIA</button>
            <button class="btn-light btn-off" onclick="teecesMode('off')">OFF</button>
          </div>
          <div class="text-row">
            <input type="text" id="teeces-text" placeholder="Texte FLD…" maxlength="20"
                   autocomplete="off" autocorrect="off" spellcheck="false">
            <button onclick="teecesText()">OK</button>
          </div>
        </div>
        <div class="light-section">
          <div class="section-title">PSI</div>
          <div class="psi-swatches">
            <button class="psi-btn"          onclick="teecesPS(0)">OFF</button>
            <button class="psi-btn psi-rand" onclick="teecesPS(1)">RAND</button>
            <button class="psi-btn psi-red"  onclick="teecesPS(2)">●</button>
            <button class="psi-btn psi-blue" onclick="teecesPS(3)">●</button>
          </div>
        </div>
      </div>

    </div><!-- /drawer-body -->
  </div><!-- /bottom-drawer -->

  <script src="js/mobile.js"></script>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
cd "J:/R2-D2_Build/software"
git add android/app/src/main/assets/mobile.html
git commit -m "feat: HUD mobile.html — full rewrite, drawer structure"
```

---

## Task 2: CSS

**Files:**
- Rewrite: `android/app/src/main/assets/css/mobile.css`

- [ ] **Step 1: Write mobile.css**

```css
/* ── Reset & base ──────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg:       #050a10;
  --primary:  #00aaff;
  --ok:       #00cc55;
  --warn:     #ffaa00;
  --danger:   #ff3344;
  --text:     #c8d8e8;
  --text-dim: #4a6a8a;
  --panel-bg: rgba(4, 10, 22, 0.92);
}

html, body {
  width: 100%; height: 100%;
  overflow: hidden;
  background: var(--bg);
  color: var(--text);
  font-family: 'Courier New', Courier, monospace;
  font-size: 14px;
  touch-action: none;
  user-select: none;
  -webkit-user-select: none;
}

/* ── Z-index layers ─────────────────────────────
   0  = background (cam-bg)
   10 = hud-drive (joysticks, corners, lock, estop, pills)
   20 = drawer-backdrop
   30 = bottom-drawer
   40 = status-bar
   50 = lock-modal
   60 = alert-toast
──────────────────────────────────────────────── */

/* ── Status bar ─────────────────────────────────── */
#status-bar {
  position: fixed;
  top: 0; left: 0; right: 0;
  height: 28px;
  background: rgba(0, 5, 18, 0.9);
  border-bottom: 1px solid rgba(0, 80, 180, 0.2);
  display: flex;
  align-items: center;
  padding: 0 10px;
  gap: 8px;
  z-index: 40;
}

#status-indicators {
  display: flex;
  align-items: center;
  gap: 5px;
}

.ind {
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 9px;
  font-weight: bold;
  letter-spacing: .1em;
  transition: background .3s, color .3s;
}
.ind.ok  { background: rgba(0,200,80,.12); color: var(--ok);     border: 1px solid rgba(0,200,80,.25); }
.ind.err { background: rgba(255,40,40,.08); color: var(--danger); border: 1px solid rgba(255,40,40,.2); }

#uart-pct {
  font-size: 9px;
  color: var(--text-dim);
}

#mode-badge {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  padding: 2px 12px;
  border-radius: 12px;
  font-size: 8px;
  font-weight: bold;
  letter-spacing: .18em;
  white-space: nowrap;
  pointer-events: none;
}
#mode-badge.hidden { display: none; }
#mode-badge.kids   {
  background: rgba(255,150,0,.14); color: var(--warn);
  border: 1px solid rgba(255,150,0,.3);
  animation: pulse-warn 2s ease-in-out infinite;
}
#mode-badge.locked {
  background: rgba(255,40,60,.14); color: var(--danger);
  border: 1px solid rgba(255,40,60,.3);
  animation: pulse-danger 1.8s ease-in-out infinite;
}

#status-host {
  margin-left: auto;
  font-size: 9px;
  color: var(--text-dim);
  letter-spacing: .06em;
  cursor: pointer;
}

/* ── Alert toast ────────────────────────────────── */
#alert-toast {
  position: fixed;
  top: 36px; left: 50%;
  transform: translateX(-50%);
  padding: 6px 18px;
  background: rgba(0,10,30,.9);
  border: 1px solid rgba(0,120,255,.3);
  border-radius: 20px;
  font-size: 11px;
  letter-spacing: .08em;
  color: var(--text);
  z-index: 60;
  white-space: nowrap;
}
#alert-toast.hidden { display: none; }

/* ── HUD drive ──────────────────────────────────── */
#hud-drive {
  position: fixed;
  inset: 0;
  z-index: 10;
  overflow: hidden;
}

/* ── Camera background ──────────────────────────── */
#cam-bg {
  position: absolute;
  inset: 0;
  z-index: 0;
  background:
    radial-gradient(ellipse 55% 45% at 50% 55%, rgba(15,35,10,.8) 0%, transparent 65%),
    repeating-linear-gradient(0deg,  transparent, transparent 28px, rgba(0,60,0,.05) 28px, rgba(0,60,0,.05) 29px),
    repeating-linear-gradient(90deg, transparent, transparent 38px, rgba(0,60,0,.05) 38px, rgba(0,60,0,.05) 39px),
    linear-gradient(160deg, #0a1a0a 0%, #050d15 100%);
}
#cam-bg::after {
  content: '';
  position: absolute; inset: 0;
  background: repeating-linear-gradient(
    0deg, transparent, transparent 3px,
    rgba(0,0,0,.06) 3px, rgba(0,0,0,.06) 4px
  );
  pointer-events: none;
}

/* ── HUD corners ────────────────────────────────── */
.hud-corner {
  position: absolute;
  width: 26px; height: 26px;
  border-color: rgba(0,170,255,.4);
  border-style: solid;
  z-index: 10;
}
.hud-corner.tl { top: 32px;  left: 8px;  border-width: 2px 0 0 2px; }
.hud-corner.tr { top: 32px;  right: 8px; border-width: 2px 2px 0 0; }
.hud-corner.bl { bottom: 8px; left: 8px;  border-width: 0 0 2px 2px; }
.hud-corner.br { bottom: 8px; right: 8px; border-width: 0 2px 2px 0; }

/* ── Temperature HUD ────────────────────────────── */
#hud-temp {
  position: absolute;
  top: 32px; right: 42px;
  font-size: 9px;
  color: rgba(200,220,255,.4);
  letter-spacing: .06em;
  z-index: 10;
}

/* ── Lock button ────────────────────────────────── */
#lock-btn {
  position: absolute;
  top: 34px; left: 12px;
  width: 34px; height: 34px;
  border-radius: 50%;
  border: 1.5px solid rgba(0,120,255,.2);
  background: rgba(0,15,40,.7);
  font-size: 16px;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer;
  z-index: 15;
  transition: border-color .3s, background .3s;
}
#lock-btn.kids   { border-color: rgba(255,150,0,.5);  background: rgba(40,20,0,.7); }
#lock-btn.locked { border-color: rgba(255,40,60,.5);  background: rgba(40,0,10,.7); }

/* ── E-STOP ─────────────────────────────────────── */
#estop-btn {
  position: absolute;
  left: 50%; top: 70px;
  transform: translateX(-50%);
  width: 64px; height: 64px;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 30%, #992222, #3a0808);
  border: 2.5px solid rgba(255,40,40,.5);
  color: var(--danger);
  font-size: 9px;
  font-family: 'Courier New', monospace;
  font-weight: bold;
  letter-spacing: .05em;
  box-shadow: 0 0 20px rgba(255,0,0,.2), inset 0 0 10px rgba(0,0,0,.5);
  animation: pulse-estop 2.5s ease-in-out infinite;
  z-index: 15;
  cursor: pointer;
}

#estop-reset-btn {
  position: absolute;
  left: 50%; top: 70px;
  transform: translateX(-50%);
  width: 64px; height: 64px;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 30%, #226622, #0a2a0a);
  border: 2.5px solid rgba(0,200,80,.5);
  color: var(--ok);
  font-size: 9px;
  font-family: 'Courier New', monospace;
  letter-spacing: .05em;
  z-index: 15;
  cursor: pointer;
}
#estop-reset-btn.hidden { display: none; }

/* ── Quick pills ────────────────────────────────── */
#quick-pills {
  position: absolute;
  left: 50%; top: 145px;
  transform: translateX(-50%);
  display: flex;
  gap: 8px;
  z-index: 15;
}

.pill-btn {
  padding: 5px 14px;
  border-radius: 16px;
  background: rgba(0,15,40,.75);
  border: 1px solid rgba(0,100,200,.22);
  color: rgba(0,160,255,.7);
  font-family: 'Courier New', monospace;
  font-size: 10px;
  letter-spacing: .1em;
  cursor: pointer;
  transition: background .15s, border-color .15s, color .15s;
}
.pill-btn:active,
.pill-btn.active {
  background: rgba(0,50,110,.85);
  border-color: rgba(0,160,255,.5);
  color: #00ccff;
}

/* ── Joysticks ──────────────────────────────────── */
.js-wrap {
  position: absolute;
  display: flex;
  flex-direction: column;
  align-items: center;
  z-index: 10;
}
#js-left-wrap  { left: calc(22% - 65px);  top: calc(55% - 65px); }
#js-right-wrap { right: calc(22% - 65px); top: calc(55% - 65px); }

.js-label {
  font-size: 9px;
  letter-spacing: .15em;
  color: rgba(0,170,255,.5);
  margin-bottom: 5px;
  text-transform: uppercase;
}

.joystick { width: 130px; height: 130px; }

.js-ring {
  width: 100%; height: 100%;
  border-radius: 50%;
  border: 1.5px solid rgba(0,140,255,.3);
  background: radial-gradient(circle, rgba(0,40,90,.5) 0%, rgba(0,10,30,.35) 100%);
  display: flex; align-items: center; justify-content: center;
  position: relative;
  box-shadow: inset 0 0 20px rgba(0,30,80,.4);
  transition: box-shadow .15s;
}
.js-ring.touching {
  box-shadow: inset 0 0 20px rgba(0,30,80,.4), 0 0 22px rgba(0,120,255,.5);
}

.js-knob {
  position: absolute;
  top: 50%; left: 50%;
  width: 46px; height: 46px;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 30%, #2255bb, #0a1a3a);
  border: 1.5px solid rgba(0,140,255,.45);
  box-shadow: 0 0 12px rgba(0,100,255,.2);
  transform: translate(-50%, -50%);
}

/* Lock mode visuals on joystick zone */
#hud-drive[data-lock="1"] .js-ring {
  border-color: rgba(255,150,0,.3);
}
#hud-drive[data-lock="2"] .js-ring {
  border-color: rgba(255,40,60,.4);
}
#hud-drive[data-lock="2"] .js-knob {
  background: radial-gradient(circle at 35% 30%, #882233, #3a0010);
  border-color: rgba(255,40,60,.35);
}

/* ── Drawer backdrop ────────────────────────────── */
#drawer-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,.35);
  z-index: 20;
  pointer-events: auto;
}
#drawer-backdrop.hidden { display: none; }

/* ── Bottom drawer ──────────────────────────────── */
#bottom-drawer {
  position: fixed;
  left: 0; right: 0; bottom: 0;
  height: 160px;
  background: var(--panel-bg);
  border-top: 1px solid rgba(0,100,200,.25);
  z-index: 30;
  display: flex;
  flex-direction: column;
  transform: translateY(100%);
  transition: transform 250ms ease-out;
}
#bottom-drawer.open {
  transform: translateY(0);
}
#bottom-drawer.hidden { display: none; }

#drawer-header {
  height: 30px;
  display: flex;
  align-items: center;
  padding: 0 12px;
  border-bottom: 1px solid rgba(0,80,160,.15);
  flex-shrink: 0;
}
#drawer-title {
  font-size: 10px;
  letter-spacing: .2em;
  color: rgba(0,160,255,.6);
  text-transform: uppercase;
  flex: 1;
}
#drawer-close {
  background: none;
  border: none;
  color: rgba(0,120,200,.5);
  font-size: 14px;
  cursor: pointer;
  padding: 4px 8px;
}

#drawer-body {
  flex: 1;
  overflow: hidden;
  padding: 8px 12px;
}

.drawer-pane { height: 100%; }
.drawer-pane.hidden { display: none; }

/* ── Drawer: Audio ──────────────────────────────── */
#volume-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 7px;
  font-size: 12px;
}
#vol-slider { flex: 1; accent-color: var(--primary); }
#vol-pct    { font-size: 10px; color: var(--text-dim); min-width: 32px; }
#volume-bar button {
  background: rgba(0,20,50,.7);
  border: 1px solid rgba(0,100,200,.2);
  color: rgba(0,160,255,.7);
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 12px;
  cursor: pointer;
}

#cat-list {
  display: flex;
  gap: 6px;
  overflow-x: auto;
  padding-bottom: 5px;
  margin-bottom: 5px;
  scrollbar-width: none;
}
#cat-list::-webkit-scrollbar { display: none; }

.cat-btn {
  flex-shrink: 0;
  padding: 3px 10px;
  border-radius: 10px;
  border: 1px solid rgba(0,100,200,.2);
  background: rgba(0,20,50,.7);
  color: rgba(0,160,255,.65);
  font-family: 'Courier New', monospace;
  font-size: 9px;
  letter-spacing: .08em;
  cursor: pointer;
  white-space: nowrap;
}
.cat-btn.active {
  background: rgba(0,55,110,.8);
  border-color: rgba(0,160,255,.4);
  color: #00ccff;
}

#sound-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  overflow-y: auto;
  max-height: 34px;
  scrollbar-width: none;
}
#sound-grid::-webkit-scrollbar { display: none; }

.snd-btn {
  padding: 3px 8px;
  border-radius: 4px;
  border: 1px solid rgba(0,80,160,.18);
  background: rgba(0,15,40,.7);
  color: rgba(0,150,255,.65);
  font-family: 'Courier New', monospace;
  font-size: 8px;
  letter-spacing: .04em;
  cursor: pointer;
}
.snd-btn.now-playing {
  border-color: rgba(0,200,80,.4);
  color: var(--ok);
}
.rnd-btn {
  padding: 3px 10px;
  border-radius: 4px;
  border: 1px solid rgba(0,120,200,.25);
  background: rgba(0,30,70,.8);
  color: rgba(0,180,255,.7);
  font-family: 'Courier New', monospace;
  font-size: 8px;
  letter-spacing: .08em;
  cursor: pointer;
}

/* ── Drawer: Sequences ──────────────────────────── */
#seq-list {
  overflow-y: auto;
  max-height: 80px;
  margin-bottom: 6px;
  scrollbar-width: thin;
  scrollbar-color: rgba(0,100,200,.2) transparent;
}

.seq-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 0;
  border-bottom: 1px solid rgba(0,60,120,.1);
}
.seq-name { flex: 1; font-size: 10px; color: var(--text); letter-spacing: .05em; text-transform: uppercase; }
.seq-run, .seq-loop, .seq-stop {
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid rgba(0,80,160,.2);
  background: rgba(0,20,50,.7);
  color: rgba(0,160,255,.7);
  font-family: 'Courier New', monospace;
  font-size: 9px;
  cursor: pointer;
}
.seq-run.running  { border-color: rgba(0,200,80,.4); color: var(--ok); }

#stop-all-btn {
  width: 100%;
  padding: 4px;
  border-radius: 4px;
  border: 1px solid rgba(255,40,40,.25);
  background: rgba(40,0,0,.7);
  color: rgba(255,80,80,.7);
  font-family: 'Courier New', monospace;
  font-size: 9px;
  letter-spacing: .1em;
  cursor: pointer;
}

/* ── Drawer: Lights ─────────────────────────────── */
.light-section { margin-bottom: 8px; }
.section-title {
  font-size: 8px;
  letter-spacing: .18em;
  color: rgba(0,140,255,.4);
  text-transform: uppercase;
  border-bottom: 1px solid rgba(0,80,160,.12);
  padding-bottom: 3px;
  margin-bottom: 5px;
}
.btn-row { display: flex; gap: 6px; margin-bottom: 5px; }
.btn-light {
  padding: 4px 12px;
  border-radius: 4px;
  border: 1px solid rgba(0,100,200,.2);
  background: rgba(0,20,55,.7);
  color: rgba(0,160,255,.7);
  font-family: 'Courier New', monospace;
  font-size: 9px;
  letter-spacing: .08em;
  cursor: pointer;
}
.btn-off { border-color: rgba(255,40,40,.2); color: rgba(255,80,80,.65); }
.text-row { display: flex; gap: 6px; }
.text-row input {
  flex: 1;
  background: rgba(0,15,40,.7);
  border: 1px solid rgba(0,80,160,.2);
  border-radius: 4px;
  color: var(--text);
  font-family: 'Courier New', monospace;
  font-size: 10px;
  padding: 3px 8px;
}
.text-row button {
  padding: 3px 10px;
  border-radius: 4px;
  border: 1px solid rgba(0,120,200,.25);
  background: rgba(0,30,70,.8);
  color: rgba(0,180,255,.7);
  font-family: 'Courier New', monospace;
  font-size: 9px;
  cursor: pointer;
}

.psi-swatches { display: flex; gap: 8px; align-items: center; }
.psi-btn {
  padding: 4px 12px;
  border-radius: 4px;
  border: 1px solid rgba(100,100,100,.2);
  background: rgba(0,15,35,.7);
  color: rgba(200,220,255,.6);
  font-family: 'Courier New', monospace;
  font-size: 10px;
  cursor: pointer;
}
.psi-rand { border-color: rgba(0,100,200,.25); color: rgba(0,160,255,.7); }
.psi-red  { border-color: rgba(200,30,30,.3); color: #ff4444; font-size: 14px; }
.psi-blue { border-color: rgba(30,80,200,.3); color: #4488ff; font-size: 14px; }

/* ── Lock modal ─────────────────────────────────── */
#lock-modal {
  position: fixed; inset: 0;
  background: rgba(0,0,0,.6);
  display: flex; align-items: center; justify-content: center;
  z-index: 50;
}
#lock-modal.hidden { display: none; }

#lock-modal-box {
  background: rgba(4,10,22,.96);
  border: 1px solid rgba(0,100,200,.3);
  border-radius: 10px;
  padding: 24px 28px;
  min-width: 260px;
  display: flex; flex-direction: column; gap: 12px;
}
#lock-modal-title {
  font-size: 12px; letter-spacing: .25em; color: var(--danger); text-align: center;
}
#lock-pwd {
  background: rgba(0,15,40,.8);
  border: 1px solid rgba(0,80,160,.25);
  border-radius: 5px;
  color: var(--text);
  font-family: 'Courier New', monospace;
  font-size: 14px;
  padding: 8px 12px;
  outline: none;
  letter-spacing: .15em;
}
#lock-pwd-err {
  font-size: 10px; color: var(--danger); letter-spacing: .1em; text-align: center;
}
#lock-pwd-err.hidden { display: none; }
#lock-modal-btns { display: flex; gap: 10px; }
#lock-modal-btns button {
  flex: 1; padding: 8px;
  border-radius: 5px;
  border: 1px solid rgba(0,100,200,.25);
  background: rgba(0,25,55,.8);
  color: rgba(0,160,255,.7);
  font-family: 'Courier New', monospace;
  font-size: 11px; letter-spacing: .1em;
  cursor: pointer;
}

/* ── Animations ─────────────────────────────────── */
@keyframes pulse-warn {
  0%, 100% { opacity: 1; }
  50%       { opacity: .55; }
}
@keyframes pulse-danger {
  0%, 100% { opacity: 1; box-shadow: 0 0 6px rgba(255,40,60,.4); }
  50%       { opacity: .6; box-shadow: none; }
}
@keyframes pulse-estop {
  0%, 100% { box-shadow: 0 0 20px rgba(255,0,0,.2), inset 0 0 10px rgba(0,0,0,.5); }
  50%       { box-shadow: 0 0 35px rgba(255,0,0,.45), inset 0 0 10px rgba(0,0,0,.5); }
}
```

- [ ] **Step 2: Commit**

```bash
cd "J:/R2-D2_Build/software"
git add android/app/src/main/assets/css/mobile.css
git commit -m "feat: HUD mobile.css — full rewrite, drone dark theme"
```

---

## Task 3: JavaScript

**Files:**
- Rewrite: `android/app/src/main/assets/js/mobile.js`

- [ ] **Step 1: Write mobile.js**

```javascript
// ============================================================
//  R2-D2 Mobile Control — mobile.js  v3 (HUD)
// ============================================================
'use strict';

// ── Config ───────────────────────────────────────────────────
let API_BASE    = window.R2D2_API_BASE || 'http://192.168.4.1:5000';
let speedLimit  = 1.0;
let lockMode    = 0;   // 0=Normal  1=Kids  2=ChildLock
let estopActive = false;
let driveActive = false;
let domeActive  = false;

const DRIVE_MS = 50;
let lastDriveT = 0;
let lastDomeT  = 0;

// ── API helper ────────────────────────────────────────────────
function api(method, endpoint, body) {
  return fetch(API_BASE + endpoint, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body:    body ? JSON.stringify(body) : undefined,
  }).catch(() => null);
}

// ── Heartbeat ─────────────────────────────────────────────────
setInterval(() => api('POST', '/heartbeat'), 200);

// ── Toast ─────────────────────────────────────────────────────
let _toastTimer = null;
function showToast(msg, ms = 3000) {
  const el = document.getElementById('alert-toast');
  el.textContent = msg;
  el.classList.remove('hidden');
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => el.classList.add('hidden'), ms);
}

// ── Status polling (1 s) ──────────────────────────────────────
let _lastUartPct = 100;
let _lastEstop   = false;

setInterval(() => {
  api('GET', '/status').then(r => r && r.json()).then(s => {
    if (!s) return;

    _setInd('ind-hb',   s.heartbeat_ok);
    _setInd('ind-uart', s.uart_ready);
    _setInd('ind-bt',   s.bt_connected);

    const pct = s.uart_health?.health_pct ?? 100;
    const uEl = document.getElementById('uart-pct');
    if (uEl) {
      uEl.textContent = pct < 100 ? `${Math.round(pct)}%` : '';
      uEl.style.color = pct < 80 ? 'var(--warn)' : 'var(--text-dim)';
    }
    if (pct < 80 && _lastUartPct >= 80) showToast(`⚠️ UART dégradé — ${Math.round(pct)}%`);
    if (!s.uart_ready && _lastUartPct > 0) showToast('🔴 UART déconnecté !', 5000);
    _lastUartPct = pct;

    if (s.temperature != null) {
      const tv = document.getElementById('hud-temp');
      if (tv) tv.textContent = `${s.temperature}°C`;
    }

    if (s.estop_active !== _lastEstop) {
      _lastEstop = s.estop_active;
      _applyEstopUI(s.estop_active);
    }
    estopActive = s.estop_active;

    if (s.lock_mode !== undefined && s.lock_mode !== lockMode) {
      lockMode = s.lock_mode;
      _applyLockMode(false);
    }
  }).catch(() => {});
}, 1000);

function _setInd(id, ok) {
  const el = document.getElementById(id);
  if (!el) return;
  el.classList.toggle('ok',  !!ok);
  el.classList.toggle('err', !ok);
}

function _applyEstopUI(active) {
  document.getElementById('estop-btn')?.classList.toggle('hidden', active);
  document.getElementById('estop-reset-btn')?.classList.toggle('hidden', !active);
  if (active) { jsLeft.reset(); jsRight.reset(); }
}

// ── Drawer ────────────────────────────────────────────────────
let _activeDrawer = null;
let _audioInit    = false;
let _seqInit      = false;

function openDrawer(tab) {
  if (_activeDrawer === tab) { closeDrawer(); return; }
  _activeDrawer = tab;

  // Show/hide panes
  document.querySelectorAll('.drawer-pane').forEach(p => p.classList.add('hidden'));
  document.getElementById('drawer-' + tab)?.classList.remove('hidden');

  // Title
  const titles = { audio: '🔊 AUDIO', seq: '🎬 SÉQUENCES', lights: '💡 LIGHTS' };
  document.getElementById('drawer-title').textContent = titles[tab] || tab;

  // Active pill
  document.querySelectorAll('.pill-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('pill-' + tab)?.classList.add('active');

  // Show drawer
  const drawer = document.getElementById('bottom-drawer');
  drawer.classList.remove('hidden');
  requestAnimationFrame(() => drawer.classList.add('open'));

  // Show backdrop (pointer-events:none so joysticks work)
  const bd = document.getElementById('drawer-backdrop');
  bd.classList.remove('hidden');

  // Push history for back-button
  history.pushState({ drawer: tab }, '');

  // Lazy load
  if (tab === 'audio'  && !_audioInit) { _audioInit = true; loadCategories(); }
  if (tab === 'seq'    && !_seqInit)   { _seqInit   = true; loadSequences(); }

  _haptic(20);
}

function closeDrawer() {
  if (!_activeDrawer) return;
  _activeDrawer = null;

  const drawer = document.getElementById('bottom-drawer');
  drawer.classList.remove('open');
  drawer.addEventListener('transitionend', () => {
    if (!_activeDrawer) drawer.classList.add('hidden');
  }, { once: true });

  document.getElementById('drawer-backdrop')?.classList.add('hidden');
  document.querySelectorAll('.pill-btn').forEach(b => b.classList.remove('active'));
}

// Back button support
window.addEventListener('popstate', () => {
  if (_activeDrawer) closeDrawer();
});

// ── Joystick ──────────────────────────────────────────────────
class MobileJoystick {
  constructor(id, onMove, onStop, canStart) {
    const wrap     = document.getElementById(id);
    this.ring      = wrap.querySelector('.js-ring');
    this.knob      = wrap.querySelector('.js-knob');
    this.onMove    = onMove;
    this.onStop    = onStop;
    this.canStart  = canStart || (() => true);
    this.touchId   = null;
    this.x = 0; this.y = 0;
    this.ring.addEventListener('touchstart',  e => this._start(e), { passive: false });
    this.ring.addEventListener('touchmove',   e => this._move(e),  { passive: false });
    this.ring.addEventListener('touchend',    e => this._end(e),   { passive: false });
    this.ring.addEventListener('touchcancel', e => this._end(e),   { passive: false });
  }

  _start(e) {
    e.preventDefault();
    if (this.touchId !== null) return;
    if (!this.canStart()) return;
    const t = e.changedTouches[0];
    this.touchId = t.identifier;
    this.ring.classList.add('touching');
    this._update(t);
  }

  _move(e) {
    e.preventDefault();
    for (const t of e.changedTouches) {
      if (t.identifier === this.touchId) { this._update(t); break; }
    }
  }

  _end(e) {
    for (const t of e.changedTouches) {
      if (t.identifier !== this.touchId) continue;
      this.touchId = null;
      this.x = 0; this.y = 0;
      this._setKnob(0, 0);
      this.ring.classList.remove('touching');
      this.onStop();
      break;
    }
  }

  _update(touch) {
    const r  = this.ring.getBoundingClientRect();
    const cx = r.left + r.width  / 2;
    const cy = r.top  + r.height / 2;
    const mr = r.width / 2 * 0.72;
    let dx = touch.clientX - cx;
    let dy = touch.clientY - cy;
    const d = Math.hypot(dx, dy);
    if (d > mr) { dx = dx / d * mr; dy = dy / d * mr; }
    this.x = dx / mr;
    this.y = dy / mr;
    this._setKnob(dx, dy);
    this.onMove(this.x, this.y);
  }

  _setKnob(dx, dy) {
    this.knob.style.transform =
      `translate(calc(-50% + ${dx}px), calc(-50% + ${dy}px))`;
  }

  reset() {
    this.touchId = null; this.x = 0; this.y = 0;
    this._setKnob(0, 0);
    this.ring.classList.remove('touching');
  }
}

// Propulsion — blocked in ChildLock or E-STOP
const jsLeft = new MobileJoystick(
  'js-left',
  (x, y) => {
    const now = Date.now();
    if (now - lastDriveT < DRIVE_MS) return;
    lastDriveT = now;
    const thr = -y * speedLimit;
    const str =  x * speedLimit * 0.55;
    const L = Math.max(-1, Math.min(1, thr + str));
    const R = Math.max(-1, Math.min(1, thr - str));
    api('POST', '/motion/drive', { left: +L.toFixed(3), right: +R.toFixed(3) });
    driveActive = true;
  },
  () => { if (driveActive) { api('POST', '/motion/stop'); driveActive = false; } },
  () => !estopActive && lockMode !== 2
);

// Dôme — blocked only in E-STOP
const jsRight = new MobileJoystick(
  'js-right',
  (x, _y) => {
    const now = Date.now();
    if (now - lastDomeT < DRIVE_MS) return;
    lastDomeT = now;
    const speed = +(x * 0.85).toFixed(3);
    api('POST', '/motion/dome/turn', { speed });
    domeActive = true;
  },
  () => { if (domeActive) { api('POST', '/motion/dome/stop'); domeActive = false; } },
  () => !estopActive
);

// ── E-STOP ────────────────────────────────────────────────────
function triggerEstop() {
  api('POST', '/system/estop');
  estopActive = true;
  jsLeft.reset(); jsRight.reset();
  _applyEstopUI(true);
  showToast('🔴 E-STOP activé', 5000);
  if (window.AndroidBridge) AndroidBridge.vibrate(400);
}

function resetEstop() {
  api('POST', '/system/estop_reset');
  api('POST', '/bt/estop_reset');
  estopActive = false;
  _applyEstopUI(false);
}

// ── Lock ──────────────────────────────────────────────────────
function cycleLockMode() {
  if (lockMode === 2) { _showLockModal(); return; }
  lockMode = lockMode === 0 ? 1 : 2;
  _applyLockMode(true);
}

function _applyLockMode(sendApi) {
  const btn   = document.getElementById('lock-btn');
  const badge = document.getElementById('mode-badge');
  const hud   = document.getElementById('hud-drive');

  const CLS   = ['', 'kids', 'locked'];
  const BADGE = ['', 'KIDS MODE', 'CHILD LOCK'];

  if (btn) btn.className = CLS[lockMode] ? 'lock-btn ' + CLS[lockMode] : '';

  if (badge) {
    if (lockMode === 0) { badge.className = 'hidden'; badge.textContent = ''; }
    else { badge.textContent = '● ' + BADGE[lockMode]; badge.className = CLS[lockMode]; }
  }

  if (hud) hud.dataset.lock = lockMode;

  if (lockMode === 0)      speedLimit = 1.0;
  else if (lockMode === 1) speedLimit = 0.2;
  else {
    speedLimit = 0;
    jsLeft.reset(); jsRight.reset();
    api('POST', '/motion/stop');
  }

  if (sendApi) api('POST', '/lock/set', { mode: lockMode });
}

function _showLockModal() {
  const m = document.getElementById('lock-modal');
  const i = document.getElementById('lock-pwd');
  const e = document.getElementById('lock-pwd-err');
  if (m) m.classList.remove('hidden');
  if (e) e.classList.add('hidden');
  if (i) { i.value = ''; setTimeout(() => i.focus(), 80); }
}

function closeLockModal() {
  document.getElementById('lock-modal')?.classList.add('hidden');
}

function submitLockPwd() {
  const pwd = document.getElementById('lock-pwd')?.value || '';
  if (pwd === 'deetoo') {
    closeLockModal();
    lockMode = 0;
    _applyLockMode(true);
  } else {
    document.getElementById('lock-pwd-err')?.classList.remove('hidden');
    const i = document.getElementById('lock-pwd');
    if (i) { i.value = ''; i.focus(); }
    if (window.AndroidBridge) AndroidBridge.vibrate(80);
  }
}

// ── Audio ─────────────────────────────────────────────────────
let _activeCategory = null;

function loadCategories() {
  api('GET', '/audio/categories').then(r => r && r.json()).then(data => {
    if (!data?.categories) return;
    const list = document.getElementById('cat-list');
    list.innerHTML = '';
    data.categories.forEach((cat, i) => {
      const name = cat.name ?? cat;
      const btn  = document.createElement('button');
      btn.className   = 'cat-btn';
      btn.textContent = name;
      btn.onclick     = () => selectCategory(name, btn);
      list.appendChild(btn);
      if (i === 0) btn.click();
    });
  }).catch(() => {});
}

function selectCategory(name, btn) {
  document.querySelectorAll('.cat-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  _activeCategory = name;
  loadSounds(name);
}

function loadSounds(cat) {
  api('GET', `/audio/sounds?category=${encodeURIComponent(cat)}`).then(r => r && r.json()).then(data => {
    if (!data?.sounds) return;
    const grid = document.getElementById('sound-grid');
    grid.innerHTML = '';

    const rnd = document.createElement('button');
    rnd.className   = 'rnd-btn';
    rnd.textContent = `🎲 RANDOM`;
    rnd.onclick     = () => { api('POST', '/audio/random', { category: cat }); _haptic(30); };
    grid.appendChild(rnd);

    data.sounds.forEach(snd => {
      const btn = document.createElement('button');
      btn.className   = 'snd-btn';
      btn.textContent = snd.replace(/\.\w+$/, '');
      btn.title       = snd;
      btn.onclick     = () => { api('POST', '/audio/play', { sound: snd }); _haptic(20); };
      grid.appendChild(btn);
    });
  }).catch(() => {});
}

function stopAudio()  { api('POST', '/audio/stop'); }

function setVolume(val) {
  document.getElementById('vol-pct').textContent = val + '%';
  api('POST', '/audio/volume', { volume: parseInt(val, 10) });
}

// ── Sequences ─────────────────────────────────────────────────
function loadSequences() {
  api('GET', '/scripts/list').then(r => r && r.json()).then(data => {
    if (!data?.scripts) return;
    const list = document.getElementById('seq-list');
    list.innerHTML = '';
    data.scripts.forEach(name => {
      const row   = document.createElement('div');
      row.className = 'seq-row';
      const label = name.replace(/_/g, ' ');
      row.innerHTML = `
        <span class="seq-name">${label}</span>
        <button class="seq-run"  onclick="runSeq('${name}',false)">▶ RUN</button>
        <button class="seq-loop" onclick="runSeq('${name}',true)">🔁</button>
        <button class="seq-stop" onclick="stopAllSeq()">⏹</button>
      `;
      list.appendChild(row);
    });
  }).catch(() => {});
}

function runSeq(name, loop) { api('POST', '/scripts/run', { name, loop }); _haptic(30); }
function stopAllSeq()       { api('POST', '/scripts/stop_all'); _haptic(50); }

// ── Lights ────────────────────────────────────────────────────
function teecesMode(mode) { api('POST', '/teeces/' + mode); }
function teecesText() {
  const t = document.getElementById('teeces-text')?.value.trim();
  if (t) api('POST', '/teeces/text', { text: t });
}
function teecesPS(mode) { api('POST', '/teeces/psi', { mode }); }

// ── Host dialog ───────────────────────────────────────────────
function showHostDialog() {
  if (window.AndroidBridge) {
    const h = prompt('IP du Master R2-D2:', AndroidBridge.getHost());
    if (h?.trim()) {
      AndroidBridge.setHost(h.trim());
      API_BASE = 'http://' + h.trim() + ':5000';
      _updateHostLabel();
    }
  }
}

function _updateHostLabel() {
  const el = document.getElementById('status-host');
  if (el) el.textContent = API_BASE.replace('http://', '').replace(':5000', '');
}

// ── Haptic ────────────────────────────────────────────────────
function _haptic(ms) { if (window.AndroidBridge) AndroidBridge.vibrate(ms); }

// ── Init ──────────────────────────────────────────────────────
window.addEventListener('load', () => {
  if (window.AndroidBridge) {
    API_BASE = 'http://' + AndroidBridge.getHost() + ':5000';
  } else if (window.R2D2_API_BASE) {
    API_BASE = window.R2D2_API_BASE;
  }
  _updateHostLabel();

  const vs = document.getElementById('vol-slider');
  if (vs) document.getElementById('vol-pct').textContent = vs.value + '%';

  _applyLockMode(false);
});
```

- [ ] **Step 2: Commit**

```bash
cd "J:/R2-D2_Build/software"
git add android/app/src/main/assets/js/mobile.js
git commit -m "feat: HUD mobile.js v3 — drawer, openDrawer/closeDrawer, back button"
```

---

## Task 4: Sync to master/

**Files:**
- Sync: `master/templates/mobile.html`
- Sync: `master/static/css/mobile.css`
- Sync: `master/static/js/mobile.js`

- [ ] **Step 1: Copy assets to master**

```bash
cp android/app/src/main/assets/css/mobile.css master/static/css/mobile.css
cp android/app/src/main/assets/js/mobile.js  master/static/js/mobile.js
```

- [ ] **Step 2: Patch mobile.html for Flask (change asset paths)**

Copy `android/app/src/main/assets/mobile.html` to `master/templates/mobile.html`, changing:
```html
<!-- FROM (Android relative paths): -->
<link rel="stylesheet" href="css/mobile.css">
...
<script src="js/mobile.js"></script>

<!-- TO (Flask url_for): -->
<link rel="stylesheet" href="{{ url_for('static', filename='css/mobile.css') }}">
...
<script src="{{ url_for('static', filename='js/mobile.js') }}"></script>
```

- [ ] **Step 3: Commit sync**

```bash
cd "J:/R2-D2_Build/software"
git add master/templates/mobile.html master/static/css/mobile.css master/static/js/mobile.js
git commit -m "feat: sync HUD assets to master/ templates+static"
```

---

## Task 5: Build APK & Deploy

- [ ] **Step 1: Build APK**

```powershell
powershell.exe -Command "& { \$env:JAVA_HOME='C:/Program Files/Android/Android Studio/jbr'; Set-Location 'J:/R2-D2_Build/software/android'; ./gradlew.bat assembleDebug }"
```

Expected: `BUILD SUCCESSFUL`

- [ ] **Step 2: Copy APK**

```bash
cp android/app/build/outputs/apk/debug/app-debug.apk android/compiled/R2-D2_Control.apk
```

- [ ] **Step 3: Install via ADB**

```bash
"C:/Users/erict/AppData/Local/Android/Sdk/platform-tools/adb.exe" install -r android/compiled/R2-D2_Control.apk
"C:/Users/erict/AppData/Local/Android/Sdk/platform-tools/adb.exe" shell am force-stop com.r2d2.control
"C:/Users/erict/AppData/Local/Android/Sdk/platform-tools/adb.exe" shell am start -n com.r2d2.control/.MainActivity
```

Expected: `Success` + app launches in landscape HUD mode

- [ ] **Step 4: Commit APK + push**

```bash
cd "J:/R2-D2_Build/software"
git add android/compiled/R2-D2_Control.apk
git commit -m "ci: build HUD APK v3"
git push
```

- [ ] **Step 5: Deploy to Pi**

```python
import paramiko, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.2.104', username='artoo', password='deetoo', timeout=10)
stdin, stdout, stderr = c.exec_command('cd /home/artoo/r2d2 && bash scripts/update.sh 2>&1')
for line in stdout: print(line, end='')
c.close()
```
