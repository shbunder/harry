---
id: STORY-260914-1d8a9c
title: Fold a multi-line event title onto one line
feature: FEAT-260914-e871d4
status: Done
created: 2026-09-14
---

# STORY-260914-1d8a9c — Fold a multi-line event title onto one line

Part of [[FEAT-260914-e871d4]].

## Description

One helper in `_shape`, applied to both free-text fields, with a fixture carrying the real
shape of the problem.

## Acceptance criteria

- [x] `'Kids
 School [15:15]'` becomes `'Kids School [15:15]'`
- [x] Tabs, carriage returns and runs of spaces collapse to one space
- [x] Leading and trailing whitespace goes
- [x] `where` gets the same treatment
- [x] An ordinary title is returned unchanged
- [x] A fixture carries a genuinely multi-line SUMMARY, so the test cannot pass by accident

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

