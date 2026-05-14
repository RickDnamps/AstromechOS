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
Slave audio driver — N-channel polyphony (configurable, default 6).
Plays MP3 sounds via mpg123 (native 3.5mm jack Pi 4B).
N independent channels run simultaneously with independent per-channel volume.

UART commands (n = channel index, n=0 → 'S:', n=1 → 'S2:', n=2 → 'S3:', etc.):
  S:Happy001          → channel 0: play at 100%
  S:Happy001:75       → channel 0: play at 75%
  S:RANDOM:happy      → channel 0: play random from category at 100%
  S:RANDOM:happy:30   → channel 0: play random at 30%
  S:STOP              → channel 0: stop
  S2:Happy001:50      → channel 1 at 50% (and so on for S3:, S4: …)

Volume is per-channel via mpg123 -f flag (0–32768). No global ALSA change.

Prerequisite: sudo apt install -y mpg123
"""

import json
import logging
import os
import queue
import random
import subprocess
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.base_driver import BaseDriver

log = logging.getLogger(__name__)

_SOUNDS_DIR  = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'sounds'))
_INDEX_FILE  = os.path.join(_SOUNDS_DIR, 'sounds_index.json')


def _reap(proc, label: str = '') -> None:
    """Terminate + wait an mpg123 subprocess to avoid zombie processes.

    B-5: proc.terminate() only sends SIGTERM; the OS keeps the
    <defunct> entry in the process table until the parent calls wait().
    Without this reaper a long-running slave accumulates zombies on
    every preemption / stop(). 0.5s SIGTERM grace then SIGKILL — mpg123
    normally exits in <50ms when interrupted, so the timeout almost
    never fires."""
    try:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                log.warning("mpg123 %s did not exit on SIGTERM — killing", label)
                proc.kill()
                try:
                    proc.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    log.error("mpg123 %s did not respond to SIGKILL", label)
        else:
            # Already exited but the parent never wait()'d — drain the
            # zombie now. wait() on a finished process returns immediately.
            proc.wait(timeout=0.1)
    except (OSError, subprocess.SubprocessError) as e:
        log.warning("Audio reap %s: %s", label, e)


class AudioDriver(BaseDriver):
    def __init__(self, sounds_dir: str = _SOUNDS_DIR, channels: int = 6):
        self._sounds_dir = os.path.abspath(sounds_dir)
        self._index: dict[str, list[str]] = {}
        self._channels = channels
        self._procs: list[subprocess.Popen | None] = [None] * channels
        self._lock = threading.Lock()
        # B-11: bound the launch queue. A stuck worker (mpg123 hang on a
        # broken audio device) combined with a tight UART loop (e.g. choreo
        # player firing audio events at 50ms tick) could otherwise grow the
        # queue without limit and exhaust RAM. With maxsize=64, a put on a
        # full queue drops the OLDEST request (FIFO) — appropriate for
        # audio: stale queued sounds aren't worth playing minutes late.
        self._launch_q: queue.Queue = queue.Queue(maxsize=64)
        self._ready = False
        # B-15: last-played-per-category for the no-repeat rule in
        # play_random(). {category: last_filename}.
        self._last_random: dict[str, str] = {}
        # B-17: amixer availability probe. Set in setup() — None until
        # probed. Used by set_volume() to skip the subprocess call when
        # ALSA isn't usable, avoiding silent failures.
        self._amixer_ok: bool | None = None

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
            # B-17: probe amixer availability ONCE at setup so set_volume()
            # can fail fast instead of paying the subprocess overhead on
            # every call when ALSA is unusable (no audio HAT, jack via BT
            # speaker, etc.).
            try:
                r = subprocess.run(
                    ['amixer', '-c', '0', 'cget', 'numid=1'],
                    capture_output=True, timeout=2,
                )
                self._amixer_ok = (r.returncode == 0)
                if self._amixer_ok:
                    log.info("AudioDriver: amixer card 0 numid=1 OK")
                else:
                    log.warning("AudioDriver: amixer probe failed — volume control disabled")
            except (FileNotFoundError, subprocess.TimeoutExpired) as e:
                self._amixer_ok = False
                log.warning("AudioDriver: amixer unavailable (%s) — volume control disabled", e)
            threading.Thread(target=self._launch_worker, name="audio-launch", daemon=True).start()
            return True
        except (OSError, json.JSONDecodeError) as e:
            log.error(f"Error loading sounds_index.json: {e}")
            return False

    def shutdown(self) -> None:
        self._ready = False
        # Drain queue so the worker exits on its next timeout
        while not self._launch_q.empty():
            try:
                self._launch_q.get_nowait()
            except queue.Empty:
                break
        self.stop()

    def is_ready(self) -> bool:
        return self._ready

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def play(self, filename: str, channel: int = 0, volume: int = 100) -> bool:
        """Plays an MP3 file by name (without extension) on the given channel at given volume (0-100)."""
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
        self._launch(path, channel, volume)
        return True

    def play_random(self, category: str, channel: int = 0, volume: int = 100) -> bool:
        """Plays a random sound from the given category on the given channel at given volume (0-100).

        B-15: avoid playing the same file twice in a row. The previous
        random.choice() implementation had a 1/N chance of repeating
        which felt jarring in idle/ALIVE mode. We now track the last
        sound per category and re-roll once if the choice matches.
        """
        cat = category.lower()
        sounds = self._index.get(cat)
        if not sounds:
            log.warning(f"Unknown audio category: {category!r}")
            return False
        last = self._last_random.get(cat)
        filename = random.choice(sounds)
        # One re-roll if we landed on the same sound. With N>1 sounds the
        # second roll has (N-1)/N chance of being different — good enough,
        # avoids an infinite loop on a single-sound category.
        if filename == last and len(sounds) > 1:
            filename = random.choice(sounds)
        self._last_random[cat] = filename
        return self.play(filename, channel, volume)

    def stop(self, channel: int | None = None) -> None:
        """Stops channel N, or all channels (channel=None).
        Also drains any pending launches for the stopped channels from the queue.
        """
        channels = set(range(self._channels)) if channel is None else {channel}
        # Drain queued-but-unstarted launches for these channels
        kept = []
        while True:
            try:
                kept.append(self._launch_q.get_nowait())
            except queue.Empty:
                break
        for item in kept:
            if item[0] not in channels:
                self._launch_q.put(item)
        # Terminate running processes
        with self._lock:
            for ch in channels:
                if 0 <= ch < len(self._procs):
                    proc = self._procs[ch]
                    if proc:
                        # B-5: reap (terminate + wait) instead of fire-and-forget
                        # terminate. Same zombie risk applies here as in the
                        # launch path on preemption.
                        _reap(proc, label=f'stop-ch{ch}')
                        log.debug("Sound stopped (ch%d)", ch)
                    self._procs[ch] = None

    def set_volume(self, volume: int) -> None:
        """Sets ALSA volume (0-100) on the 3.5mm jack (card 0). B-17: skip
        the subprocess call entirely when the amixer probe at setup
        determined the card is unusable — avoids per-call subprocess.run
        cost and the silent failure that previously masked the issue."""
        if self._amixer_ok is False:
            log.debug("set_volume skipped — amixer not available")
            return
        vol = max(0, min(100, volume))
        try:
            subprocess.run(
                ['amixer', '-c', '0', 'cset', 'numid=1', f'{vol}%'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=2,
            )
            log.info(f"Volume: {vol}%")
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            log.error(f"set_volume error: {e}")
            # Update the cached probe so we stop retrying.
            self._amixer_ok = False

    def handle_volume(self, value: str) -> None:
        """UART callback VOL:75 → sets the volume."""
        try:
            self.set_volume(int(value))
        except (ValueError, TypeError) as e:
            log.error(f"Invalid VOL message {value!r}: {e}")

    # B-18: handle_uart / handle_uart2 removed — they were one-shot
    # wrappers over _handle_channel(value, channel=0/1) but the actual
    # UART wiring in slave/main.py uses make_channel_handler(_i) for every
    # channel (line 190). Dead code that confused future readers about
    # whether the channel dispatch was via closure or direct method.
    # Keep make_channel_handler as the sole entry point.

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
            # RANDOM:category  or  RANDOM:category:volume
            rest = value[7:]
            parts = rest.rsplit(':', 1)
            if len(parts) == 2 and parts[1].isdigit():
                self.play_random(parts[0], channel, int(parts[1]))
            else:
                self.play_random(rest, channel)
        else:
            # filename  or  filename:volume
            parts = value.rsplit(':', 1)
            if len(parts) == 2 and parts[1].isdigit():
                self.play(parts[0], channel, int(parts[1]))
            else:
                self.play(value, channel)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _launch(self, path: str, channel: int = 0, volume: int = 100) -> None:
        """Enqueues a play request. Returns immediately — Popen happens in worker thread.

        B-11: queue is bounded (maxsize=64). When full, drop the OLDEST
        pending request so a fresh sound can still be queued — stale audio
        requests aren't worth playing seconds-to-minutes late. Logs a
        warning so the operator notices accumulating backpressure (worker
        hang on a broken audio device, etc.)."""
        scale = int(max(0, min(100, volume)) / 100 * 32768)
        try:
            self._launch_q.put_nowait((channel, path, scale))
        except queue.Full:
            try:
                dropped = self._launch_q.get_nowait()
                log.warning(
                    "Audio queue full — dropped oldest: ch%d %s",
                    dropped[0], os.path.basename(dropped[1]),
                )
            except queue.Empty:
                pass
            # Try once more — should succeed now.
            try:
                self._launch_q.put_nowait((channel, path, scale))
            except queue.Full:
                log.error("Audio queue still full after drop — request lost")
                return
        log.info("Audio ch%d vol%d%% queued: %s", channel, volume, os.path.basename(path))

    def _launch_worker(self) -> None:
        """Worker thread: consumes the launch queue and calls subprocess.Popen.
        Runs as a daemon thread — never blocks the UART reader thread.
        """
        while self._ready or not self._launch_q.empty():
            try:
                channel, path, scale = self._launch_q.get(timeout=0.5)
            except queue.Empty:
                continue
            with self._lock:
                proc = self._procs[channel] if 0 <= channel < len(self._procs) else None
                if proc and proc.poll() is None:
                    # B-5: reap the previous process — terminate() only sends
                    # SIGTERM and does NOT wait for the child to exit. Without
                    # the wait the OS keeps the process table entry as a
                    # <defunct> zombie until astromech-slave exits. Over a
                    # long choreo (or just repeated UI triggers) zombies
                    # accumulate. wait(timeout=0.5) gives mpg123 a chance to
                    # exit gracefully; kill() + wait() forces it if needed.
                    _reap(proc, label=f'ch{channel}')
                try:
                    new_proc = subprocess.Popen(
                        ['mpg123', '-q', '-f', str(scale), path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    self._procs[channel] = new_proc
                    log.info("Audio ch%d: %s", channel, os.path.basename(path))
                except FileNotFoundError:
                    log.error("mpg123 not found — sudo apt install -y mpg123")
                except Exception as e:
                    log.error("Audio launch error (ch%d): %s", channel, e)
