#!/usr/bin/env bash
# scripts/lib_config.sh — shared identity / config helpers for AstromechOS
# install + deploy + update scripts.
#
# Source with:
#     . "$(dirname "$0")/lib_config.sh"
# or:
#     . "$REPO_PATH/scripts/lib_config.sh"
#
# Provides:
#   cfg_get <section> <key> <default>   read a value from /boot init,
#                                       local.cfg, main.cfg, default.
#   capture_user                        set TARGET_USER + TARGET_HOME from
#                                       $SUDO_USER / logname / prompt /
#                                       legacy 'artoo'.
#   slave_user                          SSH user on the Slave (cfg + waterfall).
#   slave_host                          Slave hostname/IP (cfg + waterfall).
#   slave_target                        composite user@host string.
#
# Resolution waterfall (matches shared/identity.py for the Python side):
#   1. /boot/astromech_init.cfg  (AstromechOS Imager bootstrap)
#   2. local.cfg  ([system]/[deploy]/[slave])
#   3. main.cfg   (in-repo defaults)
#   4. $SUDO_USER / $(logname) / $(whoami) auto-detection
#   5. Legacy 'artoo' / 'astromech-slave.local' (rétrocompat for the
#      original R2-D2 install — never reached on a fresh Imager install).

# Resolve REPO + cfg paths if the caller didn't set them.
: "${REPO:=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
: "${REPO_PATH:=$REPO}"
: "${LOCAL_CFG:=$REPO/master/config/local.cfg}"
: "${MAIN_CFG:=$REPO/master/config/main.cfg}"

# Candidate paths for the Imager bootstrap (Bookworm moved /boot → /boot/firmware).
ASTRO_BOOT_INIT_CANDIDATES=(
    "/boot/astromech_init.cfg"
    "/boot/firmware/astromech_init.cfg"
)

# ──────────────────────────────────────────────────────────────────
# cfg_get <section> <key> <default>
# Read a key from /boot init → local.cfg → main.cfg → default.
# Prints the resolved value to stdout (or the default on miss).
# ──────────────────────────────────────────────────────────────────
cfg_get() {
    local section="$1" key="$2" default="$3"
    local f val
    # 1. Imager bootstrap (one-shot file, written by the Imager UI to /boot).
    for f in "${ASTRO_BOOT_INIT_CANDIDATES[@]}"; do
        [ -f "$f" ] || continue
        val=$(awk -F= -v s="[$section]" -v k="$key" '
            /^\[/{cur=$0}
            cur==s && $1 ~ "^[[:space:]]*"k"[[:space:]]*$" {
                gsub(/^[[:space:]]+|[[:space:]]+$/, "", $2)
                print $2; exit
            }' "$f" 2>/dev/null)
        if [ -n "$val" ]; then echo "$val"; return 0; fi
    done
    # 2. local.cfg, then 3. main.cfg.
    for f in "$LOCAL_CFG" "$MAIN_CFG"; do
        [ -f "$f" ] || continue
        val=$(awk -F= -v s="[$section]" -v k="$key" '
            /^\[/{cur=$0}
            cur==s && $1 ~ "^[[:space:]]*"k"[[:space:]]*$" {
                gsub(/^[[:space:]]+|[[:space:]]+$/, "", $2)
                print $2; exit
            }' "$f" 2>/dev/null)
        if [ -n "$val" ]; then echo "$val"; return 0; fi
    done
    # 4. Caller-supplied default.
    echo "$default"
}

# ──────────────────────────────────────────────────────────────────
# capture_user — set TARGET_USER + TARGET_HOME for the install.
# Exits non-zero if root or non-existent user (caller should `|| exit`).
# Waterfall: Imager bootstrap [system] user → $SUDO_USER → logname →
# whoami → interactive prompt (TTY) → legacy 'artoo'.
# ──────────────────────────────────────────────────────────────────
capture_user() {
    local u=""
    # 1. Imager bootstrap (future: /boot/astromech_init.cfg).
    u=$(cfg_get system user "")
    # 2. $SUDO_USER (set by sudo when invoked from a regular login).
    if [ -z "$u" ] && [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ]; then
        u="$SUDO_USER"
    fi
    # 3. logname (the login-session user, even if running as root).
    if [ -z "$u" ] && command -v logname >/dev/null 2>&1; then
        u=$(logname 2>/dev/null || true)
    fi
    # 4. whoami (last-ditch).
    [ -z "$u" ] && u=$(whoami)
    # 5. Interactive prompt (only if we have a TTY and still don't have a user
    #    OR ended up with root — refuse to install as root).
    if { [ "$u" = "root" ] || [ -z "$u" ]; } && [ -t 0 ]; then
        echo "" >&2
        echo "[!] AstromechOS install: could not auto-detect the target Linux user." >&2
        echo "    (Tip: run via 'sudo bash $0' from a regular login, or pre-write" >&2
        echo "     [system] user = <name> in /boot/astromech_init.cfg via the Imager.)" >&2
        printf "    Linux user to install AstromechOS for: " >&2
        read -r u
    fi
    # 6. Legacy fallback — keeps the original R2-D2 install path working.
    [ -z "$u" ] && u="artoo"
    # Validation.
    [ "$u" = "root" ] && { echo "[ERR] refusing to install as root — pick a regular user" >&2; return 1; }
    id "$u" &>/dev/null || { echo "[ERR] user '$u' does not exist on this system" >&2; return 1; }
    TARGET_USER="$u"
    TARGET_HOME=$(getent passwd "$u" | cut -d: -f6)
    [ -z "$TARGET_HOME" ] && TARGET_HOME="/home/$u"
    export TARGET_USER TARGET_HOME
}

# ──────────────────────────────────────────────────────────────────
# slave_user / slave_host / slave_target — SSH endpoint for Master→Slave.
# ──────────────────────────────────────────────────────────────────
slave_user() {
    local u
    u=$(cfg_get deploy slave_user "")
    [ -z "$u" ] && u=$(cfg_get system user "")
    [ -z "$u" ] && u="${TARGET_USER:-}"
    [ -z "$u" ] && [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ] && u="$SUDO_USER"
    [ -z "$u" ] && u=$(logname 2>/dev/null || whoami 2>/dev/null || echo "")
    [ -z "$u" ] && u="artoo"
    echo "$u"
}

slave_host() {
    local h
    h=$(cfg_get slave host "")
    [ -z "$h" ] && h=$(cfg_get deploy slave_host "")
    [ -z "$h" ] && h="astromech-slave.local"
    echo "$h"
}

slave_target() {
    echo "$(slave_user)@$(slave_host)"
}
