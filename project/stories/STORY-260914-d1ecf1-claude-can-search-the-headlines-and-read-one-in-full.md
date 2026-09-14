---
id: STORY-260914-d1ecf1
title: Claude can search the headlines and read one in full
feature: FEAT-260912-24d052
status: Done
created: 2026-09-14
---

# STORY-260914-d1ecf1 — Claude can search the headlines and read one in full

Part of [[FEAT-260912-24d052]].

## Description

The two tools, and the article fetch behind one of them.

`news_search` is where Claude sees the forty headlines. `news_article` is where it reads
the ones it picked. They stay apart on purpose: choosing among the headlines is the product,
which is the consolidation rule in `.claude/rules/tool-design.md`.

`news.article(id)` re-resolves the id against the feeds rather than reading anything the
search left behind, so the digest holds no state between its two calls — the interface
FEAT-260912-0f2744 wrote down. The 5-minute fetch cache from the previous story is what
keeps that from costing seven downloads.

## Acceptance criteria

- [x] `news_search()` returns the 20 newest candidates, and `news_search(limit=40)` returns 40
- [x] `news_search(limit=100)` returns at most 50
- [x] `news_search(source="bbc")` returns only BBC candidates
- [x] `news_search(since="2026-09-14")` returns only candidates published on or after that date
- [x] `news_search(query="train")` returns only candidates whose title or summary contains it, case-insensitively
- [x] `news_search()` defaults to `detail="concise"`: id, title, source, feed, date and a summary cut to 200 characters, and no link
- [x] `news_search(detail="full")` carries the whole summary and the link
- [x] `news_search` reports `unavailable` alongside the candidates, so a dead feed is visible to Claude as well as in Slack
- [x] `news_article(id)` returns at least 1000 characters of text from the recorded BBC page for `cy5zg41dkqwo`
- [x] `news_article` fetches with a browser `User-Agent` and follows redirects, which is what the short `vrtnws.be/p.…` links need
- [x] `news_article` on an id no feed carries raises, and the message names the id and says to search again
- [x] `news_article` on a page answering 403 returns `available: false` with why, and one line reaches Slack
- [x] `news_article` on a page with no extractable article text returns `available: false` with why
- [x] Both tools are deferred, `readOnlyHint: true`, and namespaced `news_`
- [x] The connector lists both in `provides:`
- [x] `docs/sources.md` describes the news source: the `FEEDS` and `TIMEZONE` settings, what a candidate and an article carry, what happens when a feed or an article page dies, and what lands in Slack

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

