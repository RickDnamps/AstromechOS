/*
 * ============================================================
 *  ██████╗ ██████╗       ██████╗ ██████╗
 *  ██╔══██╗╚════██╗      ██╔══██╗╚════██╗
 *  ██████╔╝ █████╔╝      ██║  ██║ █████╔╝
 *  ██╔══██╗██╔═══╝       ██║  ██║██╔═══╝
 *  ██║  ██║███████╗      ██████╔╝███████╗
 *  ╚═╝  ╚═╝╚══════╝      ╚═════╝ ╚══════╝
 *
 *  R2-D2 Control System — Distributed Robot Controller
 * ============================================================
 *  Copyright (C) 2025 RickDnamps
 *  https://github.com/RickDnamps/R2D2_Control
 *
 *  This file is part of R2D2_Control.
 *
 *  R2D2_Control is free software: you can redistribute it
 *  and/or modify it under the terms of the GNU General
 *  Public License as published by the Free Software
 *  Foundation, either version 2 of the License, or
 *  (at your option) any later version.
 *
 *  R2D2_Control is distributed in the hope that it will be
 *  useful, but WITHOUT ANY WARRANTY; without even the implied
 *  warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
 *  PURPOSE. See the GNU General Public License for details.
 *
 *  You should have received a copy of the GNU GPL along with
 *  R2D2_Control. If not, see <https://www.gnu.org/licenses/>.
 * ============================================================
 */
/**
 * R2-D2 Control Dashboard — app.js
 * Holographic theme — Classes + REST polling
 * No external dependencies.
 */

'use strict';

// ================================================================
// Utilities
// ================================================================

function el(id) { return document.getElementById(id); }

function escapeHtml(s) {
  return String(s)
    .replace(/&/g,'&amp;')
    .replace(/</g,'&lt;')
    .replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;');
}

// ================================================================
// API Helper
// ================================================================

async function api(endpoint, method = 'GET', body = null) {
  try {
    const base = (typeof window.R2D2_API_BASE === 'string' && window.R2D2_API_BASE) ? window.R2D2_API_BASE : '';
    const url  = base + endpoint;
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(url, opts);
    const data = await res.json();
    return data;
  } catch (e) {
    console.error(`API ${method} ${endpoint}:`, e);
    return null;
  }
}

// ================================================================
// Toast Manager
// ================================================================

class ToastManager {
  constructor() {
    this._el = el('toast');
    this._timer = null;
  }

  show(msg, type = 'info') {
    const t = this._el;
    t.textContent = msg;
    t.className = `toast toast-${type} show`;
    clearTimeout(this._timer);
    this._timer = setTimeout(() => t.classList.remove('show'), 3000);
  }
}

const toastMgr = new ToastManager();
function toast(msg, type = 'info') { toastMgr.show(msg, type); }

// ================================================================
// Tab Navigation
// ================================================================

// ================================================================
// Lock Manager — Kids Mode / Child Lock
// ================================================================

class LockManager {
  constructor() {
    this._mode         = 0;   // 0=Normal 1=Kids 2=ChildLock
    this._kidsSpeed    = parseInt(localStorage.getItem('kidsSpeedLimit') || '20');
    this._prevSpeed    = null;
    this._kidsTimer    = null;
    this._kidsTimedOut = false;
    this._KIDS_TIMEOUT = 5 * 60 * 1000;   // 5 minutes
  }

  get mode() { return this._mode; }

  init() {
    const s = el('kids-speed-slider');
    if (s) s.value = this._kidsSpeed;
    const v = el('kids-speed-val');
    if (v) v.textContent = this._kidsSpeed + '%';
    document.body.dataset.lockMode = '0';
  }

  setKidsSpeed(val) {
    this._kidsSpeed = val;
    localStorage.setItem('kidsSpeedLimit', val);
    const v = el('kids-speed-val');
    if (v) v.textContent = val + '%';
    if (this._mode === 1) this._applyKidsSpeed();
  }

  onBtnClick() {
    if (this._mode === 0) {
      this._applyMode(1);                        // Normal → Kids (direct)
    } else if (this._mode === 1) {
      if (this._kidsTimedOut) {
        this._showKidsChoiceModal();             // ≥5 min en Kids → choix
      } else {
        this._applyMode(2);                      // <5 min en Kids → Child Lock direct
      }
    } else {
      this._showUnlockModal();                   // Child Lock → déverrouillage
    }
  }

  // Modal choix depuis Kids mode expiré (3 options)
  _showKidsChoiceModal() {
    const m = el('lock-modal');
    m.classList.remove('hidden');
    el('lock-modal-icon').style.color   = 'var(--orange)';
    el('lock-modal-title').style.color  = 'var(--orange)';
    el('lock-modal-title').textContent  = 'KIDS MODE ACTIVE';
    el('lock-modal-sub').textContent    = 'Enter password to return to normal mode';
    el('lock-childlock-btn').style.display = '';   // montrer bouton Child Lock
    el('lock-pwd-input').value = '';
    el('lock-pwd-error').classList.add('hidden');
    setTimeout(() => el('lock-pwd-input').focus(), 80);
  }

  // Modal déverrouillage simple (Child Lock → Normal)
  _showUnlockModal() {
    const m = el('lock-modal');
    m.classList.remove('hidden');
    el('lock-modal-icon').style.color   = 'var(--red)';
    el('lock-modal-title').style.color  = 'var(--red)';
    el('lock-modal-title').textContent  = 'CHILD LOCK ACTIVE';
    el('lock-modal-sub').textContent    = 'Enter password to return to normal mode';
    el('lock-childlock-btn').style.display = 'none';   // cacher bouton Child Lock
    el('lock-pwd-input').value = '';
    el('lock-pwd-error').classList.add('hidden');
    setTimeout(() => el('lock-pwd-input').focus(), 80);
  }

  cancelModal() { el('lock-modal').classList.add('hidden'); }

  onOverlayClick(e) { if (e.target === el('lock-modal')) this.cancelModal(); }

  // Depuis le modal : escalader en Child Lock
  escalateToChildLock() {
    el('lock-modal').classList.add('hidden');
    this._applyMode(2);
  }

  submitModal() {
    const pwd = el('lock-pwd-input').value;
    if (pwd === 'deetoo') {
      el('lock-modal').classList.add('hidden');
      this._applyMode(0);
    } else {
      el('lock-pwd-error').classList.remove('hidden');
      const inp = el('lock-pwd-input');
      inp.value = '';
      inp.classList.remove('shake');
      void inp.offsetWidth;
      inp.classList.add('shake');
      inp.focus();
    }
  }

  _applyMode(mode) {
    const prev = this._mode;
    this._mode = mode;
    document.body.dataset.lockMode = mode;

    const label = el('lock-mode-label');
    if (label) label.textContent = ['', 'KIDS', 'LOCK'][mode];

    // Timer Kids Mode
    if (mode === 1) {
      this._prevSpeed    = Math.round(_speedLimit * 100);
      this._kidsTimedOut = false;
      this._applyKidsSpeed();
      this._kidsTimer = setTimeout(() => { this._kidsTimedOut = true; }, this._KIDS_TIMEOUT);
    } else {
      clearTimeout(this._kidsTimer);
      this._kidsTimedOut = false;
      if (mode === 0 && prev !== 0 && this._prevSpeed !== null) {
        const s = el('speed-slider');
        if (s) { s.value = this._prevSpeed; setSpeed(this._prevSpeed); }
        this._prevSpeed = null;
      }
    }

    api('/lock/set', 'POST', { mode });

    const msgs  = ['Normal mode restored', 'Kids Mode — speed limited', 'Child Lock — movement blocked'];
    const types = ['ok', 'warn', 'error'];
    toast(msgs[mode], types[mode]);
  }

  _applyKidsSpeed() {
    const s = el('speed-slider');
    if (s) { s.value = this._kidsSpeed; setSpeed(this._kidsSpeed); }
  }

  isDriveLocked() { return this._mode === 2; }
  isKidsMode()    { return this._mode === 1; }

  syncFromStatus(lockMode) {
    if (lockMode !== undefined && lockMode !== this._mode) {
      this._mode = lockMode;
      document.body.dataset.lockMode = lockMode;
      const label = el('lock-mode-label');
      if (label) label.textContent = ['', 'KIDS', 'LOCK'][lockMode];
      if (lockMode === 1) this._applyKidsSpeed();
    }
  }
}

const lockMgr = new LockManager();

// ================================================================
// Admin Guard — onglets protégés (SERVO / VESC / CONFIG)
// ================================================================

class AdminGuard {
  constructor() {
    this._unlocked  = false;
    this._timer     = null;
    this._TIMEOUT   = 5 * 60 * 1000;   // 5 minutes
    this._PROTECTED = new Set(['systems', 'vesc', 'config', 'editor']);
    // Bound handler — stored to allow removeEventListener
    this._boundActivity = () => this._onActivity();
  }

  get unlocked() { return this._unlocked; }
  isProtected(tabId) { return this._PROTECTED.has(tabId); }

  showModal() {
    const m = el('admin-modal');
    if (!m) return;
    m.classList.remove('hidden');
    el('admin-pwd-input').value = '';
    el('admin-pwd-error').classList.add('hidden');
    setTimeout(() => el('admin-pwd-input').focus(), 80);
  }

  cancel() { el('admin-modal').classList.add('hidden'); }

  onOverlayClick(e) {
    if (e.target === el('admin-modal')) this.cancel();
  }

  submit() {
    const pwd = el('admin-pwd-input').value;
    if (pwd === 'deetoo') {
      this._unlock();
    } else {
      el('admin-pwd-error').classList.remove('hidden');
      const inp = el('admin-pwd-input');
      inp.value = '';
      inp.classList.remove('shake');
      void inp.offsetWidth;
      inp.classList.add('shake');
      inp.focus();
    }
  }

  _unlock() {
    this._unlocked = true;
    document.body.classList.add('admin-unlocked');
    el('admin-modal').classList.add('hidden');
    toast('Admin access granted — expires in 5 min', 'ok');
    // Écouter l'activité pour reset le timer quand sur un onglet admin
    document.addEventListener('mousemove', this._boundActivity, { passive: true });
    document.addEventListener('click',     this._boundActivity, { passive: true });
    document.addEventListener('keydown',   this._boundActivity, { passive: true });
    this._startTimer();
  }

  lock() {
    if (!this._unlocked) return;
    this._unlocked = false;
    clearTimeout(this._timer);
    document.body.classList.remove('admin-unlocked');
    document.removeEventListener('mousemove', this._boundActivity);
    document.removeEventListener('click',     this._boundActivity);
    document.removeEventListener('keydown',   this._boundActivity);
    // Si on est sur un onglet protégé → revenir à DRIVE
    const active = document.querySelector('.tab.active');
    if (active && this._PROTECTED.has(active.dataset.tab)) {
      switchTab('drive');
    }
    toast('Admin access expired', 'info');
  }

  onTabSwitch(tabId) {
    if (!this._unlocked) return;
    // Toujours (re)lancer le timer au changement d'onglet
    this._startTimer();
  }

  _onActivity() {
    if (!this._unlocked) return;
    // Reset le timer uniquement si on est sur un onglet admin
    const active = document.querySelector('.tab.active');
    if (active && this._PROTECTED.has(active.dataset.tab)) {
      this._startTimer();
    }
  }

  _startTimer() {
    clearTimeout(this._timer);
    this._timer = setTimeout(() => this.lock(), this._TIMEOUT);
  }
}

const adminGuard = new AdminGuard();

function switchTab(tabId) {
  // Onglet protégé sans accès → ouvrir modal
  if (adminGuard.isProtected(tabId) && !adminGuard.unlocked) {
    adminGuard.showModal();
    return;
  }

  document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  const tabBtn = document.querySelector(`.tab[data-tab="${tabId}"]`);
  const tabContent = el(`tab-${tabId}`);
  if (tabBtn) tabBtn.classList.add('active');
  if (tabContent) tabContent.classList.add('active');

  adminGuard.onTabSwitch(tabId);

  if (tabId === 'config') { loadSettings(); loadServoSettings(); }
  if (tabId === 'sequences') loadScripts();
  if (tabId === 'audio') loadAudioCategories();
  if (tabId === 'editor') {
    if (typeof seqEditor !== 'undefined') seqEditor.loadSequenceList();
    if (typeof lightEditor !== 'undefined') lightEditor.loadSequenceList();
  }
  if (tabId === 'vesc') vescPanel.refresh();
}

document.querySelectorAll('.tab').forEach(btn => {
  btn.addEventListener('click', () => switchTab(btn.dataset.tab));
});

// ================================================================
// Battery Gauge
// ================================================================

class BatteryGauge {
  constructor() {
    this._arc      = el('battery-gauge-arc');
    this._arcMini  = el('battery-arc-path');
    this._text     = el('battery-gauge-text');
    this._pct      = el('battery-pct');
    this._TOTAL    = 170;   // full arc length (main)
    this._MINI     = 63;    // full arc length (mini header)
    this._MIN_V    = 20.0;
    this._MAX_V    = 29.4;
  }

  update(voltage) {
    if (!voltage || voltage < 1) return;
    const pct  = Math.max(0, Math.min(1, (voltage - this._MIN_V) / (this._MAX_V - this._MIN_V)));
    const color = pct > 0.5 ? '#00cc66' : pct > 0.25 ? '#ff8800' : '#ff2244';

    // Main arc
    if (this._arc) {
      const offset = this._TOTAL * (1 - pct);
      this._arc.style.strokeDashoffset = offset;
      this._arc.style.stroke = color;
    }
    if (this._text) {
      this._text.textContent = voltage.toFixed(1) + 'V';
      this._text.style.fill = color;
    }

    // Mini header arc
    if (this._arcMini) {
      const offsetMini = this._MINI * (1 - pct);
      this._arcMini.style.strokeDashoffset = offsetMini;
      this._arcMini.style.stroke = color;
    }
    if (this._pct) {
      this._pct.textContent = voltage.toFixed(1) + 'V';
      this._pct.style.color = color;
    }
  }
}

const batteryGauge = new BatteryGauge();

// ================================================================
// Virtual Joystick
// ================================================================

