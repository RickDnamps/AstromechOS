# 💡 AstromechOS — Idées à développer (UX & effet WOW)

> Brainstorm vivant : pistes d'amélioration UX + "effet WOW", au-delà du backlog `bd`.
> Créé le 2026-05-26. **Aucune n'est encore un ticket** — promouvoir dans `bd` au moment de choisir.
>
> **Légende** — 💥 effet WOW (1→3) · 🛠️ effort (S/M/L) · 🏆 = vaut le coup de "brûler des tokens".
> Quand une idée étend un item du backlog `bd` existant, c'est noté *(étend …)*.
>
> **Workflow** : choisir une idée → `bd create` → skill `brainstorming` (design) → `writing-plans` (plan) → implémentation + tests live.

---

## 🎭 Showmanship — conventions / foule

- [x] **🏆 #1 — Piste "SHOW" dans le timeline choreo (bloc-référence-choré)** · 💥💥💥 · 🛠️M · ✅ **LIVRÉ 2026-05-26** (epic software-gio, commits 72c8052..17c24f8 ; voir `bd memories show-track-feature` + AUDIT_HISTORY phase SHOW)
  **Approche retenue (réflexion 2026-05-26)** : au lieu d'un séquenceur séparé, ajouter une **piste "SHOW"** (sous Drive) où un bloc = une **référence** vers un autre `.chor` (choisi dans l'inspector). Réutilise tout l'éditeur (drag, inspector, save/load) → effort L→M, et ça compose avec les autres pistes (flourish son/lumière entre deux choré).
  **Décisions d'archi à clouer** :
  1. **Référence (pointeur), pas snapshot** → expansion au PLAY (la sous-choré reste éditable live).
  2. **Pas de `safe_play` récursif** → pré-pass "flatten" qui injecte les events de la sous-choré décalés de `T` dans la timeline jouée (player reste mono-choré, safety intacte).
  3. **Piste séquentielle** (blocs bout-à-bout / warn sur chevauchement) pour éviter les collisions de dôme/servos.
  4. **Garde anti-cycle** (A→B→A interdit, valider au save+play) + **brancher `cascade_rename`/`cascade_delete`** (le rename/delete d'une choré met à jour les références SHOW, comme les shortcuts).
  5. **Agréger `uses_propulsion`/`uses_dome`** sur toutes les choré référencées → lockout per-axe correct.
  - Le bloc s'affiche à la vraie durée de la choré référencée. *(remplace l'ancien "Show Director" séparé ; étend "Scènes/Presets")*

- [ ] **🏆 #2 — Mode "crowd-reactive" via la caméra** · 💥💥💥 · 🛠️L
  La caméra OTG détecte visage/mouvement → le dôme se tourne vers la personne la plus proche + son "curious" + frémissement de panneaux. « Il m'a regardé !! ». *(étend "AI tracking", cadré personnalité réactive)*

- [ ] **#3 — Lumières + dôme réactifs à la musique** · 💥💥💥 · 🛠️M
  FFT sur le MP3 en cours (ou un micro) → AstroPixels pulsent + dôme rebondit sur le beat. Cantina → le droïde "danse".

- [ ] **#4 — Wake-word "Hey Artoo"** · 💥💥 · 🛠️M
  Micro tablette → mot-clé → réponse aléatoire / behavior. Interaction mains-libres avec la foule.

## 🕹️ UX opérateur — piloter mieux, yeux sur la foule

- [ ] **#5 — Gamepad haptique + repères audio** · 💥💥 · 🛠️S
  Vibration manette sur E-STOP / rampe anti-bascule / batterie basse. Piloter sans regarder l'écran.

- [ ] **🏆 #6 — Roue de commande radiale (game-style)** · 💥💥 · 🛠️M
  Maintien d'un bouton → menu radial des sons/behaviors top sous le pouce ("weapon wheel"). Plus rapide que la grille de shortcuts.

- [ ] **#7 — Tilt-to-look (gyroscope)** · 💥💥 · 🛠️M
  Incliner la tablette → le dôme/caméra suit. Immersif en POV caméra.

- [ ] **#8 — Mini-carte "ghost trail"** · 💥 · 🛠️M
  Trace estompée des déplacements (intégration RPM VESC) — utile dans les espaces serrés.

## 👥 Multi-droïde — le logiciel vise N robots

- [ ] **🏆 #9 — Contrôle "escouade"** · 💥💥💥 · 🛠️L
  Découverte des autres AstromechOS sur le réseau → switch entre eux OU séquence synchronisée de groupe (3 droïdes dansent à l'unisson). Showstopper.

- [ ] **#10 — AstromechOS Hub : partage communautaire** · 💥💥 · 🛠️M
  Export/import `.chor` + thèmes via code/QR partageable. Les builders s'échangent leurs choré. *(s'appuie sur Backup)*

- [ ] **#11 — Mode "co-pilote" spectateur (QR)** · 💥💥 · 🛠️M
  Un QR sur le droïde → invité ouvre un contrôle web limité + rate-limité + safe (jouer un son, saluer) sur son tél. Les enfants interagissent sans la tablette. *(s'appuie sur auth + netBreaker)*

## 🤖 IA / intelligent

- [ ] **🏆🏆 #12 — Générateur de choré en langage naturel (propulsé Claude)** · 💥💥💥 · 🛠️L
  « fais peur, puis jette un œil prudent au coin » → un LLM compose la timeline `.chor` depuis les briques existantes. LE token-burner — et méta : Claude Code construit une feature propulsée par Claude.

- [ ] **#13 — Diagnostics auto-narrés** · 💥 · 🛠️S
  Le cockpit parle : « VESC gauche à 72°C, pense à une pause » (TTS).

- [ ] **#14 — Mood Engine v2 : profils de personnalité** · 💥💥 · 🛠️M
  Sassy / Sleepy / Hyper / Patrol biaisent idle behaviors + choix des sons + tempo lumières. *(étend "Personnalité")*

## 🔧 Plaisir du builder

- [ ] **🏆 #15 — Visualiseur d'I/O corps entier (live)** · 💥💥💥 · 🛠️M
  SVG animé du droïde où chaque servo/HAT/VESC s'allume quand il bouge — comme le live-monitor de choreo, mais pour tout le corps. Debug + wow.

- [ ] **#16 — Flight recorder + replay** · 💥💥 · 🛠️M
  Enregistre une session (inputs + télémétrie) → rejoue-la OU convertis-la en `.chor`. *(étend "Enregistreur de mouvements")*

- [ ] **#17 — Wizard "premier boot" avec checks live** · 💥 · 🛠️M
  Setup animé qui vérifie chaque sous-système en vrai (UART, VESCs, servos, caméra) avec ✓ verts. *(étend "SD image creator")*

---

## 🎯 Top 3 "brûler des tokens"
1. **#12** — Générateur de choré en langage naturel (jamais vu sur un droïde, wow + utilité réelle, méta).
2. **#2 ou #3** — Crowd-reactive / music-reactive (caméra + audio déjà là → meilleur wow public par token investi).
3. **#9** — Contrôle escouade multi-droïde (concrétise le pivot "N robots" + showstopper convention).

## 📌 Notes
- Ces idées **complètent** le backlog `bd` (`bd list --status=open`) — certaines l'étendent (noté ci-dessus).
- Sécurité : toute nouvelle voie de contrôle (co-pilote QR, escouade, wake-word) doit respecter la chaîne safety (`@require_admin` sur les mutations, E-STOP/heartbeat jamais gatés, netBreaker, rate-limit).
- Promotion : `bd create --title="…" --type=feature --priority=N`, puis brainstorm → plan → build.
