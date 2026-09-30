"""Tests for scripts/tinyview_scraper_local_authenticated.py, the nightly TinyView scrape.

Several strips can share a date (Kowal Comics' five-part "Bella" is all filed under
2026/09/24), so the nightly scrape decides "already recorded" by each strip's own
address, fetches every new strip by that address, and adds a same-day rerun's strips
to the day's file instead of replacing it.

No browser, no network: the browser session and TinyviewScraper are replaced by a
stub that serves a canned listing per series.
"""

import json
import os
import sys
from contextlib import contextmanager
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from comiccaster.tinyview_scraper import BrowserSessionLost
from comiccaster.tinyview_strips import canonical_strip_url, strip_folder

# Importing the script runs load_dotenv() (there and in tinyview_scraper_secure),
# which would read the operator's real .env with its TinyView credentials.
with patch('dotenv.load_dotenv'):
    import tinyview_scraper_local_authenticated as tvl


DATE = '2026-09-29'
BASE = 'https://tinyview.com'
TOTAL_PREFIX = 'Listed but not recorded: '

KOWAL = {'name': 'Kowal Comics', 'slug': 'kowal-comics', 'url': 'https://tinyview.com/kowal-comics'}
ADHDINOS = {'name': 'ADHDinos', 'slug': 'adhdinos', 'url': 'https://tinyview.com/adhdinos'}
FOWL = {'name': 'Fowl Language', 'slug': 'fowl-language-tinyview', 'url': 'https://tinyview.com/fowl-language'}


def address(series, date, strip):
    return f'{BASE}/{series}/{date}/{strip}'


def bella(part):
    return address('kowal-comics', '2026/09/24', f'bella-part-{part}-of-5')


def listed(url):
    """One entry as TinyviewScraper.get_recent_comics returns it."""
    href = url[len(BASE):]
    series, year, month, day, strip = canonical_strip_url(url)[len(BASE) + 1:].split('/')
    date = f'{year}/{month}/{day}'
    return {
        'href': href,
        'date': date,
        'date_obj': datetime.strptime(date, '%Y/%m/%d'),
        'title': strip,
        'url': url,
    }


def saved_record(feed_slug, url, name='Kowal Comics', title='saved earlier'):
    """A strip as an earlier run saved it in data/tinyview_<date>.json."""
    folder = strip_folder(url)
    panel = f'https://cdn.tinyview.com/{folder}/1.jpg'
    return {
        'name': name,
        'slug': feed_slug,
        'date': '-'.join(folder.split('/')[1:4]),
        'url': url,
        'source': 'tinyview',
        'images': [{'url': panel, 'alt': panel, 'title': ''}],
        'image_urls': [panel],
        'image_count': 1,
        'description': '',
        'title': title,
    }


def write_saved(data_dir, filename, records):
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / filename).write_text(json.dumps(records, indent=2))


def read_saved(data_dir, filename=f'tinyview_{DATE}.json'):
    return json.loads((data_dir / filename).read_text())


