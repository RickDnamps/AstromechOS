# ChoreoPlayer — VESC Telemetry & Fail-Safe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add UART fail-safe detection and VESC telemetry threshold monitoring to `ChoreoPlayer`, exposing live data via `get_status()` and aborting the choreography (audio + lights + servos + propulsion) on UART loss or hardware overload.

**Architecture:** Inject a `telem_getter` callable into `ChoreoPlayer.__init__`; the run loop reads telemetry every 500ms and checks voltage/temp/current against configurable thresholds. Propulsion dispatch tracks consecutive `drive()` failures; 3 consecutive failures trigger an UART-loss abort. All aborts set a single `abort_reason` field persisted in `get_status()`.

**Tech Stack:** Python 3.10, `threading.Event`, `configparser`, `pytest`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `master/config/main.cfg` | Modify | Add threshold keys to existing `[choreo]` section |
| `master/choreo_player.py` | Modify | Add `telem_getter`, threshold config, fail counters, `_check_telem()`, enrich `get_status()` |
| `tests/test_choreo_player.py` | Modify | Add tests for UART fail-safe + 3 threshold aborts + status enrichment |

---

## Task 1 — Add threshold config keys to `main.cfg`

**Files:**
- Modify: `master/config/main.cfg`

- [ ] **Step 1: Add threshold keys to the `[choreo]` section**

  Current `[choreo]` section:
  ```ini
  [choreo]
  audio_latency = 0.10
  ```

  Replace with:
  ```ini
  [choreo]
  audio_latency           = 0.10
  telem_check_interval    = 0.5
  uart_fail_threshold     = 3
  vesc_min_voltage        = 20.0
  vesc_max_temp           = 80.0
  vesc_max_current        = 30.0
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add master/config/main.cfg
  git commit -m "Config: choreo — VESC telemetry thresholds (20V/80C/30A) + uart_fail_threshold"
  ```

---

## Task 2 — Constructor: `telem_getter` + state variables

**Files:**
- Modify: `master/choreo_player.py`
- Test: `tests/test_choreo_player.py`

- [ ] **Step 1: Write failing tests**

  Add to the bottom of `tests/test_choreo_player.py`:

  ```python
  # ── Telemetry getter injection ─────────────────────────────────────────────────

  import configparser

  def _make_cfg(**overrides):
      """ConfigParser with test-friendly choreo defaults."""
      cfg = configparser.ConfigParser()
      cfg['choreo'] = {
          'audio_latency':        '0.0',
          'telem_check_interval': '0.5',
          'uart_fail_threshold':  '3',
          'vesc_min_voltage':     '20.0',
          'vesc_max_temp':        '80.0',
          'vesc_max_current':     '30.0',
          **{k: str(v) for k, v in overrides.items()},
      }
      return cfg


  def test_telem_getter_stored():
      getter = lambda: {'L': None, 'R': None}
      player = ChoreoPlayer(
          cfg=None, audio=None, teeces=None,
          dome_motor=None, dome_servo=None, body_servo=None,
          telem_getter=getter,
      )
      assert player._telem_getter is getter


  def test_threshold_defaults_when_cfg_none():
      player = ChoreoPlayer(
          cfg=None, audio=None, teeces=None,
          dome_motor=None, dome_servo=None, body_servo=None,
      )
      assert player._vesc_min_voltage  == pytest.approx(20.0)
      assert player._vesc_max_temp     == pytest.approx(80.0)
      assert player._vesc_max_current  == pytest.approx(30.0)
      assert player._uart_fail_threshold == 3
      assert player._telem_check_interval == pytest.approx(0.5)


  def test_threshold_read_from_cfg():
      cfg = _make_cfg(vesc_min_voltage='18.0', vesc_max_temp='70.0', vesc_max_current='25.0')
      player = ChoreoPlayer(
          cfg=cfg, audio=None, teeces=None,
          dome_motor=None, dome_servo=None, body_servo=None,
      )
      assert player._vesc_min_voltage  == pytest.approx(18.0)
      assert player._vesc_max_temp     == pytest.approx(70.0)
      assert player._vesc_max_current  == pytest.approx(25.0)


  def test_get_status_has_abort_reason_and_telem_fields():
      player = _make_player()
      status = player.get_status()
      assert 'abort_reason' in status
      assert 'telem' in status
      assert status['abort_reason'] is None
      assert status['telem'] is None
  ```

