# AstromechOS — UI / Frontend Patterns

> Reference catalog of reusable frontend building blocks (helpers, CSS classes,
> status fields, endpoints). CLAUDE.md keeps only the high-level rules; the full
> detail lives here so it isn't loaded into every session's context.
>
> **RULE before building any new UI**: reuse these patterns, don't reinvent.
> Grep the existing classes (`holo-slider`, `btn-*`, `settings-card`…) before
> writing new HTML — never a native browser default when a custom class exists.

---

## 🖥️ Topbar & Cockpit

**Topbar (clean)** : brand · `pill-offline` (Master unreachable) · `pill-slave` (UART down) · `cockpit-btn` STATUS · battery arc · temp + clock.

**Cockpit pills** : `ck-pill-hb` (HB ok/down) · `ck-pill-uart` (≥95% green / 70-94% orange / <70% red) · `ck-pill-bt` (RSSI threshold).

**STATUS button color** updated every poll via `cockpitPanel.updateBtn(data)` (bench mode = orange intentional).

**E-STOP overlay** : `position:fixed inset:0 pointer-events:none z-index:9999`, class `active` = red pulsing border, synced from `data.estop_active`. Prompt `.estop-prompt` à l'intérieur : titre rouge "EMERGENCY STOP ENGAGED" + sub "Press RESET E-STOP below to re-arm drive" (opacity contrôlée par le `.active` de l'overlay parent).

**SERVICES HAT health row** (chantier 2026-05-30, consolidated) : single row inside the SERVICES grid (slot ex-Dome/Body Servo/Body Motor rows, between BT Gamepad and Body Screen), rendered by `cockpitPanel._hatHealthRow(data)`. Left = layout summary `Master X HAT(s) · Slave Y HAT(s)` (from `data.hats.{master,slave}.hats[]`). Right = Orbitron status pill driven by **LIVE driver metrics** (`data.dome_hat_health[]` + `body_hat_health[]` + `motor_hat_health`, refreshed every `/status` tick): green `ALL HEALTHY` / red `⚠ N ERRORS` / red `⚠ COLLISION @…` (top priority, needs PCA9685 solder fix) / amber `⚠ DEGRADED — RESCAN`. Whole row clickable → Settings → HATs (per-HAT detail lives there: errors count, chip, address). The previous separate `<div id="ck-hardware-health">` widget + gray badge were dropped at the same commit. Backend sources : `reg.dome_servo.hat_health()` (Master direct) · `reg.slave_uart_health['body_hat_health' / 'motor_hat_health']` (Slave UART relay).

**Cockpit clickable shortcuts** (chantier 2026-05-30) : every cockpit row is a clickable shortcut to its admin surface via the standard router so admin-gated panels naturally land on the password prompt (no bypass). Two helpers generate the inline onclick string :
- `cockpitPanel._cockpitGoto(panel)` → Settings sub-panel (uses `switchTab('settings') + setTimeout(switchSettingsPanel(panel), 50ms)`)
- `cockpitPanel._cockpitTab(tab)` → top-level tab (`switchTab('drive'|'audio'|'sequences'|'lights'|'choreo'|'settings')`)

`_svcRow(label, cls, val, panel?)` has an optional 4th arg : when set, adds the onclick + `.cockpit-row-clickable` class (cursor pointer, subtle hover slide). Activity/Network rows that need HTML content (inline spans) build their own `<div>` manually with the same class + onclick.

**Mapping verrouillé 2026-05-30** (16 clickable rows) : SERVICES → E-STOP → System · Bench Mode → VESC · UART → Diagnostics · VESC L/R → VESC · AstroPixels → Lights · Camera → Camera · BT Gamepad → Bluetooth · HAT health → HATs · Body Screen → System · Body Audio → Audio ; ACTIVITY → Choreo → tab `choreo` · Audio → tab `audio` · ALIVE → Behavior ; NETWORK → Master/Slave IP → Network · Version → Deploy. Toute nouvelle row cockpit doit avoir un mapping (sinon discoverability cassée).

**JS syntax rule** : `StatusPoller` est un `class` (no trailing comma) · `cockpitPanel` est un object literal (trailing comma). Mixer = silent syntax error. **Toujours `node --check master/static/js/app.js` avant commit.**

**Drive mode pills overlay** (`#drive-mode-strip`) : `position:absolute top:8px center` SUR le flux camera (PAS dans drive-wrapper — sinon push le layout). Pills `mode-bench` (🛡 BENCH MODE, ambré pulsant) · `mode-kids` (👶 KIDS MODE X%, vert) · `mode-lock` (🔒 CHILD LOCK, rouge). Visible quand `vesc_bench_mode || lock_mode≠0`. Tooltip natif via `title=` pour l'explication complète.

