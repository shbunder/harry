---
id: STORY-260915-6bf64f
title: The delete after an upload uses the tablet's current state
feature: FEAT-260915-bbbab1
status: Backlog
created: 2026-09-15
---

# STORY-260915-6bf64f — The delete after an upload uses the tablet's current state

Part of [[FEAT-260915-bbbab1]].

## Description

Two calls in `_retire` gain `refresh=True`: the listing, so it sees the folder as it is after
the upload rather than as it was before, and the delete, so the metadata write carries the
generation the server is actually on.

One unit of work because the two are the same mistake — the connector held one view of the
tablet across a write that changed it — and because the only thing that proves either is a
`live` test, which has to push twice whichever call is at fault.

## Acceptance criteria

- [ ] `client.list_directory_hydrated` and `client.delete` are both called with `refresh=True` inside `_retire`
- [ ] The stand-in records the `refresh` argument of each, and a test asserts both are true
- [ ] `test_the_stand_in_has_the_same_shape_as_the_real_client` still passes, so `refresh` is a parameter remarkapy really takes
- [ ] A `live` test pushes one name twice and asserts the folder holds one document with the second push's id
- [ ] A delete that fails anyway still leaves the page, logs, and alerts under `retire`
- [ ] The runbook row for a rejected removal says what it means, rather than pointing at a protocol change

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

