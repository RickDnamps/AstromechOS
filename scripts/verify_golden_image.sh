#!/bin/bash
# ============================================================================
# verify_golden_image.sh — final quality gate for a Golden Image .img file.
#
# Loop-mounts the raw image READ-ONLY and checks the 9 ship-state criteria
# inside the actual filesystem content. This is the check that proves an
# image will provision (hotspot + pairing) on a fresh flash — the two
# historical Golden Image bugs (firstboot disabled in the 07-06 images,
# runcmd_done baked in) would both have been caught by this gate.
#
# Run on any Linux with loop-device support (WSL2 Debian works), as root:
#   sudo bash verify_golden_image.sh /path/to/AstromechOS_Master_<date>.img
#   # WSL example:
#   wsl -d Debian -u root -- bash /mnt/j/R2-D2_Build/AstromechOS/scripts/verify_golden_image.sh \
#       /mnt/i/AstromechOS_Master_11-06-2026.img
#
# Exit 0 = ship-clean. Exit 1 = at least one FAIL (do NOT distribute).
#
# Criteria (the clean_for_imager.sh contract):
#   1. No per-deployment NM profiles (astromech-*/r2d2-*)
#   2. No SSH keys/authorized_keys in the UID-1000 home
#   3. No lifecycle markers (pair_sealed, runcmd_done) — baked pair_sealed
#      means a fresh flash NEVER seals (bootstrap SSID forever)
#   4. astromech-firstboot ENABLED (enable symlink present) — the 06-08 bug
#   5. machine-id truncated
#   6. firstboot.log + .bash_history empty
#   7. Boot partition carries no leftover trigger marker / secrets dir
#   8. /var/log/journal present (persistent journald — bd software-7dh)
#   9. No stale netplan 90-NM-*.yaml (old-pairing leftover — bd software-ri7)
# ============================================================================
set -u

IMG="${1:-}"
if [ -z "$IMG" ] || [ ! -f "$IMG" ]; then
    echo "Usage: sudo bash $0 /path/to/AstromechOS_<Role>_<date>.img" >&2
    exit 2
fi
if [ "$(id -u)" -ne 0 ]; then
    echo "[FATAL] must run as root (loop mounts)" >&2
    exit 2
fi

BOOT_MNT=$(mktemp -d)
ROOT_MNT=$(mktemp -d)
FAIL=0

LOOP=$(losetup -Pfr --show "$IMG") || { echo "[FATAL] losetup failed"; exit 2; }
cleanup() {
    umount "$BOOT_MNT" 2>/dev/null
    umount "$ROOT_MNT" 2>/dev/null
    losetup -d "$LOOP" 2>/dev/null
    rmdir "$BOOT_MNT" "$ROOT_MNT" 2>/dev/null
}
trap cleanup EXIT

mount -o ro "${LOOP}p1" "$BOOT_MNT" 2>/dev/null || echo "[WARN] boot partition mount failed"
mount -o ro,noload "${LOOP}p2" "$ROOT_MNT" 2>/dev/null || { echo "[FATAL] rootfs mount failed"; exit 2; }

echo "=== verify_golden_image: $IMG ==="

# 1. NM profiles
if ls "$ROOT_MNT/etc/NetworkManager/system-connections/" 2>/dev/null | grep -qE "astromech|r2d2"; then
    echo "[FAIL] 1. per-deployment NM profile(s) present"; FAIL=1
else
    echo "[PASS] 1. no per-deployment NM profiles"
fi

# 2. SSH keys
USERHOME=$(ls -d "$ROOT_MNT"/home/* 2>/dev/null | head -1)
BAD=0
for k in authorized_keys id_ed25519 id_ed25519.pub; do
    [ -f "$USERHOME/.ssh/$k" ] && { echo "[FAIL] 2. $k present"; BAD=1; FAIL=1; }
done
[ "$BAD" -eq 0 ] && echo "[PASS] 2. no SSH keys / authorized_keys"

# 3. Lifecycle markers
if ls "$ROOT_MNT/var/lib/astromech/" 2>/dev/null | grep -qE "pair_sealed|runcmd_done"; then
    echo "[FAIL] 3. lifecycle marker(s) baked in (pairing/bootcmd would be skipped on fresh flash)"; FAIL=1
else
    echo "[PASS] 3. no pair_sealed / runcmd_done"
fi

# 4. firstboot enabled
if [ -L "$ROOT_MNT/etc/systemd/system/multi-user.target.wants/astromech-firstboot.service" ]; then
    echo "[PASS] 4. astromech-firstboot enabled"
else
    echo "[FAIL] 4. firstboot enable symlink MISSING (no hotspot/pairing on fresh flash)"; FAIL=1
fi

# 5. machine-id
if [ -s "$ROOT_MNT/etc/machine-id" ]; then
    echo "[FAIL] 5. machine-id non-empty"; FAIL=1
else
    echo "[PASS] 5. machine-id truncated"
fi

# 6. Logs/history
FBLOG=$(stat -c %s "$ROOT_MNT/var/log/astromech-firstboot.log" 2>/dev/null || echo 0)
HIST=$(stat -c %s "$USERHOME/.bash_history" 2>/dev/null || echo 0)
if [ "$FBLOG" -eq 0 ] && [ "$HIST" -eq 0 ]; then
    echo "[PASS] 6. logs/history clean"
else
    echo "[FAIL] 6. residual logs (firstboot.log=$FBLOG, .bash_history=$HIST)"; FAIL=1
fi

# 7. Boot partition leftovers
if ls "$BOOT_MNT" 2>/dev/null | grep -iqE "ASTROMECH_FIRSTBOOT_READY|astromech_secrets"; then
    echo "[FAIL] 7. leftover trigger/secrets on boot partition"; FAIL=1
else
    echo "[PASS] 7. boot partition clean (Imager adds trigger+secrets at flash)"
fi

# 8. Persistent journal dir (bd software-7dh: 11-06 images shipped without
#    it → volatile journals → zero forensics on flashed robots)
if [ -d "$ROOT_MNT/var/log/journal" ]; then
    echo "[PASS] 8. /var/log/journal present (persistent journald)"
else
    echo "[FAIL] 8. /var/log/journal MISSING — flashed robots get volatile logs"; FAIL=1
fi

# 9. Stale netplan-exported NM profiles (bd software-ri7: leftover
#    90-NM-*.yaml regenerates an old pairing's connection on every boot)
if ls "$ROOT_MNT/etc/netplan/" 2>/dev/null | grep -q "^90-NM-"; then
    echo "[FAIL] 9. stale netplan 90-NM-*.yaml present (old pairing leftover)"; FAIL=1
else
    echo "[PASS] 9. no stale netplan-exported profiles"
fi

echo ""
if [ "$FAIL" -eq 0 ]; then
    echo ">>> SHIP-CLEAN: image is safe to distribute / pishrink"
    exit 0
else
    echo ">>> NOT SHIP-CLEAN: fix the source Pi (clean_for_imager.sh) and re-DD" >&2
    exit 1
fi