class StubScraper:
    """Stands in for TinyviewScraper: a canned listing per series, no browser.

    Without an address, scrape_comic behaves like the real date lookup and loads the
    first listed strip filed under that date.
    """

    def __init__(self, listings, empty=(), raising=(), untitled=(), reported_urls=None,
                 lost=(), lost_listing=()):
        self.listings = listings
        self.empty = set(empty)
        self.raising = set(raising)
        self.lost = set(lost)  # addresses whose page load finds the browser session dead
        self.lost_listing = set(lost_listing)  # series whose listing load finds it dead
        self.untitled = set(untitled)
        self.reported_urls = reported_urls or {}
        self.listing_calls = []
        self.scrape_calls = []
        self.driver = None

    def get_recent_comics(self, comic_slug, days_back=90):
        self.listing_calls.append((comic_slug, days_back))
        if comic_slug in self.lost_listing:
            raise BrowserSessionLost('invalid session id')
        return [dict(entry) for entry in self.listings.get(comic_slug, [])]

    def scrape_comic(self, comic_slug, date, *, strip_url=None):
        if strip_url is None:
            matches = [e['url'] for e in self.listings.get(comic_slug, []) if e['date'] == date]
            loaded = canonical_strip_url(matches[0]) if matches else None
        else:
            loaded = canonical_strip_url(strip_url)
        self.scrape_calls.append(
            {'comic_slug': comic_slug, 'date': date, 'strip_url': strip_url, 'loaded': loaded})
        if loaded is None or loaded in self.empty:
            return None
        if loaded in self.raising:
            raise RuntimeError('page crashed')
        if loaded in self.lost:
            raise BrowserSessionLost('invalid session id')
        folder = strip_folder(loaded)
        panel = f'https://cdn.tinyview.com/{folder}/1.jpg'
        result = {
            'source': 'tinyview',
            'comic_slug': comic_slug,
            'date': date,
            'url': self.reported_urls.get(loaded, loaded),
            'images': [{'url': panel, 'alt': 'panel', 'title': ''}],
            'image_count': 1,
            'published_date': datetime(2026, 9, 29),
            'description': f'about {folder}',
        }
        if loaded not in self.untitled:
            result['title'] = f'title of {folder}'
        return result

    def loaded(self):
        return [call['loaded'] for call in self.scrape_calls]


@pytest.fixture(autouse=True)
def forbid_browser(monkeypatch):
    """Any test that reaches the real browser setup fails instead of starting Chrome."""
    def refuse(*args, **kwargs):
        raise AssertionError('a test tried to start a browser')
    monkeypatch.setattr(tvl, 'setup_driver', refuse)


@contextmanager
def no_browser(scraper):
    """Run the authenticated scrape with a mock driver and ``scraper`` in place of TinyviewScraper."""
    driver = MagicMock(name='driver')
    with patch.object(tvl, 'setup_driver', return_value=driver), \
            patch.object(tvl, 'is_authenticated', return_value=True), \
            patch.object(tvl, 'load_config_from_env', return_value={}), \
            patch.object(tvl, 'TinyviewScraper', return_value=scraper):
        yield driver


def run_nightly(data_dir, comics, scraper, days_back=90):
    """Load what is recorded in ``data_dir``, then run the scrape over ``comics``."""
    recorded = tvl.load_recorded_strips(str(data_dir))
    with no_browser(scraper):
        return tvl.scrape_all_comics_authenticated(comics, DATE, days_back, recorded)


def run_total(output):
    """The end-of-run count and the addresses listed under it."""
    lines = output.splitlines()
    starts = [i for i, line in enumerate(lines) if line.startswith(TOTAL_PREFIX)]
    assert len(starts) == 1, f'expected one "{TOTAL_PREFIX}N" line, got {len(starts)}:\n{output}'
    start = starts[0]
    count = int(lines[start][len(TOTAL_PREFIX):])
    return count, [line.strip() for line in lines[start + 1:start + 1 + count]]


# --- What is already recorded -------------------------------------------------


