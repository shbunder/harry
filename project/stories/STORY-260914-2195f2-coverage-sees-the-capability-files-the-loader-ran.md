---
id: STORY-260914-2195f2
title: Coverage sees the capability files the loader ran
feature: FEAT-260914-e1e8d0
status: Backlog
created: 2026-09-14
---

# STORY-260914-2195f2 — Coverage sees the capability files the loader ran

Part of [[FEAT-260914-e1e8d0]].

## Description

Make the number mean what it says. The loader copies each capability folder to a temporary
directory and imports it from there, so coverage records paths that no longer exist and
attributes nothing back to `.harry/`.

Two ways out, and the choice is the work: a `[paths]` remap in the coverage configuration
that folds the temporary copies onto the real files, or loading capabilities in place for
the test run. The first keeps the loader's isolation and is a configuration change; the
second is simpler to read and gives up the isolation that stops one test's edits reaching
another.

## Acceptance criteria

- [ ] `coverage report` includes `.harry/connectors/weather/connector.py`
- [ ] Removing the WMO word table's fallback branch changes the reported percentage
- [ ] A test asserts the measured file set contains at least one path under `.harry/`
- [ ] `fail_under` is unchanged or raised, never lowered, and the gate passes

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

