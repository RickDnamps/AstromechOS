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
# resync_slave.sh — Rsync + restart Slave uniquement (sans git pull ni restart Master)
# Called by: update.sh, API /system/resync_slave, dome button
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

# Check connectivity
if ! $SSH $SLAVE "echo ok" > /dev/null 2>&1; then
    fail "Slave inaccessible"
    exit 1
fi

# Rsync code
rsync -az --delete -e "$SSH" \
    --exclude='__pycache__' --exclude='*.pyc' \
    --exclude='sounds/*.mp3' --exclude='vendor/' \
    "$REPO/slave/" "$SLAVE:$REPO/slave/" 2>&1 \
    && ok "slave/ synced" || fail "rsync slave/ failed"

rsync -az -e "$SSH" \
    --exclude='__pycache__' --exclude='*.pyc' \
    "$REPO/shared/" "$SLAVE:$REPO/shared/" 2>&1 \
    && ok "shared/ synced" || fail "rsync shared/ failed"

rsync -az -e "$SSH" "$VERSION_FILE" "$SLAVE:$VERSION_FILE" 2>/dev/null
ok "VERSION → $(cat $VERSION_FILE 2>/dev/null || echo 'unknown')"

# Install the service file if modified (PYTHONPATH, ExecStart, etc.)
SERVICE_SRC="$REPO/slave/services/r2d2-slave.service"
if [ -f "$SERVICE_SRC" ]; then
    $SSH $SLAVE "sudo tee /etc/systemd/system/r2d2-slave.service > /dev/null" < "$SERVICE_SRC" \
        && $SSH $SLAVE "sudo systemctl daemon-reload" \
        && ok "Service file installed" \
        || warn "Service file: install failed (check sudo)"
fi

# Restart Slave
if $SSH $SLAVE "sudo systemctl restart r2d2-slave.service" 2>/dev/null; then
    sleep 4
    SLAVE_STATUS=$($SSH $SLAVE "systemctl is-active r2d2-slave.service" 2>/dev/null)
    if [ "$SLAVE_STATUS" = "active" ]; then
        ok "r2d2-slave active"
    else
        # Attempt reboot if service failed
        warn "Service failed ($SLAVE_STATUS) — rebooting Slave..."
        $SSH $SLAVE "sudo reboot" 2>/dev/null && ok "Slave rebooting" || fail "Slave reboot failed"
    fi
else
    fail "Unable to restart r2d2-slave"
fi

[ $ERRORS -eq 0 ] && echo -e "  ${GREEN}✓ Resync OK${NC}" || echo -e "  ${RED}✗ Resync with $ERRORS error(s)${NC}"
exit $ERRORS
