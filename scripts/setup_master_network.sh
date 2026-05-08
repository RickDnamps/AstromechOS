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
# setup_master_network.sh — AstromechOS Master network configuration
# =============================================================================
#
# ⚠️  INSTALL THE MASTER FIRST — before the Slave.
#     The Slave needs the Master hotspot credentials to configure itself.
#
# This script must be run ONCE on the R2-Master.
#
# What it does:
#   1. Reads the home WiFi credentials already configured on wlan0
#   2. Prompts for the R2-D2 hotspot SSID/password (customizable)
#   3. Saves everything to local.cfg (survives git pulls)
#   4. Configures wlan1 (USB dongle) to connect to the home WiFi
#   5. Converts wlan0 into an access point (192.168.4.1)
#
# End result:
#   wlan0  → R2-D2 Hotspot             192.168.4.1  (Slave + remote control)
#   wlan1  → Home WiFi                 DHCP         (git pull / GitHub)
#
# Prerequisites:
#   - Raspberry Pi OS Bookworm 64-bit Lite (NetworkManager active)
#   - Pi connected to home WiFi via wlan0 (configured via Imager)
#   - WiFi USB dongle plugged in (will be wlan1) OR plug in later
#
# Usage:
#   sudo bash /home/artoo/astromechos/scripts/setup_master_network.sh
#
# Note the hotspot SSID and password — you will need them
# to configure the Slave with setup_slave_network.sh.
#
# =============================================================================

set -e

REPO_PATH="$(cd "$(dirname "$0")/.." && pwd)"
LOCAL_CFG="${REPO_PATH}/master/config/local.cfg"
LOCAL_CFG_EXAMPLE="${REPO_PATH}/master/config/local.cfg.example"

# Default hotspot values (can be changed interactively)
HOTSPOT_SSID="AstromechOS"
HOTSPOT_PASS="r2d2droid"
HOTSPOT_IP="192.168.4.1/24"
HOTSPOT_CON="r2d2-hotspot"
INTERNET_CON="r2d2-internet"

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
echo -e "${BLU}  AstromechOS Master — Network configuration${NC}"
echo -e "${BLU}========================================${NC}"
echo ""

# --- Root check ---
[[ $EUID -eq 0 ]] || die "This script must be run with sudo"

# --- NetworkManager check ---
if ! systemctl is-active --quiet NetworkManager; then
    die "NetworkManager is not active. Bookworm required.\n    sudo systemctl enable --now NetworkManager"
fi
ok "NetworkManager active"

# --- Repo check ---
[[ -d "$REPO_PATH" ]] || die "Repo not found: $REPO_PATH\n    Clone first: git clone ... $REPO_PATH"

# =============================================================================
# STEP 1 — Retrieve home WiFi credentials from wlan0
# =============================================================================
echo ""
info "Step 1 — Reading home WiFi credentials (current wlan0)..."

HOME_SSID=""
HOME_PASS=""

# Find the active connection name on wlan0
WLAN0_CON=$(nmcli -g GENERAL.CONNECTION device show wlan0 2>/dev/null | tr -d ' ')

if [[ -n "$WLAN0_CON" && "$WLAN0_CON" != "--" ]]; then
    info "Active connection on wlan0: '$WLAN0_CON'"

    # Extract SSID
    HOME_SSID=$(nmcli -g 802-11-wireless.ssid connection show "$WLAN0_CON" 2>/dev/null | tr -d ' ')

    # Extract password (requires sudo, already root here)
    HOME_PASS=$(nmcli -s -g 802-11-wireless-security.psk connection show "$WLAN0_CON" 2>/dev/null | tr -d ' ')

    if [[ -n "$HOME_SSID" ]]; then
        ok "SSID detected: '$HOME_SSID'"
    fi
    if [[ -n "$HOME_PASS" ]]; then
        ok "Password retrieved (masked)"
    else
        warn "Password not found automatically (open network or unknown format)"
    fi
else
    warn "No active connection on wlan0"
fi

# --- Ask for confirmation or manual entry ---
echo ""
if [[ -n "$HOME_SSID" ]]; then
    read -r -p "Use WiFi '${HOME_SSID}' for wlan1 (internet)? [Y/n] " CONFIRM
    if [[ "$CONFIRM" =~ ^[Nn] ]]; then
        HOME_SSID=""
        HOME_PASS=""
    fi
fi

