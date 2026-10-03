"""Tests for farside_morning.py, the Far Side morning pass's decision helper.

The morning pass is a shell orchestrator that cannot be unit-tested on CI, so
every decision it makes lives in this helper: which date a slot targets,
whether it is the final (noon) slot, whether a scraped dose ships, whether the
operator's checkout is safe to sync, and the slot log Pass 1 reads back.

Clock, git-state readings and file contents are inputs here. Files go to
tmp_path rather than being mocked, so real JSON loading and log parsing run.
"""

import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from scripts.farside_morning import (
    decide,
    evaluate_dose_file,
    expected_count,
    format_log_line,
    last_miss,
    is_final_slot,
    main,
    parse_log_line,
    safe_sync_verdict,
    slot_date,
    terminal_status,
)

CDT = timezone(timedelta(hours=-5))
CST = timezone(timedelta(hours=-6))

MONDAY = date(2026, 10, 5)
TUESDAY = date(2026, 10, 6)
SATURDAY = date(2026, 10, 10)
SUNDAY = date(2026, 10, 11)


def at(day, hour, minute=0, tz=CDT):
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=tz)


def dose(tmp_path, day, n, name=None):
    """A daily file shaped like data/farside_daily_<date>.json on main."""
    p = tmp_path / (name or f'farside_daily_{day.isoformat()}.json')
    p.write_text(json.dumps({
        'target_date': day.isoformat(),
        'scraped_at': '2026-10-05T11:00:00+00:00',
        'comics': [
            {'id': str(22800 + i), 'date': day.isoformat(),
             'url': f'https://www.thefarside.com/x/{i}'}
            for i in range(n)
        ],
    }))
    return p


def run(capsys, argv):
    code = main(argv)
    return code, capsys.readouterr().out


# --- Slot clock ------------------------------------------------------------

class TestSlotClock:
    def test_final_slot_true_at_noon(self):
        assert is_final_slot(at(MONDAY, 12, 0))

    def test_final_slot_true_at_coalesced_late_firing(self):
        assert is_final_slot(at(MONDAY, 23, 30))

    def test_final_slot_false_at_1130(self):
        assert not is_final_slot(at(MONDAY, 11, 30))

    def test_slot_date_at_2330_local_is_the_local_date(self):
        """23:30 CDT is 00:30 the next day in Eastern; the slot stays local."""
        assert slot_date(at(MONDAY, 23, 30)) == MONDAY

    def test_slot_date_early_morning(self):
        assert slot_date(at(MONDAY, 3, 30)) == MONDAY


class TestExpectedCount:
    @pytest.mark.parametrize('day,n', [
        (MONDAY, 5), (TUESDAY, 5), (date(2026, 10, 9), 5),  # Friday
        (SATURDAY, 2), (SUNDAY, 2),
    ])
    def test_weekday_five_weekend_two(self, day, n):
        assert expected_count(day) == n


# --- Ship decision -----------------------------------------------------------

