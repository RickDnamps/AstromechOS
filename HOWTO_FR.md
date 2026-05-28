# AstromechOS — Guide d'installation

> 🇬🇧 **[Read in English →](HOWTO.md)** *(version principale — plus à jour)*

Tout est automatisé. L'installation complète = **3 commandes + 2 reboots**.

> **Portabilité (2026-05-28)** — AstromechOS n'impose plus que l'utilisateur du Pi s'appelle `artoo`. Les scripts d'installation détectent automatiquement ton user via `$SUDO_USER` (ou lisent `/boot/astromech_init.cfg` si l'AstromechOS Imager — à venir — en a écrit un), et tous les fichiers systemd + cibles SSH + chemins du repo sont dérivés au runtime via `shared/identity.py` + `scripts/lib_config.sh`. Les exemples utilisent `artoo` comme placeholder — **remplace-le par ton username Pi** si tu as imagé ta carte SD sous un autre nom. Le Master et le Slave **doivent partager le même utilisateur Linux** (et le même mot de passe — ça simplifie la distribution des clés SSH et l'auth de premier contact).

> **🛡️ Sécurité Déploiement & First-Boot Imager (2026-05-28)** — le panneau Settings → Deploy lance un **test ADN Git** (paternité) avant d'autoriser `origin` à pointer vers un repo qui n'est pas un fork de RickDnamps/AstromechOS — bloque les fautes de frappe, les URLs hostiles, les clones mal collés, tout en amont du `git pull`. La même primitive tourne au premier boot d'une carte SD préparée par l'Imager (`scripts/firstboot_setup.sh` + le service oneshot `astromech-firstboot.service`), qui injecte atomiquement les clés SSH, configure hostname + rôle, et valide l'ADN du remote — provisioning 100% headless. Architecture, modèle de menace, procédures de recovery → **[docs/DEPLOY_SECURITY.md](docs/DEPLOY_SECURITY.md)**.

---

## Prérequis matériel

| Composant | Master (dôme) | Slave (corps) |
|-----------|--------------|---------------|
| Modèle Pi | Pi 4B 4GB | Pi 4B 2GB |
| OS | Raspberry Pi OS Lite 64-bit Trixie | idem |
| WiFi | wlan0 intégré + **clé USB WiFi** (wlan1) | wlan0 intégré seulement |

> Le Master a besoin d'une clé USB WiFi (wlan1) : wlan0 devient le hotspot
> pour le Slave et les télécommandes, pendant que wlan1 reste connecté à internet
> pour les mises à jour git.

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
| Hostname | `astromech-master` | `astromech-slave` |
| WiFi | ton réseau maison | ton réseau maison |
| SSH | activé | activé |

Les deux Pi démarrent connectés à ton WiFi maison sur wlan0.
Trouver leurs IPs dans ton routeur, ou utiliser `astromech-master.local` / `astromech-slave.local`.

---

## Étape 1 — Installer le Master

Brancher la clé USB WiFi dans le Master, puis se connecter en SSH depuis le PC :

```bash
ssh artoo@astromech-master.local
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
curl -fsSL https://raw.githubusercontent.com/RickDnamps/AstromechOS/main/scripts/setup_master.sh | sudo bash
```

Le script gère tout automatiquement :
- Mise à jour système + paquets
- Clone du repo git
- Fix UART (`miniuart-bt` — le Bluetooth reste actif pour la manette)
- Activation UART matériel + I2C
- Dépendances Python
- `local.cfg` créé depuis le template exemple
- Reconfiguration WiFi : wlan0 → hotspot `Astromech_Control_XXXX` (192.168.4.1), wlan1 → internet maison
- Génération clé SSH Ed25519 (pour rsync Master → Slave)
- Services systemd installés et activés

