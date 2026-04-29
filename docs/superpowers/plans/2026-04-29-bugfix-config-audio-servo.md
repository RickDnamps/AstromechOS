# Bugfix: Atomic Config Writes, Audio Queue Worker, Servo Reload

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix three documented bugs — non-atomic config writes (software-k5z), audio Popen blocking the UART watchdog thread (software-2j2), and servo calibration angles not refreshed after save (software-fmf).

**Architecture:** Each fix is independent. Task 1 adds a shared atomic-write helper used by four blueprints. Task 2 moves `subprocess.Popen` out of the UART callback thread into a dedicated queue worker. Task 3 adds a `reload()` method to both servo drivers and wires it into the calibration save path.

**Tech Stack:** Python 3.11+, `queue.Queue`, `os.replace()` (POSIX atomic rename), `configparser`, `pytest`

---

## File Map

| File | Change |
|------|--------|
| `master/config/config_loader.py` | Add `write_cfg_atomic()` |
| `master/api/settings_bp.py` | `_write_key()` → use `write_cfg_atomic` |
| `master/api/vesc_bp.py` | `_save_vesc_cfg()` → use `write_cfg_atomic` |
| `master/api/servo_bp.py` | arms write + `_sync_angles_json` reload call |
| `master/api/behavior_bp.py` | `save_config()` → use `write_cfg_atomic` |
| `master/drivers/dome_servo_driver.py` | Add `reload()` |
| `slave/drivers/audio_driver.py` | Add `_launch_q` + `_launch_worker` thread |
| `slave/drivers/body_servo_driver.py` | Add `reload()`, handle `SRV:RELOAD` in `handle_uart` |
| `tests/test_bugfix_config_audio_servo.py` | New test file |

---

## Task 1 — Atomic config writes (software-k5z)

**Files:**
- Modify: `master/config/config_loader.py`
- Modify: `master/api/settings_bp.py:66-73`
- Modify: `master/api/vesc_bp.py:49-59`
- Modify: `master/api/servo_bp.py:399-411`
- Modify: `master/api/behavior_bp.py:117-120`
- Test: `tests/test_bugfix_config_audio_servo.py`

- [ ] **Step 1.1 — Write failing tests**

```python
# tests/test_bugfix_config_audio_servo.py
import configparser, os, tempfile, pytest
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from master.config.config_loader import write_cfg_atomic


class TestWriteCfgAtomic:
    def test_writes_key_to_file(self, tmp_path):
        cfg = configparser.ConfigParser()
        cfg.add_section('vesc')
        cfg.set('vesc', 'power_scale', '0.8')
        dest = tmp_path / 'local.cfg'
        write_cfg_atomic(cfg, str(dest))
        readback = configparser.ConfigParser()
        readback.read(str(dest))
        assert readback.get('vesc', 'power_scale') == '0.8'

    def test_no_tmp_file_left_after_success(self, tmp_path):
        cfg = configparser.ConfigParser()
        cfg.add_section('x')
        dest = tmp_path / 'local.cfg'
        write_cfg_atomic(cfg, str(dest))
        assert not os.path.exists(str(dest) + '.tmp')

    def test_original_untouched_if_replace_fails(self, tmp_path, monkeypatch):
        # Simulate crash between write and replace
        original_content = '[vesc]\npower_scale = 1.0\n'
        dest = tmp_path / 'local.cfg'
        dest.write_text(original_content, encoding='utf-8')
        def boom(src, dst): raise OSError("disk full")
        monkeypatch.setattr(os, 'replace', boom)
        cfg = configparser.ConfigParser()
        cfg.add_section('vesc')
        cfg.set('vesc', 'power_scale', '0.5')
        with pytest.raises(OSError):
            write_cfg_atomic(cfg, str(dest))
        # Original must be intact
        assert dest.read_text(encoding='utf-8') == original_content
```

- [ ] **Step 1.2 — Run tests to confirm they fail**

```
cd J:\R2-D2_Build\software
python -m pytest tests/test_bugfix_config_audio_servo.py::TestWriteCfgAtomic -v
```

Expected: `ERROR` — `ImportError: cannot import name 'write_cfg_atomic'`

- [ ] **Step 1.3 — Add `write_cfg_atomic` to config_loader.py**

