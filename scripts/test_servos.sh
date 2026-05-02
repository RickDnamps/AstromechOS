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
#  Copyright (C) 2025 RickDnamps
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
# Test servos Master + Slave — checks I2C, installs libs if needed, tests servos
# Usage: bash scripts/test_servos.sh
# Ctrl+C to stop tests

REPO=/home/artoo/r2d2
SLAVE=artoo@r2-slave.local

# ──────────────────────────────────────────────
# MASTER — I2C check + install + test
# ──────────────────────────────────────────────
echo "=== MASTER — I2C ==="
if ! command -v i2cdetect &>/dev/null; then
    echo "Installation i2c-tools..."
    sudo apt-get install -y i2c-tools -q
fi

I2C_MASTER=$(sudo /usr/sbin/i2cdetect -y 1 2>&1)
echo "$I2C_MASTER" | grep -q "40" && echo "✓ PCA9685 @ 0x40 detected" || echo "✗ 0x40 NOT detected — check I2C wiring Master"

echo ""
echo "=== MASTER — Python dependencies ==="
python3 -c "import adafruit_pca9685" 2>/dev/null && echo "✓ adafruit-pca9685 already installed" || {
    echo "Installation adafruit-circuitpython-pca9685..."
    pip install adafruit-circuitpython-pca9685 -q && echo "✓ Installed"
}

# ──────────────────────────────────────────────
# SLAVE — I2C check + install + test
# ──────────────────────────────────────────────
echo ""
echo "=== SLAVE — Sync scripts ==="
rsync -a $REPO/scripts/ $SLAVE:$REPO/scripts/ && echo "✓ Scripts synced" || echo "⚠ rsync failed"

echo ""
echo "=== SLAVE — I2C ==="
I2C_SLAVE=$(ssh $SLAVE "sudo /usr/sbin/i2cdetect -y 1 2>&1" 2>&1)
echo "$I2C_SLAVE" | grep -q "41" && echo "✓ PCA9685 @ 0x41 detected" || echo "✗ 0x41 NOT detected — check I2C wiring Slave"

echo ""
echo "=== SLAVE — Python dependencies ==="
ssh $SLAVE "python3 -c 'import adafruit_pca9685' 2>/dev/null && echo '✓ adafruit-pca9685 already installed' || { pip install adafruit-circuitpython-pca9685 -q && echo '✓ Installed'; }"

# ──────────────────────────────────────────────
# Abort si I2C manquant
# ──────────────────────────────────────────────
if ! echo "$I2C_MASTER" | grep -q "40"; then
    echo ""
    echo "✗ Test aborted — PCA9685 Master not detected"
    exit 1
fi
if ! echo "$I2C_SLAVE" | grep -q "41"; then
    echo ""
    echo "✗ Test aborted — PCA9685 Slave not detected"
    exit 1
fi

# ──────────────────────────────────────────────
# LAUNCH TESTS IN PARALLEL
# ──────────────────────────────────────────────
echo ""
echo "=== Servo test running — Ctrl+C to stop ==="
echo "  Master : PCA9685 @ 0x40, channel 0  (dome servo)"
echo "  Slave  : PCA9685 @ 0x41, canal 0  (servo body)"
echo ""

cleanup() {
    echo ""
    echo "=== Stopping ==="
    pkill -9 -f test_servo_master.py 2>/dev/null
    ssh $SLAVE "pkill -9 -f test_servo_slave.py" 2>/dev/null
    kill $MASTER_PID $SLAVE_PID 2>/dev/null
    # Cut PWM via direct I2C — guaranteed regardless of what happened
    python3 $REPO/scripts/estop.py
    exit 0
}
trap cleanup INT TERM

python3 -u $REPO/scripts/test_servo_master.py standard 2>&1 | sed 's/^/[MASTER] /' &
MASTER_PID=$!

ssh $SLAVE "python3 -u $REPO/scripts/test_servo_slave.py standard 2>&1" | sed 's/^/[SLAVE]  /' &
SLAVE_PID=$!

wait $MASTER_PID $SLAVE_PID
