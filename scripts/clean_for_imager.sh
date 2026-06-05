#!/bin/bash
# ============================================================================
# scripts/clean_for_imager.sh — Universal pre-imaging cleanup for AstromechOS
# ============================================================================
# Identical script on Master and Slave. Auto-detects role via `hostname` and
# applies:
#
#   A) Whitelist sweep in /home/<install-user>/
#      Keep      : astromechos/, angles_backup/, all hidden entries (.*)
#      Delete    : everything else at the TOP level of the home dir
#
#   B) System cleanup (logs, caches, history, apt, machine-id)
#
#   C) Final  sync && echo 3 > /proc/sys/vm/drop_caches
#
# The home-dir sweep uses the shell glob `*` which by default does NOT match
# dotfiles — hidden state (.ssh, .bash_history, .config, …) is therefore
# preserved without an explicit pattern.
#
# Usage:
#   sudo /usr/local/bin/clean_for_imager.sh             (interactive confirm)
#   sudo /usr/local/bin/clean_for_imager.sh --yes       (CI / scripted)
#   sudo /usr/local/bin/clean_for_imager.sh --dry-run   (simulate, no writes)
#   sudo scripts/clean_for_imager.sh --install          (copy self to
#                                                        /usr/local/bin/,
#                                                        chmod 0755 root:root)
#
# Safety: REFUSES TO RUN unless ALL of the following are true:
#   - Invoked as root (EUID 0).
#   - /proc/device-tree/model says "Raspberry Pi".
#   - The AstromechOS repo is present under /home/*/astromechos.
#   - Operator passes --yes OR --dry-run OR types `y` at the prompt.
# ============================================================================

set -u

# ─── Pretty output ──────────────────────────────────────────────────────────
RED=$'\033[91m';  YELLOW=$'\033[93m'; GREEN=$'\033[92m'; CYAN=$'\033[96m'
GRAY=$'\033[90m'; BOLD=$'\033[1m';    RESET=$'\033[0m'; WHITE=$'\033[97m'

step()  { printf "${CYAN}${BOLD}▶ %s${RESET}\n" "$*"; }
ok()    { printf "  ${GREEN}✓${RESET} %s\n" "$*"; }
warn()  { printf "  ${YELLOW}⚠${RESET} %s\n" "$*"; }
err()   { printf "${RED}${BOLD}✗ %s${RESET}\n" "$*" >&2; }
dryln() { printf "  ${GRAY}[dry-run]${RESET} %s\n" "$*"; }

# ─── --install mode ─────────────────────────────────────────────────────────
SELF=$(readlink -f "$0" 2>/dev/null || realpath "$0" 2>/dev/null || echo "$0")
DEST=/usr/local/bin/clean_for_imager.sh
if [ "${1:-}" = "--install" ]; then
    if [ "$EUID" -ne 0 ]; then
        err "--install requires root (sudo)"
        exit 1
    fi
    install -m 0755 -o root -g root "$SELF" "$DEST"
    ok "Installed to $DEST (mode 0755 root:root)"
    ok "Run:  sudo $DEST --dry-run   # preview"
    ok "      sudo $DEST              # interactive"
    ok "      sudo $DEST --yes        # scripted"
    exit 0
fi

# ─── CLI flags ──────────────────────────────────────────────────────────────
DRY_RUN=false
YES=false
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=true ;;
        --yes)     YES=true ;;
        --help|-h)
            sed -n '2,30p' "$0"
            exit 0
            ;;
        *) ;;
    esac
done

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

# AstromechOS repo + install-user autodetect.
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

# ─── Role identification (hostname-based) ───────────────────────────────────
# Hostname is the primary signal; installed services are the fallback when
# the hostname doesn't include master/slave (fresh imager, custom rename).
HOSTNAME_RAW=$(hostname 2>/dev/null || echo "unknown")
case "$HOSTNAME_RAW" in
    *master*|astromech-m*|r2-master|r2-m*) ROLE="Master" ;;
    *slave*|astromech-s*|r2-slave|r2-s*)   ROLE="Slave"  ;;
    *)
        if systemctl list-unit-files astromech-master.service >/dev/null 2>&1; then
            ROLE="Master"
        elif systemctl list-unit-files astromech-slave.service >/dev/null 2>&1; then
            ROLE="Slave"
        else
            ROLE="Unknown"
        fi
        ;;
