# Settings Menu — Brainstorm & Roadmap
**Date:** 2026-04-11  
**Status:** Brainstorming — en attente de validation

---

## État actuel du menu Settings

Panneaux existants (sidebar iPad-style) :
| Icône | Panneau | Contenu actuel |
|-------|---------|----------------|
| 🎮 | Bluetooth | Manette BT, mappings boutons, timeout inactivité |
| 🔒 | Lock Mode | Admin password, timeout session |
| 🦾 | Arms | Config servos des bras + panneau body associé |
| 🔧 | **Servos → Calibration** | Labels, angles open/close, test open/close, save |
| ⚡ | VESC | Power scale, inversion L/R, CAN bus setup |
| 💡 | Lights | Séquences lumières (placeholder) |
| 🔋 | Battery | Nombre de cellules, seuils de tension |
| 🎵 | Audio | Nombre de canaux, volume |
| 📷 | Camera | Config caméra USB |
| 📡 | Network | WiFi, Hotspot |
| 🚀 | Deploy | Git pull, update, reboot |
| 🖥️ | System | E-Stop, reboot Slave |

---

## Changement immédiat (zéro code)

### 🔧 → 🎯 Servos devient **Calibration**
Le panneau Servos a déjà tout : labels, angles, test open/close, save.  
**Action :** renommer l'icône + label dans la sidebar seulement.  
**Effort :** 2 minutes.

---

## Nouvelles idées — par panneau

---

### 🤖 Behavior — Personnalité & Réactions automatiques

**Concept :** R2 vit tout seul sans que quelqu'un touche l'interface.

#### Idle Reactions
- Après X minutes d'inactivité → jouer automatiquement un son aléatoire et/ou une choreo
- Slider pour configurer le délai (ex: 0 = désactivé, 1-30 minutes)
- Choix de la catégorie audio pour les réactions idle (ex: "happy", "excited")
- Choix de la choreo idle (dropdown des choreos existantes)

#### Mode Personnalité
- Preset : **Excited** / **Calm** / **Sneaky** / **Patrol**
- Chaque mode ajuste : fréquence des sons random, catégories favorisées, vitesse de rotation dôme random
- Exemple : Excited = sons fréquents, beaucoup de mouvement dôme / Calm = rare, doux

