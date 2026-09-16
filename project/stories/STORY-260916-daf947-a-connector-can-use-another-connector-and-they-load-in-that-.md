---
id: STORY-260916-daf947
title: A connector can use another connector, and they load in that order
feature: FEAT-260912-9c933f
status: Backlog
created: 2026-09-16
---

# STORY-260916-daf947 — A connector can use another connector, and they load in that order

Part of [[FEAT-260912-9c933f]].

## Description

News has to hand De Tijd's pages to the tijd connector without importing it. Tools and jobs
already do this with `requires:` and `optional:`; connectors cannot, because they load in name
order and "news" sorts first — see [[ADR-260916-d4acc6]].

## Acceptance criteria

- [ ] A connector declaring `optional: [x]` is loaded after `x` and handed it in `context.connectors`, when `x` sorts after it — proven through `load()`, not by calling the ordering function
- [ ] A connector declaring `requires: [x]` is skipped with "needs x, which did not load" when `x` did not load
- [ ] A connector naming nothing loads in name order, as before
- [ ] Two connectors that name each other both load, in name order, and nothing raises
- [ ] `make lint` refuses a connector naming a connector that does not exist, and refuses two connectors that name each other
- [ ] `docs/capabilities.md` says a connector may name connectors, and which list to use

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

