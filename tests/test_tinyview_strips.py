"""Tests for comiccaster/tinyview_strips.py, the one definition of a TinyView strip.

Until 2026-09-29 the scraper identified a strip by its date and kept any image
under that date's folder, so strips sharing a date collapsed into one record
carrying each other's panels (Kowal Comics' "Bella", five parts filed under
2026/09/24). The scraper and the feed generator now share this module's rules:
a strip is its own address, and an image belongs to it only when it sits under
that address's folder on the TinyView CDN.
"""

import pytest

from comiccaster.tinyview_strips import (
    canonical_strip_url,
    image_belongs_to_strip,
    strip_folder,
)

BELLA_4 = 'https://tinyview.com/kowal-comics/2026/09/24/bella-part-4-of-5'
CDN = 'https://cdn.tinyview.com'


class TestCanonicalStripUrl:
    @pytest.mark.parametrize('variant', [
        BELLA_4 + '?ref=home',
        BELLA_4 + '#comments',
        BELLA_4 + '/',
        BELLA_4 + '/?ref=home#comments',
    ])
    def test_query_fragment_and_trailing_slash_are_dropped(self, variant):
        assert canonical_strip_url(variant) == BELLA_4

    def test_canonical_address_is_unchanged(self):
        assert canonical_strip_url(BELLA_4) == BELLA_4
        assert canonical_strip_url(canonical_strip_url(BELLA_4)) == BELLA_4

    def test_host_case_is_normalized(self):
        assert canonical_strip_url(BELLA_4.replace('tinyview.com', 'TinyView.com')) == BELLA_4


class TestStripFolder:
    def test_folder_comes_from_the_address_not_the_feed_slug(self):
        # The fowl-language-tinyview feed is filed at fowl-language on TinyView.
        url = 'https://tinyview.com/fowl-language/2026/09/27/cutting-edge'
        assert strip_folder(url) == 'fowl-language/2026/09/27/cutting-edge'

    def test_folder_ignores_query_and_trailing_slash(self):
        assert strip_folder(BELLA_4 + '/?ref=home') == 'kowal-comics/2026/09/24/bella-part-4-of-5'

    @pytest.mark.parametrize('url', [
        'https://tinyview.com/kowal-comics/2026/09/24',          # date only, no strip
        'https://tinyview.com/kowal-comics',                     # series page
        'https://tinyview.com/kowal-comics/2026/9x/24/bella',    # malformed date
        'https://example.com/kowal-comics/2026/09/24/bella',     # not TinyView
        'https://tinyview.com/kowal-comics/2026/09/24/bella/extra',
        '',
    ])
    def test_non_strip_addresses_have_no_folder(self, url):
        assert strip_folder(url) is None


class TestImageBelongsToStrip:
    def test_fowl_language_panel_belongs_to_its_strip(self):
        strip = 'https://tinyview.com/fowl-language/2026/09/27/cutting-edge'
        image = f'{CDN}/fowl-language/2026/09/27/cutting-edge/cutting-edge-1.jpg'
        assert image_belongs_to_strip(image, strip)

    def test_same_date_sibling_panel_does_not_belong(self):
        image = f'{CDN}/kowal-comics/2026/09/24/bella-part-3-of-5/Kowal-Comics-Ep-34-Panel-1.jpg'
        assert not image_belongs_to_strip(image, BELLA_4)

    def test_cover_image_inside_the_strip_folder_belongs(self):
        image = (f'{CDN}/kowal-comics/2026/09/24/bella-part-4-of-5/'
                 'Tinyview_-_Kowal_Comics_-_Series_Cover_Image-6.png')
        assert image_belongs_to_strip(image, BELLA_4)

    def test_right_folder_on_another_host_does_not_belong(self):
        image = 'https://example.com/kowal-comics/2026/09/24/bella-part-4-of-5/panel-1.jpg'
        assert not image_belongs_to_strip(image, BELLA_4)

    def test_strip_whose_name_prefixes_a_sibling_does_not_claim_its_images(self):
        strip = 'https://tinyview.com/kowal-comics/2026/09/24/bella-part-1'
        image = f'{CDN}/kowal-comics/2026/09/24/bella-part-1-of-5/panel-1.jpg'
        assert not image_belongs_to_strip(image, strip)

    def test_image_query_string_does_not_matter(self):
        image = f'{CDN}/kowal-comics/2026/09/24/bella-part-4-of-5/panel-1.jpg?w=800'
        assert image_belongs_to_strip(image, BELLA_4)

    def test_nothing_belongs_to_an_address_that_is_not_a_strip(self):
        image = f'{CDN}/kowal-comics/2026/09/24/bella-part-4-of-5/panel-1.jpg'
        assert not image_belongs_to_strip(image, 'https://tinyview.com/kowal-comics/2026/09/24')
