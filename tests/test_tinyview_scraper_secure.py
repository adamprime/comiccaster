"""Smoke tests for scripts/tinyview_scraper_secure.py setup_driver().

Covers two things, no network and no real browser (the driver builder is
mocked):

  1. The persistent Chrome profile's filesystem safety: the profile carries
     an authenticated TinyView session, so its directory must be created
     private (0o700), mirroring the Comics Kingdom Shape A profile.
  2. The driver is built via the shared ``build_chrome_driver`` helper, which
     auto-resolves a ChromeDriver matching the installed Chrome. TinyView must
     not regress to a raw ``webdriver.Chrome()`` that leans on a manually
     pinned driver on PATH (incident 2026-06-09: Chrome/ChromeDriver major
     mismatch silently broke the overnight scrape).
"""

import os
import stat
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import tinyview_scraper_secure as tvs


def _options_from(mock_build):
    """Extract the Options passed to the mocked build_chrome_driver call."""
    args, _ = mock_build.call_args
    return args[0]


class TestSetupDriverProfile:
    def test_profile_flag_added_when_use_profile_true(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        with patch.object(tvs, "build_chrome_driver") as build:
            build.return_value = MagicMock()
            tvs.setup_driver(use_profile=True)

            options = _options_from(build)
            expected = f"--user-data-dir={tmp_path / '.tinyview_chrome_profile'}"
            assert expected in options.arguments

    def test_no_profile_flag_when_use_profile_false(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        with patch.object(tvs, "build_chrome_driver") as build:
            build.return_value = MagicMock()
            tvs.setup_driver(use_profile=False)

            options = _options_from(build)
            assert not any(a.startswith("--user-data-dir=") for a in options.arguments)

    def test_profile_directory_created_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        profile_dir = tmp_path / ".tinyview_chrome_profile"
        assert not profile_dir.exists()

        with patch.object(tvs, "build_chrome_driver") as build:
            build.return_value = MagicMock()
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

        with patch.object(tvs, "build_chrome_driver") as build:
            build.return_value = MagicMock()
            tvs.setup_driver(use_profile=True)

        assert existing.read_bytes() == b"pretend-sqlite-content"

    def test_profile_directory_mode_is_0o700(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        profile_dir = tmp_path / ".tinyview_chrome_profile"
        # Pre-create with a more permissive mode to prove setup_driver tightens it.
        profile_dir.mkdir(mode=0o755)

        with patch.object(tvs, "build_chrome_driver") as build:
            build.return_value = MagicMock()
            tvs.setup_driver(use_profile=True)

        assert stat.S_IMODE(profile_dir.stat().st_mode) == 0o700


class TestSetupDriverBuilder:
    def test_uses_shared_build_chrome_driver(self, tmp_path, monkeypatch):
        """Driver must come from the auto-resolving helper, not a raw
        webdriver.Chrome() bound to a manually pinned PATH driver."""
        monkeypatch.setenv("HOME", str(tmp_path))
        with patch.object(tvs, "build_chrome_driver") as build:
            build.return_value = MagicMock()
            driver = tvs.setup_driver(use_profile=True)

            build.assert_called_once()
            assert driver is build.return_value