class TestLoadExistingData:
    def test_collects_every_saved_strip_address_including_the_backup_file(self, tmp_path, capsys):
        write_saved(tmp_path, 'tinyview_2026-09-25.json', [
            saved_record('kowal-comics', bella(4)),
            saved_record('adhdinos', address('adhdinos', '2026/09/23', 'taking-chances'), name='ADHDinos'),
        ])
        write_saved(tmp_path, 'tinyview_2025-11-16_backup.json', [
            saved_record('kowal-comics', address('kowal-comics', '2025/11/14', 'old-strip')),
        ])

        recorded = tvl.load_recorded_strips(str(tmp_path))

        assert recorded == {
            bella(4),
            address('adhdinos', '2026/09/23', 'taking-chances'),
            address('kowal-comics', '2025/11/14', 'old-strip'),
        }
        assert 'Loaded 3' in capsys.readouterr().out

    def test_strips_sharing_a_date_are_recorded_separately(self, tmp_path):
        write_saved(tmp_path, 'tinyview_2026-09-25.json', [
            saved_record('kowal-comics', bella(3)),
            saved_record('kowal-comics', bella(4)),
        ])

        assert tvl.load_recorded_strips(str(tmp_path)) == {bella(3), bella(4)}

    def test_addresses_are_canonical(self, tmp_path):
        write_saved(tmp_path, 'tinyview_2026-09-25.json', [
            saved_record('kowal-comics', bella(4) + '#comments'),
            saved_record('kowal-comics', bella(3) + '/'),
        ])

        assert tvl.load_recorded_strips(str(tmp_path)) == {bella(3), bella(4)}

    def test_no_saved_files_means_nothing_recorded(self, tmp_path):
        assert tvl.load_recorded_strips(str(tmp_path)) == set()

    def test_an_unreadable_file_is_skipped_and_the_rest_still_count(self, tmp_path, capsys):
        write_saved(tmp_path, 'tinyview_2026-09-25.json', [saved_record('kowal-comics', bella(4))])
        (tmp_path / 'tinyview_2026-09-26.json').write_text('{not json')

        assert tvl.load_recorded_strips(str(tmp_path)) == {bella(4)}
        assert 'tinyview_2026-09-26.json' in capsys.readouterr().out

    def test_a_malformed_entry_does_not_cost_the_rest_of_its_file(self, tmp_path):
        write_saved(tmp_path, 'tinyview_2026-09-25.json', [
            'not a record',
            {'url': 42},
            saved_record('kowal-comics', bella(4)),
        ])
        write_saved(tmp_path, 'tinyview_2026-09-26.json', [
            saved_record('adhdinos', address('adhdinos', '2026/09/23', 'taking-chances'), name='ADHDinos'),
        ])

        recorded = tvl.load_recorded_strips(str(tmp_path))

        assert recorded == {
            bella(4),
            address('adhdinos', '2026/09/23', 'taking-chances'),
        }


# --- The nightly scrape -------------------------------------------------------


