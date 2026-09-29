#!/usr/bin/env python3
"""Render generated feed XML as one HTML page for a visual check before it ships.

The page shows each feed's channel fields, then every item as a card: title,
pubDate, guid, link, categories and the strip's images. It flags what should
never ship (a duplicate or missing guid, an unparseable date, items out of
newest-first order, an item with no images). With --against it also marks each
item new, changed or unchanged compared with a reference copy, and lists items
the reference has that this feed dropped, which is what a subscriber would see
as re-deliveries or lost strips.

Usage:
    python scripts/preview_feeds.py FEED_OR_DIR [...] [--against REF] [-o OUT.html] [--open]

REF is a directory holding feeds with the same file names, or a git ref such as
origin/main, in which case each feed is compared with public/feeds/<name> at
that ref. The page is written to the system temp directory unless -o is given.
It reads local files only; images load from the comic sites when the page is
opened in a browser.
"""

import argparse
import html
import subprocess
import sys
import tempfile
import webbrowser
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FEEDS_DIR = 'public/feeds'
REQUIRED_ITEM_FIELDS = ('title', 'link', 'guid', 'pubDate')
# Fields whose change a subscriber sees as a different item or a re-delivery.
IDENTITY_FIELDS = ('title', 'pubDate', 'link', 'guid_is_permalink', 'categories')


class _ImageCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []

    def handle_starttag(self, tag, attrs):
        if tag == 'img':
            src = dict(attrs).get('src')
            if src:
                self.images.append(src)


def _images_in(description):
    collector = _ImageCollector()
    collector.feed(description)
    return collector.images


def parse_feed(xml_text):
    """Return {'channel': {...}, 'items': [...]} with every field as written.

    Raises ValueError when the text is not an RSS 2.0 feed.
    """
    # Only local feeds this project generated are parsed; the stdlib parser does
    # not resolve external entities.
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise ValueError(f'not well-formed XML: {e}') from e
    channel = root.find('channel')
    if root.tag != 'rss' or channel is None:
        raise ValueError(f'not an RSS feed (root element <{root.tag}>)')

    items = []
    for element in channel.findall('item'):
        guid = element.find('guid')
        description = element.findtext('description', default='')
        items.append({
            'title': element.findtext('title', default=''),
            'link': element.findtext('link', default=''),
            'guid': (guid.text or '') if guid is not None else '',
            'guid_is_permalink': guid.get('isPermaLink', '') if guid is not None else '',
            'pubDate': element.findtext('pubDate', default=''),
            'categories': [c.text or '' for c in element.findall('category')],
            'description': description,
            'images': _images_in(description),
        })

    return {
        'channel': {
            'title': channel.findtext('title', default=''),
            'link': channel.findtext('link', default=''),
            'description': channel.findtext('description', default=''),
            'lastBuildDate': channel.findtext('lastBuildDate', default=''),
            'categories': [c.text or '' for c in channel.findall('category')],
        },
        'items': items,
    }


def _label(number, item):
    return f"Item {number} ({item['guid'] or item['title'] or 'untitled'})"


def check_feed(feed):
    """Return findings as {'level': 'error' | 'warning', 'message', 'item'} dicts.

    'item' is the 1-based item number a finding is about, or None.
    """
    findings = []

    def add(level, message, item=None):
        findings.append({'level': level, 'message': message, 'item': item})

    items = feed['items']
    if not items:
        add('warning', 'Feed has no items')

    first_seen = {}
    previous_date = None
    order_reported = False
    for number, item in enumerate(items, 1):
        for field in REQUIRED_ITEM_FIELDS:
            if not item[field].strip():
                add('error', f'{_label(number, item)} has no {field}', number)

        guid = item['guid'].strip()
        if guid:
            if guid in first_seen:
                add('error', f'Duplicate guid {guid} (items {first_seen[guid]} and {number})', number)
            else:
                first_seen[guid] = number

        date = None
        if item['pubDate'].strip():
            try:
                date = parsedate_to_datetime(item['pubDate'])
            except (TypeError, ValueError):
                add('error', f"{_label(number, item)} has an unparseable pubDate '{item['pubDate']}'", number)
        if date is not None and previous_date is not None and date > previous_date and not order_reported:
            add('warning', f'Items are not newest-first: item {number} is newer than item {number - 1}', number)
            order_reported = True
        if date is not None:
            previous_date = date

        if not item['images']:
            add('warning', f'{_label(number, item)} has no images', number)

    return findings


