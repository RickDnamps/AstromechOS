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
# =============================================================================
# setup_slave.sh — Full R2-Slave installation (single command)
# =============================================================================
#
# This script automates all Slave installation steps:
#   1. System update + packages
#   2. UART fix (disable-bt to free ttyAMA0)
#   3. Enable UART + I2C via raspi-config
#   4. Create the /home/artoo/r2d2 directory
#   5. Network configuration (wlan0 → Master hotspot)
#   → reboot
#
# After reboot, the Master runs rsync + installs services automatically:
#   bash /home/artoo/r2d2/scripts/deploy.sh --first-install
#
# Usage (on the R2-Slave, connected to home WiFi):
#   curl -fsSL https://raw.githubusercontent.com/RickDnamps/AstromechOS/main/scripts/setup_slave.sh | sudo bash
#
# Or if the script was copied from the Master:
#   sudo bash /home/artoo/setup_slave.sh
#
# =============================================================================

set -e

# Reopen stdin from the terminal if the script is run via pipe (curl | bash)
[ -t 0 ] || exec < /dev/tty

REPO_PATH="/home/artoo/r2d2"
USER="artoo"
GITHUB_RAW="https://raw.githubusercontent.com/RickDnamps/AstromechOS/main"

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

# Check that we are on the Slave (not the Master)
HOSTNAME=$(hostname)
if [ "$HOSTNAME" = "r2-master" ]; then
    err "This script must be run on the R2-SLAVE, not on the Master! (hostname: $HOSTNAME)"
fi

# Check that the artoo user exists
id "$USER" &>/dev/null || err "User '$USER' does not exist — reconfigure via Raspberry Pi Imager"

echo ""
echo "============================================================"
echo "  R2-D2 Slave — Installation automatique"
echo "============================================================"
echo ""

# =============================================================================
# STEP 1 — System update + packages
# =============================================================================
info "Step 1/5 — Updating system + packages..."
apt-get update -qq
apt-get upgrade -y -qq
apt-get install -y -qq \
    python3-pip python3-serial python3-smbus \
    git alsa-utils mpg123 avahi-daemon i2c-tools \
    pulseaudio pulseaudio-module-bluetooth bluez libasound2-plugins
ok "Packages installed (mpg123 + i2c-tools + pulseaudio BT included)"

# =============================================================================
# STEP 2 — UART fix: free ttyAMA0 — keep BT functional for speaker
# =============================================================================
info "Step 2/5 — UART fix (miniuart-bt — BT remains functional for speaker)..."
CONFIG="/boot/firmware/config.txt"
if grep -q "dtoverlay=miniuart-bt" "$CONFIG"; then
    ok "dtoverlay=miniuart-bt already present"
elif grep -q "dtoverlay=disable-bt" "$CONFIG"; then
    # disable-bt cuts BT entirely — replace so the BT speaker still works
    sed -i 's/dtoverlay=disable-bt/dtoverlay=miniuart-bt/' "$CONFIG"
    ok "dtoverlay=disable-bt replaced by miniuart-bt (BT speaker preserved)"
else
    echo "dtoverlay=miniuart-bt" >> "$CONFIG"
    ok "dtoverlay=miniuart-bt added to $CONFIG"
fi

# =============================================================================
# STEP 3 — Enable hardware UART + I2C
# =============================================================================
info "Step 3/5 — Enabling UART + I2C..."
raspi-config nonint do_serial_hw 0   # enable hardware UART
raspi-config nonint do_serial_cons 1 # disable serial console on UART
raspi-config nonint do_i2c 0         # enable I2C
ok "Hardware UART enabled, serial console disabled, I2C enabled"

# =============================================================================
# STEP 4 — Create the repo directory (will be filled by rsync from the Master)
# =============================================================================
info "Step 4/5 — Preparing repo directory..."
mkdir -p "$REPO_PATH/slave"
chown -R "$USER:$USER" "$REPO_PATH"
ok "Directory $REPO_PATH ready"

# =============================================================================
# STEP 4b — Python pip dependencies (installed now so no internet needed later)
# The Slave has no internet access once connected to the Master hotspot.
# smbus2 + adafruit PCA9685 + pyserial must be pre-installed here.
# Note: pyvesc is NOT required — VESC communication uses native CRC-16/CCITT.
# =============================================================================
info "Step 4b — Installing Python dependencies..."
pip3 install --break-system-packages -q \
    "pyserial>=3.5" \
    "smbus2>=0.4.0" \
    "adafruit-circuitpython-pca9685>=2.4.0" \
    "RPi.GPIO>=0.7.1" \
|| warn "Some pip packages failed — will retry via deploy.sh --first-install"
ok "Python dependencies installed"

