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
import re
import sys
from datetime import date, timedelta
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


# --- #207: first-sighting identity and the 90-date window -------------------
#
# Comics Kingdom serves its newest post for any date, so the scraper saves a
# strip again every night under that night's address. Each strip is identified
# by its image set and dated by its first sighting in all saved history; a feed
# lists the strips first sighted in the 90 dates ending on the newest data file.

NEWEST = '2026-10-01'
WINDOW_START = '2026-07-04'  # 89 days before NEWEST: the window's first day
DAY_BEFORE_WINDOW = '2026-07-03'  # 90 days before NEWEST

CK_DAILY = [
    {'name': 'Blondie', 'slug': 'blondie', 'source': 'comicskingdom',
     'url': 'https://comicskingdom.com/blondie'},
    {'name': 'Mostly Gravy', 'slug': 'mostly-gravy', 'source': 'comicskingdom',
     'url': 'https://comicskingdom.com/mostly-gravy'},
    {'name': 'Secret Agent X-9', 'slug': 'secret-agent-x-9', 'source': 'comicskingdom',
     'url': 'https://comicskingdom.com/secret-agent-x-9'},
    # Owned by GoComics; old Comics Kingdom data still carries it.
    {'name': 'Broom-Hilda', 'slug': 'broomhilda',
     'url': 'https://www.gocomics.com/broomhilda'},
]


def _days(first, count):
    start = date.fromisoformat(first)
    return [(start + timedelta(days=n)).isoformat() for n in range(count)]


def _image(slug, tag):
    return f'https://wp.comicskingdom.com/uploads/{slug}-{tag}.jpg'


def ck_record(slug, day, images):
    """One saved record, shaped like comicskingdom_scraper_individual.py's output."""
    record = {
        'name': slug.replace('-', ' ').title(),
        'slug': slug,
        'date': day,
        'url': f'https://comicskingdom.com/{slug}/{day}',
        'source': 'comicskingdom',
    }
    if len(images) == 1:
        record['image_url'] = images[0]
    else:
        record['image_urls'] = list(images)
    return record


@pytest.fixture
def ck_repo(tmp_path, monkeypatch):
    """A repo-shaped tree with the generator's default paths relative to it."""
    _write_catalogs(tmp_path, daily=CK_DAILY, political=[])
    (tmp_path / 'data').mkdir()
    (tmp_path / 'public' / 'feeds').mkdir()
    monkeypatch.chdir(tmp_path)
    return tmp_path


def save_ck_day(repo, day, records, filename=None):
    path = repo / 'data' / (filename or f'comicskingdom_{day}.json')
    path.write_text(json.dumps(records))
    return path


def build_ck():
    """Run the generator the way the pipeline does: no arguments, repo as cwd."""
    return gen.main()


def ck_feed(repo, slug):
    return repo / 'public' / 'feeds' / f'{slug}.xml'


def ck_items(repo, slug):
    channel = ET.parse(ck_feed(repo, slug)).getroot().find('channel')
    items = []
    for item in channel.findall('item'):
        description = item.findtext('description') or ''
        items.append({
            'title': item.findtext('title'),
            'link': item.findtext('link'),
            'guid': item.findtext('guid'),
            'guid_is_permalink': item.find('guid').get('isPermaLink'),
            'pub_date': item.findtext('pubDate'),
            'description': description,
            'images': re.findall(r'<img src="([^"]+)"', description),
            'alts': re.findall(r'alt="([^"]+)"', description),
        })
    return items


def ck_guids(repo, slug):
    return [item['guid'] for item in ck_items(repo, slug)]


def ck_url(slug, day):
    return f'https://comicskingdom.com/{slug}/{day}'


