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
# Diagnostic AstromechOS — lit les logs Master + Slave et teste les servos via API
# Usage: bash scripts/check_logs.sh
# Options: --tail 50   (number of log lines, default 80)
#          --servo     (envoie aussi une commande test servo via API)

MASTER=${USER:-astromech}@${MASTER_HOST:-astromech-master.local}
SLAVE=${USER:-astromech}@${SLAVE_HOST:-astromech-slave.local}
MASTER_IP=192.168.4.1
TAIL=${2:-80}

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

sep() { echo -e "\n${CYAN}══════════════════════════════════════════════${NC}"; }
ok()  { echo -e "${GREEN}✓${NC} $1"; }
err() { echo -e "${RED}✗${NC} $1"; }
warn(){ echo -e "${YELLOW}⚠${NC} $1"; }

sep
echo -e "${CYAN}  AstromechOS Diagnostic — $(date '+%H:%M:%S')${NC}"
sep

# ──────────────────────────────────────────────
# 1. Statut des services
# ──────────────────────────────────────────────
echo ""
echo "=== SERVICES ==="
ssh -o ConnectTimeout=5 $MASTER "systemctl is-active astromech-master" 2>/dev/null \
    | grep -q "active" && ok "astromech-master.service ACTIF" || err "astromech-master.service INACTIF"

ssh -o ConnectTimeout=5 $SLAVE "systemctl is-active astromech-slave" 2>/dev/null \
    | grep -q "active" && ok "astromech-slave.service ACTIF"  || err "astromech-slave.service INACTIF"

# ──────────────────────────────────────────────
# 2. API Flask — status
# ──────────────────────────────────────────────
echo ""
echo "=== API FLASK (Master :5000) ==="
STATUS=$(curl -s --max-time 5 http://$MASTER_IP:5000/status 2>/dev/null)
if [ -n "$STATUS" ]; then
    ok "Flask responding"
    echo "$STATUS" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    for k,v in sorted(d.items()):
        icon = '✓' if v == True else ('✗' if v == False else '·')
        print(f'  {icon}  {k}: {v}')
except: print('  (JSON invalide)')
" 2>/dev/null
else
    err "Flask not responding (service down or network issue?)"
fi

# ──────────────────────────────────────────────
# 3. I2C — verify that the chips respond
# ──────────────────────────────────────────────
echo ""
echo "=== I2C ==="
I2C_MASTER=$(ssh -o ConnectTimeout=5 $MASTER "sudo /usr/sbin/i2cdetect -y 1 2>&1" 2>/dev/null)
if echo "$I2C_MASTER" | grep -q "40"; then
    ok "Master  PCA9685 @ 0x40 detected"
else
    err "Master  PCA9685 @ 0x40 NOT DETECTED"
fi

I2C_SLAVE=$(ssh -o ConnectTimeout=5 $SLAVE "sudo /usr/sbin/i2cdetect -y 1 2>/dev/null" 2>/dev/null)
if echo "$I2C_SLAVE" | grep -q "41"; then
    ok "Slave   PCA9685 @ 0x41 detected"
else
    err "Slave   PCA9685 @ 0x41 NOT DETECTED"
fi

# ──────────────────────────────────────────────
# 4. Test servo via API (option --servo)
# ──────────────────────────────────────────────
if [ "$1" == "--servo" ] || [ "$2" == "--servo" ]; then
    echo ""
    echo "=== TEST SERVO VIA API ==="
    echo -n "  POST /servo/dome/open dome_panel_1 ... "
    R=$(curl -s -X POST http://$MASTER_IP:5000/servo/dome/open \
        -H "Content-Type: application/json" \
        -d '{"name":"dome_panel_1","duration":800}' 2>/dev/null)
    echo "$R"

    sleep 1.5

    echo -n "  POST /servo/body/open body_panel_1 ... "
    R=$(curl -s -X POST http://$MASTER_IP:5000/servo/body/open \
        -H "Content-Type: application/json" \
        -d '{"name":"body_panel_1","duration":800}' 2>/dev/null)
    echo "$R"
fi

# ──────────────────────────────────────────────
# 5. Master logs — last lines + errors
# ──────────────────────────────────────────────
echo ""
sep
echo -e "${CYAN}  MASTER LOGS — last $TAIL lines${NC}"
sep
# Read master logs directly (no SSH — already on the master)
sudo journalctl -u astromech-master -b --no-pager -n $TAIL --output=short-iso 2>/dev/null \
    | grep -iE "servo|dome|pca|smbus|error|warn|ready|setup|Error" \
    | tail -40

echo ""
echo "--- Lignes traceback / exception ---"
sudo journalctl -u astromech-master -b --no-pager -n $TAIL --output=short-iso 2>/dev/null \
    | grep -iE "traceback|Exception|NoneType|AttributeError|TypeError" | tail -20

# ──────────────────────────────────────────────
# 6. Slave logs — last lines + errors
# ──────────────────────────────────────────────
echo ""
sep
echo -e "${CYAN}  SLAVE LOGS — last $TAIL lines${NC}"
sep
ssh -o ConnectTimeout=5 $SLAVE \
    "sudo journalctl -u astromech-slave -b --no-pager -n $TAIL --output=short-iso 2>/dev/null" 2>/dev/null \
    | grep -iE "servo|SRV|pca|smbus|error|warn|ready|setup|Error" \
    | tail -40

echo ""
echo "--- Lignes traceback / exception ---"
ssh -o ConnectTimeout=5 $SLAVE \
    "sudo journalctl -u astromech-slave -b --no-pager -n $TAIL --output=short-iso 2>/dev/null" 2>/dev/null \
    | grep -iE "traceback|Exception|NoneType|AttributeError|TypeError" | tail -20

# ──────────────────────────────────────────────
# 7. PCA9685 registers — current state (MODE1)
# ──────────────────────────────────────────────
echo ""
echo "=== MODE1 PCA9685 (sleep/wake state) ==="
python3 -c "
import smbus2
b = smbus2.SMBus(1)
mode1 = b.read_byte_data(0x40, 0x00)
b.close()
sleep = bool(mode1 & 0x10)
print(f'Master 0x40 MODE1=0x{mode1:02X} → {\"SLEEPING\" if sleep else \"AWAKE\"}')
" 2>/dev/null || err "Impossible de lire MODE1 Master (smbus2 manquant ou chip absent)"

ssh -o ConnectTimeout=5 $SLAVE "python3 -c \"
import smbus2
b = smbus2.SMBus(1)
mode1 = b.read_byte_data(0x41, 0x00)
b.close()
sleep = bool(mode1 & 0x10)
print(f'Slave  0x41 MODE1=0x{mode1:02X} → {\"SLEEPING\" if sleep else \"AWAKE\"}')
\"" 2>/dev/null || err "Impossible de lire MODE1 Slave"

sep
echo ""
echo "USAGE:"
echo "  bash scripts/check_logs.sh             # diagnostic complet"
echo "  bash scripts/check_logs.sh --servo     # + teste un servo via API"
echo ""
