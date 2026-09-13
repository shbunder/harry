---
id: ADR-260913-18a8ae
title: A tool exists because someone would ask for it
status: Accepted
created: 2026-09-13
feature: ''
supersedes: ADR-260913-63991e
superseded_by: ''
---

# ADR-260913-18a8ae — A tool exists because someone would ask for it

## Status

Accepted. Supersedes
[ADR-260913-63991e](ADR-260913-63991e-if-harry-can-read-it-claude-can-ask-for-it.md),
which made exposure automatic. It was written the same day and lasted about an hour.

## Context & problem

Two failure modes, and the first decision fixed one by walking into the other.

**Data trapped behind a job.** The original design let a connector exist only to serve a
job, so Harry would hold an iCloud credential, a working CalDAV client and today's events
while *"what's on my calendar?"* returned nothing. That is reach thrown away, and it is
what ADR-260913-63991e was right to reject.

**A surface shaped by somebody else's API.** Its fix was to expose every read path
automatically. But a connector's read paths are the shape of the *service*, not the shape
of anything a person wants. CalDAV can list calendars, walk collections, fetch by UID and
run raw REPORT queries. Exposing all of that is not generosity, it is handing the model a
protocol and hoping.

The tool roster is sent on every request and the model picks from names and descriptions
alone. Every tool is rent, and two tools that read alike make it pick wrong — and that
failure looks like a bug in whichever one it chose. Deferral lowers the rent; it does not
make a badly shaped surface good.

So the question is not *how much* to expose. It is **what the deciding test should be**,
because the previous two answers were "whatever a job needs" and "whatever the API has",
and neither of those is about the person asking.

## Decision drivers

1. A surface somebody designed, rather than one that accumulated.
2. Not trapping data behind a job — the original failure, which still has to stay fixed.
3. Anthropic's measured guidance: fewer, higher-leverage tools beat many granular ones.
4. Keeping the un-exposed visible, so a gap is a decision rather than an oversight.

## Considered options

### Option 1: Expose every read path automatically (the superseded decision)

**For:** Nothing is ever trapped. No per-tool argument. A connector is useful the day it
lands.

**Against:** The surface is shaped by whichever API the connector wraps. It grows without
anybody choosing, each addition is rent on every request, and the descriptions get thinner
as the count rises — which is the one thing that actually decides whether the model picks
correctly.

### Option 2: Expose only what a job needs

**For:** The smallest possible surface, every tool demonstrably used.

**Against:** The original failure, restored. It answers exactly the questions somebody
anticipated, and ad-hoc asks are most of what Harry will actually get.

### Option 3: Expose deliberately, against a stated test

Each tool is a choice, listed in the connector's `provides:`, and the test is whether a
person would plausibly ask for it.

**For:** The surface is designed rather than derived. It can still cover everything worth
asking, because the test is about the asker, not about the API or the job. And the choice
is written down where the next person can disagree with it.

**Against:** It is a judgement call, so it can be got wrong in both directions — and a
judgement call cannot be enforced by a validator the way a naming rule can.

## Decision outcome

**A tool exists because someone would ask for it.** Not because a connector can do it, and
not because a job needs it.

Exposure is an explicit choice, per tool, listed in the connector's `provides:`. A read
path a connector has and does not expose is normal and needs no justification. A read path
somebody would plausibly ask about and that is *not* exposed is the bug.

**Shape is part of the choice, not an afterthought.** `icloud_list_events(day)` is a tool;
`icloud_caldav_report(xml)` is a protocol with a tool's name on it. The question is never
only whether to expose something but what shape it should take for the person asking — what
it returns, what it leaves out, and what it is called.

**A job composes tools; it does not reach past them.** That part of the superseded decision
stands and is the reason the first failure mode does not come back: since the digest can
only call tools, anything it needs is exposed by construction. What changes is that this is
no longer the *only* reason to expose something.

The three things that stay internal are unchanged: a health check, anything only core would
call, and a write whose consequences a person should approve first.

## Consequences

**Good:**

- The surface is designed. Every tool on it is there because somebody decided it should be,
  and `provides:` is where that decision is visible and arguable.
- Fewer, better-described tools. Description quality is the highest-leverage thing on this
  surface and it is the first thing to suffer when the count grows unchosen.
- You control what the agent sees, which is the actual product decision. What Harry can
  reach and what Claude is offered are now two different lists on purpose.

**Bad:**

- **It is a judgement call, and the validator cannot check it.** Namespacing, annotations
  and a missing description all fail at the gate. "Would somebody ask for this?" fails
  nowhere, so it fails in review or not at all.
- **The trapped-data failure can come back quietly.** Nothing errors when a useful read
  path goes unexposed — it just is not there, and nobody notices until they ask and get
  nothing. The mitigation is cheap and should be built: have `/new-connector` write down
  every read path the connector has, with the exposed ones marked, so the gap is legible
  rather than invisible. Without that, this decision degrades back into option 2 by
  inattention.
- **Two decisions in one day on the same question.** The record now has a superseded ADR
  that was correct about the problem and wrong about the fix. That is worth leaving intact
  rather than editing away: the failure it names is still the one this has to keep avoiding.
