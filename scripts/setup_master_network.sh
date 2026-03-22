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
# =============================================================================
# setup_master_network.sh — Configuration réseau R2-D2 Master
# =============================================================================
#
# ⚠️  INSTALLER LE MASTER EN PREMIER — avant le Slave.
#     Le Slave a besoin des credentials du hotspot Master pour se configurer.
#
# Ce script doit être exécuté UNE SEULE FOIS sur le R2-Master.
#
# Ce qu'il fait :
#   1. Lit les credentials WiFi maison déjà configurés sur wlan0
#   2. Demande le SSID/mot de passe du hotspot R2-D2 (personnalisable)
#   3. Sauvegarde tout dans local.cfg (survit aux git pull)
#   4. Configure wlan1 (clé USB) pour se connecter au WiFi maison
#   5. Convertit wlan0 en point d'accès (192.168.4.1)
#
# Résultat final :
#   wlan0  → Hotspot R2-D2            192.168.4.1  (Slave + télécommande)
#   wlan1  → WiFi maison              DHCP         (git pull / GitHub)
#
# Prérequis :
#   - Raspberry Pi OS Bookworm 64-bit Lite (NetworkManager actif)
#   - Pi connecté au WiFi maison via wlan0 (configuré via Imager)
#   - Clé USB WiFi branchée (sera wlan1) OU brancher plus tard
#
# Usage :
#   sudo bash /home/artoo/r2d2/scripts/setup_master_network.sh
#
# Note le SSID et mot de passe du hotspot — tu en auras besoin
# pour configurer le Slave avec setup_slave_network.sh.
#
# =============================================================================

set -e

REPO_PATH="/home/artoo/r2d2"
LOCAL_CFG="${REPO_PATH}/master/config/local.cfg"
LOCAL_CFG_EXAMPLE="${REPO_PATH}/master/config/local.cfg.example"

# Valeurs par défaut du hotspot (modifiables interactivement)
HOTSPOT_SSID="R2D2_Control"
HOTSPOT_PASS="r2d2droid"
HOTSPOT_IP="192.168.4.1/24"
HOTSPOT_CON="r2d2-hotspot"
INTERNET_CON="r2d2-internet"

# Couleurs
RED='\033[0;31m'
GRN='\033[0;32m'
YEL='\033[1;33m'
BLU='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLU}[INFO]${NC}  $*"; }
ok()    { echo -e "${GRN}[ OK ]${NC}  $*"; }
warn()  { echo -e "${YEL}[WARN]${NC}  $*"; }
die()   { echo -e "${RED}[ERR ]${NC}  $*" >&2; exit 1; }

# =============================================================================
echo ""
echo -e "${BLU}========================================${NC}"
echo -e "${BLU}  R2-D2 Master — Configuration réseau  ${NC}"
echo -e "${BLU}========================================${NC}"
echo ""

# --- Vérification root ---
[[ $EUID -eq 0 ]] || die "Ce script doit être exécuté avec sudo"

# --- Vérification NetworkManager ---
if ! systemctl is-active --quiet NetworkManager; then
    die "NetworkManager n'est pas actif. Bookworm requis.\n    sudo systemctl enable --now NetworkManager"
fi
ok "NetworkManager actif"

# --- Vérification repo ---
[[ -d "$REPO_PATH" ]] || die "Repo introuvable: $REPO_PATH\n    Cloner d'abord: git clone ... $REPO_PATH"

# =============================================================================
# ÉTAPE 1 — Récupérer les credentials WiFi maison depuis wlan0
# =============================================================================
echo ""
info "Étape 1 — Lecture des credentials WiFi maison (wlan0 actuel)..."

HOME_SSID=""
HOME_PASS=""

# Trouver le nom de connexion active sur wlan0
WLAN0_CON=$(nmcli -g GENERAL.CONNECTION device show wlan0 2>/dev/null | tr -d ' ')

if [[ -n "$WLAN0_CON" && "$WLAN0_CON" != "--" ]]; then
    info "Connexion active sur wlan0 : '$WLAN0_CON'"

    # Extraire SSID
    HOME_SSID=$(nmcli -g 802-11-wireless.ssid connection show "$WLAN0_CON" 2>/dev/null | tr -d ' ')

    # Extraire mot de passe (requiert sudo, déjà root ici)
    HOME_PASS=$(nmcli -s -g 802-11-wireless-security.psk connection show "$WLAN0_CON" 2>/dev/null | tr -d ' ')

    if [[ -n "$HOME_SSID" ]]; then
        ok "SSID détecté : '$HOME_SSID'"
    fi
    if [[ -n "$HOME_PASS" ]]; then
        ok "Mot de passe récupéré (masqué)"
    else
        warn "Mot de passe non trouvé automatiquement (réseau ouvert ou format inconnu)"
    fi
else
    warn "Aucune connexion active sur wlan0"
fi

# --- Demander confirmation ou saisie manuelle ---
echo ""
if [[ -n "$HOME_SSID" ]]; then
    read -r -p "Utiliser le WiFi '${HOME_SSID}' pour wlan1 (internet) ? [O/n] " CONFIRM
    if [[ "$CONFIRM" =~ ^[Nn] ]]; then
        HOME_SSID=""
        HOME_PASS=""
    fi
