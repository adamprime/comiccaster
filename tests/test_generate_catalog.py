"""Tests for scripts/generate_catalog.py.

``public/catalog.json`` is the one machine-readable list of every comic
ComicCaster offers, for agents that should not have to scrape ``index.html`` or
reconcile seven tab lists with seven different key sets. It is built,
network-free, from the ``public/*comics_list.json`` files plus
``public/feeds/*.xml``, and rebuilt in Phase 2 of every pipeline pass that
writes feeds.

Unit tests run offline against files under ``tmp_path``. The tests at the end
check the committed catalog against the committed lists and feed files.
"""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import generate_catalog as gen  # noqa: E402


PROJECT_ROOT = Path(__file__).parent.parent
PUBLIC = PROJECT_ROOT / 'public'

ENTRY_KEYS = [
    'slug', 'name', 'author', 'source', 'category', 'language',
    'feed_url', 'site_url', 'has_feed', 'last_updated',
]

LIST_FILES = [
    'comics_list.json',
    'political_comics_list.json',
    'spanish_comics_list.json',
    'tinyview_comics_list.json',
    'farside_comics_list.json',
    'newyorker_comics_list.json',
    'external_comics_list.json',
]


def _feed_xml(last_build_date='Sat, 24 Oct 2026 08:22:47 +0000', items=1):
    item = '<item><title>Strip</title><pubDate>Sat, 24 Oct 2026 00:00:00 +0000</pubDate></item>'
    return (
        "<?xml version='1.0' encoding='UTF-8'?>"
        '<rss version="2.0"><channel><title>Feed</title>'
        f'<lastBuildDate>{last_build_date}</lastBuildDate>'
        f'{item * items}</channel></rss>'
    )


@pytest.fixture
def public(tmp_path):
    """A public/ dir with every list present and empty, and a feeds/ dir."""
    (tmp_path / 'feeds').mkdir()
    for name in LIST_FILES:
        (tmp_path / name).write_text('[]')
    return tmp_path


def _write_list(public, name, comics):
    (public / name).write_text(json.dumps(comics))


def _write_feed(public, slug, **kwargs):
    (public / 'feeds' / f'{slug}.xml').write_text(_feed_xml(**kwargs))


def _by_slug(catalog, source=None):
    return {
        c['slug']: c for c in catalog['comics']
        if source is None or c['source'] == source
    }


# --- Entry shape -------------------------------------------------------------

def test_a_hosted_comic_gets_an_absolute_feed_url_and_its_lastbuilddate(public):
    _write_list(public, 'comics_list.json', [{
        'name': 'Pickles', 'author': 'Brian Crane',
        'url': 'https://www.gocomics.com/pickles', 'slug': 'pickles',
        'position': 300, 'is_updated': True,
    }])
    _write_feed(public, 'pickles', last_build_date='Sat, 24 Oct 2026 08:22:47 +0000')

    entry = _by_slug(gen.build_catalog(public))['pickles']

    assert list(entry) == ENTRY_KEYS
    assert entry == {
        'slug': 'pickles',
        'name': 'Pickles',
        'author': 'Brian Crane',
        'source': 'gocomics',
        'category': 'daily',
        'language': 'en',
        'feed_url': 'https://comiccaster.xyz/feeds/pickles.xml',
        'site_url': 'https://www.gocomics.com/pickles',
        'has_feed': True,
        'last_updated': '2026-10-24T08:22:47+00:00',
    }


def test_last_updated_is_normalised_to_utc(public):
    _write_list(public, 'comics_list.json', [{'name': 'A', 'slug': 'a', 'url': 'https://www.gocomics.com/a'}])
    _write_feed(public, 'a', last_build_date='Fri, 23 Oct 2026 22:15:00 -0500')

    assert _by_slug(gen.build_catalog(public))['a']['last_updated'] == '2026-10-24T03:15:00+00:00'


