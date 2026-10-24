---
title: Merging a Dependabot bump does not update the host venv the pipeline runs from
date: 2026-08-24
category: best-practices
module: pipeline
problem_type: config-drift
component: requirements.txt / venv/ on the always-on host
severity: medium
applies_when:
  - "Dependabot PRs have been merged but scraper behavior on the host is unchanged"
  - "CI is green on a dependency bump yet the nightly run still hits an old library bug"
  - "Reproducing a pipeline failure locally gives a different result than the host does"
  - "Auditing what version of selenium/requests the production scrapers actually load"
  - "A CVE is fixed upstream and CI already tests the fixed version, but the host may still run the vulnerable one"
  - "A vulnaudit pipeline issue opened, or a dependency is being removed rather than bumped"
tags: [dependencies, dependabot, venv, drift, selenium, pipeline, ci-vs-production, constraints, security, brotli, osv, pip-audit, certifi, ci]
stack: [python, github-actions]
github_prs: [163, 170, 182, 186, 189, 243, 245, 247, 249]
last_updated: 2026-10-24
---

## TL;DR

`requirements.txt` is the *declared* dependency set. The daily pipeline executes
from `venv/` on the always-on host. Nothing connects the two automatically, so
merging a bump advances the declaration while production keeps running the old
library. Run `venv/bin/python -m pip install -r requirements.txt -c constraints.txt`
on the host after merging dependency PRs. It is the step that makes the bump
real. Since 2026-08-25, `constraints.txt` locks every transitive on the host, so
a fix only reaches production once it is in **that** file. Until 2026-10-24
CI never read it. That's how the host was still on the vulnerable brotli 1.2.0
while CI tested 1.2.1 (see "Security fixes" below). CI's Tests job now
installs with it too (see "CI now tests the lock").

## What was observed

On 2026-08-24, five Dependabot PRs were open. Before merging, the host venv held:

| package      | venv had | requirements.txt pinned |
|--------------|----------|-------------------------|
| selenium     | 4.44.0   | 4.46.0                  |
| pytest       | 9.1.0    | 9.1.1                   |

The venv was **two selenium minors behind the pin that was already on `main`** —
drift accumulated from earlier merges, not from the PRs being reviewed that day.

## Why it is easy to miss

Every signal available in the PR says "shipped":

- Until 2026-10-24, CI installed `requirements.txt` unconstrained into a clean
  runner, so it always tested the *newest* versions and always went green. It
  now installs with `-c constraints.txt` (see "CI now tests the lock").
- Netlify redeploys on push, which makes the merge feel like a deployment.
- The nightly pipeline keeps reporting ALL SUCCESS, because it is succeeding —
  just with the old libraries.

None of those touch `venv/`. Netlify serves the static feeds; it does not run
the scrapers. The scrapers run on the host, from the venv, and only a manual
`pip install` moves that forward.

## The check

```bash
# What production actually loads, vs. what main declares:
venv/bin/python -m pip list | grep -iE "^(selenium|pytz|feedparser|python-dotenv|requests) "
cat requirements.txt
```

## The fix, and how to verify it

```bash
git pull --ff-only                                 # get the merged pins (tree must be clean)
venv/bin/python -m pip freeze > /tmp/before.txt
venv/bin/python -m pip install -r requirements.txt -c constraints.txt   # make them real
venv/bin/python -m pip freeze | diff /tmp/before.txt -                  # only the bumped lines should move
venv/bin/python -m pytest -q                       # 819 passed on 2026-10-24
```

Run it in the pipeline clone only on a clean tree. Pass 1 and Pass 2 begin
with `git reset --hard origin/main`, so a half-finished edit there is silently
wiped at 03:05 or 13:00 rather than blocking the run. Build any change in a
`git worktree`, and test it in a throwaway venv made from the production venv's
base interpreter (`/opt/homebrew/opt/python@3.14/bin/python3.14`). Bare
`python3` on the host is Apple's 3.9.6, which `setup.py` rejects. Upgrade pip
in the throwaway venv first: Homebrew's 3.14 seeds new venvs with pip 25.3,
which the audit flags with five CVEs and which, like every pip below 26.2.2,
trusts the compromised emSign CAs (see "pip carries its own certifi").

