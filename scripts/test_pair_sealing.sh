#!/usr/bin/env bash
# test_pair_sealing.sh
#
# Unit tests for scripts/astromech_pair_sealing.sh. Mocks nmcli / ssh / ping
# / gen_hotspot_ssid.sh / sudo / chown via PATH override into a temp dir,
# and overrides MARKER_DIR + LOCAL_CFG_PATH via env so we don't touch the
# real /var/lib/astromech or master/config/local.cfg.
#
# We override the sealing script's hardcoded paths by re-exporting them
# AFTER the script's `MARKER_DIR=` assignment via a wrapper that source's
# the script — but the script is designed to be exec'd, not sourced.
# Instead we exploit the fact that the script uses MARKER_DIR/MARKER vars
# computed AT runtime and writes via mkdir/touch — we can redirect the
# WHOLE filesystem view it has by chrooting MARKER_DIR/LOGFILE writes into
# our temp dir using a small wrapper that pre-creates a fake repo + cfg
# layout and runs the script with REPO_PATH override.
#
# Run from any dir:
#   bash scripts/test_pair_sealing.sh
#
# Exit 0 = all tests pass. Exit 1 = at least one test failed.

set -u

PASS=0
FAIL=0
FAILED_TESTS=()

# Compute the real repo path (parent of this script's dir).
TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REAL_REPO="$(cd "$TEST_DIR/.." && pwd)"
REAL_SCRIPT="$REAL_REPO/scripts/astromech_pair_sealing.sh"

if [ ! -f "$REAL_SCRIPT" ]; then
    echo "[ERR] $REAL_SCRIPT not found — run from a checked-out repo" >&2
    exit 1
fi

# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

assert_eq() {
    local label="$1" expected="$2" actual="$3"
    if [ "$expected" = "$actual" ]; then
        PASS=$((PASS+1))
        echo "  [PASS] $label"
    else
        FAIL=$((FAIL+1))
        FAILED_TESTS+=("$label")
        echo "  [FAIL] $label"
        echo "         expected: '$expected'"
        echo "         actual:   '$actual'"
    fi
}

assert_file_exists() {
    local label="$1" path="$2"
    if [ -e "$path" ]; then
        PASS=$((PASS+1))
        echo "  [PASS] $label (exists: $path)"
    else
        FAIL=$((FAIL+1))
        FAILED_TESTS+=("$label")
        echo "  [FAIL] $label (missing: $path)"
    fi
}

assert_file_absent() {
    local label="$1" path="$2"
    if [ ! -e "$path" ]; then
        PASS=$((PASS+1))
        echo "  [PASS] $label (absent: $path)"
    else
        FAIL=$((FAIL+1))
        FAILED_TESTS+=("$label")
        echo "  [FAIL] $label (unexpectedly exists: $path)"
    fi
}

# Build a sandbox per test:
#   $SANDBOX/repo/scripts/astromech_pair_sealing.sh   (copy of real, patched
#                                                      for sandbox marker dir)
#   $SANDBOX/repo/scripts/lib_config.sh               (copy of real)
#   $SANDBOX/repo/scripts/gen_hotspot_ssid.sh         (MOCK)
#   $SANDBOX/repo/master/config/local.cfg             (test fixture)
#   $SANDBOX/bin/{nmcli,ssh,ping,sudo,chown,stat}     (MOCKS via PATH override)
#   $SANDBOX/var/lib/astromech/                       (marker dir override)
#
# We patch the script in-place to swap /var/lib/astromech and
# /var/log/astromech-pair-sealing.log to sandbox paths. This is a unit
# test, not an integration test — we're verifying CONTROL FLOW + exit
# codes + side effects, not real systemd integration.

