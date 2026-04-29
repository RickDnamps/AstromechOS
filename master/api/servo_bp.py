# ============================================================
#  ██████╗ ██████╗       ██████╗ ██████╗
#  ██╔══██╗╚════██╗      ██╔══██╗╚════██╗
#  ██████╔╝ █████╔╝      ██║  ██║ █████╔╝
#  ██╔══██╗██╔═══╝       ██║  ██║██╔═══╝
#  ██║  ██║███████╗      ██████╔╝███████╗
#  ╚═╝  ╚═╝╚══════╝      ╚═════╝ ╚══════╝
#
#  R2-D2 Control System — Distributed Robot Controller
# ============================================================
#  Copyright (C) 2025 RickDnamps
#  https://github.com/RickDnamps/R2D2_Control
#
#  This file is part of R2D2_Control.
#
#  R2D2_Control is free software: you can redistribute it
#  and/or modify it under the terms of the GNU General
#  Public License as published by the Free Software
#  Foundation, either version 2 of the License, or
#  (at your option) any later version.
#
#  R2D2_Control is distributed in the hope that it will be
#  useful, but WITHOUT ANY WARRANTY; without even the implied
#  warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
#  PURPOSE. See the GNU General Public License for details.
#
#  You should have received a copy of the GNU GPL along with
#  R2D2_Control. If not, see <https://www.gnu.org/licenses/>.
# ============================================================
"""
Blueprint API Servo — Phase 4 (MG90S 180°).
Controls body servos (via UART → Slave) and dome servos (local Master).

Each panel has its own open angle (open_angle) and close angle
(close_angle). Angles are passed directly to the drivers — no more
duration calculation (legacy SG90 CR removed).

Config in local.cfg, section [servo_panels]:
    dome_panel_1_open  = 110      # open angle (10–170°)
    dome_panel_1_close = 20       # close angle (10–170°)
    body_panel_1_open  = 110
    body_panel_1_close = 20
    ...

Dome endpoints (Master PCA9685 @ 0x40 direct):
  POST /servo/dome/open          {"name": "dome_panel_1"}
  POST /servo/dome/close         {"name": "dome_panel_1"}
  POST /servo/dome/open_all
  POST /servo/dome/close_all
  GET  /servo/dome/list
  GET  /servo/dome/state

Body endpoints (Slave PCA9685 @ 0x41 via UART):
  POST /servo/body/open          {"name": "body_panel_1"}
  POST /servo/body/close         {"name": "body_panel_1"}
  POST /servo/body/open_all
  POST /servo/body/close_all
  GET  /servo/body/list
  GET  /servo/body/state

Calibration:
  GET  /servo/settings           → {panels: {name: {open, close}}}
  POST /servo/settings           → {panels: {name: {open, close}}}
"""

import configparser
import json
import os
import subprocess

from flask import Blueprint, request, jsonify
import master.registry as reg
from master.config.config_loader import write_cfg_atomic

servo_bp = Blueprint('servo', __name__, url_prefix='/servo')

_MAIN_CFG          = '/home/artoo/r2d2/master/config/main.cfg'
_LOCAL_CFG         = '/home/artoo/r2d2/master/config/local.cfg'
_DOME_ANGLES_FILE  = '/home/artoo/r2d2/master/config/dome_angles.json'
_SLAVE_ANGLES_FILE = '/home/artoo/r2d2/slave/config/servo_angles.json'


def _slave_host() -> str:
    """Read Slave host from local.cfg [slave] host — configurable per installation."""
    cfg = configparser.ConfigParser()
    cfg.read([_MAIN_CFG, _LOCAL_CFG])
    return 'artoo@' + cfg.get('slave', 'host', fallback='r2-slave.local')

BODY_SERVOS = [f'Servo_S{i}' for i in range(16)]
DOME_SERVOS = [f'Servo_M{i}' for i in range(16)]
_ALL_PANELS = DOME_SERVOS + BODY_SERVOS

_DEFAULT_OPEN  = 110
_DEFAULT_CLOSE =  20
_DEFAULT_SPEED =  10
_ANGLE_MIN     =  10
_ANGLE_MAX     = 170
_SPEED_MIN     =   1
_SPEED_MAX     =  10


# ================================================================
# Helpers config per-panel
# ================================================================

def _clamp(val: int) -> int:
    return max(_ANGLE_MIN, min(_ANGLE_MAX, val))

def _clamp_speed(val: int) -> int:
    return max(_SPEED_MIN, min(_SPEED_MAX, val))


