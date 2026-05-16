# ============================================================
#   █████╗  ██████╗ ███████╗
#  ██╔══██╗██╔═══██╗██╔════╝
#  ███████║██║   ██║███████╗
#  ██╔══██║██║   ██║╚════██║
#  ██║  ██║╚██████╔╝███████║
#  ╚═╝  ╚═╝ ╚═════╝ ╚══════╝
#
#  AstromechOS — Open control platform for astromech builders
# ============================================================
#  Copyright (C) 2026 RickDnamps
#  https://github.com/RickDnamps/AstromechOS
#
#  This file is part of AstromechOS.
#
#  AstromechOS is free software: you can redistribute it
#  and/or modify it under the terms of the GNU General
#  Public License as published by the Free Software
#  Foundation, either version 2 of the License, or
#  (at your option) any later version.
#
#  AstromechOS is distributed in the hope that it will be
#  useful, but WITHOUT ANY WARRANTY; without even the implied
#  warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
#  PURPOSE. See the GNU General Public License for details.
#
#  You should have received a copy of the GNU GPL along with
#  AstromechOS. If not, see <https://www.gnu.org/licenses/>.
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
import logging
import os
import subprocess
import threading
import time

from flask import Blueprint, request, jsonify
from master.api._admin_auth import require_admin
import master.registry as reg
from master.config.config_loader import write_cfg_atomic

log = logging.getLogger(__name__)
# B-49 (audit 2026-05-15): share settings_bp's write lock so concurrent
# /servo/arms + /settings/config can't race on local.cfg RMW.
from master.api.settings_bp import _cfg_write_lock

servo_bp = Blueprint('servo', __name__, url_prefix='/servo')

from shared.paths import MAIN_CFG as _MAIN_CFG, LOCAL_CFG as _LOCAL_CFG, DOME_ANGLES as _DOME_ANGLES_FILE, SLAVE_ANGLES as _SLAVE_ANGLES_FILE


def _slave_host() -> str:
    """Read Slave host from local.cfg [slave] host — configurable per installation."""
    cfg = configparser.ConfigParser()
    cfg.read([_MAIN_CFG, _LOCAL_CFG])
    return 'artoo@' + cfg.get('slave', 'host', fallback='r2-slave.local')

def _read_hat_addresses() -> tuple[list, list]:
    """Returns (master_hat_addrs, slave_hat_addrs) from local.cfg [i2c_servo_hats].
    Defaults to one HAT each: Master 0x40, Slave 0x41.
    """
    cfg = configparser.ConfigParser()
    cfg.read([_MAIN_CFG, _LOCAL_CFG])
    def _parse(s: str) -> list[int]:
        # B-248 (remaining tabs audit 2026-05-15): log on parse fail
        # instead of silently dropping. Otherwise a typo like
        # `master_hats = 0xZZ` quietly drops to the fallback [0x40]
        # and the operator has no idea why their HAT isn't detected.
        result = []
        for p in s.split(','):
            p = p.strip()
            if p:
                try:
                    result.append(int(p, 16) if p.startswith('0x') else int(p))
                except ValueError:
                    log.warning("Invalid I2C HAT addr %r — ignored", p)
        return result
    master = _parse(cfg.get('i2c_servo_hats', 'master_hats', fallback='0x40')) or [0x40]
    slave  = _parse(cfg.get('i2c_servo_hats', 'slave_hats',  fallback='0x41')) or [0x41]
    return master, slave

_master_hat_addrs, _slave_hat_addrs = _read_hat_addresses()
DOME_SERVOS = [f'Servo_M{i}' for i in range(len(_master_hat_addrs) * 16)]
BODY_SERVOS = [f'Servo_S{i}' for i in range(len(_slave_hat_addrs)  * 16)]
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


