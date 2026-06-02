#!/bin/bash
# ============================================================
#  AstromechOS — live Master<->Slave hotspot 5 GHz switch
# ============================================================
# Switches the Master<->Slave link (wlan0 hotspot) from 2.4 GHz to 5 GHz
# (band a, channel 36 — UNII-1, non-DFS) WITHOUT changing the SSID or password
# (band/channel only) so already-paired tablets/PC just re-associate by name.
#
# Run AS THE astromech USER (NOT via sudo bash) so the master->slave ssh uses
# astromech's key. Privileged ops use `sudo -n` (astromech has NOPASSWD). The operator's
# SSH to the Master is over wlan1 (home WiFi) — independent of the wlan0 hotspot
# — so Master control is never lost; the deadman only covers this script dying.
#
# NOTE: `iw` lives in /usr/sbin (not in a bare non-login PATH) and reg reads need
# root here, so all iw calls go through `sudo -n iw`. 5 GHz feasibility is judged
# from nmcli's WIFI-PROPERTIES.5GHZ + the reg domain advertising the UNII-1 band.
#
# SAFETY: SLAVE-FIRST + systemd-run DEADMAN auto-rollback on BOTH Pis. The script
# also verifies synchronously and reverts NOW on failure; the deadman backstops a
# script death. softAP-on-5GHz support of the brcmfmac firmware is unproven — the
# verify+deadman is exactly what tests it safely.
#
# Usage (on the Master, as astromech):
#   bash scripts/wifi_5ghz_switch.sh --dry-run   # validate + print plan, change nothing
#   bash scripts/wifi_5ghz_switch.sh             # execute the live switch
set -u
export PATH="/usr/sbin:/sbin:$PATH"

DRY=0; [[ "${1:-}" == "--dry-run" ]] && DRY=1

HOTSPOT_CON="${HOTSPOT_CON:-astromech-hotspot}"        # Master AP connection (NM)
SLAVE_CON="${SLAVE_CON:-astromech-master-hotspot}"     # Slave client connection (NM)
SLAVE_HOST="${SLAVE_HOST:-192.168.4.171}"              # Slave on the hotspot subnet
BAND="${HOTSPOT_BAND:-a}"; CHANNEL="${HOTSPOT_CHANNEL:-36}"; COUNTRY="${REG_COUNTRY:-CA}"
DEADMAN_M="${DEADMAN_M:-180}"; DEADMAN_S="${DEADMAN_S:-210}"   # slave reverts AFTER master
UNIT="astromech-5g-rollback"
SSH="ssh -o StrictHostKeyChecking=no -o ConnectTimeout=8 ${USER:-astromech}@${SLAVE_HOST}"

log(){ echo "[5GHz] $*"; }

# 5 GHz feasibility: wlan0 reports 5GHz capability AND the reg domain advertises
# the UNII-1 band (5150-5250 = channels 36-48). Robust (no iw PATH / phy index).
fiveok(){
  sudo -n iw reg set "${COUNTRY}" >/dev/null 2>&1 || true
  local cap reg
  cap="$(nmcli -f WIFI-PROPERTIES dev show wlan0 2>/dev/null | grep -i '5ghz' | grep -ci yes)"
  reg="$(sudo -n iw reg get 2>/dev/null | grep -c '5150 - 5250')"
  [[ "${cap:-0}" -ge 1 && "${reg:-0}" -ge 1 ]] && echo yes || echo no
}

sudo -n iw reg set "$COUNTRY" 2>/dev/null || true

# Capture current state (PRESERVE the SSID + know the revert target). Reads = no sudo.
ORIG_SSID="$(nmcli -g 802-11-wireless.ssid con show "$HOTSPOT_CON" 2>/dev/null)"
ORIG_BAND="$(nmcli -g 802-11-wireless.band con show "$HOTSPOT_CON" 2>/dev/null)"
ORIG_CHAN="$(nmcli -g 802-11-wireless.channel con show "$HOTSPOT_CON" 2>/dev/null)"

log "Hotspot connection : $HOTSPOT_CON"
log "Current SSID       : '$ORIG_SSID'   (PRESERVED — never touched)"
log "Current band/chan  : band='${ORIG_BAND:-auto/2.4}' chan='${ORIG_CHAN:-0}'"
log "Target             : band=$BAND channel=$CHANNEL (5 GHz UNII-1) — SAME SSID/password"

