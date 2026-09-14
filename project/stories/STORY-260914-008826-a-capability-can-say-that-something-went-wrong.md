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

- [x] context.alert(message) reaches every registered sink with exactly what the capability wrote
- [x] A key makes a repeating fault report once a day; no key means every time
- [x] The key is namespaced by core to <kind>:<name>:<key>, so two capabilities using "down" do not silence each other
- [x] With no sink registered it is a WARNING naming the capability that raised it, and nothing raises
- [x] A capability handed no alerts at all logs under its own logger, which already carries its name
- [x] The re-entry guard is per thread, so an alert raised while a sink is blocking is not dropped
- [x] Every sink failing returns normally, is logged, and leaves the key unrecorded so the next occurrence tries again
- [x] An alert raised inside register() is logged, the capability still loads, a sink loaded later does not get it, and the key stays unrecorded
- [x] Alerts tells "attached with no sinks" apart from "not attached yet" — only the first counts as delivery
- [x] A declared secret is [redacted] in the message before any sink sees it
- [x] A sink alerting from its own failure path is refused re-entry, logged and dropped
- [x] A capability importing harry.alerts is still skipped — context.alert is the only way in
- [x] docs/alerting.md, docs/capabilities.md and the three /new-* skills say when to log and when to alert
- [x] Context's public names are pinned by a test

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

