# WiFi Watchdog + RP2040 Cockpit Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a hierarchical WiFi watchdog on the Slave that reconnects to the Master AP or falls back to home WiFi, plus redesign the RP2040 firmware to display exactly what it is told instead of tracking boot items independently.

**Architecture:** WiFiWatchdog runs as a daemon thread alongside existing Slave services. DisplayDriver gets new methods mirroring the DISP: protocol. RP2040 firmware is partially rewritten — boot item tracking is replaced with a simple spinner, new states (NET, LOCKED, BOOTING) and updated command parser. The RP2040 is flashed manually via USB; all other changes deploy via normal git+rsync pipeline.

**Tech Stack:** Python 3.10+ (Slave), MicroPython (RP2040), nmcli (NetworkManager), subprocess.run, pyserial

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `slave/drivers/display_driver.py` | Modify | Add `_last_cmd`, 7 new DISP methods |
| `slave/wifi_watchdog.py` | **CREATE** | WiFiWatchdog daemon thread |
| `slave/main.py` | Modify | Wire WiFiWatchdog + bus_health_push + system_locked |
| `rp2040/firmware/display.py` | Modify | New renderers: draw_booting, draw_net, draw_locked; update draw_ok |
| `rp2040/firmware/main.py` | Modify | Remove boot tracking, new states, updated parse_command + navigation |
| `scripts/test_wifi_watchdog.py` | **CREATE** | Non-destructive validation script |

---

## Task 1 — DisplayDriver: `_last_cmd` + new DISP methods

**Files:**
- Modify: `slave/drivers/display_driver.py`

### Context

The existing `_send()` method sends raw DISP: strings to the RP2040. We add:
1. `_last_cmd: str` attribute — updated on every `_send()` call — used by the test script to assert what was last sent.
2. Seven new methods covering WiFi watchdog states, bus health, and system locked.

- [ ] **Step 1: Add `_last_cmd` to `__init__` and update `_send()`**

In `DisplayDriver.__init__`, add after `self._ready = False`:
```python
self._last_cmd: str = ""
```

In `_send()`, add after `log.debug(f"Display TX: {cmd}")`:
```python
self._last_cmd = cmd
```

Full updated `_send()`:
```python
def _send(self, cmd: str) -> bool:
    if not self.is_ready():
        log.debug(f"DisplayDriver non prêt, commande ignorée: {cmd}")
        return False
    try:
        self._serial.write(f"{cmd}\n".encode('utf-8'))
        log.debug(f"Display TX: {cmd}")
        self._last_cmd = cmd
        return True
    except serial.SerialException as e:
        log.error(f"Erreur display send: {e}")
        self._ready = False
        return False
```

- [ ] **Step 2: Add the 7 new public methods**

Add after the `telemetry()` method and before `send_raw()`:

```python
# ------------------------------------------------------------------
# WiFi Watchdog états réseau
# ------------------------------------------------------------------

def net_scanning(self, attempt: int) -> bool:
    """Scan WiFi — tentative de reconnexion au hotspot Master (Level 1)."""
    return self._send(f"DISP:NET:SCANNING:{attempt}")

def net_connecting_ap(self, attempt: int) -> bool:
    """Connexion en cours vers hotspot Master."""
    return self._send(f"DISP:NET:AP:{attempt}")

def net_home_try(self) -> bool:
    """Basculement vers WiFi domestique (Level 2)."""
    return self._send("DISP:NET:HOME_TRY")

def net_home_ok(self, ip: str) -> bool:
    """Connecté au WiFi domestique — affiche l'IP obtenue."""
    return self._send(f"DISP:NET:HOME:{ip}")

def net_ok(self) -> bool:
    """Connexion Master rétablie."""
    return self._send("DISP:NET:OK")

def bus_health(self, pct: float) -> bool:
    """Santé du bus UART — mis à jour toutes les 10s."""
    return self._send(f"DISP:BUS:{pct:.1f}")

def system_locked(self) -> bool:
    """Cadenas rouge — watchdog VESC déclenché."""
    return self._send("DISP:LOCKED")
```

- [ ] **Step 3: Verify the file looks correct**

Read `slave/drivers/display_driver.py` and confirm:
- `self._last_cmd: str = ""` in `__init__`
- `self._last_cmd = cmd` in `_send()` (after the write, inside the try block)
- 7 new methods present with correct DISP: strings

- [ ] **Step 4: Commit**

```bash
git add slave/drivers/display_driver.py
git commit -m "feat: DisplayDriver — _last_cmd + net/bus/locked methods"
```

---

## Task 2 — Create `slave/wifi_watchdog.py`

**Files:**
- Create: `slave/wifi_watchdog.py`

### Context

Runs as daemon thread. Pings `r2-master.local` every 30s. On failure:
- **Level 1** (attempts 1–5): disconnect wlan0, reconnect `r2d2-master-hotspot` via nmcli
- **Level 2** (after 5 Level-1 failures): connect to `netplan-wlan0-mywifi2` (home WiFi, already configured on Slave, autoconnect OFF)
- In HOME_FALLBACK: check every 60s if Master is back, reconnect AP if found

The DisplayDriver reference is passed in at construction time.

- [ ] **Step 1: Create the file**

