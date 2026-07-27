"""Tests for report_pipeline_failures.py.

The `gh` CLI is mocked throughout -- these tests never touch the network and
never create a real issue.
"""

import json
import os
import subprocess
import sys

import pytest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from scripts.report_pipeline_failures import (
    LABEL,
    MARKER_PREFIX,
    SOURCE_NAMES,
    issue_body,
    issue_title,
    main,
    open_issues_by_key,
    parse_failed,
    report,
)


ALL_COVERED = [
    'gocomics', 'comicskingdom', 'tinyview', 'newyorker',
    'farside', 'creators', 'mrboffo', 'push',
]


def gh_responder(open_issues=None, labels=None):
    """Build a fake `gh` that answers list queries and records mutations.

    `open_issues` maps a marker key -> issue number.
    """
    open_issues = open_issues or {}
    labels = labels if labels is not None else [LABEL]

    def fake_gh(*args):
        if args[:2] == ('label', 'list'):
            return json.dumps([{'name': n} for n in labels])
        if args[:2] == ('issue', 'list'):
            return json.dumps([
                {'number': num, 'body': f'blah\n{MARKER_PREFIX}{key}\nblah'}
                for key, num in open_issues.items()
            ])
        return ''

    return fake_gh


@pytest.fixture
def gh_mock():
    with patch('scripts.report_pipeline_failures.gh') as m:
        m.side_effect = gh_responder()
        yield m


def calls_of(gh_mock, *prefix):
    """All recorded gh calls whose leading args match `prefix`."""
    return [c.args for c in gh_mock.call_args_list if c.args[:len(prefix)] == prefix]


class TestParseFailed:
    def test_parses_source_and_kind(self):
        assert parse_failed('tinyview:scrape,push:push') == {
            'tinyview': 'scrape',
            'push': 'push',
        }

    def test_empty_string_is_no_failures(self):
        assert parse_failed('') == {}
        assert parse_failed('   ') == {}

    def test_tolerates_whitespace_and_blank_entries(self):
        assert parse_failed(' gocomics:scrape , ,creators:invariant ') == {
            'gocomics': 'scrape',
            'creators': 'invariant',
        }

    def test_slug_without_kind_defaults_to_unknown(self):
        assert parse_failed('mrboffo') == {'mrboffo': 'unknown'}


class TestOpenIssuesByKey:
    def test_maps_marker_key_to_issue_number(self, gh_mock):
        gh_mock.side_effect = gh_responder(open_issues={'tinyview': 42, 'push': 7})
        assert open_issues_by_key() == {'tinyview': 42, 'push': 7}

    def test_ignores_issues_without_a_marker(self, gh_mock):
        gh_mock.side_effect = lambda *a: json.dumps(
            [{'number': 1, 'body': 'no marker here'}]
        ) if a[:2] == ('issue', 'list') else ''
        assert open_issues_by_key() == {}

    def test_handles_null_body(self, gh_mock):
        gh_mock.side_effect = lambda *a: json.dumps(
            [{'number': 1, 'body': None}]
        ) if a[:2] == ('issue', 'list') else ''
        assert open_issues_by_key() == {}

    def test_queries_open_issues(self, gh_mock):
        gh_mock.side_effect = gh_responder()
        open_issues_by_key()
        args = calls_of(gh_mock, 'issue', 'list')[0]
        assert '--state' in args and args[args.index('--state') + 1] == 'open'

    def test_does_not_filter_by_label(self, gh_mock):
        """Label-filtered listing is eventually consistent on GitHub's side.

        Right after an issue is created it can be missing from a label-filtered
        list for ~a minute, which made the next run open a duplicate instead of
        commenting. The body marker is authoritative; the label is cosmetic.
        """
        gh_mock.side_effect = gh_responder()
        open_issues_by_key()
        assert '--label' not in calls_of(gh_mock, 'issue', 'list')[0]

    def test_duplicate_markers_resolve_to_the_oldest_issue(self, gh_mock):
        gh_mock.side_effect = lambda *a: json.dumps([
            {'number': 172, 'body': f'{MARKER_PREFIX}tinyview'},
            {'number': 171, 'body': f'{MARKER_PREFIX}tinyview'},
        ]) if a[:2] == ('issue', 'list') else ''
        assert open_issues_by_key() == {'tinyview': 171}


