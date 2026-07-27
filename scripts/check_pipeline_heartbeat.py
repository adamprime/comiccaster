#!/usr/bin/env python3
"""Alert when the daily pipeline goes silent.

`report_pipeline_failures.py` reports what broke *during* a run. It structurally
cannot report a run that never happened: if the Mac Mini is off, asleep, or
network-dead, no step fails, so no issue is opened and a dead pipeline looks
exactly like a healthy one.

This is the dead-man's switch for that case. It deliberately runs on GitHub
Actions rather than on the Mini -- a heartbeat hosted on the machine it is
monitoring dies with it.

Health signal: the pipeline commits feed updates to main on every successful
run (twice daily). If no *pipeline* commit has landed within --stale-hours, the
pipeline is presumed down. Human commits are ignored on purpose: a code push at
midnight must not mask a pipeline that stopped running.

Reuses the reporter's issue machinery, so a heartbeat alert opens, comments,
and auto-closes exactly like a source failure -- and clears itself as soon as
the pipeline commits again.
"""

import argparse
import re
import subprocess
import sys
import time
from datetime import date

sys.path.insert(0, __file__.rsplit("/", 1)[0])

from report_pipeline_failures import report  # noqa: E402

HEARTBEAT_SLUG = "heartbeat"

# Pass 1 runs at 03:05 and Pass 2 at 13:00, so a healthy repo sees a pipeline
# commit every day. 20h tolerates a normal daily cadence plus schedule drift
# while still catching a wholly missed night.
DEFAULT_STALE_HOURS = 20

# Commit subjects the pipeline itself writes (see local_master_update.sh and
# local_pass2_update.sh). Matched as prefixes.
PIPELINE_COMMIT_PATTERNS = (
    "Update all comic feeds for",
    "Update comic feeds for",
    "Pass 2 GoComics feed update for",
)

LOG_DEPTH = 200


def now_ts() -> int:
    return int(time.time())


def git_log() -> str:
    return subprocess.run(
        ["git", "log", f"-n{LOG_DEPTH}", "--format=%ct%x09%s"],
        check=True, capture_output=True, text=True,
    ).stdout


def find_latest_pipeline_commit(log_output: str):
    """Return (timestamp, subject) of the newest pipeline commit, or None.

    `git log` is newest-first, so the first match wins.
    """
    for line in (log_output or "").splitlines():
        timestamp, _, subject = line.partition("\t")
        if not subject:
            continue
        if not any(subject.startswith(p) for p in PIPELINE_COMMIT_PATTERNS):
            continue
        if not re.fullmatch(r"\d+", timestamp.strip()):
            continue
        return int(timestamp), subject
    return None


def staleness(log_output: str, now: int, stale_hours: float):
    """Return (is_stale, age_in_hours_or_None, human detail)."""
    latest = find_latest_pipeline_commit(log_output)
    if latest is None:
        return True, None, (
            f"Found no pipeline commit in the last {LOG_DEPTH} commits on main."
        )

    timestamp, subject = latest
    age_hours = (now - timestamp) / 3600.0
    detail = (
        f"Last pipeline commit was {age_hours:.1f}h ago: \"{subject}\"\n"
        f"Threshold: {stale_hours}h."
    )
    return age_hours > stale_hours, age_hours, detail


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stale-hours", type=float, default=DEFAULT_STALE_HOURS,
        help="hours without a pipeline commit before alerting",
    )
    args = parser.parse_args(argv)

    stale, age_hours, detail = staleness(git_log(), now_ts(), args.stale_hours)

    if stale:
        print(f"STALE: {detail}")
        detail = (
            f"{detail}\n\n"
            "No pipeline commit has landed in the expected window, which means "
            "the daily run did not happen at all -- not that a source failed. "
            "Check that the Mac Mini is awake and online and that the LaunchAgents "
            "(com.comiccaster.master / com.comiccaster.pass2) are loaded."
        )
        failed = {HEARTBEAT_SLUG: "heartbeat"}
    else:
        print(f"OK: {detail}")
        failed = {}

    # Covers only the heartbeat: this check examined no comic sources, so it
    # must never auto-close a source issue.
    return report(
        [HEARTBEAT_SLUG],
        failed,
        "heartbeat",
        date.today().isoformat(),
        detail,
    )


if __name__ == "__main__":
    sys.exit(main())
