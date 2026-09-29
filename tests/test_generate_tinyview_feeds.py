"""Tests for scripts/generate_tinyview_feeds_from_data.py.

Each TinyView feed is built from every usable strip saved with a strip date in
the 90 days up to the newest ``data/tinyview_YYYY-MM-DD.json``. Strips are
deduplicated by address (the earliest-recorded copy wins), each item shows only
its own strip's images, and a comic with no usable strip in the window keeps
its feed file exactly as it is.

Every test runs offline against files under ``tmp_path``.
"""

import json
import logging
import os
import re
import sys
import xml.etree.ElementTree as ET

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import generate_tinyview_feeds_from_data as gen  # noqa: E402


NEWEST = '2026-09-29'
WINDOW_START = '2026-07-01'  # exactly 90 days before NEWEST
DAY_BEFORE_WINDOW = '2026-06-30'  # 91 days before NEWEST


def _comic(name, slug, series=None, author=None):
    return {
        'name': name,
        'slug': slug,
        'author': author or name,
        'url': f'https://tinyview.com/{series or slug}',
        'source': 'tinyview',
    }


CATALOG = [
    _comic('ADHDinos', 'adhdinos', author='Pina Vazquez'),
    _comic('Fowl Language', 'fowl-language-tinyview', series='fowl-language'),
    _comic('Graphic Rage', 'graphic-rage'),
    _comic('Kowal Comics', 'kowal-comics'),
    _comic('Mr. Lovenstein', 'mrlovenstein'),
    _comic('Nick Anderson', 'nick-anderson'),
]


def strip_url(series, date, part):
    year, month, day = date.split('-')
    return f'https://tinyview.com/{series}/{year}/{month}/{day}/{part}'


def own_images(series, date, part, count=2):
    year, month, day = date.split('-')
    folder = f'https://cdn.tinyview.com/{series}/{year}/{month}/{day}/{part}'
    return [f'{folder}/{n}.jpg' for n in range(1, count + 1)]


def strip(slug, date, part, series=None, name=None, images=None,
          date_text=None, description=''):
    """One saved strip record, shaped like the scraper's output."""
    series = series or slug
    if images is None:
        images = own_images(series, date, part)
    return {
        'name': name if name is not None else part,
        'slug': slug,
        'date': date_text or date,
        'url': strip_url(series, date, part),
        'source': 'tinyview',
        'description': description,
        'images': [{'url': url, 'alt': url, 'title': ''} for url in images],
    }


@pytest.fixture
def repo(tmp_path):
    """A repo-shaped tree: data/, public/feeds/ and the TinyView catalog."""
    (tmp_path / 'data').mkdir()
    (tmp_path / 'public' / 'feeds').mkdir(parents=True)
    (tmp_path / 'public' / 'tinyview_comics_list.json').write_text(json.dumps(CATALOG))
    return tmp_path


def save_day(repo, file_date, entries, filename=None):
    """Write one day's data file, as the scraper does."""
    path = repo / 'data' / (filename or f'tinyview_{file_date}.json')
    path.write_text(json.dumps(entries))
    return path


def build(repo):
    """Run the generator over ``repo`` without touching the working directory."""
    return gen.main(
        data_dir=repo / 'data',
        output_dir=repo / 'public' / 'feeds',
        catalog_path=repo / 'public' / 'tinyview_comics_list.json',
    )


def feed_path(repo, slug):
    return repo / 'public' / 'feeds' / f'{slug}.xml'


def feed_items(repo, slug):
    """The items of a written feed, in document order."""
    channel = ET.parse(feed_path(repo, slug)).getroot().find('channel')
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
        })
    return items


def guids(repo, slug):
    return [item['guid'] for item in feed_items(repo, slug)]


def without_build_date(xml_text):
    return re.sub(r'<lastBuildDate>[^<]*</lastBuildDate>', '', xml_text)


def warnings_naming(caplog, text):
    return [r for r in caplog.records if r.levelno >= logging.WARNING and text in r.getMessage()]


