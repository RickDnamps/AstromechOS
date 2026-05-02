# R2-D2 — Installation Guide

> This is the **primary and most up-to-date guide**. 🇫🇷 [Lire en français](HOWTO_FR.md) *(may lag behind)*

Everything is automated. The full installation is **3 commands + 2 reboots**.

---

## Hardware prerequisites

| Component | Master (dome) | Slave (body) |
|-----------|--------------|--------------|
| Pi model | Pi 4B 4GB | Pi 4B 2GB |
| OS | Raspberry Pi OS Lite 64-bit Trixie | same |
| Wi-Fi | built-in wlan0 + **USB Wi-Fi dongle** (wlan1) | built-in wlan0 only |

> The Master needs a USB Wi-Fi dongle (wlan1) so that wlan0 can be the hotspot
> for the Slave and remote controls, while wlan1 stays connected to the internet
> for git updates.

---

## UART wiring — connect the two Pi before anything else

The Master and Slave communicate over a **physical UART serial link** at 115200 baud.
Without this wire, nothing works: no heartbeat → Slave watchdog cuts motors after 500ms,
no audio commands, no servo control, no telemetry.

**Connect 3 wires between the two Pi boards:**

```
Master Pi 4B              Slave Pi 4B
─────────────────         ─────────────────
Pin 8  GPIO14 TX  ──────→  Pin 10 GPIO15 RX
Pin 10 GPIO15 RX  ←──────  Pin 8  GPIO14 TX
Pin 6  GND        ─────── Pin 6  GND
```

> Both Pi 4B use 3.3V GPIO — no level shifter needed.
> Use female-female jumper wires for bench testing.
> In the assembled robot these 3 wires run through the slip ring (wires 7, 8, and GND).

**GPIO pin map (physical header numbering):**

```
 Pi GPIO header (looking at the pins from above, USB ports at bottom)
 ┌─────┬─────┐
 │ 3V3 │ 5V  │  ← pins 1, 2
 │ SDA │ 5V  │  ← pins 3, 4
 │ SCL │ GND │  ← pins 5, 6  ← GND here
 │  4  │ 14  │  ← pins 7, 8  ← TX here (GPIO14)
 │ GND │ 15  │  ← pins 9, 10 ← RX here (GPIO15)
 │ 17  │ 18  │
 ...
```

The UART port used is `/dev/ttyAMA0` (hardware UART, freed from Bluetooth by the install scripts).

> **Bench testing without the robot assembled?**
> Place both Pi side by side and use 10cm jumper wires.
> The system works exactly the same — the slip ring is just a longer version of the same 3 wires.

---

## Step 0 — Flash both SD cards

Use **Raspberry Pi Imager** → click ⚙️ Options before writing:

| Setting | Master | Slave |
|---------|--------|-------|
| Username | `artoo` | `artoo` |
| Password | (your choice — same on both is recommended) | same |
| Hostname | `r2-master` | `r2-slave` |
| Wi-Fi | your home network | your home network |
| SSH | enabled | enabled |

Both Pis boot directly connected to your home Wi-Fi on wlan0.
Find their IPs in your router, or use `r2-master.local` / `r2-slave.local`.

---

## Step 1 — Install the Master

Plug the USB Wi-Fi dongle into the Master, then SSH into it from your PC:

```bash
ssh artoo@r2-master.local
# or: ssh artoo@<MASTER_IP>  if .local doesn't resolve
```

**Before running the installer**, note the Master's current IP on your home network —
you'll need it to reconnect after the reboot:

```bash
hostname -I
# example output: 192.168.1.42  — write this down
```

Run the one-line installer:

```bash
curl -fsSL https://raw.githubusercontent.com/RickDnamps/R2D2_Control/main/scripts/setup_master.sh | sudo bash
```

This script handles everything automatically:
- System update + packages
- Git clone of the repo
- UART fix (`miniuart-bt` — Bluetooth stays active for the gamepad)
- Enable hardware UART + I2C
- Python dependencies
- `local.cfg` from the example template
- Wi-Fi reconfiguration: wlan0 → hotspot `R2D2_Control` (192.168.4.1), wlan1 → home internet
- Ed25519 SSH key generation (for Master → Slave rsync)
- systemd services installed and enabled

**At the end it asks to reboot — answer Y.**

---

### After the reboot — reconnecting to the Master

