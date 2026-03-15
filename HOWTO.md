# R2-D2 — Guide d'installation complet

> Phase 1 : Infrastructure UART / Heartbeat / Watchdog / Version / Hotspot

---

## Prérequis

- **R2-Master** : Raspberry Pi 4B 4G — Raspberry Pi OS Lite 64-bit (Bookworm) — fraîchement installé
- **R2-Slave** : Raspberry Pi 4B 2G — Raspberry Pi OS Lite 64-bit (Bookworm) — fraîchement installé
- Les deux Pi sont **sur le même réseau Wi-Fi domestique** pour la première installation
- Ton PC peut les joindre en SSH
- Git installé sur ton PC
- **Username sur les deux Pi : `artoo`** (configurer via Raspberry Pi Imager → Options → Username)

---

## Vue d'ensemble

```
ÉTAPE 1 — Préparation des deux Pi (OS, paquets, repo)
ÉTAPE 2 — Pi 4B : hotspot wlan0 + wlan1 internet
ÉTAPE 3 — R2-Master → R2-Slave : SSH sans mot de passe
ÉTAPE 4 — Déploiement du code (rsync initial)
ÉTAPE 5 — Services systemd
ÉTAPE 6 — RP2040 firmware
ÉTAPE 7 — Tests de validation Phase 1
```

---

## ÉTAPE 0 — Configurer local.cfg (OBLIGATOIRE — à faire une seule fois)

`local.cfg` est le fichier de **configuration personnelle** de ton R2-D2.
Il n'est **jamais écrasé par git pull** — c'est là que vivent ton WiFi et ton GitHub.

```bash
# Sur le R2-Master, après le git clone
cd /home/artoo/r2d2/master/config
cp local.cfg.example local.cfg
nano local.cfg
```

Remplir au minimum :
```ini
[github]
repo_url = https://github.com/TON_USER/r2d2.git   # ton repo ou ton fork
branch = main
auto_pull_on_boot = true

[hotspot]
ssid = R2D2_Control     # personnalise si tu veux
password = r2d2droid

[deploy]
button_pin = 17         # BCM pin du bouton dôme

[slave]
host = r2-slave.local
```

> **Fork ?** Change simplement `repo_url` vers ton fork.
> Le Master mettra à jour le remote `origin` automatiquement au prochain git pull.

---

## ÉTAPE 1 — Préparation des deux Pi

### 1.1 — Sur le R2-Master (Pi 4B 4G — Dôme)

```bash
# Connexion SSH (réseau domestique, première fois)
ssh artoo@<IP_R2SLAVE_RESEAU_MAISON>

# Définir le hostname
sudo hostnamectl set-hostname r2-master

# Mise à jour système
sudo apt-get update && sudo apt-get upgrade -y

# Paquets système
sudo apt-get install -y python3-pip python3-serial git rsync

# Dépendances Python
pip3 install -r /home/artoo/r2d2/master/requirements.txt

# Activer UART hardware (désactiver console série)
sudo raspi-config nonint do_serial_hw 0   # active UART hardware
sudo raspi-config nonint do_serial_cons 1  # désactive console sur UART

# Activer I2C
sudo raspi-config nonint do_i2c 0

# Cloner le repo depuis GitHub (adapter l'URL)
git clone https://github.com/<TON_USER>/r2d2.git /home/artoo/r2d2

# Générer le fichier VERSION
cd /home/artoo/r2d2
git rev-parse --short HEAD > /home/artoo/r2d2/VERSION

sudo reboot
```

### 1.2 — Sur le R2-Slave (Pi 4B 2G — Corps)

```bash
# Connexion SSH (réseau domestique, première fois)
ssh artoo@<IP_R2SLAVE_RESEAU_MAISON>

# Définir le hostname
sudo hostnamectl set-hostname r2-slave

# Mise à jour système
sudo apt-get update && sudo apt-get upgrade -y

# Paquets système
sudo apt-get install -y python3-pip python3-serial git

# Dépendances Python (copiées par rsync à l'étape 4)
# pip3 install -r /home/artoo/r2d2/requirements.txt  ← après le premier rsync

# Activer UART hardware
sudo raspi-config nonint do_serial_hw 0
sudo raspi-config nonint do_serial_cons 1

# Activer I2C
sudo raspi-config nonint do_i2c 0

# Créer le dossier du repo (sera rempli par rsync depuis le Master)
mkdir -p /home/artoo/r2d2

sudo reboot
```

