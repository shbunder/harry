---
id: ADR-260913-c477cd
title: A capability may declare a connector optional, and render without it
status: Accepted
created: 2026-09-13
feature: FEAT-260912-0f2744
supersedes: ''
superseded_by: ''
---

# ADR-260913-c477cd — A capability may declare a connector optional, and render without it

## Status

Accepted. Amends [[ADR-260913-210e08]], which said `requires:` is the whole contract — what
decides whether a capability loads *and* what it is handed. It is now one of two.

## Context & problem

The morning page composes five sources: the weather, the calendar, two news feeds, De Tijd,
and the tablet it lands on. None of them exists yet, and they will arrive one at a time over
several features, each with its own credential and its own way of failing.

`requires:` refuses a capability whose connector did not load. That is right for a tool that
cannot work without one — `slack_post` without Slack is nothing. It is exactly wrong for the
digest: the page is **supposed** to render with a section missing. "A dead feed prints
unavailable and the rest renders" is the Degrading principle, and a digest that refuses to
load until all five sources exist has no way to express it.

The `/new-tool` template has carried `optional: [<connector>, …]` since the scaffolding, and
nothing has ever implemented it. This is the feature that needs it.

## Decision drivers

1. A section that cannot be built prints that it could not, and the rest of the page renders.
2. A capability should still be refused when something it genuinely cannot work without is
   missing. Degrading is not the same as tolerating everything.
3. What a capability can reach stays declared. No capability discovers connectors at run time.

## Considered options

### Option 1: Everything in `requires:`, and the capability degrades internally

The digest declares all five and checks each one itself.

**For:** One field, one rule, nothing new. The declaration still says everything it touches.

**Against:** The digest would not load at all until every source exists — so it could not be
built first, could not be seen working, and could not grow a section at a time. And the day
a credential lapses and its connector stops loading, the whole page disappears rather than
one section of it. That is the opposite of what Degrading asks for, and it is the failure the
page exists to survive.

### Option 2: `optional:` beside `requires:`

Two lists. `requires:` must have loaded or the capability is skipped; `optional:` is handed
over when it loaded and simply absent when it did not.

**For:** The declaration says which sources are load-bearing and which are sections. The
digest can ship before any source exists and gain a line as each lands. A capability that
needs something absolutely still says so, and is still refused.

**Against:** A second list to keep right, and a capability author now has to decide which
list each name goes in. The wrong choice is silent: a source in `optional:` that the page
actually cannot do without produces an empty page rather than a refusal.

## Decision outcome

**`optional:` beside `requires:`, and `context.connectors` carries both.**

```yaml
# slack_post: without Slack there is nothing to do at all
requires: [slack]

# the digest: every source is a section, and the tablet is where it goes if there is one
optional: [weather, icloud, news, tijd, remarkable]
```

```python
def register(registry: Registry, context: Context) -> None:
    slack = context.connectors['slack']  # guaranteed by `requires:`
    weather = context.connectors.get('weather')  # None when it did not load
```

The digest declares **everything** optional, including the tablet — a page with no tablet
is a page on disk, which is what `make digest-dry` has always been for. That turns the dry
run from a special mode into what happens naturally when there is nowhere to push.

**The test for which list a name goes in**, so it does not get re-argued: *if this connector
is missing, is there still something worth putting on the page?* If yes, `optional:`. If no,
`requires:`.

`context.connectors` stays one mapping rather than two, because at the point of use the
question is always "do I have this?" and a capability that reaches for a required connector
with `.get()` is not wrong, just cautious.

## Consequences

**Good:**

- The digest can be built before the sources it composes, and gain a section as each lands.
- A lapsed credential costs one section of the page rather than the page.
- Which sources are load-bearing is written down, where a reader looks.

**Bad:**

- **A second list, and a judgement about which one to use.** The test above is the whole
  defence, and it is a sentence rather than something the gate can check.
- **The wrong choice fails quietly.** A source in `optional:` that the page really cannot do
  without gives an empty page instead of a refusal. Nothing will catch that; it is the same
  shape as "not exposing a read path somebody would ask about", and it belongs in review.
- **`.get()` returning `None` is now a shape capability authors meet.** Every optional
  connector is an `if` in the capability. That is the cost of a page that degrades, paid
  where the degrading happens.
