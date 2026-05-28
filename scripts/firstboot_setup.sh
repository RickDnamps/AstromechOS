#!/usr/bin/env bash
# ============================================================================
# scripts/firstboot_setup.sh — AstromechOS first-boot provisioning.
#
# Runs ONCE at the very first boot of a freshly-imaged SD card. Triggered by
# the systemd oneshot `astromech-firstboot.service` if and only if the marker
# file `/boot/ASTROMECH_FIRSTBOOT_READY` is present. The AstromechOS Imager
# (PC tool) prepares the SD card BEFORE flashing by writing:
#
#   /boot/ASTROMECH_FIRSTBOOT_READY            (trigger marker — deleted at end)
#   /boot/astromech_init.cfg                   (cfg-style bootstrap, read by
#                                                lib_config.sh::cfg_get during
#                                                install and by this script
#                                                for misc settings)
#   /boot/astromech_secrets/  (chmod 0700)
#       init_config.json                       ({role,hostname,...})
#       authorized_keys                        (OpenSSH public keys, one per
#                                                line — appended to the
#                                                target user's authorized_keys)
#       id_ed25519 + id_ed25519.pub            (optional — robot's own keypair
#                                                for outbound SSH; only useful
#                                                on the Master for the
#                                                Master→Slave authorized push)
#
# Workflow:
#   1. Bail if the trigger marker is absent (defensive — nothing to do).
#   2. Source lib_config.sh; run capture_user to set TARGET_USER + TARGET_HOME
#      from /boot/astromech_init.cfg [system] user → $SUDO_USER → ...
#   3. Inject SSH public keys from /boot/astromech_secrets/authorized_keys
#      into $TARGET_HOME/.ssh/authorized_keys (atomic; perms 0600;
#      owned by $TARGET_USER). Copy the optional id_ed25519* keypair.
#   4. Parse /boot/astromech_secrets/init_config.json → hostname + role.
#      Set hostname via hostnamectl. Persist [system] role = master|slave
#      to local.cfg via write_local_cfg.
#   5. If a custom github.repo_url is configured (via /boot/astromech_init.cfg
#      or local.cfg [github] repo_url) AND it differs from origin's current
#      URL: DNA-validate via dna_validate. If valid, switch origin +
#      `git reset --hard origin/<branch>`. If invalid, log + KEEP origin
#      pointed at the (presumably official) original.
#   6. Self-destruct: rm the trigger marker, shred + rmdir the secrets
#      directory, sync, reboot.
#
# Idempotency: every step is safe to re-run on its own; we only delete the
# trigger in step 6, so a crashed run can be retried by simply re-booting.
# All output is captured to /var/log/astromech-firstboot.log AND echoed.
#
# Must be invoked as root (it writes /etc/hostname, /var/log, /boot, ...)
# from the systemd service astromech-firstboot.service.
# ============================================================================

set -u   # treat unset vars as error; DO NOT use `set -e` here — we want to
         # keep going even if a sub-step fails, so the operator can SSH in
         # later and finish manually rather than be locked out of a brick.

# ─── Logging ─────────────────────────────────────────────────────────────
LOGFILE="/var/log/astromech-firstboot.log"
mkdir -p /var/log
log() { local m; m="[$(date -Iseconds)] $*"; echo "$m" | tee -a "$LOGFILE" >&2; }
log_ok()  { log "[OK]   $*"; }
log_warn(){ log "[WARN] $*"; }
log_err() { log "[ERR]  $*"; }
log "=========================================="
log "AstromechOS firstboot_setup.sh starting"
log "=========================================="

# ─── 1. Trigger marker check ────────────────────────────────────────────
TRIGGER="/boot/ASTROMECH_FIRSTBOOT_READY"
[ -f "/boot/firmware/ASTROMECH_FIRSTBOOT_READY" ] && TRIGGER="/boot/firmware/ASTROMECH_FIRSTBOOT_READY"
if [ ! -f "$TRIGGER" ]; then
    log "No trigger marker at $TRIGGER — nothing to do."
    exit 0
