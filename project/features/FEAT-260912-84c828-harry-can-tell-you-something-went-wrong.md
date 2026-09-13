---
id: FEAT-260912-84c828
title: Harry can tell you something went wrong
track: full
created: 2026-09-12
touches: [connectors/slack, core/alerts, core/main, core/registry, core/loader]
stories: [STORY-260913-1f320c, STORY-260913-e6f9b4, STORY-260913-bb45b7]
decisions: [ADR-260912-399f07, ADR-260912-895441]
---

# FEAT-260912-84c828 — Harry can tell you something went wrong

## Summary

One-way messages into Slack, which every other feature depends on. Alerting is a core principle and it cannot wait for the Slack loop in a later phase: a degraded source, a lapsed credential and a failed push all need somewhere to arrive from the first morning.

## Acceptance criteria

<!-- One box per scenario. These are what the pre-close-verifier builds its
     traceability matrix from. -->

- [ ] An alert reaches Slack as one chat.postMessage carrying the channel and the caller's text, with nothing added
- [ ] Core raises an alert without naming any capability, and a connector that registered itself receives it
- [ ] With nothing registered, an alert is a WARNING in the log and nothing raises
- [ ] An alert carrying a key is not sent again within 24 hours; one with no key is always sent
- [ ] Slack being unreachable or answering 500 costs the message, is logged, and does not break the caller
- [ ] A capability skipped at start-up produces one alert naming it, its kind and the reason; one that loaded produces none
- [ ] The bot token appears in no log line, no alert and no /health field, and the committed .env leaves it empty

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260913-1f320c]] — An alert reaches Slack, and nothing about it names Slack in core
- [ ] [[STORY-260913-e6f9b4]] — The same fault does not tell you twice today
- [ ] [[STORY-260913-bb45b7]] — A capability that did not load reaches a person

## Notes

<!-- Appended by `board.py note`. -->
- **2026-09-13** — Inherits a case from FEAT-260912-8a0ab0: a capability skipped at start-up reaches nobody today. /health carries it, and nothing watches /health. A capability skipped three weeks ago looks exactly like one that was never installed.

## Links

- Requirements: [[FEAT-260912-84c828]]
- [[ADR-260912-399f07]] — capabilities are folders under `.harry/`
- [[ADR-260912-895441]] — a capability's settings live in its own folder