def test_the_lastbuilddate_is_found_in_a_feed_with_many_items(public):
    _write_list(public, 'comics_list.json', [{'name': 'A', 'slug': 'a', 'url': 'https://www.gocomics.com/a'}])
    _write_feed(public, 'a', items=200)

    assert _by_slug(gen.build_catalog(public))['a']['last_updated'] == '2026-10-24T08:22:47+00:00'


@pytest.mark.parametrize('body', [
    pytest.param('not xml at all', id='unparseable'),
    pytest.param('<rss><channel><title>t</title></channel></rss>', id='no-lastBuildDate'),
    pytest.param('<rss><channel><lastBuildDate>yesterday</lastBuildDate></channel></rss>', id='bad-date'),
])
def test_an_unreadable_lastbuilddate_is_null_but_the_feed_still_counts(public, body):
    _write_list(public, 'comics_list.json', [{'name': 'A', 'slug': 'a', 'url': 'https://www.gocomics.com/a'}])
    (public / 'feeds' / 'a.xml').write_text(body)

    entry = _by_slug(gen.build_catalog(public))['a']
    assert entry['has_feed'] is True
    assert entry['feed_url'] == 'https://comiccaster.xyz/feeds/a.xml'
    assert entry['last_updated'] is None


def test_a_missing_author_is_null(public):
    _write_list(public, 'comics_list.json', [{'name': 'A', 'slug': 'a', 'url': 'https://www.gocomics.com/a'}])
    _write_feed(public, 'a')

    assert _by_slug(gen.build_catalog(public))['a']['author'] is None


def test_a_declared_source_is_kept(public):
    _write_list(public, 'comics_list.json', [{
        'name': 'Zits', 'slug': 'zits', 'author': 'Jerry Scott and Jim Borgman',
        'url': 'https://comicskingdom.com/zits', 'source': 'comicskingdom',
    }])
    _write_feed(public, 'zits')

    entry = _by_slug(gen.build_catalog(public))['zits']
    assert entry['source'] == 'comicskingdom'
    assert entry['category'] == 'daily'


# --- Listed comics without a feed, feeds without a listing --------------------

def test_a_listed_comic_with_no_feed_file_is_marked_and_has_no_feed_url(public):
    """Dormant comics stay listed, as on the site, but give agents no 404 to copy."""
    _write_list(public, 'political_comics_list.json', [{
        'name': 'Steve Benson', 'slug': 'stevebenson', 'author': 'Steve Benson',
        'url': 'https://www.gocomics.com/stevebenson', 'is_political': True,
    }])

    entry = _by_slug(gen.build_catalog(public))['stevebenson']
    assert entry['has_feed'] is False
    assert entry['feed_url'] is None
    assert entry['last_updated'] is None
    assert entry['site_url'] == 'https://www.gocomics.com/stevebenson'


def test_a_feed_file_no_list_claims_is_left_out_and_reported(public):
    _write_list(public, 'comics_list.json', [{'name': 'A', 'slug': 'a', 'url': 'https://www.gocomics.com/a'}])
    _write_feed(public, 'a')
    _write_feed(public, 'delisted')

    catalog = gen.build_catalog(public)
    assert set(_by_slug(catalog)) == {'a'}
    assert gen.unlisted_feeds(public, catalog) == ['delisted']


# --- Categories and the lists a comic sits in --------------------------------

@pytest.mark.parametrize('list_name, category', [
    ('comics_list.json', 'daily'),
    ('political_comics_list.json', 'political'),
    ('spanish_comics_list.json', 'spanish'),
    ('tinyview_comics_list.json', 'tinyview'),
    ('farside_comics_list.json', 'farside'),
    ('newyorker_comics_list.json', 'newyorker'),
])
def test_each_list_sets_the_category_of_its_comics(public, list_name, category):
    _write_list(public, list_name, [{'name': 'A', 'slug': 'a', 'url': 'https://example.com/a'}])
    _write_feed(public, 'a')

    assert _by_slug(gen.build_catalog(public))['a']['category'] == category


