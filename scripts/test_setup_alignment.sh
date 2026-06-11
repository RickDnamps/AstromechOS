#!/usr/bin/env bash
# test_setup_alignment.sh
#
# Smoke checks that scripts/setup_master.sh and scripts/setup_slave.sh stay
# aligned with the runtime fixes shipped in main. Cheaper than full sandbox
# integration: we just grep for the LOAD-BEARING lines that, if removed,
# would silently regress the fresh-install path back to a pre-fix state.
#
# Covers:
#   - rpi-resize.service enabled at install time (Pi OS ships it disabled,
#     our triple-defense rootfs resize needs it ON)
#   - pair-sealing .path unit installed + enabled on Master (commit 9cc150b)
#   - lib_config.sh sourced (provides install_service_template, capture_user,
#     write_local_cfg parent-owner chown — commits 1973566 + 327085f effects)
#
# Run from any dir:
#   bash scripts/test_setup_alignment.sh
#
# Exit 0 = all checks pass. Exit 1 = at least one regression detected.

set -u

PASS=0
FAIL=0
FAILED=()

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$TEST_DIR/.." && pwd)"

MASTER="$REPO/scripts/setup_master.sh"
SLAVE="$REPO/scripts/setup_slave.sh"
WLAN="$REPO/scripts/astromech_wlan_setup.sh"
MASTER_NET="$REPO/scripts/setup_master_network.sh"
FIRSTBOOT_UNIT="$REPO/master/services/astromech-firstboot.service.template"
WLAN_UNIT="$REPO/master/services/astromech-wlan-setup.service.template"
LIB_CONFIG="$REPO/scripts/lib_config.sh"
UPDATE_SH="$REPO/scripts/update.sh"
MASTER_MAIN="$REPO/master/main.py"

assert_grep() {
    local label="$1" file="$2" pattern="$3"
    if grep -qE "$pattern" "$file"; then
        PASS=$((PASS+1))
        echo "  [PASS] $label"
    else
        FAIL=$((FAIL+1))
        FAILED+=("$label")
        echo "  [FAIL] $label"
        echo "         file:    $file"
        echo "         pattern: $pattern"
    fi
}

assert_no_grep() {
    local label="$1" file="$2" pattern="$3"
    if grep -qE "$pattern" "$file"; then
        FAIL=$((FAIL+1))
        FAILED+=("$label")
        echo "  [FAIL] $label (unexpectedly found)"
        echo "         file:    $file"
        echo "         pattern: $pattern"
    else
        PASS=$((PASS+1))
        echo "  [PASS] $label"
    fi
}

echo "================================================================"
echo "setup_master.sh + setup_slave.sh — alignment smoke checks"
echo "================================================================"

# ── rpi-resize.service stays out of setup_*.sh; lives in clean_for_imager.sh ─
# On a fresh Pi OS install via rpi-imager, the FS is already grown before
# setup_*.sh runs (rpi-imager triggers the resize on the user's behalf).
# rpi-resize.service enable belongs to the Golden Image build prep, which is
# scripts/clean_for_imager.sh — that's the script the operator runs before
# DD'ing the master+slave for a pishrunk Golden Image.
CLEAN="$REPO/scripts/clean_for_imager.sh"
echo ""
echo "rpi-resize.service handling (per role):"
assert_grep "clean_for_imager.sh enables rpi-resize"      "$CLEAN"  'systemctl enable rpi-resize\.service'
assert_no_grep "setup_master.sh does NOT enable rpi-resize" "$MASTER" 'systemctl enable rpi-resize\.service'
assert_no_grep "setup_slave.sh does NOT enable rpi-resize"  "$SLAVE"  'systemctl enable rpi-resize\.service'

