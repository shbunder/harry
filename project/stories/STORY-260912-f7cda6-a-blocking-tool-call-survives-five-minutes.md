---
id: STORY-260912-f7cda6
title: A blocking tool call survives five minutes
feature: FEAT-260912-cfeb21
status: Backlog
created: 2026-09-12
---

# STORY-260912-f7cda6 — A blocking tool call survives five minutes

Part of [[FEAT-260912-cfeb21]].

## Description

The whole Slack loop rests on a tool call being held open while a human answers. If it does not hold, `ask_human` becomes a request id plus a poll — more turns, same outcome, a different module. Phase 4 is not designed until this is answered.

## Acceptance criteria

<!-- These drive the tests. Write checkable statements, not activities.
     Bad:  Wire up the article fetcher
     Good: A De Tijd article whose browser session has expired falls back to its RSS
           summary, and the page still renders -->

- [ ] A Claude Code session calls `sleep` and receives the result in the same turn, five minutes later
- [ ] The setting that governs the timeout is named, with its default and its ceiling
- [ ] The longest call that succeeds is recorded, and the first length that fails
- [ ] The finding is a dated note on this feature, since Phase 4 has no feature or decision yet
- [ ] It says which of the two designs Phase 4 takes, in one sentence, so the next person does not re-derive it

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

