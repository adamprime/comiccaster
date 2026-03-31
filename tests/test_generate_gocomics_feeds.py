"""Tests for generate_gocomics_feeds.py."""

import json
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytz
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from scripts.generate_gocomics_feeds import (
    load_scraped_data,
    load_comics_catalog,
    generate_feed_for_comic,
    main,
)


@pytest.fixture
def sample_scraped_data(tmp_path):
    """Create sample Phase 1 JSON data files."""
    data_dir = tmp_path / 'data'
    data_dir.mkdir()

    day1 = [
        {
            'name': 'Garfield',
            'slug': 'garfield',
            'image_url': 'https://example.com/garfield-0330.jpg',
            'date': '2026-03-30',
            'url': 'https://www.gocomics.com/garfield/2026/03/30',
            'category': 'comics',
        },
        {
            'name': 'Peanuts',
            'slug': 'peanuts',
            'image_url': 'https://example.com/peanuts-0330.jpg',
            'date': '2026-03-30',
            'url': 'https://www.gocomics.com/peanuts/2026/03/30',
            'category': 'comics',
        },
    ]
    day2 = [
        {
            'name': 'Garfield',
            'slug': 'garfield',
            'image_url': 'https://example.com/garfield-0331.jpg',
            'date': '2026-03-31',
            'url': 'https://www.gocomics.com/garfield/2026/03/31',
            'category': 'comics',
        },
        {
            'name': 'Calvin and Hobbes',
            'slug': 'calvinandhobbes',
            'image_url': 'https://example.com/ch-0331.jpg',
            'date': '2026-03-31',
            'url': 'https://www.gocomics.com/calvinandhobbes/2026/03/31',
            'category': 'comics',
        },
    ]

    (data_dir / 'comics_2026-03-30.json').write_text(json.dumps(day1))
    (data_dir / 'comics_2026-03-31.json').write_text(json.dumps(day2))
    return data_dir


@pytest.fixture
def sample_catalog(tmp_path):
    """Create sample comics catalog files."""
    catalog = [
        {'name': 'Garfield', 'slug': 'garfield', 'url': 'https://www.gocomics.com/garfield'},
        {'name': 'Peanuts', 'slug': 'peanuts', 'url': 'https://www.gocomics.com/peanuts'},
        {'name': 'Calvin and Hobbes', 'slug': 'calvinandhobbes', 'url': 'https://www.gocomics.com/calvinandhobbes'},
        {'name': 'Zits', 'slug': 'zits', 'url': 'https://www.gocomics.com/zits'},
    ]
    catalog_file = tmp_path / 'comics_list.json'
    catalog_file.write_text(json.dumps(catalog))
    return catalog_file


