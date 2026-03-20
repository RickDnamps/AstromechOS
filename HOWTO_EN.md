# R2-D2 — Complete Installation Guide

> 🇫🇷 [Lire en français](HOWTO.md)

| Phase | Content | Status |
|-------|---------|--------|
| **1** | Infrastructure: UART / Heartbeat / Watchdog / Version sync / Hotspot | ✅ Ready |
| **2** | Propulsion: VESCs / Dome motor / Body servos | 🔧 Uncomment to activate |
| **3** | Behavioral sequence scripts (.scr) | 🔧 Uncomment to activate |
| **4** | Flask REST API + Web Dashboard | 🔧 Uncomment to activate |

---

## ⚠️ Mandatory installation order

```
1. R2-Master  (steps 0 → 2)    ← ALWAYS FIRST
2. R2-Slave   (steps 1b → 2b)  ← only after Master has rebooted
3. Common steps (3 → 7)
```

> The Slave must connect to the **Master's Wi-Fi hotspot**.
> That hotspot doesn't exist until the Master is configured and rebooted.
> Setting up the Slave first = you can't reach it over SSH.

---

## Hardware prerequisites

| Component | Master (dome) | Slave (body) |
|-----------|--------------|--------------|
| Pi 4B | 4GB | 2GB |
| OS | Raspberry Pi OS Lite 64-bit Trixie | same |
| Wi-Fi | built-in wlan0 + **USB Wi-Fi dongle** (wlan1) | built-in wlan0 only |
| Initial network | connected to your home Wi-Fi | connected to your home Wi-Fi |

**Before you start — flash SD cards with Raspberry Pi Imager:**
Click ⚙️ Options in the Imager for **both** cards:
- Username: `artoo`
- Password: (your choice — same on both is recommended)
- Wi-Fi: your home network (SSID + password)
- SSH: enabled
- Hostname Master: `r2-master`
- Hostname Slave: `r2-slave`

---

## Overview

```
─── PHASE 1 ────────────────────────────────────────────────
── On R2-Master (FIRST) ──
STEP 0  — local.cfg (GitHub, desired hotspot settings)
STEP 1  — Packages + git repo
STEP 2  — Master network: hotspot on wlan0 + internet on wlan1
           → note the hotspot SSID/password
           → sudo reboot

── On R2-Slave (after Master has rebooted) ──
STEP 1b — Packages on Slave
STEP 2b — Slave network: connect wlan0 to Master hotspot
           → sudo reboot

── Common steps ──
STEP 3  — Passwordless SSH Master → Slave
STEP 4  — Initial code deployment (rsync)
STEP 5  — systemd services
STEP 6  — RP2040 firmware
STEP 7  — Phase 1 validation tests

─── PHASE 2 ────────────────────────────────────────────────
STEP 8  — VESC wiring (propulsion)
STEP 9  — Dome motor wiring (TB6612)
STEP 10 — Body servo wiring (PCA9685 I2C)
STEP 11 — Enable Phase 2 drivers

─── PHASE 3 ────────────────────────────────────────────────
STEP 12 — Sequence scripts (.scr)
STEP 13 — Enable ScriptEngine

─── PHASE 4 ────────────────────────────────────────────────
STEP 14 — Flask REST API
STEP 15 — Web Dashboard
STEP 16 — Phase 4 validation tests
```

---

## STEP 0 — Configure local.cfg (once only)

`local.cfg` is your **personal R2-D2 configuration file**.
It is **never overwritten by git pull** — this is where your Wi-Fi credentials and GitHub URL live.

```bash
# On R2-Master, after git clone
cd /home/artoo/r2d2/master/config
cp local.cfg.example local.cfg
# That's it — all values are pre-filled in the example.
# [home_wifi] will be filled automatically by setup_master_network.sh (step 2).
```

> If you want to customize the hotspot SSID/password or the dome button GPIO pin,
> edit `local.cfg` with `nano local.cfg` before moving to step 2.

---

## STEP 1 — Prepare both Pi boards

### 1.1 — On R2-Master (Pi 4B 4GB — Dome)

