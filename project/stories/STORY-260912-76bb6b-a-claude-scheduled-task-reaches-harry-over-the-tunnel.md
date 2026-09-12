---
id: STORY-260912-76bb6b
title: A Claude scheduled task reaches Harry over the tunnel
feature: FEAT-260912-cfeb21
status: Backlog
created: 2026-09-12
---

# STORY-260912-76bb6b — A Claude scheduled task reaches Harry over the tunnel

Part of [[FEAT-260912-cfeb21]].

## Description

The one on the critical path. The morning page is triggered by a Claude scheduled task, so if a scheduled task cannot reach a self-hosted MCP server then the digest has no trigger and the clock has to live somewhere else.

## Acceptance criteria

<!-- These drive the tests. Write checkable statements, not activities.
     Bad:  Wire up the article fetcher
     Good: A De Tijd article whose browser session has expired falls back to its RSS
           summary, and the page still renders -->

- [ ] A Claude scheduled task configured against the tunnel URL calls `ping` and the result comes back to that session
- [ ] What had to be configured, and where, is written down step by step — this is the setup nobody will remember
- [ ] If it does not work, the reason is recorded: the plan, the account tier, or the network
- [ ] The finding is written into the scenario on the morning-page feature that depends on it

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

