#!/usr/bin/env python3
"""Decisions for the Far Side morning pass, one slot at a time.

The site publishes the Daily Dose at an unpredictable hour, so a LaunchAgent
retries every 30 minutes from 03:30 to 12:00 host-local time and ships on the
first slot that finds a complete dose. The orchestrator is shell
(scripts/local_farside_morning.sh), which CI cannot test, so every decision it
makes is delegated here:

  * slot           -- which date this slot targets, and whether it is the final
                      (noon) slot. Host-local date: a late coalesced 23:30
                      firing still targets today, not tomorrow's Eastern date.
  * evaluate       -- whether a dose file ships. Validity is the pipeline's own
                      count guard (check_scrape_counts.py); before the final
                      slot the dose must also have its expected count, 5 strips
                      on weekdays and 2 at weekends. Works on any path, so the
                      shell can evaluate origin/main's copy from a temp file.
  * safe-sync      -- whether the operator's checkout may be reset and committed
                      to: on main, HEAD an ancestor of origin/main, and no
                      tracked change except the slot's own daily file.
  * log            -- append one line per slot to logs/farside_morning_slots.log
                      (timestamp with UTC offset, date, outcome, count), so the
                      publish window can be read straight off the log.
  * last-miss      -- when the last slot found a date's dose unpublished or
                      incomplete; the shipping commit records it.
  * check-terminal -- for Pass 1: did the morning pass reach a terminal outcome
                      for a date? Skipped when the log cannot answer yet.

Pure functions take the clock, dates, git readings and file contents as
arguments; only `main` reads the clock, stdin or the filesystem.
"""

import argparse
import json
import sys
from collections import namedtuple
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.check_scrape_counts import (  # noqa: E402
    SOURCE_RULES,
    count_entries,
    evaluate as count_guard,
)

SOURCE_KEY = "farside_daily"
DEFAULT_LOG = Path("logs") / "farside_morning_slots.log"

# The noon slot ships anything the count guard accepts and is the only one
# that alerts. Any firing at or after noon is final, including a coalesced
# late one after the host slept through the schedule.
FINAL_HOUR = 12

WEEKDAY_COUNT = 5
WEEKEND_COUNT = 2

TERMINAL_OUTCOMES = frozenset({"already-shipped", "shipped", "final-unshipped"})
# Slots that found the site had not yet published the full dose.
MISS_OUTCOMES = frozenset({"unpublished", "incomplete"})

# argparse exits 2 on a usage error, which is also check-terminal's "skip".
# A broken invocation from Pass 1 must not read as a legitimate skip.
USAGE_ERROR_EXIT = 64

LogEntry = namedtuple("LogEntry", "timestamp date outcome count")


# --- Slot clock -------------------------------------------------------------

def slot_date(now):
    """The Daily Dose date a slot targets: the host-local date of `now`."""
    return now.date()


def is_final_slot(now):
    return now.hour >= FINAL_HOUR


def expected_count(day):
    """Strips in a complete dose: 5 Monday-Friday, 2 Saturday and Sunday."""
    return WEEKEND_COUNT if day.weekday() >= 5 else WEEKDAY_COUNT


# --- Ship decision ----------------------------------------------------------

def decide(data, day, final):
    """Return (decision, count) for parsed dose contents.

    decision is 'ship', 'incomplete' (valid but not yet the expected count,
    before the final slot) or 'unshippable' (fails the count guard).
    `data` is None when the file was missing or unreadable.
    """
    if not isinstance(data, dict):
        return "unshippable", 0
    count = count_entries(data, SOURCE_RULES[SOURCE_KEY]["payload"])
    ok, _ = count_guard(SOURCE_KEY, count)
    if not ok:
        return "unshippable", count
    if final or count == expected_count(day):
        return "ship", count
    return "incomplete", count


def load_dose(path):
    """Parsed JSON, or None when missing or unreadable. Impure."""
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None


