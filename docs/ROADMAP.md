# R2-D2 Control — Roadmap & Feature Ideas

> Brainstorm session 2026-03-22 — priorités et idées pour les prochaines phases de développement.

---

## ✅ Déjà en production

| Fonctionnalité | Notes |
|---|---|
| UART Master↔Slave + CRC + watchdog | 3 couches de sécurité indépendantes |
| Audio — 317 sons, 14 catégories | mpg123, volume cubique, random par catégorie |
| Teeces32 FLD/RLD/PSI | JawaLite, preview live dans UI |
| RP2040 LCD GC9A01 | 6 écrans (BOOT/OP/LOCKED/NET/TELEM/BUS) |
| 40 séquences comportementales .scr | scared, excited, patrol, cantina, leia… |
| REST API Flask + dashboard web 6 onglets | dark blue R2-D2 theme, mobile-first |
| App Android | offline banner, auto-discovery IP |
| Manette BT evdev (Pi-native) | Shield/Xbox/PS, mapping configurable |
| Jumelage BT depuis l'UI | scan / pair / unpair sans SSH |
| BT battery % + RSSI | affiché en live dans Config tab (sysfs + hcitool, polling 30s) |
| BT keep-alive joystick | thread 300ms — corrige VESC cut quand joystick maintenu immobile |
| BT panneaux config-aware | angles/vitesse depuis servo_angles.json, pas de valeurs hardcodées |
| BT inactivity timeout étendu | slider 600s + saisie manuelle jusqu'à 3600s |
| Caméra USB autodetect | sysfs scan — pas de `/dev/videoN` hardcodé · auto-reconnect stream |
| Admin inactivity tous onglets | VESC / Choreo / Config trackés via pointerdown + _activeTabId |
| Déploiement auto (bouton dôme) | git pull + rsync + reboot en un clic |
| E-STOP + RESET sans restart | PCA9685 SLEEP instantané |
| Cockpit Status Panel complet | Topbar propre · pills HB/UART/BT · pill SLAVE · E-STOP overlay · STATUS toujours à jour |
| HAT diagnostic cockpit | Dome/Body Servo HATs · Motor HAT I2C probe · RP2040 Screen health · labels config-driven |
| CSS theme system | 8 built-in themes · theme customizer avec live preview · 7 polices sci-fi |
| Behavior engine ALIVE | idle behaviors configurables |

---

## 🔥 Priorité 1 — Manette Performance complète

> La Shield devient un instrument de spectacle, pas juste un joystick.

- [ ] **Éditeur de mapping visuel** dans l'onglet Config
  - Chaque bouton/axe → dropdown : son, catégorie, séquence spécifique, panneau, mode…
  - Gâchettes L2/R2 = volume ou vitesse dôme en temps réel
- [ ] **Mode Conduite** (défaut) — sticks = drive + dôme, boutons = sons rapides
- [ ] **Mode Performance** (combo bouton pour switcher) — tous les boutons déclenchent des séquences/sons, sticks font le dôme seulement
- [ ] Déclencher des **séquences .scr** directement depuis la manette

---

## 🔨 Priorité 1b — VESC Safety Lock *(critique — avant utilisation en public)*

> Un seul VESC en panne = poussée asymétrique = robot incontrôlable. Le système doit refuser de bouger, pas juste avertir.

- [ ] **Détection VESC_DEGRADED** — trigger si :
  - VESC L ou R absent au boot (pas de telemetry dans les Xs)
  - Fault code actif (`fault_str ≠ FAULT_CODE_NONE`) sur l'un ou l'autre
  - Timeout telemetry en cours d'opération
  - CAN scan ne trouve pas VESC ID2
- [ ] **Blocage propulsion total** — aucune commande `M:` envoyée au Slave, quel que soit la source (web / BT gamepad / Android)
- [ ] **Overlay Drive tab** — alerte rouge évidente sur la zone caméra (style "STREAM TAKEN") ou bannière fixe en bas
  - Message : `PROPULSION DISABLED — VESC [L/R] not responding`
  - Joystick web grisé et non-interactif
  - BT gamepad : axe drive ignoré (keepalive supprimé aussi)
  - Android : même gate JS
- [ ] Dome / audio / servos / séquences restent **100% opérationnels**

> ⚠️ Pour l'instant les tests bench avec un seul VESC sont acceptables. Cette protection est obligatoire avant toute utilisation autour de personnes.

---

## 🔥 Priorité 2 — Télémétrie VESC + Protection batterie

> Le robot ne mourra jamais d'une batterie à plat sans prévenir.