class VirtualJoystick {
  constructor(ringId, knobId, onMove, onStop, valXId = null, valYId = null) {
    this.ring   = el(ringId);
    this.knob   = el(knobId);
    this._lastSend = 0;   // throttle: ms timestamp of last onMove call
    this._THROTTLE_MS = 1000 / 60;  // 60 req/s max
    this.onMove = onMove;
    this.onStop = onStop;
    this._valXId = valXId;
    this._valYId = valYId;
    this.active = false;
    this.x = 0;
    this.y = 0;
    this._keepAlive = null;  // timer keep-alive watchdog Master
    this._bind();
  }

  _bind() {
    const r = this.ring;
    r.addEventListener('touchstart',  e => { e.preventDefault(); this._start(e.touches[0]); }, { passive: false });
    r.addEventListener('touchmove',   e => { e.preventDefault(); this._move(e.touches[0]); },  { passive: false });
    r.addEventListener('touchend',    () => this._release());
    r.addEventListener('touchcancel', () => this._release());
    r.addEventListener('mousedown',   e => this._start(e));
    document.addEventListener('mousemove', e => { if (this.active) this._move(e); });
    document.addEventListener('mouseup',   () => { if (this.active) this._release(); });
  }

  _start(ptr) {
    this.active = true;
    this.ring.classList.add('active');
    this._move(ptr);
    // Keep-alive : renvoie la position courante toutes les 200ms pendant que
    // le joystick est tenu immobile — alimente le MotionWatchdog côté Master.
    this._keepAlive = setInterval(() => {
      if (this.active) this.onMove(this.x, this.y);
    }, 200);
  }

  _move(ptr) {
    if (!this.active) return;
    const rect   = this.ring.getBoundingClientRect();
    const cx     = rect.left + rect.width  / 2;
    const cy     = rect.top  + rect.height / 2;
    const radius = rect.width / 2;
    const dx     = ptr.clientX - cx;
    const dy     = ptr.clientY - cy;
    const maxR   = radius * 0.72;
    const dist   = Math.sqrt(dx * dx + dy * dy);
    const clamp  = Math.min(dist, maxR);
    const angle  = Math.atan2(dy, dx);
    const kx     = Math.cos(angle) * clamp;
    const ky     = Math.sin(angle) * clamp;

    this.x = Math.max(-1, Math.min(1, dx / maxR));
    this.y = Math.max(-1, Math.min(1, dy / maxR));

    this.knob.style.transform = `translate(calc(-50% + ${kx}px), calc(-50% + ${ky}px))`;
    const now = performance.now();
    if (now - this._lastSend >= this._THROTTLE_MS) {
      this._lastSend = now;
      this.onMove(this.x, this.y);
    }

    // Android haptic feedback — light vibration when joystick moves significantly
    const nx = this.x;
    const ny = this.y;
    if (window.AndroidBridge && Math.abs(nx) + Math.abs(ny) > 0.1) {
      window.AndroidBridge.vibrate(20);
    }

    // Update value displays
    if (this._valXId) {
      const vx = el(this._valXId);
      if (vx) vx.textContent = this.x.toFixed(2);
    }
    if (this._valYId) {
      const vy = el(this._valYId);
      if (vy) vy.textContent = this.y.toFixed(2);
    }
  }

  _release() {
    this.active = false;
    clearInterval(this._keepAlive);
    this._keepAlive = null;
    this.x = 0;
    this.y = 0;
    this.ring.classList.remove('active');
    this.knob.style.transform = 'translate(-50%, -50%)';
    this.onStop();
    if (this._valXId) { const v = el(this._valXId); if (v) v.textContent = '0.00'; }
    if (this._valYId) { const v = el(this._valYId); if (v) v.textContent = '0.00'; }
  }

  /** Déplace le knob visuellement depuis une source externe (manette BT).
   *  x, y ∈ [-1, 1].  Ne déclenche PAS onMove ni de requête HTTP. */
  setExternal(x, y) {
    if (this.active) return;   // joystick tactile prioritaire
    const maxR = this.ring.offsetWidth / 2;
    const kx   = x * maxR;
    const ky   = y * maxR;
    this.knob.style.transform = `translate(calc(-50% + ${kx}px), calc(-50% + ${ky}px))`;
    if (this._valXId) { const v = el(this._valXId); if (v) v.textContent = x.toFixed(2); }
    if (this._valYId) { const v = el(this._valYId); if (v) v.textContent = y.toFixed(2); }
  }
}

// ================================================================
// Propulsion & Dome
// ================================================================

let _speedLimit = 0.6;

function setSpeed(val) {
  _speedLimit = val / 100;
  el('speed-val').textContent = val + '%';
  // update slider gradient
  const slider = el('speed-slider');
  if (slider) slider.style.setProperty('--val', val + '%');
}

function driveStop()       { api('/motion/stop',      'POST'); }
function domeStop()        { api('/motion/dome/stop', 'POST'); }
function domeRandom(on)    { api('/motion/dome/random', 'POST', { enabled: on }); }

function emergencyStop() {
  driveStop();
  domeStop();
  api('/audio/stop', 'POST');
  api('/servo/dome/close_all', 'POST');
  api('/servo/body/close_all', 'POST');
  api('/system/estop', 'POST');
  toast('EMERGENCY STOP', 'error');
  audioBoard.setPlaying(false);
}

function estopReset() {
  api('/system/estop_reset', 'POST').then(r => {
    if (r && r.status === 'reset') {
      toast('E-STOP RESET — servos re-armed', 'ok');
    } else {
      toast('Reset failed', 'error');
    }
  }).catch(() => toast('Reset failed', 'error'));
}

// Left joystick — Propulsion (arcade drive)
let _leftActive = false;
const jsLeft = new VirtualJoystick(
  'js-left-ring', 'js-left-knob',
  (x, y) => {
    if (lockMgr.isDriveLocked()) return;   // Child Lock : joystick gauche bloqué
    _leftActive = true;
    const throttle = -y * _speedLimit;
    const steering =  x * _speedLimit * 0.55;
    api('/motion/arcade', 'POST', { throttle, steering });
    // update throttle/steer displays
    const t = el('js-left-t'); if (t) t.textContent = throttle.toFixed(2);
    const s = el('js-left-s'); if (s) s.textContent = steering.toFixed(2);
  },
  () => {
    _leftActive = false;
    driveStop();
    const t = el('js-left-t'); if (t) t.textContent = '0.00';
    const s = el('js-left-s'); if (s) s.textContent = '0.00';
  }
);

// Right joystick — Dome
let _domeActive = false;
const jsRight = new VirtualJoystick(
  'js-right-ring', 'js-right-knob',
  (x, y) => {
    const DEADZONE = 0.06;
    const vx = el('js-right-x'); if (vx) vx.textContent = x.toFixed(2);
    const vy = el('js-right-y'); if (vy) vy.textContent = y.toFixed(2);
    if (Math.abs(x) > DEADZONE) {
      api('/motion/dome/turn', 'POST', { speed: x * 0.85 });
      _domeActive = true;
    } else if (_domeActive) {
      domeStop();
      _domeActive = false;
    }
  },
  () => {
    domeStop();
    _domeActive = false;
    const vx = el('js-right-x'); if (vx) vx.textContent = '0.00';
    const vy = el('js-right-y'); if (vy) vy.textContent = '0.00';
  }
);

// ================================================================
// Keyboard Control (WASD / Arrows)
// ================================================================

const _keys = {};
const KBD_IDS = { 'KeyW': 'kbd-w', 'ArrowUp': 'kbd-w', 'KeyS': 'kbd-s', 'ArrowDown': 'kbd-s',
                  'KeyA': 'kbd-a', 'ArrowLeft': 'kbd-a', 'KeyD': 'kbd-d', 'ArrowRight': 'kbd-d' };

document.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT' || e.target.tagName === 'TEXTAREA') return;
  if (e.code === 'Space') { e.preventDefault(); emergencyStop(); return; }
  if (_keys[e.code]) return;
  _keys[e.code] = true;
  _updateKbdUI();
  _handleKeys();
});

document.addEventListener('keyup', e => {
  delete _keys[e.code];
  _updateKbdUI();
  _handleKeys();
});

function _updateKbdUI() {
  ['kbd-w','kbd-s','kbd-a','kbd-d'].forEach(id => {
    const k = el(id);
    if (k) k.classList.remove('active');
  });
  Object.keys(_keys).forEach(code => {
    const id = KBD_IDS[code];
    if (id) { const k = el(id); if (k) k.classList.add('active'); }
  });
}

function _handleKeys() {
  if (_leftActive) return; // joystick takes priority
  const fwd   = _keys['KeyW'] || _keys['ArrowUp'];
  const back  = _keys['KeyS'] || _keys['ArrowDown'];
  const left  = _keys['KeyA'] || _keys['ArrowLeft'];
  const right = _keys['KeyD'] || _keys['ArrowRight'];

  if (!fwd && !back && !left && !right) { driveStop(); return; }

  const throttle = (fwd ? 1 : back  ? -1 : 0) * _speedLimit;
  const steering = (right ? 1 : left ? -1 : 0) * _speedLimit * 0.5;
  api('/motion/arcade', 'POST', { throttle, steering });
}

// ================================================================
// Teeces Controller
// ================================================================

class TeecesController {
  constructor() {
    this._currentMode = 'random';
    this._initFLD();
    this._initPSI();
  }

  _initFLD() {
    const PSI_COLORS = [
      '#ff2244','#ff8800','#ffee00','#00cc66',
      '#00aaff','#8844ff','#ff44aa','#ffffff'
    ];

    // Build FLD dots (3 rows x 10 dots)
    for (let row = 0; row < 3; row++) {
      const rowEl = el(`fld-row-${row}`);
      if (!rowEl) continue;
      rowEl.innerHTML = '';
      for (let col = 0; col < 10; col++) {
        const dot = document.createElement('div');
        dot.className = 'fld-dot';
        rowEl.appendChild(dot);
      }
    }
    // Set initial mode
    this._applyFLDMode('random');

    // Build PSI swatches
    const swatches = el('psi-swatches');
    if (swatches) {
      swatches.innerHTML = PSI_COLORS.map((c, i) => `
        <div class="psi-swatch" style="background:${c};box-shadow:0 0 8px ${c}40"
             onclick="teecesController.setPSI(${i+1})" title="PSI mode ${i+1}"></div>
      `).join('');
    }
  }

  _initPSI() {
    // PSI dots start blue
    const pl = el('psi-left');
    const pr = el('psi-right');
    if (pl) { pl.style.background = '#00aaff'; pl.style.boxShadow = '0 0 10px #00aaff'; }
    if (pr) { pr.style.background = '#00aaff'; pr.style.boxShadow = '0 0 10px #00aaff'; }
  }

  _applyFLDMode(mode) {
    const preview = el('fld-preview');
    if (!preview) return;
    preview.className = `fld-preview mode-${mode}`;
  }

  setMode(mode) {
    this._currentMode = mode;
    api(`/teeces/${mode}`, 'POST').then(d => {
      if (d) toast(`Teeces: ${mode.toUpperCase()}`, 'ok');
    });
    document.querySelectorAll('[id^="teeces-btn-"]').forEach(b => b.classList.remove('btn-active'));
    const btn = el(`teeces-btn-${mode}`);
    if (btn) btn.classList.add('btn-active');
    this._applyFLDMode(mode);
  }

  sendText(text) {
    if (!text) return;
    api('/teeces/text', 'POST', { text }).then(d => {
      if (d) toast(`FLD: "${text}"`, 'ok');
    });
  }

  setPSI(modeNum) {
    api('/teeces/psi', 'POST', { mode: modeNum }).then(d => {
      if (d) toast(`PSI mode ${modeNum}`, 'ok');
    });
    const PSI_COLORS = ['#ff2244','#ff8800','#ffee00','#00cc66','#00aaff','#8844ff','#ff44aa','#ffffff'];
    const color = PSI_COLORS[modeNum - 1] || '#00aaff';
    ['psi-left','psi-right'].forEach(id => {
      const d = el(id);
      if (d) { d.style.background = color; d.style.boxShadow = `0 0 10px ${color}`; }
    });
    // highlight active swatch
    document.querySelectorAll('.psi-swatch').forEach((s, i) => {
      s.classList.toggle('active', i === modeNum - 1);
    });
  }
}

const teecesController = new TeecesController();

function teecesMode(mode)  { teecesController.setMode(mode); }
function sendTeecesText()  { teecesController.sendText(el('teeces-text').value.trim()); }

// ================================================================
// Servo Panel
// ================================================================

class ServoPanel {
  constructor(gridId, servos, apiPrefix) {
    this._gridId    = gridId;
    this._servos    = servos;
    this._apiPrefix = apiPrefix;  // e.g. '/servo/dome' or '/servo/body'
    this._state     = {};
    this._servos.forEach(n => this._state[n] = 'close');
    this.render();
  }

  render() {
    const grid = el(this._gridId);
    if (!grid) return;
    const varName = this._getVar();
    grid.innerHTML = this._servos.map(name => {
      const num      = name.split('_').pop();
      const panel    = (_servoCfg.panels || {})[name] || { open: 110, close: 20, speed: 10 };
      return `
        <div class="servo-row" id="servo-row-${name}">
          <span class="servo-name">P${num}</span>
          <div class="servo-calib-wrap">
            <label class="servo-calib-label">O<input type="number" id="sc-open-${name}"
              class="servo-angle-in" min="10" max="170" value="${panel.open}"></label>
            <label class="servo-calib-label">C<input type="number" id="sc-close-${name}"
              class="servo-angle-in" min="10" max="170" value="${panel.close}"></label>
            <label class="servo-calib-label">S<input type="number" id="sc-speed-${name}"
              class="servo-angle-in" min="1" max="10" value="${panel.speed ?? 10}"></label>
          </div>
          <button class="btn btn-xs" onclick="${varName}.open('${name}')">OPEN</button>
          <button class="btn btn-xs btn-dark" onclick="${varName}.close('${name}')">CLOSE</button>
        </div>
      `;
    }).join('');
  }