def test_language_is_the_one_the_comic_declares(public):
    """The same field the feed generator writes as the feed's <language>."""
    comic = {'name': 'Peanuts en Español', 'slug': 'peanuts-espanol',
             'url': 'https://www.gocomics.com/peanuts-espanol', 'language': 'es'}
    _write_list(public, 'comics_list.json', [comic])
    _write_list(public, 'spanish_comics_list.json', [{k: v for k, v in comic.items() if k != 'language'}])
    _write_feed(public, 'peanuts-espanol')

    entry = _by_slug(gen.build_catalog(public))['peanuts-espanol']
    assert (entry['category'], entry['language']) == ('spanish', 'es')


def test_language_defaults_to_english(public):
    _write_list(public, 'spanish_comics_list.json', [{'name': 'A', 'slug': 'a', 'url': 'https://example.com/a'}])
    _write_feed(public, 'a')

    assert _by_slug(gen.build_catalog(public))['a']['language'] == 'en'


@pytest.mark.parametrize('other_list, category', [
    ('spanish_comics_list.json', 'spanish'),
    ('political_comics_list.json', 'political'),
    ('farside_comics_list.json', 'farside'),
    ('newyorker_comics_list.json', 'newyorker'),
])
def test_a_comic_in_the_daily_list_and_another_is_one_entry_in_the_other_category(
        public, other_list, category):
    """Spanish, Far Side and New Yorker comics repeat in the Daily list; one feed, one entry."""
    comic = {'name': 'A', 'slug': 'a', 'url': 'https://example.com/a'}
    _write_list(public, 'comics_list.json', [comic])
    _write_list(public, other_list, [comic])
    _write_feed(public, 'a')

    catalog = gen.build_catalog(public)
    assert [c['slug'] for c in catalog['comics']] == ['a']
    assert catalog['comics'][0]['category'] == category


def test_the_daily_list_supplies_the_author_for_a_comic_also_on_the_political_tab(public):
    """The political list's `author` for its dual-listed strips is the strip's own name."""
    _write_list(public, 'comics_list.json', [{
        'name': 'Doonesbury', 'author': 'Garry Trudeau',
        'url': 'https://www.gocomics.com/doonesbury', 'slug': 'doonesbury',
    }])
    _write_list(public, 'political_comics_list.json', [{
        'name': 'Doonesbury', 'author': 'Doonesbury',
        'url': 'https://www.gocomics.com/doonesbury', 'slug': 'doonesbury', 'is_political': True,
    }])
    _write_feed(public, 'doonesbury')

    entry = _by_slug(gen.build_catalog(public))['doonesbury']
    assert entry['author'] == 'Garry Trudeau'
    assert entry['category'] == 'political'


def test_a_later_list_fills_an_author_the_daily_list_lacks(public):
    _write_list(public, 'comics_list.json', [{'name': 'A', 'slug': 'a', 'url': 'https://example.com/a'}])
    _write_list(public, 'spanish_comics_list.json', [{
        'name': 'A', 'slug': 'a', 'url': 'https://example.com/a', 'author': 'Someone',
    }])
    _write_feed(public, 'a')

    assert _by_slug(gen.build_catalog(public))['a']['author'] == 'Someone'


# --- External RSS ------------------------------------------------------------

def test_an_external_comic_points_at_the_publishers_own_feed(public):
    _write_list(public, 'external_comics_list.json', [{
        'name': 'xkcd', 'slug': 'xkcd', 'author': 'Randall Munroe',
        'url': 'https://xkcd.com/', 'feed_url': 'https://xkcd.com/rss.xml',
        'source': 'external-rss',
    }])

    entry = _by_slug(gen.build_catalog(public))['xkcd']
    assert entry == {
        'slug': 'xkcd',
        'name': 'xkcd',
        'author': 'Randall Munroe',
        'source': 'external-rss',
        'category': 'external',
        'language': 'en',
        'feed_url': 'https://xkcd.com/rss.xml',
        'site_url': 'https://xkcd.com/',
        'has_feed': True,
        'last_updated': None,
    }


