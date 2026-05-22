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
        self._last_choreo_name: str = ''  # W7: surfaced in /behavior/status
        self._last_choreo_ts:   float = 0.0

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
        """Signal the background thread to stop.

        B10/E17 fix 2026-05-16: also cancel the pending audio reset
        Timer thread + the dome auto rotation thread. Previously these
        kept running after shutdown, causing NoneType errors when they
        fired after reg.uart was already torn down."""
        self._stop_event.set()
        prev = getattr(self, '_audio_reset_timer', None)
        if prev is not None and prev.is_alive():
            try: prev.cancel()
            except Exception: pass
        # Release dome ownership if we had it
        try:
            if self._reg.dome:
                self._reg.dome.set_random(False)
        except Exception:
            pass

    def set_alive(self, enabled: bool) -> None:
        """Toggle ALIVE mode. Persists to local.cfg and handles dome auto."""
        self._write_cfg('alive_enabled', 'true' if enabled else 'false')
        if enabled:
            # Reset activity timer so idle doesn't fire immediately
            self._reg.last_activity = time.monotonic()
            # E11 fix 2026-05-16: also reset _last_idle_trigger so the
            # 30s gap is honored from THIS enable (was stale from hours-old
            # previous activation, could allow immediate fire if combined
            # with E2 negative idle_timeout exploit).
            self._last_idle_trigger = time.monotonic()
            log.info("ALIVE mode ON")
        else:
            log.info("ALIVE mode OFF")
        # B2 fix 2026-05-16: refuse to start dome auto rotation while
        # safety chain is engaged. Stop path runs unconditionally
        # (release ownership) so toggling OFF always stops the dome.
        if enabled and self._is_safety_locked():
            log.warning("set_alive(True): safety chain engaged — dome auto NOT started")
            return
        self._sync_dome_auto(enabled)

    def _is_safety_locked(self) -> bool:
        """B1/B2 fix 2026-05-16: centralized safety gate. ALIVE motion
        side effects (dome rotation, choreo, sounds, lights) must respect
        E-STOP, stow, and Child Lock — same invariant as motion_bp /
        servo_bp. CLAUDE.md 'Safety chain invariant'."""
        if getattr(self._reg, 'estop_active', False):
            return True
        if getattr(self._reg, 'stow_in_progress', False):
            return True
        # lock_mode==2 = Child Lock — blocks motion-class behaviors
        # (sounds and lights are operator-level, see ALIVE gate below)
        if getattr(self._reg, 'lock_mode', 0) == 2:
            return True
        return False

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
            # P3 fix 2026-05-16: tick 5s when ALIVE on (needs responsive
            # idle check), 30s when off (just polling enabled flag).
            # Reduces idle CPU/GIL pressure significantly when operator
            # never enables ALIVE.
            try:
                alive = self._cfg.getboolean('behavior', 'alive_enabled', fallback=False)
            except Exception:
                alive = False
            self._stop_event.wait(timeout=5.0 if alive else 30.0)

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

        mode = self._cfg.get('behavior', 'idle_mode', fallback='choreo')

        # B14 fix 2026-05-16: only advance _last_idle_trigger if the
        # trigger ACTUALLY dispatched. Previously, every safe_play
        # reject (lock_mode, busy, etc.) burned a 30s cooldown. Now
        # a refused choreo lets the next tick retry immediately.
        fired = False
        if mode == 'sounds':
            fired = self._trigger_sounds()
        elif mode == 'sounds_lights':
            fired = self._trigger_sounds()
            self._trigger_lights()  # lights don't gate the cooldown
        elif mode == 'lights':
            fired = self._trigger_lights()
        elif mode == 'choreo':
            fired = self._trigger_choreo()
        else:
            log.warning("Unknown idle_mode: %s", mode)
        if fired:
            self._last_idle_trigger = now

    # ------------------------------------------------------------------
    # Guard
    # ------------------------------------------------------------------

    def _should_trigger_idle(self, now: float) -> bool:
        """Return True if all conditions for an idle trigger are met."""
        alive = self._cfg.getboolean('behavior', 'alive_enabled', fallback=False)
        if not alive:
            return False

        # B1 fix 2026-05-16: skip if E-STOP / stow_in_progress engaged.
        # Was: only _trigger_choreo was gated via safe_play. Audio + lights
        # paths fired UART commands during declared emergency. Per
        # CLAUDE.md safety chain invariant.
        if self._is_safety_locked():
            return False

        # B8/E5/E19 fix 2026-05-16: at boot reg.last_activity is 0.0 →
        # since_activity = now - 0 = huge → fired idle within 30s of boot
        # regardless of idle_timeout_min. Treat 0.0 as 'never touched' →
        # bootstrap last_activity here so the first full timeout window
        # is honored.
        if self._reg.last_activity <= 0:
            self._reg.last_activity = now
            return False

        if self._reg.choreo.is_playing():
            return False

        # E2 fix 2026-05-16: clamp idle_timeout AT READ SITE. Hand-edited
        # local.cfg with idle_timeout_min=0 or negative used to make the
        # timeout 0s → engine fired every 30s indefinitely (only blocked
        # by _MIN_IDLE_GAP_S). Minimum 1 minute.
        raw_timeout = self._cfg.getfloat('behavior', 'idle_timeout_min', fallback=10.0)
        idle_timeout_s = max(60.0, raw_timeout * 60.0)
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

    def _trigger_sounds(self) -> bool:
        """Send UART random audio command for idle reaction.

        Schedules a delayed reset of reg.audio_playing so subsequent
        sounds/sounds_lights idle triggers are NOT permanently blocked
        by a flag that nothing ever clears. Returns True if the command
        was actually dispatched (B14: cooldown only on actual dispatch)."""
        try:
            category = self._cfg.get('behavior', 'idle_audio_category', fallback='happy')
            if not self._reg.uart:
                log.warning("ALIVE sounds: UART not available")
                return False
            self._reg.uart.send('S', f'RANDOM:{category}')
            self._reg.audio_playing = True
            self._schedule_audio_reset()
            log.info("ALIVE sounds: category=%s", category)
            return True
        except Exception:
            log.exception("ALIVE sounds trigger failed")
            return False

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

    def _trigger_lights(self) -> bool:
        """Trigger random lights animation via Teeces/AstroPixels controller.
        Returns True if dispatched (B14 cooldown gate)."""
        try:
            if not (self._reg.teeces and self._reg.teeces.is_ready()):
                log.warning("ALIVE lights: teeces driver not ready")
                return False
            self._reg.teeces.random_mode()
            log.info("ALIVE lights: random_mode triggered")
            return True
        except Exception:
            log.exception("ALIVE lights trigger failed")
            return False

    # B21 fix 2026-05-16: track last-played choreo to avoid same-twice-
    # in-a-row randomness annoyance. Operator perceives ALIVE as less
    # repetitive even with a 2-choreo list.
    _last_choreo_name: str = ''

    def _trigger_choreo(self) -> bool:
        """Pick a random choreo from idle_choreo_list and play it.
        Returns True if safe_play dispatched the choreo (B14 cooldown gate)."""
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
                return False

            # B21: prefer not to repeat the last one if there are alternatives
            candidates = [c for c in choreo_list if c != self._last_choreo_name]
            if not candidates:
                candidates = choreo_list   # only 1 entry total → no choice
            choreo_name = random.choice(candidates)
            choreo_path = os.path.join(self._choreo_dir, choreo_name + '.chor')
            if not os.path.isfile(choreo_path):
                log.warning("ALIVE choreo not found: %s", choreo_path)
                return False

            choreo_data = self._load_choreo(choreo_path)
            if not choreo_data:
                return False
            log.info("ALIVE choreo: %s", choreo_name)
            # B-8: route through choreo_bp.safe_play so concurrent
            # Sequences-tab clicks and behavior triggers contend on
            # the same _play_lock. Lazy import — choreo_bp imports
            # the registry which holds reg.behavior_engine, so a
            # top-level import would be circular.
            from master.api.choreo_bp import safe_play
            ok = safe_play(choreo_data, log_label='behavior')
            if ok:
                # W7 fix 2026-05-16: track for last-played indicator + B21
                self._last_choreo_name = choreo_name
                # Expose to /behavior/status
                self._last_choreo_ts = time.monotonic()
                return True
            # E9 fix 2026-05-16: log when safe_play refused so debugging
            # 'why didn't ALIVE fire?' has a breadcrumb in journalctl
            log.info("ALIVE choreo refused by safe_play: %s", choreo_name)
            return False
        except Exception:
            log.exception("ALIVE choreo trigger failed")
            return False

    # ------------------------------------------------------------------
    # Dome auto sync
    # ------------------------------------------------------------------

    def _sync_dome_auto(self, alive_on: bool) -> None:
        """Enable/disable dome auto rotation when ALIVE is toggled.

        B4 fix 2026-05-16: STOP path always runs unconditionally — we
        need to release dome ownership regardless of the current cfg
        flag. Previously: operator enables ALIVE with dome_auto=true →
        dome rotating. Operator edits dome_auto=false (no set_alive
        call). Operator clicks ALIVE OFF → _sync_dome_auto(False) early-
        returns because cfg flag is false → dome KEEPS rotating forever.
        Now: stop path bypasses the gate; only START honors the flag."""
        try:
            if not alive_on:
                # Always release dome ownership when ALIVE going OFF.
                if self._reg.dome:
                    self._reg.dome.set_random(False)
                    log.debug("Dome auto → False (ALIVE off, unconditional stop)")
                return
            dome_auto = self._cfg.getboolean('behavior', 'dome_auto_on_alive', fallback=True)
            if not dome_auto:
                return
            if self._reg.dome:
                self._reg.dome.set_random(True)
                log.debug("Dome auto → True (ALIVE on)")
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
