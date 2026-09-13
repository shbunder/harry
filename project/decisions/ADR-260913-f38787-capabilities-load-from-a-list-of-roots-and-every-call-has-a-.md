---
id: ADR-260913-f38787
title: Capabilities load from a list of roots, and every call has a principal
status: Accepted
created: 2026-09-13
feature: ''
supersedes: ''
superseded_by: ''
---

# ADR-260913-f38787 — Capabilities load from a list of roots, and every call has a principal

## Status

Accepted. Two seams built now for things not being built now.

## Context & problem

Two futures are likely enough to design for and expensive enough to retrofit.

**Somebody else runs their own Harry.** Today this repository is both the package and the
instance. That is fine while there is one of each. The moment a second person wants one,
they should get a *directory* — their own capabilities, their own credentials, their own
data — rather than a fork of somebody else's repository. Home Assistant is the same shape:
`pip install homeassistant`, then a config directory holding `custom_components/`.

**The NUC serves more than one person.** Harry sits on a household machine. "What's on my
calendar" has to mean a different calendar depending on who asked, and the morning page is
one person's morning. Every credentialled connector is currently singular: one iCloud
account, one tablet, one Slack channel.

The retrofit costs are wildly different from the build costs. Adding a second root to a
loader that already takes a list is nothing. Adding it to a loader hard-wired to one
directory touches discovery, config, tests and every path in between. And identity is
worse: if tool calls are anonymous, giving them a caller later changes every tool
signature, every store row and the auth layer at once.

So the question is not whether to build multi-user — it is which seams have to exist before
Phase 1 writes code against their absence.

## Decision drivers

1. Only build what is expensive to retrofit. Everything else waits for a real second user.
2. Do not let Phase 1 write code that assumes one user or one directory.
3. Other people's credentials must never land in the repository.
4. Keep the single-user path exactly as simple as it is today.

## Considered options

### Option 1: Build it when somebody asks

**For:** No speculative work. The system stays as small as its actual requirements.

**Against:** Both retrofits are the expensive kind. Identity in particular cannot be added
cheaply: it is a parameter on every tool, a column on every row, and a decision in the auth
layer, and by then there is code to change rather than code to write.

### Option 2: Build multi-user now

Accounts, per-user credentials, per-user jobs, an invite flow.

**For:** Done properly, once.

**Against:** Weeks of work for one user, and every bit of it designed against guesses about
how a second person would actually use it. The morning page does not exist yet.

### Option 3: Build the seams, not the feature

A loader that takes a list of roots with one entry. An identity that resolves to one
principal. Config that takes an optional principal and ignores it.

**For:** Hours, not weeks. Nothing in Phase 1 can then assume singularity, because the
plural shape is already the shape. The expensive half of both retrofits disappears.

**Against:** Machinery with one caller looks like over-engineering until the second one
arrives, and if it never arrives it was waste. It also adds a concept — the principal —
that everything has to carry for no present benefit.

## Decision outcome

**Capabilities load from a list of roots**, in order, later winning on name collision:

1. **bundled** — shipped inside the package
2. **the instance** — `.harry/` in the working directory
3. **extra** — `$HARRY_CAPABILITIES_DIR`, when set

Later-wins is the swap mechanism, and it is the whole point: an instance drops its own
`connectors/icloud/` next to a bundled one and takes over, with no fork and no patch. Entry
points become a fourth root when there is something to install; the list makes that
additive.

**Every call has a principal.** `Principal(id, name)` resolves from the bearer token. Today
exactly one token resolves, to `owner`, and nothing behaves differently — but the parameter
exists, so no tool, no store row and no job is written as though there were only ever one
caller.

**A capability's settings gain a per-principal layer**, above the instance's own:

1. `HARRY_<NAME>_<KEY>` in the environment
2. `<data>/users/<principal>/connectors/<name>.env` — this person's
3. `.harry/connectors/<name>/.env.local` — the instance's
4. `.harry/connectors/<name>/.env` — committed, generated
5. the declared default

Layer 2 lives in the **data volume, never the repository**. Other people's credentials are
not a thing to be committed, and the boundary is physical rather than a rule.

**What is deliberately not built:** accounts, an invite flow, per-user jobs, per-user
channels, a second token. Those wait for a second person who actually wants one, and they
are additive once these three seams exist.

## Consequences

**Good:**

- Somebody else's Harry becomes a directory rather than a fork, and swapping a bundled
  connector is dropping a folder with the same name.
- No Phase 1 code can assume one user, because the plural shape is already there.
- Other people's credentials have somewhere to go that is not the repository, decided
  before anyone needed it rather than after.

**Bad:**

- **A concept with one instance.** `Principal` will be threaded through code that does
  nothing with it for months. That reads as ceremony, and the argument for it is entirely
  about a future that may not arrive.
- **Five layers of configuration precedence**, where three would do today. Each is
  defensible and the stack as a whole is harder to hold in your head than it was this
  morning. `tests/test_capability_config.py` is the mitigation and has to stay exhaustive,
  because nobody will reason this out from the code.
- **The bundled root does not exist yet**, so the list has one real entry and a
  speculative one. That is honest about what has been proved: the mechanism is tested, the
  arrangement is not.
- **Identity is a seam, not a security boundary.** One token resolving to one principal is
  not authentication, and it must not be mistaken for it. A second principal needs a real
  answer about token issue, rotation and scope — and that answer is not in this decision.