> Le script demande aussi le **nom du robot** (affiché dans l'en-tête du dashboard).

**À la fin il demande de rebooter — répondre Y.**

---

### Après le reboot — se reconnecter au Master

Après le reboot, le WiFi du Master a changé :

```
Avant :  wlan0 → WiFi maison  (accessible depuis ton PC)
Après :  wlan0 → hotspot `Astromech_Control_XXXX`  192.168.4.1  (seulement depuis le hotspot)
         wlan1 → WiFi maison  (nouvelle IP assignée par le routeur)
```

> Le SSID du hotspot est **unique par robot** : `Astromech_Control_XXXX` où `XXXX` est dérivé
> du numéro de série du Pi. Le SSID exact est affiché à la fin de l'installation — note-le.
> Ainsi plusieurs droïdes peuvent fonctionner au même endroit (convention) sans collision.

Ton PC est encore sur le réseau maison, donc **deux options** pour se reconnecter :

**Option A — Connecter le PC au hotspot du robot (`Astromech_Control_XXXX`) (recommandé)**

1. Sur ton PC, se connecter au réseau WiFi : **`Astromech_Control_XXXX`** (le SSID affiché à la fin de l'install)
2. SSH avec l'IP fixe du hotspot :
   ```bash
   ssh artoo@192.168.4.1
   ```
   Cette IP ne change jamais — c'est celle à utiliser pour tous les SSH futurs.

**Option B — Rester sur le réseau maison, utiliser la nouvelle IP de wlan1**

Le wlan1 du Master reçoit une nouvelle IP DHCP depuis ton routeur.
La trouver via :
- La page admin du routeur (chercher `astromech-master`)
- Essayer : `ssh artoo@astromech-master.local` (fonctionne sur Linux/Mac via mDNS, peu fiable sur Windows)
- Un scanner réseau (ex : Fing sur téléphone, Angry IP Scanner sur PC)

> L'option A est plus simple et c'est ce qu'on utilise en permanence — l'IP 192.168.4.1 est fixe pour toujours.
> Basculer dessus maintenant, plus besoin de chercher des IPs ensuite.

---

## Étape 2 — Installer le Slave

**Pendant que le Slave est encore sur le WiFi maison** (avant de rejoindre le hotspot), se connecter en SSH :

```bash
ssh artoo@astromech-slave.local
# ou : ssh artoo@<IP_SLAVE>
```

Lancer l'installateur en une ligne :

```bash
curl -fsSL https://raw.githubusercontent.com/RickDnamps/AstromechOS/main/scripts/setup_slave.sh | sudo bash
```

Le script gère tout automatiquement :
- Mise à jour système + paquets (`mpg123`, `alsa-utils`, `i2c-tools`, `python3-smbus`, `pulseaudio`, `pulseaudio-module-bluetooth`, `bluez`, `libasound2-plugins`)
- Fix UART (`miniuart-bt` — la puce BT reste active via le mini-UART, libérant l'UART matériel PL011 `/dev/ttyAMA0` pour le lien Master↔Slave)
- Activation UART matériel + I2C
- Dépendances Python (pyserial, smbus2, adafruit-pca9685)
- WiFi : connexion wlan0 au hotspot du robot (`Astromech_Control_XXXX`)
- Routage ALSA → PulseAudio (`~/.asoundrc`) — l'audio `mpg123` passe par PulseAudio, ce qui permet la sortie jack 3.5mm ou enceinte Bluetooth
- Support enceinte BT : l'utilisateur `artoo` est ajouté au groupe `bluetooth`, modules PulseAudio BT configurés (`default.pa`), linger activé pour la session sans login

**À la fin il demande de rebooter — répondre Y.**

Le Slave rejoint alors le hotspot du Master et reçoit une adresse DHCP dans la plage `192.168.4.x`. Le Master le rejoint toujours par son hostname (`astromech-slave.local`), donc tu n'as jamais besoin de connaître l'IP exacte. Les exemples ci-dessous utilisent `192.168.4.171` comme bail typique — remplace par l'adresse réellement reçue si elle diffère (le panneau STATUS du cockpit affiche l'IP live du Slave).

---

## Étape 3 — Premier déploiement du code (depuis le Master)

Se connecter en SSH au Master avec la même méthode qu'à l'étape 1 :

- **Option A (hotspot) :** ton PC est sur le hotspot du robot → `ssh artoo@192.168.4.1`
- **Option B (réseau maison) :** `ssh artoo@astromech-master.local` ou l'IP trouvée dans le routeur

Lancer le premier déploiement :

```bash
bash /home/artoo/astromechos/scripts/deploy.sh --first-install
```

Cela :
- rsync tout le code vers le Slave
- Installe les dépendances pip sur le Slave
- Installe et active le service systemd `astromech-slave`
- Redémarre le Slave

Puis copier la clé SSH vers le Slave (active le rsync sans mot de passe pour les futures mises à jour) :

```bash
ssh-copy-id artoo@astromech-slave.local
```

**Terminé.** Ton droïde est opérationnel.

---

## Connexion au dashboard

Flask écoute sur toutes les interfaces réseau — pas besoin de changer de WiFi, le dashboard est accessible **depuis les deux réseaux**.

**Depuis le WiFi maison (le plus pratique — rester sur son réseau normal) :**

Trouver l'IP de wlan1 du Master (celle assignée par le routeur) :
- Dans la page admin du routeur (chercher `astromech-master`)
- Ou en SSH sur le Master : `hostname -I` — la deuxième IP est wlan1
- Ou essayer directement dans un navigateur : `http://astromech-master.local:5000` (fonctionne sur Linux/Mac/Android)

Puis ouvrir : `http://<IP-wlan1>:5000`

> Cette IP peut changer si le routeur la réassigne. Pour la figer, créer un bail DHCP statique dans les paramètres du routeur pour l'adresse MAC du Master.

**Depuis le hotspot du robot (`Astromech_Control_XXXX`) (IP fixe, toujours disponible — idéal en convention) :**

Se connecter au WiFi **`Astromech_Control_XXXX`**, puis ouvrir : **http://192.168.4.1:5000**

**L'application Android** détecte automatiquement le Master sur le réseau auquel elle est connectée.

---

## Utilisation quotidienne

### Mode Admin

Cliquer sur le bouton **🔒 ADMIN** dans la barre d'onglets (à côté de l'engrenage ⚙️) pour déverrouiller le mode admin depuis n'importe quel onglet — pas besoin d'aller dans Settings d'abord. Entrer le mot de passe une fois ; l'admin reste actif pendant 5 minutes d'inactivité. Le minuteur se réarme à chaque mouvement de souris, clic ou touche, donc tu ne seras pas déconnecté tant que tu travailles. Recliquer sur le bouton (devenu 🔓) pour verrouiller immédiatement.

### Changer le mot de passe admin (Admin → Config → System)

Il y a **deux mots de passe distincts** sur le robot — ne pas les confondre :

- 🔑 **Mot de passe Admin Interface** — celui qu'on tape pour déverrouiller ce dashboard/app (Settings + les éditeurs Choreo, Audio & Séquences). Le changer dans **System → Change Admin Password**. Cela ne met à jour que le mot de passe du dashboard ; ça ne touche **pas** ton login Linux.
- 🖥️ **Mot de passe Linux / SSH** — le mot de passe du compte système du Pi (l'utilisateur créé à l'install, ex. `artoo`). Il est complètement séparé et n'est **pas** changeable depuis le dashboard. Pour le changer, se connecter en SSH et lancer `passwd`. Le dashboard affiche toujours ton *vrai* nom d'utilisateur (lu depuis le système, jamais codé en dur), donc l'aide « Forgot password? » à l'écran pointe vers le bon utilisateur et le bon chemin de config pour ton installation.

Donc changer le mot de passe admin verrouille l'interface web mais laisse SSH inchangé — change aussi le mot de passe Linux si tu veux sécuriser complètement l'accès distant.

### Ajouter des sons

En mode admin, l'**onglet Audio** affiche une zone d'upload. Glisser un MP3 dessus (ou cliquer pour parcourir), choisir une catégorie, et uploader. Le son est enregistré et synchronisé sur le Slave Pi automatiquement — pas de SSH, pas de redémarrage, disponible immédiatement.

Pour créer une nouvelle catégorie, utiliser le panneau **Create Category** sous la zone d'upload.

### Gérer les chorégraphies

**Cartes choreo (onglet Sequences) — mode admin seulement :**
- Cliquer le **label** pour le renommer (affiché dans le sélecteur de fichier et sur la carte)
- Cliquer l'**emoji** pour ouvrir le sélecteur d'emoji
- Utiliser le **menu déroulant de catégorie** sur la carte pour la réassigner à une autre catégorie

Les catégories (créer / renommer / réordonner / supprimer) se gèrent depuis les pastilles de catégorie en haut de l'**onglet Sequences** — pas d'édition de fichier nécessaire. L'**onglet CHOREO** est l'éditeur de timeline lui-même.

**Éditer la timeline (souris *et* tactile) :**
- **Ajouter un bloc** — glisser une action depuis la palette de gauche (AUDIO / LIGHT / DOME / servos / DRIVE) sur sa piste et la déposer à l'endroit voulu dans le temps. Sur tablette, glisser au doigt, ou **taper** une pastille de la palette pour déposer le bloc à la fin (puis régler son START dans l'inspecteur).
- **Déplacer un bloc** — le glisser gauche/droite le long de sa piste. Le glisser entièrement hors de la timeline le supprime (avec un toast UNDO).
- **Redimensionner un bloc** — glisser son bord droit. Sur tablette la poignée est toujours visible et adaptée au doigt ; sur desktop elle apparaît au survol.
- **SNAP / ZOOM** sont dans la barre du bas (à côté du temps écoulé/total). La règle de temps affiche des marques fines (chaque seconde) en zoom avant et plus espacées en zoom arrière.

