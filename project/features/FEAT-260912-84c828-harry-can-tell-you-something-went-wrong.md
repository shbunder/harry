---
id: FEAT-260912-84c828
title: Harry can tell you something went wrong
track: full
created: 2026-09-12
touches: [connectors/slack]
stories: []
decisions: []
---

# FEAT-260912-84c828 — Harry can tell you something went wrong

## Summary

One-way messages into Slack, which every other feature depends on. Alerting is a core principle and it cannot wait for the Slack loop in a later phase: a degraded source, a lapsed credential and a failed push all need somewhere to arrive from the first morning.

## Acceptance criteria

<!-- One box per scenario. These are what the pre-close-verifier builds its
     traceability matrix from. -->

- [ ] A notify call puts a message in the configured channel
- [ ] A failure that keeps repeating is reported once a day, not once an attempt
- [ ] When Slack itself is unreachable the failure is still logged, and the caller is not broken by it
- [ ] The bot token never reaches a log, a span, or an error message

## Stories

<!-- Maintained by `board.py new-story`. -->

## Notes

<!-- Appended by `board.py note`. -->
- **2026-09-13** — Inherits a case from FEAT-260912-8a0ab0: a capability skipped at start-up reaches nobody today. /health carries it, and nothing watches /health. A capability skipped three weeks ago looks exactly like one that was never installed.

## Links

- Requirements: [[FEAT-260912-84c828]]