In `master/config/config_loader.py`, add after the existing `is_auto_pull_enabled` function:

```python
def write_cfg_atomic(cfg: configparser.ConfigParser, path: str) -> None:
    """Writes cfg to path atomically using a .tmp file + os.replace().
    If the process crashes between write and replace, the original file
    is untouched. os.replace() is atomic on POSIX (rename syscall).
    """
    tmp = path + '.tmp'
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(tmp, 'w', encoding='utf-8') as f:
        cfg.write(f)
    os.replace(tmp, path)
```

Also add `import os` at the top if not already present (it is, at line 38).

- [ ] **Step 1.4 — Run tests to confirm they pass**

```
python -m pytest tests/test_bugfix_config_audio_servo.py::TestWriteCfgAtomic -v
```

Expected: 3 PASSED

- [ ] **Step 1.5 — Update `settings_bp._write_key()`**

In `master/api/settings_bp.py`, add import at top (after existing imports):

```python
from master.config.config_loader import write_cfg_atomic
```

Replace lines 66-73:

```python
def _write_key(section: str, key: str, value: str) -> None:
    """Writes or updates a key in local.cfg."""
    cfg = _read_cfg()
    if not cfg.has_section(section):
        cfg.add_section(section)
    cfg.set(section, key, value)
    write_cfg_atomic(cfg, LOCAL_CFG)
```

- [ ] **Step 1.6 — Update `vesc_bp._save_vesc_cfg()`**

In `master/api/vesc_bp.py`, add import after existing imports:

```python
from master.config.config_loader import write_cfg_atomic
```

Replace lines 49-59:

```python
def _save_vesc_cfg(**kwargs) -> None:
    """Persist one or more keys to local.cfg [vesc]."""
    cfg = configparser.ConfigParser()
    if os.path.exists(_LOCAL_CFG):
        cfg.read(_LOCAL_CFG)
    if not cfg.has_section('vesc'):
        cfg.add_section('vesc')
    for k, v in kwargs.items():
        cfg.set('vesc', k, str(v))
    write_cfg_atomic(cfg, _LOCAL_CFG)
```

- [ ] **Step 1.7 — Update `servo_bp` arms config write**

In `master/api/servo_bp.py`, add import after existing imports:

```python
from master.config.config_loader import write_cfg_atomic
```

Find the arms config write block (around line 399-411) and replace the `open(..., 'w')` call:

```python
    os.makedirs(os.path.dirname(_LOCAL_CFG), exist_ok=True)
    write_cfg_atomic(cfg, _LOCAL_CFG)
```

- [ ] **Step 1.8 — Update `behavior_bp.save_config()`**

In `master/api/behavior_bp.py`, add import after existing imports:

```python
from master.config.config_loader import write_cfg_atomic
```

Replace lines 117-120 (the `open(cfg_path, 'w')` block):

```python
        cfg_path = os.path.normpath(_CFG_PATH)
        write_cfg_atomic(parser, cfg_path)
        # Update in-memory config on the engine if available
        be = reg.behavior_engine
        if be:
            be._cfg.read(cfg_path)
```

- [ ] **Step 1.9 — Commit**

```bash
git add master/config/config_loader.py master/api/settings_bp.py master/api/vesc_bp.py master/api/servo_bp.py master/api/behavior_bp.py tests/test_bugfix_config_audio_servo.py
git commit -m "Fix: atomic local.cfg writes via write_cfg_atomic (software-k5z)"
```

---

## Task 2 — Audio queue worker decoupled from UART thread (software-2j2)

**Files:**
- Modify: `slave/drivers/audio_driver.py`
- Test: `tests/test_bugfix_config_audio_servo.py`

- [ ] **Step 2.1 — Write failing tests**

Append to `tests/test_bugfix_config_audio_servo.py`:

```python
import queue, threading, time
from unittest.mock import patch, MagicMock


class TestAudioQueueWorker:
    def _make_driver(self, tmp_path):
        import json
        sounds = tmp_path / 'sounds'
        sounds.mkdir()
        (sounds / 'Happy001.mp3').write_bytes(b'')
        index = {'categories': {'happy': ['Happy001']}}
        (sounds / 'sounds_index.json').write_text(json.dumps(index))
        sys.path.insert(0, str(tmp_path.parent))
        from slave.drivers.audio_driver import AudioDriver
        d = AudioDriver(sounds_dir=str(sounds))
        d.setup()
        return d

    def test_launch_returns_immediately(self, tmp_path):
        d = self._make_driver(tmp_path)
        popen_started = threading.Event()
        popen_done = threading.Event()

        original_popen = __import__('subprocess').Popen
        def slow_popen(*args, **kwargs):
            popen_started.set()
            time.sleep(0.2)   # simulate 200ms fork
            popen_done.set()
            return MagicMock(poll=lambda: None)

        with patch('subprocess.Popen', side_effect=slow_popen):
            t0 = time.monotonic()
            d.play('Happy001', channel=0)
            elapsed = time.monotonic() - t0

        # _launch() must return in <20ms even if Popen blocks for 200ms
        assert elapsed < 0.02, f"_launch blocked for {elapsed*1000:.0f}ms"
        # Popen must eventually be called
        assert popen_started.wait(timeout=1.0), "Popen never called"
        d.shutdown()

    def test_stop_drains_queue(self, tmp_path):
        d = self._make_driver(tmp_path)
        launched = []

        def tracking_popen(*args, **kwargs):
            launched.append(args[0])
            return MagicMock(poll=lambda: 0)

        with patch('subprocess.Popen', side_effect=tracking_popen):
            # Queue 3 plays then stop ch0 before worker processes them
            d._launch_q.put((0, '/fake/a.mp3', 32768))
            d._launch_q.put((0, '/fake/b.mp3', 32768))
            d.stop(0)
            time.sleep(0.1)

        # None of the ch0 items should have been launched
        ch0_launched = [a for a in launched if 'a.mp3' in a[-1] or 'b.mp3' in a[-1]]
        assert len(ch0_launched) == 0
        d.shutdown()
```

- [ ] **Step 2.2 — Run tests to confirm they fail**

```
python -m pytest tests/test_bugfix_config_audio_servo.py::TestAudioQueueWorker -v
```

Expected: FAIL — `test_launch_returns_immediately` fails because `_launch` currently blocks.

- [ ] **Step 2.3 — Refactor `audio_driver.py`**

Add `import queue` at the top (with other imports).

In `AudioDriver.__init__`, add after `self._lock = threading.Lock()`:

```python
        self._launch_q: queue.Queue = queue.Queue()
```

In `AudioDriver.setup()`, start the worker thread before `self._ready = True`:

```python
        threading.Thread(target=self._launch_worker, name="audio-launch", daemon=True).start()
        self._ready = True
```

Replace `AudioDriver.stop()` entirely:

```python
    def stop(self, channel: int | None = None) -> None:
        """Stops channel N, or all channels (channel=None).
        Also drains any pending launches for the stopped channels from the queue.
        """
        channels = set(range(self._channels)) if channel is None else {channel}
        # Drain queued-but-unstarted launches for these channels
        kept = []
        while True:
            try:
                kept.append(self._launch_q.get_nowait())
            except queue.Empty:
                break
        for item in kept:
            if item[0] not in channels:
                self._launch_q.put(item)
        # Terminate running processes
        with self._lock:
            for ch in channels:
                if 0 <= ch < len(self._procs):
                    proc = self._procs[ch]
                    if proc and proc.poll() is None:
                        proc.terminate()
                        log.debug("Sound stopped (ch%d)", ch)
                    self._procs[ch] = None
```

Replace `AudioDriver.shutdown()` entirely:

```python
    def shutdown(self) -> None:
        self._ready = False
        # Drain queue so the worker exits on next timeout
        while not self._launch_q.empty():
            try:
                self._launch_q.get_nowait()
            except queue.Empty:
                break
        self.stop()
```

Replace `AudioDriver._launch()` entirely:

```python
    def _launch(self, path: str, channel: int = 0, volume: int = 100) -> None:
        """Enqueues a play request. Returns immediately — Popen happens in worker thread."""
        scale = int(max(0, min(100, volume)) / 100 * 32768)
        self._launch_q.put((channel, path, scale))
        log.info("Audio ch%d vol%d%% queued: %s", channel, volume, os.path.basename(path))
```

Add new method `_launch_worker` after `_launch`:

```python
    def _launch_worker(self) -> None:
        """Worker thread: consumes the launch queue and calls subprocess.Popen.
        Runs as a daemon thread — never blocks the UART reader thread.
        """
        while self._ready or not self._launch_q.empty():
            try:
                channel, path, scale = self._launch_q.get(timeout=0.5)
            except queue.Empty:
                continue
            with self._lock:
                proc = self._procs[channel] if 0 <= channel < len(self._procs) else None
                if proc and proc.poll() is None:
                    proc.terminate()
                try:
                    new_proc = subprocess.Popen(
                        ['mpg123', '-q', '-f', str(scale), path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    self._procs[channel] = new_proc
                    log.info("Audio ch%d: %s", channel, os.path.basename(path))
                except FileNotFoundError:
                    log.error("mpg123 not found — sudo apt install -y mpg123")
                except Exception as e:
                    log.error("Audio launch error (ch%d): %s", channel, e)
```

- [ ] **Step 2.4 — Run tests to confirm they pass**

```
python -m pytest tests/test_bugfix_config_audio_servo.py::TestAudioQueueWorker -v
```

Expected: 2 PASSED

- [ ] **Step 2.5 — Commit**

```bash
git add slave/drivers/audio_driver.py tests/test_bugfix_config_audio_servo.py
git commit -m "Fix: audio Popen moved to queue worker, UART thread non-blocking (software-2j2)"
```

---

## Task 3 — Servo angles reload after calibration save (software-fmf)

**Files:**
- Modify: `master/drivers/dome_servo_driver.py`
- Modify: `slave/drivers/body_servo_driver.py`
- Modify: `master/api/servo_bp.py:170-186`
- Test: `tests/test_bugfix_config_audio_servo.py`

- [ ] **Step 3.1 — Write failing tests**

Append to `tests/test_bugfix_config_audio_servo.py`:

```python
import json


class TestServoReload:
    def test_dome_servo_reload(self, tmp_path):
        angles_file = tmp_path / 'dome_angles.json'
        angles_file.write_text(json.dumps({'Servo_M0': {'open': 90, 'close': 10, 'speed': 5}}))

        from master.drivers.dome_servo_driver import DomeServoDriver, _load_dome_angles
        import master.drivers.dome_servo_driver as mod
        mod.DOME_ANGLES_FILE = str(angles_file)

        d = DomeServoDriver()
        d._angles = _load_dome_angles()
        assert d._angles['Servo_M0']['open'] == 90

        # Update file on disk
        angles_file.write_text(json.dumps({'Servo_M0': {'open': 130, 'close': 10, 'speed': 5}}))

        d.reload()
        assert d._angles['Servo_M0']['open'] == 130

    def test_body_servo_reload(self, tmp_path):
        angles_file = tmp_path / 'servo_angles.json'
        angles_file.write_text(json.dumps({'Servo_S0': {'open': 80, 'close': 15, 'speed': 7}}))

        from slave.drivers.body_servo_driver import BodyServoDriver, _load_servo_angles
        import slave.drivers.body_servo_driver as mod
        mod.SERVO_ANGLES_FILE = str(angles_file)

        d = BodyServoDriver()
        d._angles = _load_servo_angles()
        assert d._angles['Servo_S0']['open'] == 80

        angles_file.write_text(json.dumps({'Servo_S0': {'open': 120, 'close': 15, 'speed': 7}}))
        d.reload()
        assert d._angles['Servo_S0']['open'] == 120

    def test_body_servo_uart_reload_command(self, tmp_path):
        angles_file = tmp_path / 'servo_angles.json'
        angles_file.write_text(json.dumps({'Servo_S0': {'open': 60, 'close': 10, 'speed': 5}}))

        from slave.drivers.body_servo_driver import BodyServoDriver
        import slave.drivers.body_servo_driver as mod
        mod.SERVO_ANGLES_FILE = str(angles_file)

        d = BodyServoDriver()
        d._angles = {'Servo_S0': {'open': 60, 'close': 10, 'speed': 5}}

        angles_file.write_text(json.dumps({'Servo_S0': {'open': 150, 'close': 10, 'speed': 5}}))
        d.handle_uart('RELOAD')
        assert d._angles['Servo_S0']['open'] == 150
```

- [ ] **Step 3.2 — Run tests to confirm they fail**

