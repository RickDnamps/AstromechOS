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
# deploy.sh — Deploys Slave code to the R2-Slave (Pi 4B 2G) and restarts the service
# Usage: bash scripts/deploy.sh [--no-reboot] [--git-pull]
#
# Options:
#   --no-reboot   rsync only, without restarting the Slave
#   --git-pull    git pull before rsync (requires wlan1 connected)

set -e

REPO_PATH="/home/artoo/r2d2"
SLAVE_USER="artoo"
SLAVE_HOST="r2-slave.local"
SLAVE_REPO="/home/artoo/r2d2"
VERSION_FILE="/home/artoo/r2d2/VERSION"
SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=10"
VENDOR_DIR="$REPO_PATH/slave/vendor"

DO_REBOOT=true
DO_GIT_PULL=false
FIRST_INSTALL=false

# Parse arguments
for arg in "$@"; do
    case $arg in
        --no-reboot)     DO_REBOOT=false ;;
        --git-pull)      DO_GIT_PULL=true ;;
        --first-install) FIRST_INSTALL=true ;;
    esac
done

echo "=== R2-D2 Deploy ==="

# ------------------------------------------------------------------
# git pull optionnel
# ------------------------------------------------------------------
if [ "$DO_GIT_PULL" = true ]; then
    echo "[1/4] git pull..."
    if ip addr show wlan1 | grep -q "inet "; then
        cd "$REPO_PATH"
        git pull && git rev-parse --short HEAD > "$VERSION_FILE"
        echo "      git pull OK — version: $(cat $VERSION_FILE)"
    else
        echo "      wlan1 not available — git pull skipped"
    fi
else
    echo "[1/4] git pull skipped (use --git-pull to enable)"
fi

# ------------------------------------------------------------------
# Check that the Slave is reachable
# ------------------------------------------------------------------
echo "[2/4] Checking Slave connection (${SLAVE_HOST})..."
if ! ssh $SSH_OPTS "${SLAVE_USER}@${SLAVE_HOST}" echo "ping" > /dev/null 2>&1; then
    echo "ERROR: Cannot reach the Slave ${SLAVE_HOST}"
    echo "       Check that the R2-Slave is connected to the R2D2_Control hotspot"
    exit 1
fi
echo "      Slave reachable OK"

# ------------------------------------------------------------------
# rsync slave/ + shared/ + VERSION
# ------------------------------------------------------------------
echo "[3/4] rsync vers ${SLAVE_HOST}..."

rsync -avz --delete \
    -e "ssh $SSH_OPTS" \
    "$REPO_PATH/slave/" \
    "${SLAVE_USER}@${SLAVE_HOST}:${SLAVE_REPO}/slave/"

rsync -avz \
    -e "ssh $SSH_OPTS" \
    "$REPO_PATH/shared/" \
    "${SLAVE_USER}@${SLAVE_HOST}:${SLAVE_REPO}/shared/"

rsync -az \
    -e "ssh $SSH_OPTS" \
    "$VERSION_FILE" \
    "${SLAVE_USER}@${SLAVE_HOST}:${VERSION_FILE}"

LOCAL_VERSION=$(cat "$VERSION_FILE" 2>/dev/null || echo "unknown")
echo "      rsync OK — deployed version: ${LOCAL_VERSION}"

# ------------------------------------------------------------------
# pip dependencies — install from local cache (vendor/)
# vendor/ is pre-downloaded on the Master (internet required once)
# then transferred to the Slave via rsync → no internet needed on the Slave
# ------------------------------------------------------------------
echo "      pip dependencies..."
REQS="$REPO_PATH/slave/requirements.txt"

_pip_install_slave() {
    # Try offline install from vendor/, fall back to PyPI on failure
    ssh $SSH_OPTS "${SLAVE_USER}@${SLAVE_HOST}" \
        "pip3 install --break-system-packages -q --no-index --find-links=${SLAVE_REPO}/slave/vendor -r ${SLAVE_REPO}/slave/requirements.txt" \
    || {
        echo "      → vendor/ incomplete, falling back to PyPI installation..."
        ssh $SSH_OPTS "${SLAVE_USER}@${SLAVE_HOST}" \
            "pip3 install --break-system-packages -q -r ${SLAVE_REPO}/slave/requirements.txt"
    }
}

if [ -d "$VENDOR_DIR" ] && [ "$(ls -A $VENDOR_DIR)" ]; then
    # Install from local cache — works without internet
    echo "      → offline installation from vendor/"
    _pip_install_slave
