"""Tests for authenticated_scraper_secure.py extraction logic."""

import json
import pytest
from unittest.mock import MagicMock, patch
from bs4 import BeautifulSoup

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from scripts.authenticated_scraper_secure import (
    extract_comics_from_page,
    _extract_comic_slug_from_link,
    _get_image_src,
    _get_badge_name,
    merge_with_existing,
)


def _make_comic_container(slug, badge_name, image_asset_id, include_strip=True,
                          relative_links=False):
    """Build a minimal comic container matching the profile page structure."""
    badge_url = (
        f"https://gocomicscmsassets.gocomics.com/staging-assets/assets/"
        f"Global_Feature_Badge_{badge_name.replace(' ', '_')}_600_abc123.png"
    )
    strip_url = (
        f"https://featureassets.gocomics.com/assets/{image_asset_id}"
        f"?optimizer=image&width=2800&quality=85"
    )
    strip_html = f"""
        <img src="{strip_url}"
             srcset="{strip_url} 2800w"
             alt="" width="900" height="291" />
    """ if include_strip else ""

    link_href = f"/{slug}" if relative_links else f"https://www.gocomics.com/{slug}"

    return f"""
    <div class="ComicViewer-module-scss-module__x__comicViewer">
      <div>
        <div>
          <a href="{link_href}">
            <div>
              <img src="{badge_url}"
                   srcset="{badge_url}?optimizer=image&width=128&quality=75 128w"
                   alt="" width="600" height="750" />
            </div>
          </a>
        </div>
      </div>
      {strip_html}
    </div>
    """


def _build_page_html(containers_html):
    """Wrap container HTML fragments in a minimal page."""
    return f"<html><body>{containers_html}</body></html>"


def _mock_driver(html):
    """Create a mock Selenium driver that returns the given HTML."""
    driver = MagicMock()
    driver.page_source = html
    driver.execute_script = MagicMock()
    return driver


class TestExtractComicSlugFromLink:
    def test_absolute_url(self):
        assert _extract_comic_slug_from_link('https://www.gocomics.com/garfield') == 'garfield'

    def test_relative_url(self):
        assert _extract_comic_slug_from_link('/garfield') == 'garfield'

    def test_rejects_profile_url(self):
        assert _extract_comic_slug_from_link('/profile/User123/comics/456') is None

    def test_rejects_next_url(self):
        assert _extract_comic_slug_from_link('/_next/static/chunks/main.js') is None

    def test_rejects_api_url(self):
        assert _extract_comic_slug_from_link('/api/auth/callback') is None

    def test_rejects_external_url(self):
        assert _extract_comic_slug_from_link('https://example.com/garfield') is None

    def test_rejects_empty_path(self):
        assert _extract_comic_slug_from_link('/') is None


class TestGetImageSrc:
    def test_src_with_featureassets(self):
        soup = BeautifulSoup(
            '<img src="https://featureassets.gocomics.com/assets/abc123" />',
            'html.parser',
        )
        assert 'abc123' in _get_image_src(soup.find('img'))

    def test_srcset_with_featureassets(self):
        soup = BeautifulSoup(
            '<img src="" srcset="https://featureassets.gocomics.com/assets/abc?w=32 32w, '
            'https://featureassets.gocomics.com/assets/abc?w=2800 2800w" />',
            'html.parser',
        )
        result = _get_image_src(soup.find('img'))
        assert 'w=2800' in result

    def test_no_featureassets(self):
        soup = BeautifulSoup('<img src="https://other.com/img.jpg" />', 'html.parser')
        assert _get_image_src(soup.find('img')) == 'https://other.com/img.jpg'


class TestGetBadgeName:
    def test_extracts_badge_name_from_src(self):
        soup = BeautifulSoup(
            '<img src="https://example.com/Global_Feature_Badge_Garfield_600_abc.png" />',
            'html.parser',
        )
        assert _get_badge_name(soup.find('img')) == 'Garfield'

    def test_extracts_multiword_badge_name(self):
        soup = BeautifulSoup(
            '<img srcset="https://example.com/Global_Feature_Badge_Calvin_And_Hobbes_600_x.png 128w" />',
            'html.parser',
        )
        assert _get_badge_name(soup.find('img')) == 'Calvin And Hobbes'

    def test_returns_none_for_non_badge(self):
        soup = BeautifulSoup(
            '<img src="https://featureassets.gocomics.com/assets/strip123" />',
            'html.parser',
        )
        assert _get_badge_name(soup.find('img')) is None


