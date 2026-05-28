"""master/api/hats_bp.py — zero-config HAT health surface.

Aggregates Master + Slave hardware layout (hw_layout.json on both sides)
into a single payload for the Settings -> HATs panel and the Cockpit
"Hardware Health" widget. Exposes a manual rescan that re-runs
scripts/detect_hats.py on both Pis.

Strict observation/decision split (chantier 2026-05-28):
  - shared/hw_layout.py is the single source of truth for state.
    hats_bp NEVER re-implements the READY/DEGRADED/CRITICAL ranking
    (it calls hw_layout.worst_status and hat_status).
  - hats_bp NEVER mutates an existing hw_layout.json — only the
    detection script writes that file. Rescan delegates to
    scripts/detect_hats.py via subprocess locally + SSH on the slave.
  - The slave's hw_layout.json is available on the Master via the
    existing rsync sync (master->slave deploys also pull the slave's
    config files back via the standard project mechanism); a fresh
    rescan additionally SCPs the file back immediately.

Routes
======
GET  /hats/layout    Aggregated payload. LAN-open (same policy as the
                     status endpoint — read-only summary).
POST /hats/rescan    Re-run detect_hats.py on both Pis. @require_admin.
"""
from __future__ import annotations

import configparser
import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

from flask import Blueprint, jsonify

from master.api._admin_auth import require_admin
from shared import hw_layout as _hwl
from shared.paths import LOCAL_CFG, MAIN_CFG

log = logging.getLogger('hats_bp')

hats_bp = Blueprint('hats', __name__, url_prefix='/hats')

# Repository root — used to locate scripts/detect_hats.py and the
# master/slave config dirs without hardcoding /home/<user>/astromechos.
_REPO     = Path(__file__).resolve().parent.parent.parent
_DETECT   = _REPO / 'scripts' / 'detect_hats.py'
_MASTER_OUT = _REPO / 'master' / 'config' / 'hw_layout.json'
_SLAVE_OUT  = _REPO / 'slave'  / 'config' / 'hw_layout.json'


def _layout_summary(role: str) -> dict:
    """Load the hw_layout.json for <role> and shape it for the front-end.

    Returns:
      { host, present, bus, scanned_at, status, hats: [...], errors: [...] }

    - present=False indicates the file is missing or unreadable (the
      front-end shows DEGRADED with a hint to run rescan).
    - status is hw_layout.worst_status(layout) — the single 'health'
      indicator the cockpit widget colours green/yellow/red.
    """
    layout = _hwl.load_for(role)
    if layout is None:
        return {
            'host':       role,
            'present':    False,
            'status':     _hwl.STATUS_DEGRADED,
            'hats':       [],
            'errors':     [],
            'scanned_at': None,
            'bus':        None,
        }
    return {
        'host':       layout.get('host', role),
        'present':    True,
        'status':     _hwl.worst_status(layout),
        'hats':       layout.get('hats', []),
        'errors':     layout.get('errors', []),
        'scanned_at': layout.get('scanned_at'),
        'bus':        layout.get('bus'),
    }


def _combined_status(master: dict, slave: dict) -> str:
    """Worst-of-both status used as the top-level health badge.

    Both layouts can have their own worst_status; we just take the
    higher-priority of the two. Mirrors the priority cascade so the
    cockpit widget colours red iff EITHER side has a collision.
    """
    priority = {
        _hwl.STATUS_CRITICAL: 3,
        _hwl.STATUS_DEGRADED: 2,
        _hwl.STATUS_READY:    1,
    }
    cands = [master.get('status'), slave.get('status')]
    cands = [c for c in cands if c in priority]
    if not cands:
        return _hwl.STATUS_DEGRADED
    return max(cands, key=lambda s: priority.get(s, 0))


def hats_payload() -> dict:
    """Reusable payload builder — imported by /status enrichment in
    Phase B so the cockpit poller gets HAT health on every tick without
    a second HTTP round-trip."""
    master = _layout_summary('master')
    slave  = _layout_summary('slave')
    return {
        'master':           master,
        'slave':            slave,
        'aggregate_status': _combined_status(master, slave),
    }


