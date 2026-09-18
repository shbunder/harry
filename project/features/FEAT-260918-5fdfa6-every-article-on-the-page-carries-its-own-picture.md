---
id: FEAT-260918-5fdfa6
title: Every article on the page carries its own picture
track: full
created: 2026-09-18
touches: [connectors/news, docs/sources, tools/digest_build, tools/news_article]
stories: [STORY-260918-568279]
decisions: []
---

# FEAT-260918-5fdfa6 — Every article on the page carries its own picture

## Summary

A story is illustrated on the morning page only when its **feed** published a picture.
Measured 2026-09-18: VRT 46/46 and BBC 31/31 carry one, and De Tijd 0/10, ROB tv 0/13 and KW
0/50 carry none. Three of five sources are never illustrated, and the page just gained two of
them.

The pictures exist — every one of those article pages declares an `og:image` — and Harry
already downloads those pages to extract their text, then throws the HTML away. This takes
the picture out of a response it has already paid for. De Tijd is reachable only through the
logged-in browser, which is the reader the tijd connector already is.

## Acceptance criteria

<!-- One box per scenario. These are what the pre-close-verifier builds its
     traceability matrix from. -->

- [ ] When a feed publishes no picture, the article's own `og:image` is used instead
- [ ] A feed that does publish one keeps it — the page never overrides a feed's own picture
- [ ] No request is made beyond the one that already fetched the article
- [ ] De Tijd articles are illustrated, from the page the logged-in browser received — by the same parse as every other source, not a second one
- [ ] A card whose feed carried no picture is illustrated on the page from the article's own
- [ ] A story with no picture anywhere still prints, without one, and nothing reaches Slack
- [ ] A picture whose address is dead costs that card its picture and nothing else

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260918-568279]] — A picture comes from the article when the feed has none

## Notes

<!-- Appended by `board.py note`. -->

## Links

- Requirements: [[FEAT-260918-5fdfa6]]
