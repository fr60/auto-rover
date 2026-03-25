#!/bin/bash
# ─────────────────────────────────────────────────────────────
# deploy/setup_ota.sh  —  run ONCE on the Pi
#
# Handles everything in one script:
#   1. SSH deploy key for GitHub
#   2. Clone private repo
#   3. System packages (gpsd, pigpio)
#   4. gpsd configuration for F9P
#   5. Python dependencies
#   6. systemd services (rover + OTA watcher)
#
# Skips any step already completed — safe to re-run.
#
# Usage:
#   chmod +x setup_ota.sh
#   ./setup_ota.sh
# ─────────────────────────────────────────────────────────────
 
set -e
 
CURRENT_USER=$(whoami)
HOME_DIR=$(eval echo "~$CURRENT_USER")
KEY_FILE="$HOME_DIR/.ssh/rover_deploy_key"
SSH_CONFIG="$HOME_DIR/.ssh/config"
ROVER_DIR="$HOME_DIR/auto-rover"
DEPLOY_DIR="$ROVER_DIR/deploy"
 
echo ""
echo "════════════════════════════════════════════════════"
echo "  Rover Pi setup"
echo "════════════════════════════════════════════════════"
echo "  User:    $CURRENT_USER"
echo "  Home:    $HOME_DIR"
echo "  Project: $ROVER_DIR"
echo ""
 
# ── 1. SSH deploy key ─────────────────────────────────────────
echo "── Step 1: SSH deploy key ───────────────────────────"
if [ -f "$KEY_FILE" ]; then
    echo "  Key already exists — skipping."
else
    echo "  Generating SSH deploy key..."
    mkdir -p "$HOME_DIR/.ssh"
    chmod 700 "$HOME_DIR/.ssh"
    ssh-keygen -t ed25519 -f "$KEY_FILE" -N "" -C "rover-pi-deploy"
    echo "  Key generated."
fi
 
# ── 2. SSH config alias ───────────────────────────────────────
echo ""
echo "── Step 2: SSH config ───────────────────────────────"
if grep -q "rover-pi-github" "$SSH_CONFIG" 2>/dev/null; then
    echo "  Config alias already exists — skipping."
else
    echo "  Adding GitHub SSH alias..."
    cat >> "$SSH_CONFIG" <<EOF
 
Host rover-pi-github
    HostName github.com
    User git
    IdentityFile $KEY_FILE
    IdentitiesOnly yes
EOF
    chmod 600 "$SSH_CONFIG"
    echo "  Done."
fi
 
# ── 3. Test GitHub connection ─────────────────────────────────
echo ""
echo "── Step 3: GitHub connection test ───────────────────"
if ssh -T rover-pi-github 2>&1 | grep -q "successfully authenticated"; then
    echo "  GitHub connection OK."
else
    echo ""
    echo "  ┌─────────────────────────────────────────────┐"
    echo "  │  ACTION REQUIRED                            │"
    echo "  │  Add this deploy key to GitHub:             │"
    echo "  │  Repo → Settings → Deploy keys → Add key   │"
    echo "  │  Title: rover-pi  |  Write access: NO       │"
    echo "  └─────────────────────────────────────────────┘"
    echo ""
    cat "$KEY_FILE.pub"
    echo ""
    echo "  Then re-run this script."
    exit 1
fi
 
# ── 4. Clone repo ─────────────────────────────────────────────
echo ""
echo "── Step 4: Clone repo ───────────────────────────────"
if [ -d "$ROVER_DIR/.git" ]; then
    echo "  Repo already cloned — pulling latest..."
    cd "$ROVER_DIR" && git pull origin main --quiet
else
    echo ""
    read -p "  Enter GitHub repo path (e.g. username/repo-name): " REPO_PATH
    git clone "git@rover-pi-github:$REPO_PATH.git" "$ROVER_DIR"
    echo "  Cloned to $ROVER_DIR"
fi
 
# ── 5. System packages ────────────────────────────────────────
echo ""
echo "── Step 5: System packages ──────────────────────────"
echo "  Updating package list..."
sudo apt-get update -q
echo "  Installing gpsd, pigpio, python3-pip..."
sudo apt-get install -y gpsd gpsd-clients pigpio python3-pigpio python3-pip \
    --no-install-recommends -q
echo "  Done."
 
# ── 6. Configure gpsd for F9P ────────────────────────────────
echo ""
echo "── Step 6: Configure gpsd ───────────────────────────"
F9P_DEV=$(ls /dev/ttyACM* 2>/dev/null | head -1)
if [ -z "$F9P_DEV" ]; then
    echo "  F9P not detected yet — defaulting to /dev/ttyACM0"
    echo "  Plug in the F9P then run: sudo systemctl restart gpsd"
    F9P_DEV="/dev/ttyACM0"
else
    echo "  F9P detected at: $F9P_DEV"
fi
 
sudo tee /etc/default/gpsd > /dev/null <<EOF
START_DAEMON="true"
GPSD_OPTIONS="-n"
DEVICES="$F9P_DEV"
USBAUTO="true"
EOF
 
sudo systemctl enable gpsd
sudo systemctl restart gpsd
echo "  gpsd configured and running."
 
# ── 7. Enable pigpio daemon ───────────────────────────────────
echo ""
echo "── Step 7: pigpio daemon ────────────────────────────"
sudo systemctl enable pigpiod
sudo systemctl start pigpiod
echo "  pigpiod running."
 
# ── 8. Python dependencies ────────────────────────────────────
echo ""
echo "── Step 8: Python dependencies ──────────────────────"
if [ -f "$ROVER_DIR/requirements.txt" ]; then
    pip3 install -r "$ROVER_DIR/requirements.txt" \
        --break-system-packages --quiet
    echo "  Python packages installed."
else
    echo "  requirements.txt not found — skipping."
fi
 
# ── 9. Install systemd services ───────────────────────────────
echo ""
echo "── Step 9: systemd services ─────────────────────────"
 
sed "s/User=pi/User=$CURRENT_USER/g" "$DEPLOY_DIR/rover.service" \
    | sed "s|/home/pi|$HOME_DIR|g" \
    | sudo tee /etc/systemd/system/rover.service > /dev/null
 
sed "s/User=pi/User=$CURRENT_USER/g" "$DEPLOY_DIR/ota_watcher.service" \
    | sed "s|/home/pi|$HOME_DIR|g" \
    | sudo tee /etc/systemd/system/ota_watcher.service > /dev/null
 
sed "s|/home/pi|$HOME_DIR|g" "$DEPLOY_DIR/ota_watcher.timer" \
    | sudo tee /etc/systemd/system/ota_watcher.timer > /dev/null
 
sudo systemctl daemon-reload
sudo systemctl enable rover.service
sudo systemctl enable ota_watcher.timer
sudo systemctl start  ota_watcher.timer
echo "  Services installed. OTA watcher active."
 
 
# ── 10. All done (no file rewriting needed)
# ── Done ──────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════"
echo "  Setup complete!"
echo ""
echo "  Check status:"
echo "    sudo systemctl status gpsd"
echo "    sudo systemctl status pigpiod"
echo "    sudo systemctl status rover.service"
echo ""
echo "  Test GPS:"
echo "    cd $ROVER_DIR && python3 tests/test_gps.py"
echo ""
echo "  OTA: git push from laptop → Pi updates in 30s"
echo "    tail -f /var/log/rover_ota.log"
echo "════════════════════════════════════════════════════"
echo ""