  updateInputs() {
    this._servos.forEach(name => {
      const panel = (_servoCfg.panels || {})[name];
      if (!panel) return;
      const oEl = el(`sc-open-${name}`);
      const cEl = el(`sc-close-${name}`);
      const sEl = el(`sc-speed-${name}`);
      if (oEl) oEl.value = panel.open;
      if (cEl) cEl.value = panel.close;
      if (sEl) sEl.value = panel.speed ?? 10;
    });
  }

  _getVar() {
    return this._apiPrefix.includes('dome') ? 'domeServoPanel' : 'bodyServoPanel';
  }

  open(name) {
    api(`${this._apiPrefix}/open`, 'POST', { name }).then(d => {
      if (d) { toast(`P${name.split('_').pop()}: OPEN`, 'ok'); this._setFill(name, 100); }
    });
    this._state[name] = 'open';
  }

  close(name) {
    api(`${this._apiPrefix}/close`, 'POST', { name }).then(d => {
      if (d) { toast(`P${name.split('_').pop()}: CLOSE`, 'ok'); this._setFill(name, 0); }
    });
    this._state[name] = 'close';
  }

  async saveAngles() {
    const panels = {};
    this._servos.forEach(name => {
      const oEl = el(`sc-open-${name}`);
      const cEl = el(`sc-close-${name}`);
      const sEl = el(`sc-speed-${name}`);
      if (oEl && cEl) {
        panels[name] = {
          open:  parseInt(oEl.value) || 110,
          close: parseInt(cEl.value) || 20,
          speed: parseInt(sEl?.value) || 10,
        };
      }
    });
    const data = await api('/servo/settings', 'POST', { panels });
    if (!data) { toast('Network error', 'error'); return; }
    _servoCfg = data;
    this.updateInputs();
    toast('Angles saved', 'ok');
  }

  _setFill(name, pct) {
    const f = el(`servo-fill-${name}`);
    if (f) f.style.width = pct + '%';
  }
}

// Servo calibration config (loaded from /servo/settings at init)
// Format : { ms_90deg: 150, panels: { dome_panel_1: { open: 70, close: 70, open_ms: 117, close_ms: 117 }, ... } }
let _servoCfg = { ms_90deg: 150, panels: {} };

async function loadServoSettings() {
  const data = await api('/servo/settings');
  if (!data) return;
  _servoCfg = data;
  if (el('servo-ms90')) el('servo-ms90').value = data.ms_90deg;
  updateServoDurationPreview();
  domeServoPanel.updateInputs();
  bodyServoPanel.updateInputs();
}

function updateServoDurationPreview() {
  const ms90 = parseInt(el('servo-ms90')?.value ?? _servoCfg.ms_90deg ?? 150);
  if (isNaN(ms90)) return;
  const dur  = Math.max(50, Math.round(70 / 90 * ms90));
  const prev = el('servo-duration-preview');
  if (prev) prev.textContent = `Example 70° = ${dur} ms`;
}

async function saveServoMs90() {
  const ms90 = parseInt(el('servo-ms90')?.value ?? 150);
  const data = await api('/servo/settings', 'POST', { ms_90deg: ms90, panels: {} });
  if (!data) { toast('Network error', 'error'); return; }
  _servoCfg = data;
  updateServoDurationPreview();
  domeServoPanel.updateInputs();
  bodyServoPanel.updateInputs();
  toast(`ms_90deg saved: ${ms90} ms`, 'ok');
}

async function testServoSettings(dir) {
  const endpoint = dir === 'open' ? '/servo/dome/open' : '/servo/dome/close';
  const data = await api(endpoint, 'POST', { name: 'dome_panel_1' });
  if (data) toast(`Test dome_panel_1 ${dir.toUpperCase()} — ${data.duration}ms`, 'ok');
}

const DOME_SERVOS = Array.from({length: 11}, (_, i) => `dome_panel_${i + 1}`);
const BODY_SERVOS = Array.from({length: 11}, (_, i) => `body_panel_${i + 1}`);

const domeServoPanel = new ServoPanel('dome-servo-list', DOME_SERVOS, '/servo/dome');
const bodyServoPanel = new ServoPanel('body-servo-list', BODY_SERVOS, '/servo/body');

// ================================================================
// Audio Board
// ================================================================

class AudioBoard {
  constructor() {
    this._currentCat = null;
    this._playing    = false;
    this._ICONS = {
      alarm:'🚨', happy:'😄', hum:'🎵', misc:'🎲', proc:'⚙️', quote:'💬',
      razz:'🤪', sad:'😢', sent:'🤔', ooh:'😲', whistle:'🎶', scream:'😱',
      special:'⭐', sent:'🗣️'
    };
    this._CAT_COLORS = {
      alarm:'#ff2244',  happy:'#ffcc00',  hum:'#00aaff',  misc:'#aa44ff',
      proc:'#00ffea',   quote:'#ff8800',  razz:'#ff44cc',  sad:'#4499ff',
      sent:'#00cc66',   ooh:'#ff6600',    whistle:'#44ffbb', scream:'#ff0055',
      special:'#ffaa00'
    };
    // Noms d'affichage propres pour chaque catégorie
    this._CAT_LABELS = {
      alarm:'Alarm',    happy:'Happy',    hum:'Hum',       misc:'Misc',
      proc:'Process',   quote:'Quote',    razz:'Razz',     sad:'Sad',
      sent:'Sentiment', ooh:'Ooh',        whistle:'Whistle', scream:'Scream',
      special:'Special'
    };
  }

  // Formate un nom de fichier pour l'affichage
  // "Happy001" → "001"  |  "Cantina" → "Cantina"
  _formatSound(filename) {
    const m = filename.match(/^[A-Za-z_]+?(\d+)$/);
    return m ? m[1].replace(/^0+/, '') || '1' : filename;
  }

  async loadCategories() {
    const data = await api('/audio/categories');
    if (!data || !data.categories) return;
    const wrap = el('audio-categories');
    if (!wrap) return;

    // Accepte les deux formats : [{name, count}] ou {name: count}
    const cats = Array.isArray(data.categories)
      ? data.categories
      : Object.entries(data.categories).map(([name, count]) => ({ name, count }));

    wrap.innerHTML = cats.map(({ name, count }) => {
      const color = this._CAT_COLORS[name] || '#00aaff';
      const label = this._CAT_LABELS[name] || name.charAt(0).toUpperCase() + name.slice(1);
      const icon  = this._ICONS[name] || '🔊';
      return `
        <div class="category-pill" id="cat-pill-${name}"
             onclick="audioBoard.selectCategory('${name}')"
             style="--cat-color:${color}">
          <span class="cat-icon">${icon}</span>
          <span class="cat-label">${label}</span>
          <span class="cat-count">${count}</span>
        </div>`;
    }).join('');

    // Sélectionner la première catégorie par défaut
    if (cats.length > 0) this.selectCategory(cats[0].name);
  }

  async selectCategory(cat) {
    this._currentCat = cat;

    // Marquer la pill active
    document.querySelectorAll('.category-pill').forEach(p => p.classList.remove('active'));
    const pill = el(`cat-pill-${cat}`);
    if (pill) {
      pill.classList.add('active');
      pill.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
    }

    // Mettre à jour le titre de la section sons
    const label = this._CAT_LABELS[cat] || cat.toUpperCase();
    const color = this._CAT_COLORS[cat] || '#00aaff';
    const nameEl = el('audio-cat-name');
    if (nameEl) {
      nameEl.textContent = label;
      nameEl.style.color  = color;
    }

    // Afficher le spinner pendant le chargement
    const grid = el('audio-sounds-grid');
    if (!grid) return;
    grid.innerHTML = '<div class="sounds-loading">Loading...</div>';

    const data = await api(`/audio/sounds?category=${cat}`);

    if (data && data.sounds && data.sounds.length > 0) {
      // Bouton RANDOM en premier
      const randomBtn = `
        <button class="sound-btn sound-btn-random"
                onclick="audioBoard.playRandom('${cat}')"
                title="Random sound from ${label}">
          🎲 RANDOM
        </button>`;

      const soundBtns = data.sounds.map(s => {
        const display = this._formatSound(s);
        return `<button class="sound-btn"
                  onclick="audioBoard.play('${escapeHtml(s)}')"
                  title="${escapeHtml(s)}">
                  ${escapeHtml(display)}
                </button>`;
      }).join('');

      grid.innerHTML = randomBtn + soundBtns;
    } else {
      grid.innerHTML = `
        <button class="sound-btn sound-btn-random" onclick="audioBoard.playRandom('${cat}')">
          🎲 RANDOM ${label}
        </button>`;
    }
  }

  play(sound) {
    api('/audio/play', 'POST', { sound }).then(d => {
      if (d && d.ok !== false) this.setPlaying(true, sound);
    });
  }

  playRandom(cat) {
    const c = cat || this._currentCat || 'happy';
    api('/audio/random', 'POST', { category: c }).then(d => {
      if (d) {
        const label = this._CAT_LABELS[c] || c;
        this.setPlaying(true, `🎲 ${label}`);
      }
    });
  }

  setPlaying(active, name = '') {
    this._playing = active;
    const waveform = el('waveform');
    const text     = el('now-playing-text');
    if (waveform) waveform.classList.toggle('playing', active);
    if (text) text.textContent = active ? name : 'IDLE';
  }
}

const audioBoard = new AudioBoard();

function audioStop() {
  api('/audio/stop', 'POST').then(d => {
    if (d) { audioBoard.setPlaying(false); toast('Audio stopped', 'ok'); }
  });
}

function audioRandom() {
  audioBoard.playRandom(null);
}

// ================================================================
// VESC Panel
// ================================================================

class VescPanel {
  constructor() {
    this._scaleDebounce = null;
  }

  // Called by StatusPoller on every refresh
  async refresh() {
    const d = await api('/vesc/telemetry');
    if (!d) return;
    this._updateStatus(d);
    this._updateCard('L', d.L);
    this._updateCard('R', d.R);
    this._updateScale(d.power_scale);
  }

  _updateStatus(d) {
    const pill  = el('vesc-conn-pill');
    const label = el('vesc-conn-label');
    if (!pill) return;
    if (d.connected) {
      pill.classList.add('online');
      label.textContent = 'ONLINE';
    } else {
      pill.classList.remove('online');
      label.textContent = 'OFFLINE';
    }
    // Battery voltage — use whichever side is available
    const src = d.L || d.R;
    const vEl  = el('vesc-voltage');
    const fill = el('vesc-battery-fill');
    if (src && vEl) {
      const v = src.v_in;
      vEl.textContent = v.toFixed(1);
      vEl.className = 'vesc-battery-value' + (v < 21 ? ' danger' : v < 22 ? ' warn' : '');
      // 6S LiPo: 19.2V empty → 25.2V full
      const pct = Math.max(0, Math.min(100, ((v - 19.2) / (25.2 - 19.2)) * 100));
      if (fill) {
        fill.style.width = pct + '%';
        fill.style.background = v < 21 ? '#ff4455' : v < 22 ? '#ffcc00' : '#00ff88';
      }
    } else if (vEl) {
      vEl.textContent = '--.-';
    }
  }

  _updateCard(side, data) {
    const s = side.toLowerCase();
    const fault = el(`v${s}-fault`);
    const card  = el(`vesc-card-${side}`);
    if (!data) {
      if (fault) { fault.textContent = 'OFFLINE'; fault.className = 'vesc-fault'; }
      if (card)  card.classList.remove('fault-active');
      ['temp','curr','rpm','duty'].forEach(k => {
        const e = el(`v${s}-${k}`);
        if (e) e.textContent = '--';
      });
      return;
    }
    // Metrics
    this._setMetric(`v${s}-temp`, data.temp.toFixed(1), data.temp > 80 ? 'danger' : data.temp > 60 ? 'hot' : '');
    this._setMetric(`v${s}-curr`, data.current.toFixed(1), '');
    this._setMetric(`v${s}-rpm`,  Math.abs(data.rpm), '');
    this._setMetric(`v${s}-duty`, Math.round(Math.abs(data.duty) * 100), '');
    // Fault
    if (fault) {
      const isFault = data.fault !== 0;
      fault.textContent = data.fault_str || 'NONE';
      fault.className = 'vesc-fault ' + (isFault ? 'error' : 'ok');
      if (card) card.classList.toggle('fault-active', isFault);
    }
  }

  _setMetric(id, val, cls) {
    const e = el(id);
    if (!e) return;
    e.textContent = val;
    e.className = 'vesc-metric-val' + (cls ? ' ' + cls : '');
  }

  _updateScale(scale) {
    const slider = el('vesc-scale-slider');
    const label  = el('vesc-scale-label');
    const info   = el('vesc-scale-pct');
    const pct = Math.round(scale * 100);
    if (slider && slider !== document.activeElement) slider.value = pct;
    if (label) label.textContent = pct + '%';
    if (info)  info.textContent  = pct;
  }

  initSlider() {
    const slider = el('vesc-scale-slider');
    const label  = el('vesc-scale-label');
    const info   = el('vesc-scale-pct');
    if (!slider) return;
    _updateSliderBg(slider);
    slider.addEventListener('input', () => {
      const pct = parseInt(slider.value, 10);
      if (label) label.textContent = pct + '%';
      if (info)  info.textContent  = pct;
      _updateSliderBg(slider);
      clearTimeout(this._scaleDebounce);
      this._scaleDebounce = setTimeout(() => {
        api('/vesc/config', 'POST', { scale: pct / 100 });
      }, 200);
    });
  }
}

const vescPanel = new VescPanel();

function vescInvert(side) {
  if (!confirm(`Invert ${side === 'L' ? 'LEFT' : 'RIGHT'} motor direction?`)) return;
  api('/vesc/invert', 'POST', { side }).then(d => {
    if (d) toast(`Motor ${side} direction inverted`, 'ok');
  });
}

function vescFocDetect(side) {
  if (!confirm(
    `⚡ FOC AUTODETECT — ${side === 'L' ? 'LEFT' : 'RIGHT'} motor\n\n` +
    `Motor must be FREE TO SPIN.\nDo NOT run this while R2-D2 is on the ground.\n\nContinue?`
  )) return;
  // FOC detect is done via VESC Tool directly — this just shows the reminder
  toast(`FOC Detect: connect via VESC Tool on /dev/ttyACM${side === 'L' ? '0' : '1'}`, 'info');
}

