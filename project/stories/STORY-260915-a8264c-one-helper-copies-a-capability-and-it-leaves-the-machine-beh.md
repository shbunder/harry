---
id: STORY-260915-a8264c
title: One helper copies a capability, and it leaves the machine behind
feature: FEAT-260915-257c60
status: Backlog
created: 2026-09-15
---

# STORY-260915-a8264c — One helper copies a capability, and it leaves the machine behind

Part of [[FEAT-260915-257c60]].

## Description

Eight test files copy a capability folder into a temporary root with
`shutil.copytree(REPO / '.harry' / …)`. Every one of them takes the whole folder, so
whatever is sitting in the working tree comes along — `.env.local`, `__pycache__`, and
anything else somebody left there.

The fix is one helper in `tests/conftest.py` that copies a capability and leaves the machine
behind, every call site moved onto it, and a guard that fails if a ninth call site appears.
One unit of work because the guard is what makes the move stick: eight edits with nothing
holding them is a ninth edit away from being back where it started.

## Acceptance criteria

- [ ] `copy_capability(source, destination)` in `tests/conftest.py` copies a capability folder without `.env.local` or `__pycache__`
- [ ] Given a source folder containing both, the destination has the declaration, the `.env`, the Python, and neither of those two
- [ ] All eight test files use it; none calls `shutil.copytree` on `.harry/` directly
- [ ] A test greps the test files and fails on a direct `copytree` of `.harry/`, so the ninth call site cannot slip in
- [ ] `tests/test_news_connector.py` passes with `.harry/connectors/news/.env.local` naming a third feed, and with the file absent
- [ ] Every capability folder given a throwaway `.env.local` leaves `make check` green

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

