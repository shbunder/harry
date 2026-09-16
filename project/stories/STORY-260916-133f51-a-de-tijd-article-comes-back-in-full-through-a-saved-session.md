---
id: STORY-260916-133f51
title: A De Tijd article comes back in full through a saved session
feature: FEAT-260912-9c933f
status: Done
created: 2026-09-16
---

# STORY-260916-133f51 — A De Tijd article comes back in full through a saved session

Part of [[FEAT-260912-9c933f]].

## Description

The reading half of De Tijd. A new `tijd` connector holds a saved session and a headed
Chromium. News hands it any article link on tijd.be, and it hands back the page as a
subscriber sees it — or says why it could not.

The image starts a virtual display for the whole container, so the browser has somewhere to
draw. Logging in is the next story; this one works from a session saved by the spike.

**The call between the two.** News calls `tijd.read(link)` and gets plain data back, because
it may not import tijd's exceptions: `{"url": …, "html": …}` for a page read as a subscriber
sees it, or `{"why": …, "said": true}` when it could not be. `said` means tijd has already
put the line in Slack, so news answers `available: false` with that `why` and alerts
nothing. tijd raises its own lines so that its own context scrubs `EMAIL` and `PASSWORD`.

## Acceptance criteria

- [x] `.harry/connectors/tijd/` declares `email` and `password` as required and secret, a session directory defaulting to `/data/tijd`, and `expires: session`
- [x] News declares `optional: [tijd]` and sends every article link whose host is `tijd.be` or ends in `.tijd.be` to `tijd.read`; every other link is fetched as before
- [x] With no tijd connector loaded, a De Tijd link is fetched over plain HTTP, as today
- [x] `tijd.read` answers `{"url", "html"}` or `{"why", "said": true}`, and news turns the second into `available: false` with the feed's summary and no alert of its own
- [x] A reader that raises instead of answering costs that one article: news answers `available: false` and alerts under its own `article:<feed>` key
- [x] A page whose `<html>` carries `paywall-active` is never handed back as the article, so a 263-character lead is never printed as the whole story
- [x] A logged-in page — no `paywall-active` — is handed back without a login being attempted
- [x] A 403 answers a why saying De Tijd refused the browser, and that logging in again will not help
- [x] A page that has not loaded within 30 seconds answers a why saying so
- [x] A browser that cannot start, or stops mid-page, answers a why saying so — and in the same Harry, VRT NWS and BBC News articles are still fetched and returned
- [x] Each of those faults is one Slack line per 24 hours, keyed by its reason's name; the same reason twice is one line and a different reason is a second line
- [x] No why and no Slack line contains the email, the password, an exception's text or a URL's query string — even when the underlying error does
- [x] After a page is read in full, the session is written back to `storage-state.json`, mode 600, by writing a temporary file and renaming it
- [x] A saved session that is not valid JSON is treated as no session and logged
- [x] A session that cannot be written answers the article anyway and says so in Slack
- [x] Two article calls at once use the browser one after the other, never together
- [x] No read takes longer than 150 seconds, and once one is known stuck every later De Tijd article is answered at once rather than queued behind it
- [x] The image starts a virtual display before Harry, `DISPLAY` is set, and Harry is still the process that receives `docker stop`
- [x] The paywall and refusal rules are tested against recorded pages in `tests/fixtures/` — the logged-out page as recorded, a logged-in page reduced to its markers with placeholder prose
- [x] by inspection: prose, read against the behaviour it describes — `.harry/connectors/tijd/CONNECTOR.md` says what it needs, how to set it up, what each failure looks like and what to do about it; `.harry/connectors/news/CONNECTOR.md` says a page on tijd.be is read by the tijd connector, which says its own faults

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

