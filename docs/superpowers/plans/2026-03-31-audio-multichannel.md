# Audio Multi-Channel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand R2-D2 audio from 2 hardcoded channels to N configurable channels (default 6) with priority-based slot eviction in ChoreoPlayer and matching editor validation.

**Architecture:** `AudioDriver` (Slave) becomes N-slot, registering one UART callback per channel (`S:`, `S2:`, …`Sn:`). `ChoreoPlayer` (Master) owns a slot scheduler — it picks free slots, evicts Low/Normal on overflow, and never evicts High-priority sounds. Channel count is set via the web Config tab, written to `local.cfg` + SCPed to `slave/config/slave.cfg`, and takes effect after an auto service restart.

**Tech Stack:** Python 3.10 (configparser, threading.Timer), Flask Blueprint, vanilla JS, mpg123 (Slave audio backend)

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `slave/drivers/audio_driver.py` | Modify | Dynamic N-slot pool, `make_channel_handler()` |
| `slave/config/slave.cfg` | Create | Slave-side config (audio_channels = 6) |
| `slave/main.py` | Modify | Read slave.cfg, register N UART callbacks dynamically |
| `master/choreo_player.py` | Modify | Audio slot scheduler + priority eviction + timer lifecycle |
| `master/api/settings_bp.py` | Modify | Expose + save `audio.channels`, SCP slave.cfg, restart services |
| `master/templates/index.html` | Modify | Audio Channels card in Config tab + compatibility banner in CHOREO tab |
| `master/static/js/app.js` | Modify | loadSettings + saveAudioChannels + inspector priority picker + overflow validation |

---

### Task 1: AudioDriver — Dynamic N-slot pool

**Files:**
- Modify: `slave/drivers/audio_driver.py`

- [ ] **Step 1: Update `__init__` to accept `channels` param and build dynamic `_procs`**

Replace the constructor in `slave/drivers/audio_driver.py`:

```python
class AudioDriver(BaseDriver):
    def __init__(self, sounds_dir: str = _SOUNDS_DIR, channels: int = 6):
        self._sounds_dir = os.path.abspath(sounds_dir)
        self._index: dict[str, list[str]] = {}
        self._channels = channels
        self._procs: list[subprocess.Popen | None] = [None] * channels
        self._lock = threading.Lock()
        self._ready = False
```

- [ ] **Step 2: Add `make_channel_handler()` method**

Add after `handle_uart2`:

```python
    def make_channel_handler(self, ch: int):
        """Returns a UART callback closure routing to channel ch."""
        def handler(value: str):
            self._handle_channel(value, ch)
        return handler
```

- [ ] **Step 3: Update `play()` to validate channel range**

Replace the `play()` method:

```python
    def play(self, filename: str, channel: int = 0) -> bool:
        """Plays an MP3 file by name (without extension) on the given channel."""
        if not filename or any(c in filename for c in ('/', '\\', '..')):
            log.warning(f"Audio filename rejected (path traversal): {filename!r}")
            return False
        if not (0 <= channel < self._channels):
            log.warning(f"Audio channel {channel} out of range (0–{self._channels - 1})")
            return False
        path = os.path.join(self._sounds_dir, filename + '.mp3')
        if not os.path.isfile(path):
            log.warning(f"Sound not found: {path}")
            return False
        self._launch(path, channel)
        return True
```

- [ ] **Step 4: Update `stop()` to use `self._channels`**

Replace the `stop()` method:

```python
    def stop(self, channel: int | None = None) -> None:
        """Stops channel N, or all channels (channel=None)."""
        channels = list(range(self._channels)) if channel is None else [channel]
        with self._lock:
            for ch in channels:
                if 0 <= ch < len(self._procs):
                    proc = self._procs[ch]
                    if proc and proc.poll() is None:
                        proc.terminate()
                        log.debug(f"Sound stopped (ch{ch})")
                    self._procs[ch] = None
```

- [ ] **Step 5: Update docstring at top of file**

