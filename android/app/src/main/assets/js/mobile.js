// ============================================================
//  R2-D2 Mobile Control — mobile.js
//  Self-contained, no dependency on app.js
// ============================================================
'use strict';

// ── Config ───────────────────────────────────────────────────
let API_BASE    = window.R2D2_API_BASE || 'http://192.168.4.1:5000';
let speedLimit  = 1.0;
let lockMode    = 0;   // 0=Normal 1=Kids 2=ChildLock
let estopActive = false;
let driveActive = false;
let domeActive  = false;

const DRIVE_MS  = 50;   // max 20 req/s (mobile battery friendly)
let lastDriveT  = 0;
let lastDomeT   = 0;

// ── API helper ────────────────────────────────────────────────
function api(method, endpoint, body) {
  return fetch(API_BASE + endpoint, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body:    body ? JSON.stringify(body) : undefined,
  }).catch(() => null);
}

// ── Heartbeat (200ms — keeps app_watchdog alive) ──────────────
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

// ── Status polling (1s) ───────────────────────────────────────
let _lastUartPct = 100;
let _lastEstop   = false;

setInterval(() => {
  api('GET', '/status').then(r => r && r.json()).then(s => {
    if (!s) return;

    // Indicators
    _setInd('ind-hb',   s.heartbeat_ok);
    _setInd('ind-uart', s.uart_ready);
    _setInd('ind-bt',   s.bt_connected);

    // UART health %
    const pct = s.uart_health?.health_pct ?? 100;
    const uartPctEl = document.getElementById('uart-pct');
    if (uartPctEl) {
      uartPctEl.textContent = pct < 100 ? `${Math.round(pct)}%` : '';
      uartPctEl.style.color = pct < 80 ? 'var(--warn)' : 'var(--text-dim)';
    }
    if (pct < 80 && _lastUartPct >= 80) {
      showToast(`⚠️ UART dégradé — ${Math.round(pct)}%`);
    }
    if (!s.uart_ready && _lastUartPct > 0) {
      showToast('🔴 UART déconnecté !', 5000);
    }
    _lastUartPct = pct;

    // Temperature
    if (s.temperature != null) {
      const tv = document.getElementById('temp-val');
      if (tv) tv.textContent = `🌡️ ${s.temperature}°C`;
    }

    // E-STOP sync
    if (s.estop_active !== _lastEstop) {
      _lastEstop = s.estop_active;
      _applyEstopUI(s.estop_active);
    }
    estopActive = s.estop_active;

    // Sync lock mode from server
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

// ── Tab switching ─────────────────────────────────────────────
let _audioInit = false;
let _seqInit   = false;

function switchTab(tab, btn) {
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + tab).classList.add('active');
  btn.classList.add('active');
  if (tab === 'audio'     && !_audioInit) { _audioInit = true; loadCategories(); }
  if (tab === 'sequences' && !_seqInit)   { _seqInit   = true; loadSequences();  }
}

// ── Joystick ──────────────────────────────────────────────────
class MobileJoystick {
  constructor(id, onMove, onStop) {
    const wrap   = document.getElementById(id);
    this.ring    = wrap.querySelector('.js-ring');
    this.knob    = wrap.querySelector('.js-knob');
    this.onMove  = onMove;
    this.onStop  = onStop;
    this.touchId = null;
    this.x = 0; this.y = 0;
    this.ring.addEventListener('touchstart',  e => this._start(e), { passive: false });
    this.ring.addEventListener('touchmove',   e => this._move(e),  { passive: false });
    this.ring.addEventListener('touchend',    e => this._end(e),   { passive: false });
    this.ring.addEventListener('touchcancel', e => this._end(e),   { passive: false });
  }

  _start(e) {
    e.preventDefault();
    if (this.touchId !== null) return;
    const t = e.changedTouches[0];
    this.touchId = t.identifier;
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
    this.knob.style.transform = `translate(calc(-50% + ${dx}px), calc(-50% + ${dy}px))`;
  }

  reset() {
    this.touchId = null; this.x = 0; this.y = 0;
    this._setKnob(0, 0);
  }
}

// Propulsion (left stick — throttle + steer)
const jsLeft = new MobileJoystick('js-left', (x, y) => {
  if (lockMode === 2 || estopActive) return;
  const now = Date.now();
  if (now - lastDriveT < DRIVE_MS) return;
  lastDriveT = now;
  const thr = -y * speedLimit;
  const str =  x * speedLimit * 0.55;
  const L = Math.max(-1, Math.min(1, thr + str));
  const R = Math.max(-1, Math.min(1, thr - str));
  api('POST', '/motion/drive', { left: +L.toFixed(3), right: +R.toFixed(3) });
  driveActive = true;
}, () => {
  if (driveActive) { api('POST', '/motion/stop'); driveActive = false; }
});

// Dôme (right stick — X axis only)
const jsRight = new MobileJoystick('js-right', (x, _y) => {
  if (estopActive) return;
  const now = Date.now();
  if (now - lastDomeT < DRIVE_MS) return;
  lastDomeT = now;
  const speed = +(x * 0.85).toFixed(3);
  api('POST', '/motion/dome/turn', { speed });
  domeActive = true;
}, () => {
  if (domeActive) { api('POST', '/motion/dome/stop'); domeActive = false; }
});

// ── Drive controls ────────────────────────────────────────────
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

function updateSpeedLimit(val) {
  speedLimit = val / 100;
  const el = document.getElementById('speed-pct');
  if (el) el.textContent = val + '%';
}

// Lock cycle : Normal(0) → Kids(1) → ChildLock(2) → Normal
function cycleLockMode() {
  lockMode = (lockMode + 1) % 3;
  _applyLockMode(true);
}

function _applyLockMode(sendApi) {
  const btn = document.getElementById('lock-btn');
  const sc  = document.getElementById('speed-container');

  if (lockMode === 0) {
    speedLimit = 1.0;
    if (btn) { btn.textContent = '🔒'; btn.className = 'lock-btn'; }
    if (sc)  sc.classList.add('hidden');
  } else if (lockMode === 1) {
    const sliderVal = document.getElementById('speed-slider')?.value || 50;
    updateSpeedLimit(sliderVal);
    if (btn) { btn.textContent = '🔒'; btn.className = 'lock-btn kids'; }
    if (sc)  sc.classList.remove('hidden');
  } else {
    speedLimit = 0;
    if (btn) { btn.textContent = '🔒'; btn.className = 'lock-btn locked'; }
    if (sc)  sc.classList.add('hidden');
    jsLeft.reset(); jsRight.reset();
    api('POST', '/motion/stop');
  }

  if (sendApi) api('POST', '/lock/set', { mode: lockMode });
}

// ── Audio ─────────────────────────────────────────────────────
let _activeCategory = null;

function loadCategories() {
  api('GET', '/audio/categories').then(r => r && r.json()).then(data => {
    if (!data?.categories) return;
    const list = document.getElementById('cat-list');
    list.innerHTML = '';
    data.categories.forEach((cat, i) => {
      const btn = document.createElement('button');
      btn.className   = 'cat-btn';
      btn.textContent = cat;
      btn.onclick     = () => selectCategory(cat, btn);
      list.appendChild(btn);
      if (i === 0) btn.click();   // auto-select first
    });
  }).catch(() => {});
}

function selectCategory(cat, btn) {
  document.querySelectorAll('.cat-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  _activeCategory = cat;
  loadSounds(cat);
}

function loadSounds(cat) {
  api('GET', `/audio/sounds?category=${cat}`).then(r => r && r.json()).then(data => {
    if (!data?.sounds) return;
    const grid = document.getElementById('sound-grid');
    grid.innerHTML = '';

    // Random button (full width)
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

function stopAudio() { api('POST', '/audio/stop'); }

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
      const row = document.createElement('div');
      row.className = 'seq-row';
      row.id = 'seq-row-' + name;
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

function runSeq(name, loop) {
  api('POST', '/scripts/run', { name, loop });
  _haptic(30);
}

function stopAllSeq() {
  api('POST', '/scripts/stop_all');
  _haptic(50);
}

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
    const current = AndroidBridge.getHost();
    const h = prompt('IP du Master R2-D2:', current);
    if (h && h.trim()) {
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
function _haptic(ms) {
  if (window.AndroidBridge) AndroidBridge.vibrate(ms);
}

// ── Init ──────────────────────────────────────────────────────
window.addEventListener('load', () => {
  // Resolve API base
  if (window.AndroidBridge) {
    API_BASE = 'http://' + AndroidBridge.getHost() + ':5000';
  } else if (window.R2D2_API_BASE) {
    API_BASE = window.R2D2_API_BASE;
  }
  _updateHostLabel();

  // Init volume display
  const vs = document.getElementById('vol-slider');
  if (vs) document.getElementById('vol-pct').textContent = vs.value + '%';
});
