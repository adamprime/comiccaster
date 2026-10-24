"""Static files that let AI agents use comiccaster.xyz without scraping index.html.

Agents read ``/llms.txt`` to learn the site, ``/catalog.json`` to find comics
and feed URLs, and fetch feeds directly. Browser-based agents and web apps can
only read the catalog and the feeds cross-origin if Netlify sends a CORS
header for them, which ``public/_headers`` configures.
"""

from pathlib import Path

import pytest


PUBLIC = Path(__file__).parent.parent / 'public'


def _header_rules(text):
    """Parse Netlify's _headers format into {path: {header-name-lowercase: value}}."""
    rules, path = {}, None
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        if not line[0].isspace():
            path = line.strip()
            rules.setdefault(path, {})
        elif path is not None and ':' in line:
            name, value = line.strip().split(':', 1)
            rules[path][name.strip().lower()] = value.strip()
    return rules


def test_the_headers_parser_reads_netlify_blocks():
    rules = _header_rules('/a/*\n  X-One: 1\n  X-Two: two: parts\n\n# note\n/b\n  X-Three: 3\n')
    assert rules == {'/a/*': {'x-one': '1', 'x-two': 'two: parts'}, '/b': {'x-three': '3'}}


@pytest.mark.parametrize('path', ['/feeds/*', '/rss/*', '/catalog.json'])
def test_feeds_and_the_catalog_can_be_read_cross_origin(path):
    rules = _header_rules((PUBLIC / '_headers').read_text())
    assert rules.get(path, {}).get('access-control-allow-origin') == '*'


def test_the_existing_favicon_headers_are_kept():
    rules = _header_rules((PUBLIC / '_headers').read_text())
    assert rules['/images/favicon.svg']['content-type'] == 'image/svg+xml'
    assert rules['/favicon.ico']['content-type'] == 'image/x-icon'


def test_llms_txt_says_where_the_catalog_and_feeds_are():
    text = (PUBLIC / 'llms.txt').read_text()
    assert text.startswith('# ComicCaster\n')
    for needle in [
        'https://comiccaster.xyz/catalog.json',
        'https://comiccaster.xyz/feeds/<slug>.xml',
        'https://comiccaster.xyz/rss/<slug>',
        '/.netlify/functions/generate-opml',
        'has_feed',
    ]:
        assert needle in text, f'llms.txt does not mention {needle}'


def test_llms_txt_is_plain_ascii():
    """Netlify serves .txt without a charset, so non-ASCII text can render as mojibake."""
    (PUBLIC / 'llms.txt').read_bytes().decode('ascii')


def test_robots_txt_allows_everything():
    lines = [line.strip() for line in (PUBLIC / 'robots.txt').read_text().splitlines()]
    assert 'User-agent: *' in lines
    assert not [line for line in lines if line.lower().startswith('disallow:') and line[9:].strip()]