class TestShipDecision:
    def test_monday_five_strips_before_noon_ships(self, tmp_path):
        p = dose(tmp_path, MONDAY, 5)
        assert evaluate_dose_file(p, MONDAY, final=False) == ('ship', 5)

    def test_monday_three_strips_before_noon_is_incomplete(self, tmp_path):
        p = dose(tmp_path, MONDAY, 3)
        assert evaluate_dose_file(p, MONDAY, final=False) == ('incomplete', 3)

    def test_saturday_two_strips_before_noon_ships(self, tmp_path):
        p = dose(tmp_path, SATURDAY, 2)
        assert evaluate_dose_file(p, SATURDAY, final=False) == ('ship', 2)

    def test_final_slot_ships_a_short_weekday_dose(self, tmp_path):
        p = dose(tmp_path, TUESDAY, 3)
        assert evaluate_dose_file(p, TUESDAY, final=True) == ('ship', 3)

    def test_final_slot_empty_dose_is_unshippable(self, tmp_path):
        p = dose(tmp_path, TUESDAY, 0)
        assert evaluate_dose_file(p, TUESDAY, final=True) == ('unshippable', 0)

    def test_final_slot_missing_file_is_unshippable(self, tmp_path):
        p = tmp_path / 'farside_daily_2026-10-06.json'
        assert evaluate_dose_file(p, TUESDAY, final=True) == ('unshippable', 0)

    def test_unreadable_json_is_unshippable(self, tmp_path):
        p = tmp_path / 'farside_daily_2026-10-06.json'
        p.write_text('{not json')
        assert evaluate_dose_file(p, TUESDAY, final=False) == ('unshippable', 0)

    def test_wrong_shape_is_unshippable_not_a_crash(self, tmp_path):
        p = tmp_path / 'farside_daily_2026-10-06.json'
        p.write_text('[1, 2, 3, 4, 5]')
        assert evaluate_dose_file(p, TUESDAY, final=False) == ('unshippable', 0)

    def test_evaluates_any_path_with_an_explicit_date(self, tmp_path):
        """The shell extracts origin/main's copy to a temp file (KTD2)."""
        p = dose(tmp_path, SATURDAY, 2, name='origin-copy.tmp')
        assert evaluate_dose_file(p, SATURDAY, final=False) == ('ship', 2)

    def test_more_than_expected_waits_before_noon(self):
        """R3: before noon only the expected count ships."""
        assert decide({'comics': [{}] * 6}, MONDAY, final=False) == ('incomplete', 6)


# --- Safe-sync verdict -------------------------------------------------------

DAILY = 'data/farside_daily_2026-10-05.json'


class TestSafeSync:
    def test_clean_main_ancestor_is_safe(self):
        assert safe_sync_verdict('main', True, '', MONDAY) == (True, None)

    def test_only_own_daily_file_changed_is_safe(self):
        status = f' M {DAILY}\n'
        assert safe_sync_verdict('main', True, status, MONDAY) == (True, None)

    def test_own_daily_file_staged_is_safe(self):
        status = f'M  {DAILY}\n'
        assert safe_sync_verdict('main', True, status, MONDAY) == (True, None)

    def test_other_branch_is_unsafe(self):
        assert safe_sync_verdict('fix/thing', True, '', MONDAY) == (False, 'branch')

    def test_detached_head_is_unsafe(self):
        assert safe_sync_verdict('HEAD', True, '', MONDAY) == (False, 'branch')

    def test_unpushed_commit_is_unsafe(self):
        assert safe_sync_verdict('main', False, '', MONDAY) == (False, 'ahead')

    def test_other_unstaged_change_is_unsafe(self):
        status = f' M {DAILY}\n M scripts/scrape_farside.py\n'
        assert safe_sync_verdict('main', True, status, MONDAY) == (False, 'dirty')

    def test_other_staged_change_is_unsafe(self):
        status = 'A  docs/notes.md\n'
        assert safe_sync_verdict('main', True, status, MONDAY) == (False, 'dirty')

    def test_another_days_daily_file_is_unsafe(self):
        status = ' M data/farside_daily_2026-10-04.json\n'
        assert safe_sync_verdict('main', True, status, MONDAY) == (False, 'dirty')

    def test_rename_away_from_own_file_is_unsafe(self):
        status = f'R  {DAILY} -> data/elsewhere.json\n'
        assert safe_sync_verdict('main', True, status, MONDAY) == (False, 'dirty')

    def test_rename_onto_own_file_is_unsafe(self):
        status = f'R  data/elsewhere.json -> {DAILY}\n'
        assert safe_sync_verdict('main', True, status, MONDAY) == (False, 'dirty')


# --- Slot log ----------------------------------------------------------------