if [[ -z "$HOME_SSID" ]]; then
    echo ""
    info "Manual entry of home WiFi credentials:"
    read -r -p "  SSID (WiFi network name): " HOME_SSID
    [[ -n "$HOME_SSID" ]] || die "Empty SSID — aborting"
    read -r -s -p "  WiFi password           : " HOME_PASS
    echo ""
fi

# =============================================================================
# STEP 1b — Configure the R2-D2 hotspot (SSID + password)
# =============================================================================
echo ""
echo -e "${BLU}--- R2-D2 Hotspot (access point for the Slave and remote control) ---${NC}"
echo ""
echo    "  The R2-Master will create a WiFi network that the Slave will connect to."
echo    "  You can customize the name and password, or keep the defaults."
echo ""
read -r -p "  Hotspot SSID     [${HOTSPOT_SSID}]: " INPUT
[[ -n "$INPUT" ]] && HOTSPOT_SSID="$INPUT"

while true; do
    read -r -s -p "  Hotspot password [${HOTSPOT_PASS}]: " INPUT
    echo ""
    if [[ -z "$INPUT" ]]; then
        break   # keep default
    fi
    if [[ ${#INPUT} -lt 8 ]]; then
        warn "WPA password must be at least 8 characters — try again"
    else
        HOTSPOT_PASS="$INPUT"
        break
    fi
done

echo ""
ok "Hotspot configured: SSID='${HOTSPOT_SSID}'  (password saved)"
echo ""
echo -e "  ${YEL}⚠  Note these details — you will need them for the Slave:${NC}"
echo    "     SSID     : ${HOTSPOT_SSID}"
echo    "     Password : ${HOTSPOT_PASS}"
echo ""

# =============================================================================
# STEP 2 — Save to local.cfg
# =============================================================================
echo ""
info "Step 2 — Saving to local.cfg..."

# Create local.cfg from the example if it does not exist yet
if [[ ! -f "$LOCAL_CFG" ]]; then
    if [[ -f "$LOCAL_CFG_EXAMPLE" ]]; then
        cp "$LOCAL_CFG_EXAMPLE" "$LOCAL_CFG"
        chown artoo:artoo "$LOCAL_CFG"
        info "local.cfg created from example"
    else
        die "local.cfg.example not found: $LOCAL_CFG_EXAMPLE"
    fi
fi

# Helper to write/update a key in a .cfg section
cfg_set() {
    local file="$1" section="$2" key="$3" value="$4"
    # Check if the section exists
    if grep -q "^\[${section}\]" "$file"; then
        # Update or add the key in the section
        if grep -q "^${key}\s*=" "$file"; then
            sed -i "s|^${key}\s*=.*|${key} = ${value}|" "$file"
        else
            sed -i "/^\[${section}\]/a ${key} = ${value}" "$file"
        fi
    else
        # Add the entire section
        echo "" >> "$file"
        echo "[${section}]" >> "$file"
        echo "${key} = ${value}" >> "$file"
    fi
}

cfg_set "$LOCAL_CFG" "home_wifi" "ssid"     "$HOME_SSID"
cfg_set "$LOCAL_CFG" "home_wifi" "password" "$HOME_PASS"
cfg_set "$LOCAL_CFG" "hotspot"   "ssid"     "$HOTSPOT_SSID"
cfg_set "$LOCAL_CFG" "hotspot"   "password" "$HOTSPOT_PASS"
chown artoo:artoo "$LOCAL_CFG"

ok "Home WiFi credentials saved to local.cfg [home_wifi]"
ok "Hotspot credentials saved to local.cfg [hotspot]"

# =============================================================================
# STEP 3 — Configure wlan1 (USB dongle) for home WiFi
# =============================================================================
echo ""
info "Step 3 — Configuring wlan1 → home WiFi '$HOME_SSID'..."

# Delete the old r2d2-internet connection if it exists
if nmcli connection show "$INTERNET_CON" &>/dev/null; then
    nmcli connection delete "$INTERNET_CON"
    info "Old connection '$INTERNET_CON' deleted"
fi

# Create the wlan1 connection
if [[ -n "$HOME_PASS" ]]; then
    nmcli connection add \
        type wifi \
        ifname wlan1 \
        con-name "$INTERNET_CON" \
        ssid "$HOME_SSID" \
        wifi-sec.key-mgmt wpa-psk \
        wifi-sec.psk "$HOME_PASS" \
        connection.autoconnect yes \
        connection.autoconnect-priority 10
else
    # Open network
    nmcli connection add \
        type wifi \
        ifname wlan1 \
        con-name "$INTERNET_CON" \
        ssid "$HOME_SSID" \
        connection.autoconnect yes \
        connection.autoconnect-priority 10
fi

ok "Connection '$INTERNET_CON' created for wlan1"

# Try to bring it up if wlan1 already exists
if ip link show wlan1 &>/dev/null; then
    info "wlan1 detected — connecting..."
    nmcli connection up "$INTERNET_CON" && ok "wlan1 connected to '$HOME_SSID'" \
        || warn "wlan1 connection failed — check that the WiFi USB dongle is plugged in"
else
    warn "wlan1 not detected now — the connection will activate automatically when the USB dongle is plugged in"
fi

# =============================================================================
# STEP 4 — Remove the wlan0 home connection and create the hotspot
# =============================================================================
echo ""
info "Step 4 — Converting wlan0 to hotspot '$HOTSPOT_SSID'..."

# Delete the old hotspot connection if it exists
if nmcli connection show "$HOTSPOT_CON" &>/dev/null; then
    nmcli connection delete "$HOTSPOT_CON"
    info "Old hotspot deleted"
fi

# Remove the home WiFi connection from wlan0 to free the interface
if [[ -n "$WLAN0_CON" && "$WLAN0_CON" != "--" ]]; then
    # Deactivate first, then redirect so it no longer takes priority
    # Do NOT delete — NetworkManager will be redirected via autoconnect
    nmcli connection modify "$WLAN0_CON" connection.interface-name wlan1 2>/dev/null || true
    info "Connection '$WLAN0_CON' redirected to wlan1"
fi

# Create the hotspot on wlan0
nmcli connection add \
    type wifi \
    ifname wlan0 \
    con-name "$HOTSPOT_CON" \
    ssid "$HOTSPOT_SSID" \
    mode ap \
    wifi-sec.key-mgmt wpa-psk \
    wifi-sec.psk "$HOTSPOT_PASS" \
    ipv4.method shared \
    ipv4.addresses "$HOTSPOT_IP" \
    ipv6.method disabled \
    connection.autoconnect yes \
    connection.autoconnect-priority 100

ok "Hotspot '$HOTSPOT_CON' created on wlan0"

# Activate the hotspot
nmcli connection up "$HOTSPOT_CON" && ok "Hotspot started on wlan0" \
    || warn "Hotspot startup deferred to reboot"

# =============================================================================
# STEP 5 — Avahi for .local resolution
# =============================================================================
echo ""
info "Step 5 — Checking avahi-daemon (.local DNS)..."

if ! command -v avahi-daemon &>/dev/null; then
    apt-get install -y avahi-daemon -qq
fi
systemctl enable --now avahi-daemon
ok "avahi-daemon active (r2-master.local / r2-slave.local)"

# =============================================================================
# SUMMARY
# =============================================================================
echo ""
echo -e "${GRN}========================================${NC}"
echo -e "${GRN}  Master network configured ✓           ${NC}"
echo -e "${GRN}========================================${NC}"
echo ""
echo -e "  ${BLU}wlan0${NC} → R2-D2 Hotspot (access point)"
echo    "         SSID     : ${HOTSPOT_SSID}"
echo    "         Password : ${HOTSPOT_PASS}"
echo    "         Fixed IP : 192.168.4.1"
echo ""
echo -e "  ${BLU}wlan1${NC} → Home WiFi / internet (USB dongle)"
echo    "         SSID     : ${HOME_SSID}"
echo    "         (automatic connection when dongle is plugged in)"
echo ""
echo -e "  ${BLU}Saved to${NC}: ${LOCAL_CFG}"
echo    "    [home_wifi]  ssid / password"
echo    "    [hotspot]    ssid / password"
echo ""
echo -e "  ${YEL}══════════════════════════════════════${NC}"
echo -e "  ${YEL}  INFORMATION FOR SLAVE SETUP:         ${NC}"
echo -e "  ${YEL}══════════════════════════════════════${NC}"
echo    ""
echo    "  On the R2-Slave, you will need:"
echo -e "  ${GRN}  Hotspot SSID     : ${HOTSPOT_SSID}${NC}"
echo -e "  ${GRN}  Hotspot Password : ${HOTSPOT_PASS}${NC}"
echo    ""
echo    "  Slave command (after Master reboot):"
echo    "  sudo bash $REPO_PATH/scripts/setup_slave_network.sh"
echo    ""
echo -e "  ${YEL}Next steps:${NC}"
echo    "    1. Plug the WiFi USB dongle into the Master (if not already done)"
echo    "    2. sudo reboot"
echo    "    3. Configure the Slave: setup_slave_network.sh"
echo ""
