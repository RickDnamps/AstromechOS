#!/usr/bin/env bash
# ============================================================
#  ██████╗ ██████╗       ██████╗ ██████╗
#  ██╔══██╗╚════██╗      ██╔══██╗╚════██╗
#  ██████╔╝ █████╔╝      ██║  ██║ █████╔╝
#  ██╔══██╗██╔═══╝       ██║  ██║██╔═══╝
#  ██║  ██║███████╗      ██████╔╝███████╗
#  ╚═╝  ╚═╝╚══════╝      ╚═════╝ ╚══════╝
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
# deploy_rp2040.sh — Push MicroPython firmware to the RP2040 via USB/ampy
# Usage: bash scripts/deploy_rp2040.sh [/dev/ttyACMx]
#
# Must be run on the Slave Pi (where the RP2040 is connected via USB).
# Temporarily stops r2d2-slave.service to release the USB port.

set -e

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FIRMWARE_DIR="$REPO_DIR/rp2040/firmware"

# Couleurs
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${GREEN}[deploy_rp2040]${NC} $*"; }
warn() { echo -e "${YELLOW}[deploy_rp2040]${NC} $*"; }
err()  { echo -e "${RED}[deploy_rp2040]${NC} $*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Find the RP2040 port
# ---------------------------------------------------------------------------
find_port() {
    # Look up by stable USB identifier (Raspberry Pi / MicroPython)
    local by_id
    by_id=$(ls /dev/serial/by-id/ 2>/dev/null | grep -i "Raspberry_Pi" | head -1)
    if [ -n "$by_id" ]; then
        echo "/dev/serial/by-id/$by_id"
        return
    fi
    # Fallback: try ACM ports from highest to lowest
    # (with VESCs connected = ttyACM2, without VESCs = ttyACM0)
    for p in /dev/ttyACM2 /dev/ttyACM1 /dev/ttyACM0; do
        [ -e "$p" ] && echo "$p" && return
    done
}

PORT="${1:-}"
if [ -z "$PORT" ]; then
    PORT="$(find_port)"
fi
[ -z "$PORT" ] && err "RP2040 port not found. Connect the RP2040 via USB and try again."
log "Port RP2040 : $PORT"

# ---------------------------------------------------------------------------
# Installer ampy si absent — s'assurer que ~/.local/bin est dans PATH
# ---------------------------------------------------------------------------
export PATH="$HOME/.local/bin:$PATH"

if ! command -v ampy &>/dev/null; then
    warn "ampy not found — installing (adafruit-ampy)..."
    pip3 install --quiet --break-system-packages adafruit-ampy
    export PATH="$HOME/.local/bin:$PATH"
fi

# ---------------------------------------------------------------------------
# Stop r2d2-slave.service to release the port
# ---------------------------------------------------------------------------
SLAVE_WAS_RUNNING=false
if systemctl is-active --quiet r2d2-slave.service 2>/dev/null; then
    log "Stopping r2d2-slave.service (releasing USB port)..."
    sudo systemctl stop r2d2-slave.service
    SLAVE_WAS_RUNNING=true
fi

cleanup() {
    if [ "$SLAVE_WAS_RUNNING" = true ]; then
        log "Restarting r2d2-slave.service..."
        sudo systemctl start r2d2-slave.service
    fi
}
trap cleanup EXIT

# Short pause to ensure the port is fully released
sleep 1

# ---------------------------------------------------------------------------
# Pousser les fichiers firmware
# ---------------------------------------------------------------------------
log "Upload display.py..."
ampy --port "$PORT" put "$FIRMWARE_DIR/display.py" display.py

if [ -f "$FIRMWARE_DIR/touch.py" ]; then
    log "Upload touch.py..."
    ampy --port "$PORT" put "$FIRMWARE_DIR/touch.py" touch.py
fi

log "Upload main.py (last — triggers execution on reset)..."
ampy --port "$PORT" put "$FIRMWARE_DIR/main.py" main.py

# ---------------------------------------------------------------------------
# Reset soft du RP2040
# ---------------------------------------------------------------------------
log "Reset RP2040 (soft reset via ampy)..."
ampy --port "$PORT" reset

log ""
log "✓ RP2040 firmware deployed to $PORT"
log "  The RP2040 restarts and shows the BOOTING spinner (orange)."
log "  If the r2d2-slave service was active, it restarts automatically."
