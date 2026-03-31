"""Tests for backfill_gocomics_feeds.py."""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock, call

import pytz
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from scripts.backfill_gocomics_feeds import (
    backfill_comic,
    get_comic_by_slug,
    main,
    MAX_WORKERS,
    BATCH_DELAY,
)


@pytest.fixture
def sample_comic():
    return {
        'name': 'Garfield',
        'slug': 'garfield',
        'url': 'https://www.gocomics.com/garfield',
    }


class TestBackfillComic:
    @patch('scripts.backfill_gocomics_feeds.time.sleep')
    @patch('scripts.backfill_gocomics_feeds.regenerate_feed')
    @patch('scripts.backfill_gocomics_feeds.scrape_comic_enhanced_http')
    def test_successful_backfill(self, mock_scrape, mock_regen, mock_sleep, sample_comic):
        mock_scrape.return_value = {
            'image': 'https://example.com/g.jpg',
            'url': 'https://www.gocomics.com/garfield/2026/03/31',
            'title': 'Garfield',
            'description': 'Comic strip',
        }
        mock_regen.return_value = True

        result = backfill_comic(sample_comic, days=3)

        assert result is True
        assert mock_scrape.call_count == 3
        mock_regen.assert_called_once()
        entries = mock_regen.call_args[0][1]
        assert len(entries) == 3

    @patch('scripts.backfill_gocomics_feeds.time.sleep')
    @patch('scripts.backfill_gocomics_feeds.regenerate_feed')
    @patch('scripts.backfill_gocomics_feeds.scrape_comic_enhanced_http')
    def test_partial_scrape_success(self, mock_scrape, mock_regen, mock_sleep, sample_comic):
        mock_scrape.side_effect = [
            {'image': 'https://example.com/g.jpg', 'url': 'u1', 'title': 't', 'description': 'd'},
            None,
            {'image': 'https://example.com/g2.jpg', 'url': 'u2', 'title': 't', 'description': 'd'},
        ]
        mock_regen.return_value = True

        result = backfill_comic(sample_comic, days=3)

        assert result is True
        entries = mock_regen.call_args[0][1]
        assert len(entries) == 2

    @patch('scripts.backfill_gocomics_feeds.time.sleep')
    @patch('scripts.backfill_gocomics_feeds.scrape_comic_enhanced_http')
    def test_all_scrapes_fail(self, mock_scrape, mock_sleep, sample_comic):
        mock_scrape.return_value = None

        result = backfill_comic(sample_comic, days=3)

        assert result is False

    @patch('scripts.backfill_gocomics_feeds.time.sleep')
    @patch('scripts.backfill_gocomics_feeds.regenerate_feed')
    @patch('scripts.backfill_gocomics_feeds.scrape_comic_enhanced_http')
    def test_pacing_between_batches(self, mock_scrape, mock_regen, mock_sleep, sample_comic):
        mock_scrape.return_value = {
            'image': 'https://example.com/g.jpg',
            'url': 'u',
            'title': 't',
            'description': 'd',
        }
        mock_regen.return_value = True

        # 5 days with MAX_WORKERS=2 means 3 batches, 2 sleeps between them
        backfill_comic(sample_comic, days=5)

        assert mock_sleep.call_count == 2
        mock_sleep.assert_called_with(BATCH_DELAY)


class TestGetComicBySlug:
    @patch('scripts.backfill_gocomics_feeds.load_political_comics_list')
    @patch('scripts.backfill_gocomics_feeds.load_comics_list')
    def test_finds_regular_comic(self, mock_regular, mock_political):
        mock_regular.return_value = [
            {'name': 'Garfield', 'slug': 'garfield'},
        ]
        mock_political.return_value = []

        result = get_comic_by_slug('garfield')
        assert result['name'] == 'Garfield'

    @patch('scripts.backfill_gocomics_feeds.load_political_comics_list')
    @patch('scripts.backfill_gocomics_feeds.load_comics_list')
    def test_finds_political_comic(self, mock_regular, mock_political):
        mock_regular.return_value = []
        mock_political.return_value = [
            {'name': 'Doonesbury', 'slug': 'doonesbury'},
        ]

        result = get_comic_by_slug('doonesbury')
        assert result['name'] == 'Doonesbury'

    @patch('scripts.backfill_gocomics_feeds.load_political_comics_list')
    @patch('scripts.backfill_gocomics_feeds.load_comics_list')
    def test_not_found(self, mock_regular, mock_political):
        mock_regular.return_value = []
        mock_political.return_value = []

        result = get_comic_by_slug('nonexistent')
        assert result is None


class TestMainCli:
    @patch('scripts.backfill_gocomics_feeds.backfill_comic')
    @patch('scripts.backfill_gocomics_feeds.get_comic_by_slug')
    def test_single_comic(self, mock_get, mock_backfill):
        mock_get.return_value = {'name': 'Garfield', 'slug': 'garfield'}
        mock_backfill.return_value = True

        with patch('sys.argv', ['backfill', '--comic', 'garfield', '--days', '5']):
            result = main()

        assert result == 0
        mock_backfill.assert_called_once()
        assert mock_backfill.call_args[0][1] == 5

    @patch('scripts.backfill_gocomics_feeds.get_comic_by_slug')
    def test_comic_not_found(self, mock_get):
        mock_get.return_value = None

        with patch('sys.argv', ['backfill', '--comic', 'nonexistent']):
            result = main()

        assert result == 1

    @patch('scripts.backfill_gocomics_feeds.time.sleep')
    @patch('scripts.backfill_gocomics_feeds.backfill_comic')
    @patch('scripts.backfill_gocomics_feeds.load_political_comics_list')
    @patch('scripts.backfill_gocomics_feeds.load_comics_list')
    def test_all_comics(self, mock_regular, mock_political, mock_backfill, mock_sleep):
        mock_regular.return_value = [
            {'name': 'Garfield', 'slug': 'garfield'},
            {'name': 'Peanuts', 'slug': 'peanuts'},
        ]
        mock_political.return_value = []
        mock_backfill.return_value = True

        with patch('sys.argv', ['backfill', '--all']):
            result = main()

        assert result == 0
        assert mock_backfill.call_count == 2
