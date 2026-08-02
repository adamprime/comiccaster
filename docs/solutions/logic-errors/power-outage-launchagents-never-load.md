---
title: Power outage — pipeline silently never ran because LaunchAgents need a GUI login
date: 2026-08-02
category: logic-errors
module: pipeline
problem_type: environment
component: launchd / macOS host
severity: high
applies_when:
  - "A scheduled run is missing entirely and logs/master_update.log has NO entry for it (not a failure — no attempt)"
  - "The host was rebooted (power outage, forced restart) and nobody logged in afterwards"
  - "SSH / Screen Sharing to the mini is refused after a reboot until someone physically logs in at the machine"
  - "The pipeline-heartbeat issue fires but no per-source failure issue accompanies it"
tags: [launchd, launchagent, power-outage, auto-login, filevault, tailscale, remote-access, heartbeat, catchup]
stack: [macos, launchd, tailscale]
github_issues: [181]
---

## TL;DR

The 2026-08-01 13:00 Pass 2 and 2026-08-02 03:05 Pass 1 **never ran**. Nothing
failed — nothing was attempted. A power outage rebooted the mini at
`2026-08-01 11:02:38`; the box came back up on its own but sat at the login
window for ~25h.

The pipeline runs as **LaunchAgents** (`~/Library/LaunchAgents/com.comiccaster.master`,
`.pass2`, `.catchup`). LaunchAgents load on **GUI login**, not at boot. No login
→ no agents → no runs, with nothing written to any log to say so.

Same root cause made the box unreachable: Tailscale (how the mini is reached
remotely) was a **user-session app** that also never started, so SSH and Screen
Sharing were dead until someone walked to the machine.

## Why the logs are useless here

This failure mode leaves **no trace in `logs/master_update.log`** — the last entry
is simply the previous successful run. Reaching for the pipeline logs first wastes
time. Establish whether a session existed at the scheduled time:

```bash
sysctl -n kern.boottime          # when did it reboot?
who                              # is anyone logged in? console session present?
pmset -g log | grep -i "shutdown cause"   # clean shutdown, or power loss?
last reboot
```

An unclean power loss leaves **no** preceding sleep/shutdown record.

## What was actually misconfigured

Two settings, each independently sufficient to cause the outage:

| Setting | Was | Now |
| --- | --- | --- |
| `/etc/kcpassword` | **missing** | present (auto-login works) |
| `/Library/Preferences/com.apple.loginwindow autoLoginUser` | `openclaw` | unchanged |
| `io.tailscale.ipn.macsys TailscaleStartOnLogin` | `0` | `1` |
| `io.tailscale.ipn.macsys VPNOnDemandIsUserConfigured` | `0` | `1` |
| `pmset autorestart` | `1` (already correct) | `1` |

**The auto-login trap:** macOS needs *both* `autoLoginUser` **and** `/etc/kcpassword`.
`autoLoginUser` alone only preselects the user at the login window — it looks
configured and does nothing. Only System Settings → Users & Groups → "Automatic log
in as" writes `kcpassword`; there is no safe CLI path (`sysadminctl -autologin` puts
the password in shell history and the process list).

This is possible only because **FileVault is Off** (`fdesetup status`). With FileVault
on, auto-login is greyed out entirely and this whole recovery chain is unavailable —
the box would require manual unlock after every power event.

Security note: `/etc/kcpassword` is XOR-obfuscated with a published key, not
encrypted. With FileVault off, physical access already yields the deploy key and the
CK/TinyView session cookies, so auto-login doesn't widen exposure — but it is a
deliberate trade, not a free win.

## Tailscale specifics (this build)

Installed build is the **standalone `io.tailscale.ipn.macsys`**, not the App Store
one, with a Network Extension registered at system level. **Do not replace it with
Homebrew `tailscaled`** — that means tearing down a signed system extension and
re-authing the node for no gain.

CLI lives inside the bundle (there is no `tailscale` in `PATH`):

```bash
/Applications/Tailscale.app/Contents/MacOS/Tailscale status
/Applications/Tailscale.app/Contents/MacOS/Tailscale debug prefs
```