**Barre d'outils de l'éditeur choreo — mode admin seulement :**

Les boutons **RENAME · SAVE · DELETE · EXPORT · IMPORT** ne sont visibles que lorsque l'admin est déverrouillé. Les non-admins peuvent quand même ouvrir, éditer et jouer les chorégraphies — ils ne peuvent simplement pas écrire les changements sur disque.

- **RENAME** — renomme le fichier `.chor` sur disque (le nom interne affiché dans le sélecteur). À utiliser pour donner un nom propre et permanent après expérimentation.
- **SAVE** — la seule façon d'écrire une choreo sur disque. Toujours requise pour garder ton travail.
- **DELETE** — supprime définitivement le fichier `.chor`.
- **EXPORT / IMPORT** — télécharger ou uploader des fichiers `.chor` pour sauvegarde ou partage.

**Jouer sans sauvegarder — mode preview :**

N'importe qui (admin ou non) peut appuyer sur **Play** à tout moment sans sauvegarder d'abord. La choreo courante est écrite dans un fichier temporaire invisible (`__preview__.chor`) et jouée de là — il n'apparaît jamais dans la liste et est écrasé à chaque preview.

Ce que fait Play :
| Situation | Admin | Résultat |
|-----------|-------|----------|
| Fichier existant, pas de modif | tout le monde | Joue le fichier sauvegardé directement |
| Fichier existant, modifié | ✅ | Auto-sauvegarde les changements, puis joue |
| Fichier existant, modifié | ❌ | Joue via preview — fichier sur disque inchangé |
| Nouvelle choreo (jamais sauvée) | tout le monde | Joue via preview — rien d'écrit sur disque |

