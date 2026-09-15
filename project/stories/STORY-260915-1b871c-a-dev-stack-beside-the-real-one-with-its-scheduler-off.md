---
id: STORY-260915-1b871c
title: A dev stack beside the real one, with its scheduler off
feature: FEAT-260915-2a6ce1
status: Backlog
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

- [ ] A `harry-dev` service runs from the same image on a different port
- [ ] It has its own data directory and its own `.env.local` files, and shares neither
- [ ] Its scheduler does not run — no jobs are registered and no deadline is watched
- [ ] A test proves the scheduler is off rather than asserting the setting that turns it off
- [ ] Stopping, restarting or rebuilding either service leaves the other running
- [ ] `make up` starts the real one only; starting dev is a separate, explicit command
- [ ] `docs/operating.md` says which is which and how to tell them apart from the outside

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