**There is no "Run unattended" setting in this build** (verified on 1.98.10: no such
string in the binary, no `--unattended` flag on `set` or `up`; `ForceDaemon` is absent
from prefs). That was a Windows-only flag. The macOS equivalents are `Start on Login`
plus **VPN On Demand**, and `AlwaysOn.Enabled` — the latter an **MDM/device-policy**
key (`Tailscale syspolicy list`), not a user setting, which the binary notes will
*disable* on-demand when set.

**The tunnel does not come up before login** — settled empirically by the
2026-08-02 13:03:57 verification reboot (see below). Process start times:

```
openclaw  13:04:07  /Applications/Tailscale.app/Contents/MacOS/Tailscale
root      13:04:09  …/io.tailscale.ipn.macsys.network-extension
```

The root-owned network extension starts *two seconds after* the user-owned GUI
app, i.e. the extension is brought up **by** the logged-in session, not ahead of
it. There is no pre-login window in which SSH works.

The consequence is the important part: **auto-login is the only thing that makes
this box remotely reachable.** If `kcpassword` is ever cleared, the failure is not
"the pipeline is late" but "the host is unreachable and cannot be fixed remotely" —
it needs someone physically at the machine. That makes the post-macOS-update
re-verify checklist below load-bearing, not hygiene.

## The recovery chain (defence in depth)

| Layer | Covers |
| --- | --- |
| `pmset autorestart 1` | Power returns → box boots itself |
| Auto-login (`kcpassword`) | Session starts → LaunchAgents load → runs happen |
| Tailscale Start-on-Login + On Demand | SSH / Screen Sharing return without a human |
| LAN (`192.168.1.123`) | Independent path whenever you're on-site |

## What worked correctly, and should not be "fixed"

Both safety nets behaved exactly as designed and did the recovery:

- **`com.comiccaster.catchup`** (`RunAtLoad`, canary `data/comics_$TODAY.json`,
  `scripts/catchup_master_update.sh`) fired the instant a session started, saw
  today's GoComics JSON missing, and ran the full master update — ALL SUCCESS,
  commit `3eb4d36d8`.
- **`pipeline-heartbeat.yml`** opened issue #181, which is the *only* mechanism that
  can report a run that never happened — the host itself was off and structurally
  could not report anything. It self-clears once a fresh pipeline commit lands.

## Verification reboot (2026-08-02) — the whole chain, confirmed

The fixes above were validated by a deliberate reboot, not left to the next
outage. Boot at `13:03:57`, and with **nobody at the keyboard**:

| Time | Event | Layer proven |
| --- | --- | --- |
| 13:03:57 | `kern.boottime` | box boots itself |
| ~13:04 | `openclaw console` in `who` | auto-login / `kcpassword` |
| 13:04:07 | Tailscale GUI app | Start-on-Login |
| 13:04:09 | network extension | tunnel up → SSH returns |
| 13:04:13 | `com.comiccaster.catchup` fired | LaunchAgents load on login |

Total: **~16 seconds** from power to a fully recovered, remotely reachable host,
versus ~25h of silent downtime before the fix.

The catch-up agent logged
`data/comics_2026-08-02.json present, today's run already happened. Skipping.` —
the correct no-op, since Pass 1 (12:15) and Pass 2 (13:02) had both landed before
the reboot. That exercises the canary's *skip* branch; the outage itself had
already exercised its *run* branch.

`pipeline-heartbeat.yml` was then dispatched manually to close issue #181 rather
than waiting for the 11:00 UTC schedule — it verified a fresh pipeline commit and
self-cleared as designed.

## Prevention

Do not convert the LaunchAgents to LaunchDaemons — the scrapers want a real user
session for Chrome and keychain access. Auto-login is the correct fix; the catch-up
agent covers the residual case.

After any macOS update, re-verify — updates have been known to reset login settings:

```bash
ls -l /etc/kcpassword                                          # must exist
defaults read /Library/Preferences/com.apple.loginwindow autoLoginUser
defaults read io.tailscale.ipn.macsys TailscaleStartOnLogin    # must be 1
```
