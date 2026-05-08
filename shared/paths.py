"""
Centralised path constants — derived from this file's location so the
system works regardless of install directory or username.

  shared/paths.py  →  parent  =  shared/
                    →  parent.parent  =  repo root (BASE_DIR)
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Master
MAIN_CFG     = str(BASE_DIR / 'master' / 'config' / 'main.cfg')
LOCAL_CFG    = str(BASE_DIR / 'master' / 'config' / 'local.cfg')
DOME_ANGLES  = str(BASE_DIR / 'master' / 'config' / 'dome_angles.json')
VERSION_FILE = str(BASE_DIR / 'VERSION')
DEBUG_DIR    = str(BASE_DIR / 'debug')

# Slave
SLAVE_CFG    = str(BASE_DIR / 'slave' / 'config' / 'slave.cfg')
SLAVE_ANGLES = str(BASE_DIR / 'slave' / 'config' / 'servo_angles.json')
SLAVE_SOUNDS = str(BASE_DIR / 'slave' / 'sounds')

# Scripts
SCRIPTS_DIR  = str(BASE_DIR / 'scripts')
