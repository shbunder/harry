---
id: STORY-260914-d1ecf1
title: Claude can search the headlines and read one in full
feature: FEAT-260912-24d052
status: Backlog
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

- [ ] `news_search()` returns the 20 newest candidates
- [ ] `news_search(limit=100)` returns at most 50
- [ ] `news_search(source="bbc")` returns only BBC candidates
- [ ] `news_search(since="2026-09-14")` returns only candidates published on or after that date
- [ ] `news_search(query="train")` returns only candidates whose title or summary contains it, case-insensitively
- [ ] `news_search` reports `unavailable` alongside the candidates, so a dead feed is visible to Claude as well as in Slack
- [ ] `news_article(id)` returns at least 1000 characters of text from the recorded BBC page for `cy5zg41dkqwo`
- [ ] `news_article` fetches with a browser `User-Agent` and follows redirects, which is what the short `vrtnws.be/p.…` links need
- [ ] `news_article` on an id no feed carries raises, and the message names the id and says to search again
- [ ] `news_article` on a page answering 403 returns `available: false` with why, and one line reaches Slack
- [ ] `news_article` on a page with no extractable article text returns `available: false` with why
- [ ] Both tools are deferred, `readOnlyHint: true`, and namespaced `news_`
- [ ] The connector lists both in `provides:`

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

