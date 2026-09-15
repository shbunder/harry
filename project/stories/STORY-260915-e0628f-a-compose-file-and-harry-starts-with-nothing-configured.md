---
id: STORY-260915-e0628f
title: A compose file, and Harry starts with nothing configured
feature: FEAT-260915-2a6ce1
status: Backlog
created: 2026-09-15
---

# STORY-260915-e0628f — A compose file, and Harry starts with nothing configured

Part of [[FEAT-260915-2a6ce1]].

## Description

**Do this first. Nothing else can be tested until it exists.**

`make up`, `make down` and `make logs` all shell out to `docker compose` and there is no
compose file in the repository. The `Dockerfile` is current and thoughtful — it copies neither
`.env` nor `.env.local`, on purpose, so configuration arrives as environment variables.

The acceptance test needs no credentials: a machine with nothing configured must start, answer
`/health`, and name what each skipped capability is missing. That is not a stub state, it is
the state every credential arrives into one at a time.

## Acceptance criteria

- [ ] `compose.yaml` builds from the `Dockerfile` and runs one service on `HARRY_PORT`
- [ ] The data volume is named and survives `make down` followed by `make up`
- [ ] `restart: unless-stopped`, so Harry comes back with the machine
- [ ] The healthcheck the image already declares is what compose waits on
- [ ] `make up` on a tree with no `.env.local` anywhere starts Harry and answers `/health`
- [ ] `/health` lists every capability as skipped, each naming the setting it is missing
- [ ] No credential and no secret is in the committed compose file
- [ ] `docs/operating.md` says how to start, stop and follow it, in the present tense

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

