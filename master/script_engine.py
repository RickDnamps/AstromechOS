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
R2-D2 Script Engine — Phase 3.
Executes behavioral sequences from .scr files (CSV format).

.scr format (inspired by r2_control ScriptThread):
  # Comment
  sound,Happy001               → play a specific sound
  sound,RANDOM,happy           → random sound from category
  dome,turn,0.5                → dome rotation (speed -1.0..1.0)
  dome,stop                    → stop dome
  dome,random,on               → dome random mode
  servo,utility_arm_left,1.0,500  → servo: name, position, duration ms
  servo,all,close              → close all servos
  servo,all,open               → open all servos
  motion,0.5,0.5,2000          → drive: left, right, duration ms
  motion,stop                  → stop drive
  teeces,random                → Teeces random mode
  teeces,leia                  → Teeces Leia mode
  teeces,off                   → Teeces off
  teeces,anim,11               → trigger T-code animation (Imperial March)
  teeces,raw,0T5               → send raw JawaLite command
  sleep,1.5                    → pause 1.5 seconds
  sleep,random,2,5             → random pause between 2 and 5 seconds

Phase 3 activation:
  1. Uncomment the import in master/main.py
  2. Pass drivers to ScriptEngine in main()
  3. uart.register_callback('SCRIPT', engine.handle_uart) [optional]