setup_sandbox() {
    SANDBOX="$(mktemp -d)"
    mkdir -p "$SANDBOX/repo/scripts" "$SANDBOX/repo/master/config" "$SANDBOX/bin" \
             "$SANDBOX/var/lib/astromech" "$SANDBOX/var/log" "$SANDBOX/calls"

    # Copy real lib_config.sh (script source's it).
    cp "$REAL_REPO/scripts/lib_config.sh" "$SANDBOX/repo/scripts/lib_config.sh"

    # Copy and patch the sealing script: redirect MARKER_DIR + LOGFILE.
    sed -e "s|/var/lib/astromech|$SANDBOX/var/lib/astromech|g" \
        -e "s|/var/log/astromech-pair-sealing.log|$SANDBOX/var/log/astromech-pair-sealing.log|g" \
        "$REAL_SCRIPT" > "$SANDBOX/repo/scripts/astromech_pair_sealing.sh"
    chmod +x "$SANDBOX/repo/scripts/astromech_pair_sealing.sh"

    # Mock gen_hotspot_ssid.sh — yields a deterministic test SSID.
    cat > "$SANDBOX/repo/scripts/gen_hotspot_ssid.sh" <<'GEN'
#!/usr/bin/env bash
echo "Astromech-TEST"
GEN
    chmod +x "$SANDBOX/repo/scripts/gen_hotspot_ssid.sh"

    # local.cfg fixture with [hotspot] section + slave host.
    cat > "$SANDBOX/repo/master/config/local.cfg" <<CFG
[slave]
host = test-slave.local
user = testuser

[hotspot]
ssid = Astromech-BOOT
password = testpassword123
CFG

    # ── Default mocks (per-test override via re-writing the file). ────
    # Each mock records its invocation to $SANDBOX/calls/<name>.log so we
    # can assert which commands were called.

    # ping: by default, succeed.
    cat > "$SANDBOX/bin/ping" <<PING
#!/usr/bin/env bash
echo "ping \$*" >> "$SANDBOX/calls/ping.log"
exit \${MOCK_PING_EXIT:-0}
PING
    chmod +x "$SANDBOX/bin/ping"

    # ssh: by default, succeed (probe + push both).
    cat > "$SANDBOX/bin/ssh" <<SSH
#!/usr/bin/env bash
echo "ssh \$*" >> "$SANDBOX/calls/ssh.log"
exit \${MOCK_SSH_EXIT:-0}
SSH
    chmod +x "$SANDBOX/bin/ssh"

    # nmcli: by default, return current SSID = bootstrap (so flip is needed)
    # and accept modify/up. The script also reads .psk via -s -g — return
    # the bootstrap PSK there too.
    cat > "$SANDBOX/bin/nmcli" <<NMCLI
#!/usr/bin/env bash
echo "nmcli \$*" >> "$SANDBOX/calls/nmcli.log"
case "\$*" in
    *"-t -f 802-11-wireless.ssid connection show astromech-hotspot"*)
        echo "\${MOCK_NMCLI_CURRENT_SSID:-802-11-wireless.ssid:Astromech-BOOT}"
        ;;
    *"-s -g 802-11-wireless-security.psk connection show astromech-hotspot"*)
        echo "\${MOCK_NMCLI_PSK:-testpassword123}"
        ;;
    *"connection modify"*|*"connection up"*)
        exit \${MOCK_NMCLI_MOD_EXIT:-0}
        ;;
esac
exit 0
NMCLI
    chmod +x "$SANDBOX/bin/nmcli"

    # sudo: passthrough (no-op the auth check, exec the rest).
    cat > "$SANDBOX/bin/sudo" <<SUDO
#!/usr/bin/env bash
echo "sudo \$*" >> "$SANDBOX/calls/sudo.log"
shift  # drop -n if present
while [ "\$1" = "-n" ]; do shift; done
exec "\$@"
SUDO
    chmod +x "$SANDBOX/bin/sudo"

    # chown: log + no-op (test sandbox doesn't need real chown — and
    # running this test as non-root would fail real chown anyway).
    cat > "$SANDBOX/bin/chown" <<CHOWN
#!/usr/bin/env bash
echo "chown \$*" >> "$SANDBOX/calls/chown.log"
exit 0
CHOWN
    chmod +x "$SANDBOX/bin/chown"
}

teardown_sandbox() {
    [ -n "${SANDBOX:-}" ] && [ -d "$SANDBOX" ] && rm -rf "$SANDBOX"
    unset SANDBOX MOCK_PING_EXIT MOCK_SSH_EXIT MOCK_NMCLI_CURRENT_SSID \
          MOCK_NMCLI_PSK MOCK_NMCLI_MOD_EXIT
}

# Run the patched sealing script with PATH-prepended mocks. Returns the
# script's exit code in $RUN_EXIT.
run_sealing() {
    PATH="$SANDBOX/bin:$PATH" \
    REPO_PATH="$SANDBOX/repo" \
    REPO="$SANDBOX/repo" \
    LOCAL_CFG="$SANDBOX/repo/master/config/local.cfg" \
    SUDO_USER="testuser" \
    bash "$SANDBOX/repo/scripts/astromech_pair_sealing.sh" \
        >"$SANDBOX/stdout.log" 2>"$SANDBOX/stderr.log"
    RUN_EXIT=$?
}

# ──────────────────────────────────────────────────────────────────────
# TEST 1: Marker present → instant exit 0, no commands run
# ──────────────────────────────────────────────────────────────────────
test_marker_present_skips() {
    echo ""
    echo "TEST 1: Marker present → instant exit 0, no commands run"
    setup_sandbox
    # Pre-write marker.
    touch "$SANDBOX/var/lib/astromech/pair_sealed"
    run_sealing
    assert_eq "exit code 0 when marker present" "0" "$RUN_EXIT"
    assert_file_absent "no nmcli calls" "$SANDBOX/calls/nmcli.log"
    assert_file_absent "no ssh calls" "$SANDBOX/calls/ssh.log"
    assert_file_absent "no ping calls" "$SANDBOX/calls/ping.log"
    teardown_sandbox
}