After reboot, the Master's Wi-Fi changes:

```
Before:  wlan0 → your home Wi-Fi  (accessible from your PC)
After:   wlan0 → hotspot R2D2_Control  192.168.4.1  (only from hotspot)
         wlan1 → your home Wi-Fi  (new IP assigned by your router)
```

Your PC is still on the home network, so you have **two options** to reconnect:

**Option A — Connect your PC to the R2D2_Control hotspot (recommended)**

1. On your PC, connect to Wi-Fi network: **R2D2_Control**
2. SSH using the fixed hotspot IP:
   ```bash
   ssh artoo@192.168.4.1
   ```
   This IP never changes — use it for all future SSH sessions.

**Option B — Stay on home network, use the new wlan1 IP**

The Master's wlan1 gets a new DHCP IP from your router.
Find it in one of these ways:
- Check your router's admin page (look for `r2-master`)
- Try: `ssh artoo@r2-master.local` (works on Linux/Mac via mDNS, unreliable on Windows)
- Use a network scanner app (e.g. Fing on phone, Angry IP Scanner on PC)

> Option A is simpler and what you'll use permanently — the hotspot IP 192.168.4.1 is fixed forever.
> Switch to it now and you won't need to look up IPs again.

---

## Step 2 — Install the Slave

**While the Slave is still on your home Wi-Fi** (before connecting to the hotspot), SSH into it:

```bash
ssh artoo@r2-slave.local
# or: ssh artoo@<SLAVE_IP>
```

Run the one-line installer:

```bash
curl -fsSL https://raw.githubusercontent.com/RickDnamps/R2D2_Control/main/scripts/setup_slave.sh | sudo bash
```

This script handles everything automatically:
- System update + packages (`mpg123`, `alsa-utils`, `i2c-tools`, `python3-smbus`, `pulseaudio`, `pulseaudio-module-bluetooth`, `bluez`, `libasound2-plugins`)
- UART fix (`miniuart-bt` — BT chip stays active via mini-UART, freeing the PL011 hardware UART `/dev/ttyAMA0` for the Master↔Slave link)
- Enable hardware UART + I2C
- Python dependencies (pyserial, smbus2, adafruit-pca9685)
- Wi-Fi: connect wlan0 to the `R2D2_Control` hotspot
- ALSA → PulseAudio routing (`~/.asoundrc`) — `mpg123` audio routes through PulseAudio, enabling 3.5mm jack or BT speaker output
- BT speaker support: `artoo` user added to `bluetooth` group, PulseAudio BT modules configured (`default.pa`), linger enabled for headless session

**At the end it asks to reboot — answer Y.**

The Slave is now connected to the Master hotspot at `192.168.4.171`.

---

## Step 3 — First code deployment (from the Master)

SSH into the Master using whichever method you used in Step 1:

- **Option A (hotspot):** your PC is on `R2D2_Control` → `ssh artoo@192.168.4.1`
- **Option B (home network):** `ssh artoo@r2-master.local` or the IP you found in your router

Run the first deployment:

```bash
bash /home/artoo/r2d2/scripts/deploy.sh --first-install
```

This:
- rsync's all code to the Slave
- Installs pip dependencies on the Slave
- Installs and enables `r2d2-slave` systemd service
- Restarts the Slave

Then copy the SSH key to the Slave (enables passwordless rsync for future updates):

```bash
ssh-copy-id artoo@r2-slave.local
```

**Done.** R2-D2 is operational.

---

## Connecting to the dashboard

Flask listens on all network interfaces — no need to switch Wi-Fi, you can reach the dashboard from **either network**.

**From your home Wi-Fi (most convenient — stay on your normal network):**

Find the Master's wlan1 IP (the one your router assigned):
- Check your router's admin page (look for `r2-master`)
- Or SSH into the Master and run `hostname -I` — the second IP is wlan1
- Or try `http://r2-master.local:5000` directly in a browser (works on Linux/Mac/Android)

Then open: `http://<wlan1-IP>:5000`

> This IP can change if your router reassigns it. To keep it stable, assign a static DHCP lease in your router settings for the Master's MAC address.

**From the R2D2_Control hotspot (fixed IP, always works — best for events):**

Connect your device to Wi-Fi **R2D2_Control**, then open: **http://192.168.4.1:5000**

