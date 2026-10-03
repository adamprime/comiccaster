#!/bin/bash
# Production entrypoint for the Far Side morning pass on the Mac Mini (openclaw user).
#
# LaunchD (~/Library/LaunchAgents/com.comiccaster.farside.plist) points here,
# every 30 minutes from 03:30 to 12:00. Sets host-specific environment, then
# execs the tracked morning-pass script. Far Side needs no browser and no
# credentials; this only has to reach GitHub over SSH for the push.
#
# Mirrors scripts/mini_master_pass2.sh.
set -eu
export PATH="$HOME/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export GIT_SSH_COMMAND="ssh -i $HOME/.ssh/comiccaster_deploy -o IdentitiesOnly=yes"
exec "$(dirname "$0")/local_farside_morning.sh"
