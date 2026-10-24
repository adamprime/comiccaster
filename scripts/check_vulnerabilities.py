#!/usr/bin/env python3
"""Audit the packages installed in the host venv against the OSV database.

CVE-2026-111497 (#243) showed a gap no other signal covered. CI installs
`requirements.txt` unconstrained, so it was already testing the patched brotli
1.2.1 and stayed green. The host venv installs with `-c constraints.txt`, which
still pinned the vulnerable 1.2.0. Dependabot reads the repository, not the
host. Nothing looked at what production actually runs.

This does. It lists what is installed in the venv (`pip list`, every transitive
included) and asks OSV (https://osv.dev) -- the source of PyPI's own advisory
data and one of pip-audit's two backends -- whether any of those exact versions
has a known vulnerability. It talks to the
OSV API directly with the `requests` the pipeline already depends on, rather
than installing pip-audit and its dozen dependencies into the venv it audits.

Exit codes, which the pipeline reads:

  *  0 -- audited, nothing known-vulnerable.
  *  1 -- a known-vulnerable package, or the audit could not run. Alerts. A
         probe that failed to run must never read as healthy, so a rejected
         query, a malformed answer, a TLS failure or a broken `pip list` all
         land here.
  * 75 -- OSV was unreachable (EX_TEMPFAIL): DNS, timeout, connection, or a
         5xx/429 from OSV. Warns only, and the pipeline does not count the
         audit as covered that run, so an open issue stays open.

What this cannot see: the interpreter itself, Homebrew's shared libraries
(Node loads Homebrew's libbrotli, not this venv's), and npm packages. It audits
Python packages only.

**This script has no flag to print its findings into an alert body, and that is
deliberate**, as with check_host_config.py: the alert opens an issue on a
public repository, and which package on the host is exploitable, by which CVE,
is not something to advertise there while the hole is still open. The
specifics stay in the local run log.
"""

import argparse
import json
import re
import subprocess
import sys

import requests

OSV_QUERYBATCH_URL = "https://api.osv.dev/v1/querybatch"
OSV_VULN_URL = "https://api.osv.dev/v1/vulns/{}"
HTTP_TIMEOUT_SECONDS = 30

# sysexits.h EX_TEMPFAIL: a transient failure; the next run retries.
EX_UNREACHABLE = 75


class AuditError(Exception):
    """The audit could not produce a trustworthy answer. Alerts."""


class AuditUnreachable(AuditError):
    """OSV could not be reached. Transient: warns, does not alert."""


def canonical_name(name):
    """PEP 503 name, which is how OSV keys PyPI packages."""
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_pip_list(raw):
    """[(name, version)] from `pip list --format=json`."""
    try:
        return [
            (canonical_name(entry["name"]), entry["version"])
            for entry in json.loads(raw)
        ]
    except (ValueError, TypeError, KeyError) as exc:
        raise AuditError(f"could not parse `pip list` output: {exc!r}") from exc


def list_installed(python):
    """Everything installed for `python`. Impure; `parse_pip_list` holds the logic.

    Editable installs are excluded: comiccaster itself is not on PyPI, and
    querying its name could match an unrelated project's advisories.
    """
    cmd = [python, "-m", "pip", "list", "--format=json", "--exclude-editable"]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120, check=False
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise AuditError(f"could not run `pip list` for {python}: {exc}") from exc
    if result.returncode != 0:
        raise AuditError(
            f"`pip list` failed for {python}: {result.stderr.strip()}"
        )
    return parse_pip_list(result.stdout)


def osv_request(url, payload=None):
    """POST `payload` to OSV (GET when None) and return the decoded JSON.

    Sorts failures into transient (AuditUnreachable) and broken (AuditError).
    The line matters: a broken check filed as transient would warn every day
    while the host went unaudited and every run read green.
    """
    try:
        if payload is None:
            response = requests.get(url, timeout=HTTP_TIMEOUT_SECONDS)
        else:
            response = requests.post(url, json=payload, timeout=HTTP_TIMEOUT_SECONDS)
    except requests.exceptions.SSLError as exc:
        # Subclasses ConnectionError, but a certificate failure repeats daily.
        raise AuditError(f"TLS failure talking to OSV: {exc}") from exc
    except (
        requests.ConnectionError,
        requests.Timeout,
        requests.exceptions.ChunkedEncodingError,
    ) as exc:
        raise AuditUnreachable(f"could not reach OSV: {exc}") from exc

    if response.status_code == 429 or response.status_code >= 500:
        raise AuditUnreachable(f"OSV answered HTTP {response.status_code}")
    if response.status_code != 200:
        raise AuditError(f"OSV rejected the query: HTTP {response.status_code}")
    try:
        return response.json()
    except ValueError as exc:
        raise AuditError("OSV answered with something that is not JSON") from exc


