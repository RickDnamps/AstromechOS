#!/usr/bin/env bash
# ============================================================================
# scripts/astromech_wlan_setup.sh — boot-time wlan1 NM provisioning.
#
# Triggered by astromech-wlan-setup.service AFTER firstboot has settled.
# Two credential sources, in priority order:
#   1. /boot/astromech_wlan.conf (or /boot/firmware/...) — Imager-baked,
#      shredded after successful consumption.
#   2. local.cfg [home_wifi] ssid + password — persistent fallback.
# If neither source is present, OR wlan1 is not plugged in, OR the NM
# profile 'astromech-internet' already exists: NO-OP. Returns 0 in every
# scenario so the boot is never blocked.
# ============================================================================

set -u   # `set -e` is forbidden — we always return 0 (mirror firstboot:51-53)

# ─── Logging ─────────────────────────────────────────────────────────────
LOGFILE="/var/log/astromech-wlan-setup.log"
mkdir -p /var/log
log() { local m; m="[$(date -Iseconds)] $*"; echo "$m" | tee -a "$LOGFILE" >&2; }
log_ok()  { log "[OK]   $*"; }
log_warn(){ log "[WARN] $*"; }
log_err() { log "[ERR]  $*"; }
log "=========================================="
log "AstromechOS wlan1 setup starting"
log "=========================================="

# ─── Helper: securely wipe the /boot creds file ─────────────────────────
# Defined early because section (g)'s idempotent-skip path calls it BEFORE
# section (i) would otherwise declare it. Bash needs the function defined
# before the line that calls it, regardless of file order.
_shred_boot_conf() {
    if [ -f "$WLAN_CONF" ]; then
        if command -v shred >/dev/null 2>&1; then
            shred -u "$WLAN_CONF" 2>/dev/null \
                && log_ok "Boot creds file securely wiped (shred): $WLAN_CONF" \
                || { rm -f "$WLAN_CONF" 2>/dev/null && log_warn "shred failed, used plain rm: $WLAN_CONF"; }
        else
            rm -f "$WLAN_CONF" 2>/dev/null && log_warn "shred not available, used plain rm: $WLAN_CONF"
        fi
    fi
}

