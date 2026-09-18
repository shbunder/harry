---
id: STORY-260918-f117b8
title: What Claude is handed each morning is only what it chooses on
feature: FEAT-260918-4065d5
status: Done
created: 2026-09-18
---

# STORY-260918-f117b8 — What Claude is handed each morning is only what it chooses on

Part of [[FEAT-260918-4065d5]].

## Description

<!-- What changes, and why this is one unit of work rather than two. -->

## Acceptance criteria

<!-- These drive the tests. Write checkable statements, not activities.
     Bad:  Wire up the article fetcher
     Good: A De Tijd article whose browser session has expired falls back to its RSS
           summary, and the page still renders -->

- [x] `digest_list_candidates` drops `image` from every headline it returns, and a test fails if it comes back
- [x] It drops `feed` too: every id already begins with that feed's slug, and `source` is the name a person reads
- [x] **`date` stays on every headline.** `news.search` applies no date filter, so the newest 40 can include yesterday's stories, and a candidate that lost its date would be put on today's page as today's news
- [x] `news_search` is unchanged — it serves a caller asking across days, where `feed` and `date` are the answer rather than noise
- [x] The trim happens in the tool, not in `CONCISE_FIELDS`, so the connector keeps serving both callers
- [x] Measured on the running stack, before and after, with the three regional feeds configured: the payload for 40 headlines and what fraction each field costs

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

