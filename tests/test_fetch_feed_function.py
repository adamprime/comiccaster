"""The feed-preview function must only fetch ComicCaster's own feeds and the
listed external feeds.

Until 2026-10-24 functions/fetch-feed.js fetched any URL it was sent, which
made it an open proxy on the Netlify account: POSTing Hacker News' RSS URL to
the live site returned Hacker News' feed. These tests run the real handler
under node, with the network and rss-parser stubbed out.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).parent.parent
FETCH_FEED = PROJECT_ROOT / "functions" / "fetch-feed.js"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

# Loads the handler with rss-parser and fetch replaced, runs one POST per case,
# and prints what the handler returned and what it tried to fetch.
DRIVER = r"""
const Module = require('module');
const fs = require('fs');

const calls = { fetch: [], parseURL: [] };

class FakeParser {
  async parseString(xml) {
    return { title: 'Feed', description: 'd', link: 'l',
             items: [{ title: 'Strip', content: '<img src="x">', link: 'l', pubDate: 'p' }] };
  }
  async parseURL(url) {
    calls.parseURL.push(url);
    throw new Error('parseURL follows redirects and must not be used');
  }
}

const originalLoad = Module._load;
Module._load = function (request, parent, isMain) {
  if (request === 'rss-parser') return FakeParser;
  return originalLoad.apply(this, arguments);
};

// Keep stdout for the results; the function's own logging goes to stderr.
console.log = console.error;

const cases = JSON.parse(fs.readFileSync(0, 'utf8'));
let redirects = {};

global.fetch = async (url, options = {}) => {
  url = String(url);
  calls.fetch.push({ url, redirect: options.redirect });
  if (redirects[url]) {
    return { ok: false, status: 302, headers: { get: () => redirects[url] },
             text: async () => '' };
  }
  return { ok: true, status: 200, headers: { get: () => null }, text: async () => '<rss/>' };
};

const { handler } = require(process.argv[1]);

(async () => {
  const results = [];
  for (const c of cases) {
    calls.fetch = [];
    redirects = c.redirect_to ? { [c.url]: c.redirect_to } : {};
    const res = await handler({
      httpMethod: 'POST',
      headers: {},
      body: JSON.stringify({ url: c.url }),
    });
    let body = null;
    try { body = JSON.parse(res.body); } catch (e) {}
    results.push({ url: c.url, status: res.statusCode, body,
                   fetched: calls.fetch, parseURL: calls.parseURL.slice() });
  }
  process.stdout.write(JSON.stringify(results));
})().catch((e) => { console.error(e); process.exit(1); });
"""


def run_handler(cases, context="production"):
    cases = [c if isinstance(c, dict) else {"url": c} for c in cases]
    proc = subprocess.run(
        [NODE, "-e", DRIVER, str(FETCH_FEED)],
        input=json.dumps(cases),
        capture_output=True,
        text=True,
        env={**os.environ, "CONTEXT": context},
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def external_feed_urls():
    comics = json.loads((PROJECT_ROOT / "public" / "external_comics_list.json").read_text())
    return [comic["feed_url"] for comic in comics]


OWN_FEEDS = [
    "https://comiccaster.xyz/feeds/calvinandhobbes.xml",
    "https://www.comiccaster.xyz/feeds/calvinandhobbes.xml",
    # Deploy previews preview their own branch's feed (see public/index.html).
    "https://deploy-preview-244--comiccaster.netlify.app/feeds/calvinandhobbes.xml",
    "https://comiccaster.netlify.app/feeds/tinyview-nick-anderson.xml",
]

REJECTED = [
    # Worked against the live site on 2026-10-24.
    "https://news.ycombinator.com/rss",
    "http://169.254.169.254/latest/meta-data/",
    "file:///etc/passwd",
    # Lookalike hosts.
    "https://comiccaster.xyz.evil.example/feeds/calvinandhobbes.xml",
    "https://comiccaster.xyz@evil.example/feeds/calvinandhobbes.xml",
    "https://evil.example/feeds/calvinandhobbes.xml?u=https://comiccaster.xyz",
    "https://other-site.netlify.app/feeds/calvinandhobbes.xml",
    "https://deploy-preview-1--other-site.netlify.app/feeds/calvinandhobbes.xml",
    # Our hosts, but not a feed, or not the way the site serves it.
    "https://comiccaster.xyz/.netlify/functions/fetch-feed",
    "https://comiccaster.xyz/feeds/../index.html",
    "https://comiccaster.xyz/feeds/nested/calvinandhobbes.xml",
    "https://comiccaster.xyz:8443/feeds/calvinandhobbes.xml",
    "https://user:pass@comiccaster.xyz/feeds/calvinandhobbes.xml",
    "http://comiccaster.xyz/feeds/calvinandhobbes.xml",
    "http://localhost:8888/feeds/calvinandhobbes.xml",
    # Listed external hosts, but not the listed feed URL.
    "https://xkcd.com/atom.xml",
    "https://xkcd.com/rss.xml?x=1",
    "not a url",
]


def test_previews_our_own_feeds():
    for result in run_handler(OWN_FEEDS):
        assert result["status"] == 200, result
        assert [f["url"] for f in result["fetched"]] == [result["url"]]
        assert result["body"]["items"][0]["title"] == "Strip"


def test_previews_every_listed_external_feed():
    urls = external_feed_urls()
    assert len(urls) >= 10
    for result in run_handler(urls):
        assert result["status"] == 200, result
        assert [f["url"] for f in result["fetched"]] == [result["url"]]


@pytest.mark.parametrize("url", REJECTED)
def test_rejects_anything_else_without_fetching(url):
    [result] = run_handler([url])
    assert result["status"] in (400, 403), result
    assert result["fetched"] == []
    assert result["parseURL"] == []


def test_does_not_follow_redirects():
    # A listed feed that starts redirecting could otherwise point the function
    # anywhere, including addresses the allowlist would refuse.
    [result] = run_handler([{
        "url": "https://xkcd.com/rss.xml",
        "redirect_to": "http://169.254.169.254/latest/meta-data/",
    }])
    assert result["status"] != 200
    assert result["fetched"] == [{"url": "https://xkcd.com/rss.xml", "redirect": "manual"}]
    assert result["parseURL"] == []


def test_local_dev_previews_localhost_feeds():
    [result] = run_handler(["http://localhost:8888/feeds/calvinandhobbes.xml"], context="dev")
    assert result["status"] == 200, result
    assert result["fetched"][0]["url"] == "http://localhost:8888/feeds/calvinandhobbes.xml"


def test_local_dev_still_rejects_other_hosts():
    [result] = run_handler(["https://news.ycombinator.com/rss"], context="dev")
    assert result["status"] == 403
    assert result["fetched"] == []