class TestScrapeByAddress:
    def test_same_date_siblings_of_a_recorded_strip_are_each_scraped_and_recorded(self, tmp_path):
        write_saved(tmp_path, 'tinyview_2026-09-25.json', [saved_record('kowal-comics', bella(4))])
        scraper = StubScraper({'kowal-comics': [listed(bella(n)) for n in (5, 4, 3, 2, 1)]})

        results = run_nightly(tmp_path, [KOWAL], scraper)

        assert sorted(scraper.loaded()) == sorted([bella(1), bella(2), bella(3), bella(5)])
        assert all(call['strip_url'] is not None for call in scraper.scrape_calls)
        assert sorted(r['url'] for r in results) == sorted([bella(1), bella(2), bella(3), bella(5)])
        for record in results:
            assert record['date'] == '2026-09-24'
            assert record['image_urls'] == [f'https://cdn.tinyview.com/{strip_folder(record["url"])}/1.jpg']

    def test_a_strip_listed_more_than_once_is_scraped_once(self, tmp_path):
        scraper = StubScraper({'kowal-comics': [
            listed(bella(5)),
            listed(bella(5) + '#comments'),
            listed(bella(5)),
        ]})

        results = run_nightly(tmp_path, [KOWAL], scraper)

        assert scraper.loaded() == [bella(5)]
        assert [r['url'] for r in results] == [bella(5)]

    def test_a_strip_recorded_in_any_saved_file_is_not_scraped(self, tmp_path):
        in_backup = address('kowal-comics', '2025/11/14', 'old-strip')
        write_saved(tmp_path, 'tinyview_2026-09-25.json', [saved_record('kowal-comics', bella(4))])
        write_saved(tmp_path, 'tinyview_2025-11-16_backup.json', [saved_record('kowal-comics', in_backup)])
        scraper = StubScraper({'kowal-comics': [listed(bella(4)), listed(in_backup)]})

        results = run_nightly(tmp_path, [KOWAL], scraper)

        assert scraper.scrape_calls == []
        assert results == []

    def test_an_unrecorded_strip_sixty_days_old_is_scraped_by_its_address(self, tmp_path):
        old = address('kowal-comics', '2026/07/31', 'summer-strip')
        scraper = StubScraper({'kowal-comics': [listed(old)]})

        results = run_nightly(tmp_path, [KOWAL], scraper)

        assert scraper.listing_calls == [('kowal-comics', 90)]
        assert scraper.scrape_calls == [
            {'comic_slug': 'kowal-comics', 'date': '2026/07/31', 'strip_url': old, 'loaded': old}]
        assert [(r['url'], r['date']) for r in results] == [(old, '2026-07-31')]

    def test_the_saved_record_keeps_its_shape_with_the_listed_address(self, tmp_path):
        final = bella(5) + '-redirected'
        scraper = StubScraper({'kowal-comics': [listed(bella(5))]}, reported_urls={bella(5): final})

        results = run_nightly(tmp_path, [KOWAL], scraper)

        panel = 'https://cdn.tinyview.com/kowal-comics/2026/09/24/bella-part-5-of-5/1.jpg'
        assert results == [{
            'name': 'Kowal Comics',
            'slug': 'kowal-comics',
            'date': '2026-09-24',
            'url': bella(5),
            'source': 'tinyview',
            'images': [{'url': panel, 'alt': 'panel', 'title': ''}],
            'image_urls': [panel],
            'image_count': 1,
            'description': 'about kowal-comics/2026/09/24/bella-part-5-of-5',
            'title': 'title of kowal-comics/2026/09/24/bella-part-5-of-5',
        }]

    def test_a_strip_without_a_title_is_titled_by_comic_and_date(self, tmp_path):
        scraper = StubScraper({'kowal-comics': [listed(bella(5))]}, untitled={bella(5)})

        results = run_nightly(tmp_path, [KOWAL], scraper)

        assert results[0]['title'] == 'Kowal Comics - 2026/09/24'

    def test_the_feed_slug_is_saved_while_the_series_path_is_scraped(self, tmp_path):
        strip = address('fowl-language', '2026/09/22', 'bedtime')
        scraper = StubScraper({'fowl-language': [listed(strip)]})

        results = run_nightly(tmp_path, [FOWL], scraper)

        assert scraper.listing_calls == [('fowl-language', 90)]
        assert [(c['comic_slug'], c['strip_url']) for c in scraper.scrape_calls] == [('fowl-language', strip)]
        assert [(r['slug'], r['name'], r['url']) for r in results] == [
            ('fowl-language-tinyview', 'Fowl Language', strip)]

    def test_a_series_with_nothing_listed_records_nothing(self, tmp_path, capsys):
        scraper = StubScraper({})

        results = run_nightly(tmp_path, [KOWAL], scraper)

        assert results == []
        assert scraper.scrape_calls == []
        assert run_total(capsys.readouterr().out) == (0, [])

    def test_the_browser_is_closed_at_the_end(self, tmp_path):
        scraper = StubScraper({'kowal-comics': [listed(bella(5))]})
        recorded = tvl.load_recorded_strips(str(tmp_path))

        with no_browser(scraper) as driver:
            tvl.scrape_all_comics_authenticated([KOWAL], DATE, 90, recorded)

        driver.quit.assert_called_once()


