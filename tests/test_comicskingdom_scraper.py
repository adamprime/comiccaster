"""Smoke tests for scripts/comicskingdom_scraper_individual.py.

Unit 2 of the CK scraper reliability plan. Characterization tests that
lock current control-flow behavior so Unit 3's fix doesn't silently
regress adjacent paths. Intentionally narrow — no network, no real
browser, no end-to-end extraction; those are covered by manual
verification in Unit 3.
"""

import io
import json
import os
import pickle
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import comicskingdom_scraper_individual as cki


# --- Comics Kingdom page fixtures -------------------------------------------
#
# Shaped like the anonymous captures of 2026-10-01 (`props.pageProps.session`
# null). Query keys and asset URLs are copied verbatim from them. A logged-in
# page carries session.accessToken and session.user, so raw logged-in page
# source never becomes a fixture: anonymous_page() refuses any page that has a
# session.

UPLOADS = 'https://wp.comicskingdom.com/comicskingdom-redesign-uploads-production'

ZITS_QUERY = '#url:"/wp-json/wp/v2/posts",args:#sourceUrl:"https://wp.comicskingdom.com",postType:"ck_comic",per_page:10,order:"desc",date_inclusive:true,ck_feature:"zits",before_ymd:"2026-10-01",_embed:true,,'
ZITS_SLUG_QUERY = '#url:"/wp-json/wp/v2/posts",args:#sourceUrl:"https://wp.comicskingdom.com",slug:"zits-2026-10-01",postType:"ck_comic",_embed:true,,'
ZITS_FEATURE = '#url:"/wp-json/wp/v2/posts",args:#sourceUrl:"https://wp.comicskingdom.com",slug:"zits",postType:"ck_feature",_embed:true,,'
PROS_CONS_QUERY = '#url:"/wp-json/wp/v2/posts",args:#sourceUrl:"https://wp.comicskingdom.com",postType:"ck_comic",per_page:10,order:"desc",date_inclusive:true,ck_feature:"pros-cons",before_ymd:"2026-10-01",_embed:true,,'
POPEYE_QUERY = '#url:"/wp-json/wp/v2/posts",args:#sourceUrl:"https://wp.comicskingdom.com",postType:"ck_comic",per_page:1,order:"desc",date_inclusive:true,ck_feature:"eye-lie-popeye",before_ymd:"2026-10-01",_embed:true,,'
BUF_QUERY = '#url:"/wp-json/wp/v2/posts",args:#sourceUrl:"https://wp.comicskingdom.com",postType:"ck_comic",per_page:10,order:"desc",date_inclusive:true,ck_feature:"bringing-up-father",before_ymd:"2026-10-01",_embed:true,,'
BEETLE_QUERY = '#url:"/wp-json/wp/v2/posts",args:#sourceUrl:"https://wp.comicskingdom.com",postType:"ck_comic",per_page:10,order:"desc",date_inclusive:true,ck_feature:"beetle-bailey-vintage",before_ymd:"1967-10-01",_embed:true,,'
# Same shape, for the comic Comics Kingdom serves at /edge-city.
EDGE_CITY_QUERY = '#url:"/wp-json/wp/v2/posts",args:#sourceUrl:"https://wp.comicskingdom.com",postType:"ck_comic",per_page:10,order:"desc",date_inclusive:true,ck_feature:"edge-city",before_ymd:"2026-08-24",_embed:true,,'
APP_KEY = '#url:"/wp-json/headless-wp/v1/app",args:#sourceUrl:"https://wp.comicskingdom.com",,'

ZITS_1001_PANELS = [
    f'{UPLOADS}/2026/10/Y2taaXRzLUVORy02NjY5NDE1.jpg',
    f'{UPLOADS}/2026/10/Y2taaXRzLUVORy02NjY5NDE5.jpg',
]
POPEYE_PANELS = [
    f'{UPLOADS}/2026/05/Y2tFeWUgTGllIFBvcGV5ZS1FTkctNjExMzc5NQ.jpg',
    f'{UPLOADS}/2026/05/Y2tFeWUgTGllIFBvcGV5ZS1FTkctNjExMzgxNw.jpg',
    f'{UPLOADS}/2026/05/Y2tFeWUgTGllIFBvcGV5ZS1FTkctNjExMzgyNw.jpg',
    f'{UPLOADS}/2026/05/Y2tFeWUgTGllIFBvcGV5ZS1FTkctNjExMzg0MQ.jpg',
    f'{UPLOADS}/2026/05/Y2tFeWUgTGllIFBvcGV5ZS1FTkctNjExMzg0Nw.jpg',
    f'{UPLOADS}/2026/05/Y2tFeWUgTGllIFBvcGV5ZS1FTkctNjExMzgzOQ.jpg',
    f'{UPLOADS}/2026/05/Y2tFeWUgTGllIFBvcGV5ZS1FTkctNjExMzg1Mw.jpg',
    f'{UPLOADS}/2026/05/Y2tFeWUgTGllIFBvcGV5ZS1FTkctNjExMzgzNw.jpg',
    f'{UPLOADS}/2026/05/Y2tFeWUgTGllIFBvcGV5ZS1FTkctNjExMzc5Nw.jpg',
    f'{UPLOADS}/2026/05/Y2tFeWUgTGllIFBvcGV5ZS1FTkctNjExMzgxMw.jpg',
    f'{UPLOADS}/2026/05/Y2tFeWUgTGllIFBvcGV5ZS1FTkctNjExMzg1MQ.jpg',
    f'{UPLOADS}/2026/05/Y2tFeWUgTGllIFBvcGV5ZS1FTkctNjExMzgzNQ.jpg',
    f'{UPLOADS}/2026/05/Y2tFeWUgTGllIFBvcGV5ZS1FTkctNjExMzg0Mw.jpg',
    f'{UPLOADS}/2026/05/Y2tFeWUgTGllIFBvcGV5ZS1FTkctNjExMzg1OQ.jpg',
    f'{UPLOADS}/2026/05/Y2tFeWUgTGllIFBvcGV5ZS1FTkctNjExMzg0OQ.jpg',
    f'{UPLOADS}/2026/05/Y2tFeWUgTGllIFBvcGV5ZS1FTkctNjExMzg1NQ.jpg',
    f'{UPLOADS}/2026/05/Y2tFeWUgTGllIFBvcGV5ZS1FTkctNjExMzgyMw.jpg',
    f'{UPLOADS}/2026/05/Y2tFeWUgTGllIFBvcGV5ZS1FTkctNjExMzg1Nw.jpg',
    f'{UPLOADS}/2026/05/Y2tFeWUgTGllIFBvcGV5ZS1FTkctNjExMzg0NQ.jpg',
]


def _post(post_id, date, link, panels=(), single='', featured='', slug=None):
    """A ck_comic post as the page embeds it, trimmed to the fields that matter."""
    return {
        'id': post_id,
        'date': f'{date}T00:00:00',
        'link': link,
        'slug': slug or f"{link.rstrip('/').split('/')[-2]}-{date}",
        'title': {'rendered': date},
        'assets': {
            'featured': {'url': featured, 'width': 500, 'height': 500},
            'single': {'url': single, 'width': 2048 if single else 0},
            'panels': [{'url': u, 'width': 2047, 'height': 1301} for u in panels],
        },
    }