class TestHistoryWindow:
    """R1 and KTD1: every strip in the 90-day window, anchored on the newest data file."""

    def test_three_daily_files_each_adding_a_strip_give_three_items_newest_first(self, repo):
        save_day(repo, '2026-09-27', [strip('nick-anderson', '2026-09-26', 'first')])
        save_day(repo, '2026-09-28', [strip('nick-anderson', '2026-09-27', 'second')])
        save_day(repo, NEWEST, [strip('nick-anderson', '2026-09-28', 'third')])

        assert build(repo) == 0

        assert guids(repo, 'nick-anderson') == [
            strip_url('nick-anderson', '2026-09-28', 'third'),
            strip_url('nick-anderson', '2026-09-27', 'second'),
            strip_url('nick-anderson', '2026-09-26', 'first'),
        ], "the feed must carry every saved strip in the window, newest first"

    def test_strip_dated_exactly_90_days_before_the_newest_file_is_included(self, repo):
        save_day(repo, WINDOW_START, [strip('nick-anderson', WINDOW_START, 'boundary')])
        save_day(repo, NEWEST, [strip('nick-anderson', NEWEST, 'today')])

        build(repo)

        assert strip_url('nick-anderson', WINDOW_START, 'boundary') in guids(repo, 'nick-anderson'), (
            "the boundary day (exactly 90 days before the newest data file) counts as inside"
        )

    def test_strip_dated_91_days_before_the_newest_file_is_excluded(self, repo):
        # The file itself is inside the window; only the strip's own date is not.
        save_day(repo, '2026-07-02', [
            strip('nick-anderson', DAY_BEFORE_WINDOW, 'too-old'),
            strip('nick-anderson', '2026-07-02', 'in-window'),
        ])
        save_day(repo, NEWEST, [strip('nick-anderson', NEWEST, 'today')])

        build(repo)

        assert guids(repo, 'nick-anderson') == [
            strip_url('nick-anderson', NEWEST, 'today'),
            strip_url('nick-anderson', '2026-07-02', 'in-window'),
        ]

    def test_legacy_slash_date_inside_the_window_is_included(self, repo):
        save_day(repo, '2026-09-20', [
            strip('nick-anderson', '2026-09-19', 'legacy', date_text='2026/09/19'),
        ])
        save_day(repo, NEWEST, [strip('nick-anderson', NEWEST, 'today')])

        build(repo)

        items = feed_items(repo, 'nick-anderson')
        legacy = [i for i in items if i['guid'] == strip_url('nick-anderson', '2026-09-19', 'legacy')]
        assert legacy, "a strip saved with a legacy YYYY/MM/DD date must be included"
        assert legacy[0]['pub_date'] == 'Sat, 19 Sep 2026 23:59:59 +0000'

    def test_strip_dated_on_the_window_start_but_saved_in_an_earlier_named_file_is_included(
        self, repo
    ):
        # A scraper run with a past --date can save a strip under an older file
        # name than the strip's own date. Here the only copy of the window-start
        # strip lives in a file named one day before window_start; it must still
        # be read and kept, not dropped by a file-name pre-filter.
        save_day(repo, DAY_BEFORE_WINDOW, [strip('nick-anderson', WINDOW_START, 'late-saved')])
        save_day(repo, NEWEST, [strip('nick-anderson', NEWEST, 'today')])

        assert build(repo) == 0

        assert strip_url('nick-anderson', WINDOW_START, 'late-saved') in guids(repo, 'nick-anderson'), (
            "a strip dated exactly on the window start must count even when its only "
            "saved copy sits in a file named a day (or more) earlier"
        )

    def test_window_is_anchored_on_the_newest_data_file_not_the_clock(self, repo):
        # Recovery regeneration must not depend on when it runs (R5).
        save_day(repo, '2025-11-01', [strip('nick-anderson', '2025-10-31', 'autumn')])
        save_day(repo, '2026-01-10', [strip('nick-anderson', '2026-01-09', 'winter')])

        build(repo)

        assert guids(repo, 'nick-anderson') == [
            strip_url('nick-anderson', '2026-01-09', 'winter'),
            strip_url('nick-anderson', '2025-10-31', 'autumn'),
        ]