class TestSlotLog:
    def test_line_carries_offset_timestamp_date_outcome_count(self):
        line = format_log_line(at(MONDAY, 6, 0), MONDAY, 'shipped', 5)
        assert line == '2026-10-05T06:00:00-05:00\t2026-10-05\tshipped\t5'

    def test_naive_timestamp_is_refused(self):
        with pytest.raises(ValueError):
            format_log_line(datetime(2026, 10, 5, 6, 0), MONDAY, 'shipped', 5)

    def test_lines_either_side_of_dst_change_parse_and_order(self):
        before = format_log_line(
            datetime(2026, 10, 31, 23, 30, tzinfo=CDT), date(2026, 10, 31),
            'final-unshipped', 0)
        after = format_log_line(
            datetime(2026, 11, 1, 3, 30, tzinfo=CST), date(2026, 11, 1),
            'unpublished', 0)
        b, a = parse_log_line(before), parse_log_line(after)
        assert b.timestamp.utcoffset() == timedelta(hours=-5)
        assert a.timestamp.utcoffset() == timedelta(hours=-6)
        assert (b.date, b.outcome, b.count) == (date(2026, 10, 31), 'final-unshipped', 0)
        assert (a.date, a.outcome, a.count) == (date(2026, 11, 1), 'unpublished', 0)
        # 04:30Z before 09:30Z: comparable across the offset change.
        assert a.timestamp - b.timestamp == timedelta(hours=5)

    def test_malformed_line_parses_as_none(self):
        assert parse_log_line('garbage') is None
        assert parse_log_line('') is None


def log_text(*rows):
    return ''.join(
        format_log_line(ts, d, outcome, n) + '\n' for ts, d, outcome, n in rows
    )


class TestTerminalStatus:
    HISTORY = (at(MONDAY, 11, 30), MONDAY, 'shipped', 5)

    @pytest.mark.parametrize('outcome', ['shipped', 'already-shipped', 'final-unshipped'])
    def test_terminal_outcomes(self, outcome):
        text = log_text(self.HISTORY, (at(TUESDAY, 9, 0), TUESDAY, outcome, 5))
        assert terminal_status(text, TUESDAY)[0] == 'terminal'

    def test_only_unpublished_and_lock_busy_is_not_terminal(self):
        text = log_text(
            self.HISTORY,
            (at(TUESDAY, 3, 30), TUESDAY, 'unpublished', 0),
            (at(TUESDAY, 4, 0), TUESDAY, 'lock-busy', 0),
        )
        assert terminal_status(text, TUESDAY)[0] == 'missing'

    def test_no_line_for_the_date_is_not_terminal(self):
        assert terminal_status(log_text(self.HISTORY), TUESDAY)[0] == 'missing'

    def test_terminal_for_another_date_does_not_count(self):
        text = log_text(self.HISTORY, (at(TUESDAY, 3, 30), TUESDAY, 'unpublished', 0))
        # Monday shipped; Tuesday did not.
        assert terminal_status(text, TUESDAY)[0] == 'missing'

    def test_missing_log_is_skip(self):
        assert terminal_status(None, TUESDAY)[0] == 'skip'

    def test_only_entries_dated_checked_day_or_later_is_skip(self):
        """Install day: manual runs dated the checked day, nothing older."""
        wed = TUESDAY + timedelta(days=1)
        text = log_text(
            (at(TUESDAY, 10, 0), TUESDAY, 'unpublished', 0),
            (at(wed, 3, 30), wed, 'lock-busy', 0),
        )
        assert terminal_status(text, TUESDAY)[0] == 'skip'

    def test_malformed_lines_are_ignored(self):
        text = 'garbage\n' + log_text(self.HISTORY) + 'more\tjunk\n'
        assert terminal_status(text, TUESDAY)[0] == 'missing'


# --- CLI ---------------------------------------------------------------------

class TestMainSlot:
    def test_prints_date_and_final_flag(self, capsys):
        code, out = run(capsys, ['slot', '--now', '2026-10-05T23:30:00-05:00'])
        assert code == 0
        assert out == 'SLOT_DATE=2026-10-05\nSLOT_FINAL=1\n'

    def test_not_final_before_noon(self, capsys):
        code, out = run(capsys, ['slot', '--now', '2026-10-05T11:30:00-05:00'])
        assert code == 0
        assert out == 'SLOT_DATE=2026-10-05\nSLOT_FINAL=0\n'

    def test_default_clock_is_real_local_time(self, capsys):
        code, out = run(capsys, ['slot'])
        assert code == 0
        assert out.startswith(f'SLOT_DATE={datetime.now().astimezone().date().isoformat()}\n')