> **Imager prerequisite:** when flashing the SD card, configure via
> Raspberry Pi Imager → ⚙️ Options:
> - Username: `artoo` / Password: (your choice)
> - Hostname: `r2-master`
> - Wi-Fi: your home network (SSID + password)
> - SSH: enabled
>
> The Pi will boot directly connected to your home Wi-Fi on `wlan0`.

```bash
# SSH connection (home network, first time)
ssh artoo@r2-master.local
# or with IP if .local doesn't resolve yet:
ssh artoo@<R2MASTER_IP>

# Set hostname
sudo hostnamectl set-hostname r2-master

# System update
sudo apt-get update && sudo apt-get upgrade -y

# System packages
sudo apt-get install -y python3-pip python3-serial git rsync

# Python dependencies
pip3 install --break-system-packages -r /home/artoo/r2d2/master/requirements.txt

# Enable hardware UART (disable serial console)
sudo raspi-config nonint do_serial_hw 0    # enable hardware UART
sudo raspi-config nonint do_serial_cons 1  # disable console on UART

# Enable I2C
sudo raspi-config nonint do_i2c 0

# Clone repo from GitHub (replace with your URL)
git clone https://github.com/RickDnamps/R2D2_Control.git /home/artoo/r2d2

# Generate the VERSION file
cd /home/artoo/r2d2
git rev-parse --short HEAD > /home/artoo/r2d2/VERSION

sudo reboot
```

### 1.2 — On R2-Slave (Pi 4B 2GB — Body)

> **Imager prerequisite:** same as Master:
> - Username: `artoo` / Hostname: `r2-slave`
> - Wi-Fi: your home network (the Slave will switch to the Master hotspot later)
> - SSH: enabled

```bash
# SSH connection (home network, first time)
ssh artoo@r2-slave.local

# Set hostname
sudo hostnamectl set-hostname r2-slave

# System update
sudo apt-get update && sudo apt-get upgrade -y

# System packages
sudo apt-get install -y python3-pip python3-serial git

# Python dependencies (copied by rsync at step 4)
# pip3 install --break-system-packages -r /home/artoo/r2d2/slave/requirements.txt  ← after first rsync

# Enable hardware UART
sudo raspi-config nonint do_serial_hw 0
sudo raspi-config nonint do_serial_cons 1

# Enable I2C
sudo raspi-config nonint do_i2c 0

# Create the repo folder (will be filled by rsync from Master)
mkdir -p /home/artoo/r2d2

sudo reboot
```

---

## STEP 2 — Wi-Fi Hotspot on R2-Master

### Overview

Raspberry Pi OS Trixie uses **NetworkManager** by default.
The script automatically detects your home Wi-Fi credentials (already configured on wlan0 by the Imager),
saves them to `local.cfg`, then switches the interfaces:

```
Initial state (straight from Imager):
  wlan0  → connected to your home Wi-Fi

Final state after the script:
  wlan0  → Hotspot "R2D2_Control"  192.168.4.1   (Slave + remotes connect here)
  wlan1  → your home Wi-Fi          DHCP           (git pull / GitHub)
```

### 2.1 — Plug in the USB Wi-Fi dongle (wlan1)

Plug the USB Wi-Fi dongle into a USB port **before** running the script.

Verify it shows up:
```bash
ip link show
# should show both wlan0 AND wlan1
```

> If the dongle isn't available yet, the script configures it anyway.
> It will connect automatically on first plug-in.

### 2.2 — Run the network setup script

```bash
sudo bash /home/artoo/r2d2/scripts/setup_master_network.sh
```

The script will:
1. **Read** the home Wi-Fi SSID and password from NetworkManager
2. **Confirm** with you (or let you type them manually if not detected)
3. **Save** to `master/config/local.cfg` → `[home_wifi]` section
4. **Configure wlan1** with those credentials (auto-connect)
5. **Convert wlan0** into a hotspot named `R2D2_Control` (fixed IP 192.168.4.1)
6. Enable **avahi-daemon** for `.local` hostname resolution

```bash
sudo reboot
```

### 2.3 — Verify after reboot