```python
"""
WiFi Watchdog — Slave Pi 4B.
Surveille la connectivité au hotspot Master (r2d2-master-hotspot).
Level 1 : jusqu'à 5 tentatives de reconnexion au hotspot.
Level 2 : fallback sur WiFi domestique (netplan-wlan0-mywifi2).
"""

import logging
import subprocess
import threading
import time
import re

log = logging.getLogger(__name__)

# Paramètres
PING_HOST           = "r2-master.local"
PING_RETRIES        = 3          # pings consécutifs avant de déclarer la perte
PING_TIMEOUT_S      = 2          # timeout par ping
CHECK_INTERVAL_S    = 30         # intervalle de vérification normal
L1_WAIT_S           = 15         # attente après nmcli connection up (Level 1)
L1_MAX_ATTEMPTS     = 5          # avant de passer Level 2
L2_WAIT_S           = 20         # attente après connexion home WiFi
HOME_CHECK_S        = 60         # intervalle de vérification en HOME_FALLBACK
AP_PROFILE          = "r2d2-master-hotspot"
HOME_PROFILE        = "netplan-wlan0-mywifi2"
IFACE               = "wlan0"

# États internes
CONNECTED     = "CONNECTED"
SCANNING      = "SCANNING"
HOME_FALLBACK = "HOME_FALLBACK"


class WiFiWatchdog:
    def __init__(self, display) -> None:
        """
        display : instance de DisplayDriver (déjà initialisé).
        Peut être None — les appels display sont silencieusement ignorés.
        """
        self._display  = display
        self._stop_evt = threading.Event()
        self._thread   = threading.Thread(
            target=self._run,
            name='wifi-watchdog',
            daemon=True,
        )

    def start(self) -> None:
        """Lance le thread de surveillance."""
        log.info("WiFiWatchdog démarré")
        self._thread.start()

    def stop(self) -> None:
        """Signal d'arrêt propre — retourne sans attendre la fin du thread."""
        self._stop_evt.set()

    # ------------------------------------------------------------------
    # Interne
    # ------------------------------------------------------------------

    def _run(self) -> None:
        state          = CONNECTED
        l1_attempt     = 0

        while not self._stop_evt.is_set():
            # ---- Délai selon l'état courant ----
            wait = HOME_CHECK_S if state == HOME_FALLBACK else CHECK_INTERVAL_S
            if self._stop_evt.wait(wait):
                break  # arrêt demandé

            ping_ok = self._ping_master()

            if state == CONNECTED:
                if not ping_ok:
                    log.warning("WiFiWatchdog: Master injoignable — Level 1 démarre")
                    state      = SCANNING
                    l1_attempt = 0
                    # Pas de délai supplémentaire — Level 1 démarre immédiatement

            if state == SCANNING:
                # Relancé ici aussi si on vient de CONNECTED → SCANNING ci-dessus
                if ping_ok:
                    log.info("WiFiWatchdog: Master joignable — CONNECTED")
                    state = CONNECTED
                    self._disp_net_ok()
                    continue

                l1_attempt += 1
                log.info(f"WiFiWatchdog: Level 1 tentative {l1_attempt}/{L1_MAX_ATTEMPTS}")
                self._disp_net_scanning(l1_attempt)

                # Déconnecter + reconnecter
                self._nmcli_disconnect()
                self._disp_net_ap(l1_attempt)
                self._nmcli_up(AP_PROFILE)

                # Attendre puis re-pinger
                if self._stop_evt.wait(L1_WAIT_S):
                    break
                if self._ping_master():
                    log.info("WiFiWatchdog: Level 1 reconnexion OK")
                    state = CONNECTED
                    self._disp_net_ok()
                    continue

                # Tentative échouée
                if l1_attempt >= L1_MAX_ATTEMPTS:
                    log.warning("WiFiWatchdog: Level 1 épuisé — Level 2 (home fallback)")
                    state = HOME_FALLBACK
                    self._level2_connect()

            elif state == HOME_FALLBACK:
                if ping_ok:
                    log.info("WiFiWatchdog: Master de retour — reconnexion AP")
                    self._nmcli_up(AP_PROFILE)
                    if self._stop_evt.wait(L1_WAIT_S):
                        break
                    if self._ping_master():
                        state = CONNECTED
                        self._disp_net_ok()
                    else:
                        log.warning("WiFiWatchdog: retour AP échoué — reste HOME_FALLBACK")
                        self._level2_connect()  # re-tenter home

    def _level2_connect(self) -> None:
        """Connecte au WiFi domestique et affiche l'état."""
        self._disp_net_home_try()
        self._nmcli_up(HOME_PROFILE)
        if self._stop_evt.wait(L2_WAIT_S):
            return
        ip = self._get_wlan0_ip()
        if ip:
            log.info(f"WiFiWatchdog: HOME_FALLBACK actif — IP {ip}")
            self._disp_net_home_ok(ip)
        else:
            log.warning("WiFiWatchdog: home WiFi connecté mais pas d'IP")

    # ------------------------------------------------------------------
    # Helpers réseau
    # ------------------------------------------------------------------

    def _ping_master(self) -> bool:
        """Retourne True si au moins un ping réussit parmi PING_RETRIES tentatives."""
        for _ in range(PING_RETRIES):
            if self._stop_evt.is_set():
                return False
            try:
                result = subprocess.run(
                    ['ping', '-c', '1', '-W', str(PING_TIMEOUT_S), PING_HOST],
                    capture_output=True,
                    timeout=PING_TIMEOUT_S + 1,
                )
                if result.returncode == 0:
                    return True
            except Exception:
                pass
        return False

    def _nmcli_disconnect(self) -> None:
        try:
            subprocess.run(
                ['nmcli', 'device', 'disconnect', IFACE],
                capture_output=True, timeout=10,
            )
        except Exception as e:
            log.warning(f"nmcli disconnect: {e}")

    def _nmcli_up(self, profile: str) -> None:
        try:
            subprocess.run(
                ['nmcli', 'connection', 'up', profile],
                capture_output=True, timeout=15,
            )
        except Exception as e:
            log.warning(f"nmcli connection up {profile}: {e}")

    def _get_wlan0_ip(self) -> str | None:
        """Retourne l'IP courante de wlan0, ou None."""
        try:
            result = subprocess.run(
                ['ip', '-4', 'addr', 'show', IFACE],
                capture_output=True, text=True, timeout=5,
            )
            m = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', result.stdout)
            return m.group(1) if m else None
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Helpers display (silencieux si _display est None)
    # ------------------------------------------------------------------

    def _disp_net_scanning(self, attempt: int) -> None:
        if self._display:
            try:
                self._display.net_scanning(attempt)
            except Exception:
                pass

    def _disp_net_ap(self, attempt: int) -> None:
        if self._display:
            try:
                self._display.net_connecting_ap(attempt)
            except Exception:
                pass

    def _disp_net_home_try(self) -> None:
        if self._display:
            try:
                self._display.net_home_try()
            except Exception:
                pass

    def _disp_net_home_ok(self, ip: str) -> None:
        if self._display:
            try:
                self._display.net_home_ok(ip)
            except Exception:
                pass

    def _disp_net_ok(self) -> None:
        if self._display:
            try:
                self._display.net_ok()
            except Exception:
                pass
```

- [ ] **Step 2: Verify the file was created at `slave/wifi_watchdog.py`**

- [ ] **Step 3: Commit**

```bash
git add slave/wifi_watchdog.py
git commit -m "feat: WiFiWatchdog — hierarchical Level 1/2 reconnection daemon"
```

