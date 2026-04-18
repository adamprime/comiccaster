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
        # Current behavior: any exception returns False (the entire `except`
        # block swallows everything).
        assert cki.is_authenticated(driver) is False


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

        config = {"cookie_file": cookie_file}
        assert cki.authenticate_with_cookies(driver, config) is False

        captured = capsys.readouterr()
        # This exact string is what Unit 3 will intentionally reshape.
        # Locking it here so Unit 3's change is visible as a test diff.
        assert "Authentication failed - please run reauth script" in captured.out

    def test_returns_true_when_cookies_load_and_auth_succeeds(self, tmp_path):
        cookie_file = tmp_path / "cookies.pkl"
        with open(cookie_file, "wb") as f:
            pickle.dump([{"name": "s", "value": "v", "domain": "comicskingdom.com"}], f)

        driver = MagicMock()
        driver.current_url = "https://comicskingdom.com/favorites"

        config = {"cookie_file": cookie_file}
        assert cki.authenticate_with_cookies(driver, config) is True


# --- setup_driver -----------------------------------------------------------


class TestSetupDriver:
    def test_headless_when_show_browser_false(self):
        with patch.object(cki.webdriver, "Chrome") as chrome_cls:
            chrome_cls.return_value = MagicMock()
            cki.setup_driver(show_browser=False)

            args, kwargs = chrome_cls.call_args
            options = kwargs["options"]
            assert "--headless=new" in options.arguments

    def test_not_headless_when_show_browser_true(self):
        with patch.object(cki.webdriver, "Chrome") as chrome_cls:
            chrome_cls.return_value = MagicMock()
            cki.setup_driver(show_browser=True)

            args, kwargs = chrome_cls.call_args
            options = kwargs["options"]
            assert "--headless=new" not in options.arguments

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


# --- load_config_from_env ---------------------------------------------------


class TestLoadConfigFromEnv:
    def test_credentials_not_printed(self, capsys, monkeypatch):
        monkeypatch.setenv("COMICSKINGDOM_USERNAME", "test-user-do-not-log")
        monkeypatch.setenv("COMICSKINGDOM_PASSWORD", "test-pass-do-not-log")
        monkeypatch.setenv(
            "COMICSKINGDOM_COOKIE_FILE", "data/comicskingdom_cookies.pkl"
        )

        cki.load_config_from_env()
        captured = capsys.readouterr()
        assert "test-user-do-not-log" not in captured.out
        assert "test-pass-do-not-log" not in captured.out
