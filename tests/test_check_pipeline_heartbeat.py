"""Tests for check_pipeline_heartbeat.py.

The heartbeat answers a question the failure reporter structurally cannot: did
the pipeline run at all? A Mini that is off or asleep produces no failing step,
so silence looks exactly like success. These tests pin that logic down.
"""

import os
import sys

import pytest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from scripts.check_pipeline_heartbeat import (
    DEFAULT_STALE_HOURS,
    HEARTBEAT_SLUG,
    find_latest_pipeline_commit,
    main,
    staleness,
)


# 2026-07-27 12:00:00 UTC, an arbitrary fixed "now" for age arithmetic.
NOW = 1785196800
HOUR = 3600


def log(*entries):
    """Build `git log --format=%ct%x09%s` output."""
    return "\n".join(f"{ts}\t{subject}" for ts, subject in entries)


class TestFindLatestPipelineCommit:
    def test_finds_a_pass1_feed_commit(self):
        out = log((NOW - 3 * HOUR, "Update all comic feeds for 2026-07-27"))
        assert find_latest_pipeline_commit(out) == (
            NOW - 3 * HOUR, "Update all comic feeds for 2026-07-27"
        )

    def test_finds_a_pass2_commit(self):
        out = log((NOW - HOUR, "Pass 2 GoComics feed update for 2026-07-27"))
        assert find_latest_pipeline_commit(out)[0] == NOW - HOUR

    def test_finds_a_recovery_commit(self):
        out = log((NOW - HOUR, "Update comic feeds for 2026-07-27 (recovery after push conflict)"))
        assert find_latest_pipeline_commit(out)[0] == NOW - HOUR

    def test_ignores_non_pipeline_commits(self):
        """A human code commit must not mask a dead pipeline."""
        out = log(
            (NOW - HOUR, "feat: add a new comic source"),
            (NOW - 30 * HOUR, "Update all comic feeds for 2026-07-26"),
        )
        assert find_latest_pipeline_commit(out)[0] == NOW - 30 * HOUR

    def test_returns_newest_when_several_match(self):
        out = log(
            (NOW - 2 * HOUR, "Update all comic feeds for 2026-07-27"),
            (NOW - 26 * HOUR, "Update all comic feeds for 2026-07-26"),
        )
        assert find_latest_pipeline_commit(out)[0] == NOW - 2 * HOUR

    def test_returns_none_when_no_pipeline_commits(self):
        out = log((NOW - HOUR, "docs: update the readme"))
        assert find_latest_pipeline_commit(out) is None

    def test_handles_empty_log(self):
        assert find_latest_pipeline_commit("") is None

    def test_ignores_malformed_lines(self):
        out = "garbage\nnot-a-timestamp\tUpdate all comic feeds for 2026-07-27"
        assert find_latest_pipeline_commit(out) is None


class TestStaleness:
    def test_fresh_run_is_healthy(self):
        out = log((NOW - 3 * HOUR, "Update all comic feeds for 2026-07-27"))
        stale, age, _ = staleness(out, NOW, DEFAULT_STALE_HOURS)
        assert stale is False
        assert age == pytest.approx(3.0)

    def test_old_run_is_stale(self):
        out = log((NOW - 30 * HOUR, "Update all comic feeds for 2026-07-26"))
        stale, age, _ = staleness(out, NOW, DEFAULT_STALE_HOURS)
        assert stale is True
        assert age == pytest.approx(30.0)

    def test_no_pipeline_commit_at_all_is_stale(self):
        stale, age, detail = staleness("", NOW, DEFAULT_STALE_HOURS)
        assert stale is True
        assert age is None
        assert 'no' in detail.lower()

    def test_threshold_is_configurable(self):
        out = log((NOW - 10 * HOUR, "Update all comic feeds for 2026-07-27"))
        assert staleness(out, NOW, 8)[0] is True
        assert staleness(out, NOW, 12)[0] is False

    def test_boundary_is_not_stale_at_exactly_the_threshold(self):
        out = log((NOW - 20 * HOUR, "Update all comic feeds for 2026-07-26"))
        assert staleness(out, NOW, 20)[0] is False

    def test_default_threshold_tolerates_a_normal_daily_cadence(self):
        """Pass 1 runs daily; a ~24h-old commit checked hours later is normal."""
        assert DEFAULT_STALE_HOURS >= 20

    def test_detail_mentions_the_age_and_subject(self):
        out = log((NOW - 30 * HOUR, "Update all comic feeds for 2026-07-26"))
        detail = staleness(out, NOW, DEFAULT_STALE_HOURS)[2]
        assert '30' in detail
        assert '2026-07-26' in detail


class TestMain:
    @patch('scripts.check_pipeline_heartbeat.report')
    @patch('scripts.check_pipeline_heartbeat.git_log')
    def test_reports_failure_when_stale(self, mock_log, mock_report):
        mock_log.return_value = log((NOW - 40 * HOUR, "Update all comic feeds for 2026-07-25"))
        mock_report.return_value = 0

        with patch('scripts.check_pipeline_heartbeat.now_ts', return_value=NOW):
            assert main([]) == 0

        covered, failed = mock_report.call_args.args[0], mock_report.call_args.args[1]
        assert covered == [HEARTBEAT_SLUG]
        assert HEARTBEAT_SLUG in failed

    @patch('scripts.check_pipeline_heartbeat.report')
    @patch('scripts.check_pipeline_heartbeat.git_log')
    def test_reports_healthy_when_fresh(self, mock_log, mock_report):
        mock_log.return_value = log((NOW - 2 * HOUR, "Update all comic feeds for 2026-07-27"))
        mock_report.return_value = 0

        with patch('scripts.check_pipeline_heartbeat.now_ts', return_value=NOW):
            assert main([]) == 0

        # Healthy: covered so a prior heartbeat issue auto-closes, none failed.
        assert mock_report.call_args.args[0] == [HEARTBEAT_SLUG]
        assert mock_report.call_args.args[1] == {}

    @patch('scripts.check_pipeline_heartbeat.report')
    @patch('scripts.check_pipeline_heartbeat.git_log')
    def test_only_covers_heartbeat(self, mock_log, mock_report):
        """Must never auto-close a source issue -- it examined no sources."""
        mock_log.return_value = log((NOW - 2 * HOUR, "Update all comic feeds for 2026-07-27"))
        mock_report.return_value = 0

        with patch('scripts.check_pipeline_heartbeat.now_ts', return_value=NOW):
            main([])

        assert mock_report.call_args.args[0] == [HEARTBEAT_SLUG]

    @patch('scripts.check_pipeline_heartbeat.report')
    @patch('scripts.check_pipeline_heartbeat.git_log')
    def test_threshold_flag_is_honoured(self, mock_log, mock_report):
        mock_log.return_value = log((NOW - 10 * HOUR, "Update all comic feeds for 2026-07-27"))
        mock_report.return_value = 0

        with patch('scripts.check_pipeline_heartbeat.now_ts', return_value=NOW):
            main(['--stale-hours', '8'])

        assert HEARTBEAT_SLUG in mock_report.call_args.args[1]

    @patch('scripts.check_pipeline_heartbeat.report')
    @patch('scripts.check_pipeline_heartbeat.git_log')
    def test_propagates_reporter_exit_code(self, mock_log, mock_report):
        mock_log.return_value = log((NOW - 2 * HOUR, "Update all comic feeds for 2026-07-27"))
        mock_report.return_value = 1

        with patch('scripts.check_pipeline_heartbeat.now_ts', return_value=NOW):
            assert main([]) == 1