def _result(*posts):
    """A fallback query value: Comics Kingdom wraps the post list in `result`."""
    return {'result': list(posts), 'pageInfo': {'totalItems': len(posts)}, 'queriedObject': {}}


ZITS_1001 = _post(
    7693423, '2026-10-01', 'https://wp.comicskingdom.com/zits/2026-10-01',
    panels=ZITS_1001_PANELS,
    single=f'{UPLOADS}/2026/10/Y2taaXRzLUVORy02NjMyMjA3.jpg',
    featured=f'{UPLOADS}/2026/10/Y2taaXRzLUVORy02NjY5NDE1.jpg',
)
ZITS_0930 = _post(
    7693420, '2026-09-30', 'https://wp.comicskingdom.com/zits/2026-09-30',
    panels=[
        f'{UPLOADS}/2026/09/Y2taaXRzLUVORy02NjY5NDA3.jpg',
        f'{UPLOADS}/2026/09/Y2taaXRzLUVORy02NjY5NDA5.jpg',
        f'{UPLOADS}/2026/09/Y2taaXRzLUVORy02NjY5Mzk1.jpg',
    ],
    single=f'{UPLOADS}/2026/09/Y2taaXRzLUVORy02NjMyMjA5.jpg',
    featured=f'{UPLOADS}/2026/09/Y2taaXRzLUVORy02NjY5NDA3.jpg',
)
PROS_CONS_0731 = _post(
    249907, '2023-07-31', 'https://wp.comicskingdom.com/pros-cons/2023-07-31',
    panels=[
        f'{UPLOADS}/2023/07/Pros-amp-Cons.ENG_.2023-07-31.1.jpeg',
        f'{UPLOADS}/2023/07/Pros-amp-Cons.ENG_.2023-07-31.2.jpeg',
        f'{UPLOADS}/2023/07/Pros-amp-Cons.ENG_.2023-07-31.3.jpeg',
    ],
    single=f'{UPLOADS}/2023/07/Pros-amp-Cons.ENG_.2023-07-31.jpeg',
    featured=f'{UPLOADS}/2023/07/Pros-amp-Cons.ENG_.2023-07-31.1-500x500.jpeg',
)
POPEYE_EPISODE = _post(
    7550015, '2026-05-13', 'https://wp.comicskingdom.com/eye-lie-popeye/2026-05-13',
    panels=POPEYE_PANELS, single='', featured=POPEYE_PANELS[0],
)
BUF_1001 = _post(
    7693066, '2026-10-01', 'https://wp.comicskingdom.com/vintage/bringing-up-father/2026-10-01',
    panels=[],
    single=f'{UPLOADS}/2026/10/Y2tCcmluZ2luZyBVcCBGYXRoZXIgKFZpbnRhZ2UpLUVORy02NjAwMTE1.jpg',
    featured=f'{UPLOADS}/2026/10/Y2tCcmluZ2luZyBVcCBGYXRoZXIgKFZpbnRhZ2UpLUVORy02NjAwMTE1-500x500.jpg',
    slug='bringing-up-father-2026-10-01',
)
BEETLE_1967 = _post(
    5643991, '1967-10-01', 'https://wp.comicskingdom.com/vintage/beetle-bailey-vintage/1967-10-01',
    panels=[],
    single=f'{UPLOADS}/1967/10/Beetle-Bailey.ENG_.1967-10-01.jpeg',
    featured=f'{UPLOADS}/1967/10/Beetle-Bailey.ENG_.1967-10-01-500x500.jpeg',
    slug='beetle-bailey-1-1967-10-01',
)


def _next_data(fallback, page='/[...path]'):
    return {
        'props': {'pageProps': {'fallback': fallback, 'session': None, 'postType': 'ck_comic'}},
        'page': page,
    }


def _html(next_data):
    """Serialize a page the way Comics Kingdom embeds its data."""
    return (
        '<!DOCTYPE html><html><head><title>Comics Kingdom</title></head><body>'
        '<div id="__next"></div>'
        '<script id="__NEXT_DATA__" type="application/json">'
        + json.dumps(next_data)
        + '</script></body></html>'
    )


def anonymous_page(next_data):
    """The only way a fixture page is built: it must carry no session."""
    assert next_data['props']['pageProps']['session'] is None, (
        "fixture pages must be anonymous-shaped: a logged-in page carries "
        "session.accessToken and session.user"
    )
    return _html(next_data)


def ck_page(queries):
    """A dated comic page holding `queries`, plus the keys every page has."""
    fallback = dict(queries)
    fallback[APP_KEY] = {'settings': {}}
    fallback['@seo'] = {'title': 'Comics Kingdom'}
    return anonymous_page(_next_data(fallback))


ZITS_PAGE = ck_page({
    ZITS_SLUG_QUERY: {'result': ZITS_1001, 'pageInfo': {}, 'queriedObject': {}},
    ZITS_QUERY: _result(ZITS_1001, ZITS_0930),
    ZITS_FEATURE: {'result': {'id': 1, 'slug': 'zits', 'link': 'https://wp.comicskingdom.com/zits'}},
})
PROS_CONS_PAGE = ck_page({PROS_CONS_QUERY: _result(PROS_CONS_0731)})
POPEYE_PAGE = ck_page({POPEYE_QUERY: _result(POPEYE_EPISODE)})
BUF_PAGE = ck_page({BUF_QUERY: _result(BUF_1001)})
BEETLE_PAGE = ck_page({BEETLE_QUERY: _result(BEETLE_1967)})
NOT_FOUND_PAGE = anonymous_page(_next_data(
    {APP_KEY: {'settings': {}}, '@seo': {'title': 'Page not found'}}, page='/404'
))


# --- load_cookies -----------------------------------------------------------


class TestLoadCookies:
    def test_returns_true_when_pickle_valid(self, tmp_path):
        cookie_file = tmp_path / "cookies.pkl"
        cookies = [
            {"name": "session", "value": "abc", "domain": "comicskingdom.com"},
            {"name": "csrf", "value": "xyz", "domain": "comicskingdom.com"},
        ]
        with open(cookie_file, "wb") as f:
            pickle.dump(cookies, f)

        driver = MagicMock()
        assert cki.load_cookies(driver, cookie_file) is True
        driver.get.assert_called_once_with("https://comicskingdom.com")
        assert driver.add_cookie.call_count == len(cookies)

    def test_returns_false_when_file_missing(self, tmp_path):
        missing = tmp_path / "does-not-exist.pkl"
        driver = MagicMock()
        assert cki.load_cookies(driver, missing) is False
        driver.get.assert_not_called()
        driver.add_cookie.assert_not_called()

    def test_returns_false_on_unpickle_error(self, tmp_path, capsys):
        bad = tmp_path / "corrupt.pkl"
        bad.write_bytes(b"not a valid pickle")

        driver = MagicMock()
        assert cki.load_cookies(driver, bad) is False

        captured = capsys.readouterr()
        # Should surface a readable error line, not a raw traceback.
        assert "Error loading cookies" in captured.out
        assert "Traceback" not in captured.out


# --- is_authenticated -------------------------------------------------------


