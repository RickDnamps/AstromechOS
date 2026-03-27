"""Tests for ChoreoPlayer — easing, interpolation, event queue, export."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from master.choreo_player import _ease, _interpolate


# ── Easing functions ──────────────────────────────────────────────────────────

def test_ease_linear_endpoints():
    assert _ease(0.0, 'linear') == pytest.approx(0.0)
    assert _ease(1.0, 'linear') == pytest.approx(1.0)

def test_ease_linear_midpoint():
    assert _ease(0.5, 'linear') == pytest.approx(0.5)

def test_ease_in_midpoint():
    # t² at t=0.5 → 0.25
    assert _ease(0.5, 'ease-in') == pytest.approx(0.25)

def test_ease_out_midpoint():
    # 1-(1-t)² at t=0.5 → 0.75
    assert _ease(0.5, 'ease-out') == pytest.approx(0.75)

def test_ease_in_out_midpoint():
    # Must be exactly 0.5 at t=0.5 (symmetric)
    assert _ease(0.5, 'ease-in-out') == pytest.approx(0.5)

def test_ease_unknown_falls_back_to_linear():
    assert _ease(0.3, 'unknown-easing') == pytest.approx(0.3)

def test_ease_clamps_below_zero():
    assert _ease(-0.5, 'ease-in') == pytest.approx(0.0)

def test_ease_clamps_above_one():
    assert _ease(1.5, 'ease-out') == pytest.approx(1.0)


# ── Angle interpolation ───────────────────────────────────────────────────────

def test_interpolate_linear_midpoint():
    kf = [
        {'t': 0.0,  'angle': 0,   'easing': 'linear'},
        {'t': 10.0, 'angle': 180, 'easing': 'linear'},
    ]
    assert _interpolate(5.0, kf) == pytest.approx(90.0)

def test_interpolate_clamps_before_first_keyframe():
    kf = [
        {'t': 2.0, 'angle': 45,  'easing': 'linear'},
        {'t': 8.0, 'angle': 135, 'easing': 'linear'},
    ]
    assert _interpolate(0.0, kf) == pytest.approx(45.0)

def test_interpolate_clamps_after_last_keyframe():
    kf = [
        {'t': 0.0, 'angle': 0,   'easing': 'linear'},
        {'t': 5.0, 'angle': 180, 'easing': 'linear'},
    ]
    assert _interpolate(20.0, kf) == pytest.approx(180.0)

def test_interpolate_ease_out_first_half_faster():
    kf = [
        {'t': 0.0,  'angle': 0,   'easing': 'linear'},
        {'t': 10.0, 'angle': 100, 'easing': 'ease-out'},
    ]
    # ease-out: 1-(1-0.5)^2 = 0.75 → 75 degrees at t=5
    assert _interpolate(5.0, kf) == pytest.approx(75.0)

def test_interpolate_three_keyframes_selects_correct_segment():
    kf = [
        {'t': 0.0,  'angle': 0,   'easing': 'linear'},
        {'t': 5.0,  'angle': 100, 'easing': 'linear'},
        {'t': 10.0, 'angle': 200, 'easing': 'linear'},
    ]
    # t=7.5 is in second segment: 100 + (200-100)*0.5 = 150
    assert _interpolate(7.5, kf) == pytest.approx(150.0)


# ── ChoreoPlayer event queue ──────────────────────────────────────────────────

from master.choreo_player import ChoreoPlayer


def _make_player(latency=0.10):
    """Create a ChoreoPlayer with all drivers mocked as None."""
    return ChoreoPlayer(
        cfg=None, audio=None, teeces=None,
        dome_motor=None, dome_servo=None, body_servo=None,
        audio_latency=latency,
    )


def test_event_queue_sorted_by_time():
    player = _make_player()
    tracks = {
        'audio':      [{'t': 5.0, 'action': 'play', 'file': 'TEST'}],
        'lights':     [{'t': 2.0, 'duration': 3.0, 'action': 'mode', 'mode': 'random'}],
        'servos':     [{'t': 1.0, 'servo': 'dome_panel_1', 'action': 'open', 'duration': 0.5}],
        'propulsion': [],
    }
    events = player._build_event_queue(tracks)
    times = [e['t'] for e in events]
    assert times == sorted(times)


def test_audio_events_not_shifted():
    player = _make_player(latency=0.10)
    tracks = {
        'audio':      [{'t': 0.0, 'action': 'play', 'file': 'CANTINA'}],
        'lights':     [],
        'servos':     [],
        'propulsion': [],
    }
    events = player._build_event_queue(tracks)
    audio_events = [e for e in events if e['track'] == 'audio']
    assert audio_events[0]['t'] == pytest.approx(0.0)


def test_non_audio_events_shifted_by_latency():
    player = _make_player(latency=0.10)
    tracks = {
        'audio':      [],
        'lights':     [{'t': 2.0, 'duration': 3.0, 'action': 'mode', 'mode': 'random'}],
        'servos':     [{'t': 1.0, 'servo': 'dome_panel_1', 'action': 'open', 'duration': 0.5}],
        'propulsion': [],
    }
    events = player._build_event_queue(tracks)
    lights_ev = next(e for e in events if e['track'] == 'lights' and e.get('action') == 'mode')
    servo_ev  = next(e for e in events if e['track'] == 'servos')
    assert lights_ev['t'] == pytest.approx(2.10)
    assert servo_ev['t']  == pytest.approx(1.10)


def test_lights_block_gets_auto_restore_event():
    player = _make_player(latency=0.0)
    tracks = {
        'audio':      [],
        'lights':     [{'t': 5.0, 'duration': 3.0, 'action': 'mode', 'mode': 'alarm'}],
        'servos':     [],
        'propulsion': [],
    }
    events = player._build_event_queue(tracks)
    restore_events = [
        e for e in events
        if e['track'] == 'lights' and e.get('_auto_restore') is True
    ]
    assert len(restore_events) == 1
    assert restore_events[0]['t'] == pytest.approx(8.0)   # 5.0 + 3.0


def test_propulsion_block_gets_auto_stop():
    player = _make_player(latency=0.0)
    tracks = {
        'audio':      [],
        'lights':     [],
        'servos':     [],
        'propulsion': [{'t': 10.0, 'duration': 2.0, 'left': 0.3, 'right': 0.3}],
    }
    events = player._build_event_queue(tracks)
    stop_events = [
        e for e in events
        if e['track'] == 'propulsion' and e.get('action') == 'stop'
    ]
    assert len(stop_events) == 1
    assert stop_events[0]['t'] == pytest.approx(12.0)   # 10.0 + 2.0


# ── Export to .scr ────────────────────────────────────────────────────────────

def test_export_scr_contains_header_comment():
    player = _make_player(latency=0.0)
    chor = {
        'meta': {'name': 'my_show', 'duration': 5.0},
        'tracks': {
            'audio': [], 'lights': [], 'dome': [],
            'servos': [], 'propulsion': [], 'markers': [],
        }
    }
    scr = player.export_scr(chor)
    assert '# Exported from my_show.chor' in scr
    assert '# WARNING' in scr


def test_export_scr_audio_play():
    player = _make_player(latency=0.0)
    chor = {
        'meta': {'name': 'test', 'duration': 5.0},
        'tracks': {
            'audio': [{'t': 0.0, 'action': 'play', 'file': 'CANTINA'}],
            'lights': [], 'dome': [], 'servos': [], 'propulsion': [], 'markers': [],
        }
    }
    lines = [l for l in player.export_scr(chor).splitlines() if l and not l.startswith('#')]
    assert 'sound,CANTINA' in lines


def test_export_scr_sleep_between_events():
    player = _make_player(latency=0.0)
    chor = {
        'meta': {'name': 'test', 'duration': 10.0},
        'tracks': {
            'audio': [{'t': 0.0, 'action': 'play', 'file': 'CANTINA'}],
            'lights': [],
            'dome': [],
            'servos': [{'t': 2.0, 'servo': 'dome_panel_1', 'action': 'open', 'duration': 0.5}],
            'propulsion': [], 'markers': [],
        }
    }
    lines = [l for l in player.export_scr(chor).splitlines() if l and not l.startswith('#')]
    assert lines[0] == 'sound,CANTINA'
    assert lines[1] == 'sleep,2.00'
    assert lines[2] == 'servo,dome_panel_1,open'


def test_export_scr_servo_close():
    player = _make_player(latency=0.0)
    chor = {
        'meta': {'name': 'test', 'duration': 5.0},
        'tracks': {
            'audio': [],
            'lights': [],
            'dome': [],
            'servos': [{'t': 1.0, 'servo': 'all', 'action': 'close', 'duration': 0.5}],
            'propulsion': [], 'markers': [],
        }
    }
    lines = [l for l in player.export_scr(chor).splitlines() if l and not l.startswith('#')]
    assert 'servo,all,close' in lines


def test_export_scr_lights_mode():
    player = _make_player(latency=0.0)
    chor = {
        'meta': {'name': 'test', 'duration': 5.0},
        'tracks': {
            'audio': [],
            'lights': [{'t': 0.0, 'duration': 5.0, 'action': 'mode', 'mode': 'disco'}],
            'dome': [], 'servos': [], 'propulsion': [], 'markers': [],
        }
    }
    lines = [l for l in player.export_scr(chor).splitlines() if l and not l.startswith('#')]
    assert 'teeces,anim,13' in lines


def test_export_scr_propulsion():
    player = _make_player(latency=0.0)
    chor = {
        'meta': {'name': 'test', 'duration': 10.0},
        'tracks': {
            'audio': [], 'lights': [], 'dome': [],
            'servos': [],
            'propulsion': [{'t': 3.0, 'duration': 2.0, 'left': 0.5, 'right': 0.5}],
            'markers': [],
        }
    }
    lines = [l for l in player.export_scr(chor).splitlines() if l and not l.startswith('#')]
    assert any('motion,0.5,0.5' in l for l in lines)
    assert 'motion,stop' in lines
