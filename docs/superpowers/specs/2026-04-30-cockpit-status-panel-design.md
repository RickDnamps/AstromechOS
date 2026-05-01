# Cockpit Status Panel — Design Spec

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a collapsible STATUS panel in the header that shows all R2-D2 system vitals in one glance, accessible from any tab without leaving it.

**Architecture:** A toggle button in the header opens/closes a dropdown panel rendered below the header bar, overlaying the active tab content. The panel reads from the existing `/status` endpoint (already polled every 2s by StatusPoller) — no new API endpoints needed. Panel state (open/closed) is not persisted.

**Tech Stack:** HTML/CSS/JS only — no new Python. Reuses `reg.*` data already exposed by `/status`.

---

## Placement

- New button `⬡ STATUS` added to the right side of the existing header, beside the HB/UART/BT pills
- Clicking toggles a panel that slides down below the header, overlaying the active tab
- Clicking again (or pressing Escape) closes the panel
- Button label changes: `STATUS ▼` when closed, `STATUS ▲` when open
- Button style: same pill style as HB/UART/BT, but slightly larger and always visible

## Panel Layout

The panel is divided into 4 sections rendered in a compact grid:

### Section 1 — Vitaux (4 cards, 1 row)
| Card | Value | Color logic |
|---|---|---|
| BATTERIE | voltage V + % (BatteryGauge.voltToPct) | green/orange/red via voltToColor |
| VESC L / R | temp L and temp R | green <50°C · orange <70°C · red ≥70°C |
| PI TEMP | CPU temperature °C | green <60°C · orange <75°C · red ≥75°C |
| UPTIME | hours + minutes | always dim white |

### Section 2 — Services (left column) + Activité + Réseau (right column)

**Services** — each row: label + ✓ OK (green) or ✗ (red) or ⚠ warning (orange):
- UART — `uart_ready` + `uart_health`
- VESC L / R — `vesc_l_ok` / `vesc_r_ok`
- Teeces — `teeces_ready`
- Caméra — `camera_active` (derived from `/camera/status`)
- BT Gamepad — `bt_connected` + RSSI level (green >-70dBm · orange ≤-70dBm)
- Servos Dôme / Body — `dome_servo_ready` / `servo_ready`

**Activité:**
- Choreo — name + progress bar if playing, "— idle" otherwise
- Audio — current track if playing, "— idle" otherwise
- ALIVE — ON (green) / OFF (dim)

**Réseau:**
- IP — `window.location.hostname` (already known client-side, no API call needed)
- Version — `data.version`
- Clients connectés — omit for now (requires new API endpoint, YAGNI)

### Section 3 — Alertes récentes

A list of active warnings derived from status data (no separate alert log needed):
- Pi temp ≥75°C → red alert
- Pi temp ≥60°C → orange warning
- VESC temp ≥70°C → red alert
- Battery voltage low (voltToColor === red) → red alert
- BT RSSI ≤ -80dBm → orange warning
- UART CRC errors > 0 → orange warning
- If no alerts → single green "✓ Aucun problème détecté"

## Behavior

- Panel refreshes on every StatusPoller tick (2s) while open — no extra polling
- Panel uses the same `data` object already passed around — zero duplicate fetches
- Escape key closes panel if open
- Clicking anywhere outside the panel closes it (click-away)
- Panel is not shown on mobile in portrait orientation (too small — pills in header suffice)
- Z-index above tab content, below any existing modals

## CSS

- New classes: `.cockpit-btn`, `.cockpit-panel`, `.cockpit-section`, `.cockpit-card`, `.cockpit-row`, `.cockpit-alert`
- Panel slides in with a `transform: translateY` + `opacity` transition (150ms ease-out)
- Panel background: `rgba(13, 13, 26, 0.97)` with `backdrop-filter: blur(8px)`
- Border: `1px solid rgba(0, 200, 100, 0.2)` (green tint — "all systems")
- Border changes to `rgba(255, 136, 0, 0.4)` if any orange/red alert is active

## Files Modified

- `master/templates/index.html` — add `.cockpit-btn` in header + `#cockpit-panel` div after header
- `master/static/js/app.js` — `cockpitPanel` object with `toggle()`, `update(data)`, `_buildAlerts(data)`; hook into StatusPoller
- `master/static/css/style.css` — all `.cockpit-*` styles + slide animation