def _safe_int(v, default: int) -> int:
    """B3 fix 2026-05-16: defensive int() — a hand-edited or corrupted
    angles JSON with `"open": "x"` used to raise ValueError inside
    _read_panels_cfg which crashed GET /servo/settings with 500 →
    the entire Calibration sub-panel became unreachable until the
    file was fixed by SSH. Now falls back to the default silently and
    the bad value gets normalized on next save."""
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


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

    # Defensive in case the loaded JSON isn't a dict (e.g. file is just `null`)
    if not isinstance(dome_json, dict): dome_json = {}
    if not isinstance(body_json, dict): body_json = {}

    panels = {}
    for name in DOME_SERVOS:
        j = dome_json.get(name, {}) if isinstance(dome_json.get(name), dict) else {}
        panels[name] = {
            'label': str(j.get('label', name))[:40],
            'open':  _clamp(_safe_int(j.get('open',  _DEFAULT_OPEN),  _DEFAULT_OPEN)),
            'close': _clamp(_safe_int(j.get('close', _DEFAULT_CLOSE), _DEFAULT_CLOSE)),
            'speed': _clamp_speed(_safe_int(j.get('speed', _DEFAULT_SPEED), _DEFAULT_SPEED)),
        }
    for name in BODY_SERVOS:
        j = body_json.get(name, {}) if isinstance(body_json.get(name), dict) else {}
        panels[name] = {
            'label': str(j.get('label', name))[:40],
            'open':  _clamp(_safe_int(j.get('open',  _DEFAULT_OPEN),  _DEFAULT_OPEN)),
            'close': _clamp(_safe_int(j.get('close', _DEFAULT_CLOSE), _DEFAULT_CLOSE)),
            'speed': _clamp_speed(_safe_int(j.get('speed', _DEFAULT_SPEED), _DEFAULT_SPEED)),
        }
    return {'panels': panels}


def _write_panels_cfg(panels: dict) -> None:
    # Sync to JSON files (source of truth for drivers)
    _sync_angles_json(panels)


# B-205 (remaining tabs audit 2026-05-15): single lock for the angle
# JSON files. Two concurrent /servo/settings + /servo/arms posts both
# call _sync_angles_json which RMW's the same files; without this lock
# the second writer's `existing` dict is the pre-first-write snapshot
# → first writer's label changes are silently lost.
_angles_lock = threading.Lock()


def _update_angles_file(filepath: str, panels: dict, names: list) -> None:
    """Updates a JSON angles file with the provided panels.

    B-204 (remaining tabs audit 2026-05-15): atomic write — tmp +
    os.replace + fsync. Previously open(w) truncated then wrote; a
    crash between truncate and write left an empty/partial file. On
    next reload (`reg.dome_servo.reload()`) the empty dict cleared
    EVERY servo's calibration in memory. Same hardening pattern as
    settings_bp write_cfg_atomic.

    Caller MUST hold _angles_lock so two concurrent updates don't read
    a pre-first-write `existing` and overwrite each other's edits."""
    subset = {k: v for k, v in panels.items() if k in names}
    if not subset:
        return
    existing = {}
    if os.path.exists(filepath):
        try:
            with open(filepath) as f:
                existing = json.load(f)
            if not isinstance(existing, dict):
                raise json.JSONDecodeError("not a dict at top level", "", 0)
        except (OSError, json.JSONDecodeError) as e:
            # E12 fix 2026-05-16: was starting with existing={} which
            # meant a per-HAT save (subset of 16 servos) would WIPE all
            # the other HATs' calibration from disk → cascading data
            # loss after one corruption event. Quarantine the bad file
            # to `.broken-<ts>` and refuse the save so operator can
            # recover manually. The lock is released by the caller.
            import time as _time
            broken_path = f"{filepath}.broken-{int(_time.time())}"
            try:
                os.replace(filepath, broken_path)
                log.error("angles file %s corrupted (%s) — quarantined to %s",
                          filepath, e, broken_path)
            except OSError:
                log.exception("failed to quarantine corrupted angles file %s", filepath)
            raise RuntimeError(
                f"angles file corrupted; quarantined to {broken_path}. "
                f"Restore from backup or restart Master to regenerate defaults."
            )
    for name, vals in subset.items():
        prev = existing.get(name) if isinstance(existing.get(name), dict) else {}
        existing[name] = {
            'label': str(vals.get('label', prev.get('label', name)))[:40],
            'open':  _clamp(_safe_int(vals.get('open',  prev.get('open',  110)), 110)),
            'close': _clamp(_safe_int(vals.get('close', prev.get('close',  20)),  20)),
            'speed': _clamp_speed(_safe_int(vals.get('speed', prev.get('speed', 10)), 10)),
        }
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    # User-reported 2026-05-16: rotate 3 .bak generations BEFORE writing
    # so an unintended mutation (audit script, cascade label revert,
    # operator fat-finger) can be reverted via SSH:
    #   cp dome_angles.json.bak1 dome_angles.json && restart astromechos
    from master.config.config_loader import rotate_backup as _rotate
    _rotate(filepath)
    tmp = filepath + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(existing, f, indent=2)
        f.flush()
        try:
            os.fsync(f.fileno())
        except OSError:
            pass
    # Audit finding M-7 2026-05-15: matches write_cfg_atomic chmod
    # 0o600 — these JSON files hold operator-set labels which are
    # config-grade content, not just opaque servo angles.
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, filepath)


