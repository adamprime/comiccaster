#!/usr/bin/env python3
"""Verify the host settings the pipeline silently depends on.

The pipeline runs as LaunchAgents, which load only on **GUI login**. Three
settings make that login happen without a human, and a fourth makes the box
reachable afterwards:

  * ``/etc/kcpassword``            -- the obfuscated auto-login credential
  * ``autoLoginUser``             -- who to log in as
  * FileVault **off**              -- FileVault makes auto-login unavailable
  * ``TailscaleStartOnLogin``      -- SSH / Screen Sharing return after a reboot

None of these announce themselves when they break. macOS updates have been
known to reset login settings, and the failure is invisible until the next
reboot -- at which point the box sits at the login window with no pipeline and
no Tailscale, since the tunnel is started *by* the login session.

Recovery then depends on the LAN fallback (SSH from another node on the same
subnet, which works because sshd is boot-loaded), and that in turn needs
FileVault to stay off -- an encrypted volume is not mounted before unlock, so
sshd could not read `authorized_keys`. Hence FileVault is checked here too: it
guards the fallback as well as auto-login.

The gap this closes is one of timing, not prevention. We cannot stop an update
from clearing these, but between the update and the next reboot the machine is
still up and still reachable, and the fix is a minute of Screen Sharing. This
makes that window visible instead of letting the reboot be the discovery event.

See docs/solutions/logic-errors/power-outage-launchagents-never-load.md.

**This script has no flag to print its findings into an alert body, and that is
deliberate** -- see the note on `main`.
"""

import argparse
import subprocess
import sys
from pathlib import Path

KCPASSWORD_PATH = Path("/etc/kcpassword")
LOGINWINDOW_PREFS = "/Library/Preferences/com.apple.loginwindow"
TAILSCALE_DOMAIN = "io.tailscale.ipn.macsys"

# The pipeline's LaunchAgents live in this user's home, so auto-login must
# target this account specifically -- logging in as anyone else loads nothing.
EXPECTED_LOGIN_USER = "openclaw"


def parse_filevault_status(raw):
    """True/False from `fdesetup status`, or None if unreadable.

    None matters: a probe that failed to run must never read as healthy.
    """
    text = (raw or "").strip()
    if "FileVault is On" in text:
        return True
    if "FileVault is Off" in text:
        return False
    return None


def parse_defaults_bool(raw):
    """True/False from a `defaults read` of a 0/1 key, or None if unset."""
    text = (raw or "").strip()
    if text == "1":
        return True
    if text == "0":
        return False
    return None


def _run(cmd):
    """Best-effort command capture. Returns '' rather than raising."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=15, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout


def gather():
    """Probe the live host. Impure; `evaluate` holds the logic."""
    auto_login_user = _run(
        ["defaults", "read", LOGINWINDOW_PREFS, "autoLoginUser"]
    ).strip()

    return {
        # Readable by any user: we only need existence, never the contents.
        "kcpassword_present": KCPASSWORD_PATH.exists(),
        "auto_login_user": auto_login_user or None,
        "filevault_on": parse_filevault_status(_run(["fdesetup", "status"])),
        "tailscale_start_on_login": parse_defaults_bool(
            _run(["defaults", "read", TAILSCALE_DOMAIN, "TailscaleStartOnLogin"])
        ),
    }


def evaluate(readings):
    """Return (status, detail) where status is 'ok' or 'broken'.

    Reports *every* problem rather than the first, so one run tells the operator
    the whole story instead of revealing the next fault on the next day.
    """
    problems = []

    if not readings.get("kcpassword_present"):
        problems.append(
            "/etc/kcpassword is missing -- auto-login will NOT happen at the "
            "next reboot. Re-set it in System Settings > Users & Groups > "
            "Automatically log in as."
        )

    user = readings.get("auto_login_user")
    if user != EXPECTED_LOGIN_USER:
        problems.append(
            f"autoLoginUser is {user!r}, expected {EXPECTED_LOGIN_USER!r} -- "
            "the pipeline's LaunchAgents only load for that account."
        )

    filevault_on = readings.get("filevault_on")
    if filevault_on is not False:
        detail = "unreadable" if filevault_on is None else "ON"
        problems.append(
            f"FileVault is {detail} -- FileVault makes auto-login unavailable, "
            "so the pipeline would not start after a reboot."
        )

    tailscale = readings.get("tailscale_start_on_login")
    if tailscale is not True:
        detail = "unreadable" if tailscale is None else "disabled"
        problems.append(
            f"Tailscale start-on-login is {detail} -- remote access (SSH and "
            "Screen Sharing) would NOT return after a reboot."
        )

    if problems:
        return "broken", (
            "Host configuration drifted; fix before the next reboot, while the "
            "box is still reachable:\n  - " + "\n  - ".join(problems)
        )

    return "ok", (
        "Host configuration ok: auto-login armed and remote access will survive "
        "a reboot."
    )


def main(argv=None) -> int:
    """Print the verdict locally and signal via exit code.

    Deliberately offers no `--detail-only` flag, unlike check_ck_session.py.
    The findings describe this host's security posture -- whether the disk is
    encrypted, which account logs in unattended -- and the pipeline alert they
    feed opens an issue on a **public** repository. The alert therefore carries
    only a failure key and a generic title; the specifics stay in the local run
    log, where the operator reads them. tests/test_check_host_config.py pins
    that absence so it cannot be undone by accident.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quiet", action="store_true", help="suppress output")
    args = parser.parse_args(argv)

    status, detail = evaluate(gather())

    if not args.quiet:
        icon = "✅" if status == "ok" else "❌"
        print(f"{icon} {detail}")

    return 0 if status == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
