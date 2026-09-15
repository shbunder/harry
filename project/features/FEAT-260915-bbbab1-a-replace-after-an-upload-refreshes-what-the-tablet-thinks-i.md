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

**Replace shipped green and did nothing on a real morning.** The page went up beside
yesterday's copy and the log said `could not retire the older '2026-09-15': the tablet
rejected the request`. The degraded path was exactly right — page delivered, warning logged,
one line in Slack — and the thing it was degrading from had never run.

A fresh client deleted the same document a moment later without complaint.

**The first theory was wrong and is worth recording as wrong.** reMarkable's sync API carries
a generation counter and `delete` is a metadata write, so a client holding the generation from
before `put_pdf` should be refused — `remarkapy` takes `refresh=` on exactly those calls. That
fix was written, and a live test written for it, and **the live test passed against the
unfixed connector too**, with one older copy and with two. A fix whose test cannot fail is a
belief, so it was reverted.

What is left is what can be shown: **the removal made one attempt where a push makes two.**
reMarkable answers a transient error often enough that one is too few, and the cost is not a
retry — it is a duplicate that stays forever, because nothing revisits yesterday's name once
tomorrow's is different.

## Acceptance criteria

- [x] A removal refused once is tried once more, and a retry that works says nothing
- [x] A removal refused twice stops there — the same ceiling the push has — keeps the page, logs, and alerts under its own key
- [x] A `live` test pushes a name that already has two copies and finds one afterwards, so the protocol and the loop are both held
- [x] That live test says at its assertion what it cannot prove: the retry, which needs the service to fail
- [x] The runbook says a duplicate means the removal was refused twice, and that nothing will revisit that name

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260915-6bf64f]] — The delete after an upload uses the tablet's current state

## Notes

<!-- Appended by `board.py note`. -->
- **2026-09-15** — Reflection: found by pushing a real page, not by a test. The first theory (a stale sync generation, fixed with remarkapy's refresh=) was implemented and live-tested, and the live test passed against the unfixed connector with one older copy and with two — so it was reverted rather than shipped. The defect that can be shown is the single attempt where a push gets two; both probe directions go red. The live test is kept as a protocol guard and says at its assertion that it cannot prove the retry. Traceability 5/5 and 6/6.

## Links