```bash
# From your PC connected to the "R2D2_Control" hotspot:
ping 192.168.4.1          # R2-Master responds ✓

# Verify wlan1 has internet:
ssh artoo@192.168.4.1
ping -I wlan1 8.8.8.8     # internet via wlan1 ✓

# Verify network config:
nmcli device status
# wlan0  wifi  connected  r2d2-hotspot
# wlan1  wifi  connected  r2d2-internet
```

### 2.4 — Verify local.cfg

```bash
cat /home/artoo/r2d2/master/config/local.cfg
# Should contain:
# [home_wifi]
# ssid = YOUR_HOME_WIFI
# password = ***
```

> `local.cfg` is **gitignored** — it will never be overwritten by a `git pull`.
> If you change your home Wi-Fi, edit this section manually and run:
> `nmcli connection modify r2d2-internet wifi-sec.psk "NEW_PASSWORD"`

---

## STEP 1b — Prepare R2-Slave (base packages)

> The Slave is still on your home Wi-Fi at this stage — that's normal.
> Its network will switch to the Master hotspot at step 2b.

```bash
# SSH connection (home network — while Slave is still on it)
ssh artoo@r2-slave.local

# System update
sudo apt-get update && sudo apt-get upgrade -y

# System packages
sudo apt-get install -y python3-pip python3-serial git alsa-utils

# Enable hardware UART (disable serial console)
sudo raspi-config nonint do_serial_hw 0
sudo raspi-config nonint do_serial_cons 1

# Enable I2C
sudo raspi-config nonint do_i2c 0

# Create the repo folder (will be filled by rsync from Master)
mkdir -p /home/artoo/r2d2

# Don't reboot yet — wait for step 2b
```

---

## STEP 2b — Slave network: connect to Master hotspot

> ⚠️ The Master must be **rebooted with its hotspot active** before continuing.
> Connect your PC to the `R2D2_Control` hotspot and verify:
> ```bash
> ping 192.168.4.1   # must respond
> ```

### 2b.1 — Copy the script to the Slave

The repo isn't on the Slave yet — copy the script from the Master:

```bash
# From the Master
scp /home/artoo/r2d2/scripts/setup_slave_network.sh \
    artoo@r2-slave.local:/home/artoo/setup_slave_network.sh
```

> If you can't SSH to the Slave from the Master yet,
> copy the script directly from your PC (which is still on home Wi-Fi).

### 2b.2 — Run the script on the Slave

```bash
# On R2-Slave (SSH via home Wi-Fi — last time)
ssh artoo@r2-slave.local

sudo bash /home/artoo/setup_slave_network.sh
```

The script asks:
- **Master hotspot SSID** (default: `R2D2_Control` — change if you customized it)
- **Password** for the hotspot (the one you set during Master setup)

```bash
sudo reboot
```

### 2b.3 — Verify after Slave reboot

```bash
# From your PC connected to the R2D2_Control hotspot (or from the Master)
ping r2-slave.local          # must respond ✓
ssh artoo@r2-slave.local     # connects without issues ✓

# On the Slave — verify assigned IP
ip addr show wlan0
# should show 192.168.4.x
```

---

## STEP 3 — Passwordless SSH: R2-Master → R2-Slave

> Both Pis are now on the same network (hotspot `R2D2_Control`).
> The Slave is reachable as `r2-slave.local` from the Master.

### 3.1 — Generate and copy SSH keys

```bash
# From R2-Master
bash /home/artoo/r2d2/scripts/setup_ssh_keys.sh
# Enter the R2-Slave password when prompted (last time)
```

Verify:
```bash
ssh artoo@r2-slave.local echo "SSH OK"
# Should print "SSH OK" without asking for a password
```

---

## STEP 4 — Initial code deployment

### 4.1 — Copy Slave code to R2-Slave

