# Cockpit Status Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a collapsible STATUS dropdown panel in the header that shows all R2-D2 system vitals from any tab without leaving it.

**Architecture:** Toggle button added to header → `#cockpit-panel` div placed right after `</header>` in DOM flow, styled as `position: fixed` overlay below the header. Reads data from the existing `/status` poll (StatusPoller, 2s). No new polling. Two small new fields added to `/status` (camera_active, vesc_l_temp, vesc_r_temp). Click-away and Escape close the panel.

**Tech Stack:** HTML/CSS/JS (no new Flask endpoints beyond minor /status field additions). Vanilla JS, no libraries.

---

## Files

| File | Change |
|---|---|
| `master/api/status_bp.py` | Add `camera_active`, `vesc_l_temp`, `vesc_r_temp` to `/status` response |
| `master/static/css/style.css` | All `.cockpit-*` CSS + slide animation + responsive hide |
| `master/templates/index.html` | Button in header + `#cockpit-panel` div after `</header>` |
| `master/static/js/app.js` | `cockpitPanel` object + StatusPoller hook |

---

## Task 1: Extend /status with camera and per-side VESC temps

**Files:**
- Modify: `master/api/status_bp.py` (after line 126 — end of `get_status()` return dict)

Context: `_active_token` is a module-level int in `camera_bp.py`. Non-zero means a stream is active. `reg.vesc_telem` dict has `'L'` and `'R'` keys with dicts containing `'temp'`.

- [ ] **Step 1: Add the three new fields to the `/status` response**

In `master/api/status_bp.py`, add an import near the top (after existing imports):

```python
try:
    from master.api import camera_bp as _cam_bp
except Exception:
    _cam_bp = None
```

Then in `get_status()`, add these three lines inside the `return jsonify({...})` dict, right after `'vesc_bench_mode': bool(reg.vesc_bench_mode),`:

```python
'camera_active':  bool(_cam_bp and _cam_bp._active_token > 0),
'vesc_l_temp':    (reg.vesc_telem.get('L') or {}).get('temp'),
'vesc_r_temp':    (reg.vesc_telem.get('R') or {}).get('temp'),
```

- [ ] **Step 2: Verify the endpoint returns the new fields**

```bash
# On dev machine (Pi must be running):
curl -s http://192.168.2.104:5000/status | python -m json.tool | grep -E "camera_active|vesc_l_temp|vesc_r_temp"
```

Expected output (values will vary):
```
"camera_active": false,
"vesc_l_temp": null,
"vesc_r_temp": null,
```

- [ ] **Step 3: Commit**

```bash
git add master/api/status_bp.py
git commit -m "Feat: add camera_active + vesc_l/r_temp to /status for cockpit panel"
```

---

## Task 2: CSS — cockpit panel styles

**Files:**
- Modify: `master/static/css/style.css` (append before the last `}` or after the `.vesc-bench-btn` block)

- [ ] **Step 1: Add all cockpit CSS**

Append to the end of `master/static/css/style.css`:

```css
/* ================================================================
   Cockpit Status Panel
   ================================================================ */

/* Toggle button in header — same pill style, slightly prominent */
.cockpit-btn {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 3px 10px;
  background: rgba(0,200,100,0.1);
  border: 1px solid rgba(0,200,100,0.35);
  border-radius: 10px;
  color: var(--green);
  font-family: var(--font); font-size: 10px; font-weight: 700; letter-spacing: 1.2px;
  cursor: pointer;
  user-select: none;
  transition: background 0.2s, border-color 0.2s, box-shadow 0.2s;
  white-space: nowrap;
}
.cockpit-btn:hover {
  background: rgba(0,200,100,0.18);
  box-shadow: 0 0 8px rgba(0,200,100,0.3);
}
.cockpit-btn.open {
  background: rgba(0,200,100,0.2);
  border-color: var(--green);
  box-shadow: 0 0 10px rgba(0,200,100,0.35);
}
.cockpit-btn.alert {
  border-color: var(--orange);
  color: var(--orange);
  background: rgba(255,136,0,0.1);
}

/* Panel — fixed below topbar, full width, overlays tab content */
.cockpit-panel {
  position: fixed;
  top: var(--topbar-h);
  left: 0; right: 0;
  z-index: 190;
  background: rgba(10, 11, 22, 0.97);
  border-bottom: 1px solid rgba(0,200,100,0.2);
  backdrop-filter: blur(10px);
  overflow: hidden;
  max-height: 0;
  opacity: 0;
  transition: max-height 0.18s ease-out, opacity 0.15s ease-out,
              border-color 0.2s;
  pointer-events: none;
}
.cockpit-panel.open {
  max-height: 520px;
  opacity: 1;
  pointer-events: auto;
}
.cockpit-panel.has-alert {
  border-bottom-color: rgba(255,136,0,0.4);
}

.cockpit-inner {
  padding: 12px 16px 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* Section title */
.cockpit-section-title {
  font-size: 8px;
  letter-spacing: 2px;
  color: rgba(255,255,255,0.3);
  margin-bottom: 6px;
  text-transform: uppercase;
}

/* Vitals row — 4 cards */
.cockpit-vitals {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 6px;
}
.cockpit-card {
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 6px;
  padding: 7px 10px;
  text-align: center;
  transition: border-color 0.2s;
}
.cockpit-card-lbl {
  font-size: 8px;
  letter-spacing: 1.5px;
  color: rgba(255,255,255,0.35);
  margin-bottom: 3px;
}
.cockpit-card-val {
  font-size: 17px;
  font-weight: 700;
  line-height: 1.1;
  color: var(--green);
}
.cockpit-card-sub {
  font-size: 9px;
  color: rgba(255,255,255,0.4);
  margin-top: 2px;
}

/* Services + Activity + Network — 2 columns */
.cockpit-cols {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.cockpit-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 3px 7px;
  background: rgba(255,255,255,0.03);
  border-radius: 4px;
  font-size: 11px;
  margin-bottom: 3px;
}
.cockpit-row-lbl { color: rgba(255,255,255,0.45); }
.cockpit-row-val { font-weight: 600; }
.cockpit-ok   { color: var(--green); }
.cockpit-warn { color: var(--orange); }
.cockpit-err  { color: var(--red); }
.cockpit-dim  { color: rgba(255,255,255,0.3); }

/* Alerts row */
.cockpit-alerts {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.cockpit-alert {
  padding: 3px 9px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
  border: 1px solid;
}
.cockpit-alert.ok   { background: rgba(0,200,100,0.07); border-color: rgba(0,200,100,0.2); color: rgba(255,255,255,0.35); }
.cockpit-alert.warn { background: rgba(255,136,0,0.1);  border-color: rgba(255,136,0,0.35); color: var(--orange); }
.cockpit-alert.err  { background: rgba(255,34,68,0.1);  border-color: rgba(255,34,68,0.35); color: var(--red); }

/* Hide on portrait mobile — too dense */
@media (max-width: 480px) and (orientation: portrait) {
  .cockpit-panel { display: none !important; }
  .cockpit-btn   { display: none !important; }
}
```

- [ ] **Step 2: Verify no CSS parse errors**

Open `http://192.168.2.104:5000` in browser. Open DevTools → Console. No CSS errors should appear.

- [ ] **Step 3: Commit**

```bash
git add master/static/css/style.css
git commit -m "Feat: cockpit panel CSS — button, panel, cards, rows, alerts"
```

---

## Task 3: HTML — button in header + panel structure

**Files:**
- Modify: `master/templates/index.html`

Context: The header is `<header class="topbar">` (line 52). `topbar-center` contains the status pills (HB, UART, BT, version). The cockpit button goes at the end of `topbar-center`. The panel `div` goes immediately after `</header>` (line 96).

- [ ] **Step 1: Add the cockpit button to the header**

Find this block in `master/templates/index.html`:

```html
    <div class="status-pill" id="pill-version">v?</div>
  </div>
```

Replace with:

```html
    <div class="status-pill" id="pill-version">v?</div>
    <button id="cockpit-btn" class="cockpit-btn" onclick="cockpitPanel.toggle()" title="System status overview">⬡ STATUS ▼</button>
  </div>
```

- [ ] **Step 2: Add the panel div after </header>**

Find this exact line in `master/templates/index.html`:

```html
<div class="lock-mode-bar"></div>
```

Replace with:

```html
<!-- Cockpit Status Panel — fixed overlay below header -->
<div id="cockpit-panel" class="cockpit-panel">
  <div class="cockpit-inner">

    <!-- Vitaux -->
    <div>
      <div class="cockpit-section-title">VITAUX</div>
      <div class="cockpit-vitals">
        <div class="cockpit-card" id="ck-battery">
          <div class="cockpit-card-lbl">BATTERIE</div>
          <div class="cockpit-card-val" id="ck-battery-v">--V</div>
          <div class="cockpit-card-sub" id="ck-battery-pct">--%</div>
        </div>
        <div class="cockpit-card" id="ck-vesc">
          <div class="cockpit-card-lbl">VESC L / R</div>
          <div class="cockpit-card-val" id="ck-vesc-l">--°C</div>
          <div class="cockpit-card-sub" id="ck-vesc-r">--°C</div>
        </div>
        <div class="cockpit-card" id="ck-pi">
          <div class="cockpit-card-lbl">PI TEMP</div>
          <div class="cockpit-card-val" id="ck-pi-temp">--°C</div>
          <div class="cockpit-card-sub" id="ck-pi-hint"></div>
        </div>
        <div class="cockpit-card">
          <div class="cockpit-card-lbl">UPTIME</div>
          <div class="cockpit-card-val" id="ck-uptime" style="font-size:13px">--</div>
          <div class="cockpit-card-sub" id="ck-version">v?</div>
        </div>
      </div>
    </div>

    <!-- Services + Activité/Réseau -->
    <div class="cockpit-cols">
      <div>
        <div class="cockpit-section-title">SERVICES</div>
        <div id="ck-services"></div>
      </div>
      <div>
        <div class="cockpit-section-title">ACTIVITÉ</div>
        <div id="ck-activity"></div>
        <div class="cockpit-section-title" style="margin-top:8px">RÉSEAU</div>
        <div id="ck-network"></div>
      </div>
    </div>

    <!-- Alertes -->
    <div>
      <div class="cockpit-section-title">ALERTES</div>
      <div class="cockpit-alerts" id="ck-alerts">
        <span class="cockpit-alert ok">✓ En attente de données...</span>
      </div>
    </div>

  </div>
</div>

<div class="lock-mode-bar"></div>
```

- [ ] **Step 3: Verify panel renders (hidden by default)**

Open `http://192.168.2.104:5000`. The STATUS button should appear in the header pills area. The panel should be invisible (max-height:0). No layout shifts.

- [ ] **Step 4: Commit**

```bash
git add master/templates/index.html
git commit -m "Feat: cockpit panel HTML — STATUS button in header + panel structure"
```

---

## Task 4: JS — cockpitPanel object + StatusPoller hook

**Files:**
- Modify: `master/static/js/app.js`

Context: `StatusPoller.poll()` already calls `api('/status')` and passes `data` to various update functions. `batteryGauge.voltToPct(v)` and `batteryGauge.voltToColor(v)` are globally available. `el(id)` is the `document.getElementById` shortcut.

- [ ] **Step 1: Add the cockpitPanel object**

Find this line in `master/static/js/app.js`:

```javascript
class StatusPoller {
```

Insert the entire `cockpitPanel` object immediately before it:

```javascript
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
    if (btn)   btn.textContent = `⬡ STATUS ${this.isOpen ? '▲' : '▼'}`;
  },

  close() {
    if (!this.isOpen) return;
    this.isOpen = false;
    const panel = el('cockpit-panel');
    const btn   = el('cockpit-btn');
    if (panel) panel.classList.remove('open');
    if (btn)   btn.textContent = '⬡ STATUS ▼';
  },

  update(data) {
    this._updateVitals(data);
    this._updateServices(data);
    this._updateActivity(data);
    this._updateNetwork(data);
    this._updateAlerts(data);
  },

  _updateVitals(data) {
    const v = data.battery_voltage;
    if (v != null) {
      const col = batteryGauge.voltToColor(v);
      const pct = Math.round(batteryGauge.voltToPct(v));
      const bv  = el('ck-battery-v');
      const bp  = el('ck-battery-pct');
      if (bv) { bv.textContent = v.toFixed(1) + 'V'; bv.style.color = col; }
      if (bp) { bp.textContent = pct + '%'; bp.style.color = col; }
      const bc = el('ck-battery');
      if (bc) { bc.style.borderColor = col + '44'; }
    }

    const lt = data.vesc_l_temp;
    const rt = data.vesc_r_temp;
    const ckL = el('ck-vesc-l');
    const ckR = el('ck-vesc-r');
    if (ckL) {
      ckL.textContent = lt != null ? lt.toFixed(0) + '°C' : '--°C';
      ckL.style.color = lt == null ? '' : lt >= 70 ? 'var(--red)' : lt >= 50 ? 'var(--orange)' : 'var(--green)';
    }
    if (ckR) {
      ckR.textContent = rt != null ? rt.toFixed(0) + '°C' : '--°C';
      ckR.style.color = rt == null ? '' : rt >= 70 ? 'var(--red)' : rt >= 50 ? 'var(--orange)' : 'var(--green)';
    }

    const t = data.temperature;
    const pt = el('ck-pi-temp');
    const ph = el('ck-pi-hint');
    if (pt) {
      pt.textContent = t != null ? t + '°C' : '--°C';
      pt.style.color = t == null ? '' : t >= 75 ? 'var(--red)' : t >= 60 ? 'var(--orange)' : 'var(--green)';
    }
    if (ph) ph.textContent = t == null ? '' : t >= 75 ? '⚠ critique' : t >= 60 ? '⚠ chaud' : 'OK';

    const up = el('ck-uptime');
    if (up) up.textContent = data.uptime || '--';
    const ver = el('ck-version');
    if (ver) ver.textContent = 'v' + (data.version || '?');
  },

  _svcRow(label, cls, val) {
    return `<div class="cockpit-row"><span class="cockpit-row-lbl">${label}</span><span class="cockpit-row-val cockpit-${cls}">${val}</span></div>`;
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
    svc.innerHTML =
      this._svcRow('UART',          uartCls,   uartVal) +
      this._svcRow('VESC L',        vescLCls,  data.vesc_l_ok ? '✓ OK' : '✗ OFFLINE') +
      this._svcRow('VESC R',        vescRCls,  data.vesc_r_ok ? '✓ OK' : '✗ OFFLINE') +
      this._svcRow('Teeces',        data.teeces_ready     ? 'ok' : 'dim', data.teeces_ready     ? '✓ OK' : '— N/A') +
      this._svcRow('Caméra',        data.camera_active    ? 'ok' : 'dim', data.camera_active    ? '✓ streaming' : '— idle') +
      this._svcRow('BT Gamepad',    btCls,     btVal) +
      this._svcRow('Servo Dôme',    data.dome_servo_ready ? 'ok' : 'dim', data.dome_servo_ready ? '✓ OK' : '— N/A') +
      this._svcRow('Servo Body',    data.servo_ready      ? 'ok' : 'dim', data.servo_ready      ? '✓ OK' : '— N/A');
  },

  _updateActivity(data) {
    const act = el('ck-activity');
    if (!act) return;
    const choreoVal = data.choreo_playing
      ? `<span class="cockpit-ok">▶ ${escapeHtml(data.choreo_name || '?')}</span>`
      : '<span class="cockpit-dim">— idle</span>';
    const audioVal = data.audio_playing
      ? `<span class="cockpit-ok">♪ ${escapeHtml(data.audio_current || '?')}</span>`
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
      `<div class="cockpit-row"><span class="cockpit-row-lbl">IP</span><span class="cockpit-row-val cockpit-ok">${window.location.hostname}</span></div>` +
      `<div class="cockpit-row"><span class="cockpit-row-lbl">Version</span><span class="cockpit-row-val cockpit-dim">v${escapeHtml(data.version || '?')}</span></div>`;
  },

  _updateAlerts(data) {
    const box = el('ck-alerts');
    if (!box) return;
    const alerts = this._buildAlerts(data);
    const hasAlert = alerts.some(a => a.cls !== 'ok');

    const panel = el('cockpit-panel');
    const btn   = el('cockpit-btn');
    if (panel) panel.classList.toggle('has-alert', hasAlert);
    if (btn)   btn.classList.toggle('alert', hasAlert);

    box.innerHTML = alerts.map(a =>
      `<span class="cockpit-alert ${a.cls}">${escapeHtml(a.msg)}</span>`
    ).join('');
  },

  _buildAlerts(data) {
    const alerts = [];
    const t = data.temperature;
    if (t != null) {
      if (t >= 75) alerts.push({ cls: 'err',  msg: `Pi ${t}°C — surchauffe` });
      else if (t >= 60) alerts.push({ cls: 'warn', msg: `Pi ${t}°C — surveiller` });
    }
    const vt = data.vesc_temp;
    if (vt != null && vt >= 70) alerts.push({ cls: 'err', msg: `VESC ${vt.toFixed(0)}°C — surchauffe` });
    else if (vt != null && vt >= 50) alerts.push({ cls: 'warn', msg: `VESC ${vt.toFixed(0)}°C — chaud` });

    const v = data.battery_voltage;
    if (v != null && batteryGauge.voltToColor(v) === '#ff2244')
      alerts.push({ cls: 'err',  msg: `Batterie critique ${v.toFixed(1)}V` });
    else if (v != null && batteryGauge.voltToColor(v) === '#ff8800')
      alerts.push({ cls: 'warn', msg: `Batterie faible ${v.toFixed(1)}V` });

    if (!data.vesc_l_ok) alerts.push({ cls: 'err',  msg: 'VESC L offline / fault' });
    if (!data.vesc_r_ok) alerts.push({ cls: 'err',  msg: 'VESC R offline / fault' });

    const rssi = data.bt_rssi;
    if (data.bt_connected && rssi != null && rssi <= -80)
      alerts.push({ cls: 'warn', msg: `BT signal faible ${rssi} dBm` });

    if ((data.uart_crc_errors ?? 0) > 0)
      alerts.push({ cls: 'warn', msg: `UART ${data.uart_crc_errors} CRC errors` });

    if (alerts.length === 0)
      alerts.push({ cls: 'ok', msg: '✓ Aucun problème détecté' });

    return alerts;
  },
};

// Close cockpit panel on click-away
document.addEventListener('click', (e) => {
  if (!cockpitPanel.isOpen) return;
  const panel = el('cockpit-panel');
  const btn   = el('cockpit-btn');
  if (panel && !panel.contains(e.target) && btn && !btn.contains(e.target))
    cockpitPanel.close();
});

// Close cockpit panel on Escape
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && cockpitPanel.isOpen) cockpitPanel.close();
});

```

