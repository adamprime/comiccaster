"""Tests for the ComicFeedGenerator class."""

import pytest
import dateutil.parser
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock
from feedgen.feed import FeedGenerator
from feedgen.entry import FeedEntry
from comiccaster.feed_generator import ComicFeedGenerator

@pytest.fixture
def comic_info():
    """Sample comic information."""
    return {
        'name': 'Test Comic',
        'author': 'Test Author',
        'url': 'https://www.gocomics.com/test-comic',
        'slug': 'test-comic'
    }

@pytest.fixture
def metadata():
    """Sample comic strip metadata."""
    return {
        'title': 'Test Comic - 2024-04-06',
        'url': 'https://www.gocomics.com/test-comic/2024/04/06',
        'image': 'https://example.com/test-comic.jpg',
        'description': 'Test comic strip for April 6, 2024',
        'pub_date': 'Sat, 06 Apr 2024 00:00:00 -0400'
    }

@pytest.fixture
def feed_generator(tmp_path):
    """Create a ComicFeedGenerator instance with a temporary output directory."""
    return ComicFeedGenerator(output_dir=str(tmp_path))

def test_initialization(tmp_path):
    """Test ComicFeedGenerator initialization."""
    generator = ComicFeedGenerator(
        base_url='https://example.com',
        output_dir=str(tmp_path)
    )
    
    assert generator.base_url == 'https://example.com'
    assert generator.output_dir == Path(tmp_path)
    assert generator.output_dir.exists()

def test_create_feed(feed_generator, comic_info):
    """Test creating a new feed."""
    fg = feed_generator.create_feed(comic_info)

    feed_str = fg.rss_str(pretty=True).decode('utf-8')
    assert 'Test Comic - GoComics' in feed_str
    assert comic_info['url'] in feed_str
    assert 'Daily Test Comic comic strip by Test Author' in feed_str
    assert '<language>en</language>' in feed_str
    assert comic_info['author'] in feed_str


def test_create_feed_declares_the_comics_own_language(feed_generator, comic_info):
    """A Spanish comic's catalog entry says language: es; its feed must say so too."""
    fg = feed_generator.create_feed({**comic_info, 'language': 'es'})

    feed_str = fg.rss_str(pretty=True).decode('utf-8')
    assert '<language>es</language>' in feed_str
    assert '<language>en</language>' not in feed_str


def test_generate_feed_writes_the_language_into_the_feed_file(feed_generator, comic_info):
    entries = [{
        'title': 'Test Comic - Day 1',
        'url': 'https://example.com/comic/1',
        'image': 'https://example.com/image/1.jpg',
        'pub_date': 'Sun, 1 Apr 2024 00:00:00 -0400',
    }]

    assert feed_generator.generate_feed({**comic_info, 'language': 'es'}, entries) is True
    feed_xml = (feed_generator.output_dir / f"{comic_info['slug']}.xml").read_text()
    assert '<language>es</language>' in feed_xml


@pytest.mark.parametrize('source,display', [
    ('mrboffo', 'Neatly Chiseled Features'),
    ('farside-daily', 'The Far Side'),
    ('farside-new', 'The Far Side'),
    ('newyorker', 'The New Yorker'),
    ('creators', 'Creators'),
    ('comicskingdom', 'Comics Kingdom'),
])
def test_create_feed_custom_source_branding(feed_generator, comic_info, source, display):
    """One-off custom scrapers are branded by their own source, not GoComics."""
    comic_info = {**comic_info, 'source': source}
    fg = feed_generator.create_feed(comic_info)

    feed_str = fg.rss_str(pretty=True).decode('utf-8')
    assert f'Test Comic - {display}' in feed_str
    assert f'from {display}' in feed_str
    assert 'GoComics' not in feed_str

def test_create_entry(feed_generator, comic_info, metadata):
    """Test creating a feed entry."""
    fe = feed_generator.create_entry(comic_info, metadata)

    # Create a properly configured feed generator for testing
    fg = feed_generator.create_feed(comic_info)
    fg.add_entry(fe)
    feed_str = fg.rss_str(pretty=True).decode('utf-8')

    assert metadata['title'] in feed_str
    assert metadata['url'] in feed_str
    assert metadata['image'] in feed_str
    assert metadata['description'] in feed_str
    assert '2024-04-06' in feed_str