else
    # No vendor/ directory: download from PyPI (requires NAT wlan1 active)
    echo "      → vendor/ missing, downloading from PyPI (requires internet via Master NAT)"
    if ip addr show wlan1 2>/dev/null | grep -q "inet "; then
        # Pre-download on the Master (setuptools + wheel first to avoid errors)
        mkdir -p "$VENDOR_DIR"
        pip3 download -q setuptools wheel -d "$VENDOR_DIR"
        pip3 download -q -r "$REQS" -d "$VENDOR_DIR"
        # Re-rsync the freshly created vendor/ directory
        rsync -az -e "ssh $SSH_OPTS" "$VENDOR_DIR/" "${SLAVE_USER}@${SLAVE_HOST}:${SLAVE_REPO}/slave/vendor/"
        _pip_install_slave
        echo "      → vendor/ created for future offline deployments"
    else
        echo "      WARNING: vendor/ missing and wlan1 unavailable — attempting direct PyPI install..."
        ssh $SSH_OPTS "${SLAVE_USER}@${SLAVE_HOST}" \
            "pip3 install --break-system-packages -q -r ${SLAVE_REPO}/slave/requirements.txt" \
        || echo "      FAILED pip — run 'bash scripts/vendor_deps.sh' with internet to build the cache"
    fi
fi

# ------------------------------------------------------------------
# Premier install : services systemd + audio sur le Slave
# ------------------------------------------------------------------
if [ "$FIRST_INSTALL" = true ]; then
    echo "[4/5] Installation services systemd + audio + BT sur le Slave..."
    ssh $SSH_OPTS "${SLAVE_USER}@${SLAVE_HOST}" bash << 'REMOTE'
        # Services systemd
        sudo cp /home/artoo/r2d2/slave/services/r2d2-slave.service   /etc/systemd/system/
        sudo cp /home/artoo/r2d2/slave/services/r2d2-version.service /etc/systemd/system/
        sudo systemctl daemon-reload
        sudo systemctl enable r2d2-version r2d2-slave
        echo "  → systemd services installed"

        # mpg123 (MP3 player)
        if ! which mpg123 > /dev/null 2>&1; then
            sudo apt-get install -y -qq mpg123
            echo "  → mpg123 installed"
        else
            echo "  → mpg123 already present"
        fi

        # pulseaudio + BT packages (BT speaker support)
        if ! which pulseaudio > /dev/null 2>&1; then
            sudo apt-get install -y -qq \
                pulseaudio pulseaudio-module-bluetooth bluez libasound2-plugins
            echo "  → pulseaudio + BT installed"
        else
            echo "  → pulseaudio already present"
        fi

        # Route ALSA through pulseaudio (fallback to 3.5mm jack when no BT)
        cat > /home/artoo/.asoundrc << 'ASOUNDRC'
pcm.!default {
  type pulse
}
ctl.!default {
  type pulse
}
ASOUNDRC
        amixer -c 0 cset numid=1 100% > /dev/null 2>&1 || true
        amixer -c 0 cset numid=2 on   > /dev/null 2>&1 || true
        sudo alsactl store 2>/dev/null || true
        echo "  → ALSA → pulseaudio routing configured, volume 100%"

        # PulseAudio BT modules + bluetooth group
        sudo usermod -aG bluetooth artoo
        mkdir -p /home/artoo/.config/pulse
        cat > /home/artoo/.config/pulse/default.pa << 'PULSECONF'
.include /etc/pulse/default.pa
load-module module-bluetooth-policy
load-module module-bluetooth-discover
PULSECONF
        chown -R artoo:artoo /home/artoo/.config

        # Allow pulseaudio to run without active login session
        sudo loginctl enable-linger artoo
        ARTOO_UID=$(id -u artoo)
        sudo -u artoo XDG_RUNTIME_DIR="/run/user/$ARTOO_UID" \
            systemctl --user enable pulseaudio.service pulseaudio.socket 2>/dev/null || true
        echo "  → PulseAudio BT configured"
REMOTE
    echo "      Services + audio + BT OK"
else
    echo "[4/5] systemd services skipped (--first-install not specified)"
fi

# ------------------------------------------------------------------
# Reboot Slave
# ------------------------------------------------------------------
if [ "$DO_REBOOT" = true ]; then
    echo "[5/5] Restarting r2d2-slave service on the Slave..."
    ssh $SSH_OPTS "${SLAVE_USER}@${SLAVE_HOST}" \
        "sudo systemctl restart r2d2-slave" 2>/dev/null || \
    ssh $SSH_OPTS "${SLAVE_USER}@${SLAVE_HOST}" \
        "sudo reboot" 2>/dev/null || true
    echo "      Slave restarted"
else
    echo "[5/5] Reboot skipped (--no-reboot)"
fi

echo ""
echo "=== Deploy complete — version: ${LOCAL_VERSION} ==="