fi
log_ok "Trigger marker found: $TRIGGER"

# ─── /boot path discovery ───────────────────────────────────────────────
# Pi OS Bookworm + uses /boot/firmware/. Both layouts supported.
BOOT_DIR="/boot"
[ -d "/boot/firmware" ] && BOOT_DIR="/boot/firmware"
SECRETS_DIR="$BOOT_DIR/astromech_secrets"
INIT_CFG="$BOOT_DIR/astromech_init.cfg"
INIT_JSON="$SECRETS_DIR/init_config.json"
AUTH_KEYS_SRC="$SECRETS_DIR/authorized_keys"
log_ok "BOOT_DIR=$BOOT_DIR  SECRETS_DIR=$SECRETS_DIR"

# ─── 2. Identify the install user (TARGET_USER + TARGET_HOME) ───────────
# capture_user looks in /boot/astromech_init.cfg [system] user first, then
# falls through to $SUDO_USER / logname / 'artoo' legacy.
REPO_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib_config.sh
. "$REPO_PATH/scripts/lib_config.sh"

# We're running as root (systemd unit). The "install" user is the one
# whose home will receive the SSH keys + own the repo install. capture_user
# normally errors if it can't auto-detect; for firstboot we accept whatever
# /boot says, else fall back to 'pi' if it exists, else 'artoo'.
if ! capture_user 2>/dev/null; then
    for u in pi astromech artoo; do
        if id "$u" &>/dev/null; then
            TARGET_USER="$u"
            TARGET_HOME=$(getent passwd "$u" | cut -d: -f6 || echo "/home/$u")
            export TARGET_USER TARGET_HOME
            break
        fi
    done
fi
if [ -z "${TARGET_USER:-}" ] || ! id "$TARGET_USER" &>/dev/null; then
    log_err "Cannot resolve a valid target user — aborting (keeping trigger so a retry is possible)."
    exit 2
fi
log_ok "Target user: $TARGET_USER  home: $TARGET_HOME"

# ─── 3. SSH key injection ────────────────────────────────────────────────
# Append every PUBLIC key in $SECRETS_DIR/authorized_keys to the target
# user's ~/.ssh/authorized_keys, atomically and with strict perms. The
# optional id_ed25519 keypair (private + public) is copied into ~/.ssh/
# so the Master can SSH OUT to the Slave from boot one (Imager generates
# the pair once, writes the public half to the Slave's authorized_keys
# via this same mechanism).
SSH_DIR="$TARGET_HOME/.ssh"
mkdir -p "$SSH_DIR"
chmod 0700 "$SSH_DIR"
chown "$TARGET_USER:$TARGET_USER" "$SSH_DIR"

if [ -f "$AUTH_KEYS_SRC" ]; then
    # Atomic append: copy current → tmp → append source → mv back
    TMP_AK="$(mktemp -p "$SSH_DIR" .authkeys.XXXXXX)"
    if [ -f "$SSH_DIR/authorized_keys" ]; then
        cat "$SSH_DIR/authorized_keys" > "$TMP_AK"
    else
        : > "$TMP_AK"
    fi
    # Strip stray CR/empty lines from the Imager-supplied file
    awk 'NF' "$AUTH_KEYS_SRC" | tr -d '\r' >> "$TMP_AK"
    # Dedupe (sort -u would reorder; awk preserves first-seen order)
    awk '!seen[$0]++' "$TMP_AK" > "$TMP_AK.dedup"
    mv "$TMP_AK.dedup" "$SSH_DIR/authorized_keys"
    rm -f "$TMP_AK"
    chmod 0600 "$SSH_DIR/authorized_keys"
    chown "$TARGET_USER:$TARGET_USER" "$SSH_DIR/authorized_keys"
    NB_KEYS=$(awk 'NF' "$SSH_DIR/authorized_keys" | wc -l)
    log_ok "authorized_keys: $NB_KEYS key(s) installed for $TARGET_USER"
