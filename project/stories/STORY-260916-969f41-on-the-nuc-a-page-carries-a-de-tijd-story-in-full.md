---
id: STORY-260916-969f41
title: On the NUC, a page carries a De Tijd story in full
feature: FEAT-260912-9c933f
status: Backlog
created: 2026-09-16
---

# STORY-260916-969f41 — On the NUC, a page carries a De Tijd story in full

Part of [[FEAT-260912-9c933f]].

## Description

The proof that matters: the real stack on the NUC, with the mounted credentials, the virtual
display and a De Tijd feed, builds a page with a De Tijd story in full. Nothing pushed.

## Acceptance criteria

- [ ] The real stack is deployed from the main checkout with the tijd connector loaded, and `make health` says so
- [ ] A page built through `scripts/call_tool.py` inside the container, with one De Tijd story chosen and deliver=false, carries that story's whole article (live)
- [ ] The session file is on the `harry-data` volume, mode 600, and appears in neither `git status` nor the image
- [ ] `docs/sources.md` lists De Tijd, and `docs/operating.md` has its runbook: where the credentials go, how to add the feed, and what each Slack line means
- [ ] `CLAUDE.md` and `.claude/rules/secrets-and-config.md` name the De Tijd password, not the storage state, as the credential that deserves fear

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

