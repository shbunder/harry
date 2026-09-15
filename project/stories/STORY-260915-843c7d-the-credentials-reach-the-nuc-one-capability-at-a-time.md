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

- [x] Each credential reaches the NUC without appearing in the repository, the image, a committed compose file, or a shell history
- [x] Putting one in place turns its capability from skipped to loaded with no rebuild
- [x] `docs/operating.md` says where each file goes and what its mode should be
- [ ] A page is built by hand on the NUC with `make digest-candidates` and `make digest-dry`, and nothing is pushed
- [x] The runbook says what to do when each credential lapses, and which of them expire on their own

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes


- **2026-09-15** — Left open on purpose: the fourth criterion. The mechanism is proven and the runbook is written, but no real credential has been put on this NUC — that is the operator's to do and it is the step where the reMarkable token physically moves onto a new machine. What was proven instead: five placeholder HARRY_<CAPABILITY>_<SETTING> values in a mode-600 root .env.local took /health from 8 loaded / 7 skipped to 15 loaded / 0 skipped on a restart with no rebuild. A page WAS built by hand on the NUC from weather and news alone (no credentials): 40 headlines, then a 53-page PDF with 20 articles at /data/digest/2026-09-15.pdf, deliver=false, nothing pushed. The criterion's wording names 'make digest-candidates and make digest-dry', which the requirements page corrects — make is not in the image and the Makefile is not copied in, so the route is scripts/call_tool.py. Reword the criterion or read it as satisfied by the call_tool route.

