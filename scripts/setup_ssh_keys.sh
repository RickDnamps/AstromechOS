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
# setup_ssh_keys.sh — SSH sans mot de passe R2-Master → R2-Slave
# Run from the R2-Master (Pi 4B) after the hotspot is active
# and the R2-Slave is connected (hostname: r2-slave.local)
#
# Usage: bash setup_ssh_keys.sh

set -e

SLAVE_USER="artoo"
SLAVE_HOST="r2-slave.local"

echo "=== SSH key generation (if absent) ==="
if [ ! -f ~/.ssh/id_ed25519 ]; then
    ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519
    echo "Key generated: ~/.ssh/id_ed25519"
else
    echo "Existing key: ~/.ssh/id_ed25519"
fi

echo "=== Copy public key to R2-Slave ==="
echo "You will need to enter the R2-Slave password one last time."
ssh-copy-id -i ~/.ssh/id_ed25519.pub "${SLAVE_USER}@${SLAVE_HOST}"

echo "=== Test connexion SSH sans mot de passe ==="
if ssh -o BatchMode=yes -o ConnectTimeout=5 "${SLAVE_USER}@${SLAVE_HOST}" echo "OK"; then
    echo ""
    echo "=== Passwordless SSH configured successfully ==="
    echo "  R2-Master → R2-Slave (${SLAVE_HOST}) : OK"
else
    echo "ERROR: passwordless SSH connection failed"
    exit 1
fi