class AnglesCorruptedError(RuntimeError):
    """E12 fix 2026-05-16: signaled when an angles JSON file is
    corrupted and was quarantined. Caller (save endpoint) should
    return 503 with the message so operator sees a clear error
    instead of a silent partial save."""
    pass


def _sync_angles_json(panels: dict) -> None:
    """Writes dome_angles.json (Master) and servo_angles.json (Slave via scp).
    Notifies both drivers to reload angles immediately — no service restart needed.

    B-205 (remaining tabs audit 2026-05-15): the whole read+write+SCP
    cycle runs under _angles_lock so concurrent /servo/settings +
    /servo/arms posts can't lose each other's label changes.

    Raises AnglesCorruptedError if either file was quarantined —
    save endpoint should respond 503.
    """
    with _angles_lock:
        try:
            _update_angles_file(_DOME_ANGLES_FILE, panels, DOME_SERVOS)
            if reg.dome_servo and reg.dome_servo.is_ready():
                reg.dome_servo.reload()
        except OSError as e:
            log.warning("Failed to write dome_angles.json: %s", e)
        except RuntimeError as e:
            raise AnglesCorruptedError(str(e)) from e
        try:
            _update_angles_file(_SLAVE_ANGLES_FILE, panels, BODY_SERVOS)
        except OSError as e:
            log.warning("Failed to write servo_angles.json: %s", e)
            return
        except RuntimeError as e:
            raise AnglesCorruptedError(str(e)) from e
    # B-225 (remaining tabs audit 2026-05-15): SCP runs in a daemon
    # thread now. Was blocking the Flask request thread for up to 5s;
    # rapid Calibration saves (operator iterating angles) stacked
    # threads. The reload signal still fires on success — operator
    # sees the new angles take effect within ~1s of SCP completion.
    # E10 fix 2026-05-16: track sync status in module-level dict so the
    # next POST response can surface a warning if the Slave didn't get
    # the file. Was: fire-and-forget log.warning only → operator drove
    # the robot with stale Slave angles, never knew.
    def _bg_scp_and_reload():
        global _last_slave_sync_status
        import time as _t
        _last_slave_sync_status = {'attempted': True, 'ok': False, 'error': 'running', 'ts': _t.time()}
        try:
            scp_result = subprocess.run(
                ['scp', _SLAVE_ANGLES_FILE, f'{_slave_host()}:{_SLAVE_ANGLES_FILE}'],
                timeout=5, check=False, capture_output=True,
            )
        except (subprocess.TimeoutExpired, OSError) as e:
            log.warning("Sync servo_angles.json to Slave failed: %s", e)
            _last_slave_sync_status = {'attempted': True, 'ok': False, 'error': str(e), 'ts': _t.time()}
            return
        if scp_result.returncode == 0:
            if reg.uart:
                reg.uart.send('SRV', 'RELOAD')
            _last_slave_sync_status = {'attempted': True, 'ok': True, 'error': None, 'ts': _t.time()}
        else:
            err = scp_result.stderr.decode(errors='replace').strip()[:200] or f'rc={scp_result.returncode}'
            log.warning("SCP servo_angles.json to Slave failed (rc=%d) — Slave not reloaded",
                        scp_result.returncode)
            _last_slave_sync_status = {'attempted': True, 'ok': False, 'error': err, 'ts': _t.time()}

    threading.Thread(target=_bg_scp_and_reload, daemon=True,
                     name='angles-sync').start()


# Module-level state for E10 (last Slave SFTP sync result). Read by
# servo_settings_save to surface a warning in the response when the
# operator saves body servo angles but the Slave push silently failed.
_last_slave_sync_status: dict = {'attempted': False, 'ok': True, 'error': None}


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


# B-260 / B-261 / B-262 (remaining tabs audit 2026-05-15): helper +
# allowlist gate for the body/dome move/open/close endpoints. Was:
# - `float(body.get('position', 0.0))` raised TypeError on list/dict
# - name passed straight to the driver which silently rejected unknown
#   names — API returned 200 with `{name: <bogus>}` instead of 400.
def _valid_servo_name(name: str, side: str) -> bool:
    if side == 'body':
        return name in BODY_SERVOS
    if side == 'dome':
        return name in DOME_SERVOS
    return False


def _safe_position(raw) -> float | None:
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    import math
    if not math.isfinite(v):
        return None
    return max(0.0, min(1.0, v))


