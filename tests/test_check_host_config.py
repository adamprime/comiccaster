"""Tests for check_host_config.py.

The probes shell out to macOS-only tools, so they are exercised through their
pure parsers; `evaluate` and `main` are tested against injected readings. That
keeps the suite offline and platform-independent, per the repo's testing rules.

One test here guards a *security* property rather than behaviour: the script
must not grow a flag that prints specifics, because this repo is public and the
pipeline alert derived from it must stay opaque.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from scripts.check_host_config import (
    EXPECTED_LOGIN_USER,
    evaluate,
    main,
    parse_defaults_bool,
    parse_filevault_status,
)


def reading(**overrides):
    """A fully healthy set of readings, with per-test overrides."""
    healthy = {
        'kcpassword_present': True,
        'auto_login_user': EXPECTED_LOGIN_USER,
        'filevault_on': False,
        'tailscale_start_on_login': True,
    }
    healthy.update(overrides)
    return healthy


class TestParsers:
    @pytest.mark.parametrize('raw,expected', [
        ('FileVault is Off.', False),
        ('FileVault is On.', True),
        ('FileVault is On, but needs a restart.', True),
    ])
    def test_parse_filevault_status(self, raw, expected):
        assert parse_filevault_status(raw) is expected

    def test_filevault_unreadable_is_unknown(self):
        assert parse_filevault_status('') is None
        assert parse_filevault_status('command not found') is None

    @pytest.mark.parametrize('raw,expected', [
        ('1', True),
        ('0', False),
        ('  1\n', True),
    ])
    def test_parse_defaults_bool(self, raw, expected):
        assert parse_defaults_bool(raw) is expected

    def test_missing_default_is_none(self):
        assert parse_defaults_bool('does not exist') is None
        assert parse_defaults_bool('') is None


class TestEvaluate:
    def test_healthy_host_is_ok(self):
        status, detail = evaluate(reading())
        assert status == 'ok'
        assert 'ok' in detail.lower()

    def test_missing_kcpassword_breaks_autologin(self):
        status, detail = evaluate(reading(kcpassword_present=False))
        assert status == 'broken'
        assert 'kcpassword' in detail

    def test_unset_auto_login_user_breaks_autologin(self):
        status, detail = evaluate(reading(auto_login_user=None))
        assert status == 'broken'
        assert 'autoLoginUser' in detail

    def test_wrong_auto_login_user_breaks_autologin(self):
        status, detail = evaluate(reading(auto_login_user='someone-else'))
        assert status == 'broken'
        assert 'autoLoginUser' in detail

    def test_filevault_on_breaks_autologin(self):
        """FileVault makes auto-login unavailable, so the chain cannot work."""
        status, detail = evaluate(reading(filevault_on=True))
        assert status == 'broken'
        assert 'FileVault' in detail

    def test_tailscale_off_breaks_remote_access(self):
        """The pipeline still runs, but nobody can get in to fix anything."""
        status, detail = evaluate(reading(tailscale_start_on_login=False))
        assert status == 'broken'
        assert 'remote access' in detail.lower()

    def test_every_problem_is_reported_not_just_the_first(self):
        status, detail = evaluate(reading(
            kcpassword_present=False,
            filevault_on=True,
            tailscale_start_on_login=False,
        ))
        assert status == 'broken'
        assert 'kcpassword' in detail
        assert 'FileVault' in detail
        assert 'remote access' in detail.lower()

    def test_unknown_readings_are_not_treated_as_healthy(self):
        """A probe that failed to run must not read as a passing check."""
        status, _ = evaluate(reading(filevault_on=None))
        assert status == 'broken'
        status, _ = evaluate(reading(tailscale_start_on_login=None))
        assert status == 'broken'


class TestMain:
    def test_exit_zero_when_healthy(self, monkeypatch, capsys):
        monkeypatch.setattr('scripts.check_host_config.gather', lambda: reading())
        assert main([]) == 0
        assert '✅' in capsys.readouterr().out

    def test_exit_one_when_broken(self, monkeypatch, capsys):
        monkeypatch.setattr(
            'scripts.check_host_config.gather',
            lambda: reading(kcpassword_present=False),
        )
        assert main([]) == 1
        assert '❌' in capsys.readouterr().out

    def test_quiet_suppresses_output(self, monkeypatch, capsys):
        monkeypatch.setattr('scripts.check_host_config.gather', lambda: reading())
        assert main(['--quiet']) == 0
        assert capsys.readouterr().out == ''

    def test_has_no_detail_only_flag(self, monkeypatch):
        """Security guard, not a style preference.

        check_ck_session.py exposes --detail-only to feed an alert body. This
        script deliberately does not: its findings describe the host's security
        posture (disk encryption, auto-login user), and the GitHub issue it
        drives is public. Specifics must stay in the local log. If someone adds
        such a flag, this test should fail and make them justify it.
        """
        monkeypatch.setattr('scripts.check_host_config.gather', lambda: reading())
        with pytest.raises(SystemExit):
            main(['--detail-only'])
