"""Tests for the Far Side feed generator's pure building functions.

These exercise the refactor's deterministic piece — given known scrape data,
the generator should produce the same entry list regardless of when it runs.
"""

import importlib.util
import sys
from datetime import datetime
from pathlib import Path

import pytest
import pytz


# Load scripts/generate_farside_feeds.py as a module without polluting the
# scripts/ directory with a package marker.
_THIS = Path(__file__).resolve()
_SPEC = importlib.util.spec_from_file_location(
    'generate_farside_feeds',
    _THIS.parent.parent / 'scripts' / 'generate_farside_feeds.py',
)
gen = importlib.util.module_from_spec(_SPEC)
sys.modules['generate_farside_feeds'] = gen
_SPEC.loader.exec_module(gen)


def _fake_comic(idx, with_caption=True):
    return {
        'id': f'comic-{idx}',
        'url': f'https://www.thefarside.com/2026/04/17/{idx}',
        'image_url': f'https://img.example/{idx}.jpg',
        'original_image_url': f'https://img.example/orig-{idx}.jpg',
        'caption': f'caption {idx}' if with_caption else '',
        'title': f'title {idx}',
    }


class TestBuildDailyEntries:
    def test_fifteen_entries_across_three_days(self):
        """3 days × 5 comics → 15 entries with correct #N and pub times."""
        snapshots = [
            ('2026-04-15', [_fake_comic(i) for i in range(5)]),
            ('2026-04-16', [_fake_comic(5 + i) for i in range(5)]),
            ('2026-04-17', [_fake_comic(10 + i) for i in range(5)]),
        ]
        entries = gen.build_daily_entries(snapshots)
        assert len(entries) == 15
        # Titles: #1..#5 within each day
        expected_titles = [
            f"The Far Side - {d} #{n}"
            for d in ('2026-04-15', '2026-04-16', '2026-04-17')
            for n in (1, 2, 3, 4, 5)
        ]
        assert [e['title'] for e in entries] == expected_titles
        # Pub times: minute increments globally 0..14, hour=8, each day's
        # own target_date (Eastern).
        for i, e in enumerate(entries):
            parsed = datetime.strptime(e['pub_date'], '%a, %d %b %Y %H:%M:%S %z')
            assert parsed.hour == 8
            assert parsed.minute == i
            # Day index 0 == 04-15, 1 == 04-16, 2 == 04-17
            day_index = i // 5
            expected_day = ('15', '16', '17')[day_index]
            assert parsed.strftime('%Y-%m-%d') == f'2026-04-{expected_day}'

    def test_single_day_five_entries(self):
        snapshots = [('2026-04-17', [_fake_comic(i) for i in range(5)])]
        entries = gen.build_daily_entries(snapshots)
        assert len(entries) == 5
        assert entries[0]['title'] == 'The Far Side - 2026-04-17 #1'
        assert entries[4]['title'] == 'The Far Side - 2026-04-17 #5'

    def test_empty_snapshots_empty_result(self):
        assert gen.build_daily_entries([]) == []

    def test_skips_comic_without_image_url_but_keeps_counter(self):
        """Missing image_url → entry dropped, but global `i` still advances.
        Preserves original behavior where index drives pub_time minutes."""
        good1 = _fake_comic(1)
        bad = {**_fake_comic(2), 'image_url': ''}
        good2 = _fake_comic(3)
        snapshots = [('2026-04-17', [good1, bad, good2])]
        entries = gen.build_daily_entries(snapshots)
        assert len(entries) == 2
        # Second entry should have minute=2, not 1 (the skipped counter position)
        parsed = datetime.strptime(entries[1]['pub_date'], '%a, %d %b %Y %H:%M:%S %z')
        assert parsed.minute == 2

    def test_caption_renders_in_description(self):
        snapshots = [('2026-04-17', [_fake_comic(1, with_caption=True)])]
        e = gen.build_daily_entries(snapshots)[0]
        assert 'caption 1' in e['description']
        assert '<img src="https://img.example/1.jpg"' in e['description']
        assert 'Visit The Far Side' in e['description']

    def test_no_caption_omits_caption_block(self):
        snapshots = [('2026-04-17', [_fake_comic(1, with_caption=False)])]
        e = gen.build_daily_entries(snapshots)[0]
        # The italic-styled caption <p> should not be present
        assert 'font-style: italic;' not in e['description']

    def test_bad_target_date_skips_snapshot(self):
        snapshots = [
            ('not-a-date', [_fake_comic(1)]),
            ('2026-04-17', [_fake_comic(2)]),
        ]
        entries = gen.build_daily_entries(snapshots)
        assert len(entries) == 1
        assert entries[0]['title'] == 'The Far Side - 2026-04-17 #1'


class TestBuildNewStuffEntries:
    def test_three_comics_step_one_day_apart(self):
        eastern = pytz.timezone('US/Eastern')
        scraped_at = eastern.localize(datetime(2026, 4, 17, 12, 0, 0))
        comics = [_fake_comic(i) for i in range(3)]
        entries = gen.build_new_stuff_entries(scraped_at, comics)
        assert len(entries) == 3
        assert entries[0]['title'] == 'The Far Side - New Stuff: title 0'
        # pub_dates: scraped_at, -1d, -2d
        dates = [
            datetime.strptime(e['pub_date'], '%a, %d %b %Y %H:%M:%S %z').date()
            for e in entries
        ]
        assert dates[0].isoformat() == '2026-04-17'
        assert dates[1].isoformat() == '2026-04-16'
        assert dates[2].isoformat() == '2026-04-15'

    def test_empty_comics_empty_entries(self):
        eastern = pytz.timezone('US/Eastern')
        scraped_at = eastern.localize(datetime(2026, 4, 17, 12, 0, 0))
        assert gen.build_new_stuff_entries(scraped_at, []) == []

    def test_missing_image_url_dropped(self):
        eastern = pytz.timezone('US/Eastern')
        scraped_at = eastern.localize(datetime(2026, 4, 17, 12, 0, 0))
        comics = [{**_fake_comic(1), 'image_url': ''}, _fake_comic(2)]
        entries = gen.build_new_stuff_entries(scraped_at, comics)
        assert len(entries) == 1
        assert 'title 2' in entries[0]['title']

    def test_description_includes_new_stuff_link(self):
        eastern = pytz.timezone('US/Eastern')
        scraped_at = eastern.localize(datetime(2026, 4, 17, 12, 0, 0))
        entries = gen.build_new_stuff_entries(scraped_at, [_fake_comic(1)])
        assert 'thefarside.com/new-stuff' in entries[0]['description']
        assert 'See all new work' in entries[0]['description']
