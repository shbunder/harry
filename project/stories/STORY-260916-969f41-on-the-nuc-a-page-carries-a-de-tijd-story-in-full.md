---
id: STORY-260916-969f41
title: On the NUC, a page carries a De Tijd story in full
feature: FEAT-260912-9c933f
status: Done
created: 2026-09-16
---

# STORY-260916-969f41 — On the NUC, a page carries a De Tijd story in full

Part of [[FEAT-260912-9c933f]].

## Description

The proof that matters: the real stack on the NUC, with the mounted credentials, the virtual
display and a De Tijd feed, builds a page with a De Tijd story in full. Nothing pushed.

## Acceptance criteria

- [x] The tijd connector's `.env.local` is moved from the worktree into the main checkout's `.harry/connectors/tijd/` without being read, mode 600
- [x] De Tijd's feed is in `FEEDS` in the main checkout's `.harry/connectors/news/.env.local` — by inspection: this machine's file, and its slugs and hosts are all that is read
- [x] The real stack is deployed from the main checkout with the tijd connector loaded, and `make health` says so
- [x] The `harry-data` volume holds no De Tijd session before the first build, so Harry's own login runs against the real page
- [x] A page built through `scripts/call_tool.py` inside the container, with one De Tijd story chosen and deliver=false, carries that story's whole article (live)
- [x] The session file is on the `harry-data` volume, mode 600, and appears in neither `git status` nor the image
- [x] by inspection: prose — `docs/sources.md` lists De Tijd, and `docs/operating.md` has its runbook: where the credentials go, how to add the feed, and what each Slack line means
- [x] by inspection: prose — `CLAUDE.md` and `.claude/rules/secrets-and-config.md` name the De Tijd password, not the storage state, as the credential that deserves fear
- [x] The spike's throwaway `tijd-spike` volume is deleted — by inspection: `docker volume ls` lists no `tijd-spike` since 2026-09-16

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