- [ ] **Step 2: Run tests to verify they fail**

  ```bash
  cd J:/R2-D2_Build/software
  python -m pytest tests/test_choreo_player.py::test_telem_getter_stored tests/test_choreo_player.py::test_threshold_defaults_when_cfg_none tests/test_choreo_player.py::test_threshold_read_from_cfg tests/test_choreo_player.py::test_get_status_has_abort_reason_and_telem_fields -v
  ```

  Expected: 4 × FAILED (AttributeError or KeyError)

- [ ] **Step 3: Implement — update `__init__` and `_status` in `choreo_player.py`**

  Replace the `__init__` signature and body (lines 58–83 of current file):

  ```python
  def __init__(self, cfg, audio, teeces, dome_motor, dome_servo,
               body_servo, vesc=None, telem_getter=None, audio_latency=None):
      # Resolve audio latency: explicit arg > cfg > default
      if audio_latency is not None:
          self._latency = float(audio_latency)
      elif cfg is not None:
          self._latency = cfg.getfloat('choreo', 'audio_latency', fallback=0.10)
      else:
          self._latency = 0.10

      self._audio      = audio
      self._teeces     = teeces
      self._dome_motor = dome_motor
      self._dome_servo = dome_servo
      self._body_servo = body_servo
      self._vesc       = vesc
      self._telem_getter = telem_getter

      # Threshold config
      if cfg is not None:
          self._telem_check_interval = cfg.getfloat('choreo', 'telem_check_interval', fallback=0.5)
          self._uart_fail_threshold  = cfg.getint('choreo',   'uart_fail_threshold',  fallback=3)
          self._vesc_min_voltage     = cfg.getfloat('choreo', 'vesc_min_voltage',     fallback=20.0)
          self._vesc_max_temp        = cfg.getfloat('choreo', 'vesc_max_temp',        fallback=80.0)
          self._vesc_max_current     = cfg.getfloat('choreo', 'vesc_max_current',     fallback=30.0)
      else:
          self._telem_check_interval = 0.5
          self._uart_fail_threshold  = 3
          self._vesc_min_voltage     = 20.0
          self._vesc_max_temp        = 80.0
          self._vesc_max_current     = 30.0

      # Runtime state — reset on each play()
      self._drive_fail_count: int       = 0
      self._abort_reason: str | None    = None
      self._last_telem: dict | None     = None
      self._last_telem_check: float     = 0.0

      self._stop_flag  = threading.Event()
      self._thread: threading.Thread | None = None
      self._status_lock = threading.Lock()
      self._status = {
          'playing':      False,
          'name':         None,
          't_now':        0.0,
          'duration':     0.0,
          'abort_reason': None,
          'telem':        None,
      }
  ```

- [ ] **Step 4: Run tests to verify they pass**

  ```bash
  python -m pytest tests/test_choreo_player.py::test_telem_getter_stored tests/test_choreo_player.py::test_threshold_defaults_when_cfg_none tests/test_choreo_player.py::test_threshold_read_from_cfg tests/test_choreo_player.py::test_get_status_has_abort_reason_and_telem_fields -v
  ```

  Expected: 4 × PASSED

- [ ] **Step 5: Run the full existing test suite to confirm no regressions**

  ```bash
  python -m pytest tests/test_choreo_player.py -v
  ```

  Expected: all previously passing tests still PASS

- [ ] **Step 6: Commit**

  ```bash
  git add master/choreo_player.py tests/test_choreo_player.py
  git commit -m "Feat: choreo — telem_getter + threshold config + abort_reason/telem in status"
  ```

---

## Task 3 — UART fail-safe: track consecutive `drive()` failures

**Files:**
- Modify: `master/choreo_player.py`
- Modify: `tests/test_choreo_player.py`

