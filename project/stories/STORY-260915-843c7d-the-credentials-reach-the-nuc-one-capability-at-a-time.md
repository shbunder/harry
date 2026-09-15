---
id: STORY-260915-843c7d
title: The credentials reach the NUC, one capability at a time
feature: FEAT-260915-2a6ce1
status: Backlog
created: 2026-09-15
---

# STORY-260915-843c7d — The credentials reach the NUC, one capability at a time

Part of [[FEAT-260915-2a6ce1]].

## Description

Four capabilities, three credentials, one at a time — watching `/health` turn each from
skipped to loaded. Weather first because it needs none, then news, then iCloud, then the
tablet.

**The reMarkable token is the dangerous one.** It grants complete read and write over every
document on the tablet, with no scopes and no expiry, and there is no read-only variant to ask
for. The iCloud app password gives full calendar access. Both live only in a gitignored
`.env.local` beside their connector.

## Acceptance criteria

- [ ] Each credential reaches the NUC without appearing in the repository, the image, a committed compose file, or a shell history
- [ ] Putting one in place turns its capability from skipped to loaded with no rebuild
- [ ] `docs/operating.md` says where each file goes and what its mode should be
- [ ] A page is built by hand on the NUC with `make digest-candidates` and `make digest-dry`, and nothing is pushed
- [ ] The runbook says what to do when each credential lapses, and which of them expire on their own

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