Replace the module docstring lines:

```
Slave audio driver — N-channel polyphony (configurable, default 6).
Plays MP3 sounds via mpg123 (native 3.5mm jack Pi 4B).
N independent channels run simultaneously.

UART commands (n = channel index, n=0 → 'S:', n=1 → 'S2:', n=2 → 'S3:', etc.):
  S:Happy001          → channel 0: play specific file
  S:RANDOM:happy      → channel 0: play random from category
  S:STOP              → channel 0: stop
  S2:Happy001         → channel 1 (and so on for S3:, S4: …)
```

- [ ] **Step 6: Verify manually**

```python
# Quick sanity check — run on dev machine (no Pi needed)
from slave.drivers.audio_driver import AudioDriver
import os; os.environ.setdefault('PYTHONPATH', '.')
a = AudioDriver(channels=4)
assert len(a._procs) == 4
h = a.make_channel_handler(2)
assert callable(h)
print("AudioDriver N-slot OK")
```

- [ ] **Step 7: Commit**

```bash
git add slave/drivers/audio_driver.py
git commit -m "Feat: AudioDriver N-slot pool + make_channel_handler (audio multichannel)"
```

---

### Task 2: slave.cfg + slave/main.py dynamic callback registration

**Files:**
- Create: `slave/config/slave.cfg`
- Modify: `slave/main.py`

- [ ] **Step 1: Create `slave/config/slave.cfg`**

```ini
[audio]
audio_channels = 6
```

- [ ] **Step 2: Add config reader function in `slave/main.py`**

Add after the imports, before `UART_PORT`:

```python
import configparser

_SLAVE_CFG = '/home/artoo/r2d2/slave/config/slave.cfg'

def _read_audio_channels() -> int:
    """Reads audio_channels from slave.cfg. Defaults to 6 if absent."""
    cfg = configparser.ConfigParser()
    try:
        cfg.read(_SLAVE_CFG)
    except Exception:
        pass
    return cfg.getint('audio', 'audio_channels', fallback=6)
```

- [ ] **Step 3: Update the Audio init block in `main()` to register N callbacks dynamically**

Replace this block in `main()`:

```python
# BEFORE:
    display.boot_item('AUDIO')
    audio = AudioDriver()
    if audio.setup():
        uart.register_callback('S',   audio.handle_uart)
        uart.register_callback('S2',  audio.handle_uart2)
        uart.register_callback('VOL', audio.handle_volume)
        display.boot_ok('AUDIO')
    else:
        log.warning("AudioDriver unavailable — audio disabled")
        display.boot_fail('AUDIO')
```

```python
# AFTER:
    display.boot_item('AUDIO')
    _audio_channels = _read_audio_channels()
    audio = AudioDriver(channels=_audio_channels)
    if audio.setup():
        for _i in range(_audio_channels):
            _msg_type = 'S' if _i == 0 else f'S{_i + 1}'
            uart.register_callback(_msg_type, audio.make_channel_handler(_i))
        uart.register_callback('VOL', audio.handle_volume)
        log.info("Audio: %d channels registered (S: … S%d:)", _audio_channels, _audio_channels)
        display.boot_ok('AUDIO')
    else:
        log.warning("AudioDriver unavailable — audio disabled")
        display.boot_fail('AUDIO')
```

- [ ] **Step 4: Verify the slave.cfg file is in the right place**

```bash
cat slave/config/slave.cfg
# Expected: [audio]\naudio_channels = 6
```

- [ ] **Step 5: Commit**

```bash
git add slave/config/slave.cfg slave/main.py
git commit -m "Feat: slave.cfg + dynamic audio callback registration (audio multichannel)"
```

---

### Task 3: ChoreoPlayer — slot scheduler with priority eviction

**Files:**
- Modify: `master/choreo_player.py`

- [ ] **Step 1: Add `_audio_channels`, `_audio_slots`, `_audio_timers` to `__init__`**

