---
id: FEAT-260912-24d052
title: Headlines arrive from VRT NWS and the BBC
track: full
created: 2026-09-12
touches: [connectors/news, docs, tools/news]
stories: [STORY-260914-94e747, STORY-260914-636ac0, STORY-260914-d1ecf1]
decisions: [ADR-260914-5a682c]
---

# FEAT-260912-24d052 — Headlines arrive from VRT NWS and the BBC

## Summary

The candidates Claude chooses from. Feeds in, deduplicated headlines out, and the full text of anything on a site that serves plain HTTP. De Tijd is deliberately not here: it blocks scripted clients and needs its own feature.

## Acceptance criteria

<!-- One box per scenario. These are what the pre-close-verifier builds its
     traceability matrix from. -->

- [ ] An Atom feed and an RSS 2.0 feed both produce candidates carrying title, summary, source, published time and link
- [ ] A candidate's id is `<feed-slug>-<YYYY-MM-DD>-<first 6 title words>`, and a collision gets `-2`
- [ ] One story carried by two feeds is one candidate, kept from the feed listed first in `FEEDS`
- [ ] Two links to the same page are the same story once the query string and fragment are dropped
- [ ] `news_search` returns the 20 newest candidates by default and never more than 50
- [ ] `news_search` narrows by source slug and by a `since` date
- [ ] `news_article` returns at least 1000 characters of a recorded BBC page, fetched with a browser User-Agent, following the redirect
- [ ] `news_article` on an unknown id fails with a message naming the id and telling the caller to search again
- [ ] A feed that 404s is listed unavailable with why, the other feeds still return, and one line reaches Slack
- [ ] A feed that has already failed in the last 24 hours sends nothing further to Slack
- [ ] A feed answering HTML instead of XML is listed unavailable, not fatal
- [ ] A feed document declaring `<!DOCTYPE` before its root element is refused unread
- [ ] Four calls within one minute fetch each feed once; a call after 5 minutes fetches again
- [ ] An article page that answers 403 gives `available: false` with why, and one line reaches Slack
- [ ] Every parsing test runs against a recorded fixture in `tests/fixtures/news/`, never a live URL

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260914-94e747]] — Candidates arrive from an Atom feed and an RSS feed
- [ ] [[STORY-260914-636ac0]] — A dead feed says so in Slack and costs nothing else
- [ ] [[STORY-260914-d1ecf1]] — Claude can search the headlines and read one in full

## Notes

<!-- Appended by `board.py note`. -->

## Links

- Requirements: [[FEAT-260912-24d052]]
- Decision: [[ADR-260914-5a682c]] — Feeds are parsed with the standard library, not a feed library

