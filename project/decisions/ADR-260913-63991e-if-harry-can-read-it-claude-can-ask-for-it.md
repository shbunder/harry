---
id: ADR-260913-63991e
title: If Harry can read it, Claude can ask for it
status: Superseded
created: 2026-09-13
feature: ''
supersedes: ''
superseded_by: ADR-260913-18a8ae
---

# ADR-260913-63991e — If Harry can read it, Claude can ask for it

## Status

Superseded by [[ADR-260913-18a8ae]]

## Context & problem

The morning page was the first thing designed, and the design drifted toward serving it.
A connector existed so a job could use it: iCloud was reached because the digest needed an
agenda, and the tool surface was going to be the handful of verbs the digest called —
`list_candidates`, `fetch_articles`, `build_digest`.

Follow that and Harry ends up holding an iCloud credential, a working CalDAV client and
today's events, while **"what's on my calendar?"** in an ordinary Claude session gets
nothing. The data is a round trip away from the model and locked behind a job that runs
once a day at 06:30.

That is backwards. Holding the credentials and reaching the services is the expensive,
fiddly half; the morning page is one consumer of it.

## Decision drivers

1. Harry's value is reach. Anything reached and not exposed is reach thrown away.
2. Ad-hoc questions are most of the use, and none of them were designed for.
3. Whatever makes a large tool surface affordable, because this makes it larger.

## Considered options

### Option 1: Expose what a job needs

Tools are the verbs the jobs call. A connector's data reaches Claude through whatever
composite the job happens to require.

**For:** The smallest possible surface, which is what
[ADR-260912-b22e46](ADR-260912-b22e46-tools-are-one-verb-each-namespaced-by-owner-and-lean-on-mcp-.md)
argues for — fewer, higher-leverage tools, less roster to carry on every request.

**Against:** It answers exactly the questions somebody anticipated. "What's on my calendar",
"did anything land on the tablet", "what did De Tijd run about the budget" are all one
credential and one client away, and all impossible. And the composites are shaped for a job:
`list_candidates` returns weather, agenda and forty headlines because the digest wants one
round trip. Asking it what is on your calendar means asking for all of that.

### Option 2: Every read path a connector has becomes a tool

A connector exposes what it can reach. Jobs then compose those tools rather than reaching
past them.

**For:** Harry becomes useful the moment a connector exists, without waiting for a job to
want it. Each tool is scoped to one question, so an ad-hoc ask is cheap. And it inverts the
dependency correctly: a job is one consumer of a connector, not its reason for existing.

**Against:** Many more tools. That is only affordable because most of them defer — without
tool search this would put every connector's roster in front of the model on every request.

## Decision outcome

**If Harry can read it, Claude can ask for it.** Every read path a connector has becomes an
MCP tool unless there is a stated reason it should not — and "no job needs it yet" is not
one.

So `icloud_list_events` exists because Harry can reach the calendar, not because the digest
wants an agenda. The digest then calls it like anything else.

This does not contradict the consolidation rule; it is that rule applied to a second
consumer. `digest_list_candidates` still exists and still returns weather, agenda and
headlines in one call, because a job running unattended does not need to see what passed
between three round trips. An ad-hoc question does, so it gets the narrow tool. The two
serve different callers and neither is redundant.

**What stays internal** needs saying out loud, or the rule is unbounded:

- a health check — the machinery Harry uses to notice a credential lapsed
- anything whose only sensible caller is core, like lifecycle hooks
- a write whose consequences a person should approve first, until it has an annotation
  saying so

Everything else is exposed, and **deferred by default**. `always_load: true` stays reserved
for the two or three a session reaches for nearly every time. Deferral is what makes this
affordable, so this decision and the deferral decision hold each other up.

## Consequences

**Good:**

- A connector is useful on the day it lands, not on the day a job wants it.
- The dependency points the right way: jobs consume connectors, and a connector no longer
  has to guess which job will need what.
- Ad-hoc asks stop being an afterthought, and they are most of what Harry will actually be
  asked.
- A third party's connector is immediately reachable from any session, which is what makes
  "drop in a folder" worth anything.

**Bad:**

- **The tool surface grows with every connector**, and the roster is sent on every request.
  Deferral covers it, and the moment it stops covering it is a measurement nobody is taking
  yet — worth watching once there are thirty tools rather than five.
- **More surface is more to describe well.** Each tool's body is what the model reads to
  choose, and a connector shipping six thin tools with six vague descriptions is worse than
  two good ones. The rule is expose generously; the obligation is describe carefully.
- **The internal/exposed line is a judgement call**, and the three exceptions above are
  where it will be argued. A health check that somebody decides is "useful to ask about" is
  the first step back toward exposing everything including the machinery.
- Read paths are cheap to expose and writes are not. This decision is about reads; a write
  reaching the tablet or Slack still needs its annotations right before it is offered
  casually.
