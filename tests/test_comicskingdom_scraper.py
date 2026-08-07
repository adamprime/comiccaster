"""Smoke tests for scripts/comicskingdom_scraper_individual.py.

Unit 2 of the CK scraper reliability plan. Characterization tests that
lock current control-flow behavior so Unit 3's fix doesn't silently
regress adjacent paths. Intentionally narrow — no network, no real
browser, no end-to-end extraction; those are covered by manual
verification in Unit 3.
"""

import io
import os
import pickle
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import comicskingdom_scraper_individual as cki


# --- load_cookies -----------------------------------------------------------


class TestLoadCookies:
    def test_returns_true_when_pickle_valid(self, tmp_path):
        cookie_file = tmp_path / "cookies.pkl"
        cookies = [
            {"name": "session", "value": "abc", "domain": "comicskingdom.com"},
            {"name": "csrf", "value": "xyz", "domain": "comicskingdom.com"},
        ]
        with open(cookie_file, "wb") as f:
            pickle.dump(cookies, f)

        driver = MagicMock()
        assert cki.load_cookies(driver, cookie_file) is True
        driver.get.assert_called_once_with("https://comicskingdom.com")
        assert driver.add_cookie.call_count == len(cookies)

    def test_returns_false_when_file_missing(self, tmp_path):
        missing = tmp_path / "does-not-exist.pkl"
        driver = MagicMock()
        assert cki.load_cookies(driver, missing) is False
        driver.get.assert_not_called()
        driver.add_cookie.assert_not_called()

    def test_returns_false_on_unpickle_error(self, tmp_path, capsys):
        bad = tmp_path / "corrupt.pkl"
        bad.write_bytes(b"not a valid pickle")

        driver = MagicMock()
        assert cki.load_cookies(driver, bad) is False

        captured = capsys.readouterr()
        # Should surface a readable error line, not a raw traceback.
        assert "Error loading cookies" in captured.out
        assert "Traceback" not in captured.out


# --- is_authenticated -------------------------------------------------------


class TestIsAuthenticated:
    def test_true_when_redirected_off_login(self):
        driver = MagicMock()
        driver.current_url = "https://comicskingdom.com/favorites"
        assert cki.is_authenticated(driver) is True
        driver.get.assert_called_once_with("https://comicskingdom.com/favorites")

    def test_false_when_current_url_mentions_login(self):
        driver = MagicMock()
        driver.current_url = "https://comicskingdom.com/login?redirect=/favorites"
        assert cki.is_authenticated(driver) is False

    def test_false_when_driver_get_raises(self):
        driver = MagicMock()
        driver.get.side_effect = Exception("renderer timeout")
        assert cki.is_authenticated(driver) is False

    def test_navigation_error_is_reported_not_swallowed(self, capsys):
        """The 2026-08-07 failure was invisible because `e` was never printed.

        The log showed a START line, no END line, and "please run reauth
        script" -- which was wrong advice: no reauth was needed, the run
        self-healed. The exception text is the only thing that distinguishes
        a transient navigation error from a genuinely dead session.
        """
        driver = MagicMock()
        driver.get.side_effect = TimeoutError("renderer timeout")

        assert cki.is_authenticated(driver) is False

        out = capsys.readouterr().out
        assert "renderer timeout" in out
        assert "TimeoutError" in out

    def test_login_redirect_is_distinguished_from_navigation_error(self, capsys):
        """These need different operator responses, so they must read
        differently: a login redirect wants a reauth, a navigation error
        wants a retry."""
        driver = MagicMock()
        driver.current_url = "https://comicskingdom.com/login?redirect=/favorites"

        assert cki.is_authenticated(driver) is False

        out = capsys.readouterr().out.lower()
        assert "login" in out
        assert "navigation failed" not in out


# --- authenticate_with_cookies ----------------------------------------------