def _read_panels_cfg() -> dict:
    """Returns {'panels': {name: {'label': str, 'open': int, 'close': int, 'speed': int}}}"""
    dome_json: dict = {}
    body_json: dict = {}
    try:
        with open(_DOME_ANGLES_FILE) as f:
            dome_json = json.load(f)
    except Exception:
        pass
    try:
        with open(_SLAVE_ANGLES_FILE) as f:
            body_json = json.load(f)
    except Exception:
        pass

    panels = {}
    for name in DOME_SERVOS:
        j = dome_json.get(name, {})
        panels[name] = {
            'label': j.get('label', name),
            'open':  _clamp(int(j.get('open',  _DEFAULT_OPEN))),
            'close': _clamp(int(j.get('close', _DEFAULT_CLOSE))),
            'speed': _clamp_speed(int(j.get('speed', _DEFAULT_SPEED))),
        }
    for name in BODY_SERVOS:
        j = body_json.get(name, {})
        panels[name] = {
            'label': j.get('label', name),
            'open':  _clamp(int(j.get('open',  _DEFAULT_OPEN))),
            'close': _clamp(int(j.get('close', _DEFAULT_CLOSE))),
            'speed': _clamp_speed(int(j.get('speed', _DEFAULT_SPEED))),
        }
    return {'panels': panels}


def _write_panels_cfg(panels: dict) -> None:
    # Sync to JSON files (source of truth for drivers)
    _sync_angles_json(panels)


def _update_angles_file(filepath: str, panels: dict, names: list) -> None:
    """Updates a JSON angles file with the provided panels."""
    subset = {k: v for k, v in panels.items() if k in names}
    if not subset:
        return
    existing = {}
    if os.path.exists(filepath):
        try:
            with open(filepath) as f:
                existing = json.load(f)
        except Exception:
            pass
    for name, vals in subset.items():
        existing[name] = {
            'label': str(vals.get('label', existing.get(name, {}).get('label', name)))[:40],
            'open':  _clamp(int(vals.get('open',  existing.get(name, {}).get('open',  110)))),
            'close': _clamp(int(vals.get('close', existing.get(name, {}).get('close',  20)))),
            'speed': _clamp_speed(int(vals.get('speed', existing.get(name, {}).get('speed', 10)))),
        }
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w') as f:
        json.dump(existing, f, indent=2)


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
        scp_result = subprocess.run(
            ['scp', _SLAVE_ANGLES_FILE, f'{_slave_host()}:{_SLAVE_ANGLES_FILE}'],
            timeout=5, check=False, capture_output=True,
        )
        if scp_result.returncode == 0:
            if reg.uart:
                reg.uart.send('SRV', 'RELOAD')
        else:
            log.warning("SCP servo_angles.json to Slave failed (rc=%d) — Slave not reloaded", scp_result.returncode)
    except Exception as e:
        log.warning("Sync servo_angles.json to Slave failed: %s", e)


def _panel_angle(name: str, direction: str, panels_cfg: dict) -> int:
    panel = panels_cfg['panels'].get(name, {})
    return panel.get('open' if direction == 'open' else 'close',
                     _DEFAULT_OPEN if direction == 'open' else _DEFAULT_CLOSE)

def _panel_speed(name: str, panels_cfg: dict) -> int:
    return panels_cfg['panels'].get(name, {}).get('speed', _DEFAULT_SPEED)


# ================================================================
# BODY SERVOS (via UART → Slave)
# ================================================================

@servo_bp.get('/body/list')
def body_list():
    return jsonify({'servos': BODY_SERVOS})


@servo_bp.get('/body/state')
def body_state():
    return jsonify(reg.servo.state if reg.servo else {})


@servo_bp.post('/body/move')
def body_move():
    body     = request.get_json(silent=True) or {}
    name     = body.get('name', '')
    position = float(body.get('position', 0.0))
    if not name:
        return jsonify({'error': 'Field "name" required'}), 400
    cfg         = _read_panels_cfg()
    open_angle  = _panel_angle(name, 'open',  cfg)
    close_angle = _panel_angle(name, 'close', cfg)
    if reg.servo:
        reg.servo.move(name, position, open_angle, close_angle)
    elif reg.uart:
        angle = close_angle + max(0.0, min(1.0, position)) * (open_angle - close_angle)
        reg.uart.send('SRV', f'{name},{angle:.1f}')
    return jsonify({'status': 'ok', 'name': name, 'position': position})


@servo_bp.post('/body/open')
def body_open():
    body = request.get_json(silent=True) or {}
    name = body.get('name', '')
    if not name:
        return jsonify({'error': 'Field "name" required'}), 400
    cfg   = _read_panels_cfg()
    angle = _panel_angle(name, 'open', cfg)
    speed = _panel_speed(name, cfg)
    if reg.servo:
        reg.servo.open(name, angle, speed)
    elif reg.uart:
        reg.uart.send('SRV', f'{name},{angle}')
    return jsonify({'status': 'ok', 'name': name, 'angle': angle})


