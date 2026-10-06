"""The rerun schedule for Comics Kingdom's fixed vintage archives.

32 vintage series stopped advancing on Comics Kingdom: each one's newest post has
not changed since February 2026, though every archive date can still be loaded.
ComicCaster replays each archive itself, one archive date per delivery date:

    archive date = start + ((delivery - anchor) mod L)

``start`` and ``end`` bound a densely covered stretch of the archive, and
``anchor`` is the delivery date that gets ``start``, on the same weekday. ``L`` is
the range rounded up to whole weeks, so every archive date lands on its own
weekday, loop after loop: Sunday strips arrive on Sundays. The padding days at the
end of a loop point past ``end``; the page then shows the last strip, which is not
that date's own, so nothing is delivered.

The schedule depends only on the catalog's three values and the delivery date. It
never reads the clock and keeps no cursor, so any host and any push-recovery
regeneration get the same answer (a cursor file would be reverted by push
recovery's ``git reset --hard``).

Selenium-free on purpose: the network-free feed generator may import this module.
"""

from datetime import date, timedelta
from typing import Dict, NamedTuple, Optional


class RerunSchedule(NamedTuple):
    start: date
    end: date
    anchor: date

    @property
    def loop_days(self) -> int:
        """The range's length in days, rounded up to whole weeks."""
        days = (self.end - self.start).days + 1
        return -(-days // 7) * 7


def rerun_schedule(comic: Dict) -> Optional[RerunSchedule]:
    """The catalog entry's schedule, or None for a comic that is not rerun.

    Only the 32 fixed archives carry ``rerun_start``, ``rerun_end`` and
    ``rerun_anchor`` (YYYY-MM-DD). Bringing Up Father is vintage too, but Comics
    Kingdom still reposts it daily, so it carries none.
    """
    if 'rerun_start' not in comic:
        return None
    return RerunSchedule(
        start=date.fromisoformat(comic['rerun_start']),
        end=date.fromisoformat(comic['rerun_end']),
        anchor=date.fromisoformat(comic['rerun_anchor']),
    )


def archive_date(schedule: RerunSchedule, delivery: date) -> Optional[date]:
    """The archive date delivered on ``delivery``, or None before the anchor."""
    if delivery < schedule.anchor:
        return None
    offset = (delivery - schedule.anchor).days % schedule.loop_days
    return schedule.start + timedelta(days=offset)
