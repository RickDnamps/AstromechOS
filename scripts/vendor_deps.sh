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
# vendor_deps.sh — Pré-télécharge les dépendances pip dans slave/vendor/
# À lancer UNE FOIS sur le Master quand internet (wlan1) est disponible.
# Le dossier vendor/ est ensuite transféré au Slave par deploy.sh — sans internet.
#
# Usage: bash scripts/vendor_deps.sh

set -e

REPO_PATH="/home/artoo/r2d2"
VENDOR_DIR="$REPO_PATH/slave/vendor"
REQS="$REPO_PATH/slave/requirements.txt"

echo "=== Pré-téléchargement des dépendances Slave ==="

if ! ip addr show wlan1 2>/dev/null | grep -q "inet "; then
    echo "ERREUR: wlan1 non connecté — internet requis pour cette opération"
    exit 1
fi

mkdir -p "$VENDOR_DIR"
echo "Téléchargement vers $VENDOR_DIR..."
pip3 download -r "$REQS" -d "$VENDOR_DIR"

echo ""
echo "=== Vendor créé ==="
ls "$VENDOR_DIR"
echo ""
echo "Le prochain 'bash scripts/deploy.sh' installera les dépendances"
echo "sur le Slave sans connexion internet."