```bash
# From R2-Master — use the script (recommended)
bash /home/artoo/r2d2/scripts/deploy.sh --first-install

# Or manually:
rsync -avz --delete \
  -e "ssh -o StrictHostKeyChecking=no" \
  /home/artoo/r2d2/slave/ \
  artoo@r2-slave.local:/home/artoo/r2d2/slave/

rsync -avz \
  -e "ssh -o StrictHostKeyChecking=no" \
  /home/artoo/r2d2/shared/ \
  artoo@r2-slave.local:/home/artoo/r2d2/shared/

rsync \
  -e "ssh -o StrictHostKeyChecking=no" \
  /home/artoo/r2d2/VERSION \
  artoo@r2-slave.local:/home/artoo/r2d2/VERSION
```

### 4.2 — Verify code on R2-Slave

```bash
ssh artoo@r2-slave.local
ls /home/artoo/r2d2/slave/
# Should show: main.py  uart_listener.py  watchdog.py  version_check.py  drivers/  services/
cat /home/artoo/r2d2/VERSION
# Should show the same git hash as on R2-Master
```

---

## STEP 5 — systemd services

### 5.1 — On R2-Master

```bash
# Copy service files
sudo cp /home/artoo/r2d2/master/services/r2d2-master.service /etc/systemd/system/
sudo cp /home/artoo/r2d2/master/services/r2d2-monitor.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable and start
sudo systemctl enable r2d2-master r2d2-monitor
sudo systemctl start r2d2-master

# Check status
sudo systemctl status r2d2-master
journalctl -u r2d2-master -f   # live logs
```

### 5.2 — On R2-Slave

```bash
# Copy service files
sudo cp /home/artoo/r2d2/slave/services/r2d2-slave.service /etc/systemd/system/
sudo cp /home/artoo/r2d2/slave/services/r2d2-version.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable and start
sudo systemctl enable r2d2-version r2d2-slave
sudo systemctl start r2d2-slave

# Check status
sudo systemctl status r2d2-slave
journalctl -u r2d2-slave -f   # live logs
```

---

## STEP 6 — RP2040 Firmware

### 6.1 — Install MicroPython on the RP2040

> No software required for this step — just drag and drop a file.

1. Download MicroPython firmware for RP2040:
   https://micropython.org/download/RPI_PICO/

2. Put the RP2040 in BOOTSEL mode:
   - Hold the **BOOT** button
   - Plug in the USB cable
   - Release BOOT
   - A drive named `RPI-RP2` appears on your PC

3. Drag and drop the `.uf2` file onto that drive → the RP2040 reboots automatically with MicroPython installed ✅

### 6.2 — Copy the R2-D2 firmware

> **Thonny** (or `mpremote`) is needed from here to send code to the RP2040.
> Install Thonny: https://thonny.org (Windows/Mac/Linux)

**Via Thonny:**
1. Open Thonny → menu `Run` → `Select interpreter` → `MicroPython (Raspberry Pi Pico)`
2. Open each file from `rp2040/firmware/` and do `File` → `Save as` → `Raspberry Pi Pico`

**Via `mpremote` (command line):**
```bash
pip install mpremote

# Install the GC9A01 display driver (round screen)
mpremote connect auto mip install gc9a01

# Copy R2-D2 firmware files
cd J:/R2-D2_Build/software/rp2040/firmware
mpremote connect auto cp main.py :main.py
mpremote connect auto cp display.py :display.py
mpremote connect auto cp touch.py :touch.py
```

### 6.3 — Test the display

**Via Thonny:** open the REPL (bottom console) → the RP2040 should show the R2-D2 boot screen.

**Via `mpremote`:**
```bash
mpremote connect auto repl
# Ctrl+D for soft-reboot to see main.py start
```

---

## STEP 7 — Phase 1 Validation Tests

### 7.1 — Test UART + CRC

From R2-Master, test manually:
```bash
python3 -c "
import sys; sys.path.insert(0, '/home/artoo/r2d2')
from shared.uart_protocol import build_msg, parse_msg
print(build_msg('H', '1'))       # H:1:43\n expected
print(build_msg('M', '50'))      # M:50:72\n expected
print(parse_msg('H:1:43'))       # ('H', '1') expected
print(parse_msg('H:1:00'))       # None expected (invalid CRC)
"
```

### 7.2 — Test Watchdog