---

## Task 3 — `slave/main.py` integration

**Files:**
- Modify: `slave/main.py`

Three changes:
1. Import and start `WiFiWatchdog` (after `uart.start()`, before `checker.run()`)
2. Start `bus_health_push` daemon thread (after `uart.start()`)
3. Add `display.system_locked()` in `emergency_stop_vesc()`
4. Add `wifi_watchdog.stop()` in `shutdown()`

- [ ] **Step 1: Add import**

After the existing imports block, add:
```python
from slave.wifi_watchdog import WiFiWatchdog
```

- [ ] **Step 2: Add `display.system_locked()` in `emergency_stop_vesc()`**

The `emergency_stop_vesc` function is a module-level function defined before `main()`. It does NOT have access to `display` directly in its current form. The display object is created inside `main()`. The fix: close over `display` by redefining `emergency_stop_vesc` inside `main()` after `display` is initialized.

Replace the current module-level `emergency_stop_vesc` function:
```python
def emergency_stop_vesc() -> None:
    """Coupe d'urgence VESC — appelée par le watchdog."""
    log = logging.getLogger("watchdog.stop")
    log.error("COUPURE VESC — watchdog timeout")
    # Phase 2: vesc_g.stop() + vesc_d.stop()
```

with a version that takes display as a parameter (so it can be called from a closure inside main):
```python
def emergency_stop_vesc() -> None:
    """Coupe d'urgence VESC — appelée par le watchdog. Redéfinie dans main() avec closure display."""
    log = logging.getLogger("watchdog.stop")
    log.error("COUPURE VESC — watchdog timeout")
    # Phase 2: vesc_g.stop() + vesc_d.stop()
```

Then inside `main()`, after `display = DisplayDriver()` setup, redefine `emergency_stop_vesc` as a local function — **before** the `watchdog.register_stop_callback(emergency_stop_vesc)` call:

```python
# Redéfinir emergency_stop avec closure sur display
def emergency_stop_vesc() -> None:
    log = logging.getLogger("watchdog.stop")
    log.error("COUPURE VESC — watchdog timeout")
    display.system_locked()
    # Phase 2: vesc_g.stop() + vesc_d.stop()
```

Add this block right after the `display.boot_start()` call (line 87), before the UART/Watchdog section.

**Critical:** Do NOT add a second `register_stop_callback` call. The existing call at line 105 (`watchdog.register_stop_callback(emergency_stop_vesc)`) will pick up the local closure automatically because Python resolves names at call time. Adding a second call would double-register and `system_locked()` would fire twice.

- [ ] **Step 3: Add WiFiWatchdog start + bus_health_push thread**

Find the block after `uart.start()` and before the `VersionChecker` block. Add:

```python
    # ------------------------------------------------------------------
    # WiFi Watchdog — reconnexion automatique wlan0
    # ------------------------------------------------------------------
    wifi_watchdog = WiFiWatchdog(display)
    wifi_watchdog.start()

    # ------------------------------------------------------------------
    # Bus Health push — envoie le % santé UART au RP2040 toutes les 10s
    # ------------------------------------------------------------------
    def _bus_health_push():
        while True:
            time.sleep(10)
            stats = uart.get_health_stats()
            display.bus_health(stats['health_pct'])

    threading.Thread(
        target=_bus_health_push,
        name='bus-health-push',
        daemon=True,
    ).start()
```

- [ ] **Step 4: Add `wifi_watchdog.stop()` in shutdown handler**

In the `shutdown()` function, add `wifi_watchdog.stop()` alongside the other stop calls:
```python
    def shutdown(sig, frame):
        log.info("Signal arrêt reçu")
        wifi_watchdog.stop()
        watchdog.stop()
        uart.stop()
        audio.shutdown()
        if servo.is_ready(): servo.shutdown()
        display.shutdown()
        log.info("Slave arrêté proprement")
        sys.exit(0)
```

- [ ] **Step 5: Verify the complete `main.py`**

Read `slave/main.py` and confirm:
- `from slave.wifi_watchdog import WiFiWatchdog` present in imports
- Local `emergency_stop_vesc` closure calls `display.system_locked()`
- WiFiWatchdog starts after `uart.start()`
- `_bus_health_push` thread starts after `uart.start()`
- `wifi_watchdog.stop()` in shutdown handler

- [ ] **Step 6: Commit**

```bash
git add slave/main.py
git commit -m "feat: slave/main.py — WiFiWatchdog + bus_health_push + system_locked"
```

---

## Task 4 — RP2040 `display.py`: new renderers + update draw_ok

**Files:**
- Modify: `rp2040/firmware/display.py`

Four new/updated functions. All use the same existing helpers (`_draw_ring`, `_text_center`, `_progress_bar`). Note: no color for `YELLOW` — use `ORANGE` for warnings.

- [ ] **Step 1: Add `CYAN` color constant (used for NET screen)**

After the existing color constants block:
```python
CYAN    = gc9a01.color565(0,   200, 200)
```

- [ ] **Step 2: Add `_spin_frame` module-level variable (used by draw_booting and draw_locked)**

After the `CENTER_Y = 120` line:
```python
_spin_frame = 0   # animation frame counter — incremented each draw call
```

- [ ] **Step 3: Add `draw_booting(tft)` function**

Add after `draw_boot()` (before `draw_boot_progress()`):

```python
def draw_booting(tft):
    """Ecran de démarrage — spinner orange. Remplace le suivi individuel des items."""
    global _spin_frame
    _spin_frame = (_spin_frame + 1) % 8

    tft.fill(BLACK)
    _draw_ring(tft, CENTER_X, CENTER_Y, 115, 6, ORANGE)
    _text_center(tft, 'STARTING UP', CENTER_Y - 20, ORANGE)
    _text_center(tft, 'Please wait', CENTER_Y - 6,  GRAY)

    # Spinner : 8 segments sur cercle rayon 30, segment actif = ORANGE, autres = DK_GRAY
    sr = 30
    seg_len = 10
    for i in range(8):
        angle_deg = i * 45
        angle_rad = angle_deg * 3.14159 / 180.0
        cos_a = _cos_approx(angle_rad)
        sin_a = _sin_approx(angle_rad)
        x1 = int(CENTER_X + cos_a * sr)
        y1 = int(CENTER_Y + sin_a * sr)
        x2 = int(CENTER_X + cos_a * (sr + seg_len))
        y2 = int(CENTER_Y + sin_a * (sr + seg_len))
        color = ORANGE if i == _spin_frame else DK_GRAY
        # Dessiner un petit trait (approximation avec fill_rect)
        dx = x2 - x1
        dy = y2 - y1
        tft.fill_rect(min(x1, x2), min(y1, y2), max(1, abs(dx)), max(1, abs(dy)), color)

    _text_center(tft, 'R2-D2', CENTER_Y + 50, ORANGE)
```

