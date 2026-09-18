---
id: STORY-260918-30a017
title: The page can print a seventh topic, and Nearby leads it
feature: FEAT-260918-4065d5
status: Backlog
created: 2026-09-18
---

# STORY-260918-30a017 — The page can print a seventh topic, and Nearby leads it

Part of [[FEAT-260918-4065d5]].

## Description

<!-- What changes, and why this is one unit of work rather than two. -->

## Acceptance criteria

<!-- These drive the tests. Write checkable statements, not activities.
     Bad:  Wire up the article fetcher
     Good: A De Tijd article whose browser session has expired falls back to its RSS
           summary, and the page still renders -->

- [ ] `marks.py` carries `regional` first, with its own shape, and a test fails if it is dropped or moved behind `belgium`
- [ ] A pick with topic `regional` is drawn with the Nearby mark — not sorted last and unmarked, which is what an unknown topic gets
- [ ] Front-page picks sort with every `regional` ahead of every `belgium`, and a test fails if the order changes
- [ ] The second sheet heads its first section "Nearby" when anything regional is in it
- [ ] A page built with nothing regional prints no Nearby heading, and the other sections render unchanged
- [ ] `.harry/jobs/morning-page/JOB.md` describes the topic, names Oostende, Leuven and Holsbeek, and says to leave the section out on a day with none
- [ ] The claude.ai routine's copy of the brief is updated in the same change, and the board records that it was

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