class TestDataFiles:
    """KTD1: only strictly named data files are read; bad input is skipped, not fatal."""

    def test_backup_file_is_ignored(self, repo):
        save_day(repo, '2026-09-28', [strip('nick-anderson', '2026-09-27', 'real')])
        save_day(repo, '2026-09-28', [strip('nick-anderson', '2026-09-26', 'from-backup')],
                 filename='tinyview_2026-09-28_backup.json')

        assert build(repo) == 0

        assert guids(repo, 'nick-anderson') == [strip_url('nick-anderson', '2026-09-27', 'real')]

    def test_empty_data_file_is_ignored_without_error(self, repo, caplog):
        save_day(repo, '2026-09-27', [strip('nick-anderson', '2026-09-26', 'saved')])
        save_day(repo, '2026-09-28', [])
        save_day(repo, NEWEST, [])

        with caplog.at_level(logging.WARNING):
            assert build(repo) == 0

        assert guids(repo, 'nick-anderson') == [strip_url('nick-anderson', '2026-09-26', 'saved')]
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING], (
            "an empty [] data file is normal (a night with nothing new) and must not warn"
        )

    @pytest.mark.parametrize('content', ['{not json', '{"slug": "nick-anderson"}'],
                             ids=['invalid-json', 'not-a-list'])
    def test_malformed_file_is_skipped_with_a_warning_and_other_feeds_build(
        self, repo, caplog, content
    ):
        save_day(repo, '2026-09-27', [strip('nick-anderson', '2026-09-26', 'good')])
        (repo / 'data' / 'tinyview_2026-09-28.json').write_text(content)
        save_day(repo, NEWEST, [strip('kowal-comics', '2026-09-28', 'also-good')])

        with caplog.at_level(logging.WARNING):
            assert build(repo) == 0

        assert warnings_naming(caplog, 'tinyview_2026-09-28.json'), (
            "a malformed data file must be named in a warning"
        )
        assert guids(repo, 'nick-anderson') == [strip_url('nick-anderson', '2026-09-26', 'good')]
        assert guids(repo, 'kowal-comics') == [strip_url('kowal-comics', '2026-09-28', 'also-good')]

    def test_malformed_record_is_skipped_with_a_warning_and_the_rest_build(self, repo, caplog):
        no_url = strip('nick-anderson', '2026-09-25', 'no-url')
        del no_url['url']
        bad_date = strip('nick-anderson', '2026-09-24', 'bad-date', date_text='last Tuesday')
        save_day(repo, NEWEST, [
            'not a record',
            no_url,
            bad_date,
            strip('nick-anderson', '2026-09-28', 'good'),
        ])

        with caplog.at_level(logging.WARNING):
            assert build(repo) == 0

        assert len(warnings_naming(caplog, f'tinyview_{NEWEST}.json')) >= 3, (
            "each skipped record must be warned about, naming its data file"
        )
        assert guids(repo, 'nick-anderson') == [strip_url('nick-anderson', '2026-09-28', 'good')]


class TestDeduplication:
    """KTD2 and R5: one item per strip address, in a stable order."""

    def test_strip_saved_in_two_files_keeps_the_older_files_copy(self, repo):
        first = strip('nick-anderson', '2026-09-26', 'cartoon',
                      name='First copy', description='as first recorded')
        later = strip('nick-anderson', '2026-09-26', 'cartoon',
                      name='Later copy', description='as recorded again')
        save_day(repo, '2026-09-27', [first])
        save_day(repo, NEWEST, [later])

        build(repo)

        items = feed_items(repo, 'nick-anderson')
        assert len(items) == 1
        assert items[0]['title'] == 'First copy'
        assert 'as first recorded' in items[0]['description']

    def test_four_identical_copies_in_one_file_give_one_item(self, repo):
        bella = strip('kowal-comics', '2026-09-24', 'bella-part-4-of-5')
        save_day(repo, NEWEST, [bella, bella, bella, bella])

        build(repo)

        assert guids(repo, 'kowal-comics') == [strip_url('kowal-comics', '2026-09-24', 'bella-part-4-of-5')]

    def test_copy_without_usable_images_does_not_hide_a_later_usable_copy(self, repo):
        # R1: a strip counts once it has been saved with its own images.
        save_day(repo, '2026-09-27', [strip('nick-anderson', '2026-09-26', 'cartoon', images=[])])
        save_day(repo, NEWEST, [strip('nick-anderson', '2026-09-26', 'cartoon')])

        build(repo)

        items = feed_items(repo, 'nick-anderson')
        assert [i['guid'] for i in items] == [strip_url('nick-anderson', '2026-09-26', 'cartoon')]
        assert items[0]['images'] == own_images('nick-anderson', '2026-09-26', 'cartoon')

    def test_same_date_siblings_come_out_in_the_same_order_whatever_order_files_are_read(
        self, tmp_path
    ):
        part_a = strip('kowal-comics', '2026-09-24', 'bella-part-1-of-5')
        part_b = strip('kowal-comics', '2026-09-24', 'bella-part-2-of-5')
        orders = []
        for name, (older, newer) in {'a-first': (part_a, part_b), 'b-first': (part_b, part_a)}.items():
            root = tmp_path / name
            root.mkdir()
            (root / 'data').mkdir()
            (root / 'public' / 'feeds').mkdir(parents=True)
            (root / 'public' / 'tinyview_comics_list.json').write_text(json.dumps(CATALOG))
            save_day(root, '2026-09-25', [older])
            save_day(root, NEWEST, [newer])
            build(root)
            orders.append(guids(root, 'kowal-comics'))

        assert sorted(orders[0]) == sorted([part_a['url'], part_b['url']])
        assert orders[0] == orders[1], (
            "same-date strips must come out in one fixed order regardless of which file saved them first"
        )

    def test_rebuilding_from_the_same_data_gives_the_same_feed(self, repo):
        save_day(repo, '2026-09-25', [
            strip('kowal-comics', '2026-09-24', 'bella-part-2-of-5'),
            strip('kowal-comics', '2026-09-24', 'bella-part-1-of-5'),
        ])
        save_day(repo, NEWEST, [strip('kowal-comics', '2026-09-28', 'bella-part-5-of-5')])

        build(repo)
        first = feed_path(repo, 'kowal-comics').read_text()
        build(repo)
        second = feed_path(repo, 'kowal-comics').read_text()

        assert without_build_date(first) == without_build_date(second)


