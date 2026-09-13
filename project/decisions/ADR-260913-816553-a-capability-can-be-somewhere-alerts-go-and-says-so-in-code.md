---
id: ADR-260913-816553
title: A capability can be somewhere alerts go, and says so in code
status: Accepted
created: 2026-09-13
feature: FEAT-260912-84c828
supersedes: ''
superseded_by: ''
---

# ADR-260913-816553 — A capability can be somewhere alerts go, and says so in code

## Status

Accepted. Amends two things that were written before this question came up:

- `CLAUDE.md` listed the registry's contract as `connector`, `tool`, `job`, `route`,
  `slack_action`, `on`. `alerts` joins it, and `slack_action` stays where it was — it is
  the *inbound* half (a button, a slash command), which this decision does not touch.
- The loader's requirements page says "registry exposes exactly `connector()`, `tool()`
  and `job()`". That was true of the loader, and its Non-goals said the next method would
  arrive with the feature that executes it. This is that feature, and this is that method.

## Context & problem

Harry's whole design is degradation: a feed dies and the page renders, a credential lapses
and one source falls back, a capability is half-written and the rest come up. Every one of
those is invisible when it works, which means every one is invisible when it does not. So
core has to be able to say "this went wrong" to a person.

It must do that **without knowing that Slack exists.** Core knowing a capability's name is
the one thing the whole folder layout exists to prevent — the moment it does, adding the
next capability costs a core edit and a core review.

So: how does a capability tell core "send failures here"?

The immediate forcing case is that a connector already has one registration.
`Registry._bind` allows exactly one per folder and refuses any kind that is not the
folder's own — a rule worth keeping, because it is what makes "one folder, one
implementation" true rather than aspirational. Alerting is not a fourth kind of
capability. It is something a connector can additionally be.

## Decision drivers

1. Core names no capability, ever.
2. A capability declares what it is; core does not infer it.
3. The contract a capability is written against should be readable in one place.
4. Whatever this is, a Harry with none of it must still start and still work.

## Considered options

### Option 1: A declaration field and a conventional method name

`alerts: true` in the connector's frontmatter, and core calls `client.send_alert(message)`
on whatever that folder registered.

**For:** No new registry method, so the contract stays at three. It fits "frontmatter is
what Harry does" — the declaration is already machine-readable and already read. A third
party changes one line of YAML rather than learning an API.

**Against:** The real contract becomes a method name that appears in no declaration, no
type and no documentation — a capability that spells it `notify` fails at the first
failure, which is the worst possible moment to find out. Nothing can check it at the gate
either: `scripts/check_capabilities.py` reads declarations, not Python. And the failure is
silent by construction, because the thing that would report it is the thing that is broken.

### Option 2: A fourth registry method, `registry.alerts(fn)`

The capability hands core a function. Core holds every function it was handed and calls
them all.

**For:** Explicit, typed, and visible in `harry.sdk` — the one place a capability author
looks. Wrong usage fails at registration, at start-up, on the machine of whoever wrote it,
rather than at the first failure three weeks later. The registry is already the contract;
this is the contract growing by one entry rather than a second, weaker contract appearing
beside it.

**Against:** One more method on the surface every capability is written against, and
methods are easy to add and hard to remove. It also blurs "kind" and "role" unless the
difference is stated — which is what the next section does.

## Decision outcome

**`registry.alerts(fn)`, and it is a role rather than a kind.**

The registry now carries two different things, and they are not the same shape:

| | What it is | How many per folder |
|---|---|---|
| `connector()`, `tool()`, `job()` | The folder's **kind** — what this capability *is* | Exactly one, and it must match the declaration |
| `alerts()` | A **role** — something this capability can additionally *do* | At most one, alongside the kind |

So the Slack connector registers its client with `connector()` and its sink with
`alerts()`, and neither refuses the other. `alerts()` does not go through `_bind` and does
not consume the folder's one implementation. Registering a sink twice from one folder is
still an error, because two sinks in one folder is a typo rather than an intention.

**Core holds the sinks and knows nothing else about them.** `harry.alerts.Alerts` is built
from the catalogue after loading — sinks are capabilities, and a capability has to load
before it can carry news — and `send()` calls every sink it has.

**Zero sinks is a working Harry.** With nothing registered, an alert is a WARNING in the
log and nothing else. A fresh checkout has no Slack credential, and alerting that fell over
without one would make the unconfigured case the broken case, which is backwards.

## Consequences

**Good:**

- Core reports faults and still names no capability. `git grep` proves it.
- A capability author sees the whole vocabulary in `harry.sdk`, and getting it wrong fails
  at start-up rather than at the first failure.
- The kind/role distinction gives later additions somewhere to go. A connector that can
  answer "is my credential still good?" is another role, not another kind.
- Nothing about this is Slack. A second sink — a file, an email, a different workspace —
  is another folder, with no core change.

**Bad:**

- **The registry has two concepts now**, and the difference has to be explained every time
  somebody adds to it. Without the table above, the fourth role and the fourth kind would
  be indistinguishable to whoever writes them.
- **The gate cannot check a role.** `scripts/check_capabilities.py` reads declarations, and
  a role is registered in Python. A connector that means to be a sink and never calls
  `alerts()` is silent — exactly the failure this decision is meant to prevent, one level
  up. What makes it survivable is that the alerting path has a real caller in the same
  feature, so it is exercised on every start-up rather than only when something breaks.
- **The thing that reports failures cannot report its own absence.** If the sink capability
  is the one that failed to load, that is in `/health` and the log and nowhere else. No
  arrangement of this fixes it; it is named here so nobody spends an afternoon rediscovering
  it.