class TestIsAuthenticated:
    def test_true_when_redirected_off_login(self):
        driver = MagicMock()
        driver.current_url = "https://comicskingdom.com/favorites"
        assert cki.is_authenticated(driver) is True
        driver.get.assert_called_once_with("https://comicskingdom.com/favorites")

    def test_false_when_current_url_mentions_login(self):
        driver = MagicMock()
        driver.current_url = "https://comicskingdom.com/login?redirect=/favorites"
        assert cki.is_authenticated(driver) is False

    def test_false_when_driver_get_raises(self):
        driver = MagicMock()
        driver.get.side_effect = Exception("renderer timeout")
        assert cki.is_authenticated(driver) is False

    def test_navigation_error_is_reported_not_swallowed(self, capsys):
        """The 2026-08-07 failure was invisible because `e` was never printed.

        The log showed a START line, no END line, and "please run reauth
        script" -- which was wrong advice: no reauth was needed, the run
        self-healed. The exception text is the only thing that distinguishes
        a transient navigation error from a genuinely dead session.
        """
        driver = MagicMock()
        driver.get.side_effect = TimeoutError("renderer timeout")

        assert cki.is_authenticated(driver) is False

        out = capsys.readouterr().out
        assert "renderer timeout" in out
        assert "TimeoutError" in out

    def test_login_redirect_is_distinguished_from_navigation_error(self, capsys):
        """These need different operator responses, so they must read
        differently: a login redirect wants a reauth, a navigation error
        wants a retry."""
        driver = MagicMock()
        driver.current_url = "https://comicskingdom.com/login?redirect=/favorites"

        assert cki.is_authenticated(driver) is False

        out = capsys.readouterr().out.lower()
        assert "login" in out
        assert "navigation failed" not in out


# --- authenticate_with_cookies ----------------------------------------------


class TestAuthenticateWithCookies:
    def test_reauth_message_when_cookies_load_but_auth_fails(
        self, tmp_path, capsys
    ):
        # Cookies load successfully...
        cookie_file = tmp_path / "cookies.pkl"
        with open(cookie_file, "wb") as f:
            pickle.dump([{"name": "s", "value": "v", "domain": "comicskingdom.com"}], f)

        # ...but is_authenticated returns False (session rejected).
        driver = MagicMock()
        driver.current_url = "https://comicskingdom.com/login"

        assert cki.authenticate_with_cookies(driver, cookie_file) is False

        captured = capsys.readouterr()
        assert "Authentication failed - please run reauth script" in captured.out

    def test_returns_true_when_cookies_load_and_auth_succeeds(self, tmp_path):
        cookie_file = tmp_path / "cookies.pkl"
        with open(cookie_file, "wb") as f:
            pickle.dump([{"name": "s", "value": "v", "domain": "comicskingdom.com"}], f)

        driver = MagicMock()
        driver.current_url = "https://comicskingdom.com/favorites"

        assert cki.authenticate_with_cookies(driver, cookie_file) is True