```
python -m pytest tests/test_bugfix_config_audio_servo.py::TestServoReload -v
```

Expected: FAIL — `AttributeError: 'DomeServoDriver' object has no attribute 'reload'`

- [ ] **Step 3.3 — Add `reload()` to `DomeServoDriver`**

In `master/drivers/dome_servo_driver.py`, add after the `is_ready()` method (after line 157):

```python
    def reload(self) -> None:
        """Reloads calibrated angles from dome_angles.json without restarting the driver."""
        self._angles = _load_dome_angles()
        log.info("DomeServoDriver: angles reloaded from disk (%d entries)", len(self._angles))
```

- [ ] **Step 3.4 — Add `reload()` and `SRV:RELOAD` handling to `BodyServoDriver`**

In `slave/drivers/body_servo_driver.py`, add after the `is_ready()` method:

```python
    def reload(self) -> None:
        """Reloads calibrated angles from servo_angles.json without restarting the driver."""
        self._angles = _load_servo_angles()
        log.info("BodyServoDriver: angles reloaded from disk (%d entries)", len(self._angles))
```

In `BodyServoDriver.handle_uart()` (around line 200), add a check at the top of the method:

```python
    def handle_uart(self, value: str) -> None:
        """Callback UART — SRV:NAME,ANGLE_DEG[,SPEED] or SRV:RELOAD"""
        if value == 'RELOAD':
            self.reload()
            return
        try:
            parts = value.split(',')
            speed = int(parts[2]) if len(parts) >= 3 else 10
            self._move_ramp(parts[0], float(parts[1]), speed)
        except (ValueError, IndexError) as e:
            log.error("Invalid SRV message %r: %s", value, e)
```

- [ ] **Step 3.5 — Wire reload into `servo_bp._sync_angles_json()`**

In `master/api/servo_bp.py`, update `_sync_angles_json()` to trigger reloads after writes. Add at the end of the function, after the `except Exception` block:

```python
def _sync_angles_json(panels: dict) -> None:
    """Writes dome_angles.json (Master) and servo_angles.json (Slave via scp).
    Notifies both drivers to reload angles immediately — no service restart needed.
    """
    import logging
    log = logging.getLogger(__name__)
    try:
        _update_angles_file(_DOME_ANGLES_FILE, panels, DOME_SERVOS)
        if reg.dome_servo and reg.dome_servo.is_ready():
            reg.dome_servo.reload()
    except Exception as e:
        log.warning("Failed to write dome_angles.json: %s", e)
    try:
        _update_angles_file(_SLAVE_ANGLES_FILE, panels, BODY_SERVOS)
        subprocess.run(
            ['scp', _SLAVE_ANGLES_FILE, f'{_SLAVE_HOST}:{_SLAVE_ANGLES_FILE}'],
            timeout=5, check=False, capture_output=True,
        )
        if reg.uart:
            reg.uart.send('SRV', 'RELOAD')
    except Exception as e:
        log.warning("Sync servo_angles.json to Slave failed: %s", e)
```

- [ ] **Step 3.6 — Run tests to confirm they pass**

```
python -m pytest tests/test_bugfix_config_audio_servo.py::TestServoReload -v
```

Expected: 3 PASSED

- [ ] **Step 3.7 — Run full test suite**

```
python -m pytest tests/ -v
```

Expected: all previously passing tests still pass + 8 new tests green.

- [ ] **Step 3.8 — Commit**

```bash
git add master/drivers/dome_servo_driver.py slave/drivers/body_servo_driver.py master/api/servo_bp.py tests/test_bugfix_config_audio_servo.py
git commit -m "Fix: servo angles reload on calibration save, no restart needed (software-fmf)"
```

---

## Task 4 — Close Beads issues + deploy

- [ ] **Step 4.1 — Close the three bugs**

```bash
bd close software-k5z software-2j2 software-fmf
```

- [ ] **Step 4.2 — Push and deploy**

```bash
git pull --rebase && git push
```

Then deploy to Pi:

```python
import paramiko, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.2.104', username='artoo', password='deetoo', timeout=10)
stdin, stdout, stderr = c.exec_command('cd /home/artoo/r2d2 && bash scripts/update.sh 2>&1')
for line in stdout: print(line, end='')
c.close()
```
