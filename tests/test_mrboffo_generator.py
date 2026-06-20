"""Tests for the Mr. Boffo feed generator's pure building functions."""

import importlib.util
import sys
from datetime import datetime
from pathlib import Path

import pytz


_THIS = Path(__file__).resolve()
_SPEC = importlib.util.spec_from_file_location(
    'generate_mrboffo_feeds',
    _THIS.parent.parent / 'scripts' / 'generate_mrboffo_feeds.py',
)
gen = importlib.util.module_from_spec(_SPEC)
sys.modules['generate_mrboffo_feeds'] = gen
_SPEC.loader.exec_module(gen)


def _comic(**overrides):
    base = {
        'image_url': 'http://www.mrboffo.com/images/daily/2026/today.jpg',
        'title': 'Mr. Boffo',
        'url': 'http://www.mrboffo.com/daily.html',
    }
    base.update(overrides)
    return base


class TestBuildEntries:
    def test_single_snapshot_produces_one_entry(self):
        entries = gen.build_entries([('2026-06-20', [_comic()])])
        assert len(entries) == 1
        e = entries[0]
        assert e['title'] == 'Mr. Boffo - 2026-06-20'
        assert '2026-06-20' in e['description']
        assert e['id'] == 'mrboffo-2026-06-20'

    def test_image_url_has_date_cache_buster(self):
        """The fixed image path gets a date query so readers fetch fresh bytes."""
        entries = gen.build_entries([('2026-06-20', [_comic()])])
        assert entries[0]['image_url'] == (
            'http://www.mrboffo.com/images/daily/2026/today.jpg?d=2026-06-20'
        )

    def test_feed_window_is_one(self):
        """Source has no archive; the feed only ever holds the current strip."""
        assert gen.FEED_WINDOW == 1

    def test_pub_date_is_noon_eastern(self):
        entry = gen.build_entries([('2026-06-20', [_comic()])])[0]
        pub = entry['pub_date']
        assert pub.hour == 12
        # Eastern timezone-aware
        assert pub.tzinfo is not None

    def test_multi_day_window_distinct_monotonic_pub_dates(self):
        snapshots = [
            ('2026-06-18', [_comic()]),
            ('2026-06-19', [_comic()]),
            ('2026-06-20', [_comic()]),
        ]
        entries = gen.build_entries(snapshots)
        assert len(entries) == 3
        pub_dates = [e['pub_date'] for e in entries]
        # Strictly increasing -> no feed-dedup collisions.
        assert pub_dates == sorted(pub_dates)
        assert len(set(pub_dates)) == 3

    def test_comic_missing_image_is_skipped(self):
        snapshots = [
            ('2026-06-19', [_comic(image_url=None)]),
            ('2026-06-20', [_comic()]),
        ]
        entries = gen.build_entries(snapshots)
        assert len(entries) == 1
        assert entries[0]['title'] == 'Mr. Boffo - 2026-06-20'

    def test_invalid_target_date_falls_back_to_now(self):
        entries = gen.build_entries([('not-a-date', [_comic()])])
        assert len(entries) == 1
        # Did not raise; produced a timezone-aware pub_date.
        assert entries[0]['pub_date'].tzinfo is not None

    def test_empty_snapshots_empty_entries(self):
        assert gen.build_entries([]) == []


class TestFindSnapshots:
    def test_returns_latest_date_shaped_file(self, tmp_path):
        (tmp_path / 'mrboffo_2026-06-18.json').write_text('{}')
        (tmp_path / 'mrboffo_2026-06-20.json').write_text('{}')
        (tmp_path / 'mrboffo_2026-06-19.json').write_text('{}')
        latest = gen.find_latest_snapshot(data_dir=tmp_path)
        assert latest.name == 'mrboffo_2026-06-20.json'

    def test_ignores_non_date_shaped_files(self, tmp_path):
        (tmp_path / 'mrboffo_2026-06-20.json').write_text('{}')
        (tmp_path / 'mrboffo_notes.json').write_text('{}')
        latest = gen.find_latest_snapshot(data_dir=tmp_path)
        assert latest.name == 'mrboffo_2026-06-20.json'

    def test_window_returns_oldest_first(self, tmp_path):
        for day in ('17', '18', '19', '20'):
            (tmp_path / f'mrboffo_2026-06-{day}.json').write_text('{}')
        snaps = gen.find_snapshots(data_dir=tmp_path, window=2)
        assert [p.name for p in snaps] == [
            'mrboffo_2026-06-19.json',
            'mrboffo_2026-06-20.json',
        ]

    def test_returns_none_when_no_dated_snapshots(self, tmp_path):
        (tmp_path / 'mrboffo_notes.json').write_text('{}')
        assert gen.find_latest_snapshot(data_dir=tmp_path) is None

    def test_returns_none_for_empty_dir(self, tmp_path):
        assert gen.find_latest_snapshot(data_dir=tmp_path) is None


class TestLoadSnapshot:
    def test_reads_target_date_and_comics(self, tmp_path):
        import json
        path = tmp_path / 'mrboffo_2026-06-20.json'
        path.write_text(json.dumps({
            'target_date': '2026-06-20',
            'scraped_at': '2026-06-20T08:00:00+00:00',
            'comics': [_comic()],
        }))
        target_date, comics = gen.load_snapshot(path)
        assert target_date == '2026-06-20'
        assert len(comics) == 1

    def test_falls_back_to_filename_date_when_target_date_missing(self, tmp_path):
        import json
        path = tmp_path / 'mrboffo_2026-06-20.json'
        path.write_text(json.dumps({'comics': [_comic()]}))
        target_date, comics = gen.load_snapshot(path)
        assert target_date == '2026-06-20'
