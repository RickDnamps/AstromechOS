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
# setup_master.sh — Full R2-Master installation (single command)
# =============================================================================
#
# This script automates all Master installation steps:
#   1. System update + packages
#   2. Git repo clone
#   3. UART fix (disable-bt to free ttyAMA0)
#   4. Enable UART + I2C via raspi-config
#   5. Python dependencies installation
#   6. Copy local.cfg
#   7. Network configuration (wlan0 hotspot + wlan1 internet)
#   8. systemd services installation
#   → final reboot
#
# Usage (on the R2-Master, connected to home WiFi):
#   curl -fsSL https://raw.githubusercontent.com/RickDnamps/AstromechOS/main/scripts/setup_master.sh | sudo bash
#
# Or if the repo is already cloned:
#   sudo bash /home/artoo/astromechos/scripts/setup_master.sh
#
# =============================================================================

set -e

REPO_URL="https://github.com/RickDnamps/AstromechOS.git"
REPO_PATH="$(cd "$(dirname "$0")/.." && pwd)"
# USER + HOME_DIR are set by capture_user below (after err()/info() helpers
# are defined and lib_config.sh is sourced).

# Colors
RED='\033[0;31m'
GRN='\033[0;32m'
YEL='\033[1;33m'
BLU='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLU}[INFO]${NC}  $*"; }
ok()    { echo -e "${GRN}[ OK ]${NC}  $*"; }
warn()  { echo -e "${YEL}[WARN]${NC}  $*"; }
err()   { echo -e "${RED}[ERR ]${NC}  $*"; exit 1; }

# Check that we are running as root
[ "$EUID" -eq 0 ] || err "Run with sudo: sudo bash $0"

# Check that we are on the Master (not the Slave)
HOSTNAME=$(hostname)
if [ "$HOSTNAME" = "astromech-slave" ]; then
    err "This script must be run on the R2-MASTER, not on the Slave! (hostname: $HOSTNAME)"
fi

# Capture the install target user — $SUDO_USER (run with sudo from a regular
# login), /boot/astromech_init.cfg [system] user (future Imager bootstrap),
# interactive prompt, or legacy 'artoo'. Sets TARGET_USER + TARGET_HOME and
# refuses root + non-existent users.
# shellcheck source=lib_config.sh
. "$REPO_PATH/scripts/lib_config.sh"
capture_user || err "Could not determine install user. Run via 'sudo bash $0' from a regular login (so \$SUDO_USER is set), or provide [system] user in /boot/astromech_init.cfg."
USER="$TARGET_USER"
HOME_DIR="$TARGET_HOME"
info "Installing AstromechOS for user: $USER (home: $HOME_DIR)"

echo ""
echo "============================================================"
echo "  AstromechOS Master — Installation automatique"
echo "============================================================"
echo ""

# =============================================================================
# STEP 1 — System update + packages
# =============================================================================
info "Step 1/8 — Updating system..."
apt-get update -qq
apt-get upgrade -y -qq
apt-get install -y -qq \
    python3-pip python3-serial python3-evdev python3-mutagen \
    git rsync avahi-daemon
ok "Packages installed"

# =============================================================================
# STEP 2 — Clone the repo
# =============================================================================
info "Step 2/8 — Cloning git repo..."
if [ -d "$REPO_PATH/.git" ]; then
    warn "Repo already present — git pull..."
    sudo -u "$USER" git -C "$REPO_PATH" pull --ff-only || warn "git pull failed (no connection?)"
else
    sudo -u "$USER" git clone "$REPO_URL" "$REPO_PATH" || err "git clone failed — check internet connection"
fi
sudo -u "$USER" git -C "$REPO_PATH" rev-parse --short HEAD > "$REPO_PATH/VERSION"
ok "Repo cloned — version: $(cat $REPO_PATH/VERSION)"

# =============================================================================
# STEP 3 — UART fix: free ttyAMA0 from Bluetooth
# =============================================================================
info "Step 3/8 — UART fix (miniuart-bt — BT remains functional for the controller)..."
CONFIG="/boot/firmware/config.txt"
if grep -q "dtoverlay=miniuart-bt" "$CONFIG"; then
    ok "dtoverlay=miniuart-bt already present"
elif grep -q "dtoverlay=disable-bt" "$CONFIG"; then
    # disable-bt cuts BT → controller unusable — fix it
    sed -i 's/dtoverlay=disable-bt/dtoverlay=miniuart-bt/' "$CONFIG"
    ok "dtoverlay=disable-bt replaced by miniuart-bt (BT controller preserved)"
else
    echo "dtoverlay=miniuart-bt" >> "$CONFIG"
    ok "dtoverlay=miniuart-bt added to $CONFIG"
fi

# =============================================================================
# STEP 4 — Enable hardware UART + I2C
# =============================================================================
info "Step 4/8 — Enabling UART + I2C..."
raspi-config nonint do_serial_hw 0   # enable hardware UART
raspi-config nonint do_serial_cons 1 # disable serial console on UART
raspi-config nonint do_i2c 0         # enable I2C
ok "Hardware UART enabled, serial console disabled, I2C enabled"

# =============================================================================
# STEP 5 — Python dependencies
# =============================================================================
info "Step 5/8 — Installing Python dependencies..."
sudo -u "$USER" pip3 install --break-system-packages -q \
    -r "$REPO_PATH/master/requirements.txt"