```bash
# On R2-Slave
journalctl -u r2d2-slave -f

# On R2-Master — temporarily stop the Master service
sudo systemctl stop r2d2-master

# Watch in Slave logs:
# → after 500ms: "WATCHDOG TRIGGERED"
# → restart Master: "Watchdog: heartbeat resumed"
sudo systemctl start r2d2-master
```

### 7.3 — Test Version Sync

```bash
# Simulate a version mismatch on R2-Slave
ssh artoo@r2-slave.local "echo 'aabbcc' > /home/artoo/r2d2/VERSION"

# Restart the Slave
ssh artoo@r2-slave.local "sudo systemctl restart r2d2-slave"

# Watch the logs — it should attempt a sync
ssh artoo@r2-slave.local "journalctl -u r2d2-slave -f"
```

### 7.4 — Test Teeces32

```bash
# On R2-Master
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

### 7.5 — Test Dome Button

```bash
# Verify BCM17 is wired correctly (button to GND)
python3 -c "
import RPi.GPIO as GPIO, time
GPIO.setmode(GPIO.BCM)
GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_UP)
print('Press the button...')
while True:
    print('State:', GPIO.input(17))
    time.sleep(0.1)
"
```

### 7.6 — Test RP2040 Display

Plug the RP2040 into R2-Slave (USB), then:
```bash
# On R2-Slave — send a DISP: command manually
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

### 7.7 — Test Audio (native 3.5mm jack)

```bash
# On R2-Slave
aplay /home/artoo/r2d2/slave/sounds/001.wav

# Or via Python subprocess
python3 -c "
import subprocess
subprocess.run(['aplay', '/home/artoo/r2d2/slave/sounds/001.wav'])
"
```

---

## UART Wiring Reference

```
R2-Master  BCM14 (TX, pin 8)   ──→  BCM15 (RX, pin 10)  R2-Slave
R2-Master  BCM15 (RX, pin 10)  ←──  BCM14 (TX, pin 8)   R2-Slave
R2-Master  GND   (pin 6)       ───  GND   (pin 6)        R2-Slave
```

> **UART wires pass through the slip ring.** Verify continuity with a multimeter before starting the services.
> Both R2-Master and R2-Slave use `/dev/ttyAMA0` — same port name, each on its own hardware.

---

## STEP 8 — VESC Wiring (Phase 2)

### 8.1 — USB connection

Both VESCs connect directly to R2-Slave (Pi 4B) via USB:

```
R2-Slave  USB  ──→  Left VESC   (/dev/ttyACM0)
R2-Slave  USB  ──→  Right VESC  (/dev/ttyACM1)
```

Verify ports after plugging in:
```bash
ls /dev/ttyACM*
# Should show: /dev/ttyACM0  /dev/ttyACM1
```

### 8.2 — VESC configuration (via VESC Tool)

Configure each VESC via VESC Tool (from a PC):
- **Motor Type**: FOC or BLDC depending on your motor
- **Current Limits**: match your motor spec (e.g. 30A max)
- **Direction**: reverse the right VESC if wheels spin opposite directions
- **UART Baud**: 115200

### 8.3 — USB permissions on Slave

```bash
sudo usermod -a -G dialout artoo
# SSH disconnect/reconnect required to take effect
```

---

## STEP 9 — Dome Motor Wiring (Phase 2)

### 9.1 — Motor Driver HAT (TB6612)

The dome motor is controlled directly via the Motor Driver HAT on the Slave (I2C 0x40):

```
R2-Slave  I2C SDA (GPIO2, pin 3)  ──→  Motor HAT SDA
R2-Slave  I2C SCL (GPIO3, pin 5)  ──→  Motor HAT SCL
12V Buck                           ──→  Motor HAT VIN
GND                                ──→  Motor HAT GND
Motor wires                        ──→  Motor HAT MOTORA
```

Verify I2C detection:
```bash
sudo i2cdetect -y 1
# Should show "40" at address 0x40
```

---

## STEP 10 — Body Servo Wiring (Phase 2)

### ⚠️ 10.0 — Identify your servo type BEFORE wiring