@servo_bp.post('/body/close')
def body_close():
    body = request.get_json(silent=True) or {}
    name = body.get('name', '')
    if not name:
        return jsonify({'error': 'Field "name" required'}), 400
    cfg   = _read_panels_cfg()
    angle = _panel_angle(name, 'close', cfg)
    speed = _panel_speed(name, cfg)
    if reg.servo:
        reg.servo.close(name, angle, speed)
    elif reg.uart:
        reg.uart.send('SRV', f'{name},{angle}')
    return jsonify({'status': 'ok', 'name': name, 'angle': angle})


@servo_bp.post('/body/open_all')
def body_open_all():
    cfg = _read_panels_cfg()
    for name in BODY_SERVOS:
        angle = _panel_angle(name, 'open', cfg)
        speed = _panel_speed(name, cfg)
        if reg.servo:
            reg.servo.open(name, angle, speed)
        elif reg.uart:
            reg.uart.send('SRV', f'{name},{angle},{speed}')
    return jsonify({'status': 'ok'})


@servo_bp.post('/body/close_all')
def body_close_all():
    cfg = _read_panels_cfg()
    for name in BODY_SERVOS:
        angle = _panel_angle(name, 'close', cfg)
        speed = _panel_speed(name, cfg)
        if reg.servo:
            reg.servo.close(name, angle, speed)
        elif reg.uart:
            reg.uart.send('SRV', f'{name},{angle},{speed}')
    return jsonify({'status': 'ok'})


# ================================================================
# DOME SERVOS (direct PCA9685 @ 0x40 on Master)
# ================================================================

@servo_bp.get('/dome/list')
def dome_list():
    return jsonify({'servos': DOME_SERVOS})


@servo_bp.get('/dome/state')
def dome_state():
    return jsonify(reg.dome_servo.state if reg.dome_servo else {})


@servo_bp.post('/dome/move')
def dome_move():
    body     = request.get_json(silent=True) or {}
    name     = body.get('name', '')
    position = float(body.get('position', 0.0))
    if not name:
        return jsonify({'error': 'Field "name" required'}), 400
    if not reg.dome_servo:
        return jsonify({'error': 'dome_servo driver not ready — check master logs'}), 503
    cfg         = _read_panels_cfg()
    open_angle  = _panel_angle(name, 'open',  cfg)
    close_angle = _panel_angle(name, 'close', cfg)
    reg.dome_servo.move(name, position, open_angle, close_angle)
    return jsonify({'status': 'ok', 'name': name, 'position': position})


@servo_bp.post('/dome/open')
def dome_open():
    body = request.get_json(silent=True) or {}
    name = body.get('name', '')
    if not name:
        return jsonify({'error': 'Field "name" required'}), 400
    if not reg.dome_servo:
        return jsonify({'error': 'dome_servo driver not ready — check master logs'}), 503
    cfg   = _read_panels_cfg()
    angle = _panel_angle(name, 'open', cfg)
    speed = _panel_speed(name, cfg)
    reg.dome_servo.open(name, angle, speed)
    return jsonify({'status': 'ok', 'name': name, 'angle': angle})


@servo_bp.post('/dome/close')
def dome_close():
    body = request.get_json(silent=True) or {}
    name = body.get('name', '')
    if not name:
        return jsonify({'error': 'Field "name" required'}), 400
    if not reg.dome_servo:
        return jsonify({'error': 'dome_servo driver not ready — check master logs'}), 503
    cfg   = _read_panels_cfg()
    angle = _panel_angle(name, 'close', cfg)
    speed = _panel_speed(name, cfg)
    reg.dome_servo.close(name, angle, speed)
    return jsonify({'status': 'ok', 'name': name, 'angle': angle})


@servo_bp.post('/dome/open_all')
def dome_open_all():
    if not reg.dome_servo:
        return jsonify({'status': 'ok'})
    cfg = _read_panels_cfg()
    for name in DOME_SERVOS:
        reg.dome_servo.open(name, _panel_angle(name, 'open', cfg), _panel_speed(name, cfg))
    return jsonify({'status': 'ok'})


@servo_bp.post('/dome/close_all')
def dome_close_all():
    if not reg.dome_servo:
        return jsonify({'status': 'ok'})
    cfg = _read_panels_cfg()
    for name in DOME_SERVOS:
        reg.dome_servo.close(name, _panel_angle(name, 'close', cfg), _panel_speed(name, cfg))
    return jsonify({'status': 'ok'})


# ================================================================
# ARMS CONFIG — which body servos are the arm servos
# ================================================================

_ARM_COUNT_MAX = 4


