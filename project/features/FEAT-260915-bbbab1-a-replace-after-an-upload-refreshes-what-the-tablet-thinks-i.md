---
id: FEAT-260915-bbbab1
title: A replace after an upload refreshes what the tablet thinks it has
track: story
created: 2026-09-15
touches: [connectors/remarkable]
stories: [STORY-260915-6bf64f]
decisions: []
---

# FEAT-260915-bbbab1 — A replace after an upload refreshes what the tablet thinks it has

## Summary

**The replace that shipped yesterday does not work against a real tablet.** Every test passes
and the stand-in cannot see it: pushing the same name twice leaves two documents on the
device, and the connector correctly reports that it could not remove the older one.

Found by building the morning page end to end and pushing it. The log says
`could not retire the older '2026-09-15': the tablet rejected the request`, the page arrives,
and the Slack line fires — the degraded path is exactly right, and the thing it is degrading
from never worked.

The same `client.delete(id)` succeeds from a fresh client. It fails only when an upload
happened first in the same session. reMarkable's sync API carries a generation counter, and
`delete` is a metadata write — `move(item, TRASH_PARENT_ID)` under the hood — so after
`put_pdf` advances the server's generation the connector is still holding the one from before
and the write is refused.

`remarkapy` takes `refresh=` on both the listing and the delete for precisely this. The
connector passes neither.

## Acceptance criteria

- [ ] `_retire` reads the folder and deletes with the tablet's current state, not the one it held before the upload
- [ ] A `live` test pushes the same name twice against the real tablet and finds one document afterwards
- [ ] The stand-in records whether each call asked for a refresh, and a unit test asserts both did — so the fix cannot be undone silently
- [ ] The degraded path is unchanged: a delete that still fails leaves the page on the tablet, logs, and alerts under its own key
- [ ] The runbook says what a rejected removal means now, since "reMarkable changed the protocol" was the wrong sentence for it

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260915-6bf64f]] — The delete after an upload uses the tablet's current state

## Notes

<!-- Appended by `board.py note`. -->

## Links

