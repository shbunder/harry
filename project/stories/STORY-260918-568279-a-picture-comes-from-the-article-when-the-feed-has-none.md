---
id: STORY-260918-568279
title: A picture comes from the article when the feed has none
feature: FEAT-260918-5fdfa6
status: Done
created: 2026-09-18
---

# STORY-260918-568279 — A picture comes from the article when the feed has none

Part of [[FEAT-260918-5fdfa6]].

## Description

<!-- What changes, and why this is one unit of work rather than two. -->

## Acceptance criteria

<!-- These drive the tests. Write checkable statements, not activities.
     Bad:  Wire up the article fetcher
     Good: A De Tijd article whose browser session has expired falls back to its RSS
           summary, and the page still renders -->

- [x] `news.article()` returns the page's `og:image` as `image` when the feed entry carried none, parsed from the HTML it already fetched
- [x] A feed entry that carried a picture keeps it, and the article's is ignored — tested against a recorded page whose `og:image` differs from the feed's
- [x] A page with no `og:image` leaves `image` null, logs nothing and alerts nothing
- [x] De Tijd is covered by the same parse, from the HTML its reader already returns — no second copy of the rule inside the tijd connector, and no change to what a reader must hand back
- [x] `digest_build` illustrates a card from the article's picture when the feed gave none, and prefers the feed's when both exist
- [x] `.harry/tools/news_article/TOOL.md` no longer tells Claude that nothing is fetched to produce `image`, because now something is
- [x] Every page used as evidence is a recorded fixture under `tests/fixtures/`, not a live URL. De Tijd's is the one already there, `tests/fixtures/tijd/article-logged-in.html`, which carries an `og:image`
- [x] `live` — through the running stack, a De Tijd article on the page carries a picture

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

