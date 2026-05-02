# Choreo Servo & VESC Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Choreo files store servo hardware IDs (`Servo_M0`) + a `servo_label` documentation field; the editor warns visually when servo labels or VESC invert config don't match the current machine config, so users can't accidentally run a wrong Choreo and damage hardware.

**Architecture:**
- `choreo_player.py` gets a label→ID fallback resolver so old Choreos (with label-based refs like `dome_panel_1`) still work at playback time.
- `app.js` `load()` migrates legacy label refs in-memory, builds a `_servoIssues` map (⚠️ label mismatch / ❌ ID unknown), and shows a VESC-invert banner if the file's snapshot disagrees with current config.
- `app.js` `save()` auto-refreshes `servo_label` from live config and writes a `config_snapshot` into `meta`.
- Timeline block renderer adds a small badge to flagged items so the user sees exactly which blocks need attention.

**Tech Stack:** Python 3, Flask, vanilla JS (no bundler), JSON `.chor` files, `dome_angles.json` / `servo_angles.json`.

---

## File Map

| File | Change |
|---|---|
| `master/choreo_player.py` | Add `_build_label_map()` + label fallback in servo dispatch |
| `master/static/js/app.js` | `load()`: migration + validation; `save()`: label refresh + snapshot; block renderer: badges; VESC banner |
| `android/app/src/main/assets/js/app.js` | Sync from master after app.js changes |
| `master/choreographies/*.chor` | Auto-migrated in-memory on load + re-saved by user (no script needed) |

---

## Task 1 — `choreo_player.py`: Label→ID fallback resolver

**Files:**
- Modify: `master/choreo_player.py`

### Context

Currently, `dome_servo_driver.py:292` does `if name not in SERVO_MAP: log.warning(...)` and returns `False`. Old Choreos store servo names as labels (`dome_panel_1`, `body_panel_2`). These silently fail at playback. The fix: build a reverse map (normalised label → hardware ID) from the angles config files and use it as a fallback before giving up.

- `dome_angles.json` → `{ "Servo_M0": { "label": "Dome_Panel_1", ... }, ... }`
- `slave/config/servo_angles.json` → same structure for `Servo_S*`

- [ ] **Step 1: Add `_build_label_map()` to `choreo_player.py`**

Add after the existing imports, before the `ChoreoPlayer` class:

```python
import re as _re

_DOME_ANGLES_PATH = '/home/artoo/r2d2/master/config/dome_angles.json'
_BODY_ANGLES_PATH = '/home/artoo/r2d2/slave/config/servo_angles.json'


def _normalise_label(s: str) -> str:
    """Lower-case, replace spaces/hyphens with underscores."""
    return _re.sub(r'[\s\-]+', '_', s.strip().lower())


def _build_label_map() -> dict[str, str]:
    """
    Returns { normalised_label -> servo_id } for all configured servos.
    Used to resolve legacy label-based Choreo references.
    """
    result: dict[str, str] = {}
    for path in (_DOME_ANGLES_PATH, _BODY_ANGLES_PATH):
        try:
            import json as _json
            with open(path) as f:
                data = _json.load(f)
            for servo_id, cfg in data.items():
                label = cfg.get('label', '')
                if label:
                    result[_normalise_label(label)] = servo_id
                # Also map the ID itself so both forms resolve
                result[_normalise_label(servo_id)] = servo_id
        except Exception:
            pass
    return result
```

- [ ] **Step 2: Load label map at `ChoreoPlayer.__init__`**

In `__init__`, after `self._engine = engine`, add:

```python
        self._label_map: dict[str, str] = _build_label_map()
```

- [ ] **Step 3: Add `_resolve_servo_id()` helper method**

Add inside the `ChoreoPlayer` class, near the top of the internal section:

```python
    def _resolve_servo_id(self, name: str) -> str:
        """
        Resolve a servo reference to a hardware ID.
        Accepts: hardware ID ('Servo_M0'), normalised label ('dome_panel_1'),
                 or special keywords ('all', 'all_dome', 'all_body').
        Returns the hardware ID, or the original string if unresolvable.
        """
        _SPECIAL = ('all', 'all_dome', 'all_body')
        if name in _SPECIAL:
            return name
        # Already a hardware ID?
        from master.drivers.dome_servo_driver import SERVO_MAP as _DOME_MAP
        try:
            from slave.drivers.body_servo_driver import SERVO_CHANNELS as _BODY_MAP
        except Exception:
            _BODY_MAP = {}
        if name in _DOME_MAP or name in _BODY_MAP:
            return name
        # Try label lookup
        resolved = self._label_map.get(_normalise_label(name))
        if resolved:
            log.info("ChoreoPlayer: resolved servo label %r → %r", name, resolved)
            return resolved
        log.warning("ChoreoPlayer: unknown servo ref %r — label map has no match", name)
        return name
```

