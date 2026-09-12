---
id: FEAT-260912-cfeb21
title: Every unknown that could sink the morning page is settled
status: Backlog
track: full
created: 2026-09-12
touches: [scratch]
stories: []
decisions: []
---

# FEAT-260912-cfeb21 — Every unknown that could sink the morning page is settled

## Summary

Five questions nobody has answered, each of which can invalidate a later phase. Each one is a throwaway script that prints PASS or FAIL, and each finding is written into the decision or the scenario that depends on it. The connector question is the one on the critical path: if a Claude scheduled task cannot reach Harry, the morning page has no trigger and nothing downstream is safe to build.

## Acceptance criteria

<!-- One box per scenario. These are what the pre-close-verifier builds its
     traceability matrix from. -->

- [ ] A Claude scheduled task calls a tool on Harry over the tunnel and gets the result back
- [ ] A De Tijd article's full body is on stdout, pulled through a browser session saved by hand
- [ ] An MCP tool call that blocks for five minutes returns its result rather than timing out
- [ ] A one-page PDF pushed with remarkapy appears on the tablet, and we know whether the free tier carries it
- [ ] Today's iCloud events come back over CalDAV, and we know whether Reminders arrive as VTODO
- [ ] Every finding is written into the decision or scenario that depends on it, quoting what was measured

## Stories

<!-- Maintained by `board.py new-story`. -->

## Notes

<!-- Appended by `board.py note`. -->

## Links

- Requirements: [[FEAT-260912-cfeb21]]
