---
id: FEAT-260912-9c933f
title: De Tijd articles arrive in full, and Harry says when the login lapses
track: full
created: 2026-09-12
touches: [connectors/tijd]
stories: []
decisions: []
---

# FEAT-260912-9c933f — De Tijd articles arrive in full, and Harry says when the login lapses

## Summary

The fragile source. De Tijd returns 403 to any non-browser client, even for free articles, so this reads it through a real browser carrying a real login. That session expires every few weeks, and the alert is the feature: without it the page quietly loses its best source and you notice in three weeks.

## Acceptance criteria

<!-- One box per scenario. These are what the pre-close-verifier builds its
     traceability matrix from. -->

- [ ] A De Tijd article's full text is extracted through a browser session saved on disk
- [ ] A redirect stub link resolves to the real article before extraction
- [ ] When the session has expired the article falls back to its RSS summary and the page still renders
- [ ] An expired session puts one message in Slack naming De Tijd — one, not one per article
- [ ] The saved session is read from the data volume and never written into the repo

## Stories

<!-- Maintained by `board.py new-story`. -->

## Notes

<!-- Appended by `board.py note`. -->
- **2026-09-13** — DE TIJD PASSES, but not for the reason the plan assumed, and the difference is one argument. A saved browser session is necessary and NOT sufficient: playwright's default headless is chrome-headless-shell, a stripped binary De Tijd 403s on every URL including the homepage, with a perfectly good 89-cookie Auth0 session attached. Launching the FULL chromium in headless mode - launch(headless=True, channel='chromium') - is served normally: HTTP 200, redirect stub resolved, 1,942 characters through trafilatura. Measured all four combinations; the stealth flag --disable-blink-features=AutomationControlled made no difference either way, and no virtual display is needed. So the container needs no Xvfb, only the full chromium binary, which playwright install chromium already fetches alongside the shell. Get channel='chromium' wrong and the failure looks exactly like an expired login.
- **2026-09-13** — The redirect stub resolves cleanly. tijd.be/r/t/1/id/10685805 -> the real article URL, in one hop, inside the browser. So the news connector can take feed links as-is and does not need a separate resolution step.
- **2026-09-13** — How long a De Tijd session lasts is still unknown and cannot be answered today: it worked at 0.0 days old, which is a lower bound and nothing more. Leaving that criterion unticked rather than ticking it on a number that says nothing. The way to actually get it: the connector records the session's age on every successful fetch, so the answer accumulates by itself and the first failure tells you the ceiling. Until then assume weeks, alert on the first 403, and do not build a renewal schedule around a guess.

## Links

- Requirements: [[FEAT-260912-9c933f]]