# ── firstboot re-enable before DD (2026-06-10 root cause: no-AP on fresh flash) ──
# firstboot_setup.sh self-disables astromech-firstboot at the end of its first
# run, so the canonical (flashed + firstboot-completed) DD source has it
# DISABLED. clean_for_imager.sh MUST re-enable it before DD or every flashed
# card boots with firstboot disabled → no hotspot, no pairing. Autopsy-confirmed
# on a flashed master SD: multi-user.target.wants/astromech-firstboot.service
# was MISSING. The enable MUST be fail-loud (abort prep) so a broken Golden
# Image can never ship silently again.
echo ""
echo "firstboot re-enable before DD (no-AP regression guard):"
assert_grep "clean_for_imager.sh re-enables astromech-firstboot" \
    "$CLEAN" 'systemctl enable astromech-firstboot\.service'
assert_grep "clean_for_imager.sh fail-loud verifies the firstboot enable symlink" \
    "$CLEAN" 'multi-user\.target\.wants/astromech-firstboot\.service'
assert_grep "firstboot_setup.sh self-disables firstboot after first run (why re-enable is needed)" \
    "$REPO/scripts/firstboot_setup.sh" 'systemctl disable astromech-firstboot\.service'

# ── pair-sealing (commit 9cc150b) ────────────────────────────────────
echo ""
echo "pair-sealing install (9cc150b):"
assert_grep "master installs pair-sealing.service template" "$MASTER" 'astromech-pair-sealing\.service\.template'
assert_grep "master installs pair-sealing.path template"    "$MASTER" 'astromech-pair-sealing\.path\.template'
assert_grep "master enables pair-sealing.path"              "$MASTER" 'systemctl enable.*astromech-pair-sealing\.path'
# The .service must NOT be enabled directly — the .path triggers it.
assert_no_grep "master does NOT enable pair-sealing.service directly" "$MASTER" 'systemctl enable[^|]*astromech-pair-sealing\.service([^.]|$)'

# ── pair-sealing timer fallback (2026-06-08 fix) ─────────────────────
# Bug verified live 2026-06-08: inotify events on the dnsmasq leases file
# can be MISSED (slave joins during .path startup, dnsmasq writes via
# atomic rename → no MODIFY event). astromech-pair-sealing.timer is a
# belt-and-suspenders fallback that retries the .service every 60s while
# the marker is absent. The script (astromech_pair_sealing.sh:59) exits
# 0 immediately if the marker already exists, so timer ticks are
# cheap no-ops once paired.
PAIR_TIMER_UNIT="$REPO/master/services/astromech-pair-sealing.timer.template"
echo ""
echo "pair-sealing timer fallback (2026-06-08 fix):"
assert_grep "setup_master.sh installs astromech-pair-sealing.timer.template" \
    "$MASTER" 'astromech-pair-sealing\.timer\.template'
assert_grep "setup_master.sh enables astromech-pair-sealing.timer" \
    "$MASTER" 'systemctl enable.*astromech-pair-sealing\.timer'
assert_grep "pair-sealing.timer has Unit=astromech-pair-sealing.service" \
    "$PAIR_TIMER_UNIT" '^Unit=astromech-pair-sealing\.service'
assert_grep "pair-sealing.timer has OnUnitInactiveSec=60sec (retry cadence)" \
    "$PAIR_TIMER_UNIT" '^OnUnitInactiveSec=60sec'
assert_grep "pair-sealing.timer has WantedBy=timers.target" \
    "$PAIR_TIMER_UNIT" '^WantedBy=timers\.target'

# ── pair-sealing hardening (2026-06-11, software-4rs) ────────────────
# Live first-flashed-pair boot: boot dnsmasq churn trigger-limited the .path
# into permanent 'failed', and the sealed robot's .timer ticked a skipped
# .service every 60s forever. Guards below lock the three-part fix.
PAIR_PATH_UNIT="$REPO/master/services/astromech-pair-sealing.path.template"
echo ""
echo "pair-sealing hardening (2026-06-11):"
assert_grep "pair-sealing.path burst raised to 20 (boot-churn headroom)" \
    "$PAIR_PATH_UNIT" '^TriggerLimitBurst=20'