def test_single_image_centering_wrapper(feed_generator, comic_info):
    """Test that single images are wrapped in a centering div with max-width."""
    content = feed_generator._create_single_image_content(
        'https://example.com/comic.jpg', '', comic_info
    )
    assert 'max-width: 700px' in content
    assert 'text-align: center' in content
    assert 'https://example.com/comic.jpg' in content


def test_single_image_no_display_block(feed_generator, comic_info):
    """Images must NOT have display:block -- litehtml renders img as inline-block
    by default, which lets text-align:center on the parent div do the centering.
    display:block breaks this in litehtml (RSS Guard's renderer)."""
    content = feed_generator._create_single_image_content(
        'https://example.com/comic.jpg', '', comic_info
    )
    assert 'display: block' not in content, (
        "display:block on <img> breaks centering in litehtml-based readers (RSS Guard). "
        "Images should remain inline-block so text-align:center on the parent works."
    )


def test_multi_image_centering_wrapper(feed_generator, comic_info):
    """Test that multi-image gallery div has consistent max-width centering and no style block."""
    images = [
        {'url': 'https://example.com/panel1.jpg', 'alt': 'Panel 1'},
        {'url': 'https://example.com/panel2.jpg', 'alt': 'Panel 2'},
    ]
    content = feed_generator._create_multi_image_content(images, '', comic_info)
    assert 'max-width: 700px' in content
    assert 'margin: 10px auto' in content
    assert '<style>' not in content, "RSS feeds should use inline styles only, not <style> blocks"


def test_multi_image_no_display_block(feed_generator, comic_info):
    """Multi-image panels must NOT have display:block on img tags -- same litehtml
    compatibility reason as single images."""
    images = [
        {'url': 'https://example.com/panel1.jpg', 'alt': 'Panel 1'},
        {'url': 'https://example.com/panel2.jpg', 'alt': 'Panel 2'},
    ]
    content = feed_generator._create_multi_image_content(images, '', comic_info)
    assert 'display: block' not in content, (
        "display:block on <img> breaks centering in litehtml-based readers (RSS Guard). "
        "Images should remain inline-block so text-align:center on the parent works."
    )


def test_multi_image_text_align_center(feed_generator, comic_info):
    """The gallery wrapper must use text-align:center for litehtml compatibility."""
    images = [
        {'url': 'https://example.com/panel1.jpg', 'alt': 'Panel 1'},
    ]
    content = feed_generator._create_multi_image_content(images, '', comic_info)
    assert 'text-align: center' in content

def test_create_entry_minimal_metadata(feed_generator, comic_info):
    """Test creating a feed entry with minimal metadata."""
    minimal_metadata = {'url': comic_info['url']}
    fe = feed_generator.create_entry(comic_info, minimal_metadata)
    
    # Create a properly configured feed generator for testing
    fg = feed_generator.create_feed(comic_info)
    fg.add_entry(fe)
    feed_str = fg.rss_str(pretty=True).decode('utf-8')
    
    assert comic_info['name'] in feed_str
    assert comic_info['url'] in feed_str
    # Check for date in ISO format (YYYY-MM-DD)
    current_date = datetime.now(timezone.utc)
    date_str = current_date.strftime('%Y-%m-%d')
    assert date_str in feed_str

def test_create_entry_invalid_date(feed_generator, comic_info, metadata):
    """Test creating a feed entry with invalid publication date."""
    metadata['pub_date'] = 'invalid date'
    fe = feed_generator.create_entry(comic_info, metadata)
    
    # Create a properly configured feed generator for testing
    fg = feed_generator.create_feed(comic_info)
    fg.add_entry(fe)
    feed_str = fg.rss_str(pretty=True).decode('utf-8')
    
    # Should still create entry with current date
    assert metadata['title'] in feed_str
    assert metadata['url'] in feed_str

# parse_date_with_timezone tries RFC 2822, then a bare YYYY-MM-DD, then
# dateutil. Every generator today passes a datetime, or (Far Side) an RFC 2822
# string, so dateutil only runs for other string formats. The tests below pin
# what each branch returns, so a dateutil upgrade that changes parsing fails
# here instead of shifting dates in a live feed.

CST = timezone(timedelta(hours=-6))

def test_parse_date_returns_an_aware_datetime_unchanged(feed_generator):
    when = datetime(2026, 11, 22, 3, 5, tzinfo=CST)
    result = feed_generator.parse_date_with_timezone(when)
    assert result == when
    assert result.utcoffset() == timedelta(hours=-6)

