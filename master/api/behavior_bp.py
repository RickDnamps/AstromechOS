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
#  useful, but WITHOUT ANY WARRANTY; without even the
#  implied warranty of MERCHANTABILITY or FITNESS FOR A
#  PARTICULAR PURPOSE. See the GNU General Public License
#  for more details.
# ============================================================
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
        'alive_enabled':       cfg.getboolean('behavior', 'alive_enabled',       fallback=False),
        'startup_enabled':     cfg.getboolean('behavior', 'startup_enabled',     fallback=False),
        'startup_delay':       cfg.getfloat  ('behavior', 'startup_delay',       fallback=5.0),
        'startup_choreo':      cfg.get       ('behavior', 'startup_choreo',      fallback='startup.chor'),
        'idle_mode':           cfg.get       ('behavior', 'idle_mode',           fallback='choreo'),
        'idle_timeout_min':    cfg.getfloat  ('behavior', 'idle_timeout_min',    fallback=10.0),
        'idle_audio_category': cfg.get       ('behavior', 'idle_audio_category', fallback='happy'),
        'idle_choreo_list':    [c.strip() for c in cfg.get('behavior', 'idle_choreo_list', fallback='').split(',') if c.strip()],
        'dome_auto_on_alive':  cfg.getboolean('behavior', 'dome_auto_on_alive',  fallback=True),
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
        with open(cfg_path, 'w', encoding='utf-8') as f:
            parser.write(f)
        # Update in-memory config on the engine if available
        be = reg.behavior_engine
        if be:
            be._cfg.read(os.path.normpath(_CFG_PATH))
        log.info("Behavior config saved")
        return jsonify({'ok': True})
    except Exception as e:
        log.exception("Failed to save behavior config")
        return jsonify({'ok': False, 'error': str(e)}), 500
