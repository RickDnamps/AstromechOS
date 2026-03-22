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
Moteur de scripts R2-D2 — Phase 3.
Exécute des séquences comportementales depuis des fichiers .scr (CSV).

Format .scr (inspiré de r2_control ScriptThread):
  # Commentaire
  sound,Happy001               → joue un son spécifique
  sound,RANDOM,happy           → son aléatoire de catégorie
  dome,turn,0.5                → rotation dôme (vitesse -1.0..1.0)
  dome,stop                    → arrêt dôme
  dome,random,on               → mode aléatoire dôme
  servo,utility_arm_left,1.0,500  → servo: nom, position, durée ms
  servo,all,close              → ferme tous les servos
  servo,all,open               → ouvre tous les servos
  motion,0.5,0.5,2000          → propulsion: left, right, durée ms
  motion,stop                  → arrêt propulsion
  teeces,random                → Teeces mode aléatoire
  teeces,leia                  → Teeces mode Leia
  teeces,off                   → Teeces éteint
  sleep,1.5                    → pause 1.5 secondes
  sleep,random,2,5             → pause aléatoire entre 2 et 5 secondes

Activation Phase 3:
  1. Décommenter l'import dans master/main.py
  2. Passer les drivers au ScriptEngine dans main()
  3. uart.register_callback('SCRIPT', engine.handle_uart) [optionnel]
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


class ScriptEngine:
    """
    Gestionnaire de séquences R2-D2.
    Exécute des fichiers .scr dans des threads daemon.
    """

    def __init__(self, uart=None, teeces=None,
                 vesc=None, dome=None, servo=None, dome_servo=None):
        """
        Parameters
        ----------
        uart       : UARTController  (pour envoyer S:, M:, D:, SRV:)
        teeces     : TeecesController
        vesc       : VescDriver (master-side)
        dome       : DomeMotorDriver (rotation dôme DC)
        servo      : BodyServoDriver (panneaux body via UART → Slave)
        dome_servo : DomeServoDriver (panneaux dôme I2C direct sur Master)
        """
        self._uart       = uart
        self._teeces     = teeces
        self._vesc       = vesc
        self._dome       = dome
        self._servo      = servo
        self._dome_servo = dome_servo
        self._running: dict[int, '_ScriptRunner'] = {}
        self._next_id = 1
        self._lock    = threading.Lock()

    def list_scripts(self) -> list[str]:
        """Retourne les noms des scripts disponibles."""
        files = glob.glob(os.path.join(SCRIPTS_DIR, '*.scr'))
        return [os.path.splitext(os.path.basename(f))[0] for f in sorted(files)]

    def list_running(self) -> list[dict]:
        """Retourne les scripts en cours d'exécution."""
        with self._lock:
            return [{'id': sid, 'name': r.name}
                    for sid, r in self._running.items()]

    def run(self, name: str, loop: bool = False) -> int | None:
        """
        Lance un script — un seul à la fois.
        Arrête tous les scripts en cours et remet les servos en position fermée avant de démarrer.
        Retourne l'ID du script ou None si introuvable.
        """
        path = os.path.join(SCRIPTS_DIR, name + '.scr')
        if not os.path.isfile(path):
            log.error(f"Script introuvable: {path}")
            return None

        # Un seul script à la fois : stopper les précédents
        self.stop_all()

        # Reset servos en position fermée avant la nouvelle séquence
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
        )
        with self._lock:
            self._running[script_id] = runner
        runner.start()
        log.info(f"Script lancé: {name} (id={script_id}, loop={loop})")
        return script_id

    def stop(self, script_id: int) -> bool:
        """Arrête un script par ID — retire immédiatement de _running."""
        with self._lock:
            runner = self._running.pop(script_id, None)
        if runner:
            runner.stop()
            log.info(f"Script arrêté: {runner.name} (id={script_id})")
            return True
        return False

    def stop_all(self) -> None:
        """Arrête toutes les séquences en cours + coupe le son."""
        with self._lock:
            runners = list(self._running.values())
            self._running.clear()
        for runner in runners:
            runner.stop()
        # Couper le son en cours (ex. Gangnam, Birthday)
        if self._uart:
            try:
                self._uart.send('S', 'STOP')
            except Exception as e:
                log.warning(f"stop_all: S:STOP failed: {e}")

    # ------------------------------------------------------------------
    # Dispatch des commandes de script
    # ------------------------------------------------------------------

    def execute_command(self, row: list[str], stop_event=None) -> None:
        """Exécute une ligne CSV de script."""
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
                self._cmd_motion(row)
            elif cmd == 'teeces':
                self._cmd_teeces(row)
            else:
                log.debug(f"Commande script inconnue: {cmd!r}")
        except Exception as e:
            log.error(f"Erreur exécution commande {row}: {e}")

    def _cmd_sleep(self, row: list[str], stop_event=None) -> None:
        if row[1] == 'random':
            t = random.uniform(float(row[2]), float(row[3]))
        else:
            t = float(row[1])
        if stop_event:
            stop_event.wait(t)   # interruptible — retourne dès que stop est signalé
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
            # servo,dome_panel_1,open          → angle calibré
            # servo,dome_panel_1,open,150      → angle override
            # servo,dome_panel_1,open,150,8    → angle + speed override
            angle = float(row[3]) if len(row) > 3 else None
            speed = int(row[4])   if len(row) > 4 else None
            if name.startswith('dome_panel_'):
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

        if name.startswith('dome_panel_'):
            if self._dome_servo:
                self._dome_servo.move(name, position, duration)
        else:
            if self._servo:
                self._servo.move(name, position, duration)

    def _cmd_motion(self, row: list[str]) -> None:
        # Child Lock — filtrer toutes les commandes de déplacement des séquences
        try:
            import master.registry as _reg
            if getattr(_reg, 'lock_mode', 0) == 2:
                log.debug("_cmd_motion ignoré: Child Lock actif")
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
            self._teeces.leia_mode()
        elif action == 'off':
            self._teeces.all_off()
        elif action == 'text':
            self._teeces.fld_text(row[2] if len(row) > 2 else '')
        elif action == 'psi':
            mode = int(row[2]) if len(row) > 2 else 0
            if mode == 0:
                self._teeces.psi_random()
            else:
                self._teeces.psi_mode(mode)

    def _on_done(self, script_id: int) -> None:
        with self._lock:
            self._running.pop(script_id, None)


# ------------------------------------------------------------------
# Runner thread
# ------------------------------------------------------------------

class _ScriptRunner(threading.Thread):
    def __init__(self, script_id: int, name: str, path: str,
                 loop: bool, engine: ScriptEngine, on_done):
        super().__init__(name=f"script-{name}", daemon=True)
        self.script_id = script_id
        self.name      = name
        self._path     = path
        self._loop     = loop
        self._engine   = engine
        self._on_done  = on_done
        self._stop_event = threading.Event()

    def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                with open(self._path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    for row in reader:
                        if self._stop_event.is_set():
                            break
                        self._engine.execute_command(row, self._stop_event)
            except Exception as e:
                log.error(f"Erreur lecture script {self.name}: {e}")
                break

            if not self._loop:
                break

        self._on_done(self.script_id)
        log.debug(f"Script terminé: {self.name}")

    def stop(self) -> None:
        self._stop_event.set()
