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
# setup_slave_network.sh — AstromechOS Slave network configuration
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
#   3. Configures the hostname astromech-slave
#   4. Enables avahi-daemon for astromech-slave.local resolution
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
#   sudo bash /home/artoo/astromechos/scripts/setup_slave_network.sh
#
# =============================================================================

set -e

# Reopen stdin from the terminal if the script is run via pipe (curl | bash).
# `[ -r /dev/tty ]` is not enough on Git Bash / restricted shells (the path can
# exist but raise EIO on open). The reliable probe is a group-redirect: the
# `:` no-op forces bash to actually open /dev/tty; if that fails the error is
# captured by 2>/dev/null inside the group and the `&&` short-circuits before
# we ever reach the real `exec`. Firstboot (systemd, no tty) falls through.
if [ ! -t 0 ] && { : < /dev/tty; } 2>/dev/null; then
    exec < /dev/tty
fi

HOTSPOT_CON="astromech-master-hotspot"

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

# ─── CLI arg parsing (non-interactive mode for firstboot orchestration) ──
# When --non-interactive is set, prompts are skipped and SSID/PSK come from
# --ssid / --psk flags. firstboot_setup.sh passes the bootstrap SSID/PSK
# pre-baked by the Imager into /boot/astromech_init.cfg [hotspot].
NON_INTERACTIVE=""
SSID_FLAG=""
PSK_FLAG=""
while [ $# -gt 0 ]; do
    case "$1" in
        --non-interactive) NON_INTERACTIVE=1 ;;
        --ssid)        SSID_FLAG="${2:-}"; shift ;;
        --psk)         PSK_FLAG="${2:-}"; shift ;;
        -h|--help)
            echo "Usage: $0 [--non-interactive --ssid X --psk Y]"
            exit 0 ;;
        *) die "unknown flag: $1" ;;
    esac
    shift
done
if [ -n "$NON_INTERACTIVE" ]; then
    [ -n "$SSID_FLAG" ] || die "--non-interactive requires --ssid"
    [ -n "$PSK_FLAG" ]  || die "--non-interactive requires --psk"
    [ "${#PSK_FLAG}" -ge 8 ] || die "--psk too short (WPA requires >=8 chars)"
fi

# =============================================================================
echo ""
echo -e "${BLU}========================================${NC}"
echo -e "${BLU}  AstromechOS Slave — Network configuration${NC}"
echo -e "${BLU}========================================${NC}"
echo ""
if [ -n "$NON_INTERACTIVE" ]; then
    info "Non-interactive mode (firstboot): target SSID='$SSID_FLAG'"
else
    echo -e "  ${YEL}⚠  The R2-Master must be configured and rebooted before continuing.${NC}"
    echo    "     (setup_master_network.sh must have been run on the Master)"
    echo ""
    read -r -p "  Is the Master ready and its hotspot active? [y/N] " READY
    [[ "$READY" =~ ^[Oo] ]] || die "Configure the Master first, then re-run this script."
fi

# --- Root check ---
[[ $EUID -eq 0 ]] || die "This script must be run with sudo"

# --- NetworkManager check ---
if ! systemctl is-active --quiet NetworkManager; then
    die "NetworkManager is not active. Bookworm required."
fi
ok "NetworkManager active"

# --- WiFi regulatory domain (REQUIRED so the Slave can associate on 5 GHz) ---
# Must match the Master's country, else the kernel disables 5 GHz channels and
# the Slave can't join a 5 GHz hotspot. Set + persist (systemd oneshot, before
# NetworkManager) so it survives a fresh SD flash / reboot.
REG_COUNTRY="${REG_COUNTRY:-CA}"
setup_regdomain() {
    info "Setting WiFi regulatory domain → ${REG_COUNTRY} (enables 5 GHz)..."
    raspi-config nonint do_wifi_country "$REG_COUNTRY" 2>/dev/null || true
    iw reg set "$REG_COUNTRY" 2>/dev/null || true
    cat > /etc/systemd/system/astromech-regdom.service <<UNIT
[Unit]
Description=AstromechOS - set WiFi regulatory domain (enables 5 GHz)
DefaultDependencies=no
Before=NetworkManager.service wpa_supplicant.service network-pre.target
Wants=network-pre.target
[Service]
Type=oneshot
ExecStart=/bin/sh -c 'iw reg set ${REG_COUNTRY}'
RemainAfterExit=yes
[Install]
WantedBy=multi-user.target
UNIT
    systemctl daemon-reload 2>/dev/null || true
    systemctl enable astromech-regdom.service 2>/dev/null || true
    systemctl start  astromech-regdom.service 2>/dev/null || true
    ok "Regulatory domain '${REG_COUNTRY}' applied + persisted (astromech-regdom.service)"
}
setup_regdomain

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

if [ -n "$NON_INTERACTIVE" ]; then
    HOTSPOT_SSID="$SSID_FLAG"
    HOTSPOT_PASS="$PSK_FLAG"
    info "Non-interactive: SSID='$HOTSPOT_SSID' (PSK from --psk)"
else
    # Each Master now has a per-robot SSID (Astromech_Control_XXXX). Enter the EXACT
    # SSID shown during the Master network setup (or in master/config/local.cfg
    # [hotspot] ssid). The default is only the base name in case it was overridden.
    read -r -p "  Master hotspot SSID [Astromech_Control]: " INPUT
    HOTSPOT_SSID="${INPUT:-Astromech_Control}"

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
fi

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
if [[ "$CURRENT_HOSTNAME" != "astromech-slave" ]]; then
    hostnamectl set-hostname astromech-slave
    # Update /etc/hosts
    sed -i "s/127.0.1.1.*/127.0.1.1\tastromech-slave/" /etc/hosts
    ok "Hostname configured: astromech-slave"
else
    ok "Hostname already correct: astromech-slave"
fi

if ! command -v avahi-daemon &>/dev/null; then
    apt-get install -y avahi-daemon -qq
fi
systemctl enable --now avahi-daemon
ok "avahi-daemon active (astromech-slave.local)"

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
echo -e "  ${BLU}Hostname${NC}: astromech-slave  →  astromech-slave.local"
echo ""
echo -e "  ${YEL}Next steps:${NC}"
echo    "    1. sudo reboot"
echo    "    2. From the Master, verify:"
echo    "       ping astromech-slave.local"
echo    "       ssh ${USER:-artoo}@astromech-slave.local"
echo    "    3. Continue installation: HOWTO.md Step 3"
echo ""
