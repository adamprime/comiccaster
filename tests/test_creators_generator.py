"""Tests for the Creators feed generator's pure building function."""

import importlib.util
import sys
from datetime import datetime
from pathlib import Path

import pytz


_THIS = Path(__file__).resolve()
_SPEC = importlib.util.spec_from_file_location(
    'generate_creators_feeds',
    _THIS.parent.parent / 'scripts' / 'generate_creators_feeds.py',
)
gen = importlib.util.module_from_spec(_SPEC)
sys.modules['generate_creators_feeds'] = gen
_SPEC.loader.exec_module(gen)


def _comic_info(**overrides):
    base = {
        'name': 'Test Comic',
        'slug': 'test-comic',
        'author': 'Tester',
        'url': 'https://www.creators.com/read/test-comic',
        'source': 'creators',
    }
    base.update(overrides)
    return base


def _release(**overrides):
    base = {
        'release_date': '2026-04-17',
        'full': 'https://image.example/full.jpg',
        'thumb': 'https://image.example/thumb.jpg',
        'formatted_url': 'https://www.creators.com/read/test-comic/04/26/411999',
        'title': 'A Funny Strip',
    }
    base.update(overrides)
    return base


class TestBuildEntriesForComic:
    def test_three_releases_produce_three_sorted_entries(self):
        releases = [
            _release(release_date='2026-04-17', formatted_url='u1'),
            _release(release_date='2026-04-15', formatted_url='u2'),
            _release(release_date='2026-04-16', formatted_url='u3'),
        ]
        entries = gen.build_entries_for_comic(_comic_info(), releases)
        # Sorted ascending by pub_date
        assert [e['url'] for e in entries] == ['u2', 'u3', 'u1']
        assert entries[0]['pub_date'].strftime('%Y-%m-%d') == '2026-04-15'

    def test_missing_release_date_skipped(self):
        releases = [_release(release_date=''), _release(formatted_url='ok')]
        entries = gen.build_entries_for_comic(_comic_info(), releases)
        assert len(entries) == 1

    def test_missing_image_skipped(self):
        releases = [_release(full=None, thumb=None), _release(formatted_url='ok')]
        entries = gen.build_entries_for_comic(_comic_info(), releases)
        assert len(entries) == 1

    def test_missing_formatted_url_skipped(self):
        releases = [_release(formatted_url=''), _release(formatted_url='ok')]
        entries = gen.build_entries_for_comic(_comic_info(), releases)
        assert len(entries) == 1

    def test_full_prefers_over_thumb(self):
        release = _release(full='https://use-me/full.jpg', thumb='https://ignore/thumb.jpg')
        entry = gen.build_entries_for_comic(_comic_info(), [release])[0]
        assert entry['images'][0]['url'] == 'https://use-me/full.jpg'

    def test_falls_back_to_thumb_when_no_full(self):
        release = _release(full=None, thumb='https://thumb.example/x.jpg')
        entry = gen.build_entries_for_comic(_comic_info(), [release])[0]
        assert entry['images'][0]['url'] == 'https://thumb.example/x.jpg'

    def test_title_fallback_uses_comic_name_and_date(self):
        release = _release(title=None)
        entry = gen.build_entries_for_comic(_comic_info(name='My Strip'), [release])[0]
        assert entry['title'] == 'My Strip - 2026-04-17'

    def test_title_preserved_when_provided(self):
        release = _release(title='Deliberate Title')
        entry = gen.build_entries_for_comic(_comic_info(), [release])[0]
        assert entry['title'] == 'Deliberate Title'

    def test_image_alt_is_comic_name(self):
        entry = gen.build_entries_for_comic(_comic_info(name='Alt Check'), [_release()])[0]
        assert entry['images'][0]['alt'] == 'Alt Check'

    def test_image_alt_fallback_when_comic_has_no_name(self):
        # comic_info without name
        info = {'slug': 's', 'source': 'creators'}
        entry = gen.build_entries_for_comic(info, [_release()])[0]
        assert entry['images'][0]['alt'] == 'Comic'

    def test_pub_date_is_utc(self):
        entry = gen.build_entries_for_comic(_comic_info(), [_release()])[0]
        assert entry['pub_date'].tzinfo == pytz.UTC

    def test_invalid_date_skipped(self):
        releases = [_release(release_date='not-a-date'), _release(formatted_url='ok')]
        entries = gen.build_entries_for_comic(_comic_info(), releases)
        assert len(entries) == 1

    def test_limit_applied_to_raw_releases(self):
        """Only MAX_ENTRIES_PER_FEED releases are processed, even if more arrive."""
        many = [_release(formatted_url=f'url-{i}', release_date='2026-04-17') for i in range(50)]
        entries = gen.build_entries_for_comic(_comic_info(), many)
        assert len(entries) == gen.MAX_ENTRIES_PER_FEED

    def test_empty_releases_empty_entries(self):
        assert gen.build_entries_for_comic(_comic_info(), []) == []

    def test_description_includes_date(self):
        entry = gen.build_entries_for_comic(_comic_info(), [_release(release_date='2026-04-17')])[0]
        assert '2026-04-17' in entry['description']

    def test_id_equals_url(self):
        entry = gen.build_entries_for_comic(_comic_info(), [_release(formatted_url='https://x/y')])[0]
        assert entry['id'] == entry['url'] == 'https://x/y'


class TestFindLatestSnapshot:
    def test_returns_latest_date_shaped_file(self, tmp_path):
        (tmp_path / 'creators_2026-04-15.json').write_text('{}')
        (tmp_path / 'creators_2026-04-17.json').write_text('{}')
        (tmp_path / 'creators_2026-04-16.json').write_text('{}')
        latest = gen.find_latest_snapshot(data_dir=tmp_path)
        assert latest.name == 'creators_2026-04-17.json'

    def test_ignores_non_date_shaped_files(self, tmp_path):
        """Regression: pre-existing creators_discovery_report.json must not win."""
        (tmp_path / 'creators_2026-04-17.json').write_text('{}')
        (tmp_path / 'creators_discovery_report.json').write_text('{}')
        (tmp_path / 'creators_something_else.json').write_text('{}')
        latest = gen.find_latest_snapshot(data_dir=tmp_path)
        assert latest.name == 'creators_2026-04-17.json'

    def test_returns_none_when_no_dated_snapshots(self, tmp_path):
        (tmp_path / 'creators_discovery_report.json').write_text('{}')
        assert gen.find_latest_snapshot(data_dir=tmp_path) is None

    def test_returns_none_for_empty_dir(self, tmp_path):
        assert gen.find_latest_snapshot(data_dir=tmp_path) is None