def test_an_external_feed_and_a_hosted_feed_with_the_same_slug_are_both_listed(public):
    """False Knees has a GoComics feed here and its own RSS; they are different feeds."""
    _write_list(public, 'comics_list.json', [{
        'name': 'False Knees', 'author': 'Joshua Barkman',
        'url': 'https://www.gocomics.com/false-knees', 'slug': 'false-knees',
    }])
    _write_list(public, 'external_comics_list.json', [{
        'name': 'False Knees', 'slug': 'false-knees', 'author': 'Joshua Barkman',
        'url': 'https://falseknees.com/', 'feed_url': 'https://falseknees.com/rss.xml',
        'source': 'external-rss',
    }])
    _write_feed(public, 'false-knees')

    catalog = gen.build_catalog(public)
    assert sorted(c['feed_url'] for c in catalog['comics']) == [
        'https://comiccaster.xyz/feeds/false-knees.xml',
        'https://falseknees.com/rss.xml',
    ]
    assert gen.unlisted_feeds(public, catalog) == []


# --- Document --------------------------------------------------------------

def test_the_document_points_at_the_site_and_counts_its_comics(public):
    _write_list(public, 'comics_list.json', [
        {'name': 'B', 'slug': 'b', 'url': 'https://www.gocomics.com/b'},
        {'name': 'A', 'slug': 'a', 'url': 'https://www.gocomics.com/a'},
    ])

    catalog = gen.build_catalog(public)
    assert catalog['site'] == 'https://comiccaster.xyz'
    assert catalog['docs'] == 'https://comiccaster.xyz/llms.txt'
    assert catalog['count'] == 2 == len(catalog['comics'])


def test_comics_are_sorted_by_name_ignoring_case(public):
    _write_list(public, 'comics_list.json', [
        {'name': 'beta', 'slug': 'b', 'url': 'https://www.gocomics.com/b'},
        {'name': 'Alpha', 'slug': 'a', 'url': 'https://www.gocomics.com/a'},
        {'name': 'Gamma', 'slug': 'g', 'url': 'https://www.gocomics.com/g'},
    ])

    assert [c['name'] for c in gen.build_catalog(public)['comics']] == ['Alpha', 'beta', 'Gamma']


def test_a_missing_list_file_is_an_error_not_a_smaller_catalog(public):
    (public / 'political_comics_list.json').unlink()

    with pytest.raises(FileNotFoundError):
        gen.build_catalog(public)


def test_main_writes_the_catalog_and_running_it_twice_changes_nothing(public):
    _write_list(public, 'comics_list.json', [{'name': 'Ñandú', 'slug': 'n', 'url': 'https://www.gocomics.com/n'}])
    _write_feed(public, 'n')
    out = public / 'catalog.json'

    assert gen.main(public_dir=public) == 0
    first = out.read_bytes()
    assert gen.main(public_dir=public) == 0

    assert out.read_bytes() == first
    assert out.stat().st_mode & 0o777 == 0o644
    assert first.endswith(b'\n')
    assert json.loads(first)['comics'][0]['name'] == 'Ñandú'
    assert [p.name for p in public.iterdir() if p.name.startswith('catalog')] == ['catalog.json']


def test_main_leaves_the_previous_catalog_when_the_build_fails(public):
    out = public / 'catalog.json'
    out.write_text('{"previous": true}\n')
    (public / 'comics_list.json').write_text('{ broken')

    assert gen.main(public_dir=public) == 1
    assert out.read_text() == '{"previous": true}\n'


# --- The committed catalog -------------------------------------------------
#
# The pipeline rebuilds catalog.json after every pass that writes feeds, so the
# committed file must agree with the committed lists and feeds. A disagreement
# means a pass that writes feeds stopped rebuilding it, or a list edit shipped
# without a rebuild. `last_updated` is excluded: the Far Side morning pass
# rewrites farside-daily.xml without rebuilding the catalog.

# Feed files deliberately left without a catalog entry. Each one is a comic
# delisted on purpose whose old feed file was kept so existing subscribers get
# a frozen feed rather than a 404.
RETIRED_FEEDS = {
    # Left GoComics; delisted in #140 (0bfc55d56f, 2026-05-16). Its feed holds a
    # single placeholder item from 2025-04-09.
    'everyday-people-cartoons',
}


