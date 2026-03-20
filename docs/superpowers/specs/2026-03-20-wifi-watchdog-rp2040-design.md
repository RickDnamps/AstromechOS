# Design Spec — WiFi Watchdog Hiérarchique & RP2040 Cockpit

**Date :** 2026-03-20
**Statut :** Approuvé
**Scope :** Slave Pi 4B + RP2040 firmware + script de validation

---

## Contexte

Le Slave R2-D2 ne dispose que d'un seul adaptateur WiFi (wlan0). Il se connecte normalement au hotspot Master (`R2D2_Control`, prio 100). Un second profil NetworkManager existe déjà sur le Slave (`netplan-wlan0-mywifi2`, prio -10, autoconnect OFF) — c'est le WiFi domestique. Le RP2040 actuel affiche un diagnostic de boot à 7 items sujet à des faux FAIL (race conditions de timing). Il est peu utilisé en pratique.

---

## Partie 1 — WiFi Watchdog Hiérarchique

### Fichier : `slave/wifi_watchdog.py`

Nouveau module indépendant, thread daemon démarré depuis `slave/main.py` **après `uart.start()` et avant `checker.run()`**, avec référence au `DisplayDriver` déjà initialisé.

```python
wifi_watchdog = WiFiWatchdog(display)
wifi_watchdog.start()
```

Ajouté dans le `shutdown()` handler de `slave/main.py` :
```python
wifi_watchdog.stop()
```

### Logique de reconnexion

```
Toutes les 30s :
  ping r2-master.local (3 tentatives, timeout 2s chacune)

  Si tout OK → état CONNECTED, rien faire

  Si 3 pings échoués → NIVEAU 1 (tentatives 1..5)
    → display.net_scanning(attempt)        [DISP:NET:SCANNING:N]
    → nmcli device disconnect wlan0
    → display.net_connecting_ap(attempt)   [DISP:NET:AP:N]
    → nmcli connection up r2d2-master-hotspot
    → attendre 15s, réessayer ping
    → Si ping OK → CONNECTED + display.net_ok()

  Après 5 tentatives Niveau 1 échouées → NIVEAU 2
    → display.net_home_try()               [DISP:NET:HOME_TRY]
    → nmcli connection up netplan-wlan0-mywifi2
    → attendre 20s
    → lire IP courante via "ip -4 addr show wlan0"
    → Si IP obtenue → display.net_home_ok(ip) [DISP:NET:HOME:<ip>]
    →   état HOME_FALLBACK : toutes les 60s, tenter ping r2-master.local
    →   Si Master redevient joignable → nmcli connection up r2d2-master-hotspot
    →                                 → display.net_ok() → état CONNECTED

Note : pendant Level 1 (~75s max), le rsync automatique (deploy_controller) échouera
silencieusement — nmcli connection up ra2d2-master-hotspot inclut ce retry et rétablit
l'accès SSH. Le deploy_controller est sur le Master (pas le Slave), donc le pipeline
git pull → rsync n'est pas bloqué côté Master.
```

### États internes

| État | Description |
|------|-------------|
| `CONNECTED` | wlan0 connecté au hotspot Master, pings OK |
| `SCANNING` | 1–5 tentatives de reconnexion au hotspot |
| `HOME_FALLBACK` | Connecté au WiFi maison, Master injoignable |

### Interface `WiFiWatchdog`

```python
class WiFiWatchdog:
    def __init__(self, display: DisplayDriver): ...
    def start(self) -> None: ...   # lance le thread daemon
    def stop(self) -> None: ...    # signal d'arrêt propre
```

---

## Partie 2 — Nouveaux DISP: Commands

### Côté Slave — `slave/drivers/display_driver.py`

Nouvelles méthodes :

