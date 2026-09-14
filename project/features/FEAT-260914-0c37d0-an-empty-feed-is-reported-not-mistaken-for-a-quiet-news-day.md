---
id: FEAT-260914-0c37d0
title: An empty feed is reported, not mistaken for a quiet news day
track: story
created: 2026-09-14
touches: [connectors/news]
stories: [STORY-260914-2c449d]
decisions: []
---

# FEAT-260914-0c37d0 — An empty feed is reported, not mistaken for a quiet news day

## Summary

At 19:00 on 14 September 2026, `www.vrt.be/vrtnws/nl.rss.articles.xml` answered **200 with a
valid Atom document containing zero entries** — 555 bytes of header and nothing else. Three
fetches, four seconds apart, all the same. An hour earlier the same URL carried fifty
stories.

Harry reported nothing. `unavailable` was empty, no line reached Slack, and the morning page
would have been built from the BBC alone — which is indistinguishable from a quiet day in
Belgium.

**That is the exact failure this connector was written to prevent.** Its own ADR says a dead
feed "does not look broken: the candidate list is just shorter, Claude picks six BBC stories,
and the page reads like a slow news day in Belgium." The guard covers a feed that 404s,
times out, answers HTML, or declares entities. It does not cover the one that politely
answers an empty feed.

An empty feed is not the same as an unreadable one, so it should not read the same. But it is
not a normal Tuesday either: a national broadcaster publishes something every hour.

## Acceptance criteria

- [ ] A configured feed that parses but yields no candidates is listed in `unavailable`, saying it answered an empty feed
- [ ] The other feeds' candidates still come back — an empty feed costs its own source and nothing else
- [ ] One line reaches Slack naming that feed, once per 24 hours, under its own key rather than the one a fetch failure uses
- [ ] A feed that yields candidates reports nothing, and a day when every feed is genuinely quiet is still not an error
- [ ] The fixture is the real 555-byte document VRT served, recorded

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260914-2c449d]] — Say when a feed answers empty

## Notes

<!-- Appended by `board.py note`. -->

## Links