def compare_feeds(current, reference):
    """Compare items by guid with a reference copy of the same feed.

    Each current item is 'new' (guid not in the reference), 'changed' (a field in
    IDENTITY_FIELDS differs), 'description' (only the description differs) or
    'same'. 'missing' lists reference items this feed no longer has.
    """
    by_guid = {}
    for item in reference['items']:
        by_guid.setdefault(item['guid'], item)

    statuses = {}
    for item in current['items']:
        old = by_guid.get(item['guid'])
        if old is None:
            statuses[item['guid']] = {'status': 'new', 'fields': []}
            continue
        fields = [f for f in IDENTITY_FIELDS if item[f] != old[f]]
        if fields:
            statuses[item['guid']] = {'status': 'changed', 'fields': fields}
        elif item['description'] != old['description']:
            statuses[item['guid']] = {'status': 'description', 'fields': ['description']}
        else:
            statuses[item['guid']] = {'status': 'same', 'fields': []}

    current_guids = {item['guid'] for item in current['items']}
    missing = [item for guid, item in by_guid.items() if guid not in current_guids]

    counts = {'new': 0, 'changed': 0, 'description': 0, 'same': 0}
    for status in statuses.values():
        counts[status['status']] += 1
    counts['missing'] = len(missing)
    return {'items': statuses, 'missing': missing, 'counts': counts}


def load_reference(feed_path, against, repo_root=REPO_ROOT):
    """Return (xml_text, label) for the reference copy of feed_path, or (None, None).

    against is a directory holding a file of the same name, or a git ref whose
    public/feeds/<name> is used.
    """
    name = Path(feed_path).name
    if Path(against).is_dir():
        candidate = Path(against) / name
        if candidate.is_file():
            return candidate.read_text(encoding='utf-8'), str(candidate)
        return None, None

    spec = f'{against}:{FEEDS_DIR}/{name}'
    result = subprocess.run(['git', '-C', str(repo_root), 'show', spec],
                            capture_output=True, text=True, encoding='utf-8')
    if result.returncode != 0:
        return None, None
    return result.stdout, spec


# --- rendering -----------------------------------------------------------------

STATUS_LABELS = {
    'new': 'New',
    'changed': 'Changed',
    'description': 'Description changed',
    'same': 'Unchanged',
}

