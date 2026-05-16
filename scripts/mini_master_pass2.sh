#!/bin/bash
# Production pass-2 entrypoint for ComicCaster on Mac Mini (openclaw user).
#
# LaunchD (~/Library/LaunchAgents/com.comiccaster.pass2.plist) points here.
# Sets host-specific environment, then execs the tracked pass-2 script.
# Pass 2 is GoComics-only — no CK browser flag needed (CK does not run here).
#
# Mirrors scripts/mini_master_update.sh but for the late-morning pass.

set -eu

export PATH="$HOME/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export GIT_SSH_COMMAND="ssh -i $HOME/.ssh/comiccaster_deploy -o IdentitiesOnly=yes"

exec "$(dirname "$0")/local_pass2_update.sh"
