#!/bin/bash
# ============================================================================
# scripts/clean_for_imager.sh — Industrial pre-imaging cleanup for AstromechOS
# ============================================================================
# Prepares a running Pi for cloning into a distributable .img:
#   1. Stops every astromech-* service cleanly.
#   2. Removes the security snapshot directory ($TARGET_HOME/astromech_security_snapshot/).
#   3. Purges pip / npm / generic .cache directories for the install user + root.
#   4. Empties /tmp/ (mindepth 1 so the tmpfs mount itself is preserved).
#   5. Removes node_modules + dist/build inside the AstromechOS repo ONLY
#      (NEVER traverses the whole $HOME to avoid nuking unrelated work).
#   6. Vacuums systemd journal + truncates active /var/log files (the rotation
#      pattern preserves file existence so daemons keep writing after reboot —
#      we never `rm -rf /var/log/*` which breaks logrotate and live writers).
#   7. Erases shell history for the install user + root (.bash_history,
#      .zsh_history, .python_history).
#   8. apt-get clean + autoremove (apt cache + orphan packages).
#   9. Truncates /etc/machine-id and removes /var/lib/dbus/machine-id so the
#      next boot regenerates a unique ID for every cloned card (critical for
#      fleet deploys — otherwise every Pi has the same DHCP / NetworkManager
#      / systemd identity).
#  10. Reports disk usage before/after the cleanup.
#
# Safety: REFUSES TO RUN unless ALL of the following are true:
#   - Invoked as root (EUID 0).
#   - /proc/device-tree/model says "Raspberry Pi".
#   - The AstromechOS repo is present (i.e. this is an AstromechOS Pi,
#     not someone else's Pi that we'd brick by purging logs).
#   - The operator passes --yes OR confirms an interactive prompt.
#
# Usage:
#   sudo /usr/local/bin/clean_for_imager.sh           (interactive confirm)
#   sudo /usr/local/bin/clean_for_imager.sh --yes     (CI / scripted)
#   sudo scripts/clean_for_imager.sh --install         (copy self to
#                                                       /usr/local/bin/
#                                                       + chmod 0755)
# ============================================================================

set -u

# ─── Pretty output ──────────────────────────────────────────────────────────
RED=$'\033[91m';  YELLOW=$'\033[93m'; GREEN=$'\033[92m'; CYAN=$'\033[96m'
GRAY=$'\033[90m'; BOLD=$'\033[1m';    RESET=$'\033[0m'

step() { printf "${CYAN}${BOLD}▶ %s${RESET}\n" "$*"; }
ok()   { printf "  ${GREEN}✓${RESET} %s\n" "$*"; }
warn() { printf "  ${YELLOW}⚠${RESET} %s\n" "$*"; }
err()  { printf "${RED}${BOLD}✗ %s${RESET}\n" "$*" >&2; }

# ─── --install mode ─────────────────────────────────────────────────────────
SELF=$(readlink -f "$0" 2>/dev/null || realpath "$0" 2>/dev/null || echo "$0")
DEST=/usr/local/bin/clean_for_imager.sh
if [ "${1:-}" = "--install" ]; then
    if [ "$EUID" -ne 0 ]; then
        err "--install requires root (sudo)"
        exit 1
    fi
    install -m 0755 -o root -g root "$SELF" "$DEST"
    ok "Installed to $DEST"
    ok "Run:  sudo clean_for_imager.sh"
    exit 0
fi

# ─── Hard safety guards ─────────────────────────────────────────────────────
if [ "$EUID" -ne 0 ]; then
    err "Must run as root (sudo)."
    exit 1
fi

MODEL=$(cat /proc/device-tree/model 2>/dev/null | tr -d '\0' || true)
case "$MODEL" in
    *"Raspberry Pi"*) : ;;
    *)
        err "This script only runs on a Raspberry Pi (model='$MODEL'). Aborting."
        exit 1
        ;;
esac

# Auto-detect the AstromechOS repo path (any user, not just artoo).
REPO=""
TARGET_USER=""
TARGET_HOME=""
for CAND in /home/*/astromechos; do
    if [ -d "$CAND/master" ] || [ -d "$CAND/slave" ] || [ -d "$CAND/.git" ]; then
        REPO="$CAND"
        TARGET_HOME=$(dirname "$CAND")
        TARGET_USER=$(basename "$TARGET_HOME")
        break
    fi
done
if [ -z "$REPO" ] || [ -z "$TARGET_USER" ]; then
    err "AstromechOS repo not found under /home/*/astromechos — this doesn't look like an AstromechOS Pi. Aborting."
    exit 1
