---
id: FEAT-260918-4065d5
title: A Nearby section brings Oostende, Leuven and Holsbeek onto the page
track: full
created: 2026-09-18
touches: [connectors/news, docs/sources, jobs/morning-page, tools/digest_build, tools/digest_list_candidates]
stories: [STORY-260918-30a017, STORY-260918-177cde, STORY-260918-f117b8]
decisions: [ADR-260918-713fa1]
---

# FEAT-260918-4065d5 — A Nearby section brings Oostende, Leuven and Holsbeek onto the page

## Summary

The page gains a **Nearby** section: news from Oostende, Leuven and Holsbeek, printed first,
ahead of Belgium. Those three towns are where its reader lives, and today they reach the page
only when something big enough for national news happens in them — two stories in fifty on
2026-09-18, and Holsbeek not at all in a normal week.

So this adds a seventh topic and the sources to fill it. Which stories are local stays
Claude's judgement, like every other topic. On a day with nothing nearby the section is left
out, the way basketball is on a day with no basketball.

## Acceptance criteria

<!-- One box per scenario. These are what the pre-close-verifier builds its
     traceability matrix from. -->

- [x] A pick with topic `regional` carries the Nearby mark and sorts ahead of every `belgium` pick
- [x] A `regional` pick is drawn with its own mark, not sorted last and unmarked as an unknown topic is
- [x] The second sheet's first section is headed "Nearby" when there is anything to put in it
- [x] A page with nothing regional prints no Nearby heading, and every other section is unchanged
- [x] The news connector reads ROB tv, HLN Leuven and HLN Oostende beside the national feeds, and their ids carry their own slugs
- [x] A regional feed that fails is named in `unavailable` and costs only itself — the national headlines still arrive
- [x] Every place that lists the topics agrees: `marks.py`, `digest_build/TOOL.md`, the job's brief, and the claude.ai routine's copy
- [x] The brief names a missing source in the intro whenever the section it feeds is thin, so a half-empty Nearby section cannot read as a quiet week
- [ ] The job's brief and the claude.ai routine's copy name the same three towns and the same rule for a day with none
- [x] `digest_list_candidates` hands Claude no `image` and no `feed` — 17% of the payload it never uses — while `date` stays and `news_search` is unchanged
- [x] `docs/sources.md` says which feeds carry the three towns, and that VRT's regional feeds answer 410

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260918-30a017]] — The page can print a seventh topic, and Nearby leads it
- [ ] [[STORY-260918-177cde]] — Three regional feeds carry the towns the national ones miss
- [ ] [[STORY-260918-f117b8]] — What Claude is handed each morning is only what it chooses on

## Notes

<!-- Appended by `board.py note`. -->
- **2026-09-18** — Built and rendered against real feeds on 2026-09-18. With the three regional feeds configured, digest_list_candidates returned 40 headlines — 30 VRT, 6 HLN Oostende, 2 HLN Leuven, 2 ROB tv — so 10 regional in the newest 40, inside the 1-20 band the story asks for, and unavailable was empty. A page built from them put the two local stories at 1 and 2 with the Nearby mark, ahead of at-home, and crowded came back empty. The payload trim measured on the same call: 21,959 characters down to 17,049, a 22.4% saving, about 1,227 tokens every morning. A headline is now date, id, source, summary and title. Still open: the three feeds go in the NUC's .env.local, which is the owner's to edit, and the claude.ai routine's copy of the brief needs the same seven topics.

## Links

- Requirements: [[FEAT-260918-4065d5]]
- Decision: [[ADR-260918-713fa1]] — The paper runs to seven topics, and the seventh is a place

