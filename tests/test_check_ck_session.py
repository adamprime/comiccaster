"""Tests for check_ck_session.py.

Uses a real temporary SQLite database shaped like Chrome's cookie store, so
these exercise the actual query path without mocking sqlite and without
touching the operator's real profile.
"""

import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from scripts.check_ck_session import (
    CK_HOST,
    DEFAULT_WARN_DAYS,
    TOKEN_NAME,
    chrome_time_to_datetime,
    datetime_to_chrome_time,
    days_remaining,
    describe_renewal,
    evaluate,
    main,
    read_token_expiry,
)


NOW = datetime(2026, 7, 28, 12, 0, 0, tzinfo=timezone.utc)


def make_profile(tmp_path, cookies):
    """Build a Chrome-shaped profile dir. `cookies` is (host, name, expiry_dt)."""
    default = tmp_path / 'Default'
    default.mkdir(parents=True, exist_ok=True)
    db = default / 'Cookies'
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE cookies (host_key TEXT, name TEXT, expires_utc INTEGER, "
        "is_persistent INTEGER)"
    )
    for host, name, expiry in cookies:
        conn.execute(
            "INSERT INTO cookies VALUES (?, ?, ?, ?)",
            (host, name, datetime_to_chrome_time(expiry) if expiry else 0,
             1 if expiry else 0),
        )
    conn.commit()
    conn.close()
    return tmp_path


class TestChromeTimeConversion:
    def test_roundtrips(self):
        when = datetime(2026, 8, 4, 11, 21, 25, tzinfo=timezone.utc)
        assert chrome_time_to_datetime(datetime_to_chrome_time(when)) == when

    def test_known_chrome_epoch_value(self):
        """Chrome counts microseconds from 1601-01-01."""
        assert chrome_time_to_datetime(11644473600 * 1_000_000) == datetime(
            1970, 1, 1, tzinfo=timezone.utc
        )

    def test_zero_is_session_cookie(self):
        assert chrome_time_to_datetime(0) is None


class TestReadTokenExpiry:
    def test_reads_the_auth_token_expiry(self, tmp_path):
        expiry = datetime(2026, 8, 4, 11, 21, 25, tzinfo=timezone.utc)
        profile = make_profile(tmp_path, [(CK_HOST, TOKEN_NAME, expiry)])
        assert read_token_expiry(profile) == expiry

    def test_ignores_other_cookies(self, tmp_path):
        expiry = datetime(2026, 8, 4, tzinfo=timezone.utc)
        profile = make_profile(tmp_path, [
            (CK_HOST, '_ga', datetime(2027, 1, 1, tzinfo=timezone.utc)),
            (CK_HOST, TOKEN_NAME, expiry),
        ])
        assert read_token_expiry(profile) == expiry

    def test_ignores_the_same_name_on_another_host(self, tmp_path):
        profile = make_profile(tmp_path, [
            ('g010.comicskingdom.com', TOKEN_NAME,
             datetime(2027, 1, 1, tzinfo=timezone.utc)),
        ])
        assert read_token_expiry(profile) is None

    def test_returns_none_when_token_absent(self, tmp_path):
        profile = make_profile(tmp_path, [(CK_HOST, '_ga', None)])
        assert read_token_expiry(profile) is None

    def test_returns_none_when_profile_missing(self, tmp_path):
        assert read_token_expiry(tmp_path / 'nope') is None

    def test_does_not_mutate_the_profile(self, tmp_path):
        """Must be safe to run against a profile Chrome may be using."""
        expiry = datetime(2026, 8, 4, tzinfo=timezone.utc)
        profile = make_profile(tmp_path, [(CK_HOST, TOKEN_NAME, expiry)])
        db = profile / 'Default' / 'Cookies'
        before = db.stat().st_mtime, db.stat().st_size
        read_token_expiry(profile)
        assert (db.stat().st_mtime, db.stat().st_size) == before


class TestDaysRemaining:
    def test_counts_forward(self):
        assert days_remaining(NOW + timedelta(days=7), NOW) == pytest.approx(7.0)

    def test_negative_when_expired(self):
        assert days_remaining(NOW - timedelta(days=1), NOW) == pytest.approx(-1.0)

    def test_fractional(self):
        assert days_remaining(NOW + timedelta(hours=12), NOW) == pytest.approx(0.5)