def evaluate_dose_file(path, day, final):
    return decide(load_dose(path), day, final)


# --- Safe-sync verdict ------------------------------------------------------

def own_daily_path(day):
    return f"data/farside_daily_{day.isoformat()}.json"


def changed_paths(porcelain):
    """Paths named in `git status --porcelain` (v1) output.

    Each line is two status columns, a space, then the path; a rename or copy
    names both sides as `old -> new`, and both count as changed.
    """
    paths = []
    for line in porcelain.splitlines():
        if not line.strip():
            continue
        rest = line[3:]
        paths.extend(rest.split(" -> ") if " -> " in rest else [rest])
    return paths


def safe_sync_verdict(branch, head_is_ancestor, porcelain, day):
    """Return (safe, reason); reason is 'branch', 'ahead' or 'dirty'.

    The only tracked change a slot may sync over is its own daily file -- the
    one path it wrote itself, and which it saves and restores around the reset.
    """
    if branch != "main":
        return False, "branch"
    if not head_is_ancestor:
        return False, "ahead"
    own = own_daily_path(day)
    if any(p != own for p in changed_paths(porcelain)):
        return False, "dirty"
    return True, None


# --- Slot log ---------------------------------------------------------------

def format_log_line(now, day, outcome, count):
    """`<iso timestamp with offset>\\t<date>\\t<outcome>\\t<count>`.

    The offset keeps lines comparable across a DST change, so a naive
    timestamp is refused rather than written ambiguously.
    """
    if now.utcoffset() is None:
        raise ValueError("slot log timestamps need a UTC offset")
    return "\t".join([
        now.isoformat(timespec="seconds"), day.isoformat(), outcome, str(count),
    ])


def parse_log_line(line):
    """LogEntry for a well-formed line, else None."""
    fields = line.rstrip("\n").split("\t")
    if len(fields) != 4:
        return None
    try:
        timestamp = datetime.fromisoformat(fields[0])
        day = date.fromisoformat(fields[1])
        count = int(fields[3])
    except ValueError:
        return None
    if timestamp.utcoffset() is None or not fields[2]:
        return None
    return LogEntry(timestamp, day, fields[2], count)


def terminal_status(log_text, day):
    """Return (status, detail); status is 'terminal', 'missing' or 'skip'.

    'skip' when there is no log, or no entry dated before `day`: the morning
    pass was not yet installed on that day, so its silence proves nothing.
    """
    if log_text is None:
        return "skip", "no slot log yet; morning pass not installed or never ran"
    entries = [e for e in map(parse_log_line, log_text.splitlines()) if e]
    terminal = [e for e in entries if e.date == day and e.outcome in TERMINAL_OUTCOMES]
    if terminal:
        last = terminal[-1]
        return "terminal", (
            f"{day}: {last.outcome} ({last.count} strips) at "
            f"{last.timestamp.isoformat()}"
        )
    if not any(e.date < day for e in entries):
        return "skip", f"no slot log entry before {day}; morning pass was not running yet"
    seen = sorted({e.outcome for e in entries if e.date == day})
    return "missing", (
        f"{day}: no terminal outcome in the slot log "
        f"(seen: {', '.join(seen) if seen else 'nothing'})"
    )


def last_miss(log_text, day):
    """Timestamp of the last slot that found `day`'s dose unpublished or
    incomplete, or None. The shipping commit names it, so the commit itself
    records the publish window."""
    misses = [e for e in map(parse_log_line, (log_text or "").splitlines())
              if e and e.date == day and e.outcome in MISS_OUTCOMES]
    return misses[-1].timestamp if misses else None


# --- CLI ----------------------------------------------------------------------

class _Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(USAGE_ERROR_EXIT, f"{self.prog}: error: {message}\n")


def _iso_date(text):
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a YYYY-MM-DD date: {text!r}")


