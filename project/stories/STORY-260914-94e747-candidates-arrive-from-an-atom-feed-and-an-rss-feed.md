---
id: STORY-260914-94e747
title: Candidates arrive from an Atom feed and an RSS feed
feature: FEAT-260912-24d052
status: Done
created: 2026-09-14
---

# STORY-260914-94e747 — Candidates arrive from an Atom feed and an RSS feed

Part of [[FEAT-260912-24d052]].

## Description

The `news` connector, and the part of it that turns two documents into one list.

Both feed formats, the readable id, and the deduplication live together because they are
one pass over one document: the format decides where the link is, the link is what
deduplicates, and the title and date are what make the id. Splitting them would mean
writing the Atom branch twice.

Nothing reaches the network in the tests. `tests/fixtures/news/` carries the real VRT NWS
Atom feed, the real BBC news and BBC world RSS feeds — the two that genuinely share four
stories — and a feed that is not a feed.

## Acceptance criteria

- [x] The recorded VRT NWS Atom feed yields candidates with title, summary, source name, published time and link
- [x] The recorded BBC RSS 2.0 feed yields the same five fields
- [x] The VRT link taken is the entry's `rel="alternate"` link, not its `rel="self"` one, which is another feed document
- [x] The VRT entry titled "Tessenderlo-Ham hakt knoop door: vanaf 1 januari 2027 brengt OCMW niet langer maaltijden aan huis", published 2026-09-14T09:05:56Z, gets the id `vrt-2026-09-14-tessenderlo-ham-hakt-knoop-door`
- [x] A story published 2026-09-13T22:30:00Z gets an id dated 2026-09-14, because Europe/Brussels is two hours ahead in September
- [x] Two stories from one feed on one day whose first 5 title words match get ids ending `-2` and `-3`, and all three are returned
- [x] The story at `bbc.co.uk/news/videos/cx2z5gjj838o`, carried by both recorded BBC feeds under different headlines, appears once
- [x] A link with `?at_medium=RSS&at_campaign=rss` and the same link without it are one story
- [x] The candidate kept on a duplicate is the one from the feed listed first in `FEEDS`
- [x] Candidates come back newest first
- [x] `FEEDS=vrt=VRT NWS=https://…|bbc=BBC News=https://…` parses into two feeds with those slugs and names
- [x] A `FEEDS` entry with fewer than three parts is skipped and logged, and the rest still load
- [x] An accented title folds into a url-safe id — "Tsjechië" becomes `tsjechie`, not a percent-escape and not a dropped word
- [x] A `TIMEZONE` naming a zone that does not exist logs and files stories under UTC, rather than taking the connector down

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

