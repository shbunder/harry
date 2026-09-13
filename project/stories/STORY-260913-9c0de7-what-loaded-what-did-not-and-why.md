---
id: STORY-260913-9c0de7
title: What loaded, what did not, and why
feature: FEAT-260912-8a0ab0
status: Backlog
created: 2026-09-13
---

# STORY-260913-9c0de7 — What loaded, what did not, and why

Part of [[FEAT-260912-8a0ab0]].

## Description

The endpoint that makes a skipped capability visible. Without it the difference between working and silently three-quarters working is a log file nobody opens.

## Acceptance criteria

<!-- These drive the tests. Write checkable statements, not activities.
     Bad:  Wire up the article fetcher
     Good: A De Tijd article whose browser session has expired falls back to its RSS
           summary, and the page still renders -->

- [x] GET /health returns 200 with every capability, its kind, and loaded or skipped
- [x] Every skipped one carries its reason
- [x] Harry running with four of five capabilities is 200, not an error — a skip is information
- [x] No secret appears in any field of the response, asserted against a capability that has one

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

