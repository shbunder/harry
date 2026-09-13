---
id: STORY-260913-b76fbd
title: The SDK is the only thing a capability may import
feature: FEAT-260912-8a0ab0
status: Backlog
created: 2026-09-13
---

# STORY-260913-b76fbd — The SDK is the only thing a capability may import

Part of [[FEAT-260912-8a0ab0]].

## Description

What a capability is allowed to reach, and the run-time check that it did not reach past it. Written first because every other story registers against it, and because a boundary added afterwards is one that already has violations.

## Acceptance criteria

<!-- These drive the tests. Write checkable statements, not activities.
     Bad:  Wire up the article fetcher
     Good: A De Tijd article whose browser session has expired falls back to its RSS
           summary, and the page still renders -->

- [x] `harry.sdk` exposes the Registry and the Context a capability is handed, and nothing else
- [x] A capability importing harry.scheduler, harry.store, harry.mcp or harry.main is skipped, with a reason naming the import
- [x] The SDK imports nothing from a capability, in either direction
- [x] A capability that imports only harry.sdk loads

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

