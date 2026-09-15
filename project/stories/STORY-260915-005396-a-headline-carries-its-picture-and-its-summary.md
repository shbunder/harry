---
id: STORY-260915-005396
title: A headline carries its picture and its summary
feature: FEAT-260915-10c6e3
status: Done
created: 2026-09-15
---

# STORY-260915-005396 — A headline carries its picture and its summary

Part of [[FEAT-260915-10c6e3]].

## Description

Two parsers, two feed shapes, one field. VRT publishes its picture as an Atom `link` with
`rel="enclosure"`; the BBC publishes a `media:thumbnail` at 240px whose path serves 800px if
you ask for it. Both are already in the document `_parse` is holding and both are discarded.

`article()` is the same story from the other end: it rebuilds its answer from five keys of
the candidate it just resolved, so a story whose page will not load loses the feed's own
summary — the one thing that was always going to be readable. Adding `summary` and `image`
there is the same change to the same shape.

## Acceptance criteria

- [x] A VRT candidate carries `image`: the `rel="enclosure"` URL from its Atom entry
- [x] A BBC candidate carries `image`: its `media:thumbnail` URL with `/standard/240/` asked for as `/standard/800/`
- [x] A candidate from a feed with no image carries `image: null`, and nothing reaches Slack — `tests/fixtures/news/collision.xml` is three such entries
- [x] `image` is on a `concise` candidate as well as a `full` one
- [x] `news.article(id)` carries `summary` and `image` when the page was read
- [x] `news.article(id)` carries `summary` and `image` when the page answered 403, alongside `available: false` and `why`
- [x] The `news_search` tool returns `image` on a candidate, and the `news_article` tool returns `summary` and `image`; both `TOOL.md` bodies say what they are
- [x] `docs/` describes `image` and `summary` beside the rest of the news connector

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

