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
Version Check — Version validation at Slave boot.
Requests the version from the Master via UART and compares it with the local version.
Triggers a rsync if versions differ (max 3 attempts with backoff).
"""

import logging
import threading
import time
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

log = logging.getLogger(__name__)

VERSION_FILE = "/home/artoo/r2d2/VERSION"
VERSION_REQUEST_TIMEOUT_S = 10.0
MAX_SYNC_RETRIES = 3
SYNC_RETRY_BACKOFF_S = [5, 15, 30]


class VersionChecker:
    def __init__(self, uart_listener, display_driver=None):
        self._uart = uart_listener
        self._display = display_driver
        self._master_version: str | None = None
        self._version_event = threading.Event()

    def run(self) -> bool:
        """
        Runs the version check.
        Returns True if versions match or sync succeeded, False if in degraded mode.
        """
        local_version = self._read_local_version()
        log.info(f"Local version: {local_version}")

        if self._display:
            self._display.syncing(local_version)

        # Register version callback
        self._uart.register_callback('V', self._on_version_received)

        # Request version from Master
        self._uart.send('V', '?')
        log.info("Requesting version from Master...")

        if not self._version_event.wait(timeout=VERSION_REQUEST_TIMEOUT_S):
            log.error("Master unreachable — starting in degraded mode")
            if self._display:
                self._display.error("MASTER_OFFLINE")
            return False

        master_version = self._master_version
        log.info(f"Master version: {master_version}")

        if local_version == master_version:
            log.info("Versions match — normal startup")
            if self._display:
                self._display.ready(local_version)  # green OPERATIONAL screen 3s
            return True

        # Versions differ → rsync
        log.warning(f"Version mismatch: local={local_version} master={master_version}")
        if self._display:
            self._display.syncing(master_version)

        success = self._trigger_rsync(master_version)
        if success:
            if self._display:
                self._display.ready(master_version)  # green OPERATIONAL screen 3s
            return True
        else:
            log.error("Sync failed — starting in degraded mode with local version")
            if self._display:
                self._display.error("SYNC_FAILED")
            return False

    def _on_version_received(self, value: str) -> None:
        """UART callback: receives the version from the Master."""
        if value == '?':
            # Master demande notre version
            local = self._read_local_version()
            self._uart.send('V', local)
            return
        self._master_version = value
        self._version_event.set()

    def _read_local_version(self) -> str:
        try:
            with open(VERSION_FILE) as f:
                return f.read().strip()
        except Exception:
            return "unknown"

    def _trigger_rsync(self, expected_version: str) -> bool:
        """
        Requests a resync from the Master via HTTP POST /system/resync_slave.
        The Master runs resync_slave.sh (rsync + service install + restart).
        If resync succeeds, the service is restarted by the Master → this process stops.
        """
        import urllib.request
        import json

        MASTER_API = "http://192.168.4.1:5000"

        for attempt in range(MAX_SYNC_RETRIES):
            log.info(f"Sync attempt {attempt + 1}/{MAX_SYNC_RETRIES}")
            try:
                req = urllib.request.Request(
                    f"{MASTER_API}/system/resync_slave",
                    data=json.dumps({}).encode(),
                    headers={'Content-Type': 'application/json'},
                    method='POST'
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    log.info(f"Resync requested from Master: {resp.status}")
                # Wait for the Master to rsync and restart this service
                # Service restart would kill this process — if we reach here, it failed
                backoff = SYNC_RETRY_BACKOFF_S[attempt] if attempt < MAX_SYNC_RETRIES - 1 else 30
                log.info(f"Waiting {backoff}s for Master resync...")
                time.sleep(backoff)
                local = self._read_local_version()
                if local == expected_version:
                    log.info(f"Sync succeeded on attempt {attempt + 1}")
                    return True
            except Exception as e:
                log.warning(f"HTTP resync failed: {e}")
                if attempt < MAX_SYNC_RETRIES - 1:
                    time.sleep(SYNC_RETRY_BACKOFF_S[attempt])

        log.error("All resync attempts failed")
        return False