M5="$(fiveok)"
S5="$($SSH "COUNTRY=${COUNTRY}; $(declare -f fiveok); fiveok" 2>/dev/null | tr -d '[:space:]')"
$SSH true 2>/dev/null && SLAVE_OK=1 || SLAVE_OK=0

log "5 GHz feasible     : master=${M5}  slave=${S5:-no}"
log "Slave reachable    : $([[ $SLAVE_OK -eq 1 ]] && echo yes || echo no)  ($SLAVE_HOST)"
log "Reg domain         : $(sudo -n iw reg get 2>/dev/null | grep -m1 country || echo '(none)')"

[[ -n "$ORIG_SSID" ]]   || { log "ABORT: cannot read current SSID — wrong connection name?"; exit 2; }
[[ "$M5" == "yes" ]]    || { log "ABORT: master not 5 GHz-feasible (cap/reg)"; exit 2; }
[[ "${S5}" == "yes" ]]  || { log "ABORT: slave not 5 GHz-feasible (cap/reg)"; exit 2; }
[[ $SLAVE_OK -eq 1 ]]   || { log "ABORT: slave unreachable — cannot arm its deadman"; exit 2; }

if [[ $DRY -eq 1 ]]; then
  log "================= DRY-RUN — NO changes to hotspot/SSID ================="
  log "Would execute, slave-first:"
  log " 1. SLAVE deadman  (+${DEADMAN_S}s): ssh slave -> sudo -n systemd-run --unit=$UNIT 'iw reg set $COUNTRY; nmcli con down/up $SLAVE_CON'"
  log " 2. MASTER deadman (+${DEADMAN_M}s): sudo -n systemd-run --unit=$UNIT 'nmcli con mod $HOTSPOT_CON band=${ORIG_BAND:-<auto>} chan=${ORIG_CHAN:-0}; nmcli con up'"
  log " 3. FLIP master   : sudo -n nmcli con mod $HOTSPOT_CON 802-11-wireless.band $BAND .channel $CHANNEL  (SSID '$ORIG_SSID' untouched); con up"
  log " 4. wait 25s, ping slave $SLAVE_HOST (x5)"
  log " 5a SUCCESS -> cancel both deadmans + persist reg-domain $COUNTRY (astromech-regdom.service) on both Pis"
  log " 5b FAIL    -> revert master to band='${ORIG_BAND:-auto}' NOW + cancel deadmans + report (stay 2.4)"
  log "Backstop: if this script/SSH dies mid-flight, both Pis self-revert to 2.4 via systemd-run."
  log "Operator SSH (wlan1/192.168.2.x) is NOT affected by the wlan0 hotspot flip."
  log "================= END DRY-RUN — prerequisites OK ✓ ================="
  exit 0
fi

# ===================== REAL EXECUTION (slave-first) =====================
log "[1/5] Arming SLAVE deadman (+${DEADMAN_S}s)..."
$SSH "sudo -n systemctl stop ${UNIT}.timer 2>/dev/null; sudo -n systemd-run --on-active=${DEADMAN_S} --unit=${UNIT} --timer-property=AccuracySec=1s /bin/sh -c 'iw reg set ${COUNTRY}; nmcli con down ${SLAVE_CON} || true; nmcli con up ${SLAVE_CON} || true'" \
  && log "  slave deadman armed (re-associates at +${DEADMAN_S}s if not cancelled)" \
  || { log "ABORT: failed to arm slave deadman — no changes made"; exit 3; }

log "[2/5] Arming MASTER deadman (+${DEADMAN_M}s)..."
sudo -n systemctl stop ${UNIT}.timer 2>/dev/null || true
sudo -n systemd-run --on-active=${DEADMAN_M} --unit=${UNIT} --timer-property=AccuracySec=1s \
  /bin/sh -c "nmcli con mod '${HOTSPOT_CON}' 802-11-wireless.band '${ORIG_BAND}' 802-11-wireless.channel ${ORIG_CHAN:-0}; nmcli con up '${HOTSPOT_CON}'" \
  && log "  master deadman armed (reverts AP to 2.4 at +${DEADMAN_M}s if not cancelled)" \
  || { log "ABORT: failed to arm master deadman"; $SSH "sudo -n systemctl stop ${UNIT}.timer 2>/dev/null"; exit 3; }

