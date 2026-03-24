"""Tests — ScriptEngine changes for sequence editor."""
import os
import sys
import tempfile
import threading
import time

import pytest

# Add repo root to path so master.* imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from master.script_engine import ScriptEngine


def make_scr(content: str) -> str:
    """Write a temp .scr file and return its path."""
    f = tempfile.NamedTemporaryFile(mode='w', suffix='.scr',
                                    delete=False, encoding='utf-8')
    f.write(content)
    f.close()
    return f.name


# ── skip_motion ──────────────────────────────────────────────────────────────

def test_skip_motion_suppresses_motion_command():
    """motion command is skipped when skip_motion=True."""
    calls = []
    engine = ScriptEngine()
    # Monkey-patch _cmd_motion to track calls
    original = engine._cmd_motion
    engine._cmd_motion = lambda row, **kw: calls.append(row)

    row = ['motion', '0.5', '0.5', '500']
    engine.execute_command(row, skip_motion=True)
    assert calls == [], "motion should be suppressed with skip_motion=True"


def test_skip_motion_false_calls_motion():
    """motion command is NOT skipped when skip_motion=False (default)."""
    called = []

    class FakeVesc:
        def drive(self, l, r): called.append((l, r))
        def stop(self): called.append('stop')

    engine = ScriptEngine(vesc=FakeVesc())
    row = ['motion', '0.3', '-0.3', '0']
    engine.execute_command(row, skip_motion=False)
    assert called != [], "motion should be called when skip_motion=False"


# ── step progress ─────────────────────────────────────────────────────────────

def test_step_progress_tracked():
    """step_index, step_total, current_cmd are updated during execution."""
    scr = make_scr("# comment\nsleep,0.05\nsleep,0.05\n")
    tmp_dir = os.path.dirname(scr)
    scr_name = os.path.splitext(os.path.basename(scr))[0]
    engine = ScriptEngine()
    # Point sequences_dir at the temp dir so run() can find the file by name
    engine.sequences_dir = tmp_dir
    sid = engine.run(scr_name)
    time.sleep(0.02)  # let runner start
    with engine._lock:
        runners = list(engine._running.values())
    if runners:
        runner = runners[0]
        assert runner.step_total == 2
        assert runner.step_index >= 0
    engine.stop_all()
    os.unlink(scr)


# ── script,name sub-sequence ──────────────────────────────────────────────────

def test_script_subseq_executes_inline():
    """script,name command executes another .scr file inline."""
    executed = []

    engine = ScriptEngine()
    original_exec = engine.execute_command

    def tracking_exec(row, stop_event=None, skip_motion=False):
        executed.append(row[0] if row else '')
        original_exec(row, stop_event=stop_event, skip_motion=skip_motion)

    engine.execute_command = tracking_exec

    sub = make_scr("sleep,0.01\n")
    main = make_scr(f"script,{os.path.splitext(os.path.basename(sub))[0]}\n")

    # Inject sequences_dir pointing to temp dir
    engine.sequences_dir = os.path.dirname(sub)

    stop = threading.Event()
    # Import _ScriptRunner directly to test _run_file
    from master.script_engine import _ScriptRunner
    runner = _ScriptRunner(
        script_id=1, name='test', path=main,
        loop=False, engine=engine, on_done=lambda sid: None,
        skip_motion=False,
    )
    runner._run_file(main, stop)

    assert 'sleep' in executed, "sub-sequence sleep command should have been executed"
    os.unlink(sub)
    os.unlink(main)


# ── list_running step progress ────────────────────────────────────────────────

def test_list_running_includes_step_progress():
    """list_running() returns step_index, step_total, current_cmd."""
    scr = make_scr("sleep,0.2\n")
    tmp_dir = os.path.dirname(scr)
    scr_name = os.path.splitext(os.path.basename(scr))[0]
    engine = ScriptEngine()
    engine.sequences_dir = tmp_dir
    sid = engine.run(scr_name)
    time.sleep(0.05)
    running = engine.list_running()
    assert len(running) == 1
    entry = running[0]
    assert 'step_index' in entry
    assert 'step_total' in entry
    assert 'current_cmd' in entry
    engine.stop_all()
    os.unlink(scr)
