#!/bin/bash
# ============================================================
#   █████╗  ██████╗ ███████╗
#  ██╔══██╗██╔═══██╗██╔════╝
#  ███████║██║   ██║███████╗
#  ██╔══██║██║   ██║╚════██║
#  ██║  ██║╚██████╔╝███████║
#  ╚═╝  ╚═╝ ╚═════╝ ╚══════╝
#
#  AstromechOS — Open control platform for astromech builders
# ============================================================
#  Copyright (C) 2026 RickDnamps
#  https://github.com/RickDnamps/AstromechOS
#
#  This file is part of AstromechOS.
#
#  AstromechOS is free software: you can redistribute it
#  and/or modify it under the terms of the GNU General
#  Public License as published by the Free Software
#  Foundation, either version 2 of the License, or
#  (at your option) any later version.
#
#  AstromechOS is distributed in the hope that it will be
#  useful, but WITHOUT ANY WARRANTY; without even the implied
#  warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
#  PURPOSE. See the GNU General Public License for details.
#
#  You should have received a copy of the GNU GPL along with
#  AstromechOS. If not, see <https://www.gnu.org/licenses/>.
# ============================================================
# update.sh — Full AstromechOS update: git pull + rsync Slave + restart everything
# Usage: bash scripts/update.sh
# Run on the Master (r2-master.local)
#
# This script:
#   1. Git pull (if wlan1 available)
#   2. Check Slave connectivity
#   3. Rsync slave/ + shared/ + scripts/ + rp2040/ to the Slave
#   4. Restart the Slave service
#   5. Restart the Master service (app + motion watchdogs included)
#   6. Verify that services are active

REPO="$(cd "$(dirname "$0")/.." && pwd)"
SLAVE=artoo@r2-slave.local
SSH="ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10"
VERSION_FILE=$REPO/VERSION
ERRORS=0

# ──────────────────────────────────────────────
# Helpers affichage
# ──────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; ERRORS=$((ERRORS+1)); }
step() { echo -e "\n${CYAN}[$1]${NC} $2"; }

echo -e "${CYAN}"
echo "   █████╗  ██████╗ ███████╗"
echo "  ██╔══██╗██╔═══██╗██╔════╝"
echo "  ███████║██║   ██║███████╗"
echo "  ██╔══██║██║   ██║╚════██║"
echo "  ██║  ██║╚██████╔╝███████║"
echo "  ╚═╝  ╚═╝ ╚═════╝ ╚══════╝"
echo -e "         UPDATE SYSTEM${NC}"
echo "  ────────────────────────────────────"

# ──────────────────────────────────────────────
# 0. Backup custom sequences avant git pull
# ──────────────────────────────────────────────
SEQUENCES_DIR="$REPO/master/sequences"
SEQUENCES_BACKUP="/home/artoo/sequences_backup"
step "0/7" "Backup custom sequences"
mkdir -p "$SEQUENCES_BACKUP"
if rsync -a "$SEQUENCES_DIR/" "$SEQUENCES_BACKUP/" 2>/dev/null; then
    ok "Sequences backed up → $SEQUENCES_BACKUP"
else
    warn "Sequence backup failed — directory missing?"
fi

# ──────────────────────────────────────────────
# 0b. Backup user-customised servo angles
# ──────────────────────────────────────────────
# These two files contain per-robot calibration — open/close angles,
# speed, and the user's custom labels (arm names, panel names, etc.).
# Both files USED to be tracked in git, so a 'git pull' could restore
# them to the default labels and wipe a user's customisations (incident
# 2026-05-14: git reset --hard during repo recovery wiped Arm1/Arm2
# labels). They're now untracked, but we still backup as a safety net
# in case anything else (rsync --delete, a future regression) overwrites
# them. Restored AFTER git pull below.
ANGLES_BACKUP="/home/artoo/angles_backup"
step "0b/7" "Backup servo angle calibrations"
mkdir -p "$ANGLES_BACKUP"
if [ -f "$REPO/master/config/dome_angles.json" ]; then
    cp -p "$REPO/master/config/dome_angles.json" "$ANGLES_BACKUP/dome_angles.json"
fi
if [ -f "$REPO/slave/config/servo_angles.json" ]; then
    cp -p "$REPO/slave/config/servo_angles.json" "$ANGLES_BACKUP/servo_angles.json"
fi
ok "Angle calibrations backed up → $ANGLES_BACKUP"

