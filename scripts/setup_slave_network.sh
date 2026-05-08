#!/bin/bash
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
# =============================================================================
# setup_slave_network.sh — R2-D2 Slave network configuration
# =============================================================================
#
# ⚠️  INSTALL THE MASTER FIRST (setup_master_network.sh).
#     This script needs the Master hotspot SSID and password.
#
# This script must be run ONCE on the R2-Slave.
#
# What it does:
#   1. Prompts for the R2-Master hotspot SSID and password
#   2. Replaces the home WiFi connection (wlan0) with the Master hotspot
#   3. Configures the hostname r2-slave
#   4. Enables avahi-daemon for r2-slave.local resolution
#
# End result:
#   wlan0  → R2-Master Hotspot  192.168.4.x  (DHCP assigned by Master)
#   (no wlan1 — the Slave does not need internet directly)
#
# Prerequisites:
#   - Raspberry Pi OS Bookworm 64-bit Lite (NetworkManager active)
#   - Slave connected to home WiFi via wlan0 (initial state)
#   - R2-Master configured and hotspot started (Master reboot done)
#   - Master hotspot SSID + password at hand
#
# Usage:
#   sudo bash /home/artoo/r2d2/scripts/setup_slave_network.sh
#
# =============================================================================

set -e

# Reopen stdin from the terminal if the script is run via pipe (curl | bash)
[ -t 0 ] || exec < /dev/tty

HOTSPOT_CON="r2d2-master-hotspot"

# Colors
RED='\033[0;31m'
GRN='\033[0;32m'
YEL='\033[1;33m'
BLU='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLU}[INFO]${NC}  $*"; }
ok()    { echo -e "${GRN}[ OK ]${NC}  $*"; }
warn()  { echo -e "${YEL}[WARN]${NC}  $*"; }
die()   { echo -e "${RED}[ERR ]${NC}  $*" >&2; exit 1; }

# =============================================================================
echo ""
echo -e "${BLU}========================================${NC}"
echo -e "${BLU}  R2-D2 Slave — Network configuration  ${NC}"
echo -e "${BLU}========================================${NC}"
echo ""
echo -e "  ${YEL}⚠  The R2-Master must be configured and rebooted before continuing.${NC}"
echo    "     (setup_master_network.sh must have been run on the Master)"
echo ""
read -r -p "  Is the Master ready and its hotspot active? [y/N] " READY
[[ "$READY" =~ ^[Oo] ]] || die "Configure the Master first, then re-run this script."

# --- Root check ---
[[ $EUID -eq 0 ]] || die "This script must be run with sudo"

# --- NetworkManager check ---
if ! systemctl is-active --quiet NetworkManager; then
    die "NetworkManager is not active. Bookworm required."
fi
ok "NetworkManager active"

# =============================================================================
# STEP 1 — Enter Master hotspot credentials
# =============================================================================
echo ""
echo -e "${BLU}--- R2-Master hotspot credentials ---${NC}"
echo ""
echo    "  This information can be found at the end of setup_master_network.sh"
echo    "  or in master/config/local.cfg [hotspot] on the Master."
echo ""

HOTSPOT_SSID=""
HOTSPOT_PASS=""

read -r -p "  Master hotspot SSID [AstromechOS]: " INPUT
HOTSPOT_SSID="${INPUT:-AstromechOS}"

while true; do
    read -r -s -p "  Hotspot password                  : " HOTSPOT_PASS
    echo ""
    if [[ -z "$HOTSPOT_PASS" ]]; then
        warn "Empty password — try again (default: r2d2droid if unchanged)"
        read -r -s -p "  Hotspot password                  : " HOTSPOT_PASS
        echo ""
        [[ -n "$HOTSPOT_PASS" ]] || HOTSPOT_PASS="r2d2droid"
    fi
    break
done

echo ""
ok "Target hotspot: SSID='${HOTSPOT_SSID}'"

# =============================================================================
# STEP 2 — Delete old hotspot connection if it already exists
# =============================================================================
echo ""
info "Step 2 — Cleaning up old connections..."

