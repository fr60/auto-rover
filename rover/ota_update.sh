#!/bin/bash
# ─────────────────────────────────────────────────────────────
# ota_update.sh  —  called every 30s by systemd timer
#
# Checks if GitHub has a newer commit than what's on the Pi.
# If yes: pulls, installs dependencies, restarts rover service.
# If no:  exits silently.
# ─────────────────────────────────────────────────────────────


ROVER_DIR="/home/fared/rover"
LOG="/var/log/rover_ota.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

cd "$ROVER_DIR" || exit 1

# Fetch remote refs without merging
git fetch origin main --quiet 2>&1

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" = "$REMOTE" ]; then
    # No update needed — exit silently
    exit 0
fi

# ── New commit detected ───────────────────────────────────────

echo "[$TIMESTAMP] New commit detected: $REMOTE" >> "$LOG"
echo "[$TIMESTAMP] Previous:           $LOCAL"   >> "$LOG"

# Pull the new code
git pull origin main --quiet 2>&1 | tee -a "$LOG"

# Install any new Python dependencies
if [ -f "requirements.txt" ]; then
    pip3 install -r requirements.txt --break-system-packages --quiet 2>&1 | tee -a "$LOG"
fi

# Restart the rover service
sudo systemctl restart rover.service 2>&1 | tee -a "$LOG"

echo "[$TIMESTAMP] Update complete — rover.service restarted" >> "$LOG"
echo "---" >> "$LOG"
