#!/bin/bash
# ============================================================
#   █████╗  ██████╗ ███████╗
#  ██╔══██╗██╔═══██╗██╔════╝
#  ███████║██║   ██║███████╗
#  ██╔══██║██║   ██║╚════██║
#  ██║  ██║╚██████╔╝███████║
#  ╚═╝  ╚═╝ ╚═════╝ ╚══════╝
#
#  AstromechOS — Open control platform for astromech builders
# ============================================================
#  Copyright (C) 2026 RickDnamps
#  https://github.com/RickDnamps/AstromechOS
#
#  This file is part of AstromechOS.
#
#  AstromechOS is free software: you can redistribute it
#  and/or modify it under the terms of the GNU General
#  Public License as published by the Free Software
#  Foundation, either version 2 of the License, or
#  (at your option) any later version.
#
#  AstromechOS is distributed in the hope that it will be
#  useful, but WITHOUT ANY WARRANTY; without even the implied
#  warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
#  PURPOSE. See the GNU General Public License for details.
#
#  You should have received a copy of the GNU GPL along with
#  AstromechOS. If not, see <https://www.gnu.org/licenses/>.
# ============================================================
# setup_hotspot.sh — Configure wlan0 as an access point on Pi 4B
# wlan1 = external USB adapter → internet (git pull)
# wlan0 = interface interne → hotspot "AstromechOS" 192.168.4.x
#
# Usage: sudo bash setup_hotspot.sh

set -e

SSID="AstromechOS"
PASSPHRASE="r2d2droid"
HOTSPOT_IP="192.168.4.1"
DHCP_RANGE_START="192.168.4.2"
DHCP_RANGE_END="192.168.4.20"
IFACE="wlan0"

echo "=== Installation des paquets ==="
apt-get update -qq
apt-get install -y hostapd dnsmasq

echo "=== Stopping services ==="
systemctl stop hostapd dnsmasq 2>/dev/null || true
systemctl unmask hostapd

echo "=== Configuration IP statique wlan0 ==="
cat >> /etc/dhcpcd.conf << EOF

# R2-D2 Hotspot
interface ${IFACE}
    static ip_address=${HOTSPOT_IP}/24
    nohook wpa_supplicant
EOF

echo "=== Configuration hostapd ==="
cat > /etc/hostapd/hostapd.conf << EOF
interface=${IFACE}
driver=nl80211
ssid=${SSID}
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=${PASSPHRASE}
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
EOF

# Pointer hostapd vers sa config
sed -i 's|#DAEMON_CONF=""|DAEMON_CONF="/etc/hostapd/hostapd.conf"|' /etc/default/hostapd

echo "=== Configuration dnsmasq (DHCP) ==="
mv /etc/dnsmasq.conf /etc/dnsmasq.conf.bak 2>/dev/null || true
cat > /etc/dnsmasq.conf << EOF
interface=${IFACE}
dhcp-range=${DHCP_RANGE_START},${DHCP_RANGE_END},255.255.255.0,24h
EOF

echo "=== Activation du routage IP (pour wlan1 internet) ==="
sed -i 's|#net.ipv4.ip_forward=1|net.ipv4.ip_forward=1|' /etc/sysctl.conf
sysctl -p

# NAT : wlan1 → wlan0
iptables -t nat -A POSTROUTING -o wlan1 -j MASQUERADE
iptables -A FORWARD -i wlan1 -o ${IFACE} -m state --state RELATED,ESTABLISHED -j ACCEPT
iptables -A FORWARD -i ${IFACE} -o wlan1 -j ACCEPT
# Persister iptables
apt-get install -y iptables-persistent -qq
netfilter-persistent save

echo "=== Enabling services at startup ==="
systemctl enable hostapd dnsmasq
systemctl start hostapd dnsmasq

echo ""
echo "=== Hotspot configured ==="
echo "  SSID : ${SSID}"
echo "  Key  : ${PASSPHRASE}"
echo "  IP   : ${HOTSPOT_IP}"
echo ""
echo "  R2-Slave must connect to '${SSID}' and will get 192.168.4.2+"
echo "  Reboot the Pi 4B to apply all changes."
