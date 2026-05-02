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
Active controller registry — dependency injection for Flask.
Blueprints access drivers through this module.
Initialized in master/main.py before Flask starts.
"""

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from master.uart_controller      import UARTController
    from master.lights.base_controller import BaseLightsController
    from master.deploy_controller    import DeployController
    from master.script_engine        import ScriptEngine
    from master.drivers.vesc_driver  import VescDriver
    from master.drivers.dome_motor_driver  import DomeMotorDriver
    from master.drivers.body_servo_driver  import BodyServoDriver
    from master.drivers.dome_servo_driver  import DomeServoDriver
    from master.behavior_engine      import BehaviorEngine

# These variables are assigned in main.py before app.run()
uart:        'UARTController | None'    = None
teeces:      'BaseLightsController | None' = None
deploy:      'DeployController | None'  = None
engine:      'ScriptEngine | None'      = None
choreo:      'ChoreoPlayer | None'      = None
vesc:        'VescDriver | None'        = None
dome:        'DomeMotorDriver | None'   = None
servo:       'BodyServoDriver | None'   = None
dome_servo:  'DomeServoDriver | None'   = None

# VESC telemetry — updated by TL/TR callbacks on the Master
# Format: {'v_in': 23.5, 'temp': 35.2, 'current': 8.5, 'rpm': 1200, 'duty': 0.45, 'fault': 0, 'ts': 1234567890.0}
vesc_telem: dict = {'L': None, 'R': None}
vesc_power_scale: float = 1.0
vesc_invert_L: bool = False
vesc_invert_R: bool = False
vesc_duty_mode: bool = False   # True = COMM_SET_DUTY (bench testing), False = COMM_SET_RPM (default)
vesc_bench_mode: bool = False  # True = bypass VESC safety lock (no telem required)

# CAN bus scan result — updated by CANFOUND callback in main.py
# None = no result yet, [] = no VESC found, [...] = found IDs
vesc_can_scan_result: list | None = None
vesc_can_scan_event: threading.Event = threading.Event()

# Slave UART health — updated by the slave-health-poll thread in main.py
# None = Slave unreachable or not yet polled
# dict: {'total': N, 'errors': E, 'health_pct': 98.1, 'window_s': 60}
slave_uart_health: dict | None = None

# Audio state — updated by audio_bp on each play/stop
audio_playing: bool = False
audio_current: str  = ''

# Lock mode — 0=Normal, 1=Kids, 2=Child Lock
lock_mode: int = 0

# Bluetooth gamepad (evdev) — initialized in main.py
bt_ctrl: 'BTControllerDriver | None' = None

# Global E-Stop — True when E-Stop is active (servos cut)
# Set to True by /system/estop and gamepad E-Stop button
# Reset to False by /system/estop_reset and /bt/estop_reset
estop_active: bool = False

# Timestamp of last drive/dome command from web/Android (priority over BT gamepad)
web_last_drive_t: float = 0.0
web_last_dome_t:  float = 0.0

# Kids Mode speed limit (0.0..1.0) — synchronized from JS via /lock/set
kids_speed_limit: float = 0.5

# Behavior engine — timestamp of last user interaction (monotonic)
last_activity: float = 0.0

# BehaviorEngine instance — initialized in main.py
behavior_engine: 'BehaviorEngine | None' = None
