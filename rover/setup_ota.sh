#!/bin/bash

# ─────────────────────────────────────────────────────────────
# setup_ota.sh  —  run ONCE on the Pi
#
# What this does:
#   1. Generates an SSH key pair for GitHub access (deploy key)
#   2. Clones your private repo
#   3. Installs the OTA watcher as a systemd timer
#   4. Installs the rover as a systemd service
#
# Usage:
#   chmod +x setup_ota.sh
#   ./setup_ota.sh
#
# After running, copy the printed public key into GitHub:
#   Repo → Settings → Deploy keys → Add deploy key
#   Title: "rover-pi"  |  Allow write access: NO
# ─────────────────────────────────────────────────────────────
 
set -e

REPO_URL="git@github.com:fr60/auto-rover.git"   # ← change this
ROVER_DIR="/home/fareed/rover"
KEY_FILE="/home/fareed/.ssh/rover_deploy_key"

# ── 1. Generate SSH deploy key ────────────────────────────────

echo ""
echo "==> Generating SSH deploy key for GitHub access..."
mkdir -p /home/fareed/.ssh
chmod 700 /home/fareed/.ssh

if [ -f "$KEY_FILE" ]; then
    ssh-keygen -t ed25519 -f "$KEY_FILE" -N "" -C "rover-pi-deploy"
    echo "Key generated."
else
    echo "Key already exists, skipping."
fi


# ── 2. Configure SSH to use this key for GitHub ───────────────
SSH_CONFIG="/home/fareed/.ssh/config"
if ! grep -q "rover-pi-github" "$SSH_CONFIG" 2>/dev/null; then
cat >> "$SSH_CONFIG" <<EOF

Host rover-pi-github
    HostName github.com
    User git
    IdentityFile $KEY_FILE
    IdentitiesOnly yes
EOF
fi

# Update repo URL to use the SSH config alias
REPO_URL_SSH="${REPO_URL/git@github.com:/git@rover-pi-github:}"


# ── 3. Clone the repo ─────────────────────────────────────────
echo ""
echo "==> Cloning repo..."
if [ ! -d "$ROVER_DIR/.git" ]; then
    git clone "$REPO_URL_SSH" "$ROVER_DIR"
    echo "Cloned to $ROVER_DIR"
else
    echo "Repo already exists at $ROVER_DIR"
fi

# ── 4. Install rover systemd service ──────────────────────────
echo ""
echo "==> Installing rover.service..."
sudo cp "$ROVER_DIR/rover.service" /etc/systemd/system/rover.service
sudo systemctl daemon-reload
sudo systemctl enable rover.service
echo "rover.service installed (not started yet)"

# ── 5. Install OTA watcher timer ──────────────────────────────
echo ""
echo "==> Installing OTA watcher..."
sudo cp "$ROVER_DIR/ota_watcher.service" /etc/systemd/system/ota_watcher.service
sudo cp "$ROVER_DIR/ota_watcher.timer"   /etc/systemd/system/ota_watcher.timer
sudo systemctl daemon-reload
sudo systemctl enable ota_watcher.timer
sudo systemctl start  ota_watcher.timer
echo "OTA watcher running (polls every 30s)"

# ── 6. Print deploy key ───────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════"
echo "  ACTION REQUIRED — add this deploy key to GitHub:"
echo "  Repo → Settings → Deploy keys → Add deploy key"
echo "  Title: rover-pi   |   Allow write access: NO"
echo "════════════════════════════════════════════════════"
echo ""
cat "$KEY_FILE.pub"
echo ""
echo "════════════════════════════════════════════════════"
echo ""
echo "Once the key is added, test with:"
echo "  ssh -T rover-pi-github"
echo "  cd $ROVER_DIR && git pull"