---
id: STORY-260914-2245c2
title: Claude can ask what a day looks like
feature: FEAT-260912-e7ce2d
status: Done
created: 2026-09-14
---

# STORY-260914-2245c2 — Claude can ask what a day looks like

Part of [[FEAT-260912-e7ce2d]].

## Description

The tool, so "what's on tomorrow?" works from any session rather than only from the morning
page.

`icloud_list_events(day)` is the shape `.claude/rules/tool-design.md` names as its own
example of a tool rather than a protocol: it answers what a person wants to know, not what
CalDAV can be asked.

## Acceptance criteria

- [x] `icloud_list_events()` returns today, in the configured timezone
- [x] `icloud_list_events(day="2026-09-15")` returns that day
- [x] A day that is not an ISO date is an error naming the format wanted
- [x] The tool is readOnlyHint true and defers
- [x] It is listed in the connector's `provides:`
- [x] It is skipped, saying it needs the connector, when no credential is configured
- [x] iCloud being down reaches Claude as an error rather than an empty day, so a dead source is never reported as a free morning

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

