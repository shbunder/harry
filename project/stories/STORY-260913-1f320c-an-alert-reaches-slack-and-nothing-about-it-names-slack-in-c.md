---
id: STORY-260913-1f320c
title: An alert reaches Slack, and nothing about it names Slack in core
feature: FEAT-260912-84c828
status: Backlog
created: 2026-09-13
---

# STORY-260913-1f320c — An alert reaches Slack, and nothing about it names Slack in core

Part of [[FEAT-260912-84c828]].

## Description

The connector, the seam and the rule that keeps them apart. Core says something went wrong; a capability decides that means Slack. Written first because the other two stories call it.

## Acceptance criteria

<!-- These drive the tests. Write checkable statements, not activities.
     Bad:  Wire up the article fetcher
     Good: A De Tijd article whose browser session has expired falls back to its RSS
           summary, and the page still renders -->

- [ ] A capability registers itself as an alert sink with registry.alerts(fn), and core sends to every one that did
- [ ] An alert with no sink registered is a WARNING in the log, and nothing raises
- [ ] The Slack connector sends one chat.postMessage carrying the channel and the caller's text, with nothing added
- [ ] Slack answering 500, or refusing the connection, is logged and does not reach the caller
- [ ] The next alert after a failed one is still attempted
- [ ] No file in src/harry/ names the Slack connector in code
- [ ] The bot token is in no log line, no alert and no /health field, and the committed .env leaves it empty

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

