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
# Crash-safe push intent (field log 2026-06-12): written right BEFORE the
# SSH push to the slave, removed when sealing completes. If a run dies
# between the push and the Master AP flip (the firstboot scheduled reboot
# did exactly that), the slave is left hunting the FINAL SSID while the
# master still broadcasts the bootstrap one — and the normal retry path
# can never proceed (it requires the slave reachable, which now requires
# the flip). The intent marker lets a later run ROLL FORWARD: flip the AP
# without re-probing, reuniting the pair.
INTENT="$MARKER_DIR/pair_push_intent"
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
#
# Bug fix 2026-06-05: the service runs as User=root (needs nmcli + marker
# write), so ssh would consult /root/.ssh which has no Imager-baked key.
# Explicitly use the TARGET_USER's id_ed25519 (the outbound key firstboot
# installed into /home/$TARGET_USER/.ssh/) and pin known_hosts to that
# same dir so accept-new persists across runs without polluting /root.
_SSH_KEY="/home/$TARGET_USER/.ssh/id_ed25519"
_SSH_KNOWN="/home/$TARGET_USER/.ssh/known_hosts"
_SSH_OPTS="-i $_SSH_KEY -o UserKnownHostsFile=$_SSH_KNOWN -o StrictHostKeyChecking=accept-new -o BatchMode=yes"

_slave_reachable() {
    if ! ping -c 1 -W 2 "$SLAVE_TARGET" >/dev/null 2>&1; then
        log "Slave not reachable ($SLAVE_TARGET ping fail)."
        return 1
    fi
    if ! ssh $_SSH_OPTS -o ConnectTimeout=4 "$SSH_USER@$SLAVE_TARGET" 'true' >/dev/null 2>&1; then
        log "Slave SSH not yet ready (probe to $SSH_USER@$SLAVE_TARGET failed)."
        return 1
    fi
    return 0
}

# ROLL_FORWARD=1 means: a previous run already pushed the FINAL SSID to the
# slave and died before flipping the Master AP. The slave is EXPECTED to be
# unreachable (it hunts an SSID nobody broadcasts yet) — skip the probe and
# the push, flip the AP, and the slave's NM autoconnect reunites the pair.
# Age-gated at 180s: a slave that dropped for benign reasons (its own
# firstboot reboot) comes back on the bootstrap SSID within ~1 min and takes
# the normal path; only a genuinely orphaned slave stays unreachable.
# Residual risk accepted: a slave that lost power in the ~1s between probe
# and push AND stayed off >180s would still hold the bootstrap SSID after a
# roll-forward — power it while the master is up and re-pair per
# docs/FIRSTBOOT.md (rm pair_sealed + restart units).
ROLL_FORWARD=0
if _slave_reachable; then
    log_ok "Slave reachable at $SSH_USER@$SLAVE_TARGET"
elif [ -f "$INTENT" ]; then
    _AGE=$(( $(date +%s) - $(stat -c %Y "$INTENT" 2>/dev/null || echo 0) ))
    if [ "$_AGE" -ge 180 ]; then
        ROLL_FORWARD=1
        log_warn "Push intent is ${_AGE}s old and the slave is still unreachable — assuming the previous run pushed the final SSID and was killed before the AP flip (field log 2026-06-12). ROLLING FORWARD: flipping the Master AP without re-push."
    else
        log "Push intent present (${_AGE}s old), slave unreachable — letting it settle before roll-forward. Exit 2."
        exit 2
    fi
else
    log "Exit 2."
    exit 2
fi

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
    rm -f "$INTENT" 2>/dev/null || true
    # Quiesce the trigger units on THIS exit path too (field 2026-06-12: the
    # idempotent path returned before step 11, leaving the active .timer
    # ticking a condition-skipped service every 60s until the next reboot).
    if [ "$MARKER_DIR" = "/var/lib/astromech" ] && command -v systemctl >/dev/null 2>&1; then
        systemctl reset-failed astromech-pair-sealing.path 2>/dev/null || true
        systemctl stop --no-block astromech-pair-sealing.path astromech-pair-sealing.timer 2>/dev/null || true
    fi
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

if [ "$ROLL_FORWARD" -eq 1 ]; then
    log "Roll-forward: skipping slave push (delivered by the interrupted run)."
else
    # CRASH-SAFE ORDER (field log 2026-06-12): record the push intent BEFORE
    # the push. If this process dies between the push and the AP flip (the
    # firstboot scheduled reboot did exactly that — sealing log stopped at
    # 'Slave reachable', slave profile mtime proved the push landed), the
    # next run finds the intent + an unreachable slave and rolls forward.
    mkdir -p "$MARKER_DIR"
    printf '%s\n' "$FINAL_SSID" > "$INTENT" 2>/dev/null || true
    if ! ssh $_SSH_OPTS -o ConnectTimeout=6 "$SSH_USER@$SLAVE_TARGET" "$_PUSH" 2>>"$LOGFILE"; then
        log_err "SSH push to Slave failed."
        # Leave the intent in place: an ssh killed mid-flight may still have
        # delivered the nmcli on the slave — the age-gated roll-forward will
        # converge either way.
        exit 1
    fi
    log_ok "Slave NM profile updated with FINAL_SSID='$FINAL_SSID'"
fi

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
rm -f "$INTENT" 2>/dev/null || true

# ── 11. Quiesce the trigger units for THIS session ───────────────────────
# The ConditionPathExists=!marker gate on .path/.timer only applies at the
# units' NEXT activation — the already-active .timer would otherwise keep
# ticking a condition-skipped .service every 60s (journal spam for the rest
# of the session), and a .path stuck in 'failed (trigger-limit-hit)' from
# boot churn (observed live 2026-06-11) would linger forever. Stopping the
# .timer from the oneshot it triggered is safe — it does not kill this
# running instance. Guarded so the sandboxed test harness (fake MARKER_DIR)
# never touches the real units.
if [ "$MARKER_DIR" = "/var/lib/astromech" ] && command -v systemctl >/dev/null 2>&1; then
    systemctl reset-failed astromech-pair-sealing.path 2>/dev/null || true
    systemctl stop --no-block astromech-pair-sealing.path astromech-pair-sealing.timer 2>/dev/null || true
fi

log_ok "Pair-sealing complete. Marker written. Service will not run again."
exit 0
