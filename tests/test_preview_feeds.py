"""Tests for scripts/preview_feeds.py, the visual check for generated feed XML.

Before a feed change ships, the operator looks at the raw XML: that every item
has its guid, title, date and link, that each strip shows its own images, and
which items are new or changed against what is already published. These tests
pin what the preview parses, flags and renders. They run offline on small
hand-written feeds.
"""

import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import preview_feeds as pf


def item(guid, title='Nick Anderson', date='Sun, 27 Sep 2026 23:59:59 +0000', images=('1.jpg',),
         link=None, extra=''):
    link = link or guid
    imgs = ''.join(f'&lt;img src="https://cdn.tinyview.com/s/{guid[-1]}/{i}"&gt;' for i in images)
    return (f'<item><title>{title}</title><link>{link}</link>'
            f'<description>&lt;p&gt;Caption&lt;/p&gt;{imgs}</description>'
            f'<guid isPermaLink="false">{guid}</guid>{extra}<pubDate>{date}</pubDate></item>')


def feed(*items, title='Nick Anderson - TinyView'):
    return ('<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
            f'<title>{title}</title><link>https://tinyview.com/nick-anderson</link>'
            '<description>Daily strip</description><category>TinyView</category>'
            '<lastBuildDate>Tue, 29 Sep 2026 18:43:00 +0000</lastBuildDate>'
            + ''.join(items) + '</channel></rss>')


A = 'https://tinyview.com/nick-anderson/2026/09/27/a'
B = 'https://tinyview.com/nick-anderson/2026/09/26/b'
C = 'https://tinyview.com/nick-anderson/2026/09/25/c'


class TestParseFeed:
    def test_channel_and_item_fields_are_read_as_written(self):
        parsed = pf.parse_feed(feed(item(A, extra='<category>Political Comics</category>')))
        assert parsed['channel']['title'] == 'Nick Anderson - TinyView'
        assert parsed['channel']['lastBuildDate'] == 'Tue, 29 Sep 2026 18:43:00 +0000'
        assert parsed['channel']['categories'] == ['TinyView']
        (only,) = parsed['items']
        assert only['guid'] == A
        assert only['guid_is_permalink'] == 'false'
        assert only['title'] == 'Nick Anderson'
        assert only['link'] == A
        assert only['pubDate'] == 'Sun, 27 Sep 2026 23:59:59 +0000'
        assert only['categories'] == ['Political Comics']

    def test_images_come_from_the_description_in_order(self):
        (only,) = pf.parse_feed(feed(item(A, images=('1.jpg', '2.jpg'))))['items']
        assert only['images'] == ['https://cdn.tinyview.com/s/a/1.jpg', 'https://cdn.tinyview.com/s/a/2.jpg']

    def test_missing_fields_read_as_empty(self):
        parsed = pf.parse_feed(feed('<item><title>No guid</title></item>'))
        (only,) = parsed['items']
        assert only['guid'] == '' and only['pubDate'] == '' and only['images'] == []

    def test_text_that_is_not_rss_is_an_error(self):
        with pytest.raises(ValueError):
            pf.parse_feed('<html><body>not a feed</body></html>')


class TestCheckFeed:
    def messages(self, xml, level=None):
        return [c['message'] for c in pf.check_feed(pf.parse_feed(xml)) if level in (None, c['level'])]

    def test_a_well_formed_feed_has_no_findings(self):
        assert self.messages(feed(item(A), item(B, date='Sat, 26 Sep 2026 23:59:59 +0000'))) == []

    def test_duplicate_guids_are_an_error(self):
        errors = self.messages(feed(item(A), item(A)), 'error')
        assert any('Duplicate guid' in m and A in m for m in errors)

    def test_missing_required_fields_are_errors(self):
        errors = self.messages(feed('<item><title>Only a title</title></item>'), 'error')
        assert any('guid' in m for m in errors)
        assert any('pubDate' in m for m in errors)
        assert any('link' in m for m in errors)

    def test_an_unparseable_date_is_an_error(self):
        errors = self.messages(feed(item(A, date='yesterday')), 'error')
        assert any('pubDate' in m and 'yesterday' in m for m in errors)

    def test_items_out_of_newest_first_order_are_a_warning(self):
        warnings = self.messages(feed(item(C, date='Fri, 25 Sep 2026 23:59:59 +0000'), item(A)), 'warning')
        assert any('newest-first' in m for m in warnings)

    def test_an_item_with_no_images_is_a_warning(self):
        warnings = self.messages(feed(item(A, images=())), 'warning')
        assert any('no images' in m and A in m for m in warnings)

    def test_an_empty_feed_is_a_warning(self):
        assert any('no items' in m for m in self.messages(feed(), 'warning'))


class TestCompare:
    def compare(self, current, reference):
        return pf.compare_feeds(pf.parse_feed(current), pf.parse_feed(reference))

    def test_items_are_marked_new_same_or_changed(self):
        result = self.compare(
            feed(item(A), item(B, title='Renamed'), item(C)),
            feed(item(B), item(C)),
        )
        assert result['items'][A]['status'] == 'new'
        assert result['items'][B] == {'status': 'changed', 'fields': ['title']}
        assert result['items'][C] == {'status': 'same', 'fields': []}
        assert result['missing'] == []

    def test_a_description_only_change_is_reported_separately(self):
        result = self.compare(feed(item(A, images=('1.jpg',))), feed(item(A, images=('1.jpg', '2.jpg'))))
        assert result['items'][A] == {'status': 'description', 'fields': ['description']}

    def test_items_only_in_the_reference_are_missing(self):
        result = self.compare(feed(item(A)), feed(item(A), item(B)))
        assert [m['guid'] for m in result['missing']] == [B]

    def test_counts_summarize_the_comparison(self):
        result = self.compare(feed(item(A), item(B, title='x')), feed(item(B), item(C)))
        assert result['counts'] == {'new': 1, 'changed': 1, 'description': 0, 'same': 0, 'missing': 1}


