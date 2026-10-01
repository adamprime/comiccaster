#!/usr/bin/env python3
"""
Comics Kingdom scraper - visits individual comic pages.
More reliable than trying to parse the favorites page.

Each comic's dated page embeds its own data (`__NEXT_DATA__`), which names the
post the page displays. That post -- its date, address and images -- is what
gets recorded; nothing is read from the rendered DOM.
"""

import sys
import os
import json
import re
import argparse
import pickle
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from comiccaster.comicskingdom_catalog import load_comicskingdom_catalog
from comiccaster.webdriver_setup import build_chrome_driver
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading


# Unit 1 instrumentation (2026-04-18). Timestamped log lines at every Chrome
# interaction boundary so we can see which call is hanging when the renderer
# timeout fires. Remove after Unit 3 lands.
# See docs/plans/2026-04-18-001-fix-comicskingdom-scraper-reliability-plan.md
_SCRAPE_CALL_COUNT = 0


def _log_timing(label):
    """Print a timestamped marker line. Instrumentation only; no behavior change."""
    now = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    print(f"[{now}] {label}")


def load_cookie_file_path():
    """Return the cookie pickle file path from $COMICSKINGDOM_COOKIE_FILE.

    Defaults to data/comicskingdom_cookies.pkl. Under Shape A profile-based
    auth this is the only piece of configuration the daily scrape needs;
    credentials are typed by the operator into the browser during reauth
    (CK's bot check rejects JS-injected fills) and are never read from env.
    """
    cookie_file = Path(os.environ.get(
        'COMICSKINGDOM_COOKIE_FILE', 'data/comicskingdom_cookies.pkl'
    ))
    print("✅ Loaded configuration from environment")
    print(f"   Cookie file: {cookie_file}")
    return cookie_file


