"""
BehaviorEngine — makes R2-D2 feel alive without human interaction.

Two subsystems:
  1. Startup sequence: plays a choreo after boot delay.
  2. ALIVE mode: triggers idle reactions (audio/lights/choreo) after inactivity.

Config: local.cfg [behavior]
  startup_enabled     = true/false
  startup_delay       = 5              (seconds)
  startup_choreo      = startup.chor
  alive_enabled       = false
  idle_timeout_min    = 10             (minutes)
  idle_mode           = choreo         (sounds|sounds_lights|lights|choreo)
  idle_audio_category = happy
  idle_choreo_list    = patrol.chor,celebrate.chor
  dome_auto_on_alive  = true
"""

import configparser
import json
import logging
import os
import random
import threading
import time

import master.registry as _registry
from master.config.config_loader import write_cfg_atomic

log = logging.getLogger(__name__)

_MIN_IDLE_GAP_S = 30.0   # minimum seconds between idle triggers


class BehaviorEngine:
    """Background behavior engine — startup sequence + ALIVE mode idle reactions."""

    def __init__(self, cfg: configparser.ConfigParser, choreo_dir: str = None):
        self._cfg = cfg
        self._choreo_dir = choreo_dir or os.path.join(
            os.path.dirname(__file__), 'choreographies'
        )
        self._reg = _registry          # injectable for tests
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._last_idle_trigger: float = 0.0
        self._alive_was_on: bool = False  # track dome auto state

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background behavior thread."""
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, name='behavior-engine', daemon=True
        )
        self._thread.start()
        log.info("BehaviorEngine started")

    def stop(self) -> None:
        """Signal the background thread to stop."""
        self._stop_event.set()

    def set_alive(self, enabled: bool) -> None:
        """Toggle ALIVE mode. Persists to local.cfg and handles dome auto."""
        self._write_cfg('alive_enabled', 'true' if enabled else 'false')
        if enabled:
            # Reset activity timer so idle doesn't fire immediately
            self._reg.last_activity = time.monotonic()
            log.info("ALIVE mode ON")
        else:
            log.info("ALIVE mode OFF")
        self._sync_dome_auto(enabled)

    # ------------------------------------------------------------------
    # Background loop
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """Main background loop — startup then periodic idle check."""
        self._run_startup()

        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception:
                log.exception("BehaviorEngine tick error")
            self._stop_event.wait(timeout=5.0)

    def _run_startup(self) -> None:
        """Play startup choreo after boot delay (if enabled)."""
        try:
            enabled = self._cfg.getboolean('behavior', 'startup_enabled', fallback=False)
            if not enabled:
                return
            delay = self._cfg.getfloat('behavior', 'startup_delay', fallback=5.0)
            choreo_name = self._cfg.get('behavior', 'startup_choreo', fallback='startup')
            # Audit finding CR-6 2026-05-15: tolerate legacy '.chor'
            # suffix in the cfg value. behavior_bp's regex rejects it
            # at save time, so freshly-saved values won't have it, but
            # historical local.cfg ships with .chor — strip if present
            # so the file lookup still works.
            if choreo_name.endswith('.chor'):
                choreo_name = choreo_name[:-5]
            choreo_path = os.path.join(self._choreo_dir, choreo_name + '.chor')

            if not os.path.isfile(choreo_path):
                log.warning("Startup choreo not found: %s — skipping", choreo_path)
                return

            if delay > 0:
                if self._stop_event.wait(timeout=delay):
                    return   # stopped before startup could run

            choreo_data = self._load_choreo(choreo_path)
            if choreo_data:
                log.info("Playing startup choreo: %s", choreo_name)
                # B-8: route through choreo_bp.safe_play so concurrent
                # Sequences-tab clicks and behavior triggers contend on
                # the same _play_lock. Lazy import — choreo_bp imports
                # the registry which holds reg.behavior_engine, so a
                # top-level import would be circular.
                from master.api.choreo_bp import safe_play
                safe_play(choreo_data, log_label='behavior')
        except Exception:
            log.exception("Startup sequence error")

    def _tick(self) -> None:
        """Called every 5s — check if idle reaction should fire."""
        now = time.monotonic()
        if not self._should_trigger_idle(now):
            return

        self._last_idle_trigger = now
        mode = self._cfg.get('behavior', 'idle_mode', fallback='choreo')

        if mode == 'sounds':
            self._trigger_sounds()
        elif mode == 'sounds_lights':
            self._trigger_sounds()
            self._trigger_lights()
        elif mode == 'lights':
            self._trigger_lights()
        elif mode == 'choreo':
            self._trigger_choreo()
        else:
            log.warning("Unknown idle_mode: %s", mode)

    # ------------------------------------------------------------------
    # Guard
    # ------------------------------------------------------------------

    def _should_trigger_idle(self, now: float) -> bool:
        """Return True if all conditions for an idle trigger are met."""
        alive = self._cfg.getboolean('behavior', 'alive_enabled', fallback=False)
        if not alive:
            return False

        if self._reg.choreo.is_playing():
            return False

        idle_timeout_s = self._cfg.getfloat('behavior', 'idle_timeout_min', fallback=10.0) * 60.0
        since_activity = now - self._reg.last_activity
        if since_activity < idle_timeout_s:
            return False

        if now - self._last_idle_trigger < _MIN_IDLE_GAP_S:
            return False

        mode = self._cfg.get('behavior', 'idle_mode', fallback='choreo')
        if mode in ('sounds', 'sounds_lights') and self._reg.audio_playing:
            return False

        return True

    # ------------------------------------------------------------------
    # Reaction implementations
    # ------------------------------------------------------------------

    def _trigger_sounds(self) -> None:
        """Send UART random audio command for idle reaction.

        Schedules a delayed reset of reg.audio_playing so subsequent
        sounds/sounds_lights idle triggers are NOT permanently blocked by
        a flag that nothing ever clears. Mirrors the timer pattern used by
        api/audio_bp.play_random — same 60s ceiling for unknown-duration
        random sounds.
        """
        try:
            category = self._cfg.get('behavior', 'idle_audio_category', fallback='happy')
            if self._reg.uart:
                self._reg.uart.send('S', f'RANDOM:{category}')
                self._reg.audio_playing = True
                self._schedule_audio_reset()
                log.info("ALIVE sounds: category=%s", category)
            else:
                log.warning("ALIVE sounds: UART not available")
        except Exception:
            log.exception("ALIVE sounds trigger failed")

    def _schedule_audio_reset(self, seconds: float = 60.0) -> None:
        """Clear reg.audio_playing after the given delay so the idle gate
        can re-open. Cancels any prior pending reset."""
        prev = getattr(self, '_audio_reset_timer', None)
        if prev is not None and prev.is_alive():
            prev.cancel()
        def _reset():
            self._reg.audio_playing = False
        t = threading.Timer(seconds, _reset)
        t.daemon = True
        t.start()
        self._audio_reset_timer = t

    def _trigger_lights(self) -> None:
        """Trigger random lights animation via Teeces/AstroPixels controller."""
        try:
            if self._reg.teeces:
                self._reg.teeces.random_mode()
                log.info("ALIVE lights: random_mode triggered")
            else:
                log.warning("ALIVE lights: teeces not available")
        except Exception:
            log.exception("ALIVE lights trigger failed")

    def _trigger_choreo(self) -> None:
        """Pick a random choreo from idle_choreo_list and play it."""
        try:
            raw = self._cfg.get('behavior', 'idle_choreo_list', fallback='')
            # Audit finding CR-6: tolerate legacy '.chor' suffix per
            # entry. Strip on parse so the file lookup works regardless
            # of which historical format the cfg holds.
            choreo_list = []
            for c in raw.split(','):
                c = c.strip()
                if not c:
                    continue
                if c.endswith('.chor'):
                    c = c[:-5]
                choreo_list.append(c)
            if not choreo_list:
                log.warning("idle_choreo_list is empty — nothing to play")
                return

            choreo_name = random.choice(choreo_list)
            choreo_path = os.path.join(self._choreo_dir, choreo_name + '.chor')
            if not os.path.isfile(choreo_path):
                log.warning("ALIVE choreo not found: %s", choreo_path)
                return

            choreo_data = self._load_choreo(choreo_path)
            if choreo_data:
                log.info("ALIVE choreo: %s", choreo_name)
                # B-8: route through choreo_bp.safe_play so concurrent
                # Sequences-tab clicks and behavior triggers contend on
                # the same _play_lock. Lazy import — choreo_bp imports
                # the registry which holds reg.behavior_engine, so a
                # top-level import would be circular.
                from master.api.choreo_bp import safe_play
                safe_play(choreo_data, log_label='behavior')
        except Exception:
            log.exception("ALIVE choreo trigger failed")

    # ------------------------------------------------------------------
    # Dome auto sync
    # ------------------------------------------------------------------

    def _sync_dome_auto(self, alive_on: bool) -> None:
        """Enable/disable dome auto rotation when ALIVE is toggled."""
        try:
            dome_auto = self._cfg.getboolean('behavior', 'dome_auto_on_alive', fallback=True)
            if not dome_auto:
                return
            if self._reg.dome:
                self._reg.dome.set_random(alive_on)
                log.debug("Dome auto → %s (ALIVE=%s)", alive_on, alive_on)
        except Exception:
            log.exception("Dome auto sync failed")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load_choreo(self, path: str) -> dict | None:
        """Load and parse a .chor JSON file. Returns None on error."""
        try:
            with open(path, encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            log.exception("Failed to load choreo: %s", path)
            return None

    def _write_cfg(self, key: str, value: str) -> None:
        """Persist a [behavior] key to local.cfg.

        B-206 (remaining tabs audit 2026-05-15): holds settings_bp's
        `_cfg_write_lock` around the RMW. Before this, a concurrent
        /behavior/config or /settings/config save (both of which DO
        hold the lock) could interleave with this writer and lose
        keys. Lazy import to avoid circular at module load.
        """
        try:
            from master.api.settings_bp import _cfg_write_lock
            cfg_path = os.path.join(
                os.path.dirname(__file__), 'config', 'local.cfg'
            )
            with _cfg_write_lock:
                parser = configparser.ConfigParser()
                parser.read(cfg_path)
                if not parser.has_section('behavior'):
                    parser.add_section('behavior')
                parser.set('behavior', key, value)
                # Also update in-memory config
                if not self._cfg.has_section('behavior'):
                    self._cfg.add_section('behavior')
                self._cfg.set('behavior', key, value)
                write_cfg_atomic(parser, cfg_path)
        except Exception:
            log.exception("Failed to persist behavior config key=%s", key)