For a **selenium** bump specifically, `pytest` is necessary but *not* sufficient:
the suite mocks the browser by design (see CLAUDE.md — unit tests never touch
live sources), so it exercises none of the driver API that actually changed.
Smoke-test the real driver path before the next scheduled run:

```python
from selenium.webdriver.chrome.options import Options
from comiccaster.webdriver_setup import build_chrome_driver
o = Options()
for f in ("--headless=new", "--no-sandbox", "--disable-dev-shm-usage"):
    o.add_argument(f)
d = build_chrome_driver(o)
print(d.capabilities["browserVersion"], d.capabilities["chrome"]["chromedriverVersion"])
d.quit()
```

That confirms `webdriver_manager` still resolves a ChromeDriver matching the
installed Chrome under the new selenium — the exact failure mode from the
2026-06-09 incident documented in `comiccaster/webdriver_setup.py`.

Note that loading a GoComics URL in this smoke test returns an
"Establishing a secure connection" interstitial. That is the site's bot check
answering a bare headless browser, **not** a selenium regression — the
production GoComics path authenticates separately. Judge the smoke test on
whether the driver launches, reports versions, and quits cleanly.

## Security fixes: the lock holds them back too (2026-10-24)

`constraints.txt` made the host reproducible, which also means a transitive
security fix never arrives on its own. CVE-2026-111497 (Brotli decoder memory
corruption, CVSS 9.2) was fixed in PyPI `Brotli` 1.2.1 on 2026-10-22. Two days
later:

| where | brotli | why |
|---|---|---|
| CI | 1.2.1 | installs `requirements.txt` unconstrained; `>=1.2.0` resolved the newest |
| host venv | 1.2.0 | `constraints.txt` pinned `brotli==1.2.0` |

Every PR stayed green, and the pipeline kept reporting ALL SUCCESS, on the
vulnerable version. The "CI is the canary" design is working as intended
here: CI showed 1.2.1 broke nothing. But that only helps if someone then moves
the lock.

**The `Accept-Encoding` header doesn't protect us.** `comiccaster/http_client.py`
sends `Accept-Encoding: gzip, deflate`, but urllib3 picks its decoder from the
*response's* `Content-Encoding` (`urllib3/response.py`, `CONTENT_DECODERS`) and
includes `br` whenever brotli is importable. Any site a scraper fetches could
send a `br` body, and that's how a compromised comic site reaches the decoder.