# B2/E2 fix 2026-05-16: centralized safety gate for servo motion
# endpoints. Was missing on body_open/close/move + dome_open/close/move
# → operator clicking OPEN during E-STOP saw toast "OK" while physical
# servo refused (dome) OR moved anyway (body — no freeze flag in
# slave body_servo driver). Defense-in-depth: backend refuses 403,
# frontend doesn't need to know.
#
# Per-axis: dome endpoints also block if choreo_uses_dome (operator
# would race the choreo's dome events). Body endpoints don't have
# an equivalent per-axis choreo flag since 'body' tracks are panel
# state, not joystick — but we still block on E-STOP + stow.
def _check_servo_safety(side: str) -> tuple[bool, tuple]:
    """Return (ok, (response, status)) — caller uses:
       safe, resp = _check_servo_safety('dome')
       if not safe: return resp
    """
    if getattr(reg, 'estop_active', False):
        return False, (jsonify({'error': 'E-STOP engaged — release before moving servos'}), 403)
    if getattr(reg, 'stow_in_progress', False):
        return False, (jsonify({'error': 'stow in progress — wait until complete'}), 503)
    if side == 'dome' and reg.choreo is not None:
        try:
            st = reg.choreo.get_status() or {}
            if st.get('playing') and st.get('uses_dome'):
                return False, (jsonify({'error': 'choreo using dome — stop choreo first'}), 503)
        except Exception:
            pass
    return True, (None, 0)


@servo_bp.post('/body/move')
def body_move():
    safe, resp = _check_servo_safety('body')
    if not safe: return resp
    body     = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    name     = body.get('name', '')
    if not name:
        return jsonify({'error': 'Field "name" required'}), 400
    if not _valid_servo_name(name, 'body'):
        return jsonify({'error': f'unknown body servo: {name}'}), 404
    position = _safe_position(body.get('position', 0.0))
    if position is None:
        return jsonify({'error': 'position must be a float 0..1'}), 400
    cfg         = _read_panels_cfg()
    open_angle  = _panel_angle(name, 'open',  cfg)
    close_angle = _panel_angle(name, 'close', cfg)
    if reg.servo:
        reg.servo.move(name, position, open_angle, close_angle)
    elif reg.uart:
        angle = close_angle + position * (open_angle - close_angle)
        reg.uart.send('SRV', f'{name},{angle:.1f}')
    return jsonify({'status': 'ok', 'name': name, 'position': position})


@servo_bp.post('/body/open')
def body_open():
    safe, resp = _check_servo_safety('body')
    if not safe: return resp
    body = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    name = body.get('name', '')
    if not name:
        return jsonify({'error': 'Field "name" required'}), 400
    if not _valid_servo_name(name, 'body'):
        return jsonify({'error': f'unknown body servo: {name}'}), 404
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
    safe, resp = _check_servo_safety('body')
    if not safe: return resp
    body = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    name = body.get('name', '')
    if not name:
        return jsonify({'error': 'Field "name" required'}), 400
    if not _valid_servo_name(name, 'body'):
        return jsonify({'error': f'unknown body servo: {name}'}), 404
    cfg   = _read_panels_cfg()
    angle = _panel_angle(name, 'close', cfg)
    speed = _panel_speed(name, cfg)
    if reg.servo:
        reg.servo.close(name, angle, speed)
    elif reg.uart:
        reg.uart.send('SRV', f'{name},{angle}')
    return jsonify({'status': 'ok', 'name': name, 'angle': angle})


def _arm_servo_set() -> set:
    """Returns the set of servo IDs under arm control (arm servos + their panels).
    These are excluded from open_all/close_all — arm sequences must run in panel-first order.
    """
    arms = _read_arms_cfg()
    count = arms['count']
    return (
        {s for s in arms['servos'][:count] if s} |
        {s for s in arms['panels'][:count] if s}
    )


def _servo_open(name: str, cfg: dict) -> None:
    angle = _panel_angle(name, 'open', cfg)
    speed = _panel_speed(name, cfg)
    if reg.servo:
        reg.servo.open(name, angle, speed)
    elif reg.uart:
        reg.uart.send('SRV', f'{name},{angle},{speed}')


def _servo_close(name: str, cfg: dict) -> None:
    angle = _panel_angle(name, 'close', cfg)
    speed = _panel_speed(name, cfg)
    if reg.servo:
        reg.servo.close(name, angle, speed)
    elif reg.uart:
        reg.uart.send('SRV', f'{name},{angle},{speed}')