def test_parse_date_reads_a_naive_datetime_as_utc(feed_generator):
    result = feed_generator.parse_date_with_timezone(datetime(2026, 11, 22, 3, 5))
    assert result == datetime(2026, 11, 22, 3, 5, tzinfo=timezone.utc)

@pytest.mark.parametrize('date_str, expected', [
    # Far Side's format: the offset is kept.
    ('Sat, 22 Nov 2026 06:00:00 -0600', datetime(2026, 11, 22, 6, 0, tzinfo=CST)),
    ('2026-11-22', datetime(2026, 11, 22, tzinfo=timezone.utc)),
])
def test_parse_date_handles_rfc2822_and_plain_dates_without_dateutil(
        feed_generator, mocker, date_str, expected):
    spy = mocker.spy(dateutil.parser, 'parse')
    result = feed_generator.parse_date_with_timezone(date_str)
    assert spy.call_count == 0
    assert result == expected
    assert result.utcoffset() == expected.utcoffset()

@pytest.mark.parametrize('date_str, expected', [
    ('2026-11-22T03:05:00-06:00', datetime(2026, 11, 22, 3, 5, tzinfo=CST)),
    ('2026-11-22T09:05:00Z', datetime(2026, 11, 22, 9, 5, tzinfo=timezone.utc)),
    # No offset in the string: read as UTC.
    ('2026-11-22T03:05:00', datetime(2026, 11, 22, 3, 5, tzinfo=timezone.utc)),
    ('November 22, 2026', datetime(2026, 11, 22, tzinfo=timezone.utc)),
    ('2026/11/22', datetime(2026, 11, 22, tzinfo=timezone.utc)),
])
def test_parse_date_falls_back_to_dateutil_for_other_formats(
        feed_generator, mocker, date_str, expected):
    spy = mocker.spy(dateutil.parser, 'parse')
    result = feed_generator.parse_date_with_timezone(date_str)
    assert spy.call_count == 1
    assert result == expected
    assert result.utcoffset() == expected.utcoffset()

@pytest.mark.parametrize('date_str', ['not a date', ''])
def test_parse_date_turns_an_unparseable_date_into_now_and_logs_it(
        feed_generator, caplog, date_str):
    # A missing pub_date arrives as '' and takes this path too: the entry is
    # silently stamped with the run time, so the log line is the only trace.
    before = datetime.now(timezone.utc)
    result = feed_generator.parse_date_with_timezone(date_str)
    after = datetime.now(timezone.utc)
    assert before <= result <= after
    assert 'Failed to parse date string' in caplog.text

def test_update_feed_new(feed_generator, comic_info, metadata):
    """Test updating a non-existent feed (creates new)."""
    result = feed_generator.update_feed(comic_info, metadata)
    
    assert result is True
    feed_path = feed_generator.output_dir / f"{comic_info['slug']}.xml"
    assert feed_path.exists()
    
    with open(feed_path) as f:
        feed_content = f.read()
        assert metadata['title'] in feed_content
        assert metadata['url'] in feed_content
        assert metadata['image'] in feed_content

@patch('pathlib.Path.exists')
def test_update_feed_existing(mock_exists, feed_generator, comic_info, metadata):
    """Test updating an existing feed."""
    mock_exists.return_value = True
    
    # Create a new feed first
    fg = feed_generator.create_feed(comic_info)
    feed_path = feed_generator.output_dir / f"{comic_info['slug']}.xml"
    fg.rss_file(str(feed_path))
    
    # Now update it
    result = feed_generator.update_feed(comic_info, metadata)
    assert result is True
    
    # Verify the feed was updated
    with open(feed_path) as f:
        feed_content = f.read()
        assert metadata['title'] in feed_content
        assert metadata['url'] in feed_content
        assert metadata['image'] in feed_content

def test_update_feed_error(feed_generator, comic_info, metadata):
    """Test error handling in update_feed."""
    with patch('feedgen.feed.FeedGenerator.rss_file') as mock_rss_file:
        mock_rss_file.side_effect = Exception('Test error')
        result = feed_generator.update_feed(comic_info, metadata)
        
        assert result is False

def test_generate_feed(feed_generator, comic_info):
    """Test generating a complete feed with multiple entries."""
    entries = [
        {
            'title': f'Test Comic - Day {i}',
            'url': f'https://example.com/comic/{i}',
            'image': f'https://example.com/image/{i}.jpg',
            'description': f'Test description {i}',
            'pub_date': f'Sun, {i} Apr 2024 00:00:00 -0400'
        }
        for i in range(1, 4)
    ]
    
    result = feed_generator.generate_feed(comic_info, entries)
    
    assert result is True
    feed_path = feed_generator.output_dir / f"{comic_info['slug']}.xml"
    assert feed_path.exists()
    
    with open(feed_path) as f:
        feed_content = f.read()
        # Verify entries are present
        for i in range(1, 4):
            assert f'Test Comic - Day {i}' in feed_content
            assert f'https://example.com/comic/{i}' in feed_content
            assert f'Test description {i}' in feed_content

