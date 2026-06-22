"""Smoke tests for scripts/tinyview_scraper_secure.py setup_driver().

Focused on the persistent Chrome profile's filesystem safety: the profile
carries an authenticated TinyView session, so its directory must be created
private (0o700), mirroring the Comics Kingdom Shape A profile. No network,
no real browser — webdriver.Chrome is mocked.
"""

import os
import stat
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import tinyview_scraper_secure as tvs


class TestSetupDriverProfile:
    def test_profile_flag_added_when_use_profile_true(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        with patch.object(tvs.webdriver, "Chrome") as chrome_cls:
            chrome_cls.return_value = MagicMock()
            tvs.setup_driver(use_profile=True)

            _, kwargs = chrome_cls.call_args
            options = kwargs["options"]
            expected = f"--user-data-dir={tmp_path / '.tinyview_chrome_profile'}"
            assert expected in options.arguments

    def test_no_profile_flag_when_use_profile_false(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        with patch.object(tvs.webdriver, "Chrome") as chrome_cls:
            chrome_cls.return_value = MagicMock()
            tvs.setup_driver(use_profile=False)

            _, kwargs = chrome_cls.call_args
            options = kwargs["options"]
            assert not any(a.startswith("--user-data-dir=") for a in options.arguments)

    def test_profile_directory_created_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        profile_dir = tmp_path / ".tinyview_chrome_profile"
        assert not profile_dir.exists()

        with patch.object(tvs.webdriver, "Chrome") as chrome_cls:
            chrome_cls.return_value = MagicMock()
            tvs.setup_driver(use_profile=True)

        assert profile_dir.is_dir()

    def test_profile_directory_contents_preserved_when_exists(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        profile_dir = tmp_path / ".tinyview_chrome_profile"
        profile_dir.mkdir()
        existing = profile_dir / "Default" / "Cookies"
        existing.parent.mkdir(parents=True)
        existing.write_bytes(b"pretend-sqlite-content")

        with patch.object(tvs.webdriver, "Chrome") as chrome_cls:
            chrome_cls.return_value = MagicMock()
            tvs.setup_driver(use_profile=True)

        assert existing.read_bytes() == b"pretend-sqlite-content"

    def test_profile_directory_mode_is_0o700(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        profile_dir = tmp_path / ".tinyview_chrome_profile"
        # Pre-create with a more permissive mode to prove setup_driver tightens it.
        profile_dir.mkdir(mode=0o755)

        with patch.object(tvs.webdriver, "Chrome") as chrome_cls:
            chrome_cls.return_value = MagicMock()
            tvs.setup_driver(use_profile=True)

        assert stat.S_IMODE(profile_dir.stat().st_mode) == 0o700
