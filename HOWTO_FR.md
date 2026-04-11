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

## Câblage UART — connecter les deux Pi avant toute chose

Le Master et le Slave communiquent via un **lien série UART physique** à 115200 baud.
Sans ce câble, rien ne fonctionne : pas de heartbeat → le watchdog du Slave coupe les moteurs
après 500ms, pas de commandes audio, pas de servos, pas de télémétrie.

**Connecter 3 fils entre les deux Pi :**

```
Master Pi 4B              Slave Pi 4B
─────────────────         ─────────────────
Pin 8  GPIO14 TX  ──────→  Pin 10 GPIO15 RX
Pin 10 GPIO15 RX  ←──────  Pin 8  GPIO14 TX
Pin 6  GND        ─────── Pin 6  GND
```

> Les deux Pi 4B utilisent du GPIO 3.3V — pas de convertisseur de niveau nécessaire.
> Utiliser des fils jumper femelle-femelle pour les tests sur établi.
> Dans le robot assemblé, ces 3 fils passent par le slip ring (fils 7, 8 et GND).

**Plan de la broche GPIO (numérotation physique du connecteur) :**

```
 Connecteur GPIO Pi (vu de dessus, ports USB en bas)
 ┌─────┬─────┐
 │ 3V3 │ 5V  │  ← broches 1, 2
 │ SDA │ 5V  │  ← broches 3, 4
 │ SCL │ GND │  ← broches 5, 6  ← GND ici
 │  4  │ 14  │  ← broches 7, 8  ← TX ici (GPIO14)
 │ GND │ 15  │  ← broches 9, 10 ← RX ici (GPIO15)
 │ 17  │ 18  │
 ...
```

Le port UART utilisé est `/dev/ttyAMA0` (UART matériel, libéré du Bluetooth par les scripts d'install).

> **Test sur établi sans le robot assemblé ?**
> Poser les deux Pi côte à côte et utiliser des fils jumper de 10cm.
> Le système fonctionne exactement pareil — le slip ring n'est qu'une version plus longue des mêmes 3 fils.

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

**Avant de lancer l'installateur**, noter l'IP actuelle du Master sur le réseau maison —
elle sera utile pour se reconnecter après le reboot :

```bash
hostname -I
# exemple : 192.168.1.42  — noter cette valeur
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

---

### Après le reboot — se reconnecter au Master

Après le reboot, le WiFi du Master a changé :

```
Avant :  wlan0 → WiFi maison  (accessible depuis ton PC)
Après :  wlan0 → hotspot R2D2_Control  192.168.4.1  (seulement depuis le hotspot)
         wlan1 → WiFi maison  (nouvelle IP assignée par le routeur)
```

Ton PC est encore sur le réseau maison, donc **deux options** pour se reconnecter :

**Option A — Connecter le PC au hotspot R2D2_Control (recommandé)**

1. Sur ton PC, se connecter au réseau WiFi : **R2D2_Control**
2. SSH avec l'IP fixe du hotspot :
   ```bash
   ssh artoo@192.168.4.1
   ```
   Cette IP ne change jamais — c'est celle à utiliser pour tous les SSH futurs.

**Option B — Rester sur le réseau maison, utiliser la nouvelle IP de wlan1**

Le wlan1 du Master reçoit une nouvelle IP DHCP depuis ton routeur.
La trouver via :
- La page admin du routeur (chercher `r2-master`)
- Essayer : `ssh artoo@r2-master.local` (fonctionne sur Linux/Mac via mDNS, peu fiable sur Windows)
- Un scanner réseau (ex : Fing sur téléphone, Angry IP Scanner sur PC)

> L'option A est plus simple et c'est ce qu'on utilise en permanence — l'IP 192.168.4.1 est fixe pour toujours.
> Basculer dessus maintenant, plus besoin de chercher des IPs ensuite.

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

Se connecter en SSH au Master avec la même méthode qu'à l'étape 1 :

- **Option A (hotspot) :** ton PC est sur `R2D2_Control` → `ssh artoo@192.168.4.1`
- **Option B (réseau maison) :** `ssh artoo@r2-master.local` ou l'IP trouvée dans le routeur

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

Flask écoute sur toutes les interfaces réseau — pas besoin de changer de WiFi, le dashboard est accessible **depuis les deux réseaux**.

**Depuis le WiFi maison (le plus pratique — rester sur son réseau normal) :**

Trouver l'IP de wlan1 du Master (celle assignée par le routeur) :
- Dans la page admin du routeur (chercher `r2-master`)
- Ou en SSH sur le Master : `hostname -I` — la deuxième IP est wlan1
- Ou essayer directement dans un navigateur : `http://r2-master.local:5000` (fonctionne sur Linux/Mac/Android)

Puis ouvrir : `http://<IP-wlan1>:5000`

> Cette IP peut changer si le routeur la réassigne. Pour la figer, créer un bail DHCP statique dans les paramètres du routeur pour l'adresse MAC du Master.

**Depuis le hotspot R2D2_Control (IP fixe, toujours disponible — idéal en convention) :**

Se connecter au WiFi **R2D2_Control**, puis ouvrir : **http://192.168.4.1:5000**

**L'application Android** détecte automatiquement le Master sur le réseau auquel elle est connectée.

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