- [ ] **Step 4: Apply `_resolve_servo_id()` in the servo dispatch section**

In `choreo_player.py`, find the servo event dispatch block (around line 440 where `servo = ev.get('servo', '')`). Replace:

```python
                servo   = ev.get('servo', '')
```

With:

```python
                servo   = self._resolve_servo_id(ev.get('servo', ''))
```

- [ ] **Step 5: Verify the import path for `SERVO_MAP`**

Check `master/drivers/dome_servo_driver.py` to confirm `SERVO_MAP` is module-level. If the import path `master.drivers.dome_servo_driver` doesn't work in the Pi's PYTHONPATH context, use a try/except with a hardcoded fallback set:

```python
    def _resolve_servo_id(self, name: str) -> str:
        _SPECIAL = ('all', 'all_dome', 'all_body')
        if name in _SPECIAL:
            return name
        try:
            from master.drivers.dome_servo_driver import SERVO_MAP as _DOME_MAP
        except ImportError:
            _DOME_MAP = {f'Servo_M{i}': i for i in range(11)}
        try:
            from slave.drivers.body_servo_driver import SERVO_CHANNELS as _BODY_MAP
        except ImportError:
            _BODY_MAP = {f'Servo_S{i}': i for i in range(11)}
        if name in _DOME_MAP or name in _BODY_MAP:
            return name
        resolved = self._label_map.get(_normalise_label(name))
        if resolved:
            log.info("ChoreoPlayer: resolved servo label %r → %r", name, resolved)
            return resolved
        log.warning("ChoreoPlayer: unknown servo ref %r — label map has no match", name)
        return name
```

- [ ] **Step 6: Commit**

```bash
git add master/choreo_player.py
git commit -m "Fix: ChoreoPlayer resolves legacy label-based servo refs to hardware IDs"
```

---

## Task 2 — `app.js` load(): Migrate legacy refs + build `_servoIssues`

**Files:**
- Modify: `master/static/js/app.js` — `load()` function (~line 4745)

### Context

Legacy Choreos store servo names as labels (`dome_panel_1`). The inspector already uses hardware IDs as values in the dropdown (line 4418). We need to:
1. On load, upgrade any `item.servo` that looks like a label to a hardware ID (using `_servoSettings` reverse lookup).
2. Build `_servoIssues` — a map of `"track:idx"` → `'warn'|'error'` for display.

A `servo` ref is considered a label (not an ID) if it doesn't match `/^Servo_[MS]\d+$/` and isn't a special keyword.

- [ ] **Step 1: Add `_servoIssues` state variable**

Near the other state variables at the top of the `choreoEditor` IIFE (~line 3590):

```javascript
  let _servoIssues  = {};  // { 'dome_servos:0': 'warn'|'error', … }
```

- [ ] **Step 2: Add `_buildLabelToId()` helper**

Add inside the `choreoEditor` IIFE, near the other helpers:

```javascript
  // Build reverse map: normalised_label → servo_id from _servoSettings
  // e.g. { 'dome_panel_1': 'Servo_M0', 'front_arm': 'Servo_S3' }
  function _buildLabelToId() {
    const map = {};
    for (const [id, cfg] of Object.entries(_servoSettings)) {
      if (cfg.label) map[cfg.label.toLowerCase().replace(/[\s\-]+/g, '_')] = id;
      map[id.toLowerCase()] = id;  // also accept 'servo_m0' → 'Servo_M0'
    }
    return map;
  }
```

- [ ] **Step 3: Add `_migrateLegacyServoRefs()` helper**

