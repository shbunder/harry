---
id: FEAT-260914-fc1515
title: A capability can report its own failure, not just receive somebody else's
track: full
created: 2026-09-14
touches: [core/registry,core/loader,core/main,core/sdk]
stories: []
decisions: []
---

# FEAT-260914-fc1515 — A capability can report its own failure, not just receive somebody else's

## Summary

`registry.alerts(fn)` lets a capability *receive* alerts. Nothing lets one *raise* one — `Context` carries name, kind, folder, declaration, body, config, log and connectors, and no way to say that something went wrong. So the connector that knows its credential has lapsed cannot tell anybody.

Found while planning the weather connector, which does not need it: no credential, and "Weather unavailable" on the page is visibly different from a normal weather line, every morning. **Three later features do need it**, and each already carries the criterion: De Tijd ("an expired session puts one message in Slack naming De Tijd — one, not one per article"), iCloud, and the tablet ("a push that fails is retried once, and a second failure puts one message in Slack"). De Tijd's whole point is that alert.

## Acceptance criteria

<!-- One box per scenario. These are what the pre-close-verifier builds its
     traceability matrix from. -->

- [ ] A capability can raise an alert from its own code, without importing anything but harry.sdk
- [ ] The alert goes wherever alerts go, and carries a key so a fault repeating every five minutes reports once a day
- [ ] A capability that raises one before any sink registered still works — the alert is logged
- [ ] Raising an alert never breaks the caller, the way the sink side already does not
- [ ] A capability cannot raise one claiming to be another capability
- [ ] docs/alerting.md and the three /new-* skills say how a capability reports a failure

## Stories

<!-- Maintained by `board.py new-story`. -->

## Notes

<!-- Appended by `board.py note`. -->
- **2026-09-14** — Blocks FEAT-260912-9c933f (De Tijd), FEAT-260912-e7ce2d (iCloud) and FEAT-260912-74f222 (the tablet). Each already carries a Slack criterion it cannot satisfy. Does not block FEAT-260912-5f7ec5 (weather): no credential to lapse, and an unavailable weather line is visibly different from a normal one on every page.

## Links

- Requirements: [[FEAT-260914-fc1515]]
