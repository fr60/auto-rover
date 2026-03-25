#!/bin/bash
# ─────────────────────────────────────────────
# Rover GPS setup — run once on the Pi 5
# Installs gpsd, configures it for the F9P
# ─────────────────────────────────────────────

set -e

echo "==> Updating package list..."
sudo apt-get update -q

echo "==> Installing gpsd and tools..."
sudo apt-get install -y gpsd gpsd-clients python3-pip


echo "==> Installing Python GPS library..."
pip3 install gpsd-py3 --break-system-packages


echo "==> Detecting F9P USB device..."
F9P_DEV=$(ls /dev/ttyACM* 2>/dev/null | head -1)

if [ -z "$F9P_DEV" ]; then
    echo "WARNING: No /dev/ttyACM* device found."
    echo "  Make sure the F9P is plugged into a USB port and try again."
    F9P_DEV="/dev/ttyACM0"
fi

echo "==> F9P device: $F9P_DEV"

echo "==> Writing gpsd config..."
sudo tee /etc/default/gpsd > /dev/null <<EOF
START_DAEMON="true"
GPSD_OPTIONS="-n"
DEVICES="$F9P_DEV"
USBAUTO="true"
GPSD_SOCKET="/var/run/gpsd.sock"
EOF


echo "==> Enabling and restarting gpsd..."
sudo systemctl enable gpsd
sudo systemctl restart gpsd