class TestAuthenticateWithCookies:
    def test_reauth_message_when_cookies_load_but_auth_fails(
        self, tmp_path, capsys
    ):
        # Cookies load successfully...
        cookie_file = tmp_path / "cookies.pkl"
        with open(cookie_file, "wb") as f:
            pickle.dump([{"name": "s", "value": "v", "domain": "comicskingdom.com"}], f)

        # ...but is_authenticated returns False (session rejected).
        driver = MagicMock()
        driver.current_url = "https://comicskingdom.com/login"

        assert cki.authenticate_with_cookies(driver, cookie_file) is False

        captured = capsys.readouterr()
        assert "Authentication failed - please run reauth script" in captured.out

    def test_returns_true_when_cookies_load_and_auth_succeeds(self, tmp_path):
        cookie_file = tmp_path / "cookies.pkl"
        with open(cookie_file, "wb") as f:
            pickle.dump([{"name": "s", "value": "v", "domain": "comicskingdom.com"}], f)

        driver = MagicMock()
        driver.current_url = "https://comicskingdom.com/favorites"

        assert cki.authenticate_with_cookies(driver, cookie_file) is True


class TestAuthenticateWithProfile:
    """use_profile=True branch of authenticate_with_cookies."""

    def test_returns_true_and_skips_load_cookies(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        # Populate the profile so "Default/Cookies" exists (authenticated state)
        (tmp_path / ".comicskingdom_chrome_profile" / "Default").mkdir(parents=True)
        (tmp_path / ".comicskingdom_chrome_profile" / "Default" / "Cookies").write_bytes(b"x")

        driver = MagicMock()
        driver.current_url = "https://comicskingdom.com/favorites"

        # Prove load_cookies is not called when use_profile=True
        with patch.object(cki, "load_cookies") as mock_load:
            result = cki.authenticate_with_cookies(driver, None, use_profile=True)

        assert result is True
        mock_load.assert_not_called()

    def test_empty_profile_emits_distinct_message(
        self, tmp_path, monkeypatch, capsys
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        # Profile dir does not exist at all → treated as empty

        driver = MagicMock()
        driver.current_url = "https://comicskingdom.com/login"

        result = cki.authenticate_with_cookies(driver, None, use_profile=True)
        assert result is False

        captured = capsys.readouterr()
        assert "has no stored session" in captured.out
        # Distinct from the legacy reauth message — critical for the
        # empty-vs-expired distinction.
        assert "Authentication failed - please run reauth script" not in captured.out

    def test_populated_profile_but_auth_fails_uses_legacy_message(
        self, tmp_path, monkeypatch, capsys
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        # Profile exists and has a Cookies file → treat as session-expired
        (tmp_path / ".comicskingdom_chrome_profile" / "Default").mkdir(parents=True)
        (tmp_path / ".comicskingdom_chrome_profile" / "Default" / "Cookies").write_bytes(b"x")

        driver = MagicMock()
        driver.current_url = "https://comicskingdom.com/login"

        result = cki.authenticate_with_cookies(driver, None, use_profile=True)
        assert result is False

        captured = capsys.readouterr()
        assert "Authentication failed - please run reauth script" in captured.out
        assert "has no stored session" not in captured.out

    def test_use_profile_false_preserves_legacy_behavior(self, tmp_path, capsys):
        # Legacy flow when use_profile=False should be identical to pre-Unit-3.
        cookie_file = tmp_path / "cookies.pkl"
        with open(cookie_file, "wb") as f:
            pickle.dump([{"name": "s", "value": "v", "domain": "comicskingdom.com"}], f)

        driver = MagicMock()
        driver.current_url = "https://comicskingdom.com/favorites"

        assert cki.authenticate_with_cookies(driver, cookie_file, use_profile=False) is True


# --- setup_driver -----------------------------------------------------------


class TestSetupDriver:
    def test_headless_when_show_browser_false(self):
        with patch.object(cki.webdriver, "Chrome") as chrome_cls:
            chrome_cls.return_value = MagicMock()
            # Pass use_profile=False so this test stays focused on the
            # headless flag and doesn't touch the user's real $HOME.
            cki.setup_driver(show_browser=False, use_profile=False)

            args, kwargs = chrome_cls.call_args
            options = kwargs["options"]
            assert "--headless=new" in options.arguments

    def test_not_headless_when_show_browser_true(self):
        with patch.object(cki.webdriver, "Chrome") as chrome_cls:
            chrome_cls.return_value = MagicMock()
            cki.setup_driver(show_browser=True, use_profile=False)

            args, kwargs = chrome_cls.call_args
            options = kwargs["options"]
            assert "--headless=new" not in options.arguments

    def test_default_use_profile_is_true(self, tmp_path, monkeypatch):
        """Shape A cutover: use_profile is True by default."""
        monkeypatch.setenv("HOME", str(tmp_path))
        with patch.object(cki.webdriver, "Chrome") as chrome_cls:
            chrome_cls.return_value = MagicMock()
            cki.setup_driver()

            args, kwargs = chrome_cls.call_args
            options = kwargs["options"]
            assert any(a.startswith("--user-data-dir=") for a in options.arguments)

    def test_no_profile_flag_when_use_profile_false(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        with patch.object(cki.webdriver, "Chrome") as chrome_cls:
            chrome_cls.return_value = MagicMock()
            cki.setup_driver(use_profile=False)

            args, kwargs = chrome_cls.call_args
            options = kwargs["options"]
            assert not any(a.startswith("--user-data-dir=") for a in options.arguments)

    def test_profile_flag_added_when_use_profile_true(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        with patch.object(cki.webdriver, "Chrome") as chrome_cls:
            chrome_cls.return_value = MagicMock()
            cki.setup_driver(use_profile=True)

            args, kwargs = chrome_cls.call_args
            options = kwargs["options"]
            expected = f"--user-data-dir={tmp_path / '.comicskingdom_chrome_profile'}"
            assert expected in options.arguments

    def test_profile_directory_created_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        profile_dir = tmp_path / ".comicskingdom_chrome_profile"
        assert not profile_dir.exists()

        with patch.object(cki.webdriver, "Chrome") as chrome_cls:
            chrome_cls.return_value = MagicMock()
            cki.setup_driver(use_profile=True)

        assert profile_dir.is_dir()

    def test_profile_directory_contents_preserved_when_exists(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        profile_dir = tmp_path / ".comicskingdom_chrome_profile"
        profile_dir.mkdir()
        # Simulate an existing Chrome profile artifact
        existing_cookies = profile_dir / "Default" / "Cookies"
        existing_cookies.parent.mkdir(parents=True)
        existing_cookies.write_bytes(b"pretend-sqlite-content")

        with patch.object(cki.webdriver, "Chrome") as chrome_cls:
            chrome_cls.return_value = MagicMock()
            cki.setup_driver(use_profile=True)

        assert existing_cookies.read_bytes() == b"pretend-sqlite-content"

    def test_profile_directory_mode_is_0o700(self, tmp_path, monkeypatch):
        import stat

        monkeypatch.setenv("HOME", str(tmp_path))
        profile_dir = tmp_path / ".comicskingdom_chrome_profile"
        # Pre-create with a more permissive mode to prove setup_driver tightens it.
        profile_dir.mkdir(mode=0o755)

        with patch.object(cki.webdriver, "Chrome") as chrome_cls:
            chrome_cls.return_value = MagicMock()
            cki.setup_driver(use_profile=True)

        assert stat.S_IMODE(profile_dir.stat().st_mode) == 0o700

    def test_profile_and_show_browser_coexist(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        with patch.object(cki.webdriver, "Chrome") as chrome_cls:
            chrome_cls.return_value = MagicMock()
            cki.setup_driver(show_browser=True, use_profile=True)

            args, kwargs = chrome_cls.call_args
            options = kwargs["options"]
            expected = f"--user-data-dir={tmp_path / '.comicskingdom_chrome_profile'}"
            assert expected in options.arguments
            assert "--headless=new" not in options.arguments


# --- wait_for_manual_login --------------------------------------------------


class TestWaitForManualLogin:
    """Behavior tests for the manual-login helper.

    The function only confirms the login form is present and waits for the
    operator to complete login in a visible browser; it does not type or
    submit.
    """

    def test_function_exists_on_individual(self):
        assert callable(cki.wait_for_manual_login)

    def test_returns_true_when_redirect_away_from_login(self, monkeypatch):
        driver = MagicMock()
        driver.current_url = "https://comicskingdom.com/account"

        # Speed up the 120-iteration wait loop
        monkeypatch.setattr(cki.time, "sleep", lambda *_a, **_kw: None)

        mock_wdw = MagicMock()
        mock_wdw.return_value.until.return_value = MagicMock()
        monkeypatch.setattr(cki, "WebDriverWait", mock_wdw)

        result = cki.wait_for_manual_login(driver)
        assert result is True

    def test_returns_false_on_timeout(self, monkeypatch):
        driver = MagicMock()
        driver.current_url = "https://comicskingdom.com/login?step=captcha"

        monkeypatch.setattr(cki.time, "sleep", lambda *_a, **_kw: None)

        mock_wdw = MagicMock()
        mock_wdw.return_value.until.return_value = MagicMock()
        monkeypatch.setattr(cki, "WebDriverWait", mock_wdw)

        result = cki.wait_for_manual_login(driver)
        assert result is False

    def test_returns_false_when_no_username_field(self, monkeypatch):
        driver = MagicMock()

        monkeypatch.setattr(cki.time, "sleep", lambda *_a, **_kw: None)

        # All three selector attempts raise (no username field findable)
        mock_wdw = MagicMock()
        mock_wdw.return_value.until.side_effect = Exception("not found")
        monkeypatch.setattr(cki, "WebDriverWait", mock_wdw)

        result = cki.wait_for_manual_login(driver)
        assert result is False

    def test_does_not_inject_credentials_via_js(self, monkeypatch):
        """CK's bot check rejects JS-injected fills — the function must not attempt them."""
        driver = MagicMock()
        driver.current_url = "https://comicskingdom.com/account"

        monkeypatch.setattr(cki.time, "sleep", lambda *_a, **_kw: None)

        mock_wdw = MagicMock()
        mock_wdw.return_value.until.return_value = MagicMock()
        monkeypatch.setattr(cki, "WebDriverWait", mock_wdw)

        cki.wait_for_manual_login(driver)
        assert not driver.execute_script.called


# --- load_cookie_file_path --------------------------------------------------


class TestLoadCookieFilePath:
    def test_uses_env_var_when_set(self, monkeypatch):
        monkeypatch.setenv("COMICSKINGDOM_COOKIE_FILE", "/tmp/ck-test.pkl")
        assert str(cki.load_cookie_file_path()) == "/tmp/ck-test.pkl"

    def test_falls_back_to_default_when_unset(self, monkeypatch):
        monkeypatch.delenv("COMICSKINGDOM_COOKIE_FILE", raising=False)
        assert (
            str(cki.load_cookie_file_path()) == "data/comicskingdom_cookies.pkl"
        )

    def test_does_not_read_credential_env_vars(self, capsys, monkeypatch):
        # Shape A: credentials are typed by the operator into the browser at
        # reauth time and are never loaded from env. Setting them here proves
        # the loader ignores them and they cannot leak into stdout.
        monkeypatch.setenv("COMICSKINGDOM_USERNAME", "test-user-do-not-log")
        monkeypatch.setenv("COMICSKINGDOM_PASSWORD", "test-pass-do-not-log")

        cki.load_cookie_file_path()

        captured = capsys.readouterr()
        assert "test-user-do-not-log" not in captured.out
        assert "test-pass-do-not-log" not in captured.out


# --- reauth_comicskingdom.py -------------------------------------------------


class TestReauthScript:
    """Unit 4 — reauth rewrite imports from _individual, seeds the profile."""

    def _load_reauth_module(self):
        """Fresh import of the reauth script for a test.

        Using importlib so each test gets a clean module state and
        patch.object works cleanly on the reauth-local names.
        """
        import importlib
        import scripts.reauth_comicskingdom as reauth
        importlib.reload(reauth)
        return reauth

    def test_imports_from_individual_not_secure(self):
        """AST-level: the reauth script must not import from _secure."""
        import ast
        repo_root = Path(__file__).parent.parent
        source = (repo_root / "scripts" / "reauth_comicskingdom.py").read_text()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert "comicskingdom_scraper_secure" not in module, (
                    f"reauth_comicskingdom.py still imports from _secure: "
                    f"line {node.lineno}"
                )
                # Positive check: it does import from _individual.
                # At least one import should reference it.
        assert any(
            isinstance(n, ast.ImportFrom)
            and "comicskingdom_scraper_individual" in (n.module or "")
            for n in ast.walk(tree)
        )

    def test_exits_zero_when_login_mints_a_new_token(self, monkeypatch, tmp_path):
        """Success requires a *new* token on disk, not just a login that looked fine.

        A reauth performed while the old session is still valid can leave the
        old expiry untouched; that is not success (2026-07-28 outage).
        """
        from datetime import datetime, timedelta, timezone

        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setattr("builtins.input", lambda *_a, **_kw: "")

        reauth = self._load_reauth_module()

        driver = MagicMock()
        fresh = datetime.now(timezone.utc) + timedelta(days=7)
        with patch.object(reauth, "setup_driver", return_value=driver) as ms, \
             patch.object(reauth, "wait_for_manual_login", return_value=True) as ml, \
             patch.object(reauth, "read_token_expiry", side_effect=[None, fresh]):
            result = reauth.main()

        assert result == 0
        # setup_driver must be invoked with use_profile=True
        ms.assert_called_once()
        _, kwargs = ms.call_args
        assert kwargs.get("use_profile") is True
        assert kwargs.get("show_browser") is True
        # login helper was invoked with only the driver (no JS-filled creds)
        ml.assert_called_once_with(driver)

    def test_exits_nonzero_when_the_expiry_does_not_move(self, monkeypatch, tmp_path):
        """The 2026-07-28 failure: login looked fine, no new token was issued."""
        from datetime import datetime, timedelta, timezone

        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setattr("builtins.input", lambda *_a, **_kw: "")

        reauth = self._load_reauth_module()

        stale = datetime.now(timezone.utc) + timedelta(hours=6)
        with patch.object(reauth, "setup_driver", return_value=MagicMock()), \
             patch.object(reauth, "wait_for_manual_login", return_value=True), \
             patch.object(reauth, "read_token_expiry", side_effect=[stale, stale]):
            result = reauth.main()

        assert result == 1

    def test_exits_nonzero_when_no_token_lands_on_disk(self, monkeypatch, tmp_path):
        """Chrome closed without flushing cookies — the leading 07-28 hypothesis."""
        from datetime import datetime, timedelta, timezone

        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setattr("builtins.input", lambda *_a, **_kw: "")

        reauth = self._load_reauth_module()

        old = datetime.now(timezone.utc) + timedelta(hours=6)
        with patch.object(reauth, "setup_driver", return_value=MagicMock()), \
             patch.object(reauth, "wait_for_manual_login", return_value=True), \
             patch.object(reauth, "read_token_expiry", side_effect=[old, None]):
            result = reauth.main()

        assert result == 1

    def test_reads_the_expiry_after_quitting_the_browser(self, monkeypatch, tmp_path):
        """Chrome flushes cookies on clean shutdown, so order matters."""
        from datetime import datetime, timedelta, timezone

        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setattr("builtins.input", lambda *_a, **_kw: "")

        reauth = self._load_reauth_module()

        order = []
        driver = MagicMock()
        driver.quit.side_effect = lambda: order.append("quit")
        fresh = datetime.now(timezone.utc) + timedelta(days=7)

        def read(_profile):
            order.append("read")
            return fresh

        with patch.object(reauth, "setup_driver", return_value=driver), \
             patch.object(reauth, "wait_for_manual_login", return_value=True), \
             patch.object(reauth, "read_token_expiry", side_effect=read):
            reauth.main()

        # first read is the "before" snapshot, then quit, then the "after" read
        assert order == ["read", "quit", "read"]

    def test_exits_nonzero_on_login_fail(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setattr("builtins.input", lambda *_a, **_kw: "")

        reauth = self._load_reauth_module()

        driver = MagicMock()
        with patch.object(reauth, "setup_driver", return_value=driver), \
             patch.object(reauth, "wait_for_manual_login", return_value=False):
            result = reauth.main()

        assert result == 1

    def test_does_not_write_pickle_file(self, monkeypatch, tmp_path, capsys):
        # Even after a successful login, no pickle file should be produced --
        # the profile carries the session, not a pkl.
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv(
            "COMICSKINGDOM_COOKIE_FILE", str(tmp_path / "unused.pkl")
        )
        monkeypatch.setattr("builtins.input", lambda *_a, **_kw: "")

        reauth = self._load_reauth_module()

        driver = MagicMock()
        with patch.object(reauth, "setup_driver", return_value=driver), \
             patch.object(reauth, "wait_for_manual_login", return_value=True):
            reauth.main()

        assert not (tmp_path / "unused.pkl").exists()


# --- main(): authentication retry -------------------------------------------


class TestAuthRetry:
    """The first Chrome launch after an auto-update is unreliable.

    2026-08-05 landed on the login page, 2026-08-07 threw on navigation, and
    both self-healed on the next run — each costing a full day of Comics
    Kingdom. The retry rebuilds the driver because what recovers is the next
    *launch*, not the next navigation.
    """

    def _run_main(self, monkeypatch, tmp_path, auth_results):
        monkeypatch.setattr(
            sys, "argv",
            ["prog", "--date", "2026-08-07", "--output-dir", str(tmp_path)],
        )
        drivers = [MagicMock(), MagicMock()]
        made = []

        def fake_setup(**_kw):
            d = drivers[len(made)]
            made.append(d)
            return d

        calls = {"auth": 0}

        def fake_auth(*_a, **_kw):
            result = auth_results[calls["auth"]]
            calls["auth"] += 1
            return result

        with patch.object(cki, "setup_driver", side_effect=fake_setup), \
             patch.object(cki, "authenticate_with_cookies", side_effect=fake_auth), \
             patch.object(cki, "load_comics_catalog", return_value=[{"slug": "x"}]), \
             patch.object(cki, "load_cookie_file_path", return_value=tmp_path / "c.pkl"), \
             patch.object(cki, "scrape_all_comics", return_value=[{"slug": "x"}]):
            rc = cki.main()
        return rc, made, calls["auth"]

    def test_retries_once_with_a_fresh_driver_and_succeeds(
        self, monkeypatch, tmp_path, capsys
    ):
        rc, made, auth_calls = self._run_main(
            monkeypatch, tmp_path, auth_results=[False, True]
        )
        assert rc == 0
        assert auth_calls == 2
        assert len(made) == 2, "retry must build a NEW driver, not reuse the old one"
        assert "succeeded on retry" in capsys.readouterr().out

    def test_first_driver_is_quit_before_retrying(self, monkeypatch, tmp_path):
        _rc, made, _ = self._run_main(
            monkeypatch, tmp_path, auth_results=[False, True]
        )
        made[0].quit.assert_called()

    def test_gives_up_after_one_retry(self, monkeypatch, tmp_path, capsys):
        rc, made, auth_calls = self._run_main(
            monkeypatch, tmp_path, auth_results=[False, False]
        )
        assert rc == 1
        assert auth_calls == 2, "must not retry forever"
        assert len(made) == 2
        assert "after retry" in capsys.readouterr().out

    def test_no_retry_when_first_attempt_succeeds(self, monkeypatch, tmp_path):
        rc, made, auth_calls = self._run_main(
            monkeypatch, tmp_path, auth_results=[True]
        )
        assert rc == 0
        assert auth_calls == 1
        assert len(made) == 1, "a healthy run must not launch a second browser"