CSS = """
:root { --bg:#f6f6f4; --card:#fff; --text:#1d1d1f; --muted:#6b6b70; --line:#dcdcd8;
  --err:#b42318; --err-bg:#fdecea; --warn:#8a5a00; --warn-bg:#fff4d6; --ok:#1e7a3c; --ok-bg:#e6f4ea;
  --new:#1f5fbf; --new-bg:#e7efff; --code:#f0f0ec; }
@media (prefers-color-scheme: dark) { :root { --bg:#161618; --card:#202024; --text:#ececef; --muted:#a0a0a8;
  --line:#35353b; --err:#ff8a80; --err-bg:#3a1d1b; --warn:#ffcf66; --warn-bg:#3a3018; --ok:#7fd99a;
  --ok-bg:#183222; --new:#8fb4ff; --new-bg:#1c2740; --code:#2a2a30; } }
* { box-sizing: border-box; }
body { margin:0; padding:24px 16px; background:var(--bg); color:var(--text);
  font:14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
main { max-width:1100px; margin:0 auto; }
h1 { font-size:20px; margin:0 0 4px; } h2 { font-size:17px; margin:0; }
.muted { color:var(--muted); }
code, .mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size:12.5px; word-break:break-all; }
table { border-collapse:collapse; width:100%; }
th, td { text-align:left; padding:6px 8px; border-bottom:1px solid var(--line); vertical-align:top; }
th { color:var(--muted); font-weight:600; white-space:nowrap; }
.wrap { overflow-x:auto; }
.card { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:14px 16px; margin:14px 0; }
.badge { display:inline-block; padding:1px 8px; border-radius:999px; font-size:12px; font-weight:600; white-space:nowrap; }
.error { color:var(--err); background:var(--err-bg); } .warning { color:var(--warn); background:var(--warn-bg); }
.okay { color:var(--ok); background:var(--ok-bg); }
.status-new { color:var(--new); background:var(--new-bg); } .status-changed { color:var(--err); background:var(--err-bg); }
.status-description { color:var(--warn); background:var(--warn-bg); } .status-same { color:var(--muted); background:var(--code); }
.findings { list-style:none; padding:0; margin:8px 0 0; } .findings li { margin:4px 0; }
.item { border-left:4px solid var(--line); }
.item.flag-new { border-left-color:var(--new); } .item.flag-changed, .item.flag-error { border-left-color:var(--err); }
.item.flag-description, .item.flag-warning { border-left-color:var(--warn); }
.item-head { display:flex; gap:8px; align-items:baseline; flex-wrap:wrap; margin-bottom:6px; }
.fields th { width:110px; }
.images { display:flex; flex-wrap:wrap; gap:8px; margin-top:10px; }
.images a { display:block; } .images img { display:block; max-width:100%; max-height:420px; border:1px solid var(--line); border-radius:4px; background:var(--code); }
details pre { background:var(--code); padding:10px; border-radius:6px; overflow-x:auto; white-space:pre-wrap; }
.toolbar { position:sticky; top:0; background:var(--bg); padding:8px 0; z-index:1; border-bottom:1px solid var(--line); margin-bottom:8px; }
section.feed { margin-top:28px; }
"""

SCRIPT = """
const box = document.getElementById('only-flagged');
box.addEventListener('change', () => {
  document.querySelectorAll('.item').forEach(el => { el.hidden = box.checked && !el.dataset.flagged; });
});
"""


def _e(value):
    return html.escape(str(value), quote=True)


def _badge(css_class, text):
    return f'<span class="badge {css_class}">{_e(text)}</span>'


def _findings_list(findings):
    if not findings:
        return f'<p>{_badge("okay", "No problems found")}</p>'
    rows = ''.join(f'<li>{_badge(f["level"], f["level"])} {_e(f["message"])}</li>' for f in findings)
    return f'<ul class="findings">{rows}</ul>'


def _item_card(number, item, findings, status):
    levels = {f['level'] for f in findings}
    classes = ['card', 'item']
    badges = [f'<span class="muted">#{number}</span>']
    if status:
        classes.append(f'flag-{status["status"]}')
        badges.append(_badge(f'status-{status["status"]}', STATUS_LABELS[status['status']]))
        if status['fields']:
            badges.append(f'<span class="muted">({_e(", ".join(status["fields"]))})</span>')
    for level in ('error', 'warning'):
        if level in levels:
            classes.append(f'flag-{level}')
    flagged = bool(findings) or (status is not None and status['status'] != 'same')

    link = item['link']
    link_html = (f'<a class="mono" href="{_e(link)}" rel="noopener noreferrer" target="_blank">{_e(link)}</a>'
                 if link.startswith(('http://', 'https://')) else f'<span class="mono">{_e(link)}</span>')
    fields = [
        ('pubDate', f'<span class="mono">{_e(item["pubDate"])}</span>'),
        ('guid', f'<span class="mono">{_e(item["guid"])}</span>'
                 f' <span class="muted">isPermaLink={_e(item["guid_is_permalink"] or "(unset)")}</span>'),
        ('link', link_html),
        ('categories', _e(', '.join(item['categories'])) or '<span class="muted">none</span>'),
        ('images', str(len(item['images']))),
    ]
    field_rows = ''.join(f'<tr><th>{name}</th><td>{value}</td></tr>' for name, value in fields)
    images = ''.join(
        f'<a href="{_e(src)}" rel="noopener noreferrer" target="_blank">'
        f'<img src="{_e(src)}" alt="{_e(src)}" loading="lazy"></a>'
        for src in item['images'] if src.startswith(('http://', 'https://'))
    )
    notes = ''.join(f'<li>{_badge(f["level"], f["level"])} {_e(f["message"])}</li>' for f in findings)
    return (
        f'<article class="{" ".join(classes)}"{" data-flagged=1" if flagged else ""}>'
        f'<div class="item-head">{" ".join(badges)} <h2>{_e(item["title"] or "(no title)")}</h2></div>'
        + (f'<ul class="findings">{notes}</ul>' if notes else '')
        + f'<div class="wrap"><table class="fields">{field_rows}</table></div>'
        + (f'<div class="images">{images}</div>' if images else '')
        + f'<details><summary class="muted">Raw description HTML</summary><pre>{_e(item["description"])}</pre></details>'
        + '</article>'
    )