def _arm_open_sequence(arm: str, panel: str, delay: float, cfg: dict) -> None:
    """Open panel → wait delay → open arm (runs in its own thread).

    Audit findings M-3 + M-4 2026-05-15: previously silently ignored
    stow_in_progress (could write conflicting body-servo angles while
    safe-home was running) and swallowed driver errors (operator saw
    half-open arm with no error in UI). Now bails on stow and logs
    failures with full stack trace."""
    try:
        if getattr(reg, 'stow_in_progress', False):
            log.info("arm_open(%s) skipped — stow_in_progress", arm)
            return
        if panel:
            _servo_open(panel, cfg)
            time.sleep(delay)
        # Re-check stow after the delay — the safe-home stow may
        # have started between the two writes.
        if getattr(reg, 'stow_in_progress', False):
            log.info("arm_open(%s) aborted mid-sequence — stow_in_progress", arm)
            return
        _servo_open(arm, cfg)
    except Exception:
        log.exception("arm_open_sequence(arm=%s, panel=%s) failed", arm, panel)


def _arm_close_sequence(arm: str, panel: str, delay: float, cfg: dict) -> None:
    """Close arm → wait delay → close panel (runs in its own thread)."""
    try:
        if getattr(reg, 'stow_in_progress', False):
            log.info("arm_close(%s) skipped — stow_in_progress", arm)
            return
        _servo_close(arm, cfg)
        if panel:
            time.sleep(delay)
            if getattr(reg, 'stow_in_progress', False):
                log.info("arm_close(%s) aborted mid-sequence — stow_in_progress", arm)
                return
            _servo_close(panel, cfg)
    except Exception:
        log.exception("arm_close_sequence(arm=%s, panel=%s) failed", arm, panel)


def _launch_arm_sequences(arms_cfg: dict, cfg: dict, action: str) -> None:
    """Start one daemon thread per configured arm for open or close sequences."""
    for i in range(arms_cfg['count']):
        arm   = arms_cfg['servos'][i]
        panel = arms_cfg['panels'][i]
        delay = arms_cfg['delays'][i]
        if not arm:
            continue
        target = _arm_open_sequence if action == 'open' else _arm_close_sequence
        threading.Thread(target=target, args=(arm, panel, delay, cfg), daemon=True).start()


@servo_bp.post('/body/open_all')
def body_open_all():
    safe, resp = _check_servo_safety('body')
    if not safe: return resp
    cfg     = _read_panels_cfg()
    arm_set = _arm_servo_set()
    for name in BODY_SERVOS:
        if name in arm_set:
            continue
        _servo_open(name, cfg)
    _launch_arm_sequences(_read_arms_cfg(), cfg, 'open')
    return jsonify({'status': 'ok'})


@servo_bp.post('/body/close_all')
def body_close_all():
    safe, resp = _check_servo_safety('body')
    if not safe: return resp
    cfg     = _read_panels_cfg()
    arm_set = _arm_servo_set()
    for name in BODY_SERVOS:
        if name in arm_set:
            continue
        _servo_close(name, cfg)
    _launch_arm_sequences(_read_arms_cfg(), cfg, 'close')
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
    safe, resp = _check_servo_safety('dome')
    if not safe: return resp
    body     = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    name     = body.get('name', '')
    if not name:
        return jsonify({'error': 'Field "name" required'}), 400
    if not _valid_servo_name(name, 'dome'):
        return jsonify({'error': f'unknown dome servo: {name}'}), 404
    position = _safe_position(body.get('position', 0.0))
    if position is None:
        return jsonify({'error': 'position must be a float 0..1'}), 400
    if not reg.dome_servo:
        return jsonify({'error': 'dome_servo driver not ready — check master logs'}), 503
    cfg         = _read_panels_cfg()
    open_angle  = _panel_angle(name, 'open',  cfg)
    close_angle = _panel_angle(name, 'close', cfg)
    reg.dome_servo.move(name, position, open_angle, close_angle)
    return jsonify({'status': 'ok', 'name': name, 'position': position})


@servo_bp.post('/dome/open')
def dome_open():
    safe, resp = _check_servo_safety('dome')
    if not safe: return resp
    body = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    name = body.get('name', '')
    if not name:
        return jsonify({'error': 'Field "name" required'}), 400
    if not _valid_servo_name(name, 'dome'):
        return jsonify({'error': f'unknown dome servo: {name}'}), 404
    if not reg.dome_servo:
        return jsonify({'error': 'dome_servo driver not ready — check master logs'}), 503
    cfg   = _read_panels_cfg()
    angle = _panel_angle(name, 'open', cfg)
    speed = _panel_speed(name, cfg)
    reg.dome_servo.open(name, angle, speed)
    return jsonify({'status': 'ok', 'name': name, 'angle': angle})