```javascript
  const _SERVO_SPECIAL = new Set(['all', 'all_dome', 'all_body']);
  const _SERVO_ID_RE   = /^Servo_[MS]\d+$/;

  // Upgrade label-based servo refs to hardware IDs in-place.
  // Returns true if any migration was done (caller should mark _dirty).
  function _migrateLegacyServoRefs() {
    const labelToId = _buildLabelToId();
    let migrated = false;
    for (const track of ['dome_servos', 'body_servos', 'arm_servos']) {
      for (const ev of (_chor.tracks[track] || [])) {
        if (!ev.servo || _SERVO_SPECIAL.has(ev.servo) || _SERVO_ID_RE.test(ev.servo)) continue;
        const norm   = ev.servo.toLowerCase().replace(/[\s\-]+/g, '_');
        const found  = labelToId[norm];
        if (found) {
          log.debug?.(`Choreo migrate: ${ev.servo} → ${found}`);
          ev.servo_label = _servoSettings[found]?.label || ev.servo;
          ev.servo       = found;
          migrated       = true;
        }
      }
    }
    return migrated;
  }
```

- [ ] **Step 4: Add `_validateServoRefs()` helper**

```javascript
  // Build _servoIssues map after migration.
  // ⚠️ warn  = servo ID valid, but servo_label doesn't match current label (renamed)
  // ❌ error = servo ID not in _servoSettings at all
  function _validateServoRefs() {
    _servoIssues = {};
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
```

- [ ] **Step 5: Call migration + validation in `load()` after `_chor = chor`**

Inside the `load()` function, after the existing normalize/migrate steps (after line 4775 `_dirty = false;`), add:

```javascript
      // Migrate legacy label-based servo refs → hardware IDs
      if (_migrateLegacyServoRefs()) {
        _dirty = true;
        toast('Servo refs migrated to hardware IDs — save to confirm', 'warn');
      }
      // Validate servo refs against current config
      _validateServoRefs();
```

- [ ] **Step 6: Commit**

```bash
git add master/static/js/app.js
git commit -m "Feat: Choreo load() migrates legacy servo label refs and builds validation map"
```

---

## Task 3 — `app.js`: Visual ⚠️/❌ badges on timeline blocks

**Files:**
- Modify: `master/static/js/app.js` — `_renderTrack()` / block HTML builder

### Context

Find where servo track blocks are rendered (look for `chor-block` and `data-track` in `_renderTrack`). We'll inject a small badge span when `_servoIssues` has an entry for that block.

- [ ] **Step 1: Locate the block-render HTML builder**

Search for the function that generates `.chor-block` HTML. It will be something like:

```javascript
function _renderBlock(track, idx, ev) { ... }
```

or inline inside `_renderTrack`. Find the line that builds the block's innerHTML/outerHTML.

- [ ] **Step 2: Inject the issue badge**

In the block HTML builder, after computing `label` for the block, add the badge:

```javascript
    const issueKey   = `${track}:${idx}`;
    const issueLevel = _servoIssues[issueKey];
    const issueBadge = issueLevel === 'error'
      ? '<span class="chor-issue-badge error" title="Servo ID not found in config">❌</span>'
      : issueLevel === 'warn'
      ? '<span class="chor-issue-badge warn"  title="Servo label changed since creation — verify intent">⚠️</span>'
      : '';
```

And include `${issueBadge}` in the block's HTML output, after the label span.

- [ ] **Step 3: Add CSS for `.chor-issue-badge`**

In `master/static/css/style.css`, find the `.chor-block` section and add:

```css
.chor-issue-badge {
  position: absolute;
  top: 1px;
  right: 2px;
  font-size: 9px;
  line-height: 1;
  pointer-events: none;
}
.chor-issue-badge.error { color: var(--red, #ff2244); }
.chor-issue-badge.warn  { color: var(--orange, #ff8800); }
```

- [ ] **Step 4: Re-run `_validateServoRefs()` after inspector changes**

In `_onFieldChange()`, when `field === 'servo'`, re-validate and re-render that track:

```javascript
  function _onFieldChange(track, idx, field, value) {
    if (track === 'audio') _validateAudioOverflow();
    // Re-validate servo issues when servo assignment changes
    if ((track === 'dome_servos' || track === 'body_servos' || track === 'arm_servos') && field === 'servo') {
      // Auto-refresh servo_label from current config
      const settings = _servoSettings[value];
      if (settings?.label) {
        const item = (_chor.tracks[track] || [])[idx];
        if (item) item.servo_label = settings.label;
      }
      _validateServoRefs();
      _renderTrack(track);
    }
    if (track !== 'audio' || field !== 'file' || !value) return;
    // ... rest of existing audio duration logic
```

- [ ] **Step 5: Commit**

