# Behavior Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the BehaviorEngine — a background system that plays a startup sequence on boot and triggers idle reactions (ALIVE mode) after inactivity, making R2-D2 feel alive at conventions without human interaction.

**Architecture:** A `BehaviorEngine` class runs in a daemon thread that reads config fresh from `local.cfg [behavior]` on each cycle. It is initialized in `main.py` after `reg.choreo` is set up. A Flask blueprint at `/behavior/*` exposes toggle and status endpoints. The Drive tab gets an ALIVE button replacing Dome Auto, and Settings gets a new Behavior panel.

**Tech Stack:** Python 3 threading, Flask Blueprint, configparser, existing `reg.choreo.play()` / `reg.dome.set_random()` / Flask `before_request` hook. Frontend: vanilla JS, HTML, CSS matching existing patterns.

---

## File Structure

| File | Change |
|------|--------|
| `master/behavior_engine.py` | New — `BehaviorEngine` class |
| `master/registry.py` | Add `last_activity: float`, `behavior_engine` |
| `master/flask_app.py` | `before_request` hook + register `behavior_bp` |
| `master/main.py` | Init + start `BehaviorEngine` after `reg.choreo` |
| `master/api/behavior_bp.py` | New blueprint — `/behavior/alive`, `/behavior/status`, `/behavior/config` |
| `master/templates/index.html` | ALIVE button in Drive tab; Behavior panel + sidebar entry in Settings |
| `master/static/js/app.js` | ALIVE toggle logic; behaviorPanel JS object |
| `master/static/css/style.css` | ALIVE button styles |
| `master/config/local.cfg.example` | Add `[behavior]` section |
| `tests/test_behavior_engine.py` | New — unit tests for BehaviorEngine |

---

### Task 1: Registry + activity tracking

**Files:**
- Modify: `master/registry.py`
- Modify: `master/flask_app.py`
- Test: `tests/test_behavior_engine.py` (create file, first test only)

- [ ] **Step 1: Write the failing test**

Create `tests/test_behavior_engine.py`:

```python
"""Tests for BehaviorEngine — registry fields and activity tracking."""
import time
import types
import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import master.registry as reg


def test_registry_has_last_activity():
    assert hasattr(reg, 'last_activity'), "reg.last_activity not defined"
    assert isinstance(reg.last_activity, float)


def test_registry_has_behavior_engine():
    assert hasattr(reg, 'behavior_engine'), "reg.behavior_engine not defined"
    assert reg.behavior_engine is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/artoo/r2d2
python -m pytest tests/test_behavior_engine.py::test_registry_has_last_activity tests/test_behavior_engine.py::test_registry_has_behavior_engine -v
```

Expected: FAIL — `AttributeError: module has no attribute 'last_activity'`

- [ ] **Step 3: Add fields to registry.py**

At the bottom of `master/registry.py`, after the `kids_speed_limit` line, add:

```python
# Behavior engine — timestamp of last user interaction (monotonic)
last_activity: float = 0.0

# BehaviorEngine instance — initialized in main.py
behavior_engine = None
```

- [ ] **Step 4: Add before_request hook to flask_app.py**

In `master/flask_app.py`, add the import at the top of `create_app()` (after existing imports):

```python
import time as _time
from flask import request as _request
import master.registry as _reg
```

Then inside `create_app()`, after blueprint registrations (after `app.register_blueprint(camera_bp)`), add:

```python
# ------------------------------------------------------------------
# Activity tracking — update last_activity on every POST request
# ------------------------------------------------------------------
@app.before_request
def _update_last_activity():
    if _request.method == 'POST':
        _reg.last_activity = _time.monotonic()
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/test_behavior_engine.py::test_registry_has_last_activity tests/test_behavior_engine.py::test_registry_has_behavior_engine -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add master/registry.py master/flask_app.py tests/test_behavior_engine.py
git commit -m "Feat: add last_activity + behavior_engine to registry, before_request hook"
```

---

### Task 2: BehaviorEngine core

