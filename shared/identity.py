"""
shared/identity.py — single source of truth for runtime IDENTITY.

Replaces the 4 duplicate `_slave_host()` helpers and the hardcoded
`'artoo@'` literals scattered across master/api/*. Designed to make
AstromechOS portable across any Raspberry Pi OS username (pi /
astromech / artoo / ...).

──────────────────────────────────────────────────────────────────────
Resolution priority (every getter follows the same waterfall):

   1. Future /boot/astromech_init.cfg overrides (AstromechOS Imager hook).
      The Imager writes the operator's choices (user, admin pw, Wi-Fi,
      hotspot SSID, …) to /boot/astromech_init.cfg on the SD card.
      At first boot, setup_master.sh / setup_slave.sh MERGE that file
      into local.cfg and delete it from /boot. Runtime code therefore
      reads local.cfg only — but the boot-init path is reserved here
      so the contract is documented and discoverable.

   2. The robot's local.cfg ([system] / [deploy] / [slave] sections).

   3. main.cfg defaults (in-repo, in git).

   4. Runtime auto-detection (pwd.getpwuid(os.getuid()) for user, etc.).

   5. Legacy fallback 'artoo' / 'astromech-slave.local' — kept ONLY so
      existing R2-D2 deployments (where local.cfg may pre-date the
      [system] section) keep booting unchanged. A fresh install via
      the Imager / setup_*.sh writes [system] + [deploy] so the legacy
      fallback is never reached at runtime.

──────────────────────────────────────────────────────────────────────
Cross-platform note: this module is imported on the Master Pi (Linux)
at runtime but ALSO loaded by unit tests on Windows dev machines.
`pwd` and `os.getuid()` are POSIX-only — both are guarded so the
module imports cleanly on Windows and falls back to env vars there.
"""
from __future__ import annotations

import configparser
import os
from typing import Optional

# POSIX-only stdlib modules — guarded so the module imports on Windows dev.
try:
    import pwd as _pwd
except ImportError:                       # Windows: pwd does not exist
    _pwd = None                           # type: ignore[assignment]


# ─── Future AstromechOS Imager hook ──────────────────────────────────
# The Imager (separate flashing app, planned) will write a one-time
# bootstrap config to /boot/astromech_init.cfg on the freshly-imaged
# SD card. Two candidate locations because Raspberry Pi OS Bookworm
# moved /boot → /boot/firmware. The install script (setup_master.sh)
# is responsible for merging it into local.cfg and unlinking it.
_BOOT_INIT_CANDIDATES = (
    '/boot/astromech_init.cfg',
    '/boot/firmware/astromech_init.cfg',
)


def boot_init_path() -> Optional[str]:
    """Return the /boot Imager bootstrap path if it exists, else None.

    Reserved for the install scripts (setup_master.sh consumes + removes
    it on first boot). Runtime code reads local.cfg — which the install
    has already populated from this file."""
    for p in _BOOT_INIT_CANDIDATES:
        try:
            if os.path.isfile(p):
                return p
        except OSError:
            continue
    return None


# ─── Config loader ───────────────────────────────────────────────────
def _cfg_paths() -> tuple[str, str]:
    """Indirection so unit tests can monkey-patch the cfg locations."""
    # Lazy import to keep this module side-effect free if shared.paths
    # itself has a setup issue.
    from shared.paths import MAIN_CFG, LOCAL_CFG
    return MAIN_CFG, LOCAL_CFG


def _cfg() -> configparser.ConfigParser:
    """Read main.cfg + local.cfg (the latter overrides). Fresh each call
    so a /settings save in another blueprint is picked up immediately —
    matches the pattern used by the existing _read_cfg() helpers."""
    c = configparser.ConfigParser()
    try:
        main_cfg, local_cfg = _cfg_paths()
        c.read([main_cfg, local_cfg])
    except Exception:
        pass
    return c


