"""The OPML function answers a plain GET link as well as the site's POST.

Until 2026-11-22 functions/generate-opml.js only accepted a POSTed JSON body,
so an agent couldn't hand a person a bundle and a person couldn't share one.
The GET form takes ``?type=<category>&comics=<slug>,<slug>`` and returns the
same OPML. It must stay a pure lookup: nothing from the query reaches the
OPML except a slug listed in that category, and it never fetches anything,
so it can't become another open proxy (see
docs/solutions/logic-errors/feed-preview-function-was-an-open-proxy.md).

These tests run the real handler under node, laid out the way the Netlify
build lays it out (the five public comic lists copied next to the function),
with the network stubbed so any outbound request is recorded.
"""

import json
import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote, urlsplit

import pytest


PROJECT_ROOT = Path(__file__).parent.parent
PUBLIC = PROJECT_ROOT / "public"
OPML_FUNCTION = PROJECT_ROOT / "functions" / "generate-opml.js"
NODE = shutil.which("node")
BASE = "https://comiccaster.xyz"

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

LISTS = {
    "daily": "comics_list.json",
    "political": "political_comics_list.json",
    "spanish": "spanish_comics_list.json",
    "tinyview": "tinyview_comics_list.json",
    "external": "external_comics_list.json",
}

MAX_COMICS = 100
MAX_QUERY_LENGTH = 5000

# Builds a Netlify-style event per case, runs the handler, and prints what it
# returned and every outbound request it tried to make.
DRIVER = r"""
const Module = require('module');
const fs = require('fs');

const outbound = [];
const NETWORK = new Set(['http', 'https', 'http2', 'net', 'tls', 'dgram',
  'node:http', 'node:https', 'node:http2', 'node:net', 'node:tls', 'node:dgram',
  'node-fetch', 'axios', 'undici', 'rss-parser']);
const originalLoad = Module._load;
Module._load = function (request, parent, isMain) {
  if (NETWORK.has(request)) outbound.push({ require: request });
  return originalLoad.apply(this, arguments);
};
global.fetch = async (url) => {
  outbound.push({ fetch: String(url) });
  throw new Error('the OPML function must not fetch anything');
};

// Keep stdout for the results; the function's own logging goes to stderr.
console.log = console.error;

function eventFor(c) {
  const event = { httpMethod: c.method, headers: {} };
  if (c.body !== undefined) event.body = c.body;
  if (c.query !== undefined) {
    const params = new URLSearchParams(c.query);
    const multi = {};
    for (const [key, value] of params) (multi[key] = multi[key] || []).push(value);
    const single = {};
    for (const key of Object.keys(multi)) single[key] = multi[key].join(', ');
    const fields = c.fields || ['rawQuery', 'queryStringParameters', 'multiValueQueryStringParameters'];
    if (fields.includes('rawQuery')) event.rawQuery = c.query;
    if (fields.includes('queryStringParameters')) event.queryStringParameters = single;
    if (fields.includes('multiValueQueryStringParameters')) event.multiValueQueryStringParameters = multi;
  }
  return event;
}

const cases = JSON.parse(fs.readFileSync(0, 'utf8'));
const { handler } = require(process.argv[1]);

(async () => {
  const results = [];
  for (const c of cases) {
    outbound.length = 0;
    const res = await handler(eventFor(c), {});
    const headers = {};
    for (const [k, v] of Object.entries(res.headers || {})) headers[k.toLowerCase()] = v;
    results.push({ status: res.statusCode, headers, body: res.body, outbound: outbound.slice() });
  }
  process.stdout.write(JSON.stringify(results));
})().catch((e) => { console.error(e); process.exit(1); });
"""


def load_list(category):
    return json.loads((PUBLIC / LISTS[category]).read_text())


@pytest.fixture(scope="module")
def deployed(tmp_path_factory):
    """The function as Netlify deploys it: netlify.toml's build copies the
    public lists next to it. The committed copies under functions/ are stale,
    so running it in place would test old data."""
    root = tmp_path_factory.mktemp("netlify")
    functions = root / "functions"
    functions.mkdir()
    shutil.copy(OPML_FUNCTION, functions / "generate-opml.js")
    for filename in LISTS.values():
        shutil.copy(PUBLIC / filename, functions / filename)
    feeds = root / "public" / "feeds"
    feeds.mkdir(parents=True)
    for slug in ("peanuts", "pickles"):
        shutil.copy(PUBLIC / "feeds" / f"{slug}.xml", feeds / f"{slug}.xml")
    return root


