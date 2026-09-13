---
id: ADR-260912-895441
title: A capability's settings live in its own folder, in its own .env pair
status: Accepted
created: 2026-09-12
feature: ''
supersedes: ''
superseded_by: ''
---

# ADR-260912-895441 — A capability's settings live in its own folder, in its own .env pair

## Status

Accepted. Extends
[ADR-260912-399f07](ADR-260912-399f07-capabilities-are-folders-under-harry-connectors-tools-and-jo.md),
which made a capability a folder, by putting the last thing that was still outside it back
inside.

## Context & problem

A capability was made self-contained in stages. Its declaration, its code, its runbook and
its tools all moved into its folder. Its **settings** did not: they were declared in the
frontmatter but their values still lived in the repository-root `.env` pair, reached
through a derived key like `HARRY_ICLOUD_APP_PASSWORD`.

That left the promise half-kept. A third party dropping in a connector still had to edit a
file at the root of somebody else's repository to make it work, and the root `.env` still
accumulated every key of every capability anybody had ever added — the exact list that was
supposed to stop being everybody's business.

The derived prefix existed to stop two capabilities colliding on a name like `api_key`.
That problem only exists in a shared namespace.

## Decision drivers

1. A capability should be one folder, with nothing of it anywhere else.
2. Adding a capability should never edit a file the capability does not own.
3. Keep the two-file layering that already works: committed documentation, local secrets.
4. Keep a container able to inject configuration, which is flat by nature.

## Considered options

### Option 1: Keep the root pair, with derived keys

`HARRY_<IMPLEMENTATION>_<SETTING>` in the repository-root `.env` and `.env.local`.

**For:** One place to look for every value. One pair of files to back up. Flat keys map
directly onto how containers and secret managers inject configuration.

**Against:** The root file grows without bound and belongs to nobody. A capability is not
self-contained, so a third party cannot add one without editing the root. And the prefix
is pure ceremony — it exists only to avoid collisions in a namespace that did not have to
be shared.

### Option 2: A `.env` pair inside each capability folder

`.harry/connectors/icloud/.env` committed, `.harry/connectors/icloud/.env.local` ignored.

**For:** The folder is the namespace, so keys are bare — `APP_PASSWORD`, not
`HARRY_ICLOUD_APP_PASSWORD`. A capability is genuinely one directory. The root pair
shrinks to the six settings core actually owns. And the layering people already understand
— committed template, local overrides — applies unchanged one level down.

**Against:** More files. Harry has to find and read them rather than reading one pair at
start-up. And a container still injects flat environment variables, so the derived key
cannot disappear entirely — it survives as the override name.

## Decision outcome

**A capability's settings live in its own folder, in its own `.env` pair**, with the same
meaning the root pair has:

```
.harry/connectors/icloud/
├── CONNECTOR.md      the schema, in `config:`
├── .env              committed — every key, its description, its default. Secrets empty.
├── .env.local        gitignored — this machine's secrets and overrides
└── icloud.py
```

**Keys are bare.** The folder is the namespace, so `APP_PASSWORD` cannot collide with
another connector's `APP_PASSWORD`. The prefix was only ever there to fake a namespace
that now exists for real.

Precedence for one setting, highest first — the same shape as the root pair, one level
down:

1. `HARRY_<IMPLEMENTATION>_<SETTING>` in the real environment — how a container injects
2. `.env.local` in the capability's folder
3. `.env` in the capability's folder
4. the `default:` in its declaration

**The committed `.env` is generated, not hand-written.** `make env-template` writes it from
the `config:` block, so the description beside each key cannot drift from the schema
Harry validates against. You edit `.env.local`; you never edit `.env`.

**`requires_env:` is retired.** It listed raw environment variable names, which is a second
copy of what `config:` already says with `required: true`. One of the two had to go, and
the schema is the one that carries types and descriptions.

## Consequences

**Good:**

- A capability is finally one directory. Copying that directory to another Harry is the
  whole of installing it, and nothing at the root has to be touched.
- The root `.env` drops to the six settings core owns: port, data directory, API token,
  public URL, capabilities directory, log level.
- The runbook, the credential's expiry, its schema and its value now sit within one
  `ls` of each other, which is the state somebody wants at 07:00 when the login has lapsed.
- Bare keys make a capability's `.env` readable on its own. `APP_PASSWORD=` beside a
  comment saying where to get one needs no decoding.

**Bad:**

- **Secrets are now scattered across many files rather than one.** Backing up or rotating
  them means walking `.harry/**/.env.local` rather than copying a single file. `make
  env-template` should grow a companion that lists every local file and which of them are
  missing a required value, or this becomes a foot-gun the first time a machine is rebuilt.
- **A container must not bake these in.** The committed `.env` files carry no secrets, so
  copying them is harmless, but a build run on a developer machine would sweep up every
  `.env.local` in the tree. That needs a `.dockerignore`, and it is the kind of thing that
  is discovered by finding a credential in a published image.
- More file reads at start-up, one pair per capability. Irrelevant at this scale and worth
  saying out loud so nobody optimises it into a cache that goes stale.
- The derived key survives as the environment-override name, so there are two spellings of
  the same setting — `APP_PASSWORD` in the file, `HARRY_ICLOUD_APP_PASSWORD` in the
  environment. That is the price of letting a container inject anything at all, and the
  generated `.env` names both.
