---
id: STORY-260919-606b47
title: Four across, and the job named in the brief
feature: FEAT-260919-593422
status: In Progress
created: 2026-09-19
---

# STORY-260919-606b47 — Four across, and the job named in the brief

Part of [[FEAT-260919-593422]].

## Description

<!-- What changes, and why this is one unit of work rather than two. -->

## Acceptance criteria

<!-- These drive the tests. Write checkable statements, not activities.
     Bad:  Wire up the article fetcher
     Good: A De Tijd article whose browser session has expired falls back to its RSS
           summary, and the page still renders -->

- [x] `CARDS_ACROSS` is 4 in `sheet.py`, the card width follows from it, and the picture and headline are sized for the narrower card
- [x] A test builds a second sheet and fails if it is drawn three across
- [x] Measured on one heavy day before and after: the second sheet's page count and how many of its sections fit on the first page
- [x] `page.py`'s `SECOND_SHEET_PAGES` comment says three pages were reached on 2026-09-19, not that they cannot be
- [x] `JOB.md` says `harry_mark_done("morning-page")`, and the routine's copy is updated to match
- [ ] `by inspection: the routine lives on claude.ai` — the routine's brief names the job the same way

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