**The Android app** auto-discovers the Master on whichever network it's connected to.

---

## Daily use

### Admin mode

Click the **🔒 ADMIN** button in the tab bar (beside the ⚙️ gear) to unlock admin mode from any tab — no need to navigate to Settings first. Enter the password once, and admin stays active for 5 minutes of inactivity. The timer resets on any mouse movement, click, or key press, so you won't be logged out while actively working. Click the button again (now 🔓) to lock immediately.

### Adding sounds

In admin mode, the **Audio tab** shows an upload zone. Drag an MP3 onto it (or click to browse), choose a category, and upload. The sound is saved and synced to the Slave Pi automatically — no SSH, no restart, available immediately.

To create a new category, use the **Create Category** panel below the upload zone.

### Managing choreographies

**Choreo cards (Sequences tab) — admin mode only:**
- Click the **label** to rename it (displayed in the file selector and on the card)
- Click the **emoji** to open the emoji picker
- Use the **category dropdown** on the card to reassign it to a different category

Choreo categories (create / rename / reorder / delete) are managed from the category panel in the CHOREO tab — no file editing required.

**Choreo editor toolbar — admin mode only:**

The toolbar buttons **RENAME · SAVE · DELETE · EXPORT · IMPORT** are only visible when admin is unlocked. Non-admins can still open, edit, and play choreographies — they just cannot persist changes to disk.

- **RENAME** — renames the `.chor` file on disk (the internal filename shown in the file selector). Use this to give a file a clean permanent name after experimenting.
- **SAVE** — the only way to write a choreo to disk. Always required to keep your work.
- **DELETE** — permanently removes the `.chor` file.
- **EXPORT / IMPORT** — download or upload `.chor` files for backup or sharing.

**Play without saving — preview mode:**

Anyone (admin or not) can press **Play** at any time without saving first. The current choreo is written to an invisible temp file (`__preview__.chor`) and played from there — it never appears in the choreo list and is overwritten on every preview play.

Rules for what Play does:
| Situation | Admin | Result |
|-----------|-------|--------|
| Existing file, no changes | any | Plays the saved file directly |
| Existing file, modified | ✅ | Auto-saves changes, then plays |
| Existing file, modified | ❌ | Plays via preview — file on disk unchanged |
| New choreo (never saved) | any | Plays via preview — nothing written to disk |

When admin plays an unsaved choreo, a reminder toast appears: **"Preview playing — press Save to keep this choreography"**.

### Cockpit Status Panel

The **STATUS** button in the top-right corner of the dashboard opens a collapsible overlay showing a live snapshot of the robot from any tab: audio · lights · VESC voltage/amps/watts · Pi CPU/RAM/temperature · Master and Slave IPs · E-Stop and Bench mode state.

### VESC safety lock

When a VESC is offline or reporting a fault, a red banner appears in the Drive tab and all drive commands are blocked (web, Android, BT gamepad). This prevents accidentally driving on a half-connected bench setup.

To test software without motors physically connected, enable **Bench mode** in **Config → VESC**. The setting is persisted in `local.cfg` and survives reboots. Disable it before field use.

### SSH access

```bash
# From any device on the R2D2_Control hotspot:
ssh artoo@192.168.4.1    # Master (dome)
ssh artoo@192.168.4.171  # Slave (body)

# From the Master, reach the Slave:
ssh artoo@r2-slave.local
```

> Do not use `.local` hostnames from Windows — mDNS is unreliable.
> Use the fixed IPs above instead.

### Update R2-D2

**From the dashboard:** click the **Admin** button (top right) → enter password **`deetoo`** → the Config tab and other protected menus become visible → Config → System → Update button (git pull + rsync + restart, all automatic).

> Admin session expires after 5 minutes of inactivity. The password can be changed in the Config tab once logged in.

**Or from SSH on the Master:**

```bash
bash /home/artoo/r2d2/scripts/update.sh
```

This does: backup sequences → git pull → rsync to Slave → restart Slave → restart Master → verify services.

### Check service status

```bash
# On Master:
sudo systemctl status r2d2-master
sudo journalctl -u r2d2-master -f

# On Slave (from Master):
ssh artoo@r2-slave.local sudo systemctl status r2d2-slave
ssh artoo@r2-slave.local sudo journalctl -u r2d2-slave -f
```

### Collect debug info