@pytest.fixture(scope="module")
def run(deployed):
    def run_cases(cases):
        proc = subprocess.run(
            [NODE, "-e", DRIVER, str(deployed / "functions" / "generate-opml.js")],
            input=json.dumps(cases),
            capture_output=True,
            text=True,
            cwd=deployed,
            env={**os.environ, "URL": BASE},
            timeout=60,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr
        results = json.loads(proc.stdout)
        for result in results:
            assert result["outbound"] == [], result
        return results

    return run_cases


@pytest.fixture(scope="module")
def get(run):
    def get_one(query, **extra):
        [result] = run([{"method": "GET", "query": query, **extra}])
        return result

    return get_one


@pytest.fixture(scope="module")
def post(run):
    def post_one(payload):
        body = payload if isinstance(payload, str) else json.dumps(payload)
        [result] = run([{"method": "POST", "body": body}])
        return result

    return post_one


def outlines(opml_text):
    """[(text, xmlUrl)] of the feed outlines; fails if the OPML isn't well-formed."""
    root = ET.fromstring(opml_text)
    return [(o.get("text"), o.get("xmlUrl")) for o in root.iter("outline") if o.get("type") == "rss"]


def without_date(opml_text):
    return re.sub(r"<dateCreated>[^<]*</dateCreated>", "", opml_text)


def expected_url(comic):
    if comic.get("source") == "external-rss":
        return comic["feed_url"]
    if comic.get("source") in ("comicskingdom", "tinyview", "farside", "newyorker", "creators", "mrboffo"):
        return f"{BASE}/feeds/{comic['slug']}.xml"
    return f"{BASE}/rss/{comic['slug']}"


def json_error(result):
    assert result["headers"].get("content-type") == "application/json", result
    return json.loads(result["body"])["error"]


# --- The link works and returns the POST form's OPML -------------------------

def test_a_link_returns_an_opml_download(get):
    result = get("type=daily&comics=peanuts,pickles")
    assert result["status"] == 200, result
    assert result["headers"]["content-type"] == "application/xml"
    assert result["headers"]["content-disposition"] == 'attachment; filename="daily-comics.opml"'
    assert outlines(result["body"]) == [
        ("Peanuts", f"{BASE}/rss/peanuts"),
        ("Pickles", f"{BASE}/rss/pickles"),
    ]


def test_a_link_and_a_post_return_the_same_opml(get, post):
    link = get("type=daily&comics=peanuts,pickles")
    posted = post({"type": "daily", "comics": ["peanuts", "pickles"]})
    assert posted["status"] == 200, posted
    assert without_date(link["body"]) == without_date(posted["body"])
    assert link["headers"]["content-disposition"] == posted["headers"]["content-disposition"]


def test_a_link_can_be_read_cross_origin(get):
    assert get("type=daily&comics=peanuts")["headers"]["access-control-allow-origin"] == "*"


@pytest.mark.parametrize("category", list(LISTS))
def test_each_category_names_and_links_its_comics_from_its_list(get, category):
    comics = load_list(category)[:5]
    slugs = [comic["slug"] for comic in comics]
    result = get(f"type={category}&comics={','.join(slugs)}")
    assert result["status"] == 200, result
    assert outlines(result["body"]) == [(comic["name"], expected_url(comic)) for comic in comics]
    filename = {"daily": "daily-comics.opml", "political": "political-cartoons.opml",
                "spanish": "spanish-comics.opml", "tinyview": "tinyview-comics.opml",
                "external": "external-comics.opml"}[category]
    assert result["headers"]["content-disposition"] == f'attachment; filename="{filename}"'


def test_type_defaults_to_daily(get):
    result = get("comics=peanuts")
    assert result["status"] == 200, result
    assert result["headers"]["content-disposition"] == 'attachment; filename="daily-comics.opml"'


@pytest.mark.parametrize("query", [
    "type=daily&comics=peanuts&comics=pickles",   # repeated parameter
    "type=daily&comics=peanuts,%20pickles",       # space after the comma
    "type=daily&comics=peanuts%2Cpickles",        # comma percent-encoded
    "type=daily&comics=peanuts,,pickles,",        # empty entries
    "type=daily&comics=peanuts,pickles,peanuts",  # duplicates collapse
])
def test_comics_can_be_written_the_ways_links_get_written(get, query):
    result = get(query)
    assert result["status"] == 200, result
    assert [text for text, _ in outlines(result["body"])] == ["Peanuts", "Pickles"]


def test_works_without_netlify_raw_query_fields(get):
    result = get("type=daily&comics=peanuts,pickles", fields=["queryStringParameters"])
    assert result["status"] == 200, result
    assert [text for text, _ in outlines(result["body"])] == ["Peanuts", "Pickles"]


def test_the_example_link_in_llms_txt_works(get):
    text = (PUBLIC / "llms.txt").read_text()
    links = re.findall(r"https://comiccaster\.xyz/\.netlify/functions/generate-opml\?\S+", text)
    assert links, "llms.txt shows no example OPML link"
    for link in links:
        result = get(urlsplit(link).query)
        assert result["status"] == 200, (link, result)
        assert outlines(result["body"])


# --- Only listed slugs of the link's own category reach the OPML -------------

def test_slugs_in_no_list_are_dropped(get):
    result = get("type=daily&comics=peanuts,not-a-comic")
    assert [text for text, _ in outlines(result["body"])] == ["Peanuts"]


def test_slugs_from_another_category_are_dropped(get):
    tinyview_slug = load_list("tinyview")[0]["slug"]
    result = get(f"type=daily&comics=peanuts,{tinyview_slug}")
    assert [text for text, _ in outlines(result["body"])] == ["Peanuts"]


def test_the_category_decides_which_feed_a_shared_slug_means(get):
    # false-knees is ComicCaster's GoComics feed under daily and the
    # publisher's own feed under external. That's why one link is one category.
    external = next(c for c in load_list("external") if c["slug"] == "false-knees")
    assert any(c["slug"] == "false-knees" for c in load_list("daily"))
    daily = get("type=daily&comics=false-knees")
    ext = get("type=external&comics=false-knees")
    assert outlines(daily["body"])[0][1] == f"{BASE}/rss/false-knees"
    assert outlines(ext["body"])[0][1] == external["feed_url"]


def test_a_path_that_names_a_feed_file_is_dropped(get):
    # public/feeds/../feeds/pickles.xml exists, which the POST form's filter accepts.
    result = get(f"type=daily&comics=peanuts,{quote('../feeds/pickles', safe='')}")
    assert outlines(result["body"]) == [("Peanuts", f"{BASE}/rss/peanuts")]
    assert "../" not in result["body"]


def test_unlisted_input_is_never_echoed(get):
    hostile = '<script>alert(1)</script>,"onload="x,https://evil.example/rss'
    result = get(f"type=daily&comics=peanuts,{quote(hostile, safe=',')}")
    assert result["status"] == 200, result
    assert outlines(result["body"]) == [("Peanuts", f"{BASE}/rss/peanuts")]
    for needle in ("<script", "onload", "evil.example"):
        assert needle not in result["body"]


def test_no_listed_slugs_is_an_error(get):
    result = get("type=daily&comics=not-a-comic,another-one")
    assert result["status"] == 400
    assert "available feeds" in json_error(result)


# --- Bad links get a clear error ---------------------------------------------

@pytest.mark.parametrize("query", ["type=daily", "type=daily&comics=", "type=daily&comics=,,", ""])
def test_a_link_without_comics_is_an_error(get, query):
    result = get(query)
    assert result["status"] == 400, result
    assert "at least one comic" in json_error(result)
    assert "generate-opml?type=daily&comics=" in json.loads(result["body"])["example"]


@pytest.mark.parametrize("type_", ["farside", "newyorker", "Daily", "", "../../etc/passwd", "daily,tinyview"])
def test_an_unknown_type_is_an_error(get, type_):
    result = get(f"type={quote(type_, safe='')}&comics=peanuts")
    assert result["status"] == 400, result
    error = json_error(result)
    for category in LISTS:
        assert category in error


def test_one_link_is_one_category(get):
    result = get("type=daily&type=tinyview&comics=peanuts")
    assert result["status"] == 400, result
    assert "one" in json_error(result)


def test_at_most_100_comics_per_link(get):
    slugs = [comic["slug"] for comic in load_list("daily")]
    ok = get(f"type=daily&comics={','.join(slugs[:MAX_COMICS])}")
    assert ok["status"] == 200, ok
    assert len(outlines(ok["body"])) == MAX_COMICS
    too_many = get(f"type=daily&comics={','.join(slugs[:MAX_COMICS + 1])}")
    assert too_many["status"] == 400, too_many
    assert str(MAX_COMICS) in json_error(too_many)


def test_the_length_cap_fits_100_of_the_longest_real_slugs(get):
    slugs = sorted((c["slug"] for c in load_list("daily")), key=len, reverse=True)[:MAX_COMICS]
    query = "type=daily&comics=" + "%2C".join(slugs)
    assert len(query) <= MAX_QUERY_LENGTH
    result = get(query)
    assert result["status"] == 200, result
    assert len(outlines(result["body"])) == MAX_COMICS


@pytest.mark.parametrize("fields", [
    None,                                        # Netlify sends rawQuery
    ["queryStringParameters"],                   # without it
    ["multiValueQueryStringParameters"],
])
def test_an_overlong_query_is_refused(get, fields):
    query = "type=daily&comics=peanuts," + "x" * MAX_QUERY_LENGTH
    extra = {"fields": fields} if fields else {}
    result = get(query, **extra)
    assert result["status"] == 414, result
    assert str(MAX_QUERY_LENGTH) in json_error(result)


# --- Names are escaped, for both forms ---------------------------------------

def test_names_with_ampersands_make_well_formed_opml(get, post):
    names = ["Barney & Clyde", "Mutt & Jeff"]
    link = get("type=daily&comics=barneyandclyde,muttandjeff")
    posted = post({"type": "daily", "comics": ["barneyandclyde", "muttandjeff"]})
    for result in (link, posted):
        assert result["status"] == 200, result
        assert [text for text, _ in outlines(result["body"])] == names


# --- POST is unchanged, other methods are refused ----------------------------

def test_post_still_reports_its_existing_errors(post):
    assert post("not json")["status"] == 400
    assert json.loads(post("not json")["body"])["error"] == "Invalid request body"
    assert json.loads(post({"type": "daily", "comics": []})["body"])["error"] == "Please select at least one comic"


@pytest.mark.parametrize("method", ["PUT", "DELETE", "PATCH"])
def test_other_methods_are_refused(run, method):
    [result] = run([{"method": method, "query": "type=daily&comics=peanuts"}])
    assert result["status"] == 405
    assert result["headers"]["allow"] == "GET, POST"
