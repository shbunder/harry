---
id: STORY-260915-a8264c
title: One helper copies a capability, and it leaves the machine behind
feature: FEAT-260915-257c60
status: Done
created: 2026-09-15
---

# STORY-260915-a8264c — One helper copies a capability, and it leaves the machine behind

Part of [[FEAT-260915-257c60]].

## Description

Eight test files copy a capability folder into a temporary root with
`shutil.copytree(REPO / '.harry' / …)`. Every one of them takes the whole folder, so
whatever is sitting in the working tree comes along — `.env.local`, `__pycache__`, and
anything else somebody left there.

The fix is one helper in `tests/capability_copy.py` that copies a capability and leaves the
machine behind, every call site moved onto it, and a guard that fails if a ninth call site
appears. Not `conftest.py`: with pytest's `--import-mode=importlib` a conftest is not
importable by name, and a module beside the tests is — `from .capability_copy import …`,
the same shape `test_alerts.py` already uses for `test_loader`.
One unit of work because the guard is what makes the move stick: eight edits with nothing
holding them is a ninth edit away from being back where it started.

## Acceptance criteria

- [x] `copy_capability(source, destination)` in `tests/capability_copy.py` copies a capability folder without `.env.local`, `__pycache__` or a loose `.pyc`
- [x] Given a source folder containing both, the destination has the declaration, the `.env`, the Python, and neither of those two
- [x] All eight call sites, across six test files, use it; none copies out of `.harry/` directly
- [x] A test parses every `tests/*.py` and fails on a copy whose source comes out of `.harry/`, however it is spelled, so the ninth call site cannot slip in
- [x] `tests/test_news_connector.py` passes with `.harry/connectors/news/.env.local` naming a third feed, and with the file absent — `by inspection: the suite cannot run itself both ways; 51 of 51 each time`
- [x] Every capability folder given a throwaway `.env.local` leaves `make check` green — `by inspection: verified against a scratch copy of the tree, twelve planted files, 670 passed`

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