"""

import csv
import glob
import logging
import os
import random
import threading
import time

log = logging.getLogger(__name__)

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), 'sequences')
LIGHT_DIR   = os.path.join(os.path.dirname(__file__), 'light_sequences')


class ScriptEngine:
    """
    R2-D2 sequence manager.
    Executes .scr files in daemon threads.
    """

    def __init__(self, uart=None, teeces=None,
                 vesc=None, dome=None, servo=None, dome_servo=None):
        """
        Parameters
        ----------
        uart       : UARTController  (for sending S:, M:, D:, SRV:)
        teeces     : TeecesController
        vesc       : VescDriver (master-side)
        dome       : DomeMotorDriver (DC dome rotation)
        servo      : BodyServoDriver (body panels via UART → Slave)
        dome_servo : DomeServoDriver (dome panels I2C direct on Master)
        """
        self._uart       = uart
        self._teeces     = teeces
        self._vesc       = vesc
        self._dome       = dome
        self._servo      = servo
        self._dome_servo = dome_servo
        self._running: dict[int, '_ScriptRunner'] = {}
        self._light_ids: set[int] = set()
        self._next_id = 1
        self._lock    = threading.Lock()
        self.sequences_dir = SCRIPTS_DIR

    def list_scripts(self) -> list[str]:
        """Returns the names of available scripts."""
        files = glob.glob(os.path.join(self.sequences_dir, '*.scr'))
        return [os.path.splitext(os.path.basename(f))[0] for f in sorted(files)]

    def list_running(self) -> list[dict]:
        """Returns currently running scripts."""
        with self._lock:
            return [
                {
                    'id': sid,
                    'name': r.name,
                    'step_index': r.step_index,
                    'step_total': r.step_total,
                    'current_cmd': r.current_cmd,
                }
                for sid, r in self._running.items()
            ]

    def run(self, name: str, loop: bool = False, skip_motion: bool = False) -> int | None:
        """
        Start a script — one at a time.
        Stops all running scripts and resets servos to closed position before starting.
        Returns the script ID or None if not found.
        """
        path = os.path.join(self.sequences_dir, name + '.scr')
        if not os.path.isfile(path):
            log.error(f"Script not found: {path}")
            return None

        # Only one script at a time: stop previous ones
        self.stop_all()

        # Reset servos to closed position before the new sequence
        try:
            if self._dome_servo:
                self._dome_servo.close_all()
        except Exception as e:
            log.warning(f"run: close_all dome_servo: {e}")
        try:
            if self._servo:
                self._servo.close_all()
        except Exception as e:
            log.warning(f"run: close_all servo: {e}")

        with self._lock:
            script_id = self._next_id
            self._next_id += 1

        runner = _ScriptRunner(
            script_id=script_id,
            name=name,
            path=path,
            loop=loop,
            engine=self,
            on_done=self._on_done,
            skip_motion=skip_motion,
        )
        with self._lock:
            self._running[script_id] = runner
        runner.start()
        log.info(f"Script started: {name} (id={script_id}, loop={loop})")
        return script_id

    def run_light(self, name: str, loop: bool = False) -> int | None:
        """
        Run a .lseq light sequence in parallel (does NOT stop other sequences,
        does NOT reset servos — light runs alongside regular sequences).
        """
        path = os.path.join(LIGHT_DIR, f'{name}.lseq')
        if not os.path.isfile(path):
            log.warning('run_light: not found: %s', path)
            return None
        with self._lock:
            script_id     = self._next_id
            self._next_id += 1
        runner = _ScriptRunner(
            script_id=script_id,
            name=name,
            path=path,
            loop=loop,
            engine=self,
            on_done=self._on_done,
            skip_motion=True,   # light sequences never drive motors
        )
        with self._lock:
            self._running[script_id] = runner
            self._light_ids.add(script_id)
        runner.start()
        log.info('Light sequence started: %s (id=%d)', name, script_id)
        return script_id

    def stop_light_all(self) -> None:
        """Stop only light sequences — leaves regular sequences and audio untouched."""
        with self._lock:
            ids_to_stop = list(self._light_ids)
            self._light_ids.clear()
            runners = [self._running.pop(sid, None) for sid in ids_to_stop]
        for runner in runners:
            if runner:
                runner.stop()
        log.info('All light sequences stopped')

    def stop(self, script_id: int) -> bool:
        """Stop a script by ID — removes it from _running immediately."""
        with self._lock:
            runner = self._running.pop(script_id, None)
        if runner:
            runner.stop()
            log.info(f"Script stopped: {runner.name} (id={script_id})")
            return True
        return False

    def stop_all(self) -> None:
        """Stop all running sequences and cut audio."""
        with self._lock:
            runners = list(self._running.values())
            self._running.clear()
        for runner in runners:
            runner.stop()
        # Stop current audio (e.g. Gangnam, Birthday)
        if self._uart:
            try:
                self._uart.send('S', 'STOP')
            except Exception as e:
                log.warning(f"stop_all: S:STOP failed: {e}")

    # ------------------------------------------------------------------
    # Script command dispatch
    # ------------------------------------------------------------------

    def execute_command(self, row: list[str], stop_event=None, skip_motion: bool = False) -> None:
        """Execute a CSV line from a script."""
        if not row or row[0].startswith('#'):
            return
        cmd = row[0].lower().strip()

        try:
            if cmd == 'sleep':
                self._cmd_sleep(row, stop_event)
            elif cmd == 'sound':
                self._cmd_sound(row)
            elif cmd == 'dome':
                self._cmd_dome(row)
            elif cmd == 'servo':
                self._cmd_servo(row)
            elif cmd == 'motion':
                if skip_motion:
                    log.debug("motion ignored (test mode without propulsion)")
                else:
                    self._cmd_motion(row)
            elif cmd == 'teeces':
                self._cmd_teeces(row)
            elif cmd == 'lseq':
                self._cmd_lseq(row)
            elif cmd == 'wait_light':
                self._cmd_wait_light(row, stop_event)
            else:
                log.debug(f"Unknown script command: {cmd!r}")
        except Exception as e:
            log.error(f"Error executing command {row}: {e}")

    def _cmd_sleep(self, row: list[str], stop_event=None) -> None:
        if row[1] == 'random':
            t = random.uniform(float(row[2]), float(row[3]))
        elif row[1] == 'fixed':
            t = float(row[2])
        else:
            t = float(row[1])  # legacy: sleep,1.0
        if stop_event:
            stop_event.wait(t)   # interruptible — returns as soon as stop is signaled
        else:
            time.sleep(t)

    def _cmd_sound(self, row: list[str]) -> None:
        if not self._uart:
            return
        if row[1].upper() == 'RANDOM':
            category = row[2] if len(row) > 2 else 'happy'
            self._uart.send('S', f'RANDOM:{category}')
        else:
            self._uart.send('S', row[1])

    def _cmd_dome(self, row: list[str]) -> None:
        if not self._dome:
            return
        action = row[1].lower()
        if action == 'turn':
            self._dome.turn(float(row[2]))
        elif action == 'stop':
            self._dome.stop()
        elif action == 'center':
            self._dome.center()
        elif action == 'random':
            self._dome.set_random(row[2].lower() == 'on')

    def _cmd_servo(self, row: list[str]) -> None:
        if row[1].lower() == 'all':
            action = row[2].lower() if len(row) > 2 else 'open'
            if self._dome_servo:
                if action == 'open':
                    self._dome_servo.open_all()
                else:
                    self._dome_servo.close_all()
            if self._servo:
                if action == 'open':
                    self._servo.open_all()
                else:
                    self._servo.close_all()
            return

        name   = row[1]
        action = row[2].lower() if len(row) > 2 else 'open'

        if action in ('open', 'close'):
            # servo,Servo_M0,open          → calibrated angle
            # servo,Servo_M0,open,150      → angle override
            # servo,Servo_M0,open,150,8    → angle + speed override
            angle = float(row[3]) if len(row) > 3 else None
            speed = int(row[4])   if len(row) > 4 else None
            if name.startswith('Servo_M'):
                if self._dome_servo:
                    if action == 'open':
                        self._dome_servo.open(name, angle, speed)
                    else:
                        self._dome_servo.close(name, angle, speed)
            else:
                if self._servo:
                    if action == 'open':
                        self._servo.open(name, angle, speed)
                    else:
                        self._servo.close(name, angle, speed)
            return

        position = float(action)
        duration = int(row[3]) if len(row) > 3 else 300

        if name.startswith('Servo_M'):
            if self._dome_servo:
                self._dome_servo.move(name, position, duration)
        else:
            if self._servo:
                self._servo.move(name, position, duration)

    def _cmd_motion(self, row: list[str]) -> None:
        # Child Lock — block all motion commands from sequences
        try:
            import master.registry as _reg
            if getattr(_reg, 'lock_mode', 0) == 2:
                log.debug("_cmd_motion ignored: Child Lock active")
                return
        except Exception:
            pass

        if not self._vesc:
            return
        if row[1].lower() == 'stop':
            self._vesc.stop()
        else:
            left     = float(row[1])
            right    = float(row[2])
            duration = int(row[3]) if len(row) > 3 else 0
            self._vesc.drive(left, right)
            if duration > 0:
                time.sleep(duration / 1000.0)
                self._vesc.stop()

    def _cmd_teeces(self, row: list[str]) -> None:
        if not self._teeces:
            return
        action = row[1].lower()
        if action == 'random':
            self._teeces.random_mode()
        elif action == 'leia':
            self._teeces.leia()
        elif action == 'off':
            self._teeces.off()
        elif action == 'text':
            text    = row[2] if len(row) > 2 else ''
            display = row[3].lower() if len(row) > 3 else 'fld'
            self._teeces.text(text, display)
        elif action == 'psi':
            mode = int(row[2]) if len(row) > 2 else 0
            # mode=0 in .scr means "random" (legacy from psi_random)
            self._teeces.psi(1 if mode == 0 else mode)
        elif action == 'anim':
            mode = int(row[2]) if len(row) > 2 else 1
            self._teeces.animation(mode)
        elif action == 'raw':
            self._teeces.raw(row[2] if len(row) > 2 else '')

    def _cmd_lseq(self, row: list[str]) -> None:
        """Fire-and-forget: start a light sequence in background (parallel like sound)."""
        if len(row) < 2 or not row[1]:
            log.warning('lseq: missing name')
            return
        name = row[1].strip()
        # Run in a daemon thread so the main sequence continues immediately
        t = threading.Thread(
            target=self.run_light,
            args=(name,),
            daemon=True,
            name=f'lseq-{name}',
        )
        t.start()
        log.debug('lseq: launched %s in background', name)

    def _cmd_wait_light(self, row: list[str], stop_event=None) -> None:
        """Block until all running light sequences finish (or stop_event is set)."""
        log.debug('wait_light: waiting for light sequences to finish')
        while True:
            with self._lock:
                if not self._light_ids:
                    return
            if stop_event and stop_event.is_set():
                return
            time.sleep(0.1)

    def _on_done(self, script_id: int) -> None:
        with self._lock:
            self._running.pop(script_id, None)
            self._light_ids.discard(script_id)


# ------------------------------------------------------------------
# Runner thread
# ------------------------------------------------------------------

class _ScriptRunner(threading.Thread):
    def __init__(self, script_id: int, name: str, path: str,
                 loop: bool, engine: ScriptEngine, on_done,
                 skip_motion: bool = False):
        super().__init__(name=f"script-{name}", daemon=True)
        self.script_id = script_id
        self.name      = name
        self._path     = path
        self._loop     = loop
        self._engine   = engine
        self._on_done  = on_done
        self._stop_event = threading.Event()
        self._skip_motion = skip_motion
        self.step_index   = 0
        self.step_total   = 0
        self.current_cmd  = ""

    def _count_steps(self, path) -> int:
        """Count non-comment, non-empty lines in a .scr file."""
        count = 0
        try:
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    stripped = line.strip()
                    if stripped and not stripped.startswith('#'):
                        count += 1
        except Exception:
            pass
        return count

    def _run_file(self, path, stop_event: threading.Event) -> None:
        """Execute all commands in a .scr file. Respects stop_event.

        # WARNING: script,name commands are recursive. A→B→A causes infinite
        # recursion until stop_event is set or Python stack limit is hit.
        # Use the STOP button to break circular sub-sequences.
        """
        self.step_total = self._count_steps(path)
        self.step_index = 0
        try:
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    if stop_event.is_set():
                        return
                    row = [c.strip() for c in line.split(',')]
                    if not row or not row[0] or row[0].startswith('#'):
                        continue
                    # Handle script,name sub-sequence inline (recursive, blocking)
                    if row[0].lower() == 'script':
                        if len(row) < 2 or not row[1]:
                            log.warning("script: missing name, skipping")
                            continue
                        sub_name = row[1]
                        sub_path = os.path.join(self._engine.sequences_dir,
                                                f"{sub_name}.scr")
                        if os.path.isfile(sub_path):
                            self._run_file(sub_path, stop_event)
                        else:
                            log.warning(f"script: sub-sequence '{sub_name}' not found, skipping")
                        continue
                    # Track step progress
                    self.current_cmd = line.strip()
                    self.step_index += 1
                    self._engine.execute_command(row, stop_event,
                                                 skip_motion=self._skip_motion)
        except Exception as e:
            log.error(f"Error reading file {path}: {e}")

    def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._run_file(self._path, self._stop_event)
            except Exception as e:
                log.error(f"Script error {self.name}: {e}")
                break
            if not self._loop:
                break
        self._on_done(self.script_id)
        log.debug(f"Script finished: {self.name}")

    def stop(self) -> None:
        self._stop_event.set()