@servo_bp.post('/dome/close')
def dome_close():
    safe, resp = _check_servo_safety('dome')
    if not safe: return resp
    body = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    name = body.get('name', '')
    if not name:
        return jsonify({'error': 'Field "name" required'}), 400
    if not _valid_servo_name(name, 'dome'):
        return jsonify({'error': f'unknown dome servo: {name}'}), 404
    if not reg.dome_servo:
        return jsonify({'error': 'dome_servo driver not ready — check master logs'}), 503
    cfg   = _read_panels_cfg()
    angle = _panel_angle(name, 'close', cfg)
    speed = _panel_speed(name, cfg)
    reg.dome_servo.close(name, angle, speed)
    return jsonify({'status': 'ok', 'name': name, 'angle': angle})


@servo_bp.post('/dome/open_all')
def dome_open_all():
    safe, resp = _check_servo_safety('dome')
    if not safe: return resp
    if not reg.dome_servo:
        return jsonify({'status': 'ok'})
    cfg = _read_panels_cfg()
    for name in DOME_SERVOS:
        reg.dome_servo.open(name, _panel_angle(name, 'open', cfg), _panel_speed(name, cfg))
    return jsonify({'status': 'ok'})


@servo_bp.post('/dome/close_all')
def dome_close_all():
    safe, resp = _check_servo_safety('dome')
    if not safe: return resp
    if not reg.dome_servo:
        return jsonify({'status': 'ok'})
    cfg = _read_panels_cfg()
    for name in DOME_SERVOS:
        reg.dome_servo.close(name, _panel_angle(name, 'close', cfg), _panel_speed(name, cfg))
    return jsonify({'status': 'ok'})


# ================================================================
# ARMS CONFIG — which body servos are the arm servos
# ================================================================

_ARM_COUNT_MAX = 6


_ARM_DEFAULT_DELAY = 0.5  # seconds between panel open and arm extension

def _read_arms_cfg() -> dict:
    """Returns {count, servos[4], panels[4], delays[4]} from local.cfg [arms].
    Always returns exactly 4 slots (empty string = not assigned).
    Values are servo IDs (e.g. 'Servo_S12'), never labels.
    delays are floats in seconds (default 0.5).
    """
    cfg = configparser.ConfigParser()
    cfg.read(_LOCAL_CFG)
    count  = max(0, min(_ARM_COUNT_MAX, cfg.getint('arms', 'count', fallback=0)))
    servos = [cfg.get('arms', f'arm_{i}',   fallback='').strip() for i in range(1, _ARM_COUNT_MAX + 1)]
    panels = [cfg.get('arms', f'panel_{i}', fallback='').strip() for i in range(1, _ARM_COUNT_MAX + 1)]
    delays = [round(max(0.1, min(5.0, cfg.getfloat('arms', f'delay_{i}', fallback=_ARM_DEFAULT_DELAY))), 2)
              for i in range(1, _ARM_COUNT_MAX + 1)]
    return {'count': count, 'servos': servos, 'panels': panels, 'delays': delays}


@servo_bp.get('/arms')
def arms_config_get():
    return jsonify(_read_arms_cfg())