- [ ] **Step 1: Write failing tests**

  Add to `tests/test_choreo_player.py`:

  ```python
  # ── UART fail-safe ─────────────────────────────────────────────────────────────

  class _FailVesc:
      """Mock VESC whose drive() always returns False."""
      def drive(self, l, r): return False
      def stop(self): pass


  class _OkVesc:
      """Mock VESC whose drive() always returns True."""
      def drive(self, l, r): return True
      def stop(self): pass


  def _chor_with_propulsion(events_list, duration=5.0):
      """Minimal .chor dict with the given propulsion events."""
      return {
          'meta': {'name': 'uart_test', 'duration': duration},
          'tracks': {
              'audio': [], 'lights': [], 'dome': [],
              'servos': [], 'markers': [],
              'propulsion': events_list,
          },
      }


  def test_uart_failsafe_aborts_after_threshold():
      """3 consecutive drive() False → abort_reason='uart_loss'."""
      player = ChoreoPlayer(
          cfg=None, audio=None, teeces=None,
          dome_motor=None, dome_servo=None, body_servo=None,
          vesc=_FailVesc(), audio_latency=0.0,
      )
      chor = _chor_with_propulsion([
          {'t': 0.00, 'left': 0.3, 'right': 0.3},
          {'t': 0.05, 'left': 0.3, 'right': 0.3},
          {'t': 0.10, 'left': 0.3, 'right': 0.3},
      ])
      player.play(chor)
      player._thread.join(timeout=2.0)

      assert not player.is_playing()
      assert player.get_status()['abort_reason'] == 'uart_loss'


  def test_uart_failsafe_resets_counter_on_success():
      """2 failures then 1 success resets counter — no abort."""
      call_count = {'n': 0}

      class _FlakyVesc:
          def drive(self, l, r):
              call_count['n'] += 1
              return call_count['n'] != 1 and call_count['n'] != 2  # fail on calls 1+2, succeed on 3+
          def stop(self): pass

      player = ChoreoPlayer(
          cfg=None, audio=None, teeces=None,
          dome_motor=None, dome_servo=None, body_servo=None,
          vesc=_FlakyVesc(), audio_latency=0.0,
      )
      chor = _chor_with_propulsion([
          {'t': 0.00, 'left': 0.3, 'right': 0.3},
          {'t': 0.05, 'left': 0.3, 'right': 0.3},
          {'t': 0.10, 'left': 0.3, 'right': 0.3},
      ], duration=0.3)
      player.play(chor)
      player._thread.join(timeout=2.0)

      # Choreo ran to completion (duration 0.3s), not aborted
      assert player.get_status()['abort_reason'] is None


  def test_abort_reason_resets_on_next_play():
      """abort_reason from previous run is cleared on play()."""
      player = ChoreoPlayer(
          cfg=None, audio=None, teeces=None,
          dome_motor=None, dome_servo=None, body_servo=None,
          vesc=_FailVesc(), audio_latency=0.0,
      )
      chor = _chor_with_propulsion([
          {'t': 0.00, 'left': 0.3, 'right': 0.3},
          {'t': 0.05, 'left': 0.3, 'right': 0.3},
          {'t': 0.10, 'left': 0.3, 'right': 0.3},
      ])
      player.play(chor)
      player._thread.join(timeout=2.0)
      assert player.get_status()['abort_reason'] == 'uart_loss'

      # Second play with a working VESC
      player._vesc = _OkVesc()
      chor2 = _chor_with_propulsion([], duration=0.1)
      player.play(chor2)
      player._thread.join(timeout=2.0)
      assert player.get_status()['abort_reason'] is None
  ```

- [ ] **Step 2: Run tests to verify they fail**

  ```bash
  python -m pytest tests/test_choreo_player.py::test_uart_failsafe_aborts_after_threshold tests/test_choreo_player.py::test_uart_failsafe_resets_counter_on_success tests/test_choreo_player.py::test_abort_reason_resets_on_next_play -v
  ```

  Expected: 3 × FAILED