def query_osv(packages):
    """{(name, version): [vuln ids]} for each package OSV knows a vuln in."""
    body = {"queries": [
        {"package": {"name": name, "ecosystem": "PyPI"}, "version": version}
        for name, version in packages
    ]}
    answer = osv_request(OSV_QUERYBATCH_URL, body)

    try:
        results = answer["results"]
        if not isinstance(results, list):
            raise TypeError("results is not a list")
        if len(results) != len(packages):
            # zip() would quietly drop the unanswered packages from the audit.
            raise AuditError(
                f"OSV returned {len(results)} results for {len(packages)} packages"
            )
        hits = {}
        for package, result in zip(packages, results):
            ids = [vuln["id"] for vuln in result.get("vulns", [])]
            if ids:
                hits[package] = ids
        return hits
    except (KeyError, TypeError, AttributeError) as exc:
        raise AuditError(f"unexpected OSV response shape: {exc!r}") from exc


def fixed_versions(vuln, name):
    """Versions that fix `vuln` for package `name`, in OSV's order."""
    fixed = []
    for affected in vuln.get("affected") or []:
        if canonical_name(affected.get("package", {}).get("name", "")) != name:
            continue
        for version_range in affected.get("ranges") or []:
            for event in version_range.get("events") or []:
                if "fixed" in event and event["fixed"] not in fixed:
                    fixed.append(event["fixed"])
    return fixed


def describe(name, ids):
    """One finding per distinct advisory.

    OSV returns the same flaw under several ids (a GHSA and a PYSEC for the
    brotli CVE), each listing the others as aliases, so report each flaw once.
    """
    findings = []
    covered = set()
    for vuln_id in ids:
        if vuln_id in covered:
            continue
        covered.add(vuln_id)
        try:
            vuln = osv_request(OSV_VULN_URL.format(vuln_id))
        except AuditError:
            # The batch query already proved the finding. Details only make it
            # actionable, so losing them must not lose the finding.
            findings.append({"id": vuln_id, "label": vuln_id, "summary": "", "fixed": []})
            continue
        if vuln.get("withdrawn"):
            continue
        aliases = vuln.get("aliases") or []
        covered.update(aliases)
        cves = [alias for alias in aliases if alias.startswith("CVE-")]
        findings.append({
            "id": vuln_id,
            "label": cves[0] if cves else vuln_id,
            "summary": vuln.get("summary") or "",
            "fixed": fixed_versions(vuln, name),
        })
    return findings


def audit(packages):
    """[(name, version, findings)] for every known-vulnerable package."""
    if not packages:
        raise AuditError("no installed packages found; an audit of nothing is not clean")
    report = []
    for (name, version), ids in query_osv(packages).items():
        findings = describe(name, ids)
        if findings:
            report.append((name, version, findings))
    return report


def evaluate(report, package_count, python):
    """Return (status, detail) where status is 'ok' or 'vulnerable'."""
    if not report:
        return "ok", (
            f"No known vulnerabilities in the {package_count} packages installed "
            f"for {python} (OSV)."
        )

    lines = []
    for name, version, findings in report:
        for finding in findings:
            label = finding["label"]
            if finding["id"] != label:
                label += f" ({finding['id']})"
            fix = (
                "fixed in " + " or ".join(finding["fixed"])
                if finding["fixed"] else "no fixed version published yet"
            )
            summary = f": {finding['summary']}" if finding["summary"] else ""
            lines.append(f"{name} {version} -- {label}{summary}; {fix}")
    return "vulnerable", (
        f"Known-vulnerable packages installed for {python}:\n  - "
        + "\n  - ".join(lines)
        + "\nBump the pin in constraints.txt (and requirements.txt for a direct "
        "dependency), then run: venv/bin/python -m pip install -r "
        "requirements.txt -c constraints.txt"
    )


def main(argv=None) -> int:
    """Print the verdict locally and signal via exit code (see the module doc)."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--python", default=sys.executable,
        help="interpreter whose packages to audit (default: the one running "
             "this script, which in the pipeline is the activated host venv)",
    )
    args = parser.parse_args(argv)

    try:
        packages = list_installed(args.python)
        status, detail = evaluate(audit(packages), len(packages), args.python)
    except AuditUnreachable as exc:
        status, detail = "unreachable", (
            f"Vulnerability audit skipped: {exc}. This is a warning, not an "
            "alert; the next run retries."
        )
    except AuditError as exc:
        status, detail = "error", f"Vulnerability audit could not run: {exc}"

    icon = {"ok": "✅", "unreachable": "⚠️ ", "vulnerable": "❌", "error": "❌"}[status]
    print(f"{icon} {detail}")

    return {"ok": 0, "unreachable": EX_UNREACHABLE}.get(status, 1)


if __name__ == "__main__":
    sys.exit(main())
