---
id: ADR-260916-d4acc6
title: A connector can name another connector, and connectors load in that order
status: Accepted
created: 2026-09-16
feature: FEAT-260912-9c933f
supersedes: ''
superseded_by: ''
---

# ADR-260916-d4acc6 — A connector can name another connector, and connectors load in that order

## Status

Accepted

Drives [[FEAT-260912-9c933f]].

## Context & problem

The news connector fetches every article page. For De Tijd it has to hand the page to a
connector that holds a logged-in browser — and it may not import that connector, because two
folders that import each other cannot be swapped.

Tools and jobs already solve this. They declare `requires:` or `optional:`, and the loader
hands them the connectors they named in `context.connectors`. **Connectors cannot.** Three
things stop it:

- The loader loads connectors in name order. `news` sorts before `tijd`, so when news
  registers, tijd has not loaded, and news would be handed nothing.
- `scripts/check_capabilities.py` does not check `requires:` or `optional:` on a connector.
- Nothing refuses two connectors that need each other.

Today a connector that named a later connector would load, look healthy, and be handed
nothing, every morning. Nothing would say so.

## Decision drivers

- **Modular** — a capability never imports another one, and core never learns a name
- The order things load in is written down, not an accident of spelling
- One broken credential should cost as little as possible

## Considered options

### Option 1: Put De Tijd's browser and login inside the news connector

**For:** no contract change and no core change.
**Against:** news becomes a credential holder that expires, with a password in its runbook. The
owner asked for the credential to belong to its own connector. A second paywalled site would
pile into the same folder.

### Option 2: The tijd connector plugs itself into news

tijd declares `requires: [news]` and calls `news.add_reader(self)` when it registers.

**For:** news names nothing.
**Against:** it works only because "news" sorts before "tijd". Rename either and it breaks,
loudly at best. One connector changing another's object at start-up is action at a distance.

### Option 3: Every caller of `news.article` passes the reader in

The tools already load after every connector, so they could declare `optional: [tijd]` and
pass it through.

**For:** no loader change.
**Against:** two call sites today, `news_article` and `digest_build`. The next caller that
forgets gets 403s on De Tijd, and nothing says why.

### Option 4: Connectors declare `requires:` and `optional:`, and load in that order

The same two lists tools and jobs use. The loader loads a connector after every connector it
names. `make lint` refuses a name that does not exist, and a loop.

**For:** no new concept — the lists already exist and mean the same thing. The load order
becomes a declared fact.
**Against:** a change to the loader and the validator, both core. A loop has to be handled
somewhere.

## Decision outcome

**Option 4.** A connector may declare `requires:` and `optional:`, naming other connectors, and
connectors load after the connectors they name. **Modular** drove it.

News declares `optional: [tijd]` and asks `context.connectors.get('tijd')` — the shape every
tool already uses. The test from [[ADR-260913-c477cd]] decides which list: if tijd is missing,
is there still something worth doing? News still has every other feed, so tijd is optional.

A loop is refused by `make lint`. If one reaches a running Harry anyway, from a capabilities
directory the lint never saw, the connectors in it load in name order, as they do today.
Nothing crashes, and the connector loaded first is handed nothing for the other.

## Consequences

**Good:**

- News reads De Tijd through a connector it names, without importing it.
- A connector naming a later connector is handed it, rather than silently handed nothing.

**Bad:**

- **Connectors no longer load in plain name order.** The start-up log reads in dependency
  order, which is less obvious at a glance.
- **`requires:` on a connector can cost two connectors.** If a required connector is skipped,
  so is the one that needs it. That is why news declares tijd `optional:` — one lapsed login
  must not take every headline down with it.
- **A loop from an unvalidated root degrades quietly.** The first connector is handed nothing,
  and only the lint would have said so.
