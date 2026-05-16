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
Blueprint API Teeces — Phase 4.
Controls Teeces32 LEDs (PSI, logics, FLD) via local TeecesController.

Endpoints:
  POST /teeces/random           → random mode
  POST /teeces/leia             → Leia mode
  POST /teeces/off              → turn everything off
  POST /teeces/text             {"text": "HELLO"}
  POST /teeces/psi              {"mode": 1}
  GET  /teeces/animations       → list all known T-codes
  POST /teeces/animation        {"mode": 11}
  POST /teeces/raw              {"cmd": "0T5"}
  GET  /teeces/state
"""

import re
from flask import Blueprint, request, jsonify
import master.registry as reg
from master.api._admin_auth import require_admin
from master.lights.base_controller import sanitize_lights_text

teeces_bp = Blueprint('teeces', __name__, url_prefix='/teeces')

# B4/B5/E3 fix 2026-05-16: `_mode` is a canonical string the frontend
# StatusPoller reads via /status.teeces_mode to re-sync chip+button
# state. Was previously only updated by random/leia/off endpoints —
# animation/text/raw never touched it, so /teeces/state lied (and the
# UI lied too because it depends on this). Now ALL mutation endpoints
# update _mode with one of:
#   'random' | 'off' | 'leia' | 'text' | 'raw' | 'animation:<N>' | 'psi'
# `current_teeces_mode()` is the safe read for status_bp (returns
# 'random' default if module not yet imported).
_mode = 'random'


def current_teeces_mode() -> str:
    """Module-public accessor — used by status_bp to expose mode in /status."""
    return _mode


# E5 fix 2026-05-16: persist the operator's chosen default mode so a
# Master reboot restores RANDOM/OFF/LEIA instead of always defaulting
# to RANDOM. Animation:N/text/raw/psi are transient and NOT persisted
# (operator's intent there is "play this NOW", not "make this default").
_PERSISTABLE_MODES = ('random', 'off', 'leia')


def _persist_mode(mode: str) -> None:
    """Write the default mode to local.cfg if it's a stable choice.
    Uses the cross-blueprint cfg_write_lock so it doesn't race with
    other settings writers (CLAUDE.md mandate)."""
    if mode not in _PERSISTABLE_MODES:
        return
    try:
        from master.api.settings_bp import _cfg_write_lock
        from master.config.config_loader import write_cfg_atomic, MAIN_CFG, LOCAL_CFG
        import configparser
        with _cfg_write_lock:
            cfg = configparser.ConfigParser()
            cfg.read([MAIN_CFG, LOCAL_CFG])
            if not cfg.has_section('lights'):
                cfg.add_section('lights')
            cfg.set('lights', 'last_mode', mode)
            write_cfg_atomic(cfg, LOCAL_CFG)
    except Exception:
        # Best-effort — if persistence fails the in-RAM _mode is still
        # correct; only reboot recovery suffers.
        import logging
        logging.getLogger(__name__).exception("Lights mode persistence failed")


def restore_mode_from_cfg(cfg) -> str:
    """Called once from main.py after teeces.setup() succeeds. Reads
    [lights] last_mode (default 'random') and dispatches the matching
    driver call so hardware + UI agree on boot. Returns the restored
    mode string for log line."""
    global _mode
    last = (cfg.get('lights', 'last_mode', fallback='random') or 'random').strip().lower()
    if last not in _PERSISTABLE_MODES:
        last = 'random'
    _mode = last
    if reg.teeces:
        if   last == 'off':    reg.teeces.off()
        elif last == 'leia':   reg.teeces.leia()
        else:                  reg.teeces.random_mode()
    return last

# /teeces/raw command allowlist. Real JawaLite commands look like
# `<addr>T<mode>` or `<addr>M<text>` etc. The firmware Teeces also
# uses # for setup. Bound to the universe the lights/teeces module
# actually sends. (Audit finding H-2 2026-05-15.)
_TEECES_RAW_RE = re.compile(r'^[A-Za-z0-9 ,@#%&+*/.=:;_-]{1,32}$')

# Frontend display vocabulary (modern: 5 values) + legacy 3 for
# backwards-compat with old .chor files and bench scripts.
# B1 fix 2026-05-16: backend used to only accept the legacy 3 →
# every SEND from UI with FLD TOP/BOT/BOTH/ALL was silently 400.
_DISPLAY_TARGETS = (
    'fld_top', 'fld_bottom', 'fld_both', 'rld', 'all',   # modern (UI)
    'fld', 'both',                                       # legacy
)


def _sanitize_text(raw: str) -> str:
    """Strip control characters + cap length 20 (FLD line max).
    Kept as a thin wrapper for callers that import the symbol."""
    return sanitize_lights_text(raw, 20)


def _dispatch_text(text: str, display: str) -> None:
    """Forward a text+display tuple to the active driver.

    AstroPixels+ supports the full 5-value vocabulary natively
    (@1M=FLD top, @2M=FLD bot, @3M=RLD). Teeces32 only has fld/rld/both
    so we collapse:
      fld_top | fld_bottom | fld_both  -> 'fld'
      rld                              -> 'rld'
      all                              -> 'both'
    """
    if not reg.teeces:
        return
    # Driver class name disambiguates without an isinstance import
    # (avoids pulling AstroPixelsDriver at module load just for type check).
    backend = type(reg.teeces).__name__
    if 'AstroPixels' in backend:
        reg.teeces.text(text, display)
        return
    # Teeces32 path
    if display in ('fld_top', 'fld_bottom', 'fld_both'):
        target = 'fld'
    elif display == 'all':
        target = 'both'
    else:
        target = display   # fld | rld | both
    reg.teeces.text(text, target)


# 2026-05-16: User feedback — Lights operator-level actions (random/
# leia/off/text/psi/animation) demoted from @require_admin to LAN-open.
# Rationale: aligns with /motion/* and /audio/play|volume|stop which
# are already LAN-open. Lights are not safety-critical (flashing LEDs
# don't harm the robot, motion/audio CAN). Inconsistency was confusing
# operators ('why does SEND text need admin but drive doesn't?').
# /raw stays admin-only — it writes arbitrary serial bytes, real risk.


@teeces_bp.post('/random')
def teeces_random():
    """Activates Teeces random animation mode. LAN-open (operator-level)."""
    global _mode
    _mode = 'random'
    if reg.teeces:
        reg.teeces.random_mode()
    _persist_mode(_mode)   # E5: survives reboot
    return jsonify({'status': 'ok', 'mode': 'random'})


@teeces_bp.post('/leia')
def teeces_leia():
    """Activates Leia mode (holographic message). LAN-open."""
    global _mode
    _mode = 'leia'
    if reg.teeces:
        reg.teeces.leia()
    _persist_mode(_mode)   # E5: survives reboot
    return jsonify({'status': 'ok', 'mode': 'leia'})


@teeces_bp.post('/off')
def teeces_off():
    """Turns off all Teeces LEDs. LAN-open."""
    global _mode
    _mode = 'off'
    if reg.teeces:
        reg.teeces.off()
    _persist_mode(_mode)   # E5: survives reboot
    return jsonify({'status': 'ok', 'mode': 'off'})


@teeces_bp.post('/text')
def teeces_text():
    """Displays text on FLD, RLD, or both. Body: {"text": "HELLO", "display": "fld"}
    Control characters (\\r, \\n, \\x00) are stripped before the
    command is built — without this, an embedded \\r terminates the
    FLD frame early and the rest of the operator's string runs as a
    fresh JawaLite command (audit H-3 2026-05-15)."""
    global _mode
    body    = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    text    = _sanitize_text(body.get('text', ''))
    display = str(body.get('display', 'fld_top')).lower()
    if display not in _DISPLAY_TARGETS:
        return jsonify({
            'error': "display must be one of: fld_top, fld_bottom, fld_both, rld, all (or legacy fld/both)",
        }), 400
    _dispatch_text(text, display)
    _mode = 'text'   # B4/B5 fix: surface mode change to /status
    return jsonify({'status': 'ok', 'text': text, 'display': display})


@teeces_bp.post('/psi')
def teeces_psi():
    """Controls the PSIs. Body: {"mode": 1}"""
    body = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    try:
        mode = int(body.get('mode', 1))
    except (TypeError, ValueError):
        return jsonify({'error': 'mode must be an integer'}), 400
    if reg.teeces:
        reg.teeces.psi(mode)
    global _mode
    _mode = 'psi'   # B4/B5 fix: surface PSI activity to /status
    return jsonify({'status': 'ok', 'mode': mode})


@teeces_bp.post('/psi_seq')
def teeces_psi_seq():
    """PSI sequence control. Body: {"target": "both", "sequence": "normal"}
    target: both | fpsi | rpsi
    sequence: normal | flash | alarm | failure | redalert | leia | march
    """
    body     = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    target   = str(body.get('target',   'both')).lower()
    sequence = str(body.get('sequence', 'normal')).lower()
    if target not in ('both', 'fpsi', 'rpsi'):
        return jsonify({'error': "target must be 'both', 'fpsi', or 'rpsi'"}), 400
    if sequence not in ('normal', 'flash', 'alarm', 'failure', 'redalert', 'leia', 'march'):
        return jsonify({'error': 'unknown sequence'}), 400
    if reg.teeces:
        if hasattr(reg.teeces, 'psi_seq'):
            reg.teeces.psi_seq(target, sequence)
        else:
            _TEECES_MAP = {'normal':1,'flash':1,'alarm':3,'redalert':3,'leia':1,'failure':1,'march':1}
            reg.teeces.psi(_TEECES_MAP.get(sequence, 1))
    global _mode
    _mode = 'psi'   # B4/B5 fix: surface PSI activity to /status
    return jsonify({'status': 'ok', 'target': target, 'sequence': sequence})


@teeces_bp.get('/animations')
def teeces_animations():
    """List all known T-code animations. LAN-open: read-only metadata."""
    from master.lights.base_controller import BaseLightsController
    return jsonify({
        'animations': [
            {'mode': k, 'name': v}
            for k, v in BaseLightsController.ANIMATIONS.items()
        ]
    })


@teeces_bp.post('/animation')
def teeces_animation():
    """Trigger a T-code animation. Body: {"mode": 11}"""
    body = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    try:
        mode = int(body.get('mode', 1))
    except (TypeError, ValueError):
        return jsonify({'error': 'mode must be an integer'}), 400
    from master.lights.base_controller import BaseLightsController
    if mode not in BaseLightsController.ANIMATIONS:
        return jsonify({'error': f'unknown animation mode {mode}'}), 400
    if reg.teeces:
        reg.teeces.animation(mode)
    name = BaseLightsController.ANIMATIONS.get(mode, f'T{mode}')
    global _mode
    _mode = f'animation:{mode}'   # B4/B5 fix: chip re-sync via /status
    return jsonify({'status': 'ok', 'mode': mode, 'name': name})


@teeces_bp.post('/raw')
@require_admin
def teeces_raw():
    """Send raw JawaLite command. Body: {"cmd": "0T5"}
    Admin-only + strict allowlist regex + 32-char cap. Without these,
    a POST `{"cmd": "0T1\\r0T999\\r..."}` would inject an unbounded
    command stream into the serial bus (audit H-2 2026-05-15)."""
    body = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))
    cmd = str(body.get('cmd', '')).strip()
    if not cmd:
        return jsonify({'error': 'field "cmd" required'}), 400
    if not _TEECES_RAW_RE.match(cmd):
        return jsonify({'error': 'invalid cmd — alphanumeric + JawaLite operators only, ≤32 chars'}), 400
    if reg.teeces:
        reg.teeces.raw(cmd)
    global _mode
    _mode = 'raw'   # B4/B5 fix: surface raw send to /status
    return jsonify({'status': 'ok', 'cmd': cmd})


@teeces_bp.get('/state')
def teeces_state():
    """Current Teeces state."""
    backend = type(reg.teeces).__name__.replace('Driver', '').lower() if reg.teeces else 'none'
    return jsonify({
        'mode':    _mode,
        'ready':   bool(reg.teeces and reg.teeces.is_ready()),
        'backend': backend,
    })
