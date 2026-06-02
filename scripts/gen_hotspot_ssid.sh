#!/usr/bin/env bash
# =============================================================================
# gen_hotspot_ssid.sh — print a per-robot hotspot SSID.
#
# A fixed SSID collides when several AstromechOS robots run in the same place
# (expos / conventions). This derives a unique 4-char suffix from the Pi's
# hardware so each robot's access point is distinct, e.g. "Astromech-3A2B".
#
# Suffix source order: Pi serial (/proc/cpuinfo) → wlan0 MAC → random.
# Usage:   gen_hotspot_ssid.sh [base]      (base defaults to "Astromech")
# Output:  <base>-<XXXX>   (XXXX = 4 uppercase hex chars)
# =============================================================================
set -euo pipefail

BASE="${1:-Astromech}"
suffix=""

# 1. Pi serial — stable + unique per board (last 4 hex chars).
# `|| true`: under `set -euo pipefail`, a grep no-match (boards with no
# /proc/cpuinfo "Serial" line, e.g. Pi 5 / non-Pi) would abort the script BEFORE
# the fallbacks below — collapsing every such robot to the fixed base name.
serial="$(grep -m1 -E '^Serial' /proc/cpuinfo 2>/dev/null | awk '{print $NF}' | tr -d '[:space:]' || true)"
if [[ "$serial" =~ [0-9a-fA-F]{4}$ ]]; then
    suffix="${serial: -4}"
fi

# 2. Fallback: last 4 hex of the wlan0 MAC.
if [[ -z "$suffix" ]]; then
    mac="$(cat /sys/class/net/wlan0/address 2>/dev/null | tr -d ':[:space:]' || true)"
    [[ "$mac" =~ [0-9a-fA-F]{4}$ ]] && suffix="${mac: -4}"
fi

# 3. Last resort: random.
[[ -z "$suffix" ]] && suffix="$(printf '%04x' $((RANDOM % 65536)))"

# Uppercase for a clean, readable SSID.
printf '%s-%s\n' "$BASE" "$(printf '%s' "$suffix" | tr 'a-f' 'A-F')"
