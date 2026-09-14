---
id: STORY-260914-008826
title: A capability can say that something went wrong
feature: FEAT-260914-fc1515
status: Backlog
created: 2026-09-14
---

# STORY-260914-008826 — A capability can say that something went wrong

Part of [[FEAT-260914-fc1515]].

## Description

The missing half of alerting. A capability can offer somewhere alerts go and cannot raise one, so the connector that knows its credential has lapsed cannot say so — which is the exact thing alerting exists for.

## Acceptance criteria

<!-- These drive the tests. Write checkable statements, not activities.
     Bad:  Wire up the article fetcher
     Good: A De Tijd article whose browser session has expired falls back to its RSS
           summary, and the page still renders -->

- [ ] context.alert(message) reaches every registered sink with exactly what the capability wrote
- [ ] A key makes a repeating fault report once a day; no key means every time
- [ ] The key is namespaced by core to <kind>:<name>:<key>, so two capabilities using "down" do not silence each other
- [ ] With no sink registered it is a WARNING naming the capability, and nothing raises
- [ ] Every sink failing returns normally, is logged, and leaves the key unrecorded so the next occurrence tries again
- [ ] An alert raised inside register() is logged, the capability still loads, and a sink loaded later does not get it
- [ ] A capability importing harry.alerts is still skipped — context.alert is the only way in
- [ ] docs/alerting.md and the three /new-* skills say when to log and when to alert

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

