# R2-D2 — Guide d'installation

> 🇬🇧 **[Read in English →](HOWTO.md)** *(recommended — more up to date)*

Tout est automatisé. L'installation complète = **3 commandes + 2 reboots**.

---

## Prérequis matériel

| Composant | Master (dôme) | Slave (corps) |
|-----------|--------------|---------------|
| Pi | Pi 4B 4GB | Pi 4B 2GB |
| OS | Raspberry Pi OS Lite 64-bit Trixie | idem |
| WiFi | wlan0 intégré + **clé USB WiFi** (wlan1) | wlan0 intégré |

> Le Master a besoin d'une clé USB WiFi (wlan1) : wlan0 devient le hotspot
> pour le Slave et les télécommandes, wlan1 reste connecté à internet pour git.

---

## Étape 0 — Graver les deux cartes SD

Utiliser **Raspberry Pi Imager** → cliquer ⚙️ Options avant d'écrire :

| Paramètre | Master | Slave |
|-----------|--------|-------|
| Username | `artoo` | `artoo` |
| Password | (ton choix — même des deux côtés recommandé) | idem |
| Hostname | `r2-master` | `r2-slave` |
| WiFi | ton réseau maison | ton réseau maison |
| SSH | activé | activé |

Les deux Pi démarrent connectés à ton WiFi maison sur wlan0.
Trouver leurs IPs dans ton routeur, ou utiliser `r2-master.local` / `r2-slave.local`.

---

## Étape 1 — Installer le Master

Brancher la clé USB WiFi dans le Master, puis se connecter en SSH depuis le PC :

```bash
ssh artoo@r2-master.local
# ou : ssh artoo@<IP_MASTER>  si .local ne résout pas
```

Lancer l'installateur en une ligne :

```bash
curl -fsSL https://raw.githubusercontent.com/RickDnamps/R2D2_Control/main/scripts/setup_master.sh | sudo bash
```

Le script gère tout automatiquement :
- Mise à jour système + paquets
- Clone du repo git
- Fix UART (`miniuart-bt` — le Bluetooth reste actif pour la manette)
- Activation UART matériel + I2C
- Dépendances Python
- `local.cfg` créé depuis le template exemple
- Reconfiguration WiFi : wlan0 → hotspot `R2D2_Control` (192.168.4.1), wlan1 → internet maison
- Génération clé SSH Ed25519 (pour rsync Master → Slave)
- Services systemd installés et activés

**À la fin il demande de rebooter — répondre Y.**

Après le reboot, le hotspot `R2D2_Control` est actif.
Le SSH utilise maintenant l'IP du hotspot :

```bash
ssh artoo@192.168.4.1
```

---

## Étape 2 — Installer le Slave

**Pendant que le Slave est encore sur le WiFi maison** (avant de rejoindre le hotspot), se connecter en SSH :

```bash
ssh artoo@r2-slave.local
# ou : ssh artoo@<IP_SLAVE>
```

Lancer l'installateur en une ligne :

```bash
curl -fsSL https://raw.githubusercontent.com/RickDnamps/R2D2_Control/main/scripts/setup_slave.sh | sudo bash
```

Le script gère tout automatiquement :
- Mise à jour système + paquets (mpg123, alsa-utils, i2c-tools, python3-smbus)
- Fix UART (`disable-bt`)
- Activation UART matériel + I2C
- Dépendances Python (pyserial, smbus2, adafruit-pca9685)
- WiFi : connexion wlan0 au hotspot `R2D2_Control`
- Audio ALSA : sortie jack 3.5mm, volume 100%

**À la fin il demande de rebooter — répondre Y.**

Le Slave est maintenant connecté au hotspot Master à `192.168.4.171`.

---

## Étape 3 — Premier déploiement du code (depuis le Master)

Se connecter en SSH au Master :

```bash
ssh artoo@192.168.4.1
```

Lancer le premier déploiement :

```bash
bash /home/artoo/r2d2/scripts/deploy.sh --first-install
```

Cela :
- rsync tout le code vers le Slave
- Installe les dépendances pip sur le Slave
- Installe et active le service systemd `r2d2-slave`
- Redémarre le Slave

Puis copier la clé SSH vers le Slave (active le rsync sans mot de passe pour les futures mises à jour) :

```bash
ssh-copy-id artoo@r2-slave.local
```

**Terminé.** R2-D2 est opérationnel.

---

## Connexion au dashboard

1. Connecter son téléphone / tablette / PC au hotspot WiFi : **R2D2_Control**
2. Ouvrir un navigateur : **http://192.168.4.1:5000**

L'application Android se connecte automatiquement sur le même hotspot.

---

## Utilisation quotidienne