# ──────────────────────────────────────────────────────────────────────
# TEST 2: Marker absent + slave unreachable → exit 2, marker NOT created
# ──────────────────────────────────────────────────────────────────────
test_slave_unreachable_exits_2() {
    echo ""
    echo "TEST 2: Slave unreachable → exit 2, marker NOT created"
    setup_sandbox
    # Force ping to fail.
    cat > "$SANDBOX/bin/ping" <<'PING'
#!/usr/bin/env bash
exit 1
PING
    chmod +x "$SANDBOX/bin/ping"
    run_sealing
    assert_eq "exit code 2 when slave unreachable" "2" "$RUN_EXIT"
    assert_file_absent "marker not created on unreachable" "$SANDBOX/var/lib/astromech/pair_sealed"
    teardown_sandbox
}

# ──────────────────────────────────────────────────────────────────────
# TEST 3: Slave reachable + AP already on FINAL_SSID → exit 0, marker created,
#         no nmcli modify call
# ──────────────────────────────────────────────────────────────────────
test_already_on_final_ssid() {
    echo ""
    echo "TEST 3: AP already on FINAL_SSID → exit 0 + marker, no flip"
    setup_sandbox
    # Override nmcli to report current SSID = "Astromech-TEST" (matches
    # gen_hotspot_ssid mock output).
    cat > "$SANDBOX/bin/nmcli" <<NMCLI
#!/usr/bin/env bash
echo "nmcli \$*" >> "$SANDBOX/calls/nmcli.log"
case "\$*" in
    *"-t -f 802-11-wireless.ssid connection show astromech-hotspot"*)
        echo "802-11-wireless.ssid:Astromech-TEST"
        ;;
    *"-s -g 802-11-wireless-security.psk connection show astromech-hotspot"*)
        echo "testpassword123"
        ;;
    *"connection modify"*|*"connection up"*)
        echo "MODIFY-OR-UP-CALLED" >> "$SANDBOX/calls/nmcli_modify.log"
        exit 0
        ;;
esac
exit 0
NMCLI
    chmod +x "$SANDBOX/bin/nmcli"

    run_sealing
    assert_eq "exit code 0 when already on FINAL_SSID" "0" "$RUN_EXIT"
    assert_file_exists "marker created" "$SANDBOX/var/lib/astromech/pair_sealed"
    assert_file_absent "no nmcli modify/up call when already on final" "$SANDBOX/calls/nmcli_modify.log"
    teardown_sandbox
}

# ──────────────────────────────────────────────────────────────────────
# TEST 4: Full happy path — slave reachable, AP on bootstrap, flip happens,
#         marker created, ssh push + nmcli modify both invoked
# ──────────────────────────────────────────────────────────────────────
test_full_handover_happy_path() {
    echo ""
    echo "TEST 4: Full handover happy path — ssh push + nmcli flip + marker"
    setup_sandbox
    # Default mocks already set: ping ok, ssh ok, nmcli current = bootstrap.
    # nmcli modify call gets logged via the default mock's connection modify
    # branch. Add a side-channel log to assert ON the modify call.
    cat > "$SANDBOX/bin/nmcli" <<NMCLI
#!/usr/bin/env bash
echo "nmcli \$*" >> "$SANDBOX/calls/nmcli.log"
case "\$*" in
    *"-t -f 802-11-wireless.ssid connection show astromech-hotspot"*)
        echo "802-11-wireless.ssid:Astromech-BOOT"
        exit 0
        ;;
    *"-s -g 802-11-wireless-security.psk connection show astromech-hotspot"*)
        echo "testpassword123"
        exit 0
        ;;
    *"connection modify astromech-hotspot"*)
        echo "MODIFIED" >> "$SANDBOX/calls/nmcli_modify.log"
        exit 0
        ;;
    *"connection up astromech-hotspot"*)
        echo "UP" >> "$SANDBOX/calls/nmcli_up.log"
        exit 0
        ;;
esac
exit 0
NMCLI
    chmod +x "$SANDBOX/bin/nmcli"

    run_sealing
    assert_eq "exit code 0 on full handover" "0" "$RUN_EXIT"
    assert_file_exists "marker created on full handover" "$SANDBOX/var/lib/astromech/pair_sealed"
    assert_file_exists "ssh push invoked" "$SANDBOX/calls/ssh.log"
    assert_file_exists "nmcli connection modify called" "$SANDBOX/calls/nmcli_modify.log"
    assert_file_exists "nmcli connection up called" "$SANDBOX/calls/nmcli_up.log"
    teardown_sandbox
}

# ──────────────────────────────────────────────────────────────────────
# Run all tests
# ──────────────────────────────────────────────────────────────────────
echo "================================================================"
echo "astromech_pair_sealing.sh — unit tests"
echo "================================================================"

test_marker_present_skips
test_slave_unreachable_exits_2
test_already_on_final_ssid
test_full_handover_happy_path

echo ""
echo "================================================================"
echo "Results: $PASS passed, $FAIL failed"
echo "================================================================"
if [ "$FAIL" -gt 0 ]; then
    echo "Failed assertions:"
    for t in "${FAILED_TESTS[@]}"; do
        echo "  - $t"
    done
    exit 1
fi
exit 0
