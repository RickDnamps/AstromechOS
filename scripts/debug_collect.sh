#!/bin/bash
# Collecte diagnostic R2-D2 et push sur GitHub dans debug/
# Usage: bash scripts/debug_collect.sh
# Ensuite: git pull sur le PC de dev → Claude lit les fichiers

REPO=/home/artoo/r2d2
SLAVE=artoo@r2-slave.local
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
OUT_DIR=$REPO/debug/$TIMESTAMP
SLAVE_OUT=$OUT_DIR/slave

mkdir -p "$OUT_DIR"
mkdir -p "$SLAVE_OUT"

echo "=== Collecte debug $TIMESTAMP ==="

# ──────────────────────────────────────────────
# MASTER
# ──────────────────────────────────────────────
echo "[Master] Infos système..."
{
  echo "=== HOSTNAME ==="
  hostname

  echo ""
  echo "=== DATE ==="
  date

  echo ""
  echo "=== UPTIME ==="
  uptime

  echo ""
  echo "=== UART /dev/ttyAMA0 ==="
  ls -la /dev/ttyAMA0 2>&1
  echo "--- fuser ---"
  fuser /dev/ttyAMA0 2>&1 || echo "(libre)"

  echo ""
  echo "=== PROCESSUS PYTHON ==="
  ps aux | grep python3 | grep -v grep

  echo ""
  echo "=== SERVICES SYSTEMD ==="
  systemctl status r2d2-master.service  --no-pager 2>&1 || echo "(service inexistant)"
  systemctl status r2d2-monitor.service --no-pager 2>&1 || echo "(service inexistant)"

  echo ""
  echo "=== RÉSEAU ==="
  ip addr show wlan0 2>&1
  ip addr show wlan1 2>&1

  echo ""
  echo "=== VERSION ==="
  cat $REPO/VERSION 2>&1 || echo "(pas de fichier VERSION)"
  echo "--- git log ---"
  cd $REPO && git log --oneline -5

  echo ""
  echo "=== DEVICES SÉRIE ==="
  ls -la /dev/ttyAMA0 /dev/ttyUSB0 /dev/ttyACM* 2>&1

  echo ""
  echo "=== /boot/firmware/config.txt (extrait uart/bt) ==="
  grep -E "uart|bluetooth|miniuart|disable.bt|enable_uart" /boot/firmware/config.txt 2>&1 || echo "(aucune ligne uart/bt)"

} > "$OUT_DIR/master_system.txt"

echo "[Master] Logs..."
cp /tmp/master.log "$OUT_DIR/master_log.txt" 2>/dev/null || echo "(aucun log master)" > "$OUT_DIR/master_log.txt"

# ──────────────────────────────────────────────
# SLAVE (via SSH)
# ──────────────────────────────────────────────
echo "[Slave] Vérification SSH..."
if ! ssh -o ConnectTimeout=5 $SLAVE "echo OK" > /dev/null 2>&1; then
  echo "SLAVE INJOIGNABLE via SSH" > "$SLAVE_OUT/status.txt"
  echo "[Slave] Injoignable — infos slave ignorées"
else
  echo "[Slave] Infos système..."
  ssh $SLAVE "
    echo '=== HOSTNAME ===' && hostname
    echo '' && echo '=== DATE ===' && date
    echo '' && echo '=== UART /dev/ttyAMA0 ===' && ls -la /dev/ttyAMA0 2>&1
    echo '--- fuser ---' && fuser /dev/ttyAMA0 2>&1 || echo '(libre)'
    echo '' && echo '=== PROCESSUS PYTHON ===' && ps aux | grep python3 | grep -v grep
    echo '' && echo '=== SERVICES SYSTEMD ===' && systemctl status r2d2-slave.service --no-pager 2>&1 || echo '(service inexistant)'
    echo '' && echo '=== DEVICES SÉRIE ===' && ls -la /dev/ttyAMA0 /dev/ttyACM* 2>&1
    echo '' && echo '=== /boot/firmware/config.txt (uart/bt) ===' && grep -E 'uart|bluetooth|miniuart|disable.bt|enable_uart' /boot/firmware/config.txt 2>&1 || echo '(aucune ligne uart/bt)'
  " > "$SLAVE_OUT/slave_system.txt" 2>&1

  echo "[Slave] Logs..."
  ssh $SLAVE "cat /tmp/slave.log 2>/dev/null || echo '(aucun log slave)'" > "$SLAVE_OUT/slave_log.txt" 2>&1
fi

# ──────────────────────────────────────────────
# RÉSUMÉ
# ──────────────────────────────────────────────
{
  echo "Debug collecté: $TIMESTAMP"
  echo "Master: $(hostname)"
  echo "Slave SSH: $(ssh -o ConnectTimeout=3 $SLAVE "hostname" 2>/dev/null || echo "injoignable")"
  echo ""
  echo "Fichiers:"
  ls -la "$OUT_DIR/"
  ls -la "$SLAVE_OUT/" 2>/dev/null
} > "$OUT_DIR/README.txt"

cat "$OUT_DIR/README.txt"

# ──────────────────────────────────────────────
# PUSH SUR GITHUB
# ──────────────────────────────────────────────
echo ""
echo "=== Push GitHub ==="
cd $REPO
git add debug/
git commit -m "debug: collect $TIMESTAMP"
git push

echo ""
echo "=== Fait ==="
echo "Sur ton PC de dev, fais: git pull"
echo "Les fichiers sont dans: debug/$TIMESTAMP/"
