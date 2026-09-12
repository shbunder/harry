---
id: FEAT-260912-0f2744
title: The morning page lands on the tablet before you're up
status: Backlog
track: full
created: 2026-09-12
touches: [jobs/morning-page, tools/digest]
stories: []
decisions: []
---

# FEAT-260912-0f2744 — The morning page lands on the tablet before you're up

## Summary

What all of it is for. At 06:30 a Claude scheduled task asks Harry for candidates, decides what matters, writes a short intro and asks for the page. Harry fetches the chosen articles, renders the PDF and pushes it. Not headlines: the full articles, as pages behind the front page.

## Acceptance criteria

<!-- One box per scenario. These are what the pre-close-verifier builds its
     traceability matrix from. -->

- [ ] digest_list_candidates returns the weather, the agenda and up to 40 headlines with ids to choose from
- [ ] digest_build takes the chosen ids and an intro, renders the page and pushes it
- [ ] The page is one front page, then one to two pages per article, with an outline the tablet navigator reads
- [ ] The page renders at exactly 509.34 by 679.13 points, so the tablet never rescales it
- [ ] A section whose source is unavailable prints that, and every other section still renders
- [ ] How many articles it carries is the job's own setting, defaulting to eight
- [ ] A page not built by the deadline puts one message in Slack

## Stories

<!-- Maintained by `board.py new-story`. -->

## Notes

<!-- Appended by `board.py note`. -->

## Links

- Requirements: [[FEAT-260912-0f2744]]
