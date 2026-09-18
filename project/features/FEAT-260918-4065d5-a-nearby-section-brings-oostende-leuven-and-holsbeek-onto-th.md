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

The page gains a **Nearby** section: news from Oostende, Leuven and Holsbeek. Those three
towns are where its reader lives, and today they reach the page only when something big
enough for national news happens in them — two stories in fifty on 2026-09-18, and Holsbeek
not at all in a normal week.

It sits near the back, after basketball and before the oddity, because the towns are a
standing interest rather than the day's news. A local paper files far more than a national
one, so its stories are filtered to the three towns, capped, and handed over last — and one
leads the front page only when another paper carries it too. Which stories are local stays
Claude's judgement, like every other topic. On a day with nothing nearby the section is left
out, the way basketball is on a day with no basketball.

## Acceptance criteria

<!-- One box per scenario. These are what the pre-close-verifier builds its
     traceability matrix from. -->

- [x] A pick with topic `regional` carries the Nearby mark — which an unknown topic does not get — and sorts behind the day's news, after basketball and before the oddity
- [x] A `regional` pick is drawn with its own mark, not sorted last and unmarked as an unknown topic is
- [x] The second sheet heads a "Nearby" section when there is anything to put in it, behind "At home"
- [x] A page with nothing regional prints no Nearby heading, and every other section is unchanged
- [x] The news connector reads ROB tv and KW West-Vlaanderen beside the national feeds, and their ids carry their own slugs
- [x] A local paper is handed over only where it names one of the three towns, capped, and last — so one filing fifty stories a day cannot take the page
- [x] A nearby story leads the front page only when another paper carries it too, refused by name otherwise
- [x] Every id `digest_list_candidates` offers is one `digest_build` can still resolve
- [x] A regional feed that fails is named in `unavailable` and costs only itself — the national headlines still arrive
- [x] Every place that lists the topics agrees: `marks.py`, `digest_build/TOOL.md`, the job's brief, and the claude.ai routine's copy
- [x] The brief names a missing source in the intro whenever the section it feeds is thin, so a half-empty Nearby section cannot read as a quiet week
- [ ] `by inspection: the routine lives on claude.ai and no test can read it` — the job's brief and the routine's copy name the same seven topics, the same three towns, and the same rule for a day with none
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
- **2026-09-18** — Design changed by the owner on 2026-09-18, after seeing it built. Nearby moves from the front of the paper to the back, between basketball and the oddity: the three towns are a standing interest rather than the day's news, so the front is what happened and the back is what this reader keeps an eye on. Two rules came with it. A feed named in nearby_feeds is handed over only where it names one of nearby_places, capped at nearby_limit and placed last — without which KW took 17 of the newest 40 and left ROB tv, the feed that actually covers the towns, with one story. And a nearby story leads the front page only when another paper carries it too, which digest_build enforces by refusing a front-page regional pick with an empty also. HLN is out by preference; Oostende now comes from KW, which is a whole province, so the section will be thin there.
- **2026-09-18** — Pre-close verifier found two criticals, both fixed. digest_build resolved ids against 60 candidates while digest_list_candidates had moved to a pool of 150, and because the local papers are excluded from the rest rather than merged with them, the ordinary headlines offered reach deeper than 60 — a pick from the bottom of the page would have raised 'no candidate is …, the feeds move on', which is not what had happened. And the brief said 'exactly one of these six words' above a table of seven, twice; a model following the count never emits the seventh, which is silent. Both guarded now: a test builds a page from the deepest id the listing offers, and another reads the topics out of marks.py, the tool body and the brief and refuses to let them disagree. Also fixed: the mark test passed with the topic deleted and with the pin blanked, the brief equated Harry's keyword match with the regional topic, a misspelled nearby_feeds slug turned the control off silently, news_search still promised a ceiling of 50, and the tool's example still showed the two fields it had stopped returning.
- **2026-09-18** — Measured on the real configuration, 2026-09-18. digest_list_candidates returned 40 headlines — 14 VRT NWS, 13 BBC News, 10 De Tijd, 2 ROB tv, 1 KW — with 3 nearby, last in the list and every one about Leuven or Oostende: a shop closing in Oostende, a school renovation in Leuven, and the Leuven ring going car-free. unavailable was empty and no slug warning fired, so both config files agree on spelling. A headline now carries date, id, source, summary and title, and the payload is 18,349 characters, about 4,600 tokens. The national feeds are no longer crowded out: before the filter, KW alone took 17 of the newest 40 and left ROB tv with one.

## Links

- Requirements: [[FEAT-260918-4065d5]]
- Decision: [[ADR-260918-713fa1]] — The paper runs to seven topics, and the seventh is a place