class TestItemFields:
    """KTD3 and R2: guid, title and pub_date are derived exactly as before this change.

    The expected values are literals produced by the generator as it stood before
    the 90-day window (it read only the newest data file); the ADHDinos record is
    the one saved in data/tinyview_2026-09-28.json, whose item is in the committed
    public/feeds/adhdinos.xml.
    """

    def test_item_fields_match_the_previous_generator_for_the_same_strip(self, repo):
        record = {
            'name': 'ADHDinos',
            'slug': 'adhdinos',
            'date': '2026-09-27',
            'url': 'https://tinyview.com/adhdinos/2026/09/27/hammer-of-shame',
            'source': 'tinyview',
            'description': 'Learning the hard way',
            'images': [
                {'url': 'https://cdn.tinyview.com/adhdinos/2026/09/27/hammer-of-shame/1-frame-1.jpg',
                 'alt': 'https://cdn.tinyview.com/adhdinos/2026/09/27/hammer-of-shame/1-frame-1.jpg',
                 'title': ''},
            ],
        }
        save_day(repo, '2026-09-28', [record])

        build(repo)

        [item] = feed_items(repo, 'adhdinos')
        assert item['title'] == 'ADHDinos'
        assert item['guid'] == 'https://tinyview.com/adhdinos/2026/09/27/hammer-of-shame'
        assert item['guid_is_permalink'] == 'false'
        assert item['link'] == 'https://tinyview.com/adhdinos/2026/09/27/hammer-of-shame'
        assert item['pub_date'] == 'Sun, 27 Sep 2026 23:59:59 +0000'
        assert 'Learning the hard way' in item['description']

    def test_record_without_a_name_is_titled_with_the_comic_name_and_its_saved_date(self, repo):
        record = strip('nick-anderson', '2026-09-20', 'some-cartoon', date_text='2026/09/20')
        del record['name']
        save_day(repo, NEWEST, [record])

        build(repo)

        [item] = feed_items(repo, 'nick-anderson')
        assert item['title'] == 'Nick Anderson - 2026/09/20'
        assert item['guid'] == 'https://tinyview.com/nick-anderson/2026/09/20/some-cartoon'
        assert item['pub_date'] == 'Sun, 20 Sep 2026 23:59:59 +0000'


class TestOwnImages:
    """R4: each item shows only the images filed under its own strip."""

    def test_strip_carrying_a_siblings_images_shows_only_its_own(self, repo):
        mine = own_images('kowal-comics', '2026-09-24', 'bella-part-4-of-5')
        siblings = own_images('kowal-comics', '2026-09-24', 'bella-part-5-of-5')
        save_day(repo, NEWEST, [
            strip('kowal-comics', '2026-09-24', 'bella-part-4-of-5', images=siblings + mine),
        ])

        build(repo)

        [item] = feed_items(repo, 'kowal-comics')
        assert item['images'] == mine

    def test_fowl_language_strip_keeps_its_images(self, repo):
        # The feed slug is fowl-language-tinyview; TinyView files the strip at fowl-language.
        save_day(repo, NEWEST, [
            strip('fowl-language-tinyview', '2026-09-28', 'nap-time', series='fowl-language'),
        ])

        build(repo)

        [item] = feed_items(repo, 'fowl-language-tinyview')
        assert item['images'] == own_images('fowl-language', '2026-09-28', 'nap-time')


