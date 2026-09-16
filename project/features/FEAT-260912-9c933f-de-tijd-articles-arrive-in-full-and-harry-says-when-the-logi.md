---
id: FEAT-260912-9c933f
title: De Tijd articles arrive in full, because Harry logs in by itself — and says when it cannot
track: full
created: 2026-09-12
touches: [CLAUDE.md, Dockerfile, compose, connectors/news, connectors/tijd, core, docs/capabilities, docs/operating, docs/sources, env, rules, scripts]
stories: [STORY-260916-f048f5, STORY-260916-ebeb3f, STORY-260916-daf947, STORY-260916-133f51, STORY-260916-c04a3c, STORY-260916-969f41]
decisions: [ADR-260916-b26785, ADR-260916-bcbd69, ADR-260916-d4acc6]
---

# FEAT-260912-9c933f — De Tijd articles arrive in full, because Harry logs in by itself — and says when it cannot

## Summary

De Tijd is the source most worth having, and its articles are only readable by a logged-in
subscriber in a real browser window. This reads them through a headed Chromium on a virtual
display, with a session Harry saves and renews by itself: **Harry logs in with the account's
email and password** whenever the session has lapsed. When it cannot — a refused password, a
captcha, a browser De Tijd refuses — the story prints the feed's summary and one Slack line
says which.

Two changes underneath make that possible. The real stack now reads each connector's own
`.env.local`, through a read-only mount, so the De Tijd login lives in one file beside its
connector. And a connector can name another connector, so news can hand De Tijd's pages to
the tijd connector without importing it.

**Start with the first story.** It measures an automated login from the NUC before anything is
built on it. If De Tijd refuses a scripted login, [[ADR-260916-b26785]] is revisited first.

## Acceptance criteria

<!-- One box per scenario. These are what the pre-close-verifier builds its
     traceability matrix from. -->

- [ ] On the real stack, a connector's own `.env.local` is read through a read-only mount of `.harry/`, and an environment variable still wins over it
- [ ] The dev stack reads no connector's `.env.local` — only `.env.dev.local`
- [ ] A connector declaring `optional:` or `requires:` is loaded after the connectors it names, and `make lint` refuses unknown names and loops
- [ ] With a saved session, a De Tijd article comes back with its whole text — more than 1,000 characters where a logged-out reader gets 263 — and no login is attempted
- [ ] With no session, or a lapsed one, Harry logs in, saves the session to `/data/tijd/storage-state.json` with mode 600, and returns the whole article in the same call
- [ ] A refused login makes five De Tijd articles print their summary, after one login attempt, with no retry for 6 hours and one Slack line naming De Tijd that contains neither the email nor the password
- [ ] A 403 from De Tijd is reported as the browser being refused, and never leads to a login
- [ ] A captcha or a login step Harry does not know stops the login within 60 seconds and is reported for what it is; a login page that does not answer waits 15 minutes, not 6 hours
- [ ] A browser that cannot start costs De Tijd's text and nothing else, and says so in Slack
- [ ] On the NUC, starting with no saved session, a page built with a De Tijd story, deliver=false, carries its whole article, and the session exists only on the data volume

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260916-f048f5]] — Harry logs in to De Tijd from the NUC, measured before anything is built on it
- [ ] [[STORY-260916-ebeb3f]] — A connector's own .env.local reaches the real stack
- [ ] [[STORY-260916-daf947]] — A connector can use another connector, and they load in that order
- [ ] [[STORY-260916-133f51]] — A De Tijd article comes back in full through a saved session
- [ ] [[STORY-260916-c04a3c]] — Harry logs in to De Tijd by itself, once, and says when it cannot
- [ ] [[STORY-260916-969f41]] — On the NUC, a page carries a De Tijd story in full

## Notes

