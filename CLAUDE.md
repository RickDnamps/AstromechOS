# R2-D2 Project — Claude Code Context

## 🎯 Vision
Système de contrôle distribué pour une réplique R2-D2 grandeur nature.
Architecture Master/Slave sur deux Raspberry Pi communiquant via UART physique
et Wi-Fi local. Inspiré de [r2_control by dpoulson](https://github.com/dpoulson/r2_control)
pour l'API REST Flask et la structure modulaire.

---

## 🖥️ Hardware — Inventaire complet

### Master — Raspberry Pi 4B (Dôme, tourne avec le slipring)
| Composant | Interface | Détails |
|-----------|-----------|---------|
| Waveshare Servo Driver HAT | I2C 0x40 | PCA9685 16ch — servos dôme |
| Teeces32 (LEDs logics FLD/RLD/PSI) | USB `/dev/ttyUSB0` | Protocole JawaLite 9600 baud |
| Caméra | USB | Vision / suivi de personne |
| UART vers Pi 4B Slave | BCM 14/15 `/dev/ttyAMA0` | Via slipring 3.3V |

### Slave — Raspberry Pi 4B 2G (Corps, fixe)
| Composant | Interface | Détails |
|-----------|-----------|---------|
| Waveshare Motor Driver HAT | I2C 0x40 | TB6612 — moteur DC rotation dôme |
| Breakout PCA9685 | I2C 0x41 | 16ch PWM — servos body/bras/panneaux |
| FSESC Mini 6.7 PRO × 2 | USB `/dev/ttyACM0` `/dev/ttyACM1` | PyVESC — moteurs propulsion 24V |
| RP2040-Touch-LCD-1.28 (Waveshare) | USB `/dev/ttyACM2` | Écran rond 240x240 diagnostic |
| Jack audio 3.5mm intégré | Natif Pi 4B | Audio Mr Baddeley → Ampli → HP |
| UART vers Pi 4B dôme | BCM 14/15 `/dev/ttyAMA0` | Via slipring 3.3V |

> ✅ Plus besoin de MAX98357A DAC — le Pi 4B 2G a un jack 3.5mm natif
> ✅ Plus besoin de hub USB — 4 ports USB natifs suffisent
> ✅ BCM 18/19/21 libres pour usage futur

### Slipring — Fils traversants (dôme tourne)
| Fil | Signal | Notes |
|-----|--------|-------|
| 1 | 24V | Alimente Buck DC-DC dôme (calibre plus gros) |
| 2 | GND | Commun |
| 3 | UART TX | R2-Slave (corps) → R2-Master (dôme) |
| 4 | UART RX | R2-Master (dôme) → R2-Slave (corps) |
| 5-6 | Spare | Réservé futur |

### Propulsion
- 2× Hub Motor 250W/24V (double shaft) — roues motrices
- 4× JayCreer 58mm Omni Wheels — stabilisation omnidirectionnelle
- Batterie 24V (XT60) — source principale
- 2× Buck DC-DC : 24V→5V/10A (servos+logique) et 24V→5V/5A (Pi+audio)

---

## 📡 Protocole UART Master ↔ Slave

### Format des messages
```
TYPE:VALEUR\n          # message simple
TYPE:VALEUR:CRC\n      # message avec checksum (XOR des bytes)
```

### Types de messages définis
```python
# Mouvement (Master → Slave)
"M:50\n"              # Vitesse moteurs (duty -100 à +100)
"M:LEFT:50:RIGHT:30\n" # Vitesse différentielle gauche/droite

# Moteur dôme DC (Master → Slave)
"D:50\n"              # Rotation dôme (duty -100 à +100)
"D:0\n"               # Stop dôme

# Servos body (Master → Slave)
"SRV:door_left:1.0:0.5\n"  # nom:position(0-1):durée(s)

# Audio (Master → Slave)
"S:01\n"              # Jouer son numéro 01

# Heartbeat (Master → Slave, toutes les 200ms)
"H:1\n"

# Version sync (bidirectionnel)
"V:?\n"               # Slave demande version au Master
"V:abc123\n"          # Réponse avec hash git

# Telemetry (Slave → Master, toutes les 1s)
"T:VOLT:48.2:TEMP:32:RPM:150\n"

# Status display (Master → Slave pour RP2040)
"DISP:BOOT\n"
"DISP:SYNCING:abc123\n"
"DISP:OK:abc123\n"
"DISP:ERROR:MASTER_OFFLINE\n"
"DISP:TELEM:48.2V:32C\n"
```

### Watchdog Slave (CRITIQUE — sécurité)
- Master envoie `H:1` toutes les **200ms**
- Slave coupe les VESC si aucun heartbeat reçu après **500ms**
- Slave envoie confirmation `H:OK\n` à chaque heartbeat reçu

---

## 🌐 API REST Flask (sur Master Pi 4B)
Inspirée de r2_control par dpoulson. Port **5000**.
Structure modulaire via **Flask Blueprints**.

### Endpoints core
```
GET  /                          → liste des endpoints
GET  /status                    → état complet du système
GET  /shutdown/now              → arrêt propre

GET  /servo/<part>/<name>/<pos>/<duration>
                                → part = body|dome
                                → pos = 0.0 à 1.0
                                → duration = secondes

GET  /servo/<part>/list         → liste servos configurés
GET  /servo/close               → fermer tous les servos
GET  /servo/open                → ouvrir tous les servos

GET  /drive/<left>/<right>      → commande différentielle (-100 à +100)
GET  /drive/stop                → arrêt immédiat

GET  /dome/<speed>              → rotation dôme (-100 à +100)
GET  /dome/stop                 → stop dôme

GET  /audio/<sound_id>          → jouer son (ex: /audio/01)
GET  /audio/list                → liste des sons disponibles

GET  /teeces/<command>          → commande JawaLite directe
                                → ex: /teeces/0T1 (random)
                                → ex: /teeces/0T20 (off)

GET  /display/<state>           → état RP2040 (BOOT|SYNCING|OK|ERROR)

GET  /telemetry                 → voltage, temp, RPM depuis VESC
```

### Socket.io events (temps réel)
```javascript
// Serveur → Client
emit('telemetry', {voltage: 48.2, temp: 32, rpm: 150})
emit('status', {master: 'ok', slave: 'ok', version: 'abc123'})
emit('alert', {level: 'error', msg: 'MASTER_OFFLINE'})

// Client → Serveur
on('drive', {left: 50, right: 50})
on('dome', {speed: 30})
```

---

## 🔄 Système de déploiement (Single Source of Truth)

### Flow complet
```
1. Bouton dôme appui court  → Master: git pull
2. Master: rsync /slave/ → artoo@r2-slave.local via SSH/Wi-Fi local
3. Master: envoie "REBOOT\n" via UART
4. Slave reboot
5. Au boot Slave:
   a. Lire /home/artoo/r2d2/VERSION (git hash local)
   b. Envoyer "V:?\n" au Master via UART
   c. Master répond "V:abc123\n"
   d. Si identique → démarrer app principale
   e. Si différent  → re-déclencher rsync (max 3 tentatives)
   f. Si Master injoignable → mode dégradé (démarrer version actuelle)
                            → afficher erreur sur RP2040 et Teeces32
```

### Bouton physique dôme
```python
BUTTON_SHORT_PRESS = "git pull + rsync + reboot"   # < 2 secondes
BUTTON_LONG_PRESS  = "rollback git checkout HEAD^"  # > 2 secondes
```

### Fichier VERSION
```bash
# Généré automatiquement après chaque git pull
git rev-parse --short HEAD > /home/artoo/r2d2/VERSION
```

---

## 📺 RP2040 Écran Diagnostic (Waveshare Touch LCD 1.28)

### États affichés
| Commande UART | Affichage | Couleur |
|--------------|-----------|---------|
| `DISP:BOOT` | Splash R2-D2 | Blanc |
| `DISP:SYNCING:v1` | Spinner + versions | Orange |
| `DISP:OK:v1` | Libère vers écran principal | Vert |
| `DISP:ERROR:MASTER_OFFLINE` | Alerte bloquante | Rouge |
| `DISP:TELEM:48V:32C` | Jauge batterie + temp | Bleu |

### Navigation tactile
- TAP = action primaire
- SWIPE = changer d'écran
- HOLD 2s = action critique (arrêt d'urgence)
- Double TAP = retour accueil

### Firmware RP2040
- Language: **MicroPython** avec LVGL ou dessin direct GC9A01
- Reçoit commandes via USB serial depuis R2-Slave
- Autonome — ne nécessite pas de mise à jour fréquente

---

## 🎵 Audio

### Teeces32 — Alertes visuelles sur logics dôme
```python
# Commandes JawaLite envoyées via /dev/ttyUSB0 à 9600 baud
"0T1\r"              # Animations aléatoires (mode normal)
"0T20\r"             # Tout éteint
"0T6\r"              # Mode Leia
"1MALERTE MASTER\r"  # Texte défilant sur FLD
"1MERREUR CODE\r"    # Affichage erreur
"4S1\r"              # PSI random
```

### Sons Mr Baddeley
- Stockés sur SD R2-Slave : `/home/artoo/r2d2/slave/sounds/`
- Format : WAV ou MP3 numérotés `001.wav`, `002.wav`...
- Lecture : `aplay` via subprocess (jack 3.5mm natif Pi 4B)
- Déclenchement : commande UART `S:01\n` depuis Master

---

## 🏗️ Structure du repo

```
r2d2/
├── CLAUDE.md                    ← CE FICHIER (contexte Claude Code)
├── VERSION                      ← git hash courant
├── master/
│   ├── main.py                  ← point d'entrée Master
│   ├── uart_controller.py       ← gestion UART + heartbeat
│   ├── teeces_controller.py     ← commandes JawaLite
│   ├── deploy_controller.py     ← git pull + rsync + bouton
│   ├── api/
│   │   ├── __init__.py          ← Flask app factory
│   │   ├── core.py              ← endpoints core + Socket.io
│   │   ├── servo_bp.py          ← Blueprint servos
│   │   ├── drive_bp.py          ← Blueprint propulsion
│   │   ├── audio_bp.py          ← Blueprint audio
│   │   └── teeces_bp.py         ← Blueprint Teeces32
│   ├── config/
│   │   ├── main.cfg             ← config principale
│   │   └── servo_list.cfg       ← définition des servos
│   └── services/
│       ├── r2d2-master.service  ← systemd
│       └── r2d2-monitor.service ← watchdog systemd
├── slave/
│   ├── main.py                  ← point d'entrée Slave
│   ├── uart_listener.py         ← écoute UART + dispatcher
│   ├── watchdog.py              ← coupe VESC si heartbeat perdu
│   ├── version_check.py         ← validation version au boot
│   ├── drivers/
│   │   ├── vesc_driver.py       ← PyVESC wrapper
│   │   ├── motor_driver.py      ← Motor Driver HAT (I2C 0x40)
│   │   ├── servo_driver.py      ← PCA9685 body (I2C 0x41)
│   │   ├── audio_driver.py      ← MAX98357A via aplay
│   │   └── display_driver.py    ← RP2040 via USB serial
│   └── services/
│       ├── r2d2-slave.service   ← systemd
│       └── r2d2-version.service ← validation version au boot
└── rp2040/
    └── firmware/
        ├── main.py              ← MicroPython firmware
        ├── display.py           ← rendu GC9A01
        └── touch.py             ← CST816S touch handler
```

---

## 🛠️ Directives de codage

### Règles absolues
1. **Python 3.10+** partout
2. **Gestion d'erreurs stricte** — try/except sur tout I/O (UART, I2C, USB)
3. **Watchdog prioritaire** — le watchdog ne peut jamais être bloqué
4. **Drivers isolés** — un fichier par périphérique, interface commune
5. **systemd** pour tous les services — `Restart=always`, `RestartSec=3`
6. **Logging** — `logging` Python standard, niveau INFO en prod, DEBUG en dev
7. **Config par fichiers .cfg** — jamais de hardcoding d'adresses/pins

### Interface commune des drivers
```python
class BaseDriver:
    def setup(self) -> bool: ...      # init hardware, retourne False si échec
    def shutdown(self) -> None: ...   # arrêt propre
    def is_ready(self) -> bool: ...   # état du driver
```

### Conventions UART
```python
MSG_TERMINATOR = "\n"
MSG_SEPARATOR  = ":"
HEARTBEAT_INTERVAL_MS = 200
WATCHDOG_TIMEOUT_MS   = 500
BAUD_RATE = 115200
```

### Protocole CRC — Checksum XOR obligatoire sur tous les messages

Le bus UART traverse un slipring — risque de bit flip. Chaque message
doit inclure un CRC (XOR de tous les bytes du payload avant le CRC).

**Format :**
```
TYPE:VALEUR:CRC\n
```

**Calcul du CRC (XOR de tous les bytes du payload) :**
```python
def calc_crc(payload: str) -> str:
    """
    payload = tout ce qui est avant le dernier ':'
    ex: pour "M:50:CRC"  → payload = "M:50"
    ex: pour "H:1:CRC"   → payload = "H:1"
    """
    crc = 0
    for byte in payload.encode("utf-8"):
        crc ^= byte
    return format(crc, '02X')  # retourne hex sur 2 chars ex: "3F"

def build_msg(type: str, value: str) -> str:
    payload = f"{type}:{value}"
    return f"{payload}:{calc_crc(payload)}\n"

def parse_msg(raw: str) -> tuple[str, str] | None:
    """
    Retourne (type, value) si CRC valide, None si invalide.
    Rejette silencieusement les messages corrompus.
    """
    raw = raw.strip()
    parts = raw.split(":")
    if len(parts) < 3:
        return None                          # format invalide
    *payload_parts, received_crc = parts
    payload = ":".join(payload_parts)
    expected_crc = calc_crc(payload)
    if received_crc != expected_crc:
        logging.warning(f"CRC mismatch: got {received_crc}, expected {expected_crc} for '{payload}'")
        return None                          # message corrompu, ignoré
    msg_type = payload_parts[0]
    msg_value = ":".join(payload_parts[1:])
    return (msg_type, msg_value)

# Exemples de messages valides générés
build_msg("M", "50")          # → "M:50:7F\n"
build_msg("H", "1")           # → "H:1:59\n"
build_msg("S", "01")          # → "S:01:62\n"
build_msg("V", "abc123")      # → "V:abc123:XX\n"

# Messages multi-valeurs (ex: drive différentiel)
build_msg("M", "LEFT:50:RIGHT:30")  # → "M:LEFT:50:RIGHT:30:XX\n"
# Note: parse_msg gère les valeurs composées correctement
# car seul le DERNIER segment est le CRC
```

**Règles :**
- Messages sans CRC = rejetés (sauf pendant la phase de boot initiale)
- CRC en hexadécimal majuscule sur 2 caractères (`00` à `FF`)
- En cas de 3 messages invalides consécutifs → logger une alerte
- Le Watchdog heartbeat `H:1:CRC\n` doit toujours passer — si 3 CRC
  invalides consécutifs sur heartbeat → considérer le bus comme bruité
  et loguer un warning (mais NE PAS couper les VESC pour un bus bruité,
  seulement pour un heartbeat absent)

### Gestion des versions
```python
VERSION_FILE = "/home/artoo/r2d2/VERSION"   # sur les deux Pi
VERSION_REQUEST = "V:?\n"
VERSION_RESPONSE_PREFIX = "V:"
MAX_SYNC_RETRIES = 3
SYNC_RETRY_BACKOFF_S = [5, 15, 30]  # backoff exponentiel
```

---

## 📦 Dépendances Python

### Hostnames
```
R2-Master  →  Pi 4B 4G  (Dôme)    →  r2-master.local
R2-Slave   →  Pi 4B 2G  (Corps)   →  r2-slave.local
```
Configurer via `sudo raspi-config` → System Options → Hostname
ou : `echo "r2-master" | sudo tee /etc/hostname`

### Username
```
Username sur les deux Pi : artoo
# Pas 'pi' — créer l'utilisateur artoo à l'installation
# via Raspberry Pi Imager → Options App → Username: artoo
```

Utilisation dans les scripts :
```python
MASTER_HOST = "r2-master.local"
SLAVE_HOST  = "r2-slave.local"
MASTER_IP   = "192.168.4.1"   # IP fixe sur wlan0 (Hotspot)
SLAVE_IP    = "192.168.4.2"   # IP fixe attribuée par le Master DHCP
SSH_USER    = "artoo"
```

### SSH sans mot de passe — Clés SSH (obligatoire pour rsync automatique)
```
⚠️ NE PAS utiliser un mot de passe vide — utiliser des clés SSH
⚠️ NE PAS utiliser l'username 'pi' — utiliser 'artoo'

Principe :
  R2-Master génère une paire de clés Ed25519
  La clé publique est copiée sur R2-Slave
  R2-Master peut SSH/rsync vers R2-Slave sans mot de passe
  Nécessaire pour : rsync automatique au boot, bouton dôme,
                    reboot Slave depuis Master

Setup (une seule fois sur R2-Master) :
```bash
# 1. Générer la paire de clés sur R2-Master
ssh-keygen -t ed25519 -C "r2-master" -f ~/.ssh/id_ed25519 -N ""
# -N "" = passphrase vide sur la CLÉ (≠ mot de passe du compte artoo)
# La clé reste sécurisée — seul R2-Master peut s'en servir

# 2. Copier la clé publique vers R2-Slave (une seule fois manuellement)
ssh-copy-id artoo@r2-slave.local

# 3. Tester
ssh artoo@r2-slave.local
# → connexion sans mot de passe ✅

# 4. Après ça, le rsync est 100% automatique
rsync -av /home/artoo/r2d2/slave/ artoo@r2-slave.local:/home/artoo/r2d2/
```
```

### Réseau Pi 4B — Double interface Wi-Fi
```
wlan0 = interface interne Pi 4B
        → Point d'Accès (Hotspot) permanent
        → SSID: "R2D2_Control"
        → IP fixe: 192.168.4.1
        → R2-Slave s'y connecte automatiquement
        → App Android s'y connecte pour contrôle

wlan1 = clé USB Wi-Fi externe
        → Client Wi-Fi domestique (réseau maison)
        → Connexion automatique si réseau connu disponible
        → Utilisé UNIQUEMENT pour git pull / GitHub
        → Optionnel — le droid fonctionne sans
```

**Logique git pull au démarrage :**
```python
def try_git_pull() -> bool:
    """
    Tentative de git pull au boot si wlan1 connecté.
    Timeout court pour ne pas bloquer le démarrage.
    Retourne True si pull réussi, False sinon (pas bloquant).
    """
    if not is_wlan1_connected():
        logging.info("wlan1 non disponible — git pull ignoré")
        return False
    try:
        result = subprocess.run(
            ["git", "pull"],
            cwd="/home/artoo/r2d2",
            timeout=30,          # max 30s pour ne pas bloquer le boot
            capture_output=True
        )
        if result.returncode == 0:
            # Mettre à jour le fichier VERSION
            update_version_file()
            logging.info("git pull réussi au démarrage")
            return True
        else:
            logging.warning(f"git pull échoué: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        logging.warning("git pull timeout — démarrage sans update")
        return False
    except Exception as e:
        logging.error(f"git pull erreur: {e}")
        return False

def is_wlan1_connected() -> bool:
    """Vérifie si wlan1 a une IP (= connecté au Wi-Fi domestique)."""
    try:
        result = subprocess.run(
            ["ip", "addr", "show", "wlan1"],
            capture_output=True, text=True, timeout=5
        )
        return "inet " in result.stdout
    except Exception:
        return False
```

**Séquence de boot Master complète :**
```
1. wlan0 démarre en mode AP (toujours, prioritaire)
2. wlan1 tente connexion Wi-Fi domestique (si connu)
3. Si wlan1 connecté → git pull (timeout 30s, non bloquant)
4. Mettre à jour VERSION si pull réussi
5. Démarrer rsync vers Slave si nouvelle version
6. Démarrer app principale (Flask + UART)
```

**Bouton dôme — logique complète :**
```python
BUTTON_PIN = XX  # BCM à définir

# Appui court (< 2s) :
#   Si wlan1 dispo  → git pull + rsync + reboot Slave
#   Si wlan1 absent → rsync version locale + reboot Slave
#                     (utile pour forcer re-sync sans internet)

# Appui long (> 2s) :
#   → git checkout HEAD^ (rollback)
#   → rsync version précédente + reboot Slave

# Double appui :
#   → afficher version courante sur Teeces32 et RP2040
```

### Master (Pi 4B)
```
flask
flask-socketio
pyserial          # UART + Teeces32 USB
RPi.GPIO          # bouton dôme
adafruit-pca9685  # Servo Driver HAT
paramiko          # SSH pour rsync
```

### Slave (Pi 4B 2G corps)
```
pyserial          # UART Master + VESC USB + RP2040 USB
pyvesc            # contrôle VESC
adafruit-pca9685  # PCA9685 body (I2C 0x41)
RPi.GPIO          # GPIO général
# Pas de lib audio nécessaire — jack 3.5mm natif, aplay out of the box
```

---

## 🔌 Adresses I2C

| Bus | Adresse | Composant | Pi |
|-----|---------|-----------|-----|
| I2C-1 | 0x40 | Servo Driver HAT (servos dôme) | R2-Master Pi 4B 4G |
| I2C-1 | 0x40 | Motor Driver HAT (moteur DC dôme) | R2-Slave Pi 4B 2G |
| I2C-1 | 0x41 | Breakout PCA9685 (servos body) | R2-Slave Pi 4B 2G |

---

## 🔧 Pins GPIO

### Pi 4B 2G (Corps — Slave)
| BCM | Fonction |
|-----|----------|
| 2 | I2C SDA |
| 3 | I2C SCL |
| 14 | UART TX → slipring → Pi 4B dôme RX |
| 15 | UART RX ← slipring ← Pi 4B dôme TX |
| 18/19/21 | Libres (plus besoin I2S) |
| Jack 3.5mm | Audio natif → Ampli → Haut-parleurs |

### Pi 4B 4G (Dôme — Master)
| BCM | Fonction |
|-----|----------|
| 2 | I2C SDA |
| 3 | I2C SCL |
| 14 | UART TX → slipring → R2-Slave RX |
| 15 | UART RX ← slipring ← R2-Slave TX |
| XX | Bouton dôme (à définir) |

### ⚠️ CÂBLAGE UART — TOUJOURS CROISER TX→RX
```
CORRECT ✅
R2-Master BCM14 (TX) ──→ BCM15 (RX) R2-Slave
R2-Master BCM15 (RX) ←── BCM14 (TX) R2-Slave
R2-Master GND        ─── GND         R2-Slave

INCORRECT ❌ (ne fonctionnera jamais)
R2-Master BCM14 (TX) ──→ BCM14 (TX) R2-Slave
R2-Master BCM15 (RX) ──→ BCM15 (RX) R2-Slave
```
TX d'un côté = toujours sur RX de l'autre. Règle physique universelle.

---

## 🚀 Ordre de développement (Phases)

### Phase 1 — Infrastructure (PRIORITÉ) ✅ Planifié
- [ ] **1.1** Hotspot Wi-Fi Pi 4B (`wlan0`) + clé USB internet (`wlan1`)
- [ ] **1.2** SSH sans mot de passe R2-Master → R2-Slave
- [ ] **1.3** UART + Heartbeat + **Watchdog** (critique sécurité)
- [ ] **1.4** Validation version au boot + rsync auto-guérissant
- [ ] **1.5** Bouton dôme (update/rollback)
- [ ] **1.6** Écran RP2040 boot/sync/erreur
- [ ] **1.7** Teeces32 alertes JawaLite

### Phase 2 — Propulsion
- [ ] **2.1** Driver VESC (PyVESC) + télémétrie
- [ ] **2.2** Rampes accélération/freinage
- [ ] **2.3** Contrôle différentiel

### Phase 3 — Personnalité
- [ ] **3.1** Audio Mr Baddeley (jack 3.5mm natif Pi 4B + aplay)
- [ ] **3.2** Contrôle servos dôme (PCA9685 R2-Master)
- [ ] **3.3** Contrôle servos body (PCA9685 R2-Slave)
- [ ] **3.4** Moteur DC dôme (Motor Driver HAT R2-Slave)

### Phase 4 — Interface
- [ ] **4.1** API REST Flask + Socket.io (inspiré r2_control)
- [ ] **4.2** Dashboard web (joysticks, soundboard, telemetry)
- [ ] **4.3** App Android UDP (deux joysticks style mobile)

### Phase 5 — Vision
- [ ] **5.1** Caméra USB + flux vidéo
- [ ] **5.2** Suivi de personne (OpenCV/TF Lite)

---

## 🐙 GitHub Repository

```
URL     : https://github.com/RickDnamps/R2D2_Control.git
Owner   : RickDnamps
Branch  : main
Licence : GNU GPL v3
```

### Setup initial (une seule fois sur le PC de développement)
```bash
# Cloner le repo
git clone https://github.com/RickDnamps/R2D2_Control.git
cd R2D2_Control

# Copier le CLAUDE.md dans le repo
# Puis premier commit
git add CLAUDE.md
git commit -m "Add project architecture and context"
git push
```

### Setup sur R2-Master (une seule fois)
```bash
# Cloner sur le Pi via wlan1 (Wi-Fi domestique)
cd /home/artoo
git clone https://github.com/RickDnamps/R2D2_Control.git r2d2
cd r2d2

# Générer le fichier VERSION initial
git rev-parse --short HEAD > VERSION
```

### Workflow git quotidien
```bash
# Sur le PC de dev — après avoir codé
git add .
git commit -m "Phase 1.3: UART watchdog implementation"
git push

# Sur R2-Master — via bouton dôme ou manuellement
git pull
git rev-parse --short HEAD > VERSION
# → rsync automatique vers R2-Slave déclenché
```

### Conventions de commit
```
Phase X.Y: description courte    # nouvelle fonctionnalité
Fix: description du bug          # correction de bug
Config: description              # changement de config
Docs: description                # documentation
```

### .gitignore — ne jamais committer
```
slave/sounds/         # sons trop lourds pour git
*.log                 # logs
master/config/local.cfg  # credentials WiFi + GitHub URL personnelle
slave/vendor/         # dépendances pip pré-téléchargées
```

---

## 📚 Code de référence — r2_control by dpoulson

Le code source complet de r2_control est disponible localement :
```
J:\R2-D2_Build\software\others\r2_control-master\
```

### Instructions pour Claude Code
1. **Lire et analyser** ce code avant de coder les modules équivalents
2. **S'inspirer** de la structure, pas copier — notre architecture est différente
3. **Modules particulièrement intéressants à étudier :**
   ```
   r2_control-master/
   ├── r2_control.py        ← structure principale, app factory Flask
   ├── modules/
   │   ├── audio.py         ← gestion audio, commandes son
   │   ├── servo.py         ← contrôle servos PCA9685
   │   └── scripts.py       ← système de scripts/séquences
   ├── controllers/
   │   └── web.py           ← interface web Flask, Blueprint
   └── configs/             ← structure des fichiers .cfg
   ```

4. **Ce qu'on garde de r2_control :**
   - Structure Blueprint Flask pour l'API REST
   - Système de config `.cfg` pour servos et hardware
   - Pattern audio avec liste de sons numérotés
   - Concept de "scripts" pour séquences d'actions

5. **Ce qu'on adapte / remplace :**
   - Pas de I2C direct depuis le Master → tout passe par UART vers R2-Slave
   - Pas de contrôleur PS3/Wii → joysticks Android UDP + web
   - Pas de périscope ni smoke machine
   - Watchdog UART remplace la gestion simple des erreurs

### Sons Mr Baddeley
Les sons sont aussi dans le répertoire r2_control :
```
J:\R2-D2_Build\software\others\r2_control-master\sounds\
```
**Instructions :**
- Copier tous les fichiers audio vers `/home/artoo/r2d2/slave/sounds/`
- Conserver la numérotation existante si possible
- Générer un fichier `sounds_index.json` avec la liste complète
- Une fois importés et validés → le répertoire `r2_control-master` peut être supprimé

```python
# Format de l'index des sons
{
    "01": {"file": "001.wav", "description": "Beep court"},
    "02": {"file": "002.wav", "description": "Excitation"},
    ...
}
```

- Le **Watchdog est non-négociable** — toujours tester en premier
- Le **slipring limite les fils** — ne jamais ajouter un signal sans valider le budget fils
- Le **RP2040 est autonome** — son firmware change rarement, ne pas l'inclure dans le pipeline rsync
- **Mode dégradé** = Slave démarre avec version locale si Master injoignable + alerte RP2040 + alerte Teeces32
- **Teeces32** = protocole JawaLite, compatible ESP32, USB `/dev/ttyUSB0` sur Pi 4B
- **FSESC Mini 6.7 PRO** = 4-13S LiPo, utiliser PyVESC avec commandes SET_DUTY ou SET_RPM
- **Hub Motors 250W/24V double shaft** — prévoir rampes douces (risque basculement)
- **r2_control inspiration** : structure Blueprint Flask, config `.cfg`, API REST propre
