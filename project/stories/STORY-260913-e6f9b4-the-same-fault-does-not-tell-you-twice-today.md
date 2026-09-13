---
id: STORY-260913-e6f9b4
title: The same fault does not tell you twice today
feature: FEAT-260912-84c828
status: Backlog
created: 2026-09-13
---

# STORY-260913-e6f9b4 — The same fault does not tell you twice today

Part of [[FEAT-260912-84c828]].

## Description

Suppression, so a fault that repeats every five minutes does not. In memory, and a restart clears it — stated on the requirements page rather than hidden, because the store is its own piece.

## Acceptance criteria

<!-- These drive the tests. Write checkable statements, not activities.
     Bad:  Wire up the article fetcher
     Good: A De Tijd article whose browser session has expired falls back to its RSS
           summary, and the page still renders -->

- [ ] An alert carrying a key is sent once, and the same key within 24 hours is not sent
- [ ] The same key 24 hours later is sent again
- [ ] An alert with no key is always sent, however often it repeats
- [ ] Two different keys do not suppress each other

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