**Anti-tip ramp visual cue** (`body.drive-ramping` / `body.dome-ramping`) : pulse ambré inset sur le joystick ring concerné pendant les 400ms du ramp-down. Source : `data.drive_ramp_active` / `dome_ramp_active` du `/status`.

**Joystick knob gradient color** : `Math.hypot(x, y)` → vert <33% / ambré <66% / rouge ≥66%. Box-shadow scale avec magnitude. Reset au release.

**STOWING button text** : pendant les ~3-5s de `_safe_home_runner`, le texte du bouton E-STOP devient `STOWING…`. Optimistic (instant au clic) + 500ms watch loop pour clear quand `data.stow_in_progress === false`. Pattern memo : commits `cc7532b..ccf22a3`.

**Toast position** : `top:60px` (PAS bottom — masquait le bouton E-STOP). Animation slide-down-on-enter, fade-out-on-exit.

**Themed dialogs** (`_appDialog` → `confirmDialog`/`alertDialog`/`promptDialog`, Promise-based) : remplacent les natifs `confirm/alert/prompt` (qui rendaient des boutons en locale OS, ex "Annuler"). Non-bloquants → l'overlay `.admin-modal` (z-index 2000) bloque le pointeur, et `_appDialog.isOpen()` gate le keydown drive pour que WASD ne pilote pas derrière. Détails : `bd memories the-themed-dialog-appdialog`.

---

## 🎨 Settings WOW patterns

**`withSaveFeedback(btn, asyncFn)`** universal helper (app.js) : wrap toute API save → button passe Saving… (spinner) → Saved ✓ (vert pulse) → restore. Failed path = red shake. Utilisé pour `saveConfig` (Deploy), `saveLightsBackend`, `saveBatteryCells`, `armsConfig._testRow`. Étendre aux autres save handlers.

**Settings nav grouping** : 5 sections via `.settings-nav-section-label` (header texte petit + ligne fade-to-transparent à droite, pointer-events:none) — OPERATOR / HARDWARE / CONNECTIVITY / APPEARANCE / SYSTEM.

**Mode switcher buttons** (Lock panel, `.lock-mode-switcher`) : 3 boutons grid avec colors sémantiques (vert/ambré/rouge) + icon + sub-label. `.active` class sync via `lockMgr.syncFromStatus`.

**Live preview before APPLY** (Battery, Camera bitrate) : `onchange` sur dropdowns/sliders update une `<div>` preview avec les valeurs calculées AVANT le save → operator informed.

**REBOOT/SHUTDOWN countdown overlay** (`#reboot-overlay`) : full-screen, big amber title + countdown 30→0 + polling `/status` jusqu'à reconnexion → auto `location.reload()`. Réutilisé par I2 deploy progress (custom title "UPDATING").

**Deploy commit card** : `GET /system/version` (commit + msg + relative date) + `GET /system/deploy_status` (git fetch + remote SHA + behind_count, cached 60s, admin-gated). Card visible avant UPDATE button.

**WiFi/BT signal bars** (`.signal-bars` + `.signal-bar.lit/.weak/.bad`) : SVG-like CSS 4-bar component, lit count = strength tier. WiFi % thresholds : ≥75/50/25 → 4/3/2/1 bars. BT RSSI : ≥-55/-65/-75 → 4/3/2/1. Color : green ≥-65 / amber ≥-75 / red.

**Custom card lists** (WiFi scan) : remplace `<select><option>` quand on veut SVG + multi-info per row. Garde un `<select style="display:none">` pour la compatibilité form-state.

**Diagnostics auto-refresh** : `diagPanel._autoTimer` (5s) + `diagPanel._tailTimer` (2s tail mode) — self-clean check `.active` class à chaque tick.

**Behavior next-trigger countdown** : `/behavior/status` expose `next_idle_in_s` (computed depuis `last_activity + idle_timeout_min`). Frontend `_startCountdown` utilise `performance.now()` pour ticking local précis.

**Camera preview thumbnail** post-restart : `_showPreview()` injecte `<img src="/camera/stream?_=ts">` 2.2s après save (cold start), auto-close 8s plus tard pour libérer le stream.

**Badges pattern** : sur les fields spécifiques (jamais sur les section headers — confusant). REBOOT (ambré) pour conséquences lourdes (~30s Master reboot). LIVE (vert) parcimonieux. Note précise > badges partout.

**Loading states** : seulement si latence réelle >200ms. Fade artificiel sur des switches instant = sluggish, pas WOW. Pattern : voir `feedback_polish_matters.md` memory.

