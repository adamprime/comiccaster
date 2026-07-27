#!/usr/bin/env python3
"""Open, update, and close GitHub issues for pipeline failures.

The daily pipeline is unattended (03:05 and 13:00), so its macOS desktop
notification is effectively invisible. This turns a failure into a durable,
remote alert: one GitHub issue per failing source, identified by a
"Pipeline-Failure-Key: <slug>" line in the issue body.

State machine, evaluated per source in --covered:

    failing, no open issue    -> open one
    failing, open issue       -> comment on it
    healthy, open issue       -> comment and close it
    healthy, no open issue    -> nothing

--covered is what makes this safe to run from both passes. Pass 2 scrapes
GoComics only, so it covers only GoComics; without that scoping it would
auto-close a Comics Kingdom issue merely because CK wasn't in its failure
list -- CK isn't healthy, it simply wasn't examined.

Uses the `gh` CLI, which is installed and authenticated on the pipeline host.
Never raises into the pipeline: gh errors are logged and reported via exit
code, and the caller invokes this with `|| true`.
"""

import argparse
import json
import subprocess
import sys

LABEL = "pipeline-failure"
LABEL_COLOR = "b60205"
MARKER_PREFIX = "Pipeline-Failure-Key: "
LOG_TAIL_LINES = 40

# Display names for the pipeline's stable slugs. `push` and `preflight` are
# pseudo-sources: whole-run failures that aren't tied to one comic source.
SOURCE_NAMES = {
    "gocomics": "GoComics",
    "comicskingdom": "Comics Kingdom",
    "tinyview": "TinyView",
    "newyorker": "New Yorker",
    "farside": "Far Side",
    "creators": "Creators",
    "mrboffo": "Mr. Boffo",
    "push": "Git push",
    "preflight": "SSH preflight",
}


def gh(*args: str) -> str:
    return subprocess.run(
        ["gh", *args], check=True, capture_output=True, text=True
    ).stdout


def parse_failed(raw: str) -> dict:
    """Parse "slug:kind,slug:kind" into {slug: kind}."""
    failed = {}
    for entry in (raw or "").split(","):
        entry = entry.strip()
        if not entry:
            continue
        slug, _, kind = entry.partition(":")
        failed[slug.strip()] = kind.strip() or "unknown"
    return failed


def parse_covered(raw: str) -> list:
    return [s.strip() for s in (raw or "").split(",") if s.strip()]


def display_name(slug: str) -> str:
    return SOURCE_NAMES.get(slug, slug)


def issue_title(slug: str, kind: str) -> str:
    return f"[pipeline] {display_name(slug)} {kind} failed"


def issue_body(slug: str, kind: str, run: str, date: str, log_tail: str) -> str:
    body = (
        f"The {run} pipeline run on {date} reported a **{kind}** failure for "
        f"**{display_name(slug)}**.\n\n"
        f"- Source: {display_name(slug)} (`{slug}`)\n"
        f"- Failure: {kind}\n"
        f"- Run: {run}\n"
        f"- First seen: {date}\n\n"
        "This issue closes itself automatically when this source next succeeds.\n"
    )
    if log_tail:
        body += f"\n<details><summary>Log tail</summary>\n\n```\n{log_tail}\n```\n\n</details>\n"
    body += f"\n{MARKER_PREFIX}{slug}\n"
    return body


def recurrence_comment(slug: str, kind: str, run: str, date: str, log_tail: str) -> str:
    comment = (
        f"Still failing: **{kind}** on the {run} run of {date}.\n"
    )
    if log_tail:
        comment += f"\n<details><summary>Log tail</summary>\n\n```\n{log_tail}\n```\n\n</details>\n"
    return comment


def recovery_comment(slug: str, run: str, date: str) -> str:
    return (
        f"Recovered: {display_name(slug)} succeeded on the {run} run of {date}. "
        "Closing automatically.\n"
    )


def ensure_label() -> None:
    existing = json.loads(gh("label", "list", "--json", "name", "--limit", "200"))
    if any(label["name"] == LABEL for label in existing):
        return
    gh(
        "label", "create", LABEL,
        "--description", "Automated feed pipeline failure",
        "--color", LABEL_COLOR,
    )


