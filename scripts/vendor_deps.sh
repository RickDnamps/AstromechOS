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
# vendor_deps.sh — Pre-download pip dependencies into slave/vendor/
# Run ONCE on the Master when internet (wlan1) is available.
# The vendor/ directory is then transferred to the Slave by deploy.sh — no internet needed.
#
# Usage: bash scripts/vendor_deps.sh

set -e

REPO_PATH="/home/artoo/r2d2"
VENDOR_DIR="$REPO_PATH/slave/vendor"
REQS="$REPO_PATH/slave/requirements.txt"

echo "=== Pre-downloading Slave dependencies ==="

if ! ip addr show wlan1 2>/dev/null | grep -q "inet "; then
    echo "ERROR: wlan1 not connected — internet required for this operation"
    exit 1
fi

mkdir -p "$VENDOR_DIR"
echo "Downloading to $VENDOR_DIR..."
pip3 download -r "$REQS" -d "$VENDOR_DIR"

echo ""
echo "=== Vendor directory created ==="
ls "$VENDOR_DIR"
echo ""
echo "The next 'bash scripts/deploy.sh' will install the dependencies"
echo "sur le Slave sans connexion internet."
