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
WiFi Watchdog — Slave Pi 4B.
Monitors connectivity to the Master hotspot (r2d2-master-hotspot).
Level 1 : up to 5 reconnection attempts to the hotspot.
Level 2 : fallback to home WiFi (netplan-wlan0-mywifi2).
"""

import logging
import subprocess
import threading
import time
import re

log = logging.getLogger(__name__)

# Parameters
PING_HOST           = "r2-master.local"
PING_RETRIES        = 3          # consecutive pings before declaring loss
PING_TIMEOUT_S      = 2          # timeout per ping
CHECK_INTERVAL_S    = 30         # normal check interval
L1_WAIT_S           = 15         # wait after nmcli connection up (Level 1)
L1_MAX_ATTEMPTS     = 5          # before switching to Level 2
L2_WAIT_S           = 20         # wait after home WiFi connection
HOME_CHECK_S        = 60         # check interval in HOME_FALLBACK state
AP_PROFILE          = "r2d2-master-hotspot"
HOME_PROFILE        = "netplan-wlan0-mywifi2"
IFACE               = "wlan0"

# Internal states
CONNECTED     = "CONNECTED"
SCANNING      = "SCANNING"
HOME_FALLBACK = "HOME_FALLBACK"


class WiFiWatchdog:
    def __init__(self, display) -> None:
        """
        display : DisplayDriver instance (already initialized).
        Can be None — display calls are silently ignored.
        """
        self._display  = display
        self._stop_evt = threading.Event()
        self._thread   = threading.Thread(
            target=self._run,
            name='wifi-watchdog',
            daemon=True,
        )

    def start(self) -> None:
        """Starts the monitoring thread."""
        log.info("WiFiWatchdog started")
        self._thread.start()

    def stop(self) -> None:
        """Clean stop signal — returns without waiting for the thread to finish."""
        self._stop_evt.set()

    # ------------------------------------------------------------------
    # Interne
    # ------------------------------------------------------------------

    def _run(self) -> None:
        state          = CONNECTED
        l1_attempt     = 0

        while not self._stop_evt.is_set():
            # ---- Delay based on current state ----
            wait = HOME_CHECK_S if state == HOME_FALLBACK else CHECK_INTERVAL_S
            if self._stop_evt.wait(wait):
                break  # stop requested

            ping_ok = self._ping_master()

            if state == CONNECTED:
                if not ping_ok:
                    log.warning("WiFiWatchdog: Master unreachable — Level 1 starting")
                    state      = SCANNING
                    l1_attempt = 0

            if state == SCANNING:
                if ping_ok:
                    log.info("WiFiWatchdog: Master reachable — CONNECTED")
                    state = CONNECTED
                    self._disp_net_ok()
                    self._stop_evt.wait(3)   # display "RECONNECTED" for 3s then return to OK screen
                    self._disp_operational()
                    continue

                l1_attempt += 1
                log.info(f"WiFiWatchdog: Level 1 attempt {l1_attempt}/{L1_MAX_ATTEMPTS}")
                self._disp_net_scanning(l1_attempt)

                # Disconnect + reconnect
                self._nmcli_disconnect()
                self._disp_net_ap(l1_attempt)
                self._nmcli_up(AP_PROFILE)

                # Wait then re-ping
                if self._stop_evt.wait(L1_WAIT_S):
                    break
                if self._ping_master():
                    log.info("WiFiWatchdog: Level 1 reconnexion OK")
                    state = CONNECTED
                    self._disp_net_ok()
                    self._stop_evt.wait(3)
                    self._disp_operational()
                    continue

                # Attempt failed
                if l1_attempt >= L1_MAX_ATTEMPTS:
                    log.warning("WiFiWatchdog: Level 1 exhausted — Level 2 (home fallback)")
                    state = HOME_FALLBACK
                    self._level2_connect()

            elif state == HOME_FALLBACK:
                if ping_ok:
                    log.info("WiFiWatchdog: Master back online — reconnecting to AP")
                    self._nmcli_up(AP_PROFILE)
                    if self._stop_evt.wait(L1_WAIT_S):
                        break
                    if self._ping_master():
                        state = CONNECTED
                        self._disp_net_ok()
                        self._stop_evt.wait(3)
                        self._disp_operational()
                    else:
                        log.warning("WiFiWatchdog: AP reconnect failed — staying in HOME_FALLBACK")
                        self._level2_connect()  # re-tenter home

    def _level2_connect(self) -> None:
        """Connects to home WiFi and displays the status."""
        self._disp_net_home_try()
        self._nmcli_up(HOME_PROFILE)
        if self._stop_evt.wait(L2_WAIT_S):
            return
        ip = self._get_wlan0_ip()
        if ip:
            log.info(f"WiFiWatchdog: HOME_FALLBACK active — IP {ip}")
            self._disp_net_home_ok(ip)
        else:
            log.warning("WiFiWatchdog: home WiFi connected but no IP assigned")

    # ------------------------------------------------------------------
    # Network helpers
    # ------------------------------------------------------------------

    def _ping_master(self) -> bool:
        """Returns True if at least one ping succeeds among PING_RETRIES attempts."""
        for _ in range(PING_RETRIES):
            if self._stop_evt.is_set():
                return False
            try:
                result = subprocess.run(
                    ['ping', '-c', '1', '-W', str(PING_TIMEOUT_S), PING_HOST],
                    capture_output=True,
                    timeout=PING_TIMEOUT_S + 1,
                )
                if result.returncode == 0:
                    return True
            except Exception:
                pass
        return False

    def _nmcli_disconnect(self) -> None:
        try:
            subprocess.run(
                ['nmcli', 'device', 'disconnect', IFACE],
                capture_output=True, timeout=10,
            )
        except Exception as e:
            log.warning(f"nmcli disconnect: {e}")

    def _nmcli_up(self, profile: str) -> None:
        try:
            subprocess.run(
                ['nmcli', 'connection', 'up', profile],
                capture_output=True, timeout=15,
            )
        except Exception as e:
            log.warning(f"nmcli connection up {profile}: {e}")

    def _get_wlan0_ip(self) -> str | None:
        """Returns the current wlan0 IP address, or None."""
        try:
            result = subprocess.run(
                ['ip', '-4', 'addr', 'show', IFACE],
                capture_output=True, text=True, timeout=5,
            )
            m = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', result.stdout)
            return m.group(1) if m else None
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Display helpers (silent if _display is None)
    # ------------------------------------------------------------------

    def _disp_net_scanning(self, attempt: int) -> None:
        if self._display:
            try:
                self._display.net_scanning(attempt)
            except Exception:
                pass

    def _disp_net_ap(self, attempt: int) -> None:
        if self._display:
            try:
                self._display.net_connecting_ap(attempt)
            except Exception:
                pass

    def _disp_net_home_try(self) -> None:
        if self._display:
            try:
                self._display.net_home_try()
            except Exception:
                pass

    def _disp_net_home_ok(self, ip: str) -> None:
        if self._display:
            try:
                self._display.net_home_ok(ip)
            except Exception:
                pass

    def _disp_net_ok(self) -> None:
        if self._display:
            try:
                self._display.net_ok()
            except Exception:
                pass

    def _disp_operational(self) -> None:
        """Returns the RP2040 screen to OPERATIONAL mode after a network event."""
        if self._display:
            try:
                self._display.ok()
            except Exception:
                pass
