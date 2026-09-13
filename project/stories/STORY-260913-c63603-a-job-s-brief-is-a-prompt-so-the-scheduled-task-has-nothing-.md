---
id: STORY-260913-c63603
title: A job's brief is a prompt, so the scheduled task has nothing to copy
feature: FEAT-260912-334932
status: Backlog
created: 2026-09-13
---

# STORY-260913-c63603 — A job's brief is a prompt, so the scheduled task has nothing to copy

Part of [[FEAT-260912-334932]].

## Description

A trigger: claude job's body is a brief addressed to Claude. Publishing it as an MCP prompt means the scheduled task invokes it by name instead of carrying a copy that drifts from the file.

## Acceptance criteria

<!-- These drive the tests. Write checkable statements, not activities.
     Bad:  Wire up the article fetcher
     Good: A De Tijd article whose browser session has expired falls back to its RSS
           summary, and the page still renders -->

- [ ] A trigger: claude job is published as a prompt named for the job
- [ ] Rendering the prompt returns the job's body verbatim
- [ ] A trigger: schedule job has no prompt — nothing reads a heuristic job's body
- [ ] A job the loader skipped has no prompt

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