**The fix (#243)** bumped both files: `constraints.txt` to `brotli==1.2.1`
(what the host installs) and `requirements.txt` to `brotli>=1.2.1` (so an
unconstrained install can't resolve the vulnerable version). Then run the
install and verification above. The freeze diff should show only the brotli
line.

**Why nothing proposed it sooner:** Dependabot version updates run weekly
(they do edit `constraints.txt`; see pluggy, #241), and Dependabot
security-update PRs were turned off. **They were turned on on 2026-10-24**, so
the next transitive CVE should arrive as a PR as soon as GitHub publishes an
advisory. That PR is still only half the fix. Merging it changes the files,
and the host only changes when you run the install above.

### Watching what the host runs

Turning on Dependabot security updates still left a gap: Dependabot reads the
repository, so it can't see a host that lags the repo. Since 2026-10-24 every
Pass 1 runs `scripts/check_vulnerabilities.py` from the venv. It lists every
installed package with `pip list` (transitives included) and asks OSV (the
source of PyPI's advisory data, and a pip-audit backend) about those exact
versions. A hit opens a `vulnaudit` issue. That issue is deliberately generic,
because the repo is public; run the script on the host for the package, the
advisory and the fix version. When OSV is unreachable the audit only warns
(exit 75), and that run doesn't count `vulnaudit` as covered, so an open issue
stays open.

Its first real run found a second hole the same day. The host had certifi
2026.7.22, which ships emSign roots whose intermediate keys were compromised
(GHSA-6q48-6c7w-9gw2, critical, fixed in 2026.10.19). CI and every PR were
green on it. #247 pinned 2026.10.19, the release the PSF recommends. 2026.10.23
is an automated bundle sync that also drops two emSign roots (C1, ECC C3) that
10.19 had deliberately restored as unaffected; neither release has an advisory.

**pip carries its own certifi.** pip vendors a copy (`pip._vendor.certifi`) and
uses it for every download from PyPI, whatever certifi package the venv has.
Every pip below 26.2.2 kept trusting the compromised emSign CAs
(discuss.python.org/t/109576). The host's pip 26.2.1 vendored certifi
2026.06.17, and OSV has no advisory for pip itself, so the audit could not see
it, even though Pass 1 and Pass 2 download through it on every run
(`pip install -e .`). Upgrade pip from a hash-pinned wheel, so the upgrade
itself can't be swapped in transit, and before installing anything else:

```bash
venv/bin/python -m pip install "pip @ https://files.pythonhosted.org/packages/3f/06/3e4420302363fbb71be3c7f35ce042f54bfca330e3e66b3a2e3c4cca579f/pip-26.2.2-py3-none-any.whl#sha256=fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70"
venv/bin/python -c "import pip._vendor.certifi as c; print(c.__version__)"   # 2026.10.19
```

Check the hash against PyPI's own JSON API (`https://pypi.org/pypi/pip/<version>/json`),
not only against the advisory that quotes it.

Fewer packages also means fewer holes. The same change removed APScheduler,
tzlocal and requests-toolbelt, which nothing imported. Removing a package
takes one more step than adding one: `pip install -r requirements.txt -c
constraints.txt` never uninstalls anything. And `setup.py` declared
APScheduler and requests-toolbelt too, and the pipeline runs `pip install -e .`
on every pass, which would quietly reinstall them. So drop the package from `setup.py` as well,
merge, then refresh the editable install *before* uninstalling:

```bash
git pull --ff-only
venv/bin/python -m pip install -e . -c constraints.txt   # re-reads setup.py's install_requires
venv/bin/python -m pip uninstall -y APScheduler tzlocal requests-toolbelt
venv/bin/python -m pip install -r requirements.txt -c constraints.txt   # should be a no-op
venv/bin/python -m pip check
```

## CI now tests the lock (2026-10-24)

CI used to install unconstrained on purpose, as a canary for new transitive
releases. The cost showed twice in one day: CI was green on patched brotli and
certifi while the host ran the vulnerable versions, so a green PR said nothing
about production. GitHub's dependency graph doesn't help either. It reads only
`requirements.txt` and `setup.py`, so Dependabot alerts can't see a transitive
pin.

Now the PR-time Tests job (`tests.yml`) installs with `-c constraints.txt`, the
set the host runs. The canary moved to `dependency-canary.yml`, a weekly (and
manual) unconstrained run with no `pull_request` trigger, so it never shows up
on a PR. (Neither job is a required check; see
`docs/solutions/best-practices/github-merge-without-required-checks.md`.) It prints which packages resolved past their pins, then runs the suite.
A canary failure that Tests doesn't reproduce means a new transitive release
broke us.

One consequence is intended: bumping a direct dependency in `requirements.txt`
without moving its `constraints.txt` pin now fails Tests with a resolution
conflict. Bump both, so the version that turns CI green is the one the host
will install.

## Timing

Do the sync in the window between runs, not just before one. Pass 1 is 03:05,
the Far Side morning pass runs every 30 minutes from 03:30 to 12:00 (from the
same venv), and Pass 2 is 13:00 (GoComics only). So the open window is from
when Pass 2 finishes until about 02:45. An afternoon or evening sync leaves
hours to notice a problem before Pass 1; a 02:55 sync does not.

Run each step under the pipeline lock, so it waits for a run in progress
instead of landing during it:

```bash
/usr/bin/lockf -k -t 1800 logs/pipeline.lock venv/bin/python -m pip install -r requirements.txt -c constraints.txt
```

Checking `launchctl list | grep -i comiccaster` for a PID is not enough on its
own: a morning-pass slot can start between the check and the install. Write the
`lockf` prefix out in full on each command, because zsh won't word-split it out
of a variable. See
`docs/solutions/best-practices/parallel-sessions-on-the-live-pipeline-checkout.md`.

## Related

- `docs/solutions/logic-errors/silent-empty-scrape-passed-as-success.md` — the
  other case where the pipeline reported success while doing nothing useful.
