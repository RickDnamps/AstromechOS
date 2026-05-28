"""master/api/deploy_bp.py — clean /api/deploy/* alias surface for the
Settings → Deploy panel and the AstromechOS Imager.

The canonical handlers for git-pull / rollback / commit-info / repo-cfg
already live in status_bp + settings_bp (they cohabit there for
historical reasons + share the `_deploy_safety_check`). This blueprint
exposes the deploy-only surface under a stable, documented namespace
that's easy to audit, easy to lock down, and easy to consume from
external clients (Imager, mobile, CI). Each route is a THIN wrapper
that delegates to the canonical implementation — zero duplicated logic.

Routes
======
GET  /api/deploy/status        Returns the current local commit, the
                               remote tip on the configured branch, the
                               commit subject, and the behind_count.
                               Same payload shape as /system/deploy_status.

POST /api/deploy/save-config   Persist deploy-related cfg keys
                               (github.repo_url / github.branch /
                               github.auto_pull_on_boot / slave.host).
                               Runs the DNA paternity gate inherited
                               from /settings/config. Rejects any
                               unrelated key in the payload so a
                               client can't smuggle audio.channels or
                               other unrelated cfg through this URL.

POST /api/deploy/update        Trigger the full deploy pipeline:
                               git pull → rsync to Slave → reboot
                               Slave → restart Master service.
                               Gated by _deploy_safety_check (refuses
                               while E-STOP/stow/choreo/motion ramp
                               are active).

POST /api/deploy/rollback      Revert to HEAD^ + rsync + reboot Slave
                               + restart Master. Same safety gate.

All routes require admin (X-Admin-Pw header) — same as their
canonical /system/* + /settings/* counterparts.
"""
from flask import Blueprint, jsonify, request

from master.api._admin_auth import require_admin

deploy_bp = Blueprint('deploy', __name__, url_prefix='/api/deploy')


# Whitelist of cfg keys accepted by /api/deploy/save-config. The
# underlying /settings/config endpoint accepts a much wider set
# (audio, battery, choreo, …); we narrow it here so a misbehaving
# client can't reuse this endpoint to mutate unrelated cfg.
_DEPLOY_KEYS = frozenset({
    'github.repo_url',
    'github.branch',
    'github.auto_pull_on_boot',
    'slave.host',
})


@deploy_bp.get('/status')
@require_admin
def deploy_status():
    """Current local commit + remote tip + behind/ahead status.

    Thin wrapper around status_bp.system_deploy_status — same payload:
        { local_sha, remote_sha, remote_msg, behind_count }
    On error: { error: <message> }. Cached 60 s upstream."""
    from master.api.status_bp import system_deploy_status
    return system_deploy_status()


@deploy_bp.post('/save-config')
@require_admin
def deploy_save_config():
    """Save deploy-related cfg keys with the DNA paternity check.

    Body: {"github.repo_url": "...", "github.branch": "...", ...}
    Only the keys in `_DEPLOY_KEYS` are accepted; any extra key
    rejects the whole request with 400. The delegated /settings/config
    handler runs validate_paternity() on github.repo_url BEFORE writing
    anything, and on failure leaves both local.cfg and the `origin`
    remote untouched (atomic refusal).
    """
    raw = request.get_json(silent=True)
    if not isinstance(raw, dict):
        return jsonify({'error': 'JSON body must be an object'}), 400
    extras = sorted(set(raw.keys()) - _DEPLOY_KEYS)
    if extras:
        return jsonify({
            'error': 'unexpected keys for /api/deploy/save-config',
            'extra': extras,
            'allowed': sorted(_DEPLOY_KEYS),
        }), 400
    # Delegate to the canonical handler. set_config() reads the JSON
    # body again via request.get_json (Flask caches it on the request),
    # runs the per-key normalisers, runs the DNA paternity gate, writes
    # the cfg, and hot-reloads DeployController. We pass its return
    # straight through (jsonify or (jsonify, status_code)).
    from master.api.settings_bp import set_config
    return set_config()


@deploy_bp.post('/update')
@require_admin
def deploy_update():
    """Trigger git pull + rsync + Slave reboot + Master restart.

    Gated by _deploy_safety_check upstream (refuses with 503 if
    E-STOP / stow / choreo / motion ramp is active)."""
    from master.api.status_bp import system_update
    return system_update()


@deploy_bp.post('/rollback')
@require_admin
def deploy_rollback():
    """Revert to HEAD^ + rsync + Slave reboot + Master restart.

    Same safety gate as /update. Use sparingly — the rollback target
    is just the immediate prior commit; for older snapshots, restore
    from a backup .bck instead."""
    from master.api.status_bp import system_rollback
    return system_rollback()