#### Startup Sequence
- Son joué au démarrage du Pi (dropdown fichiers audio)
- Choreo jouée au démarrage (dropdown choreos, option "aucune")
- Délai avant le startup (ex: 5s pour laisser le temps aux drivers de s'initialiser)

**Complexité :** Moyenne — nécessite un scheduler dans `main.py` + config dans `local.cfg [behavior]`  
**Priorité :** ⭐⭐⭐ (R2 devient vivant en convention sans intervention)

---

### 📺 Display — Écran RP2040

**Concept :** Contrôler ce que l'écran GC9A01 du corps affiche.

#### Contenu au boot
- **IP Master** (wlan1) — déjà dans le backlog, très utile pour SSH sans écran
- **Nom du robot** — ex: "R2-D2" affiché au centre
- **Animation** — une des animations existantes du firmware
- **OFF** — écran éteint après le boot

#### Message personnalisé
- Champ texte libre (max 20 chars) affiché en boucle au repos
- Exemple : "ARTOO" ou "HELLO THERE"

#### Luminosité
- Slider 10–100% (commande envoyée au RP2040 via DISP:BRIGHT:N)

**Complexité :** Faible-Moyenne — nouveau protocole DISP: + config `local.cfg [display]`  
**Priorité :** ⭐⭐⭐ (IP au boot = déjà dans le backlog officiel)

---

### 🩺 Diagnostics — Santé du système

**Concept :** Voir l'état interne sans SSH.

#### Status services
- Tableau en temps réel : Master ✅ / Slave ✅ / UART ✅ / VESC L ✅ / VESC R ✅ / Audio ✅ / Teeces ✅
- Polling toutes les 2s via `/status`
- Couleur : vert / orange / rouge selon l'état

#### Log viewer
- Les 50 dernières lignes du journal Flask (`journalctl -u r2d2-master -n 50`)
- Bouton REFRESH
- Filtre : ALL / ERROR / WARNING

#### Stats UART
- Messages envoyés/reçus depuis le boot
- Erreurs CRC (indique des problèmes de slipring ou de câblage)
- Latence heartbeat (temps de réponse Slave)

#### Ping Slave
- Bouton TEST → envoie un heartbeat forcé → affiche le temps de réponse ou TIMEOUT

**Complexité :** Moyenne — nécessite de nouveaux endpoints API (`/diagnostics/logs`, `/diagnostics/stats`)  
**Priorité :** ⭐⭐⭐ (très utile pour le bench et les conventions)

---

### 🎚 Sound Profiles — Audio avancé

**Concept :** Contrôle fin de l'audio pour différents contextes.

#### Profils de volume sauvegardés
- 3 slots : **Convention** / **Maison** / **Extérieur**
- Chaque profil stocke : volume master, volume par catégorie
- Un bouton par profil → applique instantanément

#### Catégories dans la rotation random
- Liste de toutes les catégories audio avec checkbox
- Décocher "scream" si tu veux pas effrayer les enfants en convention 😄
- Sauvegardé dans `local.cfg [audio] excluded_categories`

#### Son de démarrage
- Dropdown fichier audio joué au boot (optionnel)
- (Peut être dans Behavior aussi)

**Complexité :** Faible — surtout config + logique audio existante  
**Priorité :** ⭐⭐ (pratique mais pas urgent)

---

### 🗃 Backup & Restore — Sauvegarde config

**Concept :** Exporter/restaurer toute la config d'un coup.

#### Export
- Bouton **EXPORT CONFIG** → télécharge un `.zip` contenant :
  - `local.cfg`
  - `dome_angles.json`
  - `servo_angles.json`
  - Tous les `.chor`
  - `bt_config.json`

#### Import
- Upload d'un `.zip` → décompresse, vérifie, applique, redémarre

#### Reset Factory
- Bouton protégé (Admin Guard) → supprime `local.cfg`, remet les défauts
- Confirmation en 2 étapes obligatoire

**Complexité :** Moyenne — zip/unzip via Flask, endpoint `/settings/backup`  
**Priorité :** ⭐⭐ (très utile si tu changes de Pi ou réinstalle)

---

### ⏰ Scheduler — Planification (futuriste)

**Concept :** R2 joue des séquences à des heures précises.

#### Tâches planifiées
- Jusqu'à 5 slots : heure + action (choreo ou son)
- Exemple : 14h00 → jouer "march.chor" (parade à heure fixe en convention)
- Exemple : toutes les 15 minutes → son random catégorie "excited"

#### Activation/désactivation
- Toggle ON/OFF global du scheduler
- Activer seulement quand tu veux (convention vs maison)

**Complexité :** Élevée — thread scheduler dans `main.py` + persistance  
**Priorité :** ⭐ (fun mais vraiment pour plus tard)

---

## Résumé — Matrice de priorité

| Panneau | Utilité bench | Utilité convention | Complexité | Priorité |
|---------|--------------|-------------------|------------|----------|
| 🎯 Calibration (rename) | ⭐⭐⭐ | ⭐⭐⭐ | Nulle | **Maintenant** |
| 📺 Display (IP boot) | ⭐⭐⭐ | ⭐⭐ | Faible | **Court terme** |
| 🩺 Diagnostics | ⭐⭐⭐ | ⭐⭐ | Moyenne | **Court terme** |
| 🤖 Behavior | ⭐ | ⭐⭐⭐ | Moyenne | **Avant convention** |
| 🎚 Sound Profiles | ⭐ | ⭐⭐⭐ | Faible | **Avant convention** |
| 🗃 Backup | ⭐⭐ | ⭐ | Moyenne | **Quand stable** |
| ⏰ Scheduler | ⭐ | ⭐⭐ | Élevée | **Plus tard** |

---

## Notes techniques

- Tous les nouveaux panneaux suivent le pattern sidebar existant (`switchSettingsPanel()`)
- Nouvelle config → toujours dans `local.cfg` avec `configparser`, jamais hardcodé
- Nouveaux endpoints API → nouveaux blueprints Flask ou extension de `status_bp.py`
- Admin Guard appliqué aux actions destructives (Backup/Restore, Reset Factory)

---

## 🧠 Phase Future — Intelligence Artificielle (non prioritaire)

**Vision :** R2 semble vraiment vivant — il reconnaît les gens, réagit aux voix, répond intelligemment.

**Contrainte matérielle :** Tout doit tourner **en local** sur le Pi (offline, autonome en convention).  
**Plan B hardware :** Pi 5 si le Pi 4B 2GB est trop limité pour l'inférence locale.

### Reconnaissance faciale
- Caméra USB déjà en place (holo projector)
- **Face detection** → R2 tourne le dôme vers la personne (dome motor)
- **Face tracking** → suit la personne qui se déplace
- **Face recognition** → reconnaît des visages enregistrés → réaction personnalisée ("Hey, c'est Jean!")
- Stack envisagée : OpenCV + `face_recognition` (dlib) sur Pi

### Reconnaissance vocale
- Nécessite un **microphone USB** (pas encore dans le système)
- **Wake word** : "Hey Artoo" → R2 sort de veille
- **Speech-to-text** offline : Vosk ou Whisper.cpp (léger, Pi-compatible)
- Commandes vocales → déclenche sons/choreos/réponses

### Personnalité IA
- R2 "comprend" son environnement et réagit de façon contextuelle
- Génère des séquences de bips/sons R2 appropriés selon la situation
- Potentiellement : petit LLM local (Ollama + modèle quantisé) pour des réponses contextuelles

### Panneau Settings futur : `🧠 Intelligence`
- Toggle face tracking ON/OFF + sensibilité
- Gestion des visages connus (ajouter/supprimer)
- Wake word configuration
- Mode privacy (désactiver tout)
- Sélection du modèle STT

**Priorité :** 🔮 Phase 5+ — après assemblage final et tests complets  
**Hardware requis :** Microphone USB + potentiellement Pi 5

---

*Document en attente de validation — aucun code écrit*