# ─── INI value reader (handles '=' inside values) ────────────────────────
# $1=section header (e.g. "[home_wifi]")  $2=key  $3=file
# Captures the FULL value after the FIRST '=', so SSIDs/PSKs containing '='
# are preserved verbatim. The previous `-F= ... print $2` truncated at the
# first '=' — a WPA2 PSK like "p=ssw0rd!" became "p" (then <8 chars → the
# profile was silently rejected). Surrounding whitespace is trimmed; inner
# characters are kept exactly.
_ini_get() {
    awk -v s="$1" -v k="$2" '
        /^[[:space:]]*\[/ {
            cur=$0; sub(/^[[:space:]]+/,"",cur); sub(/[[:space:]]+$/,"",cur); next
        }
        cur==s && $0 ~ "^[[:space:]]*"k"[[:space:]]*=" {
            v=$0
            sub(/^[[:space:]]*[^=]*=[[:space:]]*/,"",v)   # strip "key ="
            sub(/[[:space:]]+$/,"",v)                     # trim trailing ws
            print v; exit
        }' "$3" 2>/dev/null
}

# ─── Source lib_config.sh ────────────────────────────────────────────────
REPO_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib_config.sh
. "$REPO_PATH/scripts/lib_config.sh"

# Non-fatal: we run as root from systemd; TARGET_USER is only used for
# ownership of any files we touch, and lib_config provides safe fallbacks.
capture_user 2>/dev/null || true

# ─── /boot path discovery ────────────────────────────────────────────────
# Pi OS Bookworm + uses /boot/firmware/. Both layouts supported.
BOOT_DIR="/boot"
[ -d "/boot/firmware" ] && BOOT_DIR="/boot/firmware"
WLAN_CONF="$BOOT_DIR/astromech_wlan.conf"
log_ok "BOOT_DIR=$BOOT_DIR  WLAN_CONF=$WLAN_CONF"

# ─── 1. wlan1 presence check (with enumeration wait) ─────────────────────
# Optional dev-mode override: WLAN_SETUP_FAKE_WLAN1=1 simulates presence
# (for local Windows-side testing). NEVER set in production.
#
# RACE FIX: a USB Wi-Fi dongle can take several seconds to enumerate after
# boot (driver probe + udev rename to wlan1). This service is a systemd
# oneshot — a single early check would no-op PERMANENTLY even though the
# dongle appears moments later, which is exactly why a working dongle never
# got an 'astromech-internet' profile on a fresh flash. Poll for up to ~30s.
if [ "${WLAN_SETUP_FAKE_WLAN1:-0}" != "1" ]; then
    _wlan1_wait="${WLAN1_WAIT_SECS:-30}"
    while [ ! -e /sys/class/net/wlan1 ] && [ "$_wlan1_wait" -gt 0 ]; do
        sleep 1
        _wlan1_wait=$((_wlan1_wait - 1))
    done
    if [ ! -e /sys/class/net/wlan1 ]; then
        log "wlan1 interface still absent after wait (no USB dongle plugged in?) — no-op"
        exit 0
    fi
fi
log_ok "wlan1 interface present"

# ─── 2. Credential resolution ────────────────────────────────────────────
# Try /boot/astromech_wlan.conf first, then local.cfg [home_wifi].
# We inline the awk parser (clone of cfg_get's, lib_config.sh:66-71) rather
# than call cfg_get — cfg_get cascades and would silently fall back to
# local.cfg even when the /boot file is empty, which would defeat the
# "did we actually use the /boot file?" logic that drives the shred decision.
SSID=""
PSK=""
SOURCE=""

if [ -f "$WLAN_CONF" ]; then
    log_ok "Imager-baked creds file found: $WLAN_CONF"
    SSID=$(_ini_get "[home_wifi]" ssid     "$WLAN_CONF")
    PSK=$(_ini_get  "[home_wifi]" password "$WLAN_CONF")
    [ -n "$SSID" ] && SOURCE="boot"
fi

if [ -z "$SSID" ]; then
    log "No usable creds in $WLAN_CONF — falling back to local.cfg [home_wifi]"
    SSID=$(cfg_get home_wifi ssid "")
    PSK=$(cfg_get home_wifi password "")
    [ -n "$SSID" ] && SOURCE="local_cfg"
fi

if [ -z "$SSID" ]; then
    log "No [home_wifi] credentials in either source — no-op"
    exit 0
fi

# ─── 3. Sanity checks ────────────────────────────────────────────────────
# WPA-PSK min 8 chars (mirror firstboot:382). Empty PSK = open network.
if [ -n "$PSK" ] && [ "${#PSK}" -lt 8 ]; then
    log_err "WiFi password <8 chars (WPA min) — refusing to create profile"
    exit 0
fi
if [ -z "$PSK" ]; then
    log_warn "Empty PSK — creating OPEN network profile (no encryption)"
fi

# ─── 4. Profile create vs update — split by source ───────────────────────
# Bug fix 2026-06-05: previously this block exited 0 whenever the profile
# already existed, which was WRONG when SOURCE=boot. The Imager-baked
# /boot/firmware/astromech_wlan.conf is the operator's explicit at-flash
# choice; if the Golden Image had a stale 'astromech-internet' profile
# from the BUILDER Pi (e.g., builder's home wifi creds), the old code
# shredded the new creds + kept the stale profile + wlan1 never joined the
# operator's home wifi. With this fix, SOURCE=boot ALWAYS wins: it updates
# the existing profile in place, then falls through to the "bring up" +
# "shred" block below.
PROFILE_EXISTS=0
if nmcli -t -f NAME connection show 2>/dev/null | grep -Fxq 'astromech-internet'; then
    PROFILE_EXISTS=1
fi

if [ "$PROFILE_EXISTS" = "1" ] && [ "$SOURCE" != "boot" ]; then
    log_ok "Profile 'astromech-internet' already exists — no-op (idempotent, source=$SOURCE)"
    exit 0
fi

# ─── 5. NM profile creation OR update ────────────────────────────────────
# Run nmcli directly (no sudo: the service runs as root). Tolerant on
# failure — any error path falls through to exit 0 so the boot never blocks.
if [ "$PROFILE_EXISTS" = "1" ]; then
    log "Updating existing NM profile 'astromech-internet' for wlan1 (ssid=$SSID, source=$SOURCE)"
else
    log "Creating NM profile 'astromech-internet' for wlan1 (ssid=$SSID, source=$SOURCE)"
fi

# Make sure NetworkManager actually MANAGES wlan1. USB dongles are often left
# unmanaged (claimed by dhcpcd/wpa_supplicant, or brought up after NM
# started) — and an unmanaged device silently refuses to activate any
# profile, which is a prime suspect for "profile created but never connects".
nmcli device set wlan1 managed yes 2>>"$LOGFILE" \
    && log_ok "wlan1 set managed=yes" \
    || log_warn "could not set wlan1 managed (continuing)"

# Prime NM's scan cache so the target SSID is known before we activate.
nmcli device wifi rescan ifname wlan1 2>>"$LOGFILE" || true
sleep 2

if [ "$PROFILE_EXISTS" = "1" ]; then
    # Modify in place — set SSID, autoconnect, ipv4, powersave, then PSK/keymgmt.
    MOD_CMD=(nmcli connection modify astromech-internet
             connection.interface-name wlan1
             802-11-wireless.ssid "$SSID"
             connection.autoconnect yes
             connection.autoconnect-priority 10
             ipv4.method auto
             802-11-wireless.powersave 2)
    if [ -n "$PSK" ]; then
        MOD_CMD+=(wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$PSK")
    else
        # Open network: clear any prior wifi-sec settings.
        MOD_CMD+=(wifi-sec.key-mgmt "" wifi-sec.psk "")
    fi
    if "${MOD_CMD[@]}" 2>>"$LOGFILE"; then
        log_ok "NM profile 'astromech-internet' updated with fresh creds"
    else
        log_err "nmcli connection modify failed — leaving network alone"
        # Even on failure we shred the /boot creds (otherwise plaintext stays
        # on the partition; operator can retry via Flask /settings/wifi).
        [ "$SOURCE" = "boot" ] && _shred_boot_conf
        exit 0
    fi
else
    ADD_CMD=(nmcli connection add type wifi ifname wlan1 con-name astromech-internet
             ssid "$SSID"
             connection.autoconnect yes
             connection.autoconnect-priority 10
             ipv4.method auto
             802-11-wireless.powersave 2)   # 2 = disable powersave (assoc stability)
    if [ -n "$PSK" ]; then
        ADD_CMD+=(wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$PSK")
    fi
    if "${ADD_CMD[@]}" 2>>"$LOGFILE"; then
        log_ok "NM profile 'astromech-internet' created"
    else
        log_err "nmcli connection add failed — leaving network alone"
        # Even on failure we shred the /boot creds (otherwise plaintext stays
        # on the partition; operator can retry via Flask /settings/wifi).
        [ "$SOURCE" = "boot" ] && _shred_boot_conf
        exit 0
    fi
fi

# Bring it up — RETRY a few times. Right after boot the dongle may still be
# scanning, so the AP isn't visible on the first attempt; a single try then
# left it disconnected. Rescan + retry, then fall back to NM autoconnect.
_up_ok=0
for _try in 1 2 3 4; do
    if nmcli connection up astromech-internet 2>>"$LOGFILE"; then
        log_ok "wlan1 associated with '$SSID' (attempt $_try)"
        _up_ok=1
        break
    fi
    log_warn "connection up attempt $_try failed — rescan + retry"
    nmcli device wifi rescan ifname wlan1 2>>"$LOGFILE" || true
    sleep 3
done
if [ "$_up_ok" != "1" ]; then
    log_warn "could not bring up wlan1 now — profile saved with autoconnect=yes; NM will retry when '$SSID' is in range"
fi

# ─── 6. Persist to local.cfg + shred the /boot source ────────────────────
# Only if source was the /boot file (avoids rewriting what's already there).
if [ "$SOURCE" = "boot" ]; then
    log "Persisting creds to local.cfg [home_wifi] for Flask UI consistency"
    write_local_cfg home_wifi ssid "$SSID" \
        && log_ok "local.cfg [home_wifi] ssid persisted" \
        || log_warn "Could not persist ssid to local.cfg"
    if [ -n "$PSK" ]; then
        write_local_cfg home_wifi password "$PSK" \
            && log_ok "local.cfg [home_wifi] password persisted" \
            || log_warn "Could not persist password to local.cfg"
    fi
    _shred_boot_conf
fi

# ─── 7. End banner ───────────────────────────────────────────────────────
sync
log_ok "wlan1 setup complete — exiting 0"
log "=========================================="
exit 0