class TestMainEvaluate:
    def test_ship(self, tmp_path, capsys):
        p = dose(tmp_path, MONDAY, 5)
        code, out = run(capsys, ['evaluate', '--file', str(p), '--date', '2026-10-05'])
        assert (code, out) == (0, 'DECISION=ship\nCOUNT=5\n')

    def test_incomplete(self, tmp_path, capsys):
        p = dose(tmp_path, MONDAY, 3)
        code, out = run(capsys, ['evaluate', '--file', str(p), '--date', '2026-10-05'])
        assert (code, out) == (0, 'DECISION=incomplete\nCOUNT=3\n')

    def test_final_ships_short_dose(self, tmp_path, capsys):
        p = dose(tmp_path, MONDAY, 3)
        code, out = run(capsys, ['evaluate', '--file', str(p),
                                 '--date', '2026-10-05', '--final'])
        assert (code, out) == (0, 'DECISION=ship\nCOUNT=3\n')

    def test_missing_file_is_unshippable(self, tmp_path, capsys):
        code, out = run(capsys, ['evaluate', '--file', str(tmp_path / 'nope.json'),
                                 '--date', '2026-10-05', '--final'])
        assert (code, out) == (0, 'DECISION=unshippable\nCOUNT=0\n')


class TestMainSafeSync:
    def test_safe(self, monkeypatch, capsys):
        monkeypatch.setattr('sys.stdin', _Stdin(f' M {DAILY}\n'))
        code, out = run(capsys, ['safe-sync', '--date', '2026-10-05',
                                 '--branch', 'main', '--head-is-ancestor', '1'])
        assert (code, out) == (0, 'SAFE=1\n')

    @pytest.mark.parametrize('branch,anc,status,reason', [
        ('feature', '1', '', 'branch'),
        ('main', '0', '', 'ahead'),
        ('main', '1', ' M README.md\n', 'dirty'),
    ])
    def test_unsafe(self, monkeypatch, capsys, branch, anc, status, reason):
        monkeypatch.setattr('sys.stdin', _Stdin(status))
        code, out = run(capsys, ['safe-sync', '--date', '2026-10-05',
                                 '--branch', branch, '--head-is-ancestor', anc])
        assert (code, out) == (0, f'SAFE=0 REASON={reason}\n')


class _Stdin:
    def __init__(self, text):
        self._text = text

    def read(self):
        return self._text


