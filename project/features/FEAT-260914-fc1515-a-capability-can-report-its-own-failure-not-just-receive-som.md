---
id: FEAT-260914-fc1515
title: A capability can report its own failure, not just receive somebody else's
track: full
created: 2026-09-14
touches: [core/alerts, core/loader, core/main, core/registry, core/sdk, docs]
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

- [x] context.alert(message) reaches every registered sink with exactly what the capability wrote
- [x] A key makes a repeating fault report once a day, and no key means every time
- [x] Core namespaces the key to <kind>:<name>:<key>, so one capability cannot silence another's
- [x] With nothing registered it is a WARNING naming the capability that raised it — "connector tijd: the session has expired" — and nothing raises
- [x] Every sink failing still returns, is logged, and does not record the key — so the next occurrence tries again
- [x] An alert raised inside register() is logged, the capability still loads, a sink loaded later does not receive it, and the key is not recorded — so the same fault at call time is still sent
- [x] A secret the capability declared is [redacted] in the message before any sink sees it
- [x] A sink that alerts from its own failure path is refused re-entry rather than recursing
- [x] A capability importing harry.alerts is still skipped — context.alert is the only way in
- [x] docs/alerting.md, docs/capabilities.md and the three /new-* skills say how a capability reports a failure, and that log is for whoever reads the log while alert is for whoever does not — by inspection: prose in five markdown files, and no automation can judge whether the sentence is clear
- [x] A test pins Context's public names, so the twelfth addition is deliberate rather than incidental

## Stories

<!-- Maintained by `board.py new-story`. -->
- [x] [[STORY-260914-008826]] — A capability can say that something went wrong

## Notes

<!-- Appended by `board.py note`. -->
- **2026-09-14** — Blocks FEAT-260912-9c933f (De Tijd), FEAT-260912-e7ce2d (iCloud) and FEAT-260912-74f222 (the tablet). Each already carries a Slack criterion it cannot satisfy. Does not block FEAT-260912-5f7ec5 (weather): no credential to lapse, and an unavailable weather line is visibly different from a normal one on every page.
- **2026-09-14** — Reflection: pre-close-verifier returned REQUEST CHANGES — 2 Critical, 2 Important, 2 Suggestions, all acted on. Traceability 11/11 feature criteria and 15/15 story criteria; one marked by inspection (prose in five markdown files). Degraded paths exercised: no sinks, sinks not yet attached, every sink raising, one sink of two raising, a sink alerting about itself, a capability handed no alerts at all, and a second thread alerting while a sink blocks. Scope drift: none.

## Lessons Learned

### What worked

**The plan check paid for itself before a line was written.** The design as planned would
have eaten the alert the feature exists to send: alerting counts zero sinks as a delivery —
correctly, because in a Harry with no Slack the log line *is* the channel — and reusing that
during loading would have recorded the key against nobody, holding back the same fault at
06:30. Caught on the page, fixed in the design, and the tests that hold it go through
`load()` with a fixture connector that alerts inside its own `register()`.

**Writing the rejected option out properly.** Forwarding capability loggers to Slack needed
no contract change at all and could not be forgotten. It lost on a case already on disk —
the weather connector's WARNING for an unrecognised WMO code would have become a Slack
message every morning — and on keying, which a log line cannot carry. Neither reason was
obvious until the option was written down fairly.

### What to do differently

**The wiring line is the least-watched line in a feature.** `build_app()` passing `alerts`
into `load()` is one keyword, and deleting it left all 396 tests green while every
capability in production would have got nothing. **Every feature has one line where it
becomes real; ask which it is, and whether a test takes it.** Third time on this board that
a control was tested one layer beneath its only production caller.

**I ticked a criterion that was not implemented.** Three documents said the no-sink log line
names the capability. It did not, and I ticked all three. Reading a criterion and believing
it is not checking it — the check is finding the assertion, or writing it.

**A guard for one thread is not a guard for the process.** The re-entry guard was a plain
flag, which also drops an unrelated alert raised while a sink is blocking. The Slack sink
blocks for five seconds and the scheduler runs beside it, so that is an ordinary morning.
**Ask of any flag: who else runs while this is set?**

**A `pragma: no cover` justification can be false on the day it is written.** Mine said "the
loader always hands one over" while `load()` defaulted the parameter to `None`. The evidence
for skipping the fallback's test was the thing the fallback existed to catch.

### Patterns to reuse

- **`Alerts._attached`** — *attached with nothing* and *not attached yet* look the same and
  mean opposite things. Any object built empty and filled in later has this distinction, and
  the docstring at `src/harry/alerts.py` says why in a way that survives a refactor.
- **`threading.local()` for a re-entry guard** — re-entry is one thread calling itself;
  anything process-wide is a lock you did not mean to take.
- **`tests/fixtures/capabilities/connectors/complainer/`** — a connector that puts its own
  credential in its own alert, because that is what people write. Reuse for any path where a
  message leaves the machine.
- **`tests/test_sdk_boundary.py::test_the_context_surface_is_pinned`** — pins what is on an
  exported object, not just what is exported. `Context` had grown three times with nothing
  holding the line.

## Links

- Requirements: [[FEAT-260914-fc1515]]
- [[ADR-260914-c469a4]] — a capability reports a fault through its context, not through its log
- [[ADR-260913-816553]] — a capability can be somewhere alerts go
- Decision: [[ADR-260914-c469a4]] — A capability reports a fault through its context, not through its log

