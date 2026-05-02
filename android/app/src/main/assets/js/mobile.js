// ============================================================
//  AstromechOS Mobile HUD — mobile.js  v4
//  Self-contained, no dependency on app.js
//  v4: VESC safety lock, battery display, choreo drawer
// ============================================================
'use strict';

// ── Config ───────────────────────────────────────────────────
let API_BASE    = window.R2D2_API_BASE || 'http://192.168.4.1:5000';
let speedLimit  = 1.0;
let lockMode    = 0;   // 0=Normal  1=Kids  2=ChildLock
let estopActive     = false;
let vescDriveSafe   = true;
let driveActive = false;
let domeActive  = false;

const DRIVE_MS = 50;   // max 20 req/s
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

// ── Battery voltage → color class ────────────────────────────
// Thresholds per cell: ≥3.8V green · ≥3.6V orange · <3.6V red
function _battClass(v, cells) {
  if (!v || !cells) return '';
  const vpc = v / cells;
  if (vpc >= 3.8) return 'ok';
  if (vpc >= 3.6) return 'warn';
  return 'err';
}

// ── Status polling (1 s) ──────────────────────────────────────
let _lastUartPct    = 100;
let _lastEstop      = false;
let _lastVescSafe   = true;
let _batteryCells   = 4;
let _choreoRunning  = false;
let _choreoName     = '';

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
    if (pct < 80 && _lastUartPct >= 80) showToast(`⚠ UART degraded — ${Math.round(pct)}%`);
    if (!s.uart_ready && _lastUartPct > 0) showToast('🔴 UART disconnected!', 5000);
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

    // Battery voltage
    if (s.battery_cells) _batteryCells = s.battery_cells;
    const battEl = document.getElementById('batt-display');
    if (battEl) {
      if (s.battery_voltage) {
        battEl.textContent = `${s.battery_voltage.toFixed(1)}V`;
        battEl.className = 'batt-display ' + _battClass(s.battery_voltage, _batteryCells);
      } else {
        battEl.textContent = '';
        battEl.className = 'batt-display';
      }
    }

    // VESC safety lock — block drive if either VESC is offline or faulted
    const safe = s.vesc_drive_safe !== false;
    if (safe !== _lastVescSafe) {
      _lastVescSafe = safe;
      vescDriveSafe = safe;
      _applyVescSafetyUI(safe, s);
    } else {
      vescDriveSafe = safe;
    }

    // Choreo status — update playing bar if open
    if (s.choreo_playing !== undefined) {
      _choreoRunning = s.choreo_playing;
      _choreoName    = s.choreo_name || '';
      _updateChoreoBar();
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

function _applyVescSafetyUI(safe, s) {
  const banner = document.getElementById('vesc-safety-banner');
  const msg    = document.getElementById('vesc-safety-msg');
  if (!banner) return;

  if (!safe) {
    const who = (!s.vesc_l_ok && !s.vesc_r_ok) ? 'L+R'
              : (!s.vesc_l_ok) ? 'L' : 'R';
    if (msg) msg.textContent = `DRIVE BLOCKED — VESC ${who} OFFLINE`;
    banner.classList.remove('hidden');
    jsLeft.reset();
  } else {
    banner.classList.add('hidden');
  }
}

// ── Drawer system ─────────────────────────────────────────────
let _activeDrawer  = null;
let _drawerExpanded = false;
let _audioInit     = false;
let _seqInit       = false;
let _choreoInit    = false;

function openDrawer(tab) {
  if (_activeDrawer === tab) { closeDrawer(); return; }
  _activeDrawer = tab;

  // Hide all panes, show selected
  document.querySelectorAll('.drawer-pane').forEach(p => p.classList.remove('active'));
  document.getElementById('drawer-' + tab)?.classList.add('active');

  // Update title
  const titles = { audio: '🔊 AUDIO', choreo: '🎭 CHOREO', seq: '🎬 SEQUENCES', lights: '💡 LIGHTS' };
  document.getElementById('drawer-title').textContent = titles[tab] || tab;

  // Active pill highlight
  document.querySelectorAll('.pill-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('pill-' + tab)?.classList.add('active');

  // Show drawer with animation (reset expanded on new open)
  const drawer = document.getElementById('bottom-drawer');
  drawer.classList.remove('expanded');
  _drawerExpanded = false;
  drawer.classList.remove('hidden');
  requestAnimationFrame(() => drawer.classList.add('open'));

  // Show backdrop
  document.getElementById('drawer-backdrop')?.classList.remove('hidden');

  // Push history entry for back button
  history.pushState({ drawer: tab }, '');

  // Lazy load on first open
  if (tab === 'audio'  && !_audioInit)  { _audioInit  = true; loadCategories(); }
  if (tab === 'seq'    && !_seqInit)    { _seqInit    = true; loadSequences();  }
  if (tab === 'choreo' && !_choreoInit) { _choreoInit = true; loadChoreos();    }

  _haptic(20);
}

function closeDrawer() {
  if (!_activeDrawer) return;
  _activeDrawer = null;
  _drawerExpanded = false;

  const drawer = document.getElementById('bottom-drawer');
  drawer.classList.remove('open', 'expanded');
  drawer.addEventListener('transitionend', () => {
    if (!_activeDrawer) drawer.classList.add('hidden');
  }, { once: true });

  document.getElementById('drawer-backdrop')?.classList.add('hidden');
  document.querySelectorAll('.pill-btn').forEach(b => b.classList.remove('active'));
}

function _expandDrawer() {
  _drawerExpanded = true;
  document.getElementById('bottom-drawer')?.classList.add('expanded');
  _haptic(15);
}

function _collapseDrawer() {
  _drawerExpanded = false;
  document.getElementById('bottom-drawer')?.classList.remove('expanded');
  _haptic(15);
}

// ── Drawer swipe gesture (header swipe up = expand, down = collapse/close) ──
(function () {
  let _swipeStartY = null;
  let _swipeStartX = null;
  const SWIPE_THRESH = 40;  // px

  function _onTouchStart(e) {
    const t = e.touches[0];
    _swipeStartY = t.clientY;
    _swipeStartX = t.clientX;
  }

  function _onTouchEnd(e) {
    if (_swipeStartY === null) return;
    const t = e.changedTouches[0];
    const dy = t.clientY - _swipeStartY;
    const dx = t.clientX - _swipeStartX;
    _swipeStartY = null;
    _swipeStartX = null;

    // Ignore if horizontal swipe dominates
    if (Math.abs(dx) > Math.abs(dy)) return;

    if (dy < -SWIPE_THRESH) {
      // Swipe UP → expand
      if (!_drawerExpanded && _activeDrawer) _expandDrawer();
    } else if (dy > SWIPE_THRESH) {
      // Swipe DOWN → collapse if expanded, close if not
      if (_drawerExpanded) {
        _collapseDrawer();
      } else if (_activeDrawer) {
        closeDrawer();
      }
    }
  }

  window.addEventListener('load', () => {
    const header = document.getElementById('drawer-header');
    if (header) {
      header.addEventListener('touchstart', _onTouchStart, { passive: true });
      header.addEventListener('touchend',   _onTouchEnd,   { passive: true });
    }
  });
})();

// Back button: collapse expanded drawer first, then close, otherwise consume
window.addEventListener('popstate', () => {
  if (_drawerExpanded) {
    _collapseDrawer();
    history.pushState({ drawer: _activeDrawer }, '');  // keep the entry
  } else if (_activeDrawer) {
    closeDrawer();
  }
});

// ── Joystick — floating Roblox-style ──────────────────────────
// Ring appears at finger touch point, disappears on release.
class MobileJoystick {
  // zoneId  : touch zone element id (covers half-screen)
  // wrapId  : floating ring wrapper id
  // canStart: optional () => bool — returns false to block
  constructor(zoneId, wrapId, onMove, onStop, canStart) {
    this.zone     = document.getElementById(zoneId);
    this.wrap     = document.getElementById(wrapId);
    this.ring     = this.wrap.querySelector('.js-ring');
    this.knob     = this.wrap.querySelector('.js-knob');
    this.onMove   = onMove;
    this.onStop   = onStop;
    this.canStart = canStart || (() => true);
    this.touchId  = null;
    this.cx = 0; this.cy = 0;   // ring center (viewport coords)
    this.mr = 0;                 // max knob travel (px)
    this.x  = 0; this.y = 0;

    this.zone.addEventListener('touchstart',  e => this._start(e), { passive: false });
    this.zone.addEventListener('touchmove',   e => this._move(e),  { passive: false });
    this.zone.addEventListener('touchend',    e => this._end(e),   { passive: false });
    this.zone.addEventListener('touchcancel', e => this._end(e),   { passive: false });
  }

  _start(e) {
    e.preventDefault();
    if (this.touchId !== null) return;
    if (!this.canStart()) return;
    const t = e.changedTouches[0];
    this.touchId = t.identifier;

    const HALF = 65;            // half of 130px ring
    this.cx = t.clientX;
    this.cy = t.clientY;
    this.mr = HALF * 0.75;      // ~49px max knob travel

    // Place ring centered at finger position (fixed = viewport coords)
    this.wrap.style.left    = (t.clientX - HALF) + 'px';
    this.wrap.style.top     = (t.clientY - HALF) + 'px';
    this.wrap.style.display = 'block';
    this.ring.classList.add('touching');
    this._updateKnob(t);
  }

  _move(e) {
    e.preventDefault();
    for (const t of e.changedTouches) {
      if (t.identifier === this.touchId) { this._updateKnob(t); break; }
    }
  }

  _end(e) {
    for (const t of e.changedTouches) {
      if (t.identifier !== this.touchId) continue;
      this.touchId = null;
      this.x = 0; this.y = 0;
      this._setKnob(0, 0);
      this.ring.classList.remove('touching');
      this.wrap.style.display = 'none';   // disappears on release
      this.onStop();
      break;
    }
  }

  _updateKnob(touch) {
    let dx = touch.clientX - this.cx;
    let dy = touch.clientY - this.cy;
    const d = Math.hypot(dx, dy);
    if (d > this.mr) { dx = dx / d * this.mr; dy = dy / d * this.mr; }
    this.x =  dx / this.mr;
    this.y =  dy / this.mr;
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
    this.wrap.style.display = 'none';
  }
}

// Propulsion — blocked if ChildLock, E-STOP, or VESC unsafe
const jsLeft = new MobileJoystick(
  'js-zone-left',
  'js-left-wrap',
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
  () => !estopActive && lockMode !== 2 && vescDriveSafe
);

// Dome — blocked only by E-STOP (Kids mode: dome free)
const jsRight = new MobileJoystick(
  'js-zone-right',
  'js-right-wrap',
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

// ── Drive controls ────────────────────────────────────────────
function triggerEstop() {
  api('POST', '/system/estop');
  estopActive = true;
  jsLeft.reset(); jsRight.reset();
  _applyEstopUI(true);
  showToast('🔴 E-STOP activated', 5000);
  if (window.AndroidBridge) AndroidBridge.vibrate(400);
}

function resetEstop() {
  api('POST', '/system/estop_reset');
  api('POST', '/bt/estop_reset');
  estopActive = false;
  _applyEstopUI(false);
}

// ── Lock — cycle Normal(0) → Kids(1) → ChildLock(2) ──────────
// Exit ChildLock: password modal
function cycleLockMode() {
  if (lockMode === 2) { _showLockModal(); return; }
  lockMode = lockMode === 0 ? 1 : 2;
  _applyLockMode(true);
}

function _applyLockMode(sendApi) {
  const btn   = document.getElementById('lock-btn');
  const badge = document.getElementById('mode-badge');
  const hud   = document.getElementById('hud-drive');

  const CLS    = ['', 'kids', 'locked'];
  const BADGE  = ['', 'KIDS MODE', 'CHILD LOCK'];

  if (btn) btn.className = 'lock-btn ' + CLS[lockMode];

  if (badge) {
    if (lockMode === 0) {
      badge.className = 'hidden';
      badge.textContent = '';
    } else {
      badge.textContent = BADGE[lockMode];
      badge.className   = CLS[lockMode];
    }
  }

  if (hud) hud.dataset.lock = lockMode;

  if (lockMode === 0) {
    speedLimit = 1.0;
  } else if (lockMode === 1) {
    speedLimit = 0.2;
  } else {
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
    const err = document.getElementById('lock-pwd-err');
    if (err) err.classList.remove('hidden');
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
      const name = cat.name ?? cat;   // API: {name, count}
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
    rnd.textContent = `🎲  RANDOM  ${cat.toUpperCase()}`;
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

// ── Choreographies ────────────────────────────────────────────
let _choreoItems = [];   // [{name, label, emoji, category, duration}]

function loadChoreos() {
  api('GET', '/choreo/list').then(r => r && r.json()).then(data => {
    if (!data?.choreos) return;
    _choreoItems = data.choreos;
    _renderChoreoList();
  }).catch(() => {});
}

function _renderChoreoList() {
  const list = document.getElementById('choreo-list');
  if (!list) return;
  list.innerHTML = '';

  // Group by category
  const byCategory = {};
  const catOrder = [];
  _choreoItems.forEach(c => {
    const cat = c.category || 'uncategorized';
    if (!byCategory[cat]) { byCategory[cat] = []; catOrder.push(cat); }
    byCategory[cat].push(c);
  });

  catOrder.forEach(cat => {
    const items = byCategory[cat];

    // Category label (skip if only one unnamed group)
    if (catOrder.length > 1 || cat !== 'uncategorized') {
      const lbl = document.createElement('div');
      lbl.className = 'choreo-category-label';
      lbl.textContent = cat;
      list.appendChild(lbl);
    }

    items.forEach(c => {
      const row = document.createElement('div');
      row.className = 'choreo-row' + (_choreoName === c.name && _choreoRunning ? ' playing' : '');
      row.dataset.name = c.name;

      const dur = c.duration ? `${Math.round(c.duration)}s` : '';
      row.innerHTML =
        `<span class="choreo-emoji">${c.emoji || '🎭'}</span>` +
        `<span class="choreo-name">${c.label || c.name}</span>` +
        `<span class="choreo-dur">${dur}</span>`;

      row.onclick = () => { playChoreo(c.name, c.label || c.name); _haptic(30); };
      list.appendChild(row);
    });
  });

  _updateChoreoBar();
}

function _updateChoreoBar() {
  const bar  = document.getElementById('choreo-playing-bar');
  const name = document.getElementById('choreo-playing-name');
  if (!bar) return;

  if (_choreoRunning && _choreoName) {
    const item = _choreoItems.find(c => c.name === _choreoName);
    if (name) name.textContent = `▶ ${item?.label || _choreoName}`;
    bar.classList.remove('hidden');
  } else {
    bar.classList.add('hidden');
  }

  // Update playing highlight on rows
  document.querySelectorAll('.choreo-row').forEach(row => {
    row.classList.toggle('playing', _choreoRunning && row.dataset.name === _choreoName);
  });
}

function playChoreo(name, label) {
  api('POST', '/choreo/play', { name }).then(r => r && r.json()).then(d => {
    if (d) {
      _choreoRunning = true;
      _choreoName    = name;
      _updateChoreoBar();
    }
  }).catch(() => {});
}

function stopChoreo() {
  api('POST', '/choreo/stop').then(() => {
    _choreoRunning = false;
    _choreoName    = '';
    _updateChoreoBar();
  }).catch(() => {});
  _haptic(50);
}

// ── Sequences ─────────────────────────────────────────────────
function loadSequences() {
  api('GET', '/scripts/list').then(r => r && r.json()).then(data => {
    if (!data?.scripts) return;
    const list = document.getElementById('seq-list');
    list.innerHTML = '';
    data.scripts.forEach(name => {
      const row = document.createElement('div');
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
    const h = prompt('AstromechOS Master IP:', AndroidBridge.getHost());
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

// ── Camera stream — last-connect-wins proxy ───────────────────
let _camToken     = null;
let _camPollTimer = null;

async function _initCameraStream() {
  await _takeCameraStream();
}

async function _takeCameraStream() {
  const r = await fetch(API_BASE + '/camera/take', { method: 'POST' })
    .then(r => r.json()).catch(() => null);
  if (!r) return;
  _camToken = r.token;

  const img   = document.getElementById('cam-stream');
  const bg    = document.getElementById('cam-bg');
  const taken = document.getElementById('cam-taken');
  if (!img) return;

  if (taken) taken.style.display = 'none';
  img.src = API_BASE + `/camera/stream?t=${_camToken}`;
  img.style.display = 'block';
  if (bg) bg.style.display = 'none';

  _startCamPoll();
}

function _startCamPoll() {
  clearInterval(_camPollTimer);
  _camPollTimer = setInterval(async () => {
    if (!_camToken) return;
    const r = await fetch(API_BASE + '/camera/status')
      .then(r => r.json()).catch(() => null);
    if (!r) return;
    if (r.active_token !== _camToken) {
      _camToken = null;
      const img   = document.getElementById('cam-stream');
      const bg    = document.getElementById('cam-bg');
      const taken = document.getElementById('cam-taken');
      if (img)   { img.src = ''; img.style.display = 'none'; }
      if (bg)    bg.style.display = 'block';
      if (taken) taken.style.display = 'flex';
      clearInterval(_camPollTimer);
    }
  }, 3000);
}

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

  // Init lock visual (data-lock = 0)
  _applyLockMode(false);

  // Start camera stream
  _initCameraStream();
});
