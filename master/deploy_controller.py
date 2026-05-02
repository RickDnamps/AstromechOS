# ============================================================
#  ██████╗ ██████╗       ██████╗ ██████╗
#  ██╔══██╗╚════██╗      ██╔══██╗╚════██╗
#  ██████╔╝ █████╔╝      ██║  ██║ █████╔╝
#  ██╔══██╗██╔═══╝       ██║  ██║██╔═══╝
#  ██║  ██║███████╗      ██████╔╝███████╗
#  ╚═╝  ╚═╝╚══════╝      ╚═════╝ ╚══════╝
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
Deploy Controller — Update and deployment.
- git pull from wlan1 (internet)
- rsync /slave/ to Pi Zero via SSH
- Physical dome button (short=update, long=rollback, double=version)
- Reboot Slave via UART
"""

import logging
import subprocess
import threading
import time
import configparser
import sys
import os

log = logging.getLogger(__name__)

VERSION_FILE = "/home/artoo/r2d2/VERSION"
MAX_SYNC_RETRIES = 3
SYNC_RETRY_BACKOFF_S = [5, 15, 30]


class DeployController:
    def __init__(self, cfg: configparser.ConfigParser, uart_controller, teeces_controller):
        self._repo_path   = cfg.get('master', 'repo_path')
        self._slave_user  = cfg.get('deploy', 'slave_user')
        self._slave_host  = cfg.get('slave',  'host',             fallback=cfg.get('deploy', 'slave_host'))
        self._slave_path  = cfg.get('deploy', 'slave_path')
        self._button_pin  = cfg.getint('deploy', 'button_pin',    fallback=17)
        self._short_press_threshold = cfg.getfloat('deploy', 'button_short_press_s')
        self._internet_iface = cfg.get('network', 'internet_interface')
        self._github_url    = cfg.get('github', 'repo_url',   fallback='')
        self._github_branch = cfg.get('github', 'branch',     fallback='main')
        self._uart = uart_controller
        self._teeces = teeces_controller
        self._running = False

    def start(self) -> None:
        self._running = True
        threading.Thread(target=self._button_loop, name="deploy-btn", daemon=True).start()
        log.info("DeployController started")

    def stop(self) -> None:
        self._running = False

    # ------------------------------------------------------------------
    # GPIO Button
    # ------------------------------------------------------------------

    def _button_loop(self) -> None:
        try:
            import RPi.GPIO as GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self._button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        except Exception as e:
            log.error(f"GPIO init failed: {e} — button disabled")
            return

        last_release = 0.0
        while self._running:
            try:
                if GPIO.input(self._button_pin) == GPIO.LOW:
                    press_start = time.monotonic()
                    # Wait for release
                    while GPIO.input(self._button_pin) == GPIO.LOW:
                        time.sleep(0.05)
                    duration = time.monotonic() - press_start

                    now = time.monotonic()
                    if duration >= self._short_press_threshold:
                        # Long press → rollback
                        log.info("Button: long press → rollback")
                        self.rollback()
                    elif (now - last_release) < 0.5:
                        # Double press → show version
                        log.info("Button: double press → show version")
                        self._show_version()
                    else:
                        # Short press → update
                        log.info("Button: short press → update")
                        self.update_and_deploy()

                    last_release = now
                time.sleep(0.05)
            except Exception as e:
                log.error(f"Error in button_loop: {e}")
                time.sleep(1)

    # ------------------------------------------------------------------
    # Main actions
    # ------------------------------------------------------------------

    def update_and_deploy(self) -> bool:
        """Short press: git pull (if internet available) + rsync + reboot Slave."""
        if self._is_internet_available():
            self.git_pull()
        else:
            log.info("wlan1 unavailable — rsync local version")
        success = self.rsync_to_slave()
        if success:
            self.reboot_slave()
        return success

    def rollback(self) -> bool:
        """Long press: git checkout HEAD^ + rsync + reboot Slave."""
        log.info("Rollback: git checkout HEAD^")
        try:
            result = subprocess.run(
                ["git", "checkout", "HEAD^"],
                cwd=self._repo_path,
                capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                log.error(f"git checkout HEAD^ failed: {result.stderr}")
                return False
            self._update_version_file()
            log.info("Rollback git OK")
        except Exception as e:
            log.error(f"Rollback error: {e}")
            return False

        success = self.rsync_to_slave()
        if success:
            self.reboot_slave()
        return success

    def git_pull(self) -> bool:
        """
        git pull with timeout.
        Uses the GitHub URL from local.cfg — supports forks.
        Updates remote 'origin' if the URL has changed.
        """
        try:
            # Sync remote origin with local.cfg if needed
            if self._github_url:
                self._sync_remote_url()

            result = subprocess.run(
                ["git", "pull", "origin", self._github_branch],
                cwd=self._repo_path,
                timeout=30,
                capture_output=True, text=True
            )
            if result.returncode == 0:
                self._update_version_file()
                log.info(f"git pull succeeded (branch: {self._github_branch})")
                return True
            else:
                log.warning(f"git pull failed: {result.stderr.strip()}")
                return False
        except subprocess.TimeoutExpired:
            log.warning("git pull timeout")
            return False
        except Exception as e:
            log.error(f"git pull error: {e}")
            return False

    def _sync_remote_url(self) -> None:
        """Updates git remote origin if the URL in local.cfg has changed."""
        url = self._github_url
        if not (url.startswith('https://') or url.startswith('http://') or url.startswith('git@')):
            log.warning(f"Invalid GitHub URL ignored: {url!r}")
            return
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=self._repo_path,
                capture_output=True, text=True, timeout=5
            )
            current_url = result.stdout.strip()
            if current_url != url:
                subprocess.run(
                    ["git", "remote", "set-url", "origin", url],
                    cwd=self._repo_path, timeout=5, check=True
                )
                log.info(f"Remote origin updated: {url}")
        except Exception as e:
            log.warning(f"Unable to sync remote URL: {e}")

    def rsync_to_slave(self, retries: int = MAX_SYNC_RETRIES) -> bool:
        """rsync slave/ to Pi Zero. Retry with backoff."""
        slave_slave_path = f"{self._slave_user}@{self._slave_host}:{self._slave_path}/"
        local_path = os.path.join(self._repo_path, "slave/")

        for attempt in range(retries):
            try:
                log.info(f"rsync attempt {attempt + 1}/{retries}")
                result = subprocess.run(
                    [
                        "rsync", "-avz", "--delete",
                        "-e", "ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10",
                        local_path, slave_slave_path
                    ],
                    timeout=120,
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    log.info("rsync succeeded")
                    return True
                else:
                    log.warning(f"rsync failed (code {result.returncode}): {result.stderr.strip()}")
            except subprocess.TimeoutExpired:
                log.warning("rsync timeout")
            except Exception as e:
                log.error(f"rsync error: {e}")

            if attempt < retries - 1:
                backoff = SYNC_RETRY_BACKOFF_S[attempt]
                log.info(f"Retrying in {backoff}s")
                time.sleep(backoff)

        log.error("rsync failed after all retries")
        if self._teeces:
            self._teeces.system_error("SYNC")
        return False

    def reboot_slave(self) -> None:
        """Sends REBOOT command to the Slave via UART."""
        if self._uart:
            self._uart.send('REBOOT', '1')
            log.info("REBOOT command sent to Slave")

    # ------------------------------------------------------------------
    # Utilitaires
    # ------------------------------------------------------------------

    def _show_version(self) -> None:
        version = self._read_version()
        if self._teeces:
            self._teeces.show_version(version)
        log.info(f"Current version: {version}")

    def _update_version_file(self) -> None:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=self._repo_path,
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                with open(VERSION_FILE, 'w') as f:
                    f.write(version)
                log.info(f"VERSION updated: {version}")
        except Exception as e:
            log.error(f"Error updating VERSION: {e}")

    def _read_version(self) -> str:
        try:
            with open(VERSION_FILE) as f:
                return f.read().strip()
        except Exception:
            return "unknown"

    def _is_internet_available(self) -> bool:
        try:
            result = subprocess.run(
                ["ip", "addr", "show", self._internet_iface],
                capture_output=True, text=True, timeout=5
            )
            return "inet " in result.stdout
        except Exception:
            return False
