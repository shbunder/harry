---
id: STORY-260914-abef7c
title: Claude can see what today could contain, and pick from it
feature: FEAT-260912-0f2744
status: Backlog
created: 2026-09-14
---

# STORY-260914-abef7c — Claude can see what today could contain, and pick from it

Part of [[FEAT-260912-0f2744]].

## Description

The first of the two calls, and the one that has to work before any source exists. With nothing loaded it returns a shape rather than an error, so every later source has somewhere to arrive.

## Acceptance criteria

<!-- These drive the tests. Write checkable statements, not activities.
     Bad:  Wire up the article fetcher
     Good: A De Tijd article whose browser session has expired falls back to its RSS
           summary, and the page still renders -->

- [ ] digest_list_candidates returns today's date, a weather section, an agenda section and a headlines list
- [ ] With no sources loaded, both sections say unavailable and the headlines are empty — and it does not raise
- [ ] A source connector that loaded fills its own section with what it returned
- [ ] A source that raises leaves its own section unavailable and the others intact
- [ ] Headlines carry a readable id, title, source, published time and summary
- [ ] limit defaults to 40 and caps what comes back, and a capped answer says so

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