```python
def net_scanning(self, attempt: int) -> bool:
    return self._send(f"DISP:NET:SCANNING:{attempt}")

def net_connecting_ap(self, attempt: int) -> bool:
    return self._send(f"DISP:NET:AP:{attempt}")

def net_home_try(self) -> bool:
    return self._send("DISP:NET:HOME_TRY")

def net_home_ok(self, ip: str) -> bool:
    return self._send(f"DISP:NET:HOME:{ip}")

def net_ok(self) -> bool:
    return self._send("DISP:NET:OK")

def bus_health(self, pct: float) -> bool:
    return self._send(f"DISP:BUS:{pct:.1f}")

def system_locked(self) -> bool:
    return self._send("DISP:LOCKED")
```

Ajout de `_last_cmd: str = ""` mis à jour dans `_send()` — utilisé par le script de test.

**Limitation connue :** si le RP2040 est déconnecté en USB en cours de session, `_send()` lève une `SerialException`, met `_ready = False`, et ne tente pas de se reconnecter. Les appels suivants sont silencieusement ignorés. Comportement acceptable — reconnexion USB hors scope.

### `DISP:LOCKED` — dans `slave/main.py`

La fonction `emergency_stop_vesc()` dans `slave/main.py` a accès à `display` dans sa closure. Elle appellera `display.system_locked()` :

```python
def emergency_stop_vesc() -> None:
    log.error("COUPURE VESC — watchdog timeout")
    display.system_locked()   # ← ajout
    # Phase 2: vesc_g.stop() + vesc_d.stop()
```

### `DISP:BUS:` thread — dans `slave/main.py`

Thread daemon démarré après `uart.start()` :

```python
def _bus_health_push():
    while True:
        time.sleep(10)
        stats = uart.get_health_stats()
        display.bus_health(stats['health_pct'])

threading.Thread(target=_bus_health_push, name='bus-health-push', daemon=True).start()
```

---

## Partie 3 — RP2040 Firmware Redesign

### Philosophie : "Affiche ce qu'on lui dit"

Suppression du tracking individuel des 7 items de boot (source de faux FAIL). Le firmware n'anticipe plus — il rend ce qu'il reçoit.

### Nouveaux états

| État | Commande déclenchante | Description |
|------|-----------------------|-------------|
| `STATE_BOOTING` | `DISP:BOOT:START` | Spinner orange — remplace boot progress |
| `STATE_OK` | `DISP:READY:v` **ou** `DISP:OK:v` | Écran principal vert + barre bus health |
| `STATE_NET` | `DISP:NET:*` | Écran réseau (scanning / connecting / home) |
| `STATE_LOCKED` | `DISP:LOCKED` | Cadenas rouge clignotant — watchdog |
| `STATE_ERROR` | `DISP:ERROR:CODE` | Erreur critique (conservé, simplifié) |
| `STATE_TELEM` | `DISP:TELEM:V:T` | Télémétrie (swipe depuis OK seulement) |

