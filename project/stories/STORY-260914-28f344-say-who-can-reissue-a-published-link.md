---
id: STORY-260914-28f344
title: Say who can reissue a published link
feature: FEAT-260914-c65b74
status: Done
created: 2026-09-14
---

# STORY-260914-28f344 — Say who can reissue a published link

Part of [[FEAT-260914-c65b74]].

## Description

Three message strings and three pages, all assuming the reader owns the calendar. Plus one
fact that belongs in the operating runbook: this is the only credential Harry holds that its
user cannot rotate.

## Acceptance criteria

- [x] The 404/403 message says to get a fresh link from whoever publishes that calendar
- [x] The not-a-calendar message says the same
- [x] Neither says "republish", which only the calendar's owner can do
- [x] Both still name the link and still fit on one Slack line
- [x] `CONNECTOR.md` says a link you do not own cannot be revoked by you, and that a leak of one is permanent
- [x] `docs/operating.md` marks each credential as rotatable or not
- [x] A test asserts neither message tells the reader to republish anything

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