assert_grep "pair-sealing.timer gated on !pair_sealed (no eternal ticks on sealed robots)" \
    "$PAIR_TIMER_UNIT" '^ConditionPathExists=!/var/lib/astromech/pair_sealed'
assert_grep "sealing script quiesces trigger units after writing the marker" \
    "$REPO/scripts/astromech_pair_sealing.sh" 'systemctl stop --no-block astromech-pair-sealing\.path astromech-pair-sealing\.timer'
assert_grep "firstboot clears stale trigger-limit failed state before enabling" \
    "$REPO/scripts/firstboot_setup.sh" 'systemctl reset-failed astromech-pair-sealing\.path'

# ── firstboot root-git safe.directory (2026-06-11, software-fhl) ─────
echo ""
echo "firstboot root-git handling (2026-06-11):"
assert_grep "firstboot whitelists the repo for root git (safe.directory)" \
    "$REPO/scripts/firstboot_setup.sh" 'git config --global --add safe\.directory'
assert_grep "firstboot chowns the repo back to TARGET_USER after root git ops" \
    "$REPO/scripts/firstboot_setup.sh" 'chown -R "\$TARGET_USER:\$TARGET_USER" "\$REPO_PATH"'

# ── per-deployment lifecycle marker wipe pre-DD (2026-06-11) ─────────
# Without this, a Golden Image DD'd from a SEALED builder pair ships with
# pair_sealed baked in → fresh flashes never seal (bootstrap SSID forever).
echo ""
echo "pre-DD lifecycle marker wipe (2026-06-11):"
assert_grep "clean_for_imager.sh wipes pair_sealed pre-DD" \
    "$CLEAN" 'pair_sealed'
assert_grep "clean_for_imager.sh wipes runcmd_done pre-DD" \
    "$CLEAN" 'runcmd_done'

# ── lib_config.sh sourced (carries chown fixes 1973566 + 327085f) ────
echo ""
echo "lib_config.sh sourced (carries chown fixes):"
assert_grep "master sources lib_config.sh" "$MASTER" '\. .*lib_config\.sh'
assert_grep "slave sources lib_config.sh"  "$SLAVE"  '\. .*lib_config\.sh'

# ── capture_user called (no hardcoded astromech) ─────────────────────
echo ""
echo "capture_user called (username-agnostic install):"
assert_grep "master calls capture_user" "$MASTER" 'capture_user'
assert_grep "slave calls capture_user"  "$SLAVE"  'capture_user'

# ── wlan_setup SOURCE=boot split (bug fix 2026-06-05) ────────────────
# astromech_wlan_setup.sh must:
#   - have a PROFILE_EXISTS guard split by SOURCE
#   - skip-on-exist must be GATED on SOURCE != boot (no unconditional exit 0)
#   - perform an nmcli connection modify when SOURCE=boot + profile exists
echo ""
echo "astromech_wlan_setup.sh SOURCE=boot split (2026-06-05 fix):"
assert_grep "wlan_setup: PROFILE_EXISTS guard introduced" "$WLAN" 'PROFILE_EXISTS=1'
assert_grep "wlan_setup: skip is gated on SOURCE != boot" "$WLAN" 'PROFILE_EXISTS.*=.*"1".*SOURCE.*!=.*"boot"'
assert_grep "wlan_setup: uses nmcli connection modify when updating" "$WLAN" 'nmcli connection modify astromech-internet'
assert_no_grep "wlan_setup: NO unconditional skip on profile-exists" "$WLAN" "Profile 'astromech-internet' already exists — no-op \(idempotent\)$"

