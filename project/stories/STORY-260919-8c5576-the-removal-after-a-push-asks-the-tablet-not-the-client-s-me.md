---
id: STORY-260919-8c5576
title: The removal after a push asks the tablet, not the client's memory
feature: FEAT-260919-52866c
status: Backlog
created: 2026-09-19
---

# STORY-260919-8c5576 — The removal after a push asks the tablet, not the client's memory

Part of [[FEAT-260919-52866c]].

## Description

<!-- What changes, and why this is one unit of work rather than two. -->

## Acceptance criteria

<!-- These drive the tests. Write checkable statements, not activities.
     Bad:  Wire up the article fetcher
     Good: A De Tijd article whose browser session has expired falls back to its RSS
           summary, and the page still renders -->

- [ ] `_retire` lists the folder with `refresh=True`
- [ ] `_find_folder` lists the top level with `refresh=True`
- [ ] The test stand-in can lag: without `refresh` it answers from a snapshot, with it from the tablet — and every existing test still passes against it
- [ ] A test pushes a name whose older copy the stand-in's snapshot does not know about, and fails when `_retire` does not refresh
- [ ] The runbook and `docs/sources.md` say what a duplicate means now

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

