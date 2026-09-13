---
id: STORY-260913-c4f49d
title: One broken capability costs exactly itself
feature: FEAT-260912-8a0ab0
status: Backlog
created: 2026-09-13
---

# STORY-260913-c4f49d — One broken capability costs exactly itself

Part of [[FEAT-260912-8a0ab0]].

## Description

The property the whole design rests on. A half-written folder is the normal state of something being worked on, and the only state a third party ships in before it works.

## Acceptance criteria

<!-- These drive the tests. Write checkable statements, not activities.
     Bad:  Wire up the article fetcher
     Good: A De Tijd article whose browser session has expired falls back to its RSS
           summary, and the page still renders -->

- [ ] A capability that raises at import is skipped and Harry still serves
- [ ] Every other capability still registers
- [ ] The failure is recorded with the exception type and message
- [ ] A capability whose required setting is absent is skipped, and the reason names the setting
- [ ] Each of these is tested by making it happen, with a fixture capability that really is broken

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

