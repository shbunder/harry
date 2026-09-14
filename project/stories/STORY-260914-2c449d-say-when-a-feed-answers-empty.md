---
id: STORY-260914-2c449d
title: Say when a feed answers empty
feature: FEAT-260914-0c37d0
status: Backlog
created: 2026-09-14
---

# STORY-260914-2c449d — Say when a feed answers empty

Part of [[FEAT-260914-0c37d0]].

## Description

One branch in `_gather`, one key, and the real document as a fixture.

The care needed is in not over-reporting: a feed with nothing on it at 04:00 is plausible,
and a connector that cried wolf every night would be muted within a week. This reports a feed
that yields **zero** candidates while it is configured and reachable — which for a national
broadcaster is a publishing fault, not a quiet hour.

## Acceptance criteria

- [ ] The recorded 555-byte VRT document yields an `unavailable` entry saying the feed was empty
- [ ] The other feeds' candidates are unaffected by it
- [ ] One Slack line names that feed, keyed separately from a fetch failure so one does not silence the other
- [ ] A feed carrying stories reports nothing
- [ ] Every feed being empty reports each of them, and still returns an empty candidate list rather than raising

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

