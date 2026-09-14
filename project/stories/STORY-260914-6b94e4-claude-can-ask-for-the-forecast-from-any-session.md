---
id: STORY-260914-6b94e4
title: Claude can ask for the forecast from any session
feature: FEAT-260912-5f7ec5
status: Backlog
created: 2026-09-14
---

# STORY-260914-6b94e4 — Claude can ask for the forecast from any session

Part of [[FEAT-260912-5f7ec5]].

## Description

The tool, and the one judgement call in this feature: a source being down is an answer, not an error. A tool that raises tells the model it did something wrong, and it did not.

## Acceptance criteria

<!-- These drive the tests. Write checkable statements, not activities.
     Bad:  Wire up the article fetcher
     Good: A De Tijd article whose browser session has expired falls back to its RSS
           summary, and the page still renders -->

- [ ] weather_forecast returns the four facts and the place they are for
- [ ] With the service down it returns {available: false, why} rather than raising
- [ ] It is deferred, and harry_find_tools("weather") finds it
- [ ] The weather connector declares it in provides:, and make lint enforces that as it does for slack_post
- [ ] Asked through a real MCP client, it answers with what the connector returned

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