class TestUntouchedFeeds:
    """R3 and KTD4: only comics with a usable strip in the window are written."""

    DORMANT_XML = (
        "<?xml version='1.0' encoding='UTF-8'?>\n"
        '<rss version="2.0"><channel><title>Graphic Rage - TinyView</title>'
        '<item><title>placeholder from 2025</title></item></channel></rss>'
    )

    def test_comic_without_a_strip_in_the_window_keeps_its_feed_byte_identical(self, repo):
        dormant = feed_path(repo, 'graphic-rage')
        dormant.write_text(self.DORMANT_XML)
        before = dormant.read_bytes()
        save_day(repo, '2026-06-01', [strip('graphic-rage', '2026-05-31', 'long-ago')])
        save_day(repo, NEWEST, [strip('nick-anderson', NEWEST, 'today')])

        assert build(repo) == 0

        assert dormant.read_bytes() == before
        assert feed_path(repo, 'nick-anderson').exists()

    def test_comic_without_a_strip_in_the_window_gets_no_new_feed(self, repo):
        save_day(repo, NEWEST, [strip('nick-anderson', NEWEST, 'today')])

        build(repo)

        written = sorted(p.name for p in (repo / 'public' / 'feeds').iterdir())
        assert written == ['nick-anderson.xml']

    @pytest.mark.parametrize('images', [
        [],
        own_images('mrlovenstein', '2026-09-27', 'a-sibling'),
        ['https://example.com/mrlovenstein/2026/09/27/only-strip/1.jpg'],
    ], ids=['no-images', 'sibling-images-only', 'off-cdn-images-only'])
    def test_comic_whose_only_strip_has_no_usable_images_is_left_untouched(self, repo, images):
        existing = feed_path(repo, 'mrlovenstein')
        existing.write_text(self.DORMANT_XML)
        before = existing.read_bytes()
        save_day(repo, NEWEST, [strip('mrlovenstein', '2026-09-27', 'only-strip', images=images)])

        assert build(repo) == 0

        assert existing.read_bytes() == before, "a 0-item feed must never be written"

    def test_comic_whose_only_strip_has_no_usable_images_gets_no_feed(self, repo):
        save_day(repo, NEWEST, [strip('mrlovenstein', '2026-09-27', 'only-strip', images=[])])

        build(repo)

        assert not feed_path(repo, 'mrlovenstein').exists()

    def test_strip_for_a_slug_missing_from_the_catalog_is_skipped_and_others_build(self, repo):
        save_day(repo, NEWEST, [
            strip('not-in-catalog', '2026-09-28', 'mystery'),
            strip('nick-anderson', '2026-09-28', 'known'),
        ])

        assert build(repo) == 0

        assert not feed_path(repo, 'not-in-catalog').exists()
        assert guids(repo, 'nick-anderson') == [strip_url('nick-anderson', '2026-09-28', 'known')]


class TestPipelineInvocation:
    """The pipeline runs the script from the repo root with no arguments."""

    def test_no_argument_run_reads_data_and_writes_public_feeds(self, repo, monkeypatch):
        save_day(repo, '2026-09-27', [strip('nick-anderson', '2026-09-26', 'first')])
        save_day(repo, NEWEST, [strip('nick-anderson', '2026-09-28', 'second')])
        monkeypatch.chdir(repo)

        assert gen.main() == 0

        assert guids(repo, 'nick-anderson') == [
            strip_url('nick-anderson', '2026-09-28', 'second'),
            strip_url('nick-anderson', '2026-09-26', 'first'),
        ]

    def test_no_argument_run_filters_sibling_images(self, repo, monkeypatch):
        mine = own_images('kowal-comics', '2026-09-24', 'bella-part-4-of-5')
        siblings = own_images('kowal-comics', '2026-09-24', 'bella-part-3-of-5')
        save_day(repo, NEWEST, [
            strip('kowal-comics', '2026-09-24', 'bella-part-4-of-5', images=mine + siblings),
        ])
        monkeypatch.chdir(repo)

        assert gen.main() == 0

        assert feed_items(repo, 'kowal-comics')[0]['images'] == mine

    def test_returns_zero_and_writes_nothing_when_there_is_no_data(self, repo, monkeypatch):
        monkeypatch.chdir(repo)

        assert gen.main() == 0

        assert list((repo / 'public' / 'feeds').iterdir()) == []
