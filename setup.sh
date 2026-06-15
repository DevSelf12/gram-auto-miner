#!/bin/bash
# Gram Network Auto Miner - VPS Setup
# =====================================
# Run: bash setup.sh

set -e

echo "=========================================="
echo "  Gram Network Auto Miner - VPS Setup"
echo "=========================================="

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "[*] Installing Python3..."
    apt update && apt install -y python3 python3-pip
fi

# Install dependencies
echo "[*] Installing dependencies..."
pip3 install telethon requests --break-system-packages 2>/dev/null || pip3 install telethon requests

# Copy config if not exists
if [ ! -f config.json ]; then
    echo "[!] config.json not found!"
    echo "[!] Copy config.example.json -> config.json and fill your credentials"
    echo ""
    echo "  cp config.example.json config.json"
    echo "  nano config.json"
    echo ""
    exit 1
fi

# Create systemd service
echo "[*] Creating systemd service..."
cat > /etc/systemd/system/gram-miner.service << EOF
[Unit]
Description=Gram Network Auto Miner
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$(pwd)
ExecStart=$(which python3) miner.py
Restart=always
RestartSec=30
StandardOutput=append:$(pwd)/miner.log
StandardError=append:$(pwd)/miner.log

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable gram-miner

echo ""
echo "=========================================="
echo "  Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. First run (login):  python3 miner.py"
echo "  2. Enter phone code when prompted"
echo "  3. Start service:      systemctl start gram-miner"
echo "  4. Check status:       systemctl status gram-miner"
echo "  5. View logs:          tail -f miner.log"
echo ""
echo "IMPORTANT: Run 'python3 miner.py' ONCE first to login!"
echo "           Then start the systemd service."
echo ""
