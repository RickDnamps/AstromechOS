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
Slave audio driver.
Plays MP3 sounds via mpg123 (native 3.5mm jack Pi 4B).
UART commands:
  S:Happy001          → plays the specific file
  S:RANDOM:happy      → plays a random sound from the category
  S:STOP              → stops the current sound

Prerequisite: sudo apt install -y mpg123
"""

import json
import logging
import os
import random
import subprocess
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.base_driver import BaseDriver

log = logging.getLogger(__name__)

_SOUNDS_DIR  = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'sounds'))
_INDEX_FILE  = os.path.join(_SOUNDS_DIR, 'sounds_index.json')


class AudioDriver(BaseDriver):
    def __init__(self, sounds_dir: str = _SOUNDS_DIR):
        self._sounds_dir = os.path.abspath(sounds_dir)
        self._index: dict[str, list[str]] = {}
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._ready = False

    # ------------------------------------------------------------------
    # BaseDriver
    # ------------------------------------------------------------------

    def setup(self) -> bool:
        if not os.path.isfile(_INDEX_FILE):
            log.error(f"sounds_index.json not found: {_INDEX_FILE}")
            return False
        try:
            with open(_INDEX_FILE, encoding='utf-8') as f:
                data = json.load(f)
            self._index = data.get('categories', {})
            total = sum(len(v) for v in self._index.values())
            log.info(f"AudioDriver ready — {total} sounds in {len(self._index)} categories")
            self._ready = True
            return True
        except Exception as e:
            log.error(f"Error loading sounds_index.json: {e}")
            return False

    def shutdown(self) -> None:
        self.stop()
        self._ready = False

    def is_ready(self) -> bool:
        return self._ready

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def play(self, filename: str) -> bool:
        """Plays an MP3 file by name (without extension)."""
        if not filename or any(c in filename for c in ('/', '\\', '..')):
            log.warning(f"Audio filename rejected (path traversal): {filename!r}")
            return False
        path = os.path.join(self._sounds_dir, filename + '.mp3')
        if not os.path.isfile(path):
            log.warning(f"Sound not found: {path}")
            return False
        self._launch(path)
        return True

    def play_random(self, category: str) -> bool:
        """Plays a random sound from the given category."""
        sounds = self._index.get(category.lower())
        if not sounds:
            log.warning(f"Unknown audio category: {category!r}")
            return False
        filename = random.choice(sounds)
        return self.play(filename)

    def stop(self) -> None:
        """Stops the currently playing sound."""
        with self._lock:
            if self._proc and self._proc.poll() is None:
                self._proc.terminate()
                log.debug("Sound stopped")
            self._proc = None

    def set_volume(self, volume: int) -> None:
        """Sets ALSA volume (0-100) on the 3.5mm jack (card 0)."""
        vol = max(0, min(100, volume))
        try:
            subprocess.run(
                ['amixer', '-c', '0', 'cset', 'numid=1', f'{vol}%'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            log.info(f"Volume: {vol}%")
        except Exception as e:
            log.error(f"set_volume error: {e}")

    def handle_volume(self, value: str) -> None:
        """UART callback VOL:75 → sets the volume."""
        try:
            self.set_volume(int(value))
        except (ValueError, TypeError) as e:
            log.error(f"Invalid VOL message {value!r}: {e}")

    def handle_uart(self, value: str) -> None:
        """
        Callback for UART S: messages.
        Expected formats:
          - 'Happy001'          → play specific
          - 'RANDOM:happy'      → play random category
          - 'STOP'              → stop
        """
        if value == 'STOP':
            self.stop()
            return
        if value.startswith('RANDOM:'):
            category = value[7:]
            self.play_random(category)
        else:
            self.play(value)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _launch(self, path: str) -> None:
        """Launches mpg123 in the background, stopping the previous sound."""
        with self._lock:
            if self._proc and self._proc.poll() is None:
                self._proc.terminate()
            try:
                self._proc = subprocess.Popen(
                    ['mpg123', '-q', path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                log.info(f"Audio: {os.path.basename(path)}")
            except FileNotFoundError:
                log.error("mpg123 not found — sudo apt install -y mpg123")
            except Exception as e:
                log.error(f"Audio launch error: {e}")