// ================================================================
// CAN Bus Wizard
// ================================================================

const canWizard = {
  _scanning: false,

  async scan() {
    if (this._scanning) return;
    this._scanning = true;

    const btn    = el('can-scan-btn');
    const result = el('can-scan-result');
    if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spin">⟳</span> SCANNING…'; }
    if (result) { result.textContent = ''; result.className = 'vesc-can-result'; }

    const d = await api('/vesc/can/scan');
    this._scanning = false;
    if (btn) { btn.disabled = false; btn.innerHTML = 'SCAN CAN BUS'; }

    if (!d || d.error) {
      const msg = (d && d.error) ? d.error : 'Connection failed';
      if (result) {
        result.innerHTML = `<span class="can-err">⚠ ${escapeHtml(msg)}</span>`;
        result.className = 'vesc-can-result show';
      }
      toast('CAN scan failed', 'warn');
      return;
    }
    this._displayResult(d.ids || []);
  },

  _displayResult(ids) {
    const result = el('can-scan-result');
    if (!result) return;

    let html = `<div class="can-found-header">FOUND ${ids.length} VESC${ids.length !== 1 ? 'S' : ''} ON CAN BUS</div>`;

    if (ids.length === 0) {
      html += `<p class="can-info">No VESCs found on CAN bus.<br>Check CAN H/L wiring between VESCs and ensure VESC 1 is connected via USB (/dev/ttyACM0).</p>`;
    } else {
      html += `<div class="can-id-list">`;
      ids.forEach(id => { html += `<span class="can-id-badge">CAN ID ${id}</span>`; });
      html += `</div>`;
      if (ids.length === 1) {
        html += `<p class="can-info">✓ VESC 2 found (CAN ID ${ids[0]}). VESC 1 (USB) is the gateway.</p>`;
      } else if (ids.filter(i => i === 0).length > 0 && ids.length > 1) {
        html += `<p class="can-warn">⚠ Multiple VESCs share CAN ID 0. Assign unique IDs via VESC Tool before operating.</p>`;
      } else {
        html += `<p class="can-info">✓ ${ids.length} VESCs found on CAN bus (IDs: ${ids.join(', ')}).</p>`;
      }
    }
    result.innerHTML = html;
    result.className = 'vesc-can-result show';
    toast(`CAN scan: ${ids.length} VESC${ids.length !== 1 ? 's' : ''} found`, ids.length > 0 ? 'ok' : 'warn');
  },
};

// ================================================================
// Script Engine
// ================================================================

class ScriptEngine {
  constructor() {
    this._scripts = [];
    this._running = new Set();
    this._DESCRIPTIONS = {
      patrol:    'R2-D2 patrols with sounds + dome movement',
      celebrate: 'Victory celebration with lights and sounds',
      cantina:   'Cantina dance routine with audio',
      leia:      'Help me Obi-Wan... holographic message',
    };
  }

  async load() {
    const data = await api('/scripts/list');
    if (!data || !data.scripts) return;
    this._scripts = data.scripts;
    this.render();
  }

  render() {
    const grid = el('script-list');
    if (!grid) return;
    grid.innerHTML = this._scripts.map(entry => {
      const name = (typeof entry === 'object' && entry !== null) ? entry.name : entry;
      const desc = this._DESCRIPTIONS[name] || 'Custom sequence script';
      const isRunning = this._running.has(name);
      return `
        <div class="script-card${isRunning ? ' running' : ''}" id="script-card-${name}">
          <div class="script-name">${name.toUpperCase()}</div>
          <div class="script-desc">${desc}</div>
          <div class="script-btns">
            <div class="running-indicator"></div>
            <button class="btn btn-sm btn-active" onclick="scriptEngine.run('${name}', false)">RUN</button>
            <button class="btn btn-sm" onclick="scriptEngine.run('${name}', true)">LOOP</button>
            <button class="btn btn-sm btn-danger" onclick="scriptEngine.stopName('${name}')">STOP</button>
          </div>
        </div>
      `;
    }).join('');
  }

  run(name, loop) {
    api('/scripts/run', 'POST', { name, loop }).then(d => {
      if (d) {
        // Un seul script à la fois — effacer toutes les cartes immédiatement
        this._running.clear();
        document.querySelectorAll('.script-card').forEach(c => c.classList.remove('running'));
        const count = el('running-count');
        if (count) count.textContent = '1';
        const list = el('running-scripts');
        if (list) list.textContent = `${name}#${d.id}`;
        // Marquer uniquement la nouvelle carte
        this._running.add(name);
        const card = el(`script-card-${name}`);
        if (card) card.classList.add('running');
        toast(`${name.toUpperCase()} started${loop ? ' (loop)' : ''}`, 'ok');
        poller.poll();
      }
    });
  }

  stopName(name) {
    // We'd need the script ID — stop_all as fallback
    api('/scripts/stop_all', 'POST').then(d => {
      if (d) {
        this._running.clear();
        document.querySelectorAll('.script-card').forEach(c => c.classList.remove('running'));
        const count = el('running-count');
        if (count) count.textContent = '0';
        const list = el('running-scripts');
        if (list) list.textContent = '—';
        toast('Sequences stopped', 'ok');
      }
    });
  }

  stopAll() {
    api('/scripts/stop_all', 'POST').then(d => {
      if (d) {
        this._running.clear();
        document.querySelectorAll('.script-card').forEach(c => c.classList.remove('running'));
        const count = el('running-count');
        if (count) count.textContent = '0';
        const list = el('running-scripts');
        if (list) list.textContent = '—';
        toast('Sequences stopped', 'ok');
      }
    });
  }

  updateRunning(running) {
    const names = new Set(running.map(s => s.name));
    this._running = names;

    document.querySelectorAll('.script-card').forEach(card => {
      const name = card.id.replace('script-card-', '');
      card.classList.toggle('running', names.has(name));
    });

    const count = el('running-count');
    if (count) count.textContent = names.size;

    const list = el('running-scripts');
    if (list) {
      list.textContent = running.length
        ? running.map(s => `${s.name}#${s.id}`).join(', ')
        : '—';
    }
  }
}

const scriptEngine = new ScriptEngine();

async function loadScripts() { await scriptEngine.load(); }

// ================================================================
// BT Controller
// ================================================================

class BTController {
  constructor() {
    this._connected   = false;
    this._gamepadIdx  = null;
    this._prevBtns    = {};
    this._driveActive = false;
    this._domeActive  = false;
    this._lastDriveMs = 0;
    this._lastDomeMs  = 0;
    this._DRIVE_HZ    = 1000 / 30;   // 30 req/s
    this._DOME_HZ     = 1000 / 20;   // 20 req/s
    this._loadMappings();
    this._bind();
  }

  _bind() {
    window.addEventListener('gamepadconnected',    e => this._onConnect(e.gamepad));
    window.addEventListener('gamepaddisconnected', e => this._onDisconnect(e.gamepad));
    const poll = () => { this._tick(); requestAnimationFrame(poll); };
    requestAnimationFrame(poll);
  }

  _onConnect(gp) {
    this._gamepadIdx = gp.index;
    this._connected  = true;
    this._prevBtns   = {};
    this._setUI(true, gp.id.split('(')[0].trim().slice(0, 24));
    toast('BT controller connected', 'ok');
  }

  _onDisconnect(gp) {
    if (gp.index !== this._gamepadIdx) return;
    this._gamepadIdx  = null;
    this._connected   = false;
    this._driveActive = false;
    this._domeActive  = false;
    this._setUI(false, '—');
    api('/motion/stop',      'POST');
    api('/motion/dome/stop', 'POST');
    jsLeft.setExternal(0, 0);    // reset knobs visuels
    jsRight.setExternal(0, 0);
    toast('BT controller disconnected', 'error');
  }

  _tick() {
    const pads = navigator.getGamepads ? navigator.getGamepads() : [];

    // Auto-détection si pas encore associée
    if (this._gamepadIdx === null) {
      for (let i = 0; i < pads.length; i++) {
        if (pads[i]) { this._onConnect(pads[i]); break; }
      }
    }
    if (this._gamepadIdx === null) return;

    const gp = pads[this._gamepadIdx];
    if (!gp) {
      if (this._connected) this._onDisconnect({ index: this._gamepadIdx });
      return;
    }

    const m   = this._getMappings();
    const dz  = (parseInt(m.deadzone) || 8) / 100;
    const now = performance.now();

    // ── PROPULSION — bloquée en Child Lock (mode 2) ────────────────
    const tRaw = -this._axis(gp, m.throttle || 'L_STICK_Y');
    const sRaw =  this._axis(gp, m.steer    || 'L_STICK_X');
    const t    = Math.abs(tRaw) > dz ? tRaw * _speedLimit : 0;
    const s    = Math.abs(sRaw) > dz ? sRaw * _speedLimit * 0.55 : 0;

    // Sync visuel joystick gauche — toujours, même en Child Lock
    jsLeft.setExternal(Math.abs(sRaw) > dz ? sRaw : 0,
                       Math.abs(tRaw) > dz ? -tRaw : 0);

    if (!lockMgr.isDriveLocked()) {
      if (now - this._lastDriveMs >= this._DRIVE_HZ) {
        this._lastDriveMs = now;
        if (Math.abs(t) > 0.01 || Math.abs(s) > 0.01) {
          api('/motion/arcade', 'POST', { throttle: t, steering: s });
          this._driveActive = true;
        } else if (this._driveActive) {
          api('/motion/stop', 'POST');
          this._driveActive = false;
        }
      }
    } else if (this._driveActive) {
      // Child Lock activé en cours de conduite → arrêt immédiat
      api('/motion/stop', 'POST');
      this._driveActive = false;
    }

    // ── DÔME ──────────────────────────────────────────────────────
    const dRaw = this._axis(gp, m.dome || 'R_STICK_X');

    // Sync visuel joystick droit
    jsRight.setExternal(Math.abs(dRaw) > dz ? dRaw : 0, 0);

    if (now - this._lastDomeMs >= this._DOME_HZ) {
      this._lastDomeMs = now;
      if (Math.abs(dRaw) > dz) {
        api('/motion/dome/turn', 'POST', { speed: dRaw * 0.85 });
        this._domeActive = true;
      } else if (this._domeActive) {
        api('/motion/dome/stop', 'POST');
        this._domeActive = false;
      }
    }

    // ── BOUTONS — détection de front montant/descendant ───────────
    const prev = this._prevBtns;

    // Panneau dôme : ouvert tant qu'appuyé
    const p1 = m.panel1 || 'SQUARE';
    const p1v = this._btn(gp, p1);
    if (p1v && !prev[p1])  api('/servo/dome/open_all',  'POST');
    if (!p1v && prev[p1])  api('/servo/dome/close_all', 'POST');
    prev[p1] = p1v;

    // Panneau body : ouvert tant qu'appuyé
    const p2 = m.panel2 || 'TRIANGLE';
    const p2v = this._btn(gp, p2);
    if (p2v && !prev[p2])  api('/servo/body/open_all',  'POST');
    if (!p2v && prev[p2])  api('/servo/body/close_all', 'POST');
    prev[p2] = p2v;

    // Son aléatoire — front montant seulement
    const au = m.audio || 'CIRCLE';
    const auv = this._btn(gp, au);
    if (auv && !prev[au])  api('/audio/random', 'POST', { category: 'happy' });
    prev[au] = auv;
  }

  // Lecture d'axe — retourne -1..1
  _axis(gp, name) {
    const axisMap = { L_STICK_X: 0, L_STICK_Y: 1, R_STICK_X: 2, R_STICK_Y: 3 };
    if (name in axisMap) return gp.axes[axisMap[name]] || 0;
    const btnMap  = { L2: 6, R2: 7 };
    if (name in btnMap) { const b = gp.buttons[btnMap[name]]; return b ? b.value : 0; }
    return 0;
  }

  // Lecture bouton — retourne bool
  _btn(gp, name) {
    const map = {
      CROSS: 0, CIRCLE: 1, SQUARE: 2, TRIANGLE: 3,
      L1: 4, R1: 5, L2: 6, R2: 7, SELECT: 8, START: 9,
      L3: 10, R3: 11, DPAD_UP: 12, DPAD_DOWN: 13, DPAD_LEFT: 14, DPAD_RIGHT: 15,
    };
    const idx = map[name];
    return (idx !== undefined && gp.buttons[idx]) ? gp.buttons[idx].pressed : false;
  }

  // ── UI ─────────────────────────────────────────────────────────
  _setUI(connected, name) {
    const icon       = document.querySelector('.gamepad-icon');
    const statusText = el('bt-status-text');
    const deviceName = el('bt-device-name');
    if (icon)       icon.classList.toggle('connected', connected);
    if (statusText) { statusText.textContent = connected ? 'CONNECTED' : 'NOT CONNECTED'; statusText.classList.toggle('connected', connected); }
    if (deviceName) deviceName.textContent = name || '—';
    this._updatePill();
  }

  _updatePill() {
    const pill  = el('pill-bt');
    const label = el('pill-bt-label');
    if (!pill) return;
    const enabled   = this._piEnabled;
    const connected = this._piConnected || this._connected;
    let cls, txt;
    if (!enabled) {
      cls = 'status-pill error'; txt = 'BT OFF';
    } else if (connected) {
      cls = 'status-pill ok';   txt = 'BT';
    } else {
      cls = 'status-pill';      txt = 'BT';
    }
    pill.className = cls;
    if (label) label.textContent = txt;
  }

  // Appelé par le poller status — intègre statut Pi BT + Gamepad API
  updateStatus(data) {
    if (!data) return;
    this._piConnected = data.bt_connected || false;
    this._piEnabled   = data.bt_enabled !== false;  // défaut true si absent

    // Sync toggle UI
    const tog = el('bt-enable-toggle');
    if (tog) tog.checked = this._piEnabled;

    // Sync nom depuis Pi si manette Pi connectée
    if (this._piConnected) {
      const deviceName = el('bt-device-name');
      if (deviceName && data.bt_name && data.bt_name !== '—') deviceName.textContent = data.bt_name;
      const statusText = el('bt-status-text');
      if (statusText) { statusText.textContent = 'CONNECTED (Pi)'; statusText.classList.add('connected'); }
    }

    // Batterie
    const pct = data.bt_battery || 0;
    if (pct > 0) {
      const fillEl = el('bt-battery-fill');
      const pctEl  = el('bt-battery-pct');
      const bcolor = pct > 50 ? '#00cc66' : pct > 25 ? '#ff8800' : '#ff2244';
      if (fillEl) { fillEl.style.width = pct + '%'; fillEl.style.background = bcolor; }
      if (pctEl)  pctEl.textContent = pct + '%';
    }

    this._updatePill();
  }

