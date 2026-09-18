---
id: FEAT-260918-50ca24
title: The paper is fuller: more candidates, and a second sheet that may run to two pages
track: story
created: 2026-09-18
touches: [connectors/news-config, docs/sources-feeds, jobs/morning-page, tools/digest_build]
stories: [STORY-260918-e62f8e]
decisions: []
---

# FEAT-260918-50ca24 — The paper is fuller: more candidates, and a second sheet that may run to two pages

## Summary

The second sheet came out ragged: Culture had one story on it. Three things were starving it,
all measured on 2026-09-18.

**The brief asks for 40 candidates when the tool will give 60.** At 60 the answer carries 27
VRT, 20 BBC and 10 De Tijd — 57 national stories to choose from instead of 37, for about 6,500
tokens rather than 4,600.

**De Tijd only ever offers 10.** That is its whole `nieuws` feed. It publishes eight sections,
each of 10 and mostly distinct — `cultuur` adds 8 stories not in `nieuws`, `politiek` 10, and
`ondernemen` 8. Culture was thin partly because nothing was feeding it.

**The second sheet is treated as one page.** The brief asks for 10 to 12 and `digest_build`
reports "one or two stories too many" the moment it spills. Two pages is now what a full
second sheet looks like, so it stops being a fault and the brief asks for up to 20 — about
four in each category the day actually supports.

What does not change: Claude still decides what is on the page. More candidates is a wider
choice, not a longer paper.

## Acceptance criteria

<!-- One box per scenario. These are what the pre-close-verifier builds its
     traceability matrix from. -->

- [x] The brief asks `digest_list_candidates` for 60, and the answer carries at least 50 national candidates on a normal day
- [x] De Tijd's `cultuur`, `politiek` and `ondernemen` feeds are read beside `nieuws`, and the duplicates between them are dropped
- [x] The brief asks for up to 20 on the second sheet, about four per category where the day has them, and still leaves a category out rather than padding it
- [x] A second sheet running to two pages is not reported as crowded; three pages still is
- [x] `docs/sources.md` lists the four De Tijd feeds and says the eight sections exist
- [x] Through the running stack: a built page has at least three stories under Culture on a day the feeds carry them

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260918-e62f8e]] — A fuller second sheet, and the candidates to fill it

## Notes

<!-- Appended by `board.py note`. -->
- **2026-09-18** — Measured on the real configuration, 2026-09-18. Asking for 60 returns 60 headlines — 23 VRT NWS, 17 BBC News, 17 De Tijd, 2 ROB tv, 1 KW — with 90 dropped from the pool, all 60 ids unique and unavailable empty. De Tijd went from 10 to 17 by reading cultuur, politiek and ondernemen beside nieuws, and the four print as one source. Payload is 26,202 characters, about 6,550 tokens, up from 4,600 at 40 candidates. A page built from them: 20 on the second sheet over two pages, crowded empty, and every section carrying three or more — At home 7, Abroad 4, AI and technology 3, Culture 3, And one more thing 3. Culture had one before this.

## Links