if nmcli connection show "$HOTSPOT_CON" &>/dev/null; then
    nmcli connection delete "$HOTSPOT_CON"
    info "Old connection '$HOTSPOT_CON' deleted"
fi

# =============================================================================
# STEP 3 — Configure wlan0 to connect to the Master hotspot
# =============================================================================
echo ""
info "Step 3 — Configuring wlan0 → Master hotspot '${HOTSPOT_SSID}'..."

nmcli connection add \
    type wifi \
    ifname wlan0 \
    con-name "$HOTSPOT_CON" \
    ssid "$HOTSPOT_SSID" \
    wifi-sec.key-mgmt wpa-psk \
    wifi-sec.psk "$HOTSPOT_PASS" \
    connection.autoconnect yes \
    connection.autoconnect-priority 100

ok "Connection '${HOTSPOT_CON}' created"

# Lower the priority of other WiFi connections on wlan0
# so the Master hotspot is always preferred
for CON in $(nmcli -g NAME connection show | grep -v "$HOTSPOT_CON"); do
    TYPE=$(nmcli -g connection.type connection show "$CON" 2>/dev/null || true)
    if [[ "$TYPE" == "802-11-wireless" ]]; then
        nmcli connection modify "$CON" connection.autoconnect-priority 1 2>/dev/null || true
        info "Priority lowered for '$CON'"
    fi
done

# =============================================================================
# STEP 4 — Check that the hotspot is visible (connection after reboot)
# =============================================================================
echo ""
info "Step 4 — Checking hotspot visibility..."

# Scan to verify the network is visible — do NOT try to connect now
# because nmcli connection up breaks the SSH session (immediate WiFi switch)
VISIBLE=$(nmcli device wifi list ifname wlan0 2>/dev/null | grep "$HOTSPOT_SSID" || true)

if [[ -n "$VISIBLE" ]]; then
    ok "Hotspot '${HOTSPOT_SSID}' detected — automatic connection on reboot"
else
    warn "Hotspot '${HOTSPOT_SSID}' not visible now — check that the Master is powered on"
    warn "Connection will activate automatically on reboot if the Master is running"
fi
info "Connection deferred to reboot (avoids SSH disconnection)"

# =============================================================================
# STEP 5 — Hostname + avahi
# =============================================================================
echo ""
info "Step 5 — Hostname and .local resolution..."

# Check/fix the hostname
CURRENT_HOSTNAME=$(hostname)
if [[ "$CURRENT_HOSTNAME" != "r2-slave" ]]; then
    hostnamectl set-hostname r2-slave
    # Update /etc/hosts
    sed -i "s/127.0.1.1.*/127.0.1.1\tr2-slave/" /etc/hosts
    ok "Hostname configured: r2-slave"
else
    ok "Hostname already correct: r2-slave"
fi

if ! command -v avahi-daemon &>/dev/null; then
    apt-get install -y avahi-daemon -qq
fi
systemctl enable --now avahi-daemon
ok "avahi-daemon active (r2-slave.local)"

# =============================================================================
# SUMMARY
# =============================================================================
echo ""
echo -e "${GRN}========================================${NC}"
echo -e "${GRN}  Slave network configured ✓            ${NC}"
echo -e "${GRN}========================================${NC}"
echo ""
echo -e "  ${BLU}wlan0${NC} → R2-Master Hotspot (on reboot)"
echo    "         SSID     : ${HOTSPOT_SSID}"
echo    "         IP       : 192.168.4.x (DHCP from Master)"
echo ""
echo -e "  ${BLU}Hostname${NC}: r2-slave  →  r2-slave.local"
echo ""
echo -e "  ${YEL}Next steps:${NC}"
echo    "    1. sudo reboot"
echo    "    2. From the Master, verify:"
echo    "       ping r2-slave.local"
echo    "       ssh artoo@r2-slave.local"
echo    "    3. Continue installation: HOWTO.md Step 3"
echo ""