class TestExtractComicsFromPage:
    def test_extracts_comic_with_correct_slug(self):
        html = _build_page_html(
            _make_comic_container('garfield', 'Garfield', 'img001')
        )
        driver = _mock_driver(html)

        comics = extract_comics_from_page(driver, 'https://example.com/page', '2026-03-31')

        assert len(comics) == 1
        assert comics[0]['slug'] == 'garfield'
        assert comics[0]['name'] == 'Garfield'
        assert 'img001' in comics[0]['image_url']
        assert comics[0]['url'] == 'https://www.gocomics.com/garfield/2026/03/31'

    def test_slug_from_href_not_badge(self):
        """The slug comes from the link href, not the badge name."""
        html = _build_page_html(
            _make_comic_container('calvinandhobbes', 'Calvin_And_Hobbes', 'img002')
        )
        driver = _mock_driver(html)

        comics = extract_comics_from_page(driver, 'https://example.com/page', '2026-03-31')

        assert comics[0]['slug'] == 'calvinandhobbes'

    def test_spanish_and_english_get_different_slugs(self):
        """English and Spanish versions of the same comic produce distinct slugs."""
        html = _build_page_html(
            _make_comic_container('calvinandhobbes', 'Calvin_And_Hobbes', 'img_en')
            + _make_comic_container('calvinandhobbesespanol', 'Calvin_And_Hobbes', 'img_es')
        )
        driver = _mock_driver(html)

        comics = extract_comics_from_page(driver, 'https://example.com/page', '2026-03-31')

        slugs = [c['slug'] for c in comics]
        assert 'calvinandhobbes' in slugs
        assert 'calvinandhobbesespanol' in slugs
        assert len(comics) == 2

    def test_deduplicates_responsive_variants(self):
        """Same comic in desktop+mobile containers is deduplicated."""
        container = _make_comic_container('garfield', 'Garfield', 'img001')
        html = _build_page_html(container + container)
        driver = _mock_driver(html)

        comics = extract_comics_from_page(driver, 'https://example.com/page', '2026-03-31')

        assert len(comics) == 1

    def test_skips_containers_without_strip_image(self):
        html = _build_page_html(
            _make_comic_container('garfield', 'Garfield', 'img001', include_strip=False)
        )
        driver = _mock_driver(html)

        comics = extract_comics_from_page(driver, 'https://example.com/page', '2026-03-31')

        assert len(comics) == 0

    def test_skips_containers_without_gocomics_link(self):
        html = _build_page_html("""
        <div class="ComicViewer-module-scss-module__x__comicViewer">
          <img src="https://featureassets.gocomics.com/assets/orphan"
               srcset="https://featureassets.gocomics.com/assets/orphan 2800w" />
        </div>
        """)
        driver = _mock_driver(html)

        comics = extract_comics_from_page(driver, 'https://example.com/page', '2026-03-31')

        assert len(comics) == 0

    def test_multiple_comics_extracted(self):
        html = _build_page_html(
            _make_comic_container('garfield', 'Garfield', 'img001')
            + _make_comic_container('peanuts', 'Peanuts', 'img002')
            + _make_comic_container('bc', 'B_C', 'img003')
        )
        driver = _mock_driver(html)

        comics = extract_comics_from_page(driver, 'https://example.com/page', '2026-03-31')

        assert len(comics) == 3
        slugs = {c['slug'] for c in comics}
        assert slugs == {'garfield', 'peanuts', 'bc'}

    def test_handles_relative_links_from_selenium(self):
        """Selenium page_source uses relative hrefs like /garfield instead of absolute."""
        html = _build_page_html(
            _make_comic_container('garfield', 'Garfield', 'img001', relative_links=True)
            + _make_comic_container('peanuts', 'Peanuts', 'img002', relative_links=True)
        )
        driver = _mock_driver(html)

        comics = extract_comics_from_page(driver, 'https://example.com/page', '2026-03-31')

        assert len(comics) == 2
        assert comics[0]['slug'] == 'garfield'
        assert comics[0]['url'] == 'https://www.gocomics.com/garfield/2026/03/31'
        assert comics[1]['slug'] == 'peanuts'

    def test_falls_back_to_slug_for_display_name(self):
        """When no badge is present, display name is derived from slug."""
        html = _build_page_html("""
        <div class="ComicViewer-module-scss-module__x__comicViewer">
          <a href="https://www.gocomics.com/calvinandhobbes">link</a>
          <img src="https://featureassets.gocomics.com/assets/img999"
               srcset="https://featureassets.gocomics.com/assets/img999 2800w"
               alt="" />
        </div>
        """)
        driver = _mock_driver(html)

        comics = extract_comics_from_page(driver, 'https://example.com/page', '2026-03-31')

        assert comics[0]['slug'] == 'calvinandhobbes'
        assert comics[0]['name'] == 'Calvinandhobbes'

    def test_validation_logs_missed_comics(self, capsys):
        """When a container has a link but no strip image, validation reports it."""
        html = _build_page_html(
            _make_comic_container('garfield', 'Garfield', 'img001')
            + _make_comic_container('peanuts', 'Peanuts', 'img002', include_strip=False)
        )
        driver = _mock_driver(html)

        comics = extract_comics_from_page(driver, 'https://example.com/page', '2026-03-31')
        captured = capsys.readouterr()

        assert len(comics) == 1
        assert comics[0]['slug'] == 'garfield'
        assert '1 updated comics not extracted' in captured.out
        assert 'peanuts' in captured.out

    def test_validation_reports_all_captured(self, capsys):
        """When extraction matches page expectations, reports success."""
        html = _build_page_html(
            _make_comic_container('garfield', 'Garfield', 'img001')
            + _make_comic_container('peanuts', 'Peanuts', 'img002')
        )
        driver = _mock_driver(html)

        comics = extract_comics_from_page(driver, 'https://example.com/page', '2026-03-31')
        captured = capsys.readouterr()

        assert len(comics) == 2
        assert 'all 2 updated comics captured' in captured.out


