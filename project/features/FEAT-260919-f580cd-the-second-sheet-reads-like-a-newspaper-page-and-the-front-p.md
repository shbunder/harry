---
id: FEAT-260919-f580cd
title: The second sheet reads like a newspaper page, and the front page fills to its foot
track: full
created: 2026-09-19
touches: [docs/morning-page, jobs/morning-page, tools/digest_build]
stories: [STORY-260919-d7824c]
decisions: [ADR-260919-f32bde]
---

# FEAT-260919-f580cd — The second sheet reads like a newspaper page, and the front page fills to its foot

## Summary

The second sheet becomes a newspaper page: three ruled columns of headlines, each marked with
its topic, in the paper's running order, with a picture and a line of summary on the story
that opens each run. Harry fits it to the day — it tries a few settings and keeps the one
that fills its last page best — and it never runs past two pages. The front page's way to it
moves up into the right column's head as "Other news →", where it cannot land on a story, and
a quiet day's timetable shows more of the afternoon so the left column reaches the foot.

## Acceptance criteria

- [ ] The front page's right column head reads "Other news →" and links to the second sheet; there is no button beneath the six stories
- [ ] A page with no second-sheet stories has no "Other news" link on the front page or on any article page
- [ ] On a page built through `digest_build`, a day whose only event runs 09:30–11:30 draws hours past 13:00, its grid as tall as the room it was given, at no more than 34pt an hour
- [ ] A day with events from 07:00 to 21:00 draws 07 to 22 and no more, at no less than 18pt an hour
- [ ] A day with nothing timed, or a calendar that could not be read, draws 07 to 21 sized to the room, and the day column stays on the front page
- [ ] A day from 06:00 to 23:00 is drawn at 18pt an hour, and `crowded` says the day column did not fit on the front sheet
- [ ] The story opening each run carries its picture, a larger headline and the first sentence of its summary; the others carry headline and source only; every headline is whole; companions get a line each
- [ ] Second-sheet stories across five topics print in three columns, with no topic heading, each with its topic's mark, in the paper's order
- [ ] A full day of 20 and a light day of 10 are each set at the ladder's fewest pages, then the fullest last page, and neither runs past two pages
- [ ] A sheet forced past two pages renders at the fewest pages and `crowded` says "also today" runs to 3 pages
- [ ] KW's recorded summary prints on the sheet as its first sentence, with no tag and no character code
- [ ] A second-sheet picture that answers 404 is requested once in the whole build
- [ ] An article page's way back to the second sheet is called "Other news"
- [ ] The brief's step 3 no longer asks for about four stories in each category

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260919-d7824c]] — Broadsheet second sheet, the way onward in the column head, and a timetable that reaches the foot

## Notes

<!-- Appended by `board.py note`. -->

- 2026-09-19 — `.harry/jobs/morning-page/JOB.md` is also edited by FEAT-260913-fdd33f (a header comment, commit 3d01102), which declares only `docs, nuc, mcp-config`, so the lane check cannot see it. This feature edits step 3 only; the two diffs do not meet.

## Links

- Requirements: [[FEAT-260919-f580cd]]
- Decision: [[ADR-260919-f32bde]] — The second sheet has no sections, and fits itself to at most two pages