class TestListedButNotRecorded:
    def test_a_strip_whose_page_yields_nothing_is_not_recorded_and_is_counted(self, tmp_path, capsys):
        scraper = StubScraper({'kowal-comics': [listed(bella(5)), listed(bella(4))]}, empty={bella(5)})

        results = run_nightly(tmp_path, [KOWAL], scraper)

        assert [r['url'] for r in results] == [bella(4)]
        assert run_total(capsys.readouterr().out) == (1, [bella(5)])

    def test_a_strip_whose_scrape_raises_is_counted_and_the_rest_still_scraped(self, tmp_path, capsys):
        scraper = StubScraper({'kowal-comics': [listed(bella(5)), listed(bella(4))]}, raising={bella(5)})

        results = run_nightly(tmp_path, [KOWAL], scraper)

        assert [r['url'] for r in results] == [bella(4)]
        assert run_total(capsys.readouterr().out) == (1, [bella(5)])

    def test_the_run_total_names_every_unrecorded_strip_across_series(self, tmp_path, capsys):
        dino = address('adhdinos', '2026/09/27', 'late-panels')
        scraper = StubScraper(
            {'kowal-comics': [listed(bella(5)), listed(bella(4))], 'adhdinos': [listed(dino)]},
            empty={bella(5), dino},
        )

        run_nightly(tmp_path, [KOWAL, ADHDINOS], scraper)

        count, addresses = run_total(capsys.readouterr().out)
        assert count == 2
        assert sorted(addresses) == sorted([bella(5), dino])

    def test_each_series_logs_its_own_unrecorded_strips(self, tmp_path, capsys):
        dino = address('adhdinos', '2026/09/27', 'late-panels')
        scraper = StubScraper(
            {'kowal-comics': [listed(bella(5)), listed(bella(4))], 'adhdinos': [listed(dino)]},
            empty={bella(5), dino},
        )

        run_nightly(tmp_path, [KOWAL, ADHDINOS], scraper)

        output = capsys.readouterr().out
        kowal_section = output[output.index('[1/2]'):output.index('[2/2]')]
        dino_section = output[output.index('[2/2]'):output.index(TOTAL_PREFIX)]
        assert '1 listed strip(s) not recorded' in kowal_section and bella(5) in kowal_section
        assert dino not in kowal_section
        assert '1 listed strip(s) not recorded' in dino_section and dino in dino_section

    def test_recorded_strips_are_not_counted(self, tmp_path, capsys):
        write_saved(tmp_path, 'tinyview_2026-09-25.json', [saved_record('kowal-comics', bella(4))])
        scraper = StubScraper({'kowal-comics': [listed(bella(5)), listed(bella(4))]})

        run_nightly(tmp_path, [KOWAL], scraper)

        assert run_total(capsys.readouterr().out) == (0, [])


# --- Writing the day's file ---------------------------------------------------


def run_main(monkeypatch, output_dir, scraped, comics=(KOWAL,), argv=None):
    """Run main() with the catalog and the authenticated scrape stubbed; return what the scrape got."""
    calls = {}

    def fake_scrape_all(comics, date_str, days_back=15, recorded=None):
        calls.update(comics=comics, date_str=date_str, days_back=days_back, recorded=recorded)
        return [dict(record) for record in scraped]

    if argv is None:
        argv = ['--date', DATE, '--days-back', '90', '--output-dir', str(output_dir)]
    monkeypatch.setattr(sys, 'argv', ['tinyview_scraper_local_authenticated.py', *argv])
    monkeypatch.setattr(tvl, 'load_comics_catalog', lambda: list(comics))
    monkeypatch.setattr(tvl, 'scrape_all_comics_authenticated', fake_scrape_all)
    assert tvl.main() == 0
    return calls