# =============================================================================
# STEP 5 — Network configuration (wlan0 → Master hotspot)
# =============================================================================
info "Step 5/5 — Network configuration..."

# Find the setup_slave_network.sh script
NETWORK_SCRIPT=""

# Search locally (if launched from the repo or copied)
for candidate in \
    "$(dirname "$0")/setup_slave_network.sh" \
    "/home/artoo/r2d2/scripts/setup_slave_network.sh" \
    "/home/artoo/setup_slave_network.sh"
do
    if [ -f "$candidate" ]; then
        NETWORK_SCRIPT="$candidate"
        break
    fi
done

# Otherwise download from GitHub
if [ -z "$NETWORK_SCRIPT" ]; then
    warn "setup_slave_network.sh not found locally — downloading from GitHub..."
    TMP_SCRIPT=$(mktemp /tmp/setup_slave_network_XXXXXX.sh)
    if curl -fsSL "$GITHUB_RAW/scripts/setup_slave_network.sh" -o "$TMP_SCRIPT" 2>/dev/null; then
        NETWORK_SCRIPT="$TMP_SCRIPT"
        ok "Script downloaded"
    else
        err "Cannot download setup_slave_network.sh — check internet connection"
    fi
fi

bash "$NETWORK_SCRIPT"

# =============================================================================
# STEP 5b — Disable WiFi power saving (avoids incomplete ARPs / SSH drops)
# =============================================================================
info "Step 5b — Disabling WiFi power saving..."
cat > /etc/udev/rules.d/70-wifi-powersave.rules << 'EOF'
ACTION=="add", SUBSYSTEM=="net", KERNEL=="wlan0", RUN+="/sbin/iw dev wlan0 set power_save off"
EOF
# Apply immediately if wlan0 is already active
iw dev wlan0 set power_save off 2>/dev/null || true
ok "WiFi power saving disabled (permanent udev rule)"

# =============================================================================
# STEP 6 — ALSA → PulseAudio routing (3.5mm jack default, BT speaker optional)
# =============================================================================
info "Step 6 — Audio configuration (pulseaudio + 3.5mm jack)..."

# Route ALSA through pulseaudio so mpg123 can reach a BT speaker when one is
# connected, while falling back to the 3.5mm jack when it isn't.
cat > /home/"$USER"/.asoundrc << 'ASOUNDRC'
pcm.!default {
  type pulse
}
ctl.!default {
  type pulse
}
ASOUNDRC
chown "$USER:$USER" /home/"$USER"/.asoundrc

# Volume at 100% + unmute
amixer -c 0 cset numid=1 100% > /dev/null 2>&1 || true
amixer -c 0 cset numid=2 on   > /dev/null 2>&1 || true
alsactl store 2>/dev/null || true

ok "ALSA → pulseaudio routing configured, volume 100%"

# =============================================================================
# STEP 6b — PulseAudio Bluetooth configuration
# =============================================================================
info "Step 6b — PulseAudio Bluetooth configuration..."

# Add artoo to the bluetooth group (required for bluetoothctl without sudo)
usermod -aG bluetooth "$USER"

# Load BT modules in pulseaudio (survives reboots via user config)
PULSE_CFG_DIR="/home/$USER/.config/pulse"
mkdir -p "$PULSE_CFG_DIR"
cat > "$PULSE_CFG_DIR/default.pa" << 'PULSECONF'
.include /etc/pulse/default.pa
load-module module-bluetooth-policy
load-module module-bluetooth-discover
PULSECONF
chown -R "$USER:$USER" "/home/$USER/.config"

# Allow pulseaudio user service to run without an active login session
loginctl enable-linger "$USER"
ARTOO_UID=$(id -u "$USER")
sudo -u "$USER" XDG_RUNTIME_DIR="/run/user/$ARTOO_UID" \
    systemctl --user enable pulseaudio.service pulseaudio.socket 2>/dev/null || true

ok "PulseAudio BT configured (auto-start, BT modules loaded)"

# =============================================================================
# Summary
# =============================================================================
echo ""
echo "============================================================"
echo "  Slave installation complete ✓"
echo "============================================================"
echo ""
echo "  After reboot:"
echo "    The Slave connects to the AstromechOS hotspot on the Master."
echo ""
echo "  On the Master, run the first deployment:"
echo "    bash /home/artoo/r2d2/scripts/deploy.sh --first-install"
echo ""
echo "  This will:"
echo "    → rsync the code to the Slave"
echo "    → install Python dependencies"
echo "    → install systemd services"
echo "    → start r2d2-slave"
echo "============================================================"
echo ""

read -p "Reboot now? [Y/n] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    reboot
fi