@servo_bp.post('/arms')
@require_admin
def arms_config_save():
    import logging
    log = logging.getLogger(__name__)
    data   = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    # Audit finding L-2 2026-05-15: int() on a non-numeric body
    # value used to raise ValueError → 500 with stack trace to the
    # client. Other servo endpoints return 400 with a clear message.
    try:
        count = max(0, min(_ARM_COUNT_MAX, int(data.get('count', 0))))
    except (TypeError, ValueError):
        return jsonify({'error': 'count must be an integer'}), 400
    # B1 fix 2026-05-16: validate list shape + per-delay float-ability
    # BEFORE entering the cfg write loop. Previously, sending
    # `{"delays":["bad"]}` or `{"servos":"oops"}` reached float()/[i-1]
    # unguarded → 500 with stack trace to the client.
    servos = data.get('servos', [])
    panels = data.get('panels', [])
    delays = data.get('delays', [])
    if not isinstance(servos, list):
        return jsonify({'error': 'servos must be a list'}), 400
    if not isinstance(panels, list):
        return jsonify({'error': 'panels must be a list'}), 400
    if not isinstance(delays, list):
        return jsonify({'error': 'delays must be a list'}), 400
    # Pre-validate every delay coercion so we fail fast before holding
    # the cfg_write_lock (better UX: error returns immediately).
    for i, raw_delay in enumerate(delays):
        if isinstance(raw_delay, bool):   # True/False would silently coerce to 1.0/0.0
            return jsonify({'error': f'delay #{i+1} must be a number, got bool'}), 400
        try:
            float(raw_delay)
        except (TypeError, ValueError):
            return jsonify({'error': f'delay #{i+1} must be a number, got {raw_delay!r}'}), 400

    # Snapshot previous config so we can revert labels for removed arms
    prev = _read_arms_cfg()

    # B-49 (audit 2026-05-15): RMW under settings_bp._cfg_write_lock
    # so a concurrent /settings/config (different blueprint, same
    # local.cfg) can't load + mutate + write in between and lose one
    # side's keys.
    with _cfg_write_lock:
        cfg = configparser.ConfigParser()
        cfg.read(_LOCAL_CFG)
        if not cfg.has_section('arms'):
            cfg.add_section('arms')
        cfg.set('arms', 'count', str(count))
        new_servos, new_panels = [], []
        for i in range(1, _ARM_COUNT_MAX + 1):
            raw_servo = servos[i - 1] if i - 1 < len(servos) else ''
            raw_panel = panels[i - 1] if i - 1 < len(panels) else ''
            raw_delay = delays[i - 1] if i - 1 < len(delays) else _ARM_DEFAULT_DELAY
            sv = raw_servo if raw_servo in BODY_SERVOS else ''
            pn = raw_panel if raw_panel in BODY_SERVOS else ''
            dl = round(max(0.1, min(5.0, float(raw_delay))), 2)
            cfg.set('arms', f'arm_{i}',   sv)
            cfg.set('arms', f'panel_{i}', pn)
            cfg.set('arms', f'delay_{i}', str(dl))
            new_servos.append(sv)
            new_panels.append(pn)
        os.makedirs(os.path.dirname(_LOCAL_CFG), exist_ok=True)
        write_cfg_atomic(cfg, _LOCAL_CFG)

    # Auto-label servos in servo_angles.json to match their arm role.
    # Only overwrites if the current label doesn't already start with the expected prefix —
    # so custom suffixes like "Arm1_Pince" or "Arm1_panel_Pince" are preserved.
    panels_cfg    = _read_panels_cfg()['panels']
    label_updates = {}
    still_assigned = set()  # all servos that remain assigned in the NEW config
    for i in range(_ARM_COUNT_MAX):
        sv   = new_servos[i]
        pn   = new_panels[i]
        slot = i + 1
        arm_prefix   = f'Arm{slot}'
        panel_prefix = f'Arm{slot}_panel'
        if sv:
            still_assigned.add(sv)
            current = panels_cfg.get(sv, {}).get('label', sv)
            if not current.startswith(arm_prefix):
                label_updates[sv] = arm_prefix
        if pn:
            still_assigned.add(pn)
            current = panels_cfg.get(pn, {}).get('label', pn)
            if not current.startswith(panel_prefix):
                label_updates[pn] = panel_prefix

    # Revert labels ONLY for servos that were arms/panels before but are no longer assigned
    for i in range(_ARM_COUNT_MAX):
        prev_sv = prev['servos'][i]
        prev_pn = prev['panels'][i]
        if prev_sv and prev_sv not in still_assigned:
            label_updates[prev_sv] = prev_sv  # revert to servo ID
        if prev_pn and prev_pn not in still_assigned:
            label_updates[prev_pn] = prev_pn  # revert to servo ID

    if label_updates:
        patch = {sid: {**panels_cfg.get(sid, {}), 'label': lbl} for sid, lbl in label_updates.items()}
        _sync_angles_json({**panels_cfg, **patch})
        log.info("Arms auto-label: %s", label_updates)

    log.info("Arms config saved: count=%d servos=%s panels=%s", count, new_servos, new_panels)
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
    cfg     = _read_panels_cfg()
    arm_set = _arm_servo_set()
    for name in BODY_SERVOS:
        if name in arm_set:
            continue
        _servo_open(name, cfg)
    _launch_arm_sequences(_read_arms_cfg(), cfg, 'open')
    if reg.dome_servo:
        for name in DOME_SERVOS:
            reg.dome_servo.open(name, _panel_angle(name, 'open', cfg), _panel_speed(name, cfg))
    return jsonify({'status': 'ok'})


@servo_bp.post('/close_all')
def servo_close_all():
    cfg     = _read_panels_cfg()
    arm_set = _arm_servo_set()
    for name in BODY_SERVOS:
        if name in arm_set:
            continue
        _servo_close(name, cfg)
    _launch_arm_sequences(_read_arms_cfg(), cfg, 'close')
    if reg.dome_servo:
        for name in DOME_SERVOS:
            reg.dome_servo.close(name, _panel_angle(name, 'close', cfg), _panel_speed(name, cfg))
    return jsonify({'status': 'ok'})


# ================================================================
# Calibration per-panel
# ================================================================