  // Appelé par le toggle ON/OFF
  async setEnabled(enabled) {
    this._piEnabled = enabled;
    this._updatePill();
    await api('/bt/enable', 'POST', { enabled });
    toast(enabled ? 'BT controller enabled' : 'BT controller disabled', 'ok');
  }

  // Appelé au changement de type de manette
  onTypeChange(type) {
    // Mettre à jour les labels du tableau de mapping selon le type
    const labels = {
      ps:        { WEST: '□ Square',   NORTH: '△ Triangle', EAST: '○ Circle', SOUTH: '✕ Cross', TL: 'L1',  TR: 'R1',  MODE: 'PS'      },
      xbox:      { WEST: 'X',          NORTH: 'Y',          EAST: 'B',        SOUTH: 'A',       TL: 'LB',  TR: 'RB',  MODE: 'Xbox'    },
      nintendo:  { WEST: 'Y',          NORTH: 'X',          EAST: 'A',        SOUTH: 'B',       TL: 'L',   TR: 'R',   MODE: 'Home'    },
      generic:   { WEST: 'Btn 3',      NORTH: 'Btn 4',      EAST: 'Btn 2',    SOUTH: 'Btn 1',   TL: 'L1',  TR: 'R1',  MODE: 'Home'    },
    };
    const l = labels[type] || labels.generic;
    const setOpt = (id, val, text) => {
      const e = el(id); if (!e) return;
      for (const o of e.options) {
        if (o.value === val) { o.text = text; break; }
      }
    };
    setOpt('bt-map-panel1', 'BTN_WEST',   l.WEST);
    setOpt('bt-map-panel2', 'BTN_NORTH',  l.NORTH);
    setOpt('bt-map-audio',  'BTN_EAST',   l.EAST);
    setOpt('bt-map-estop',  'BTN_MODE',   l.MODE);
  }

  // Charge la config depuis le serveur et sync l'UI
  async loadConfig() {
    const data = await api('/bt/status');
    if (!data) return;
    this.updateStatus(data);
    // type
    const typeEl = el('bt-gamepad-type');
    if (typeEl && data.bt_gamepad_type) {
      for (const o of typeEl.options) if (o.value === data.bt_gamepad_type) { o.selected = true; break; }
      this.onTypeChange(data.bt_gamepad_type);
    }
  }

  // Sauvegarde config complète sur le serveur
  async saveFullConfig() {
    const mappings = {
      throttle:   el('bt-map-throttle')?.value         || 'ABS_Y',
      steer:      el('bt-map-steer')?.value            || 'ABS_X',
      dome:       el('bt-map-dome')?.value             || 'ABS_RX',
      panel_dome: el('bt-map-panel1')?.value           || 'BTN_WEST',
      panel_body: el('bt-map-panel2')?.value           || 'BTN_NORTH',
      audio:      el('bt-map-audio')?.value            || 'BTN_EAST',
      estop:      el('bt-map-estop')?.value            || 'BTN_MODE',
    };
    const cfg = {
      gamepad_type:       el('bt-gamepad-type')?.value          || 'ps',
      deadzone:           (parseInt(el('bt-deadzone')?.value)    || 10) / 100,
      inactivity_timeout: parseInt(el('bt-inactivity-timeout')?.value) || 30,
      mappings,
    };
    // Aussi sauvegarder localement pour la Gamepad API JS
    localStorage.setItem('r2d2-bt-mappings', JSON.stringify({
      throttle: 'L_STICK_Y', steer: 'L_STICK_X', dome: 'R_STICK_X',
      panel1: 'SQUARE', panel2: 'TRIANGLE', audio: 'CIRCLE',
      deadzone: el('bt-deadzone')?.value || '10',
    }));
    const r = await api('/bt/config', 'POST', cfg);
    toast(r?.status === 'ok' ? 'BT config saved' : 'Save error', r?.status === 'ok' ? 'ok' : 'error');
  }

  _getMappings() {
    try { const s = localStorage.getItem('r2d2-bt-mappings'); return s ? JSON.parse(s) : {}; }
    catch { return {}; }
  }

  _loadMappings() {
    try {
      const m = this._getMappings();
      const sel = (id, val) => { const e = el(id); if (e && val) { for (const o of e.options) if (o.value === val) { o.selected = true; break; } } };
      sel('bt-map-throttle', m.throttle);
      sel('bt-map-steer',    m.steer);
      sel('bt-map-dome',     m.dome);
      const dz = el('bt-deadzone');
      if (dz && m.deadzone) { dz.value = m.deadzone; const dzv = el('bt-deadzone-val'); if (dzv) dzv.textContent = m.deadzone + '%'; }
    } catch { /* ignore */ }
  }

  saveMappings() { this.saveFullConfig(); }
}

const btController = new BTController();
btController._piEnabled   = true;
btController._piConnected = false;
function saveBTConfig() { btController.saveFullConfig(); }

// ================================================================
// BT Pairing UI
// ================================================================
const btPairing = {
  _scanTimer: null,
  _pollTimer: null,

  startScan() {
    api('/bt/scan/start', 'POST').then(r => {
      if (!r) return;
      el('bt-scan-btn').disabled = true;
      el('bt-scan-label').textContent = '⏳ SCANNING...';
      el('bt-scan-status').textContent = 'Scan active — 15 seconds...';
      // Countdown
      let remaining = 15;
      this._scanTimer = setInterval(() => {
        remaining--;
        el('bt-scan-status').textContent = `Scan active — ${remaining}s remaining...`;
        if (remaining <= 0) {
          clearInterval(this._scanTimer);
          el('bt-scan-btn').disabled = false;
          el('bt-scan-label').innerHTML = '&#x1F50D; SCAN (15s)';
          el('bt-scan-status').textContent = 'Scan complete.';
        }
      }, 1000);
      // Poll devices toutes les 2s pendant le scan
      this._pollTimer = setInterval(() => this.refresh(), 2000);
      setTimeout(() => { clearInterval(this._pollTimer); this.refresh(); }, 16000);
    });
  },

  refresh() {
    api('/bt/scan/devices').then(r => {
      if (!r) return;
      this._renderDiscovered(r.discovered || []);
      this._renderPaired(r.paired || []);
    });
  },

  _renderDiscovered(list) {
    const el2 = el('bt-discovered-list');
    if (!list.length) {
      el2.innerHTML = '<div style="color:var(--txt-dim);font-size:11px">— No devices detected —</div>';
      return;
    }
    el2.innerHTML = list.map(d => `
      <div class="bt-pair-row">
        <span class="bt-pair-name">${d.name}</span>
        <span class="bt-pair-addr">${d.address}</span>
        <button class="btn btn-active btn-xs" onclick="btPairing.pair('${d.address}','${d.name.replace(/'/g,'&apos;')}')">PAIR</button>
      </div>`).join('');
  },

  _renderPaired(list) {
    const el2 = el('bt-paired-list');
    if (!list.length) {
      el2.innerHTML = '<div style="color:var(--txt-dim);font-size:11px">— No paired controller —</div>';
      return;
    }
    el2.innerHTML = list.map(d => `
      <div class="bt-pair-row">
        <span class="bt-pair-name">${d.name}</span>
        <span class="bt-pair-addr">${d.address}</span>
        <button class="btn btn-xs" onclick="btPairing.unpair('${d.address}')">REMOVE</button>
      </div>`).join('');
  },

  pair(address, name) {
    el('bt-scan-status').textContent = `Pairing with ${name}...`;
    api('/bt/pair', 'POST', { address }).then(() => {
      toast(`Pairing ${name} in progress...`, 'ok');
      setTimeout(() => this.refresh(), 5000);
    });
  },

  unpair(address) {
    api('/bt/unpair', 'POST', { address }).then(r => {
      if (r && r.status === 'ok') { toast('Device removed', 'ok'); this.refresh(); }
      else toast('Remove error', 'error');
    });
  },
};

// Charger les appareils jumelés au démarrage
window.addEventListener('DOMContentLoaded', () => setTimeout(() => btPairing.refresh(), 1500));

let _currentSpeedMode = 'normal';
function setSpeedMode(mode) {
  _currentSpeedMode = mode;
  document.querySelectorAll('.speed-mode-btn').forEach(b => {
    b.classList.toggle('btn-active', b.dataset.mode === mode);
  });
  const limits = { slow: 30, normal: 60, fast: 100 };
  const val = limits[mode] || 60;
  const slider = el('speed-slider');
  if (slider) { slider.value = val; setSpeed(val); }
  toast(`Speed mode: ${mode.toUpperCase()}`, 'ok');
}

// ================================================================
// Status Poller
// ================================================================

class StatusPoller {
  constructor() {
    this._interval = null;
  }

  start(intervalMs = 2000) {
    this.poll();
    this._interval = setInterval(() => this.poll(), intervalMs);
  }

  async poll() {
    const data = await api('/status');
    if (!data) {
      this._setOffline(true);
      return;
    }
    this._setOffline(false);

    this._setPill('pill-heartbeat', data.heartbeat_ok, 'HB');
    this._setUartPill(data.uart_ready, data.uart_health, data.uart_crc_errors ?? 0);

    const version = el('pill-version');
    if (version) version.textContent = 'v' + (data.version || '?');

    const uptime = el('uptime-label');
    if (uptime) uptime.textContent = 'up ' + (data.uptime || '--');

    const sysver = el('system-version');
    if (sysver) sysver.textContent =
      `Master: v${data.version || '?'}  |  Uptime: ${data.uptime || '--'}`;

    // Battery gauge
    if (data.battery_voltage) batteryGauge.update(data.battery_voltage);

    // Temperature
    if (data.temperature != null) {
      const temp = data.temperature;
      const tempLabel = el('temp-label');
      if (tempLabel) tempLabel.textContent = temp + '°C';
      const tempDrive = el('temp-val-drive');
      if (tempDrive) tempDrive.textContent = temp + '°C';
      const fill = el('temp-bar-fill');
      if (fill) {
        const pct = Math.min(100, temp);
        fill.style.height = pct + '%';
        fill.style.background = temp < 60 ? '#00cc66' : temp < 75 ? '#ff8800' : '#ff2244';
      }
      const tempHeader = el('temp-label');
      if (tempHeader) {
        tempHeader.textContent = temp + '°C';
        tempHeader.style.color = temp < 60 ? '#00cc66' : temp < 75 ? '#ff8800' : '#ff2244';
      }
    }

    // BT controller status
    btController.updateStatus(data);

    // Audio state
    if (data.audio_playing !== undefined) {
      audioBoard.setPlaying(data.audio_playing, data.audio_current || '');
    }

    // Scripts running
    if (data.scripts_running) {
      scriptEngine.updateRunning(data.scripts_running);
    }

    // Lock mode — sync si reconnexion ou autre client
    if (data.lock_mode !== undefined) {
      lockMgr.syncFromStatus(data.lock_mode);
    }

    // Teeces state
    if (data.teeces_mode) {
      teecesController._applyFLDMode(data.teeces_mode);
    }

    // VESC telemetry — refresh only if VESC tab is active
    if (el('tab-vesc') && el('tab-vesc').classList.contains('active')) {
      vescPanel.refresh();
    }
  }

  _setOffline(offline) {
    const wasOffline = this._offline;
    this._offline = offline;
    const pillOffline = el('pill-offline');
    if (pillOffline) pillOffline.style.display = offline ? '' : 'none';
    ['pill-heartbeat', 'pill-uart', 'pill-bt', 'pill-version'].forEach(id => {
      const p = el(id);
      if (p) p.style.display = offline ? 'none' : '';
    });
    // Reload data when coming back online
    if (wasOffline && !offline) {
      audioBoard.loadCategories();
      scriptEngine.load();
      loadServoSettings();
    }
  }

  _setUartPill(uartReady, health, masterCrcErrors) {
    const p = el('pill-uart');
    if (!p) return;
    const dot = p.querySelector('.pulse-dot');
    let cls, label, tooltip;

    if (!uartReady) {
      // Port série pas ouvert — erreur niveau OS
      cls     = 'status-pill error';
      label   = 'UART';
      tooltip = 'Serial port not open';
    } else if (health == null) {
      // Port ouvert mais Slave pas encore pollé / injoignable
      cls     = masterCrcErrors > 0 ? 'status-pill warn' : 'status-pill ok';
      label   = masterCrcErrors > 0 ? 'UART ERR' : 'UART';
      tooltip = masterCrcErrors > 0
        ? `Slave unreachable | Master invalid CRC: ${masterCrcErrors}`
        : 'Slave not yet polled';
    } else {
      // Port ouvert + données qualité disponibles — 3 niveaux
      const pct = health.health_pct;
      if      (pct >= 95) cls = 'status-pill ok';
      else if (pct >= 70) cls = 'status-pill warn';
      else                cls = 'status-pill error';
      label   = 'UART ' + pct.toFixed(0) + '%';
      tooltip = `${health.errors} errors / ${health.total} msg (${health.window_s}s)`
              + (masterCrcErrors > 0 ? ` | Master invalid CRC: ${masterCrcErrors}` : '');
    }

    p.className = cls;
    p.title     = tooltip;
    if (dot) {
      for (const node of p.childNodes) {
        if (node.nodeType === Node.TEXT_NODE) node.textContent = label;
      }
    } else {
      p.textContent = label;
    }
  }

  _setPill(id, ok, label) {
    const p = el(id);
    if (!p) return;
    const dot = p.querySelector('.pulse-dot');
    const cls = 'status-pill ' + (ok ? 'ok' : 'error');
    p.className = cls;
    // label text node — update the text without removing the dot
    if (dot) {
      // Only update text nodes
      for (const node of p.childNodes) {
        if (node.nodeType === Node.TEXT_NODE) {
          node.textContent = label;
        }
      }
    } else {
      p.textContent = label;
    }
  }
}

