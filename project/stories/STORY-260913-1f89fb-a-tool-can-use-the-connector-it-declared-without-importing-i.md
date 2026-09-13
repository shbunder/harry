---
id: STORY-260913-1f89fb
title: A tool can use the connector it declared, without importing it
feature: FEAT-260913-007e6f
status: Backlog
created: 2026-09-13
---

# STORY-260913-1f89fb — A tool can use the connector it declared, without importing it

Part of [[FEAT-260913-007e6f]].

## Description

The other half of `requires:`. It already decides whether a capability loads; now it decides what that capability can reach. Written first because the tool in the second story is its first real caller.

## Acceptance criteria

<!-- These drive the tests. Write checkable statements, not activities.
     Bad:  Wire up the article fetcher
     Good: A De Tijd article whose browser session has expired falls back to its RSS
           summary, and the page still renders -->

- [ ] context.connectors holds what each connector in `requires:` registered, keyed by name
- [ ] A connector the capability did not declare is absent from the mapping
- [ ] A connector that registered nothing is absent rather than present as None
- [ ] A capability that reaches for one it did not declare is skipped at start-up, and /health carries a sentence rather than a KeyError
- [ ] A capability with no `requires:` gets an empty mapping, not an error
- [ ] No file in src/harry/ names a connector in code — the loader copies from a list the declaration chose
- [ ] docs/capabilities.md, .harry/README.md and the three /new-* skills all describe the ninth field
- [ ] The loader's requirements page points at the ADR that amended it

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