fi

if [[ -z "$HOME_SSID" ]]; then
    echo ""
    info "Saisie manuelle des credentials WiFi maison :"
    read -r -p "  SSID (nom du réseau WiFi) : " HOME_SSID
    [[ -n "$HOME_SSID" ]] || die "SSID vide — abandon"
    read -r -s -p "  Mot de passe WiFi        : " HOME_PASS
    echo ""
fi

# =============================================================================
# ÉTAPE 1b — Configurer le hotspot R2-D2 (SSID + mot de passe)
# =============================================================================
echo ""
echo -e "${BLU}--- Hotspot R2-D2 (point d'accès pour le Slave et la télécommande) ---${NC}"
echo ""
echo    "  Le R2-Master va créer un réseau WiFi auquel le Slave se connectera."
echo    "  Tu peux personnaliser le nom et le mot de passe, ou garder les défauts."
echo ""
read -r -p "  SSID du hotspot     [${HOTSPOT_SSID}] : " INPUT
[[ -n "$INPUT" ]] && HOTSPOT_SSID="$INPUT"

while true; do
    read -r -s -p "  Mot de passe hotspot [${HOTSPOT_PASS}] : " INPUT
    echo ""
    if [[ -z "$INPUT" ]]; then
        break   # garder le défaut
    fi
    if [[ ${#INPUT} -lt 8 ]]; then
        warn "Le mot de passe WPA doit faire au moins 8 caractères — réessayer"
    else
        HOTSPOT_PASS="$INPUT"
        break
    fi
done

echo ""
ok "Hotspot configuré : SSID='${HOTSPOT_SSID}'  (mot de passe enregistré)"
echo ""
echo -e "  ${YEL}⚠  Note ces informations — tu en auras besoin pour le Slave :${NC}"
echo    "     SSID     : ${HOTSPOT_SSID}"
echo    "     Password : ${HOTSPOT_PASS}"
echo ""

# =============================================================================
# ÉTAPE 2 — Sauvegarder dans local.cfg
# =============================================================================
echo ""
info "Étape 2 — Sauvegarde dans local.cfg..."

# Créer local.cfg depuis l'exemple s'il n'existe pas encore
if [[ ! -f "$LOCAL_CFG" ]]; then
    if [[ -f "$LOCAL_CFG_EXAMPLE" ]]; then
        cp "$LOCAL_CFG_EXAMPLE" "$LOCAL_CFG"
        chown artoo:artoo "$LOCAL_CFG"
        info "local.cfg créé depuis l'exemple"
    else
        die "local.cfg.example introuvable : $LOCAL_CFG_EXAMPLE"
    fi
fi

# Fonction pour écrire/mettre à jour une clé dans une section .cfg
cfg_set() {
    local file="$1" section="$2" key="$3" value="$4"
    # Vérifier si la section existe
    if grep -q "^\[${section}\]" "$file"; then
        # Mettre à jour ou ajouter la clé dans la section
        if grep -q "^${key}\s*=" "$file"; then
            sed -i "s|^${key}\s*=.*|${key} = ${value}|" "$file"
        else
            sed -i "/^\[${section}\]/a ${key} = ${value}" "$file"
        fi
    else
        # Ajouter la section entière
        echo "" >> "$file"
        echo "[${section}]" >> "$file"
        echo "${key} = ${value}" >> "$file"
    fi
}

cfg_set "$LOCAL_CFG" "home_wifi" "ssid"     "$HOME_SSID"
cfg_set "$LOCAL_CFG" "home_wifi" "password" "$HOME_PASS"
cfg_set "$LOCAL_CFG" "hotspot"   "ssid"     "$HOTSPOT_SSID"
cfg_set "$LOCAL_CFG" "hotspot"   "password" "$HOTSPOT_PASS"
chown artoo:artoo "$LOCAL_CFG"

ok "Credentials WiFi maison sauvegardés dans local.cfg [home_wifi]"
ok "Credentials hotspot sauvegardés dans local.cfg [hotspot]"

# =============================================================================
# ÉTAPE 3 — Configurer wlan1 (clé USB) pour le WiFi maison
# =============================================================================
echo ""
info "Étape 3 — Configuration wlan1 → WiFi maison '$HOME_SSID'..."

# Supprimer l'ancienne connexion r2d2-internet si elle existe
if nmcli connection show "$INTERNET_CON" &>/dev/null; then
    nmcli connection delete "$INTERNET_CON"
    info "Ancienne connexion '$INTERNET_CON' supprimée"
fi

# Créer la connexion wlan1
if [[ -n "$HOME_PASS" ]]; then
    nmcli connection add \
        type wifi \
        ifname wlan1 \
        con-name "$INTERNET_CON" \
        ssid "$HOME_SSID" \
        wifi-sec.key-mgmt wpa-psk \
        wifi-sec.psk "$HOME_PASS" \
        connection.autoconnect yes \
        connection.autoconnect-priority 10
else
    # Réseau ouvert
    nmcli connection add \
        type wifi \
        ifname wlan1 \
        con-name "$INTERNET_CON" \
        ssid "$HOME_SSID" \
        connection.autoconnect yes \
        connection.autoconnect-priority 10
fi

ok "Connexion '$INTERNET_CON' créée pour wlan1"

# Tenter de la démarrer si wlan1 existe déjà
if ip link show wlan1 &>/dev/null; then
    info "wlan1 détecté — connexion en cours..."
    nmcli connection up "$INTERNET_CON" && ok "wlan1 connecté à '$HOME_SSID'" \
        || warn "Connexion wlan1 échouée — vérifie que la clé USB WiFi est branchée"
else
    warn "wlan1 non détecté maintenant — la connexion s'activera automatiquement au prochain branchement de la clé USB"
fi

# =============================================================================
# ÉTAPE 4 — Supprimer la connexion wlan0 maison et créer le hotspot
# =============================================================================
echo ""
info "Étape 4 — Conversion wlan0 en hotspot '$HOTSPOT_SSID'..."

# Supprimer l'ancienne connexion hotspot si elle existe
if nmcli connection show "$HOTSPOT_CON" &>/dev/null; then
    nmcli connection delete "$HOTSPOT_CON"
    info "Ancien hotspot supprimé"
fi

# Supprimer la connexion WiFi maison de wlan0 pour libérer l'interface
if [[ -n "$WLAN0_CON" && "$WLAN0_CON" != "--" ]]; then
    # Désactiver d'abord, puis configurer pour ne plus être prioritaire
    # On NE supprime PAS — NetworkManager sera redirigé via autoconnect
    nmcli connection modify "$WLAN0_CON" connection.interface-name wlan1 2>/dev/null || true
    info "Connexion '$WLAN0_CON' redirigée vers wlan1"
fi

# Créer le hotspot sur wlan0
nmcli connection add \
    type wifi \
    ifname wlan0 \
    con-name "$HOTSPOT_CON" \
    ssid "$HOTSPOT_SSID" \
    mode ap \
    wifi-sec.key-mgmt wpa-psk \
    wifi-sec.psk "$HOTSPOT_PASS" \
    ipv4.method shared \
    ipv4.addresses "$HOTSPOT_IP" \
    ipv6.method disabled \
    connection.autoconnect yes \
    connection.autoconnect-priority 100

ok "Hotspot '$HOTSPOT_CON' créé sur wlan0"

# Activer le hotspot
nmcli connection up "$HOTSPOT_CON" && ok "Hotspot démarré sur wlan0" \
    || warn "Démarrage hotspot différé au reboot"

# =============================================================================
# ÉTAPE 5 — Avahi pour résolution .local
# =============================================================================
echo ""
info "Étape 5 — Vérification avahi-daemon (.local DNS)..."

if ! command -v avahi-daemon &>/dev/null; then
    apt-get install -y avahi-daemon -qq
fi
systemctl enable --now avahi-daemon
ok "avahi-daemon actif (r2-master.local / r2-slave.local)"

# =============================================================================
# RÉSUMÉ
# =============================================================================
echo ""
echo -e "${GRN}========================================${NC}"
echo -e "${GRN}  Master réseau configuré ✓             ${NC}"
echo -e "${GRN}========================================${NC}"
echo ""
echo -e "  ${BLU}wlan0${NC} → Hotspot R2-D2 (point d'accès)"
echo    "         SSID     : ${HOTSPOT_SSID}"
echo    "         Password : ${HOTSPOT_PASS}"
echo    "         IP fixe  : 192.168.4.1"
echo ""
echo -e "  ${BLU}wlan1${NC} → WiFi maison / internet (clé USB)"
echo    "         SSID     : ${HOME_SSID}"
echo    "         (connexion automatique au branchement)"
echo ""
echo -e "  ${BLU}Sauvegardé dans${NC} : ${LOCAL_CFG}"
echo    "    [home_wifi]  ssid / password"
echo    "    [hotspot]    ssid / password"
echo ""
echo -e "  ${YEL}══════════════════════════════════════${NC}"
echo -e "  ${YEL}  INFOS POUR CONFIGURER LE SLAVE :     ${NC}"
echo -e "  ${YEL}══════════════════════════════════════${NC}"
echo    ""
echo    "  Sur le R2-Slave, tu auras besoin de :"
echo -e "  ${GRN}  Hotspot SSID     : ${HOTSPOT_SSID}${NC}"
echo -e "  ${GRN}  Hotspot Password : ${HOTSPOT_PASS}${NC}"
echo    ""
echo    "  Commande Slave (après reboot Master) :"
echo    "  sudo bash /home/artoo/r2d2/scripts/setup_slave_network.sh"
echo    ""
echo -e "  ${YEL}Prochaines étapes :${NC}"
echo    "    1. Brancher la clé USB WiFi sur le Master (si pas encore fait)"
echo    "    2. sudo reboot"
echo    "    3. Configurer le Slave : setup_slave_network.sh"
echo ""
