"""Tests for generate_comicskingdom_feeds.py and the Comics Kingdom catalog helper.

Until 2026-09-28 both Comics Kingdom loaders read only public/comics_list.json,
so the Comics Kingdom cartoonists listed only in public/political_comics_list.json
were never scraped and their feeds 404'd. These tests pin that both catalogs are
read, through one shared helper, with each slug loaded once.

No test here may reach comicskingdom.com. The generator has no network path
(TestNetworkFree), so its runs stay offline without patching.
"""

import json
import logging
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import generate_comicskingdom_feeds as gen

PROJECT_ROOT = Path(__file__).parent.parent

# The six Comics Kingdom editorial cartoonists listed only on the political tab
# whose feeds 404'd because no loader read that list.
POLITICAL_ONLY_CK_SLUGS = (
    'mike-smith', 'lee-judge', 'jimmy-margulies',
    'david-m-hitch', 'ed-gamble', 'mike-shelton',
)


def _write_catalogs(root, daily, political=None):
    """Write synthetic catalogs to <root>/public; omit political to leave it missing."""
    public = root / 'public'
    public.mkdir(parents=True, exist_ok=True)
    (public / 'comics_list.json').write_text(json.dumps(daily))
    if political is not None:
        (public / 'political_comics_list.json').write_text(json.dumps(political))
    return public


def _warnings_naming(caplog, text):
    return [
        r for r in caplog.records
        if r.levelno >= logging.WARNING and text in r.getMessage()
    ]


class TestCatalogPath:
    """The generator reads every Comics Kingdom entry from both public/ catalogs.

    Modeled on tests/test_generate_gocomics_feeds.py::TestCatalogPath: expected
    values come from the public/ files, never hard-coded counts.
    """

    def test_loads_every_comicskingdom_entry_from_both_public_catalogs(self, monkeypatch):
        public = PROJECT_ROOT / 'public'
        expected = {
            c['slug']
            for name in ('comics_list.json', 'political_comics_list.json')
            for c in json.loads((public / name).read_text())
            if isinstance(c, dict) and c.get('source') == 'comicskingdom'
        }

        monkeypatch.chdir(PROJECT_ROOT)
        slugs = [c['slug'] for c in gen.load_comics_list()]

        missing = sorted(expected - set(slugs))
        assert not missing, (
            f"Comics Kingdom catalog entries the generator never loads, so their "
            f"feeds are never written: {missing}"
        )
        assert len(slugs) == len(set(slugs)), (
            f"Generator loaded a slug more than once: "
            f"{sorted({s for s in slugs if slugs.count(s) > 1})}"
        )

    def test_includes_the_political_only_cartoonists(self, monkeypatch):
        """R4: the six cartoonists whose feeds 404'd are loaded by name."""
        monkeypatch.chdir(PROJECT_ROOT)
        slugs = {c['slug'] for c in gen.load_comics_list()}

        missing = [slug for slug in POLITICAL_ONLY_CK_SLUGS if slug not in slugs]
        assert not missing, (
            f"Political-tab Comics Kingdom cartoonists missing from the generator's "
            f"catalog: {missing}"
        )


