#!/usr/bin/env bash
# astromech_pair_sealing.sh
#
# Event-driven pair-sealing for the Master AP. Runs as root via
# astromech-pair-sealing.service, triggered by astromech-pair-sealing.path
# whenever /var/lib/misc/dnsmasq.leases changes (i.e., Slave joins/renews).
#
# Replaces the synchronous 5-min ping+ssh probe loop that used to live in
# scripts/firstboot_setup.sh:410-500 — that loop raced the slave's cloud-init
# regenerating SSH host keys + clock drift + dnsmasq settling, and frequently
# timed out leaving the Master on the bootstrap SSID with no auto-recovery.
# The new design retries forever (every lease change) until the slave is
# reachable, then performs the same handover idempotently.
#
# Flow:
#   1) Bail if already sealed (marker /var/lib/astromech/pair_sealed)
#   2) Resolve TARGET_USER + paths via lib_config.sh
#   3) Resolve SLAVE_TARGET (slave host) and SSH_USER from local.cfg
#   4) Ping + SSH-probe the slave → exit 2 if not reachable yet
#   5) Generate FINAL_SSID via gen_hotspot_ssid.sh
#   6) If Master AP already on FINAL_SSID → idempotent: mark sealed, exit 0
#   7) SSH-push final creds to Slave's astromech-master-hotspot NM profile
#   8) Flip Master AP: nmcli connection modify + up
#   9) Persist [hotspot] in local.cfg via sed (mirroring firstboot:484-490)
#  10) chown local.cfg to parent-dir owner (commit 327085f pattern)
#  11) Write marker → service won't fire again
#
# Exit codes:
#   0  sealed (or already sealed)
#   1  permanent error (gen_hotspot_ssid empty, nmcli flip failed, etc.)
#   2  slave not reachable yet — caller (path unit) will retry on next
#      lease change. SuccessExitStatus=0 2 in the .service unit so systemd
#      does NOT log this as a failure.
#
set -uo pipefail

# Find ourselves to locate the repo (mirrors update.sh / setup_master.sh).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_PATH="$(cd "$SCRIPT_DIR/.." && pwd)"
LOGFILE="/var/log/astromech-pair-sealing.log"

# Ensure log directory exists — /var/log always does, but a fresh tmpfs
# would not. mkdir -p is idempotent.
mkdir -p "$(dirname "$LOGFILE")" 2>/dev/null || true

log()      { printf '[%s] %s\n' "$(date -Iseconds)" "$*" | tee -a "$LOGFILE"; }
log_ok()   { printf '[%s] [OK]   %s\n' "$(date -Iseconds)" "$*" | tee -a "$LOGFILE"; }
log_warn() { printf '[%s] [WARN] %s\n' "$(date -Iseconds)" "$*" | tee -a "$LOGFILE"; }
log_err()  { printf '[%s] [ERR]  %s\n' "$(date -Iseconds)" "$*" | tee -a "$LOGFILE" >&2; }

# shellcheck source=lib_config.sh
. "$REPO_PATH/scripts/lib_config.sh"

MARKER_DIR="/var/lib/astromech"
MARKER="$MARKER_DIR/pair_sealed"
LOCAL_CFG_PATH="$REPO_PATH/master/config/local.cfg"

# ── 1. Already sealed? ────────────────────────────────────────────────────
if [ -f "$MARKER" ]; then
    log "Already sealed (marker $MARKER exists). Exit 0."
    exit 0
fi

# ── 2. Resolve target user (the eventual owner of marker + local.cfg) ────
# capture_user is best-effort here — if it fails (e.g., no SUDO_USER as
# systemd runs us with no parent session), the function falls back to the
# 'astromech' last-resort default per CLAUDE.md HARD RULE waterfall.
capture_user || true
TARGET_USER="${TARGET_USER:-astromech}"

# ── 3. Resolve slave target ──────────────────────────────────────────────
SLAVE_TARGET=$(cfg_get slave host "astromech-slave.local")
SSH_USER=$(cfg_get slave user "$TARGET_USER")

# ── 4. Slave reachable? ──────────────────────────────────────────────────
# Two-stage probe: ping (cheap, ~2s timeout) then SSH BatchMode (confirms
# the host key + authorized_keys flow is ready). Either failure → exit 2,
# .path unit will re-trigger us on the next lease change.
if ! ping -c 1 -W 2 "$SLAVE_TARGET" >/dev/null 2>&1; then
    log "Slave not reachable ($SLAVE_TARGET ping fail). Exit 2."
    exit 2
fi
if ! ssh -o StrictHostKeyChecking=accept-new -o BatchMode=yes \
         -o ConnectTimeout=4 "$SSH_USER@$SLAVE_TARGET" 'true' >/dev/null 2>&1; then
    log "Slave SSH not yet ready (probe to $SSH_USER@$SLAVE_TARGET failed). Exit 2."
    exit 2
fi
log_ok "Slave reachable at $SSH_USER@$SLAVE_TARGET"

# ── 5. Generate FINAL_SSID ───────────────────────────────────────────────
FINAL_SSID=$(bash "$REPO_PATH/scripts/gen_hotspot_ssid.sh" 2>/dev/null || echo "")
if [ -z "$FINAL_SSID" ]; then
    log_err "gen_hotspot_ssid.sh produced empty output."
    exit 1
fi

# Read current PSK to reuse (we don't rotate the PSK during sealing — the
# bootstrap PSK was operator-chosen at Imager flash time and is fine).
# Primary source: local.cfg [hotspot] password (set by firstboot from the
# Imager-baked /boot/astromech_init.cfg). Fallback: nmcli stored psk on
# the astromech-hotspot connection.
FINAL_PSK=$(awk -F'= ' '/^\[hotspot\]/,/^\[/ {if ($1 ~ /^password/) print $2}' \
                "$LOCAL_CFG_PATH" 2>/dev/null | head -1 | tr -d '\r')