def test_generate_feed_error(feed_generator, comic_info):
    """Test error handling in generate_feed."""
    with patch('feedgen.feed.FeedGenerator.rss_file') as mock_rss_file:
        mock_rss_file.side_effect = Exception('Test error')
        result = feed_generator.generate_feed(comic_info, [])
        
        assert result is False 

# --- Strip images as Media RSS media:content (agent access, step 1) ---------
#
# Each item names its strip images in <media:content url=... medium="image"/>,
# so an agent can read them without parsing the description's escaped HTML.
# The description itself must not change.

from html.parser import HTMLParser

import feedparser
from lxml import etree

MEDIA_NS = 'http://search.yahoo.com/mrss/'


class _ImgSources(HTMLParser):
    def __init__(self):
        super().__init__()
        self.sources = []

    def handle_starttag(self, tag, attrs):
        if tag == 'img':
            self.sources.append(dict(attrs).get('src'))


def _description_images(item):
    parser = _ImgSources()
    parser.feed(item.findtext('description') or '')
    return parser.sources


def _strip_entry(day, **fields):
    return {
        'title': f'Test Comic - 2024-04-{day:02d}',
        'url': f'https://www.gocomics.com/test-comic/2024/04/{day:02d}',
        'pub_date': f'2024-04-{day:02d}',
        'description': f'Comic strip for 2024-04-{day:02d}',
        **fields,
    }


def _written_items(feed_generator, comic_info, entries):
    assert feed_generator.generate_feed(comic_info, entries) is True
    path = feed_generator.output_dir / f"{comic_info['slug']}.xml"
    return etree.parse(str(path)).getroot().findall('channel/item')


def _media(item):
    return [(el.get('url'), el.get('medium')) for el in item.iter(f'{{{MEDIA_NS}}}content')]


def test_single_image_item_carries_one_media_content_directly_under_the_item(feed_generator, comic_info):
    [item] = _written_items(feed_generator, comic_info, [
        _strip_entry(6, image='https://img.example/strip.jpg'),
    ])

    assert _media(item) == [('https://img.example/strip.jpg', 'image')]
    [element] = item.iter(f'{{{MEDIA_NS}}}content')
    assert element.getparent() is item


@pytest.mark.parametrize('images', [
    # TinyView: a multi-panel strip, alt text set to the image URL.
    [{'url': f'https://cdn.tinyview.com/adhdinos/{n}.jpg', 'alt': f'https://cdn.tinyview.com/adhdinos/{n}.jpg'}
     for n in range(1, 4)],
    # Comics Kingdom: a multi-panel Sunday page.
    [{'url': f'https://wp.comicskingdom.com/panel-{n}.png', 'alt': f'Test Comic - Panel {n}'}
     for n in range(1, 5)],
], ids=['tinyview', 'comicskingdom'])
def test_multi_image_item_carries_one_media_content_per_image_in_order(feed_generator, comic_info, images):
    [item] = _written_items(feed_generator, comic_info, [_strip_entry(6, images=images)])

    assert _media(item) == [(image['url'], 'image') for image in images]
    assert all(el.getparent() is item for el in item.iter(f'{{{MEDIA_NS}}}content'))
    assert item.find(f'{{{MEDIA_NS}}}group') is None


def test_images_without_a_url_are_skipped_as_the_gallery_skips_them(feed_generator, comic_info):
    [item] = _written_items(feed_generator, comic_info, [_strip_entry(6, images=[
        {'url': 'https://img.example/1.png'},
        {'alt': 'no url at all'},
        {'url': ''},
        {'url': 'https://img.example/2.png'},
    ])])

    assert _media(item) == [('https://img.example/1.png', 'image'), ('https://img.example/2.png', 'image')]


def test_an_empty_images_list_falls_back_to_image_url(feed_generator, comic_info):
    [item] = _written_items(feed_generator, comic_info, [
        _strip_entry(6, images=[], image_url='https://img.example/single.gif'),
    ])

    assert _media(item) == [('https://img.example/single.gif', 'image')]