class TestComicsKingdomCatalogHelper:
    """comiccaster.comicskingdom_catalog.load_comicskingdom_catalog (KTD1, KTD2)."""

    def _load(self, catalog_dir):
        from comiccaster.comicskingdom_catalog import load_comicskingdom_catalog

        return load_comicskingdom_catalog(catalog_dir)

    def test_returns_daily_then_political_comicskingdom_entries(self, tmp_path):
        public = _write_catalogs(
            tmp_path,
            daily=[
                {'name': 'Blondie', 'slug': 'blondie', 'source': 'comicskingdom'},
                {'name': 'Zits', 'slug': 'zits', 'source': 'comicskingdom'},
            ],
            political=[
                {'name': 'Mike Smith', 'slug': 'mike-smith', 'source': 'comicskingdom',
                 'is_political': True},
            ],
        )

        comics = self._load(public)

        assert [c['slug'] for c in comics] == ['blondie', 'zits', 'mike-smith']
        assert comics[2]['is_political'] is True

    def test_excludes_entries_owned_by_other_sources(self, tmp_path):
        public = _write_catalogs(
            tmp_path,
            daily=[
                {'name': 'Garfield', 'slug': 'garfield'},
                {'name': 'Peanuts', 'slug': 'peanuts', 'source': 'gocomics'},
                {'name': 'Archie', 'slug': 'archie', 'source': 'creators'},
                {'name': 'Blondie', 'slug': 'blondie', 'source': 'comicskingdom'},
            ],
            political=[
                {'name': 'Doonesbury', 'slug': 'doonesbury', 'is_political': True},
                {'name': 'Lee Judge', 'slug': 'lee-judge', 'source': 'comicskingdom',
                 'is_political': True},
            ],
        )

        comics = self._load(public)

        assert [c['slug'] for c in comics] == ['blondie', 'lee-judge']

    def test_slug_in_both_lists_is_returned_once_as_the_daily_entry(self, tmp_path, caplog):
        """KTD2: a slip back into both lists degrades to a warning, not a double scrape."""
        daily_entry = {'name': 'Mallard Fillmore', 'slug': 'mallard-fillmore',
                       'source': 'comicskingdom'}
        public = _write_catalogs(
            tmp_path,
            daily=[daily_entry],
            political=[
                {'name': 'Mallard Fillmore', 'slug': 'mallard-fillmore',
                 'source': 'comicskingdom', 'is_political': True,
                 'author': 'Bruce Tinsley'},
                {'name': 'Mike Smith', 'slug': 'mike-smith', 'source': 'comicskingdom',
                 'is_political': True},
            ],
        )

        with caplog.at_level(logging.WARNING):
            comics = self._load(public)

        assert [c['slug'] for c in comics] == ['mallard-fillmore', 'mike-smith']
        assert comics[0] == daily_entry, "the daily-catalog entry must win"
        assert _warnings_naming(caplog, 'mallard-fillmore'), (
            "de-duplicating a slug listed in both catalogs must log a warning naming it"
        )

    def test_missing_political_catalog_warns_and_returns_daily_entries(self, tmp_path, caplog):
        """Mirrors the GoComics loader: a missing political file is logged, not fatal."""
        public = _write_catalogs(
            tmp_path,
            daily=[
                {'name': 'Blondie', 'slug': 'blondie', 'source': 'comicskingdom'},
                {'name': 'Garfield', 'slug': 'garfield'},
            ],
        )

        with caplog.at_level(logging.WARNING):
            comics = self._load(str(public))  # a str path is accepted too

        assert [c['slug'] for c in comics] == ['blondie']
        assert _warnings_naming(caplog, 'political_comics_list.json'), (
            "a missing political catalog must be logged as a warning"
        )


class TestNetworkFree:
    """Phase 2 generators never reach the network (AGENTS.md); #207 removed CK's live fallback."""

    def test_generator_has_no_network_path(self):
        assert not hasattr(gen, 'requests'), "the CK generator must not import requests"
        assert not hasattr(gen, 'extract_live_comicskingdom_entries'), (
            "the CK generator must not fetch comicskingdom.com when a comic has no data"
        )


class TestMainGeneratesPoliticalFeeds:
    """Integration: main() over a tmp_path writes a political-only comic's feed."""

    DATE = '2026-09-28'

    def test_political_only_comic_gets_a_feed_with_the_political_category(
        self, tmp_path, monkeypatch
    ):
        _write_catalogs(
            tmp_path,
            daily=[
                {'name': 'Garfield', 'slug': 'garfield',
                 'url': 'https://www.gocomics.com/garfield'},
                {'name': 'Blondie', 'slug': 'blondie', 'source': 'comicskingdom',
                 'url': 'https://comicskingdom.com/blondie'},
                {'name': 'Zits', 'slug': 'zits', 'source': 'comicskingdom',
                 'url': 'https://comicskingdom.com/zits'},
            ],
            political=[
                {'name': 'Mike Smith', 'slug': 'mike-smith', 'source': 'comicskingdom',
                 'url': 'https://comicskingdom.com/mike-smith', 'is_political': True},
            ],
        )
        data_dir = tmp_path / 'data'
        data_dir.mkdir()
        (data_dir / f'comicskingdom_{self.DATE}.json').write_text(json.dumps([
            {'name': 'Blondie', 'slug': 'blondie', 'date': self.DATE,
             'url': f'https://comicskingdom.com/blondie/{self.DATE}',
             'image_url': 'https://example.com/blondie.jpg'},
            {'name': 'Mike Smith', 'slug': 'mike-smith', 'date': self.DATE,
             'url': f'https://comicskingdom.com/mike-smith/{self.DATE}',
             'image_url': 'https://example.com/mike-smith.jpg'},
        ]))
        monkeypatch.chdir(tmp_path)

        assert gen.main() == 0

        feed = tmp_path / 'public' / 'feeds' / 'mike-smith.xml'
        assert feed.exists(), (
            "No feed written for a Comics Kingdom comic listed only in "
            "political_comics_list.json, although it has scraped data."
        )
        channel = ET.parse(feed).getroot().find('channel')
        categories = [c.text for c in channel.findall('category')]
        assert 'Political Comics' in categories, (
            f"mike-smith's feed lacks the political category; channel categories: {categories}"
        )
        assert not (tmp_path / 'public' / 'feeds' / 'zits.xml').exists(), (
            "a catalog comic with no scraped data must get no feed file"
        )
