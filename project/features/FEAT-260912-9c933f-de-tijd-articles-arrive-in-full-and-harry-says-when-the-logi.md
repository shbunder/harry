---
id: FEAT-260912-9c933f
title: De Tijd articles arrive in full, and Harry says when the login lapses
track: full
created: 2026-09-12
touches: [connectors/tijd]
stories: []
decisions: []
---

# FEAT-260912-9c933f — De Tijd articles arrive in full, and Harry says when the login lapses

## Summary

The fragile source. De Tijd returns 403 to any non-browser client, even for free articles, so this reads it through a real browser carrying a real login. That session expires every few weeks, and the alert is the feature: without it the page quietly loses its best source and you notice in three weeks.

## Acceptance criteria

<!-- One box per scenario. These are what the pre-close-verifier builds its
     traceability matrix from. -->

- [ ] A De Tijd article's full text is extracted through a browser session saved on disk
- [ ] A redirect stub link resolves to the real article before extraction
- [ ] When the session has expired the article falls back to its RSS summary and the page still renders
- [ ] An expired session puts one message in Slack naming De Tijd — one, not one per article
- [ ] The saved session is read from the data volume and never written into the repo

## Stories

<!-- Maintained by `board.py new-story`. -->

## Notes

<!-- Appended by `board.py note`. -->

## Links

- Requirements: [[FEAT-260912-9c933f]]
