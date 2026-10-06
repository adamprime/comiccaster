"""The Comics Kingdom rerun schedule (comiccaster/comicskingdom_reruns.py).

A fixed vintage archive replays one archive date per delivery date, starting at
the range's first strip on the series' anchor and looping after the range ends.
The loop is the range rounded up to whole weeks, so every archive date lands on
its own weekday. These tests are the only proof of the loop: the first live one
is years away.
"""

from datetime import date, timedelta

import pytest

from comiccaster.comicskingdom_reruns import RerunSchedule, archive_date, rerun_schedule


BEETLE = RerunSchedule(start=date(1953, 10, 5), end=date(1967, 12, 31), anchor=date(2026, 10, 19))
MARK_TRAIL = RerunSchedule(start=date(1971, 7, 5), end=date(1974, 12, 31), anchor=date(2026, 10, 12))


class TestArchiveDate:
    def test_anchor_delivers_the_first_strip_and_a_sunday_its_sunday(self):
        # AE4: Monday 10-19 gets Monday 1953-10-05, Sunday 10-25 gets Sunday 1953-10-11.
        assert archive_date(BEETLE, date(2026, 10, 19)) == date(1953, 10, 5)
        assert archive_date(BEETLE, date(2026, 10, 25)) == date(1953, 10, 11)
        assert date(1953, 10, 11).weekday() == 6

    def test_every_archive_date_shares_its_delivery_days_weekday(self):
        for n in range(21):
            day = BEETLE.anchor + timedelta(days=n)
            assert archive_date(BEETLE, day).weekday() == day.weekday()

    def test_a_day_before_the_anchor_has_no_archive_date(self):
        assert archive_date(BEETLE, date(2026, 10, 18)) is None
        assert archive_date(BEETLE, date(2026, 1, 1)) is None

    def test_padding_days_point_past_the_end_and_day_l_loops_to_the_start(self):
        # AE6: 1971-07-05 (Mon) to 1974-12-31 (Tue) is 1276 days, padded to 1281.
        assert MARK_TRAIL.loop_days == 1281
        last_strip_day = MARK_TRAIL.anchor + timedelta(days=1275)
        assert archive_date(MARK_TRAIL, last_strip_day) == date(1974, 12, 31)
        for n in range(1276, 1281):
            assert archive_date(MARK_TRAIL, MARK_TRAIL.anchor + timedelta(days=n)) > MARK_TRAIL.end
        day_l = MARK_TRAIL.anchor + timedelta(days=1281)
        assert day_l.weekday() == 0
        assert archive_date(MARK_TRAIL, day_l) == date(1971, 7, 5)

    def test_second_loop_maps_each_day_like_the_first(self):
        for n in (0, 1, 6, 400, 1275):
            first = MARK_TRAIL.anchor + timedelta(days=n)
            second = first + timedelta(days=MARK_TRAIL.loop_days)
            assert archive_date(MARK_TRAIL, second) == archive_date(MARK_TRAIL, first)

    @pytest.mark.parametrize("day", [date(2026, 11, 1), date(2027, 3, 14), date(2028, 2, 29), date(2028, 3, 1)])
    def test_dst_changes_and_leap_days_are_plain_day_counts(self, day):
        assert archive_date(BEETLE, day) == BEETLE.start + (day - BEETLE.anchor)

    def test_a_range_that_is_whole_weeks_is_not_padded(self):
        schedule = RerunSchedule(start=date(1950, 1, 2), end=date(1950, 1, 15), anchor=date(2026, 10, 19))
        assert schedule.loop_days == 14
        assert archive_date(schedule, date(2026, 11, 2)) == date(1950, 1, 2)


class TestRerunSchedule:
    def test_reads_the_three_catalog_fields(self):
        comic = {"slug": "beetle-bailey-vintage", "rerun_start": "1953-10-05",
                 "rerun_end": "1967-12-31", "rerun_anchor": "2026-10-19"}
        assert rerun_schedule(comic) == BEETLE

    def test_a_comic_without_rerun_fields_has_no_schedule(self):
        assert rerun_schedule({"slug": "zits"}) is None
        assert rerun_schedule({"slug": "bringing-up-father", "source_variant": "vintage"}) is None