def open_issues_by_key() -> dict:
    """Map marker key -> issue number for every open pipeline-failure issue.

    Deliberately does NOT filter by label: GitHub's label-filtered listing is
    eventually consistent and can omit an issue for a minute or so after it is
    created, which made a second run open a duplicate instead of commenting.
    The body marker is the authoritative identifier, so we scan open issues and
    match on that. The label stays purely for human filtering.

    On the rare duplicate (same marker on two issues), the oldest wins so that
    repeated runs converge on one issue instead of alternating.
    """
    issues = json.loads(
        gh(
            "issue", "list",
            "--state", "open",
            "--limit", "200",
            "--json", "number,body",
        )
    )
    found = {}
    for issue in issues:
        for line in (issue.get("body") or "").splitlines():
            if line.startswith(MARKER_PREFIX):
                key = line[len(MARKER_PREFIX):].strip()
                number = issue["number"]
                if key not in found or number < found[key]:
                    found[key] = number
    return found


def read_log_tail(path: str) -> str:
    if not path:
        return ""
    try:
        with open(path, "r", errors="replace") as handle:
            lines = handle.read().splitlines()
    except OSError as exc:
        print(f"could not read log file {path}: {exc}", file=sys.stderr)
        return ""
    return "\n".join(lines[-LOG_TAIL_LINES:])


def report(covered, failed, run, date, log_tail="") -> int:
    """Reconcile GitHub issues against this run's outcome.

    Returns 0 if every source was reported successfully, 1 otherwise. Never
    raises -- one source's gh error must not suppress the others' alerts.
    """
    # Always listed, even on a clean run: a previously-failing covered source
    # needs its issue closed.
    try:
        existing = open_issues_by_key()
    except (subprocess.CalledProcessError, ValueError) as exc:
        print(f"could not list existing issues: {exc}", file=sys.stderr)
        return 1

    # A slug in --failed but not --covered still deserves an alert; covering it
    # implicitly means we never silently drop a reported failure.
    targets = list(covered) + [s for s in failed if s not in covered]

    if failed:
        try:
            ensure_label()
        except (subprocess.CalledProcessError, ValueError) as exc:
            print(f"could not ensure label: {exc}", file=sys.stderr)
            return 1

    errors = 0
    for slug in targets:
        number = existing.get(slug)
        try:
            if slug in failed:
                kind = failed[slug]
                if number is None:
                    gh(
                        "issue", "create",
                        "--title", issue_title(slug, kind),
                        "--body", issue_body(slug, kind, run, date, log_tail),
                        "--label", LABEL,
                    )
                    print(f"opened issue for {slug} ({kind})")
                else:
                    gh(
                        "issue", "comment", str(number),
                        "--body", recurrence_comment(slug, kind, run, date, log_tail),
                    )
                    print(f"commented on #{number} for {slug} ({kind})")
            elif number is not None:
                gh(
                    "issue", "comment", str(number),
                    "--body", recovery_comment(slug, run, date),
                )
                gh("issue", "close", str(number))
                print(f"closed #{number}: {slug} recovered")
        except (subprocess.CalledProcessError, ValueError) as exc:
            stderr = getattr(exc, "stderr", "")
            print(f"failed to report {slug}: {exc} {stderr}", file=sys.stderr)
            errors += 1

    return 1 if errors else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, help="pipeline run label, e.g. pass1")
    parser.add_argument("--date", required=True, help="run date, YYYY-MM-DD")
    parser.add_argument(
        "--covered", required=True,
        help="comma-separated slugs this run actually examined",
    )
    parser.add_argument(
        "--failed", default="",
        help="comma-separated slug:kind entries that failed",
    )
    parser.add_argument("--log-file", default="", help="log file to excerpt")
    args = parser.parse_args(argv)

    return report(
        parse_covered(args.covered),
        parse_failed(args.failed),
        args.run,
        args.date,
        read_log_tail(args.log_file),
    )


if __name__ == "__main__":
    sys.exit(main())
