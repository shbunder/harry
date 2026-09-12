---
id: FEAT-260912-24d052
title: Headlines arrive from VRT NWS and the BBC
status: Backlog
track: full
created: 2026-09-12
touches: [connectors/news]
stories: []
decisions: []
---

# FEAT-260912-24d052 — Headlines arrive from VRT NWS and the BBC

## Summary

The candidates Claude chooses from. Feeds in, deduplicated headlines out, and the full text of anything on a site that serves plain HTTP. De Tijd is deliberately not here: it blocks scripted clients and needs its own feature.

## Acceptance criteria

<!-- One box per scenario. These are what the pre-close-verifier builds its
     traceability matrix from. -->

- [ ] Configured feeds are parsed into headline, summary, source, published time and a readable id
- [ ] Two feeds carrying the same story produce one candidate, not two
- [ ] A news_search tool returns candidates filtered by source and date, capped at a default limit
- [ ] Full article text for a VRT NWS or BBC link is extracted with a browser user-agent
- [ ] A feed that 404s marks that source unavailable and the other sources still return
- [ ] Every parsing test runs against a recorded fixture, never a live URL

## Stories

<!-- Maintained by `board.py new-story`. -->

## Notes

<!-- Appended by `board.py note`. -->

## Links

- Requirements: [[FEAT-260912-24d052]]