@hats_bp.get('/layout')
def hats_layout():
    """Aggregated master + slave HAT layout.

    Response shape (consumed by Settings HATs panel + Cockpit widget):
        {
          "master": {host, present, status, bus, scanned_at,
                     hats: [...], errors: [...]},
          "slave":  {same shape},
          "aggregate_status": "ready" | "degraded" | "critical"
        }

    LAN-open (no admin required) — matches the /status read-only policy.
    Cockpit polls this every few seconds; admin gating would force a
    password prompt for the read-only health widget.
    """
    return jsonify(hats_payload())


def _resolve_slave_host() -> Optional[str]:
    """Read [slave] host from master cfg — same pattern as the rest of
    the codebase (no hardcoded IPs)."""
    try:
        c = configparser.ConfigParser()
        c.read([MAIN_CFG, LOCAL_CFG])
        v = c.get('slave', 'host', fallback='').strip()
        return v or None
    except Exception:
        return None


def _run_master_detect(timeout: float = 15.0) -> tuple[int, str]:
    """Run scripts/detect_hats.py locally for the master."""
    if not _DETECT.is_file():
        return -1, f'detect_hats.py not found at {_DETECT}'
    try:
        env = dict(os.environ)
        r = subprocess.run(
            ['python3', str(_DETECT), '--role', 'master',
             '--output', str(_MASTER_OUT), '--no-lock'],
            capture_output=True, text=True, timeout=timeout, env=env,
        )
        return r.returncode, ((r.stdout or '') + (r.stderr or ''))[:2000]
    except subprocess.TimeoutExpired:
        return -1, 'master detect_hats timeout'
    except Exception as e:
        return -1, f'master detect_hats error: {e}'


def _run_slave_detect(timeout: float = 25.0) -> tuple[int, str]:
    """SSH to slave + run detect_hats; SCP the result back so
    /hats/layout sees the new state immediately."""
    host = _resolve_slave_host()
    if not host:
        return -1, '[slave] host not configured in local.cfg'
    # The repo path on the slave is the standard /home/<user>/astromechos.
    # We resolve it from the master's identity helper rather than hardcoding
    # — same portability rule as the rest of the deploy stack.
    try:
        from shared.identity import slave_repo_path
        repo_remote = slave_repo_path()
    except Exception:
        repo_remote = '/home/artoo/astromechos'  # legacy fallback
    ssh_cmd = [
        'ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8',
        f'artoo@{host}',
        f'cd {repo_remote} && python3 scripts/detect_hats.py '
        f'--role slave --output slave/config/hw_layout.json --no-lock',
    ]
    try:
        r = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=timeout)
        scp_cmd = [
            'scp', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8',
            f'artoo@{host}:{repo_remote}/slave/config/hw_layout.json',
            str(_SLAVE_OUT),
        ]
        scp = subprocess.run(scp_cmd, capture_output=True, text=True, timeout=10)
        out = ((r.stdout or '') + (r.stderr or '') +
               (scp.stdout or '') + (scp.stderr or ''))[:2000]
        # Surface SCP failure as a non-zero rc even if SSH succeeded —
        # otherwise the front-end shows stale data and the operator
        # thinks the rescan worked.
        rc = r.returncode if r.returncode != 0 else scp.returncode
        return rc, out
    except subprocess.TimeoutExpired:
        return -1, 'slave detect_hats timeout'
    except FileNotFoundError as e:
        return -1, f'ssh/scp not available: {e}'
    except Exception as e:
        return -1, f'slave detect_hats error: {e}'


@hats_bp.post('/rescan')
@require_admin
def hats_rescan():
    """Manual rescan trigger — re-runs detect_hats.py on both Pis +
    returns the freshly-updated layout for an immediate UI refresh.

    Body: none. Response:
        {
          'master': {'rc': 0, 'output': '...'},
          'slave':  {'rc': 0, 'output': '...'},
          'layout': { ...same shape as GET /hats/layout... }
        }

    Best-effort across both sides: if the slave is unreachable, the
    master scan still runs and the response carries the slave error
    detail so the operator can read it without ssh'ing into anything.
    """
    rc_m, out_m = _run_master_detect()
    rc_s, out_s = _run_slave_detect()
    return jsonify({
        'master':  {'rc': rc_m, 'output': out_m},
        'slave':   {'rc': rc_s, 'output': out_s},
        'layout':  hats_payload(),
    })
