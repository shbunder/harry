---
id: STORY-260913-6a5e03
title: Harry remembers when a job finished, across a restart
feature: FEAT-260912-11772e
status: Backlog
created: 2026-09-13
---

# STORY-260913-6a5e03 — Harry remembers when a job finished, across a restart

Part of [[FEAT-260912-11772e]].

## Description

harry.store at its smallest useful size: one JSON file under the data volume, and the MCP tool a Claude-triggered job's brief calls when it is done. In memory this would lose every completion on a deploy and alert for a page that was delivered.

## Acceptance criteria

<!-- These drive the tests. Write checkable statements, not activities.
     Bad:  Wire up the article fetcher
     Good: A De Tijd article whose browser session has expired falls back to its RSS
           summary, and the page still renders -->

- [ ] harry_mark_done("morning-page") records the time under the data volume
- [ ] The record is still there after a restart
- [ ] harry_mark_done for a job that does not exist is an error naming the job
- [ ] harry_mark_done is always in the MCP roster, because a brief cannot search for it
- [ ] The stand-in trigger: claude brief ends by telling Claude to call it, and says what happens if it does not
- [ ] A store file that cannot be read starts Harry with an empty record and says so, rather than refusing to start
- [ ] A store file that cannot be written logs at WARNING and does not break the caller

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

