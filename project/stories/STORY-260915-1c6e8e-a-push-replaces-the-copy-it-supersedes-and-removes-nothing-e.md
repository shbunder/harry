---
id: STORY-260915-1c6e8e
title: A push replaces the copy it supersedes, and removes nothing else
feature: FEAT-260915-fd25f2
status: Done
created: 2026-09-15
---

# STORY-260915-1c6e8e — A push replaces the copy it supersedes, and removes nothing else

Part of [[FEAT-260915-fd25f2]].

## Description

`put_pdf` creates. There is no replace in remarkapy, so "put this content at this name" is a
push followed by a removal — and the order is the whole safety argument, which is why this is
one unit of work rather than two.

It also brings this connector its first call that takes something off the tablet, holding a
token with no scopes. The bounds on that call, and the tests that make each of them fail, are
the larger half of the work.

## Acceptance criteria

- [x] Pushing a name already in the folder leaves one document, carrying the second push's content, and the answer says `replaced: 1`
- [x] The first push of a name creates it and says `replaced: 0`
- [x] The push happens before the removal: a push that fails twice removes nothing and leaves the older copy where it was
- [x] A document of another name, a document of the same name in another folder, and a folder of the same name are all untouched
- [x] `client.delete` appears exactly once in the connector, inside `_retire`, and nothing else remarkapy offers that removes or moves appears at all
- [x] A removal that fails does not fail the push; it logs, and alerts under its own key rather than the push's
- [x] The folder default is `Daily`, in the declaration and in the generated `.env`
- [x] `docs/` and the runbook say a push replaces, that the new document goes up first, and that the removal is a soft delete to the tablet's trash

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

