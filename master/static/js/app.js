/**
 * R2-D2 Control Dashboard — app.js
 * Polling REST + contrôles temps réel (pas de dépendance externe)
 */

'use strict';

// ================================================================
// API Helper
// ================================================================

async function api(endpoint, method = 'GET', body = null) {
  try {
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(endpoint, opts);
    return await res.json();
  } catch (e) {
    console.error(`API ${method} ${endpoint}:`, e);
    return null;
  }
}

// ================================================================
// Status polling (toutes les 2 secondes)
// ================================================================

async function pollStatus() {
  const data = await api('/status');
  if (!data) return;

  // Heartbeat
  setPill('pill-heartbeat', data.heartbeat_ok, '● Heartbeat');
  setPill('pill-uart',   data.uart_ready,   '● UART');
  setPill('pill-teeces', data.teeces_ready,  '● Teeces');
  setPill('pill-vesc',   data.vesc_ready,    '● VESC');

  el('uptime-label').textContent  = data.uptime  || '--';
  el('version-label').textContent = 'v' + (data.version || '?');

  // Scripts en cours
  const running = data.scripts_running || [];
  el('running-scripts').textContent =
    running.length ? running.map(s => `${s.name}#${s.id}`).join(', ') : '—';
}

function setPill(id, ok, label) {
  const p = el(id);
  if (!p) return;
  p.textContent = label;
  p.className   = 'status-pill ' + (ok ? 'ok' : 'error');
}

function el(id) { return document.getElementById(id); }

// ================================================================
// Audio
// ================================================================

async function loadAudioCategories() {
  const data = await api('/audio/categories');
  if (!data || !data.categories) return;

  const icons = {
    alarm: '🚨', happy: '😄', hum: '🎵', misc: '🎲',
    proc: '⚙️', quote: '💬', razz: '🤪', sad: '😢',
    sent: '🤔', ooh: '😲', whistle: '🎶', scream: '😱',
    special: '⭐'
  };

  const grid = el('audio-categories');
  grid.innerHTML = Object.entries(data.categories).map(([cat, count]) => `
    <button class="category-btn" onclick="playRandom('${cat}')">
      ${icons[cat] || '🔊'} ${cat}
      <span class="count">${count} sons</span>
    </button>
  `).join('');
}

function playRandom(category) {
  api('/audio/random', 'POST', { category });
}

// ================================================================
// Propulsion
// ================================================================

let _speedLimit = 0.6;

function setSpeed(val) {
  _speedLimit = val / 100;
  el('speed-val').textContent = val + '%';
}

function drive(leftRaw, rightRaw) {
  const left  = leftRaw  * _speedLimit;
  const right = rightRaw * _speedLimit;
  api('/motion/drive', 'POST', { left, right });
}

function driveStop() {
  api('/motion/stop', 'POST');
}

// Clavier ZQSD / WASD
const _keysDown = {};

document.addEventListener('keydown', (e) => {
  if (_keysDown[e.code]) return;
  _keysDown[e.code] = true;
  handleDriveKey();
});

document.addEventListener('keyup', (e) => {
  delete _keysDown[e.code];
  handleDriveKey();
});

function handleDriveKey() {
  const up    = _keysDown['KeyW'] || _keysDown['ArrowUp'];
  const down  = _keysDown['KeyS'] || _keysDown['ArrowDown'];
  const left  = _keysDown['KeyA'] || _keysDown['ArrowLeft'];
  const right = _keysDown['KeyD'] || _keysDown['ArrowRight'];

  if (!up && !down && !left && !right) { driveStop(); return; }

  let throttle = up ? 1 : (down ? -1 : 0);
  let steering = right ? 1 : (left ? -1 : 0);
  api('/motion/arcade', 'POST', {
    throttle: throttle * _speedLimit,
    steering: steering * _speedLimit * 0.5
  });
}

// ================================================================
// Dôme
// ================================================================

function domeTurn(speed)  { api('/motion/dome/turn', 'POST', { speed }); }
function domeStop()       { api('/motion/dome/stop', 'POST'); }
function domeRandom(on)   { api('/motion/dome/random', 'POST', { enabled: on }); }

// ================================================================
// Teeces
// ================================================================

async function teecesMode(mode) {
  await api(`/teeces/${mode}`, 'POST');
  // Mettre à jour le bouton actif
  document.querySelectorAll('#card-teeces .btn').forEach(b => b.classList.remove('btn-active'));
  event.target.classList.add('btn-active');
}

function sendTeecesText() {
  const text = el('teeces-text').value.trim();
  if (text) api('/teeces/text', 'POST', { text });
}

// ================================================================
// Servos
// ================================================================

const SERVOS = [
  'utility_arm_left', 'utility_arm_right',
  'panel_front_top',  'panel_front_bottom',
  'panel_rear_top',   'panel_rear_bottom',
  'charge_bay',
];

function loadServos() {
  const list = el('servo-list');
  list.innerHTML = SERVOS.map(name => `
    <div class="servo-row">
      <label>${name.replace(/_/g, ' ')}</label>
      <button class="btn" onclick="servoOpen('${name}')">Ouvrir</button>
      <button class="btn btn-dark" onclick="servoClose('${name}')">Fermer</button>
    </div>
  `).join('');
}

function servoOpen(name)  { api('/servo/open',  'POST', { name }); }
function servoClose(name) { api('/servo/close', 'POST', { name }); }

// ================================================================
// Scripts
// ================================================================

async function loadScripts() {
  const data = await api('/scripts/list');
  if (!data || !data.scripts) return;

  const list = el('script-list');
  list.innerHTML = data.scripts.map(name => `
    <div class="script-item">
      <label>${name}</label>
      <button class="btn" onclick="runScript('${name}', false)">▶ Run</button>
      <button class="btn btn-active" onclick="runScript('${name}', true)">↺ Loop</button>
    </div>
  `).join('');
}

function runScript(name, loop) {
  api('/scripts/run', 'POST', { name, loop });
}

// ================================================================
// Système
// ================================================================

function confirmAction(msg, endpoint) {
  if (confirm(msg)) {
    api(endpoint, 'POST');
  }
}

// ================================================================
// Init
// ================================================================

async function init() {
  await loadAudioCategories();
  loadServos();
  await loadScripts();
  await pollStatus();

  // Polling status toutes les 2s
  setInterval(pollStatus, 2000);
  // Refresh scripts liste toutes les 10s
  setInterval(loadScripts, 10000);
}

document.addEventListener('DOMContentLoaded', init);