class TestMainWritesTheDaysFile:
    def test_first_run_of_the_day_writes_this_runs_strips(self, tmp_path, monkeypatch):
        run_main(monkeypatch, tmp_path, [saved_record('kowal-comics', bella(5))])

        assert read_saved(tmp_path) == [saved_record('kowal-comics', bella(5))]

    def test_a_rerun_adds_a_new_strip_and_keeps_the_existing_record(self, tmp_path, monkeypatch):
        strip_a = saved_record('kowal-comics', bella(4), title='from the first run')
        write_saved(tmp_path, f'tinyview_{DATE}.json', [strip_a])

        run_main(monkeypatch, tmp_path, [saved_record('kowal-comics', bella(5))])

        saved = read_saved(tmp_path)
        assert [r['url'] for r in saved] == [bella(4), bella(5)]
        assert saved[0] == strip_a

    def test_a_rerun_that_finds_nothing_new_leaves_the_file_as_it_was(self, tmp_path, monkeypatch):
        existing = [saved_record('kowal-comics', bella(4)), saved_record('kowal-comics', bella(5))]
        write_saved(tmp_path, f'tinyview_{DATE}.json', existing)

        run_main(monkeypatch, tmp_path, [])

        assert read_saved(tmp_path) == existing

    def test_the_existing_record_wins_for_the_same_address(self, tmp_path, monkeypatch):
        strip_a = saved_record('kowal-comics', bella(4), title='from the first run')
        write_saved(tmp_path, f'tinyview_{DATE}.json', [strip_a])

        run_main(monkeypatch, tmp_path, [saved_record('kowal-comics', bella(4), title='from the rerun')])

        assert read_saved(tmp_path) == [strip_a]

    def test_other_days_files_are_left_alone(self, tmp_path, monkeypatch):
        yesterday = [saved_record('kowal-comics', bella(3))]
        write_saved(tmp_path, 'tinyview_2026-09-28.json', yesterday)

        run_main(monkeypatch, tmp_path, [saved_record('kowal-comics', bella(5))])

        assert read_saved(tmp_path, 'tinyview_2026-09-28.json') == yesterday
        assert read_saved(tmp_path) == [saved_record('kowal-comics', bella(5))]

    def test_an_unreadable_days_file_is_replaced_by_this_runs_strips(self, tmp_path, monkeypatch, capsys):
        (tmp_path / f'tinyview_{DATE}.json').write_text('{not json')

        run_main(monkeypatch, tmp_path, [saved_record('kowal-comics', bella(5))])

        assert read_saved(tmp_path) == [saved_record('kowal-comics', bella(5))]
        assert f'tinyview_{DATE}.json' in capsys.readouterr().out

    def test_the_scrape_gets_the_addresses_recorded_in_the_output_dir(self, tmp_path, monkeypatch):
        write_saved(tmp_path, 'tinyview_2026-09-25.json', [saved_record('kowal-comics', bella(4))])
        write_saved(tmp_path, 'tinyview_2025-11-16_backup.json', [
            saved_record('kowal-comics', address('kowal-comics', '2025/11/14', 'old-strip'))])

        calls = run_main(monkeypatch, tmp_path, [])

        assert calls['recorded'] == {bella(4), address('kowal-comics', '2025/11/14', 'old-strip')}
        assert calls['date_str'] == DATE
        assert calls['days_back'] == 90

    def test_the_command_line_is_unchanged(self, tmp_path, monkeypatch):
        calls = run_main(monkeypatch, tmp_path, [],
                         argv=['--date', '2026-09-28', '--days-back', '30', '--output-dir', str(tmp_path)])

        assert (calls['date_str'], calls['days_back']) == ('2026-09-28', 30)
        assert (tmp_path / 'tinyview_2026-09-28.json').exists()


class TestSameDayRerunEndToEnd:
    """main() with only the browser replaced: two runs on one day, as Pass 1 and a manual rerun."""

    def run(self, monkeypatch, output_dir, scraper):
        monkeypatch.setattr(sys, 'argv', [
            'tinyview_scraper_local_authenticated.py',
            '--date', DATE, '--days-back', '90', '--output-dir', str(output_dir)])
        monkeypatch.setattr(tvl, 'load_comics_catalog', lambda: [KOWAL])
        with no_browser(scraper):
            assert tvl.main() == 0

    def test_a_sibling_posted_after_the_first_run_is_added_on_the_rerun(self, tmp_path, monkeypatch):
        self.run(monkeypatch, tmp_path, StubScraper({'kowal-comics': [listed(bella(4))]}))
        first = read_saved(tmp_path)
        assert [r['url'] for r in first] == [bella(4)]

        rerun = StubScraper({'kowal-comics': [listed(bella(5)), listed(bella(4))]})
        self.run(monkeypatch, tmp_path, rerun)

        saved = read_saved(tmp_path)
        assert rerun.loaded() == [bella(5)]
        assert [r['url'] for r in saved] == [bella(4), bella(5)]
        assert saved[0] == first[0]

    def test_a_rerun_with_nothing_new_keeps_the_days_strips(self, tmp_path, monkeypatch):
        self.run(monkeypatch, tmp_path, StubScraper({'kowal-comics': [listed(bella(4))]}))
        first = read_saved(tmp_path)

        rerun = StubScraper({'kowal-comics': [listed(bella(4))]})
        self.run(monkeypatch, tmp_path, rerun)

        assert rerun.scrape_calls == []
        assert read_saved(tmp_path) == first


