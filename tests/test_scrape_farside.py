"""Tests for scripts/scrape_farside.py's command line.

The scraper factory is replaced with a fake, so these tests never hit
thefarside.com. The script writes to a relative data/ directory, so each test
runs inside its own tmp_path.
"""

import importlib.util
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import pytz


_THIS = Path(__file__).resolve()
_SPEC = importlib.util.spec_from_file_location(
    'scrape_farside',
    _THIS.parent.parent / 'scripts' / 'scrape_farside.py',
)
scrape_farside = importlib.util.module_from_spec(_SPEC)
sys.modules['scrape_farside'] = scrape_farside
_SPEC.loader.exec_module(scrape_farside)


def dose(first_id):
    return [{'id': str(first_id + n), 'url': f'https://example.test/{first_id + n}'}
            for n in range(5)]


class FakeFarside:
    """Stands in for both farside-daily and farside-new scrapers."""

    def __init__(self, published=None):
        # {'YYYY/MM/DD': [comics]}; any other date is unpublished (None).
        self.published = published or {}
        self.daily_calls = []
        self.new_stuff_calls = 0

    def scrape_daily_dose(self, date_slash):
        self.daily_calls.append(date_slash)
        comics = self.published.get(date_slash)
        return {'comics': comics} if comics else None

    def scrape_new_stuff(self):
        self.new_stuff_calls += 1
        return {'comics': [{'id': '501', 'url': 'https://example.test/new/501'}]}

    def scrape_new_stuff_detail(self, url):
        return {'id': url.rsplit('/', 1)[-1], 'url': url}


@pytest.fixture
def fake(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'data').mkdir()
    scraper = FakeFarside()
    monkeypatch.setattr(scrape_farside.ScraperFactory, 'get_scraper',
                        staticmethod(lambda source: scraper))
    return scraper


def daily_files(tmp_path):
    return sorted(p.name for p in (tmp_path / 'data').glob('farside_daily_*.json'))


def new_stuff_files(tmp_path):
    return sorted(p.name for p in (tmp_path / 'data').glob('farside_new_*.json'))


def three_day_window_slashes():
    today = datetime.now(pytz.timezone('US/Eastern')).date()
    return [(today - timedelta(days=n)).strftime('%Y/%m/%d') for n in (2, 1, 0)]


class TestDailyOnlyWithDate:
    def test_published_date_is_written_and_exits_zero(self, fake, tmp_path):
        fake.published = {'2026/10/03': dose(22810)}

        code = scrape_farside.main(['--daily-only', '--date', '2026-10-03'])

        assert code == 0
        assert fake.daily_calls == ['2026/10/03']
        assert daily_files(tmp_path) == ['farside_daily_2026-10-03.json']
        saved = json.loads((tmp_path / 'data' / 'farside_daily_2026-10-03.json').read_text())
        assert saved['target_date'] == '2026-10-03'
        assert [c['id'] for c in saved['comics']] == ['22810', '22811', '22812', '22813', '22814']

    def test_unpublished_date_writes_nothing_and_exits_one(self, fake, tmp_path):
        existing = tmp_path / 'data' / 'farside_daily_2026-10-02.json'
        existing.write_text('{"target_date": "2026-10-02", "comics": ["kept"]}')

        code = scrape_farside.main(['--daily-only', '--date', '2026-10-03'])

        assert code == 1
        assert fake.daily_calls == ['2026/10/03']
        assert daily_files(tmp_path) == ['farside_daily_2026-10-02.json']
        assert existing.read_text() == '{"target_date": "2026-10-02", "comics": ["kept"]}'

    def test_never_touches_new_stuff(self, fake, tmp_path):
        fake.published = {'2026/10/03': dose(22810)}
        cursor = tmp_path / 'data' / 'farside_new_last_id.txt'
        cursor.write_text('400')

        scrape_farside.main(['--daily-only', '--date', '2026-10-03'])

        assert fake.new_stuff_calls == 0
        assert cursor.read_text() == '400'
        assert new_stuff_files(tmp_path) == []


class TestDailyOnlyWithoutDate:
    def test_scrapes_the_three_day_window_and_nothing_else(self, fake, tmp_path):
        window = three_day_window_slashes()
        fake.published = {d: dose(100 + i * 5) for i, d in enumerate(window)}

        code = scrape_farside.main(['--daily-only'])

        assert code == 0
        assert fake.daily_calls == window
        assert fake.new_stuff_calls == 0
        assert len(daily_files(tmp_path)) == 3
        assert new_stuff_files(tmp_path) == []
        assert not (tmp_path / 'data' / 'farside_new_last_id.txt').exists()


class TestNewStuffOnly:
    def test_runs_new_stuff_and_writes_no_daily_files(self, fake, tmp_path):
        code = scrape_farside.main(['--new-stuff-only'])

        assert code == 0
        assert fake.new_stuff_calls == 1
        assert fake.daily_calls == []
        assert daily_files(tmp_path) == []
        assert len(new_stuff_files(tmp_path)) == 1
        assert (tmp_path / 'data' / 'farside_new_last_id.txt').read_text() == '501'


class TestNoArguments:
    def test_runs_the_three_day_window_and_new_stuff(self, fake, tmp_path):
        window = three_day_window_slashes()
        fake.published = {d: dose(100 + i * 5) for i, d in enumerate(window)}

        code = scrape_farside.main([])

        assert code == 0
        assert fake.daily_calls == window
        assert fake.new_stuff_calls == 1
        assert len(daily_files(tmp_path)) == 3
        assert len(new_stuff_files(tmp_path)) == 1


class TestUsageErrors:
    @pytest.mark.parametrize('argv', [
        ['--daily-only', '--new-stuff-only'],
        ['--date', '2026-10-03'],
        ['--new-stuff-only', '--date', '2026-10-03'],
    ])
    def test_invalid_combinations_are_rejected(self, fake, argv):
        with pytest.raises(SystemExit) as exc:
            scrape_farside.main(argv)
        assert exc.value.code == 2
        assert fake.daily_calls == []
        assert fake.new_stuff_calls == 0
