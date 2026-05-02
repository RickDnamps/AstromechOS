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

CONFIG_DIR   = os.path.dirname(__file__)
MAIN_CFG     = os.path.join(CONFIG_DIR, 'main.cfg')
LOCAL_CFG    = os.path.join(CONFIG_DIR, 'local.cfg')
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
        print("  repo_url = https://github.com/TON_USER/r2d2.git")
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


def write_cfg_atomic(cfg: configparser.ConfigParser, path: str) -> None:
    """Writes cfg to path atomically using a .tmp file + os.replace().
    If the process crashes between write and replace, the original file
    is untouched. os.replace() is atomic on POSIX (rename syscall).
    """
    tmp = path + '.tmp'
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(tmp, 'w', encoding='utf-8') as f:
        cfg.write(f)
    os.replace(tmp, path)