In `ChoreoPlayer.__init__`, after the `_body_uart_lat` block, add:

```python
        # Audio slot scheduler
        self._audio_channels: int = (
            cfg.getint('audio', 'audio_channels', fallback=6) if cfg is not None else 6
        )
        self._audio_slots: list[dict | None]           = [None] * self._audio_channels
        self._audio_timers: list[threading.Timer | None] = [None] * self._audio_channels
```

- [ ] **Step 2: Reset slots in `play()` before starting**

In `play()`, before `self._stop_flag.clear()`, add:

```python
        self._audio_slots  = [None] * self._audio_channels
        self._audio_timers = [None] * self._audio_channels
```

- [ ] **Step 3: Add `_release_slot()` and `_assign_audio_slot()` methods**

Add these two private methods anywhere before `_dispatch`:

```python
    def _release_slot(self, i: int) -> None:
        """Cancel the release timer and mark slot i as free."""
        if 0 <= i < len(self._audio_timers) and self._audio_timers[i]:
            self._audio_timers[i].cancel()
            self._audio_timers[i] = None
        if 0 <= i < len(self._audio_slots):
            self._audio_slots[i] = None

    def _assign_audio_slot(self, priority: str) -> int | None:
        """
        Return a free slot index, evicting the best candidate if necessary.
        Eviction order: low (oldest first) → normal (oldest first) → never high.
        Returns None if all slots are high-priority (new sound will be dropped).
        """
        # 1. Free slot
        for i, s in enumerate(self._audio_slots):
            if s is None:
                return i
        # 2. Evict by priority
        for evict_pri in ('low', 'normal'):
            candidates = [
                (i, s) for i, s in enumerate(self._audio_slots)
                if s is not None and s['priority'] == evict_pri
            ]
            if candidates:
                i, _ = min(candidates, key=lambda x: x[1]['started_at'])
                cmd = 'S' if i == 0 else f'S{i + 1}'
                if self._audio:
                    self._audio.send(cmd, 'STOP')
                self._release_slot(i)
                return i
        # 3. All high — drop
        log.warning(
            "ChoreoPlayer: all %d audio slots are High-priority — sound dropped",
            self._audio_channels,
        )
        return None
```

- [ ] **Step 4: Rewrite the `audio` block inside `_dispatch()`**

Find and replace the entire `if track == 'audio':` block in `_dispatch()`:

```python
            if track == 'audio':
                if not self._audio:
                    return
                if ev['action'] == 'play':
                    priority = ev.get('priority', 'normal').lower()
                    slot = self._assign_audio_slot(priority)
                    if slot is None:
                        return  # all slots High — sound dropped
                    cmd = 'S' if slot == 0 else f'S{slot + 1}'
                    self._audio.send(cmd, ev.get('file', ''))
                    duration = ev.get('duration')
                    self._audio_slots[slot] = {
                        'sound':      ev.get('file', ''),
                        'started_at': time.monotonic(),
                        'priority':   priority,
                        'duration':   duration,
                    }
                    if duration:
                        t = threading.Timer(float(duration), self._release_slot, args=(slot,))
                        t.daemon = True
                        self._audio_timers[slot] = t
                        t.start()
                elif ev['action'] == 'stop':
                    file_to_stop = ev.get('file')
                    for i, s in enumerate(self._audio_slots):
                        if s is None:
                            continue
                        if file_to_stop is None or s['sound'] == file_to_stop:
                            cmd = 'S' if i == 0 else f'S{i + 1}'
                            self._audio.send(cmd, 'STOP')
                            self._release_slot(i)
```

- [ ] **Step 5: Update `_safe_stop_all()` to stop all N channels and cancel all timers**

Replace these lines in `_safe_stop_all()`:

```python
        # BEFORE:
        lambda: self._audio.send('S', 'STOP') if self._audio else None,
        lambda: self._audio.send('S2', 'STOP') if self._audio else None,
```

