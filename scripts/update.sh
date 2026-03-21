#!/bin/bash
# update.sh — Mise à jour complète R2-D2 : git pull + rsync Slave + restart tout
# Usage: bash scripts/update.sh
# À exécuter sur le Master (r2-master.local)
#
# Ce script :
#   1. Git pull (si wlan1 dispo)
#   2. Vérifie la connectivité Slave
#   3. Rsync slave/ + shared/ + scripts/ + rp2040/ vers le Slave
#   4. Redémarre le service Slave
#   5. Redémarre le service Master (watchdogs app + motion inclus)
#   6. Vérifie que les services sont actifs

REPO=/home/artoo/r2d2
SLAVE=artoo@r2-slave.local
SSH="ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10"
VERSION_FILE=$REPO/VERSION
ERRORS=0

# ──────────────────────────────────────────────
# Helpers affichage
# ──────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; ERRORS=$((ERRORS+1)); }
step() { echo -e "\n${CYAN}[$1]${NC} $2"; }

echo -e "${CYAN}"
echo "  ██████╗ ██████╗    ██████╗ ██████╗ "
echo "  ██╔══██╗╚════██╗   ██╔══██╗╚════██╗"
echo "  ██████╔╝ █████╔╝   ██║  ██║ █████╔╝"
echo "  ██╔══██╗██╔═══╝    ██║  ██║██╔═══╝ "
echo "  ██║  ██║███████╗   ██████╔╝███████╗"
echo "  ╚═╝  ╚═╝╚══════╝   ╚═════╝ ╚══════╝"
echo -e "         UPDATE SYSTEM${NC}"
echo "  ────────────────────────────────────"

# ──────────────────────────────────────────────
# 1. Git pull
# ──────────────────────────────────────────────
step "1/6" "Git pull"
if ip addr show wlan1 2>/dev/null | grep -q "inet "; then
    cd "$REPO"
    OUTPUT=$(git pull --ff-only 2>&1)
    if echo "$OUTPUT" | grep -q "error\|fatal"; then
        fail "git pull échoué : $OUTPUT"
    else
        # Toujours mettre à jour le VERSION file avec le HEAD réel
        git rev-parse --short HEAD > "$VERSION_FILE"
        if echo "$OUTPUT" | grep -q "Already up to date"; then
            ok "Déjà à jour — $(cat $VERSION_FILE)"
        else
            ok "Mis à jour → version: $(cat $VERSION_FILE)"
        fi
    fi
else
    warn "wlan1 non disponible — git pull ignoré, version locale utilisée"
fi

# ──────────────────────────────────────────────
# 2. Vérifier le Slave
# ──────────────────────────────────────────────
step "2/6" "Connexion Slave"
if ! $SSH $SLAVE "echo ok" > /dev/null 2>&1; then
    fail "Slave inaccessible — vérifier le Wi-Fi hotspot"
    echo -e "\n${RED}Arrêt — Slave requis pour continuer.${NC}"
    exit 1
fi
ok "Slave joignable ($SLAVE)"

# ──────────────────────────────────────────────
# 3. Rsync vers le Slave
# ──────────────────────────────────────────────
step "3/6" "Sync code vers Slave"

rsync -az --delete \
    -e "$SSH" \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='sounds/*.mp3' \
    --exclude='vendor/' \
    "$REPO/slave/" "$SLAVE:$REPO/slave/" 2>&1 \
    && ok "slave/ synchronisé" || fail "rsync slave/ échoué"

rsync -az \
    -e "$SSH" \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    "$REPO/shared/" "$SLAVE:$REPO/shared/" 2>&1 \
    && ok "shared/ synchronisé" || fail "rsync shared/ échoué"

rsync -az \
    -e "$SSH" \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    "$REPO/scripts/" "$SLAVE:$REPO/scripts/" 2>&1 \
    && ok "scripts/ synchronisé" || fail "rsync scripts/ échoué"

rsync -az \
    -e "$SSH" \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    "$REPO/rp2040/" "$SLAVE:$REPO/rp2040/" 2>&1 \
    && ok "rp2040/ synchronisé" || fail "rsync rp2040/ échoué"

