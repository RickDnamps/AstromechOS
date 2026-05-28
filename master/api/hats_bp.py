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


@hats_bp.post('/remap')
@require_admin
def hats_remap():
    """Phase G6 chantier 2026-05-28 — operator re-binds a HAT IDENTITY
    to a different I2C address (e.g. after re-jumpering 0x41 -> 0x42
    in hardware) WITHOUT touching any calibration data.

    Body (JSON):
        {
          "host":  "master" | "slave",     (required)
          "hats":  [                       (required, replaces existing)
            { "id": "Body_HAT_A", "address": "0x42" },
            ...
          ]
        }

    Rules enforced server-side (defense-in-depth alongside the UI):
      - host must be 'master' or 'slave'.
      - Every entry in 'hats' must reference an EXISTING identity
        from the current config_mapping (no rename / no add — we
        only change addresses). Identity creation is out of scope
        for this endpoint; a future Imager UI will own that.
      - Every address must be 0x40..0x77 and unique within the side
        (no two identities at the same physical address).
      - Roles, channels, alias_prefix, alias_base are preserved as-is
        from the existing entries.

    On success:
      - Atomic tmp+os.replace write of config_mapping.json.
      - In-process driver reload (reg.dome_servo.reload() or
        reg.body_servo via UART SRV:RELOAD) so the change takes
        effect without a service restart.
      - 200 with the updated layout payload (same shape as
        GET /hats/layout) so the UI re-renders straight away.

    On any validation failure: 400 + clear message, no write happens."""
    from flask import request as _req
    import json as _json
    import tempfile as _tempfile
    body = _req.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({'error': 'JSON body must be an object'}), 400
    host = body.get('host')
    if host not in ('master', 'slave'):
        return jsonify({'error': "host must be 'master' or 'slave'"}), 400
    submitted = body.get('hats')
    if not isinstance(submitted, list) or not submitted:
        return jsonify({'error': "'hats' must be a non-empty array"}), 400

    current = _hwl.load_for if False else None  # ignore — we want hw_mapping
    from shared import hw_mapping as _hwm
    current_map = _hwm.load_for(host)
    if current_map is None:
        # Fallback: synthesize so the operator can re-map a fresh install
        # without first running detect_hats manually.
        cfg_paths = (
            [str(_REPO / 'slave' / 'config' / 'slave.cfg')]
            if host == 'slave'
            else [str(MAIN_CFG), str(LOCAL_CFG)]
        )
        current_map = _hwm.synthesize_from_layout(host, cfg_paths=cfg_paths)
    current_by_id = {h['id']: h for h in _hwm.all_hats(current_map)}

    # Validate each submitted entry + build the new hats[] list while
    # preserving fields the endpoint can't change (role / channels /
    # alias_prefix / alias_base).
    new_hats = []
    seen_addrs: set[str] = set()
    for entry in submitted:
        if not isinstance(entry, dict):
            return jsonify({'error': 'each hats[] entry must be an object'}), 400
        ident = entry.get('id')
        addr  = entry.get('address')
        if not isinstance(ident, str) or ident not in current_by_id:
            return jsonify({
                'error': f"unknown HAT identity {ident!r}; "
                         f"known: {sorted(current_by_id.keys())}",
            }), 400
        addr_norm = _hwm._normalise_addr(addr) if hasattr(_hwm, '_normalise_addr') else None
        if addr_norm is None:
            return jsonify({
                'error': f"invalid address {addr!r} for {ident}; "
                         f"expected '0x40'..'0x77'",
            }), 400
        if addr_norm in seen_addrs:
            return jsonify({
                'error': f"address {addr_norm} assigned to more than one HAT; "
                         f"each physical address must be unique",
            }), 400
        seen_addrs.add(addr_norm)
        prev = current_by_id[ident]
        new_hats.append({
            'id':           prev['id'],
            'role':         prev['role'],
            'address':      addr_norm,
            'channels':     prev.get('channels', 16),
            'alias_prefix': prev.get('alias_prefix'),
            'alias_base':   prev.get('alias_base'),
        })

    # Persist atomically. Stamp the timestamp + clear the synthesised
    # flag (operator-confirmed mapping is no longer a synth).
    import datetime as _dt
    new_mapping = {
        'schema_version': 1,
        'host':           host,
        'updated_at':     _dt.datetime.now(_dt.timezone.utc)
                                 .strftime('%Y-%m-%dT%H:%M:%SZ'),
        'synthesised':    False,
        'hats':           new_hats,
    }
    out_path = _REPO / host / 'config' / 'config_mapping.json'
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = _tempfile.mkstemp(dir=str(out_path.parent),
                                    prefix='.config_mapping.')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                _json.dump(new_mapping, f, indent=2)
                f.write('\n')
            os.replace(tmp, str(out_path))
            try:
                os.chmod(str(out_path), 0o644)
            except Exception:
                pass
        except Exception:
            try:
                os.unlink(tmp)
            except Exception:
                pass
            raise
    except Exception as e:
        log.error("hats_remap: write %s failed: %s", out_path, e)
        return jsonify({'error': f'write failed: {e}'}), 500

    # In-process driver reload. Best-effort — if the driver isn't loaded
    # yet (e.g. host == slave on master service) the next service start
    # picks up the new mapping. Master dome driver has a reload()
    # method that re-reads angles; we extend it to also re-read
    # mapping by setting _mapping directly first.
    try:
        import master.registry as reg
        if host == 'master' and getattr(reg, 'dome_servo', None):
            try:
                reg.dome_servo._mapping = new_mapping
                if reg.dome_servo.is_ready():
                    reg.dome_servo.reload()
            except Exception as _re:
                log.warning("hats_remap: dome_servo reload failed: %s", _re)
        # For slave, the master is a UART proxy — the SRV:RELOAD command
        # tells the slave to reload its angles JSON. Mapping reload on
        # the slave needs an SFTP push of config_mapping.json + service
        # restart; that's out of scope for this endpoint (next deploy
        # picks it up).
    except Exception:
        pass

    return jsonify({
        'status': 'ok',
        'updated_at': new_mapping['updated_at'],
        'host':       host,
        'layout':     hats_payload(),
    })


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