```python
        # AFTER — stop all N channels, then cancel timers + reset slots
        *[
            (lambda cmd=('S' if i == 0 else f'S{i+1}'): self._audio.send(cmd, 'STOP') if self._audio else None)
            for i in range(self._audio_channels)
        ],
        lambda: [self._release_slot(i) for i in range(self._audio_channels)],
```

- [ ] **Step 6: Add compatibility warning in `play()`**

In `play()`, right after the `if self.is_playing():` guard:

```python
        meta = chor.get('meta', {})
        required = meta.get('audio_channels_required', 0)
        if required > self._audio_channels:
            log.warning(
                "Choreo '%s' requires %d audio channels but system has %d — some sounds may be dropped.",
                meta.get('name', '?'), required, self._audio_channels,
            )
```

- [ ] **Step 7: Verify imports — `threading` and `time` are already imported at top of file**

```bash
grep -n "^import threading\|^import time" master/choreo_player.py
# Expected: both present on lines 7-9
```

- [ ] **Step 8: Commit**

```bash
git add master/choreo_player.py
git commit -m "Feat: ChoreoPlayer audio slot scheduler + priority eviction (audio multichannel)"
```

---

### Task 4: settings_bp.py — expose + save audio_channels via web UI

**Files:**
- Modify: `master/api/settings_bp.py`

- [ ] **Step 1: Add `_sync_audio_channels()` helper function**

Add this function after `_reload_lights_driver()` in `settings_bp.py`:

```python
def _sync_audio_channels(channels: int) -> None:
    """
    Write audio_channels to slave/config/slave.cfg locally,
    SCP it to the Slave, then restart both services (delayed to let
    the HTTP response complete first).
    """
    slave_cfg_path = '/home/artoo/r2d2/slave/config/slave.cfg'
    slave_host     = 'artoo@r2-slave.local'

    # Write slave.cfg on Master filesystem
    slave_cfg = configparser.ConfigParser()
    if os.path.exists(slave_cfg_path):
        slave_cfg.read(slave_cfg_path)
    if not slave_cfg.has_section('audio'):
        slave_cfg.add_section('audio')
    slave_cfg.set('audio', 'audio_channels', str(channels))
    try:
        os.makedirs(os.path.dirname(slave_cfg_path), exist_ok=True)
        with open(slave_cfg_path, 'w') as f:
            slave_cfg.write(f)
        log.info("slave.cfg written: audio_channels=%d", channels)
    except Exception as e:
        log.warning("Failed to write slave.cfg: %s", e)

    # SCP to Slave
    try:
        subprocess.run(
            ['scp', slave_cfg_path, f'{slave_host}:{slave_cfg_path}'],
            timeout=8, check=False, capture_output=True,
        )
        log.info("slave.cfg synced to Slave")
    except Exception as e:
        log.warning("Failed to SCP slave.cfg: %s", e)

    # Delayed restart (2s) — lets the HTTP response reach the client first
    def _delayed_restart():
        import time as _time
        _time.sleep(2)
        subprocess.run(['sudo', 'systemctl', 'restart', 'r2d2-slave'], check=False)
        _time.sleep(1)
        subprocess.run(['sudo', 'systemctl', 'restart', 'r2d2-master'], check=False)

    import threading as _threading
    _threading.Thread(target=_delayed_restart, daemon=True).start()
    log.info("Services scheduled to restart in 2s (audio_channels=%d)", channels)
```

- [ ] **Step 2: Add `audio.channels` to `GET /settings` response**

In `get_settings()`, add to the returned dict:

```python
        'audio': {
            'channels': cfg.getint('audio', 'audio_channels', fallback=6),
        },
```

- [ ] **Step 3: Add `audio.channels` to `set_config()` allowed set and handle it**

In `set_config()`, update `allowed`:

```python
    allowed = {
        'github.branch', 'github.auto_pull_on_boot',
        'slave.host', 'deploy.button_pin',
        'lights.backend',
        'audio.channels',
    }
```

