#!/bin/bash
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