# ─── Current process identity ────────────────────────────────────────
def current_user() -> str:
    """OS username this Python process runs as.

    On a freshly-imaged Pi the user is whatever the Imager configured
    (pi / astromech / …). systemd launches the service as User=<that
    user> via the templated unit file (see scripts/setup_master.sh).
    Dev / Windows fallback: $USER / $USERNAME env var."""
    if _pwd is not None:
        try:
            return _pwd.getpwuid(os.getuid()).pw_name
        except Exception:
            pass
    # Windows + POSIX-without-passwd fallback
    return os.environ.get('USER') or os.environ.get('USERNAME') or 'astromech'


def current_uid() -> int:
    """numeric UID of this process — used for XDG_RUNTIME_DIR.
    Returns -1 on Windows (no UID concept)."""
    try:
        return os.getuid()                # type: ignore[attr-defined]
    except AttributeError:                # Windows
        return -1


def current_home() -> str:
    """Home directory of the process owner (e.g. /home/pi)."""
    if _pwd is not None:
        try:
            return _pwd.getpwuid(os.getuid()).pw_dir
        except Exception:
            pass
    return os.path.expanduser('~')


# ─── Slave SSH target ────────────────────────────────────────────────
# Replaces:  master/api/settings_bp.py::_resolve_slave_ssh_target  (hardcoded 'artoo@')
#            master/api/servo_bp.py::_slave_host                    (hardcoded 'artoo@')
#            master/api/audio_bp.py::_slave_host  +  _slave_sftp_creds
#            master/api/diagnostics_bp.py::_slave_host
#            master/api/status_bp.py::_slave_host
#            master/deploy_controller.py::reload_cfg  (slave_user/slave_host)
# ────────────────────────────────────────────────────────────────────
def slave_user() -> str:
    """SSH user on the Slave.

    AstromechOS architecture rule (2026-05-28): the Master and the Slave
    always run as the SAME Linux user (and the same password). This is
    a hard design invariant — the Imager + setup scripts create
    identical accounts on both Pis, which lets ssh-copy-id target the
    same username, lets the same password unlock both at first contact,
    and removes a whole class of "which-user-is-which" bugs.

    Therefore the slave SSH user is just current_user() — no separate
    cfg key, no waterfall, no per-host divergence.

    (The previously-supported `[deploy] slave_user` cfg key is now
    intentionally ignored. Legacy R2-D2 installs are unaffected because
    their current_user() == 'artoo' anyway.)"""
    return current_user()


def slave_host() -> str:
    """Slave hostname or IP.

    Order: [slave] host (the canonical key, written by setup_slave_network.sh)
    → [deploy] slave_host (legacy duplicate) → mDNS default."""
    c = _cfg()
    return (
        c.get('slave', 'host', fallback=None)
        or c.get('deploy', 'slave_host', fallback=None)
        or 'astromech-slave.local'
    )


def slave_ssh_target() -> str:
    """Composite 'user@host' for SSH/SCP/rsync calls to the Slave."""
    return f'{slave_user()}@{slave_host()}'


def slave_password() -> Optional[str]:
    """Optional plaintext SSH password for the Slave user.

    Returns None when key-based auth is configured (the post-install
    norm — setup_ssh_keys.sh pushes the Master's pubkey to the Slave).
    The Imager may inject this at first boot for first-contact SSH;
    runtime code that fails over to key-based auth should accept None
    and rely on the SSH agent."""
    c = _cfg()
    p = c.get('deploy', 'slave_password', fallback=None)
    return p if p else None


def slave_repo_path() -> str:
    """Path of the AstromechOS install on the Slave (rsync destination).

    Both Pis are normally imaged with the same layout, so this defaults
    to the Master's own home/astromechos."""
    c = _cfg()
    return (
        c.get('deploy', 'slave_path', fallback=None)
        or c.get('system', 'repo_path', fallback=None)
        or f'{current_home()}/astromechos'
    )


# ─── Convenience for systemd / install scripts ───────────────────────
def system_repo_path() -> str:
    """Path of the AstromechOS install on THIS machine (the Master).

    Derived from $HOME of the process owner — matches what setup_master.sh
    writes to [system] repo_path at install time."""
    c = _cfg()
    return (
        c.get('system', 'repo_path', fallback=None)
        or c.get('master', 'repo_path', fallback=None)
        or f'{current_home()}/astromechos'
    )
