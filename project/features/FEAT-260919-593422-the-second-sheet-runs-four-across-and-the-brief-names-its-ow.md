---
id: FEAT-260919-593422
title: The second sheet runs four across, and the brief names its own job
track: story
created: 2026-09-19
touches: [jobs/morning-page, tools/digest_build]
stories: [STORY-260919-606b47]
decisions: []
---

# FEAT-260919-593422 — The second sheet runs four across, and the brief names its own job

## Summary

The run on 2026-09-19 at 10:34 — the first to reach Harry through the routine after its
connector was attached — showed two things.

**The second sheet ran to three pages** and `crowded` said so. Every card now carries a
picture, which makes each one taller, and that day had enough on it to spill. A spike laid one
heavy day out three ways: the current three-across layout took about a page and a half, four
across put five of six sections on the first page, and a picture-beside-headline layout drew
the headlines over the pictures in WeasyPrint. The owner chose four across.

**Both of that morning's runs guessed the job's name.** One tried `digest`, the other
`Bundervoet Bugle` — and spent twenty seconds searching Harry's tools and reading the routine
list before finding `morning-page`. The brief says "call `harry_mark_done` for this job"
without naming it.

It also corrects a claim written the day before: that three pages could not be reached with
twenty stories. That was measured on test stand-ins, and a real morning reached it.

Two capability folders are touched, which strictly puts this outside the story track. The brief
change is one word in a markdown file with no Python, and it comes out of the same run log.

## Acceptance criteria

<!-- One box per scenario. These are what the pre-close-verifier builds its
     traceability matrix from. -->

- [ ] The second sheet lays its cards out four across, each card narrower with a shorter picture
- [ ] A test fails if the second sheet goes back to three across
- [ ] On a heavy day the second sheet takes fewer pages than the three-across layout did — measured on the same data, before and after
- [ ] `SECOND_SHEET_PAGES`'s comment no longer says three pages cannot be reached, and says what was measured
- [ ] The brief calls `harry_mark_done("morning-page")` by name, in both `JOB.md` and the routine's copy

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260919-606b47]] — Four across, and the job named in the brief

## Notes

<!-- Appended by `board.py note`. -->

## Links