After the `for dotkey, value in data.items():` loop, add:

```python
    if 'audio.channels' in updated:
        try:
            channels = max(1, min(12, int(data.get('audio.channels', 6))))
            _sync_audio_channels(channels)
        except (ValueError, TypeError) as e:
            log.warning("Invalid audio.channels value: %s", e)

    return jsonify({'status': 'ok', 'updated': updated})
```

- [ ] **Step 4: Verify the response manually (on Pi or via curl)**

```bash
curl -s http://192.168.2.104:5000/settings | python3 -m json.tool | grep -A3 '"audio"'
# Expected:
# "audio": {
#     "channels": 6
# }
```

- [ ] **Step 5: Commit**

```bash
git add master/api/settings_bp.py
git commit -m "Feat: settings API exposes + saves audio_channels, syncs slave.cfg + restarts services"
```

---

### Task 5: Config tab — Audio Channels UI card

**Files:**
- Modify: `master/templates/index.html`
- Modify: `master/static/js/app.js`

- [ ] **Step 1: Add the Audio Channels card to the Config tab in index.html**

In `index.html`, after the `<!-- Lights Backend -->` section (after the closing `</section>` of that card):

```html
    <!-- Audio Channels -->
    <section class="card settings-card">
      <h2 class="card-title">AUDIO CHANNELS</h2>
      <p class="settings-note">Number of simultaneous sounds R2-D2 can play (default: 6, max: 12).<br>Applies to CHOREO timeline. Requires service restart.</p>
      <div class="form-group">
        <label>Channels</label>
        <input type="number" id="audio-channels" class="input-text"
               min="1" max="12" value="6" style="width:80px">
      </div>
      <button class="btn btn-warn" onclick="saveAudioChannels()">APPLY + RESTART SERVICES</button>
      <div class="settings-status" id="audio-channels-status"></div>
    </section>
```

- [ ] **Step 2: Populate the field in `loadSettings()` in app.js**

In `loadSettings()`, after the `if (data.lights)` block:

```javascript
  if (data.audio) {
    const inp = el('audio-channels');
    if (inp) inp.value = data.audio.channels ?? 6;
    _audioChannelsConfig = data.audio.channels ?? 6;
  }
```

- [ ] **Step 3: Add `_audioChannelsConfig` module-level variable in app.js**

Near the top of the Settings section (around line 2694), add:

```javascript
let _audioChannelsConfig = 6;  // loaded from GET /settings, used by CHOREO validation
```

- [ ] **Step 4: Add `saveAudioChannels()` function in app.js**

After `saveLightsBackend()`:

```javascript
async function saveAudioChannels() {
  const channels = parseInt(el('audio-channels')?.value) || 6;
  if (channels < 1 || channels > 12) { toast('Channels must be between 1 and 12', 'error'); return; }
  const status = el('audio-channels-status');
  if (status) { status.textContent = 'Applying…'; status.className = 'settings-status'; }
  const data = await api('/settings/config', 'POST', { 'audio.channels': channels });
  if (data?.status === 'ok') {
    _audioChannelsConfig = channels;
    toast(`Audio channels: ${channels} — services restarting`, 'ok');
    if (status) {
      status.textContent = `Set to ${channels} — reconnecting in ~5s…`;
      status.className = 'settings-status ok';
    }
  } else {
    toast('Failed to update audio channels', 'error');
    if (status) { status.textContent = 'Error'; status.className = 'settings-status error'; }
  }
}
```

- [ ] **Step 5: Commit**

```bash
git add master/templates/index.html master/static/js/app.js
git commit -m "Feat: Config tab — Audio Channels card + saveAudioChannels()"
```

---

### Task 6: CHOREO inspector — priority picker + overflow validation + compatibility banner

**Files:**
- Modify: `master/templates/index.html`
- Modify: `master/static/js/app.js`

- [ ] **Step 1: Add the compatibility banner HTML to the CHOREO tab**