```bash
bash /home/artoo/r2d2/scripts/check_logs.sh
bash /home/artoo/r2d2/scripts/debug_collect.sh
```

### Resync Slave only (without git pull)

```bash
bash /home/artoo/r2d2/scripts/resync_slave.sh
```

---

## Hardware wiring

See [ELECTRONICS.md](ELECTRONICS.md) for all hardware wiring details:
- UART slip ring
- PCA9685 servo controllers (I2C)
- VESC motor controllers (USB + CAN)
- Teeces32 / AstroPixels+ LED logic
- RP2040 display

---

## RP2040 display firmware

Flash manually via `mpremote` (only needed after hardware replacement or firmware reset):

```bash
# SSH into the Slave:
ssh artoo@r2-slave.local

# Flash (always rm before cp — mpremote compares timestamps, not content):
python3 -m mpremote connect /dev/ttyACM0 rm :display.py
python3 -m mpremote connect /dev/ttyACM0 cp /home/artoo/r2d2/rp2040/firmware/display.py :display.py
```

Or use the dedicated script from the Master:

```bash
bash /home/artoo/r2d2/scripts/deploy_rp2040.sh
```

---

## Bluetooth gamepad pairing

Pair from the dashboard: **Config tab → BT Gamepad** → Scan → pair your controller.

Or manually on the Master:

```bash
bluetoothctl
> power on
> scan on
# wait for your controller to appear
> pair XX:XX:XX:XX:XX:XX
> trust XX:XX:XX:XX:XX:XX
> connect XX:XX:XX:XX:XX:XX
> quit
```

The gamepad auto-reconnects on next boot.

> **Battery level:** supported for PS4, PS5, and Xbox controllers.
> The NVIDIA Shield controller does not expose battery via any standard Linux interface.

---

## Bluetooth speaker pairing (bench testing)

> ⚠️ Audio quality is limited due to mini-UART BT + Wi-Fi 2.4GHz coexistence on the Slave Pi. This is for bench testing only — the assembled robot will use the 3.5mm jack with a wired amplifier.

Pair a Bluetooth speaker to the **Slave Pi** from the dashboard: **Settings → Audio → Bluetooth Speaker** → Scan → pair and connect your speaker.

**What happens automatically:**
- Sound output switches to the BT speaker (A2DP sink set as PulseAudio default)
- The volume slider in the BT Speaker panel controls PA sink volume independently from the main ALSA volume slider
- Disconnecting restores the 3.5mm jack automatically

Or manually on the Slave:

```bash
ssh artoo@192.168.4.171
bluetoothctl
> power on
> pairable on
> scan on
# wait for your speaker to appear
> pair XX:XX:XX:XX:XX:XX
> trust XX:XX:XX:XX:XX:XX
> connect XX:XX:XX:XX:XX:XX
> quit
# Set as default PulseAudio sink:
XDG_RUNTIME_DIR=/run/user/$(id -u) pactl set-default-sink bluez_sink.XX_XX_XX_XX_XX_XX.a2dp_sink
```

---

## Available scripts

| Script | Where to run | Purpose |
|--------|-------------|---------|
| `scripts/setup_master.sh` | Master (once) | Full Master installation |
| `scripts/setup_slave.sh` | Slave (once) | Full Slave installation |
| `scripts/deploy.sh --first-install` | Master (once) | First code push to Slave |
| `scripts/update.sh` | Master | git pull + full update |
| `scripts/resync_slave.sh` | Master | rsync to Slave only |
| `scripts/check_logs.sh` | Master | View service logs |
| `scripts/debug_collect.sh` | Master | Collect debug bundle |
| `scripts/deploy_rp2040.sh` | Master | Flash RP2040 display firmware |
| `scripts/test_uart.sh` | Master | Test UART link to Slave |
| `scripts/test_servos.sh` | Master | Test servo sweep |
| `scripts/stop_servos.sh` | Master | Emergency servo stop |

---

## Network reference

| Host | IP | Access from |
|------|----|-------------|
| Master | `192.168.4.1` | any device on hotspot |
| Slave | `192.168.4.171` | any device on hotspot |
| Dashboard | `http://192.168.4.1:5000` | browser on hotspot |
| SSH Master | `ssh artoo@192.168.4.1` | password: `deetoo` |
| SSH Slave | `ssh artoo@192.168.4.171` | password: `deetoo` |