Two versions of the SG90 are sold **visually identical** under the same name.
Buying the wrong type is a very common mistake from Chinese suppliers.

**Physical test (30 seconds) — mandatory before continuing:**
Try to turn the servo shaft by hand past 180°:
- **Mechanical resistance / hard stop** → ✅ Standard SG90 0–180° → positional control
- **Rotates freely, no stop** → ⚠️ SG90 360° continuous rotation → time-based control

| Type | 1500µs pulse | 1000µs pulse | 2000µs pulse |
|------|-------------|-------------|-------------|
| SG90 standard (0–180°) | 90° (center) | 0° | 180° |
| SG90 360° CR | Stop (neutral) | Spin direction B | Spin direction A |

**If you have SG90 360° (continuous rotation):**
- The code works but uses time-based control (not direct angle)
- Neutral point varies per unit (calibrated at ~1700µs in this project)
- Calibrate via the web dashboard → **Settings → SERVO CALIBRATION**
- Plan for physical stops in the panel mechanism

**To buy the right servos:** search for "SG90 servo **180 degree standard**"
Avoid: "SG90 360°", "SG90 continuous rotation", "SG90-CR"

---

### 10.1 — PCA9685 I2C connection

```
R2-Slave  GPIO2 (SDA, pin 3)  ──→  PCA9685 SDA
R2-Slave  GPIO3 (SCL, pin 5)  ──→  PCA9685 SCL
R2-Slave  3.3V  (pin 1)       ──→  PCA9685 VCC
R2-Slave  GND   (pin 6)       ──→  PCA9685 GND
External 5V supply            ──→  PCA9685 V+ (servo power)
```

Verify I2C detection:
```bash
sudo i2cdetect -y 1
# Should show "41" at address 0x41
```

### 10.2 — Servo channel mapping

Edit `slave/drivers/body_servo_driver.py` → `SERVO_MAP` dict:
```python
SERVO_MAP = {
    'body_panel_1':   0,   # channel 0
    'body_panel_2':   1,   # channel 1
    'body_panel_3':   2,   # channel 2
    # ...
}
```

---

## STEP 11 — Enable Phase 2 Drivers

### 11.1 — On R2-Slave

Edit `slave/main.py` and uncomment the Phase 2 block:
```python
# ---- Phase 2 — Uncomment to activate ----
from slave.drivers.vesc_driver       import VescDriver
from slave.drivers.body_servo_driver import BodyServoDriver
```

And further down in `main()`:
```python
vesc  = VescDriver()
servo = BodyServoDriver()
if vesc.setup():
    uart.register_callback('M', vesc.handle_uart)
    watchdog.register_stop_callback(vesc.stop)
if servo.setup():
    uart.register_callback('SRV', servo.handle_uart)
```

### 11.2 — On R2-Master

Edit `master/main.py` and uncomment the Phase 2 block:
```python
from master.drivers.vesc_driver       import VescDriver
from master.drivers.dome_motor_driver import DomeMotorDriver
from master.drivers.body_servo_driver import BodyServoDriver
```

And in `main()`:
```python
vesc  = VescDriver(uart)
dome  = DomeMotorDriver(uart)
servo = BodyServoDriver(uart)
if vesc.setup():  reg.vesc  = vesc
if dome.setup():  reg.dome  = dome
if servo.setup(): reg.servo = servo
```

### 11.3 — Deploy and test

```bash
# From R2-Master
bash /home/artoo/r2d2/scripts/deploy.sh

# Manual propulsion test via Python
python3 -c "
import sys; sys.path.insert(0, '/home/artoo/r2d2')
from master.config.config_loader import load
from master.uart_controller import UARTController
from master.drivers.vesc_driver import VescDriver
cfg = load()
uart = UARTController(cfg)
uart.setup(); uart.start()
vesc = VescDriver(uart)
vesc.setup()
import time
vesc.drive(0.3, 0.3)   # move forward slowly
time.sleep(1)
vesc.stop()
uart.stop()
"
```

---

## STEP 12 — Sequence Scripts (Phase 3)