else
    log_warn "No $AUTH_KEYS_SRC — skipping SSH key injection (operator must enable SSH manually)"
fi

# Optional outbound keypair (Master → Slave)
for k in id_ed25519 id_ed25519.pub id_rsa id_rsa.pub; do
    SRC="$SECRETS_DIR/$k"
    if [ -f "$SRC" ]; then
        cp -p "$SRC" "$SSH_DIR/$k"
        chown "$TARGET_USER:$TARGET_USER" "$SSH_DIR/$k"
        case "$k" in
            *.pub) chmod 0644 "$SSH_DIR/$k" ;;
            *)     chmod 0600 "$SSH_DIR/$k" ;;
        esac
        log_ok "outbound key installed: ~/.ssh/$k"
    fi
done

# ─── 4. Identity (role + hostname) from init_config.json ────────────────
ROLE=""
HOSTNAME_TARGET=""
if [ -f "$INIT_JSON" ]; then
    log_ok "Reading $INIT_JSON"
    ROLE=$(_python - "$INIT_JSON" 'role' << 'PYEOF' 2>>"$LOGFILE" || true
import json, sys
try:
    with open(sys.argv[1], encoding='utf-8') as f:
        d = json.load(f)
    print(str(d.get(sys.argv[2], '')).strip().lower())
except Exception as e:
    print('', file=sys.stderr); sys.exit(0)
PYEOF
)
    HOSTNAME_TARGET=$(_python - "$INIT_JSON" 'hostname' << 'PYEOF' 2>>"$LOGFILE" || true
import json, sys
try:
    with open(sys.argv[1], encoding='utf-8') as f:
        d = json.load(f)
    print(str(d.get(sys.argv[2], '')).strip())
except Exception as e:
    print('', file=sys.stderr); sys.exit(0)
PYEOF
)
    log_ok "Parsed role='$ROLE'  hostname='$HOSTNAME_TARGET'"
else
    log_warn "No $INIT_JSON — role/hostname not configured (using defaults below)"
fi

# Validate + default role
case "$ROLE" in
    master|slave) ;;
    *)
        # Heuristic: any Pi without internet on wlan0 is most likely the Slave
        # (it joins the Master's hotspot). But this is best-effort only —
        # for true headless install the Imager MUST set role explicitly.
        log_warn "role missing/invalid in init_config.json; defaulting to 'master'"
        ROLE=master ;;
esac

# Apply hostname (compute from role if not explicit)
if [ -z "$HOSTNAME_TARGET" ]; then
    HOSTNAME_TARGET="astromech-$ROLE"
