#!/usr/bin/env bash
# test_setup_master_network_cfg_set.sh
#
# Regression test for scripts/setup_master_network.sh::cfg_set — pins the
# section-scoped sed invariant introduced 2026-06-06 after live SD-USB
# autopsy proved the previous global sed was leaking passwords across
# [admin] / [home_wifi] / [hotspot] / [deploy] sections of local.cfg.
#
# Strategy: extract the cfg_set function definition out of the install
# script with sed, eval it into THIS shell, then exercise it against a
# series of throw-away temp files. setup_master_network.sh itself runs
# `set -e` + root checks + nmcli at module load and CANNOT be sourced
# directly; cfg_set is pure (no side effects beyond $file) so eval'ing
# it in isolation is safe.
#
# Run from any dir:
#   bash scripts/test_setup_master_network_cfg_set.sh
#
# Exit 0 = all tests pass. Exit 1 = at least one test failed.

set -u

PASS=0
FAIL=0
FAILED_TESTS=()

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$TEST_DIR/.." && pwd)"
SUT="$REPO/scripts/setup_master_network.sh"

if [ ! -f "$SUT" ]; then
    echo "[ERR] $SUT not found — run from a checked-out repo" >&2
    exit 1
fi

# Extract the cfg_set() definition. The function spans from the line
# `cfg_set() {` to the next standalone closing brace (`^}$`). Eval the
# block into this shell so we can call it directly.
CFG_SET_SRC="$(sed -n '/^cfg_set() {$/,/^}$/p' "$SUT")"
if [ -z "$CFG_SET_SRC" ]; then
    echo "[ERR] could not extract cfg_set() from $SUT" >&2
    exit 1
fi
# shellcheck disable=SC2086
eval "$CFG_SET_SRC"

# Verify the function is now in scope.
if ! declare -F cfg_set >/dev/null; then
    echo "[ERR] cfg_set not in scope after eval" >&2
    exit 1
fi

TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

assert_line() {
    # assert_line "<label>" "<file>" "<exact line that MUST be present>"
    local label="$1" file="$2" line="$3"
    if grep -Fxq "$line" "$file"; then
        PASS=$((PASS+1))
        echo "  [PASS] $label"
    else
        FAIL=$((FAIL+1))
        FAILED_TESTS+=("$label")
        echo "  [FAIL] $label"
        echo "         expected line: '$line'"
        echo "         file contents:"
        sed 's/^/           | /' "$file"
    fi
}

assert_no_line() {
    # assert_no_line "<label>" "<file>" "<exact line that MUST be absent>"
    local label="$1" file="$2" line="$3"
    if grep -Fxq "$line" "$file"; then
        FAIL=$((FAIL+1))
        FAILED_TESTS+=("$label")
        echo "  [FAIL] $label (unexpectedly found)"
        echo "         forbidden line: '$line'"
        echo "         file contents:"
        sed 's/^/           | /' "$file"
    else
        PASS=$((PASS+1))
        echo "  [PASS] $label"
    fi
}

assert_count() {
    # assert_count "<label>" "<file>" "<regex>" "<expected count>"
    local label="$1" file="$2" pattern="$3" expected="$4"
    local actual
    actual=$(grep -c -E "$pattern" "$file" || true)
    if [ "$actual" = "$expected" ]; then
        PASS=$((PASS+1))
        echo "  [PASS] $label"
    else
        FAIL=$((FAIL+1))
        FAILED_TESTS+=("$label")
        echo "  [FAIL] $label"
        echo "         pattern:  $pattern"
        echo "         expected: $expected match(es)"
        echo "         actual:   $actual match(es)"
        echo "         file contents:"
        sed 's/^/           | /' "$file"
    fi
}

echo "================================================================"
echo "setup_master_network.sh :: cfg_set — section-scoped sed checks"
echo "================================================================"

# ──────────────────────────────────────────────────────────────────────
# Test 1 — THE CORE FIX
# cfg_set hotspot password Y must NOT touch [admin] password.
# ──────────────────────────────────────────────────────────────────────
echo ""
echo "Test 1 — [admin] password is preserved when [hotspot] password changes:"
T1="$TMPDIR/t1.cfg"
cat > "$T1" <<'EOF'
[admin]
password = astro

[hotspot]
ssid = Astromech-1609
password = bootstrap_pw
EOF
cfg_set "$T1" "hotspot" "password" "r2d2droid"

assert_line "T1: [admin] password = astro UNCHANGED" \
    "$T1" "password = astro"
assert_line "T1: [hotspot] password = r2d2droid set" \
    "$T1" "password = r2d2droid"
assert_no_line "T1: bootstrap_pw is gone" \
    "$T1" "password = bootstrap_pw"
# Exactly two 'password = ' lines (one per section), neither equal to the other.
assert_count "T1: exactly 2 password lines (one per section)" \
    "$T1" "^password = " "2"

# ──────────────────────────────────────────────────────────────────────
# Test 2 — Multi-section SSID isolation
# cfg_set home_wifi ssid mywifi2 must NOT touch [hotspot] ssid.
# ──────────────────────────────────────────────────────────────────────
echo ""
echo "Test 2 — [hotspot] ssid is preserved when [home_wifi] ssid changes:"
T2="$TMPDIR/t2.cfg"
cat > "$T2" <<'EOF'
[hotspot]
ssid = Astromech-XXXX
password = r2d2droid