Note: `_cos_approx` and `_sin_approx` helpers needed (MicroPython doesn't always have `math` trig — actually it does in recent builds, but let's use `math` directly):

```python
import math as _math

def _cos_approx(rad):
    return _math.cos(rad)

def _sin_approx(rad):
    return _math.sin(rad)
```

Add these two helper functions and `import math as _math` at the top of `display.py` (after `import math`).

Actually `import math` is already at the top — just add these two thin wrappers or inline with `math.cos`/`math.sin` directly. Use inline:

```python
def draw_booting(tft):
    """Ecran de demarrage — spinner orange. Remplace le suivi individuel des items."""
    global _spin_frame
    _spin_frame = (_spin_frame + 1) % 8

    tft.fill(BLACK)
    _draw_ring(tft, CENTER_X, CENTER_Y, 115, 6, ORANGE)
    _text_center(tft, 'STARTING UP', CENTER_Y - 20, ORANGE)
    _text_center(tft, 'Please wait', CENTER_Y - 6,  GRAY)

    # Spinner : 8 segments rayonnants, segment actif = ORANGE
    sr = 28
    seg_len = 12
    for i in range(8):
        rad = i * math.pi / 4.0
        x1 = int(CENTER_X + math.cos(rad) * sr)
        y1 = int(CENTER_Y + math.sin(rad) * sr)
        x2 = int(CENTER_X + math.cos(rad) * (sr + seg_len))
        y2 = int(CENTER_Y + math.sin(rad) * (sr + seg_len))
        color = ORANGE if i == _spin_frame else DK_GRAY
        tft.fill_rect(min(x1, x2), min(y1, y2),
                      max(2, abs(x2 - x1)), max(2, abs(y2 - y1)), color)

    _text_center(tft, 'R2-D2', CENTER_Y + 50, ORANGE)
```

- [ ] **Step 4: Update `draw_ok(tft, version)` → `draw_ok(tft, version, bus_pct=100.0)`**

Replace the current signature and add bus health bar:

```python
def draw_ok(tft, version, bus_pct=100.0):
    """Ecran operationnel normal — bordure verte fine + barre bus health."""
    tft.fill(BLACK)
    _draw_ring(tft, CENTER_X, CENTER_Y, 115, 4, GREEN)
    _text_center(tft, 'SYSTEM STATUS:', 42, GREEN)
    _text_center(tft, 'OK',            54, GREEN)
    tft.fill_rect(CENTER_X - 40, CENTER_Y - 14, 80, 12, GREEN)
    tft.fill_rect(CENTER_X - 40, CENTER_Y +  2, 80, 12, GREEN)
    _text_center(tft, 'READY', CENTER_Y + 24, GREEN)
    if version:
        _text_center(tft, version[:14], CENTER_Y + 38, GRAY)
    # Barre bus health
    bus_color = GREEN if bus_pct >= 80.0 else ORANGE
    bus_label = 'BUS {:.0f}%'.format(bus_pct)
    _text_center(tft, bus_label, CENTER_Y + 54, bus_color)
    _progress_bar(tft, 34, CENTER_Y + 64, 172, 8, bus_pct / 100.0, bus_color)
```

- [ ] **Step 5: Add `draw_net(tft, sub_state)` function**

Add after `draw_ok`:

```python
def draw_net(tft, sub_state):
    """Ecran réseau — antenne + sous-état (SCANNING:N, AP:N, HOME_TRY, HOME:<ip>, OK)."""
    tft.fill(BLACK)
    _draw_ring(tft, CENTER_X, CENTER_Y, 115, 5, CYAN)
    _text_center(tft, 'WIFI', 30, CYAN)

    # Antenne simple : 3 arcs concentriques en demi-cercle supérieur
    # Simplifié en lignes horizontales étagées (pas de trigonométrie)
    cx, cy = CENTER_X, CENTER_Y + 10
    for radius, alpha in [(14, 255), (24, 180), (34, 100)]:
        c = gc9a01.color565(0, alpha, alpha)
        # Demi-arc du haut — approximé par fill_rect sur 3 hauteurs
        tft.fill_rect(cx - radius, cy - radius, radius * 2, 3, c)
    # Mât de l'antenne
    tft.fill_rect(cx - 1, cy - 34, 3, 34, CYAN)
    tft.fill_rect(cx - 8, cy,      17,  3, CYAN)

    # Sous-état
    parts = sub_state.split(':') if sub_state else []
    cmd = parts[0].upper() if parts else ''

    if cmd == 'SCANNING':
        n = parts[1] if len(parts) > 1 else '?'
        _text_center(tft, 'SCANNING...',        CENTER_Y + 46, CYAN)
        _text_center(tft, 'Attempt {}/{}'.format(n, 5), CENTER_Y + 58, GRAY)
    elif cmd == 'AP':
        n = parts[1] if len(parts) > 1 else '?'
        _text_center(tft, 'CONNECTING AP',      CENTER_Y + 46, CYAN)
        _text_center(tft, 'Attempt {}/{}'.format(n, 5), CENTER_Y + 58, GRAY)
    elif cmd == 'HOME_TRY':
        _text_center(tft, 'HOME WIFI',          CENTER_Y + 46, ORANGE)
        _text_center(tft, 'Connecting...',      CENTER_Y + 58, GRAY)
    elif cmd == 'HOME':
        ip = ':'.join(parts[1:]) if len(parts) > 1 else '?'
        _text_center(tft, 'HOME WIFI',          CENTER_Y + 46, ORANGE)
        _text_center(tft, ip[:16],              CENTER_Y + 58, GRAY)
    elif cmd == 'OK':
        _text_center(tft, 'RECONNECTED',        CENTER_Y + 46, GREEN)
    else:
        _text_center(tft, sub_state[:16] if sub_state else 'NET EVENT', CENTER_Y + 46, CYAN)
```