In `index.html`, find the `<div class="tab-content" id="tab-choreo">` section. Add this banner as the first child inside the tab div (before the timeline container):

```html
  <div id="chor-audio-banner" style="display:none;background:rgba(255,180,0,.15);border:1px solid rgba(255,180,0,.4);border-radius:4px;padding:6px 10px;margin-bottom:8px;font-size:10px;color:#ffb400;letter-spacing:.05em"></div>
```

- [ ] **Step 2: Add the priority picker to the audio inspector in `_updatePropsPanel()` in app.js**

In the `if (track === 'audio')` block inside `_updatePropsPanel()`, after the `CHANNEL` selectRow line:

```javascript
      html += selectRow('PRIORITY', 'priority', {
        'high':   '🔒 HIGH — never evicted',
        'normal': 'NORMAL (default)',
        'low':    '▽ LOW — evicted first',
      });
```

- [ ] **Step 3: Add `_audioOverflowIdxs` module-level Set and `_validateAudioOverflow()` function**

Add near the CHOREO module state variables (search for `let _chor =` to find the right spot):

```javascript
let _audioOverflowIdxs = new Set();  // indices of audio events that will be dropped

function _validateAudioOverflow() {
  if (!_chor) return;
  const events = (_chor.tracks.audio || []).filter(e => e.action === 'play' && e.duration > 0);

  // Collect all time boundary points (start + end of every event)
  const timepoints = new Set();
  events.forEach(e => {
    timepoints.add(e.t);
    timepoints.add(e.t + (e.duration || 0));
  });

  // Peak simultaneous events (all priorities)
  let peak = 0;
  timepoints.forEach(tp => {
    const count = events.filter(e => e.t <= tp && (e.t + (e.duration || 0)) > tp).length;
    if (count > peak) peak = count;
  });
  if (_chor.meta) _chor.meta.audio_channels_required = peak || 0;

  // Flag overflow: events where more than N overlap at any point
  const overflow = new Set();
  timepoints.forEach(tp => {
    const active = events.filter(e => e.t <= tp && (e.t + (e.duration || 0)) > tp);
    if (active.length > _audioChannelsConfig) {
      // Sort by start time — events added later (higher t) are the ones dropped
      const sorted = [...active].sort((a, b) => a.t - b.t);
      sorted.slice(_audioChannelsConfig).forEach(e => {
        const idx = (_chor.tracks.audio || []).indexOf(e);
        if (idx >= 0) overflow.add(idx);
      });
    }
  });
  _audioOverflowIdxs = overflow;

  // Update banner
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

  // Trigger redraw so overflow badges appear on blocks
  _redraw();
}
```

- [ ] **Step 4: Call `_validateAudioOverflow()` when audio events change**

Find `_onFieldChange` in app.js and add a call when the track is `'audio'`:

```javascript
  _onFieldChange(track, idx, field, value) {
    if (track === 'audio') _validateAudioOverflow();
    // ... existing logic
  },
```

Also call it when an audio block is added or deleted. Find the block add and delete handlers and add `_validateAudioOverflow()` after modifying `_chor.tracks.audio`.

- [ ] **Step 5: Add overflow badge to audio block rendering**

Find where audio blocks are drawn on the timeline (search for `chor-block` class assignment or the block div creation for `track === 'audio'`). Add a visual indicator when the block index is in `_audioOverflowIdxs`:

In the block render, after setting the block's class or text content, add:

```javascript
// When rendering each audio block at index `blockIdx`:
if (track === 'audio' && _audioOverflowIdxs.has(blockIdx)) {
  blockEl.style.outline = '1px solid #ff4444';
  blockEl.title = 'May be dropped — all audio slots full at this timestamp';
}
```

- [ ] **Step 6: Call `_validateAudioOverflow()` when a choreo is loaded**

Find where `_chor` is assigned after loading (search for `_chor =` assignment in the load callback) and add:

```javascript
_validateAudioOverflow();
```

