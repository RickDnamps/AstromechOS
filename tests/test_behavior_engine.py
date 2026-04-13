"""Tests for BehaviorEngine — registry fields and activity tracking."""
import time
import types
import sys
import os
import pytest

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import master.registry as reg


def test_registry_has_last_activity():
    assert hasattr(reg, 'last_activity'), "reg.last_activity not defined"
    assert isinstance(reg.last_activity, float)


def test_registry_has_behavior_engine():
    assert hasattr(reg, 'behavior_engine'), "reg.behavior_engine not defined"
    assert reg.behavior_engine is None


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


# ---------------------------------------------------------------------------
# Flask blueprint API tests
# ---------------------------------------------------------------------------

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
