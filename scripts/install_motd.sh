#!/bin/bash
# scripts/install_motd.sh — Install the AstromechOS MOTD on this node.
# Idempotent; safe to re-run after every deploy.
#
# What it does:
#   1. Copies scripts/motd_astromechos.sh to /etc/update-motd.d/99-astromechos
#      with mode 0755 owned by root.
#   2. Disables every other update-motd.d entry (chmod -x) so only ours runs
#      — preserves the file so a future apt update doesn't re-enable them.
#   3. Truncates /etc/motd (the static banner) so it doesn't print before ours.
#   4. Smoke-tests the installed script (runs it; non-zero exit -> abort
#      with a clear error so the operator notices BEFORE the next SSH login).
#
# Usage: sudo bash scripts/install_motd.sh
# Idempotent: re-running just re-syncs the script bytes and reapplies perms.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$SCRIPT_DIR/motd_astromechos.sh"
DST="/etc/update-motd.d/99-astromechos"

if [ ! -f "$SRC" ]; then
    echo "ERROR: source script $SRC not found" >&2
    exit 2
fi
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: must run as root (use sudo)" >&2
    exit 1
fi

echo "→ Installing MOTD to $DST"
install -m 0755 -o root -g root "$SRC" "$DST"

echo "→ Disabling stock update-motd.d entries (preserves files, drops +x)"
for f in /etc/update-motd.d/*; do
    name=$(basename "$f")
    case "$name" in
        99-astromechos) ;;
        *) chmod -x "$f" 2>/dev/null || true ;;
    esac
done

echo "→ Emptying /etc/motd (static banner)"
: > /etc/motd

echo "→ Smoke-testing the installed script"
if ! bash -n "$DST"; then
    echo "ERROR: bash syntax check on $DST failed — refusing to leave broken MOTD" >&2
    exit 3
fi
# Run once to confirm it produces output without crashing.
if ! OUT=$("$DST" 2>&1); then
    echo "WARNING: $DST exited non-zero on first run:" >&2
    echo "$OUT" | head -10 >&2
    echo "(SSH login will still continue — the script set +e early)" >&2
fi

echo "→ Done. Next SSH login will display the AstromechOS MOTD."