def _aware_datetime(text):
    try:
        value = datetime.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not an ISO-8601 datetime: {text!r}")
    if value.utcoffset() is None:
        raise argparse.ArgumentTypeError(f"--now needs a UTC offset: {text!r}")
    return value


def _outcome(text):
    if not text or any(ch.isspace() for ch in text):
        raise argparse.ArgumentTypeError(f"outcome must be one word: {text!r}")
    return text


def _count(text):
    try:
        value = int(text)
    except ValueError:
        value = -1
    if value < 0:
        raise argparse.ArgumentTypeError(f"count must be a whole number: {text!r}")
    return value


def _build_parser():
    parser = _Parser(description=__doc__,
                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True,
                                parser_class=_Parser)

    p = sub.add_parser("slot", help="print SLOT_DATE and SLOT_FINAL")
    p.add_argument("--now", type=_aware_datetime)

    p = sub.add_parser("evaluate", help="print DECISION and COUNT for a dose file")
    p.add_argument("--file", required=True)
    p.add_argument("--date", required=True, type=_iso_date)
    p.add_argument("--final", action="store_true")

    p = sub.add_parser("safe-sync",
                       help="read `git status --porcelain` on stdin, print SAFE")
    p.add_argument("--date", required=True, type=_iso_date)
    p.add_argument("--branch", required=True)
    p.add_argument("--head-is-ancestor", required=True, choices=["0", "1"])

    p = sub.add_parser("log", help="append one slot-log line")
    p.add_argument("--date", required=True, type=_iso_date)
    p.add_argument("--outcome", required=True, type=_outcome)
    p.add_argument("--count", required=True, type=_count)
    p.add_argument("--now", type=_aware_datetime)
    p.add_argument("--log", type=Path, default=DEFAULT_LOG)

    p = sub.add_parser("last-miss",
                       help="print when the last slot missed a date's dose, if any")
    p.add_argument("--date", required=True, type=_iso_date)
    p.add_argument("--log", type=Path, default=DEFAULT_LOG)

    p = sub.add_parser("check-terminal",
                       help="exit 0 terminal, 1 not terminal, 2 skip")
    p.add_argument("--date", required=True, type=_iso_date)
    p.add_argument("--log", type=Path, default=DEFAULT_LOG)
    return parser


def _now(args):
    return args.now or datetime.now().astimezone()


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)

    if args.command == "slot":
        now = _now(args)
        print(f"SLOT_DATE={slot_date(now).isoformat()}")
        print(f"SLOT_FINAL={1 if is_final_slot(now) else 0}")
        return 0

    if args.command == "evaluate":
        decision, count = evaluate_dose_file(args.file, args.date, args.final)
        print(f"DECISION={decision}")
        print(f"COUNT={count}")
        return 0

    if args.command == "safe-sync":
        safe, reason = safe_sync_verdict(
            args.branch, args.head_is_ancestor == "1", sys.stdin.read(), args.date
        )
        print("SAFE=1" if safe else f"SAFE=0 REASON={reason}")
        return 0

    if args.command == "log":
        line = format_log_line(_now(args), args.date, args.outcome, args.count)
        args.log.parent.mkdir(parents=True, exist_ok=True)
        with args.log.open("a") as fh:
            fh.write(line + "\n")
        return 0

    if args.command == "last-miss":
        try:
            text = args.log.read_text()
        except OSError:
            text = None
        stamp = last_miss(text, args.date)
        if stamp:
            print(stamp.isoformat())
        return 0

    # check-terminal
    try:
        text = args.log.read_text()
    except FileNotFoundError:
        text = None
    except OSError as exc:
        # Fail loud: an unreadable log must not pass as terminal or skip.
        print(f"{args.date}: slot log unreadable ({exc})")
        return 1
    status, detail = terminal_status(text, args.date)
    print(detail)
    return {"terminal": 0, "missing": 1, "skip": 2}[status]


if __name__ == "__main__":
    sys.exit(main())
