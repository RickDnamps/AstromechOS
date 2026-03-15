#!/bin/bash
# setup_ssh_keys.sh — SSH sans mot de passe R2-Master → R2-Slave
# À lancer depuis le R2-Master (Pi 4B) après que le hotspot soit actif
# et que le R2-Slave soit connecté (hostname: r2-slave.local)
#
# Usage: bash setup_ssh_keys.sh

set -e

SLAVE_USER="artoo"
SLAVE_HOST="r2-slave.local"

echo "=== Génération clé SSH (si absente) ==="
if [ ! -f ~/.ssh/id_ed25519 ]; then
    ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519
    echo "Clé générée: ~/.ssh/id_ed25519"
else
    echo "Clé existante: ~/.ssh/id_ed25519"
fi

echo "=== Copie clé publique vers R2-Slave ==="
echo "Vous allez devoir entrer le mot de passe de R2-Slave une dernière fois."
ssh-copy-id -i ~/.ssh/id_ed25519.pub "${SLAVE_USER}@${SLAVE_HOST}"

echo "=== Test connexion SSH sans mot de passe ==="
if ssh -o BatchMode=yes -o ConnectTimeout=5 "${SLAVE_USER}@${SLAVE_HOST}" echo "OK"; then
    echo ""
    echo "=== SSH sans mot de passe configuré avec succès ==="
    echo "  R2-Master → R2-Slave (${SLAVE_HOST}) : OK"
else
    echo "ERREUR: connexion SSH sans mot de passe échouée"
    exit 1
fi
