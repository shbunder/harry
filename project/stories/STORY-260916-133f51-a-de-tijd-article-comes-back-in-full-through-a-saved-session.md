---
id: STORY-260916-133f51
title: A De Tijd article comes back in full through a saved session
feature: FEAT-260912-9c933f
status: Backlog
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

## Acceptance criteria

- [ ] `.harry/connectors/tijd/` declares `email` and `password` (secret) as required, a session directory defaulting to `/data/tijd`, and `expires: session`
- [ ] News declares `optional: [tijd]` and sends every article link whose host is tijd.be, or ends in `.tijd.be`, to it; every other link is fetched as before
- [ ] With no tijd connector loaded, a De Tijd link is fetched over plain HTTP, as today
- [ ] A page whose `<html>` carries `paywall-active` is never handed to trafilatura as the article, so a 263-character lead is never printed as the whole story
- [ ] A 403 from De Tijd answers `available: false` and a why saying De Tijd refused the browser, and that logging in again will not help
- [ ] A browser that cannot start answers `available: false` and a why saying so
- [ ] After a page is read in full, the session is written back to `storage-state.json`, mode 600, by writing a temporary file and renaming it
- [ ] Two article calls at once use the browser one after the other, never together
- [ ] News's alert key carries the reason, so a second, different reason for the same source on the same day is still said — and the same reason twice is said once
- [ ] The image starts a virtual display before Harry, `DISPLAY` is set, and Harry is still the process that receives `docker stop`
- [ ] The paywall and refusal rules are tested against recorded pages in `tests/fixtures/` — the logged-out page as recorded, a logged-in page reduced to its markers with placeholder prose
- [ ] `.harry/connectors/tijd/CONNECTOR.md` says what it needs, how to set it up, what each failure looks like and what to do about it

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

