---
id: STORY-260916-ebeb3f
title: A connector's own .env.local reaches the real stack
feature: FEAT-260912-9c933f
status: Backlog
created: 2026-09-16
---

# STORY-260916-ebeb3f — A connector's own .env.local reaches the real stack

Part of [[FEAT-260912-9c933f]].

## Description

The credential plumbing, before anything needs it. On the NUC every connector's credentials
are in its own `.env.local`, and the real stack cannot see any of them. This mounts the
checkout's `.harry/` read-only into the real service and teaches `config.py` to read a
capability's `.env.local` from there — see [[ADR-260916-bcbd69]].

**Deploying this turns on every credential already on the NUC at once**: Slack, the tablet
and iCloud. The deploy is confirmed with the owner before it happens.

## Acceptance criteria

- [ ] `HARRY_CAPABILITY_SETTINGS_DIR` is a core setting, empty by default, in `Settings` and the root `.env`, with a comment saying what mounts it
- [ ] When it is set, a capability's `.env.local` under `<dir>/<kind>/<name>/` is read, and wins over the `.env.local` beside the capability
- [ ] The environment variable still wins over the mounted file, and a principal's own file still wins over both
- [ ] When it is empty, nothing changes: a test proves a laptop resolves exactly as before
- [ ] Nothing but `.env.local` is read from the mounted directory — a `.env` placed there is ignored
- [ ] `docker-compose.yml` mounts `./.harry` read-only on the `harry` service and sets the setting there; `harry-dev` mounts nothing and sets nothing
- [ ] A test in the gate reads `docker-compose.yml` and fails if the mount stops being read-only, or if dev gains it
- [ ] With a connector's `.env.local` in the mounted tree and nothing in the root `.env.local`, a started container lists that connector as loaded (live)
- [ ] `docs/operating.md` says where a credential goes on the NUC, in the present tense, and says the dev stack still reads `.env.dev.local`
- [ ] `.claude/rules/secrets-and-config.md` states the new precedence

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