# --- A browser session that dies mid-run (#214) --------------------------------


def adhdinos_strip():
    return address('adhdinos', '2026/09/28', 'naptime')


class TestLostBrowserSession:
    """The run keeps the logged-in browser it started with; if that browser dies, the run stops.

    A replacement browser would be logged out, so every later strip could be saved with
    only its preview panels, for good. Stopping and failing lets the pipeline alert fire.
    """

    def test_the_scraper_borrows_the_logged_in_browser(self, tmp_path):
        scraper = StubScraper({'kowal-comics': [listed(bella(5))]})

        with no_browser(scraper) as driver:
            tvl.scrape_all_comics_authenticated([KOWAL], DATE, 90, set())
            tvl.TinyviewScraper.assert_called_once_with(driver=driver)

    def test_a_lost_session_stops_the_run_and_hands_back_what_was_recorded(self, tmp_path, capsys):
        scraper = StubScraper({
            'adhdinos': [listed(adhdinos_strip())],
            'kowal-comics': [listed(bella(5))],
            'fowl-language': [listed(address('fowl-language', '2026/09/28', 'politician'))],
        }, lost={bella(5)})

        with no_browser(scraper) as driver, pytest.raises(tvl.ScrapeStopped) as stopped:
            tvl.scrape_all_comics_authenticated([ADHDINOS, KOWAL, FOWL], DATE, 90, set())

        assert [record['url'] for record in stopped.value.results] == [adhdinos_strip()]
        assert [slug for slug, _ in scraper.listing_calls] == ['adhdinos', 'kowal-comics']
        assert 'Browser session lost at [2/3] Kowal Comics' in capsys.readouterr().out
        driver.quit.assert_called_once()

    def test_a_session_lost_while_listing_a_series_stops_the_run(self, tmp_path):
        scraper = StubScraper({'adhdinos': [listed(adhdinos_strip())]}, lost_listing={'kowal-comics'})

        with no_browser(scraper), pytest.raises(tvl.ScrapeStopped) as stopped:
            tvl.scrape_all_comics_authenticated([ADHDINOS, KOWAL, FOWL], DATE, 90, set())

        assert [record['url'] for record in stopped.value.results] == [adhdinos_strip()]
        assert [slug for slug, _ in scraper.listing_calls] == ['adhdinos', 'kowal-comics']

    def test_main_saves_what_was_recorded_and_exits_nonzero(self, tmp_path, monkeypatch, capsys):
        earlier = saved_record('kowal-comics', bella(4))
        write_saved(tmp_path, f'tinyview_{DATE}.json', [earlier])
        scraper = StubScraper({
            'adhdinos': [listed(adhdinos_strip())],
            'kowal-comics': [listed(bella(5))],
        }, lost={bella(5)})
        monkeypatch.setattr(sys, 'argv', [
            'tinyview_scraper_local_authenticated.py',
            '--date', DATE, '--days-back', '90', '--output-dir', str(tmp_path)])
        monkeypatch.setattr(tvl, 'load_comics_catalog', lambda: [ADHDINOS, KOWAL])

        with no_browser(scraper):
            assert tvl.main() == 1

        saved = read_saved(tmp_path)
        assert [record['url'] for record in saved] == [bella(4), adhdinos_strip()]
        assert saved[0] == earlier

    def test_a_browser_that_fails_to_close_does_not_cost_the_run(self, tmp_path, capsys):
        scraper = StubScraper({'kowal-comics': [listed(bella(5))]})

        with no_browser(scraper) as driver:
            driver.quit.side_effect = RuntimeError('chrome not reachable')
            results = tvl.scrape_all_comics_authenticated([KOWAL], DATE, 90, set())

        assert [record['url'] for record in results] == [bella(5)]
        assert 'Could not close the browser' in capsys.readouterr().out