`.scr` files are CSV files located in `master/scripts/`.
Each line is one command. Comments start with `#`.

### 12.1 — Command format

```csv
# Example commands
sound,Happy001               # play a specific sound
sound,RANDOM,happy           # random sound from a category
dome,turn,0.5                # dome rotation (speed -1.0 to 1.0)
dome,stop                    # stop dome
dome,random,on               # enable random dome rotation
servo,body_panel_1,1.0,500   # servo: name, position (0-1), duration ms
servo,all,open               # open all servo panels
servo,all,close              # close all servo panels
motion,0.4,0.4,2000          # propulsion: left, right, duration ms
motion,stop                  # stop propulsion
teeces,random                # Teeces LEDs in random mode
teeces,leia                  # Teeces Leia mode
teeces,text,HELLO            # scrolling text on FLD
sleep,1.5                    # pause 1.5 seconds
sleep,random,2,5             # random pause between 2 and 5 seconds
```

### 12.2 — Included scripts (40 total)

**Faithful dpoulson ports (26):**
`theme` `march` `leia` `evil` `failure` `alert` `malfunction` `cantina` `r2kt` `wolfwhistle`
`dome_dance` `dome_test1` `dome_test2` `test` `flap_dome` `flap_dome_fast` `flap_dome_side`
`ripple_dome` `ripple_dome_fast` `ripple_dome_side` `slow_open_close`
`looping_sounds` `looping_sounds_quick` `body_test` `dance` `hp_twitch`

**Custom scripts (14):**
`patrol` `celebrate` `panel_test` `startup` `excited` `scared` `angry` `curious`
`party` `birthday` `disco` `message` `taunt` `scan`

### 12.3 — Create a new script

```bash
nano /home/artoo/r2d2/master/scripts/my_script.scr
```

```csv
# My custom script
sound,RANDOM,happy
sleep,1.0
dome,turn,0.3
sleep,2.0
dome,stop
teeces,random
```

---

## STEP 13 — Enable ScriptEngine (Phase 3)

Edit `master/main.py` and uncomment the Phase 3 block:
```python
from master.script_engine import ScriptEngine
```

In `main()`:
```python
engine = ScriptEngine(
    uart=uart, teeces=teeces,
    vesc=reg.vesc, dome=reg.dome, servo=reg.servo
)
reg.engine = engine
```

Test from command line:
```bash
python3 -c "
import sys; sys.path.insert(0, '/home/artoo/r2d2')
from master.script_engine import ScriptEngine
engine = ScriptEngine()   # no drivers = dry-run mode
sid = engine.run('patrol')
import time; time.sleep(10)
engine.stop(sid)
"
```

---

## STEP 14 — Flask REST API (Phase 4)

### 14.1 — Enable

Edit `master/main.py` and uncomment the Phase 4 block:
```python
from master.flask_app import create_app
```

In `main()`:
```python
app = create_app()
flask_port = cfg.getint('master', 'flask_port', fallback=5000)
flask_thread = threading.Thread(
    target=lambda: app.run(host='0.0.0.0', port=flask_port,
                           use_reloader=False, threaded=True),
    name='flask', daemon=True
)
flask_thread.start()
```

Add to `master/config/main.cfg`:
```ini
[master]
flask_port = 5000
```

### 14.2 — Available endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/status` | Full system status JSON |
| POST | `/audio/play` | Play a sound `{"sound": "Happy001"}` |
| POST | `/audio/random` | Random sound `{"category": "happy"}` |
| POST | `/audio/stop` | Stop audio |
| GET | `/audio/categories` | List categories |
| POST | `/motion/drive` | Drive `{"left": 0.5, "right": 0.5}` |
| POST | `/motion/arcade` | Arcade drive `{"throttle": 0.5, "steering": 0.0}` |
| POST | `/motion/stop` | Stop propulsion |
| POST | `/motion/dome/turn` | Dome rotation `{"speed": 0.3}` |
| POST | `/motion/dome/random` | Random dome mode `{"enabled": true}` |
| POST | `/servo/move` | Move servo `{"name": "...", "position": 0.5}` |
| POST | `/servo/open_all` | Open all panels |
| POST | `/servo/close_all` | Close all panels |
| POST | `/scripts/run` | Run a script `{"name": "patrol", "loop": false}` |
| POST | `/scripts/stop_all` | Stop all scripts |
| POST | `/teeces/random` | Random LED mode |
| POST | `/teeces/leia` | Leia mode |
| POST | `/teeces/text` | FLD text `{"text": "HELLO"}` |
| POST | `/system/reboot` | Reboot Master |
| POST | `/system/reboot_slave` | Reboot Slave via UART |

