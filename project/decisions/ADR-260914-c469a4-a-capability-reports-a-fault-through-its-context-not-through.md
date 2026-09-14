---
id: ADR-260914-c469a4
title: A capability reports a fault through its context, not through its log
status: Accepted
created: 2026-09-14
feature: FEAT-260914-fc1515
supersedes: ''
superseded_by: ''
---

# ADR-260914-c469a4 — A capability reports a fault through its context, not through its log

## Status

Accepted. Adds a method to `Context`, which [[ADR-260913-210e08]] and [[ADR-260913-c477cd]]
have each amended once already. The loader's requirements page carries the running list.

## Context & problem

`registry.alerts(fn)` lets a capability offer itself as somewhere alerts go. Nothing lets a
capability *raise* one. So the connector that knows its credential has lapsed — the exact
thing alerting exists for — cannot tell anybody.

Core alerts on a capability's behalf in one case: a capability that failed to *load*. That
covers "the Slack token is missing" and nothing else. It does not cover the feed that
started 404ing in March, the browser session that expired on Tuesday, or the tablet that
refused two pushes in a row. Each of those is a capability that loaded perfectly and then
stopped working.

Three features need it and each already carries the criterion:

- **De Tijd** — *"an expired session puts one message in Slack naming De Tijd — one, not one
  per article"*. That alert is the entire point of the feature.
- **iCloud** — an app password that stops working.
- **The tablet** — *"a push that fails is retried once, and a second failure puts one message
  in Slack"*.

And a fourth that does not, but should: **news**. A dead VRT feed is not visible the way a
dead weather source is. Weather has one line, and "Weather unavailable" where a forecast
belongs looks like nothing else. A missing feed just means fewer headlines, which looks
exactly like a slow news day. That is the case `.claude/rules/external-sources.md` was
written for.

## Decision drivers

1. A capability imports `harry.sdk` and nothing else.
2. A fault that repeats every five minutes reports once a day, like every other alert.
3. One capability must not be able to silence another's alerts.
4. Raising an alert must never break the caller — the same promise the sink side makes.

## Considered options

### Option 1: Forward the capability loggers to Slack

Every capability already has `context.log`, a logger named `harry.capability.<name>`. Attach
a handler that forwards `WARNING` and above to `Alerts`. No new contract at all.

**For:** Nothing to learn and nothing to add. Every capability can already do it, today,
including ones written before this decision. It also means a capability author cannot forget
to alert — they will log the failure anyway, because logging a failure is reflex.

**Against:** It cannot distinguish "somebody should be told" from "this is a note for
whoever is reading the log". The weather connector logs a `WARNING` when Open-Meteo returns
a WMO code it has no word for — true, worth recording, and not worth a Slack message. Under
this option it becomes one, every morning, until somebody edits the table.

There is also no key. The whole suppression design is keyed, and a log line has nothing to
key on but its text — so a message with a timestamp or a URL in it would defeat the
once-a-day rule and report every five minutes. Fixing that means inventing a convention
inside log messages, which is a contract with no type and no gate.

## Option 2: `context.alert(message, key=None)`

An explicit call, beside `context.log`.

**For:** Saying something is worth waking somebody for is a decision, and this makes it one.
It carries a key, so the existing once-a-day suppression works unchanged. It is visible in
`harry.sdk`, which is where a capability author looks, and getting it wrong fails at
registration rather than at the first failure.

**Against:** A tenth thing on `Context`, which was deliberately small. And it can be
forgotten in a way option 1 cannot: a capability that logs its failure and does not alert is
silent, and nothing will catch that — it is the same shape as "not exposing a read path
somebody would ask about", and it belongs in review.

## Decision outcome

**`context.alert(message, key=None)`.**

```python
def fetch(self):
    try:
        ...
    except httpx.HTTPError as error:
        self._context.alert(f'{self.source} has stopped answering: {error}', key='feed-down')
        return []
```

**The key is namespaced by core, not by the caller.** What the capability passes is scoped
to `<kind>:<name>:<key>`, so one capability cannot suppress another's alerts by guessing a
key — and does not have to think about collisions to get dedup right.

**An alert raised before the sinks are known goes to the log.** `Alerts` is built empty
before loading and its sinks are attached after, because a sink is itself a capability and
has to load first. A capability that alerts during its own `register()` is therefore talking
to a logger. That is rare — nearly every capability alert happens at call time, hours later —
and it is the same behaviour as a Harry with no Slack configured, which is a working Harry.

**Raising an alert never breaks the caller**, exactly as a sink that raises never breaks the
reporter. The whole path is best effort in both directions, because the alternative is that
the code trying to report a problem is taken down by the reporting.

## Consequences

**Good:**

- The three features that named this alert in their criteria can satisfy them.
- A fault that repeats reports once a day, because it goes through the same keyed path as
  everything else.
- Deciding to tell somebody stays a decision. A log line and an alert mean different things
  and now look different.

**Bad:**

- **A tenth name on `Context`.** Each addition makes the next easier to argue for, and the
  test that asserts every field is checked is the only thing holding that line.
- **It can be forgotten, silently.** Option 1 could not be. A capability that catches an
  exception, logs it and returns a default is invisible, and nothing in the gate can tell
  that apart from one that had nothing to report. It belongs on the review checklist for
  every connector, and `/new-connector` already asks "what reaches Slack, and how often?" —
  that question now has somewhere to point.
- **Two ways to say something happened**, and a capability author has to choose. The line:
  **`log` is for whoever is reading the log; `alert` is for whoever is not.**
