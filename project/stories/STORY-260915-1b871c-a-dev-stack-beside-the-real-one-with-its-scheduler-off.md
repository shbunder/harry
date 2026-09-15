---
id: STORY-260915-1b871c
title: A dev stack beside the real one, with its scheduler off
feature: FEAT-260915-2a6ce1
status: Done
created: 2026-09-15
---

# STORY-260915-1b871c — A dev stack beside the real one, with its scheduler off

Part of [[FEAT-260915-2a6ce1]].

## Description

A second service in the same compose file, from the same image, differing only in
environment — the decision is [[ADR-260915-8882ef]].

The pattern already exists: `make worktree` gives every worktree its own port and its own data
directory so two stacks cannot kill each other. Extend that rather than invent a second idea.

**The scheduler is the one real asymmetry.** Two stacks both running the deadline watchdog
would both alert, and a dev stack must never be able to say "no page today" about a morning
the real one delivered — that is how a channel gets muted.

## Acceptance criteria

- [x] A `harry-dev` service runs from the same image on a different port
- [x] It has its own data directory and its own `.env.local` files, and shares neither
- [x] Its scheduler does not run — no jobs are registered and no deadline is watched
- [x] The setting that turns it off is declared in `src/harry/config.py`, typed and commented, and carried in the committed `.env` with its default — not invented in the compose file
- [x] A test proves the scheduler is off rather than asserting the setting that turns it off
- [x] Stopping, restarting or rebuilding either service leaves the other running
- [x] `make up` starts the real one only; starting dev is a separate, explicit command
- [x] `docs/operating.md` says which is which and how to tell them apart from the outside

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes


- **2026-09-15** — Verified trap, found while proving the bare boot: `make up` inside a worktree reports Healthy and is unreachable. `make worktree` appends HARRY_PORT and HARRY_DATA_DIR to that tree's .env.local, and the compose file reads .env.local as an env_file — so the container gets HARRY_PORT=7431 while compose still publishes 7430:7430, and HARRY_DATA_DIR set to a host path that does not exist in the container. Measured: Harry listens on 7431 inside, curl to 7430 on the host gets nothing, /data (the mounted volume) is empty, and jobs.json lands on the container's own filesystem where it dies with the container. Compose still says Healthy, because the image's HEALTHCHECK reads the same $HARRY_PORT and so follows the error. That is a healthcheck that cannot fail — see .claude/rules/inert-controls.md. Whatever the dev stack does about ports, it has to make the published port and the port Harry listens on impossible to disagree, and the dev service needs its own data directory that is a real mount rather than a host path leaking in through .env.local.