---

## ÉTAPE 2 — Hotspot Wi-Fi sur R2-Master

Le R2-Master doit avoir **deux interfaces Wi-Fi** :
- `wlan0` = interface interne → Hotspot permanent "R2D2_Control"
- `wlan1` = clé USB Wi-Fi externe → réseau domestique (git pull)

### 2.1 — Brancher la clé USB Wi-Fi externe

Brancher la clé USB Wi-Fi sur un port USB du R2-Master avant de continuer.

Vérifier qu'elle est détectée :
```bash
ip link show
# Doit afficher wlan0 et wlan1
```

### 2.2 — Configurer wlan1 sur le réseau domestique

Éditer `/etc/wpa_supplicant/wpa_supplicant-wlan1.conf` :
```bash
sudo nano /etc/wpa_supplicant/wpa_supplicant-wlan1.conf
```
```
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=CA

network={
    ssid="TON_WIFI_MAISON"
    psk="TON_MOT_DE_PASSE"
}
```
```bash
sudo chmod 600 /etc/wpa_supplicant/wpa_supplicant-wlan1.conf
sudo systemctl enable wpa_supplicant@wlan1
sudo systemctl start wpa_supplicant@wlan1
```

### 2.3 — Lancer le script hotspot

```bash
cd /home/artoo/r2d2
sudo bash scripts/setup_hotspot.sh
```

Le script :
- Installe `hostapd` + `dnsmasq`
- Configure `wlan0` en mode AP (SSID: `R2D2_Control`, clé: `r2d2droid`)
- Configure DHCP 192.168.4.2–20
- Active le routage IP (NAT wlan1→wlan0)

```bash
sudo reboot
```

### 2.4 — Vérification hotspot

```bash
# Après reboot, depuis ton PC connecté au hotspot R2D2_Control :
ping 192.168.4.1      # doit répondre (R2-Master)
```

---

## ÉTAPE 3 — SSH sans mot de passe R2-Master → R2-Slave

