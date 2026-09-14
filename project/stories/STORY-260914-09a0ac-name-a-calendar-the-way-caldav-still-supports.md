---
id: STORY-260914-09a0ac
title: Name a calendar the way caldav still supports
feature: FEAT-260914-4dc021
status: Done
created: 2026-09-14
---

# STORY-260914-09a0ac — Name a calendar the way caldav still supports

Part of [[FEAT-260914-4dc021]].

## Description

One call swapped, one stand-in corrected, and two guards so neither can come back.

## Acceptance criteria

- [x] `get_display_name()` is what reads a calendar's name, and `calendar.name` is nowhere in the connector
- [x] Reading a named calendar with `DeprecationWarning` raised as an error passes
- [x] The stand-in offers `get_display_name()`, and the shape test asserts caldav and the stand-in both have it
- [x] The live test passes against a real account

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