rsync -az -e "$SSH" "$VERSION_FILE" "$SLAVE:$VERSION_FILE" 2>/dev/null
ok "VERSION synchronisé → $(cat $VERSION_FILE 2>/dev/null || echo 'unknown')"

# ──────────────────────────────────────────────
# 4. Redémarrer le Slave
# ──────────────────────────────────────────────
step "4/6" "Redémarrage Slave"
if $SSH $SLAVE "sudo systemctl restart r2d2-slave.service" 2>/dev/null; then
    sleep 2
    SLAVE_STATUS=$($SSH $SLAVE "systemctl is-active r2d2-slave.service" 2>/dev/null)
    if [ "$SLAVE_STATUS" = "active" ]; then
        ok "r2d2-slave actif"
    else
        warn "r2d2-slave status: $SLAVE_STATUS"
    fi
else
    warn "systemctl échoué — reboot Slave..."
    $SSH $SLAVE "sudo reboot" 2>/dev/null && ok "Slave en reboot" || fail "Reboot Slave échoué"
fi

# ──────────────────────────────────────────────
# 5. Redémarrer le Master
# ──────────────────────────────────────────────
step "5/6" "Redémarrage Master"

VERSION=$(cat "$VERSION_FILE" 2>/dev/null || echo "unknown")

echo ""
echo "  ────────────────────────────────────"
if [ $ERRORS -eq 0 ]; then
    echo -e "  ${GREEN}✓ Sync OK — version: ${VERSION}${NC}"
else
    echo -e "  ${YELLOW}⚠ Sync avec $ERRORS erreur(s) — version: ${VERSION}${NC}"
fi
echo "  ────────────────────────────────────"
echo ""
echo -e "  ${YELLOW}→ Redémarrage Master dans 3 secondes...${NC}"
echo -e "  ${YELLOW}  (AppWatchdog + MotionWatchdog + SafeStop seront relancés)${NC}"
sleep 3

# Restart Master — r2d2-monitor.service si présent, sinon juste r2d2-master
sudo systemctl restart r2d2-master.service r2d2-monitor.service 2>/dev/null || \
    sudo systemctl restart r2d2-master.service 2>/dev/null || \
    { fail "systemctl non disponible — relance manuelle requise"; exit 1; }

# ──────────────────────────────────────────────
# 6. Vérification post-démarrage
# ──────────────────────────────────────────────
step "6/6" "Vérification services"
sleep 3   # laisser le temps au Master de démarrer Flask

MASTER_STATUS=$(systemctl is-active r2d2-master.service 2>/dev/null)
if [ "$MASTER_STATUS" = "active" ]; then
    ok "r2d2-master actif"
else
    fail "r2d2-master status: $MASTER_STATUS"
fi

SLAVE_STATUS=$($SSH $SLAVE "systemctl is-active r2d2-slave.service" 2>/dev/null)
if [ "$SLAVE_STATUS" = "active" ]; then
    ok "r2d2-slave actif"
elif [ -z "$SLAVE_STATUS" ]; then
    warn "r2d2-slave — impossible de vérifier (SSH timeout)"
else
    fail "r2d2-slave status: $SLAVE_STATUS"
fi

# Vérification API Flask (heartbeat rapide)
if curl -sf --max-time 3 http://localhost:5000/status > /dev/null 2>&1; then
    ok "API Flask répond sur :5000"
else
    warn "API Flask pas encore disponible (normal si boot lent)"
fi

# ──────────────────────────────────────────────
# Résumé final
# ──────────────────────────────────────────────
echo ""
echo "  ════════════════════════════════════"
if [ $ERRORS -eq 0 ]; then
    echo -e "  ${GREEN}✓ R2-D2 opérationnel — version: ${VERSION}${NC}"
else
    echo -e "  ${YELLOW}⚠ Démarré avec $ERRORS erreur(s) — version: ${VERSION}${NC}"
    echo -e "  ${YELLOW}  Vérifier: sudo journalctl -u r2d2-master -n 30${NC}"
fi
echo "  ════════════════════════════════════"
echo ""