class TestEvaluate:
    def test_fresh_token_is_ok(self):
        status, _ = evaluate(NOW + timedelta(days=7), NOW, DEFAULT_WARN_DAYS)
        assert status == 'ok'

    def test_token_inside_warn_window_is_expiring(self):
        status, _ = evaluate(NOW + timedelta(days=1), NOW, DEFAULT_WARN_DAYS)
        assert status == 'expiring'

    def test_already_expired_is_expired(self):
        status, _ = evaluate(NOW - timedelta(hours=1), NOW, DEFAULT_WARN_DAYS)
        assert status == 'expired'

    def test_missing_token_is_missing(self):
        status, _ = evaluate(None, NOW, DEFAULT_WARN_DAYS)
        assert status == 'missing'

    def test_boundary_exactly_at_threshold_is_expiring(self):
        status, _ = evaluate(NOW + timedelta(days=2), NOW, 2)
        assert status == 'expiring'

    def test_detail_reports_days_and_date(self):
        _, detail = evaluate(NOW + timedelta(days=7), NOW, DEFAULT_WARN_DAYS)
        assert '7.0' in detail
        assert '2026-08-04' in detail

    def test_detail_for_missing_token_mentions_reauth(self):
        _, detail = evaluate(None, NOW, DEFAULT_WARN_DAYS)
        assert 'reauth' in detail.lower()

    def test_warn_window_matches_a_seven_day_token(self):
        """A 7-day token on a 7-day cadence needs warning before the run fails."""
        assert 1 <= DEFAULT_WARN_DAYS <= 3


class TestDescribeRenewal:
    """The 2026-07-28 failure mode: a reauth that looked fine but didn't stick."""

    def test_expiry_moved_forward_is_renewed(self):
        before = NOW + timedelta(days=1)
        after = NOW + timedelta(days=7)
        renewed, message = describe_renewal(before, after, NOW)
        assert renewed is True
        assert '7.0' in message

    def test_unchanged_expiry_is_not_renewed(self):
        same = NOW + timedelta(hours=6)
        renewed, message = describe_renewal(same, same, NOW)
        assert renewed is False
        assert 'did NOT move' in message

    def test_expiry_going_backwards_is_not_renewed(self):
        renewed, _ = describe_renewal(NOW + timedelta(days=7),
                                      NOW + timedelta(days=1), NOW)
        assert renewed is False

    def test_missing_token_after_login_is_not_renewed(self):
        renewed, message = describe_renewal(NOW + timedelta(days=1), None, NOW)
        assert renewed is False
        assert 'did NOT persist' in message

    def test_first_ever_login_counts_as_renewed(self):
        """No prior token is normal on a fresh profile, not a failure."""
        renewed, _ = describe_renewal(None, NOW + timedelta(days=7), NOW)
        assert renewed is True

    def test_failure_message_tells_the_operator_what_to_do(self):
        same = NOW + timedelta(hours=6)
        assert 're-run' in describe_renewal(same, same, NOW)[1].lower()


class TestMain:
    def test_exit_zero_when_healthy(self, tmp_path, capsys):
        profile = make_profile(tmp_path, [
            (CK_HOST, TOKEN_NAME, datetime.now(timezone.utc) + timedelta(days=7)),
        ])
        assert main(['--profile', str(profile)]) == 0
        assert 'ok' in capsys.readouterr().out.lower()

    def test_exit_nonzero_when_expiring(self, tmp_path):
        profile = make_profile(tmp_path, [
            (CK_HOST, TOKEN_NAME, datetime.now(timezone.utc) + timedelta(hours=6)),
        ])
        assert main(['--profile', str(profile)]) == 1

    def test_exit_nonzero_when_missing(self, tmp_path):
        profile = make_profile(tmp_path, [(CK_HOST, '_ga', None)])
        assert main(['--profile', str(profile)]) == 1

    def test_warn_days_is_configurable(self, tmp_path):
        profile = make_profile(tmp_path, [
            (CK_HOST, TOKEN_NAME, datetime.now(timezone.utc) + timedelta(days=4)),
        ])
        assert main(['--profile', str(profile), '--warn-days', '2']) == 0
        assert main(['--profile', str(profile), '--warn-days', '6']) == 1

    def test_quiet_suppresses_output_but_keeps_exit_code(self, tmp_path, capsys):
        profile = make_profile(tmp_path, [
            (CK_HOST, TOKEN_NAME, datetime.now(timezone.utc) + timedelta(days=7)),
        ])
        assert main(['--profile', str(profile), '--quiet']) == 0
        assert capsys.readouterr().out == ''

    def test_detail_flag_prints_only_the_detail_line(self, tmp_path, capsys):
        """The pipeline pipes this straight into the alert body."""
        profile = make_profile(tmp_path, [
            (CK_HOST, TOKEN_NAME, datetime.now(timezone.utc) + timedelta(hours=6)),
        ])
        main(['--profile', str(profile), '--detail-only'])
        out = capsys.readouterr().out.strip()
        assert out
        assert '\n' not in out
