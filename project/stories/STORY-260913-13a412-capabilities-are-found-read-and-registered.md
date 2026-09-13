---
id: STORY-260913-13a412
title: Capabilities are found, read and registered
feature: FEAT-260912-8a0ab0
status: Backlog
created: 2026-09-13
---

# STORY-260913-13a412 — Capabilities are found, read and registered

Part of [[FEAT-260912-8a0ab0]].

## Description

Discovery across the roots list, reading each declaration, and calling register. The shadowing rule lives here because it is a property of the walk, not of any one kind.

## Acceptance criteria

<!-- These drive the tests. Write checkable statements, not activities.
     Bad:  Wire up the article fetcher
     Good: A De Tijd article whose browser session has expired falls back to its RSS
           summary, and the page still renders -->

- [ ] A connector, a tool and a job under .harry/ are all registered at start-up
- [ ] No file in src/harry/ names any capability — asserted by a test that greps, not by review
- [ ] A capability in a later root replaces an earlier one of the same name, and the replacement is reported at start-up rather than done silently
- [ ] A capability under HARRY_CAPABILITIES_DIR registers exactly as one in .harry/ does, and reads its settings from its own folder
- [ ] A malformed declaration is skipped with its parse error, not raised

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

