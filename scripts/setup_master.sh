#!/bin/bash
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
#   curl -fsSL https://raw.githubusercontent.com/RickDnamps/R2D2_Control/main/scripts/setup_master.sh | sudo bash
#
# Or if the repo is already cloned:
#   sudo bash /home/artoo/r2d2/scripts/setup_master.sh
#
# =============================================================================

set -e

REPO_URL="https://github.com/RickDnamps/R2D2_Control.git"
REPO_PATH="/home/artoo/r2d2"
USER="artoo"

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
if [ "$HOSTNAME" = "r2-slave" ]; then
    err "This script must be run on the R2-MASTER, not on the Slave! (hostname: $HOSTNAME)"
fi

# Check that the user exists
id "$USER" &>/dev/null || err "User '$USER' does not exist — reconfigure via Raspberry Pi Imager"

echo ""
echo "============================================================"
echo "  R2-D2 Master — Installation automatique"
echo "============================================================"
echo ""

# =============================================================================
# STEP 1 — System update + packages
# =============================================================================
info "Step 1/8 — Updating system..."
apt-get update -qq
apt-get upgrade -y -qq
apt-get install -y -qq \
    python3-pip python3-serial python3-evdev \
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

# =============================================================================
# STEP 7 — Network configuration (hotspot + wlan1)
# =============================================================================
info "Step 7/8 — Network configuration..."
bash "$REPO_PATH/scripts/setup_master_network.sh"

# =============================================================================
# STEP 7b — Ed25519 SSH key (for automatic Master → Slave rsync)
# =============================================================================
info "Step 7b/8 — Generating Ed25519 SSH key..."
SSH_KEY="/home/$USER/.ssh/id_ed25519"
if [ -f "$SSH_KEY" ]; then
    ok "SSH key already present: $SSH_KEY"
else
    sudo -u "$USER" ssh-keygen -t ed25519 -C "r2-master" -f "$SSH_KEY" -N ""
    ok "SSH key generated: $SSH_KEY"
fi
echo ""
echo -e "  ${YEL}Public key to copy to the Slave (after Slave installation):${NC}"
echo "    ssh-copy-id artoo@r2-slave.local"
echo "  (or via setup_ssh_keys.sh once the Slave is connected to the hotspot)"
echo ""

# =============================================================================
# STEP 8 — systemd services
# =============================================================================
info "Step 8/8 — Installing systemd services..."
cp "$REPO_PATH/master/services/r2d2-master.service"  /etc/systemd/system/
cp "$REPO_PATH/master/services/r2d2-monitor.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable r2d2-master r2d2-monitor
ok "systemd services installed and enabled"

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
echo "    → Connect to the R2D2_Control hotspot"
echo "    → SSH: ssh artoo@192.168.4.1"
echo "    → Check: sudo systemctl status r2d2-master"
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
