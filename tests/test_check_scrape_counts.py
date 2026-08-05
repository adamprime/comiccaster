"""Tests for check_scrape_counts.py.

The invariant guard in local_master_update.sh only asked whether a scrape's
JSON file *exists*. On 2026-08-03 TinyView scraped nothing, wrote `[]`, and the
run reported ALL SUCCESS -- a real silent failure that nobody was told about.
These tests cover the count assertion that closes that gap.

Fixtures are written to tmp_path rather than mocked, so the real filename
parsing and JSON loading are exercised.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from scripts.check_scrape_counts import (
    SOURCE_RULES,
    count_entries,
    derive_source_key,
    evaluate,
    main,
)


def write(tmp_path, name, payload):
    p = tmp_path / name
    p.write_text(json.dumps(payload))
    return p


class TestDeriveSourceKey:
    @pytest.mark.parametrize('filename,expected', [
        ('comics_2026-08-05.json', 'comics'),
        ('comicskingdom_2026-08-05.json', 'comicskingdom'),
        ('farside_daily_2026-08-05.json', 'farside_daily'),
        ('farside_new_2026-08-05.json', 'farside_new'),
        ('/abs/path/data/tinyview_2026-08-05.json', 'tinyview'),
    ])
    def test_strips_the_date_suffix(self, filename, expected):
        assert derive_source_key(filename) == expected

    def test_unrecognised_shape_returns_none(self):
        assert derive_source_key('notes.json') is None


class TestCountEntries:
    def test_top_level_list(self):
        assert count_entries([1, 2, 3], None) == 3

    def test_nested_payload_key(self):
        assert count_entries({'cartoons': [1, 2]}, 'cartoons') == 2

    def test_missing_payload_key_counts_zero(self):
        """A shape change must read as zero, not crash and not pass."""
        assert count_entries({'scraped_at': 'x'}, 'comics') == 0

    def test_empty_list(self):
        assert count_entries([], None) == 0


class TestEvaluate:
    def test_healthy_count_passes(self):
        ok, detail = evaluate('comicskingdom', 153)
        assert ok
        assert '153' in detail

    def test_empty_scrape_fails(self):
        """The 2026-08-03 TinyView case: wrote `[]`, reported ALL SUCCESS."""
        ok, detail = evaluate('tinyview', 0)
        assert not ok
        assert '0' in detail

    def test_partial_scrape_fails_for_a_fixed_catalog(self):
        """CK's catalog is 153 every day; 12 means the scrape broke midway."""
        ok, _ = evaluate('comicskingdom', 12)
        assert not ok

    def test_normal_variation_passes(self):
        """TinyView legitimately ranges 1-7 depending on what publishers post."""
        for n in (1, 3, 7):
            ok, _ = evaluate('tinyview', n)
            assert ok, f'{n} should pass'

    def test_gocomics_observed_range_passes(self):
        for n in (210, 282):
            ok, _ = evaluate('comics', n)
            assert ok, f'{n} should pass'

    def test_farside_new_is_exempt_and_says_why(self):
        """Known broken upstream (bot protection); the decision was to keep the
        feed rather than alert daily. Must not become recurring noise."""
        ok, detail = evaluate('farside_new', 0)
        assert ok
        assert 'known' in detail.lower()

    def test_unknown_source_does_not_block_the_run(self):
        """Adding a source shouldn't fail the pipeline before it's registered --
        but it must say so rather than pass silently."""
        ok, detail = evaluate('brand_new_source', 0)
        assert ok
        assert 'not registered' in detail.lower()

    def test_every_registered_source_demands_at_least_one_entry(self):
        """Except the documented exemption -- the whole point of the check."""
        for key, rule in SOURCE_RULES.items():
            if key == 'farside_new':
                continue
            assert rule['minimum'] >= 1, f'{key} would accept an empty scrape'


class TestMain:
    def test_exit_zero_on_healthy_file(self, tmp_path, capsys):
        f = write(tmp_path, 'comicskingdom_2026-08-05.json', [{}] * 153)
        assert main([str(f)]) == 0
        assert '✅' in capsys.readouterr().out

    def test_exit_one_on_empty_file(self, tmp_path, capsys):
        f = write(tmp_path, 'tinyview_2026-08-03.json', [])
        assert main([str(f)]) == 1
        assert '❌' in capsys.readouterr().out

    def test_exit_one_on_nested_empty_payload(self, tmp_path):
        f = write(tmp_path, 'newyorker_2026-08-05.json',
                  {'scraped_at': 'x', 'cartoons': []})
        assert main([str(f)]) == 1

    def test_nested_healthy_payload_passes(self, tmp_path):
        f = write(tmp_path, 'newyorker_2026-08-05.json',
                  {'scraped_at': 'x', 'cartoons': [{}] * 10})
        assert main([str(f)]) == 0

    def test_missing_file_fails(self, tmp_path):
        assert main([str(tmp_path / 'comics_2026-08-05.json')]) == 1

    def test_malformed_json_fails(self, tmp_path):
        p = tmp_path / 'comics_2026-08-05.json'
        p.write_text('{not json')
        assert main([str(p)]) == 1

    def test_farside_new_empty_still_exits_zero(self, tmp_path):
        f = write(tmp_path, 'farside_new_2026-08-05.json',
                  {'scraped_at': 'x', 'comics': []})
        assert main([str(f)]) == 0
