---
id: STORY-260916-daf947
title: A connector can use another connector, and they load in that order
feature: FEAT-260912-9c933f
status: Done
created: 2026-09-16
---

# STORY-260916-daf947 — A connector can use another connector, and they load in that order

Part of [[FEAT-260912-9c933f]].

## Description

News has to hand De Tijd's pages to the tijd connector without importing it. Tools and jobs
already do this with `requires:` and `optional:`; connectors cannot, because they load in name
order and "news" sorts first — see [[ADR-260916-d4acc6]].

## Acceptance criteria

- [x] A connector declaring `optional: [x]` is loaded after `x` and handed it in `context.connectors`, when `x` sorts after it — proven through `load()`, not by calling the ordering function
- [x] A connector declaring `requires: [x]` is loaded after `x`, and skipped with "needs x, which did not load" when `x` did not load
- [x] Connectors naming nothing load in name order, as before
- [x] In a loop, the members load in name order after whatever outside the loop they name; a member naming a later member under `optional:` is handed nothing for it, and under `requires:` is skipped with "needs <name>, which did not load"; nothing raises
- [x] A loop that reaches `load()` is logged, naming its members
- [x] A connector whose declaration cannot be read, or whose `optional:` or `requires:` is not a list, is skipped with its reason, and the other connectors still load in dependency order
- [x] `make lint` refuses a connector naming a connector that does not exist, a list that is not a list, and a loop of any length — including a connector naming itself
- [x] `docs/capabilities.md` says a connector may name connectors, which list to use, and what happens in a loop

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