const poller = new StatusPoller();

// Called by MainActivity.kt (Android) when R2D2_API_BASE is updated
// and the server becomes reachable — reloads all dynamic data
function pollStatus() {
  audioBoard.loadCategories();
  scriptEngine.load();
  loadServoSettings();
  poller.poll();
}

// ================================================================
// Clock
// ================================================================

function updateClock() {
  const c = el('clock-label');
  if (!c) return;
  const now = new Date();
  const h = String(now.getHours()).padStart(2, '0');
  const m = String(now.getMinutes()).padStart(2, '0');
  const s = String(now.getSeconds()).padStart(2, '0');
  c.textContent = `${h}:${m}:${s}`;
}

// ================================================================
// Settings
// ================================================================

async function loadSettings() {
  const data = await api('/settings');
  if (!data) return;

  if (data.wifi) {
    const ssid = el('wifi-ssid');
    if (ssid) ssid.value = data.wifi.ssid || '';
    const status = el('wifi-status');
    if (status) {
      if (data.wifi.connected) {
        status.textContent = `Connected | SSID: ${data.wifi.ssid || data.wifi.connection} | IP: ${data.wifi.ip}`;
        status.className = 'settings-status ok';
      } else {
        status.textContent = 'Not connected — wlan1 absent or Master hotspot not available';
        status.className = 'settings-status error';
      }
    }
  }

  if (data.hotspot) {
    const ssid = el('hotspot-ssid');
    if (ssid) ssid.value = data.hotspot.ssid || '';
    const status = el('hotspot-status');
    if (status) {
      status.textContent = data.hotspot.active
        ? `Active | SSID: ${data.hotspot.ssid} | IP: ${data.hotspot.ip}`
        : 'Hotspot inactive';
      status.className = 'settings-status ' + (data.hotspot.active ? 'ok' : 'error');
    }
  }

  if (data.github) {
    const branch = el('git-branch');
    if (branch) branch.value = data.github.branch || 'main';
    const autoPull = el('auto-pull');
    if (autoPull) autoPull.checked = data.github.auto_pull_on_boot;
  }

  if (data.slave) {
    const host = el('slave-host');
    if (host) host.value = data.slave.host || 'r2-slave.local';
  }
}

async function scanWifi() {
  const btn = el('btn-scan');
  if (btn) { btn.textContent = 'SCANNING...'; btn.disabled = true; }
  const data = await api('/settings/wifi/scan');
  if (btn) { btn.textContent = 'SCAN'; btn.disabled = false; }

  const sel = el('wifi-scan-list');
  if (!sel) return;

  if (!data || !data.networks || data.networks.length === 0) {
    sel.innerHTML = '<option value="">No networks found</option>';
    toast('No networks detected on wlan1', 'warn');
    return;
  }

  sel.innerHTML = '<option value="">— Select network —</option>' +
    data.networks.map(n => {
      const bars = n.signal >= 75 ? '++++ ' : n.signal >= 50 ? '+++  ' : n.signal >= 25 ? '++   ' : '+    ';
      const sec  = n.security ? ' [WPA]' : '';
      return `<option value="${escapeHtml(n.ssid)}">${bars}${escapeHtml(n.ssid)}${sec} (${n.signal}%)</option>`;
    }).join('');
}

function onScanSelect(ssid) {
  if (ssid) { const f = el('wifi-ssid'); if (f) f.value = ssid; }
}

async function applyWifi() {
  const ssid     = (el('wifi-ssid')?.value || '').trim();
  const password = el('wifi-password')?.value || '';
  if (!ssid) { toast('SSID required', 'error'); return; }
  toast('Connecting...', 'info');
  const data = await api('/settings/wifi', 'POST', { ssid, password });
  if (!data)       { toast('Network error', 'error'); return; }
  if (data.error)  { toast(data.error, 'error'); return; }
  toast(data.message || (data.connected ? 'wlan1 connected' : 'Config saved'), data.connected ? 'ok' : 'warn');
  await loadSettings();
}

async function applyHotspot() {
  const ssid     = (el('hotspot-ssid')?.value || '').trim();
  const password = el('hotspot-password')?.value || '';
  if (!ssid) { toast('SSID required', 'error'); return; }
  if (password && password.length < 8) { toast('Password: minimum 8 characters', 'error'); return; }
  if (!confirm(`Apply hotspot SSID "${ssid}"? Clients will be disconnected.`)) return;
  toast('Applying hotspot...', 'info');
  const data = await api('/settings/hotspot', 'POST', { ssid, password });
  if (!data)      { toast('Network error', 'error'); return; }
  if (data.error) { toast(data.error, 'error'); return; }
  toast('Hotspot updated', 'ok');
  const pw = el('hotspot-password');
  if (pw) pw.value = '';
  await loadSettings();
}

async function saveConfig() {
  if (!confirm('Save config? (git branch, slave host — restart required to take effect)')) return;
  const payload = {
    'github.branch':            (el('git-branch')?.value || '').trim(),
    'github.auto_pull_on_boot': el('auto-pull')?.checked ? 'true' : 'false',
    'slave.host':               (el('slave-host')?.value || '').trim(),
  };
  const data = await api('/settings/config', 'POST', payload);
  if (data && data.status === 'ok') {
    toast('Config saved', 'ok');
  } else {
    toast('Error saving config', 'error');
  }
}

function confirmAction(msg, endpoint) {
  if (confirm(msg)) {
    api(endpoint, 'POST').then(d => {
      if (d) toast('Command sent', 'ok');
    });
  }
}

async function systemUpdate() {
  if (!confirm('Force update?\n\ngit pull + rsync Slave + reboot Slave')) return;
  toast('Update started…', 'info');
  const d = await api('/system/update', 'POST');
  if (d) toast('Update in progress — Slave will reboot', 'ok');
}

// ================================================================
// Volume slider
// ================================================================

// ALSA bcm2835 maps 0-100% linearly onto ~-102dB..+4dB,
// so 50% ALSA ≈ -49dB (nearly inaudible).
// Square-root curve makes slider 50% → ALSA 71% (≈-28dB, usable).
function _sliderToAlsa(v) { return Math.round(Math.pow(v / 100, 1 / 3) * 100); }
function _alsaToSlider(v) { return Math.round(Math.pow(v / 100, 3) * 100); }

function initVolume() {
  const slider = document.getElementById('volume-slider');
  const label  = document.getElementById('volume-label');
  if (!slider) return;

  // Load current ALSA volume → convert back to slider position
  api('/audio/volume').then(d => {
    if (d && d.volume !== undefined) {
      slider.value = _alsaToSlider(d.volume);
      label.textContent = slider.value + '%';
      _updateSliderBg(slider);
    }
  });

  let _debounceTimer = null;

  slider.addEventListener('input', () => {
    const sliderVal = parseInt(slider.value, 10);
    label.textContent = sliderVal + '%';
    _updateSliderBg(slider);
    clearTimeout(_debounceTimer);
    _debounceTimer = setTimeout(() => {
      api('/audio/volume', 'POST', { volume: _sliderToAlsa(sliderVal) }).catch(() => {});
    }, 150);
  });
}

function _updateSliderBg(slider) {
  const pct = ((slider.value - slider.min) / (slider.max - slider.min)) * 100;
  slider.style.background = `linear-gradient(to right, var(--blue) ${pct}%, var(--border) ${pct}%)`;
}

// ================================================================
// Audio helpers exposed globally
// ================================================================

async function loadAudioCategories() {
  await audioBoard.loadCategories();
}

// ================================================================
// Init
// ================================================================

// ================================================================
// App Heartbeat — alimente l'AppWatchdog côté Master
// ================================================================

function startAppHeartbeat() {
  const base = () => (typeof window.R2D2_API_BASE === 'string' && window.R2D2_API_BASE) ? window.R2D2_API_BASE : '';

  // Envoi POST /heartbeat toutes les 200ms tant que la page est active
  setInterval(() => {
    fetch(base() + '/heartbeat', { method: 'POST' }).catch(() => {});
  }, 200);

  // Stop d'urgence si l'onglet / l'app se ferme
  window.addEventListener('beforeunload', () => {
    fetch(base() + '/motion/stop', { method: 'POST', keepalive: true }).catch(() => {});
    fetch(base() + '/motion/dome/stop', { method: 'POST', keepalive: true }).catch(() => {});
  });
}

// ================================================================
// Init
// ================================================================

async function init() {
  // Init speed slider gradient
  setSpeed(60);

  // Clock
  updateClock();
  setInterval(updateClock, 1000);

  // Heartbeat applicatif vers Master (sécurité watchdog)
  startAppHeartbeat();

  // Lock Manager init (kids speed slider + body data-lock-mode)
  lockMgr.init();

  // Volume slider + VESC scale slider
  initVolume();
  vescPanel.initSlider();

  // Load initial data
  await Promise.all([
    audioBoard.loadCategories(),
    scriptEngine.load(),
    poller.poll(),
    loadServoSettings(),
    btController.loadConfig(),
  ]);

  // Start polling
  poller.start(2000);

  // Refresh scripts periodically
  setInterval(() => scriptEngine.load(), 15000);

  // Sequence Editor
  window.seqEditor = new SequenceEditor();
  window.lightEditor = new LightEditor();
}

