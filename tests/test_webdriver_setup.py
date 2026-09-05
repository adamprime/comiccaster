"""Tests for the shared Chrome driver builder in ``comiccaster.webdriver_setup``.

Headless Chrome announces itself as ``HeadlessChrome/<version>``. On
2026-09-05 GoComics put a Bunny Shield bot challenge in front of its pages
that never clears for that token, while the identical browser passing a
plain ``Chrome/<version>`` user-agent clears it in under two seconds. The
builder therefore presents headless sessions as regular Chrome, keeping the
real version so the string stays truthful across Chrome updates.
"""

from unittest.mock import patch

from selenium.webdriver.chrome.options import Options

from comiccaster import webdriver_setup
from comiccaster.webdriver_setup import build_chrome_driver, regular_chrome_user_agent

HEADLESS_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) HeadlessChrome/152.0.0.0 Safari/537.36"
)
REGULAR_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
)


class TestRegularChromeUserAgent:
    def test_drops_headless_token_but_keeps_version(self):
        assert regular_chrome_user_agent(HEADLESS_UA) == REGULAR_UA

    def test_regular_user_agent_is_unchanged(self):
        assert regular_chrome_user_agent(REGULAR_UA) == REGULAR_UA


def _build_with_reported_ua(reported_ua, cdp_side_effect=None):
    """Build a driver with Chrome and ChromeDriverManager mocked out."""
    with patch.object(webdriver_setup, "ChromeDriverManager") as manager, \
            patch.object(webdriver_setup.webdriver, "Chrome") as chrome:
        manager.return_value.install.return_value = "/fake/chromedriver"
        driver = chrome.return_value
        driver.execute_script.return_value = reported_ua
        if cdp_side_effect is not None:
            driver.execute_cdp_cmd.side_effect = cdp_side_effect
        result = build_chrome_driver(Options())
    return result


class TestBuildChromeDriverUserAgent:
    def test_headless_session_presents_as_regular_chrome(self):
        driver = _build_with_reported_ua(HEADLESS_UA)

        driver.execute_cdp_cmd.assert_called_once_with(
            "Network.setUserAgentOverride", {"userAgent": REGULAR_UA}
        )

    def test_headed_session_is_left_alone(self):
        driver = _build_with_reported_ua(REGULAR_UA)

        driver.execute_cdp_cmd.assert_not_called()

    def test_override_failure_still_returns_driver(self, caplog):
        driver = _build_with_reported_ua(
            HEADLESS_UA, cdp_side_effect=RuntimeError("CDP unavailable")
        )

        assert driver is not None
        assert "user-agent" in caplog.text.lower()
