---
id: STORY-260918-177cde
title: Three regional feeds carry the towns the national ones miss
feature: FEAT-260918-4065d5
status: In Progress
created: 2026-09-18
---

# STORY-260918-177cde — Three regional feeds carry the towns the national ones miss

Part of [[FEAT-260918-4065d5]].

## Description

<!-- What changes, and why this is one unit of work rather than two. -->

## Acceptance criteria

<!-- These drive the tests. Write checkable statements, not activities.
     Bad:  Wire up the article fetcher
     Good: A De Tijd article whose browser session has expired falls back to its RSS
           summary, and the page still renders -->

- [x] The news connector reads ROB tv and KW West-Vlaanderen beside the national feeds, configured the way every other feed is — a line in `.env.local`, never a code change
- [x] Candidates from each carry that feed's own slug, so an id says where it came from
- [x] A regional feed answering 500 is named in `unavailable` and costs only itself: the national headlines still arrive, proved against a recorded fixture
- [x] Each feed's format is recorded as a fixture under `tests/fixtures/news/`, and the parser is tested against it rather than against the live URL
- [x] `by inspection: docs are prose` — `docs/sources.md` says which feed carries which town, that HLN is paywalled so its articles print the summary, and that VRT's own regional feeds answer 410 Gone
- [ ] `by inspection: the file holds this machine's configuration and is gitignored` — the three feeds are added to the NUC's `.harry/connectors/news/.env.local`
- [x] On the running stack, `digest_list_candidates` returns **at least 1 and no more than 20** regional candidates in the newest 40. Fewer than 1 means the feeds are not being read; more than 20 means local news is crowding out the national, and the cap or the feeds need revisiting. Simulated on 2026-09-18: 10

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