- [ ] **Step 3: Implement — update `play()`, `_dispatch()`, and end-of-run status**

  **a) Update `play()` to reset state (add 4 lines before `self._stop_flag.clear()`):**

  ```python
  def play(self, chor: dict) -> bool:
      """Start playback of a chor dict. Returns False if already playing."""
      if self.is_playing():
          log.warning("ChoreoPlayer: already playing, stop first")
          return False
      self._drive_fail_count = 0
      self._abort_reason     = None
      self._last_telem       = None
      self._last_telem_check = 0.0
      self._stop_flag.clear()
      self._thread = threading.Thread(
          target=self._run, args=(chor,),
          daemon=True, name="choreo-player",
      )
      self._thread.start()
      log.info(f"Choreo started: {chor['meta']['name']}")
      return True
  ```

  **b) Replace the `propulsion` branch in `_dispatch()` (currently lines 269–278):**

  ```python
  elif track == 'propulsion':
      if not self._vesc:
          return
      if ev.get('action') == 'stop':
          self._vesc.drive(0.0, 0.0)
          self._drive_fail_count = 0
      else:
          ok = self._vesc.drive(
              float(ev.get('left', 0.0)),
              float(ev.get('right', 0.0)),
          )
          if ok:
              self._drive_fail_count = 0
          else:
              self._drive_fail_count += 1
              if self._drive_fail_count >= self._uart_fail_threshold:
                  log.error(
                      f"ChoreoPlayer: UART lost — {self._drive_fail_count} consecutive "
                      f"failures — ABORT [{self._status.get('name')}]"
                  )
                  self._abort_reason = 'uart_loss'
                  self._stop_flag.set()
  ```

  **c) Update the final status block at the end of `_run()` (currently `self._status.update({'playing': False, 't_now': 0.0})`):**

  ```python
  with self._status_lock:
      self._status.update({
          'playing':      False,
          't_now':        0.0,
          'abort_reason': self._abort_reason,
          'telem':        self._last_telem,
      })
  ```

  Apply the same update to the final `with self._status_lock:` block in `_run()` (after `self._safe_stop_all()`).

- [ ] **Step 4: Run tests to verify they pass**

  ```bash
  python -m pytest tests/test_choreo_player.py::test_uart_failsafe_aborts_after_threshold tests/test_choreo_player.py::test_uart_failsafe_resets_counter_on_success tests/test_choreo_player.py::test_abort_reason_resets_on_next_play -v
  ```

  Expected: 3 × PASSED

- [ ] **Step 5: Full suite regression check**

  ```bash
  python -m pytest tests/test_choreo_player.py -v
  ```

  Expected: all tests PASS

- [ ] **Step 6: Commit**

  ```bash
  git add master/choreo_player.py tests/test_choreo_player.py
  git commit -m "Feat: choreo — UART fail-safe (3 consecutive drive() failures → abort uart_loss)"
  ```

---

## Task 4 — Telemetry threshold monitoring

**Files:**
- Modify: `master/choreo_player.py`
- Modify: `tests/test_choreo_player.py`

- [ ] **Step 1: Write failing tests**

  Add to `tests/test_choreo_player.py`:

  ```python
  # ── Telemetry threshold monitoring ────────────────────────────────────────────

  def _player_with_telem(telem_data, **cfg_overrides):
      """Player with telem_getter returning fixed data, telem_check_interval=0 for speed."""
      cfg = _make_cfg(telem_check_interval='0.0', **cfg_overrides)
      getter = lambda: telem_data
      return ChoreoPlayer(
          cfg=cfg, audio=None, teeces=None,
          dome_motor=None, dome_servo=None, body_servo=None,
          telem_getter=getter, audio_latency=0.0,
      )


  def _short_chor(duration=2.0):
      """Minimal chor with no propulsion (so drive failures don't interfere)."""
      return {
          'meta': {'name': 'telem_test', 'duration': duration},
          'tracks': {
              'audio': [], 'lights': [], 'dome': [],
              'servos': [], 'propulsion': [], 'markers': [],
          },
      }


  def test_undervoltage_aborts_choreo():
      telem = {'L': {'v_in': 15.0, 'temp': 40.0, 'current': 5.0, 'rpm': 0, 'duty': 0.0, 'fault': 0},
               'R': None}
      player = _player_with_telem(telem)
      player.play(_short_chor())
      player._thread.join(timeout=2.0)

      assert not player.is_playing()
      assert player.get_status()['abort_reason'] == 'undervoltage'


  def test_overheat_aborts_choreo():
      telem = {'L': None,
               'R': {'v_in': 25.0, 'temp': 95.0, 'current': 5.0, 'rpm': 0, 'duty': 0.0, 'fault': 0}}
      player = _player_with_telem(telem)
      player.play(_short_chor())
      player._thread.join(timeout=2.0)

      assert not player.is_playing()
      assert player.get_status()['abort_reason'] == 'overheat'


  def test_overcurrent_aborts_choreo():
      telem = {'L': {'v_in': 25.0, 'temp': 40.0, 'current': 45.0, 'rpm': 0, 'duty': 0.0, 'fault': 0},
               'R': None}
      player = _player_with_telem(telem)
      player.play(_short_chor())
      player._thread.join(timeout=2.0)

      assert not player.is_playing()
      assert player.get_status()['abort_reason'] == 'overcurrent'


  def test_nominal_telem_does_not_abort():
      telem = {
          'L': {'v_in': 24.0, 'temp': 45.0, 'current': 8.0, 'rpm': 500, 'duty': 0.3, 'fault': 0},
          'R': {'v_in': 24.0, 'temp': 45.0, 'current': 8.0, 'rpm': 500, 'duty': 0.3, 'fault': 0},
      }
      player = _player_with_telem(telem)
      player.play(_short_chor(duration=0.1))
      player._thread.join(timeout=2.0)

      assert player.get_status()['abort_reason'] is None


  def test_none_telem_getter_skips_checks():
      """telem_getter=None → no abort regardless of play content."""
      player = ChoreoPlayer(
          cfg=None, audio=None, teeces=None,
          dome_motor=None, dome_servo=None, body_servo=None,
          audio_latency=0.0,
      )
      player.play(_short_chor(duration=0.1))
      player._thread.join(timeout=2.0)

      assert player.get_status()['abort_reason'] is None
  ```