**Files:**
- Create: `master/behavior_engine.py`
- Test: `tests/test_behavior_engine.py` (add tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_behavior_engine.py`:

```python
import configparser
import threading
from unittest.mock import MagicMock, patch
from master.behavior_engine import BehaviorEngine


def _make_cfg(extra_behavior: dict = None) -> configparser.ConfigParser:
    """Minimal config for BehaviorEngine."""
    cfg = configparser.ConfigParser()
    cfg['behavior'] = {
        'startup_enabled':    'false',
        'startup_delay':      '0',
        'startup_choreo':     'startup.chor',
        'alive_enabled':      'false',
        'idle_timeout_min':   '1',
        'idle_mode':          'choreo',
        'idle_audio_category':'happy',
        'idle_choreo_list':   'patrol.chor',
        'dome_auto_on_alive': 'false',
    }
    if extra_behavior:
        cfg['behavior'].update(extra_behavior)
    return cfg


def _make_engine(cfg=None, choreo_dir=None) -> BehaviorEngine:
    """BehaviorEngine with mocked registry."""
    if cfg is None:
        cfg = _make_cfg()
    be = BehaviorEngine(cfg, choreo_dir=choreo_dir or '/tmp')
    be._reg = MagicMock()
    be._reg.choreo = MagicMock()
    be._reg.choreo.is_playing.return_value = False
    be._reg.dome = MagicMock()
    be._reg.audio_playing = False
    be._reg.last_activity = 0.0
    return be


def test_behavior_engine_instantiates():
    be = _make_engine()
    assert be is not None


def test_startup_skipped_when_disabled():
    """startup_enabled=false — choreo.play never called."""
    be = _make_engine(_make_cfg({'startup_enabled': 'false'}))
    be._run_startup()
    be._reg.choreo.play.assert_not_called()


def test_startup_skipped_when_file_missing():
    """startup_enabled=true but choreo file doesn't exist."""
    be = _make_engine(_make_cfg({'startup_enabled': 'true', 'startup_choreo': 'nonexistent.chor'}))
    be._run_startup()
    be._reg.choreo.play.assert_not_called()


def test_idle_not_triggered_when_alive_disabled():
    """alive_enabled=false — idle reaction never fires."""
    be = _make_engine(_make_cfg({'alive_enabled': 'false'}))
    be._reg.last_activity = 0.0
    result = be._should_trigger_idle(now=999999.0)
    assert result is False


def test_idle_not_triggered_when_choreo_playing():
    """Idle blocked if choreo is already running."""
    be = _make_engine(_make_cfg({'alive_enabled': 'true', 'idle_timeout_min': '0'}))
    be._reg.choreo.is_playing.return_value = True
    be._reg.last_activity = 0.0
    result = be._should_trigger_idle(now=999999.0)
    assert result is False


def test_idle_not_triggered_before_timeout():
    """No trigger when inactivity < idle_timeout."""
    be = _make_engine(_make_cfg({'alive_enabled': 'true', 'idle_timeout_min': '10'}))
    be._reg.choreo.is_playing.return_value = False
    be._reg.audio_playing = False
    now = 1000.0
    be._reg.last_activity = now - 30.0   # only 30s, need 600s (10 min)
    result = be._should_trigger_idle(now=now)
    assert result is False


def test_idle_triggered_after_timeout():
    """Trigger fires when inactivity > idle_timeout and min gap satisfied."""
    be = _make_engine(_make_cfg({'alive_enabled': 'true', 'idle_timeout_min': '0'}))
    be._reg.choreo.is_playing.return_value = False
    be._reg.audio_playing = False
    be._reg.last_activity = 0.0
    be._last_idle_trigger = 0.0
    result = be._should_trigger_idle(now=999999.0)
    assert result is True


def test_min_gap_prevents_spam():
    """Two triggers within 30s — second one blocked."""
    be = _make_engine(_make_cfg({'alive_enabled': 'true', 'idle_timeout_min': '0'}))
    be._reg.choreo.is_playing.return_value = False
    be._reg.audio_playing = False
    be._reg.last_activity = 0.0
    be._last_idle_trigger = 999999.0 - 10.0   # triggered 10s ago
    result = be._should_trigger_idle(now=999999.0)
    assert result is False


def test_set_alive_resets_last_activity():
    """Toggling ALIVE ON resets last_activity to prevent immediate trigger."""
    be = _make_engine()
    be._reg.last_activity = 0.0
    before = time.monotonic()
    be.set_alive(True)
    after = time.monotonic()
    assert before <= be._reg.last_activity <= after + 0.1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_behavior_engine.py -k "test_behavior_engine" -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'master.behavior_engine'`

- [ ] **Step 3: Implement BehaviorEngine**

Create `master/behavior_engine.py`:

```python
"""
BehaviorEngine — makes R2-D2 feel alive without human interaction.

Two subsystems:
  1. Startup sequence: plays a choreo after boot delay.
  2. ALIVE mode: triggers idle reactions (audio/lights/choreo) after inactivity.

Config: local.cfg [behavior]
  startup_enabled     = true/false
  startup_delay       = 5              (seconds)
  startup_choreo      = startup.chor
  alive_enabled       = false
  idle_timeout_min    = 10             (minutes)
  idle_mode           = choreo         (sounds|sounds_lights|lights|choreo)
  idle_audio_category = happy
  idle_choreo_list    = patrol.chor,celebrate.chor
  dome_auto_on_alive  = true
"""

import configparser
import json
import logging
import os
import random
import threading
import time
from pathlib import Path

import master.registry as _registry

log = logging.getLogger(__name__)

_MIN_IDLE_GAP_S = 30.0   # minimum seconds between idle triggers


class BehaviorEngine:
    """Background behavior engine — startup sequence + ALIVE mode idle reactions."""

    def __init__(self, cfg: configparser.ConfigParser, choreo_dir: str = None):
        self._cfg = cfg
        self._choreo_dir = choreo_dir or os.path.join(
            os.path.dirname(__file__), 'choreographies'
        )
        self._reg = _registry          # injectable for tests
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._last_idle_trigger: float = 0.0
        self._alive_was_on: bool = False  # track dome auto state

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background behavior thread."""
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, name='behavior-engine', daemon=True
        )
        self._thread.start()
        log.info("BehaviorEngine started")

    def stop(self) -> None:
        """Signal the background thread to stop."""
        self._stop_event.set()

    def set_alive(self, enabled: bool) -> None:
        """Toggle ALIVE mode. Persists to local.cfg and handles dome auto."""
        self._write_cfg('alive_enabled', 'true' if enabled else 'false')
        if enabled:
            # Reset activity timer so idle doesn't fire immediately
            self._reg.last_activity = time.monotonic()
            log.info("ALIVE mode ON")
        else:
            log.info("ALIVE mode OFF")
        self._sync_dome_auto(enabled)

    # ------------------------------------------------------------------
    # Background loop
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """Main background loop — startup then periodic idle check."""
        self._run_startup()

        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception:
                log.exception("BehaviorEngine tick error")
            self._stop_event.wait(timeout=5.0)

    def _run_startup(self) -> None:
        """Play startup choreo after boot delay (if enabled)."""
        try:
            enabled = self._cfg.getboolean('behavior', 'startup_enabled', fallback=False)
            if not enabled:
                return
            delay = self._cfg.getfloat('behavior', 'startup_delay', fallback=5.0)
            choreo_name = self._cfg.get('behavior', 'startup_choreo', fallback='startup.chor')
            choreo_path = os.path.join(self._choreo_dir, choreo_name)

            if not os.path.isfile(choreo_path):
                log.warning("Startup choreo not found: %s — skipping", choreo_path)
                return

            if delay > 0:
                time.sleep(delay)

            choreo_data = self._load_choreo(choreo_path)
            if choreo_data:
                log.info("Playing startup choreo: %s", choreo_name)
                self._reg.choreo.play(choreo_data)
        except Exception:
            log.exception("Startup sequence error")

    def _tick(self) -> None:
        """Called every 5s — check if idle reaction should fire."""
        now = time.monotonic()
        if not self._should_trigger_idle(now):
            return

        self._last_idle_trigger = now
        mode = self._cfg.get('behavior', 'idle_mode', fallback='choreo')

        if mode == 'sounds':
            self._trigger_sounds()
        elif mode == 'sounds_lights':
            self._trigger_sounds()
            self._trigger_lights()
        elif mode == 'lights':
            self._trigger_lights()
        elif mode == 'choreo':
            self._trigger_choreo()
        else:
            log.warning("Unknown idle_mode: %s", mode)

    # ------------------------------------------------------------------
    # Guard
    # ------------------------------------------------------------------

    def _should_trigger_idle(self, now: float) -> bool:
        """Return True if all conditions for an idle trigger are met."""
        alive = self._cfg.getboolean('behavior', 'alive_enabled', fallback=False)
        if not alive:
            return False

        if self._reg.choreo.is_playing():
            return False

        idle_timeout_s = self._cfg.getfloat('behavior', 'idle_timeout_min', fallback=10.0) * 60.0
        since_activity = now - self._reg.last_activity
        if since_activity < idle_timeout_s:
            return False

        if now - self._last_idle_trigger < _MIN_IDLE_GAP_S:
            return False

        mode = self._cfg.get('behavior', 'idle_mode', fallback='choreo')
        if mode in ('sounds', 'sounds_lights') and self._reg.audio_playing:
            return False

        return True

    # ------------------------------------------------------------------
    # Reaction implementations
    # ------------------------------------------------------------------

    def _trigger_sounds(self) -> None:
        """POST /audio/random with idle_audio_category."""
        try:
            category = self._cfg.get('behavior', 'idle_audio_category', fallback='happy')
            import requests
            r = requests.post(
                'http://localhost:5000/audio/random',
                json={'category': category},
                timeout=3
            )
            log.info("ALIVE sounds: category=%s status=%s", category, r.status_code)
        except Exception:
            log.exception("ALIVE sounds trigger failed")

    def _trigger_lights(self) -> None:
        """POST random lights animation."""
        try:
            import requests
            r = requests.post(
                'http://localhost:5000/lights/random',
                timeout=3
            )
            log.info("ALIVE lights: status=%s", r.status_code)
        except Exception:
            log.exception("ALIVE lights trigger failed")

    def _trigger_choreo(self) -> None:
        """Pick a random choreo from idle_choreo_list and play it."""
        try:
            raw = self._cfg.get('behavior', 'idle_choreo_list', fallback='')
            choreo_list = [c.strip() for c in raw.split(',') if c.strip()]
            if not choreo_list:
                log.warning("idle_choreo_list is empty — nothing to play")
                return

            choreo_name = random.choice(choreo_list)
            choreo_path = os.path.join(self._choreo_dir, choreo_name)
            if not os.path.isfile(choreo_path):
                log.warning("ALIVE choreo not found: %s", choreo_path)
                return

            choreo_data = self._load_choreo(choreo_path)
            if choreo_data:
                log.info("ALIVE choreo: %s", choreo_name)
                self._reg.choreo.play(choreo_data)
        except Exception:
            log.exception("ALIVE choreo trigger failed")

    # ------------------------------------------------------------------
    # Dome auto sync
    # ------------------------------------------------------------------

    def _sync_dome_auto(self, alive_on: bool) -> None:
        """Enable/disable dome auto rotation when ALIVE is toggled."""
        try:
            dome_auto = self._cfg.getboolean('behavior', 'dome_auto_on_alive', fallback=True)
            if not dome_auto:
                return
            if self._reg.dome:
                self._reg.dome.set_random(alive_on)
                log.debug("Dome auto → %s (ALIVE=%s)", alive_on, alive_on)
        except Exception:
            log.exception("Dome auto sync failed")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load_choreo(self, path: str) -> dict | None:
        """Load and parse a .chor JSON file. Returns None on error."""
        try:
            with open(path, encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            log.exception("Failed to load choreo: %s", path)
            return None

    def _write_cfg(self, key: str, value: str) -> None:
        """Persist a [behavior] key to local.cfg."""
        try:
            cfg_path = os.path.join(
                os.path.dirname(__file__), 'config', 'local.cfg'
            )
            parser = configparser.ConfigParser()
            parser.read(cfg_path)
            if not parser.has_section('behavior'):
                parser.add_section('behavior')
            parser.set('behavior', key, value)
            # Also update in-memory config
            if not self._cfg.has_section('behavior'):
                self._cfg.add_section('behavior')
            self._cfg.set('behavior', key, value)
            with open(cfg_path, 'w') as f:
                parser.write(f)
        except Exception:
            log.exception("Failed to persist behavior config key=%s", key)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_behavior_engine.py -v
```

Expected: All 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add master/behavior_engine.py tests/test_behavior_engine.py
git commit -m "Feat: add BehaviorEngine — startup sequence + ALIVE idle reactions"
```

---

### Task 3: behavior_bp.py — Flask blueprint

**Files:**
- Create: `master/api/behavior_bp.py`
- Test: `tests/test_behavior_engine.py` (add API tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_behavior_engine.py`:

```python
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def flask_client(tmp_path):
    """Flask test client with behavior_bp registered."""
    import configparser
    import master.registry as reg
    from master.behavior_engine import BehaviorEngine

    # Write a minimal local.cfg so _write_cfg works
    cfg_path = tmp_path / 'local.cfg'
    cfg_path.write_text('[behavior]\nalive_enabled = false\n')

    cfg = _make_cfg()
    be = BehaviorEngine(cfg, choreo_dir=str(tmp_path))
    be._reg = reg
    reg.behavior_engine = be
    reg.choreo = MagicMock()
    reg.choreo.is_playing.return_value = False
    reg.last_activity = 0.0

    # Patch config path
    with patch.object(be, '_write_cfg', lambda k, v: None):
        from flask import Flask
        app = Flask(__name__)
        from master.api.behavior_bp import behavior_bp
        app.register_blueprint(behavior_bp)
        app.config['TESTING'] = True
        yield app.test_client()


def test_get_behavior_status(flask_client):
    resp = flask_client.get('/behavior/status')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'alive_enabled' in data
    assert 'idle_mode' in data


def test_post_behavior_alive_toggle(flask_client):
    resp = flask_client.post(
        '/behavior/alive',
        json={'enabled': True},
        content_type='application/json'
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ok'] is True


def test_post_behavior_config(flask_client):
    resp = flask_client.post(
        '/behavior/config',
        json={
            'startup_enabled': True,
            'startup_delay': 3,
            'startup_choreo': 'startup.chor',
            'alive_enabled': False,
            'idle_timeout_min': 5,
            'idle_mode': 'sounds',
            'idle_audio_category': 'happy',
            'idle_choreo_list': ['patrol.chor'],
            'dome_auto_on_alive': True,
        },
        content_type='application/json'
    )
    assert resp.status_code == 200
    assert resp.get_json()['ok'] is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_behavior_engine.py -k "test_get_behavior_status or test_post_behavior" -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'master.api.behavior_bp'`

- [ ] **Step 3: Implement behavior_bp.py**

Create `master/api/behavior_bp.py`:

```python
"""
Blueprint API Behavior — BehaviorEngine REST endpoints.

Endpoints:
  POST /behavior/alive    {"enabled": true|false}
  GET  /behavior/status   → {alive_enabled, startup_enabled, idle_mode, ...}
  POST /behavior/config   → save full behavior config to local.cfg
"""

import logging
import os
import time
import configparser
from flask import Blueprint, request, jsonify
import master.registry as reg

log = logging.getLogger(__name__)

behavior_bp = Blueprint('behavior', __name__, url_prefix='/behavior')

_CFG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'local.cfg')


def _get_cfg() -> configparser.ConfigParser:
    """Read the current local.cfg."""
    parser = configparser.ConfigParser()
    parser.read(_CFG_PATH)
    return parser


@behavior_bp.post('/alive')
def set_alive():
    """Toggle ALIVE mode on or off."""
    data = request.get_json(silent=True) or {}
    enabled = bool(data.get('enabled', False))
    be = reg.behavior_engine
    if be is None:
        return jsonify({'ok': False, 'error': 'BehaviorEngine not initialized'}), 503
    be.set_alive(enabled)
    return jsonify({'ok': True, 'alive_enabled': enabled})


@behavior_bp.get('/status')
def get_status():
    """Current behavior engine state."""
    cfg = _get_cfg()
    now = time.monotonic()
    last = reg.last_activity
    ago = round(now - last, 1) if last > 0 else None
    return jsonify({
        'alive_enabled':      cfg.getboolean('behavior', 'alive_enabled',      fallback=False),
        'startup_enabled':    cfg.getboolean('behavior', 'startup_enabled',    fallback=False),
        'startup_delay':      cfg.getfloat  ('behavior', 'startup_delay',      fallback=5.0),
        'startup_choreo':     cfg.get       ('behavior', 'startup_choreo',     fallback='startup.chor'),
        'idle_mode':          cfg.get       ('behavior', 'idle_mode',          fallback='choreo'),
        'idle_timeout_min':   cfg.getfloat  ('behavior', 'idle_timeout_min',   fallback=10.0),
        'idle_audio_category':cfg.get       ('behavior', 'idle_audio_category',fallback='happy'),
        'idle_choreo_list':   [c.strip() for c in cfg.get('behavior', 'idle_choreo_list', fallback='').split(',') if c.strip()],
        'dome_auto_on_alive': cfg.getboolean('behavior', 'dome_auto_on_alive', fallback=True),
        'last_activity_ago_s': ago,
    })


@behavior_bp.post('/config')
def save_config():
    """Save full behavior configuration to local.cfg."""
    data = request.get_json(silent=True) or {}
    parser = _get_cfg()
    if not parser.has_section('behavior'):
        parser.add_section('behavior')

    def _set(key, value):
        parser.set('behavior', key, str(value))

    if 'startup_enabled'     in data: _set('startup_enabled',     'true' if data['startup_enabled'] else 'false')
    if 'startup_delay'       in data: _set('startup_delay',       str(int(data['startup_delay'])))
    if 'startup_choreo'      in data: _set('startup_choreo',      str(data['startup_choreo']))
    if 'alive_enabled'       in data: _set('alive_enabled',       'true' if data['alive_enabled'] else 'false')
    if 'idle_timeout_min'    in data: _set('idle_timeout_min',    str(int(data['idle_timeout_min'])))
    if 'idle_mode'           in data: _set('idle_mode',           str(data['idle_mode']))
    if 'idle_audio_category' in data: _set('idle_audio_category', str(data['idle_audio_category']))
    if 'idle_choreo_list'    in data:
        clist = data['idle_choreo_list']
        if isinstance(clist, list):
            _set('idle_choreo_list', ','.join(clist))
        else:
            _set('idle_choreo_list', str(clist))
    if 'dome_auto_on_alive'  in data: _set('dome_auto_on_alive',  'true' if data['dome_auto_on_alive'] else 'false')

    try:
        cfg_path = os.path.normpath(_CFG_PATH)
        with open(cfg_path, 'w') as f:
            parser.write(f)
        # Update in-memory config on the engine if available
        be = reg.behavior_engine
        if be:
            be._cfg.read_dict(dict(parser))
        log.info("Behavior config saved")
        return jsonify({'ok': True})
    except Exception as e:
        log.exception("Failed to save behavior config")
        return jsonify({'ok': False, 'error': str(e)}), 500
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_behavior_engine.py -k "test_get_behavior_status or test_post_behavior" -v
```

Expected: All 3 API tests PASS

- [ ] **Step 5: Commit**

```bash
git add master/api/behavior_bp.py tests/test_behavior_engine.py
git commit -m "Feat: add behavior_bp — /behavior/alive, /behavior/status, /behavior/config"
```

---

### Task 4: Wire up in main.py + flask_app.py

**Files:**
- Modify: `master/main.py`
- Modify: `master/flask_app.py`

- [ ] **Step 1: Register behavior_bp in flask_app.py**

In `master/flask_app.py`, add after the `camera_bp` import line:

```python
    from master.api.behavior_bp  import behavior_bp
```

And after `app.register_blueprint(camera_bp)`:

```python
    app.register_blueprint(behavior_bp)
```

Also update the log message at the bottom to include behavior:

```python
    log.info("Flask app created — blueprints: audio, motion, servo, scripts, status, teeces, settings, behavior")
```

- [ ] **Step 2: Initialize BehaviorEngine in main.py**

In `master/main.py`, add the import after the `from master.choreo_player import ChoreoPlayer` line (around line 244):

```python
    from master.behavior_engine import BehaviorEngine
```

After `reg.choreo.setup()` (around line 256), add:

```python
    behavior_engine = BehaviorEngine(cfg)
    reg.behavior_engine = behavior_engine
```

After `flask_thread.start()` and `log.info(f"Flask started on port {flask_port}")` (after line 350), add:

```python
    behavior_engine.start()
    log.info("BehaviorEngine started")
```

- [ ] **Step 3: Verify syntax**

```bash
python -c "import master.main" 2>&1 | head -20
```

Expected: No import errors (may fail on hardware, that is fine — just no syntax errors)

- [ ] **Step 4: Commit**

```bash
git add master/main.py master/flask_app.py
git commit -m "Feat: wire up BehaviorEngine in main.py and flask_app.py"
```

---

### Task 5: local.cfg.example — add [behavior] section

**Files:**
- Modify: `master/config/local.cfg.example`

- [ ] **Step 1: Add [behavior] section**

In `master/config/local.cfg.example`, append at the end of the file:

```ini
[behavior]
# Startup sequence — plays a choreo after boot
startup_enabled  = true
startup_delay    = 5
startup_choreo   = startup.chor

# ALIVE mode — idle reactions after inactivity
alive_enabled       = false
idle_timeout_min    = 10
idle_mode           = choreo
idle_audio_category = happy
idle_choreo_list    = startup.chor
dome_auto_on_alive  = true
```

- [ ] **Step 2: Verify file parses cleanly**

```bash
python -c "
import configparser
p = configparser.ConfigParser()
p.read('master/config/local.cfg.example')
print('behavior section keys:', list(p['behavior'].keys()))
"
```

Expected output lists all 8 behavior keys

- [ ] **Step 3: Commit**

```bash
git add master/config/local.cfg.example
git commit -m "Config: add [behavior] section to local.cfg.example"
```

---

### Task 6: HTML — Drive tab ALIVE button

**Files:**
- Modify: `master/templates/index.html`

The current "DOME AUTO" toggle (lines 351–357 in index.html) needs to be replaced with an ALIVE button. The `.drive-bottom-right` div keeps the camera button.

- [ ] **Step 1: Replace Dome Auto toggle with ALIVE button**

In `master/templates/index.html`, find and replace the `dome-toggle-wrap` block:

Find (lines ~351–357):
```html
        <div class="dome-toggle-wrap">
          <label class="toggle-label">
            DOME AUTO
            <input type="checkbox" id="dome-random-ctrl" onchange="domeRandom(this.checked)">
            <span class="toggle-switch"></span>
          </label>
        </div>
```

Replace with:
```html
        <button id="alive-toggle-btn" class="alive-btn" onclick="behaviorPanel.toggleAlive()" title="ALIVE mode — idle reactions">
          ALIVE
        </button>
```

- [ ] **Step 2: Add Behavior panel entry in Settings sidebar**

In `master/templates/index.html`, the Settings sidebar nav (around line 812). Add after the `arms` entry and before the `servos` entry:

Find:
```html
      <button class="settings-nav-item" data-panel="arms"      onclick="switchSettingsPanel('arms')">🦾 Arms</button>
      <button class="settings-nav-item" data-panel="servos"    onclick="switchSettingsPanel('servos')">🔧 Calibration</button>
```

Replace with:
```html
      <button class="settings-nav-item" data-panel="arms"      onclick="switchSettingsPanel('arms')">🦾 Arms</button>
      <button class="settings-nav-item" data-panel="behavior"  onclick="switchSettingsPanel('behavior')">🤖 Behavior</button>
      <button class="settings-nav-item" data-panel="servos"    onclick="switchSettingsPanel('servos')">🔧 Calibration</button>
```

- [ ] **Step 3: Add Behavior settings panel HTML**

In `master/templates/index.html`, find the `<!-- 🔧 Servos -->` panel comment (around line 1009) and insert the new Behavior panel **before** it:

Find:
```html
      <!-- 🔧 Servos -->
      <div class="settings-panel" id="spanel-servos">
```

Insert before:
```html
      <!-- 🤖 Behavior -->
      <div class="settings-panel" id="spanel-behavior">
        <section class="card settings-card">
          <h2 class="card-title">STARTUP SEQUENCE</h2>
          <div class="form-group" style="display:flex;align-items:center;gap:12px">
            <label class="toggle-label">
              <input type="checkbox" id="beh-startup-enabled">
              <span class="toggle-switch"></span>
              Enabled
            </label>
          </div>
          <div class="form-group">
            <label class="ctrl-label">DELAY (seconds)</label>
            <input type="number" id="beh-startup-delay" class="input-text input-sm" min="0" max="60" value="5" style="width:70px">
          </div>
          <div class="form-group">
            <label class="ctrl-label">CHOREO</label>
            <select id="beh-startup-choreo" class="input-text"></select>
          </div>
        </section>

        <section class="card settings-card" style="margin-top:12px">
          <h2 class="card-title">IDLE REACTIONS (ALIVE MODE)</h2>
          <div class="form-group" style="display:flex;align-items:center;gap:12px">
            <label class="toggle-label">
              <input type="checkbox" id="beh-alive-enabled">
              <span class="toggle-switch"></span>
              Enabled
            </label>
          </div>
          <div class="form-group">
            <label class="ctrl-label">TRIGGER AFTER (minutes of inactivity)</label>
            <input type="number" id="beh-idle-timeout" class="input-text input-sm" min="1" max="120" value="10" style="width:70px">
          </div>
          <div class="form-group">
            <label class="ctrl-label">MODE</label>
            <select id="beh-idle-mode" class="input-text" onchange="behaviorPanel.onModeChange()">
              <option value="sounds">Sounds only</option>
              <option value="sounds_lights">Sounds + Lights</option>
              <option value="lights">Lights only</option>
              <option value="choreo">Choreo</option>
            </select>
          </div>
          <div id="beh-audio-cat-row" class="form-group">
            <label class="ctrl-label">AUDIO CATEGORY</label>
            <select id="beh-audio-category" class="input-text"></select>
          </div>
          <div id="beh-choreo-row" class="form-group" style="display:none">
            <label class="ctrl-label">CHOREO LIST</label>
            <div id="beh-choreo-pills" class="beh-choreo-pills"></div>
            <div style="display:flex;gap:8px;margin-top:6px">
              <select id="beh-choreo-add-sel" class="input-text input-sm" style="flex:1"></select>
              <button class="btn btn-sm" onclick="behaviorPanel.addChoreo()">+ ADD</button>
            </div>
          </div>
          <div class="form-group" style="display:flex;align-items:center;gap:12px">
            <label class="toggle-label">
              <input type="checkbox" id="beh-dome-auto">
              <span class="toggle-switch"></span>
              Dome auto-rotation when ALIVE is ON
            </label>
          </div>
        </section>
        <div style="margin-top:12px;display:flex;gap:10px;align-items:center">
          <button class="btn btn-active" onclick="behaviorPanel.save()">SAVE</button>
          <div class="settings-status" id="beh-status"></div>
        </div>
      </div>

      <!-- 🔧 Servos -->
      <div class="settings-panel" id="spanel-servos">
```

- [ ] **Step 4: Verify HTML is well-formed**

Open the dashboard in a browser and check that the Settings sidebar shows 🤖 Behavior between Arms and Calibration. Clicking it should show the Behavior panel (content will be empty until JS is added in Task 7).

- [ ] **Step 5: Commit**

```bash
git add master/templates/index.html
git commit -m "Feat: add ALIVE button in Drive tab and Behavior panel in Settings"
```

---

### Task 7: JavaScript — ALIVE toggle + Behavior settings panel

**Files:**
- Modify: `master/static/js/app.js`

- [ ] **Step 1: Add ALIVE toggle function**

In `master/static/js/app.js`, find the `domeRandom` function (around line 1270):

```javascript
function domeRandom(on) { api('/motion/dome/random', 'POST', { enabled: on }); }
```

Add immediately after it:

```javascript
// ================================================================
// Behavior Engine — ALIVE toggle
// ================================================================

const behaviorPanel = (() => {
  // Internal state
  let _aliveOn     = false;
  let _choreoList  = [];   // current list for idle mode = choreo

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
  function load() {
    api('/behavior/status').then(d => {
      _aliveOn = d.alive_enabled;
      _applyAliveBtn();

      _setChk('beh-startup-enabled', d.startup_enabled);
      _setVal('beh-startup-delay',   d.startup_delay);
      _setChk('beh-alive-enabled',   d.alive_enabled);
      _setVal('beh-idle-timeout',    d.idle_timeout_min);
      _setChk('beh-dome-auto',       d.dome_auto_on_alive);

      _choreoList = d.idle_choreo_list || [];

      // Populate dropdowns after fetching lists
      Promise.all([
        api('/choreo/list'),
        api('/audio/categories')
      ]).then(([choreoData, audioData]) => {
        const chorFiles = (choreoData.files || []).map(f => f.name || f);
        _populateSel('beh-startup-choreo', chorFiles, d.startup_choreo);
        _populateSel('beh-choreo-add-sel', chorFiles, null);

        const cats = Object.keys(audioData.categories || {});
        _populateSel('beh-audio-category', cats, d.idle_audio_category);

        // Set mode (after dropdowns are built)
        _setSelVal('beh-idle-mode', d.idle_mode);
        onModeChange();
        _renderChoreoPills();
      });
    }).catch(() => {});
  }

  function onModeChange() {
    const mode = _getSelVal('beh-idle-mode');
    const showAudio  = mode === 'sounds' || mode === 'sounds_lights';
    const showChoreo = mode === 'choreo';
    _show('beh-audio-cat-row', showAudio);
    _show('beh-choreo-row',    showChoreo);
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
    container.innerHTML = '';
    _choreoList.forEach((name, idx) => {
      const pill = document.createElement('span');
      pill.className = 'beh-choreo-pill';
      pill.innerHTML = `${name} <button class="beh-pill-remove" onclick="behaviorPanel._removeChoreo(${idx})">×</button>`;
      container.appendChild(pill);
    });
  }

  function _removeChoreo(idx) {
    _choreoList.splice(idx, 1);
    _renderChoreoPills();
  }

  function save() {
    const payload = {
      startup_enabled:     el('beh-startup-enabled')?.checked ?? false,
      startup_delay:       parseInt(el('beh-startup-delay')?.value || '5', 10),
      startup_choreo:      _getSelVal('beh-startup-choreo') || 'startup.chor',
      alive_enabled:       el('beh-alive-enabled')?.checked ?? false,
      idle_timeout_min:    parseInt(el('beh-idle-timeout')?.value || '10', 10),
      idle_mode:           _getSelVal('beh-idle-mode') || 'choreo',
      idle_audio_category: _getSelVal('beh-audio-category') || 'happy',
      idle_choreo_list:    _choreoList,
      dome_auto_on_alive:  el('beh-dome-auto')?.checked ?? true,
    };
    api('/behavior/config', 'POST', payload)
      .then(() => _setStatus('beh-status', 'Saved', 'ok'))
      .catch(() => _setStatus('beh-status', 'Error', 'err'));
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

  return { toggleAlive, load, onModeChange, addChoreo, save, _removeChoreo, _applyAliveBtn };
})();
```

- [ ] **Step 2: Wire up lazy-load in switchSettingsPanel**

In `master/static/js/app.js`, find the `switchSettingsPanel` function (around line 462). Add after the existing lazy-load lines (after `if (panelId === 'arms') armsConfig.load();`):

```javascript
  if (panelId === 'behavior') behaviorPanel.load();
```

- [ ] **Step 3: Initialize ALIVE button state on status poll**

In `master/static/js/app.js`, find the `loadStatus` or status polling function that updates the Drive tab UI. Search for `dome-random-ctrl` — since that element is now removed, find any reference and remove it.

Search: `dome-random-ctrl`

```bash
grep -n "dome-random-ctrl\|domeRandom" master/static/js/app.js
```

Remove any lines that set `dome-random-ctrl.checked = ...` from status polling. Then add a call to initialize the ALIVE button state on page load by appending to the `init()` function (or the DOMContentLoaded handler):

In the `init()` function body, add:

```javascript
  api('/behavior/status').then(d => behaviorPanel._applyAliveBtn()).catch(() => {});
```

But first set `_aliveOn` from the status. Update the ALIVE button init inside the `init()` call:

```javascript
  api('/behavior/status').then(d => {
    if (typeof d.alive_enabled === 'boolean') {
      // Update internal _aliveOn via load — but load() also fetches dropdowns.
      // For the drive tab button, just apply state directly.
      const btn = el('alive-toggle-btn');
      if (btn) btn.classList.toggle('alive-btn-on', d.alive_enabled);
    }
  }).catch(() => {});
```

- [ ] **Step 4: Remove dead dome-random-ctrl references**

Search and remove any remaining references to `dome-random-ctrl` in `app.js` (the HTML element is gone):

```bash
grep -n "dome-random-ctrl" master/static/js/app.js
```

For each match, remove or replace the line. If found in a status update like `el('dome-random-ctrl').checked = ...`, delete that line.

- [ ] **Step 5: Commit**

```bash
git add master/static/js/app.js
git commit -m "Feat: ALIVE toggle button + behavior settings panel JS"
```

---

### Task 8: CSS — ALIVE button styles

**Files:**
- Modify: `master/static/css/style.css`

- [ ] **Step 1: Add ALIVE button styles**

In `master/static/css/style.css`, find the `.dome-toggle-wrap` block (around line 987):

```css
.dome-toggle-wrap {
  flex-shrink: 0;
}
```

Replace the entire `.dome-toggle-wrap` block with the ALIVE button styles:

```css
/* ALIVE mode toggle button — Drive tab */
.alive-btn {
  flex-shrink: 0;
  padding: 6px 14px;
  font-size: 11px;
  font-family: inherit;
  font-weight: 700;
  letter-spacing: .1em;
  color: #4a7a9b;
  background: transparent;
  border: 1px solid #1a3a4a;
  border-radius: 4px;
  cursor: pointer;
  transition: color .15s, border-color .15s, box-shadow .15s;
}
.alive-btn:hover {
  color: #7eb8d4;
  border-color: #2a5a6a;
}
.alive-btn.alive-btn-on {
  color: #00e5cc;
  border-color: #00e5cc;
  box-shadow: 0 0 8px rgba(0, 229, 204, 0.4);
}
```

- [ ] **Step 2: Add Behavior panel choreo pill styles**

In `master/static/css/style.css`, find the end of the settings-related styles (near other `.settings-*` rules) and add:

```css
/* Behavior panel — choreo list pills */
.beh-choreo-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 4px;
}
.beh-choreo-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  background: rgba(0, 229, 204, 0.08);
  border: 1px solid rgba(0, 229, 204, 0.3);
  border-radius: 12px;
  font-size: 11px;
  color: #7eb8d4;
}
.beh-pill-remove {
  background: none;
  border: none;
  color: #4a7a9b;
  cursor: pointer;
  font-size: 13px;
  line-height: 1;
  padding: 0 2px;
}
.beh-pill-remove:hover {
  color: #e05a5a;
}
```

- [ ] **Step 3: Visual verification**

Open the dashboard in a browser:
1. Drive tab → ALIVE button visible, dimmed (inactive)
2. Click ALIVE → button glows teal/cyan
3. Settings → Behavior panel → startup section and idle reactions section visible
4. Change Mode to "Choreo" → choreo pill list appears
5. Add a choreo → pill appears with × button
6. Click × → pill removed
7. SAVE → toast/status shows "Saved"

- [ ] **Step 4: Commit**

```bash
git add master/static/css/style.css
git commit -m "Feat: ALIVE button styles + behavior panel choreo pill styles"
```

---

## Post-Implementation Checklist

After all tasks are committed, verify end-to-end on the Pi:

- [ ] SSH to Master Pi and run: `cd /home/artoo/r2d2 && git pull && bash scripts/update.sh`
- [ ] Navigate to Drive tab → ALIVE button visible
- [ ] Toggle ALIVE ON → button glows, `POST /behavior/alive` returns 200
- [ ] Navigate to Settings → Behavior panel → loads startup + idle config
- [ ] Set `idle_timeout_min = 1`, idle_mode = sounds, SAVE → wait 1 min inactive → R2 plays a sound
- [ ] Set idle_mode = choreo, add `startup.chor`, SAVE → wait → startup choreo plays
- [ ] Check `GET /behavior/status` → `last_activity_ago_s` counting up correctly
- [ ] Verify startup_choreo plays ~5s after service restart (if startup_enabled = true)