class TestLoadScrapedData:
    def test_loads_multiple_days(self, sample_scraped_data, monkeypatch):
        monkeypatch.chdir(sample_scraped_data.parent)
        result = load_scraped_data(days_back=10)

        assert 'garfield' in result
        assert 'peanuts' in result
        assert 'calvinandhobbes' in result
        assert len(result['garfield']) == 2  # Appears in both days

    def test_groups_by_slug(self, sample_scraped_data, monkeypatch):
        monkeypatch.chdir(sample_scraped_data.parent)
        result = load_scraped_data(days_back=10)

        assert len(result['peanuts']) == 1  # Only in day1
        assert len(result['calvinandhobbes']) == 1  # Only in day2

    def test_no_data_files(self, tmp_path, monkeypatch):
        (tmp_path / 'data').mkdir()
        monkeypatch.chdir(tmp_path)
        result = load_scraped_data()
        assert result == {}

    def test_respects_days_back(self, sample_scraped_data, monkeypatch):
        monkeypatch.chdir(sample_scraped_data.parent)
        result = load_scraped_data(days_back=1)
        # Only the most recent file (2026-03-31) should be loaded
        assert 'garfield' in result
        assert 'calvinandhobbes' in result
        # Peanuts only in 2026-03-30 which is excluded
        assert 'peanuts' not in result

    def test_handles_corrupt_file(self, sample_scraped_data, monkeypatch):
        monkeypatch.chdir(sample_scraped_data.parent)
        (sample_scraped_data / 'comics_2026-03-29.json').write_text('not json')
        result = load_scraped_data(days_back=10)
        # Should still load valid files
        assert 'garfield' in result

    def test_deduplicates_by_slug_and_date(self, tmp_path, monkeypatch):
        """Duplicate slug+date entries (e.g. Spanish/English overlap) are
        deduplicated at load time, keeping only the first occurrence."""
        data_dir = tmp_path / 'data'
        data_dir.mkdir()
        monkeypatch.chdir(tmp_path)

        day_data = [
            {
                'name': 'Garfield',
                'slug': 'garfield',
                'image_url': 'https://example.com/garfield-english.jpg',
                'date': '2026-03-31',
                'url': 'https://www.gocomics.com/garfield/2026/03/31',
            },
            {
                'name': 'Garfield',
                'slug': 'garfield',
                'image_url': 'https://example.com/garfield-spanish.jpg',
                'date': '2026-03-31',
                'url': 'https://www.gocomics.com/garfield/2026/03/31',
            },
        ]
        (data_dir / 'comics_2026-03-31.json').write_text(json.dumps(day_data))

        result = load_scraped_data(days_back=10)

        assert len(result['garfield']) == 1
        assert result['garfield'][0]['image_url'] == 'https://example.com/garfield-english.jpg'

    def test_dedup_allows_same_slug_different_dates(self, tmp_path, monkeypatch):
        """Same slug on different dates should NOT be deduplicated."""
        data_dir = tmp_path / 'data'
        data_dir.mkdir()
        monkeypatch.chdir(tmp_path)

        day1 = [
            {
                'slug': 'garfield',
                'image_url': 'https://example.com/g-0330.jpg',
                'date': '2026-03-30',
                'url': 'https://www.gocomics.com/garfield/2026/03/30',
            },
        ]
        day2 = [
            {
                'slug': 'garfield',
                'image_url': 'https://example.com/g-0331.jpg',
                'date': '2026-03-31',
                'url': 'https://www.gocomics.com/garfield/2026/03/31',
            },
        ]
        (data_dir / 'comics_2026-03-30.json').write_text(json.dumps(day1))
        (data_dir / 'comics_2026-03-31.json').write_text(json.dumps(day2))

        result = load_scraped_data(days_back=10)

        assert len(result['garfield']) == 2


