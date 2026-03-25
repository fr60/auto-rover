#!/bin/bash
# deploy/ota_update.sh — called every 30s by systemd timer


ROVER_DIR="/home/fareed/auto-rover"
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

echo "[$TIMESTAMP] New commit: $REMOTE (was $LOCAL)" >> "$LOG"
git pull origin main --quiet 2>&1 | tee -a "$LOG"

if [ -f "requirements.txt" ]; then
    pip3 install -r requirements.txt --break-system-packages --quiet 2>&1 | tee -a "$LOG"
fi

sudo systemctl restart rover.service 2>&1 | tee -a "$LOG"

echo "[$TIMESTAMP] Update complete — rover.service restarted" >> "$LOG"
echo "---" >> "$LOG"