**Dynamic robot name** (`<span class="robot-name">R2-D2</span>`) : tout body copy qui mentionne le robot wrap dans ce span. Le default text est juste fallback — `StatusPoller` réécrit le textContent sur chaque poll depuis `data.robot_name` (skip `#header-robot-name` qui a son propre handler). Applique : settings notes, warnings VESC, audio note. Theme labels "R2-D2" intentionnellement STATIC (ce sont des noms de thèmes).

**HATs sub-panel** : `spanel-hats` contient I2C HATs (Master/Slave servo + motor HAT) + UART Latency (`body_servo_uart_lat` + RTT MEASURE/APPLY). Extrait du panel System pour cohérence sémantique (System = REBOOT/SHUTDOWN/password seulement). Dans la section nav HARDWARE entre VESC et Arms.

**Heartbeat Web Worker** (`startAppHeartbeat`) : le heartbeat 200ms tourne dans un Worker thread (inline Blob, pas de .js séparé) pour éviter qu'un sync block du main thread (heavy choreo render = 1-1.5s) cause des heartbeat misses → R3 fire E-STOP à tort. Fallback à `setInterval` si Worker fail. `_hbStart/_hbStop` sur visibilitychange. `TIMEOUT_S` server bumped à 1.5s pour tolérance jitter LAN.