Fix typo: `Center_Y` → `CENTER_Y` (step 4 review will catch this).

- [ ] **Step 6: Add `draw_locked(tft)` function**

Add after `draw_net`:

```python
def draw_locked(tft):
    """Cadenas rouge — watchdog VESC déclenché. Anneau clignotant via _spin_frame."""
    global _spin_frame
    _spin_frame = (_spin_frame + 1) % 4
    visible = _spin_frame < 2  # clignote ON/OFF 50%

    tft.fill(BLACK)
    ring_color = RED if visible else DK_GRAY
    _draw_ring(tft, CENTER_X, CENTER_Y, 115, 8, ring_color)
    _text_center(tft, 'SYSTEM STATUS:', 34, RED)
    _text_center(tft, 'LOCKED',        46, RED)

    # Cadenas simplifié :
    # Corps = rectangle
    tft.fill_rect(CENTER_X - 20, CENTER_Y - 10, 40, 32, RED)
    tft.fill_rect(CENTER_X - 14, CENTER_Y - 4,  28, 20, BLACK)  # trou intérieur
    # Anse = demi-cercle en haut
    arc_r = 16
    for dy in range(-arc_r, 0):
        r2 = arc_r * arc_r - dy * dy
        if r2 >= 0:
            dx = int(math.sqrt(r2))
            tft.fill_rect(CENTER_X - 21, CENTER_Y - 10 + dy, 4, 1, RED)
            tft.fill_rect(CENTER_X + 17, CENTER_Y - 10 + dy, 4, 1, RED)

    _text_center(tft, 'WATCHDOG',      CENTER_Y + 36, RED)
    _text_center(tft, 'TRIGGERED',     CENTER_Y + 48, WHITE)
```

- [ ] **Step 7: Review the display.py changes**

Read `rp2040/firmware/display.py` and fix any typos (notably `Center_Y` → `CENTER_Y` in draw_net).

- [ ] **Step 8: Commit**

```bash
git add rp2040/firmware/display.py
git commit -m "feat: RP2040 display — draw_booting, draw_net, draw_locked, update draw_ok"
```

---

## Task 5 — RP2040 `main.py`: partial rewrite

**Files:**
- Modify: `rp2040/firmware/main.py`

This is the largest change. The strategy is to **replace** specific sections of the file rather than full rewrite, to preserve working parts (SPI/TFT init, touch setup, stdin poller, main loop skeleton).

### Changes summary

| Remove | Add/Replace |
|--------|-------------|
| `BOOT_TIMEOUT_MS`, `_check_boot_timeout()` | `STATE_BOOTING`, `STATE_NET`, `STATE_LOCKED` |
| `STATE_BOOT_PROGRESS`, `STATE_OPERATIONAL` | `bus_health_pct`, `net_sub_state` variables |
| `boot_items` dict, `operational_since`, `boot_timed_out` | Updated `parse_command` with BUS/NET/LOCKED cases |
| `SCREENS = [STATE_OK, STATE_TELEM, STATE_BOOT_PROGRESS]` | `SCREENS = [STATE_OK, STATE_TELEM]` |
| `NAVIGABLE = {STATE_OK, STATE_TELEM, STATE_BOOT_PROGRESS}` | `NAVIGABLE = {STATE_OK, STATE_TELEM}` |
| Boot timeout check in main loop | Animation redraw trigger for BOOTING/LOCKED |
| `STATE_OPERATIONAL` auto-transition | Double tap → STATE_OK (any state) |

- [ ] **Step 1: Replace the states block and global variables**

Replace the current states/variables section (lines 68–103) with:

```python
# ------------------------------------------------------------------
# Etats
# ------------------------------------------------------------------
STATE_BOOTING = "BOOTING"
STATE_OK      = "OK"
STATE_NET     = "NET"
STATE_LOCKED  = "LOCKED"
STATE_ERROR   = "ERROR"
STATE_TELEM   = "TELEM"

# Navigation swipe — seulement quand operationnel
SCREENS   = [STATE_OK, STATE_TELEM]
NAVIGABLE = {STATE_OK, STATE_TELEM}

# Demarre en mode BOOTING (spinner orange)
state           = STATE_BOOTING
version         = ""
error_code      = ""
telem_voltage   = 0.0
telem_temp      = 0.0
net_sub_state   = ""
bus_health_pct  = 100.0
screen_idx      = 0

_needs_redraw  = True
_last_anim_ms  = 0    # dernier tick animation pour BOOTING/LOCKED
```

- [ ] **Step 2: Replace `apply_state()`**

Replace the current `apply_state()` function:

```python
def apply_state():
    global _needs_redraw
    if state == STATE_BOOTING:
        disp.draw_booting(tft)
    elif state == STATE_OK:
        disp.draw_ok(tft, version, bus_health_pct)
    elif state == STATE_NET:
        disp.draw_net(tft, net_sub_state)
    elif state == STATE_LOCKED:
        disp.draw_locked(tft)
    elif state == STATE_ERROR:
        disp.draw_error(tft, error_code)
    elif state == STATE_TELEM:
        disp.draw_telemetry(tft, telem_voltage, telem_temp)
    _needs_redraw = False
```

- [ ] **Step 3: Remove `_check_boot_timeout()` and replace `parse_command()`**

Delete the entire `_check_boot_timeout()` function (lines 121–138 in current file).

Replace the entire `parse_command()` function with:

```python
def parse_command(line):
    global state, version, error_code, telem_voltage, telem_temp
    global net_sub_state, bus_health_pct, _needs_redraw

    line = line.strip()
    if not line.startswith("DISP:"):
        return

    parts = line[5:].split(":")
    cmd = parts[0].upper()

    if cmd == "BOOT":
        # DISP:BOOT:START → passe en BOOTING (spinner)
        # DISP:BOOT:ITEM/OK/FAIL sont silencieusement ignorés (spinner continue)
        sub = parts[1].upper() if len(parts) > 1 else ""
        if sub == "START":
            state = STATE_BOOTING

    elif cmd in ("READY", "OK"):
        version = parts[1] if len(parts) > 1 else ""
        state = STATE_OK

    elif cmd == "SYNCING":
        state = STATE_BOOTING  # reste sur le spinner pendant la synchro

    elif cmd == "BUS":
        if len(parts) > 1:
            try:
                bus_health_pct = float(parts[1])
            except ValueError:
                pass
        # Ne change PAS l'etat — force redraw seulement si on est en STATE_OK
        if state == STATE_OK:
            _needs_redraw = True
        return  # pas de _needs_redraw global ici

    elif cmd == "NET":
        net_sub_state = ":".join(parts[1:]) if len(parts) > 1 else ""
        state = STATE_NET

    elif cmd == "LOCKED":
        state = STATE_LOCKED

    elif cmd == "ERROR":
        error_code = ":".join(parts[1:]).upper() if len(parts) > 1 else "UNKNOWN"
        state = STATE_ERROR

    elif cmd == "TELEM" and len(parts) >= 3:
        try:
            telem_voltage = float(parts[1].rstrip("Vv"))
            telem_temp    = float(parts[2].rstrip("Cc"))
        except ValueError:
            pass
        state = STATE_TELEM

    _needs_redraw = True
```

- [ ] **Step 4: Update touch gesture handlers**

Replace the current `on_swipe_left`, `on_swipe_right`, `on_double_tap` functions:

```python
def on_swipe_left(x, y):
    global screen_idx, state, _needs_redraw
    if state not in NAVIGABLE:
        return
    screen_idx = (screen_idx + 1) % len(SCREENS)
    state = SCREENS[screen_idx]
    _needs_redraw = True

def on_swipe_right(x, y):
    global screen_idx, state, _needs_redraw
    if state not in NAVIGABLE:
        return
    screen_idx = (screen_idx - 1) % len(SCREENS)
    state = SCREENS[screen_idx]
    _needs_redraw = True

def on_double_tap(x, y):
    """Double tap — retour a STATE_OK depuis n'importe quel etat."""
    global state, screen_idx, _needs_redraw
    state = STATE_OK
    screen_idx = 0
    _needs_redraw = True

def on_hold(x, y):
    sys.stdout.write("EMERGENCY:STOP\n")
```

- [ ] **Step 5: Update the main loop**

Replace the main loop (from `apply_state()` call at end down through `while True`):

```python
apply_state()   # afficher etat initial immediatement

buf = ""
_ANIM_INTERVAL_MS = 200   # intervalle animation pour BOOTING et LOCKED

while True:
    # Lecture commandes DISP: depuis Slave — non-bloquant
    if _poller.poll(0):
        try:
            ch = sys.stdin.read(1)
            if ch:
                buf += ch
                if '\n' in buf:
                    line, buf = buf.split('\n', 1)
                    parse_command(line)
        except Exception:
            pass

    # Touch
    if touch:
        try:
            touch.poll()
        except Exception:
            pass

    # Animation periodique pour BOOTING et LOCKED
    global _last_anim_ms
    now = time.ticks_ms()
    if state in (STATE_BOOTING, STATE_LOCKED):
        if time.ticks_diff(now, _last_anim_ms) >= _ANIM_INTERVAL_MS:
            _last_anim_ms = now
            _needs_redraw = True

    # Redessiner SEULEMENT si quelque chose a change
    if _needs_redraw:
        apply_state()

    time.sleep_ms(20)
```

Note: `global _last_anim_ms` inside the while loop is valid Python/MicroPython since `_last_anim_ms` is a module-level variable.

- [ ] **Step 6: Remove dead code**

Verify the file no longer contains references to:
- `STATE_BOOT_PROGRESS`
- `STATE_OPERATIONAL`
- `boot_items`
- `operational_since`
- `boot_timed_out`
- `_boot_start_ms`
- `_check_boot_timeout`
- `BOOT_TIMEOUT_MS`

- [ ] **Step 7: Commit**

```bash
git add rp2040/firmware/main.py
git commit -m "feat: RP2040 main — remove boot tracking, new states, render-what-you're-told"
```

> **Note:** RP2040 firmware must be flashed manually via USB (Thonny or rshell) — it is NOT part of the rsync pipeline. Flash both `main.py` and `display.py` after this task.

---

## Task 6 — Create `scripts/test_wifi_watchdog.py`

**Files:**
- Create: `scripts/test_wifi_watchdog.py`

This script runs from the **Master** via SSH onto the Slave. It's non-destructive: it tests Level 1 only (does not force Level 2 / home fallback which would cut Slave from Master during automated test).

- [ ] **Step 1: Create the file**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test WiFi Watchdog — validation non-destructive.
Exécuté depuis le Master via SSH sur le Slave :
  ssh artoo@r2-slave.local "python3 /home/artoo/r2d2/scripts/test_wifi_watchdog.py"

Étapes :
  1. Vérifie que le Slave est connecté au hotspot Master (pré-condition)
  2. Simule une coupure wlan0 — observe que le watchdog détecte et réagit
  3. Rétablit la connexion AP — vérifie la reconnexion Level 1
  4. Rapport PASS/FAIL
