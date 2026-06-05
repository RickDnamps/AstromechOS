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

# ── pair-sealing (commit 9cc150b) ────────────────────────────────────
echo ""
echo "pair-sealing install (9cc150b):"
assert_grep "master installs pair-sealing.service template" "$MASTER" 'astromech-pair-sealing\.service\.template'
assert_grep "master installs pair-sealing.path template"    "$MASTER" 'astromech-pair-sealing\.path\.template'
assert_grep "master enables pair-sealing.path"              "$MASTER" 'systemctl enable.*astromech-pair-sealing\.path'
# The .service must NOT be enabled directly — the .path triggers it.
assert_no_grep "master does NOT enable pair-sealing.service directly" "$MASTER" 'systemctl enable[^|]*astromech-pair-sealing\.service([^.]|$)'

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