def _feed_section(index, entry):
    name = entry['name']
    head = f'<h2 id="feed-{index}">{_e(name)}</h2><p class="muted mono">{_e(entry["path"])}</p>'
    if entry['error']:
        return f'<section class="feed">{head}<div class="card">{_badge("error", "error")} {_e(entry["error"])}</div></section>'

    feed = entry['feed']
    channel = feed['channel']
    channel_rows = ''.join(
        f'<tr><th>{label}</th><td>{value}</td></tr>' for label, value in (
            ('title', _e(channel['title'])),
            ('link', f'<span class="mono">{_e(channel["link"])}</span>'),
            ('description', _e(channel['description'])),
            ('categories', _e(', '.join(channel['categories'])) or '<span class="muted">none</span>'),
            ('lastBuildDate', f'<span class="mono">{_e(channel["lastBuildDate"])}</span>'),
            ('items', str(len(feed['items']))),
        )
    )
    parts = [head, f'<div class="card"><div class="wrap"><table>{channel_rows}</table></div>',
             _findings_list(entry['checks']), '</div>']

    comparison = entry['comparison']
    if entry.get('reference_note'):
        parts.append(f'<p class="muted">{_e(entry["reference_note"])}</p>')
    if comparison:
        counts = comparison['counts']
        parts.append(
            f'<div class="card"><strong>Compared with</strong> <span class="mono">{_e(entry["reference"])}</span><p>'
            + ' '.join(_badge(f'status-{key}', f'{counts[key]} {STATUS_LABELS[key].lower()}')
                       for key in ('new', 'changed', 'description', 'same'))
            + ' ' + _badge('error' if counts['missing'] else 'okay', f'{counts["missing"]} missing') + '</p>'
        )
        if comparison['missing']:
            rows = ''.join(
                f'<tr><td>{_e(m["title"])}</td><td class="mono">{_e(m["guid"])}</td><td class="mono">{_e(m["pubDate"])}</td></tr>'
                for m in comparison['missing'])
            parts.append('<p><strong>Missing</strong> <span class="muted">(in the reference, not in this feed)</span></p>'
                         f'<div class="wrap"><table><tr><th>title</th><th>guid</th><th>pubDate</th></tr>{rows}</table></div>')
        parts.append('</div>')

    by_item = {}
    for finding in entry['checks']:
        if finding['item'] is not None:
            by_item.setdefault(finding['item'], []).append(finding)
    for number, item in enumerate(feed['items'], 1):
        status = comparison['items'].get(item['guid']) if comparison else None
        parts.append(_item_card(number, item, by_item.get(number, []), status))
    return f'<section class="feed">{"".join(parts)}</section>'