class TestOpensIssueOnFailure:
    def test_creates_issue_when_none_open(self, gh_mock):
        report(ALL_COVERED, {'tinyview': 'scrape'}, run='pass1', date='2026-07-27')

        created = calls_of(gh_mock, 'issue', 'create')
        assert len(created) == 1
        args = created[0]
        body = args[args.index('--body') + 1]
        assert f'{MARKER_PREFIX}tinyview' in body
        assert args[args.index('--label') + 1] == LABEL

    def test_title_names_the_source_and_kind(self):
        assert issue_title('tinyview', 'scrape') == '[pipeline] TinyView scrape failed'

    def test_body_records_run_date_and_kind(self):
        body = issue_body('creators', 'invariant', 'pass1', '2026-07-27', 'tail')
        assert f'{MARKER_PREFIX}creators' in body
        assert '2026-07-27' in body
        assert 'pass1' in body
        assert 'invariant' in body
        assert 'tail' in body

    def test_one_issue_per_failing_source(self, gh_mock):
        report(
            ALL_COVERED,
            {'tinyview': 'scrape', 'creators': 'scrape', 'push': 'push'},
            run='pass1', date='2026-07-27',
        )
        assert len(calls_of(gh_mock, 'issue', 'create')) == 3

    def test_does_not_close_anything_when_opening(self, gh_mock):
        report(ALL_COVERED, {'tinyview': 'scrape'}, run='pass1', date='2026-07-27')
        assert calls_of(gh_mock, 'issue', 'close') == []


class TestCommentsOnRecurrence:
    def test_comments_instead_of_opening_duplicate(self, gh_mock):
        gh_mock.side_effect = gh_responder(open_issues={'tinyview': 42})

        report(ALL_COVERED, {'tinyview': 'scrape'}, run='pass1', date='2026-07-28')

        assert calls_of(gh_mock, 'issue', 'create') == []
        commented = calls_of(gh_mock, 'issue', 'comment')
        assert len(commented) == 1
        assert commented[0][2] == '42'
        assert '2026-07-28' in commented[0][commented[0].index('--body') + 1]

    def test_does_not_close_a_still_failing_source(self, gh_mock):
        gh_mock.side_effect = gh_responder(open_issues={'tinyview': 42})
        report(ALL_COVERED, {'tinyview': 'scrape'}, run='pass1', date='2026-07-28')
        assert calls_of(gh_mock, 'issue', 'close') == []


class TestAutoCloseOnRecovery:
    def test_comments_and_closes_when_source_recovers(self, gh_mock):
        gh_mock.side_effect = gh_responder(open_issues={'tinyview': 42})

        report(ALL_COVERED, {}, run='pass1', date='2026-07-29')

        closed = calls_of(gh_mock, 'issue', 'close')
        assert len(closed) == 1
        assert closed[0][2] == '42'
        commented = calls_of(gh_mock, 'issue', 'comment')
        assert len(commented) == 1
        assert commented[0][2] == '42'

    def test_no_action_for_healthy_source_without_issue(self, gh_mock):
        report(ALL_COVERED, {}, run='pass1', date='2026-07-29')
        assert calls_of(gh_mock, 'issue', 'create') == []
        assert calls_of(gh_mock, 'issue', 'close') == []
        assert calls_of(gh_mock, 'issue', 'comment') == []

    def test_closes_only_the_recovered_source(self, gh_mock):
        gh_mock.side_effect = gh_responder(open_issues={'tinyview': 42, 'creators': 43})

        report(ALL_COVERED, {'creators': 'scrape'}, run='pass1', date='2026-07-29')

        closed = calls_of(gh_mock, 'issue', 'close')
        assert len(closed) == 1
        assert closed[0][2] == '42'


class TestCoveredScoping:
    """Pass 2 only examines GoComics -- it must never touch other sources."""

    def test_does_not_close_issues_for_uncovered_sources(self, gh_mock):
        gh_mock.side_effect = gh_responder(
            open_issues={'comicskingdom': 99, 'tinyview': 98}
        )

        report(['gocomics', 'push'], {}, run='pass2', date='2026-07-27')

        assert calls_of(gh_mock, 'issue', 'close') == []
        assert calls_of(gh_mock, 'issue', 'comment') == []

    def test_pass2_still_closes_its_own_source(self, gh_mock):
        gh_mock.side_effect = gh_responder(open_issues={'gocomics': 50})

        report(['gocomics', 'push'], {}, run='pass2', date='2026-07-27')

        closed = calls_of(gh_mock, 'issue', 'close')
        assert len(closed) == 1
        assert closed[0][2] == '50'

    def test_failure_for_uncovered_source_is_still_reported(self, gh_mock):
        """A slug in --failed but not --covered should not be silently dropped."""
        report(['gocomics'], {'tinyview': 'scrape'}, run='pass1', date='2026-07-27')

        created = calls_of(gh_mock, 'issue', 'create')
        assert len(created) == 1
        assert f'{MARKER_PREFIX}tinyview' in created[0][created[0].index('--body') + 1]


