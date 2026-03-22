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
# Diagnostic R2-D2 — lit les logs Master + Slave et teste les servos via API
# Usage: bash scripts/check_logs.sh
# Options: --tail 50   (nb de lignes de log, défaut 80)
#          --servo     (envoie aussi une commande test servo via API)

MASTER=artoo@r2-master.local
SLAVE=artoo@r2-slave.local
MASTER_IP=192.168.4.1
TAIL=${2:-80}

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

sep() { echo -e "\n${CYAN}══════════════════════════════════════════════${NC}"; }
ok()  { echo -e "${GREEN}✓${NC} $1"; }
err() { echo -e "${RED}✗${NC} $1"; }
warn(){ echo -e "${YELLOW}⚠${NC} $1"; }

sep
echo -e "${CYAN}  R2-D2 Diagnostic — $(date '+%H:%M:%S')${NC}"
sep

# ──────────────────────────────────────────────
# 1. Statut des services
# ──────────────────────────────────────────────
echo ""
echo "=== SERVICES ==="
ssh -o ConnectTimeout=5 $MASTER "systemctl is-active r2d2-master" 2>/dev/null \
    | grep -q "active" && ok "r2d2-master.service ACTIF" || err "r2d2-master.service INACTIF"

ssh -o ConnectTimeout=5 $SLAVE "systemctl is-active r2d2-slave" 2>/dev/null \
    | grep -q "active" && ok "r2d2-slave.service ACTIF"  || err "r2d2-slave.service INACTIF"

# ──────────────────────────────────────────────
# 2. API Flask — status
# ──────────────────────────────────────────────
echo ""
echo "=== API FLASK (Master :5000) ==="
STATUS=$(curl -s --max-time 5 http://$MASTER_IP:5000/status 2>/dev/null)
if [ -n "$STATUS" ]; then
    ok "Flask répond"
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
    err "Flask ne répond pas (service down ou réseau ?)"
fi

# ──────────────────────────────────────────────
# 3. I2C — vérifier que les chips répondent
# ──────────────────────────────────────────────
echo ""
echo "=== I2C ==="
I2C_MASTER=$(ssh -o ConnectTimeout=5 $MASTER "sudo /usr/sbin/i2cdetect -y 1 2>&1" 2>/dev/null)
if echo "$I2C_MASTER" | grep -q "40"; then
    ok "Master  PCA9685 @ 0x40 détecté"
else
    err "Master  PCA9685 @ 0x40 NON DÉTECTÉ"
fi

I2C_SLAVE=$(ssh -o ConnectTimeout=5 $SLAVE "sudo /usr/sbin/i2cdetect -y 1 2>/dev/null" 2>/dev/null)
if echo "$I2C_SLAVE" | grep -q "41"; then
    ok "Slave   PCA9685 @ 0x41 détecté"
else
    err "Slave   PCA9685 @ 0x41 NON DÉTECTÉ"
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
# 5. Logs Master — dernières lignes + erreurs
# ──────────────────────────────────────────────
echo ""
sep
echo -e "${CYAN}  LOGS MASTER — dernières $TAIL lignes${NC}"
sep
# Lire les logs master directement (pas de SSH — on est déjà sur le master)
sudo journalctl -u r2d2-master -b --no-pager -n $TAIL --output=short-iso 2>/dev/null \
    | grep -iE "servo|dome|pca|smbus|error|warn|prêt|setup|Erreur" \
    | tail -40

echo ""
echo "--- Lignes traceback / exception ---"
sudo journalctl -u r2d2-master -b --no-pager -n $TAIL --output=short-iso 2>/dev/null \
    | grep -iE "traceback|Exception|NoneType|AttributeError|TypeError" | tail -20

# ──────────────────────────────────────────────
# 6. Logs Slave — dernières lignes + erreurs
# ──────────────────────────────────────────────
echo ""
sep
echo -e "${CYAN}  LOGS SLAVE — dernières $TAIL lignes${NC}"
sep
ssh -o ConnectTimeout=5 $SLAVE \
    "sudo journalctl -u r2d2-slave -b --no-pager -n $TAIL --output=short-iso 2>/dev/null" 2>/dev/null \
    | grep -iE "servo|SRV|pca|smbus|error|warn|prêt|setup|Erreur" \
    | tail -40

echo ""
echo "--- Lignes traceback / exception ---"
ssh -o ConnectTimeout=5 $SLAVE \
    "sudo journalctl -u r2d2-slave -b --no-pager -n $TAIL --output=short-iso 2>/dev/null" 2>/dev/null \
    | grep -iE "traceback|Exception|NoneType|AttributeError|TypeError" | tail -20

# ──────────────────────────────────────────────
# 7. Registres PCA9685 — état actuel (MODE1)
# ──────────────────────────────────────────────
echo ""
echo "=== MODE1 PCA9685 (état sleep/wake) ==="
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