ok "Python dependencies installed"

# =============================================================================
# STEP 5b — Pre-download Slave vendor deps (offline cache for deploy.sh)
# =============================================================================
info "Step 5b/8 — Pre-downloading Slave dependencies (vendor/)..."
VENDOR_DIR="$REPO_PATH/slave/vendor"
mkdir -p "$VENDOR_DIR"
chown "$USER:$USER" "$VENDOR_DIR"
if sudo -u "$USER" pip3 download -q setuptools wheel -d "$VENDOR_DIR" && \
   sudo -u "$USER" pip3 download -q -r "$REPO_PATH/slave/requirements.txt" -d "$VENDOR_DIR" 2>/dev/null; then
    ok "Slave vendor ready ($(ls $VENDOR_DIR | wc -l) packages)"
else
    warn "Slave vendor failed — no internet connection? deploy.sh will use PyPI directly"
fi

# =============================================================================
# STEP 6 — Copy local.cfg
# =============================================================================
info "Step 6/8 — Configuring local.cfg..."
LOCAL_CFG="$REPO_PATH/master/config/local.cfg"
if [ -f "$LOCAL_CFG" ]; then
    warn "local.cfg already present — kept as-is"
else
    sudo -u "$USER" cp "$REPO_PATH/master/config/local.cfg.example" "$LOCAL_CFG"
    ok "local.cfg created from example (all values pre-filled)"
fi

# Ask for robot name and write to local.cfg
echo ""
read -p "  Robot name (shown in the dashboard header) [R2-D2]: " ROBOT_NAME
ROBOT_NAME="${ROBOT_NAME:-R2-D2}"
if ! grep -q '^\[robot\]' "$LOCAL_CFG" 2>/dev/null; then
    echo -e "\n[robot]\nname = $ROBOT_NAME" | sudo -u "$USER" tee -a "$LOCAL_CFG" > /dev/null
else
    sudo -u "$USER" sed -i "/^\[robot\]/,/^\[/ s/^name\s*=.*/name = $ROBOT_NAME/" "$LOCAL_CFG"
fi
ok "Robot name set to: $ROBOT_NAME"

# =============================================================================
# STEP 7 — Network configuration (hotspot + wlan1)
# =============================================================================
info "Step 7/8 — Network configuration..."
bash "$REPO_PATH/scripts/setup_master_network.sh"

# =============================================================================
# STEP 7b — Ed25519 SSH key (for automatic Master → Slave rsync)
# =============================================================================
info "Step 7b/8 — Generating Ed25519 SSH key..."
SSH_KEY="$HOME_DIR/.ssh/id_ed25519"
if [ -f "$SSH_KEY" ]; then
    ok "SSH key already present: $SSH_KEY"
else
    sudo -u "$USER" ssh-keygen -t ed25519 -C "astromech-master" -f "$SSH_KEY" -N ""
    ok "SSH key generated: $SSH_KEY"
fi
echo ""
echo -e "  ${YEL}Public key to copy to the Slave (after Slave installation):${NC}"
echo "    ssh-copy-id $(slave_target)"
echo "  (or via setup_ssh_keys.sh once the Slave is connected to the hotspot)"
echo ""

# =============================================================================
# STEP 8 — systemd services
# =============================================================================
info "Step 8/8 — Installing systemd services..."
# Service files are now TEMPLATES (.service.template) — install_service_template
# substitutes __USER__/__HOME__/__UID__/__REPO_PATH__ at install time. Makes the
# units portable to any Pi user (artoo / pi / astromech / ...).
install_service_template "$REPO_PATH/master/services/astromech-master.service.template"  astromech-master.service
install_service_template "$REPO_PATH/master/services/astromech-monitor.service.template" astromech-monitor.service
# astromech-firstboot.service is a oneshot guarded by ConditionPathExists
# on /boot/ASTROMECH_FIRSTBOOT_READY — it does nothing on a normal boot,
# but if the AstromechOS Imager (or a manual provisioning operator) drops
# the marker file at /boot, the next boot will trigger firstboot_setup.sh.
# We install + enable it here so the trigger path exists post-install.
install_service_template "$REPO_PATH/master/services/astromech-firstboot.service.template" astromech-firstboot.service
systemctl daemon-reload
systemctl enable astromech-master astromech-monitor astromech-firstboot
ok "systemd services installed and enabled (templated for $USER)"
ok "  astromech-firstboot.service installed — fires when /boot/ASTROMECH_FIRSTBOOT_READY is dropped by the Imager"

# =============================================================================
# Summary
# =============================================================================
echo ""
echo "============================================================"
echo "  Master installation complete ✓"
echo "============================================================"
echo ""
echo "  Repo    : $REPO_PATH"
echo "  Version : $(cat $REPO_PATH/VERSION)"
echo ""
echo "  After reboot:"
echo "    → Connect to the hotspot (Astromech_Control_XXXX, unique per robot)"
echo "    → SSH: ssh $USER@192.168.4.1"
echo "    → Check: sudo systemctl status astromech-master"
echo ""
echo "  Next step: install the Slave"
echo "    sudo bash $REPO_PATH/scripts/setup_slave_network.sh"
echo ""
echo "============================================================"
echo ""

read -p "Reboot now? [Y/n] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    reboot
fi