Quand un admin joue une choreo non sauvegardée, un toast de rappel apparaît : **« Preview playing — press Save to keep this choreography »**.

### Panneau STATUS du cockpit

Le bouton **STATUS** en haut à droite du dashboard ouvre un panneau repliable montrant un instantané live du robot depuis n'importe quel onglet : audio · lumières · tension/ampères/watts VESC · CPU/RAM/température des Pi · IPs Master et Slave · état E-Stop et Bench mode.

### Verrou de sécurité VESC

Quand un VESC est hors-ligne, que la télémétrie est périmée (>2 s), ou qu'un code de fault est actif, toutes les commandes de propulsion sont bloquées partout (joystick web, API REST, manette Bluetooth, lecteur de chorégraphies). La vérification vit dans `master/vesc_safety.py` et est la source unique de vérité — aucun chemin d'entrée ne peut la contourner.

Si le VESC droit (CAN ID 2) devient silencieux pendant que le côté gauche répond toujours, le Slave détecte l'asymétrie et émet un fault `CAN_LOST` synthétique pour que la barrière de sécurité du Master se déclenche immédiatement, au lieu d'attendre le seuil de péremption de 2 s. Évite les emballements sur une roue.

Trois watchdogs indépendants renforcent ça : le **heartbeat app** (navigateur/app → Master, coupe la motion si pas de heartbeat pendant 1.5 s), le **watchdog drive** (rampe anti-tip si aucune commande de propulsion pendant 800 ms en mouvement), et le **watchdog UART du Slave** (coupe les VESCs si le heartbeat du Master est perdu pendant 500 ms).

