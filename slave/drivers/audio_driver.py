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
Slave audio driver — N-channel polyphony (configurable, default 6).
Plays MP3 sounds via mpg123 (native 3.5mm jack Pi 4B).
N independent channels run simultaneously.

UART commands (n = channel index, n=0 → 'S:', n=1 → 'S2:', n=2 → 'S3:', etc.):
  S:Happy001          → channel 0: play specific file
  S:RANDOM:happy      → channel 0: play random from category
  S:STOP              → channel 0: stop
  S2:Happy001         → channel 1 (and so on for S3:, S4: …)

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
    def __init__(self, sounds_dir: str = _SOUNDS_DIR, channels: int = 6):
        self._sounds_dir = os.path.abspath(sounds_dir)
        self._index: dict[str, list[str]] = {}
        self._channels = channels
        self._procs: list[subprocess.Popen | None] = [None] * channels
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
        self.stop()   # stops all channels
        self._ready = False

    def is_ready(self) -> bool:
        return self._ready

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def play(self, filename: str, channel: int = 0) -> bool:
        """Plays an MP3 file by name (without extension) on the given channel."""
        if not filename or any(c in filename for c in ('/', '\\', '..')):
            log.warning(f"Audio filename rejected (path traversal): {filename!r}")
            return False
        if not (0 <= channel < self._channels):
            log.warning(f"Audio channel {channel} out of range (0–{self._channels - 1})")
            return False
        path = os.path.join(self._sounds_dir, filename + '.mp3')
        if not os.path.isfile(path):
            log.warning(f"Sound not found: {path}")
            return False
        self._launch(path, channel)
        return True

    def play_random(self, category: str, channel: int = 0) -> bool:
        """Plays a random sound from the given category on the given channel."""
        sounds = self._index.get(category.lower())
        if not sounds:
            log.warning(f"Unknown audio category: {category!r}")
            return False
        filename = random.choice(sounds)
        return self.play(filename, channel)

    def stop(self, channel: int | None = None) -> None:
        """Stops channel N, or all channels (channel=None)."""
        channels = list(range(self._channels)) if channel is None else [channel]
        with self._lock:
            for ch in channels:
                if 0 <= ch < len(self._procs):
                    proc = self._procs[ch]
                    if proc and proc.poll() is None:
                        proc.terminate()
                        log.debug(f"Sound stopped (ch{ch})")
                    self._procs[ch] = None

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
        Callback for UART S: messages (channel 0).
          - 'Happy001'       → play specific on ch0
          - 'RANDOM:happy'   → play random on ch0
          - 'STOP'           → stop ch0
        """
        self._handle_channel(value, channel=0)

    def handle_uart2(self, value: str) -> None:
        """
        Callback for UART S2: messages (channel 1).
          - 'Happy001'       → play specific on ch1
          - 'RANDOM:happy'   → play random on ch1
          - 'STOP'           → stop ch1
        """
        self._handle_channel(value, channel=1)

    def make_channel_handler(self, ch: int):
        """Returns a UART callback closure routing to channel ch."""
        def handler(value: str):
            self._handle_channel(value, ch)
        return handler

    def _handle_channel(self, value: str, channel: int) -> None:
        if value == 'STOP':
            self.stop(channel)
            return
        if value.startswith('RANDOM:'):
            self.play_random(value[7:], channel)
        else:
            self.play(value, channel)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _launch(self, path: str, channel: int = 0) -> None:
        """Launches mpg123 on the given channel, stopping whatever was on that channel."""
        with self._lock:
            proc = self._procs[channel] if 0 <= channel < len(self._procs) else None
            if proc and proc.poll() is None:
                proc.terminate()
            try:
                new_proc = subprocess.Popen(
                    ['mpg123', '-q', path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self._procs[channel] = new_proc
                log.info(f"Audio ch{channel}: {os.path.basename(path)}")
            except FileNotFoundError:
                log.error("mpg123 not found — sudo apt install -y mpg123")
            except Exception as e:
                log.error(f"Audio launch error (ch{channel}): {e}")