class TestFirstSighting:
    """R1, R2: one item per image set, dated and addressed by its first sighting."""

    def test_strip_saved_on_seven_nights_is_listed_once_from_its_first_night(self, ck_repo):
        # AE2: a weekly strip stays up all week and is saved every night.
        week = _days('2026-09-24', 7)
        for day in week:
            save_ck_day(ck_repo, day, [ck_record('mostly-gravy', day, [_image('mostly-gravy', 'w39')])])

        assert build_ck() == 0

        items = ck_items(ck_repo, 'mostly-gravy')
        assert [i['guid'] for i in items] == [ck_url('mostly-gravy', '2026-09-24')]
        assert items[0]['title'] == 'Mostly Gravy - 2026-09-24'
        assert items[0]['pub_date'] == 'Thu, 24 Sep 2026 00:00:00 +0000'
        assert items[0]['alts'] == ['Mostly Gravy']

    def test_a_later_night_holding_the_same_image_adds_no_item(self, ck_repo):
        # A weekly comic: a new strip every 7 days, each saved every night it stays up.
        # Its history runs past 90 days, so the earliest copies age out of the window.
        nights = _days('2026-06-01', 122)  # 2026-06-01 .. 2026-09-30
        for n, day in enumerate(nights):
            image = _image('mostly-gravy', f'week{n // 7}')
            save_ck_day(ck_repo, day, [ck_record('mostly-gravy', day, [image])])
        build_ck()
        before = ck_guids(ck_repo, 'mostly-gravy')

        last_image = _image('mostly-gravy', f'week{(len(nights) - 1) // 7}')
        save_ck_day(ck_repo, NEWEST, [ck_record('mostly-gravy', NEWEST, [last_image])])
        build_ck()
        after = ck_guids(ck_repo, 'mostly-gravy')

        assert set(after) <= set(before), (
            f"re-delivered under new guids: {sorted(set(after) - set(before))}"
        )
        # Only a strip first sighted on the day that left the window may drop out.
        assert set(before) - set(after) <= {ck_url('mostly-gravy', DAY_BEFORE_WINDOW)}

    def test_image_order_does_not_make_a_new_strip(self, ck_repo):
        panels = [_image('blondie', 'p1'), _image('blondie', 'p2')]
        save_ck_day(ck_repo, '2026-09-30', [ck_record('blondie', '2026-09-30', panels)])
        save_ck_day(ck_repo, NEWEST, [ck_record('blondie', NEWEST, list(reversed(panels)))])

        build_ck()

        assert ck_guids(ck_repo, 'blondie') == [ck_url('blondie', '2026-09-30')]

    def test_item_fields_match_the_committed_feed(self, ck_repo):
        # Literal values from public/feeds/blondie.xml for 2026-10-01 (R2: unchanged derivation).
        panels = [
            'https://wp.comicskingdom.com/comicskingdom-redesign-uploads-production/2026/10/Y2tCbG9uZGllLUVORy02NjY4NjQ1.jpg',
            'https://wp.comicskingdom.com/comicskingdom-redesign-uploads-production/2026/10/Y2tCbG9uZGllLUVORy02NjY4NjUx.jpg',
            'https://wp.comicskingdom.com/comicskingdom-redesign-uploads-production/2026/10/Y2tCbG9uZGllLUVORy02NjY4NjUz.jpg',
        ]
        save_ck_day(ck_repo, NEWEST, [ck_record('blondie', NEWEST, panels)])

        build_ck()

        [item] = ck_items(ck_repo, 'blondie')
        assert item['guid'] == 'https://comicskingdom.com/blondie/2026-10-01'
        assert item['guid_is_permalink'] == 'false'
        assert item['link'] == 'https://comicskingdom.com/blondie/2026-10-01'
        assert item['title'] == 'Blondie - 2026-10-01'
        assert item['pub_date'] == 'Thu, 01 Oct 2026 00:00:00 +0000'
        assert 'Comic strip for 2026-10-01' in item['description']
        assert item['images'] == panels
        assert item['alts'] == ['Blondie - Panel 1', 'Blondie - Panel 2', 'Blondie - Panel 3']


