---
id: STORY-260915-98499e
title: Every event says when it ends and whose calendar it is
feature: FEAT-260915-10c6e3
status: Backlog
created: 2026-09-15
---

# STORY-260915-98499e — Every event says when it ends and whose calendar it is

Part of [[FEAT-260915-10c6e3]].

## Description

`_shape()` builds every event from an expanded occurrence and drops two facts the timetable
needs: the occurrence's end, and which calendar it was read from. The end is on the
occurrence already. The calendar's name is known one frame up, in `_collect` and
`_collect_link`, and is thrown away when the two are merged into one icalendar object — so
the merge is where this changes.

Both belong to the same read and the same shape, which is why they are one story.

## Acceptance criteria

- [ ] A timed event carries `ends`: its end time, in the same ISO shape as `at`
- [ ] An all-day event carries `ends: null`
- [ ] An event whose `DTEND` is absent carries `ends: null` and is still returned
- [ ] Every event carries `calendar`: the CalDAV calendar's display name, or a published link's label
- [ ] A calendar whose display name is missing or empty returns its events as `calendar: "Calendar"` and logs its URL once
- [ ] The `icloud_list_events` tool returns `ends` and `calendar`, and its `TOOL.md` says what they are
- [ ] `docs/` describes both fields beside the rest of the calendar connector

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