- [ ] **Dashboard temps réel** — voltage cellule, %, temp moteurs, courant instantané, RPM
- [ ] **Graphique historique** — consommation sur la session
- [ ] **Alertes progressives automatiques**
  - 30% → son proc (avertissement doux)
  - 15% → son alarm + LED rouge RP2040
  - 10% → mode économie auto (vitesse -50%, sons off)
  - 5% → arrêt moteurs + séquence shutdown
- [ ] **Refus de démarrage** si voltage trop bas au boot
- [ ] Affichage voltage sur RP2040 LCD (écran TELEMETRY déjà prévu)

---

## 🔥 Priorité 3 — Mode Show / Autonomie intelligente

> R2-D2 "vit" quand tu veux, se tait quand tu veux.

- [ ] **Toggle "Mode Show"** dans l'UI + raccourci manette dédié
- [ ] **Humeur aléatoire intelligente** — pool pondéré de séquences + sons + panneaux + dôme avec pauses naturelles qui varient, jamais répétitif
- [ ] **Programmateur de show** — timeline dans l'UI
  - "À 0:00 joue startup, toutes les 5 min une séquence random, à 1:00 joue cantina"
  - Export/import de programmes de show (.json)
  - Idéal pour convention avec horaire précis

---

## 🔥 Priorité 4 — Éditeur visuel de séquences

> N'importe quel builder peut créer ses propres séquences sans toucher à un fichier texte.

- [ ] **Timeline drag & drop** dans le dashboard
  - Blocs colorés par type : son 🔊, servo 🦾, dôme 🔄, Teeces 💡, pause ⏸
  - Lignes parallèles pour les actions simultanées
- [ ] **Aperçu en temps réel** — joue la séquence pendant qu'on la construit
- [ ] **Bibliothèque** — sauvegarder, nommer, partager
- [ ] **Export .scr** — compatible avec le format existant
- [ ] **Import** — glisser-déposer un `.scr` existant pour l'éditer visuellement

---

## 🔥 Priorité 5 — Self-Test & Diagnostic

> Partir en convention avec la certitude que tout fonctionne.

- [ ] **Self-test au boot** (optionnel, activable dans config)
  - Teste chaque servo, joue un son, tourne le dôme, vérifie UART + RP2040 + Teeces
  - Résultat en 30 sec sur le LCD + dans les logs
- [ ] **Onglet Diagnostic** dans le dashboard
  - Tester chaque composant individuellement
  - Voir le log system en direct
  - Rapport de santé vert/orange/rouge pour chaque sous-système
- [ ] **Score global de santé** affiché en permanence dans le header de l'UI

---

## 🌱 Priorité 6 — Petits capteurs, grand impact (~15$ hardware)

> Sans micro ni caméra, R2 peut déjà réagir à son environnement physique.

- [ ] **Ultrasons HC-SR04** sur le Slave (GPIO)
  - Quelqu'un s'approche à <1m → dôme tourne vers eux + son "curious"
  - Désactivable en mode silencieux
- [ ] **Accéléromètre MPU6050** sur le Slave (I2C)
  - R2 bousculé → son "surprised"
  - R2 incliné → son "alarm" + séquence stabilisation

---

## 🔮 Phase future (après caméra)

> Ces features nécessitent du hardware supplémentaire ou sont très complexes.

| Feature | Hardware requis | Complexité |
|---|---|---|
| 🎙️ **Micro dans le dôme** — contexte émotionnel, commandes vocales, réponse ambiance | Dongle USB audio ~8$ ou jack TRRS Master | ⭐⭐⭐ |
| 📷 **Caméra USB** — streaming live ✅ · suivi personne 📋 | Caméra UVC 3.6mm OTG 720/1080P commandée — holo projector housing, MJPEG hardware natif | ⭐⭐⭐⭐ |
| 👁️ **Reconnaissance faciale** — saluer par prénom, mémoire visiteurs | Caméra + modèle ML | ⭐⭐⭐⭐⭐ |
| 🏷️ **NFC/RFID** — tapoter un badge = déclencher une séquence | Module NFC ~8$ | ⭐⭐ |
| 👥 **Multi-manette** — pilote + opérateur (sons/séquences) | 2e gamepad BT | ⭐⭐ |
| 🌐 **API externe / webhooks** — déclencher R2 depuis IFTTT, Home Assistant, etc. | Aucun | ⭐⭐ |

---

## 🧠 Vision architecture Master Pi

Le **Master Pi (dôme) = cerveau central** :
- Flask API, séquences, servos dôme, Teeces32 ← déjà là
- Manette BT evdev ← déjà là
- **Caméra USB** (phase 5) ← observe les gens
- **Micro USB** (phase future) ← écoute l'ambiance
- **Mode Show** ← coordonne tout en autonomie

Le Slave Pi (corps) reste concentré sur le hardware physique : propulsion, servos body, audio, capteurs.

---

*Dernière mise à jour : 2026-05-08*