log "[3/5] Flipping master hotspot to 5 GHz (band $BAND ch $CHANNEL; SSID '$ORIG_SSID' + password PRESERVED)..."
sudo -n nmcli con mod "$HOTSPOT_CON" 802-11-wireless.band "$BAND" 802-11-wireless.channel "$CHANNEL"
timeout 35 sudo -n nmcli con up "$HOTSPOT_CON" || log "  (con up non-zero/timeout — verifying by ping)"

log "[4/5] Waiting 25s for the 5 GHz AP + slave re-association..."
sleep 25
OK=0
for i in 1 2 3 4 5; do
  if ping -c1 -W2 "$SLAVE_HOST" >/dev/null 2>&1; then OK=1; break; fi
  sleep 2
done

if [[ $OK -eq 1 ]]; then
  FREQ="$(sudo -n iw dev wlan0 info 2>/dev/null | awk '/channel/{$1="";print}')"
  log "[5/5] SUCCESS — slave reachable on 5 GHz. wlan0:${FREQ}"
  sudo -n systemctl stop ${UNIT}.timer ${UNIT}.service 2>/dev/null || true
  $SSH "sudo -n systemctl stop ${UNIT}.timer ${UNIT}.service 2>/dev/null" || true
  log "  both deadmans cancelled. Link is now 5 GHz, SSID '$ORIG_SSID' unchanged."
  # Persist the reg domain on BOTH Pis so 5 GHz survives a reboot. Build the unit
  # with printf (no heredoc) + base64 it over SSH to avoid nested-quoting failures.
  REGDOM_UNIT="$(printf '%s\n' \
    '[Unit]' \
    'Description=AstromechOS - set WiFi regulatory domain (enables 5 GHz)' \
    'DefaultDependencies=no' \
    'Before=NetworkManager.service wpa_supplicant.service network-pre.target' \
    'Wants=network-pre.target' \
    '[Service]' \
    'Type=oneshot' \
    "ExecStart=/bin/sh -c 'iw reg set ${COUNTRY}'" \
    'RemainAfterExit=yes' \
    '[Install]' \
    'WantedBy=multi-user.target')"
  REGDOM_B64="$(printf '%s' "$REGDOM_UNIT" | base64 -w0)"
  REGDOM_CMD="echo ${REGDOM_B64} | base64 -d | sudo -n tee /etc/systemd/system/astromech-regdom.service >/dev/null && sudo -n systemctl daemon-reload && sudo -n systemctl enable astromech-regdom.service"
  eval "$REGDOM_CMD" >/dev/null 2>&1 && log "  reg-domain $COUNTRY persisted on master" || log "  WARN: master regdom persist failed"
  $SSH "$REGDOM_CMD" >/dev/null 2>&1 && log "  reg-domain $COUNTRY persisted on slave"  || log "  WARN: slave regdom persist failed"
  exit 0
else
  log "[5/5] FAIL — slave NOT reachable on 5 GHz. Reverting master to 2.4 NOW..."
  sudo -n nmcli con mod "$HOTSPOT_CON" 802-11-wireless.band "$ORIG_BAND" 802-11-wireless.channel "${ORIG_CHAN:-0}"
  timeout 35 sudo -n nmcli con up "$HOTSPOT_CON" || true
  sudo -n systemctl stop ${UNIT}.timer ${UNIT}.service 2>/dev/null || true
  log "  master reverted to 2.4 (band='${ORIG_BAND:-auto}'). Waiting 20s for slave to rejoin..."
  sleep 20
  if ping -c2 -W2 "$SLAVE_HOST" >/dev/null 2>&1; then
    log "  slave back on 2.4 — cancelling slave deadman."
    $SSH "sudo -n systemctl stop ${UNIT}.timer ${UNIT}.service 2>/dev/null" || true
  else
    log "  slave not back yet — leaving its deadman (+${DEADMAN_S}s) to re-associate."
  fi
  log "  Outcome: 5 GHz softAP not viable on this firmware. Link stayed/returned to 2.4 (SSID '$ORIG_SSID')."
  exit 1
fi