**Note importante :** `DISP:READY:v` va **directement** à `STATE_OK` (plus de `STATE_OPERATIONAL` intermédiaire, plus d'auto-transition 3 secondes). Cela simplifie la logique et évite que l'écran reste figé si le Slave n'envoie pas `DISP:OK:v` après.

### Variables d'état dans le firmware

```python
bus_health_pct = 100.0   # mis à jour par DISP:BUS: — NE change PAS l'état
net_sub_state  = ""      # "SCANNING:N", "AP:N", "HOME_TRY", "HOME:<ip>", "OK"
telem_voltage  = 0.0
telem_temp     = 0.0
version        = ""
```

### `parse_command` delta — nouveaux cas

```python
elif cmd == "READY" or cmd == "OK":
    version = parts[1] if len(parts) > 1 else ""
    state = STATE_OK                     # ← direct, plus STATE_OPERATIONAL

elif cmd == "BUS":
    if len(parts) > 1:
        try: bus_health_pct = float(parts[1])
        except ValueError: pass
    # Ne change PAS state — mais force redraw si on est en STATE_OK
    if state == STATE_OK:
        _needs_redraw = True
    return                               # pas de _needs_redraw global

elif cmd == "NET":
    net_sub_state = ":".join(parts[1:]) if len(parts) > 1 else ""
    state = STATE_NET

elif cmd == "LOCKED":
    state = STATE_LOCKED
```

### Supprimé du firmware

- `boot_items` dict et tout le tracking individuel
- `BOOT_TIMEOUT_MS` et `_check_boot_timeout()`
- `STATE_OPERATIONAL` et l'auto-transition 3s
- `operational_since` variable

### Navigation swipe (redéfinie)

```python
SCREENS   = [STATE_OK, STATE_TELEM]      # Boot log supprimé
NAVIGABLE = {STATE_OK, STATE_TELEM}      # Seulement en état opérationnel
```

- Swipe gauche (en `STATE_OK`) → `STATE_TELEM`
- Swipe droite (en `STATE_TELEM`) → `STATE_OK`
- Double tap → `STATE_OK` depuis n'importe où (y compris NET/LOCKED)
- Hold → `EMERGENCY:STOP` (conservé)

### `rp2040/firmware/display.py` — Renderers

| Fonction | Signature | Notes |
|----------|-----------|-------|
| `draw_booting(tft)` | nouveau | Spinner orange, "STARTING UP" |
| `draw_ok(tft, version, bus_pct)` | modifié | + barre bus (vert≥80%, orange<80%) |
| `draw_net(tft, sub_state)` | nouveau | Antenne SVG animée, sous-état textuel |
| `draw_locked(tft)` | nouveau | Anneau rouge clignotant, cadenas SVG |
| `draw_error(tft, code)` | conservé | Simplifié — même interface |
| `draw_telemetry(tft, v, t)` | conservé | Léger update cosméticque |

---

## Partie 4 — Script de Validation

### Fichier : `scripts/test_wifi_watchdog.py`

Exécuté depuis le Master via SSH sur le Slave.

```
Étape 1 — Pré-condition
  Vérifier que le Slave est connecté au hotspot Master (nmcli)

Étape 2 — Simulation coupure
  nmcli device disconnect wlan0
  Timeout observation : 45s (35s cycle watchdog + 10s marge)
  Assertion : display._last_cmd contient "DISP:NET:SCANNING:1"

Étape 3 — Reconnexion Level 1
  nmcli connection up r2d2-master-hotspot
  Timeout : 30s
  Assertion : ping r2-master.local réussi depuis le Slave

Étape 4 — Rapport
  Afficher tous les display._last_cmd observés pendant le test
  PASS / FAIL avec message explicite

Note : Le test ne force PAS le Level 2 (home fallback) pour ne pas
couper le Slave du Master pendant le test automatisé.
```

---

## Fichiers modifiés / créés

| Fichier | Action | Changement principal |
|---------|--------|----------------------|
| `slave/wifi_watchdog.py` | NOUVEAU | Thread daemon WiFi Watchdog |
| `slave/main.py` | modifié | Import + start WiFiWatchdog + bus_health_push thread + stop() dans shutdown + `display.system_locked()` dans `emergency_stop_vesc()` |
| `slave/drivers/display_driver.py` | modifié | Méthodes `net_*`, `bus_health`, `system_locked` + `_last_cmd` attribute |
| `rp2040/firmware/main.py` | réécriture partielle | Suppression boot items/tracking, nouveaux états/parse_command |
| `rp2040/firmware/display.py` | modifié | `draw_booting`, `draw_net`, `draw_locked`, update `draw_ok` |
| `scripts/test_wifi_watchdog.py` | NOUVEAU | Test de validation non-destructif |

---

## Contraintes & risques

- **wlan0 seul adaptateur** : le Slave perd toute connectivité (~5s par tentative Level 1). Le UART est physique — le watchdog VESC n'est pas affecté.
- **nmcli** : disponible sur Trixie, `nmcli connection up` prend 3–8s.
- **RP2040 firmware** : déployé **manuellement** via USB (Thonny ou rshell) — hors pipeline rsync automatique. À flasher après implémentation.
- **Display USB disconnect** : si le RP2040 se déconnecte en USB mid-session, `_ready = False` permanent jusqu'au redémarrage du Slave. Acceptable.
- **Shutdown race** : si `wifi_watchdog.stop()` est appelé pendant un `nmcli` en cours, le sous-processus est orphelin ~3s maximum. Inoffensif.
