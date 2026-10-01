"""Tests for the Far Side Daily Dose scraper.

Network-free: responses are built in memory and the session's fetch is
patched, so these tests never hit thefarside.com.
"""

from unittest.mock import patch

import requests


# A faithful slice of a thefarside.com/YYYY/MM/DD page: each Daily Dose comic
# is a data-id container around a js-comic card with a lazy-loaded image.
def dose_html(first_id):
    cards = ''.join(
        f'''
        <div data-id="{first_id + n}" data-position="{n}">
          <div class="card tfs-comic js-comic">
            <img class="img-fluid" data-src="https://featureassets.amuniversal.com/assets/img{first_id + n}">
            <figcaption class="figure-caption">Caption {first_id + n}</figcaption>
          </div>
        </div>'''
        for n in range(5)
    )
    return f'<html><body>{cards}</body></html>'


def make_response(requested_url, final_url, html):
    """A 200 response for `final_url`; a 302 hop if it differs from `requested_url`."""
    response = requests.Response()
    response.status_code = 200
    response._content = html.encode()
    response.url = final_url
    if final_url != requested_url:
        hop = requests.Response()
        hop.status_code = 302
        hop.url = requested_url
        response.history = [hop]
    return response


class TestScrapeDailyDose:
    def test_records_the_comics_shown_on_the_dated_page(self):
        from comiccaster.farside_scraper import FarsideScraper

        scraper = FarsideScraper('farside-daily')
        url = 'https://www.thefarside.com/2026/10/01'
        with patch.object(scraper.session, 'get',
                          return_value=make_response(url, url, dose_html(22802))):
            result = scraper.scrape_daily_dose('2026/10/01')

        assert [c['id'] for c in result['comics']] == ['22802', '22803', '22804', '22805', '22806']
        assert result['comics'][0]['url'] == 'https://www.thefarside.com/2026/10/01/0'

    def test_unpublished_date_is_not_recorded_as_the_latest_dose(self):
        """A date the site hasn't published yet 302s to the homepage, which
        shows the newest dose that IS out. Recording that would file
        yesterday's comics under today's date (2026-05-28, 2026-10-01)."""
        from comiccaster.farside_scraper import FarsideScraper

        scraper = FarsideScraper('farside-daily')
        url = 'https://www.thefarside.com/2026/10/01'
        homepage = make_response(url, 'https://www.thefarside.com/', dose_html(22797))
        with patch.object(scraper.session, 'get', return_value=homepage) as get:
            result = scraper.scrape_daily_dose('2026/10/01')

        assert result is None
        # Not a transient failure: retrying minutes later won't publish it.
        assert get.call_count == 1
