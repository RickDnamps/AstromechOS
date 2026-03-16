"""
Version Check — Validation de version au boot du Slave.
Demande la version au Master via UART et compare avec la version locale.
Déclenche un rsync si divergence (max 3 tentatives avec backoff).
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
        Exécute la vérification de version.
        Retourne True si versions identiques ou sync réussi, False si mode dégradé.
        """
        local_version = self._read_local_version()
        log.info(f"Version locale: {local_version}")

        if self._display:
            self._display.syncing(local_version)

        # Enregistrer callback version
        self._uart.register_callback('V', self._on_version_received)

        # Demander version au Master
        self._uart.send('V', '?')
        log.info("Demande version au Master...")

        if not self._version_event.wait(timeout=VERSION_REQUEST_TIMEOUT_S):
            log.error("Master injoignable — démarrage en mode dégradé")
            if self._display:
                self._display.error("MASTER_OFFLINE")
            return False

        master_version = self._master_version
        log.info(f"Version Master: {master_version}")

        if local_version == master_version:
            log.info("Versions identiques — démarrage normal")
            if self._display:
                self._display.ready(local_version)  # écran vert OPÉRATIONNEL 3s
            return True

        # Versions différentes → rsync
        log.warning(f"Version mismatch: local={local_version} master={master_version}")
        if self._display:
            self._display.syncing(master_version)

        success = self._trigger_rsync(master_version)
        if success:
            if self._display:
                self._display.ready(master_version)  # écran vert OPÉRATIONNEL 3s
            return True
        else:
            log.error("Sync échoué — démarrage en mode dégradé avec version locale")
            if self._display:
                self._display.error("SYNC_FAILED")
            return False

    def _on_version_received(self, value: str) -> None:
        """Callback UART: reçoit la version du Master."""
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
        Signale au Master qu'un rsync est nécessaire.
        Le Master redéclenche rsync + reboot.
        En pratique sur Pi Zero: on attend le reboot du Master.
        """
        for attempt in range(MAX_SYNC_RETRIES):
            log.info(f"Sync tentative {attempt + 1}/{MAX_SYNC_RETRIES}")
            # Demander re-sync au Master via UART
            self._uart.send('V', '?')
            self._version_event.clear()
            if not self._version_event.wait(timeout=VERSION_REQUEST_TIMEOUT_S):
                log.warning("Pas de réponse Master pour re-sync")
            else:
                local = self._read_local_version()
                if local == expected_version:
                    log.info(f"Sync réussi à la tentative {attempt + 1}")
                    return True

            if attempt < MAX_SYNC_RETRIES - 1:
                backoff = SYNC_RETRY_BACKOFF_S[attempt]
                log.info(f"Prochain retry dans {backoff}s")
                time.sleep(backoff)

        return False
