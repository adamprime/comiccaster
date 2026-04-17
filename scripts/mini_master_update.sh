#!/bin/bash
# Production entrypoint for ComicCaster on Mac Mini (openclaw user).
#
# LaunchD (~/Library/LaunchAgents/com.comiccaster.master.plist) points here.
# This script sets host-specific environment, then execs the tracked master
# update script. Anything host-specific belongs here; general pipeline logic
# belongs in local_master_update.sh.
#
# Mini-specific requirements preserved below:
# - ChromeDriver lives in ~/bin (direct download, not Homebrew)
# - Git push uses a dedicated deploy key (not default id_rsa)
# - CK scraper runs with --show-browser because upstream anti-bot blocks
#   headless Chrome; this also requires an active GUI session + caffeinate.

set -eu

export PATH="$HOME/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export GIT_SSH_COMMAND="ssh -i $HOME/.ssh/comiccaster_deploy -o IdentitiesOnly=yes"
export CK_SCRAPER_EXTRA_ARGS="--show-browser"

exec "$(dirname "$0")/local_master_update.sh"
