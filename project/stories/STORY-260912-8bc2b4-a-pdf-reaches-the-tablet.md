---
id: STORY-260912-8bc2b4
title: A PDF reaches the tablet
feature: FEAT-260912-cfeb21
status: Backlog
created: 2026-09-12
---

# STORY-260912-8bc2b4 — A PDF reaches the tablet

Part of [[FEAT-260912-cfeb21]].

## Description

Settles the free-tier question two independent implementers disagree about, and proves the pairing flow end to end before the renderer exists to feed it.

## Acceptance criteria

<!-- These drive the tests. Write checkable statements, not activities.
     Bad:  Wire up the article fetcher
     Good: A De Tijd article whose browser session has expired falls back to its RSS
           summary, and the page still renders -->

- [x] A device is paired with rmapi using a code from my.remarkable.com
- [x] A one-page PDF pushed with remarkapy appears on the tablet
- [x] Whether this account needs a Connect subscription for that to work is recorded either way
- [x] The exact rmapi and remarkapy versions that worked are recorded, to be pinned
- [x] Where rmapi wrote the device token is named, and it is outside the repo — that token is complete read
      and write access to every document on the tablet, with no scopes and no read-only mode
- [x] The finding is a dated note on FEAT-260912-74f222, the connector that depends on it

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

