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
"""

import os

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


def build_chrome_driver(options: Options) -> webdriver.Chrome:
    """Build a Chrome WebDriver using a driver matched to the installed Chrome.

    Resolution order:
      1. ``CHROMEDRIVER_PATH`` env var -- emergency override, use that exact binary.
      2. ``webdriver_manager`` -- download/cache the right driver for the
         installed Chrome.

    Args:
        options: Pre-configured ``selenium.webdriver.chrome.options.Options``.

    Returns:
        An open ``webdriver.Chrome`` instance.
    """
    if 'CHROMEDRIVER_PATH' in os.environ:
        service = Service(executable_path=os.environ['CHROMEDRIVER_PATH'])
    else:
        service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)