Pour tester le logiciel sans moteurs physiquement connectés, activer le **Bench mode** dans **Config → VESC**. Le réglage est persisté dans `local.cfg` et survit aux reboots. Le désactiver avant utilisation sur le terrain.

### Calibration de la latence UART

Les servos du corps voyagent via UART jusqu'au Slave Pi avant d'atteindre leur HAT I2C — cela ajoute un trajet aller d'environ 5–25 ms selon le matériel, la qualité du slip ring et la charge. Le lecteur de chorégraphies compense en déclenchant les événements des servos corps ce nombre de millisecondes *en avance* pour qu'ils bougent en synchro avec les servos du dôme (qui sont en I2C direct).

**Auto-calibration** — ouvrir **Config → HATs** (sous la section HARDWARE), trouver **UART RTT calibration**, cliquer **MEASURE** (échantillonne le round-trip du heartbeat sur 40 s), puis **APPLY & SAVE**. La valeur est persistée dans `local.cfg` *et* hot-swappée dans le ChoreoPlayer en cours en un clic — pas de reboot, pas de redémarrage du Slave. Re-mesurer et ré-appliquer itérativement jusqu'à ce que les panneaux corps et dôme s'ouvrent en parfaite synchro.

Un indicateur de fit coloré (vert / orange / rouge) dit d'un coup d'œil si la valeur configurée correspond à la latence actuelle du bus. Les éditions manuelles du champ de latence s'auto-sauvegardent au blur avec un bref indicateur `✓ saved`.

### Manette Bluetooth

La manette se connecte **directement au Master Pi via Bluetooth** (evdev Linux — pas de relais téléphone, pas de matériel en plus, zéro latence). Compatible avec Xbox Series, PS4/PS5, Nintendo Switch Pro, 8BitDo, et toute manette HID standard.

**Mapping par défaut (fixe) :**

| Entrée | Action |
|--------|--------|
| Stick gauche Y | Avant / arrière propulsion |
| Stick gauche X | Direction gauche / droite |
| Stick droit X | Rotation dôme |
| Bouton Home / Guide / PS | Arrêt d'urgence |
| R1 / gâchette droite | Turbo (multiplicateur de vitesse) |

Propulsion, dôme, E-STOP et turbo sont les seuls bindings codés en dur. Tout le reste (ouvrir des panneaux, jouer un son, lancer une chorégraphie…) est assigné par toi via les **Custom Button Actions** — voir ci-dessous.

**Custom Button Actions** — assigner n'importe quel bouton libre à une action (`ouvrir/fermer bras`, `panneau corps`, `panneau dôme`, `jouer choreo`, `jouer son`, `son aléatoire`). Dans **Config → BT Gamepad**, utiliser **🎯 Capture New Button** : appuyer sur le bouton voulu de la manette, puis choisir l'action. Les mappings sont stockés **par manette** (par MAC), donc chaque manette peut avoir sa propre disposition, et ils survivent aux reboots.

**Configuration** — remapper les axes de propulsion, ajuster la deadzone, et régler le timeout d'inactivité (slider jusqu'à 600s, saisie manuelle jusqu'à 3600s) depuis **Config → BT Gamepad** — pas de SSH.

**Batterie & signal** — le panneau Config affiche le pourcentage de batterie et le RSSI Bluetooth avec code couleur live (vert/orange/rouge), mis à jour toutes les 30 secondes. Supporté par les manettes PS4, PS5 et Xbox. La manette NVIDIA Shield utilise un protocole propriétaire et n'expose pas le niveau de batterie — elle affichera 0%.

