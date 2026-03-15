#!/bin/bash
# setup_hotspot.sh — Configure wlan0 en point d'accès sur Pi 4B
# wlan1 = clé USB externe → internet (git pull)
# wlan0 = interface interne → hotspot "R2D2_Control" 192.168.4.x
#
# Usage: sudo bash setup_hotspot.sh

set -e

SSID="R2D2_Control"
PASSPHRASE="r2d2droid"
HOTSPOT_IP="192.168.4.1"
DHCP_RANGE_START="192.168.4.2"
DHCP_RANGE_END="192.168.4.20"
IFACE="wlan0"

echo "=== Installation des paquets ==="
apt-get update -qq
apt-get install -y hostapd dnsmasq

echo "=== Arrêt des services ==="
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

echo "=== Activation des services au démarrage ==="
systemctl enable hostapd dnsmasq
systemctl start hostapd dnsmasq

echo ""
echo "=== Hotspot configuré ==="
echo "  SSID : ${SSID}"
echo "  Clé  : ${PASSPHRASE}"
echo "  IP   : ${HOTSPOT_IP}"
echo ""
echo "  R2-Slave doit se connecter à '${SSID}' et obtiendra 192.168.4.2+"
echo "  Redémarrez le Pi 4B pour appliquer tous les changements."
