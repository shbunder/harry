---
id: STORY-260915-36ccd2
title: Deploying a version, and going back to the last one
feature: FEAT-260915-2a6ce1
status: Done
created: 2026-09-15
---

# STORY-260915-36ccd2 — Deploying a version, and going back to the last one

Part of [[FEAT-260915-2a6ce1]].

## Description

The compose file pins `image: harry:latest`. That is the thing the ADR's own Consequences
section warns about: prod has to name a tag per deploy and dev can track `latest`, and nothing
enforces it but a person following the runbook — so the runbook has to have it.

Small, and the reason it is its own story is that it is the only part of this feature whose
failure is discovered on the morning you most need it not to be.

## Acceptance criteria

- [x] Every build is tagged with something that cannot be reused — the date, or the short commit
- [x] The real service names a tag; the dev one may track `latest`
- [x] Deploying is one command, and the data volume is untouched by it
- [x] Going back to the previous tag is one command, and the data volume is untouched by that too
- [x] `docs/operating.md` carries both commands, written out, with a real tag in them

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes


- **2026-09-15** — Two defects found by writing tests/test_deploy.py, which drives the real make targets against a stub docker rather than reimplementing them. First: the dirty-tree gate used 'git diff --quiet HEAD', which reports clean when the only change is an untracked file — and the Dockerfile does COPY .harry/ and COPY src/, so an untracked module reached the image under a tag naming a commit it was not in. Now git status --porcelain, and the refusal prints what is in the way. Second: .deployed-tags was written before 'compose up', so a deploy that never came healthy was recorded as the running version and 'make versions' would report it. The write moved after the stack is up. Both are guarded: deleting either gate turns a named test red.

