#!/bin/bash
#
# Cron wrapper script for ComicCaster daily updates
#
# This script ensures the proper environment is loaded before
# running the daily update script.
#
# Add to crontab:
# 0 9 * * * /root/comiccaster/scripts/droplet_cron.sh >> /var/log/comiccaster.log 2>&1

set -e

# Load environment variables
if [ -f ~/.comiccaster_env ]; then
    source ~/.comiccaster_env
fi

# Change to project directory
cd /root/comiccaster

# Activate virtual environment
if [ -d venv ]; then
    source venv/bin/activate
fi

# Pull latest changes (in case you updated scripts)
git pull --rebase || echo "⚠️  Git pull failed, continuing with current version"

# Run the daily update
python3 scripts/droplet_daily_update.py

# Deactivate virtual environment
deactivate || true

echo ""
echo "======================================================================"
echo "Next run: $(date -d 'tomorrow 09:00' '+%Y-%m-%d %H:%M:%S %Z')"
echo "======================================================================"
