"""
Config loader — Fusionne main.cfg (repo) et local.cfg (local, gitignore).
local.cfg a priorité sur main.cfg pour toutes les clés qu'il définit.
Si local.cfg est absent, affiche un avertissement et propose de le créer.
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
    Charge main.cfg puis surcharge avec local.cfg.
    Arrête le programme si local.cfg est absent (premier lancement).
    """
    cfg = configparser.ConfigParser()

    # 1. Lire main.cfg (valeurs par défaut, dans le repo)
    if not os.path.exists(MAIN_CFG):
        log.error(f"main.cfg introuvable: {MAIN_CFG}")
        sys.exit(1)
    cfg.read(MAIN_CFG)

    # 2. Surcharger avec local.cfg (paramètres locaux, hors repo)
    if not os.path.exists(LOCAL_CFG):
        print("\n" + "="*60)
        print("PREMIER LANCEMENT — local.cfg manquant")
        print("="*60)
        print(f"\nCopie le fichier exemple et configure-le :")
        print(f"  cp {LOCAL_EXAMPLE} {LOCAL_CFG}")
        print(f"  nano {LOCAL_CFG}")
        print("\nMinimum requis dans local.cfg :")
        print("  [github]")
        print("  repo_url = https://github.com/TON_USER/r2d2.git")
        print("="*60 + "\n")
        sys.exit(1)

    cfg.read(LOCAL_CFG)
    log.debug(f"Config chargée: {MAIN_CFG} + {LOCAL_CFG}")
    return cfg


def get_github_url(cfg: configparser.ConfigParser) -> str:
    return cfg.get('github', 'repo_url', fallback='')


def get_github_branch(cfg: configparser.ConfigParser) -> str:
    return cfg.get('github', 'branch', fallback='main')


def is_auto_pull_enabled(cfg: configparser.ConfigParser) -> bool:
    return cfg.getboolean('github', 'auto_pull_on_boot', fallback=True)