Le R2-Slave doit être connecté au hotspot `R2D2_Control` (il obtiendra l'IP `192.168.4.2`).

### 3.1 — Configurer wpa_supplicant sur le R2-Slave

```bash
# Sur R2-Slave (depuis ton PC via SSH réseau domestique, avant reboot hotspot)
sudo nano /etc/wpa_supplicant/wpa_supplicant.conf
```
Ajouter le réseau R2D2_Control :
```
network={
    ssid="R2D2_Control"
    psk="r2d2droid"
    priority=10
}
```
```bash
sudo reboot
# Le R2-Slave doit maintenant obtenir 192.168.4.2 via le hotspot
```

### 3.2 — Générer et copier les clés SSH

```bash
# Depuis le R2-Master
bash /home/artoo/r2d2/scripts/setup_ssh_keys.sh
# Entrer le mot de passe du R2-Slave quand demandé (une dernière fois)
```

Vérification :
```bash
ssh artoo@r2-slave.local echo "SSH OK"
# Doit afficher "SSH OK" sans mot de passe
```

---

## ÉTAPE 4 — Déploiement initial du code

### 4.1 — Copier le code Slave sur le R2-Slave

```bash
# Depuis le R2-Master
rsync -avz --delete \
  -e "ssh -o StrictHostKeyChecking=no" \
  /home/artoo/r2d2/slave/ \
  artoo@r2-slave.local:/home/artoo/r2d2/

# Copier aussi le dossier shared
rsync -avz \
  -e "ssh -o StrictHostKeyChecking=no" \
  /home/artoo/r2d2/shared/ \
  artoo@r2-slave.local:/home/artoo/r2d2/shared/

# Copier le fichier VERSION
rsync \
  -e "ssh -o StrictHostKeyChecking=no" \
  /home/artoo/r2d2/VERSION \
  artoo@r2-slave.local:/home/artoo/r2d2/VERSION
```

### 4.2 — Vérifier le code sur le R2-Slave

```bash
ssh artoo@r2-slave.local
ls /home/artoo/r2d2/
# Doit afficher: main.py  uart_listener.py  watchdog.py  version_check.py  drivers/  services/
cat /home/artoo/r2d2/VERSION
# Doit afficher le même hash que sur le R2-Master
```

---

## ÉTAPE 5 — Services systemd

### 5.1 — Sur le R2-Master

```bash
# Copier les fichiers service
sudo cp /home/artoo/r2d2/master/services/r2d2-master.service /etc/systemd/system/
sudo cp /home/artoo/r2d2/master/services/r2d2-monitor.service /etc/systemd/system/

# Recharger systemd
sudo systemctl daemon-reload

# Activer et démarrer
sudo systemctl enable r2d2-master r2d2-monitor
sudo systemctl start r2d2-master

# Vérifier l'état
sudo systemctl status r2d2-master
journalctl -u r2d2-master -f   # logs en temps réel
```

### 5.2 — Sur le R2-Slave

```bash
# Copier les fichiers service
sudo cp /home/artoo/r2d2/services/r2d2-slave.service /etc/systemd/system/
sudo cp /home/artoo/r2d2/services/r2d2-version.service /etc/systemd/system/

# Recharger systemd
sudo systemctl daemon-reload

# Activer et démarrer
sudo systemctl enable r2d2-version r2d2-slave
sudo systemctl start r2d2-slave

# Vérifier l'état
sudo systemctl status r2d2-slave
journalctl -u r2d2-slave -f   # logs en temps réel
```

---

## ÉTAPE 6 — Firmware RP2040

### 6.1 — Prérequis

- Installer **Thonny** sur ton PC ou utiliser `mpremote`
- Le RP2040 doit avoir MicroPython installé

### 6.2 — Installer MicroPython sur le RP2040

1. Télécharger le firmware MicroPython pour RP2040 :
   https://micropython.org/download/RPI_PICO/

2. Brancher le RP2040 en mode BOOTSEL (maintenir BOOT enfoncé, brancher USB)

3. Copier le fichier `.uf2` sur le lecteur `RPI-RP2` qui apparaît

### 6.3 — Installer le driver GC9A01

Via `mpremote` depuis ton PC :
```bash
pip install mpremote
mpremote connect auto mip install gc9a01
```

### 6.4 — Copier le firmware R2-D2

```bash
# Depuis le dossier rp2040/firmware/
cd J:/R2-D2_Build/software/rp2040/firmware

mpremote connect auto cp main.py :main.py
mpremote connect auto cp display.py :display.py
mpremote connect auto cp touch.py :touch.py
```

### 6.5 — Tester l'affichage

```bash
mpremote connect auto repl
# Dans le REPL MicroPython :
import display, gc9a01
# ... ou simplement laisser main.py démarrer
```

Le RP2040 doit afficher l'écran de boot R2-D2 au démarrage.

---

## ÉTAPE 7 — Tests de validation Phase 1

### 7.1 — Test UART + CRC

Depuis le R2-Master, tester manuellement :
```bash
python3 -c "
import sys; sys.path.insert(0, '/home/artoo/r2d2')
from shared.uart_protocol import build_msg, parse_msg
print(build_msg('H', '1'))       # H:1:59\n attendu
print(build_msg('M', '50'))      # M:50:7F\n attendu
print(parse_msg('H:1:59'))       # ('H', '1') attendu
print(parse_msg('H:1:00'))       # None attendu (CRC invalide)
"
```

### 7.2 — Test Watchdog

```bash
# Sur le R2-Slave
journalctl -u r2d2-slave -f

# Sur le R2-Master — arrêter temporairement le service Master
sudo systemctl stop r2d2-master

# Observer dans les logs Slave :
# → après 500ms : "WATCHDOG DÉCLENCHÉ"
# → redémarrer Master : "Watchdog: heartbeat repris"
sudo systemctl start r2d2-master
```

### 7.3 — Test Version Sync

```bash
# Simuler une divergence de version sur le R2-Slave
ssh artoo@r2-slave.local "echo 'aabbcc' > /home/artoo/r2d2/VERSION"

# Redémarrer le Slave
ssh artoo@r2-slave.local "sudo systemctl restart r2d2-slave"

# Observer les logs — doit tenter une synchro
ssh artoo@r2-slave.local "journalctl -u r2d2-slave -f"
```

### 7.4 — Test Teeces32

```bash
# Sur le R2-Master
python3 -c "
import configparser, sys
sys.path.insert(0, '/home/artoo/r2d2')
from master.teeces_controller import TeecesController
cfg = configparser.ConfigParser()
cfg.read('/home/artoo/r2d2/master/config/main.cfg')
t = TeecesController(cfg)
if t.setup():
    t.random_mode()
    import time; time.sleep(2)
    t.leia_mode()
    time.sleep(2)
    t.fld_text('R2D2 OK')
    t.shutdown()
"
```

### 7.5 — Test Bouton Dôme

```bash
# Vérifier que le pin BCM17 est bien câblé (bouton vers GND)
python3 -c "
import RPi.GPIO as GPIO, time
GPIO.setmode(GPIO.BCM)
GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_UP)
print('Appuie sur le bouton...')
while True:
    print('État:', GPIO.input(17))
    time.sleep(0.1)
"
```

### 7.6 — Test écran RP2040

Brancher le RP2040 sur le R2-Slave (USB), puis :
```bash
# Sur R2-Slave — envoyer une commande DISP: manuellement
python3 -c "
import serial, time
s = serial.Serial('/dev/ttyACM2', 115200)
s.write(b'DISP:BOOT\n'); time.sleep(1)
s.write(b'DISP:SYNCING:abc123\n'); time.sleep(2)
s.write(b'DISP:OK:abc123\n'); time.sleep(2)
s.write(b'DISP:TELEM:25.4V:38C\n')
s.close()
"
```

### 7.7 — Test Audio (jack 3.5mm natif)

```bash
# Sur R2-Slave — tester la sortie audio jack 3.5mm
aplay /home/artoo/r2d2/slave/sounds/001.wav

# Ou via Python subprocess
python3 -c "
import subprocess
subprocess.run(['aplay', '/home/artoo/r2d2/slave/sounds/001.wav'])
"
```

---

## Câblage UART à vérifier

```
R2-Master  BCM14 (TX, pin 8)  ──→  BCM15 (RX, pin 10)  R2-Slave
R2-Master  BCM15 (RX, pin 10) ←──  BCM14 (TX, pin 8)   R2-Slave
R2-Master  GND   (pin 6)      ───  GND   (pin 6)        R2-Slave
```

> **Les fils UART traversent le slipring.** Vérifier la continuité au multimètre avant de démarrer les services.
> R2-Master et R2-Slave utilisent `/dev/ttyAMA0` — même port, chacun sur son propre hardware.

---

## Après chaque modification de code

```bash
# Depuis le R2-Master
cd /home/artoo/r2d2
git pull                    # récupérer les modifs
bash scripts/deploy.sh      # raccourci : rsync + reboot Slave
```

Ou utiliser le **bouton physique dôme** :
- Appui court (< 2s) : git pull + rsync + reboot Slave
- Appui long (> 2s) : rollback vers la version précédente
- Double appui : afficher la version courante sur Teeces32

---

## Logs utiles

```bash
# R2-Master
journalctl -u r2d2-master -f

# R2-Slave (via SSH)
ssh artoo@r2-slave.local "journalctl -u r2d2-slave -f"

# Tous les logs R2-D2 en même temps (depuis le R2-Master)
journalctl -u r2d2-master -f &
ssh artoo@r2-slave.local "journalctl -u r2d2-slave -f"
```
