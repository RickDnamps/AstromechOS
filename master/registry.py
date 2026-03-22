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
#  useful, but WITHOUT ANY WARRANTY; without even the implied
#  warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
#  PURPOSE. See the GNU General Public License for details.
#
#  You should have received a copy of the GNU GPL along with
#  R2D2_Control. If not, see <https://www.gnu.org/licenses/>.
# ============================================================
"""
Registre des contrôleurs actifs — injection de dépendances pour Flask.
Les blueprints accèdent aux drivers via ce module.
Initialisé dans master/main.py avant le démarrage de Flask.
"""

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from master.uart_controller      import UARTController
    from master.teeces_controller    import TeecesController
    from master.deploy_controller    import DeployController
    from master.script_engine        import ScriptEngine
    from master.drivers.vesc_driver  import VescDriver
    from master.drivers.dome_motor_driver  import DomeMotorDriver
    from master.drivers.body_servo_driver  import BodyServoDriver
    from master.drivers.dome_servo_driver  import DomeServoDriver

# Ces variables sont assignées dans main.py avant app.run()
uart:        'UARTController | None'    = None
teeces:      'TeecesController | None'  = None
deploy:      'DeployController | None'  = None
engine:      'ScriptEngine | None'      = None
vesc:        'VescDriver | None'        = None
dome:        'DomeMotorDriver | None'   = None
servo:       'BodyServoDriver | None'   = None
dome_servo:  'DomeServoDriver | None'   = None

# Télémétrie VESC — mise à jour par les callbacks TL/TR du Master
# Format: {'v_in': 23.5, 'temp': 35.2, 'current': 8.5, 'rpm': 1200, 'duty': 0.45, 'fault': 0, 'ts': 1234567890.0}
vesc_telem: dict = {'L': None, 'R': None}
vesc_power_scale: float = 1.0

# Résultat du scan CAN bus — mis à jour par callback CANFOUND dans main.py
# None = pas encore de résultat, [] = aucun VESC trouvé, [...] = IDs trouvés
vesc_can_scan_result: list | None = None
vesc_can_scan_event: threading.Event = threading.Event()

# Santé UART Slave — mis à jour par le thread slave-health-poll dans main.py
# None = Slave injoignable ou pas encore pollé
# dict: {'total': N, 'errors': E, 'health_pct': 98.1, 'window_s': 60}
slave_uart_health: dict | None = None

# État audio — mis à jour par audio_bp à chaque play/stop
audio_playing: bool = False
audio_current: str  = ''

# Lock mode — 0=Normal, 1=Kids, 2=ChildLock
lock_mode: int = 0

# Manette Bluetooth (evdev) — initialisé dans main.py
bt_ctrl: 'BTControllerDriver | None' = None

# E-Stop global — True quand E-Stop actif (servos coupés)
# Mis à True par /system/estop et bouton E-Stop manette
# Remis à False par /system/estop_reset et /bt/estop_reset
estop_active: bool = False

# Timestamp dernière commande drive/dome depuis web/Android (priorité > manette BT)
web_last_drive_t: float = 0.0
web_last_dome_t:  float = 0.0

# Limite de vitesse Kids Mode (0.0..1.0) — synchronisé depuis JS via /lock/set
kids_speed_limit: float = 0.5
