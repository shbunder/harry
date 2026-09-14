---
id: FEAT-260914-fc1515
title: A capability can report its own failure, not just receive somebody else's
track: full
created: 2026-09-14
touches: [core/registry,core/loader,core/main,core/sdk]
stories: [STORY-260914-008826]
decisions: [ADR-260914-c469a4]
---

# FEAT-260914-fc1515 — A capability can report its own failure, not just receive somebody else's

## Summary

`registry.alerts(fn)` lets a capability *receive* alerts. Nothing lets one *raise* one — `Context` carries name, kind, folder, declaration, body, config, log and connectors, and no way to say that something went wrong. So the connector that knows its credential has lapsed cannot tell anybody.

Found while planning the weather connector, which does not need it: no credential, and "Weather unavailable" on the page is visibly different from a normal weather line, every morning. **Three later features do need it**, and each already carries the criterion: De Tijd ("an expired session puts one message in Slack naming De Tijd — one, not one per article"), iCloud, and the tablet ("a push that fails is retried once, and a second failure puts one message in Slack"). De Tijd's whole point is that alert.

## Acceptance criteria

<!-- One box per scenario. These are what the pre-close-verifier builds its
     traceability matrix from. -->

- [ ] context.alert(message) reaches every registered sink with exactly what the capability wrote
- [ ] A key makes a repeating fault report once a day, and no key means every time
- [ ] Core namespaces the key to <kind>:<name>:<key>, so one capability cannot silence another's
- [ ] With nothing registered it is a WARNING in the log naming the capability, and nothing raises
- [ ] Every sink failing still returns, is logged, and does not record the key — so the next occurrence tries again
- [ ] An alert raised inside register() is logged, the capability still loads, and a sink loaded later does not receive it
- [ ] A capability importing harry.alerts is still skipped — context.alert is the only way in
- [ ] docs/alerting.md and the three /new-* skills say how a capability reports a failure, and that log is for whoever reads the log while alert is for whoever does not

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260914-008826]] — A capability can say that something went wrong

## Notes

<!-- Appended by `board.py note`. -->
- **2026-09-14** — Blocks FEAT-260912-9c933f (De Tijd), FEAT-260912-e7ce2d (iCloud) and FEAT-260912-74f222 (the tablet). Each already carries a Slack criterion it cannot satisfy. Does not block FEAT-260912-5f7ec5 (weather): no credential to lapse, and an unavailable weather line is visibly different from a normal one on every page.

## Links

- Requirements: [[FEAT-260914-fc1515]]
- [[ADR-260914-c469a4]] — a capability reports a fault through its context, not through its log
- [[ADR-260913-816553]] — a capability can be somewhere alerts go
- Decision: [[ADR-260914-c469a4]] — A capability reports a fault through its context, not through its log

