---
id: STORY-260913-78d843
title: Most tools stay out of the roster until somebody looks for one
feature: FEAT-260912-334932
status: Backlog
created: 2026-09-13
---

# STORY-260913-78d843 — Most tools stay out of the roster until somebody looks for one

Part of [[FEAT-260912-334932]].

## Description

The roster is sent on every request, so every tool in it and unused is rent paid forever. Deferral is the answer, and harry_find_tools is what makes a deferred tool findable. The reveal is server-wide because FastMCP 4.0.3 has no stable session id — measured, not assumed.

## Acceptance criteria

<!-- These drive the tests. Write checkable statements, not activities.
     Bad:  Wire up the article fetcher
     Good: A De Tijd article whose browser session has expired falls back to its RSS
           summary, and the page still renders -->

- [ ] A tool with always_load false is absent from the roster
- [ ] A tool with always_load true is in it
- [ ] harry_find_tools matches on a tool name, its namespace and its description body
- [ ] A revealed tool appears in the next listing and can then be called
- [ ] Revealing sends a tools/list_changed notification, so a client knows to look again
- [ ] harry_find_tools is in the roster even when every declared tool is deferred
- [ ] Searching for something that matches nothing says so, names no tool, and reveals none
- [ ] The match is a case-insensitive substring of the name, the namespace or the body — no ranking, results in name order
- [ ] limit defaults to 10 and refuses more than 50, and a capped answer says to search more narrowly
- [ ] A restart puts every revealed tool back out of the roster

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