def test_an_item_without_an_image_gets_no_media_elements(feed_generator, comic_info):
    [item] = _written_items(feed_generator, comic_info, [_strip_entry(6)])

    assert [el for el in item.iter() if str(el.tag).startswith(f'{{{MEDIA_NS}}}')] == []


@pytest.mark.parametrize('fields', [
    {'image': 'https://img.example/a.jpg'},
    {'image_url': 'https://img.example/b.jpg'},
    {'images': [{'url': 'https://img.example/c1.png'}, {'url': 'https://img.example/c2.png'}]},
], ids=['image', 'image_url', 'images'])
def test_media_content_names_exactly_the_images_the_description_shows(feed_generator, comic_info, fields):
    [item] = _written_items(feed_generator, comic_info, [_strip_entry(6, **fields)])

    assert [url for url, _ in _media(item)] == _description_images(item)


def test_an_image_url_with_an_ampersand_round_trips(feed_generator, comic_info):
    url = 'https://featureassets.gocomics.com/assets/abc?optimizer=image&width=2800&quality=85'
    [item] = _written_items(feed_generator, comic_info, [_strip_entry(6, image_url=url)])

    assert _media(item) == [(url, 'image')]
    xml = (feed_generator.output_dir / f"{comic_info['slug']}.xml").read_text()
    assert f'url="{url.replace("&", "&amp;")}"' in xml


def test_the_feed_declares_the_media_namespace_and_feedparser_reads_the_images(feed_generator, comic_info):
    feed_generator.generate_feed(comic_info, [
        _strip_entry(6, images=[{'url': 'https://img.example/p1.png'}, {'url': 'https://img.example/p2.png'}]),
    ])
    path = feed_generator.output_dir / f"{comic_info['slug']}.xml"

    assert etree.parse(str(path)).getroot().nsmap.get('media') == MEDIA_NS
    [entry] = feedparser.parse(str(path)).entries
    assert [m['url'] for m in entry.media_content] == ['https://img.example/p1.png', 'https://img.example/p2.png']


def test_media_urls_names_the_strip_and_leaves_a_prebuilt_description_alone(feed_generator, comic_info):
    """The Far Side writes its own description HTML and names its image in media_urls."""
    prebuilt = ('<div style="text-align: center;"><img src="https://img.example/fs.jpg" alt="The Far Side comic"/></div>'
                '<p>caption</p>')
    entry = feed_generator.create_entry(comic_info, _strip_entry(
        6, description=prebuilt, media_urls=['https://img.example/fs.jpg']))

    assert entry.description() == prebuilt
    [item] = _written_items(feed_generator, comic_info, [_strip_entry(
        6, description=prebuilt, media_urls=['https://img.example/fs.jpg'])])
    assert _media(item) == [('https://img.example/fs.jpg', 'image')]


def test_media_content_leaves_the_description_html_byte_identical(feed_generator, comic_info):
    """Pinned from the generator before media:content existed (R5)."""
    gallery = feed_generator.create_entry(comic_info, _strip_entry(6, images=[
        {'url': 'https://img.example/a.png', 'alt': 'Test Comic - Panel 1'},
        {'url': 'https://img.example/b.png', 'alt': 'Test Comic - Panel 2'},
    ]))
    single = feed_generator.create_entry(comic_info, _strip_entry(
        6, description='A caption', image_url='https://img.example/c.jpg'))

    assert gallery.description() == (
        '<div class="comic-gallery" style="text-align: center; max-width: 700px; margin: 10px auto;">\n'
        '<p style="margin-bottom: 15px; font-style: italic;">Comic strip for 2024-04-06</p>\n'
        '    <div class="comic-panel" style="margin: 15px 0;">\n'
        '        <img src="https://img.example/a.png" alt="Test Comic - Panel 1" style="max-width: 100%; height: auto;" loading="lazy">\n'
        '    </div>\n'
        '    <div class="comic-panel" style="margin: 15px 0;">\n'
        '        <img src="https://img.example/b.png" alt="Test Comic - Panel 2" style="max-width: 100%; height: auto;" loading="lazy">\n'
        '    </div>\n'
        '</div>\n'
    )
    assert single.description() == (
        '<div style="text-align: center; max-width: 700px; margin: 0 auto;">'
        '<img src="https://img.example/c.jpg" alt="Test Comic" style="max-width: 100%; height: auto;" loading="lazy">'
        '</div><p style="margin-top: 10px; font-style: italic;">A caption</p>'
    )
