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
Config loader — Merges main.cfg (repo) and local.cfg (local, gitignored).
local.cfg takes priority over main.cfg for all keys it defines.
If local.cfg is missing, displays a warning and suggests creating it.
"""

import configparser
import logging
import os
import sys

log = logging.getLogger(__name__)

from shared.paths import MAIN_CFG, LOCAL_CFG  # noqa: E402

CONFIG_DIR    = os.path.dirname(__file__)
LOCAL_EXAMPLE = os.path.join(CONFIG_DIR, 'local.cfg.example')


def load() -> configparser.ConfigParser:
    """
    Loads main.cfg then overrides with local.cfg.
    Exits the program if local.cfg is missing (first run).
    """
    cfg = configparser.ConfigParser()

    # 1. Read main.cfg (default values, in the repo)
    if not os.path.exists(MAIN_CFG):
        log.error(f"main.cfg not found: {MAIN_CFG}")
        sys.exit(1)
    cfg.read(MAIN_CFG)

    # 2. Override with local.cfg (local settings, outside the repo)
    if not os.path.exists(LOCAL_CFG):
        print("\n" + "="*60)
        print("FIRST RUN — local.cfg missing")
        print("="*60)
        print(f"\nCopy the example file and configure it:")
        print(f"  cp {LOCAL_EXAMPLE} {LOCAL_CFG}")
        print(f"  nano {LOCAL_CFG}")
        print("\nMinimum required in local.cfg:")
        print("  [github]")
        print("  repo_url = https://github.com/TON_USER/AstromechOS.git")
        print("="*60 + "\n")
        sys.exit(1)

    cfg.read(LOCAL_CFG)
    log.debug(f"Config loaded: {MAIN_CFG} + {LOCAL_CFG}")
    return cfg


def get_github_url(cfg: configparser.ConfigParser) -> str:
    return cfg.get('github', 'repo_url', fallback='')


def get_github_branch(cfg: configparser.ConfigParser) -> str:
    return cfg.get('github', 'branch', fallback='main')


def is_auto_pull_enabled(cfg: configparser.ConfigParser) -> bool:
    return cfg.getboolean('github', 'auto_pull_on_boot', fallback=True)


def _chown_to_parent_owner(path: str) -> None:
    """Chown `path` to its parent directory's owner uid/gid.

    Rationale (bug fix 2026-06-03): firstboot_setup.sh runs as ROOT and calls
    write_cfg_atomic() / rotate_backup() — files end up owned root:root mode
    0600, which the astromech-uid systemd service can't read. configparser.read
    silently swallows EACCES, so cfg.get('master','repo_path') then raises
    NoOptionError and the service crash-loops (observed 325 restarts on a test
    Pi).

    Fix is username-agnostic (per CLAUDE.md HARD RULE): we read the parent
    directory's owner — which is the operator (UID 1000) regardless of how
    the Imager renamed them — rather than hardcoding 'astromech'.

    When the script already runs as the eventual owner (normal mutation path),
    chown(self -> self) is a harmless no-op. PermissionError is swallowed so
    non-root processes can't break here trying to chown to a different UID.
    """
    try:
        parent_stat = os.stat(os.path.dirname(os.path.abspath(path)))
        os.chown(path, parent_stat.st_uid, parent_stat.st_gid)
    except (OSError, AttributeError):
        # OSError: PermissionError when non-root chown'ing to another UID, or
        #          Windows / filesystems without POSIX ownership.
        # AttributeError: os.chown unavailable on Windows.
        pass


def rotate_backup(path: str, keep: int = 3) -> None:
    """User-reported 2026-05-16: 'ça fait plusieurs fois que tu efface
    mes configs j'en ai marre'.

    Before each write, rotate <path>.bak1 → <path>.bak2 → <path>.bak3
    so the operator has 3 generations of recovery on demand. The N-th
    most recent state lives at <path>.bakN. Caller invokes BEFORE
    write_cfg_atomic / atomic_json_write.

    If path doesn't exist (first write), no-op.
    .bak1 = most recent good state (last successful write)
    .bak2 = previous one
    .bak3 = oldest kept

    Recovery from SSH:
        cp local.cfg.bak1 local.cfg && systemctl restart astromechos

    Ownership (bug fix 2026-06-03): each new .bak* file is chowned to the
    parent directory's owner so a firstboot (root-run) rotate doesn't leave
    backups unreadable by the astromech-uid service that later tries to
    restore from them. See _chown_to_parent_owner() for details.
    """
    if not os.path.exists(path):
        return
    try:
        # Rotate oldest to newest: bak{N-1} -> bakN, ..., bak1 -> bak2
        # os.replace preserves the existing file's ownership/mode, so rotated
        # backups keep whatever owner they were created with. We re-chown after
        # in case an earlier rotation under root left the owner stuck.
        for i in range(keep - 1, 0, -1):
            src = f"{path}.bak{i}"
            dst = f"{path}.bak{i+1}"
            if os.path.exists(src):
                os.replace(src, dst)
                _chown_to_parent_owner(dst)
        # Copy current path to .bak1 (NOT rename — current file still needed
        # by readers until the new write lands; rename would create a gap)
        import shutil
        shutil.copy2(path, f"{path}.bak1")
        try:
            os.chmod(f"{path}.bak1", 0o600)
        except OSError:
            pass
        # shutil.copy2 creates the destination with the CURRENT process's
        # ownership — if firstboot runs as root, .bak1 becomes root:root and
        # the service can't read it. Force back to parent dir owner.
        _chown_to_parent_owner(f"{path}.bak1")
    except OSError as e:
        log.warning("rotate_backup failed for %s: %s — proceeding with write", path, e)


def write_cfg_atomic(cfg: configparser.ConfigParser, path: str) -> None:
    """Writes cfg to path atomically using a .tmp file + os.replace().
    If the process crashes between write and replace, the original file
    is untouched. os.replace() is atomic on POSIX (rename syscall).

    B-76 / B-77 (Settings audit 2026-05-15): local.cfg + slave.cfg hold
    plaintext WiFi / hotspot / admin passwords. Restrict file
    permissions to 0600 (owner read+write only) so non-astromech users on
    the Pi can't read the passwords via filesystem access alone.
    Anyone with SSH as astromech (default password 'astropass') still gets
    them — the real defense is changing the admin + SSH passwords,
    which is operator responsibility. fsync flushes the rename
    durability so a power loss right after replace doesn't lose it.

    User-reported 2026-05-16: rotate 3 .bak generations BEFORE writing
    so an unintended mutation (bad audit script, fat-finger in dashboard,
    cascade clear) can be reverted via SSH one-line.

    Ownership (bug fix 2026-06-03): the written file is chowned to the
    parent directory's owner so that when this runs as root (firstboot
    systemd unit), the resulting local.cfg isn't left root:root mode 0600
    — which would make it unreadable by the astromech-uid service that
    starts immediately after firstboot and crash-loop the master service
    with configparser.NoOptionError. We read the parent dir owner rather
    than hardcoding 'astromech' to stay username-agnostic per the CLAUDE.md
    HARD RULE (the C# Imager renames the operator account on every flash).
    """
    rotate_backup(path)
    tmp = path + '.tmp'
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(tmp, 'w', encoding='utf-8') as f:
        cfg.write(f)
        f.flush()
        try:
            os.fsync(f.fileno())
        except OSError:
            pass   # Some filesystems (tmpfs) don't support fsync — best-effort
    os.replace(tmp, path)
    try:
        # 0o600 = rw------- for owner. Idempotent — fine to re-chmod
        # an already-restricted file. Skip silently on Windows /
        # filesystems that don't honour POSIX mode (tests on Pi only).
        os.chmod(path, 0o600)
    except OSError:
        pass
    # Preserve parent dir ownership so the service user (astromech UID 1000)
    # can read this file even when firstboot wrote it as root. No-op when the
    # current process is already the parent owner. See _chown_to_parent_owner.
    _chown_to_parent_owner(path)