- [ ] **Step 2: Hook cockpitPanel.update(data) into StatusPoller.poll()**

Find this block in `StatusPoller.poll()`:

```javascript
    // VESC tab has its own 500ms poll via _startVescTabPoll() — no refresh needed here
  }
```

Replace with:

```javascript
    // Cockpit panel — update if open
    if (cockpitPanel.isOpen) cockpitPanel.update(data);

    // VESC tab has its own 500ms poll via _startVescTabPoll() — no refresh needed here
  }
```

- [ ] **Step 3: Check alive_enabled is in /status**

`data.alive_enabled` is used in `_updateActivity()`. Verify it's exposed by `/status`:

```bash
curl -s http://192.168.2.104:5000/status | python -m json.tool | grep alive
```

If `alive_enabled` is NOT returned, add it to `status_bp.py` inside `get_status()`:

```python
'alive_enabled': _cfg.getboolean('behavior', 'alive_enabled', fallback=False),
```

Where `_cfg` is loaded as:
```python
import configparser as _cp
_cfg = _cp.ConfigParser()
_cfg.read(['/home/artoo/r2d2/master/config/main.cfg',
           '/home/artoo/r2d2/master/config/local.cfg'])
```

If `alive_enabled` IS returned already (check the behavior settings), skip this sub-step.

- [ ] **Step 4: Test in browser**

1. Open `http://192.168.2.104:5000`
2. Click **⬡ STATUS ▼** — panel slides down showing all 4 sections
3. Button becomes **⬡ STATUS ▲**
4. Click anywhere outside panel — closes
5. Press **Escape** — closes
6. Switch to AUDIO tab — click STATUS — panel still works
7. With bench mode OFF and no VESCs → VESC L/R should show ✗ OFFLINE + alert in panel

- [ ] **Step 5: Commit**

```bash
git add master/static/js/app.js master/api/status_bp.py
git commit -m "Feat: cockpitPanel JS — toggle, update, alerts, StatusPoller hook"
```

---

## Task 5: Deploy and verify

- [ ] **Step 1: Push and deploy**

```bash
git push
python -c "
import paramiko, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.2.104', username='artoo', password='deetoo', timeout=10)
stdin, stdout, stderr = c.exec_command('cd /home/artoo/r2d2 && bash scripts/update.sh 2>&1')
for line in stdout: print(line, end='')
c.close()
"
```

Expected: `✓ R2-D2 operational — version: <hash>`

- [ ] **Step 2: Final smoke test**

1. Open `http://192.168.2.104:5000` on phone and desktop simultaneously
2. STATUS button visible on both
3. Panel slides open/closed correctly
4. Vitaux show real values (battery, Pi temp, uptime)
5. Services show current state
6. Alerts section shows ✓ or real warnings
7. Panel is hidden on phone in portrait mode (test by rotating)

- [ ] **Step 3: Close beads issue**

```bash
bd close software-qep
```
