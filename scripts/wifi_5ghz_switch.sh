#!/bin/bash
# ============================================================
#  AstromechOS — live Master<->Slave hotspot 5 GHz switch
# ============================================================
# Switches the Master<->Slave link (wlan0 hotspot) from 2.4 GHz to 5 GHz
# (band a, channel 36 — UNII-1, non-DFS) WITHOUT changing the SSID or password
# (band/channel only) so already-paired tablets/PC just re-associate by name.
#
# Runs ON THE MASTER (which has key-based SSH to the Slave). The operator's SSH
# to the Master is over wlan1 (home WiFi) — independent of the wlan0 hotspot —
# so control of the Master is never lost; the deadman only covers this script
# itself dying mid-flight.
#
# SAFETY: SLAVE-FIRST + systemd-run DEADMAN auto-rollback on BOTH Pis. If the
# 5 GHz link is not verified, both Pis self-revert to the original 2.4 GHz after
# the deadman delay. The script also verifies synchronously and reverts NOW on
# failure (the deadman is the backstop if the script/SSH dies).
#
# Usage (on the Master):
#   sudo bash scripts/wifi_5ghz_switch.sh --dry-run   # validate + print plan, change nothing
#   sudo bash scripts/wifi_5ghz_switch.sh             # execute the live switch
set -u

DRY=0; [[ "${1:-}" == "--dry-run" ]] && DRY=1

HOTSPOT_CON="${HOTSPOT_CON:-astromech-hotspot}"        # Master AP connection (NM)
SLAVE_CON="${SLAVE_CON:-astromech-master-hotspot}"     # Slave client connection (NM)
SLAVE_HOST="${SLAVE_HOST:-192.168.4.171}"              # Slave on the hotspot subnet
BAND="${HOTSPOT_BAND:-a}"; CHANNEL="${HOTSPOT_CHANNEL:-36}"; COUNTRY="${REG_COUNTRY:-CA}"
DEADMAN_M="${DEADMAN_M:-180}"; DEADMAN_S="${DEADMAN_S:-210}"   # slave reverts AFTER master
UNIT="astromech-5g-rollback"
SSH="ssh -o StrictHostKeyChecking=no -o ConnectTimeout=8 artoo@${SLAVE_HOST}"

log(){ echo "[5GHz] $*"; }

# --- Ensure the regulatory domain (idempotent, harmless; required for 5 GHz) ---
iw reg set "$COUNTRY" 2>/dev/null || true

# --- Capture current state (to PRESERVE the SSID + know the revert target) ---
ORIG_SSID="$(nmcli -g 802-11-wireless.ssid con show "$HOTSPOT_CON" 2>/dev/null)"
ORIG_BAND="$(nmcli -g 802-11-wireless.band con show "$HOTSPOT_CON" 2>/dev/null)"
ORIG_CHAN="$(nmcli -g 802-11-wireless.channel con show "$HOTSPOT_CON" 2>/dev/null)"

log "Hotspot connection : $HOTSPOT_CON"
log "Current SSID       : '$ORIG_SSID'   (PRESERVED — never touched)"
log "Current band/chan  : band='${ORIG_BAND:-auto/2.4}' chan='${ORIG_CHAN:-0}'"
log "Target             : band=$BAND channel=$CHANNEL (5 GHz UNII-1) — SAME SSID/password"

# --- Count usable 5 GHz AP channel (5180 MHz = ch36) on master + slave ---
usable_5ghz(){ iw reg set "$COUNTRY" 2>/dev/null || true; iw phy phy0 info 2>/dev/null | grep " 5180 MHz" | grep -ivE "disabled|no IR" | wc -l; }
M5="$(usable_5ghz)"
S5="$($SSH "sudo -n bash -c '$(declare -f usable_5ghz); usable_5ghz'" 2>/dev/null | tr -dc '0-9')"
$SSH true 2>/dev/null && SLAVE_OK=1 || SLAVE_OK=0

log "5 GHz ch36 usable  : master=$([[ "${M5:-0}" -ge 1 ]] && echo yes || echo NO)  slave=$([[ "${S5:-0}" -ge 1 ]] && echo yes || echo NO)"
log "Slave reachable    : $([[ $SLAVE_OK -eq 1 ]] && echo yes || echo NO)  ($SLAVE_HOST)"

# --- Abort if prerequisites are not met (don't even try) ---
[[ -n "$ORIG_SSID" ]]      || { log "ABORT: cannot read current SSID — wrong connection name?"; exit 2; }
[[ "${M5:-0}" -ge 1 ]]     || { log "ABORT: master has no usable 5 GHz channel (reg domain?)"; exit 2; }
[[ "${S5:-0}" -ge 1 ]]     || { log "ABORT: slave has no usable 5 GHz channel (reg domain?)"; exit 2; }
[[ $SLAVE_OK -eq 1 ]]      || { log "ABORT: slave unreachable — cannot arm its deadman"; exit 2; }