class TestDateWindow:
    """R3, KTD3: the 90 dates ending on the newest data file, anchored on the data."""

    def test_window_first_day_is_inside_and_the_day_before_is_not(self, ck_repo):
        save_ck_day(ck_repo, DAY_BEFORE_WINDOW,
                    [ck_record('blondie', DAY_BEFORE_WINDOW, [_image('blondie', 'old')])])
        save_ck_day(ck_repo, WINDOW_START,
                    [ck_record('blondie', WINDOW_START, [_image('blondie', 'edge')])])
        save_ck_day(ck_repo, NEWEST, [ck_record('blondie', NEWEST, [_image('blondie', 'new')])])

        build_ck()

        assert ck_guids(ck_repo, 'blondie') == [
            ck_url('blondie', NEWEST), ck_url('blondie', WINDOW_START),
        ]

    def test_window_is_anchored_on_the_newest_data_file_not_the_clock(self, ck_repo):
        # Rebuilding old data (e.g. in push-rejection recovery) gives the same feed any day.
        save_ck_day(ck_repo, '2025-11-15', [ck_record('blondie', '2025-11-15', [_image('blondie', 'a')])])
        save_ck_day(ck_repo, '2026-01-10', [ck_record('blondie', '2026-01-10', [_image('blondie', 'b')])])

        build_ck()

        assert ck_guids(ck_repo, 'blondie') == [
            ck_url('blondie', '2026-01-10'), ck_url('blondie', '2025-11-15'),
        ]


class TestUntouchedFeeds:
    """R4: a comic with nothing first sighted in the window keeps its feed file as is."""

    def test_dormant_comic_keeps_its_feed_byte_identical(self, ck_repo):
        # AE1: one image, first sighted before the window, saved every night since.
        image = _image('secret-agent-x-9', 'only')
        for day in ['2026-06-20'] + _days(DAY_BEFORE_WINDOW, 91):
            save_ck_day(ck_repo, day, [ck_record('secret-agent-x-9', day, [image])])
        existing = ck_feed(ck_repo, 'secret-agent-x-9')
        existing.write_bytes(b'<rss><channel><title>published earlier</title></channel></rss>')
        before = existing.read_bytes()

        assert build_ck() == 0

        assert existing.read_bytes() == before

    def test_comic_with_nothing_in_the_window_and_no_feed_gets_no_file(self, ck_repo):
        image = _image('secret-agent-x-9', 'only')
        for day in (DAY_BEFORE_WINDOW, WINDOW_START, NEWEST):
            save_ck_day(ck_repo, day, [ck_record('secret-agent-x-9', day, [image])])

        build_ck()

        assert not ck_feed(ck_repo, 'secret-agent-x-9').exists()

    def test_slug_not_owned_by_the_ck_catalog_gets_no_feed(self, ck_repo):
        save_ck_day(ck_repo, NEWEST, [
            ck_record('broomhilda', NEWEST, [_image('broomhilda', 'x')]),
            ck_record('blondie', NEWEST, [_image('blondie', 'x')]),
        ])

        build_ck()

        assert ck_feed(ck_repo, 'blondie').exists()
        assert not ck_feed(ck_repo, 'broomhilda').exists()