def _committed_catalog():
    return json.loads((PUBLIC / 'catalog.json').read_text())


def _hosted(catalog):
    return [c for c in catalog['comics'] if c['source'] != 'external-rss']


def _feed_files():
    return {p.stem for p in (PUBLIC / 'feeds').glob('*.xml')}


def _without_last_updated(catalog):
    return [{k: v for k, v in c.items() if k != 'last_updated'} for c in catalog['comics']]


def test_the_builder_reads_every_comic_list_the_site_has():
    """A new list the builder doesn't know would be missing from the catalog, silently."""
    read = {name for name, _ in gen.HOSTED_LISTS} | {gen.EXTERNAL_LIST}
    assert read == {p.name for p in PUBLIC.glob('*comics_list.json')}


def test_the_committed_catalog_is_what_the_builder_makes_from_the_committed_lists():
    committed, rebuilt = _committed_catalog(), gen.build_catalog(PUBLIC)
    assert committed['count'] == rebuilt['count']
    assert _without_last_updated(committed) == _without_last_updated(rebuilt), (
        'public/catalog.json is stale against the comic lists or feed files. '
        'Rebuild it with: python scripts/generate_catalog.py'
    )


def test_the_committed_catalog_and_the_feed_files_agree():
    feed_files = _feed_files()
    hosted = _hosted(_committed_catalog())

    missing = sorted(c['slug'] for c in hosted if c['has_feed'] and c['slug'] not in feed_files)
    present = sorted(c['slug'] for c in hosted if not c['has_feed'] and c['slug'] in feed_files)
    unlisted = sorted(feed_files - {c['slug'] for c in hosted} - RETIRED_FEEDS)
    assert not (missing or present or unlisted), (
        f'catalog says has_feed but public/feeds/<slug>.xml is missing: {missing}\n'
        f'catalog says no feed but the file exists: {present}\n'
        f'feed files no catalog entry lists (delisted on purpose? add to RETIRED_FEEDS): {unlisted}'
    )


def test_the_retired_feed_allowlist_is_not_stale():
    feed_files = _feed_files()
    listed = {c['slug'] for c in _hosted(_committed_catalog())}
    stale = sorted(slug for slug in RETIRED_FEEDS if slug not in feed_files or slug in listed)
    assert not stale, f'RETIRED_FEEDS entries whose file is gone or that are listed again: {stale}'


def test_every_committed_feed_url_is_unique_and_every_hosted_one_is_on_comiccaster():
    comics = _committed_catalog()['comics']
    urls = [c['feed_url'] for c in comics if c['feed_url']]
    assert len(urls) == len(set(urls))
    for c in _hosted({'comics': comics}):
        if c['has_feed']:
            assert c['feed_url'] == f"https://comiccaster.xyz/feeds/{c['slug']}.xml"


# --- Pipeline wiring -------------------------------------------------------
#
# Pass 1 and Pass 2 both write feeds, and both have a reset-and-regenerate
# recovery path. Each of those four places must rebuild the catalog after its
# generators and commit it with the feeds.

@pytest.mark.parametrize('script', ['local_master_update.sh', 'local_pass2_update.sh'])
def test_each_feed_writing_pass_rebuilds_and_commits_the_catalog(script):
    text = (PROJECT_ROOT / 'scripts' / script).read_text()
    assert text.count('python scripts/generate_catalog.py') == 2, (
        f'{script} must rebuild the catalog in Phase 2 and again in push recovery'
    )
    assert 'git add -f public/catalog.json' in text


@pytest.mark.parametrize('workflow', ['tests.yml', 'codeql.yml'])
def test_pipeline_catalog_commits_do_not_start_ci(workflow):
    """Pipeline commits change no code; #242 stopped them spending Actions minutes."""
    text = (PROJECT_ROOT / '.github' / 'workflows' / workflow).read_text()
    assert text.count("- 'public/catalog.json'") == 2
