---
id: STORY-260913-bb45b7
title: A capability that did not load reaches a person
feature: FEAT-260912-84c828
status: Backlog
created: 2026-09-13
---

# STORY-260913-bb45b7 — A capability that did not load reaches a person

Part of [[FEAT-260912-84c828]].

## Description

The first real caller, and the case three features have handed forward. A capability skipped three weeks ago looks exactly like one that was never installed.

## Acceptance criteria

<!-- These drive the tests. Write checkable statements, not activities.
     Bad:  Wire up the article fetcher
     Good: A De Tijd article whose browser session has expired falls back to its RSS
           summary, and the page still renders -->

- [x] A capability skipped at start-up produces one alert reading "Harry started without the <name> <kind>: <reason>"
- [x] A capability that loaded produces none
- [x] The alert is keyed on the capability, so a restart loop does not repeat it within the day
- [x] Alerts are raised after loading finishes, because a sink is a capability and has to load first
- [x] A skipped capability whose reason held a secret has it redacted in the alert too

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

