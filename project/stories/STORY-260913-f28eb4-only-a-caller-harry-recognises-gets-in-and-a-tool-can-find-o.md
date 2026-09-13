---
id: STORY-260913-f28eb4
title: Only a caller Harry recognises gets in, and a tool can find out who
feature: FEAT-260912-334932
status: Backlog
created: 2026-09-13
---

# STORY-260913-f28eb4 — Only a caller Harry recognises gets in, and a tool can find out who

Part of [[FEAT-260912-334932]].

## Description

The bearer token at the door, and the principal behind it. One token and one person today; the parameter is there so that a second is a token rather than a change to every tool signature.

## Acceptance criteria

<!-- These drive the tests. Write checkable statements, not activities.
     Bad:  Wire up the article fetcher
     Good: A De Tijd article whose browser session has expired falls back to its RSS
           summary, and the page still renders -->

- [x] A request with no Authorization header is refused
- [x] A request with a token that is not the configured one is refused
- [x] A request with the configured token gets the roster
- [x] An unset HARRY_API_TOKEN authorises nobody, including the owner
- [x] A tool whose signature declares a principal is handed the caller, not a default
- [x] principal does not appear in that tool's input schema — Harry fills it, never the caller

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