def _summary_row(index, entry):
    link = f'<a href="#feed-{index}">{_e(entry["name"])}</a>'
    if entry['error']:
        return f'<tr><td>{link}</td><td colspan="3">{_badge("error", "could not read")}</td></tr>'
    errors = sum(1 for f in entry['checks'] if f['level'] == 'error')
    warnings = sum(1 for f in entry['checks'] if f['level'] == 'warning')
    checks = ' '.join(filter(None, [
        _badge('error', f'{errors} error{"s" * (errors != 1)}') if errors else '',
        _badge('warning', f'{warnings} warning{"s" * (warnings != 1)}') if warnings else '',
    ])) or _badge('okay', 'ok')
    comparison = entry['comparison']
    if comparison:
        c = comparison['counts']
        compared = ' '.join(filter(None, [
            _badge('status-new', f'{c["new"]} new') if c['new'] else '',
            _badge('status-changed', f'{c["changed"]} changed') if c['changed'] else '',
            _badge('status-description', f'{c["description"]} description') if c['description'] else '',
            _badge('error', f'{c["missing"]} missing') if c['missing'] else '',
        ])) or _badge('okay', 'no changes')
    else:
        compared = f'<span class="muted">{_e(entry.get("reference_note") or "not compared")}</span>'
    return f'<tr><td>{link}</td><td>{len(entry["feed"]["items"])}</td><td>{checks}</td><td>{compared}</td></tr>'


def render_report(entries):
    """Return a self-contained HTML page for the given feed entries."""
    generated = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    summary = ''.join(_summary_row(i, e) for i, e in enumerate(entries))
    sections = ''.join(_feed_section(i, e) for i, e in enumerate(entries))
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<title>Feed preview</title><style>{CSS}</style></head><body><main>'
        f'<h1>Feed preview</h1><p class="muted">{len(entries)} feed(s), generated {generated}</p>'
        '<div class="card"><div class="wrap"><table><tr><th>feed</th><th>items</th><th>checks</th><th>compared</th></tr>'
        f'{summary}</table></div></div>'
        '<div class="toolbar"><label><input type="checkbox" id="only-flagged"> '
        'Only show new or changed items and items with findings</label></div>'
        f'{sections}</main><script>{SCRIPT}</script></body></html>'
    )


# --- command line -------------------------------------------------------------

def _feed_files(paths):
    files = []
    for path in map(Path, paths):
        if path.is_dir():
            files.extend(sorted(path.glob('*.xml')))
        elif path.is_file():
            files.append(path)
    return files


def build_entry(path, against=None, repo_root=REPO_ROOT):
    entry = {'name': path.name, 'path': str(path.resolve()), 'feed': None, 'checks': [],
             'comparison': None, 'reference': None, 'reference_note': None, 'error': None}
    try:
        entry['feed'] = parse_feed(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, ValueError) as e:
        entry['error'] = f'Could not read this feed: {e}'
        return entry
    entry['checks'] = check_feed(entry['feed'])

    if against:
        text, label = load_reference(path, against, repo_root)
        if text is None:
            entry['reference_note'] = f'No copy in {against}: every item is new'
            entry['comparison'] = compare_feeds(entry['feed'], {'channel': {}, 'items': []})
            entry['reference'] = against
        else:
            try:
                entry['comparison'] = compare_feeds(entry['feed'], parse_feed(text))
                entry['reference'] = label
            except ValueError as e:
                entry['reference_note'] = f'Reference {label} could not be read: {e}'
    return entry


def main(argv=None):
    parser = argparse.ArgumentParser(description='Render feed XML as an HTML page for a visual check.')
    parser.add_argument('feeds', nargs='+', help='feed XML files or directories of them')
    parser.add_argument('--against', help='directory of reference feeds, or a git ref (e.g. origin/main)')
    parser.add_argument('-o', '--output', help='HTML file to write (default: system temp directory)')
    parser.add_argument('--open', action='store_true', help='open the page in the default browser')
    args = parser.parse_args(argv)

    files = _feed_files(args.feeds)
    if not files:
        print('No feed XML files found in: ' + ', '.join(args.feeds), file=sys.stderr)
        return 2

    entries = [build_entry(path, args.against) for path in files]
    output = Path(args.output) if args.output else Path(tempfile.gettempdir()) / 'comiccaster-feed-preview.html'
    output.write_text(render_report(entries), encoding='utf-8')

    unreadable = sum(1 for e in entries if e['error'])
    errors = sum(1 for e in entries for f in e['checks'] if f['level'] == 'error')
    print(f'Wrote {output} ({len(entries)} feed(s), {errors} error(s), {unreadable} unreadable)')
    if args.open:
        webbrowser.open(output.resolve().as_uri())
    return 0


if __name__ == '__main__':
    sys.exit(main())