if [[ $DRY -eq 1 ]]; then
  log "================= DRY-RUN — NO changes to hotspot/SSID ================="
  log "Would execute, slave-first:"
  log " 1. SLAVE deadman  (+${DEADMAN_S}s): ssh slave -> systemd-run --unit=$UNIT 'iw reg set $COUNTRY; nmcli con down/up $SLAVE_CON'"
  log " 2. MASTER deadman (+${DEADMAN_M}s): systemd-run --unit=$UNIT 'nmcli con mod $HOTSPOT_CON band=${ORIG_BAND:-<auto>} chan=${ORIG_CHAN:-0}; nmcli con up'"
  log " 3. FLIP master   : nmcli con mod $HOTSPOT_CON 802-11-wireless.band $BAND .channel $CHANNEL  (SSID '$ORIG_SSID' untouched); nmcli con up"
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
  && log "  slave deadman armed (will re-associate at +${DEADMAN_S}s if not cancelled)" \
  || { log "ABORT: failed to arm slave deadman — no changes made"; exit 3; }

log "[2/5] Arming MASTER deadman (+${DEADMAN_M}s)..."
systemctl stop ${UNIT}.timer 2>/dev/null || true
systemd-run --on-active=${DEADMAN_M} --unit=${UNIT} --timer-property=AccuracySec=1s \
  /bin/sh -c "nmcli con mod '${HOTSPOT_CON}' 802-11-wireless.band '${ORIG_BAND}' 802-11-wireless.channel ${ORIG_CHAN:-0}; nmcli con up '${HOTSPOT_CON}'" \
  && log "  master deadman armed (will revert AP to 2.4 at +${DEADMAN_M}s if not cancelled)" \
  || { log "ABORT: failed to arm master deadman"; $SSH "sudo -n systemctl stop ${UNIT}.timer 2>/dev/null"; exit 3; }

log "[3/5] Flipping master hotspot to 5 GHz (band $BAND ch $CHANNEL; SSID '$ORIG_SSID' + password PRESERVED)..."
nmcli con mod "$HOTSPOT_CON" 802-11-wireless.band "$BAND" 802-11-wireless.channel "$CHANNEL"
timeout 35 nmcli con up "$HOTSPOT_CON" || log "  (con up non-zero/timeout — verifying by ping)"

log "[4/5] Waiting 25s for the 5 GHz AP + slave re-association..."
sleep 25
OK=0
for i in 1 2 3 4 5; do
  if ping -c1 -W2 "$SLAVE_HOST" >/dev/null 2>&1; then OK=1; break; fi
  sleep 2
done

if [[ $OK -eq 1 ]]; then
  FREQ="$(iw dev wlan0 info 2>/dev/null | awk '/channel/{$1="";print}')"
  log "[5/5] ✅ SUCCESS — slave reachable on 5 GHz. wlan0:${FREQ}"
  systemctl stop ${UNIT}.timer ${UNIT}.service 2>/dev/null || true
  $SSH "sudo -n systemctl stop ${UNIT}.timer ${UNIT}.service 2>/dev/null" || true
  log "  both deadmans cancelled. Link is now 5 GHz, SSID '$ORIG_SSID' unchanged."
  # Persist the reg domain so 5 GHz survives a reboot (same oneshot the installers use).
  install_regdom(){ cat > /etc/systemd/system/astromech-regdom.service <<U
[Unit]
Description=AstromechOS - set WiFi regulatory domain (enables 5 GHz)
DefaultDependencies=no
Before=NetworkManager.service wpa_supplicant.service network-pre.target
Wants=network-pre.target
[Service]
Type=oneshot
ExecStart=/bin/sh -c 'iw reg set REGCC'
RemainAfterExit=yes
[Install]
WantedBy=multi-user.target
U
  sed -i "s/REGCC/${1}/" /etc/systemd/system/astromech-regdom.service
  systemctl daemon-reload; systemctl enable astromech-regdom.service 2>/dev/null; }
  install_regdom "$COUNTRY"
  $SSH "sudo -n bash -c '$(declare -f install_regdom); install_regdom ${COUNTRY}'" 2>/dev/null || true
  log "  reg-domain $COUNTRY persisted on both Pis (survives reboot)."
  exit 0
else
  log "[5/5] ⚠ FAIL — slave NOT reachable on 5 GHz. Reverting master to 2.4 NOW..."
  nmcli con mod "$HOTSPOT_CON" 802-11-wireless.band "$ORIG_BAND" 802-11-wireless.channel "${ORIG_CHAN:-0}"
  timeout 35 nmcli con up "$HOTSPOT_CON" || true
  systemctl stop ${UNIT}.timer ${UNIT}.service 2>/dev/null || true
  log "  master reverted to 2.4 (band='${ORIG_BAND:-auto}'). Waiting 20s for slave to rejoin..."
  sleep 20
  if ping -c2 -W2 "$SLAVE_HOST" >/dev/null 2>&1; then
    log "  slave back on 2.4 ✓ — cancelling slave deadman."
    $SSH "sudo -n systemctl stop ${UNIT}.timer ${UNIT}.service 2>/dev/null" || true
  else
    log "  slave not back yet — leaving its deadman (+${DEADMAN_S}s) to re-associate."
  fi
  log "  Outcome: 5 GHz softAP not viable on this firmware. Link stayed/returned to 2.4 (SSID '$ORIG_SSID')."
  exit 1
fi
