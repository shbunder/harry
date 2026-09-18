---
id: STORY-260918-30a017
title: The page can print a seventh topic, and Nearby leads it
feature: FEAT-260918-4065d5
status: Done
created: 2026-09-18
---

# STORY-260918-30a017 — The page can print a seventh topic

<!-- Opened as "and Nearby leads it". It led the paper when this was written; the owner moved
     it to the back on the same day, once there was a page to look at. -->

Part of [[FEAT-260918-4065d5]].

## Description

<!-- What changes, and why this is one unit of work rather than two. -->

## Acceptance criteria

<!-- These drive the tests. Write checkable statements, not activities.
     Bad:  Wire up the article fetcher
     Good: A De Tijd article whose browser session has expired falls back to its RSS
           summary, and the page still renders -->

- [x] `marks.py` carries `regional` between `sport` and `oddity`, with its own shape, and a test fails if it is dropped or moved
- [x] A pick with topic `regional` is drawn with the Nearby mark — not sorted last and unmarked, which is what an unknown topic gets
- [x] Front-page picks sort with every `regional` behind the day's news and ahead of the oddity, and a test fails if the order changes
- [x] The second sheet heads a "Nearby" section behind "At home" when anything regional is in it
- [x] A page built with nothing regional prints no Nearby heading, and the other sections render unchanged
- [x] `.harry/tools/digest_build/TOOL.md` lists the seven topics and the running order it lays the paper out in — it is the description Claude reads when it calls the tool, and `tests/test_digest_build.py` already asserts against that body
- [x] `marks.py`'s docstring no longer says six shapes are the limit, and says what was measured instead
- [x] `.harry/jobs/morning-page/JOB.md` describes the topic, names Oostende, Leuven and Holsbeek, says to leave the section out on a day with none, and says a nearby story leads only when another paper carries it
- [x] The brief says a missing source is named in the intro whenever the section it feeds is thin — not only when a whole topic is lost — so a half-empty Nearby section cannot read as a quiet week
- [ ] `by inspection: the routine lives on claude.ai and no test can read it` — the routine's copy of the brief carries the same seven topics and the same three towns as `JOB.md`, compared line by line at close

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

