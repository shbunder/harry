---
id: STORY-260918-177cde
title: Three regional feeds carry the towns the national ones miss
feature: FEAT-260918-4065d5
status: Done
created: 2026-09-18
---

# STORY-260918-177cde — Regional feeds carry the towns the national ones miss

<!-- Opened as "three feeds" and shipped with two: HLN was dropped by the owner mid-build. -->

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
- [x] `by inspection: docs are prose` — `docs/sources.md` says which feed carries which town, which five sources were tried and why each is unusable, and where the three nearby settings live
- [ ] `by inspection: the files hold this machine's configuration and are gitignored` — the two feeds are added to the NUC's `.harry/connectors/news/.env.local`, and the three nearby settings to `.harry/tools/digest_list_candidates/.env.local`
- [x] On the running stack, `digest_list_candidates` returns **at least 1** nearby candidate in the newest 40, and the page still comes back with a full 40. Fewer than 1 means the feeds are not being read or a slug is misspelled; the upper end is held by `nearby_limit` rather than by hope. Measured 2026-09-18: 40 headlines — 35 VRT, 4 ROB tv, 1 KW — with 5 nearby, last in the list

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

