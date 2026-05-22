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
# ============================================================
"""Server-side admin authentication for mutation endpoints.

Threat model: AstromechOS lives on a private LAN (R2D2_Control hotspot
or home WiFi). Anyone on that LAN — invited or uninvited — can reach
the dashboard. Until 2026-05-15, EVERY mutation endpoint trusted the
JS-only `adminGuard.unlocked` flag, which meant a guest device could
delete every choreography by hitting POST /choreo/categories directly
with any HTTP client. The /settings/admin/verify password check existed
but only gated the JS UI, not the actual API.

This module adds a `require_admin` decorator that validates an
`X-Admin-Pw` header against the `[admin] password` key in local.cfg
(default 'deetoo'). The frontend remembers the password in-memory
after a successful /settings/admin/verify, then attaches the header to
every admin POST/DELETE. On `adminGuard.lock()` the in-memory copy is
cleared.

Comparison uses `hmac.compare_digest` to avoid timing attacks even
though the threat is mostly LAN guests rather than serious adversaries
— it's one line and costs nothing.
"""
from __future__ import annotations

import hmac
import logging
from functools import wraps

from flask import request, jsonify

log = logging.getLogger(__name__)

_ADMIN_HEADER = 'X-Admin-Pw'


def _get_admin_password() -> str:
    """Read the current admin password from local.cfg.

    Lazy import of settings_bp to avoid a circular import at module
    load time (settings_bp also imports the registry which imports the
    blueprints during app factory wiring)."""
    from master.api.settings_bp import _get_admin_password as _src
    return _src()


def get_json_object():
    """Return the parsed JSON object body, or None if the body is
    missing/malformed/not an object.

    Audit finding 2026-05-15: 9+ endpoints did
    `body = (lambda _b: _b if isinstance(_b, dict) else {})(request.get_json(silent=True))` then `body.get(...)`.
    A top-level JSON array body (e.g. `curl -d '[1,2,3]'`) survived
    the `or` chain because non-empty lists are truthy → AttributeError
    on `.get` → unhandled 500 with stack trace leak. This helper
    consolidates the safe shape: blueprint code does

        body = get_json_object()
        if body is None:
            return jsonify({'error': 'expected JSON object'}), 400

    or accepts None and treats it as empty for endpoints where every
    field is optional.
    """
    body = request.get_json(silent=True)
    return body if isinstance(body, dict) else None


def _check_admin(req) -> bool:
    """Non-decorator admin auth check — for endpoints where some payload
    paths require admin but others don't (e.g. /lock/set: keyless mode
    change, admin-only kids_speed_limit change).

    Returns True if the request carries a valid X-Admin-Pw header.
    Does NOT log on failure (caller decides whether to log/reject)."""
    provided = req.headers.get(_ADMIN_HEADER, '')
    if not provided:
        return False
    try:
        expected = _get_admin_password()
        return bool(hmac.compare_digest(provided.encode(), expected.encode()))
    except Exception:
        return False


def require_admin(view):
    """Decorator: 401 unless `X-Admin-Pw` matches local.cfg [admin] password.

    Place AFTER the route decorator so Flask's URL routing happens first:

        @bp.post('/admin/thing')
        @require_admin
        def admin_thing(): ...
    """
    @wraps(view)
    def wrapper(*args, **kwargs):
        provided = request.headers.get(_ADMIN_HEADER, '')
        expected = _get_admin_password()
        # hmac.compare_digest needs equal-length operands of bytes.
        # Empty `provided` is fine — comparison returns False quickly.
        if not provided or not hmac.compare_digest(provided.encode(),
                                                   expected.encode()):
            log.warning(
                "admin endpoint refused: %s %s from %s (header %s)",
                request.method, request.path,
                request.remote_addr or 'unknown',
                'missing' if not provided else 'wrong',
            )
            return jsonify({'ok': False, 'error': 'admin authentication required'}), 401
        return view(*args, **kwargs)
    return wrapper