class TestGenerateFeedForComic:
    def test_generates_feed(self):
        comic_info = {'name': 'Garfield', 'slug': 'garfield', 'url': 'https://www.gocomics.com/garfield'}
        scraped_data = {
            'garfield': [
                {
                    'name': 'Garfield',
                    'slug': 'garfield',
                    'image_url': 'https://example.com/garfield.jpg',
                    'date': '2026-03-31',
                    'url': 'https://www.gocomics.com/garfield/2026/03/31',
                },
            ],
        }
        generator = MagicMock()
        generator.generate_feed.return_value = True

        result = generate_feed_for_comic(comic_info, scraped_data, generator)

        assert result is True
        generator.generate_feed.assert_called_once()
        call_args = generator.generate_feed.call_args
        entries = call_args[0][1]
        assert len(entries) == 1
        assert entries[0]['title'] == 'Garfield - 2026-03-31'
        assert entries[0]['images'] == [{'url': 'https://example.com/garfield.jpg', 'alt': 'Garfield'}]

    def test_returns_false_when_no_data(self):
        comic_info = {'name': 'Zits', 'slug': 'zits', 'url': 'https://www.gocomics.com/zits'}
        scraped_data = {}
        generator = MagicMock()

        result = generate_feed_for_comic(comic_info, scraped_data, generator)

        assert result is False
        generator.generate_feed.assert_not_called()

    def test_deduplicates_by_url(self):
        comic_info = {'name': 'Garfield', 'slug': 'garfield', 'url': 'https://www.gocomics.com/garfield'}
        scraped_data = {
            'garfield': [
                {
                    'slug': 'garfield',
                    'image_url': 'https://example.com/garfield.jpg',
                    'date': '2026-03-31',
                    'url': 'https://www.gocomics.com/garfield/2026/03/31',
                },
                {
                    'slug': 'garfield',
                    'image_url': 'https://example.com/garfield-dupe.jpg',
                    'date': '2026-03-31',
                    'url': 'https://www.gocomics.com/garfield/2026/03/31',  # Same URL
                },
            ],
        }
        generator = MagicMock()
        generator.generate_feed.return_value = True

        generate_feed_for_comic(comic_info, scraped_data, generator)

        entries = generator.generate_feed.call_args[0][1]
        assert len(entries) == 1

    def test_multiple_days_sorted_oldest_first(self):
        comic_info = {'name': 'Garfield', 'slug': 'garfield', 'url': 'https://www.gocomics.com/garfield'}
        scraped_data = {
            'garfield': [
                {
                    'slug': 'garfield',
                    'image_url': 'https://example.com/g2.jpg',
                    'date': '2026-03-31',
                    'url': 'https://www.gocomics.com/garfield/2026/03/31',
                },
                {
                    'slug': 'garfield',
                    'image_url': 'https://example.com/g1.jpg',
                    'date': '2026-03-30',
                    'url': 'https://www.gocomics.com/garfield/2026/03/30',
                },
            ],
        }
        generator = MagicMock()
        generator.generate_feed.return_value = True

        generate_feed_for_comic(comic_info, scraped_data, generator)

        entries = generator.generate_feed.call_args[0][1]
        assert entries[0]['pub_date'] < entries[1]['pub_date']

    def test_skips_entries_missing_image(self):
        comic_info = {'name': 'Garfield', 'slug': 'garfield', 'url': 'https://www.gocomics.com/garfield'}
        scraped_data = {
            'garfield': [
                {
                    'slug': 'garfield',
                    'image_url': '',
                    'date': '2026-03-31',
                    'url': 'https://www.gocomics.com/garfield/2026/03/31',
                },
            ],
        }
        generator = MagicMock()

        result = generate_feed_for_comic(comic_info, scraped_data, generator)

        assert result is False
        generator.generate_feed.assert_not_called()

    def test_handles_generator_exception(self):
        comic_info = {'name': 'Garfield', 'slug': 'garfield', 'url': 'https://www.gocomics.com/garfield'}
        scraped_data = {
            'garfield': [
                {
                    'slug': 'garfield',
                    'image_url': 'https://example.com/g.jpg',
                    'date': '2026-03-31',
                    'url': 'https://www.gocomics.com/garfield/2026/03/31',
                },
            ],
        }
        generator = MagicMock()
        generator.generate_feed.side_effect = Exception("write error")

        result = generate_feed_for_comic(comic_info, scraped_data, generator)

        assert result is False


class TestMain:
    @patch('scripts.generate_gocomics_feeds.ComicFeedGenerator')
    @patch('scripts.generate_gocomics_feeds.load_comics_catalog')
    @patch('scripts.generate_gocomics_feeds.load_scraped_data')
    def test_main_success(self, mock_load_data, mock_load_catalog, mock_generator_cls):
        mock_load_data.return_value = {
            'garfield': [
                {
                    'slug': 'garfield',
                    'image_url': 'https://example.com/g.jpg',
                    'date': '2026-03-31',
                    'url': 'https://www.gocomics.com/garfield/2026/03/31',
                },
            ],
        }
        mock_load_catalog.return_value = [
            {'name': 'Garfield', 'slug': 'garfield', 'url': 'https://www.gocomics.com/garfield'},
            {'name': 'Peanuts', 'slug': 'peanuts', 'url': 'https://www.gocomics.com/peanuts'},
        ]
        mock_generator_cls.return_value.generate_feed.return_value = True

        result = main()

        assert result == 0

    @patch('scripts.generate_gocomics_feeds.load_scraped_data')
    def test_main_no_data(self, mock_load_data):
        mock_load_data.return_value = {}

        result = main()

        assert result == 1

    @patch('scripts.generate_gocomics_feeds.load_comics_catalog')
    @patch('scripts.generate_gocomics_feeds.load_scraped_data')
    def test_main_no_catalog(self, mock_load_data, mock_load_catalog):
        mock_load_data.return_value = {'garfield': []}
        mock_load_catalog.return_value = []

        result = main()

        assert result == 1
