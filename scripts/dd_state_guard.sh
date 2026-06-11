#!/usr/bin/env bash
# ============================================================================
# dd_state_guard.sh — keep the BUILDER pair functional around a Golden Image DD
#
# clean_for_imager.sh deliberately strips per-deployment state (NM profiles,
# SSH keys, pair_sealed/runcmd_done markers, machine-id) and re-ARMS
# astromech-firstboot so the DD'd image provisions fresh flashes. But the
# PHYSICAL builder cards must NOT stay in that state: their /boot has no
# Imager bake anymore (secrets were consumed at their own firstboot), so a
# re-armed firstboot on the next reboot would at best no-op (no trigger) and
# at worst brick the card if a stray trigger appears. The operator wants to
# reboot the builder pair right after the DD and keep developing on it.
#
# Usage (as root, on the Pi being imaged):
#   dd_state_guard.sh backup    BEFORE clean_for_imager.sh — snapshot the
#                               per-deployment state to /dev/shm (RAM-backed:
#                               by construction it can never leak into the DD).
#   dd_state_guard.sh restore   AFTER the dd | gzip completes — re-apply the
#                               snapshot, DISABLE astromech-firstboot +
#                               rpi-resize again (deployed-robot state),
#                               remove any trigger marker, reload NM and
#                               restart the role services. Fail-loud verify.
#
# The canonical Golden Image cycle is therefore:
#   1. dd_state_guard.sh backup
#   2. clean_for_imager.sh --yes
#   3. dd if=/dev/mmcblk0 bs=4M | gzip > <ssd>/AstromechOS_<Role>_<date>.img.gz
#   4. dd_state_guard.sh restore
#   5. reboot (builder Pi comes back with final SSID, pairing sealed, no
#      firstboot attempt)
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib_config.sh
. "$SCRIPT_DIR/lib_config.sh"

if [ "$(id -u)" -ne 0 ]; then
    echo "[FATAL] must run as root (sudo $0 $*)" >&2
    exit 1
fi

capture_user 2>/dev/null || true
if [ -z "${TARGET_USER:-}" ] || ! id "$TARGET_USER" &>/dev/null; then
    # Fallback: UID-1000 owner (username-agnostic per CLAUDE.md HARD RULE)
    TARGET_USER="$(getent passwd 1000 | cut -d: -f1)"
    TARGET_HOME="$(getent passwd 1000 | cut -d: -f6)"
fi
[ -n "${TARGET_HOME:-}" ] || TARGET_HOME="$(getent passwd "$TARGET_USER" | cut -d: -f6)"

BK=/dev/shm/astromech_dd_state.tar
MODE="${1:-}"

# Paths snapshotted (relative to /, only those that exist at backup time).
# Everything clean_for_imager.sh wipes that the builder pair needs back:
#   - NM connection profiles (hotspot final SSID, internet, master-hotspot)
#   - $TARGET_HOME/.ssh        (id_ed25519 pair, authorized_keys, known_hosts)
#   - /var/lib/astromech       (pair_sealed + runcmd_done markers)
#   - machine-id (truncated for ConditionFirstBoot; restoring keeps the
#     builder's journal identity and prevents first-boot semantics on reboot)
candidate_paths() {
    echo "etc/NetworkManager/system-connections"
    echo "var/lib/astromech"
    echo "etc/machine-id"
    echo "var/lib/dbus/machine-id"
    echo "${TARGET_HOME#/}/.ssh"
}

case "$MODE" in
backup)
    echo "[dd_state_guard] snapshotting per-deployment state to $BK (tmpfs)"
    LIST=()
    while IFS= read -r p; do
        [ -e "/$p" ] && LIST+=("$p")
    done < <(candidate_paths)
    if [ "${#LIST[@]}" -eq 0 ]; then
        echo "[FATAL] nothing to back up — wrong machine?" >&2
        exit 1
    fi
    tar -C / -cpf "$BK" "${LIST[@]}"
    chmod 600 "$BK"
    echo "[dd_state_guard] backed up: ${LIST[*]}"
    echo "[dd_state_guard] OK — safe to run clean_for_imager.sh --yes now"
    ;;

restore)
    if [ ! -f "$BK" ]; then
        echo "[FATAL] $BK missing — was 'backup' run before the DD? Did the"  >&2
        echo "        machine reboot (tmpfs wiped)? Manual recovery required:" >&2
        echo "        re-run setup_master_network.sh / re-pair, then disable"  >&2
        echo "        astromech-firstboot manually."                           >&2
        exit 1
    fi
    echo "[dd_state_guard] restoring per-deployment state from $BK"
    tar -C / -xpf "$BK"

    # Back to DEPLOYED-robot state: firstboot must never re-run on the
    # builder cards (no Imager bake left in /boot to provision from), and
    # rpi-resize was only enabled for the image (FS already grown here).
    systemctl disable astromech-firstboot.service 2>/dev/null || true
    systemctl disable rpi-resize.service 2>/dev/null || true
    rm -f /boot/firmware/ASTROMECH_FIRSTBOOT_READY /boot/ASTROMECH_FIRSTBOOT_READY 2>/dev/null || true

    nmcli connection reload 2>/dev/null || true
    systemctl daemon-reload 2>/dev/null || true

    # Restart whichever role services exist on this Pi (master or slave).
    for s in astromech-master astromech-slave astromech-monitor astromech-camera; do
        if systemctl cat "$s.service" >/dev/null 2>&1; then
            systemctl restart "$s.service" 2>/dev/null || true
        fi
    done

    # ── Fail-loud verification ──────────────────────────────────────────
    FAIL=0
    if [ "$(systemctl is-enabled astromech-firstboot.service 2>/dev/null)" = "enabled" ]; then
        echo "[FAIL] astromech-firstboot is still ENABLED" >&2; FAIL=1
    else
        echo "[PASS] astromech-firstboot disabled (builder card will not re-provision)"
    fi
    if [ -e /boot/firmware/ASTROMECH_FIRSTBOOT_READY ]; then
        echo "[FAIL] firstboot trigger marker still present" >&2; FAIL=1
    else
        echo "[PASS] no firstboot trigger marker"
    fi
    if ls /etc/NetworkManager/system-connections/*.nmconnection >/dev/null 2>&1; then
        echo "[PASS] NM profiles restored ($(ls /etc/NetworkManager/system-connections/*.nmconnection | wc -l) profile(s))"
    else
        echo "[FAIL] no NM profiles restored — DO NOT REBOOT, network would be lost" >&2; FAIL=1
    fi
    if [ -s /etc/machine-id ]; then
        echo "[PASS] machine-id restored"
    else
        echo "[FAIL] machine-id still empty" >&2; FAIL=1
    fi
    if [ -d "$TARGET_HOME/.ssh" ]; then
        echo "[PASS] $TARGET_USER/.ssh restored"
    else
        echo "[WARN] $TARGET_HOME/.ssh absent (was it present at backup time?)"
    fi
    if [ "$FAIL" -ne 0 ]; then
        echo "[FATAL] restore verification failed — fix before rebooting" >&2
        exit 1
    fi
    rm -f "$BK"
    echo "[dd_state_guard] restore complete — safe to reboot and keep developing"
    ;;

*)
    echo "Usage: $0 backup|restore" >&2
    exit 2
    ;;
esac
