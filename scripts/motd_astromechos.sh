#!/bin/bash
# scripts/motd_astromechos.sh — Dynamic per-node MOTD for AstromechOS
# Installed to /etc/update-motd.d/99-astromechos by scripts/install_motd.sh
#
# Speed budget: targets under 1.5s end-to-end. The dominant cost is the
# cross-ping (`ping -c 1 -W 1` = up to 1s when peer offline). Every section
# is wrapped in defensive logic so a single failure (missing JSON, dead
# systemctl, no /sys/class/thermal entry) renders as "N/A" — never blocks
# SSH login.
#
# Chantier 2026-05-28: signature visuelle d'AstromechOS. ANSI cyan for the
# Master (Dome), green for the Slave (Body). Live hardware state from
# config_mapping.json + hw_layout.json. Cross-ping for fleet visibility.

set +e   # NEVER abort the login session on a failed sub-call.
LC_ALL=C
export LC_ALL

# ─── ANSI palette ────────────────────────────────────────────────────
RESET=$'\033[0m'
BOLD=$'\033[1m'
DIM=$'\033[2m'
CYAN=$'\033[96m'         # Bright cyan — Master / Dome badge
GREEN=$'\033[92m'        # Bright green — Slave / Body badge
YELLOW=$'\033[93m'       # Amber — warnings
RED=$'\033[91m'          # Bright red — critical / offline
GRAY=$'\033[90m'         # Dim text — secondary info
WHITE=$'\033[97m'        # Bright white — primary text
ORANGE=$'\033[38;5;208m' # Hardware accent
MAGENTA=$'\033[95m'      # Service title accent

# ─── Identify this node ──────────────────────────────────────────────
HOSTNAME_RAW=$(hostname 2>/dev/null || echo "unknown")
case "$HOSTNAME_RAW" in
    *master*|astromech-m*|r2-master|r2-m*) ROLE="master" ;;
    *slave*|astromech-s*|r2-slave|r2-s*)   ROLE="slave"  ;;
    *)
        if systemctl list-unit-files astromech-master.service >/dev/null 2>&1; then
            ROLE="master"
        elif systemctl list-unit-files astromech-slave.service >/dev/null 2>&1; then
            ROLE="slave"
        else
            ROLE="unknown"
        fi
        ;;
esac