fi
if ! id "$TARGET_USER" >/dev/null 2>&1; then
    err "Detected user '$TARGET_USER' doesn't exist. Aborting."
    exit 1
fi

# Confirmation gate.
YES=false
for arg in "$@"; do
    [ "$arg" = "--yes" ] && YES=true
done
if [ "$YES" != true ]; then
    printf "${YELLOW}${BOLD}This will purge logs, caches, history, machine-id, and stop every${RESET}\n"
    printf "${YELLOW}${BOLD}astromech-* service. It is DESTRUCTIVE and intended for pre-imaging.${RESET}\n"
    printf "${YELLOW}Target user : ${BOLD}%s${RESET}${YELLOW}    Repo : ${BOLD}%s${RESET}\n" "$TARGET_USER" "$REPO"
    printf "${YELLOW}Continue?${RESET} (type ${BOLD}yes${RESET} to confirm) : "
    read -r answer
    if [ "$answer" != "yes" ]; then
        err "Aborted by operator."
        exit 1
    fi
fi

# ─── Before snapshot ────────────────────────────────────────────────────────
printf "\n${BOLD}${CYAN}╔════════════════════════════════════════════════════════════════════╗${RESET}\n"
printf "${BOLD}${CYAN}║         AstromechOS pre-imager cleanup — STARTING                ║${RESET}\n"
printf "${BOLD}${CYAN}╚════════════════════════════════════════════════════════════════════╝${RESET}\n"
printf "${GRAY}Target user : %s\nTarget home : %s\nRepo path   : %s${RESET}\n\n" \
       "$TARGET_USER" "$TARGET_HOME" "$REPO"

BEFORE_DF=$(df -h / | awk 'NR==2 {print $3 " used, " $4 " free (" $5 ")"}')
BEFORE_USED_KB=$(df -k / | awk 'NR==2 {print $3}')