# ──────────────────────────────────────────────
# 1. Git pull
# ──────────────────────────────────────────────
step "1/7" "Git pull"
if ip addr show wlan1 2>/dev/null | grep -q "inet "; then
    cd "$REPO"
    OUTPUT=$(git pull --ff-only 2>&1)
    if echo "$OUTPUT" | grep -q "error\|fatal"; then
        fail "git pull failed: $OUTPUT"
    else
        # Always update the VERSION file with the real HEAD
        git rev-parse --short HEAD > "$VERSION_FILE"
        if echo "$OUTPUT" | grep -q "Already up to date"; then
            ok "Already up to date — $(cat $VERSION_FILE)"
        else
            ok "Updated → version: $(cat $VERSION_FILE)"
        fi
    fi
else
    warn "wlan1 not available — git pull skipped, using local version"
fi

# ──────────────────────────────────────────────
# 1b. Restore custom sequences after git pull
# ──────────────────────────────────────────────
step "1b/7" "Restore custom sequences"
if [ -d "$SEQUENCES_BACKUP" ]; then
    # --ignore-existing: skip files that already exist in dest (git-updated built-ins stay)
    # git pull --ff-only never deletes untracked files, so custom sequences are always safe
    # This restore is a safety net in case git ever adds a file that shadows a custom one
    if rsync -a --ignore-existing "$SEQUENCES_BACKUP/" "$SEQUENCES_DIR/" 2>/dev/null; then
        ok "Custom sequences restored"
    else
        warn "Sequence restore failed"
    fi
else
    ok "No backup to restore"
fi

# Restore angle calibrations only if the live files are MISSING (git was
# never supposed to ship them, but a reset --hard from a stale checkout
# can still wipe them). NEVER overwrite the live files — the operator's
# in-UI edits between deploys must win over the backup.
if [ -d "$ANGLES_BACKUP" ]; then
    if [ -f "$ANGLES_BACKUP/dome_angles.json" ] && [ ! -f "$REPO/master/config/dome_angles.json" ]; then
        cp -p "$ANGLES_BACKUP/dome_angles.json" "$REPO/master/config/dome_angles.json"
        warn "Restored dome_angles.json from backup (was missing)"
    fi
    if [ -f "$ANGLES_BACKUP/servo_angles.json" ] && [ ! -f "$REPO/slave/config/servo_angles.json" ]; then
        cp -p "$ANGLES_BACKUP/servo_angles.json" "$REPO/slave/config/servo_angles.json"
        warn "Restored servo_angles.json from backup (was missing)"
    fi
fi

# ──────────────────────────────────────────────
# 2. Check the Slave
# ──────────────────────────────────────────────
step "2/7" "Slave connection"
if ! $SSH $SLAVE "echo ok" > /dev/null 2>&1; then
    fail "Slave unreachable — check the Wi-Fi hotspot"
    echo -e "\n${RED}Stopping — Slave required to continue.${NC}"
    exit 1
fi
ok "Slave reachable ($SLAVE)"

# ──────────────────────────────────────────────
# 3. Rsync vers le Slave
# ──────────────────────────────────────────────
step "3/7" "Sync code vers Slave"

rsync -az --delete \
    -e "$SSH" \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='sounds/*.mp3' \
    --exclude='vendor/' \
    "$REPO/slave/" "$SLAVE:$REPO/slave/" 2>&1 \
    && ok "slave/ synced" || fail "rsync slave/ failed"

rsync -az \
    -e "$SSH" \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    "$REPO/shared/" "$SLAVE:$REPO/shared/" 2>&1 \
    && ok "shared/ synced" || fail "rsync shared/ failed"

rsync -az \
    -e "$SSH" \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    "$REPO/scripts/" "$SLAVE:$REPO/scripts/" 2>&1 \
    && ok "scripts/ synced" || fail "rsync scripts/ failed"

rsync -az \
    -e "$SSH" \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    "$REPO/rp2040/" "$SLAVE:$REPO/rp2040/" 2>&1 \
    && ok "rp2040/ synced" || fail "rsync rp2040/ failed"

rsync -az -e "$SSH" "$VERSION_FILE" "$SLAVE:$VERSION_FILE" 2>/dev/null
ok "VERSION synced → $(cat $VERSION_FILE 2>/dev/null || echo 'unknown')"

# Install the camera autodetect script on the Master
CAM_SCRIPT="$REPO/scripts/camera-start.sh"
if [ -f "$CAM_SCRIPT" ]; then
    sudo cp "$CAM_SCRIPT" /usr/local/bin/astromech-camera-start.sh \
        && sudo chmod +x /usr/local/bin/astromech-camera-start.sh \
        && ok "Camera autodetect script installed" \
        || warn "Camera script install failed"
fi