def _read_arms_cfg() -> dict:
    """Returns {count, servos[4], panels[4]} from local.cfg [arms].
    Always returns exactly 4 slots (empty string = not assigned).
    Values are servo IDs (e.g. 'Servo_S12'), never labels.
    """
    cfg = configparser.ConfigParser()
    cfg.read(_LOCAL_CFG)
    count  = max(0, min(_ARM_COUNT_MAX, cfg.getint('arms', 'count', fallback=0)))
    servos = [cfg.get('arms', f'arm_{i}',   fallback='').strip() for i in range(1, _ARM_COUNT_MAX + 1)]
    panels = [cfg.get('arms', f'panel_{i}', fallback='').strip() for i in range(1, _ARM_COUNT_MAX + 1)]
    return {'count': count, 'servos': servos, 'panels': panels}


@servo_bp.get('/arms')
def arms_config_get():
    return jsonify(_read_arms_cfg())


@servo_bp.post('/arms')
def arms_config_save():
    data   = request.get_json(silent=True) or {}
    count  = max(0, min(_ARM_COUNT_MAX, int(data.get('count', 0))))
    servos = data.get('servos', [])
    panels = data.get('panels', [])
    cfg = configparser.ConfigParser()
    cfg.read(_LOCAL_CFG)
    if not cfg.has_section('arms'):
        cfg.add_section('arms')
    cfg.set('arms', 'count', str(count))
    for i in range(1, _ARM_COUNT_MAX + 1):
        raw_servo = servos[i - 1] if i - 1 < len(servos) else ''
        raw_panel = panels[i - 1] if i - 1 < len(panels) else ''
        # Only accept valid body servo IDs — never store labels
        cfg.set('arms', f'arm_{i}',   raw_servo if raw_servo in BODY_SERVOS else '')
        cfg.set('arms', f'panel_{i}', raw_panel if raw_panel in BODY_SERVOS else '')
    os.makedirs(os.path.dirname(_LOCAL_CFG), exist_ok=True)
    write_cfg_atomic(cfg, _LOCAL_CFG)
    import logging; logging.getLogger(__name__).info("Arms config saved: count=%d servos=%s panels=%s", count, servos, panels)
    return jsonify({'status': 'ok', **_read_arms_cfg()})


# ================================================================
# Backward compat — /servo/open_all|close_all (script_bp, legacy calls)
# ================================================================

@servo_bp.get('/list')
def servo_list():
    return jsonify({'servos': BODY_SERVOS + DOME_SERVOS})


@servo_bp.get('/state')
def servo_state():
    body_st = reg.servo.state      if reg.servo      else {}
    dome_st = reg.dome_servo.state if reg.dome_servo else {}
    return jsonify({**body_st, **dome_st})


@servo_bp.post('/open_all')
def servo_open_all():
    cfg = _read_panels_cfg()
    for name in BODY_SERVOS:
        angle = _panel_angle(name, 'open', cfg)
        speed = _panel_speed(name, cfg)
        if reg.servo:
            reg.servo.open(name, angle, speed)
        elif reg.uart:
            reg.uart.send('SRV', f'{name},{angle},{speed}')
    if reg.dome_servo:
        for name in DOME_SERVOS:
            reg.dome_servo.open(name, _panel_angle(name, 'open', cfg), _panel_speed(name, cfg))
    return jsonify({'status': 'ok'})


@servo_bp.post('/close_all')
def servo_close_all():
    cfg = _read_panels_cfg()
    for name in BODY_SERVOS:
        angle = _panel_angle(name, 'close', cfg)
        speed = _panel_speed(name, cfg)
        if reg.servo:
            reg.servo.close(name, angle, speed)
        elif reg.uart:
            reg.uart.send('SRV', f'{name},{angle},{speed}')
    if reg.dome_servo:
        for name in DOME_SERVOS:
            reg.dome_servo.close(name, _panel_angle(name, 'close', cfg), _panel_speed(name, cfg))
    return jsonify({'status': 'ok'})


# ================================================================
# Calibration per-panel
# ================================================================

@servo_bp.get('/settings')
def servo_settings_get():
    return jsonify(_read_panels_cfg())


@servo_bp.post('/settings')
def servo_settings_save():
    data   = request.get_json(silent=True) or {}
    panels = {}
    for name, vals in (data.get('panels') or {}).items():
        if name in _ALL_PANELS and isinstance(vals, dict):
            panels[name] = {
                'label': str(vals.get('label', name))[:40],
                'open':  _clamp(int(vals.get('open',  _DEFAULT_OPEN))),
                'close': _clamp(int(vals.get('close', _DEFAULT_CLOSE))),
                'speed': _clamp_speed(int(vals.get('speed', _DEFAULT_SPEED))),
            }
    _write_panels_cfg(panels)
    return jsonify(_read_panels_cfg())