class TestLoadReference:
    def test_reference_directory_supplies_the_same_file_name(self, tmp_path):
        (tmp_path / 'ref').mkdir()
        (tmp_path / 'ref' / 'nick-anderson.xml').write_text('<rss/>')
        text, label = pf.load_reference(tmp_path / 'new' / 'nick-anderson.xml', str(tmp_path / 'ref'), tmp_path)
        assert text == '<rss/>' and 'nick-anderson.xml' in label

    def test_reference_directory_without_the_file_gives_nothing(self, tmp_path):
        (tmp_path / 'ref').mkdir()
        assert pf.load_reference(tmp_path / 'x.xml', str(tmp_path / 'ref'), tmp_path) == (None, None)

    def test_git_ref_supplies_the_published_feed(self, tmp_path):
        repo = tmp_path / 'repo'
        (repo / 'public' / 'feeds').mkdir(parents=True)
        (repo / 'public' / 'feeds' / 'nick-anderson.xml').write_text('<rss>committed</rss>')
        git = ['git', '-C', str(repo), '-c', 'user.name=t', '-c', 'user.email=t@t']
        subprocess.run(git[:3] + ['init', '-q'], check=True)
        subprocess.run(git + ['add', '.'], check=True)
        subprocess.run(git + ['commit', '-qm', 'feeds'], check=True)
        # A scratch copy anywhere is compared with public/feeds/<same name> at the ref.
        text, label = pf.load_reference(tmp_path / 'scratch' / 'nick-anderson.xml', 'HEAD', repo)
        assert text == '<rss>committed</rss>' and 'HEAD:public/feeds/nick-anderson.xml' in label

    def test_git_ref_without_the_feed_gives_nothing(self, tmp_path):
        repo = tmp_path / 'repo'
        repo.mkdir()
        subprocess.run(['git', '-C', str(repo), 'init', '-q'], check=True)
        assert pf.load_reference(tmp_path / 'brand-new.xml', 'HEAD', repo) == (None, None)


class TestRenderReport:
    def entry(self, xml, reference=None):
        parsed = pf.parse_feed(xml)
        comparison = pf.compare_feeds(parsed, pf.parse_feed(reference)) if reference else None
        return {'name': 'nick-anderson.xml', 'path': '/tmp/nick-anderson.xml', 'feed': parsed,
                'checks': pf.check_feed(parsed), 'comparison': comparison, 'reference': 'origin/main' if reference else None,
                'error': None}

    def test_each_item_shows_its_fields_and_images(self):
        html = pf.render_report([self.entry(feed(item(A, images=('1.jpg', '2.jpg'))))])
        assert A in html
        assert 'Sun, 27 Sep 2026 23:59:59 +0000' in html
        assert '<img' in html and 'https://cdn.tinyview.com/s/a/2.jpg' in html

    def test_feed_text_is_escaped_not_executed(self):
        html = pf.render_report([self.entry(feed(item(A, title='&lt;script&gt;alert(1)&lt;/script&gt;')))])
        assert '<script>alert(1)</script>' not in html
        assert '&lt;script&gt;alert(1)&lt;/script&gt;' in html

    def test_comparison_status_and_missing_items_are_shown(self):
        html = pf.render_report([self.entry(feed(item(A)), reference=feed(item(B)))])
        assert 'status-new' in html
        assert 'Missing' in html and B in html

    def test_a_feed_that_failed_to_parse_is_reported_not_raised(self):
        broken = {'name': 'bad.xml', 'path': '/tmp/bad.xml', 'feed': None, 'checks': [],
                  'comparison': None, 'reference': None, 'error': 'not RSS'}
        assert 'not RSS' in pf.render_report([broken])


class TestMain:
    def test_writes_one_report_for_several_feeds(self, tmp_path):
        feeds = tmp_path / 'feeds'
        feeds.mkdir()
        (feeds / 'a.xml').write_text(feed(item(A)))
        (feeds / 'b.xml').write_text(feed(item(B), title='Other'))
        out = tmp_path / 'report.html'
        assert pf.main([str(feeds), '-o', str(out)]) == 0
        html = out.read_text()
        assert 'a.xml' in html and 'b.xml' in html and A in html and B in html

    def test_against_a_directory_marks_changes(self, tmp_path):
        (tmp_path / 'new').mkdir()
        (tmp_path / 'old').mkdir()
        (tmp_path / 'new' / 'x.xml').write_text(feed(item(A), item(B)))
        (tmp_path / 'old' / 'x.xml').write_text(feed(item(B)))
        out = tmp_path / 'r.html'
        assert pf.main([str(tmp_path / 'new' / 'x.xml'), '--against', str(tmp_path / 'old'), '-o', str(out)]) == 0
        assert 'status-new' in out.read_text()

    def test_an_unreadable_feed_is_reported_and_the_rest_still_render(self, tmp_path):
        (tmp_path / 'good.xml').write_text(feed(item(A)))
        (tmp_path / 'bad.xml').write_text('not xml at all')
        out = tmp_path / 'r.html'
        assert pf.main([str(tmp_path / 'good.xml'), str(tmp_path / 'bad.xml'), '-o', str(out)]) == 0
        html = out.read_text()
        assert A in html and 'bad.xml' in html

    def test_no_feed_files_is_an_error(self, tmp_path):
        assert pf.main([str(tmp_path), '-o', str(tmp_path / 'r.html')]) == 2
