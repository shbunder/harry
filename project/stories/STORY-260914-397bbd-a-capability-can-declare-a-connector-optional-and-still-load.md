---
id: STORY-260914-397bbd
title: A capability can declare a connector optional and still load without it
feature: FEAT-260912-0f2744
status: Done
created: 2026-09-14
---

# STORY-260914-397bbd — A capability can declare a connector optional and still load without it

Part of [[FEAT-260912-0f2744]].

## Description

The contract addition the page needs. `requires:` refuses a capability whose connector did not load, which is right for a tool that cannot work without one and exactly wrong for a page that is supposed to render with a section missing.

## Acceptance criteria

<!-- These drive the tests. Write checkable statements, not activities.
     Bad:  Wire up the article fetcher
     Good: A De Tijd article whose browser session has expired falls back to its RSS
           summary, and the page still renders -->

- [x] A capability declaring a connector `optional:` loads whether or not that connector did
- [x] context.connectors carries an optional connector that loaded, and omits one that did not
- [x] A capability declaring both gets required ones guaranteed and optional ones only if present
- [x] `requires:` still refuses a capability whose connector is missing — optional does not weaken it
- [x] check_capabilities.py refuses an `optional:` naming a connector that does not exist, the way `requires:` does
- [x] The two lists do not interfere: a capability declaring both gets its required ones or is skipped, and its optional ones only if they loaded
- [x] The /new-tool template, .harry/README.md and docs/capabilities.md all say what the two lists mean and how to choose

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

