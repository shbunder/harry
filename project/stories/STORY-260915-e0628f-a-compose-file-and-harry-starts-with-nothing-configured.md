---
id: STORY-260915-e0628f
title: A compose file, and Harry starts with nothing configured
feature: FEAT-260915-2a6ce1
status: Done
created: 2026-09-15
---

# STORY-260915-e0628f — A compose file, and Harry starts with nothing configured

Part of [[FEAT-260915-2a6ce1]].

## Description

**Do this first, and start by reading `docker-compose.yml` — it exists.** One service,
`build: .`, `restart: unless-stopped`, the `harry-data` volume, `7430:7430`, and both env
files in the right order. `make up` works today.

**Extend it rather than renaming it.** Two rules are path-scoped to `docker-compose.yml` —
`.claude/rules/secrets-and-config.md` and `.claude/rules/no-model-calls.md` — and a rename to
`compose.yaml` drops both guards silently, including the one that stops a model credential
being mounted in. Rename it only with the `paths:` in both rules changed in the same commit.

The acceptance test needs no credentials, and it is not "everything is skipped": weather and
news declare no required setting and load on a bare machine. That asymmetry is the point —
the first page built on the NUC has a weather panel and headlines and no agenda.

## Acceptance criteria

- [x] The existing `docker-compose.yml` is extended rather than replaced, or the `paths:` in both rules that name it are changed in the same commit
- [x] The data volume is named and survives `make down` followed by `make up`
- [x] `restart: unless-stopped`, so Harry comes back with the machine
- [x] The healthcheck the image already declares is what compose waits on
- [x] `make up` on a tree with no `.env.local` anywhere starts Harry and answers `/health`
- [x] weather and news are loaded; icloud, remarkable and slack are skipped, each naming the setting it is missing
- [x] No credential and no secret is in the committed compose file
- [x] `docs/operating.md` says how to start, stop and follow it, in the present tense

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes


- **2026-09-15** — Proven on the NUC from a tree with no .env.local anywhere (tar copy into a scratch dir, project name 'bareboot'): healthy in 6s, 8 loaded and 7 skipped exactly as docs/operating.md now lists, /data survives make down + make up, and killing the python process inside the container brings it back healthy on its own with RestartCount=1. Note for anyone repeating that last one: docker kill and docker stop count as manual intervention, so restart: unless-stopped correctly does NOT restart after them — crash the process inside the container instead, or you will conclude the policy is dead when it is not.