def _servo_settings_version() -> str:
    """E1 fix 2026-05-16: max mtime across the two angles files = the
    'version' a client compares to via If-Match on save. Mirrors the
    X-Categories-Version pattern (project_optimistic_concurrency_token
    memory). Returns '0' if neither file exists yet."""
    mts = []
    for fp in (_DOME_ANGLES_FILE, _SLAVE_ANGLES_FILE):
        try:
            mts.append(os.path.getmtime(fp))
        except OSError:
            pass
    return str(max(mts) if mts else 0.0)


@servo_bp.get('/settings')
def servo_settings_get():
    data = _read_panels_cfg()
    data['dome_hats'] = [
        {'hat': i + 1, 'addr': hex(_master_hat_addrs[i]),
         'servos': [f'Servo_M{i * 16 + j}' for j in range(16)]}
        for i in range(len(_master_hat_addrs))
    ]
    data['body_hats'] = [
        {'hat': i + 1, 'addr': hex(_slave_hat_addrs[i]),
         'servos': [f'Servo_S{i * 16 + j}' for j in range(16)]}
        for i in range(len(_slave_hat_addrs))
    ]
    resp = jsonify(data)
    resp.headers['X-Servo-Version'] = _servo_settings_version()
    return resp


_LABEL_ALLOWED_CHARS = set(
    'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 _-.()'
)


def _sanitize_label(raw: str, fallback: str) -> str:
    """B-68 (audit 2026-05-15): the panel label feeds into HTML
    contexts (arms <option> via app.js:6307, Choreo block labels).
    Even with escapeHtml now applied (B-41 frontend fix), restricting
    the character set at the source keeps the data clean and prevents
    accidental control-char injection into local.cfg too. 40-char
    cap retained; any disallowed char is dropped."""
    s = ''.join(c for c in str(raw)[:40] if c in _LABEL_ALLOWED_CHARS)
    return s.strip() or fallback


@servo_bp.post('/settings')
@require_admin
def servo_settings_save():
    # E1 fix 2026-05-16: optimistic concurrency token. Client sends
    # If-Match: <version> (from prior GET's X-Servo-Version header). If
    # the file mtime has advanced since (another admin saved), return
    # 409 instead of silently overwriting their changes. Optional —
    # legacy clients without the header continue to work.
    if_match = request.headers.get('If-Match')
    if if_match:
        try:
            client_v = float(if_match)
            server_v = float(_servo_settings_version())
            if abs(client_v - server_v) > 0.001:   # FS precision tolerance
                return jsonify({
                    'error': 'version conflict',
                    'message': 'Another admin changed servo settings — refresh and retry',
                    'current_version': server_v,
                }), 409
        except (TypeError, ValueError):
            pass   # malformed If-Match treated as absent (lenient)
    data   = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    panels = {}
    for name, vals in (data.get('panels') or {}).items():
        if name in _ALL_PANELS and isinstance(vals, dict):
            panels[name] = {
                'label': _sanitize_label(vals.get('label', name), name),
                'open':  _clamp(_safe_int(vals.get('open',  _DEFAULT_OPEN),  _DEFAULT_OPEN)),
                'close': _clamp(_safe_int(vals.get('close', _DEFAULT_CLOSE), _DEFAULT_CLOSE)),
                'speed': _clamp_speed(_safe_int(vals.get('speed', _DEFAULT_SPEED), _DEFAULT_SPEED)),
            }
    try:
        _write_panels_cfg(panels)
    except AnglesCorruptedError as e:
        # E12: file was quarantined, refuse the save instead of writing
        # a fresh dict that would have wiped non-edited servos.
        return jsonify({'error': str(e), 'recoverable': False}), 503
    # E10 fix 2026-05-16: response itself can't include SCP result because
    # SCP runs async in a thread that's still in-flight when this returns.
    # Frontend polls /servo/sync_status ~1.5s after save to verify Slave
    # got the file. See _last_slave_sync_status + GET /servo/sync_status.
    resp = jsonify(_read_panels_cfg())
    resp.headers['X-Servo-Version'] = _servo_settings_version()
    return resp


@servo_bp.get('/sync_status')
def servo_sync_status():
    """E10 fix 2026-05-16: report the result of the most recent Slave
    SFTP push from a /servo/settings save. Frontend polls this ~1.5s
    after save → if `attempted && !ok`, toast a warning so the operator
    knows their body servo angles didn't reach the Slave.
    Returns: {attempted, ok, error, age_s}."""
    import time as _t
    sync = dict(_last_slave_sync_status)
    sync['age_s'] = round(_t.time() - sync.get('ts', 0), 2) if sync.get('ts') else None
    return jsonify(sync)
