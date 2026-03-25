#!/bin/bash
# ─────────────────────────────────────────────────────────────
# deploy/setup_ota.sh  —  run ONCE on the Pi
#
# Detects your actual username automatically.
# Skips any steps already completed.
#
# Usage:
#   chmod +x setup_ota.sh
#   ./setup_ota.sh
# ─────────────────────────────────────────────────────────────
 

set -e
# ── Auto-detect user and paths ────────────────────────────────
CURRENT_USER=$(whoami)
HOME_DIR=$(eval echo "~$CURRENT_USER")
KEY_FILE="$HOME_DIR/.ssh/rover_deploy_key"
SSH_CONFIG="$HOME_DIR/.ssh/config"
ROVER_DIR="$HOME_DIR/auto-rover"

echo ""
echo "==> Detected user:      $CURRENT_USER"
echo "==> Home directory:     $HOME_DIR"
echo "==> SSH key location:   $KEY_FILE"
echo "==> Rover directory:    $ROVER_DIR"
echo ""


# ── 1. SSH deploy key ─────────────────────────────────────────
if [ -f "$KEY_FILE" ]; then
    echo "==> SSH key already exists — skipping."
else
    echo "==> Generating SSH deploy key..."
    mkdir -p "$HOME_DIR/.ssh"
    chmod 700 "$HOME_DIR/.ssh"
    ssh-keygen -t ed25519 -f "$KEY_FILE" -N "" -C "rover-pi-deploy"
fi

# ── 2. SSH config alias ───────────────────────────────────────
if grep -q "rover-pi-github" "$SSH_CONFIG" 2>/dev/null; then
    echo "==> SSH config alias already exists — skipping."
else
    echo "==> Adding SSH config alias..."
    cat >> "$SSH_CONFIG" <<EOF
 
Host rover-pi-github
    HostName github.com
    User git
    IdentityFile $KEY_FILE
    IdentitiesOnly yes
EOF
    chmod 600 "$SSH_CONFIG"
fi

# ── 3. Test GitHub connection ─────────────────────────────────
echo ""
echo "==> Testing GitHub SSH connection..."
if ssh -T rover-pi-github 2>&1 | grep -q "successfully authenticated"; then
    echo "==> GitHub connection OK."
else
    echo ""
    echo "════════════════════════════════════════════════════"
    echo "  Add this deploy key to GitHub:"
    echo "  Repo → Settings → Deploy keys → Add deploy key"
    echo "  Title: rover-pi   |   Allow write access: NO"
    echo ""
    cat "$KEY_FILE.pub"
    echo ""
    echo "  Then re-run this script."
    echo "════════════════════════════════════════════════════"
    exit 1
fi

# ── 4. Clone repo ─────────────────────────────────────────────
if [ -d "$ROVER_DIR/.git" ]; then
    echo "==> Repo already cloned — skipping."
else
    echo ""
    read -p "==> Enter your GitHub repo path (e.g. username/repo-name): " REPO_PATH
    git clone "git@rover-pi-github:$REPO_PATH.git" "$ROVER_DIR"
    echo "==> Cloned to $ROVER_DIR"
fi


# ── 5. Install Python dependencies ────────────────────────────
if [ -f "$ROVER_DIR/requirements.txt" ]; then
    echo "==> Installing Python dependencies..."
    pip3 install -r "$ROVER_DIR/requirements.txt" --break-system-packages --quiet
fi


# ── 6. Install systemd services ───────────────────────────────
DEPLOY_DIR="$ROVER_DIR/deploy"
 
echo "==> Installing rover.service..."
sed "s/User=pi/User=$CURRENT_USER/g" "$DEPLOY_DIR/rover.service" \
    | sed "s|/home/pi|$HOME_DIR|g" \
    | sudo tee /etc/systemd/system/rover.service > /dev/null
 
echo "==> Installing OTA watcher..."
sed "s/User=pi/User=$CURRENT_USER/g" "$DEPLOY_DIR/ota_watcher.service" \
    | sed "s|/home/pi|$HOME_DIR|g" \
    | sudo tee /etc/systemd/system/ota_watcher.service > /dev/null
 
sed "s|/home/pi|$HOME_DIR|g" "$DEPLOY_DIR/ota_watcher.timer" \
    | sudo tee /etc/systemd/system/ota_watcher.timer > /dev/null
 
sudo systemctl daemon-reload
sudo systemctl enable rover.service
sudo systemctl enable ota_watcher.timer
sudo systemctl start  ota_watcher.timer

# ── 7. Fix paths in ota_update.sh ────────────────────────────
sed -i "s|/home/pi|$HOME_DIR|g" "$DEPLOY_DIR/ota_update.sh"
chmod +x "$DEPLOY_DIR/ota_update.sh"
 
echo ""
echo "════════════════════════════════════════════════════"
echo "  Setup complete!"
echo ""
echo "  Push to GitHub → Pi updates within 30s"
echo "  Logs:   tail -f /var/log/rover_ota.log"
echo "  Status: sudo systemctl status rover.service"
echo "════════════════════════════════════════════════════"
echo ""