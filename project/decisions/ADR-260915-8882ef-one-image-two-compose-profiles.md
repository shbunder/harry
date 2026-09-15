---
id: ADR-260915-8882ef
title: One image, two compose profiles
status: Accepted
created: 2026-09-15
feature: FEAT-260915-2a6ce1
supersedes: ''
superseded_by: ''
---

# ADR-260915-8882ef — One image, two compose profiles

## Status

Accepted

Drives [[FEAT-260915-2a6ce1]].

## Context & problem

Harry is about to run on a NUC that is on all the time and delivers a newspaper at 06:30. It
needs somewhere to try a change that is not the machine doing that — so two stacks, on one
box.

The question is whether "dev" and "prod" are two images or one image run two ways.

What the image already is settles more of this than it looks. `Dockerfile` copies neither
`.env` nor `.env.local`, and says why in a comment: compose injects configuration as real
environment variables, which outrank the dotenv files, **so the image carries no
configuration and the same image runs on any machine**. That was decided before there was a
second stack to run.

## Decision drivers

- A dev stack that is not the artefact being shipped tests something else
- Two builds is two things to keep in step, and the one that drifts is the one nobody runs
- Everything that actually differs — port, data directory, credentials, capabilities
  directory — is already configuration by construction
- **Two schedulers is a real problem, not a stylistic one.** Both would run the deadline
  watchdog, and a dev stack must never be able to say "no page today" about a morning the
  real one delivered — that is how a Slack channel gets muted
- One operator, one machine. Anything that needs a registry and a promotion pipeline is
  answering a question nobody asked

## Considered options

### Option 1: One image, two compose profiles

`harry` and `harry-dev` as services in one compose file, built from the same `Dockerfile`,
differing only in environment: `HARRY_PORT`, `HARRY_DATA_DIR`, the `.env.local` files mounted
or the variables injected, and a setting that turns the scheduler off in dev.

**For:** the thing tried in dev is byte-identical to the thing running. One build. The
difference between the stacks is readable in one file, which is also the file that documents
it. It extends a pattern this repository already uses — `make worktree` gives every worktree
its own port and data directory for exactly this reason.

**Against:** the two services share an image tag, so upgrading dev and prod separately means
being careful with tags rather than being handed the separation. A dev stack running an
older image is something you have to arrange rather than get.

### Option 2: Two images, `harry:dev` and `harry:prod`

**For:** upgrading one and not the other is the default rather than a discipline. A dev image
could carry extra tooling — a shell, a debugger, test dependencies — that has no business in
the thing delivering a newspaper.

**Against:** two builds to keep in step, and the dev one is the one that drifts, because it
is the one nobody is watching at 06:30. Extra tooling in dev is the whole problem: the stack
where a change is proved is then not the stack where it runs. And `Dockerfile` already
refuses to be environment-specific — making it environment-specific to get this is undoing a
decision that is paying for itself.

## Decision outcome

One image, two compose profiles. The image is code; everything else is configuration, which
is what the `Dockerfile` already assumed.

**Modular** drove it, with **Explainable** behind: the difference between the two stacks is a
handful of environment variables in one file a person can read, rather than a second build
whose divergence from the first is discovered by it behaving differently.

The scheduler is the one asymmetry and it is deliberate: **dev runs with it off.** A
capability that is not scheduled cannot report a deadline it was never watching.

## Consequences

**Good:** what runs in dev is what runs in prod, without a promise. One `make image`. The two
stacks cannot collide on a port or a data directory, because both are set per service and the
compose file is where you look. Adding a third stack later — a staging one, a second reader —
is another block in the same file.

**Bad:** it makes rolling dev and prod separately a thing to be careful about rather than a
thing you get. Prod has to pin a tag per deploy and dev can track `latest`, and nothing
enforces that but a person following the runbook. It also means dev has no extra tooling — no
shell niceties, no test dependencies — so debugging inside the container is thinner than it
could be, and the answer is to reproduce on a laptop where the whole gate runs anyway.
