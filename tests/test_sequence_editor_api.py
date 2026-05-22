"""Tests — script_bp.py new and modified API endpoints."""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from flask import Flask
import master.registry as reg


@pytest.fixture
def app(tmp_path):
    """Flask test app with sequences dir in tmp_path."""
    from master.api.script_bp import script_bp
    import master.api.script_bp as sbp

    # Override SEQUENCES_DIR to point to tmp_path
    sbp.SEQUENCES_DIR = tmp_path

    flask_app = Flask(__name__)
    flask_app.register_blueprint(script_bp)
    flask_app.config['TESTING'] = True

    # Mock engine
    reg.engine = MagicMock()
    reg.engine.list_scripts.return_value = ['celebrate', 'my_custom']
    reg.engine.list_running.return_value = [
        {'id': 1, 'name': 'celebrate',
         'step_index': 2, 'step_total': 5, 'current_cmd': 'sleep,0.5'}
    ]
    reg.engine.run.return_value = 42

    # Create sample .scr files
    (tmp_path / 'celebrate.scr').write_text("sound,Happy001\nsleep,0.5\n")
    (tmp_path / 'my_custom.scr').write_text("servo,body_panel_1,open\n")

    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


# ── GET /scripts/list ──────────────────────────────────────────────────────────

def test_list_includes_is_builtin(client):
    with patch('master.api.script_bp._is_builtin', side_effect=lambda n: n == 'celebrate'):
        resp = client.get('/scripts/list')
    assert resp.status_code == 200
    data = resp.get_json()
    names = {s['name']: s['is_builtin'] for s in data['scripts']}
    assert names['celebrate'] is True
    assert names['my_custom'] is False


# ── GET /scripts/running ───────────────────────────────────────────────────────

def test_running_includes_step_progress(client):
    resp = client.get('/scripts/running')
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data['running']) == 1
    entry = data['running'][0]
    assert entry['step_index'] == 2
    assert entry['step_total'] == 5
    assert entry['current_cmd'] == 'sleep,0.5'


# ── POST /scripts/run — skip_motion ───────────────────────────────────────────

def test_run_passes_skip_motion(client):
    resp = client.post('/scripts/run',
                       json={'name': 'celebrate', 'skip_motion': True})
    assert resp.status_code == 200
    reg.engine.run.assert_called_once_with('celebrate', loop=False, skip_motion=True)


# ── GET /scripts/get ──────────────────────────────────────────────────────────

def test_get_returns_steps(client, tmp_path):
    with patch('master.api.script_bp._is_builtin', return_value=False):
        resp = client.get('/scripts/get?name=my_custom')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['name'] == 'my_custom'
    assert data['is_builtin'] is False
    assert data['steps'] == [{'cmd': 'servo', 'args': ['body_panel_1', 'open']}]


def test_get_not_found(client):
    resp = client.get('/scripts/get?name=nonexistent')
    assert resp.status_code == 404


# ── POST /scripts/save ────────────────────────────────────────────────────────

def test_save_creates_scr_file(client, tmp_path):
    steps = [
        {'cmd': 'sound', 'args': ['RANDOM', 'happy']},
        {'cmd': 'sleep', 'args': ['0.5']},
    ]
    resp = client.post('/scripts/save',
                       json={'name': 'new_seq', 'steps': steps})
    assert resp.status_code == 200
    scr = tmp_path / 'new_seq.scr'
    assert scr.exists()
    content = scr.read_text()
    assert 'sound,RANDOM,happy' in content
    assert 'sleep,0.5' in content


def test_save_rejects_invalid_name(client):
    resp = client.post('/scripts/save',
                       json={'name': 'bad name!', 'steps': [{'cmd': 'sleep', 'args': ['1']}]})
    assert resp.status_code == 400


def test_save_rejects_empty_steps(client):
    resp = client.post('/scripts/save',
                       json={'name': 'empty_seq', 'steps': []})
    assert resp.status_code == 400


def test_save_blocks_builtin_overwrite(client):
    with patch('master.api.script_bp._is_builtin', return_value=True):
        resp = client.post('/scripts/save',
                           json={'name': 'celebrate',
                                 'steps': [{'cmd': 'sleep', 'args': ['1']}]})
    assert resp.status_code == 403


# ── POST /scripts/delete ──────────────────────────────────────────────────────

def test_delete_removes_file(client, tmp_path):
    with patch('master.api.script_bp._is_builtin', return_value=False):
        resp = client.post('/scripts/delete', json={'name': 'my_custom'})
    assert resp.status_code == 200
    assert not (tmp_path / 'my_custom.scr').exists()


def test_delete_blocks_builtin(client):
    with patch('master.api.script_bp._is_builtin', return_value=True):
        resp = client.post('/scripts/delete', json={'name': 'celebrate'})
    assert resp.status_code == 403


def test_delete_not_found(client):
    with patch('master.api.script_bp._is_builtin', return_value=False):
        resp = client.post('/scripts/delete', json={'name': 'ghost'})
    assert resp.status_code == 404


# ── POST /scripts/rename ─────────────────────────────────────────────────────

def test_rename_renames_file(client, tmp_path):
    with patch('master.api.script_bp._is_running', return_value=False):
        resp = client.post('/scripts/rename',
                           json={'old': 'my_custom', 'new': 'renamed_seq'})
    assert resp.status_code == 200
    assert not (tmp_path / 'my_custom.scr').exists()
    assert (tmp_path / 'renamed_seq.scr').exists()


def test_rename_blocked_if_running(client):
    with patch('master.api.script_bp._is_running', return_value=True):
        resp = client.post('/scripts/rename',
                           json={'old': 'celebrate', 'new': 'other'})
    assert resp.status_code == 409


def test_rename_invalid_new_name(client):
    resp = client.post('/scripts/rename',
                       json={'old': 'my_custom', 'new': 'bad name!'})
    assert resp.status_code == 400


def test_rename_invalid_old_name(client):
    resp = client.post('/scripts/rename',
                       json={'old': '../../etc/passwd', 'new': 'safe_name'})
    assert resp.status_code == 400