document.addEventListener('DOMContentLoaded', init);

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
    if (!palette) return;
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
    txtItem.dataset.args = JSON.stringify(['text', 'HELLO', 'fld']);
    txtItem.textContent = '💬 Text';
    let _txtDragged = false;
    txtItem.addEventListener('dragstart', () => { _txtDragged = true; });
    txtItem.addEventListener('dragend',   () => { setTimeout(() => { _txtDragged = false; }, 50); });
    txtItem.addEventListener('click', () => {
      if (_txtDragged) return;
      if (!this._openName) { alert('Create or open a sequence first.'); return; }
      this._addStep('teeces', ['text', 'HELLO', 'fld']);
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
    if (!this._canvasWrap) return;
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
    const palette = el('light-palette');
    if (palette) {
      palette.addEventListener('dragstart', e => {
        const item = e.target.closest('[data-cmd]');
        if (!item) return;
        e.dataTransfer.setData('text/cmd',  item.dataset.cmd);
        e.dataTransfer.setData('text/args', item.dataset.args || '[]');
      });
    }

    // SortableJS for reordering steps
    if (typeof Sortable !== 'undefined' && this._steps) {
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
    if (!list) return;
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
    if (action === 'text') { const disp = (step.args[2] || 'fld').toUpperCase(); return `💬 [${disp}] "${step.args[1] || ''}"` ; }
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
      } else if (action === 'text') {
        const curDisp = args[2] || 'fld';
        fields = [
          { label: 'Display', value: curDisp,
            options: ['fld:FLD (Front)', 'rld:RLD (Rear)', 'both:FLD + RLD'] },
          { label: 'Text (max 20)', value: args[1]||'', type:'text', placeholder:'HELLO' },
        ];
      } else if (action === 'psi') {
        fields = [{ label:'PSI Mode', value: args[1]||'1', options:[
          '0:Off', '1:Random', '2:Red', '3:Yellow', '4:Green',
          '5:Cyan', '6:Blue', '7:Magenta', '8:White', '9:Inverse Random'
        ] }];
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
        else if (a === 'text') newArgs = ['text', inputs[1].value.substring(0, 20).toUpperCase(), inputs[0].value];
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
    if (!dot || !text) return;
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

// ─── SequenceEditor ────────────────────────────────────────────────────────
class SequenceEditor {
  constructor() {
    // DOM refs
    this._nameInput     = document.getElementById('editor-name');
    this._steps         = document.getElementById('editor-steps');
    this._dropzone      = document.getElementById('editor-dropzone');
    this._canvasWrap    = document.getElementById('editor-canvas-wrap');
    this._seqList       = document.getElementById('editor-seq-list');
    this._statusDot     = document.getElementById('editor-status-dot');
    this._statusText    = document.getElementById('editor-status-text');
    this._statusCmd     = document.getElementById('editor-status-cmd');
    this._roBanner      = document.getElementById('editor-read-only-banner');
    this._canvasLabel   = document.getElementById('editor-canvas-label');

    // State
    this._sequence   = [];
    this._openName   = null;
    this._isBuiltin  = false;
    this._pollTimer  = null;
    this._editingIdx = null;
    this._saving     = false;
    this._seqNames   = [];   // noms de toutes les séquences (pour dropdown sous-seq)
    this._soundIndex = {};   // {category: [sounds]} chargé depuis /audio/index
    this._lseqNames  = [];   // light sequence names for lseq dropdown
    this._loadSoundIndex();
    this._loadLightSeqNames();

    this._initButtons();
    this._initPalette();
    this._initSortable();
    this._startPolling();
  }

  _esc(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  _initButtons() {
    document.getElementById('editor-btn-new')
      .addEventListener('click', () => this._newSequence());
    document.getElementById('editor-btn-save')
      .addEventListener('click', () => this.saveSequence());
    document.getElementById('editor-btn-delete')
      .addEventListener('click', () => this.deleteSequence());
    document.getElementById('editor-btn-duplicate')
      .addEventListener('click', () => this.duplicateSequence());
    document.getElementById('editor-btn-test')
      .addEventListener('click', () => this.testRun(true));
    document.getElementById('editor-btn-test-motion')
      .addEventListener('click', () => this.testRun(false));
    document.getElementById('editor-btn-stop')
      .addEventListener('click', () => this.stop());
    this._nameInput.addEventListener('blur', () => this._onNameBlur());
  }

  _initPalette() {
    document.querySelectorAll('.editor-palette-item').forEach(el => {
      el._wasDragged = false;
      el.addEventListener('dragstart', e => {
        e.dataTransfer.setData('editor-cmd', el.dataset.cmd);
        el._wasDragged = true;
      });
      el.addEventListener('dragend', () => {
        // Le click se déclenche juste après dragend — laisser passer, puis reset
        setTimeout(() => { el._wasDragged = false; }, 200);
      });
      el.addEventListener('click', () => {
        if (el._wasDragged) return;   // drag vient d'être utilisé, ignorer le click
        if (!this._openName) { alert('Create or open a sequence first.'); return; }
        if (this._isBuiltin) return;
        this._addStep(el.dataset.cmd, this._defaultArgs(el.dataset.cmd));
      });
    });
    // Un seul listener sur canvas-wrap — evite le double-fire par bubbling
    // (editor-dropzone est enfant de editor-canvas-wrap)
    this._canvasWrap.addEventListener('dragover', e => {
      e.preventDefault();
      if (!this._isBuiltin) this._dropzone.style.borderColor = '#00aaff';
    });
    this._canvasWrap.addEventListener('dragleave', e => {
      if (!this._canvasWrap.contains(e.relatedTarget))
        this._dropzone.style.borderColor = '';
    });
    this._canvasWrap.addEventListener('drop', e => {
      e.preventDefault();
      this._dropzone.style.borderColor = '';
      const cmd = e.dataTransfer.getData('editor-cmd');
      if (cmd) this._addStep(cmd, this._defaultArgs(cmd));
    });
  }

  _initSortable() {
    if (typeof Sortable === 'undefined') return;
    Sortable.create(this._steps, {
      handle: '.editor-step-handle',
      animation: 150,
      ghostClass: 'sortable-ghost',
      chosenClass: 'sortable-chosen',
      onEnd: (evt) => {
        const [moved] = this._sequence.splice(evt.oldIndex, 1);
        this._sequence.splice(evt.newIndex, 0, moved);
        this._renderSteps();
      },
    });
  }

  _startPolling() {
    this._pollTimer = setInterval(() => this._pollStatus(), 500);
  }

  async _loadSoundIndex() {
    try {
      const resp = await fetch('/audio/index');
      if (resp.ok) {
        const data = await resp.json();
        this._soundIndex = data.categories || {};
      }
    } catch (e) { /* silent — sons désactivés ou Slave absent */ }
  }

  async _loadLightSeqNames() {
    try {
      const resp = await fetch('/light/list');
      const data = await resp.json();
      this._lseqNames = data.sequences || [];
    } catch (e) {}
  }

  async loadSequenceList() {
    try {
      const [seqResp, lseqResp] = await Promise.all([
        fetch('/scripts/list'),
        fetch('/light/list'),
      ]);
      const seqData  = await seqResp.json();
      const lseqData = await lseqResp.json();
      this._renderSeqList(seqData.scripts || []);
      this._lseqNames = lseqData.sequences || [];
    } catch (e) {
      console.error('SequenceEditor: loadSequenceList', e);
    }
  }

  _renderSeqList(scripts) {
    this._seqNames = scripts.map(s => s.name);
    this._seqList.innerHTML = '';
    scripts.forEach(s => {
      const el = document.createElement('div');
      el.className = 'editor-seq-item' + (s.name === this._openName ? ' active' : '');
      el.innerHTML = s.is_builtin
        ? `<span class="lock-icon">🔒</span><span>${this._esc(s.name)}</span>`
        : `<span>${this._esc(s.name)}</span><span class="edit-badge">✏</span>`;
      el.addEventListener('click', () => this.openSequence(s.name));
      this._seqList.appendChild(el);
    });
  }

  async openSequence(name) {
    if (this._saving) return;  // don't interrupt an in-progress save
    try {
      const resp = await fetch(`/scripts/get?name=${encodeURIComponent(name)}`);
      if (!resp.ok) { alert(`Sequence "${name}" not found`); return; }
      const data = await resp.json();
      this._openName  = data.name;
      this._isBuiltin = data.is_builtin;
      this._sequence  = data.steps.map(s => ({ cmd: s.cmd, args: [...s.args] }));
      this._editingIdx = null;
      this._nameInput.value    = data.name;
      this._nameInput.readOnly = data.is_builtin;
      this._nameInput.style.borderColor = data.is_builtin ? '#4a6a8a' : '#00aaff';
      this._roBanner.style.display = data.is_builtin ? 'block' : 'none';
      this._canvasLabel.textContent = `STEPS — ${data.name}`;
      this._renderSteps();
      await this.loadSequenceList();
    } catch (e) {
      console.error('SequenceEditor: openSequence', e);
    }
  }

  _renderSteps() {
    this._steps.innerHTML = '';
    this._sequence.forEach((step, idx) => {
      this._steps.appendChild(this._renderStep(step, idx));
    });
  }

  _renderStep(step, idx) {
    const row = document.createElement('div');
    row.className = 'editor-step-row';
    row.id = 'editor-step-row-' + idx;

    const num = document.createElement('div');
    num.className = 'editor-step-num';
    num.textContent = idx + 1;

    const card = document.createElement('div');
    card.className = 'editor-step-card';
    card.dataset.cmd = step.cmd;

    const summary = document.createElement('div');
    summary.style.cssText = 'display:flex;align-items:center;gap:8px';

    const badge = document.createElement('span');
    badge.style.cssText = 'font-size:9px;padding:2px 7px;border-radius:10px;white-space:nowrap';
    badge.textContent = `${this._cmdIcon(step.cmd)} ${step.cmd}`;
    badge.style.color      = this._cmdColor(step.cmd);
    badge.style.background = this._cmdBg(step.cmd);

    const desc = document.createElement('span');
    desc.style.cssText = 'font-size:10px;color:#a0c0e0;flex:1';
    let _descText = step.args.join(' ');
    if (step.cmd === 'teeces') {
      const _a = step.args[0] || '';
      if (_a === 'anim') { const _m = LIGHT_ANIMATIONS.find(x => x.mode === parseInt(step.args[1])); _descText = _m ? `${_m.icon} ${_m.label}` : `T${step.args[1]}`; }
      else if (_a === 'random') _descText = '✨ Random';
      else if (_a === 'leia')   _descText = '🌀 Leia';
      else if (_a === 'off')    _descText = '⬛ Off';
      else if (_a === 'text')   _descText = `💬 "${step.args[1] || ''}"`;
      else if (_a === 'psi')    _descText = `💠 PSI ${step.args[1] || ''}`;
    } else if (step.cmd === 'lseq') _descText = `▶ ${step.args[0] || ''}`;
    desc.textContent = _descText;

    const actions = document.createElement('span');
    actions.style.cssText = 'font-size:9px;color:#4a6a8a;margin-left:auto;display:flex;align-items:center;gap:6px';

    if (!this._isBuiltin) {
      const btnEdit = document.createElement('span');
      btnEdit.textContent = '✏️';
      btnEdit.style.cssText = 'cursor:pointer';
      btnEdit.title = 'Edit';
      btnEdit.addEventListener('click', (e) => {
        e.stopPropagation();
        this._toggleEdit(idx);
      });

      const btnDel = document.createElement('span');
      btnDel.textContent = '🗑';
      btnDel.style.cssText = 'cursor:pointer';
      btnDel.title = 'Delete';
      btnDel.addEventListener('click', (e) => {
        e.stopPropagation();
        this._removeStep(idx);
      });

      actions.appendChild(btnEdit);
      actions.appendChild(btnDel);
    }

    summary.appendChild(badge);
    summary.appendChild(desc);
    summary.appendChild(actions);
    card.appendChild(summary);

    if (step.cmd === 'script' && step.args[0]) {
      const preview = document.createElement('div');
      preview.className = 'editor-subseq-preview';
      preview.innerHTML = `<div class="editor-subseq-preview-title">▾ ${this._esc(step.args[0])}.scr</div>`;
      this._loadSubseqPreview(step.args[0], preview);
      card.appendChild(preview);
    }

    if (this._editingIdx === idx && !this._isBuiltin) {
      card.appendChild(this._renderStepForm(step, idx));
    }

    const handle = document.createElement('div');
    handle.className = 'editor-step-handle';
    handle.textContent = '⋮⋮';
    if (this._isBuiltin) handle.style.cursor = 'default';

    row.appendChild(num);
    row.appendChild(card);
    if (!this._isBuiltin) row.appendChild(handle);

    return row;
  }

  async _loadSubseqPreview(name, el) {
    try {
      const resp = await fetch(`/scripts/get?name=${encodeURIComponent(name)}`);
      if (!resp.ok) { el.innerHTML += '<div style="color:#4a2a6a">not found</div>'; return; }
      const data = await resp.json();
      const lines = data.steps.slice(0, 4).map(s =>
        `<div>${this._esc(s.cmd)},${s.args.map(a => this._esc(a)).join(',')}</div>`
      ).join('');
      const more = data.steps.length > 4
        ? `<div style="color:#4a2a6a">…${data.steps.length - 4} more</div>`
        : '';
      el.innerHTML = `<div class="editor-subseq-preview-title">▾ ${this._esc(name)}.scr</div>${lines}${more}`;
    } catch (e) { /* silent */ }
  }

  _renderStepForm(step, idx) {
    const form = document.createElement('div');
    form.className = 'editor-step-form';

    const fields = this._stepFields(step.cmd, step.args);
    const inputs = [];
    const wraps = [];

    fields.forEach(f => {
      const wrap = document.createElement('div');
      if (f.hidden) wrap.style.display = 'none';
      const lbl = document.createElement('label');
      lbl.textContent = f.label;
      let inp;
      if (f.type === 'checkbox') {
        wrap.style.cssText = 'display:flex;flex-direction:row;align-items:center;gap:6px;flex-basis:100%';
        inp = document.createElement('input');
        inp.type = 'checkbox';
        inp.checked = !!f.value;
      } else if (f.options) {
        wrap.style.cssText = 'display:flex;flex-direction:column;gap:3px;flex:1;min-width:80px';
        inp = document.createElement('select');
        f.options.forEach(o => {
          const opt = document.createElement('option');
          if (typeof o === 'object') {
            opt.value = o.val; opt.textContent = o.lbl;
            if (o.val === f.value) opt.selected = true;
          } else {
            opt.value = o; opt.textContent = o;
            if (o === f.value) opt.selected = true;
          }
          inp.appendChild(opt);
        });
      } else {
        wrap.style.cssText = 'display:flex;flex-direction:column;gap:3px;flex:1;min-width:80px';
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

    // Pour sound : checkbox Aléatoire → show/hide Son ; catégorie change → reload Son
    if (step.cmd === 'sound' && inputs[0] && inputs[1] && inputs[2]) {
      const sonWrap = wraps[2];
      const prevSound = inputs[2].value;
      const reloadSounds = async () => {
        if (!Object.keys(this._soundIndex).length) await this._loadSoundIndex();
        const snds = this._soundIndex[inputs[1].value] || [];
        inputs[2].innerHTML = '';
        snds.forEach(s => {
          const o = document.createElement('option');
          o.value = s; o.textContent = s;
          if (s === prevSound) o.selected = true;
          inputs[2].appendChild(o);
        });
      };
      inputs[0].addEventListener('change', () => {  // checkbox Aléatoire
        const isRandom = inputs[0].checked;
        sonWrap.style.display = isRandom ? 'none' : '';
        if (!isRandom) reloadSounds();
      });
      inputs[1].addEventListener('change', () => {  // catégorie
        if (!inputs[0].checked) reloadSounds();
      });
      // Si mode FILE dès l'ouverture, peupler immédiatement
      if (!inputs[0].checked) reloadSounds();
    }

    // Pour sleep : mode change → show/hide Max
    if (step.cmd === 'sleep' && inputs[0] && wraps[2]) {
      inputs[0].addEventListener('change', () => {
        wraps[2].style.display = inputs[0].value === 'random' ? '' : 'none';
      });
    }

    // For lights (teeces/lseq): main selection → show/hide sub-fields
    if ((step.cmd === 'teeces' || step.cmd === 'lseq') && inputs[0] && wraps[1] && wraps[2]) {
      const updateLightSubs = () => {
        const v = inputs[0].value;
        wraps[1].style.display = (v === 'teeces:text' || v === 'teeces:raw') ? '' : 'none';
        wraps[2].style.display = v === 'teeces:psi' ? '' : 'none';
      };
      inputs[0].addEventListener('change', updateLightSubs);
      updateLightSubs();
    }

    const ok = document.createElement('button');
    ok.textContent = '✓ OK';
    ok.className = 'btn-editor-action';
    ok.dataset.color = 'green';
    ok.style.cssText = 'margin-top:4px;flex-basis:100%';
    ok.addEventListener('click', () => {
      let newArgs = inputs.map(inp => inp.value.trim()).filter(Boolean);
      // Normaliser sound via checkbox Aléatoire (inputs[0])
      if (this._sequence[idx].cmd === 'sound') {
        if (inputs[0].checked) {
          newArgs = ['RANDOM', inputs[1].value || 'happy'];
        } else {
          newArgs = [inputs[2].value].filter(Boolean);
          if (!newArgs.length) newArgs = ['RANDOM', inputs[1].value || 'happy'];
        }
      }
      // Normaliser sleep : fixed,dur → ['fixed','dur']  |  random,min,max → inchangé
      if (this._sequence[idx].cmd === 'sleep') {
        if (newArgs[0] === 'fixed') {
          newArgs = ['fixed', newArgs[1] || '1'];
        }
      }
      // Lights (teeces/lseq): parse encoded selection, update cmd+args
      if (this._sequence[idx].cmd === 'teeces' || this._sequence[idx].cmd === 'lseq') {
        const v = inputs[0].value;
        if (v.startsWith('lseq:')) {
          this._sequence[idx].cmd  = 'lseq';
          this._sequence[idx].args = [v.slice(5)];
        } else if (v.startsWith('teeces:anim:')) {
          this._sequence[idx].cmd  = 'teeces';
          this._sequence[idx].args = ['anim', v.slice(12)];
        } else if (v === 'teeces:text') {
          this._sequence[idx].cmd  = 'teeces';
          this._sequence[idx].args = ['text', (inputs[1].value||'').toUpperCase().slice(0,20)];
        } else if (v === 'teeces:psi') {
          this._sequence[idx].cmd  = 'teeces';
          this._sequence[idx].args = ['psi', (inputs[2].value||'1:Random').split(':')[0]];
        } else if (v === 'teeces:raw') {
          this._sequence[idx].cmd  = 'teeces';
          this._sequence[idx].args = ['raw', inputs[1].value||''];
        } else {
          this._sequence[idx].cmd  = 'teeces';
          this._sequence[idx].args = [v.slice(8)];
        }
        this._editingIdx = null;
        this._renderSteps();
        return;
      }
      this._sequence[idx].args = newArgs;
      this._editingIdx = null;
      this._renderSteps();
    });
    form.appendChild(ok);

    return form;
  }

  async _addStep(cmd, args) {
    if (this._isBuiltin) return;
    let resolvedArgs = [...args];
    // Pre-fill sub-sequence with first available option
    if (cmd === 'script' && (!resolvedArgs[0] || resolvedArgs[0] === '')) {
      const opts = this._seqNames.filter(n => n !== this._openName);
      if (opts.length > 0) resolvedArgs = [opts[0]];
    }
    // Pre-fill lights: refresh lseq names
    if (cmd === 'lseq' || cmd === 'teeces') {
      await this._loadLightSeqNames();
      if (cmd === 'lseq' && !resolvedArgs[0] && this._lseqNames.length > 0) resolvedArgs = [this._lseqNames[0]];
    }
    this._sequence.push({ cmd, args: resolvedArgs });
    this._editingIdx = this._sequence.length - 1;
    this._renderSteps();
  }

  _removeStep(idx) {
    if (this._isBuiltin) return;
    this._sequence.splice(idx, 1);
    if (this._editingIdx === idx) this._editingIdx = null;
    this._renderSteps();
  }

  async _toggleEdit(idx) {
    this._editingIdx = this._editingIdx === idx ? null : idx;
    // Refresh light sequence names before showing lights form
    if (this._editingIdx !== null) {
      const _ec = this._sequence[idx]?.cmd;
      if (_ec === 'lseq' || _ec === 'teeces') await this._loadLightSeqNames();
    }
    this._renderSteps();
  }

  _newSequence() {
    const name = prompt('New sequence name (letters, digits, - and _ only):');
    if (!name) return;
    if (!/^[a-zA-Z0-9_\-]{1,64}$/.test(name)) {
      alert('Invalid name. Use letters, digits, - and _ only (max 64 chars).');
      return;
    }
    this._openName  = name;
    this._isBuiltin = false;
    this._sequence  = [];
    this._editingIdx = null;
    this._nameInput.value    = name;
    this._nameInput.readOnly = false;
    this._nameInput.style.borderColor = '#00aaff';
    this._roBanner.style.display = 'none';
    this._canvasLabel.textContent = `STEPS — ${name} (new)`;
    this._renderSteps();
  }

  async saveSequence() {
    if (this._isBuiltin) { alert('Built-in sequence — duplicate to edit.'); return; }
    const name = this._nameInput.value.trim();
    if (!name || !/^[a-zA-Z0-9_\-]{1,64}$/.test(name)) { alert('Invalid name.'); return; }
    if (this._sequence.length === 0) { alert('Sequence is empty.'); return; }
    this._saving = true;
    try {
      const resp = await fetch('/scripts/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, steps: this._sequence }),
      });
      if (!resp.ok) { const err = await resp.json(); alert(`Error: ${err.error}`); return; }
      this._openName = name;
      this._canvasLabel.textContent = `STEPS — ${name}`;
      await this.loadSequenceList();
    } catch (e) {
      alert('Network error while saving.');
    } finally {
      this._saving = false;
    }
  }

  async deleteSequence() {
    if (this._isBuiltin) { alert('Built-in sequence — cannot delete.'); return; }
    if (!this._openName) return;
    if (!confirm(`Delete "${this._openName}"? This cannot be undone.`)) return;
    try {
      const resp = await fetch('/scripts/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: this._openName }),
      });
      if (!resp.ok) { const err = await resp.json(); alert(`Error: ${err.error}`); return; }
      this._openName  = null;
      this._sequence  = [];
      this._isBuiltin = false;
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
      const resp = await fetch('/scripts/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newName, steps: this._sequence }),
      });
      if (!resp.ok) { alert('Error while duplicating.'); return; }
      await this.openSequence(newName);
    } catch (e) { alert('Network error.'); }
  }

  async _onNameBlur() {
    const newName = this._nameInput.value.trim();
    if (!newName || newName === this._openName || this._isBuiltin) return;
    if (!/^[a-zA-Z0-9_\-]{1,64}$/.test(newName)) {
      alert('Invalid name.'); this._nameInput.value = this._openName || ''; return;
    }
    if (!this._openName) return;
    try {
      const resp = await fetch('/scripts/rename', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ old: this._openName, new: newName }),
      });
      if (!resp.ok) {
        const err = await resp.json();
        alert(`Cannot rename: ${err.error}`);
        this._nameInput.value = this._openName;
        return;
      }
      this._openName = newName;
      this._canvasLabel.textContent = `STEPS — ${newName}`;
      await this.loadSequenceList();
    } catch (e) { alert('Network error.'); }
  }

  async testRun(skipMotion) {
    if (!this._openName) { alert("Open or save a sequence first."); return; }
    try {
      const resp = await fetch('/scripts/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: this._openName, loop: false, skip_motion: skipMotion }),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        alert(`Error TEST: ${err.error || resp.status}`);
      }
    } catch (e) { console.error('testRun', e); }
  }

  async stop() {
    try {
      await fetch('/scripts/stop_all', { method: 'POST' });
    } catch (e) { console.error('stop', e); }
  }

  async _pollStatus() {
    const editorTab = document.getElementById('tab-editor');
    if (!editorTab || !editorTab.classList.contains('active')) return;
    try {
      const resp = await fetch('/scripts/running');
      const data = await resp.json();
      const running = (data.running || []).find(r => r.name === this._openName);
      if (running) {
        this._statusDot.style.background = '#00cc55';
        this._statusDot.style.boxShadow  = '0 0 6px #00cc55';
        this._statusText.style.color = '#00cc55';
        this._statusText.textContent = `RUNNING — ${running.name} (step ${running.step_index}/${running.step_total})`;
        this._statusCmd.textContent  = running.current_cmd || '';
        this._statusCmd.style.color  = '#2a4a6a';
        this._highlightStep(running.step_index - 1);
      } else {
        this._statusDot.style.background = '#2a4a6a';
        this._statusDot.style.boxShadow  = 'none';
        this._statusText.style.color = '#2a4a6a';
        this._statusText.textContent = '—';
        this._statusCmd.textContent  = '';
        this._highlightStep(-1);
      }
    } catch (e) { /* silent */ }
  }

  _highlightStep(idx) {
    this._steps.querySelectorAll('.editor-step-row').forEach(r => r.classList.remove('step-active'));
    if (idx >= 0) {
      const row = document.getElementById('editor-step-row-' + idx);
      if (row) {
        row.classList.add('step-active');
        row.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      }
    }
  }

  _cmdIcon(cmd) {
    return { sound:'🔊', sleep:'⏱', servo:'🦾', motion:'🚗',
             teeces:'💡', dome:'🔁', script:'📋', lseq:'💡', wait_light:'⏳' }[cmd] || '•';
  }

  _cmdColor(cmd) {
    return { sound:'#00cc55', sleep:'#ffaa00', servo:'#00aaff',
             motion:'#ff6633', teeces:'#aa44ff', dome:'#44ffaa',
             script:'#cc88ff', lseq:'#ffdd44', wait_light:'#aa44ff' }[cmd] || '#a0c0e0';
  }

  _cmdBg(cmd) {
    return { sound:'#0a2a10', sleep:'#2a1a00', servo:'#001a2a',
             motion:'#1a1000', teeces:'#1a0028', dome:'#0a1a10',
             script:'#1a1030', lseq:'#1a1a00', wait_light:'#1a0028' }[cmd] || '#0d1a2e';
  }

  _defaultArgs(cmd) {
    return {
      sound:   ['RANDOM', 'happy'],
      sleep:   ['1.0'],
      servo:   ['body_panel_1', 'open'],
      motion:  ['0.0', '0.0', '1000'],
      teeces:  ['random'],
      dome:    ['stop'],
      script:  [''],
      lseq:       [''],
      wait_light: [],
    }[cmd] || [];
  }

  _stepFields(cmd, args) {
    switch (cmd) {
      case 'sound': {
        const cats = Object.keys(this._soundIndex);
        const fallbackCats = ['alarm','extra','happy','hum','misc','ooh','proc','quote',
                              'razz','sad','scream','sent','special','whistle'];
        const catList = cats.length ? cats : fallbackCats;
        const isRandom = !args[0] || args[0] === 'RANDOM';
        const currentSound = (!isRandom && args[0] !== 'FILE') ? args[0] : '';
        let currentCat = isRandom ? (args[1] || catList[0] || 'happy') : (catList[0] || 'happy');
        if (!isRandom && currentSound) {
          for (const [cat, snds] of Object.entries(this._soundIndex)) {
            if (snds.includes(currentSound)) { currentCat = cat; break; }
          }
        }
        const sounds = this._soundIndex[currentCat] || [];
        return [
          { label: 'Random',   value: isRandom, type: 'checkbox' },
          { label: 'Category', value: currentCat, options: catList },
          { label: 'Sound',    value: currentSound || sounds[0] || '', options: sounds,
            hidden: isRandom },
        ];
      }
      case 'sleep': {
        const isRand = args[0] === 'random';
        const dur = isRand ? (args[1]||'1') : (args[0]==='fixed' ? (args[1]||'1') : (args[0]||'1'));
        return [
          { label: 'Mode',            value: isRand ? 'random' : 'fixed', options: ['fixed','random'] },
          { label: 'Duration (s) / Min', value: dur, type:'number', placeholder:'1.0' },
          { label: 'Max (s)',         value: args[2]||'3', type:'number', placeholder:'3.0',
            hidden: !isRand },
        ];
      }
      case 'servo': return [
        { label: 'Panel', value: args[0]||'body_panel_1',
          options: ['body_panel_1','body_panel_2','body_panel_3','body_panel_4',
                    'dome_panel_1','dome_panel_2','dome_panel_3','dome_panel_4',
                    'dome_panel_5','dome_panel_6','all'] },
        { label: 'Action', value: args[1]||'open', options: ['open','close'] },
        { label: 'Angle (optional)', value: args[2]||'', type:'number', placeholder:'—' },
        { label: 'Speed (1-10)',     value: args[3]||'', type:'number', placeholder:'—' },
      ];
      case 'motion': return [
        { label: 'Left (-1..1)',  value: args[0]||'0.0', type:'number', placeholder:'0.0' },
        { label: 'Right (-1..1)', value: args[1]||'0.0', type:'number', placeholder:'0.0' },
        { label: 'Duration ms',   value: args[2]||'1000', type:'number', placeholder:'1000' },
      ];
      case 'teeces':
      case 'lseq': {
        // Mega-dropdown: named modes + T-code animations + FLD Text + PSI + Raw + custom .lseq
        const lightOpts = [];
        lightOpts.push({ val: 'teeces:random', lbl: '✨ Random' });
        lightOpts.push({ val: 'teeces:leia',   lbl: '🌀 Leia' });
        lightOpts.push({ val: 'teeces:off',    lbl: '⬛ Off' });
        LIGHT_ANIMATIONS.forEach(a => {
          if (![1, 6, 20].includes(a.mode)) lightOpts.push({ val: `teeces:anim:${a.mode}`, lbl: `${a.icon} ${a.label}` });
        });
        lightOpts.push({ val: 'teeces:text', lbl: '💬 FLD Text…' });
        lightOpts.push({ val: 'teeces:psi',  lbl: '💠 PSI Mode…' });
        lightOpts.push({ val: 'teeces:raw',  lbl: '⚙️ Raw JawaLite…' });
        this._lseqNames.forEach(n => lightOpts.push({ val: `lseq:${n}`, lbl: `▶ ${n}` }));

        // Determine current encoded value + sub-field values
        let curVal = 'teeces:random', subText = '', curPsi = '1';
        if (cmd === 'lseq') {
          const n = args[0] || '';
          curVal = n ? `lseq:${n}` : 'teeces:random';
          if (n && !lightOpts.find(o => o.val === curVal)) lightOpts.push({ val: curVal, lbl: `▶ ${n}` });
        } else {
          const a0 = args[0] || 'random';
          if (a0 === 'random')    curVal = 'teeces:random';
          else if (a0 === 'leia') curVal = 'teeces:leia';
          else if (a0 === 'off')  curVal = 'teeces:off';
          else if (a0 === 'anim') curVal = `teeces:anim:${args[1]||'2'}`;
          else if (a0 === 'text') { curVal = 'teeces:text'; subText = args[1]||''; }
          else if (a0 === 'psi')  { curVal = 'teeces:psi';  curPsi  = args[1]||'1'; }
          else if (a0 === 'raw')  { curVal = 'teeces:raw';  subText = args[1]||''; }
        }
        const psiOpts = ['0:Off','1:Random','2:Red','3:Yellow','4:Green',
                         '5:Cyan','6:Blue','7:Magenta','8:White','9:Inverse Random'];
        const curPsiOpt = psiOpts.find(o => o.startsWith(curPsi + ':')) || psiOpts[1];
        return [
          { label: 'Light', value: curVal, options: lightOpts },
          { label: 'Text / Value', value: subText, placeholder: 'HELLO',
            hidden: curVal !== 'teeces:text' && curVal !== 'teeces:raw' },
          { label: 'PSI Mode', value: curPsiOpt, options: psiOpts,
            hidden: curVal !== 'teeces:psi' },
        ];
      }
      case 'dome': return [
        { label: 'Action', value: args[0]||'stop', options: ['turn','stop','random','center'] },
        ...(args[0]==='turn'   ? [{ label:'Vitesse (-1..1)', value: args[1]||'0.3', type:'number' }] : []),
        ...(args[0]==='random' ? [{ label:'On/Off', value: args[1]||'on', options: ['on','off'] }] : []),
      ];
      case 'script': {
        const opts = this._seqNames.filter(n => n !== this._openName);
        return opts.length > 0
          ? [{ label: 'Sub-sequence', value: args[0] || opts[0], options: opts }]
          : [{ label: 'Sub-sequence', value: args[0] || '', placeholder: 'sequence-name' }];
      }
      case 'wait_light':
        return [];   // no args — just blocks until light sequences finish
      default: return args.map((a, i) => ({ label: `arg${i+1}`, value: a }));
    }
  }
}