- [ ] **Step 2: Run tests to verify they fail**

  ```bash
  python -m pytest tests/test_choreo_player.py::test_undervoltage_aborts_choreo tests/test_choreo_player.py::test_overheat_aborts_choreo tests/test_choreo_player.py::test_overcurrent_aborts_choreo tests/test_choreo_player.py::test_nominal_telem_does_not_abort tests/test_choreo_player.py::test_none_telem_getter_skips_checks -v
  ```

  Expected: failures (AttributeError `_check_telem` not defined)

- [ ] **Step 3: Implement — add `_check_telem()` method and wire into `_run()`**

  **a) Add `_check_telem()` method to `ChoreoPlayer` (after `_safe_stop_all`):**

  ```python
  def _check_telem(self) -> None:
      """Read telemetry and abort if any threshold is exceeded."""
      try:
          telem = self._telem_getter()
      except Exception as e:
          log.warning(f"ChoreoPlayer: telem_getter error: {e}")
          return

      if telem is None:
          return

      self._last_telem = telem

      for side in ('L', 'R'):
          data = telem.get(side)
          if data is None:
              continue

          v_in    = data.get('v_in', 999.0)
          temp    = data.get('temp', 0.0)
          current = abs(data.get('current', 0.0))

          if v_in < self._vesc_min_voltage:
              log.error(
                  f"ChoreoPlayer: ABORT — undervoltage VESC {side}: "
                  f"{v_in}V < {self._vesc_min_voltage}V"
              )
              self._abort_reason = 'undervoltage'
              self._stop_flag.set()
              return

          if temp > self._vesc_max_temp:
              log.error(
                  f"ChoreoPlayer: ABORT — overheat VESC {side}: "
                  f"{temp}°C > {self._vesc_max_temp}°C"
              )
              self._abort_reason = 'overheat'
              self._stop_flag.set()
              return

          if current > self._vesc_max_current:
              log.error(
                  f"ChoreoPlayer: ABORT — overcurrent VESC {side}: "
                  f"{current}A > {self._vesc_max_current}A"
              )
              self._abort_reason = 'overcurrent'
              self._stop_flag.set()
              return
  ```

  **b) Wire into `_run()` — add telem check block after the dome interpolation block and before the status update (after the `last_dome_t = t_now` assignment):**

  ```python
  # Check telemetry thresholds
  if self._telem_getter and not self._stop_flag.is_set():
      if t_now - self._last_telem_check >= self._telem_check_interval:
          self._check_telem()
          self._last_telem_check = t_now
  ```

  **c) Also update the periodic status update inside `_run()` to include live telem (replace the existing `with self._status_lock:` block that sets `t_now`):**

  ```python
  with self._status_lock:
      self._status['t_now'] = round(t_now, 3)
      self._status['telem'] = self._last_telem
  ```

