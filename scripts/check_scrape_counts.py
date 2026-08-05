#!/usr/bin/env python3
"""Assert a scrape produced a plausible number of entries, not just a file.

The pipeline's invariant guard asked only whether `data/<src>_$DATE.json`
exists. That misses the quiet half of the failure space: a scrape that runs,
writes a well-formed file, and puts almost nothing in it.

This is not hypothetical. On 2026-08-03 TinyView scraped zero comics, wrote
`[]`, and the run finished "ALL SUCCESS" with no alert -- most likely a session
that had lapsed before the Monday-morning run. Nothing surfaced it, because the
feed generator builds each feed from a 90-day window, so a missing day looks
identical to a healthy feed with one fewer entry. The practical detection
mechanism for that class of failure has been a subscriber opening an issue.

Minimums are set from observed history (14 days as of 2026-08-05), deliberately
well below the real floor so ordinary variation never cries wolf. They are here
to catch a collapse, not to police daily wobble.

Register a new source in SOURCE_RULES -- the same "declare it in one place"
shape as scraper_factory.py, so adding a source stays a registration rather
than a new branch.
"""

import argparse
import json
import re
import sys
from pathlib import Path

# payload: key holding the list of scraped items, or None when the file *is*
#          the list. minimum: fewest entries a healthy scrape may produce.
SOURCE_RULES = {
    # Observed 210-282/day. Varies with the reactive favorites page, so the
    # floor sits far below the range and only catches a real collapse.
    "comics":        {"payload": None,       "minimum": 100,
                      "note": "GoComics"},
    # Fixed catalog: exactly 153 every day for 14 days. A partial scrape is
    # therefore detectable with a tight floor.
    "comicskingdom": {"payload": None,       "minimum": 140,
                      "note": "Comics Kingdom (catalog of 153)"},
    # Genuinely variable 0-7 -- depends what publishers posted. `> 0` is the
    # only assertion the data supports, and it is exactly what 2026-08-03
    # needed.
    "tinyview":      {"payload": None,       "minimum": 1,
                      "note": "TinyView"},
    # Stable at 10/day; looks like a fixed page size. Half of that catches a
    # collapse while tolerating a genuinely short day.
    "newyorker":     {"payload": "cartoons", "minimum": 5,
                      "note": "New Yorker"},
    "creators":      {"payload": "comics",   "minimum": 5,
                      "note": "Creators Syndicate"},
    # Upstream picks the daily set and it has legitimately been as low as 2.
    "farside_daily": {"payload": "comics",   "minimum": 1,
                      "note": "Far Side Daily Dose"},
    # Deliberate exemption, and NOT a masked bug: New Stuff has published once
    # in the whole life of this feed, so an empty result is its normal steady
    # state rather than evidence of a failed scrape. (Access is separately
    # blocked by bot protection; the recorded decision was to keep the feed.)
    # A minimum of 1 would open an issue every morning forever, which is how
    # alerting gets ignored. Contrast farside_daily, which always has content.
    "farside_new":   {"payload": "comics",   "minimum": 0,
                      "note": "Far Side New Stuff (known to publish very rarely)"},
    "mrboffo":       {"payload": "comics",   "minimum": 1,
                      "note": "Mr. Boffo"},
}

# data/<key>_YYYY-MM-DD.json -> <key>
DATED_FILENAME = re.compile(r"^(?P<key>.+)_\d{4}-\d{2}-\d{2}\.json$")


def derive_source_key(path):
    """Map a dated scrape filename back to its SOURCE_RULES key."""
    match = DATED_FILENAME.match(Path(path).name)
    return match.group("key") if match else None


def count_entries(data, payload_key):
    """Number of scraped items. A shape change reads as 0, never as a crash."""
    payload = data if payload_key is None else data.get(payload_key, [])
    try:
        return len(payload)
    except TypeError:
        return 0


def evaluate(source_key, count):
    """Return (ok, detail).

    Unknown sources pass. Registering one is a deliberate step, and a brand-new
    scraper should not turn its first run red -- but the message says plainly
    that nothing was verified, so it cannot be mistaken for a check that ran.
    """
    rule = SOURCE_RULES.get(source_key)
    if rule is None:
        return True, (
            f"{source_key}: not registered in SOURCE_RULES, so entry count was "
            f"NOT verified ({count} found). Add it to check_scrape_counts.py."
        )

    minimum = rule["minimum"]
    note = rule["note"]

    if minimum == 0:
        return True, (
            f"{note}: {count} entries, not checked -- empty is the normal state "
            "for this source, exempt by design."
        )

    if count < minimum:
        return False, (
            f"{note}: only {count} entries, expected at least {minimum}. The "
            "file exists but the scrape did not produce usable data."
        )

    return True, f"{note}: {count} entries (minimum {minimum})."


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", help="scrape JSON to check")
    args = parser.parse_args(argv)

    path = Path(args.path)
    source_key = derive_source_key(path)

    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        print(f"❌ {path.name}: file missing")
        return 1
    except (OSError, json.JSONDecodeError) as exc:
        print(f"❌ {path.name}: unreadable ({exc})")
        return 1

    rule = SOURCE_RULES.get(source_key) or {}
    count = count_entries(data, rule.get("payload"))
    ok, detail = evaluate(source_key, count)

    print(f"{'✅' if ok else '❌'} {detail}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
