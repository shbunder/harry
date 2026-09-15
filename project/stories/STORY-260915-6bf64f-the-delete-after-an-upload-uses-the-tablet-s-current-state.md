---
id: STORY-260915-6bf64f
title: The delete after an upload uses the tablet's current state
feature: FEAT-260915-bbbab1
status: Done
created: 2026-09-15
---

# STORY-260915-6bf64f — The delete after an upload uses the tablet's current state

Part of [[FEAT-260915-bbbab1]].

## Description

`_retire` calls `client.delete` once per older copy and catches whatever comes back. A push
goes through `_trying`, which attempts twice. The removal deserves the same, and cannot reuse
`_trying`: that alerts and raises `Refused`, and this caller has already put the page on the
tablet and must not raise.

So a small sibling — two attempts, then let it out to `_retire`'s own handler, which keeps
the page and says so.

## Acceptance criteria

- [x] `_twice` attempts a call twice and re-raises the last failure
- [x] A delete refused once then succeeding leaves one document, `replaced: 1`, and nothing in Slack
- [x] A delete refused twice is attempted exactly twice, keeps the page, and alerts under `retire`
- [x] Deleting once instead of twice turns a test red; deleting three times turns a test red
- [x] The live test pushes over two existing copies and finds one, and says what it cannot prove
- [x] The runbook and `docs/` say a removal is tried twice and what a surviving duplicate means

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