fi
# Strict charset (RFC 1123) — refuse if the Imager wrote garbage
if [[ "$HOSTNAME_TARGET" =~ ^[a-zA-Z0-9](-?[a-zA-Z0-9])*$ ]] && [ ${#HOSTNAME_TARGET} -le 63 ]; then
    if [ "$(hostname)" != "$HOSTNAME_TARGET" ]; then
        hostnamectl set-hostname "$HOSTNAME_TARGET" \
            && log_ok "hostname set: $HOSTNAME_TARGET" \
            || log_err "hostnamectl failed"
        # Update /etc/hosts so 127.0.1.1 resolves to the new name
        sed -i -E "s/^127\.0\.1\.1\s+.*/127.0.1.1\t$HOSTNAME_TARGET/" /etc/hosts || true
    else
        log_ok "hostname already $HOSTNAME_TARGET"
    fi
else
    log_warn "invalid hostname '$HOSTNAME_TARGET' — leaving system hostname unchanged"
fi

# Persist role in local.cfg so runtime code knows who it is
if [ -n "$ROLE" ]; then
    if write_local_cfg system role "$ROLE"; then
        log_ok "[system] role = $ROLE  written to local.cfg"
    else
        log_warn "Could not persist [system] role to local.cfg"
    fi
fi

# ─── 4.5. I2C HAT layout (read-only detection + Imager override) ────────
# Resilience philosophy (chantier 2026-05-28): the detect step OBSERVES
# (it writes hw_layout.json) but never DECIDES. If the bus is unreachable,
# smbus2 is missing, or no HAT is present, this step LOGS the failure and
# moves on — the master/slave services treat hw_layout.json as a dynamic
# reference and will boot in degraded mode rather than crash. Bricking a
# robot because a single PCA9685 is unresponsive is unacceptable.
#
# Order of preference:
#   1. /boot/hw_layout.json (Imager-provided override — wins, no scan)
#   2. scripts/detect_hats.py --output ... (read-only smbus2 scan)
#   3. silent fallback: no JSON written, services will see absence and
#      log a warning at startup (handled in commit 3+, not here)
log "Step 4.5: I2C HAT layout ..."
if [ "$ROLE" = "slave" ]; then
    HW_LAYOUT_OUT="$REPO_PATH/slave/config/hw_layout.json"
else
    HW_LAYOUT_OUT="$REPO_PATH/master/config/hw_layout.json"
fi
mkdir -p "$(dirname "$HW_LAYOUT_OUT")"

BOOT_HW_LAYOUT="$BOOT_DIR/hw_layout.json"
HW_LAYOUT_SOURCE=""

if [ -f "$BOOT_HW_LAYOUT" ]; then
    # Imager-provided override wins — copy it verbatim, no scan.
    if cp "$BOOT_HW_LAYOUT" "$HW_LAYOUT_OUT" 2>>"$LOGFILE"; then
        chmod 0644 "$HW_LAYOUT_OUT" 2>>"$LOGFILE" || true
        chown "$TARGET_USER:$TARGET_USER" "$HW_LAYOUT_OUT" 2>>"$LOGFILE" || true
        HW_LAYOUT_SOURCE="imager-override"
        log_ok "HW layout: Imager-provided $BOOT_HW_LAYOUT → $HW_LAYOUT_OUT"
    else
        log_warn "HW layout: cp $BOOT_HW_LAYOUT failed — falling through to scan"
    fi
fi

if [ -z "$HW_LAYOUT_SOURCE" ]; then
    # Run the read-only detector. Capture rc separately so we can log the
    # specific failure mode (no /dev/i2c-1, no smbus2, bus held by another
    # process) without aborting the boot. The script is GUARANTEED not to
    # write to the I2C bus (ReadOnlySMBus wrapper raises AssertionError on
    # any write attempt + the test suite spies on that contract).
    DETECT_RC=0
    python3 "$REPO_PATH/scripts/detect_hats.py" \
        --output "$HW_LAYOUT_OUT" \
        --role "$ROLE" \
        --verbose 2>&1 | tee -a "$LOGFILE" || DETECT_RC=$?
    if [ "$DETECT_RC" -eq 0 ] && [ -s "$HW_LAYOUT_OUT" ]; then
        chmod 0644 "$HW_LAYOUT_OUT" 2>>"$LOGFILE" || true
        chown "$TARGET_USER:$TARGET_USER" "$HW_LAYOUT_OUT" 2>>"$LOGFILE" || true
        HW_LAYOUT_SOURCE="scan"
        log_ok "HW layout: scan completed → $HW_LAYOUT_OUT"
    else
        # DEGRADED — do NOT abort. Surface the rc so the operator can
        # diagnose via journalctl -u astromech-firstboot.
        # Exit code map (detect_hats.py::main):
        #   2 = smbus2 not installed         3 = /dev/i2c-N missing
        #   4 = permission denied            5 = bus lock held
        case "$DETECT_RC" in
            2) DETAIL="smbus2 not installed (apt install python3-smbus)" ;;
            3) DETAIL="/dev/i2c-1 missing (enable I2C in raspi-config)" ;;
            4) DETAIL="permission denied (user not in i2c group?)" ;;
            5) DETAIL="bus lock held (master.service running?)" ;;
            *) DETAIL="rc=$DETECT_RC, see log above" ;;
        esac
        log_warn "HW layout: detection failed — $DETAIL"
        log_warn "HW layout: services will boot in DEGRADED mode (no hw_layout.json)"
        log_warn "HW layout: review later with: journalctl -u astromech-firstboot"
    fi
