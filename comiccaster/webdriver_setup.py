"""Shared Chrome WebDriver setup that auto-resolves a matching ChromeDriver.

Production scrapers historically relied on a manually pinned
``~/bin/chromedriver`` binary on ``PATH``. That binary broke every time
Chrome auto-updated past the pinned major version (see incident
2026-06-09: Chrome 149 vs. ChromeDriver 147 -- took down Comics Kingdom,
TinyView, and Far Side's New Stuff scrape until the binary was swapped
by hand).

This helper centralises driver instantiation and defaults to
``webdriver_manager``, which downloads and caches a ChromeDriver matching
the installed Chrome on demand. The result is that the next Chrome major
bump no longer requires manual intervention.

``CHROMEDRIVER_PATH`` remains an emergency override: if it is set, that
exact binary wins. Useful if webdriver-manager itself ever fails (network
hiccup, upstream outage) and we need to pin to a known-good driver
quickly.

It also presents headless sessions as regular Chrome. Headless Chrome
announces itself as ``HeadlessChrome/<version>`` and CDN bot shields refuse
that token outright: on 2026-09-05 GoComics' Bunny Shield challenge never
cleared for it, while the same browser with the ``Headless`` prefix dropped
cleared in under two seconds (issue #198). Only the token is changed -- the
real Chrome version is kept, so the string stays truthful across updates.
"""

import logging
import os

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger(__name__)

_HEADLESS_UA_TOKEN = 'HeadlessChrome/'


def regular_chrome_user_agent(user_agent: str) -> str:
    """Return ``user_agent`` with the headless marker dropped, version intact."""
    return user_agent.replace(_HEADLESS_UA_TOKEN, 'Chrome/')


def _present_as_regular_chrome(driver: webdriver.Chrome) -> None:
    """Override a headless session's user-agent so it reads as regular Chrome.

    No-op for headed sessions. A failure here is logged, not raised -- most
    sources do not care, and the scrape should still be attempted.
    """
    try:
        user_agent = driver.execute_script('return navigator.userAgent')
        if _HEADLESS_UA_TOKEN not in user_agent:
            return
        driver.execute_cdp_cmd(
            'Network.setUserAgentOverride',
            {'userAgent': regular_chrome_user_agent(user_agent)},
        )
    except Exception as exc:  # noqa: BLE001 - never let this abort a scrape
        logger.warning(
            "Could not normalise the headless user-agent (%s); "
            "bot-shielded sources such as GoComics may refuse this session",
            exc,
        )


def build_chrome_driver(options: Options) -> webdriver.Chrome:
    """Build a Chrome WebDriver using a driver matched to the installed Chrome.

    Resolution order:
      1. ``CHROMEDRIVER_PATH`` env var -- emergency override, use that exact binary.
      2. ``webdriver_manager`` -- download/cache the right driver for the
         installed Chrome.

    Args:
        options: Pre-configured ``selenium.webdriver.chrome.options.Options``.

    Returns:
        An open ``webdriver.Chrome`` instance. Headless sessions present a
        regular Chrome user-agent (see module docstring).
    """
    if 'CHROMEDRIVER_PATH' in os.environ:
        service = Service(executable_path=os.environ['CHROMEDRIVER_PATH'])
    else:
        service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    _present_as_regular_chrome(driver)
    return driver