class TestMergeWithExisting:
    """Verifies the second-pass merge logic that combines pass-1 and pass-2 scrapes."""

    def test_no_existing_file_returns_new_unchanged(self, tmp_path):
        """When no prior file exists, merge passes new comics through verbatim."""
        out = tmp_path / 'comics_2026-05-14.json'
        new = [{'slug': 'a', 'url': 'https://www.gocomics.com/a/2026/05/14'}]

        result = merge_with_existing(out, new)

        assert result == new

    def test_unreadable_existing_falls_back_to_new(self, tmp_path, capsys):
        """Corrupt existing file falls back to new data with a warning."""
        out = tmp_path / 'comics_2026-05-14.json'
        out.write_text('{ not valid json')
        new = [{'slug': 'a'}]

        result = merge_with_existing(out, new)

        assert result == new
        assert 'Could not read existing' in capsys.readouterr().out

    def test_disjoint_slugs_unions_both(self, tmp_path):
        """Pass-1 slugs not in pass-2 are preserved; pass-2 slugs are added."""
        out = tmp_path / 'comics_2026-05-14.json'
        out.write_text(json.dumps([
            {'slug': 'chipbok', 'image_url': 'pass1-chipbok'},
            {'slug': 'doonesbury', 'image_url': 'pass1-doonesbury'},
        ]))
        new = [{'slug': 'nickanderson', 'image_url': 'pass2-nickanderson'}]

        result = merge_with_existing(out, new)

        slugs = {c['slug'] for c in result}
        assert slugs == {'chipbok', 'doonesbury', 'nickanderson'}

    def test_overlapping_slug_pass_two_wins(self, tmp_path):
        """For a slug present in both passes, pass-2's entry replaces pass-1's."""
        out = tmp_path / 'comics_2026-05-14.json'
        out.write_text(json.dumps([
            {'slug': 'chipbok', 'image_url': 'pass1-image'},
        ]))
        new = [{'slug': 'chipbok', 'image_url': 'pass2-image'}]

        result = merge_with_existing(out, new)

        assert len(result) == 1
        assert result[0]['image_url'] == 'pass2-image'

    def test_mixed_overlap_and_disjoint(self, tmp_path, capsys):
        """Realistic merge: some shared slugs (pass-2 wins), some unique to each pass."""
        out = tmp_path / 'comics_2026-05-14.json'
        out.write_text(json.dumps([
            {'slug': 'chipbok', 'image_url': 'pass1-chipbok'},
            {'slug': 'doonesbury', 'image_url': 'pass1-doonesbury'},
            {'slug': 'johndeering', 'image_url': 'pass1-johndeering'},
        ]))
        new = [
            {'slug': 'chipbok', 'image_url': 'pass2-chipbok'},
            {'slug': 'nickanderson', 'image_url': 'pass2-nickanderson'},
            {'slug': 'robrogers', 'image_url': 'pass2-robrogers'},
        ]

        result = merge_with_existing(out, new)

        by_slug = {c['slug']: c['image_url'] for c in result}
        assert by_slug == {
            'chipbok': 'pass2-chipbok',
            'doonesbury': 'pass1-doonesbury',
            'johndeering': 'pass1-johndeering',
            'nickanderson': 'pass2-nickanderson',
            'robrogers': 'pass2-robrogers',
        }
        assert 'Merge: 3 from this pass + 2 preserved' in capsys.readouterr().out

    def test_entries_without_slug_are_dropped_from_preservation(self, tmp_path):
        """Pass-1 entries missing a slug field are skipped (treated as malformed)."""
        out = tmp_path / 'comics_2026-05-14.json'
        out.write_text(json.dumps([
            {'slug': 'chipbok'},
            {'no_slug_here': True},
        ]))
        new = [{'slug': 'nickanderson'}]

        result = merge_with_existing(out, new)

        slugs = {c.get('slug') for c in result}
        assert slugs == {'chipbok', 'nickanderson'}
