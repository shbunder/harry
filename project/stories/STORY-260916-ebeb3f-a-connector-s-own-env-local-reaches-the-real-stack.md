---
id: STORY-260916-ebeb3f
title: A connector's own .env.local reaches the real stack
feature: FEAT-260912-9c933f
status: In Progress
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

- [x] `HARRY_CAPABILITY_SETTINGS_DIR` is a core setting, empty by default, in `Settings` and the root `.env`, with a comment saying what mounts it
- [x] When it is set, a capability's `.env.local` at `<dir>/connectors/<name>/.env.local` — the kind's folder name, plural, as under `.harry/` — is read, and wins over the `.env.local` beside the capability
- [x] A connector and a tool with the same name read different mounted files
- [x] The environment variable still wins over the mounted file, and a principal's own file still wins over both
- [x] When it is empty, nothing changes: a file at the would-be mounted path is not read
- [x] Nothing but `.env.local` is read from the mounted directory — a `.env` placed there is ignored
- [x] Through `load()`, a connector whose required settings are only in the mounted directory loads, and is skipped when the setting is empty
- [x] `docker-compose.yml` mounts `./.harry` read-only on the `harry` service at the path its `HARRY_CAPABILITY_SETTINGS_DIR` names; `harry-dev` mounts nothing but its volume and sets nothing
- [x] `tests/test_deployment.py::test_each_stack_keeps_its_data_on_a_named_volume_of_its_own` is narrowed, not deleted: data still lives on a named volume of each stack's own, and a new test proves the only other mount is `./.harry`, read-only, on the real stack
- [x] In the built image, a container with a `.harry`-shaped directory mounted read-only and the setting pointing at it loads a connector from it (live)
- [x] `docs/operating.md` says where a credential goes on the NUC, in the present tense; that each connector's `.env.local` should be mode 600; and that the dev stack still reads `.env.dev.local`
- [ ] The connector `.env.local` files on this NUC are mode 600 before the real stack is deployed with the mount — by inspection: they are this machine's files, not the repository's
- [x] `.claude/rules/secrets-and-config.md` states the new precedence

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

