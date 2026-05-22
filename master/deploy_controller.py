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
Deploy Controller — Update and deployment.
- git pull from wlan1 (internet)
- rsync /slave/ to Pi Zero via SSH
- Reboot Slave via UART
- update_and_deploy() / rollback() called from web UI or auto-pull
"""

import logging
import re
import subprocess
import threading
import configparser
import os
import time   # B-51: rsync_to_slave's retry loop calls time.sleep(backoff)
              # but the module never imported time → NameError on first
              # retry. Settings audit 2026-05-15.

log = logging.getLogger(__name__)

from shared.paths import VERSION_FILE, MAIN_CFG, LOCAL_CFG
MAX_SYNC_RETRIES = 3
SYNC_RETRY_BACKOFF_S = [5, 15, 30]

# B4 fix 2026-05-16: branch name validator. Reject leading '-' (git would
# parse as option flag → 'git pull origin --upload-pack=/tmp/pwn' → RCE).
# Allowed: letters, digits, ./_- and / (for refs/heads/foo).
_SAFE_BRANCH_RE = re.compile(r'^[A-Za-z0-9._/\-]+$')

# E1/B7 fix 2026-05-16: module-level deploy lock — prevents two
# concurrent UPDATE clicks from racing on .git/index.lock.
_deploy_lock = threading.Lock()


class DeployController:
    def __init__(self, cfg: configparser.ConfigParser, uart_controller, teeces_controller):
        self._repo_path      = cfg.get('master', 'repo_path')
        self._slave_user     = cfg.get('deploy', 'slave_user')
        # B2/E3 fix 2026-05-16: read from cfg at INIT only for default,
        # but reload from disk on every operation that uses these fields
        # (reload_cfg). Was: cached at init → operator's /settings/config
        # change to slave_host / repo_url / branch silently ignored until
        # Master reboot.
        self._slave_path     = cfg.get('deploy', 'slave_path')
        self._internet_iface = cfg.get('network', 'internet_interface')
        self._uart    = uart_controller
        self._teeces  = teeces_controller
        self.reload_cfg()  # populate slave_host/github_url/branch from local.cfg

    def reload_cfg(self) -> None:
        """B2/E3 fix 2026-05-16: re-read mutable cfg fields from disk.
        Called from __init__ + at the start of every deploy action so
        operator's /settings/config changes take effect immediately."""
        c = configparser.ConfigParser()
        c.read([MAIN_CFG, LOCAL_CFG])
        self._slave_host    = c.get('slave',  'host',     fallback='r2-slave.local')
        self._github_url    = c.get('github', 'repo_url', fallback='')
        self._github_branch = c.get('github', 'branch',   fallback='main')

    def start(self) -> None:
        log.info("DeployController started")

    # ------------------------------------------------------------------
    # Main actions
    # ------------------------------------------------------------------

    def update_and_deploy(self) -> bool:
        """Short press: git pull (if internet available) + rsync + reboot Slave.
        B1 fix 2026-05-16: also restart astromech-master.service AFTER rsync
        so the NEW Python code actually loads. Was: only the new HTML/JS was
        served (via static files) but Python kept running OLD code until
        manual REBOOT MASTER click.
        B2/E3 fix: reload_cfg() at start so operator's recent /settings/config
        changes (repo_url, branch, slave host) are picked up."""
        # E1/B7 fix: serialize concurrent deploys
        if not _deploy_lock.acquire(blocking=False):
            log.warning("update_and_deploy refused: another deploy in progress")
            return False
        try:
            self.reload_cfg()
            if self._is_internet_available():
                self.git_pull()
            else:
                log.info("wlan1 unavailable — rsync local version")
            success = self.rsync_to_slave()
            if success:
                self.reboot_slave()
                # B1 fix 2026-05-16: restart Master service so the new Python
                # code on disk actually loads (rsync only updated Slave +
                # /static files served fresh, but Flask still runs old code).
                self._restart_master_async()
            return success
        finally:
            _deploy_lock.release()

    def _restart_master_async(self) -> None:
        """Fire-and-forget Master service restart. systemd will respawn us
        with the new code. The HTTP response from /system/update was
        already sent before this fires, so the dying request connection
        is acceptable."""
        def _restart():
            time.sleep(1.0)  # give the HTTP response time to flush
            try:
                subprocess.run(
                    ['sudo', 'systemctl', 'restart', 'astromech-master.service'],
                    check=False, timeout=10
                )
            except Exception as e:
                log.error(f"Master restart failed: {e}")
        threading.Thread(target=_restart, name='deploy-master-restart', daemon=True).start()
        log.info("Master service restart scheduled in 1s")

    def rollback(self) -> bool:
        """Long press: git checkout HEAD^ + rsync + reboot Slave.
        E1 fix 2026-05-16: same deploy lock as update_and_deploy.
        B1 fix: restart Master service after rsync."""
        if not _deploy_lock.acquire(blocking=False):
            log.warning("rollback refused: another deploy in progress")
            return False
        try:
            self.reload_cfg()
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
                self._restart_master_async()
            return success
        finally:
            _deploy_lock.release()

    def git_pull(self) -> bool:
        """
        git pull with timeout.
        Uses the GitHub URL from local.cfg — supports forks.
        Updates remote 'origin' if the URL has changed.
        """
        try:
            # B4 fix 2026-05-16: validate branch name BEFORE passing to git.
            # Without this, branch='--upload-pack=/tmp/pwn' (no whitespace,
            # passes the validator at /settings/config level) would let
            # git parse it as an OPTION FLAG and run /tmp/pwn as the remote
            # helper → RCE on Master under admin auth boundary.
            if not _SAFE_BRANCH_RE.match(self._github_branch or ''):
                log.error(f"git pull refused: unsafe branch name {self._github_branch!r}")
                return False
            if self._github_branch.startswith('-'):
                log.error(f"git pull refused: branch starts with '-' {self._github_branch!r}")
                return False

            # Sync remote origin with local.cfg if needed
            if self._github_url:
                self._sync_remote_url()

            # B12 fix 2026-05-16: --ff-only prevents merge commits on
            # divergence (operator might have a dev commit on the Pi
            # that we'd otherwise auto-merge, polluting history).
            # Also use '--' separator as defense-in-depth against future
            # branch-name parser quirks.
            result = subprocess.run(
                ["git", "pull", "--ff-only", "origin", "--", self._github_branch],
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
