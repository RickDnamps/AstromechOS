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
# resync_slave.sh — Rsync + restart Slave uniquement (sans git pull ni restart Master)
# Appelé par : update.sh, API /system/resync_slave, bouton dôme
# Usage: bash scripts/resync_slave.sh

REPO=/home/artoo/r2d2
SLAVE=artoo@r2-slave.local
SSH="ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10"
VERSION_FILE=$REPO/VERSION
ERRORS=0

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; ERRORS=$((ERRORS+1)); }

echo -e "${CYAN}  → Resync Slave...${NC}"

# Vérifier connectivité
if ! $SSH $SLAVE "echo ok" > /dev/null 2>&1; then
    fail "Slave inaccessible"
    exit 1
fi

# Rsync code
rsync -az --delete -e "$SSH" \
    --exclude='__pycache__' --exclude='*.pyc' \
    --exclude='sounds/*.mp3' --exclude='vendor/' \
    "$REPO/slave/" "$SLAVE:$REPO/slave/" 2>&1 \
    && ok "slave/ synchronisé" || fail "rsync slave/ échoué"

rsync -az -e "$SSH" \
    --exclude='__pycache__' --exclude='*.pyc' \
    "$REPO/shared/" "$SLAVE:$REPO/shared/" 2>&1 \
    && ok "shared/ synchronisé" || fail "rsync shared/ échoué"

rsync -az -e "$SSH" "$VERSION_FILE" "$SLAVE:$VERSION_FILE" 2>/dev/null
ok "VERSION → $(cat $VERSION_FILE 2>/dev/null || echo 'unknown')"

# Installer le service file si modifié (PYTHONPATH, ExecStart, etc.)
SERVICE_SRC="$REPO/slave/services/r2d2-slave.service"
if [ -f "$SERVICE_SRC" ]; then
    $SSH $SLAVE "sudo tee /etc/systemd/system/r2d2-slave.service > /dev/null" < "$SERVICE_SRC" \
        && $SSH $SLAVE "sudo systemctl daemon-reload" \
        && ok "Service file installé" \
        || warn "Service file: échec installation (vérifier sudo)"
fi

# Restart Slave
if $SSH $SLAVE "sudo systemctl restart r2d2-slave.service" 2>/dev/null; then
    sleep 4
    SLAVE_STATUS=$($SSH $SLAVE "systemctl is-active r2d2-slave.service" 2>/dev/null)
    if [ "$SLAVE_STATUS" = "active" ]; then
        ok "r2d2-slave actif"
    else
        # Tentative reboot si service en échec
        warn "Service en échec ($SLAVE_STATUS) — reboot Slave..."
        $SSH $SLAVE "sudo reboot" 2>/dev/null && ok "Slave en reboot" || fail "Reboot Slave échoué"
    fi
else
    fail "Impossible de redémarrer r2d2-slave"
fi

[ $ERRORS -eq 0 ] && echo -e "  ${GREEN}✓ Resync OK${NC}" || echo -e "  ${RED}✗ Resync avec $ERRORS erreur(s)${NC}"
exit $ERRORS