# Install/update the camera service file (Restart=always + watchdog script)
CAM_SVC="$REPO/master/services/astromech-camera.service"
if [ -f "$CAM_SVC" ]; then
    sudo tee /etc/systemd/system/astromech-camera.service > /dev/null < "$CAM_SVC" \
        && sudo systemctl daemon-reload \
        && ok "Camera service file updated" \
        || warn "Camera service file install failed"
fi

# Install the service file on the Slave (PYTHONPATH + config up to date)
SERVICE_SRC="$REPO/slave/services/astromech-slave.service"
if [ -f "$SERVICE_SRC" ]; then
    $SSH $SLAVE "sudo tee /etc/systemd/system/astromech-slave.service > /dev/null" < "$SERVICE_SRC" \
        && $SSH $SLAVE "sudo systemctl daemon-reload" \
        && ok "Service file installed (PYTHONPATH OK)" \
        || warn "Service file: sudo install failed — check sudoers"
fi

# ──────────────────────────────────────────────
# 4. Restart the Slave
# ──────────────────────────────────────────────
step "4/7" "Restarting Slave"
if $SSH $SLAVE "sudo systemctl restart astromech-slave.service" 2>/dev/null; then
    sleep 4
    SLAVE_STATUS=$($SSH $SLAVE "systemctl is-active astromech-slave.service" 2>/dev/null)
    if [ "$SLAVE_STATUS" = "active" ]; then
        ok "astromech-slave active"
    else
        # Service failed → full reboot
        warn "astromech-slave failed ($SLAVE_STATUS) — rebooting Slave..."
        $SSH $SLAVE "sudo reboot" 2>/dev/null && ok "Slave rebooting" || fail "Slave reboot failed"
    fi
else
    warn "systemctl failed — rebooting Slave..."
    $SSH $SLAVE "sudo reboot" 2>/dev/null && ok "Slave rebooting" || fail "Slave reboot failed"
fi

# ──────────────────────────────────────────────
# 5. Restart the Master
# ──────────────────────────────────────────────
step "5/7" "Restarting Master"

VERSION=$(cat "$VERSION_FILE" 2>/dev/null || echo "unknown")

echo ""
echo "  ────────────────────────────────────"
if [ $ERRORS -eq 0 ]; then
    echo -e "  ${GREEN}✓ Sync OK — version: ${VERSION}${NC}"
else
    echo -e "  ${YELLOW}⚠ Sync with $ERRORS error(s) — version: ${VERSION}${NC}"
fi
echo "  ────────────────────────────────────"
echo ""
echo -e "  ${YELLOW}→ Restarting Master in 3 seconds...${NC}"
echo -e "  ${YELLOW}  (AppWatchdog + MotionWatchdog + SafeStop will be restarted)${NC}"
sleep 3

# Restart Master — astromech-monitor.service if present, otherwise just astromech-master
sudo systemctl restart astromech-master.service astromech-monitor.service 2>/dev/null || \
    sudo systemctl restart astromech-master.service 2>/dev/null || \
    { fail "systemctl not available — manual restart required"; exit 1; }

# ──────────────────────────────────────────────
# 6. Post-startup verification
# ──────────────────────────────────────────────
step "6/7" "Verifying services"
sleep 3   # give the Master time to start Flask

MASTER_STATUS=$(systemctl is-active astromech-master.service 2>/dev/null)
if [ "$MASTER_STATUS" = "active" ]; then
    ok "astromech-master active"
else
    fail "astromech-master status: $MASTER_STATUS"
fi

SLAVE_STATUS=$($SSH $SLAVE "systemctl is-active astromech-slave.service" 2>/dev/null)
if [ "$SLAVE_STATUS" = "active" ]; then
    ok "astromech-slave active"
elif [ -z "$SLAVE_STATUS" ]; then
    warn "astromech-slave — cannot verify (SSH timeout)"
else
    fail "astromech-slave status: $SLAVE_STATUS"
fi

# Flask API check (quick heartbeat)
if curl -sf --max-time 3 http://localhost:5000/status > /dev/null 2>&1; then
    ok "Flask API responding on :5000"
else
    warn "Flask API not yet available (normal on slow boot)"
fi

# ──────────────────────────────────────────────
# Final summary
# ──────────────────────────────────────────────
echo ""
echo "  ════════════════════════════════════"
if [ $ERRORS -eq 0 ]; then
    echo -e "  ${GREEN}✓ AstromechOS operational — version: ${VERSION}${NC}"
else
    echo -e "  ${YELLOW}⚠ Started with $ERRORS error(s) — version: ${VERSION}${NC}"
    echo -e "  ${YELLOW}  Check: sudo journalctl -u astromech-master -n 30${NC}"
fi
echo "  ════════════════════════════════════"
echo ""
