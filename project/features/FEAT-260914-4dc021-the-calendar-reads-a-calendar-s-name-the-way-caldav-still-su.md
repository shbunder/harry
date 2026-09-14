---
id: FEAT-260914-4dc021
title: The calendar reads a calendar's name the way caldav still supports
track: story
created: 2026-09-14
touches: [connectors/icloud]
stories: [STORY-260914-09a0ac]
decisions: []
---

# FEAT-260914-4dc021 — The calendar reads a calendar's name the way caldav still supports

## Summary

The first thing that ever ran the calendar connector's real code path was its live test,
against a real account, minutes after the feature merged. It went red on the first run.

`caldav` 3.3 deprecated `Calendar.name` in favour of `get_display_name()`. Reading a
calendar's name raised a `DeprecationWarning`, which this repository turns into an error for
Harry's own modules — so the connector reported "iCloud answered something this connector
does not understand" and put a line in Slack, for a call that had nothing wrong with the
account at all.

Forty-five tests were green throughout, because the stand-in in `tests/test_icloud_connector.py`
offered `.name` too. **The stand-in had drifted from the library and the shape test did not
cover it** — it pinned `search`, which the recurrence decision turns on, and nothing else.

## Acceptance criteria

- [ ] The connector reads a calendar's name with `get_display_name()`, and `calendar.name` appears nowhere in it
- [ ] A test raises on `DeprecationWarning` while reading a named calendar, so the deprecated call cannot come back quietly
- [ ] The stand-in offers `get_display_name()` rather than `.name`, and the shape test asserts both the library and the stand-in have it
- [ ] `make test-live ARGS=tests/test_icloud_connector.py` passes against a real account

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260914-09a0ac]] — Name a calendar the way caldav still supports

## Notes

<!-- Appended by `board.py note`. -->

## Links