class TestMainLog:
    def test_appends_line_creating_the_directory(self, tmp_path, capsys):
        log = tmp_path / 'logs' / 'farside_morning_slots.log'
        assert main(['log', '--date', '2026-10-05', '--outcome', 'unpublished',
                     '--count', '0', '--log', str(log),
                     '--now', '2026-10-05T03:30:00-05:00']) == 0
        assert main(['log', '--date', '2026-10-05', '--outcome', 'shipped',
                     '--count', '5', '--log', str(log),
                     '--now', '2026-10-05T04:00:00-05:00']) == 0
        assert log.read_text() == (
            '2026-10-05T03:30:00-05:00\t2026-10-05\tunpublished\t0\n'
            '2026-10-05T04:00:00-05:00\t2026-10-05\tshipped\t5\n'
        )

    def test_default_clock_writes_an_offset(self, tmp_path):
        log = tmp_path / 'slots.log'
        assert main(['log', '--date', '2026-10-05', '--outcome', 'lock-busy',
                     '--count', '0', '--log', str(log)]) == 0
        entry = parse_log_line(log.read_text().strip())
        assert entry is not None and entry.timestamp.utcoffset() is not None

    def test_default_log_path_is_relative_to_cwd(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert main(['log', '--date', '2026-10-05', '--outcome', 'shipped',
                     '--count', '5', '--now', '2026-10-05T06:00:00-05:00']) == 0
        assert (tmp_path / 'logs' / 'farside_morning_slots.log').read_text() == (
            '2026-10-05T06:00:00-05:00\t2026-10-05\tshipped\t5\n'
        )

    def test_outcome_with_whitespace_is_refused(self, tmp_path):
        """A tab or space would corrupt the four-column format."""
        log = tmp_path / 'slots.log'
        with pytest.raises(SystemExit) as exc:
            main(['log', '--date', '2026-10-05', '--outcome', 'not shipped',
                  '--count', '0', '--log', str(log)])
        assert exc.value.code != 0
        assert not log.exists()


class TestLastMiss:
    def lines(self, *entries):
        return "\n".join(format_log_line(at(day, h, m), day, outcome, n)
                         for day, h, m, outcome, n in entries)

    def test_returns_the_last_unpublished_or_incomplete_slot_for_the_date(self):
        text = self.lines(
            (MONDAY, 4, 0, 'unpublished', 0),
            (MONDAY, 4, 30, 'incomplete', 3),
            (MONDAY, 5, 0, 'deferred-checkout', 5),
            (MONDAY, 5, 30, 'shipped', 5),
        )
        assert last_miss(text, MONDAY) == at(MONDAY, 4, 30)

    def test_ignores_other_dates(self):
        sunday = MONDAY - timedelta(days=1)
        text = self.lines((sunday, 11, 30, 'unpublished', 0), (MONDAY, 3, 30, 'shipped', 5))
        assert last_miss(text, MONDAY) is None

    def test_none_without_a_log(self):
        assert last_miss(None, MONDAY) is None


class TestMainLastMiss:
    def test_prints_the_last_miss_timestamp(self, capsys, tmp_path):
        log = tmp_path / 'slots.log'
        log.write_text(format_log_line(at(MONDAY, 4, 0), MONDAY, 'unpublished', 0) + '\n')
        code, out = run(capsys, ['last-miss', '--date', '2026-10-05', '--log', str(log)])
        assert (code, out) == (0, '2026-10-05T04:00:00-05:00\n')

    def test_prints_nothing_when_no_slot_missed(self, capsys, tmp_path):
        code, out = run(capsys, ['last-miss', '--date', '2026-10-05',
                                 '--log', str(tmp_path / 'absent.log')])
        assert (code, out) == (0, '')


class TestMainCheckTerminal:
    def write_log(self, tmp_path, *rows):
        log = tmp_path / 'slots.log'
        log.write_text(log_text(*rows))
        return log

    def test_terminal_exits_0(self, tmp_path, capsys):
        log = self.write_log(tmp_path, TestTerminalStatus.HISTORY,
                             (at(TUESDAY, 6, 0), TUESDAY, 'shipped', 5))
        code, out = run(capsys, ['check-terminal', '--date', '2026-10-06', '--log', str(log)])
        assert code == 0
        assert out.count('\n') == 1 and 'shipped' in out

    def test_missing_terminal_exits_1(self, tmp_path, capsys):
        log = self.write_log(tmp_path, TestTerminalStatus.HISTORY,
                             (at(TUESDAY, 6, 0), TUESDAY, 'unpublished', 0))
        code, out = run(capsys, ['check-terminal', '--date', '2026-10-06', '--log', str(log)])
        assert code == 1
        assert out.count('\n') == 1

    def test_missing_log_exits_2(self, tmp_path, capsys):
        code, out = run(capsys, ['check-terminal', '--date', '2026-10-06',
                                 '--log', str(tmp_path / 'absent.log')])
        assert code == 2
        assert out.count('\n') == 1

    def test_no_older_entries_exits_2(self, tmp_path, capsys):
        log = self.write_log(tmp_path, (at(TUESDAY, 6, 0), TUESDAY, 'unpublished', 0))
        code, _ = run(capsys, ['check-terminal', '--date', '2026-10-06', '--log', str(log)])
        assert code == 2

    def test_usage_error_is_not_mistaken_for_skip(self, capsys):
        """argparse exits 2 on bad input, which the shell would read as skip.

        An empty --date (a failed `date` computation in Pass 1) must not
        silently disable the check.
        """
        with pytest.raises(SystemExit) as exc:
            main(['check-terminal', '--date', ''])
        assert exc.value.code not in (0, 1, 2)