- [ ] **Step 4: Run tests to verify they pass**

  ```bash
  python -m pytest tests/test_choreo_player.py::test_undervoltage_aborts_choreo tests/test_choreo_player.py::test_overheat_aborts_choreo tests/test_choreo_player.py::test_overcurrent_aborts_choreo tests/test_choreo_player.py::test_nominal_telem_does_not_abort tests/test_choreo_player.py::test_none_telem_getter_skips_checks -v
  ```

  Expected: 5 × PASSED

- [ ] **Step 5: Full suite regression check**

  ```bash
  python -m pytest tests/test_choreo_player.py -v
  ```

  Expected: all tests PASS

- [ ] **Step 6: Commit**

  ```bash
  git add master/choreo_player.py tests/test_choreo_player.py
  git commit -m "Feat: choreo — telemetry threshold monitoring (undervoltage/overheat/overcurrent)"
  ```

---

## Task 5 — Wire `telem_getter` in registry + final deploy

**Files:**
- Modify: `master/main.py` (single line: pass `telem_getter` when constructing `ChoreoPlayer`)

- [ ] **Step 1: Find where ChoreoPlayer is constructed in `main.py`**

  ```bash
  grep -n "ChoreoPlayer" J:/R2-D2_Build/software/master/main.py
  ```

- [ ] **Step 2: Add `telem_getter` argument to the ChoreoPlayer construction call**

  The existing call looks like:
  ```python
  reg.choreo = ChoreoPlayer(
      cfg=cfg, audio=reg.audio, teeces=reg.teeces,
      dome_motor=reg.dome_motor, dome_servo=reg.dome_servo,
      body_servo=reg.body_servo, vesc=reg.vesc,
  )
  ```

  Add `telem_getter`:
  ```python
  reg.choreo = ChoreoPlayer(
      cfg=cfg, audio=reg.audio, teeces=reg.teeces,
      dome_motor=reg.dome_motor, dome_servo=reg.dome_servo,
      body_servo=reg.body_servo, vesc=reg.vesc,
      telem_getter=lambda: reg.vesc_telem,
  )
  ```

- [ ] **Step 3: Run full test suite**

  ```bash
  python -m pytest tests/test_choreo_player.py -v
  ```

  Expected: all tests PASS

- [ ] **Step 4: Commit**

  ```bash
  git add master/main.py
  git commit -m "Feat: choreo — wire telem_getter=lambda: reg.vesc_telem in main.py"
  ```

- [ ] **Step 5: Push and deploy**

  ```bash
  git push
  ```

  Then deploy via paramiko:
  ```python
  import paramiko, sys, io
  sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
  c = paramiko.SSHClient()
  c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
  c.connect('192.168.2.104', username='artoo', password='deetoo', timeout=10)
  stdin, stdout, stderr = c.exec_command(
      'cd /home/artoo/r2d2 && bash scripts/update.sh 2>&1'
  )
  for line in stdout:
      print(line, end='')
  c.close()
  ```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task covering it |
|-----------------|-----------------|
| `telem_getter` callable injected into constructor | Task 2 |
| Thresholds read from `[choreo]` section in cfg | Tasks 1 + 2 |
| 3 consecutive `drive()` False → abort `uart_loss` | Task 3 |
| Counter resets on successful `drive()` | Task 3 |
| `_check_telem()` every `telem_check_interval` seconds | Task 4 |
| `v_in < vesc_min_voltage` → abort `undervoltage` | Task 4 |
| `temp > vesc_max_temp` → abort `overheat` | Task 4 |
| `current > vesc_max_current` → abort `overcurrent` | Task 4 |
| `get_status()` includes `abort_reason` + `telem` | Tasks 2 + 3 + 4 |
| `abort_reason` persists after stop, resets on `play()` | Task 3 |
| `telem_getter=None` → no abort, full backward compat | Task 4 |
| Wire in `main.py` with `lambda: reg.vesc_telem` | Task 5 |

All requirements covered. No placeholders. Method names consistent throughout.