# Repo path autodetect — searches every home dir for an astromechos
# checkout. The MASTER has a real .git checkout; the SLAVE receives the
# tree via rsync (no .git) so we accept any directory containing a
# master/ or slave/ subtree as a valid repo root.
REPO=""
for CAND in /home/*/astromechos; do
    if [ -d "$CAND/.git" ] || [ -d "$CAND/master" ] || [ -d "$CAND/slave" ]; then
        REPO="$CAND"
        break
    fi
done

# Badge colour + label per role.
if [ "$ROLE" = "master" ]; then
    NODECOL="$CYAN"
    NODELABEL="DOME · MASTER"
    SUBSYSTEM="DOME"
elif [ "$ROLE" = "slave" ]; then
    NODECOL="$GREEN"
    NODELABEL="BODY · SLAVE"
    SUBSYSTEM="BODY"
else
    NODECOL="$YELLOW"
    NODELABEL="UNKNOWN ROLE"
    SUBSYSTEM="?"
fi

# ─── Helpers ─────────────────────────────────────────────────────────
# Print a horizontal rule. Width = 72 chars (matches terminal default).
rule() { printf "${GRAY}%s${RESET}\n" "────────────────────────────────────────────────────────────────────────"; }

# Centered text within 72-char width.
pad_centre() {
    local txt="$1" w=72 vis
    # Strip ANSI for measurement.
    vis=$(printf '%s' "$txt" | sed 's/\x1B\[[0-9;]*[a-zA-Z]//g')
    local pad=$(( (w - ${#vis}) / 2 ))
    [ "$pad" -lt 0 ] && pad=0
    printf "%*s%s\n" "$pad" "" "$txt"
}

# Format value with colour for a metric.
colour_temp() {
    local t="$1"
    if [ -z "$t" ] || [ "$t" = "N/A" ]; then
        printf "${GRAY}N/A${RESET}"
        return
    fi
    local i=${t%.*}
    if [ "$i" -ge 70 ] 2>/dev/null; then
        printf "${RED}● %s°C${RESET}" "$t"
    elif [ "$i" -ge 55 ] 2>/dev/null; then
        printf "${YELLOW}● %s°C${RESET}" "$t"
    else
        printf "${GREEN}● %s°C${RESET}" "$t"
    fi
}

# ─── Banner ──────────────────────────────────────────────────────────
print_banner() {
    printf "\n"
    printf "${NODECOL}${BOLD}    █████  ███████ ████████ ██████   ██████  ███    ███ ███████  ██████ ██   ██${RESET}\n"
    printf "${NODECOL}${BOLD}   ██   ██ ██         ██    ██   ██ ██    ██ ████  ████ ██      ██      ██   ██${RESET}\n"
    printf "${NODECOL}${BOLD}   ███████ ███████    ██    ██████  ██    ██ ██ ████ ██ █████   ██      ███████${RESET}\n"
    printf "${NODECOL}${BOLD}   ██   ██      ██    ██    ██   ██ ██    ██ ██  ██  ██ ██      ██      ██   ██${RESET}\n"
    printf "${NODECOL}${BOLD}   ██   ██ ███████    ██    ██   ██  ██████  ██      ██ ███████  ██████ ██   ██${RESET}\n"
    printf "\n"
    # Role badge — bright background pill on a dark base.
    printf "   ${NODECOL}${BOLD}╣ ${NODELABEL} ╠${RESET}"
    # Right-aligned git/version blurb.
    local rest_width=$((72 - 10 - ${#NODELABEL} - 4))
    [ "$rest_width" -lt 0 ] && rest_width=0
    printf "%*s\n" "$rest_width" "$(git_status_line)"
    rule
}

# ─── Git status line ─────────────────────────────────────────────────
git_status_line() {
    # Master path: real .git tree → full status (sha + branch + sync).
    if [ -n "$REPO" ] && [ -d "$REPO/.git" ]; then
        # update-motd.d scripts run as root; the AstromechOS repo is
        # owned by the install user (artoo / pi / …). Without
        # safe.directory, git 2.35+ refuses with 'dubious ownership'
        # and every read returns empty -> sha + branch render as '?'.
        # Scope the trust to this exact repo so the override doesn't
        # leak to anything else the shell does next.
        local GC=(-c "safe.directory=$REPO")
        local sha branch
        sha=$(git "${GC[@]}" -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo "?")
        branch=$(git "${GC[@]}" -C "$REPO" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "?")
        local upstream behind=0 ahead=0
        upstream=$(git "${GC[@]}" -C "$REPO" rev-parse --abbrev-ref --symbolic-full-name "@{upstream}" 2>/dev/null)
        if [ -n "$upstream" ]; then
            read -r behind ahead < <(git "${GC[@]}" -C "$REPO" rev-list --left-right --count "$upstream"...HEAD 2>/dev/null || echo "0 0")
        fi
        local pill
        if [ "${behind:-0}" -gt 0 ]; then
            pill="${YELLOW}⟳ pull required (${behind} behind)${RESET}"
        elif [ "${ahead:-0}" -gt 0 ]; then
            pill="${YELLOW}↑ ahead by ${ahead}${RESET}"
        else
            pill="${GREEN}✓ up-to-date${RESET}"
        fi
        printf "${BOLD}AstromechOS${RESET} ${DIM}v.${RESET}${WHITE}${sha}${RESET} ${DIM}(${branch})${RESET}  ${pill}"
        return
    fi
    # Slave path: rsync target — read VERSION file (written by update.sh
    # via `git rev-parse --short HEAD`). No ahead/behind possible without
    # .git, but knowing the deployed commit is what matters.
    if [ -n "$REPO" ] && [ -f "$REPO/VERSION" ]; then
        local ver
        ver=$(head -1 "$REPO/VERSION" 2>/dev/null | tr -d '[:space:]')
        if [ -n "$ver" ]; then
            printf "${BOLD}AstromechOS${RESET} ${DIM}v.${RESET}${WHITE}${ver}${RESET} ${DIM}(rsync)${RESET}  ${GREEN}✓ synced${RESET}"
            return
        fi
    fi
    printf "${GRAY}AstromechOS · version N/A${RESET}"
}

# ─── System box ──────────────────────────────────────────────────────
print_system() {
    local now uptime_str cpu_temp disk_used disk_pct mem_pct load_avg
    now=$(date '+%Y-%m-%d %H:%M:%S %Z' 2>/dev/null || echo "N/A")
    uptime_str=$(uptime -p 2>/dev/null | sed 's/^up //' || echo "N/A")

    # CPU temp (millicelsius).
    if [ -r /sys/class/thermal/thermal_zone0/temp ]; then
        cpu_temp=$(awk '{printf "%.1f", $1/1000}' /sys/class/thermal/thermal_zone0/temp 2>/dev/null)
    else
        cpu_temp="N/A"
    fi

    # Disk + memory + load via stdlib coreutils.
    if df -h / >/dev/null 2>&1; then
        read -r _ disk_used _ disk_pct _ < <(df -h / 2>/dev/null | awk 'NR==2 {print $1, $3, $4, $5, $6}')
    else
        disk_pct="N/A"
    fi
    if [ -r /proc/meminfo ]; then
        local mt ma
        mt=$(awk '/^MemTotal:/{print $2}' /proc/meminfo)
        ma=$(awk '/^MemAvailable:/{print $2}' /proc/meminfo)
        if [ -n "$mt" ] && [ -n "$ma" ] && [ "$mt" -gt 0 ]; then
            mem_pct=$(awk -v mt="$mt" -v ma="$ma" 'BEGIN{printf "%d", 100*(mt-ma)/mt}')
        fi
    fi
    [ -z "$mem_pct" ] && mem_pct="N/A"
    if [ -r /proc/loadavg ]; then
        load_avg=$(awk '{printf "%s, %s, %s", $1, $2, $3}' /proc/loadavg)
    else
        load_avg="N/A"
    fi

    printf "${MAGENTA}${BOLD}┌─[ SYSTEM ]${RESET}${GRAY}─────────────────────────────────────────────────────────────${RESET}\n"
    printf "  ${WHITE}Time${RESET}     %s\n" "$now"
    printf "  ${WHITE}Uptime${RESET}   %s\n" "$uptime_str"
    printf "  ${WHITE}CPU${RESET}      %b\n" "$(colour_temp "$cpu_temp")"
    printf "  ${WHITE}Disk${RESET}     %s used (%s available)\n" "${disk_pct:-?}" "${disk_used:-?}"
    printf "  ${WHITE}Memory${RESET}   %s%% used\n" "$mem_pct"
    printf "  ${WHITE}Load${RESET}     %s\n" "$load_avg"
}

# ─── Network box + cross-ping ────────────────────────────────────────
# Pad <label> with dim trailing dots to a fixed visual width so the
# colon separator + value column align across rows. Width 15 chars
# covers the longest label this box prints: "Peer (MASTER)" (13) plus
# 1 space + 1 dot. Anything shorter gets more dots.
_motd_pad_dots() {
    local label="$1" target=15 dots
    local need=$(( target - ${#label} - 1 ))
    [ "$need" -lt 0 ] && need=0
    printf -v dots '%*s' "$need" ''
    dots=${dots// /.}
    printf "%s ${GRAY}%s${RESET}" "$label" "$dots"
}

print_network() {
    local this_ip peer_ip peer_role_caps peer_label local_label ping_status
    # All non-loopback IPv4 addresses (could be multiple on master with WiFi+hotspot).
    this_ip=$(hostname -I 2>/dev/null | awk '{for (i=1;i<=NF;i++) if ($i !~ /^(127\.|::)/) {printf "%s%s", (n++? " · " : ""), $i}}')
    [ -z "$this_ip" ] && this_ip="N/A"

    # Cross-ping target — master pings slave, slave pings master.
    if [ "$ROLE" = "master" ]; then
        local_label="Master IP"
        peer_role_caps="SLAVE"
        # [slave] host from master local.cfg
        if [ -n "$REPO" ] && [ -f "$REPO/master/config/local.cfg" ]; then
            peer_ip=$(awk -F= '
                /^\[slave\]/{f=1; next}
                /^\[/{f=0}
                f && $1 ~ /host/ {gsub(/[ \t]/, "", $2); print $2; exit}
            ' "$REPO/master/config/local.cfg" 2>/dev/null)
        fi
        [ -z "$peer_ip" ] && peer_ip="192.168.4.171"   # legacy default
    else
        local_label="Slave IP"
        peer_role_caps="MASTER"
        # Slave's default gateway = Master (hotspot mode).
        peer_ip=$(ip route show default 2>/dev/null | awk '{print $3; exit}')
        [ -z "$peer_ip" ] && peer_ip="192.168.4.1"
    fi
    peer_label="Peer (${peer_role_caps})"

    # Sub-second ping. -W 1 = max 1s wait; on healthy LAN, ~1ms RTT.
    if ping -c 1 -W 1 -q "$peer_ip" >/dev/null 2>&1; then
        ping_status="${GREEN}● ONLINE${RESET}"
    else
        ping_status="${RED}● OFFLINE${RESET}"
    fi

    printf "${MAGENTA}${BOLD}┌─[ NETWORK ]${RESET}${GRAY}────────────────────────────────────────────────────────────${RESET}\n"
    printf "  ${WHITE}%b${RESET} ${GRAY}:${RESET} %s\n" "$(_motd_pad_dots "$local_label")" "$this_ip"
    printf "  ${WHITE}%b${RESET} ${GRAY}:${RESET} ${BOLD}%s${RESET}  %b\n" "$(_motd_pad_dots "$peer_label")" "$peer_ip" "$ping_status"
}

# ─── Hardware box (config_mapping + hw_layout) ───────────────────────
print_hardware() {
    if [ -z "$REPO" ]; then
        printf "${MAGENTA}${BOLD}┌─[ HARDWARE ]${RESET}${GRAY}───────────────────────────────────────────────────────────${RESET}\n"
        printf "  ${GRAY}repo path unknown — HAT inventory N/A${RESET}\n"
        return
    fi
    local map_path="$REPO/$ROLE/config/config_mapping.json"
    local layout_path="$REPO/$ROLE/config/hw_layout.json"
    if [ ! -f "$map_path" ]; then
        printf "${MAGENTA}${BOLD}┌─[ HARDWARE ]${RESET}${GRAY}───────────────────────────────────────────────────────────${RESET}\n"
        printf "  ${GRAY}config_mapping.json N/A — run \`scripts/detect_hats.py\`${RESET}\n"
        return
    fi

    printf "${MAGENTA}${BOLD}┌─[ HARDWARE (%s) ]${RESET}${GRAY}─────────────────────────────────────────────────${RESET}\n" "$SUBSYSTEM"
    # Parse mapping + layout with python3 (jq optional; python always present).
    python3 - "$map_path" "$layout_path" <<'PYEOF' 2>/dev/null || \
        printf "  ${GRAY}HAT inventory parse failed${RESET}\n"
import json, sys, os
GREEN  = '\033[92m'
RED    = '\033[91m'
YELLOW = '\033[93m'
GRAY   = '\033[90m'
WHITE  = '\033[97m'
BOLD   = '\033[1m'
RESET  = '\033[0m'
try:
    with open(sys.argv[1], encoding='utf-8') as f:
        m = json.load(f)
except Exception:
    print(f"  {GRAY}config_mapping.json unreadable{RESET}")
    sys.exit(0)
detected = set()
if os.path.isfile(sys.argv[2]):
    try:
        with open(sys.argv[2], encoding='utf-8') as f:
            l = json.load(f)
        for h in l.get('hats') or []:
            if isinstance(h, dict):
                a = (h.get('addr') or '').strip().lower()
                if a.startswith('0x'):
                    detected.add(a)
    except Exception:
        pass
for h in m.get('hats') or []:
    if not isinstance(h, dict):
        continue
    ident   = h.get('id', '?')
    role    = h.get('role', '?')
    addr    = (h.get('address') or '').strip().lower()
    channels= h.get('channels', 16)
    online  = addr in detected
    badge   = f"{GREEN}● CONNECTED   {RESET}" if online else f"{RED}● OFFLINE     {RESET}"
    role_pretty = {
        'servo_dome':  'dome servos',
        'servo_body':  'body servos',
        'motor_drive': 'motor drive',
    }.get(role, role)
    print(f"  {BOLD}{ident:<14}{RESET}@{addr:>5}  {badge}  {GRAY}({channels} ch · {role_pretty}){RESET}")
PYEOF
}

# ─── Services box ────────────────────────────────────────────────────
print_services() {
    printf "${MAGENTA}${BOLD}┌─[ SERVICES ]${RESET}${GRAY}───────────────────────────────────────────────────────────${RESET}\n"
    local svcs
    if [ "$ROLE" = "master" ]; then
        svcs="astromech-master astromech-monitor astromech-camera"
    elif [ "$ROLE" = "slave" ]; then
        svcs="astromech-slave"
    else
        svcs=""
    fi
    for s in $svcs; do
        if ! systemctl list-unit-files "${s}.service" >/dev/null 2>&1; then
            continue
        fi
        local state
        state=$(systemctl is-active "${s}.service" 2>/dev/null || echo "unknown")
        local badge
        case "$state" in
            active)       badge="${GREEN}● active${RESET}" ;;
            inactive)     badge="${GRAY}○ inactive${RESET}" ;;
            failed)       badge="${RED}● FAILED${RESET}" ;;
            activating)   badge="${YELLOW}● starting${RESET}" ;;
            deactivating) badge="${YELLOW}● stopping${RESET}" ;;
            *)            badge="${YELLOW}● ${state}${RESET}" ;;
        esac
        printf "  ${WHITE}%-30s${RESET}  %b\n" "${s}.service" "$badge"
    done

    # Slave-specific: UART latency probe (read from the live diagnostics).
    if [ "$ROLE" = "slave" ]; then
        # The Slave doesn't host the diagnostics endpoint locally; it
        # exposes UART round-trip via its own metric. Best-effort read.
        local lat="N/A"
        if [ -r "/run/astromech-slave-uart-lat.ms" ]; then
            lat=$(cat /run/astromech-slave-uart-lat.ms 2>/dev/null)
        fi
        printf "  ${WHITE}%-30s${RESET}  ${YELLOW}%s${RESET}\n" "UART latency (last sample, ms)" "$lat"
    fi
}

# ─── Footer ──────────────────────────────────────────────────────────
print_footer() {
    rule
    printf "  ${DIM}AstromechOS${RESET}  ${GRAY}·${RESET}  ${DIM}https://github.com/RickDnamps/AstromechOS${RESET}  ${GRAY}·${RESET}  ${DIM}type \`bd ready\` for tasks${RESET}\n"
    printf "\n"
}

# ─── Render ──────────────────────────────────────────────────────────
print_banner
print_system
print_network
print_hardware
print_services
print_footer

exit 0