**Keep-alive** — un thread en arrière-plan renvoie la dernière commande de propulsion toutes les 300ms tant que le joystick est maintenu. Cela empêche le MotionWatchdog de couper la propulsion quand le stick est tenu immobile (evdev ne fire que sur *changement* d'axe, pas en continu).

Appairer depuis le dashboard : **Config → BT Gamepad → Scan**, ou manuellement via `bluetoothctl` sur le Master.

### Kids Lock & Child Lock

Trois modes de fonctionnement, commutables depuis l'en-tête du dashboard (protégé par mot de passe) :

| Mode | Icône | Effet |
|------|-------|-------|
| **Normal** | 🟢 | Pleine vitesse, tous les contrôles actifs |
| **Kids** | 🟡 | Vitesse plafonnée à un % configurable — parfait pour les shows avec de jeunes pilotes |
| **Child Lock** | 🔴 | Toute la motion complètement bloquée — lumières & sons fonctionnent encore |

Le mode verrou s'applique **à la fois aux entrées web et Bluetooth** simultanément. Servos, audio et lumières restent pleinement opérationnels dans tous les modes.

### Application Android

Télécharger [`android/compiled/AstroMech_Control.apk`](android/compiled/AstroMech_Control.apk) — activer *Installer depuis des sources inconnues*, installer, lancer.

- **Mode plein écran immersif** — masque les barres de navigation, balayer pour révéler
- **Bannière hors-ligne** — feedback visuel immédiat quand la connexion tombe
- **Auto-découverte** — essaie mDNS → IP sauvegardée → 192.168.4.1 → scan du sous-réseau
- **Hôte configurable** — appui long pour changer l'IP du Master
- **Fonctionne hors-ligne** — tous les assets sont embarqués localement, pas d'internet requis sur le téléphone

### Accès SSH

```bash
# Depuis n'importe quel appareil sur le hotspot du robot (`Astromech_Control_XXXX`) :
ssh artoo@192.168.4.1    # Master (dôme)
ssh artoo@192.168.4.171  # Slave (corps) — bail DHCP typique, vérifier si différent

# Depuis le Master, rejoindre le Slave :
ssh artoo@astromech-slave.local
```

> Ne pas utiliser les hostnames `.local` depuis Windows — mDNS peu fiable.
> Utiliser l'IP fixe `192.168.4.1` du Master ; pour le Slave, vérifier l'IP réelle dans le panneau STATUS.

### Changer le hotspot ou le WiFi maison (Admin → Config → Network)

- **SSID / mot de passe du hotspot** (le réseau que rejoignent le Slave et ta tablette) : chaque robot a un SSID **unique** comme `Astromech_Control_XXXX` (dérivé du numéro de série du Pi), pour que plusieurs droïdes ne se chevauchent pas en expo. Quand tu changes le SSID ou le mot de passe du hotspot, le Master met à jour le **Slave d'abord** (pour qu'il puisse rejoindre), puis bascule son propre point d'accès — le Slave se reconnecte automatiquement en quelques secondes, et **l'UART maintient la propulsion/sécurité** pendant le bref trou WiFi. **Si le Slave est éteint ou injoignable, le changement est refusé** pour ne jamais l'abandonner. Ta tablette/PC doit se reconnecter manuellement avec les nouveaux identifiants.
- **WiFi maison (wlan1, internet)** : connecte la clé USB WiFi du Master à ton réseau maison pour internet + déploiements. Le panneau affiche le réseau **live** auquel tu es réellement connecté (pas une valeur sauvegardée périmée).

### Sauvegarde & Restauration

Protégez le robot contre une carte SD morte. **Admin → Config → System → Backup / Restore.**

**Pour sauvegarder :**
1. Cliquez **Create backup**. Une barre de progression tourne pendant que le Master rassemble toutes les configs, tous les sons (récupérés du Slave), les chorégraphies, les séquences de lumières, les calibrations servo/dôme et vos thèmes perso.
2. À la fin, un fichier `AstromechOS_Backup_<date>.bck` se télécharge. **Gardez-le en lieu sûr — il contient votre mot de passe Wi-Fi et le mot de passe admin.** Stockez-le hors du robot (PC, clé USB, cloud).

