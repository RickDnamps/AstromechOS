#!/usr/bin/env python3
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
# -*- coding: utf-8 -*-
"""
Test WiFi Watchdog — non-destructive validation.
Run from the Master via SSH on the Slave:
  ssh artoo@r2-slave.local "python3 /home/artoo/astromechos/scripts/test_wifi_watchdog.py"

Steps:
  1. Verify that the Slave is connected to the Master hotspot (pre-condition)
  2. Simulate a wlan0 disconnect — observe that the watchdog detects and reacts
  3. Restore the AP connection — verify Level 1 reconnection
  4. PASS/FAIL report
"""

import subprocess
import sys
import time

# --- Forcer UTF-8 ---
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

TIMEOUT_DETECTION_S = 45   # 30s cycle watchdog + 15s marge
TIMEOUT_RECONNECT_S = 30   # after nmcli connection up
AP_PROFILE          = "r2d2-master-hotspot"
SLAVE_CONN_CHECK    = "r2d2-master-hotspot"


def _run(cmd, timeout=10):
    """Run a shell command, return (returncode, stdout, stderr)."""
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def check_precondition():
    """Step 1: verify that wlan0 is connected to the Master hotspot."""
    print("\n=== Step 1 — Pre-condition ===")
    rc, out, _ = _run("nmcli -t -f NAME,DEVICE,STATE connection show --active")
    lines = [l for l in out.splitlines() if SLAVE_CONN_CHECK in l and 'wlan0' in l]
    if lines:
        print(f"  ✓ Slave connected to Master hotspot: {lines[0]}")
        return True
    print(f"  ✗ Slave NOT connected to '{SLAVE_CONN_CHECK}'")
    print(f"    Connexions actives : {out}")
    return False


def watch_journald_log(stop_at_keyword, timeout_s):
    """
    Monitor journald to detect WiFiWatchdog log entries.
    Returns True if the keyword is found in logs within the timeout.
    """
    start = time.monotonic()
    print(f"  → Observation logs ({timeout_s}s max, cherche : '{stop_at_keyword}')...", flush=True)
    while time.monotonic() - start < timeout_s:
        rc, out, _ = _run(
            "journalctl -u astromech-slave.service --no-pager -n 30 --since '3 minutes ago' 2>/dev/null",
            timeout=5
        )
        if stop_at_keyword.lower() in out.lower():
            elapsed = time.monotonic() - start
            print(f"\n  ✓ Found after {elapsed:.0f}s")
            return True
        time.sleep(2)
        print(".", end="", flush=True)
    print()
    return False


def simulate_disconnect():
    """Step 2: disconnect wlan0 to force the watchdog."""
    print("\n=== Step 2 — Simulating wlan0 disconnect ===")
    rc, out, err = _run("nmcli device disconnect wlan0")
    if rc == 0:
        print("  ✓ wlan0 disconnected")
        return True
    print(f"  ✗ Erreur nmcli disconnect (rc={rc}): {err}")
    return False


def wait_for_watchdog_reaction():
    """Wait for the WiFiWatchdog to detect the disconnect (Level 1 attempt 1)."""
    found = watch_journald_log("Level 1", TIMEOUT_DETECTION_S)
    if not found:
        print("  ✗ No Level 1 reaction within the timeout")
    return found


def restore_connection():
    """Step 3: force AP reconnection."""
    print("\n=== Step 3 — AP Reconnection ===")
    rc, out, err = _run(f"nmcli connection up {AP_PROFILE}", timeout=20)
    if rc == 0:
        print(f"  ✓ Connection '{AP_PROFILE}' restored")
    else:
        print(f"  ⚠ nmcli connection up rc={rc}: {err}")

    # Verify ping to Master
    print(f"  → Checking ping r2-master.local ({TIMEOUT_RECONNECT_S}s)...")
    start = time.monotonic()
    while time.monotonic() - start < TIMEOUT_RECONNECT_S:
        rc, _, _ = _run("ping -c 1 -W 2 r2-master.local", timeout=4)
        if rc == 0:
            print("  ✓ Ping r2-master.local : OK")
            return True
        time.sleep(3)
    print("  ✗ Ping r2-master.local : TIMEOUT")
    return False


def main():
    print("=" * 60)
    print("  Test WiFi Watchdog — validation non-destructive")
    print("=" * 60)

    results = {}

    # Step 1
    results['precondition'] = check_precondition()
    if not results['precondition']:
        print("\n⚠ Pre-condition not met — test aborted")
        sys.exit(2)

    # Step 2
    results['disconnect'] = simulate_disconnect()
    if results['disconnect']:
        results['watchdog_reacted'] = wait_for_watchdog_reaction()
    else:
        results['watchdog_reacted'] = False

    # Step 3
    results['reconnected'] = restore_connection()

    # Rapport
    print("\n=== Rapport ===")
    all_pass = all(results.values())
    for k, v in results.items():
        icon = "✓" if v else "✗"
        print(f"  {icon} {k}: {'PASS' if v else 'FAIL'}")

    if all_pass:
        print("\n✓ PASS — WiFi Watchdog functional")
        sys.exit(0)
    else:
        print("\n✗ FAIL — See details above")
        sys.exit(1)


if __name__ == '__main__':
    main()
