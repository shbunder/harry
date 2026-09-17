---
id: ADR-260916-b26785
title: Harry logs in to De Tijd by itself, with the account's email and password
status: Accepted
created: 2026-09-16
feature: FEAT-260912-9c933f
supersedes: ''
superseded_by: ''
---

# ADR-260916-b26785 — Harry logs in to De Tijd by itself, with the account's email and password

## Status

Accepted

Drives [[FEAT-260912-9c933f]].

## Context & problem

De Tijd's articles are only readable by a logged-in subscriber, in a real browser window.
Measured on 2026-09-16 from Harry's image: a headless browser gets `403 Blocked`, a headed
Chromium on a virtual display gets 200, and a reader who is not logged in gets the first
paragraph — 263 characters on the story measured.

A login lapses on its own schedule, and nobody knows that schedule yet. The 2026-09-13 spike
saw a session work at 0 days old, which is a lower bound and nothing more.

**The NUC has no screen.** Harry runs in a container on it, and the owner reaches it over SSH.
So "a person logs in" is not one keystroke. It is a route into a browser nobody can see, taken
again every time the session lapses.

## Decision drivers

- **Degrading** — a lapsed login costs De Tijd's text until somebody acts. The shorter that
  wait, the better the page
- **Bounded** — whatever Harry holds is a working login for anyone who takes it
- The browser that logs in should be the one that reads. De Tijd's edge judges browsers, and a
  session made elsewhere may not be honoured by it
- Nothing that needs a person on a schedule nobody knows

## Considered options

### Option 1: A person logs in by hand, on the NUC, through a remote view

`make tijd-login` starts the same headed Chromium in a container and shows it in a browser tab
through noVNC, over a port VS Code forwards. The session is saved to the data volume.

**For:** Harry never holds the password — only a session, which is the weaker credential. The
browser and the IP that log in are the ones that read, so De Tijd's edge sees nothing new.
It survives a captcha, because a person answers it.
**Against:** about 60 more packages in the image (x11vnc, noVNC, websockify). A renewal chore
every few weeks, triggered by a Slack line, on a schedule nobody knows. Between the line and
the chore, the page prints summaries.

### Option 2: A person logs in on a laptop, and copies the session over

**For:** no change to the image, and no password on the NUC.
**Against:** the laptop needs the repository and Playwright. A session made by another browser
on another machine may be refused by De Tijd's edge — unmeasured. It is option 1's chore
with a copy step added.

### Option 3: Harry logs in by itself, with the email and password

The account's email and password sit in `.harry/connectors/tijd/.env.local`. Harry keeps a
saved session and uses it. When a page shows the paywall and the "Log in" button, Harry opens
the login page, fills in the two fields, and saves the new session.

**For:** no renewal chore while the password is right. The session is still saved and reused,
so a login happens only when one has lapsed. It is a rule anyone could follow by hand — open
this page, fill these two fields, press this button — so it stays **Heuristic**.
**Against:** Harry holds the account password, which is a stronger credential than a session:
it can change the account, the subscription, and the password itself. A redesigned login page
or a new captcha stops it until the code changes. De Tijd's login service blocks an account
after repeated failures, so a wrong password must never be retried on every article. It cannot
work for an account that signs in with Google or Apple.

## Decision outcome

**Harry logs in to De Tijd by itself.** The owner chose this on 2026-09-16, over option 1.

**Degrading** decided it: the page no longer waits for a person to notice a Slack line and
open a remote browser. What option 3 costs in **Bounded** is paid for with rules:

- `EMAIL` and `PASSWORD` are declared `secret: true`. The tijd connector raises its own Slack
  lines, so its own context scrubs both from every line it sends — a line raised by the news
  connector would scrub news's secrets, and news has none. Every reason it gives is a fixed
  sentence with no exception text in it, so there is nothing to scrub in the first place.
- The password lives only in the connector's `.env.local` on the NUC, mode 600.
- The session is saved to `/data/tijd/storage-state.json`, mode 600, on the data volume. Never
  in the repository and never in the image.
- After a refused password, a captcha or a login step Harry does not know, it does not try
  again for 6 hours. One attempt, then a Slack line. A login page that did not answer waits 15
  minutes instead: nothing was refused, so nothing counts towards a lockout.
- A 403 is never answered with a login. It is the browser that was refused, and saying "log in
  again" would send the owner to fix the wrong thing.

## Consequences

**Good:**

- A lapsed session is renewed within the call that finds it. The page carries the article.
- A Slack line about De Tijd now means something a person has to do: the password changed, a
  captcha appeared, or the login page moved.
- Every login writes its time to `/data/tijd/logged-in-at`, and logs how long the previous
  session lasted. The open question from the 2026-09-13 spike answers itself over time.

**Bad:**

- **The De Tijd password replaces the storage state as the credential that deserves fear.**
  `.claude/rules/secrets-and-config.md` and `CLAUDE.md` name it in its place.
- **A captcha is a dead end.** If De Tijd adds one, full text stops until this decision is
  revisited — option 1 is the fallback, and it needs an image change.
- **A login page redesign breaks full text** until the selectors are updated. The Slack line
  names the field Harry could not find, so the fix starts in the right place.
- **The browser runs as root, without Chromium's sandbox, beside every credential.** It renders
  De Tijd's pages and the advertising scripts on them in the container that can read each
  connector's `.env.local` through `/settings` (the tablet token, the iCloud and Slack
  credentials, this password), the root `.env.local` with the MCP bearer token, and the saved
  session on `/data`. One exploit in the renderer would reach all of them. **The owner accepted
  this on 2026-09-17**, to have De Tijd running, with the fix as the next feature:
  [[FEAT-260917-250f5a]]. That fix is more than a user change — Playwright passes `--no-sandbox`
  unless `chromium_sandbox=True` is given, Docker's default seccomp profile usually blocks the
  sandbox, the data volume's ownership has to change, and Chromium's patch level only moves when
  the locked Playwright version does.
- **The 6-hour wait lives in memory.** A restart clears it. A container stuck restarting with a
  wrong password would try once per start; `restart: unless-stopped` makes that rare, but it
  is not impossible.