esac

# ─── Header banner ──────────────────────────────────────────────────────────
printf "\n${BOLD}${CYAN}╔════════════════════════════════════════════════════════════════════╗${RESET}\n"
printf "${BOLD}${CYAN}║         AstromechOS pre-imager cleanup — STARTING                ║${RESET}\n"
printf "${BOLD}${CYAN}╚════════════════════════════════════════════════════════════════════╝${RESET}\n"
printf "${BOLD}${WHITE}Nettoyage lancé sur ${HOSTNAME_RAW} : ${ROLE} identifié${RESET}\n"
if [ "$DRY_RUN" = true ]; then
    printf "${YELLOW}${BOLD}*** DRY-RUN MODE — no destructive action will be taken ***${RESET}\n"
fi
printf "${GRAY}Target user : %s\nTarget home : %s\nRepo path   : %s${RESET}\n\n" \
       "$TARGET_USER" "$TARGET_HOME" "$REPO"

# ─── Whitelist scan: build deletion list before asking for confirmation ────
step "0/9  Scanning $TARGET_HOME for non-whitelisted entries"
declare -a HOME_WHITELIST=( 'astromechos' 'angles_backup' )
declare -a DELETION_TARGETS=()
declare -a KEPT_TARGETS=()
shopt -s nullglob
for entry in "$TARGET_HOME"/*; do
    name=$(basename "$entry")
    keep=0
    for w in "${HOME_WHITELIST[@]}"; do
        if [ "$name" = "$w" ]; then keep=1; break; fi
    done
    if [ "$keep" -eq 1 ]; then
        KEPT_TARGETS+=("$entry")
    else
        DELETION_TARGETS+=("$entry")
    fi
done
shopt -u nullglob

printf "  ${GREEN}KEEP${RESET}   (whitelist):\n"
if [ ${#KEPT_TARGETS[@]} -eq 0 ]; then
    printf "    ${GRAY}(none of astromechos/, angles_backup/ found in this home dir)${RESET}\n"
else
    for k in "${KEPT_TARGETS[@]}"; do
        printf "    ${GREEN}•${RESET} %s\n" "$k"
    done
fi
printf "    ${GREEN}•${RESET} all hidden entries (.*)\n"
printf "  ${RED}DELETE${RESET} (non-whitelisted top-level entries):\n"
if [ ${#DELETION_TARGETS[@]} -eq 0 ]; then
    printf "    ${GRAY}(none — home dir already clean)${RESET}\n"
else
    for d in "${DELETION_TARGETS[@]}"; do
        size=$(du -sh "$d" 2>/dev/null | cut -f1 || echo "?")
        printf "    ${RED}•${RESET} %s  ${GRAY}(%s)${RESET}\n" "$d" "$size"
    done
fi
printf "\n"

# Confirmation gate. --dry-run and --yes both skip the prompt.
if [ "$DRY_RUN" != true ] && [ "$YES" != true ]; then
    printf "${YELLOW}${BOLD}This will purge logs, caches, history, machine-id, the items above${RESET}\n"
    printf "${YELLOW}${BOLD}and stop every astromech-* service. DESTRUCTIVE.${RESET}\n"
    printf "${YELLOW}Continue?${RESET} (type ${BOLD}y${RESET} to confirm) : "
    read -r answer
    case "$answer" in
        y|Y|yes|YES) : ;;
        *) err "Aborted by operator."; exit 1 ;;
    esac
fi

# ─── Before snapshot ────────────────────────────────────────────────────────
BEFORE_DF=$(df -h / | awk 'NR==2 {print $3 " used, " $4 " free (" $5 ")"}')
BEFORE_USED_KB=$(df -k / | awk 'NR==2 {print $3}')

# ─── 1. Stop astromech-* services ───────────────────────────────────────────
step "1/9  Stopping astromech-* services"
mapfile -t SVCS < <(systemctl list-unit-files 'astromech-*.service' --no-pager --plain 2>/dev/null | awk 'NR>1 && $1 ~ /\.service$/ {print $1}')
if [ ${#SVCS[@]} -eq 0 ]; then
    warn "No astromech-*.service units installed"
else
    for s in "${SVCS[@]}"; do
        if [ "$DRY_RUN" = true ]; then
            dryln "Would stop $s"
        elif systemctl stop "$s" 2>/dev/null; then
            ok "Stopped $s"
        else
            warn "Could not stop $s (probably already inactive)"
        fi
    done
fi

# ─── 2. Whitelist sweep in TARGET_HOME ──────────────────────────────────────
step "2/9  Removing non-whitelisted entries in $TARGET_HOME"
HOME_REMOVED=0
if [ ${#DELETION_TARGETS[@]} -eq 0 ]; then
    ok "Home dir already clean (only whitelist + dotfiles present)"
else
    for d in "${DELETION_TARGETS[@]}"; do
        if [ "$DRY_RUN" = true ]; then
            dryln "Would remove $d"
            HOME_REMOVED=$((HOME_REMOVED + 1))
        else
            if rm -rf -- "$d" 2>/dev/null; then
                ok "Removed $d"
                HOME_REMOVED=$((HOME_REMOVED + 1))
            else
                warn "Could not remove $d"
            fi
        fi
    done
fi

# ─── 3. Caches (pip, npm, generic .cache) ───────────────────────────────────
step "3/9  Purging caches (pip / npm / .cache)"
if [ "$DRY_RUN" = true ]; then
    dryln "Would purge pip cache for $TARGET_USER"
    dryln "Would purge npm cache for $TARGET_USER (if npm present)"
    dryln "Would rm -rf $TARGET_HOME/.cache and /root/.cache"
else
    if sudo -u "$TARGET_USER" python3 -m pip cache purge >/dev/null 2>&1; then
        ok "pip cache purged for $TARGET_USER"
    else
        warn "pip cache purge failed for $TARGET_USER (non-fatal)"
    fi
    if command -v npm >/dev/null 2>&1; then
        if sudo -u "$TARGET_USER" npm cache clean --force >/dev/null 2>&1; then
            ok "npm cache cleaned for $TARGET_USER"
        fi
    fi
    for d in "$TARGET_HOME/.cache" /root/.cache; do
        if [ -d "$d" ]; then
            rm -rf -- "$d" 2>/dev/null && ok "Removed $d" || warn "Could not remove $d"
        fi
    done
fi

# ─── 4. /tmp/ ──────────────────────────────────────────────────────────────
step "4/9  Emptying /tmp/"
if [ "$DRY_RUN" = true ]; then
    TMP_COUNT=$(find /tmp -mindepth 1 -maxdepth 1 2>/dev/null | wc -l)
    dryln "Would empty /tmp/ (${TMP_COUNT} top-level entries)"
else
    find /tmp -mindepth 1 -maxdepth 1 -exec rm -rf -- {} \; 2>/dev/null || true
    ok "/tmp/ emptied"
fi

# ─── 5. Repo-scoped artefacts ──────────────────────────────────────────────
step "5/9  Removing repo-scoped artefacts (builds, caches, rotation siblings, operator dirs)"
declare -a NODE_CANDS=(
    "$REPO/android/node_modules"
    "$REPO/android/build"
    "$REPO/android/app/build"
    "$REPO/android/.gradle"
    "$REPO/tools/node_modules"
    "$REPO/.tmp"
    "$REPO/.clone"
    "$REPO/debug"
    "$REPO/image"
)
for d in "${NODE_CANDS[@]}"; do
    if [ -d "$d" ]; then
        if [ "$DRY_RUN" = true ]; then
            dryln "Would rm -rf $d"
        else
            rm -rf -- "$d" && ok "Removed $d" || warn "Could not remove $d"
        fi
    fi
done

# Operator scratch scripts at repo root.
mapfile -t TMP_FILES < <(find "$REPO" -maxdepth 1 -type f -name '.tmp_*' 2>/dev/null)
if [ "$DRY_RUN" = true ]; then
    dryln "Would remove ${#TMP_FILES[@]} operator .tmp_* file(s) at repo root"
else
    TMP_FILES_REMOVED=0
    for f in "${TMP_FILES[@]}"; do
        rm -f -- "$f" 2>/dev/null && TMP_FILES_REMOVED=$((TMP_FILES_REMOVED + 1))
    done
    ok "Removed $TMP_FILES_REMOVED operator .tmp_* scratch file(s)"
fi

# Python bytecode caches anywhere in the repo.
mapfile -t PYC_DIRLIST < <(find "$REPO" -type d \( -name '__pycache__' -o -name '.pytest_cache' \) 2>/dev/null)
mapfile -t PYC_FILELIST < <(find "$REPO" -type f -name '*.pyc' 2>/dev/null)
if [ "$DRY_RUN" = true ]; then
    dryln "Would remove ${#PYC_DIRLIST[@]} Python cache dir(s), ${#PYC_FILELIST[@]} *.pyc file(s)"
else
    PYC_DIRS=0
    for d in "${PYC_DIRLIST[@]}"; do
        rm -rf -- "$d" 2>/dev/null && PYC_DIRS=$((PYC_DIRS + 1))
    done
    PYC_FILES=0
    for f in "${PYC_FILELIST[@]}"; do
        rm -f -- "$f" 2>/dev/null && PYC_FILES=$((PYC_FILES + 1))
    done
    ok "Removed $PYC_DIRS Python cache dir(s), $PYC_FILES *.pyc file(s)"
fi

# Rotation backups / quarantine / editor leftovers in every dir hosting
# _atomic_write_* managed files.
declare -a BAK_DIRS=(
    "$REPO/master/config"
    "$REPO/slave/config"
    "$REPO/master/choreographies"
)
mapfile -t BAK_FILES < <(
    for dir in "${BAK_DIRS[@]}"; do
        [ -d "$dir" ] || continue
        find "$dir" -maxdepth 1 -type f \
             \( -regex '.*\.bak[0-9]+$' \
                -o -name '*.broken-*' \
                -o -name '*.orig' \
                -o -name '*~' \) 2>/dev/null
    done
)
if [ "$DRY_RUN" = true ]; then
    dryln "Would remove ${#BAK_FILES[@]} rotation/quarantine/editor backup file(s)"
else
    CONFIG_BAK_REMOVED=0
    for f in "${BAK_FILES[@]}"; do
        rm -f -- "$f" 2>/dev/null && CONFIG_BAK_REMOVED=$((CONFIG_BAK_REMOVED + 1))
    done
    ok "Removed $CONFIG_BAK_REMOVED rotation/quarantine/editor backup file(s)"
fi

# ─── 6. System logs ─────────────────────────────────────────────────────────
step "6/9  Vacuuming journal + truncating /var/log files"
if [ "$DRY_RUN" = true ]; then
    JCT_SIZE=$(journalctl --disk-usage 2>/dev/null | awk -F'take up ' '{print $2}' | tr -d ' .')
    dryln "Would vacuum systemd journal (current: ${JCT_SIZE:-unknown})"
    ACTIVE=$(find /var/log -type f \( -name '*.log' -o -name 'syslog' -o -name 'kern.log' -o -name 'auth.log' -o -name 'messages' -o -name 'daemon.log' -o -name 'btmp' -o -name 'wtmp' -o -name 'lastlog' \) 2>/dev/null | wc -l)
    ARCHIVED=$(find /var/log -type f \( -name '*.gz' -o -name '*.[0-9]' -o -name '*.[0-9].gz' -o -name '*.old' \) 2>/dev/null | wc -l)
    dryln "Would truncate $ACTIVE active log file(s), delete $ARCHIVED archived log file(s)"
else
    if command -v journalctl >/dev/null 2>&1; then
        journalctl --rotate >/dev/null 2>&1 || true
        journalctl --vacuum-time=1s >/dev/null 2>&1 || true
        ok "systemd journal vacuumed"
    fi
    TRUNCATED=0
    DELETED=0
    while IFS= read -r f; do
        truncate -s 0 "$f" 2>/dev/null && TRUNCATED=$((TRUNCATED + 1))
    done < <(find /var/log -type f \( -name '*.log' -o -name 'syslog' -o -name 'kern.log' -o -name 'auth.log' -o -name 'messages' -o -name 'daemon.log' -o -name 'btmp' -o -name 'wtmp' -o -name 'lastlog' \) 2>/dev/null)
    while IFS= read -r f; do
        rm -f -- "$f" 2>/dev/null && DELETED=$((DELETED + 1))
    done < <(find /var/log -type f \( -name '*.gz' -o -name '*.[0-9]' -o -name '*.[0-9].gz' -o -name '*.old' \) 2>/dev/null)
    ok "Truncated $TRUNCATED active log file(s), deleted $DELETED archived log file(s)"
fi

# ─── 7. Shell history ──────────────────────────────────────────────────────
step "7/9  Erasing shell history"
HIST_FILES=(
    "$TARGET_HOME/.bash_history"
    "$TARGET_HOME/.zsh_history"
    "$TARGET_HOME/.python_history"
    "$TARGET_HOME/.lesshst"
    "$TARGET_HOME/.viminfo"
    /root/.bash_history
    /root/.zsh_history
    /root/.python_history
)
for h in "${HIST_FILES[@]}"; do
    if [ -f "$h" ]; then
        if [ "$DRY_RUN" = true ]; then
            dryln "Would truncate $h"
        else
            truncate -s 0 "$h" 2>/dev/null && ok "Cleared $h"
        fi
    fi
done
[ "$DRY_RUN" != true ] && history -c 2>/dev/null || true

# ─── 8. apt clean + autoremove ─────────────────────────────────────────────
step "8/9  apt-get clean + autoremove (reclaim package cache)"
if command -v apt-get >/dev/null 2>&1; then
    if [ "$DRY_RUN" = true ]; then
        dryln "Would apt-get clean && apt-get autoremove --purge -y"
    else
        apt-get clean >/dev/null 2>&1 && ok "apt-get clean"
        apt-get autoremove --purge -y >/dev/null 2>&1 && ok "apt-get autoremove --purge"
    fi
else
    warn "apt-get not available (skip)"
fi

# ─── 9. machine-id reset ────────────────────────────────────────────────────
step "9/9  Resetting machine-id (next boot regenerates)"
if [ "$DRY_RUN" = true ]; then
    [ -f /etc/machine-id ]            && dryln "Would truncate /etc/machine-id"
    [ -f /var/lib/dbus/machine-id ]   && dryln "Would remove /var/lib/dbus/machine-id"
else
    if [ -f /etc/machine-id ]; then
        : > /etc/machine-id && ok "Truncated /etc/machine-id"
    fi
    if [ -f /var/lib/dbus/machine-id ]; then
        rm -f /var/lib/dbus/machine-id && ok "Removed /var/lib/dbus/machine-id"
    fi
fi

# ─── Wipe per-deployment NM profiles + SSH keys ────────────────────────────
# The Golden Image must NOT carry deployment-specific NM connection
# profiles or SSH key state. Each deployment (one Imager flash) provides
# its own via the Imager bake (/boot/firmware/astromech_*) — firstboot
# extracts them. Anything left over from the BUILDER Pi causes the
# idempotent-skip cascade verified live 2026-06-05 (the wlan1 profile
# stayed on builder creds; the slave's authorized_keys merged a stale
# legacy master pubkey → pair-sealing SSH probe failed → SSID stuck on
# bootstrap). Wipe all of:
#   - astromech-hotspot.nmconnection         (wlan0 AP, per-deployment SSID)
#   - astromech-internet.nmconnection        (wlan1 client, per-deployment SSID/PSK)
#   - astromech-master-hotspot.nmconnection  (slave-side; per-deployment master SSID)
#   - r2d2-*.nmconnection                    (legacy rename; defense-in-depth)
# AND wipe ~/.ssh/{authorized_keys,id_ed25519,id_ed25519.pub} on the
# target_user's home dir. Imager bake re-installs all of these.
# NOTE: ~/.ssh/known_hosts is intentionally preserved (slow-changing,
# operator may have added entries).
step "Pre-DD  Wipe per-deployment NM profiles + SSH keys (Imager re-bakes)"
if [ "$DRY_RUN" = true ]; then
    for f in astromech-hotspot astromech-internet astromech-master-hotspot \
             r2d2-internet r2d2-master-hotspot; do
        p="/etc/NetworkManager/system-connections/${f}.nmconnection"
        [ -f "$p" ] && dryln "Would remove $p"
    done
    for k in authorized_keys id_ed25519 id_ed25519.pub; do
        f="$TARGET_HOME/.ssh/$k"
        [ -f "$f" ] && dryln "Would remove $f"
    done
else
    for f in astromech-hotspot astromech-internet astromech-master-hotspot \
             r2d2-internet r2d2-master-hotspot; do
        p="/etc/NetworkManager/system-connections/${f}.nmconnection"
        if [ -f "$p" ]; then
            rm -f "$p" 2>/dev/null && ok "Removed ${f}.nmconnection" \
                || warn "Could not remove $p"
        fi
    done
    for k in authorized_keys id_ed25519 id_ed25519.pub; do
        f="$TARGET_HOME/.ssh/$k"
        if [ -f "$f" ]; then
            rm -f "$f" 2>/dev/null && ok "Removed $TARGET_USER/.ssh/$k" \
                || warn "Could not remove $f"
        fi
    done
fi

# ─── Ensure rpi-resize.service enabled for first-boot FS grow ──────────────
# The DD + pishrink workflow shrinks the image's rootfs partition. On the
# operator's freshly flashed card, rpi-resize.service (gated by
# ConditionFirstBoot=yes — re-trues now that machine-id was reset above)
# triggers systemd-growfs-root which calls resize2fs to grow the FS to fill
# the SD. Pi OS ships this unit DISABLED; we enable it here so the DD'd state
# carries the enabled symlink into the Golden Image.
step "Pre-DD  Enable rpi-resize.service (first-boot FS grow on flashed cards)"
if [ "$DRY_RUN" = true ]; then
    dryln "Would: systemctl enable rpi-resize.service"
else
    if systemctl enable rpi-resize.service 2>/dev/null; then
        ok "rpi-resize.service enabled (next-boot ConditionFirstBoot=yes fires)"
    else
        warn "rpi-resize.service not present (older Pi OS) — pishrink rc.local fallback will still grow the FS"
    fi
fi

# ─── Final sync + page-cache drop ──────────────────────────────────────────
step "Final  sync + drop_caches (commit writes, flush page cache)"
if [ "$DRY_RUN" = true ]; then
    dryln "Would: sync && echo 3 > /proc/sys/vm/drop_caches"
else
    sync && ok "sync committed"
    if [ -w /proc/sys/vm/drop_caches ]; then
        echo 3 > /proc/sys/vm/drop_caches && ok "Dropped page/inode/dentry caches"
    else
        warn "/proc/sys/vm/drop_caches not writable (skip)"
    fi
fi

# ─── After snapshot + report ───────────────────────────────────────────────
AFTER_DF=$(df -h / | awk 'NR==2 {print $3 " used, " $4 " free (" $5 ")"}')
AFTER_USED_KB=$(df -k / | awk 'NR==2 {print $3}')
RECLAIMED_KB=$(( BEFORE_USED_KB - AFTER_USED_KB ))
RECLAIMED_MB=$(( RECLAIMED_KB / 1024 ))

printf "\n${BOLD}${CYAN}╔════════════════════════════════════════════════════════════════════╗${RESET}\n"
if [ "$DRY_RUN" = true ]; then
    printf "${BOLD}${CYAN}║              DRY-RUN COMPLETE — nothing was deleted              ║${RESET}\n"
else
    printf "${BOLD}${CYAN}║                       CLEANUP COMPLETE                           ║${RESET}\n"
fi
printf "${BOLD}${CYAN}╚════════════════════════════════════════════════════════════════════╝${RESET}\n"
printf "${BOLD}Host${RESET}        : %s  (${BOLD}%s${RESET})\n" "$HOSTNAME_RAW" "$ROLE"
printf "${BOLD}Disk usage${RESET}\n"
printf "  Before  : %s\n" "$BEFORE_DF"
printf "  After   : %s\n" "$AFTER_DF"
if [ "$DRY_RUN" != true ]; then
    if [ "$RECLAIMED_MB" -gt 0 ]; then
        printf "  ${GREEN}Reclaimed${RESET} : ~%d MB\n" "$RECLAIMED_MB"
    else
        printf "  ${GRAY}Reclaimed${RESET} : %d KB\n" "$RECLAIMED_KB"
    fi
fi

if [ "$DRY_RUN" = true ]; then
    printf "\n${YELLOW}${BOLD}Re-run without --dry-run to actually clean.${RESET}\n\n"
else
    printf "\n${YELLOW}${BOLD}Next steps for imaging:${RESET}\n"
    printf "  1. ${BOLD}sudo shutdown now${RESET}\n"
    printf "  2. Pull the SD card and image it from another machine:\n"
    printf "     ${GRAY}sudo dd if=/dev/sdX of=astromechos.img bs=4M status=progress${RESET}\n"
    printf "  3. Optionally shrink the image with ${BOLD}pishrink${RESET}.\n\n"
fi

exit 0
