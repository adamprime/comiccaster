#!/usr/bin/env python3
"""Watch the public feedback feed and open issues for new posts.

Idempotent: each post on https://feedback.comiccaster.xyz becomes at most one
GitHub issue, identified by a "Source: <url>" line in the issue body. Designed
to run from CI on a schedule; uses the `gh` CLI (pre-installed on runners).
"""

import json
import subprocess
import sys

import feedparser

FEED_URL = "https://feedback.comiccaster.xyz/feed/global.atom"
LABEL = "feedback-site"
LABEL_COLOR = "5319e7"
SOURCE_PREFIX = "Source: "


def gh(*args: str) -> str:
    return subprocess.run(
        ["gh", *args], check=True, capture_output=True, text=True
    ).stdout


def ensure_label() -> None:
    existing = json.loads(gh("label", "list", "--json", "name", "--limit", "200"))
    if any(label["name"] == LABEL for label in existing):
        return
    gh(
        "label", "create", LABEL,
        "--description", "Reported on feedback.comiccaster.xyz",
        "--color", LABEL_COLOR,
    )


def known_post_urls() -> set[str]:
    issues = json.loads(
        gh(
            "issue", "list",
            "--label", LABEL,
            "--state", "all",
            "--limit", "500",
            "--json", "body",
        )
    )
    urls = set()
    for issue in issues:
        for line in (issue.get("body") or "").splitlines():
            if line.startswith(SOURCE_PREFIX):
                urls.add(line[len(SOURCE_PREFIX):].strip())
    return urls


def open_issue(entry) -> None:
    title = entry.title.strip()
    author = getattr(entry, "author", "unknown")
    published = getattr(entry, "published", getattr(entry, "updated", "unknown"))
    body = (
        "New post on the feedback site.\n\n"
        f"- Title: {title}\n"
        f"- Author: {author}\n"
        f"- Published: {published}\n"
        f"\n{SOURCE_PREFIX}{entry.link}\n"
    )
    gh(
        "issue", "create",
        "--title", f"[feedback-site] {title}",
        "--body", body,
        "--label", LABEL,
    )


def main() -> int:
    feed = feedparser.parse(FEED_URL)
    if not feed.entries:
        if feed.bozo:
            print(f"feed parse error: {feed.bozo_exception}", file=sys.stderr)
            return 1
        print("feed has no entries, nothing to do")
        return 0

    ensure_label()
    seen = known_post_urls()
    new_entries = [e for e in feed.entries if e.link not in seen]
    print(
        f"feed entries: {len(feed.entries)}, "
        f"already tracked: {len(seen)}, new: {len(new_entries)}"
    )
    for entry in new_entries:
        print(f"opening issue: {entry.title}")
        open_issue(entry)
    return 0


if __name__ == "__main__":
    sys.exit(main())
