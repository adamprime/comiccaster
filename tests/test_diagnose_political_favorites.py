"""Tests for scripts/diagnose_political_favorites.py, the missing-comic runbook tool."""

import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import diagnose_political_favorites as diagnose


_CHALLENGE_HTML = """<html><head><title>Establishing a secure connection ...</title></head>
<body><iframe src="https://shield-templates-prod.b-cdn.net/33498/challenge.html"></iframe></body></html>"""

# GoComics' markup from 2026-11-03 on (hashed CSS-module class names).
_PAGE_HTML = """<html><body>
  <div class="FfaN_W_comicViewer">
    <div class="FfaN_W_comicViewer__layout"><a href="/nickanderson">Nick Anderson</a></div>
  </div>
  <div class="kf5J4a_featuresNotIssued"><div><a class="_3ke_CW_card" href="/chipbok"></a></div></div>
</body></html>"""


@pytest.fixture
def run_main(monkeypatch, tmp_path):
    """Run main() on a canned page, with config, browser and login faked out."""
    built = []

    def fake_build(options):
        built.append(options)
        return MagicMock()

    def _run(html, target='nickanderson'):
        monkeypatch.setattr(diagnose, 'load_config_from_env', lambda: {
            'credentials': {'email': 'test@example.com', 'password': 'test'},
            'custom_pages': [{'url': 'https://www.gocomics.com/profile/U/comics/1',
                              'category': 'political'}],
        })
        monkeypatch.setattr(diagnose, 'build_chrome_driver', fake_build)
        monkeypatch.setattr(diagnose, 'login', lambda driver, email, password: True)
        monkeypatch.setattr(diagnose, 'render_page', lambda driver, url: html)
        monkeypatch.setattr(sys, 'argv', ['diagnose', '--date', '2026-11-03',
                                          '--target-slug', target, '--output-dir', str(tmp_path)])
        return diagnose.main()

    _run.built = built
    return _run


class TestDiagnosePoliticalFavorites:
    def test_builds_its_driver_with_the_shared_helper(self, run_main):
        """A raw webdriver.Chrome() uses whatever chromedriver is on PATH (it
        crashed on a stale one on 2026-11-03) and runs as HeadlessChrome, which
        Bunny Shield refuses; the shared builder handles both."""
        run_main(_PAGE_HTML)

        assert len(run_main.built) == 1
        assert '--headless=new' in run_main.built[0].arguments

    def test_challenge_page_is_named_not_misdiagnosed(self, run_main, capsys):
        rc = run_main(_CHALLENGE_HTML)
        out = capsys.readouterr().out

        assert rc == 1
        assert 'bot challenge' in out.lower()
        assert 'Not on the page at all' not in out

    def test_finds_updated_and_not_issued_slugs_on_current_markup(self, run_main, capsys):
        rc = run_main(_PAGE_HTML)
        out = capsys.readouterr().out

        assert rc == 0
        assert '(updated today): 1' in out
        assert '(did NOT update today): 1' in out
        assert 'Found in ComicViewer (updated)' in out

    def test_target_listed_as_not_issued(self, run_main, capsys):
        run_main(_PAGE_HTML, target='chipbok')

        assert 'Found in FeaturesNotIssued' in capsys.readouterr().out