if [ -z "$FINAL_PSK" ]; then
    FINAL_PSK=$(nmcli -s -g 802-11-wireless-security.psk connection show astromech-hotspot 2>/dev/null || true)
fi
if [ -z "$FINAL_PSK" ]; then
    log_err "Could not resolve current hotspot PSK to reuse."
    exit 1
fi

# ── 6. Master AP already on final? Idempotent. ──────────────────────────
# If a previous sealing run flipped the SSID but crashed before writing
# the marker, just mark and exit. Avoids the cost of another nmcli flip
# (which momentarily drops clients).
CURRENT_SSID=$(nmcli -t -f 802-11-wireless.ssid connection show astromech-hotspot 2>/dev/null \
               | cut -d':' -f2- | head -1 || echo "")
if [ "$CURRENT_SSID" = "$FINAL_SSID" ]; then
    log_ok "Master AP already on FINAL_SSID='$FINAL_SSID' — writing marker and exit."
    mkdir -p "$MARKER_DIR"
    touch "$MARKER"
    chown "$TARGET_USER:$TARGET_USER" "$MARKER" 2>/dev/null || true
    exit 0
fi

# ── 7. SSH push final creds to Slave ─────────────────────────────────────
# Slave NM profile name is resolved REMOTELY (prefer new
# astromech-master-hotspot, fall back to legacy r2d2-master-hotspot —
# legacy installs upgraded in place have the old name).
#
# printf %q escapes the SSID + PSK so that quote/dollar/backslash/control
# chars in the bootstrap PSK cannot break out into the remote shell and
# execute as the slave's astromech user (which has passwordless sudo on
# nmcli). Mirrors firstboot_setup.sh:460-461 CMD-1 hardening (2026-05-30).
_NEW_CON='astromech-master-hotspot'
_LEG_CON='r2d2-master-hotspot'
_PICK="CON=\$(nmcli -t -f NAME connection show 2>/dev/null | grep -Fxq '$_NEW_CON' && echo $_NEW_CON || echo $_LEG_CON)"
_QSSID=$(printf '%q' "$FINAL_SSID")
_QPSK=$(printf '%q' "$FINAL_PSK")
_PUSH="$_PICK; sudo -n nmcli connection modify \"\$CON\" 802-11-wireless.ssid $_QSSID wifi-sec.psk $_QPSK"

if ! ssh -o StrictHostKeyChecking=accept-new -o BatchMode=yes \
         -o ConnectTimeout=6 "$SSH_USER@$SLAVE_TARGET" "$_PUSH" 2>>"$LOGFILE"; then
    log_err "SSH push to Slave failed."
    exit 1
fi
log_ok "Slave NM profile updated with FINAL_SSID='$FINAL_SSID'"

# ── 8. Flip Master AP ────────────────────────────────────────────────────
# Slave NM auto-reconnects to the new SSID (its profile now points at it).
# We do modify-then-up so any client currently connected to the bootstrap
# SSID gets cleanly migrated to the new one rather than dangling.
if ! nmcli connection modify astromech-hotspot \
        802-11-wireless.ssid "$FINAL_SSID" \
        wifi-sec.psk "$FINAL_PSK" 2>>"$LOGFILE" \
   || ! nmcli connection up astromech-hotspot 2>>"$LOGFILE"; then
    log_err "Master AP flip failed."
    exit 1
fi
log_ok "Master AP flipped to FINAL_SSID='$FINAL_SSID'"

# ── 9. Persist [hotspot] in local.cfg ────────────────────────────────────
if [ -f "$LOCAL_CFG_PATH" ]; then
    sed -i \
        -e "/^\[hotspot\]/,/^\[/ s|^ssid\s*=.*|ssid = $FINAL_SSID|" \
        -e "/^\[hotspot\]/,/^\[/ s|^password\s*=.*|password = $FINAL_PSK|" \
        "$LOCAL_CFG_PATH" 2>>"$LOGFILE" \
        && log_ok "local.cfg [hotspot] updated" \
        || log_warn "Could not update local.cfg [hotspot]"

    # Ownership preservation (commit 327085f pattern + write_local_cfg
    # bugfix 2026-06-04 in lib_config.sh): running as root, sed -i in-place
    # keeps the existing owner mostly, BUT if local.cfg was just created
    # by us (e.g., a forced firstboot rerun), it would be root:root mode
    # 0600 — the astromech-uid Flask service cannot read it →
    # configparser swallows EACCES silently → NoOptionError →
    # master crash-loop. Chown to parent-dir owner for username-agnostic
    # safety per CLAUDE.md HARD RULE.
    _OWNER="$(stat -c '%U:%G' "$(dirname "$LOCAL_CFG_PATH")" 2>/dev/null || echo '')"
    if [ -n "$_OWNER" ]; then
        chown "$_OWNER" "$LOCAL_CFG_PATH" 2>/dev/null || true
    fi
fi

# ── 10. Write marker ─────────────────────────────────────────────────────
# Both .service and .path units gate on this marker via ConditionPathExists
# — once written, neither will run again until the operator deletes it
# (e.g., to re-pair a swapped slave). Idempotent on operator-initiated
# re-pair: just `sudo rm /var/lib/astromech/pair_sealed && sudo systemctl
# start astromech-pair-sealing.service`.
mkdir -p "$MARKER_DIR"
touch "$MARKER"
chown "$TARGET_USER:$TARGET_USER" "$MARKER" 2>/dev/null || true

log_ok "Pair-sealing complete. Marker written. Service will not run again."
exit 0
