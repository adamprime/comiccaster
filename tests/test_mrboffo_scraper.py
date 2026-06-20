"""Tests for the Mr. Boffo scraper.

Network-free: HTML is supplied inline and the fetch boundary is patched, so
these tests never hit mrboffo.com.
"""

from unittest.mock import patch


# A faithful slice of mrboffocomics.com: a single daily strip image served over
# HTTPS at the fixed secure_daily.jpg path.
DAILY_HTML = '''
<html>
  <body>
    <a href="https://www.mrboffocomics.com/images/secure_daily.jpg">
      <img src="https://www.mrboffocomics.com/images/secure_daily.jpg" alt="daily">
    </a>
  </body>
</html>
'''


class TestMrBoffoScraperInterface:
    def test_inherits_from_base_scraper(self):
        from comiccaster.mrboffo_scraper import MrBoffoScraper
        from comiccaster.base_scraper import BaseScraper

        scraper = MrBoffoScraper()
        assert isinstance(scraper, BaseScraper)
        assert scraper.get_source_name() == 'mrboffo'


class TestExtractImages:
    def test_extracts_only_the_daily_strip_image(self):
        """The page has many images; only the images/daily/ one is the comic."""
        from comiccaster.mrboffo_scraper import MrBoffoScraper

        scraper = MrBoffoScraper()
        images = scraper.extract_images(DAILY_HTML)

        assert len(images) == 1
        assert images[0]['url'] == 'https://www.mrboffocomics.com/images/secure_daily.jpg'

    def test_absolutizes_relative_image_url(self):
        from comiccaster.mrboffo_scraper import MrBoffoScraper

        html = '<img src="images/secure_daily.jpg">'
        images = MrBoffoScraper().extract_images(html)

        assert images[0]['url'] == 'https://www.mrboffocomics.com/images/secure_daily.jpg'

    def test_ignores_decorative_images(self):
        from comiccaster.mrboffo_scraper import MrBoffoScraper

        html = '''
        <img src="images/header.gif" alt="banner">
        <img src="images/misterboffo.gif">
        '''
        assert MrBoffoScraper().extract_images(html) == []

    def test_returns_empty_when_no_daily_image(self):
        from comiccaster.mrboffo_scraper import MrBoffoScraper

        html = '<html><body><p>No comic today</p></body></html>'
        assert MrBoffoScraper().extract_images(html) == []

    def test_image_alt_defaults_to_comic_name(self):
        from comiccaster.mrboffo_scraper import MrBoffoScraper

        html = '<img src="images/secure_daily.jpg">'
        images = MrBoffoScraper().extract_images(html)
        assert images[0]['alt'] == 'Mr. Boffo'


class TestScrapeComic:
    def test_returns_standardized_result(self):
        from comiccaster.mrboffo_scraper import MrBoffoScraper

        scraper = MrBoffoScraper()
        with patch.object(scraper, 'fetch_comic_page', return_value=DAILY_HTML):
            result = scraper.scrape_comic()

        assert result is not None
        assert result['source'] == 'mrboffo'
        assert result['image_count'] == len(result['images'])
        assert result['image_count'] == 1
        # Single-image convenience field (from BaseScraper.build_comic_result).
        assert result['image_url'] == 'https://www.mrboffocomics.com/images/secure_daily.jpg'
        assert result['url'] == MrBoffoScraper.DAILY_URL

    def test_returns_none_when_fetch_fails(self):
        """Fail soft: a failed fetch must not raise."""
        from comiccaster.mrboffo_scraper import MrBoffoScraper

        scraper = MrBoffoScraper()
        with patch.object(scraper, 'fetch_comic_page', return_value=None):
            assert scraper.scrape_comic() is None

    def test_returns_none_when_page_has_no_strip(self):
        from comiccaster.mrboffo_scraper import MrBoffoScraper

        scraper = MrBoffoScraper()
        no_comic = '<html><body><p>Down for maintenance</p></body></html>'
        with patch.object(scraper, 'fetch_comic_page', return_value=no_comic):
            assert scraper.scrape_comic() is None

    def test_multiple_daily_images_uses_first_and_warns(self, caplog):
        """If the layout ever exposes 2+ secure_daily imgs, warn but publish first."""
        from comiccaster.mrboffo_scraper import MrBoffoScraper

        scraper = MrBoffoScraper()
        two = '''
        <img src="https://www.mrboffocomics.com/images/secure_daily.jpg">
        <img src="https://www.mrboffocomics.com/images/secure_daily_alt.jpg">
        '''
        with patch.object(scraper, 'fetch_comic_page', return_value=two):
            import logging
            with caplog.at_level(logging.WARNING):
                result = scraper.scrape_comic()

        assert result is not None
        # The scrape driver publishes images[0]; assert the first match wins.
        assert result['images'][0]['url'] == 'https://www.mrboffocomics.com/images/secure_daily.jpg'
        assert any('found 2' in r.message for r in caplog.records)