# ── clean_for_imager.sh wipes per-deployment state (bug fix 2026-06-05) ──
# clean_for_imager.sh must wipe NM profiles + SSH key state pre-DD so the
# Golden Image never carries builder-Pi-specific deployment state into a
# fresh flash (root cause of the wlan_setup idempotency + slave
# authorized_keys merge bugs verified live 2026-06-05).
echo ""
echo "clean_for_imager.sh wipes per-deployment state (2026-06-05 fix):"
assert_grep "clean_for_imager: wipes astromech-internet.nmconnection" "$CLEAN" 'astromech-internet'
assert_grep "clean_for_imager: wipes astromech-hotspot.nmconnection"  "$CLEAN" 'astromech-hotspot'
assert_grep "clean_for_imager: wipes astromech-master-hotspot.nmconnection" "$CLEAN" 'astromech-master-hotspot'
assert_grep "clean_for_imager: wipes ~/.ssh/authorized_keys"  "$CLEAN" 'authorized_keys'
assert_grep "clean_for_imager: wipes ~/.ssh/id_ed25519"        "$CLEAN" 'id_ed25519'
assert_grep "clean_for_imager: wipes ~/.ssh/id_ed25519.pub"    "$CLEAN" 'id_ed25519\.pub'

# ── setup_master_network.sh Step 1 priority order (bug fix 2026-06-05) ─
# Step 1 must resolve HOME_SSID/HOME_PASS via a 4-tier priority order:
#   1) /boot/firmware/astromech_wlan.conf (Imager bake)
#   2) --home-ssid / --home-psk flags
#   3) wlan0 active connection IF in client (infrastructure) mode
#   4) Interactive prompt
# Root cause of bug: previous code did an UNCONDITIONAL wlan0 read at Step 1,
# which on a legacy Master (wlan0 = AP/hotspot) snapshotted the HOTSPOT SSID
# into local.cfg [home_wifi] and seeded a stale astromech-internet profile
# into every Golden Image. Mode-check fixes this third defense layer.
echo ""
echo "setup_master_network.sh Step 1 priority order (2026-06-05 fix):"
assert_grep "master_network: Priority 1 reads /boot/firmware/astromech_wlan.conf" \
    "$MASTER_NET" '_WLAN_CONF="/boot/firmware/astromech_wlan\.conf"'
assert_grep "master_network: Priority 1 falls back to legacy /boot/astromech_wlan.conf" \
    "$MASTER_NET" '_WLAN_CONF="/boot/astromech_wlan\.conf"'
assert_grep "master_network: Priority 1 awk-parses [home_wifi] ssid" \
    "$MASTER_NET" '\[home_wifi\]'
assert_grep "master_network: Priority 3 checks wlan0 802-11-wireless.mode" \
    "$MASTER_NET" 'WLAN0_MODE=.*nmcli.*802-11-wireless\.mode'
assert_grep "master_network: Priority 3 skips wlan0 read when mode = ap" \
    "$MASTER_NET" 'WLAN0_MODE.*=.*"ap"'
assert_grep "master_network: Priority 3 read is gated on HOME_SSID empty" \
    "$MASTER_NET" 'if \[ -z "\$HOME_SSID" \]'
# Ensure the OLD unconditional read path is gone: there must be no nmcli
# 802-11-wireless.ssid read on wlan0 outside an HOME_SSID empty + mode-check
# guard. The old structure had the SSID read at top-level (no if-z guard
# around the WLAN0_CON discovery, and no mode check before the SSID read).
assert_no_grep "master_network: NO unconditional wlan0 SSID read (old bug path)" \
    "$MASTER_NET" 'Step 1 — Reading home WiFi credentials \(current wlan0\)\.\.\.'

