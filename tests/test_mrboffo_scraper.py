"""Tests for the Mr. Boffo scraper.

Network-free: HTML is supplied inline and the fetch boundary is patched, so
these tests never hit mrboffo.com.
"""

from unittest.mock import patch


# A trimmed but faithful slice of mrboffo.com/daily.html: decorative button and
# header images plus the single daily strip image under images/daily/.
DAILY_HTML = '''
<html>
  <body>
    <table>
      <tr><td><img src="images/jmcomics.jpg" width="435" height="82"></td></tr>
      <tr><td><img src="images/buttons/boffo.jpg" alt="Mister Boffo Daily"></td></tr>
      <tr><td><img src="images/topline.gif"></td></tr>
      <tr><td><img border="0" src="images/daily/1987/011487.jpg"></td></tr>
      <tr><td><img src="images/Archives-Link.gif"></td></tr>
    </table>
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
        assert images[0]['url'] == 'http://www.mrboffo.com/images/daily/1987/011487.jpg'

    def test_absolutizes_relative_image_url(self):
        from comiccaster.mrboffo_scraper import MrBoffoScraper

        html = '<img src="images/daily/2026/today.jpg">'
        images = MrBoffoScraper().extract_images(html)

        assert images[0]['url'].startswith('http://www.mrboffo.com/images/daily/')

    def test_ignores_decorative_images(self):
        from comiccaster.mrboffo_scraper import MrBoffoScraper

        html = '''
        <img src="images/buttons/boffo.jpg" alt="button">
        <img src="images/topline.gif">
        '''
        assert MrBoffoScraper().extract_images(html) == []

    def test_returns_empty_when_no_daily_image(self):
        from comiccaster.mrboffo_scraper import MrBoffoScraper

        html = '<html><body><p>No comic today</p></body></html>'
        assert MrBoffoScraper().extract_images(html) == []

    def test_image_alt_defaults_to_comic_name(self):
        from comiccaster.mrboffo_scraper import MrBoffoScraper

        html = '<img src="images/daily/x.jpg">'
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
        assert result['image_url'] == 'http://www.mrboffo.com/images/daily/1987/011487.jpg'
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