> Le téléchargement marche dans n'importe quel navigateur et dans l'app Android (tablette). Sur un téléphone l'écran Settings n'apparaît pas — sauvegardez depuis une tablette ou un navigateur PC.

**Pour restaurer (ex. après avoir reflashé une carte SD morte) :**
1. Réinstallez AstromechOS normalement (les deux scripts d'install), pour que le Pi démarre et que le dashboard soit joignable.
2. **Admin → Config → System → Restore from backup…**, choisissez votre `.bck`.
3. Confirmez. Le robot valide l'archive, remplace tout l'état, puis **redémarre automatiquement**. La page attend et se recharge au retour — tout est « comme avant ».

> **Le réseau est préservé :** la restauration garde les réglages Wi-Fi / hotspot / SSH *actuels* de la machine, jamais ceux du backup — donc le Master et le Slave ne se perdent jamais, même si le backup vient d'un autre réseau.
> **Sûr par conception :** le `.bck` est validé (il ne peut restaurer que des fichiers de données, jamais du code) et rejeté s'il est altéré.

### Thèmes personnalisés

Créez un thème dans **Config → Appearance → Theme** (8 sélecteurs de couleur + police). Vos thèmes perso sont enregistrés **sur le robot** (pas seulement dans le navigateur) : ils survivent aux reboots, apparaissent sur chaque appareil qui se connecte, et entrent dans les sauvegardes.

### Mettre à jour AstromechOS

**Depuis le dashboard :** cliquer sur le bouton **Admin** (en haut à droite) → entrer le mot de passe admin (défaut **`deetoo`**) → les menus protégés deviennent visibles → **Config → Deploy → UPDATE** (git pull + rsync Slave + restart, tout automatique). Si une mise à jour pose problème, le bouton **ROLLBACK** (même panneau) revient au commit précédent.

> La session admin expire après 5 minutes d'inactivité. Le mot de passe peut être changé dans **Config → System** une fois connecté.

**Ou depuis SSH sur le Master :**

```bash
bash /home/artoo/astromechos/scripts/update.sh
```

Fait : backup séquences → git pull → rsync vers Slave → restart Slave → restart Master → vérification services.

### Vérifier l'état des services

```bash
# Sur le Master :
sudo systemctl status astromech-master
sudo journalctl -u astromech-master -f

# Sur le Slave (depuis le Master) :
ssh artoo@astromech-slave.local sudo systemctl status astromech-slave
ssh artoo@astromech-slave.local sudo journalctl -u astromech-slave -f
```

> **Note :** d'anciens logs peuvent montrer des lignes `astromech-master.service: Failed with result 'exit-code'` — une par deploy/restart. Ce n'étaient **pas** des crashes ; le service s'arrête, sort, et redémarre immédiatement. Causées par un bug du handler de shutdown (corrigé), elles sont inoffensives. Un arrêt propre log maintenant `Master shut down cleanly` + `Deactivated successfully`.

### Collecter les logs de debug

```bash
bash /home/artoo/astromechos/scripts/check_logs.sh
bash /home/artoo/astromechos/scripts/debug_collect.sh
```

### Resynchroniser le Slave seulement (sans git pull)

```bash
bash /home/artoo/astromechos/scripts/resync_slave.sh
```

---

## Câblage matériel

Voir [ELECTRONICS.md](ELECTRONICS.md) pour tous les détails de câblage :
- UART slip ring
- Contrôleurs servos PCA9685 (I2C)
- Contrôleurs moteurs VESC (USB + CAN)
- LED logic Teeces32 / AstroPixels+
- Écran RP2040

### Ajouter un HAT servo supplémentaire

Chaque HAT PCA9685 ajoute 16 servos. Les HATs se distinguent par leur adresse I2C, configurée en soudant les jumpers A0–A5 sur la carte.

**Adresses courantes :**

| Adresse | Jumper soudé | Utilisation typique |
|---------|-------------|---------------------|
| `0x40`  | aucun       | Master HAT 1 (Servo_M0–M15) |
| `0x41`  | A0          | Slave HAT 1 (Servo_S0–S15) |
| `0x42`  | A1          | HAT 2 (Servo_M16–M31 ou Servo_S16–S31) |
| `0x43`  | A0 + A1     | HAT 3 (Servo_M32–M47 ou Servo_S32–S47) |

> ⚠️ Ne jamais mettre `0x40` dans les adresses Slave — c'est l'adresse du Motor HAT. Ça endommagerait le driver moteur.

**Configuration depuis le dashboard (Config → HATs, section HARDWARE) :**

- **Master HAT addresses** : entrer les adresses séparées par des virgules
  - 1 HAT : `0x40`
  - 2 HATs : `0x40, 0x42`
  - 3 HATs : `0x40, 0x42, 0x43`
- **Slave HAT addresses** : idem, en commençant par `0x41`
  - 1 HAT : `0x41`
  - 2 HATs : `0x41, 0x42`
  - 3 HATs : `0x41, 0x42, 0x43`

Cliquer **SAVE HARDWARE CONFIG** puis **REBOOT MASTER** pour appliquer.

> Les listes `DOME_SERVOS` et `BODY_SERVOS` sont calculées au démarrage — un reboot est obligatoire après tout changement d'adresse.

---

## Firmware écran RP2040

Flasher manuellement via `mpremote` (seulement après remplacement matériel ou reset firmware) :

```bash
# SSH sur le Slave :
ssh artoo@astromech-slave.local

# Flasher (toujours rm avant cp — mpremote compare les timestamps, pas le contenu) :
python3 -m mpremote connect /dev/ttyACM0 rm :display.py
python3 -m mpremote connect /dev/ttyACM0 cp /home/artoo/astromechos/rp2040/firmware/display.py :display.py
```

Ou utiliser le script dédié depuis le Master :

```bash
bash /home/artoo/astromechos/scripts/deploy_rp2040.sh
```

---

## Appairage manette Bluetooth

Depuis le dashboard : **onglet Config → BT Gamepad** → Scan → appairer la manette.

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

## Appairage enceinte Bluetooth (tests sur établi)

> ⚠️ La qualité audio est limitée à cause de la coexistence mini-UART BT + WiFi 2.4GHz sur le Slave Pi. C'est pour les tests sur établi seulement — le robot assemblé utilisera le jack 3.5mm avec un ampli filaire.

Appairer une enceinte Bluetooth au **Slave Pi** depuis le dashboard : **Config → Audio → Bluetooth Speaker** → Scan → appairer et connecter l'enceinte.

**Ce qui se passe automatiquement :**
- La sortie son bascule sur l'enceinte BT (sink A2DP défini comme défaut PulseAudio)
- Le slider de volume du panneau BT Speaker contrôle le volume du sink PA, indépendamment du slider de volume ALSA principal
- La déconnexion restaure le jack 3.5mm automatiquement

Ou manuellement sur le Slave :

```bash
ssh artoo@192.168.4.171
bluetoothctl
> power on
> pairable on
> scan on
# attendre que l'enceinte apparaisse
> pair XX:XX:XX:XX:XX:XX
> trust XX:XX:XX:XX:XX:XX
> connect XX:XX:XX:XX:XX:XX
> quit
# Définir comme sink PulseAudio par défaut :
XDG_RUNTIME_DIR=/run/user/$(id -u) pactl set-default-sink bluez_sink.XX_XX_XX_XX_XX_XX.a2dp_sink
```

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
| Slave | `192.168.4.171` (DHCP typique) | tout appareil sur le hotspot |
| Dashboard | `http://192.168.4.1:5000` | navigateur sur le hotspot |
| SSH Master | `ssh artoo@192.168.4.1` | mot de passe : `deetoo` (à changer !) |
| SSH Slave | `ssh artoo@192.168.4.171` | mot de passe : `deetoo` (à changer !) |
</content>
</invoke>