# ─── 1. Stop astromech-* services ───────────────────────────────────────────
step "1/9  Stopping astromech-* services"
mapfile -t SVCS < <(systemctl list-unit-files 'astromech-*.service' --no-pager --plain 2>/dev/null | awk 'NR>1 && $1 ~ /\.service$/ {print $1}')
if [ ${#SVCS[@]} -eq 0 ]; then
    warn "No astromech-*.service units installed"
else
    for s in "${SVCS[@]}"; do
        if systemctl stop "$s" 2>/dev/null; then
            ok "Stopped $s"
        else
            warn "Could not stop $s (probably already inactive)"
        fi
    done
fi

# ─── 2. Operator-only safety snapshots in TARGET_HOME ───────────────────────
step "2/9  Removing operator safety snapshots"
# 2a — original astromech_security_snapshot dir (created by the early
# security work in chantier 2026-05-26).
SNAPSHOT="$TARGET_HOME/astromech_security_snapshot"
if [ -d "$SNAPSHOT" ]; then
    rm -rf -- "$SNAPSHOT" && ok "Removed $SNAPSHOT" || warn "Failed to remove $SNAPSHOT"
else
    ok "No security snapshot at $SNAPSHOT (already clean)"
fi
# 2b — orphan snapshots from completed chantiers. Each pattern below
# is a known one-shot directory the operator was warned about during
# its chantier; once that chantier ships the snapshot is operator
# state with no value on a distributable image. find -maxdepth 1
# bounds the sweep to TARGET_HOME itself — never recurses.
declare -a ORPHAN_PATTERNS=(
    'migration_backup_*'            # seed-working chantier-a (2026-05-21)
    'legacy_*_decommissioned_*'     # legacy .scr→.chor migration (2026-05-22)
    'angles_backup'                 # pre-rotation manual backup (early days)
)
ORPHAN_REMOVED=0
for pat in "${ORPHAN_PATTERNS[@]}"; do
    while IFS= read -r d; do
        rm -rf -- "$d" 2>/dev/null && \
            { ORPHAN_REMOVED=$((ORPHAN_REMOVED + 1)); ok "Removed $d"; } || \
            warn "Could not remove $d"
    done < <(find "$TARGET_HOME" -maxdepth 1 -type d -name "$pat" 2>/dev/null)
done
if [ "$ORPHAN_REMOVED" -eq 0 ]; then
    ok "No orphan chantier snapshots in $TARGET_HOME"
fi

# ─── 3. Caches (pip, npm, generic .cache) ───────────────────────────────────
step "3/9  Purging caches (pip / npm / .cache)"
# pip cache for the install user
if sudo -u "$TARGET_USER" python3 -m pip cache purge >/dev/null 2>&1; then
    ok "pip cache purged for $TARGET_USER"
else
    warn "pip cache purge failed for $TARGET_USER (non-fatal)"
fi
# npm cache if npm exists
if command -v npm >/dev/null 2>&1; then
    if sudo -u "$TARGET_USER" npm cache clean --force >/dev/null 2>&1; then
        ok "npm cache cleaned for $TARGET_USER"
    fi
fi
# Generic .cache directories — bounded to KNOWN paths only
for d in "$TARGET_HOME/.cache" /root/.cache; do
    if [ -d "$d" ]; then
        rm -rf -- "$d" 2>/dev/null && ok "Removed $d" || warn "Could not remove $d"
    fi
done

# ─── 4. /tmp/ ──────────────────────────────────────────────────────────────
step "4/9  Emptying /tmp/"
# mindepth 1 preserves the /tmp mount itself. Errors silenced for files held
# open by daemons (those persist until the next reboot, which is fine).
find /tmp -mindepth 1 -maxdepth 1 -exec rm -rf -- {} \; 2>/dev/null || true
ok "/tmp/ emptied"

# ─── 5. Repo-scoped artefacts (node_modules + dist/build + config rotation backups) ──
step "5/9  Removing repo-scoped artefacts (node_modules, builds, .bak/.broken siblings)"
declare -a NODE_CANDS=(
    "$REPO/android/node_modules"
    "$REPO/android/build"
    "$REPO/android/app/build"
    "$REPO/android/.gradle"
    "$REPO/tools/node_modules"
    "$REPO/.tmp"
)
for d in "${NODE_CANDS[@]}"; do
    if [ -d "$d" ]; then
        rm -rf -- "$d" && ok "Removed $d" || warn "Could not remove $d"
    fi
done

# Config rotation backups — *.bak[N] siblings produced by the runtime
# (servo_bp _rotate, settings_bp write_cfg_atomic, shortcuts_bp etc.)
# alongside the working files. For a production-ready image these are
# stale operator state from THIS particular Pi and add no value.
# Quarantine files (*.broken-<ts>) from corruption recovery — same logic.
# Bounded to the two known config dirs to avoid sweeping unrelated paths.
CONFIG_BAK_REMOVED=0
for dir in "$REPO/master/config" "$REPO/slave/config"; do
    [ -d "$dir" ] || continue
    while IFS= read -r f; do
        rm -f -- "$f" 2>/dev/null && CONFIG_BAK_REMOVED=$((CONFIG_BAK_REMOVED + 1))
    done < <(find "$dir" -maxdepth 1 -type f \
                 \( -regex '.*\.bak[0-9]+$' -o -name '*.broken-*' \) 2>/dev/null)
done
ok "Removed $CONFIG_BAK_REMOVED config rotation/quarantine backup(s)"

# ─── 6. System logs — vacuum + truncate (NEVER rm -rf /var/log/*) ──────────
step "6/9  Vacuuming journal + truncating /var/log files"
# Aggressive journal vacuum — preserves /var/log/journal/* layout but drops content.
if command -v journalctl >/dev/null 2>&1; then
    journalctl --rotate >/dev/null 2>&1 || true
    journalctl --vacuum-time=1s >/dev/null 2>&1 || true
    ok "systemd journal vacuumed"
fi
# Active log files: truncate (keep file existence so daemons writing via
# fd never break). Rotated/archived files: delete entirely.
TRUNCATED=0
DELETED=0
while IFS= read -r f; do
    truncate -s 0 "$f" 2>/dev/null && TRUNCATED=$((TRUNCATED + 1))
done < <(find /var/log -type f \( -name "*.log" -o -name "syslog" -o -name "kern.log" -o -name "auth.log" -o -name "messages" -o -name "daemon.log" -o -name "btmp" -o -name "wtmp" -o -name "lastlog" \) 2>/dev/null)
while IFS= read -r f; do
    rm -f -- "$f" 2>/dev/null && DELETED=$((DELETED + 1))
done < <(find /var/log -type f \( -name "*.gz" -o -name "*.[0-9]" -o -name "*.[0-9].gz" -o -name "*.old" \) 2>/dev/null)
ok "Truncated $TRUNCATED active log file(s), deleted $DELETED archived log file(s)"

# ─── 7. Shell history ──────────────────────────────────────────────────────
step "7/9  Erasing shell history"
for h in \
    "$TARGET_HOME/.bash_history" \
    "$TARGET_HOME/.zsh_history" \
    "$TARGET_HOME/.python_history" \
    "$TARGET_HOME/.lesshst" \
    "$TARGET_HOME/.viminfo" \
    /root/.bash_history \
    /root/.zsh_history \
    /root/.python_history; do
    if [ -f "$h" ]; then
        truncate -s 0 "$h" 2>/dev/null && ok "Cleared $h"
    fi
done
# In-memory bash history (this very session).
history -c 2>/dev/null || true

# ─── 8. apt clean + autoremove ─────────────────────────────────────────────
step "8/9  apt-get clean + autoremove (reclaim package cache)"
if command -v apt-get >/dev/null 2>&1; then
    apt-get clean >/dev/null 2>&1 && ok "apt-get clean"
    apt-get autoremove --purge -y >/dev/null 2>&1 && ok "apt-get autoremove --purge"
else
    warn "apt-get not available (skip)"
fi

# ─── 9. machine-id reset for unique-per-clone identity ─────────────────────
step "9/9  Resetting machine-id (next boot regenerates)"
# DO NOT delete these files — many tools fail on absent paths. Truncate +
# the empty value, then systemd-machine-id-setup recreates on next boot.
if [ -f /etc/machine-id ]; then
    : > /etc/machine-id && ok "Truncated /etc/machine-id"
fi
if [ -f /var/lib/dbus/machine-id ]; then
    rm -f /var/lib/dbus/machine-id && ok "Removed /var/lib/dbus/machine-id"
fi
# Bash history file removed from above + ensure exec bit. SSH host keys are
# INTENTIONALLY preserved — fleet deploys regenerate via firstboot if needed
# (separate workflow). Removing them here would break the next normal boot's
# sshd start in the common single-Pi imaging case.

# ─── Sync to commit changes before the next dd ─────────────────────────────
sync

# ─── After snapshot + report ───────────────────────────────────────────────
AFTER_DF=$(df -h / | awk 'NR==2 {print $3 " used, " $4 " free (" $5 ")"}')
AFTER_USED_KB=$(df -k / | awk 'NR==2 {print $3}')
RECLAIMED_KB=$(( BEFORE_USED_KB - AFTER_USED_KB ))
RECLAIMED_MB=$(( RECLAIMED_KB / 1024 ))

printf "\n${BOLD}${CYAN}╔════════════════════════════════════════════════════════════════════╗${RESET}\n"
printf "${BOLD}${CYAN}║                       CLEANUP COMPLETE                           ║${RESET}\n"
printf "${BOLD}${CYAN}╚════════════════════════════════════════════════════════════════════╝${RESET}\n"
printf "${BOLD}Disk usage${RESET}\n"
printf "  Before  : %s\n" "$BEFORE_DF"
printf "  After   : %s\n" "$AFTER_DF"
if [ "$RECLAIMED_MB" -gt 0 ]; then
    printf "  ${GREEN}Reclaimed${RESET} : ~%d MB\n" "$RECLAIMED_MB"
else
    printf "  ${GRAY}Reclaimed${RESET} : %d KB\n" "$RECLAIMED_KB"
fi
printf "\n${YELLOW}${BOLD}Next steps for imaging:${RESET}\n"
printf "  1. ${BOLD}sudo shutdown now${RESET}\n"
printf "  2. Pull the SD card and image it from another machine:\n"
printf "     ${GRAY}sudo dd if=/dev/sdX of=astromechos.img bs=4M status=progress${RESET}\n"
printf "  3. Optionally shrink the image with ${BOLD}pishrink${RESET}.\n\n"

exit 0
