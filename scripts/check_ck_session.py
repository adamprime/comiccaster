#!/usr/bin/env python3
"""Report when the Comics Kingdom session token expires.

CK issues a **7-day** token, and the operator reauths on a 7-day cadence, so
the safety margin is hours rather than days. A reauth that silently fails to
mint a new token is therefore an outage the next morning -- which is exactly
what happened on 2026-07-28.

This makes that invisible clock visible. Run it:

  * right after a reauth, to confirm the expiry actually moved ~7 days out
    (`reauth_comicskingdom.py` does this automatically);
  * from the daily pipeline, to alert while there is still time to act.

Reads the expiry straight out of the Chrome profile's cookie store. The store
is copied before querying, so this is safe to run while Chrome holds the
profile open and never mutates the operator's session.

**What this cannot tell you.** It measures cookie expiry, which is not session
health. CK refreshes that expiry on *any* visit, including one it redirects to
the login page -- so a dead session keeps reporting "7.0 days remaining"
indefinitely. On 2026-08-05 this printed a green line during the very run in
which the scraper was rejected. A live session is proven only by a successful
`is_authenticated` / scrape, so the passing message says so explicitly rather
than implying health it never checked.

The value that *is* real is `describe_renewal`: run after a reauth, it catches
a login that looked fine in the browser but left no new token on disk.
"""

import argparse
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROFILE_DIR = Path.home() / ".comicskingdom_chrome_profile"
CK_HOST = "comicskingdom.com"
TOKEN_NAME = "__Secure-next-auth.session-token"

# The token lasts 7 days and the daily run needs it at 03:06, so warning at 2
# days leaves two whole mornings to act before anything breaks.
DEFAULT_WARN_DAYS = 2

# Chrome stores timestamps as microseconds since 1601-01-01 UTC.
CHROME_EPOCH_OFFSET_SECONDS = 11644473600


def chrome_time_to_datetime(expires_utc: int):
    """Convert a Chrome timestamp to UTC. 0 means a session-only cookie."""
    if not expires_utc:
        return None
    unix_seconds = expires_utc / 1_000_000 - CHROME_EPOCH_OFFSET_SECONDS
    return datetime.fromtimestamp(unix_seconds, tz=timezone.utc)


def datetime_to_chrome_time(when: datetime) -> int:
    return int((when.timestamp() + CHROME_EPOCH_OFFSET_SECONDS) * 1_000_000)


def read_token_expiry(profile_dir):
    """Return the auth token's expiry, or None if absent/unreadable.

    Copies the cookie DB first: Chrome may hold a lock on it, and we must never
    write to the operator's live profile.
    """
    db_path = Path(profile_dir) / "Default" / "Cookies"
    if not db_path.exists():
        return None

    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "Cookies"
        try:
            shutil.copy2(db_path, copy)
            conn = sqlite3.connect(f"file:{copy}?mode=ro", uri=True)
            try:
                row = conn.execute(
                    "SELECT expires_utc FROM cookies "
                    "WHERE host_key = ? AND name = ?",
                    (CK_HOST, TOKEN_NAME),
                ).fetchone()
            finally:
                conn.close()
        except (OSError, sqlite3.Error) as exc:
            print(f"could not read cookie store: {exc}", file=sys.stderr)
            return None

    return chrome_time_to_datetime(row[0]) if row else None


def days_remaining(expiry: datetime, now: datetime) -> float:
    return (expiry - now).total_seconds() / 86400.0


def evaluate(expiry, now: datetime, warn_days: float):
    """Return (status, detail). Status is ok | expiring | expired | missing."""
    if expiry is None:
        return "missing", (
            "No Comics Kingdom session token found in the Chrome profile. "
            "Run scripts/reauth_comicskingdom.py."
        )

    remaining = days_remaining(expiry, now)
    stamp = expiry.strftime("%Y-%m-%d %H:%M UTC")

    if remaining <= 0:
        return "expired", (
            f"Comics Kingdom session EXPIRED {abs(remaining):.1f} days ago "
            f"(expired {stamp}). Run scripts/reauth_comicskingdom.py."
        )
    if remaining <= warn_days:
        return "expiring", (
            f"Comics Kingdom session expires in {remaining:.1f} days ({stamp}). "
            "Run scripts/reauth_comicskingdom.py."
        )
    return "ok", (
        f"Comics Kingdom session cookie present, expires in {remaining:.1f} days "
        f"({stamp}). This does NOT mean the session works -- CK refreshes the "
        "expiry even on requests it rejects, so only a scrape proves it is live."
    )


def describe_renewal(before, after, now: datetime):
    """Compare token expiry across a reauth. Returns (renewed, message).

    This is the check that catches a reauth which *looked* fine in the browser
    but left no new token on disk: the login page redirects, the operator sees
    a logged-in page, and the old expiry is still sitting there unchanged.
    """
    if after is None:
        return False, (
            "No session token on disk after login. The session did NOT persist. "
            "Re-run the reauth and let the script close the browser itself "
            "rather than closing the window by hand."
        )

    stamp = after.strftime("%Y-%m-%d %H:%M UTC")
    remaining = days_remaining(after, now)

    if before is not None and after <= before:
        return False, (
            f"Session expiry did NOT move (still {stamp}). The login did not "
            "produce a new token, so it will expire on the old schedule "
            f"({remaining:.1f} days). Re-run the reauth."
        )

    return True, (
        f"Session renewed: expires {stamp} ({remaining:.1f} days from now)."
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile", default=str(PROFILE_DIR),
        help="Chrome profile directory to inspect",
    )
    parser.add_argument(
        "--warn-days", type=float, default=DEFAULT_WARN_DAYS,
        help="warn when fewer than this many days remain",
    )
    parser.add_argument("--quiet", action="store_true", help="suppress output")
    parser.add_argument(
        "--detail-only", action="store_true",
        help="print just the one-line detail (for the alert body)",
    )
    args = parser.parse_args(argv)

    expiry = read_token_expiry(args.profile)
    status, detail = evaluate(expiry, datetime.now(timezone.utc), args.warn_days)

    if args.detail_only:
        print(detail)
    elif not args.quiet:
        icon = {"ok": "✅", "expiring": "⚠️", "expired": "❌", "missing": "❌"}[status]
        print(f"{icon} {detail}")

    return 0 if status == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