class TestLabelHandling:
    def test_creates_label_when_absent(self, gh_mock):
        gh_mock.side_effect = gh_responder(labels=['bug'])
        report(ALL_COVERED, {'tinyview': 'scrape'}, run='pass1', date='2026-07-27')
        assert len(calls_of(gh_mock, 'label', 'create')) == 1

    def test_does_not_recreate_existing_label(self, gh_mock):
        gh_mock.side_effect = gh_responder(labels=[LABEL])
        report(ALL_COVERED, {'tinyview': 'scrape'}, run='pass1', date='2026-07-27')
        assert calls_of(gh_mock, 'label', 'create') == []

    def test_skips_label_work_when_nothing_failed(self, gh_mock):
        report(ALL_COVERED, {}, run='pass1', date='2026-07-27')
        assert calls_of(gh_mock, 'label', 'list') == []


class TestResilience:
    def test_gh_error_on_one_source_does_not_abort_others(self, gh_mock):
        base = gh_responder()
        seen = {'n': 0}

        def flaky(*args):
            if args[:2] == ('issue', 'create'):
                seen['n'] += 1
                if seen['n'] == 1:
                    raise subprocess.CalledProcessError(1, 'gh', stderr='boom')
            return base(*args)

        gh_mock.side_effect = flaky

        rc = report(
            ALL_COVERED,
            {'tinyview': 'scrape', 'creators': 'scrape'},
            run='pass1', date='2026-07-27',
        )

        assert len(calls_of(gh_mock, 'issue', 'create')) == 2
        assert rc != 0

    def test_returns_zero_when_all_reporting_succeeds(self, gh_mock):
        assert report(
            ALL_COVERED, {'tinyview': 'scrape'}, run='pass1', date='2026-07-27'
        ) == 0

    def test_listing_failure_does_not_raise(self, gh_mock):
        def broken(*args):
            if args[:2] == ('issue', 'list'):
                raise subprocess.CalledProcessError(1, 'gh', stderr='rate limited')
            return gh_responder()(*args)

        gh_mock.side_effect = broken
        assert report(
            ALL_COVERED, {'tinyview': 'scrape'}, run='pass1', date='2026-07-27'
        ) != 0


class TestMain:
    def test_wires_arguments_through(self, gh_mock):
        rc = main([
            '--run', 'pass2',
            '--date', '2026-07-27',
            '--covered', 'gocomics,push',
            '--failed', 'gocomics:scrape',
        ])

        assert rc == 0
        created = calls_of(gh_mock, 'issue', 'create')
        assert len(created) == 1
        body = created[0][created[0].index('--body') + 1]
        assert f'{MARKER_PREFIX}gocomics' in body
        assert 'pass2' in body

    def test_failed_flag_is_optional(self, gh_mock):
        assert main([
            '--run', 'pass1', '--date', '2026-07-27', '--covered', 'gocomics',
        ]) == 0
        assert calls_of(gh_mock, 'issue', 'create') == []

    def test_reads_log_tail_when_given(self, gh_mock, tmp_path):
        log = tmp_path / 'master_update.log'
        log.write_text('\n'.join(f'line {i}' for i in range(200)))

        main([
            '--run', 'pass1', '--date', '2026-07-27',
            '--covered', 'gocomics', '--failed', 'gocomics:scrape',
            '--log-file', str(log),
        ])

        body = calls_of(gh_mock, 'issue', 'create')[0]
        body = body[body.index('--body') + 1]
        assert 'line 199' in body
        assert 'line 0' not in body

    def test_missing_log_file_is_not_fatal(self, gh_mock, tmp_path):
        assert main([
            '--run', 'pass1', '--date', '2026-07-27',
            '--covered', 'gocomics', '--failed', 'gocomics:scrape',
            '--log-file', str(tmp_path / 'nope.log'),
        ]) == 0


class TestSourceNames:
    def test_every_pipeline_slug_has_a_display_name(self):
        expected = {
            'gocomics', 'comicskingdom', 'tinyview', 'newyorker',
            'farside', 'creators', 'mrboffo', 'push', 'preflight',
        }
        assert expected <= set(SOURCE_NAMES)

    def test_unknown_slug_falls_back_to_the_slug(self):
        assert 'mystery' in issue_title('mystery', 'scrape')