- [ ] **Step 7: Update `save()` to ensure `audio_channels_required` is computed before saving**

In the `save()` function:

```javascript
    async save() {
      if (!_chor) return;
      _validateAudioOverflow();  // ensure meta.audio_channels_required is up to date
      const result = await api('/choreo/save', 'POST', { chor: _chor });
      if (result) { _dirty = false; toast(`Saved: ${_chor.meta.name}`, 'ok'); }
    },
```

- [ ] **Step 8: Commit**

```bash
git add master/templates/index.html master/static/js/app.js
git commit -m "Feat: CHOREO priority picker + overflow validation + compatibility banner"
```

---

### Task 7: Sync Android assets + final deploy

**Files:**
- Modify: `android/app/src/main/assets/js/app.js`
- Modify: `android/app/src/main/assets/css/style.css` (if style.css was touched)

- [ ] **Step 1: Sync app.js to Android assets**

```bash
cp master/static/js/app.js android/app/src/main/assets/js/app.js
```

- [ ] **Step 2: Update CLAUDE.md — audio_channels config note**

In `CLAUDE.md`, under the `⚙️ Instructions Claude Code` or config section, add:

```markdown
**Audio channels** — configurable in Config tab (web UI) → writes `master/config/local.cfg` `[audio] audio_channels` + SCPs `slave/config/slave.cfg` + restarts services.
Default: 6. Range: 1–12.
```

- [ ] **Step 3: Final commit + push**

```bash
git add android/app/src/main/assets/js/app.js CLAUDE.md
git commit -m "Feat: audio multi-channel complete — N slots, priority eviction, Config UI, CHOREO validation"
git push
```

- [ ] **Step 4: Deploy to Pi**

```python
import paramiko, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.2.104', username='artoo', password='deetoo', timeout=10)
stdin, stdout, stderr = c.exec_command('cd /home/artoo/r2d2 && bash scripts/update.sh 2>&1')
for line in stdout: print(line, end='')
c.close()
```

Expected: `✓ R2-D2 operational — version: <hash>`

---

## Self-Review

### Spec Coverage

| Spec requirement | Task |
|---|---|
| N configurable channels, default 6 | Task 1 + 2 |
| slave.cfg for Slave-side config | Task 2 |
| Web UI Config tab to change channels | Task 5 |
| SCP slave.cfg + service restart on save | Task 4 |
| ChoreoPlayer slot scheduler | Task 3 |
| Priority levels: high / normal / low | Task 3 |
| Eviction: low → normal → never high | Task 3 |
| Timer-based slot release | Task 3 |
| Timer cancelled on eviction + stop() | Task 3 |
| Compatibility warning in play() log | Task 3 |
| `audio_channels_required` in .chor meta | Task 6 |
| Inspector priority picker | Task 6 |
| Overflow validation (red badge) | Task 6 |
| Compatibility banner in CHOREO tab | Task 6 |
| Backward compat (no priority = normal) | Task 3 (default in `ev.get('priority', 'normal')`) |
| All High + new event → drop + WARNING | Task 3 (`_assign_audio_slot`) |

All requirements covered. No gaps.

### Type Consistency

- `_release_slot(i: int)` — defined Task 3 Step 3, used Task 3 Steps 4, 5. ✓
- `_assign_audio_slot(priority: str) -> int | None` — defined Task 3 Step 3, used Task 3 Step 4. ✓
- `make_channel_handler(ch: int)` — defined Task 1 Step 2, called Task 2 Step 3. ✓
- `_audioChannelsConfig` — declared Task 5 Step 3, set in `loadSettings` Task 5 Step 2, read in `_validateAudioOverflow` Task 6 Step 3. ✓
- `_validateAudioOverflow()` — defined Task 6 Step 3, called Steps 4, 6, 7. ✓
- UART cmd convention: `'S' if slot == 0 else f'S{slot + 1}'` — used consistently in Task 3 Steps 3, 4, 5 and Task 2 Step 3. ✓