# ── systemd unit ordering vs cloud-init (bug fix 2026-06-06 REVERT) ──
# Initial fix added After=cloud-final.service to firstboot + wlan-setup
# to order them after the Imager-baked cloud-init runcmd scrub. Live
# SD-USB autopsy 2026-06-06 proved this CREATED a dependency cycle:
#   cloud-final.service:    After=multi-user.target
#   astromech-firstboot:    WantedBy=multi-user.target + After=cloud-final
# systemd detected the cycle and silently dropped firstboot from the
# boot transaction (firstboot.log absent, trigger marker still present,
# NM profiles empty). The Imager now bakes the scrub as bootcmd instead
# of runcmd — bootcmd runs at cloud-init-local (uptime ~7s, before
# NetworkManager), so no race with firstboot. After=cloud-final is
# unnecessary AND harmful; assert it stays out.
echo ""
echo "systemd unit ordering vs cloud-init (2026-06-06 REVERT):"
assert_no_grep "firstboot service does NOT have After=cloud-final.service" \
    "$FIRSTBOOT_UNIT" '^After=.*cloud-final\.service'
assert_no_grep "wlan-setup service does NOT have After=cloud-final.service" \
    "$WLAN_UNIT" '^After=.*cloud-final\.service'
# Defensive: don't regress the pre-existing ordering directives.
assert_grep "firstboot service still has After=network-online.target" \
    "$FIRSTBOOT_UNIT" '^After=.*network-online\.target'
assert_grep "firstboot service still has Before=astromech-master.service astromech-slave.service" \
    "$FIRSTBOOT_UNIT" '^Before=astromech-master\.service astromech-slave\.service'

# ── slave installs astromech-firstboot.service (bug fix 2026-06-06) ──
# Verified live via SD-USB autopsy 2026-06-06: the slave Golden Image was
# missing /etc/systemd/system/astromech-firstboot.service entirely. Without
# firstboot, the slave never reads /boot/firmware/astromech_secrets/
# authorized_keys → master can't SSH to slave with key auth → pair-sealing
# breaks. Fix: setup_slave.sh installs + enables the shared firstboot
# template (master and slave use the same template; firstboot_setup.sh is
# role-aware via /boot/firmware/astromech_init.cfg).
echo ""
echo "slave installs astromech-firstboot.service (2026-06-06 fix):"
assert_grep "setup_slave.sh installs astromech-firstboot.service" \
    "$SLAVE" 'install_service_template.*astromech-firstboot\.service\.template.*astromech-firstboot\.service'
assert_grep "setup_slave.sh enables astromech-firstboot" \
    "$SLAVE" 'systemctl enable astromech-firstboot'
# Defensive: don't lose the existing slave service install path
# (deploy.sh --first-install installs astromech-slave.service via SSH).
assert_grep "deploy.sh --first-install still installs astromech-slave.service" \
    "$REPO/scripts/deploy.sh" 'astromech-slave\.service\.template|astromech-slave astromech-version|astromech-version astromech-slave'

# ── auto-reinstall systemd unit templates after pull (bug fix 2026-06-06) ──
# Bug verified live 2026-06-06: a git pull updated *.service.template files
# (e.g. commit 3065d6c added After=cloud-final.service) but the installed
# /etc/systemd/system/<unit>.service stayed STALE because
# install_service_template was never re-run. DD'ing that stale legacy
# into a Golden Image propagated the race to every flashed Pi.
# Fix: reinstall_changed_service_templates diffs each rendered template
# against the installed unit and re-runs install_service_template only
# for changed ones. Invoked from both update.sh and main.py::try_git_pull
# so EVERY pull path closes the drift.
echo ""
echo "auto-reinstall systemd unit templates after pull (2026-06-06 fix):"
assert_grep "lib_config.sh defines reinstall_changed_service_templates" \
    "$LIB_CONFIG" '^reinstall_changed_service_templates\(\)'
assert_grep "update.sh calls reinstall_changed_service_templates" \
    "$UPDATE_SH" 'reinstall_changed_service_templates'
assert_grep "main.py references reinstall_changed_service_templates" \
    "$MASTER_MAIN" 'reinstall_changed_service_templates'

echo ""
echo "================================================================"
echo "Results: $PASS passed, $FAIL failed"
echo "================================================================"
if [ "$FAIL" -gt 0 ]; then
    echo "Failed checks:"
    for t in "${FAILED[@]}"; do
        echo "  - $t"
    done
    exit 1
fi
exit 0
