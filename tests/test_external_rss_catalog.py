import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent


def test_external_rss_catalog_exists_with_direct_feed_urls():
    catalog_path = PROJECT_ROOT / "public" / "external_comics_list.json"

    assert catalog_path.exists()

    comics = json.loads(catalog_path.read_text())
    assert len(comics) >= 10

    slugs = {comic["slug"] for comic in comics}
    assert "xkcd" in slugs
    assert "poorly-drawn-lines" in slugs
    assert "oglaf" not in slugs

    for comic in comics:
        assert comic["source"] == "external-rss"
        assert comic["feed_url"].startswith("https://")
        assert comic["url"].startswith("https://")


def test_external_rss_tab_exists_in_browse_and_opml_ui():
    html = (PROJECT_ROOT / "public" / "index.html").read_text()

    assert 'data-tab="external"' in html
    assert 'id="external-tab"' in html
    assert 'id="externalComicSearch"' in html
    assert 'id="external-comics-table-body"' in html

    assert 'data-tab="external-opml"' in html
    assert 'id="external-opml-tab"' in html
    assert 'id="externalFeedSearch"' in html
    assert 'id="external-comics-list"' in html
    assert 'id="generateExternalOPMLBtn"' in html


def test_external_rss_ui_uses_direct_feed_urls():
    html = (PROJECT_ROOT / "public" / "index.html").read_text()

    assert "fetch('/external_comics_list.json')" in html
    assert "comic.source === 'external-rss'" in html
    assert "comic.feed_url" in html
    assert "type: 'external'" in html
    assert "external-comics.opml" in html


def test_generate_opml_supports_external_rss_catalog():
    opml_function = (PROJECT_ROOT / "functions" / "generate-opml.js").read_text()

    assert "external_comics_list.json" in opml_function
    assert "external-rss" in opml_function
    assert "comic.feed_url" in opml_function
    assert "external-comics.opml" in opml_function


def test_netlify_build_copies_external_catalog_for_functions():
    netlify_config = (PROJECT_ROOT / "netlify.toml").read_text()

    assert "public/external_comics_list.json" in netlify_config
    assert "external_comics_list.json" in netlify_config