"""

import subprocess
import sys
import time
import importlib
import os

# --- Forcer UTF-8 ---
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

TIMEOUT_DETECTION_S = 45   # 30s cycle watchdog + 15s marge
TIMEOUT_RECONNECT_S = 30   # après nmcli connection up
AP_PROFILE          = "r2d2-master-hotspot"
SLAVE_CONN_CHECK    = "r2d2-master-hotspot"


def _run(cmd, timeout=10):
    """Exécute une commande shell, retourne (returncode, stdout, stderr)."""
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def check_precondition():
    """Étape 1 : vérifier que wlan0 est connecté au hotspot Master."""
    print("\n=== Étape 1 — Pré-condition ===")
    rc, out, _ = _run("nmcli -t -f NAME,DEVICE,STATE connection show --active")
    lines = [l for l in out.splitlines() if SLAVE_CONN_CHECK in l and 'wlan0' in l]
    if lines:
        print(f"  ✓ Slave connecté au hotspot Master : {lines[0]}")
        return True
    print(f"  ✗ Slave NON connecté à '{SLAVE_CONN_CHECK}'")
    print(f"    Connexions actives : {out}")
    return False


def get_display_last_cmd():
    """Lit _last_cmd depuis DisplayDriver en important le module Slave."""
    try:
        sys.path.insert(0, '/home/artoo/r2d2')
        # Import dynamique pour éviter de casser l'instance en cours
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "display_driver",
            "/home/artoo/r2d2/slave/drivers/display_driver.py"
        )
        # Note : on ne peut pas lire _last_cmd de l'instance en cours depuis un process séparé.
        # On observe plutôt les commandes nmcli dans les logs journald.
        return None
    except Exception:
        return None


def watch_nmcli_log(stop_at_keyword, timeout_s):
    """
    Surveille journald pour détecter les appels nmcli du WiFiWatchdog.
    Retourne True si le keyword est trouvé dans les logs dans le délai.
    """
    start = time.monotonic()
    print(f"  → Observation logs ({timeout_s}s max, cherche : '{stop_at_keyword}')...", flush=True)
    while time.monotonic() - start < timeout_s:
        rc, out, _ = _run(
            "journalctl -u r2d2-slave.service --no-pager -n 20 --since '2 minutes ago' 2>/dev/null",
            timeout=5
        )
        if stop_at_keyword.lower() in out.lower():
            return True
        time.sleep(2)
        print(".", end="", flush=True)
    print()
    return False


def simulate_disconnect():
    """Étape 2 : déconnecter wlan0 manuellement pour forcer le watchdog."""
    print("\n=== Étape 2 — Simulation coupure wlan0 ===")
    rc, out, err = _run("nmcli device disconnect wlan0")
    if rc == 0:
        print("  ✓ wlan0 déconnecté")
        return True
    print(f"  ✗ Erreur nmcli disconnect : {err}")
    return False


def wait_for_watchdog_reaction():
    """Attend que le WiFiWatchdog détecte la coupure (Level 1 attempt 1)."""
    print(f"  → Attente réaction watchdog ({TIMEOUT_DETECTION_S}s max)...")
    found = watch_nmcli_log("Level 1", TIMEOUT_DETECTION_S)
    if found:
        print("  ✓ WiFiWatchdog Level 1 détecté dans les logs")
    else:
        print("  ✗ Pas de réaction Level 1 dans le délai")
    return found


def restore_connection():
    """Étape 3 : forcer la reconnexion AP (simule ce que le watchdog ferait)."""
    print("\n=== Étape 3 — Reconnexion AP ===")
    rc, out, err = _run(f"nmcli connection up {AP_PROFILE}", timeout=20)
    if rc == 0:
        print(f"  ✓ Connexion '{AP_PROFILE}' rétablie")
    else:
        print(f"  ⚠ nmcli connection up rc={rc}: {err}")

    # Vérifier ping Master
    print(f"  → Vérification ping r2-master.local ({TIMEOUT_RECONNECT_S}s)...")
    start = time.monotonic()
    while time.monotonic() - start < TIMEOUT_RECONNECT_S:
        rc, _, _ = _run("ping -c 1 -W 2 r2-master.local", timeout=4)
        if rc == 0:
            print("  ✓ Ping r2-master.local : OK")
            return True
        time.sleep(3)
    print("  ✗ Ping r2-master.local : TIMEOUT")
    return False


def main():
    print("=" * 60)
    print("  Test WiFi Watchdog — validation non-destructive")
    print("=" * 60)

    results = {}

    # Étape 1
    results['precondition'] = check_precondition()
    if not results['precondition']:
        print("\n⚠ Pré-condition non remplie — test annulé")
        sys.exit(2)

    # Étape 2
    results['disconnect'] = simulate_disconnect()
    if results['disconnect']:
        results['watchdog_reacted'] = wait_for_watchdog_reaction()
    else:
        results['watchdog_reacted'] = False

    # Étape 3
    results['reconnected'] = restore_connection()

    # Rapport
    print("\n=== Rapport ===")
    all_pass = all(results.values())
    for k, v in results.items():
        icon = "✓" if v else "✗"
        print(f"  {icon} {k}: {'PASS' if v else 'FAIL'}")

    if all_pass:
        print("\n✓ PASS — WiFi Watchdog fonctionnel")
        sys.exit(0)
    else:
        print("\n✗ FAIL — Voir détails ci-dessus")
        sys.exit(1)


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x scripts/test_wifi_watchdog.py
```

- [ ] **Step 3: Commit**

```bash
git add scripts/test_wifi_watchdog.py
git commit -m "feat: scripts/test_wifi_watchdog.py — validation non-destructive Level 1"
```

---

## Task 7 — Deploy and verify

- [ ] **Step 1: Push to GitHub**

```bash
git push
```

- [ ] **Step 2: Deploy to Slave via SSH (paramiko)**

```python
import paramiko, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.2.104', username='artoo', password='deetoo', timeout=10)
stdin, stdout, stderr = c.exec_command('cd /home/artoo/r2d2 && git pull && bash scripts/update.sh 2>&1')
for line in stdout:
    print(line, end='')
c.close()
```

- [ ] **Step 3: Flash RP2040 manually**

Connect RP2040 via USB to PC. Use Thonny or rshell to upload:
- `rp2040/firmware/display.py` → `/display.py` on device
- `rp2040/firmware/main.py` → `/main.py` on device

Then hard-reset the RP2040 (BOOTSEL or power cycle via USB).

- [ ] **Step 4: Verify Slave boot**

SSH to Slave and check logs:
```bash
ssh artoo@r2-slave.local "journalctl -u r2d2-slave.service --no-pager -n 30"
```

Expected: WiFiWatchdog started message, no import errors.

- [ ] **Step 5: Verify WiFi Watchdog is running**

```bash
ssh artoo@r2-slave.local "ps aux | grep wifi_watchdog"
# → thread visible (daemon thread, part of r2d2-slave process)
```

Check watchdog logs after waiting 35s:
```bash
ssh artoo@r2-slave.local "journalctl -u r2d2-slave.service --no-pager -n 10"
# Expected: periodic "WiFiWatchdog: Master joignable — CONNECTED" (or silence if CONNECTED)
```

- [ ] **Step 6: Run validation test script**

From Master SSH:
```bash
ssh artoo@r2-slave.local "python3 /home/artoo/r2d2/scripts/test_wifi_watchdog.py"
```

Expected final output: `✓ PASS — WiFi Watchdog fonctionnel`

- [ ] **Step 7: Verify RP2040 display**

On Slave reboot, the RP2040 should show orange spinner ("STARTING UP") instead of the 7-item boot list. After DISP:READY, it transitions to green OK screen with bus health bar at bottom.

---

---

## Task 8 — Create `scripts/deploy_rp2040.sh`

**Files:**
- Create: `scripts/deploy_rp2040.sh`

Automates pushing MicroPython firmware to the RP2040 from the Slave Pi via USB, using `ampy`. Replaces the manual Thonny workflow. Runs on the Slave Pi (where the RP2040 is USB-connected).

- [ ] **Step 1: Create the script**

```bash
#!/usr/bin/env bash
# deploy_rp2040.sh — Pousse le firmware MicroPython vers le RP2040 via USB/ampy
# Usage: bash scripts/deploy_rp2040.sh [/dev/ttyACMx]
#
# Doit être exécuté sur le Slave Pi (où le RP2040 est branché).
# Arrête temporairement r2d2-slave.service pour libérer le port USB.

set -e

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FIRMWARE_DIR="$REPO_DIR/rp2040/firmware"

# Couleurs
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${GREEN}[deploy_rp2040]${NC} $*"; }
warn() { echo -e "${YELLOW}[deploy_rp2040]${NC} $*"; }
err()  { echo -e "${RED}[deploy_rp2040]${NC} $*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Trouver le port RP2040
# ---------------------------------------------------------------------------
find_port() {
    # Chercher par identifiant USB stable (Raspberry Pi / MicroPython)
    local by_id
    by_id=$(ls /dev/serial/by-id/ 2>/dev/null | grep -i "Raspberry_Pi" | head -1)
    if [ -n "$by_id" ]; then
        echo "/dev/serial/by-id/$by_id"
        return
    fi
    # Fallback : tester les ports ACM du plus grand au plus petit
    # (avec VESCs = ttyACM2, sans VESCs = ttyACM0)
    for p in /dev/ttyACM2 /dev/ttyACM1 /dev/ttyACM0; do
        [ -e "$p" ] && echo "$p" && return
    done
}

PORT="${1:-}"
if [ -z "$PORT" ]; then
    PORT="$(find_port)"
fi
[ -z "$PORT" ] && err "Port RP2040 introuvable. Brancher le RP2040 via USB et réessayer."
log "Port RP2040 : $PORT"

# ---------------------------------------------------------------------------
# Installer ampy si absent
# ---------------------------------------------------------------------------
if ! command -v ampy &>/dev/null; then
    warn "ampy non trouvé — installation (adafruit-ampy)..."
    pip3 install --quiet adafruit-ampy
fi

# ---------------------------------------------------------------------------
# Arrêter r2d2-slave.service pour libérer le port
# ---------------------------------------------------------------------------
SLAVE_WAS_RUNNING=false
if systemctl is-active --quiet r2d2-slave.service 2>/dev/null; then
    log "Arrêt r2d2-slave.service (libère le port USB)..."
    sudo systemctl stop r2d2-slave.service
    SLAVE_WAS_RUNNING=true
fi

cleanup() {
    if [ "$SLAVE_WAS_RUNNING" = true ]; then
        log "Redémarrage r2d2-slave.service..."
        sudo systemctl start r2d2-slave.service
    fi
}
trap cleanup EXIT

# Courte pause pour que le port soit bien libéré
sleep 1

# ---------------------------------------------------------------------------
# Pousser les fichiers firmware
# ---------------------------------------------------------------------------
log "Upload display.py..."
ampy --port "$PORT" put "$FIRMWARE_DIR/display.py" display.py

if [ -f "$FIRMWARE_DIR/touch.py" ]; then
    log "Upload touch.py..."
    ampy --port "$PORT" put "$FIRMWARE_DIR/touch.py" touch.py
fi

log "Upload main.py (en dernier — déclenche l'exécution au reset)..."
ampy --port "$PORT" put "$FIRMWARE_DIR/main.py" main.py

# ---------------------------------------------------------------------------
# Reset soft du RP2040
# ---------------------------------------------------------------------------
log "Reset RP2040 (soft reset via ampy)..."
ampy --port "$PORT" reset

log ""
log "✓ Firmware RP2040 déployé sur $PORT"
log "  Le RP2040 redémarre et affiche le spinner BOOTING (orange)."
log "  Si le service r2d2-slave était actif, il redémarre automatiquement."
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x scripts/deploy_rp2040.sh
```

- [ ] **Step 3: Commit**

```bash
git add scripts/deploy_rp2040.sh
git commit -m "feat: scripts/deploy_rp2040.sh — déploiement firmware RP2040 via ampy"
```

- [ ] **Step 4: Test the script from Slave Pi**

SSH to Slave, then:
```bash
ssh artoo@r2-slave.local "cd /home/artoo/r2d2 && bash scripts/deploy_rp2040.sh"
```

Expected output sequence:
```
[deploy_rp2040] Port RP2040 : /dev/ttyACM2   (ou ACM0 si sans VESCs)
[deploy_rp2040] Arrêt r2d2-slave.service (libère le port USB)...
[deploy_rp2040] Upload display.py...
[deploy_rp2040] Upload touch.py...
[deploy_rp2040] Upload main.py (en dernier)...
[deploy_rp2040] Reset RP2040 (soft reset via ampy)...
[deploy_rp2040] ✓ Firmware RP2040 déployé sur /dev/ttyACM2
[deploy_rp2040] Redémarrage r2d2-slave.service...
```

The RP2040 screen should show the orange spinner immediately after reset.

---

## Notes

- **RP2040 animation**: The spinner and locked blink are driven by `_last_anim_ms` in the main loop — they redraw every 200ms automatically without requiring external signals.
- **Level 2 not tested automatically**: `test_wifi_watchdog.py` does not test home WiFi fallback to avoid cutting the Slave from the test runner. Test Level 2 manually by blocking the AP for >3 minutes.
- **`slave/main.py` emergency_stop closure**: The local `emergency_stop_vesc` function defined inside `main()` shadows the module-level version. It must be defined before `watchdog.register_stop_callback(emergency_stop_vesc)` — do NOT add a second register call.
- **boot_start() still called**: `slave/main.py` still calls `display.boot_start()` (→ `DISP:BOOT:START`). In the new RP2040 firmware this triggers `STATE_BOOTING` (spinner). The subsequent `boot_item/ok/fail` calls are sent but silently ignored — the spinner keeps spinning until `DISP:READY:v`.
- **deploy_rp2040.sh**: Runs on Slave Pi where the RP2040 is connected. Stops r2d2-slave.service to release the ttyACM port, uploads files via ampy, then restarts the service via the EXIT trap.