class TestAuthenticateWithProfile:
    """use_profile=True branch of authenticate_with_cookies."""

    def test_returns_true_and_skips_load_cookies(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        # Populate the profile so "Default/Cookies" exists (authenticated state)
        (tmp_path / ".comicskingdom_chrome_profile" / "Default").mkdir(parents=True)
        (tmp_path / ".comicskingdom_chrome_profile" / "Default" / "Cookies").write_bytes(b"x")

        driver = MagicMock()
        driver.current_url = "https://comicskingdom.com/favorites"

        # Prove load_cookies is not called when use_profile=True
        with patch.object(cki, "load_cookies") as mock_load:
            result = cki.authenticate_with_cookies(driver, None, use_profile=True)

        assert result is True
        mock_load.assert_not_called()

    def test_empty_profile_emits_distinct_message(
        self, tmp_path, monkeypatch, capsys
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        # Profile dir does not exist at all → treated as empty

        driver = MagicMock()
        driver.current_url = "https://comicskingdom.com/login"

        result = cki.authenticate_with_cookies(driver, None, use_profile=True)
        assert result is False

        captured = capsys.readouterr()
        assert "has no stored session" in captured.out
        # Distinct from the legacy reauth message — critical for the
        # empty-vs-expired distinction.
        assert "Authentication failed - please run reauth script" not in captured.out

    def test_populated_profile_but_auth_fails_uses_legacy_message(
        self, tmp_path, monkeypatch, capsys
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        # Profile exists and has a Cookies file → treat as session-expired
        (tmp_path / ".comicskingdom_chrome_profile" / "Default").mkdir(parents=True)
        (tmp_path / ".comicskingdom_chrome_profile" / "Default" / "Cookies").write_bytes(b"x")

        driver = MagicMock()
        driver.current_url = "https://comicskingdom.com/login"

        result = cki.authenticate_with_cookies(driver, None, use_profile=True)
        assert result is False

        captured = capsys.readouterr()
        assert "Authentication failed - please run reauth script" in captured.out
        assert "has no stored session" not in captured.out

    def test_use_profile_false_preserves_legacy_behavior(self, tmp_path, capsys):
        # Legacy flow when use_profile=False should be identical to pre-Unit-3.
        cookie_file = tmp_path / "cookies.pkl"
        with open(cookie_file, "wb") as f:
            pickle.dump([{"name": "s", "value": "v", "domain": "comicskingdom.com"}], f)

        driver = MagicMock()
        driver.current_url = "https://comicskingdom.com/favorites"

        assert cki.authenticate_with_cookies(driver, cookie_file, use_profile=False) is True


# --- setup_driver -----------------------------------------------------------


class TestSetupDriver:
    def test_headless_when_show_browser_false(self):
        with patch.object(cki.webdriver, "Chrome") as chrome_cls:
            chrome_cls.return_value = MagicMock()
            # Pass use_profile=False so this test stays focused on the
            # headless flag and doesn't touch the user's real $HOME.
            cki.setup_driver(show_browser=False, use_profile=False)

            args, kwargs = chrome_cls.call_args
            options = kwargs["options"]
            assert "--headless=new" in options.arguments

    def test_not_headless_when_show_browser_true(self):
        with patch.object(cki.webdriver, "Chrome") as chrome_cls:
            chrome_cls.return_value = MagicMock()
            cki.setup_driver(show_browser=True, use_profile=False)

            args, kwargs = chrome_cls.call_args
            options = kwargs["options"]
            assert "--headless=new" not in options.arguments

    def test_default_use_profile_is_true(self, tmp_path, monkeypatch):
        """Shape A cutover: use_profile is True by default."""
        monkeypatch.setenv("HOME", str(tmp_path))
        with patch.object(cki.webdriver, "Chrome") as chrome_cls:
            chrome_cls.return_value = MagicMock()
            cki.setup_driver()

            args, kwargs = chrome_cls.call_args
            options = kwargs["options"]
            assert any(a.startswith("--user-data-dir=") for a in options.arguments)

    def test_no_profile_flag_when_use_profile_false(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        with patch.object(cki.webdriver, "Chrome") as chrome_cls:
            chrome_cls.return_value = MagicMock()
            cki.setup_driver(use_profile=False)

            args, kwargs = chrome_cls.call_args
            options = kwargs["options"]
            assert not any(a.startswith("--user-data-dir=") for a in options.arguments)

    def test_profile_flag_added_when_use_profile_true(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        with patch.object(cki.webdriver, "Chrome") as chrome_cls:
            chrome_cls.return_value = MagicMock()
            cki.setup_driver(use_profile=True)

            args, kwargs = chrome_cls.call_args
            options = kwargs["options"]
            expected = f"--user-data-dir={tmp_path / '.comicskingdom_chrome_profile'}"
            assert expected in options.arguments

    def test_profile_directory_created_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        profile_dir = tmp_path / ".comicskingdom_chrome_profile"
        assert not profile_dir.exists()

        with patch.object(cki.webdriver, "Chrome") as chrome_cls:
            chrome_cls.return_value = MagicMock()
            cki.setup_driver(use_profile=True)

        assert profile_dir.is_dir()

    def test_profile_directory_contents_preserved_when_exists(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        profile_dir = tmp_path / ".comicskingdom_chrome_profile"
        profile_dir.mkdir()
        # Simulate an existing Chrome profile artifact
        existing_cookies = profile_dir / "Default" / "Cookies"
        existing_cookies.parent.mkdir(parents=True)
        existing_cookies.write_bytes(b"pretend-sqlite-content")

        with patch.object(cki.webdriver, "Chrome") as chrome_cls:
            chrome_cls.return_value = MagicMock()
            cki.setup_driver(use_profile=True)

        assert existing_cookies.read_bytes() == b"pretend-sqlite-content"

    def test_profile_directory_mode_is_0o700(self, tmp_path, monkeypatch):
        import stat

        monkeypatch.setenv("HOME", str(tmp_path))
        profile_dir = tmp_path / ".comicskingdom_chrome_profile"
        # Pre-create with a more permissive mode to prove setup_driver tightens it.
        profile_dir.mkdir(mode=0o755)

        with patch.object(cki.webdriver, "Chrome") as chrome_cls:
            chrome_cls.return_value = MagicMock()
            cki.setup_driver(use_profile=True)

        assert stat.S_IMODE(profile_dir.stat().st_mode) == 0o700

    def test_profile_and_show_browser_coexist(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        with patch.object(cki.webdriver, "Chrome") as chrome_cls:
            chrome_cls.return_value = MagicMock()
            cki.setup_driver(show_browser=True, use_profile=True)

            args, kwargs = chrome_cls.call_args
            options = kwargs["options"]
            expected = f"--user-data-dir={tmp_path / '.comicskingdom_chrome_profile'}"
            assert expected in options.arguments
            assert "--headless=new" not in options.arguments


# --- wait_for_manual_login --------------------------------------------------


class TestWaitForManualLogin:
    """Behavior tests for the manual-login helper.

    The function only confirms the login form is present and waits for the
    operator to complete login in a visible browser; it does not type or
    submit.
    """

    def test_function_exists_on_individual(self):
        assert callable(cki.wait_for_manual_login)

    def test_returns_true_when_redirect_away_from_login(self, monkeypatch):
        driver = MagicMock()
        driver.current_url = "https://comicskingdom.com/account"

        # Speed up the 120-iteration wait loop
        monkeypatch.setattr(cki.time, "sleep", lambda *_a, **_kw: None)

        mock_wdw = MagicMock()
        mock_wdw.return_value.until.return_value = MagicMock()
        monkeypatch.setattr(cki, "WebDriverWait", mock_wdw)

        result = cki.wait_for_manual_login(driver)
        assert result is True

    def test_returns_false_on_timeout(self, monkeypatch):
        driver = MagicMock()
        driver.current_url = "https://comicskingdom.com/login?step=captcha"

        monkeypatch.setattr(cki.time, "sleep", lambda *_a, **_kw: None)

        mock_wdw = MagicMock()
        mock_wdw.return_value.until.return_value = MagicMock()
        monkeypatch.setattr(cki, "WebDriverWait", mock_wdw)

        result = cki.wait_for_manual_login(driver)
        assert result is False

    def test_returns_false_when_no_username_field(self, monkeypatch):
        driver = MagicMock()

        monkeypatch.setattr(cki.time, "sleep", lambda *_a, **_kw: None)

        # All three selector attempts raise (no username field findable)
        mock_wdw = MagicMock()
        mock_wdw.return_value.until.side_effect = Exception("not found")
        monkeypatch.setattr(cki, "WebDriverWait", mock_wdw)

        result = cki.wait_for_manual_login(driver)
        assert result is False

    def test_does_not_inject_credentials_via_js(self, monkeypatch):
        """CK's bot check rejects JS-injected fills — the function must not attempt them."""
        driver = MagicMock()
        driver.current_url = "https://comicskingdom.com/account"

        monkeypatch.setattr(cki.time, "sleep", lambda *_a, **_kw: None)

        mock_wdw = MagicMock()
        mock_wdw.return_value.until.return_value = MagicMock()
        monkeypatch.setattr(cki, "WebDriverWait", mock_wdw)

        cki.wait_for_manual_login(driver)
        assert not driver.execute_script.called


# --- load_cookie_file_path --------------------------------------------------


class TestLoadCookieFilePath:
    def test_uses_env_var_when_set(self, monkeypatch):
        monkeypatch.setenv("COMICSKINGDOM_COOKIE_FILE", "/tmp/ck-test.pkl")
        assert str(cki.load_cookie_file_path()) == "/tmp/ck-test.pkl"

    def test_falls_back_to_default_when_unset(self, monkeypatch):
        monkeypatch.delenv("COMICSKINGDOM_COOKIE_FILE", raising=False)
        assert (
            str(cki.load_cookie_file_path()) == "data/comicskingdom_cookies.pkl"
        )

    def test_does_not_read_credential_env_vars(self, capsys, monkeypatch):
        # Shape A: credentials are typed by the operator into the browser at
        # reauth time and are never loaded from env. Setting them here proves
        # the loader ignores them and they cannot leak into stdout.
        monkeypatch.setenv("COMICSKINGDOM_USERNAME", "test-user-do-not-log")
        monkeypatch.setenv("COMICSKINGDOM_PASSWORD", "test-pass-do-not-log")

        cki.load_cookie_file_path()

        captured = capsys.readouterr()
        assert "test-user-do-not-log" not in captured.out
        assert "test-pass-do-not-log" not in captured.out


# --- reauth_comicskingdom.py -------------------------------------------------


class TestReauthScript:
    """Unit 4 — reauth rewrite imports from _individual, seeds the profile."""

    def _load_reauth_module(self):
        """Fresh import of the reauth script for a test.

        Using importlib so each test gets a clean module state and
        patch.object works cleanly on the reauth-local names.
        """
        import importlib
        import scripts.reauth_comicskingdom as reauth
        importlib.reload(reauth)
        return reauth

    def test_imports_from_individual_not_secure(self):
        """AST-level: the reauth script must not import from _secure."""
        import ast
        repo_root = Path(__file__).parent.parent
        source = (repo_root / "scripts" / "reauth_comicskingdom.py").read_text()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert "comicskingdom_scraper_secure" not in module, (
                    f"reauth_comicskingdom.py still imports from _secure: "
                    f"line {node.lineno}"
                )
                # Positive check: it does import from _individual.
                # At least one import should reference it.
        assert any(
            isinstance(n, ast.ImportFrom)
            and "comicskingdom_scraper_individual" in (n.module or "")
            for n in ast.walk(tree)
        )

    def test_exits_zero_when_login_mints_a_new_token(self, monkeypatch, tmp_path):
        """Success requires a *new* token on disk, not just a login that looked fine.

        A reauth performed while the old session is still valid can leave the
        old expiry untouched; that is not success (2026-07-28 outage).
        """
        from datetime import datetime, timedelta, timezone

        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setattr("builtins.input", lambda *_a, **_kw: "")

        reauth = self._load_reauth_module()

        driver = MagicMock()
        fresh = datetime.now(timezone.utc) + timedelta(days=7)
        with patch.object(reauth, "setup_driver", return_value=driver) as ms, \
             patch.object(reauth, "wait_for_manual_login", return_value=True) as ml, \
             patch.object(reauth, "read_token_expiry", side_effect=[None, fresh]):
            result = reauth.main()

        assert result == 0
        # setup_driver must be invoked with use_profile=True
        ms.assert_called_once()
        _, kwargs = ms.call_args
        assert kwargs.get("use_profile") is True
        assert kwargs.get("show_browser") is True
        # login helper was invoked with only the driver (no JS-filled creds)
        ml.assert_called_once_with(driver)

    def test_exits_nonzero_when_the_expiry_does_not_move(self, monkeypatch, tmp_path):
        """The 2026-07-28 failure: login looked fine, no new token was issued."""
        from datetime import datetime, timedelta, timezone

        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setattr("builtins.input", lambda *_a, **_kw: "")

        reauth = self._load_reauth_module()

        stale = datetime.now(timezone.utc) + timedelta(hours=6)
        with patch.object(reauth, "setup_driver", return_value=MagicMock()), \
             patch.object(reauth, "wait_for_manual_login", return_value=True), \
             patch.object(reauth, "read_token_expiry", side_effect=[stale, stale]):
            result = reauth.main()

        assert result == 1

    def test_exits_nonzero_when_no_token_lands_on_disk(self, monkeypatch, tmp_path):
        """Chrome closed without flushing cookies — the leading 07-28 hypothesis."""
        from datetime import datetime, timedelta, timezone

        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setattr("builtins.input", lambda *_a, **_kw: "")

        reauth = self._load_reauth_module()

        old = datetime.now(timezone.utc) + timedelta(hours=6)
        with patch.object(reauth, "setup_driver", return_value=MagicMock()), \
             patch.object(reauth, "wait_for_manual_login", return_value=True), \
             patch.object(reauth, "read_token_expiry", side_effect=[old, None]):
            result = reauth.main()

        assert result == 1

    def test_reads_the_expiry_after_quitting_the_browser(self, monkeypatch, tmp_path):
        """Chrome flushes cookies on clean shutdown, so order matters."""
        from datetime import datetime, timedelta, timezone

        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setattr("builtins.input", lambda *_a, **_kw: "")

        reauth = self._load_reauth_module()

        order = []
        driver = MagicMock()
        driver.quit.side_effect = lambda: order.append("quit")
        fresh = datetime.now(timezone.utc) + timedelta(days=7)

        def read(_profile):
            order.append("read")
            return fresh

        with patch.object(reauth, "setup_driver", return_value=driver), \
             patch.object(reauth, "wait_for_manual_login", return_value=True), \
             patch.object(reauth, "read_token_expiry", side_effect=read):
            reauth.main()

        # first read is the "before" snapshot, then quit, then the "after" read
        assert order == ["read", "quit", "read"]

    def test_exits_nonzero_on_login_fail(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setattr("builtins.input", lambda *_a, **_kw: "")

        reauth = self._load_reauth_module()

        driver = MagicMock()
        with patch.object(reauth, "setup_driver", return_value=driver), \
             patch.object(reauth, "wait_for_manual_login", return_value=False):
            result = reauth.main()

        assert result == 1

    def test_does_not_write_pickle_file(self, monkeypatch, tmp_path, capsys):
        # Even after a successful login, no pickle file should be produced --
        # the profile carries the session, not a pkl.
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv(
            "COMICSKINGDOM_COOKIE_FILE", str(tmp_path / "unused.pkl")
        )
        monkeypatch.setattr("builtins.input", lambda *_a, **_kw: "")

        reauth = self._load_reauth_module()

        driver = MagicMock()
        with patch.object(reauth, "setup_driver", return_value=driver), \
             patch.object(reauth, "wait_for_manual_login", return_value=True):
            reauth.main()

        assert not (tmp_path / "unused.pkl").exists()


# --- main(): authentication retry -------------------------------------------


class TestAuthRetry:
    """The first Chrome launch after an auto-update is unreliable.

    2026-08-05 landed on the login page, 2026-08-07 threw on navigation, and
    both self-healed on the next run — each costing a full day of Comics
    Kingdom. The retry rebuilds the driver because what recovers is the next
    *launch*, not the next navigation.
    """

    def _run_main(self, monkeypatch, tmp_path, auth_results):
        monkeypatch.setattr(
            sys, "argv",
            ["prog", "--date", "2026-08-07", "--output-dir", str(tmp_path)],
        )
        drivers = [MagicMock(), MagicMock()]
        made = []

        def fake_setup(**_kw):
            d = drivers[len(made)]
            made.append(d)
            return d

        calls = {"auth": 0}

        def fake_auth(*_a, **_kw):
            result = auth_results[calls["auth"]]
            calls["auth"] += 1
            return result

        with patch.object(cki, "setup_driver", side_effect=fake_setup), \
             patch.object(cki, "authenticate_with_cookies", side_effect=fake_auth), \
             patch.object(cki, "load_comics_catalog", return_value=[{"slug": "x"}]), \
             patch.object(cki, "load_cookie_file_path", return_value=tmp_path / "c.pkl"), \
             patch.object(cki, "scrape_all_comics", return_value=[{"slug": "x"}]):
            rc = cki.main()
        return rc, made, calls["auth"]

    def test_retries_once_with_a_fresh_driver_and_succeeds(
        self, monkeypatch, tmp_path, capsys
    ):
        rc, made, auth_calls = self._run_main(
            monkeypatch, tmp_path, auth_results=[False, True]
        )
        assert rc == 0
        assert auth_calls == 2
        assert len(made) == 2, "retry must build a NEW driver, not reuse the old one"
        assert "succeeded on retry" in capsys.readouterr().out

    def test_first_driver_is_quit_before_retrying(self, monkeypatch, tmp_path):
        _rc, made, _ = self._run_main(
            monkeypatch, tmp_path, auth_results=[False, True]
        )
        made[0].quit.assert_called()

    def test_gives_up_after_one_retry(self, monkeypatch, tmp_path, capsys):
        rc, made, auth_calls = self._run_main(
            monkeypatch, tmp_path, auth_results=[False, False]
        )
        assert rc == 1
        assert auth_calls == 2, "must not retry forever"
        assert len(made) == 2
        assert "after retry" in capsys.readouterr().out

    def test_no_retry_when_first_attempt_succeeds(self, monkeypatch, tmp_path):
        rc, made, auth_calls = self._run_main(
            monkeypatch, tmp_path, auth_results=[True]
        )
        assert rc == 0
        assert auth_calls == 1
        assert len(made) == 1, "a healthy run must not launch a second browser"


class TestSourceSlugSeparation:
    """A comic's upstream path and its feed identity are separate things.

    GoComics and Comics Kingdom both run Edge City, but at different points in
    its history -- GoComics the 2011 sequence, Comics Kingdom the 2006 one.
    Those are two distinct works, so each needs its own feed file, but Comics
    Kingdom still only serves one path (/edge-city). `source_slug` carries the
    upstream path while `slug` stays the feed identity.
    """

    def _soup_driver(self, html):
        driver = MagicMock()
        driver.page_source = html
        driver.current_url = "https://comicskingdom.com/edge-city/2026-08-24"
        return driver

    def test_scrape_uses_source_slug_for_the_url_and_slug_for_the_record(self):
        """Fetch /edge-city, but file the result under edge-city-classic."""
        driver = self._soup_driver(NOT_FOUND_PAGE)

        with patch.object(cki, 'scrape_comic_page', wraps=cki.scrape_comic_page) as spy:
            with patch.object(cki, 'time') as _t:
                _t.sleep = lambda *_: None
                cki.scrape_all_comics(
                    driver,
                    [{'name': 'Edge City Classic', 'slug': 'edge-city-classic',
                      'source_slug': 'edge-city'}],
                    '2026-08-24',
                )

        assert spy.call_count == 1
        args, kwargs = spy.call_args
        assert args[1] == 'edge-city', (
            "Scraper must request the upstream path from source_slug; "
            f"requested {args[1]!r} instead."
        )
        assert kwargs.get('feed_slug') == 'edge-city-classic'

    def test_source_slug_defaults_to_slug(self):
        """Entries without source_slug are untouched -- 155 of 156 CK comics."""
        driver = self._soup_driver(NOT_FOUND_PAGE)

        with patch.object(cki, 'scrape_comic_page', wraps=cki.scrape_comic_page) as spy:
            with patch.object(cki, 'time') as _t:
                _t.sleep = lambda *_: None
                cki.scrape_all_comics(driver, [{'name': 'Blondie', 'slug': 'blondie'}], '2026-08-24')

        args, kwargs = spy.call_args
        assert args[1] == 'blondie'
        assert kwargs.get('feed_slug') == 'blondie'


# --- extract_displayed_post (U1) --------------------------------------------


class TestExtractDisplayedPost:
    """The page's own data names the post it displays for the requested date.

    `props.pageProps.fallback` keeps the `ck_comic` query the page ran:
    posts of `ck_feature:"<source slug>"` on or before `before_ymd:"<date>"`,
    newest first. Its first post is the one on screen. Nothing else on the
    page -- archive thumbnails, other features, `featured` crops -- may reach
    a record (#216).
    """

    def test_daily_post_with_two_panels(self):
        post, reason = cki.extract_displayed_post(ZITS_PAGE, 'zits', '2026-10-01')

        assert reason is None
        assert post == {
            'post_date': '2026-10-01',
            'post_url': 'https://comicskingdom.com/zits/2026-10-01',
            'image_urls': ZITS_1001_PANELS,
        }

    def test_post_without_panels_uses_its_single_image_never_featured(self):
        post, reason = cki.extract_displayed_post(BUF_PAGE, 'bringing-up-father', '2026-10-01')

        assert reason is None
        assert post['image_urls'] == [BUF_1001['assets']['single']['url']]
        assert post['post_url'] == 'https://comicskingdom.com/vintage/bringing-up-father/2026-10-01'

    def test_episodic_page_returns_the_episode_with_every_panel(self):
        """Episodic comics run their query with per_page:1; the match ignores per_page."""
        post, reason = cki.extract_displayed_post(POPEYE_PAGE, 'eye-lie-popeye', '2026-10-01')

        assert reason is None
        assert post['post_date'] == '2026-05-13'
        assert post['post_url'] == 'https://comicskingdom.com/eye-lie-popeye/2026-05-13'
        assert post['image_urls'] == POPEYE_PANELS
        assert len(post['image_urls']) == 19

    def test_repeat_returns_the_older_post_date(self):
        """Pros & Cons has shown its 2023-07-31 strip every night since."""
        post, reason = cki.extract_displayed_post(PROS_CONS_PAGE, 'pros-cons', '2026-10-01')

        assert reason is None
        assert post['post_date'] == '2023-07-31'
        assert post['post_url'] == 'https://comicskingdom.com/pros-cons/2023-07-31'

    def test_query_for_a_different_feature_is_ignored(self):
        post, reason = cki.extract_displayed_post(PROS_CONS_PAGE, 'zits', '2026-10-01')

        assert post is None
        assert reason.startswith('no query')

    def test_query_for_a_different_date_is_ignored(self):
        post, reason = cki.extract_displayed_post(ZITS_PAGE, 'zits', '2026-09-30')

        assert post is None
        assert reason.startswith('no query')

    def test_match_uses_the_source_slug(self):
        """edge-city-classic is filed under its own feed but served at /edge-city."""
        page = ck_page({EDGE_CITY_QUERY: _result(_post(
            100, '2026-08-24', 'https://wp.comicskingdom.com/edge-city/2026-08-24',
            single=f'{UPLOADS}/2026/08/edge-city.jpg',
        ))})

        post, reason = cki.extract_displayed_post(page, 'edge-city', '2026-08-24')
        assert reason is None
        assert post['post_date'] == '2026-08-24'

        post, reason = cki.extract_displayed_post(page, 'edge-city-classic', '2026-08-24')
        assert post is None
        assert reason.startswith('no query')

    def test_vintage_post_matches_through_its_query_key_not_its_slug(self):
        """The post's slug starts beetle-bailey-1-; ownership comes from the key."""
        assert BEETLE_1967['slug'].startswith('beetle-bailey-1-')

        post, reason = cki.extract_displayed_post(BEETLE_PAGE, 'beetle-bailey-vintage', '1967-10-01')

        assert reason is None
        assert post == {
            'post_date': '1967-10-01',
            'post_url': 'https://comicskingdom.com/vintage/beetle-bailey-vintage/1967-10-01',
            'image_urls': [f'{UPLOADS}/1967/10/Beetle-Bailey.ENG_.1967-10-01.jpeg'],
        }

    def test_post_dated_after_the_requested_date_is_rejected(self):
        """Premium early access must never be recorded."""
        early = _post(
            7693500, '2026-10-02', 'https://wp.comicskingdom.com/zits/2026-10-02',
            panels=[f'{UPLOADS}/2026/10/early.jpg'],
        )
        page = ck_page({ZITS_QUERY: _result(early, ZITS_1001)})

        post, reason = cki.extract_displayed_post(page, 'zits', '2026-10-01')

        assert post is None
        assert 'early access' in reason

    def test_post_with_neither_panels_nor_single_is_not_recorded(self):
        bare = _post(
            7693423, '2026-10-01', 'https://wp.comicskingdom.com/zits/2026-10-01',
            panels=[], single='', featured=f'{UPLOADS}/2026/10/thumb-500x500.jpg',
        )
        page = ck_page({ZITS_QUERY: _result(bare)})

        post, reason = cki.extract_displayed_post(page, 'zits', '2026-10-01')

        assert post is None
        assert reason == 'no images'

    def test_404_page_has_no_comic_query(self):
        post, reason = cki.extract_displayed_post(NOT_FOUND_PAGE, 'zits', '2026-10-01')

        assert post is None
        assert reason.startswith('no query')

    def test_empty_result_gives_a_reason(self):
        page = ck_page({ZITS_QUERY: _result()})

        post, reason = cki.extract_displayed_post(page, 'zits', '2026-10-01')

        assert post is None
        assert reason == 'empty result'

    def test_query_value_may_be_a_bare_post_list(self):
        page = ck_page({ZITS_QUERY: [ZITS_1001, ZITS_0930]})

        post, reason = cki.extract_displayed_post(page, 'zits', '2026-10-01')

        assert reason is None
        assert post['image_urls'] == ZITS_1001_PANELS

    def test_invalid_json_gives_a_reason_and_raises_nothing(self):
        page = '<script id="__NEXT_DATA__" type="application/json">{"props": </script>'

        post, reason = cki.extract_displayed_post(page, 'zits', '2026-10-01')

        assert post is None
        assert reason

    def test_page_without_next_data_gives_a_reason_and_raises_nothing(self):
        """A firewall or challenge page has no __NEXT_DATA__ at all."""
        page = '<html><head><title>Just a moment...</title></head><body></body></html>'

        post, reason = cki.extract_displayed_post(page, 'zits', '2026-10-01')

        assert post is None
        assert reason

    def test_post_date_is_the_date_part_of_its_timestamp(self):
        assert ZITS_1001['date'] == '2026-10-01T00:00:00'

        post, _ = cki.extract_displayed_post(ZITS_PAGE, 'zits', '2026-10-01')

        assert post['post_date'] == '2026-10-01'

    def test_link_whose_date_disagrees_is_rejected(self):
        mislinked = _post(
            7693423, '2026-10-01', 'https://wp.comicskingdom.com/zits/2026-09-30',
            panels=ZITS_1001_PANELS,
        )
        page = ck_page({ZITS_QUERY: _result(mislinked)})

        post, reason = cki.extract_displayed_post(page, 'zits', '2026-10-01')

        assert post is None
        assert 'mismatch' in reason

    def test_post_without_a_date_is_rejected(self):
        undated = dict(ZITS_1001)
        del undated['date']
        page = ck_page({ZITS_QUERY: _result(undated)})

        post, reason = cki.extract_displayed_post(page, 'zits', '2026-10-01')

        assert post is None
        assert reason == 'no post date'

    def test_fixture_helper_refuses_a_page_with_a_session(self):
        next_data = _next_data({ZITS_QUERY: _result(ZITS_1001)})
        next_data['props']['pageProps']['session'] = {'user': {}, 'accessToken': 'x'}

        with pytest.raises(AssertionError):
            anonymous_page(next_data)


# --- session values never leak ----------------------------------------------

SENTINEL_TOKEN = 'SENTINEL-TOKEN-XYZ'
SENTINEL_EMAIL = 'sentinel@example.invalid'
SENTINEL_NAME = 'SENTINEL-USER-NAME'


def _logged_in_zits_page():
    """A page shaped like a logged-in one, holding obviously fake session values.

    Built outside anonymous_page() on purpose: it is the one fixture that
    carries a session, and every value in it is a sentinel.
    """
    next_data = _next_data({ZITS_QUERY: _result(ZITS_1001)})
    next_data['props']['pageProps']['session'] = {
        'user': {'name': SENTINEL_NAME, 'email': SENTINEL_EMAIL},
        'expires': '2099-01-01T00:00:00.000Z',
        'accessToken': SENTINEL_TOKEN,
    }
    return _html(next_data)


class _PageDriver:
    """A browser stand-in that serves a fixed page source per requested URL."""

    def __init__(self, pages):
        self.pages = pages
        self.page_source = ''
        self.requested = []

    def get(self, url):
        self.requested.append(url)
        self.page_source = self.pages[url]

    def quit(self):
        pass


def _run_main_with_pages(monkeypatch, tmp_path, catalog, pages, date='2026-10-01'):
    """Run main() end to end against canned pages: no browser, no network."""
    monkeypatch.setattr(
        sys, 'argv', ['prog', '--date', date, '--output-dir', str(tmp_path)],
    )
    monkeypatch.setattr(cki.time, 'sleep', lambda *_a, **_kw: None)
    driver = _PageDriver(pages)
    with patch.object(cki, 'setup_driver', side_effect=lambda **_kw: driver), \
         patch.object(cki, 'authenticate_with_cookies', return_value=True), \
         patch.object(cki, 'load_comics_catalog', return_value=catalog), \
         patch.object(cki, 'load_cookie_file_path', return_value=tmp_path / 'c.pkl'):
        rc = cki.main()
    return rc, driver


class TestSessionNeverLeaks:
    """A logged-in page carries session.accessToken and session.user.

    Those values are read in-process only; they must never reach a record,
    the data file, or the run's output.
    """

    SENTINELS = (SENTINEL_TOKEN, SENTINEL_EMAIL, SENTINEL_NAME)

    def test_extraction_result_holds_no_session_values(self):
        result = cki.extract_displayed_post(_logged_in_zits_page(), 'zits', '2026-10-01')

        assert result[0] is not None, "the page's post should still be read"
        for value in self.SENTINELS:
            assert value not in repr(result)

    def test_session_values_never_reach_records_or_output(
        self, monkeypatch, tmp_path, capsys
    ):
        rc, _ = _run_main_with_pages(
            monkeypatch, tmp_path,
            catalog=[{'name': 'Zits', 'slug': 'zits'}],
            pages={'https://comicskingdom.com/zits/2026-10-01': _logged_in_zits_page()},
        )

        assert rc == 0
        written = (tmp_path / 'comicskingdom_2026-10-01.json').read_text()
        out = capsys.readouterr()
        for value in self.SENTINELS:
            assert value not in written
            assert value not in out.out
            assert value not in out.err


# --- scraper records the displayed post (U2) --------------------------------


def _scrape(monkeypatch, catalog, pages, date='2026-10-01', recorded_posts=None):
    monkeypatch.setattr(cki.time, 'sleep', lambda *_a, **_kw: None)
    driver = _PageDriver(pages)
    return cki.scrape_all_comics(driver, catalog, date, recorded_posts)


ZITS = {'name': 'Zits', 'slug': 'zits'}
PROS_CONS = {'name': 'Pros & Cons', 'slug': 'pros-cons'}
BUF = {'name': 'Bringing Up Father', 'slug': 'bringing-up-father'}
EDGE_CITY_CLASSIC = {'name': 'Edge City Classic', 'slug': 'edge-city-classic',
                     'source_slug': 'edge-city'}


class TestRecordsDisplayedPost:
    """Each record names the requested night and the post the page displayed."""

    def test_record_carries_the_request_and_the_post(self, monkeypatch):
        results = _scrape(
            monkeypatch, [ZITS],
            {'https://comicskingdom.com/zits/2026-10-01': ZITS_PAGE},
        )

        assert results == [{
            'name': 'Zits',
            'slug': 'zits',
            'date': '2026-10-01',
            'url': 'https://comicskingdom.com/zits/2026-10-01',
            'source': 'comicskingdom',
            'post_date': '2026-10-01',
            'post_url': 'https://comicskingdom.com/zits/2026-10-01',
            'image_urls': ZITS_1001_PANELS,
        }]

    def test_name_comes_from_the_catalog(self, monkeypatch):
        results = _scrape(
            monkeypatch, [{'name': 'Bringing Up Father (Vintage)', 'slug': 'bringing-up-father'}],
            {'https://comicskingdom.com/bringing-up-father/2026-10-01': BUF_PAGE},
        )

        assert results[0]['name'] == 'Bringing Up Father (Vintage)'

    def test_one_image_post_yields_image_url(self, monkeypatch):
        results = _scrape(
            monkeypatch, [BUF],
            {'https://comicskingdom.com/bringing-up-father/2026-10-01': BUF_PAGE},
        )

        assert results[0]['image_url'] == BUF_1001['assets']['single']['url']
        assert 'image_urls' not in results[0]

    def test_repeat_is_recorded_with_its_older_post_date(self, monkeypatch):
        results = _scrape(
            monkeypatch, [PROS_CONS],
            {'https://comicskingdom.com/pros-cons/2026-10-01': PROS_CONS_PAGE},
        )

        assert len(results) == 1
        assert results[0]['date'] == '2026-10-01'
        assert results[0]['post_date'] == '2023-07-31'
        assert results[0]['post_url'] == 'https://comicskingdom.com/pros-cons/2023-07-31'

    def test_page_without_a_displayed_post_yields_no_record_and_is_named(
        self, monkeypatch, capsys
    ):
        results = _scrape(
            monkeypatch, [ZITS],
            {'https://comicskingdom.com/zits/2026-10-01': NOT_FOUND_PAGE},
        )

        assert results == []
        out = capsys.readouterr().out
        assert 'Not recorded: 1' in out
        named = [line for line in out.splitlines() if 'zits' in line and 'no query' in line]
        assert named, f"totals must name the slug and reason:\n{out}"

    def test_navigation_error_is_not_recorded_and_is_named(self, monkeypatch, capsys):
        monkeypatch.setattr(cki.time, 'sleep', lambda *_a, **_kw: None)
        driver = MagicMock()
        driver.get.side_effect = TimeoutError('renderer timeout')

        results = cki.scrape_all_comics(driver, [ZITS], '2026-10-01')

        assert results == []
        out = capsys.readouterr().out
        assert 'Not recorded: 1' in out
        assert any('zits' in line and 'TimeoutError' in line for line in out.splitlines())

    def test_totals_count_recorded_repeats_and_not_recorded(
        self, monkeypatch, tmp_path, capsys
    ):
        # An earlier night already holds Pros & Cons' 2023-07-31 strip, and an
        # old-format Zits record (no post_date) that must not count.
        (tmp_path / 'comicskingdom_2026-09-30.json').write_text(json.dumps([
            {'slug': 'pros-cons', 'date': '2026-09-30', 'post_date': '2023-07-31'},
            {'slug': 'zits', 'date': '2026-09-30'},
        ]))
        late_zits = ck_page({ZITS_QUERY: _result(ZITS_0930)})

        results = _scrape(
            monkeypatch, [ZITS, PROS_CONS, BUF, EDGE_CITY_CLASSIC],
            {
                # Zits uploaded 09-30's strip late: its post date is before
                # tonight, but no earlier file holds it, so it is new.
                'https://comicskingdom.com/zits/2026-10-01': late_zits,
                'https://comicskingdom.com/pros-cons/2026-10-01': PROS_CONS_PAGE,
                'https://comicskingdom.com/bringing-up-father/2026-10-01': BUF_PAGE,
                'https://comicskingdom.com/edge-city/2026-10-01': NOT_FOUND_PAGE,
            },
            recorded_posts=cki.load_recorded_posts(tmp_path, '2026-10-01'),
        )

        assert [r['slug'] for r in results] == ['zits', 'pros-cons', 'bringing-up-father']
        assert results[0]['post_date'] == '2026-09-30'
        out = capsys.readouterr().out
        assert 'Recorded: 3 of 4' in out
        assert 'Repeats: 1' in out
        assert 'Not recorded: 1' in out
        assert any('edge-city-classic' in line and 'no query' in line
                   for line in out.splitlines())

    def test_main_writes_records_that_carry_post_date(self, monkeypatch, tmp_path):
        rc, driver = _run_main_with_pages(
            monkeypatch, tmp_path,
            catalog=[ZITS, PROS_CONS, EDGE_CITY_CLASSIC],
            pages={
                'https://comicskingdom.com/zits/2026-10-01': ZITS_PAGE,
                'https://comicskingdom.com/pros-cons/2026-10-01': PROS_CONS_PAGE,
                'https://comicskingdom.com/edge-city/2026-10-01': NOT_FOUND_PAGE,
            },
        )

        assert rc == 0
        records = json.loads((tmp_path / 'comicskingdom_2026-10-01.json').read_text())
        assert [r['slug'] for r in records] == ['zits', 'pros-cons']
        assert all(r.get('post_date') for r in records)
        # One page load per comic.
        assert len(driver.requested) == 3

    def test_main_exits_nonzero_when_nothing_is_recorded(self, monkeypatch, tmp_path):
        rc, _ = _run_main_with_pages(
            monkeypatch, tmp_path,
            catalog=[ZITS],
            pages={'https://comicskingdom.com/zits/2026-10-01': NOT_FOUND_PAGE},
        )

        assert rc == 1
        assert not (tmp_path / 'comicskingdom_2026-10-01.json').exists()


class TestLoadRecordedPosts:
    """Earlier data files say which (comic, post date) pairs are repeats."""

    def test_reads_pairs_from_files_dated_before_the_run(self, tmp_path):
        (tmp_path / 'comicskingdom_2026-09-29.json').write_text(json.dumps([
            {'slug': 'zits', 'post_date': '2026-09-29'},
        ]))
        (tmp_path / 'comicskingdom_2026-09-30.json').write_text(json.dumps([
            {'slug': 'pros-cons', 'post_date': '2023-07-31'},
            {'slug': 'blondie', 'date': '2026-09-30'},  # old format: no post_date
        ]))
        # Tonight's own file and later ones are not "earlier".
        (tmp_path / 'comicskingdom_2026-10-01.json').write_text(json.dumps([
            {'slug': 'zits', 'post_date': '2026-10-01'},
        ]))

        assert cki.load_recorded_posts(tmp_path, '2026-10-01') == {
            ('zits', '2026-09-29'),
            ('pros-cons', '2023-07-31'),
        }

    def test_unreadable_files_are_skipped_silently(self, tmp_path, capsys):
        (tmp_path / 'comicskingdom_2026-09-28.json').write_text('{not json')
        (tmp_path / 'comicskingdom_2026-09-29.json').write_text(json.dumps([
            {'slug': 'zits', 'post_date': '2026-09-29'},
        ]))

        assert cki.load_recorded_posts(tmp_path, '2026-10-01') == {('zits', '2026-09-29')}
        assert capsys.readouterr().out == ''


# --- load_comics_catalog ----------------------------------------------------


class TestLoadComicsCatalog:
    """The scraper reads Comics Kingdom entries from both public/ catalogs.

    It read only public/comics_list.json until 2026-09-28, so the editorial
    cartoonists listed only in public/political_comics_list.json (mike-smith,
    lee-judge, ...) were never scraped and their feeds 404'd.
    """

    PROJECT_ROOT = Path(__file__).parent.parent

    def test_includes_political_catalog_entries_without_duplicates(self, monkeypatch):
        political = json.loads(
            (self.PROJECT_ROOT / 'public' / 'political_comics_list.json').read_text()
        )
        political_ck = {c['slug'] for c in political if c.get('source') == 'comicskingdom'}
        assert 'mike-smith' in political_ck, "fixture assumption: mike-smith is a political CK entry"

        monkeypatch.chdir(self.PROJECT_ROOT)
        slugs = [c['slug'] for c in cki.load_comics_catalog()]

        missing = sorted(political_ck - set(slugs))
        assert not missing, (
            f"Political-tab Comics Kingdom comics the scraper never visits: {missing}"
        )
        duplicated = sorted({s for s in slugs if slugs.count(s) > 1})
        assert not duplicated, f"Slugs the scraper would visit twice: {duplicated}"