```bash
git add master/static/js/app.js master/static/css/style.css
git commit -m "Feat: Choreo timeline shows warning/error badges on servo blocks with config mismatches"
```

---

## Task 4 — `app.js` save(): Auto-refresh `servo_label` + write VESC snapshot

**Files:**
- Modify: `master/static/js/app.js` — `save()` function (~line 4831)

- [ ] **Step 1: Add `_refreshServoLabels()` helper**

```javascript
  // Before saving: refresh servo_label for every servo event from current config.
  // This keeps the label field as documentation, always matching the last-known name.
  function _refreshServoLabels() {
    for (const track of ['dome_servos', 'body_servos', 'arm_servos']) {
      for (const ev of (_chor.tracks[track] || [])) {
        if (!ev.servo || _SERVO_SPECIAL.has(ev.servo)) continue;
        const current = _servoSettings[ev.servo];
        if (current?.label) ev.servo_label = current.label;
      }
    }
  }
```

- [ ] **Step 2: Fetch VESC config at init and cache it**

Near the other cached state at the top of `choreoEditor`:

```javascript
  let _vescCfgSnapshot = null;  // { invert_L, invert_R, power_scale } — loaded at init
```

In the `init()` function (or the Promise.all block that loads servo lists), add:

```javascript
        api('/vesc/config').then(r => { if (r) _vescCfgSnapshot = r; }),
```

- [ ] **Step 3: Modify `save()` to refresh labels + write snapshot**

Replace the existing `save()`:

```javascript
    async save() {
      if (!_chor) return;
      _validateAudioOverflow();
      _refreshServoLabels();
      // Write VESC config snapshot for portability validation
      if (_vescCfgSnapshot) {
        _chor.meta.config_snapshot = {
          vesc_invert_L:    _vescCfgSnapshot.invert_L   ?? false,
          vesc_invert_R:    _vescCfgSnapshot.invert_R   ?? false,
          vesc_power_scale: _vescCfgSnapshot.power_scale ?? 1.0,
        };
      }
      const result = await api('/choreo/save', 'POST', { chor: _chor });
      if (result) {
        _dirty = false;
        _validateServoRefs();   // badges may change after label refresh
        toast(`Saved: ${_chor.meta.name}`, 'ok');
      }
    },
```

- [ ] **Step 4: Commit**

```bash
git add master/static/js/app.js
git commit -m "Feat: Choreo save() refreshes servo_label and writes VESC config snapshot to meta"
```

---

## Task 5 — `app.js` load(): VESC invert mismatch banner

**Files:**
- Modify: `master/static/js/app.js` — `load()` function
- Modify: `master/templates/index.html` — add banner element (or build it dynamically)

### Context

If the Choreo's `meta.config_snapshot.vesc_invert_L` or `vesc_invert_R` differ from the current machine's VESC config, show a red warning banner above the timeline. `power_scale` mismatch is a softer warning (orange). The user dismisses the banner; it doesn't block playback.

- [ ] **Step 1: Add `_showVescMismatchBanner()` helper**

```javascript
  function _showVescMismatchBanner(snapshot) {
    const existing = document.getElementById('chor-vesc-banner');
    if (existing) existing.remove();
    if (!_vescCfgSnapshot || !snapshot) return;

    const invertMismatch = snapshot.vesc_invert_L !== _vescCfgSnapshot.invert_L
                        || snapshot.vesc_invert_R !== _vescCfgSnapshot.invert_R;
    const scaleMismatch  = Math.abs((snapshot.vesc_power_scale ?? 1) - (_vescCfgSnapshot.power_scale ?? 1)) > 0.05;

    if (!invertMismatch && !scaleMismatch) return;

    const lines = [];
    if (invertMismatch) {
      lines.push(`⚠️ Motor direction mismatch — Choreo: L=${snapshot.vesc_invert_L ? 'INV' : 'FWD'} R=${snapshot.vesc_invert_R ? 'INV' : 'FWD'} | Current: L=${_vescCfgSnapshot.invert_L ? 'INV' : 'FWD'} R=${_vescCfgSnapshot.invert_R ? 'INV' : 'FWD'}`);
    }
    if (scaleMismatch) {
      lines.push(`ℹ️ Power scale: was ${((snapshot.vesc_power_scale ?? 1) * 100).toFixed(0)}%, now ${((_vescCfgSnapshot.power_scale ?? 1) * 100).toFixed(0)}%`);
    }

    const banner = document.createElement('div');
    banner.id = 'chor-vesc-banner';
    banner.style.cssText = invertMismatch
      ? 'background:#3a0010;border:1px solid #ff2244;color:#ff6688;padding:6px 10px;margin:4px 0;font-size:11px;border-radius:3px;display:flex;justify-content:space-between;align-items:center'
      : 'background:#2a1a00;border:1px solid #ff8800;color:#ffaa44;padding:6px 10px;margin:4px 0;font-size:11px;border-radius:3px;display:flex;justify-content:space-between;align-items:center';
    banner.innerHTML = `<span>${lines.join(' &nbsp;|&nbsp; ')}</span><button onclick="this.parentElement.remove()" style="background:none;border:none;color:inherit;cursor:pointer;font-size:13px;padding:0 4px">✕</button>`;

    const timeline = document.getElementById('chor-scroll') || document.getElementById('chor-editor');
    if (timeline) timeline.parentElement?.insertBefore(banner, timeline);
  }
```

