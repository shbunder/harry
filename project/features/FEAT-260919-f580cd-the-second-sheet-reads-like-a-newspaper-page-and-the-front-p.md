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

- [x] The front page's right column head reads "Other news →" and links to the second sheet; there is no button beneath the six stories
- [x] A page with no second-sheet stories has no "Other news" link on the front page or on any article page
- [x] On a page built through `digest_build`, a day whose only event runs 09:30–11:30 draws hours past 13:00, its grid as tall as the room it was given, at no more than 34pt an hour
- [x] A day with events from 07:00 to 21:00 draws 07 to 22 and no more, at no less than 18pt an hour
- [x] A day with nothing timed, or a calendar that could not be read, draws 07 to 21 sized to the room, and the day column stays on the front page
- [x] A day from 06:00 to 23:00 is drawn at 18pt an hour, and `crowded` says the day column did not fit on the front sheet
- [x] The story opening each run carries its picture, a larger headline and the first sentence of its summary; the others carry headline and source only; every headline is whole; companions get a line each
- [x] Second-sheet stories across five topics print in three columns, with no topic heading, each with its topic's mark, in the paper's order
- [x] A full day of 20 and a light day of 10 are each set at the ladder's fewest pages, then the fullest last page, and neither runs past two pages
- [x] A sheet forced past two pages renders at the fewest pages and `crowded` says "also today" runs to 3 pages
- [x] KW's recorded summary prints on the sheet as its first sentence, with no tag and no character code
- [x] A second-sheet picture that answers 404 is requested once in the whole build
- [x] An article page's way back to the second sheet is called "Other news"
- [x] The brief's step 3 no longer asks for about four stories in each category

## Stories

<!-- Maintained by `board.py new-story`. -->
- [x] [[STORY-260919-d7824c]] — Broadsheet second sheet, the way onward in the column head, and a timetable that reaches the foot

## Notes

<!-- Appended by `board.py note`. -->

- 2026-09-19 — `.harry/jobs/morning-page/JOB.md` is also edited by FEAT-260913-fdd33f (a header comment, commit 1c5d4fd), which declares only `docs, nuc, mcp-config`, so the lane check cannot see it. This feature edits step 3 only; the two diffs do not meet.
- **2026-09-19** — Outstanding after merge: the claude.ai routine carries its own copy of the brief, and its step 3 still asks for about four stories in each category. The owner updates it; the new step 3 is in the merge's JOB.md. Once they have, the copy is compared with JOB.md through the routines API.

## Lessons Learned

**What worked**

- **Reading the PDF the tablet opens, not the CSS.** Three columns are proved by where the
  stories' link annotations land on the sheet page, and the way onward by its annotation sitting
  above every story link on page one. A `column-count` check or an HTML check would have passed
  the old button bug; these could not. Helpers: `links()` and `starts()` in
  `tests/test_digest_build.py`, reading `/Dest` names and `get_destination_page_number`.
- **Catching the page on its way to the renderer.** `drawn()` swaps the loaded tool's `render`
  global for a spy, so a test reads the HTML production would print after every measuring and
  fitting step has run — the timetable's hours and grid height, the sheet's markup.
- **Mutants, run by name against the test meant to kill them.** 32 of them; three survivors in
  the first pass each exposed something real: a rule no test day could tell apart from another
  (fewest pages vs fullest), a 34pt ceiling that could never bind, and a KW summary whose
  character codes sat after its first sentence and so never reached the page.
- **A preview through the container's own connectors without touching `/data`**: tar the
  worktree's tracked `digest_build` files into the container's `/tmp`, and
  `load([*capability_roots(), Path('/tmp/preview-root/.harry')])` — a later root replaces an
  earlier one. `HARRY_DIGEST_BUILD_OUT_DIR=/tmp/…` and `deliver=False`.

**What to do differently**

- **A claim that something is unreachable needs a measurement, every time.** The first forced
  test said "nothing a caller can send reaches three pages". Twenty stories with nine companions
  each do, through the tool. `SECOND_SHEET_PAGES` had recorded exactly this lesson once before,
  and the rewrite deleted it.
- **Pin a threshold from both sides.** Deleting the `crowded` gate was caught; moving
  `SECOND_SHEET_PAGES` to 1 or 6 was not, until one test built a real two-page sheet that must
  not be reported and another an exactly-three-page one that must.
- **Cutting a block of a test file by "from this test to that one" takes whatever sat
  between.** It silently deleted a helper and a test; a mutant then "failed" in 0.18s on a
  `NameError`. A mutation run should treat pytest's exit code 5 (no tests) and a sub-second
  failure as errors, not kills.
- **Two agents shared one scratchpad file name** (`mutate.py`) and the verifier overwrote mine.
  Give scratch scripts a feature-specific name.

**Patterns to reuse**

- `settle()` in `.harry/tools/digest_build/page.py`: render one region alone at each setting on
  a ladder, keep `min(tried, key=(pages, -fill))`, measure the fill as the lowest classed box on
  the last page from `_boxes()`.
- `span()` in `.harry/tools/digest_build/timetable.py`: pick the extent first (run the day on
  until 34pt hours fill the room), then the scale — rather than stretching a fixed extent.
- `gist()`: strip tags and unescape until nothing changes, capped at three — ROB tv encodes its
  codes twice (`&amp;nbsp;`), KW sends HTML.
- `headline_sizes()` in the tests: walk WeasyPrint's box tree carrying an ancestor flag, and read
  `box.style['font_size']` to assert what CSS actually applied.

## Links

- Requirements: [[FEAT-260919-f580cd]]
- Decision: [[ADR-260919-f32bde]] — The second sheet has no sections, and fits itself to at most two pages

