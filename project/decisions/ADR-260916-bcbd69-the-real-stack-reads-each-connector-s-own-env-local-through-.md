---
id: ADR-260916-bcbd69
title: The real stack reads each connector's own .env.local through a read-only mount
status: Accepted
created: 2026-09-16
feature: FEAT-260912-9c933f
supersedes: ''
superseded_by: ''
---

# ADR-260916-bcbd69 — The real stack reads each connector's own .env.local through a read-only mount

## Status

Accepted

Drives [[FEAT-260912-9c933f]].

## Context & problem

A capability's settings live in its own folder: `.harry/connectors/icloud/.env.local` holds
the iCloud password. That is the rule in `.claude/rules/secrets-and-config.md`, and it is
where the owner put every credential on the NUC.

**The container cannot see any of them.** `.dockerignore` keeps every `.env.local` out of the
image, which is right, and nothing mounts one. The only route in is the root `.env.local`,
which compose injects as environment variables under the prefixed names —
`HARRY_ICLOUD_APP_PASSWORD`. So on 2026-09-16 the real stack reported icloud, remarkable and
slack as skipped, while their credentials sat on the same machine.

Following the documented route means writing every credential twice, in two spellings. The
root file then becomes a list of every capability's secrets, which is what the rule says it
must not be.

## Decision drivers

- **Bounded** — one file per credential, on one machine, in the folder it belongs to
- The image carries no configuration, and a tag says exactly what code runs. Deploy and
  rollback depend on that
- The dev stack never reads the real stack's credentials
- The environment variable still outranks every file

## Considered options

### Option 1: Keep the prefixed names in the root `.env.local`

**For:** no code change. It is documented in `docs/operating.md` and it works today.
**Against:** every credential is written twice on the NUC, and the two copies can disagree. The
root file stops belonging to core.

### Option 2: Mount the checkout's `.harry/` as an extra capability root

`HARRY_CAPABILITIES_DIR` already exists, and a later root wins on name.

**For:** no core change at all.
**Against:** the checkout's *code* replaces the image's. The tag no longer says what runs, an
uncommitted edit goes live on the next restart, and `make rollback` stops meaning anything.

### Option 3: Generate one flat env file from every connector's `.env.local`

A make target writes `HARRY_<NAME>_<KEY>` lines into a gitignored file that compose loads.

**For:** no core change. Compose's `env_file:` does the rest.
**Against:** a second copy of every secret on disk, stale the moment someone runs
`docker compose` directly. And it is a recipe reading settings, which the rule forbids.

### Option 4: Mount the checkout's `.harry/` read-only as a settings directory

Compose mounts `./.harry` at `/settings`, read-only, on the real service only. A new core
setting, `HARRY_CAPABILITY_SETTINGS_DIR`, names that directory. When it is set, Harry reads a
capability's `.env.local` from `<dir>/connectors/<name>/.env.local` — the kind's folder name,
as under `.harry/` — as well as beside the capability.

**For:** one file per credential. The image, the code and the tag are unchanged. Nothing but
`.env.local` is read from the mount. The environment still wins.
**Against:** a core setting and a change to `config.py`. The whole `.harry/` tree is visible
inside the container, code included — read by nothing, but there.

## Decision outcome

**Option 4.** The real stack reads each connector's own `.env.local` through a read-only mount
of the checkout's `.harry/`.

Precedence, highest first, becomes:

1. `HARRY_<CAPABILITY>_<SETTING>` in the environment
2. `<data>/users/<principal>/connectors/<name>.env`, when a principal is given
3. `.env.local` under `HARRY_CAPABILITY_SETTINGS_DIR`, when it is set
4. `.env.local` beside the capability
5. `.env` beside the capability
6. the declaration's `default:`

The mounted file sits above the one beside the capability because setting the directory is a
deliberate act, and in the container the one beside it never exists. **Bounded** drove it.

## Consequences

**Good:**

- A credential lives in one file on the NUC, in its connector's folder.
- iCloud, the tablet and Slack load on the real stack with nothing more to do.
- The root `.env.local` holds only core's settings again.

**Bad:**

- **Turning this on turns on every credential at once.** The first deploy lights up Slack, the
  tablet and iCloud together, and the watchdog starts reporting to Slack. That deploy is
  confirmed with the owner before it happens.
- **The two stacks now differ in how credentials arrive.** Dev still reads `.env.dev.local`
  under the prefixed names. `docs/operating.md` has to say so plainly.
- **A mount's source is resolved against the compose file.** `make up` from a worktree mounts
  that worktree's `.harry/`, whose `.env.local` files are not seeded. The real stack is
  deployed from the main checkout.
- **Editing a connector's `.env.local` still needs a restart.** Settings are read once, at
  start-up. That is unchanged, but it now surprises in a new place, because the file on the
  host changed and the container did not notice.
