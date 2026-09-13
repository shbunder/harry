---
id: ADR-260913-210e08
title: A capability is handed the connectors it declared, and imports none of them
status: Accepted
created: 2026-09-13
feature: FEAT-260913-007e6f
supersedes: ''
superseded_by: ''
---

# ADR-260913-210e08 — A capability is handed the connectors it declared, and imports none of them

## Status

Accepted. Adds one field to `Context`, which the loader's requirements page pinned at eight
("context carries name, kind, folder, declaration, body, config, config_for() and log").
That page is amended by this one.

## Context & problem

A tool declares what it needs:

```yaml
requires: [slack]
```

The loader checks it. A tool whose connector did not load is skipped, with a reason — that
much works and is tested. **But nothing ever hands the connector over.** `requires:` is half
a contract: it refuses the tool when the connector is missing and gives it nothing when the
connector is there.

Every real tool hits this on its first line. `slack_post` needs the Slack client.
`digest_build` will need remarkable, news and iCloud at once. Until now the only tools in
the repository were fixtures that return a dictionary, so nothing had noticed.

The rule that makes it a question at all: **a capability never imports another capability.**
Two folders that import each other are two folders that cannot be swapped, and swapping is
what the whole layout is for.

## Decision drivers

1. A capability imports `harry.sdk` and nothing else. That does not bend.
2. What a capability needs should be declared, not discovered at run time.
3. Core names no capability.
4. A capability author should not have to ask how the wiring works.

## Considered options

### Option 1: A lookup on the registry

`registry.connector_named('slack')`, or a `Catalogue` handed to every capability.

**For:** No change to `Context`. It is also the most flexible — a capability could reach
anything, including things it never declared.

**Against:** That flexibility is the problem. A capability that can reach any connector does
not have to declare what it needs, so `requires:` becomes decoration and the loader can no
longer refuse a tool whose connector is missing — the failure moves from start-up, where
`/health` names it, to the first call at 06:30. It also hands every capability the whole
catalogue, which is a much larger surface than the two lines of it anybody wanted.

### Option 2: The loader hands over what the declaration asked for

`context.connectors` is a mapping of name to whatever that connector registered, containing
exactly what `requires:` listed.

**For:** The declaration becomes the whole contract: what is in `requires:` is what arrives,
and a tool cannot reach anything it did not ask for. The loader already resolves the list to
refuse a tool whose connector is missing, so this is the same resolution used rather than
thrown away. A capability author writes one line and never thinks about wiring.

**Against:** A ninth field on `Context`, which the loader's page pinned at eight — so that
page needs amending, which is what this record is for. It also means a capability gets its
connectors at registration time, so a connector replaced later in the process would not be
picked up. Nothing replaces a connector at run time; Harry restarts.

## Decision outcome

**`context.connectors`, holding exactly what `requires:` named.**

```python
def register(registry: Registry, context: Context) -> None:
    slack = context.connectors['slack']

    @registry.tool
    def slack_post(channel: str, text: str) -> dict:
        slack.send(text, channel=channel)
```

Three consequences worth stating:

- **`requires:` is now the whole contract.** It decides whether the capability loads *and*
  what it can reach. A tool that wants another connector adds a name to a list, and the
  loader refuses it at start-up if that connector is not there.
- **A connector that registered nothing means the capability does not load at all.** This
  is where the decision moved while it was being built. The first version left such a
  connector out of the mapping and relied on the capability's own `KeyError` becoming the
  skip — which is a `KeyError` in `/health`, in front of somebody who is not debugging. The
  loader refuses it up front instead, with `needs <name>, which registered nothing to use`,
  so the mapping is never built rather than built incomplete.
- **Reaching for a connector that was never declared is refused in words too.** The mapping
  is a `dict` subclass whose `__missing__` says what was reached for and what was declared,
  for the same reason.
- **Order is already right.** The loader loads connectors before tools and jobs, which it
  does so that `requires:` can be refused. The same ordering is what makes this possible.

## Consequences

**Good:**

- `requires:` stops being half a contract.
- A capability still imports only `harry.sdk`, and still cannot reach a capability it did
  not declare.
- Core learns no name: the loader copies entries out of a mapping the declaration chose.

**Bad:**

- **A ninth field on the contract every capability is written against.** `Context` was
  deliberately small, and each addition makes the next one easier to argue for. The test in
  `tests/test_loader.py` that asserts every field is checked is what keeps that honest.
- **Connectors are bound at registration.** A capability that holds its connector for the
  life of the process cannot be handed a replacement. Harry restarts to pick up a change —
  the same answer the loader gives for everything else — but a future hot-reload feature
  would have to revisit this.
- **A capability can hold a connector past the point the connector is useful.** Nothing
  stops a tool caching a client whose credential has since lapsed. That is the connector's
  problem to report, and `expires:` is where it gets reported from.