<!-- Appended by `board.py note`. -->
- **2026-09-13** — DE TIJD PASSES, but not for the reason the plan assumed, and the difference is one argument. A saved browser session is necessary and NOT sufficient: playwright's default headless is chrome-headless-shell, a stripped binary De Tijd 403s on every URL including the homepage, with a perfectly good 89-cookie Auth0 session attached. Launching the FULL chromium in headless mode - launch(headless=True, channel='chromium') - is served normally: HTTP 200, redirect stub resolved, 1,942 characters through trafilatura. Measured all four combinations; the stealth flag --disable-blink-features=AutomationControlled made no difference either way, and no virtual display is needed. So the container needs no Xvfb, only the full chromium binary, which playwright install chromium already fetches alongside the shell. Get channel='chromium' wrong and the failure looks exactly like an expired login.
- **2026-09-13** — The redirect stub resolves cleanly. tijd.be/r/t/1/id/10685805 -> the real article URL, in one hop, inside the browser. So the news connector can take feed links as-is and does not need a separate resolution step.
- **2026-09-13** — How long a De Tijd session lasts is still unknown and cannot be answered today: it worked at 0.0 days old, which is a lower bound and nothing more. Leaving that criterion unticked rather than ticking it on a number that says nothing. The way to actually get it: the connector records the session's age on every successful fetch, so the answer accumulates by itself and the first failure tells you the ceiling. Until then assume weeks, alert on the first 403, and do not build a renewal schedule around a guess.
- **2026-09-16** — SUPERSEDES the note of 2026-09-13 above that says 'the container needs no Xvfb, only the full chromium binary'. That was true when measured and is not true now. Re-measured 2026-09-16 from the harry image on the NUC against De Tijd's PUBLIC homepage (no login, one request each): chrome-headless-shell 403; full Chromium headless via launch(headless=True, channel='chromium') 403 — this is the one that got 200 three days earlier; headed Chromium under Xvfb, launch(headless=False, channel='chromium') through xvfb-run, 200. So the connector must launch HEADED under a virtual display. channel='chromium' is still required (the headless shell is not the full browser), but it is no longer sufficient on its own. The image now carries xvfb and xauth, and a live test proves a headed browser starts in it. Two consequences for whoever builds this: the edge tightened in three days, so expect it to tighten again and let the 403-to-Slack alert be how you find out; and a 403 on the homepage with no session attached is bot detection, not an expired login — tell those apart before alerting 'the login lapsed', or the alert will send the operator to re-log-in for a problem a login cannot fix.
- **2026-09-16** — AUTOMATED LOGIN WORKS FROM THE NUC — measured from the harry:c32f0cc image under xvfb-run, with the account in the worktree's .harry/connectors/tijd/.env.local. Route: open https://www.tijd.be/ (NOT the article: there a second modal, .ds-modal-wrapper 'Dit artikel is alleen voor abonnees', covers the Log in button even after consent is dismissed); the consent dialog also intercepts the click on the homepage, so click 'Optionele cookies weigeren' first; click .trck_sitenav_login:visible; auth.mediafin.be/u/login/identifier, fill #username, click button[name=action][value=default]; /u/login/password, fill #password, same button; lands on www.tijd.be/. No captcha on either step. Logged in, the measured article (10686286) gave 6,120 characters through trafilatura against 263 logged out, status 200. The saved storage_state (31 cookies, 28.7 KB) opened in a fresh browser read the same 6,120 characters with no login. One deliberately wrong password: the page stays on /u/login/password and shows #error-element-password, class ulp-input-error-message, text 'E-mailadres of wachtwoord onjuist'. THE MARKER TO READ: paywall-active is on <html> in the SERVED html and at domcontentloaded (checked logged out: served tag is <html lang="nl" class="paywall-active" data-brand="tijd">), and absent from the served html when logged in. The Log in button is NOT in the served html — JavaScript draws it — so it is not a reliable 'logged out' marker and the connector does not read it. The spike session sits in a throwaway docker volume, tijd-spike, deleted when this feature closes.
- **2026-09-16** — plan-verifier: WARN, no BLOCK, 15 findings, all folded into the board before any code merged. The ones that changed the design: the tijd connector raises its own Slack lines, because Context.alert scrubs only the raising capability's declared secrets and a line raised by news would not scrub tijd's password (EMAIL is now declared secret too); every reason is a fixed sentence keyed by its name; a login page that does not answer waits 15 minutes rather than 6 hours, because nothing was refused; logged-in-at records the login time so the session-length log line has a source; the login rule is a table of expected endings per step, with Auth0's documented captcha markers named; loops are specified per list (optional: handed nothing, requires: skipped, logged) and a malformed declaration counts as naming nothing for ordering. Also found: every connector .env.local on this NUC is mode 664, and tests/test_deployment.py asserts that nothing but named volumes is mounted — narrowed deliberately in STORY-260916-ebeb3f.

## Links

- Requirements: [[FEAT-260912-9c933f]]
- Decision: [[ADR-260916-b26785]] — Harry logs in to De Tijd by itself, with the account's email and password
- Decision: [[ADR-260916-bcbd69]] — The real stack reads each connector's own .env.local through a read-only mount
- Decision: [[ADR-260916-d4acc6]] — A connector can name another connector, and connectors load in that order

