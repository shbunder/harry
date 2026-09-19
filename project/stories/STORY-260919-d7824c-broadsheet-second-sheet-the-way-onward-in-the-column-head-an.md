---
id: STORY-260919-d7824c
title: Broadsheet second sheet, the way onward in the column head, and a timetable that reaches the foot
feature: FEAT-260919-f580cd
status: Backlog
created: 2026-09-19
---

# STORY-260919-d7824c — Broadsheet second sheet, the way onward in the column head, and a timetable that reaches the foot

Part of [[FEAT-260919-f580cd]].

## Description

Three changes to one tool, `digest_build`, that were designed and reviewed together as one
page.

- **The second sheet** (`page.second_page`) stops drawing sections and cards. It draws three
  ruled columns of stories in the paper's order, each with its topic's mark, and every
  *k*-th story — the one opening a run — with a picture and the first sentence of its
  summary. `page.fit` tries a ladder of *(k, picture height)* settings, rendering the sheet
  alone for each, and keeps the one with the fewest pages, then the fullest last page.
- **The front page** loses the button and the spacer under its six stories. "Other news →"
  sits in the right column's head instead, beside "In this page", and only when there is a
  second sheet. The article pages' link to the sheet takes the same name.
- **The timetable** (`timetable.span`) picks its hours and their height together. On a day
  that would stop short of the room at 34pt an hour, it shows later hours until it fills.

One story, because they share one stylesheet and one measuring pass, and the front page's
fault and the second sheet's emptiness were found and designed as one page.

## Acceptance criteria

- [ ] The front page carries "Other news →" in its right column head, linking to the second sheet, above every story link, and no `.onward` button
- [ ] With no `more`, no page carries an "Other news" link
- [ ] Built through `digest_build`, one 09:30–11:30 event draws hours past 13:00 in a grid as tall as `fits.timetable`, at most 34pt an hour
- [ ] Built through `digest_build`, a 07:00–21:00 day draws 07 to 22 and no more, at 18pt an hour or more
- [ ] Built through `digest_build`, a day with nothing timed draws 07 to 21 sized to the room, and `crowded` is empty
- [ ] Built through `digest_build`, a 06:00–23:00 day draws 18pt hours and `crowded` names the day column
- [ ] Every k-th story on the sheet carries a picture, a larger headline and the first sentence of its summary; the rest carry neither; headlines are whole; companions print a line each
- [ ] The second sheet is drawn in three columns, with no topic heading, a mark per story, in the paper's order
- [ ] The answer's `fits.sheet` names the chosen setting, and it has the fewest pages of any ladder setting and the fullest last page among those, for 20 and for 10 stories
- [ ] With the ladder forced to one generous setting, `crowded` says "also today" runs to 3 pages or more
- [ ] KW's recorded summary prints as its first sentence, with no `<` and no `&#`
- [ ] A 404 picture on a second-sheet story is requested once per build
- [ ] The article page's link to the sheet reads "Other news"
- [ ] `JOB.md` step 3 no longer asks for about four per category; `TOOL.md` and `docs/morning-page.md` describe the sheet as it is drawn

## Tests this retires

Each asserts the layout the ADR replaces. Each is rewritten, not deleted without replacement.

- `test_nearby_heads_the_second_sheet_and_vanishes_when_there_is_nothing_in_it` — asserts a
  "Nearby" heading after "At home". There are no headings; the order it protected is kept by
  the running-order test on the sheet.
- `test_a_second_sheet_carries_the_rest_grouped_by_subject` — asserts section headings. It
  becomes the three-columns, no-headings, marks-in-order test.
- `test_a_full_second_sheet_of_two_pages_is_not_reported_as_crowded` — its docstring says
  three pages cannot be reached. It becomes the fitting test, and the forced three-page test
  covers the guard it said nothing could reach.
- `test_the_second_sheet_is_drawn_four_across` — asserts `CARD` and four across. The cards go;
  it becomes the three-column check on the stylesheet the page is drawn with.
- `test_a_nearby_story_on_the_second_sheet_needs_no_companion` — asserts the word "Nearby" on
  the page, which was the section heading. It keeps its purpose and checks the story instead.

## Subtasks

## Notes
