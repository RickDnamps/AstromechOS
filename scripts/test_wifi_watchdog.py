#!/usr/bin/env python3
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
# -*- coding: utf-8 -*-
"""
Test WiFi Watchdog — validation non-destructive.
Exécuté depuis le Master via SSH sur le Slave :
  ssh artoo@r2-slave.local "python3 /home/artoo/r2d2/scripts/test_wifi_watchdog.py"

Étapes :
  1. Vérifie que le Slave est connecté au hotspot Master (pré-condition)
  2. Simule une coupure wlan0 — observe que le watchdog détecte et réagit
  3. Rétablit la connexion AP — vérifie la reconnexion Level 1
  4. Rapport PASS/FAIL
"""

import subprocess
import sys
import time

# --- Forcer UTF-8 ---
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

TIMEOUT_DETECTION_S = 45   # 30s cycle watchdog + 15s marge
TIMEOUT_RECONNECT_S = 30   # après nmcli connection up
AP_PROFILE          = "r2d2-master-hotspot"
SLAVE_CONN_CHECK    = "r2d2-master-hotspot"


def _run(cmd, timeout=10):
    """Exécute une commande shell, retourne (returncode, stdout, stderr)."""
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def check_precondition():
    """Étape 1 : vérifier que wlan0 est connecté au hotspot Master."""
    print("\n=== Étape 1 — Pré-condition ===")
    rc, out, _ = _run("nmcli -t -f NAME,DEVICE,STATE connection show --active")
    lines = [l for l in out.splitlines() if SLAVE_CONN_CHECK in l and 'wlan0' in l]
    if lines:
        print(f"  ✓ Slave connecté au hotspot Master : {lines[0]}")
        return True
    print(f"  ✗ Slave NON connecté à '{SLAVE_CONN_CHECK}'")
    print(f"    Connexions actives : {out}")
    return False


def watch_journald_log(stop_at_keyword, timeout_s):
    """
    Surveille journald pour détecter les logs du WiFiWatchdog.
    Retourne True si le keyword est trouvé dans les logs dans le délai.
    """
    start = time.monotonic()
    print(f"  → Observation logs ({timeout_s}s max, cherche : '{stop_at_keyword}')...", flush=True)
    while time.monotonic() - start < timeout_s:
        rc, out, _ = _run(
            "journalctl -u r2d2-slave.service --no-pager -n 30 --since '3 minutes ago' 2>/dev/null",
            timeout=5
        )
        if stop_at_keyword.lower() in out.lower():
            elapsed = time.monotonic() - start
            print(f"\n  ✓ Trouvé en {elapsed:.0f}s")
            return True
        time.sleep(2)
        print(".", end="", flush=True)
    print()
    return False


def simulate_disconnect():
    """Étape 2 : déconnecter wlan0 pour forcer le watchdog."""
    print("\n=== Étape 2 — Simulation coupure wlan0 ===")
    rc, out, err = _run("nmcli device disconnect wlan0")
    if rc == 0:
        print("  ✓ wlan0 déconnecté")
        return True
    print(f"  ✗ Erreur nmcli disconnect (rc={rc}): {err}")
    return False


def wait_for_watchdog_reaction():
    """Attend que le WiFiWatchdog détecte la coupure (Level 1 attempt 1)."""
    found = watch_journald_log("Level 1", TIMEOUT_DETECTION_S)
    if not found:
        print("  ✗ Pas de réaction Level 1 dans le délai")
    return found


def restore_connection():
    """Étape 3 : forcer la reconnexion AP."""
    print("\n=== Étape 3 — Reconnexion AP ===")
    rc, out, err = _run(f"nmcli connection up {AP_PROFILE}", timeout=20)
    if rc == 0:
        print(f"  ✓ Connexion '{AP_PROFILE}' rétablie")
    else:
        print(f"  ⚠ nmcli connection up rc={rc}: {err}")

    # Vérifier ping Master
    print(f"  → Vérification ping r2-master.local ({TIMEOUT_RECONNECT_S}s)...")
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

    # Étape 1
    results['precondition'] = check_precondition()
    if not results['precondition']:
        print("\n⚠ Pré-condition non remplie — test annulé")
        sys.exit(2)

    # Étape 2
    results['disconnect'] = simulate_disconnect()
    if results['disconnect']:
        results['watchdog_reacted'] = wait_for_watchdog_reaction()
    else:
        results['watchdog_reacted'] = False

    # Étape 3
    results['reconnected'] = restore_connection()

    # Rapport
    print("\n=== Rapport ===")
    all_pass = all(results.values())
    for k, v in results.items():
        icon = "✓" if v else "✗"
        print(f"  {icon} {k}: {'PASS' if v else 'FAIL'}")

    if all_pass:
        print("\n✓ PASS — WiFi Watchdog fonctionnel")
        sys.exit(0)
    else:
        print("\n✗ FAIL — Voir détails ci-dessus")
        sys.exit(1)


if __name__ == '__main__':
    main()