### Accès SSH

```bash
# Depuis n'importe quel appareil sur le hotspot R2D2_Control :
ssh artoo@192.168.4.1    # Master (dôme)
ssh artoo@192.168.4.171  # Slave (corps)

# Depuis le Master, rejoindre le Slave :
ssh artoo@r2-slave.local
```

> Ne pas utiliser les hostnames `.local` depuis Windows — mDNS peu fiable.
> Utiliser les IPs fixes ci-dessus.

### Mettre à jour R2-D2

**Depuis le dashboard :** onglet Config → System → bouton Update (git pull + rsync + restart, tout automatique).

**Ou depuis SSH sur le Master :**

```bash
bash /home/artoo/r2d2/scripts/update.sh
```

Fait : backup séquences → git pull → rsync vers Slave → restart Slave → restart Master → vérification services.

### Vérifier l'état des services

```bash
# Sur le Master :
sudo systemctl status r2d2-master
sudo journalctl -u r2d2-master -f

# Sur le Slave (depuis le Master) :
ssh artoo@r2-slave.local sudo systemctl status r2d2-slave
ssh artoo@r2-slave.local sudo journalctl -u r2d2-slave -f
```

### Collecter les logs de debug

```bash
bash /home/artoo/r2d2/scripts/check_logs.sh
bash /home/artoo/r2d2/scripts/debug_collect.sh
```

### Resynchroniser le Slave seulement (sans git pull)

```bash
bash /home/artoo/r2d2/scripts/resync_slave.sh
```

---

## Câblage matériel

Voir [ELECTRONICS.md](ELECTRONICS.md) pour tous les détails de câblage :
- UART slip ring
- Contrôleurs servos PCA9685 (I2C)
- Contrôleurs moteurs VESC (USB + CAN)
- LED logic Teeces32 / AstroPixels+
- Écran RP2040

---

## Firmware écran RP2040

Flasher manuellement via `mpremote` (seulement après remplacement matériel ou reset firmware) :

```bash
# SSH sur le Slave :
ssh artoo@r2-slave.local

# Flasher (toujours rm avant cp — mpremote compare les timestamps, pas le contenu) :
python3 -m mpremote connect /dev/ttyACM0 rm :display.py
python3 -m mpremote connect /dev/ttyACM0 cp /home/artoo/r2d2/rp2040/firmware/display.py :display.py
```

Ou utiliser le script dédié depuis le Master :

```bash
bash /home/artoo/r2d2/scripts/deploy_rp2040.sh
```

---

## Appairage manette Bluetooth

Depuis le dashboard : **onglet Config → Bluetooth** → Scan → appairer la manette.

Ou manuellement sur le Master :

```bash
bluetoothctl
> power on
> scan on
# attendre que la manette apparaisse
> pair XX:XX:XX:XX:XX:XX
> trust XX:XX:XX:XX:XX:XX
> connect XX:XX:XX:XX:XX:XX
> quit
```

La manette se reconnecte automatiquement au prochain démarrage.

> **Niveau de batterie :** supporté pour les manettes PS4, PS5 et Xbox.
> La manette NVIDIA Shield n'expose pas la batterie via les interfaces Linux standard.

---

## Scripts disponibles

| Script | Où l'exécuter | Rôle |
|--------|--------------|------|
| `scripts/setup_master.sh` | Master (une fois) | Installation complète Master |
| `scripts/setup_slave.sh` | Slave (une fois) | Installation complète Slave |
| `scripts/deploy.sh --first-install` | Master (une fois) | Premier push de code vers le Slave |
| `scripts/update.sh` | Master | git pull + mise à jour complète |
| `scripts/resync_slave.sh` | Master | rsync vers Slave seulement |
| `scripts/check_logs.sh` | Master | Voir les logs des services |
| `scripts/debug_collect.sh` | Master | Collecter un bundle de debug |
| `scripts/deploy_rp2040.sh` | Master | Flasher le firmware RP2040 |
| `scripts/test_uart.sh` | Master | Tester le lien UART vers le Slave |
| `scripts/test_servos.sh` | Master | Tester les servos |
| `scripts/stop_servos.sh` | Master | Arrêt d'urgence servos |

---

## Référence réseau

| Hôte | IP | Accès depuis |
|------|----|-------------|
| Master | `192.168.4.1` | tout appareil sur le hotspot |
| Slave | `192.168.4.171` | tout appareil sur le hotspot |
| Dashboard | `http://192.168.4.1:5000` | navigateur sur le hotspot |
| SSH Master | `ssh artoo@192.168.4.1` | mot de passe : `deetoo` |
| SSH Slave | `ssh artoo@192.168.4.171` | mot de passe : `deetoo` |