- [ ] **Step 2: Call banner in `load()` after validation**

After the `_validateServoRefs()` call added in Task 2, add:

```javascript
      // Show VESC config mismatch banner if snapshot exists
      _showVescMismatchBanner(_chor.meta?.config_snapshot);
```

- [ ] **Step 3: Clear banner on new load**

At the start of `load()`, after `if (!name) return;`, add:

```javascript
      const oldBanner = document.getElementById('chor-vesc-banner');
      if (oldBanner) oldBanner.remove();
```

- [ ] **Step 4: Commit**

```bash
git add master/static/js/app.js
git commit -m "Feat: Choreo shows VESC invert/power-scale mismatch banner on load"
```

---

## Task 6 — Sync Android + deploy + end-to-end verification

**Files:**
- `android/app/src/main/assets/js/app.js` — sync from master

- [ ] **Step 1: Sync app.js to Android**

```bash
cp master/static/js/app.js android/app/src/main/assets/js/app.js
```

- [ ] **Step 2: Deploy to Pi**

```python
import paramiko, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.2.104', username='artoo', password='deetoo', timeout=10)
stdin, stdout, stderr = c.exec_command('cd /home/artoo/r2d2 && bash scripts/update.sh 2>&1')
for line in stdout: print(line, end='')
c.close()
```

- [ ] **Step 3: Manual verification checklist**

1. **Load `my_show2.chor`** (has old labels `dome_panel_1`, `body_panel_1`)
   - Expected: toast "Servo refs migrated to hardware IDs — save to confirm"
   - Expected: `_dirty = true` (save button enabled)
   - Expected: no ⚠️/❌ badges if labels still match current config
2. **Save** — reopen file, verify `"servo": "Servo_M0"` and `"servo_label": "Dome_Panel_1"` in JSON
3. **Rename a servo** in Config tab (e.g., Servo_M0 → "New Name")
   - Reload Choreo → ⚠️ badge on that block (label mismatch)
   - Open inspector → see dropdown, change to correct servo → badge disappears
4. **VESC mismatch banner**: flip invert_L in VESC tab, reload a Choreo with a snapshot → red banner appears
5. **Play `my_show2.chor`** → verify dome servo actually moves (was silently failing before)

- [ ] **Step 4: Final commit**

```bash
git add master/static/js/app.js android/app/src/main/assets/js/app.js
git commit -m "Sync: Android assets — choreo servo/VESC validation complete"
git push
```

---

## Spec Coverage Check

| Requirement | Task |
|---|---|
| Choreo stores hardware ID + `servo_label` | T4 save() + T2 migration |
| Timeline displays current label (live from config) | T2 already works — `_servoSettings[id]?.label` was already used in block labels |
| On save: `servo_label` auto-refreshed | T4 `_refreshServoLabels()` |
| On load: legacy label refs migrated to IDs | T2 `_migrateLegacyServoRefs()` |
| ⚠️ badge = ID valid, label changed since creation | T3 |
| ❌ badge = ID not found in config | T3 |
| Changing servo in inspector clears badge | T3 `_onFieldChange()` |
| VESC invert mismatch → red banner | T5 |
| VESC power_scale mismatch → orange banner | T5 |
| `choreo_player.py` resolves old label refs at playback | T1 |
| Migration of existing `.chor` files | T2 (in-memory on load, committed when user saves) |