class TestDataFiles:
    """R7, R8, KTD6: only strictly named files are read; bad input is skipped and named."""

    def test_unreadable_file_is_skipped_with_a_warning_naming_it(self, ck_repo, caplog):
        # AE3
        save_ck_day(ck_repo, '2026-09-30', [ck_record('blondie', '2026-09-30', [_image('blondie', 'a')])])
        broken = ck_repo / 'data' / 'comicskingdom_2026-09-15.json'
        broken.write_text('{"truncated": ')
        save_ck_day(ck_repo, NEWEST, [ck_record('mostly-gravy', NEWEST, [_image('mostly-gravy', 'a')])])

        with caplog.at_level(logging.WARNING):
            assert build_ck() == 0

        assert _warnings_naming(caplog, broken.name)
        assert ck_guids(ck_repo, 'blondie') == [ck_url('blondie', '2026-09-30')]
        assert ck_guids(ck_repo, 'mostly-gravy') == [ck_url('mostly-gravy', NEWEST)]

    def test_file_holding_an_object_is_skipped_with_a_warning_naming_it(self, ck_repo, caplog):
        odd = save_ck_day(ck_repo, '2026-09-30', {'blondie': 'not a list of records'})
        save_ck_day(ck_repo, NEWEST, [ck_record('blondie', NEWEST, [_image('blondie', 'a')])])

        with caplog.at_level(logging.WARNING):
            assert build_ck() == 0

        assert _warnings_naming(caplog, odd.name)
        assert ck_guids(ck_repo, 'blondie') == [ck_url('blondie', NEWEST)]

    def test_record_missing_its_url_is_skipped_with_a_warning(self, ck_repo, caplog):
        broken = ck_record('blondie', '2026-09-30', [_image('blondie', 'a')])
        del broken['url']
        path = save_ck_day(ck_repo, '2026-09-30', [broken])
        save_ck_day(ck_repo, NEWEST, [ck_record('blondie', NEWEST, [_image('blondie', 'b')])])

        with caplog.at_level(logging.WARNING):
            assert build_ck() == 0

        assert _warnings_naming(caplog, path.name)
        assert ck_guids(ck_repo, 'blondie') == [ck_url('blondie', NEWEST)]

    @pytest.mark.parametrize('broken', [
        'not a record',
        {'slug': 'blondie', 'date': '2026-09-31', 'url': ck_url('blondie', '2026-09-31'),
         'image_url': _image('blondie', 'a')},
        {'slug': 'blondie', 'date': '2026-09-15', 'url': ck_url('blondie', '2026-09-15'),
         'image_urls': None},
        {'slug': 'blondie', 'date': '2026-09-15', 'url': ck_url('blondie', '2026-09-15'),
         'image_urls': [_image('blondie', 'a'), 7]},
        {'slug': 'blondie', 'date': '2026-09-15', 'url': ck_url('blondie', '2026-09-15'),
         'image_url': None},
    ], ids=['not-a-dict', 'impossible-date', 'null-image-list', 'non-text-image', 'null-image'])
    def test_malformed_record_anywhere_in_history_is_skipped_with_a_warning(
        self, ck_repo, caplog, broken
    ):
        # History is read in full, so one bad record must never stop every CK feed.
        path = save_ck_day(ck_repo, '2026-05-01', [broken])
        save_ck_day(ck_repo, NEWEST, [ck_record('blondie', NEWEST, [_image('blondie', 'b')])])

        with caplog.at_level(logging.WARNING):
            assert build_ck() == 0

        assert _warnings_naming(caplog, path.name)
        assert ck_guids(ck_repo, 'blondie') == [ck_url('blondie', NEWEST)]

    def test_file_named_with_an_impossible_date_is_skipped_with_a_warning(self, ck_repo, caplog):
        save_ck_day(ck_repo, '2026-13-45', [ck_record('blondie', '2026-09-30', [_image('blondie', 'x')])])
        save_ck_day(ck_repo, NEWEST, [ck_record('blondie', NEWEST, [_image('blondie', 'b')])])

        with caplog.at_level(logging.WARNING):
            assert build_ck() == 0

        assert _warnings_naming(caplog, 'comicskingdom_2026-13-45.json')
        assert ck_guids(ck_repo, 'blondie') == [ck_url('blondie', NEWEST)]

    def test_no_data_files_fails_the_run(self, ck_repo):
        # The pipeline records CK generation as failed only from this exit code.
        assert build_ck() == 1

    def test_backup_file_is_not_read_and_does_not_anchor_the_window(self, ck_repo):
        save_ck_day(ck_repo, '2026-08-01', [ck_record('blondie', '2026-08-01', [_image('blondie', 'real')])])
        save_ck_day(ck_repo, NEWEST, [ck_record('mostly-gravy', NEWEST, [_image('mostly-gravy', 'a')])])
        save_ck_day(ck_repo, '2027-03-01',
                    [ck_record('blondie', '2027-03-01', [_image('blondie', 'from-backup')])],
                    filename='comicskingdom_2027-03-01_backup.json')

        build_ck()

        assert ck_guids(ck_repo, 'blondie') == [ck_url('blondie', '2026-08-01')]


class TestMainPaths:
    """KTD5: main() takes its directories, defaulting to the pipeline's paths."""

    def test_main_reads_and_writes_the_directories_it_is_given(self, tmp_path, monkeypatch):
        repo = tmp_path / 'elsewhere'
        _write_catalogs(repo, daily=CK_DAILY, political=[])
        (repo / 'data').mkdir()
        (repo / 'out').mkdir()
        save_ck_day(repo, NEWEST, [ck_record('blondie', NEWEST, [_image('blondie', 'a')])])
        monkeypatch.chdir(tmp_path)

        assert gen.main(data_dir=repo / 'data', output_dir=repo / 'out',
                        catalog_dir=repo / 'public') == 0

        assert (repo / 'out' / 'blondie.xml').exists()