def setup_driver(show_browser=False, use_profile=True):
    """Set up the Chrome driver.

    Defaults to use_profile=True (Shape A). Chrome launches with --user-data-dir
    pointing at ~/.comicskingdom_chrome_profile. The profile carries session
    cookies so the first request to CK arrives authenticated, which avoids the
    renderer timeout we used to hit on the first navigation
    (see docs/solutions/logic-errors/comicskingdom-hang-diagnosis.md).

    Pass use_profile=False to fall back to the legacy pickled-cookie flow
    (kept for rollback; expected to be removed once Shape A proves out).
    """
    options = Options()
    if not show_browser:
        options.add_argument('--headless=new')

    if use_profile:
        profile_dir = Path.home() / '.comicskingdom_chrome_profile'
        profile_dir.mkdir(parents=True, exist_ok=True)
        profile_dir.chmod(0o700)
        options.add_argument(f'--user-data-dir={profile_dir}')
        print(f"🔧 Using Chrome profile: {profile_dir}")

    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')

    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    _log_timing("setup_driver: webdriver.Chrome() START")
    driver = build_chrome_driver(options)
    _log_timing("setup_driver: webdriver.Chrome() END")

    # Set timeouts
    driver.set_page_load_timeout(30)
    driver.set_script_timeout(30)
    driver.implicitly_wait(10)

    # Set a standard user agent and unset the navigator.webdriver flag.
    driver.execute_cdp_cmd('Network.setUserAgentOverride', {
        "userAgent": 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    return driver


def save_cookies(driver, cookie_file):
    """Save authentication cookies to file."""
    cookies = driver.get_cookies()
    cookie_file.parent.mkdir(parents=True, exist_ok=True)
    with open(cookie_file, 'wb') as f:
        pickle.dump(cookies, f)
    print(f"✅ Cookies saved to {cookie_file}")


def load_cookies(driver, cookie_file):
    """Load saved cookies and add them to the driver."""
    if not cookie_file.exists():
        return False
    
    try:
        with open(cookie_file, 'rb') as f:
            cookies = pickle.load(f)
        
        # Navigate to site first
        _log_timing("load_cookies: driver.get(comicskingdom.com) START")
        driver.get("https://comicskingdom.com")
        _log_timing("load_cookies: driver.get(comicskingdom.com) END")
        time.sleep(2)

        # Add all cookies
        _log_timing("load_cookies: add_cookie loop START")
        for cookie in cookies:
            try:
                driver.add_cookie(cookie)
            except Exception as e:
                pass
        _log_timing("load_cookies: add_cookie loop END")

        print(f"✅ Loaded cookies from {cookie_file}")
        return True
    except Exception as e:
        print(f"❌ Error loading cookies: {e}")
        return False


def is_authenticated(driver):
    """Check if the current session is authenticated.

    Reports *why* it failed. The two failure modes need opposite responses and
    used to be indistinguishable in the log -- on 2026-08-07 the exception was
    caught and discarded, so a transient navigation error printed "please run
    reauth script" and looked identical to a dead session. No reauth was
    needed; the next run succeeded on its own.
    """
    try:
        _log_timing("is_authenticated: driver.get(/favorites) START")
        driver.get("https://comicskingdom.com/favorites")
        _log_timing("is_authenticated: driver.get(/favorites) END")
        time.sleep(2)

        if 'login' in driver.current_url:
            print("   ↳ redirected to the login page — the session is not "
                  "authenticated. A reauth is what fixes this.")
            return False

        return True
    except Exception as e:
        print(f"   ↳ navigation failed: {type(e).__name__}: {e}")
        print("   ↳ this is a browser/driver error, not a rejected session — "
              "a retry usually clears it.")
        return False


def authenticate_with_cookies(driver, cookie_file, use_profile=False):
    """Authenticate either via a persistent Chrome profile or pickled cookies.

    When use_profile is True, Chrome is expected to have launched with
    --user-data-dir pointing at ~/.comicskingdom_chrome_profile. The session
    cookies are already in the browser, so we skip the pickled-cookie load
    entirely and just verify authentication. This is the Shape A path; see
    docs/solutions/logic-errors/comicskingdom-hang-diagnosis.md.

    When use_profile is False, use the legacy pickled-cookie flow.
    """
    if use_profile:
        profile_dir = Path.home() / '.comicskingdom_chrome_profile'
        cookies_db = profile_dir / 'Default' / 'Cookies'

        if is_authenticated(driver):
            print("✅ Successfully authenticated with Chrome profile!")
            return True

        # Distinguish "profile never seeded" from "profile has a dead session".
        # Chrome creates Default/Cookies on the first authenticated navigation,
        # so its absence is a reliable signal that reauth has never run.
        if not cookies_db.exists():
            print(f"⚠️  Chrome profile at {profile_dir} has no stored session.")
            print("   Run scripts/reauth_comicskingdom.py to seed it.")
            return False

        print("❌ Authentication failed - please run reauth script")
        return False

    # Check cookie age
    if cookie_file.exists():
        cookie_age_days = (datetime.now() - datetime.fromtimestamp(
            cookie_file.stat().st_mtime
        )).days
        print(f"📅 Cookie file is {cookie_age_days} days old")

        if cookie_age_days > 60:
            print(f"⚠️  Cookies are old. Recommend re-authentication.")

    # Try to load existing cookies
    if load_cookies(driver, cookie_file):
        print("🔍 Checking if cookies are still valid...")

        if is_authenticated(driver):
            print("✅ Successfully authenticated with saved cookies!")
            return True
        else:
            print("⚠️  Saved cookies are expired or invalid")

    print("❌ Authentication failed - please run reauth script")
    return False


def wait_for_manual_login(driver):
    """Open the CK login page, confirm the form is present, and wait for the
    operator to complete login in a visible browser window.

    Polls for a redirect away from /login (up to 120 x 5s = 10 minutes).
    """
    print("\n" + "="*80)
    print("COMICS KINGDOM LOGIN")
    print("="*80)
    print("Navigating to login page...")

    driver.get("https://comicskingdom.com/login")
    time.sleep(5)

    try:
        # Confirm the login form is present before handing off to the operator
        username_field = None
        selectors = [
            (By.NAME, "username"),
            (By.ID, "username"),
            (By.CSS_SELECTOR, "input[name='username']"),
        ]

        for selector_type, selector_value in selectors:
            try:
                username_field = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((selector_type, selector_value))
                )
                break
            except:
                continue

        if not username_field:
            print("❌ Could not find username field")
            return False

        print("\n" + "="*80)
        print("⏸️  PLEASE LOG IN MANUALLY IN THE BROWSER WINDOW")
        print("="*80)
        print("Instructions:")
        print("  1. Click into the Username field and type (or paste) your username.")
        print("  2. Click into the Password field and type (or paste) your password.")
        print("  3. Click the 'Log in' button.")
        print("  4. If an image challenge appears, complete it.")
        print("  5. Wait for the page to redirect away from /login.")
        print("\nNote: CK uses an invisible reCAPTCHA — there is no checkbox to tick.")
        print("JS-injected credential fills are rejected by their bot check, which")
        print("is why you have to type or paste directly.")
        print("\n⏳ Waiting for you to complete login...")
        print("="*80 + "\n")

        # Wait for navigation away from login page
        for i in range(120):  # Wait up to 2 minutes
            time.sleep(1)
            current_url = driver.current_url

            if 'login' not in current_url:
                print(f"\n✅ Login successful! Redirected to: {current_url}")
                time.sleep(3)  # Give page time to fully load
                return True

            if (i+1) % 15 == 0:
                print(f"  ...still waiting ({i+1}/120 seconds)...")

        print("\n❌ Timeout waiting for login")
        return False

    except Exception as e:
        print(f"❌ Login failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def load_comics_catalog():
    """Load Comics Kingdom comics from the daily and political catalogs."""
    ck_comics = load_comicskingdom_catalog()

    print(f"📚 Loaded {len(ck_comics)} Comics Kingdom comics from catalog (daily + political)")
    return ck_comics


_NEXT_DATA = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)
_YMD = re.compile(r'\d{4}-\d{2}-\d{2}')


def extract_displayed_post(page_source, source_slug, date_str):
    """Return the post a comic's dated page displays, or why it shows none.

    The page embeds its data in ``__NEXT_DATA__``. Under
    ``props.pageProps.fallback`` it keeps the ``ck_comic`` query it ran for
    this page: the posts of ``ck_feature:"<source slug>"`` on or before
    ``before_ymd:"<date>"``, newest first. The first of them is the post on
    screen. The query is matched on those two fields only -- never on
    ``per_page``, which is 10 for strips and 1 for episodic comics -- and never
    on the post's own slug, because vintage posts carry another feature's
    prefix (``beetle-bailey-1-1967-10-01`` belongs to ``beetle-bailey-vintage``).

    Returns ``(post, None)`` or ``(None, reason)``. ``post`` holds
    ``post_date`` (YYYY-MM-DD, cross-checked against the date in the post's
    link), ``post_url`` (the link, on comicskingdom.com) and ``image_urls``:
    the post's panels in order, else its single image, never the ``featured``
    thumbnail. A post dated after ``date_str`` (premium early access) is
    rejected. Pure: no driver, no network, and nothing is read from
    ``pageProps.session``.
    """
    match = _NEXT_DATA.search(page_source or '')
    if not match:
        return None, 'no __NEXT_DATA__'
    try:
        next_data = json.loads(match.group(1))
    except ValueError:
        return None, 'unreadable __NEXT_DATA__'

    page_props = (next_data.get('props') or {}).get('pageProps') or {}
    fallback = page_props.get('fallback') or {}
    wanted = (
        'postType:"ck_comic"',
        f'ck_feature:"{source_slug}"',
        f'before_ymd:"{date_str}"',
    )
    key = next((k for k in fallback if all(w in k for w in wanted)), None)
    if key is None:
        return None, f'no query for {source_slug} on {date_str}'

    value = fallback[key]
    posts = value.get('result') if isinstance(value, dict) else value
    if not posts:
        return None, 'empty result'
    post = posts[0]

    post_date = str(post.get('date') or '')[:10]
    if not _YMD.fullmatch(post_date):
        return None, 'no post date'
    link = urlsplit(post.get('link') or '')
    link_date = link.path.rstrip('/').rsplit('/', 1)[-1]
    if link_date != post_date:
        return None, f'date mismatch: post {post_date}, link {link_date or "none"}'
    if post_date > date_str:
        return None, f'early access: post dated {post_date}, after {date_str}'

    assets = post.get('assets') or {}
    image_urls = [p.get('url') for p in assets.get('panels') or [] if p.get('url')]
    single = (assets.get('single') or {}).get('url')
    if not image_urls and single:
        image_urls = [single]
    if not image_urls:
        return None, 'no images'

    if link.netloc == 'wp.comicskingdom.com':
        link = link._replace(netloc='comicskingdom.com')
    return {
        'post_date': post_date,
        'post_url': urlunsplit(link),
        'image_urls': image_urls,
    }, None


_DATA_FILE = re.compile(r'comicskingdom_(\d{4}-\d{2}-\d{2})\.json')


def load_recorded_posts(data_dir, date_str):
    """Return the (slug, post_date) pairs saved in data files dated before ``date_str``.

    Used only to count repeats in the run's totals. Records saved before post
    dates were recorded carry none and add nothing; an unreadable file is
    skipped.
    """
    recorded = set()
    for path in Path(data_dir).glob('comicskingdom_*.json'):
        match = _DATA_FILE.fullmatch(path.name)
        if not match or match.group(1) >= date_str:
            continue
        try:
            records = json.loads(path.read_text())
            recorded.update(
                (r.get('slug'), r['post_date']) for r in records if 'post_date' in r
            )
        except Exception:
            continue
    return recorded


def scrape_comic_page(driver, comic_slug, date_str, name, feed_slug=None):
    """Record the post a comic's page displays for ``date_str``.

    ``comic_slug`` is the identifier Comics Kingdom serves the strip under;
    ``feed_slug`` is the identifier ComicCaster files it under. They differ only
    when two sources run the same comic and each run needs its own feed -- see
    the `source_slug` note in scrape_all_comics. ``name`` is the catalog name.

    Returns ``(record, None)``, or ``(None, reason)`` when the page shows no
    post. ``date`` and ``url`` are the requested night and page; ``post_date``
    and ``post_url`` are the displayed post's own.
    """
    global _SCRAPE_CALL_COUNT
    _SCRAPE_CALL_COUNT += 1
    url = f"https://comicskingdom.com/{comic_slug}/{date_str}"

    try:
        if _SCRAPE_CALL_COUNT <= 5:
            _log_timing(f"scrape_comic_page[{_SCRAPE_CALL_COUNT}]: driver.get({comic_slug}) START")
        driver.get(url)
        if _SCRAPE_CALL_COUNT <= 5:
            _log_timing(f"scrape_comic_page[{_SCRAPE_CALL_COUNT}]: driver.get({comic_slug}) END")
        time.sleep(2)

        post, reason = extract_displayed_post(driver.page_source, comic_slug, date_str)
    except Exception as e:
        print(f"  ⚠️  Error scraping {comic_slug}: {e}")
        return None, f"error ({type(e).__name__})"

    if post is None:
        return None, reason

    record = {
        'name': name,
        'slug': feed_slug or comic_slug,
        'date': date_str,
        'url': url,
        'source': 'comicskingdom',
        'post_date': post['post_date'],
        'post_url': post['post_url'],
    }
    image_urls = post['image_urls']
    if len(image_urls) == 1:
        record['image_url'] = image_urls[0]
    else:
        record['image_urls'] = image_urls
    return record, None


def scrape_all_comics(driver, comics, date_str, recorded_posts=None):
    """Record every comic's displayed post, then print the run's totals.

    Every displayed post is recorded, a repeat of an older post included; its
    ``post_date`` tells the two apart. ``recorded_posts`` holds the
    (slug, post_date) pairs earlier data files already hold
    (load_recorded_posts): a record matching one counts as a repeat. A post
    dated before tonight can still be new -- late uploaders' strips first
    appear the night after their post date.
    """
    recorded_posts = recorded_posts or set()
    print(f"\n{'='*80}")
    print(f"Scraping {len(comics)} Comics Kingdom comics for {date_str}")
    print("="*80)

    results = []
    repeats = 0
    not_recorded = []

    for i, comic in enumerate(comics, 1):
        slug = comic['slug']
        # `source_slug` is the path Comics Kingdom serves this comic at, when it
        # differs from the slug we file the feed under. Needed when GoComics and
        # Comics Kingdom run the same comic at different points in its history:
        # each run is a distinct work and needs its own feed, but upstream still
        # only knows the one path. Defaults to slug, so 155 of 156 entries are
        # unaffected.
        source_slug = comic.get('source_slug') or slug
        print(f"[{i}/{len(comics)}] Scraping {comic['name']} ({slug})...")

        record, reason = scrape_comic_page(
            driver, source_slug, date_str, name=comic['name'], feed_slug=slug
        )

        if record:
            results.append(record)
            if (slug, record['post_date']) in recorded_posts:
                repeats += 1
        else:
            not_recorded.append((slug, reason))

        # Small delay between requests
        time.sleep(0.5)

    # Greppable totals. Repeats are a subset of Recorded.
    print(f"\nRecorded: {len(results)} of {len(comics)}")
    print(f"Repeats: {repeats}")
    print(f"Not recorded: {len(not_recorded)}")
    for slug, reason in not_recorded:
        print(f"  - {slug}: {reason}")
    return results


def main():
    parser = argparse.ArgumentParser(
        description='Comics Kingdom scraper - visits individual comic pages'
    )
    parser.add_argument(
        '--date',
        help='Date in YYYY-MM-DD format (defaults to today). A past date shows the '
             'post on or before it, and records carry that post\'s own date, so '
             'backfilling a missed night on or after the first post-dated data file '
             'is safe. A missed night from before then stays a gap until it leaves '
             'the 90-date window: backfilling it would re-send strips older records '
             'saved a night late. Never overwrite an existing data file: records '
             'saved before #216 still rest on first sighting (CONCEPTS.md "Strip '
             'identity").',
    )
    parser.add_argument('--output-dir', default='data', help='Output directory for JSON files')
    parser.add_argument('--show-browser', action='store_true', help='Show browser window')
    parser.add_argument(
        '--no-profile',
        action='store_false',
        dest='use_profile',
        default=True,
        help='Disable the persistent Chrome profile and fall back to the '
             'legacy pickled-cookie flow (for debugging / rollback only; '
             'default is profile-based auth).',
    )

    args = parser.parse_args()

    date_str = args.date or datetime.now().strftime('%Y-%m-%d')
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cookie_file = load_cookie_file_path()

    # Load comics catalog
    comics = load_comics_catalog()

    # Posts earlier nights already saved, so the totals can count repeats
    recorded_posts = load_recorded_posts(output_dir, date_str)

    # Setup Chrome
    driver = setup_driver(show_browser=args.show_browser, use_profile=args.use_profile)

    try:
        # Authenticate, with one retry on a *fresh browser*.
        #
        # Chrome auto-updates, and the first launch afterwards migrates the
        # profile (`Last Version` in the profile dir is how Chrome detects the
        # bump). That first launch is unreliable: 2026-08-05 landed on the
        # login page, 2026-08-07 threw on navigation. Both self-healed on the
        # next run, and both cost a whole day of Comics Kingdom.
        #
        # The retry rebuilds the driver rather than just re-navigating, because
        # what recovers is the *next launch* — by then migration is done. A
        # re-navigation in the same session would not have fixed either day.
        if not authenticate_with_cookies(driver, cookie_file, use_profile=args.use_profile):
            print("🔄 Retrying authentication once with a fresh browser "
                  "(recovers the first launch after a Chrome update)...")
            try:
                driver.quit()
            except Exception:
                pass
            driver = setup_driver(
                show_browser=args.show_browser, use_profile=args.use_profile
            )
            if not authenticate_with_cookies(
                driver, cookie_file, use_profile=args.use_profile
            ):
                print("❌ Authentication failed (after retry)")
                driver.quit()
                return 1
            print("✅ Authentication succeeded on retry")
        
        # Scrape all comics
        results = scrape_all_comics(driver, comics, date_str, recorded_posts)
        
        if not results:
            print("⚠️  No comics scraped")
            driver.quit()
            return 1
        
        # Save results
        output_file = output_dir / f'comicskingdom_{date_str}.json'
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n{'='*80}")
        print(f"✅ SUCCESS! Scraped {len(results)} comics for {date_str}")
        print(f"💾 Saved to {output_file}")
        print(f"{'='*80}\n")
        
        driver.quit()
        return 0
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        driver.quit()
        return 1


if __name__ == "__main__":
    sys.exit(main())