### 14.3 — Test the API

```bash
# From any device connected to the R2D2_Control hotspot
curl http://192.168.4.1:5000/status
curl -X POST http://192.168.4.1:5000/audio/random \
     -H "Content-Type: application/json" \
     -d '{"category": "happy"}'
curl -X POST http://192.168.4.1:5000/motion/drive \
     -H "Content-Type: application/json" \
     -d '{"left": 0.3, "right": 0.3}'
```

---

## STEP 15 — Web Dashboard (Phase 4)

### 15.1 — Access

Once Flask is running, open a browser (from the R2D2_Control hotspot):
```
http://192.168.4.1:5000
# or
http://r2-master.local:5000
```

### 15.2 — Dashboard panels

| Panel | Controls |
|-------|----------|
| **Status** | Heartbeat, UART, Teeces, VESC, uptime, version |
| **Audio** | Buttons per category (14 categories, 317 sounds), Stop |
| **Drive** | D-pad (click/touch), WASD/arrow keys, speed limiter |
| **Dome** | Left/Right, Center, Random mode toggle |
| **Teeces** | Random / Leia / OFF / FLD text |
| **Servos** | Open/Close individual + Open all / Close all |
| **Scripts** | Run / Loop / Stop all + running list |
| **System** | Reboot Master, Reboot Slave, Shutdown |

### 15.3 — Keyboard control (PC browser)

| Key | Action |
|-----|--------|
| `W` / `↑` | Forward |
| `S` / `↓` | Backward |
| `A` / `←` | Turn left |
| `D` / `→` | Turn right |
| Release | Auto-stop |

---

## STEP 16 — Phase 4 Validation Tests

### 16.1 — API status test

```bash
curl http://r2-master.local:5000/status
# Should return JSON with heartbeat_ok, version, uptime, etc.
```

### 16.2 — Audio via API

```bash
curl -X POST http://r2-master.local:5000/audio/random \
     -H "Content-Type: application/json" \
     -d '{"category": "happy"}'
# Should play a sound on the Slave and return {"status": "ok"}
```

### 16.3 — Script via API

```bash
# Run the celebrate script
curl -X POST http://r2-master.local:5000/scripts/run \
     -H "Content-Type: application/json" \
     -d '{"name": "celebrate"}'

# Check it's running
curl http://r2-master.local:5000/scripts/running

# Stop it
curl -X POST http://r2-master.local:5000/scripts/stop_all
```

### 16.4 — Mobile dashboard test

From a smartphone connected to the `R2D2_Control` hotspot:
1. Open `http://192.168.4.1:5000`
2. Verify status indicators are green
3. Test audio buttons
4. Test the D-pad (touch)

---

## After every code change

```bash
# From R2-Master
cd /home/artoo/r2d2
git pull                    # pull latest changes
bash scripts/deploy.sh      # rsync to Slave + reboot Slave
```

Or use the **physical dome button**:
- Short press (< 2s): git pull + rsync + reboot Slave
- Long press (> 2s): rollback to previous version
- Double press: display current version on Teeces32

---

## Useful log commands

```bash
# R2-Master
journalctl -u r2d2-master -f

# R2-Slave (via SSH)
ssh artoo@r2-slave.local "journalctl -u r2d2-slave -f"

# Both logs simultaneously (from R2-Master)
journalctl -u r2d2-master -f &
ssh artoo@r2-slave.local "journalctl -u r2d2-slave -f"
```

---

*For electronics diagrams and wiring reference, see [ELECTRONICS.md](ELECTRONICS.md)*