fi

# ─── 5. DNA-validate + switch origin if a custom repo URL is set ────────
# Reads [github] repo_url from /boot/astromech_init.cfg first (the Imager's
# choice), falls back to local.cfg if already populated. Only swaps origin
# if validate_paternity passes.
CANDIDATE_URL=$(cfg_get github repo_url "")
CANDIDATE_BRANCH=$(cfg_get github branch "main")

if [ -n "$CANDIDATE_URL" ] && [ -d "$REPO_PATH/.git" ]; then
    # Find current origin URL (best effort — git remote in a freshly-imaged
    # repo may or may not be set yet)
    CURRENT_ORIGIN=$(git -C "$REPO_PATH" remote get-url origin 2>/dev/null || echo "")
    if [ "$CANDIDATE_URL" != "$CURRENT_ORIGIN" ]; then
        log "DNA validating candidate repo_url='$CANDIDATE_URL' branch='$CANDIDATE_BRANCH' ..."
        if dna_validate "$CANDIDATE_URL" "$CANDIDATE_BRANCH" 2>&1 | tee -a "$LOGFILE"; then
            log_ok "DNA OK — switching origin to $CANDIDATE_URL"
            git -C "$REPO_PATH" remote set-url origin "$CANDIDATE_URL"
            git -C "$REPO_PATH" fetch --no-tags origin "$CANDIDATE_BRANCH" \
                && git -C "$REPO_PATH" reset --hard "origin/$CANDIDATE_BRANCH" \
                && log_ok "Aligned to origin/$CANDIDATE_BRANCH" \
                || log_err "fetch+reset failed; origin URL still updated but tree not reset"
        else
            log_err "DNA FAIL — keeping origin pointed at: $CURRENT_ORIGIN"
            log_err "Candidate URL '$CANDIDATE_URL' is NOT a fork of RickDnamps/AstromechOS"
        fi
    else
        log_ok "github.repo_url matches current origin — no switch needed"
    fi
else
    log "Skipping repo switch: candidate='$CANDIDATE_URL' .git present=$([ -d "$REPO_PATH/.git" ] && echo y || echo n)"
fi

# ─── 6. Self-destruct + reboot ──────────────────────────────────────────
log "Cleaning up first-boot artefacts ..."

# Delete the secrets directory. Best-effort `shred` for the private key
# before unlinking, then rm -rf the parent dir.
if [ -d "$SECRETS_DIR" ]; then
    for f in "$SECRETS_DIR"/id_* "$SECRETS_DIR"/authorized_keys; do
        [ -f "$f" ] && shred -u "$f" 2>/dev/null || rm -f "$f" 2>/dev/null || true
    done
    rm -rf "$SECRETS_DIR" 2>/dev/null && log_ok "Secrets directory wiped" \
        || log_warn "Could not fully remove $SECRETS_DIR — check /boot perms"
fi

# Delete the trigger LAST — if anything above failed catastrophically the
# operator can re-trigger by re-creating the marker.
rm -f "$TRIGGER" && log_ok "Trigger marker deleted ($TRIGGER)" \
    || log_err "Could not delete trigger $TRIGGER — script will re-run on next boot"

# Also disable our own systemd unit so it doesn't even try next boot.
systemctl disable astromech-firstboot.service 2>/dev/null || true

sync
log_ok "First-boot provisioning complete — rebooting in 5s"
log "=========================================="
sleep 5
reboot
