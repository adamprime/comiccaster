# ComicCaster Deployment

This document covers how ComicCaster is deployed and how feed updates reach subscribers. If you're operating the daily update pipeline on the Mac Mini, see [LOCAL_AUTOMATION_README.md](LOCAL_AUTOMATION_README.md) for the operational details — this file is the higher-level view.

## Architecture

ComicCaster is a static site plus daily-generated RSS feed files, served by Netlify. There is no application server and no database. The moving parts:

| Component | Hosted by | Responsibility |
|---|---|---|
| Static site (`public/`) | Netlify | The landing page, comic list UI, OPML builder UI |
| Serverless functions (`functions/`) | Netlify | `generate-opml.js` (builds OPML bundles on demand), `fetch-feed.js` (feed preview) |
| Feed files (`public/feeds/*.xml`) | Netlify (served as static assets) | Pre-generated RSS per comic |
| Feed update pipeline | Dedicated always-on host, overnight daily | Scrapes sources, generates feeds, commits + pushes to `main` |
| Source data (`data/*.json`) | Git (tracked) | Authoritative pipeline inputs — each scraper writes one per run |

Feed updates are the only thing that happens on a schedule. Every other change is operator-initiated: a push to `main` triggers a Netlify build + deploy.

## Deploy flow

1. The update host scrapes and generates feeds overnight (see [LOCAL_AUTOMATION_README.md](LOCAL_AUTOMATION_README.md))
2. Master update script commits `data/*.json` + `public/feeds/*.xml` to `main` and pushes
3. Netlify webhook fires on push, runs `netlify build` with `public/` as the publish directory
4. Deploy lands at `comiccaster.xyz` (custom domain) within ~30 seconds

No deploy step is manual under normal operation. Feed changes ride the same push path as code changes.

## One-time setup (for a new deployment)

1. **Netlify site**: connect to the GitHub repo; publish directory is `public/`; functions directory is `functions/` (configured via `netlify.toml`). Set env var `NODE_VERSION=14` (newer is fine; pinned for historical reproducibility).
2. **Domain**: point DNS at Netlify per their instructions.
3. **GitHub Actions** for feed updates (`.github/workflows/update-feeds.yml`, `update-feeds-smart.yml`) are intentionally **disabled** — their `schedule:` triggers are commented out. They remain as `workflow_dispatch` fallbacks if the local host is unavailable (travel, hardware failure, etc.). Don't re-enable without confirming the local pipeline is also off; otherwise both will race to push feed updates.
4. **Local update pipeline**: install ChromeDriver, configure a repo deploy key, populate `.env`, and load the LaunchAgents that run the scheduled update and keep the host awake. See [LOCAL_AUTOMATION_README.md](LOCAL_AUTOMATION_README.md) for the operational overview; detailed provisioning steps are kept in operator-only notes.

## Disabled / unused paths

- **Self-hosted Flask deployment** — the `comiccaster/web_interface.py` Flask app is still runnable for local development (`python run_app.py`, port 5001) but not the production serving story. Netlify serves the static site directly.
- **GitHub Actions feed scheduling** — as above, the workflows exist but their `schedule` keys are commented out. `workflow_dispatch` lets you trigger them manually as emergency backup.

## Deploy rollback

Netlify keeps a history of deploys under the site dashboard. To roll back:

1. Find the last known-good deploy in the Netlify "Deploys" list
2. Click "Publish deploy" on that entry

This reverts what's served without touching the Git history. If the root cause was a bad feed commit, also revert the offending commit on `main` so the next Mini run starts from a clean state.

## Monitoring

- Netlify build status: https://app.netlify.com/sites/comiccaster/deploys (maintainer access)
- Pipeline logs: `logs/master_update.log` on the update host
- Issues / vulnerability reports: [SECURITY.md](../SECURITY.md)

## Supported comic sources

For the current list of sources and scraper quirks, see [AGENTS.md](../AGENTS.md).

## See also

- [LOCAL_AUTOMATION_README.md](LOCAL_AUTOMATION_README.md) — Mac Mini operational guide
- [TESTING_GUIDE.md](TESTING_GUIDE.md) — running the test suite
- [STATUS.md](STATUS.md) — current project state
- [AGENTS.md](../AGENTS.md) — AI-assistant-facing repo guide
