
Copy

#!/bin/bash
# ─────────────────────────────────────────────────────────────
# deploy/ota_update.sh — called every 30s by systemd timer
#
# Self-contained — detects paths at runtime.
# Never needs sed -i rewriting. Safe to re-run.
# ─────────────────────────────────────────────────────────────
 
# Detect the service user's home directory at runtime
SERVICE_USER=$(stat -c '%U' "$0")
if [ "$SERVICE_USER" = "root" ] || [ -z "$SERVICE_USER" ]; then
    # Fall back to the user who owns the rover-project directory
    ROVER_DIR=$(dirname "$(dirname "$(realpath "$0")")")
else
    ROVER_DIR="/home/$SERVICE_USER/auto-rover"
fi

    
# ROVER_DIR="/home/fareed/auto-rover"
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