[home_wifi]
ssid = old_home
password = oldpass
EOF
cfg_set "$T2" "home_wifi" "ssid" "mywifi2"

assert_line "T2: [hotspot] ssid = Astromech-XXXX UNCHANGED" \
    "$T2" "ssid = Astromech-XXXX"
assert_line "T2: [home_wifi] ssid = mywifi2 set" \
    "$T2" "ssid = mywifi2"
assert_no_line "T2: old_home is gone" \
    "$T2" "ssid = old_home"

# ──────────────────────────────────────────────────────────────────────
# Test 3 — Section absent → appended at EOF
# ──────────────────────────────────────────────────────────────────────
echo ""
echo "Test 3 — Absent section is created at EOF:"
T3="$TMPDIR/t3.cfg"
cat > "$T3" <<'EOF'
[admin]
password = astro
EOF
cfg_set "$T3" "deploy" "branch" "main"

assert_line "T3: [deploy] section created" "$T3" "[deploy]"
assert_line "T3: deploy branch = main written" "$T3" "branch = main"
assert_line "T3: [admin] password = astro UNCHANGED" \
    "$T3" "password = astro"

# ──────────────────────────────────────────────────────────────────────
# Test 4 — Key absent within existing section → appended after header
# ──────────────────────────────────────────────────────────────────────
echo ""
echo "Test 4 — Absent key in existing section appended after header:"
T4="$TMPDIR/t4.cfg"
cat > "$T4" <<'EOF'
[hotspot]
ssid = Astromech-XXXX

[home_wifi]
ssid = home
password = homepass
EOF
cfg_set "$T4" "hotspot" "password" "newpw"

assert_line "T4: [hotspot] password = newpw appended" \
    "$T4" "password = newpw"
assert_line "T4: [home_wifi] password = homepass UNCHANGED" \
    "$T4" "password = homepass"
# Exactly two 'password = ' lines exist, each scoped to its section.
assert_count "T4: exactly 2 password lines (one per section)" \
    "$T4" "^password = " "2"

# ──────────────────────────────────────────────────────────────────────
# Test 5 — Empty value overwrites correctly + section isolation
# ──────────────────────────────────────────────────────────────────────
echo ""
echo "Test 5 — Empty value overwrites only the targeted section's key:"
T5="$TMPDIR/t5.cfg"
cat > "$T5" <<'EOF'
[admin]
password = astro

[home_wifi]
ssid = home
password = homepass

[hotspot]
ssid = Astromech-XXXX
password = bootstrap
EOF
cfg_set "$T5" "home_wifi" "password" ""

assert_line "T5: [home_wifi] password is now empty" \
    "$T5" "password = "
assert_line "T5: [admin] password = astro UNCHANGED" \
    "$T5" "password = astro"
assert_line "T5: [hotspot] password = bootstrap UNCHANGED" \
    "$T5" "password = bootstrap"
assert_no_line "T5: old homepass is gone" \
    "$T5" "password = homepass"

# ──────────────────────────────────────────────────────────────────────
# Test 6 — Simulate the real-world failure mode that triggered this fix:
# the 4-call sequence from setup_master_network.sh Step 2 must end with
# every section holding its own creds.
# ──────────────────────────────────────────────────────────────────────
echo ""
echo "Test 6 — Real-world 4-call sequence keeps every section isolated:"
T6="$TMPDIR/t6.cfg"
cat > "$T6" <<'EOF'
[admin]
password = astro

[deploy]
password = deploypw

[home_wifi]
ssid = placeholder
password = placeholder

[hotspot]
ssid = placeholder
password = placeholder
EOF
cfg_set "$T6" "home_wifi" "ssid"     "mywifi2"
cfg_set "$T6" "home_wifi" "password" "1976198000"
cfg_set "$T6" "hotspot"   "ssid"     "Astromech-1609"
cfg_set "$T6" "hotspot"   "password" "r2d2droid"

assert_line "T6: [admin] password = astro PRESERVED" \
    "$T6" "password = astro"
assert_line "T6: [deploy] password = deploypw PRESERVED" \
    "$T6" "password = deploypw"
assert_line "T6: [home_wifi] ssid = mywifi2" \
    "$T6" "ssid = mywifi2"
assert_line "T6: [home_wifi] password = 1976198000" \
    "$T6" "password = 1976198000"
assert_line "T6: [hotspot] ssid = Astromech-1609" \
    "$T6" "ssid = Astromech-1609"
assert_line "T6: [hotspot] password = r2d2droid" \
    "$T6" "password = r2d2droid"
# Four distinct 'password = ' lines (admin, deploy, home_wifi, hotspot).
assert_count "T6: exactly 4 password lines (one per section)" \
    "$T6" "^password = " "4"

echo ""
echo "================================================================"
echo "Results: $PASS passed, $FAIL failed"
echo "================================================================"
if [ "$FAIL" -gt 0 ]; then
    echo "Failed tests:"
    for t in "${FAILED_TESTS[@]}"; do
        echo "  - $t"
    done
    exit 1
fi
exit 0