**Optimistic joystick lock** : `/choreo/list` expose `uses_propulsion` + `uses_dome` par row (pré-calculés en backend de `tracks.propulsion.length > 0` etc.). Frontend appelle `_setChoreoLockUI(usesProp, usesDome, name)` IMMÉDIATEMENT au click (avant l'ACK backend) + rollback `_setChoreoLockUI(false,false,'')` si POST refusé (409/503/429). StatusPoller poursuit la sync canonique. **Coverage matrix** : Sequences tab `scriptEngine.play()` ✓ · `choreoEditor.play()` ✓ · `shortcutsRunner._trigger()` ✓ (ajouté 715bca5) · **BT gamepad ✗** (pas de hook frontend possible, le press se fait sur le Pi — seul le poll cadence aide). **RÈGLE** : tout nouveau trigger path qui fire `play_choreo` DOIT call `_setChoreoLockUI` optimistiquement + rollback sur refus. Détails : `bd memories joystick-lockout-reaction-time`.

**StatusPoller cadence** : `start(intervalMs = 1000)` depuis 715bca5 (2026-05-16). Avant: 2000ms depuis l'origine du projet (commit `bf634bd`). Worst-case lockout reaction pour les paths sans optimistic lock (= BT gamepad) : 1s, average 500ms. `/status` est ~3KB JSON, doubler le rate (~30→60 req/min) reste largement sous la capacité Flask sur Pi 4B. `_inFlight` guard prévient le stacking si Flask devient lent (long-running save, deploy).

**Editor playhead guard** (`choreoEditor._startPolling`) : sameChoreo check = `loadedName && status.name && status.name === loadedName`. Si rien loadé OU mismatch → playhead figé à 0, timecode = "▶ {playing_name}". Évite que la startup choreo (post-deploy auto-fire) fasse avancer le playhead d'un editor vide.

**Global choreo abort toast** (`StatusPoller`) : edge-trigger sur transition `_lastPlaying:true → _newPlaying:false` AVEC `choreo_abort_reason` set ET reason ∈ {uart_loss, undervoltage, overheat, overcurrent} (pre-flight rejects estop_active/stow_in_progress filtrés — operator a déjà vu le 503). `_lastPlaying` initialisé au premier poll comme baseline silencieux → pas de false toast au page load.

**Signal density rule** : 2 signaux clairs > 3 signaux loud. E-STOP exemple = red border pulse + bottom button text swap suffisent ; ajouter un prompt overlay centré = saturation. Cas inverse (STOWING, mode pills, ramp visual) = vrais infos manquantes, justifient le visuel. Distinguer "feedback absent" vs "feedback redondant".

**Optimistic concurrency token** (`X-Categories-Version` header + `If-Match` POST) : pour endpoints où 2 admins peuvent modifier simultanément (categories reorder). Server retourne mtime dans header GET, client le renvoie via `If-Match` sur POST mutation, server compare → 409 sur mismatch. Frontend refresh + toast. Pattern réutilisable pour toute ressource shared-state. Backwards-compat : If-Match optionnel, legacy clients sans header passent.

**Per-robot localStorage namespacing** (`_lsGet`/`_lsSet` helpers) : multi-robot operator du même browser ne devrait pas partager last-played markers (R2 et BB-8 ont leurs propres). StatusPoller cache `robot_name` via `_setCachedRobotName(data.robot_name)` au premier poll. `_lsKey(base)` retourne `base:robot_name` ou `base` si pas encore cached. `_lsGet` fallback automatique sur legacy key pour migration. Appliqué à `astromech-last-sound` + `astromech-last-choreo`.

**Sequence card visual hierarchy** :
- `.seq-card-locks` (top-left) : 🚗 propulsion / ↻ dome — pre-play indicator que la séquence va lock les joysticks (operator sait AVANT de tap)
- `.seq-card.last-played` (top-right green dot + left border)
- `.seq-card.running` (cyan border pulse) + `.seq-card.looping`
- `.seq-card-loop` (faint 0.18 opacity sur idle cards, 0.9 hover) — gesture discoverable
- `.seq-card-meta` (footer `⏱2.4s · 12evt`) toujours visible — touch parity vs hover-only title tooltip

**Optimistic local mutation pattern** (drag-to-pill recategorization) : muter `_scripts.find(name).category = newCat` en mémoire + `_renderPills()/_renderGrid()` ciblé AVANT le POST. POST en background, rollback + toast si fail. Évite full `load()` (refetch list + categories) pour 1 card move. Status poll catche divergence dans 2s si silent fail. Pattern : `optimistic mutation → POST .then(fail ? rollback : noop)`.

**Single-instance player invariant** : ChoreoPlayer is single-instance (1 sequence at a time). Frontend `scriptEngine.play()` doit clear `_running` set AVANT d'ajouter le nouveau name, sinon double-click affiche 2 cards running pendant 2s (backend serialize via `_play_lock` mais UI ment).

**STOP button visible quand running** (`#seq-stop-btn`) : `display:flex` only when `running.length > 0`. Reuse de `scriptEngine.stopAll()` (déjà existant). Alternative was long-press ou re-tap = obscure. Pattern : critical safe-state actions doivent avoir une affordance visible, pas cachée derrière un gesture.

**Inline rename pattern** (sequence label + category label) : `_startRename`/`_startCategoryRename` swap le span avec un `<input>` in-place. Enter/blur save, Esc cancel. Width capé via `maxLength` matching server validation. CRITICAL: track `_renamingName` guard pour que le périodic reload 15s ne destroy pas l'input mid-edit.

---

## 🎬 Boot reveal & rendering stability (anti-FOUC)

**`app-ready` reveal gate** (commit `c876ce5`) : tout le `<body>` est caché pendant le boot via CSS `body:not(.app-ready) { opacity: 0; pointer-events: none; }` (PAS de transition → reveal instantané "d'un coup sec"), et `init()` ajoute `document.body.classList.add('app-ready')` JUSTE APRÈS le `Promise.all` de chargement — à ce moment le thème est résolu, l'icône du header vient du 1er poll `/status`, et le layout joystick custom est déjà appliqué synchrone depuis le miroir localStorage dans `_initThemes` (qui tourne AVANT `init()`). **Filet de sécurité OBLIGATOIRE** : `setTimeout(() => document.body.classList.add('app-ready'), 3000)` dans le handler `DOMContentLoaded` → si un fetch de boot reject, la page n'est JAMAIS laissée invisible. Supprime le résidu qui flashait au hard-reload (thème sombre par défaut · joysticks fantômes · icône changeante "cheap") parce que `app.js` est un script non-deferred en bas du `<body>` → le navigateur peint le `:root` par défaut AVANT que thème/layout s'appliquent. Le pré-paint `<head>` vars-cache (commit `1f4bd3e`) reste en defense-in-depth. **RÈGLE** : toute nouvelle donnée visuelle async au boot (thème, icône, positions) DOIT être révélée via le gate, pas après-coup.

**Stable hairline separators — JAMAIS de bordure 1px translucide sur un élément sticky** (commit `c876ce5`) : le séparateur header↔menu blanc clignotait 1px↔2px aléatoirement au reload (pire en cliquant l'onglet Lights, dont le canvas dome-sim repaint). **PAS un bug de layout** — la géométrie DOM est byte-identique (mesurée Playwright, aucun scrollbar : `body{overflow:hidden}`). C'est un artefact de rendu sous-pixel à DPR fractionnaire (Windows 125/150 %) avec DEUX amplificateurs : (a) un élément `position:sticky` a sa propre couche de compositing qui se re-raster à un offset sous-pixel variable par paint ; (b) une couleur TRANSLUCIDE haut-contraste (`rgba(255,255,255,.55)` blanc sur marine) antialiase sur 2 rangées device et sa couverture varie. **Preuve que c'est l'opacité** : dans le MÊME thème `r2d2_light`, l'underline opaque `#ffffff` de `.tab.active` n'a jamais clignoté. Les thèmes sombres (ex `r2q5` Rouge = acier sur quasi-noir) semblaient "parfaitement stables" UNIQUEMENT parce que la même variation est invisible en bas contraste — pas un mécanisme différent. **Fix** : couleur OPAQUE (`#9197a9` = équivalent opaque exact de l'ancien rgba sur le topbar marine → look inchangé) + `.topbar`/`.tabbar` en `position:relative` au lieu de `sticky` (sans risque : `body{overflow:hidden}` + onglets bornés en hauteur = rien ne défile jamais sous le header, donc sticky était un no-op qui n'ajoutait qu'une couche de compositing instable). **RÈGLE** : un séparateur fin (1px) = couleur OPAQUE sur un élément NON-composité (relative/static), JAMAIS translucide sur sticky/fixed. ⚠️ Headless Chrome ne reproduit PAS ce flicker (raster déterministe) → valider sur un vrai navigateur GPU-composité à DPR fractionnaire. Détails : `bd memories astromech-ui-fouc-and-divider-flicker-fixes`.

---

## 🛡️ Deploy security (Git DNA + Imager first-boot)

**Git DNA paternity check** (commit chantier `5a0faa7..34f7a9e`, 2026-05-28) : tout changement de `github.repo_url` (via le panneau Settings → Deploy, via `/api/deploy/save-config`, OU via `/boot/astromech_init.cfg` au premier boot) passe par `shared/git_provenance.validate_paternity` AVANT que `origin` ne soit touché. La fonction fait `git ls-remote` + `git fetch --no-tags` (sans `--depth` — un shallow grafte l'historique et casse l'`is-ancestor`) + `git merge-base --is-ancestor OFFICIAL_INITIAL_COMMIT FETCH_HEAD`. L'ancre est **figée en code** (`shared/git_provenance.py:OFFICIAL_INITIAL_COMMIT`) — pas dans la cfg, sinon un attaquant pourrait la substituer. **RÈGLE** : tout endpoint qui mute `origin`/`repo_url` DOIT appeler le validateur en amont du write ; sur fail, retourner 400 + `official_remote_preserved: true` et NE PAS écrire la cfg ni toucher au remote. Headless-testable via 12 tests `scripts/test_git_provenance.py` (tmp repos, pas de réseau). Doc complète : **[docs/DEPLOY_SECURITY.md](DEPLOY_SECURITY.md)** · `bd memories astromech-deploy-adn-firstboot-chantier-2026-05-28`.

**`/api/deploy/*` alias blueprint** (commit `61d4b68`) : `master/api/deploy_bp.py` expose 4 routes (`GET /status`, `POST /save-config`, `POST /update`, `POST /rollback`) qui **délèguent** aux handlers canoniques de `status_bp` + `settings_bp` (zéro logique dupliquée). `/save-config` whiteliste les clés `{github.repo_url, github.branch, github.auto_pull_on_boot, slave.host}` — toute autre clé → 400 avec `extra` + `allowed` listés. Le gate ADN s'active automatiquement quand `github.repo_url` change. Les routes legacy `/system/deploy_status` + `/system/update` + `/system/rollback` continuent de fonctionner (le panneau Settings → Deploy actuel les consomme).

**First-boot Imager bootstrap** (commit `f386a19` + `34f7a9e`) : `scripts/firstboot_setup.sh` + `master/services/astromech-firstboot.service.template`. Le service est un `oneshot` gardé par `ConditionPathExists=|/boot/ASTROMECH_FIRSTBOOT_READY` — il est **skippé entièrement** à chaque boot sauf si l'AstromechOS Imager a déposé le marker. Quand il fire, il : (1) inject les clés SSH publiques de `/boot/astromech_secrets/authorized_keys` dans `$TARGET_HOME/.ssh/authorized_keys` (atomic, dedupe, chmod 0600) ; (2) parse `init_config.json` pour le role + hostname (charset RFC-1123 strict — rejette `$(rm -rf /)`) ; (3) DNA-valide le `github.repo_url` configuré et swap `origin` + `reset --hard` si OK (sinon log + garde l'officiel) ; (4) shred le secrets dir + supprime le marker + `systemctl disable` self + reboot. Idempotent (le marker n'est supprimé qu'à la fin → un crash mid-way est retried au prochain boot). Doc : **[docs/DEPLOY_SECURITY.md](DEPLOY_SECURITY.md)**.

**I2C HAT detection — contrat read-only** (commit chantier `e40e376` → `0ec59df`, 2026-05-28) : `scripts/detect_hats.py` scanne 0x40-0x47 en **lecture seule absolue** + fingerprint via signature PCA9685 (SUBADR1/2/3 + ALLCALLADR — POR defaults 0xE2/0xE4/0xE8/0xE0 que notre driver ne modifie jamais) + convention ELECTRONICS.md (master = servo_dome partout, slave 0x40 = motor_drive 0x41+ = servo_body). Le contrat read-only est garanti **par trois couches indépendantes** : (1) classe-wrapper `ReadOnlySMBus` qui rejette les 7 write APIs avec `AssertionError` ; (2) fcntl flock `/run/astromech-i2c.lock` qui coordonne avec `_i2c_scan_lock` de diagnostics_bp ; (3) suite de 28 tests dont 6 end-to-end qui ASSERTENT `[c for c in FakeSMBus.calls if c[0].startswith('write')] == []`. Live-validé sur R2-D2 mid-PWM : scan 0x40-0x47 en 3 ms, JSON émis (score 4/4 confidence high), **zéro glitch servo, zéro log d'erreur du driver**. Output JSON atomique vers `master/config/hw_layout.json` (gitignored), override Imager via `/boot/hw_layout.json`. **RÈGLE** : tout nouveau code I2C de scan/probe DOIT passer par `ReadOnlySMBus` — n'instancier JAMAIS `smbus2.SMBus(1)` directement pour de la detection.

**Observation ≠ décision (résilience boot)** : la philosophie verrouillée pour le chantier de détection HAT — `detect_hats.py` observe (écrit le JSON), les services interprètent et choisissent d'opérer ou de passer en `DEGRADED`. Trois états distincts côté driver : (a) **READY** = HAT présent + signature OK → opération normale ; (b) **DEGRADED** = HAT absent du JSON → WARNING `'HAT @ 0x%02X missing — DEGRADED mode active'` + driver vivant mais I2C calls suspendus pour ce HAT (les autres sous-systèmes restent fonctionnels) ; (c) **CRITICAL** = collision d'adresse détectée (`ADDRESS_COLLISION` dans le JSON) → driver refuse de s'init, log `'CRITICAL: I2C Address Conflict at 0x40. Check hardware jumpers (A0/A1/A2)'`. Le boot ne brick JAMAIS sur (b) ; il refuse net sur (c) parce qu'opérer sur une collision = comportement erratique imprévisible. Doc : **[docs/DEPLOY_SECURITY.md](DEPLOY_SECURITY.md)** §3.5 + §4.5 (Dépannage I2C).

**Industrialisation Mapping HAT (chantier G, 2026-05-28)** — labels + calibrations ancrés à une **identité HAT stable** (`Body_HAT_A`, `Dome_HAT_A`...) au lieu de l'adresse I2C. Module `shared/hw_mapping.py` (244 LOC + 32 tests) expose `load_for(role)` / `synthesize_from_layout` / `flat_name(id, ch)` / `identity_for(flat)` / `normalise_calibration(raw, mapping)`. Les calibrations JSON sont en format **nested-by-identity** : `{"Body_HAT_A": {"0": {label, open, close, speed}, ...}}` au lieu de `{"Servo_S0": {...}}` flat. Backwards-compat : les noms externes `Servo_M{N}` / `Servo_S{N}` (.chor, shortcuts, arms, API) restent inchangés et résolvent vers `(identity, channel)` via `identity_for()`. Driver `_load_dome_angles` / `_load_servo_angles` normalisent legacy FLAT vers NESTED en mémoire au boot, écrivent NESTED au prochain save (migration-on-save). Re-mapping zero-config via `POST /hats/remap` (@require_admin) avec atomic write + driver hot-reload. **6 phases (G1→G6), 111 tests unitaires, 9 commits `01218c4 → b2a6048`**. Doc canonique : **[docs/MAPPING.md](MAPPING.md)**.

**Re-Mapping UI — blindage anti-collision (chantier G phase finale, 2026-05-28)** : les dropdowns de Settings → HATs → RE-MAP HAT IDENTITIES sont sourcés depuis `/hats/layout` — **uniquement les adresses physiquement détectées** par le scan I2C apparaissent (plus de range fictif 0x40..0x77). Si aucun HAT détecté côté nœud : note ambrée "⚠ No HATs detected — click 🔄 RESCAN HARDWARE first". Anti-collision client-side via `_checkRemapCollisions(table, banner, saveBtn)` qui fire au `change` de chaque dropdown ET au render initial : rangées en doublon passent en `.hat-remap-collision` (fond rouge, texte rouge bold, border rouge sur le `<select>`), bannière pulsante `.hat-remap-error-banner` "⚠ Collision d'adresse détectée — two identities cannot bind to the same physical address", bouton SAVE désactivé avec tooltip explicite. Defense-in-depth : si un client bypasse le bouton et POST direct, backend `/hats/remap` retourne HTTP 400 avec le message canonique `"address 0xNN assigned to more than one HAT; each physical address must be unique"`. Trois couches : UI dropdown filter → UI collision check → backend `seen_addrs` validation. **RÈGLE** : tout nouveau formulaire qui propose une adresse I2C DOIT lire les choix depuis `/hats/layout` (jamais générer une range hard-codée) ET appliquer la même primitive anti-collision si plusieurs entrées coexistent. Tests : `scripts/test_hats_remap.py` (12 tests dont 3 spécifiques au blindage anti-collision : `test_three_hat_collision_pairs` / `test_collision_with_case_variants_detected` / `test_legitimate_swap_no_collision`).

**SSH MOTD per-node (2026-05-28)** : `scripts/motd_astromechos.sh` installé via `scripts/install_motd.sh` à `/etc/update-motd.d/99-astromechos`. Affichage dynamique au login SSH : bannière ASCII ANSI gigaWOW en couleur d'identité du nœud (**cyan brillant Master / vert tactique Slave** — impossible de se tromper de terminal), badge `╣ DOME · MASTER ╠` ou `╣ BODY · SLAVE ╠`, git status ligne (Master : short sha + branch + ahead/behind vs origin via `git rev-list --left-right --count` sans fetch ; Slave : `VERSION` file + `rsync synced` badge puisque le slave n'a pas de `.git`). Sections SYSTEM (date, uptime, CPU temp avec pip 🟢<55 / 🟡 55-70 / 🔴 ≥70, disk %, RAM %, load), NETWORK (toutes les IPs locales non-loopback + cross-ping bidirectionnel via `ping -c 1 -W 1` = max 1s timeout), HARDWARE (parse `config_mapping.json` + `hw_layout.json` via python3 embedded, affiche `<id> @ 0xNN ● CONNECTED/OFFLINE`), SERVICES (`systemctl is-active` pour chaque service du rôle, couleur selon état). Robustesse : `set +e` au top, chaque section dans guards qui fallback "N/A" silencieusement → jamais bloquer SSH login. Timing live-mesuré : 0.57s Master, ~0.5s Slave. Installer idempotent : `install -m 0755 -o root:root`, `chmod -x` sur les autres entries `/etc/update-motd.d/`, `truncate -s 0 /etc/motd`, `bash -n` + smoke-run pré-exit pour échec LOUD à l'install. Détails : `bd memories astromech-ssh-motd-hacker-spec-2026-05-28`.

---

## 🎨 Theme System

> Remonté depuis `CLAUDE.md` (2026-06-13) pour alléger le contexte always-on.
> `CLAUDE.md` ne garde que les invariants courts (boot default, thèmes
> server-side, gotcha Choreo light) + un pointeur ici.

**Architecture** : `:root` defines defaults · themes override via inline style on `document.documentElement` · `--blue-rgb: R, G, B` pattern → opacity variants `rgba(var(--blue-rgb), 0.18)` auto.

**`_THEMES`** in app.js : `default · r2d2 · r2d2_light · r5d4 · bb8 · chopper · r2q5`. **Boot default = `r2d2_light`** (commit `ab05d2c`, 2026-05-29) appliqué quand ni `astromech-theme-dev[deviceKey]` ni `astromech-theme` localStorage n'ont de valeur — `app.js:168` (`_activeTheme`), `:705` (cross-tab storage), `:750` (boot IIFE) + `templates/index.html:50` (pré-paint) tous fallback sur `r2d2_light`. L'id `default` reste stable (zéro migration des localStorage / `drive_layouts.json` existants) mais son **label affiché est "Classic"** (renommé depuis "Default" au même commit). Les fallbacks de **dégradation gracieuse** à `app.js:196` (custom theme supprimé entre-temps) + `:500` (delete custom actif) restent intentionnellement sur l'id `default` car son `vars={}` est le seul reset CSS sûr ; forcer `r2d2_light` y imposerait un look non-choisi. Custom themes **persistés server-side** dans `master/config/custom_themes.json` (gitignored, atomic write) via `GET/POST /themes/custom` + `DELETE /themes/custom/<id>` (`backup_bp.py`). `localStorage` reste un cache miroir (`_syncThemesFromServer` au boot). Donc un thème perso survit au reboot / changement de device ET entre dans le backup. Validation server-side `validate_theme()` (`backup_core.py`) : id regex, hex pickers, CSS-injection guard sur `vars` (autorise `rgba()`, bloque `;{}<>`/`url(`/`expression`/`javascript:`).

**`applyTheme(id)`** : check `_THEMES`, fallback to custom · click sur custom button = applyTheme (PAS openThemeEditor — pencil/X gèrent edit/delete).

**Customizer** : 8 color pickers (BG/Topbar/Card/Accent/Text/OK/Warn/Err) + font picker (Orbitron/Share Tech Mono/Audiowide/Electrolize/Exo 2/Rajdhani/Courier New).

**Live preview** matche `.tab` pixel-for-pixel : letter-spacing 1.5px · font var(--font) · active text-shadow · SVG icons currentColor.

**Icon picker** : `_ALLOWED_LIST_EXT` (incl. .svg pour pre-shipped) vs `_ALLOWED_UPLOAD_EXT` (no .svg — XSS via same-origin). Détails : `bd memories icons-allowlist-split-upload-vs-list`.

**Readability v2 (chantier rk2)** : pickers **Input BG/Input Text/Button Text** (`--input-bg`/`--input-text`/`--btn-text`, défauts auto-contrastés WCAG via `_autoTextOn()`) — inputs (`.input-text`/`.chor-prop-*`) + boutons (`.btn`/`.shortcut-btn`) routés sur ces vars (`:root` défaut `var(--text)` → thèmes sombres inchangés). **Editor text-size** : 2 sliders Settings→Interface `--inspector-scale`/`--timeline-scale` (set sur `document.body`, **PAS** `documentElement` que `applyTheme` wipe), persistés `local.cfg [ui]` via `GET` (LAN-open)/`POST` (@require_admin) `/settings/ui_scale` + `validate_ui_scale()` (backup_core.py) + miroir localStorage + debounce par-slider. **`body.theme-light`** (toggle par `applyTheme` depuis `_THEMES[id].light` ou luminance bg custom >0.4) ancre les overrides clair. ⚠️ **GOTCHA** : l'éditeur Choreo a des surfaces **hardcodées sombres** (`.chor-command-bar`/`.chor-canvas`/`.chor-ruler`/`.chor-footer`/`.chor-src-btn`) qui n'adaptent JAMAIS au thème — toute nouvelle surface Choreo DOIT avoir un override `body.theme-light`. Audit WCAG : `.tmp/audit/audit.mjs` (Chrome headless vs Pi :5000). Détails : `bd memories theme-readability-v2-chantier-rk2-2026-05-25`.

**Per-device persistence + light dividers (chantier 2026-05-27)** : le **layout Drive** ET le **thème actif** sont persistés PAR APPAREIL — clé `deviceKey = ${pointer}_${screen.width}x${screen.height}` (résolution MONITEUR : stable au resize / 2 fenêtres côte-à-côte / clear localStorage, PAS `innerWidth`) · stockés dans `master/config/drive_layouts.json` (serveur + miroir localStorage + backup ; `_sanitize_layout` whiteliste `theme`+`deviceId`) · `_current()` fallback (exact → deviceId match → best legacy) + boot `_consolidate()` migre les vieilles clés `innerWidth` · pré-paint thème lit le hint NON-namespacé `astromech-theme-dev` (robot_name pas encore caché au script-load → `_lsKey` renverrait la clé brute) · picker **« Borrow a layout »** (Settings→Interface, admin-gated) réutilise une dispo d'un autre écran · `reset()` écrit un stub standard (PAS delete) sinon `_consolidate` ressuscite la dispo d'un autre moniteur via deviceId · en thème clair le séparateur header↔menu est une couleur **OPAQUE** (`#9197a9`) sur `.topbar`/`.tabbar` passés en `position:relative` — une bordure 1px **translucide** sur un élément **sticky** clignotait 1px↔2px au reload (artefact sous-pixel/compositing à DPR fractionnaire) · le résidu de boot (thème/icône/joysticks par défaut "cheap") est supprimé par le gate anti-FOUC `body:not(.app-ready){opacity:0}` + `.app-ready` ajouté en fin d'`init()` (thème+icône+joysticks prêts) + fallback 3s — détails §"Boot reveal & rendering stability" + `bd memories astromech-ui-fouc-and-divider-flicker-fixes`. ⚠️ La classe `admin-only` n'a AUCUNE règle CSS (marqueur sémantique) — gater les mutations par `adminGuard.unlocked` + `@require_admin`, jamais par cette classe. `bd memories drive-layout-per-device-theme-persistence-commit-0b42f61` · `bd memories audit-gotcha-the-css-class-admin-only-used`.
