---
id: FEAT-260915-fd25f2
title: A page pushed twice replaces yesterday's copy, not sits beside it
track: story
created: 2026-09-15
touches: [connectors/remarkable, docs]
stories: []
decisions: []
---

# FEAT-260915-fd25f2 — A page pushed twice replaces yesterday's copy, not sits beside it

## Summary

`push(path, name)` creates a document every time. Pushing the morning page twice on the same
day leaves **two documents both called `2026-09-15`** in the folder, and the tablet gives no
hint which is the newer one. Found by pushing today's page twice while iterating on its
design; the listing came back with the name twice and no timestamps.

That is fine exactly once a day and wrong the moment anything retries, re-renders or gets
built again after a fix — which is every morning something goes slightly wrong. The reader
opens one of two identical-looking files and cannot tell whether they are reading the page
that has the correction in it.

Harry has no delete today, deliberately: the device token grants complete read and write
over every document on the tablet, and a connector that can remove things is a connector
that can remove the wrong thing. So the shape to find is "put this content at this name",
not "list, delete, push".

## Acceptance criteria

- [ ] Pushing the same name twice leaves one document in the folder, carrying the second push's content
- [ ] The first push of a name still creates it
- [ ] A push that replaces says so in the log, naming the document
- [ ] Nothing gains the ability to delete a document the caller did not name — a test asserts the connector has no code path that removes anything else
- [ ] `docs/` says what happens on a second push, beside the rest of the tablet connector
- [ ] The runbook says what to do about the duplicates already on the tablet, since nothing here removes them

## Stories

<!-- Maintained by `board.py new-story`. -->

## Notes

<!-- Appended by `board.py note`. -->

## Links

