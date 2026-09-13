---
id: STORY-260912-8d003e
title: A De Tijd article comes back in full
feature: FEAT-260912-cfeb21
status: Backlog
created: 2026-09-12
---

# STORY-260912-8d003e — A De Tijd article comes back in full

Part of [[FEAT-260912-cfeb21]].

## Description

The riskiest spike. De Tijd returns 403 to any non-browser client, even for free articles, and it is the source most worth having. If a saved browser session does not work, that connector carries RSS summaries only and its full-text scenarios are dropped rather than degraded.

## Acceptance criteria

<!-- These drive the tests. Write checkable statements, not activities.
     Bad:  Wire up the article fetcher
     Good: A De Tijd article whose browser session has expired falls back to its RSS
           summary, and the page still renders -->

- [x] A session logged in by hand in a headed browser is saved with `storage_state`
- [x] Reusing it headless returns one article body of more than 1,000 characters of prose through trafilatura
- [x] A redirect stub link is shown to resolve to the real article, or shown not to
- [ ] How old the session was when it last worked is recorded, as the starting guess for how often it needs renewing
- [x] The finding is a dated note on FEAT-260912-9c933f, the connector that depends on it
- [x] The saved session is written to a path outside the repo, and nothing commits it

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

