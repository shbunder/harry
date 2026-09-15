---
id: STORY-260915-edb7a7
title: A push names its folder, and the connector supplies the default
feature: FEAT-260915-eb3236
status: Backlog
created: 2026-09-15
---

# STORY-260915-edb7a7 — A push names its folder, and the connector supplies the default

Part of [[FEAT-260915-eb3236]].

## Description

`self.folder` is read in three places — `_where`, `_find_folder` and the answer — and each
becomes a parameter with the setting as its default. `_folder_id` is remembered per folder
rather than once, because two callers in one process now ask for two.

One unit of work because the bound on the delete moves with it: `_retire` must scope to the
folder the document was actually pushed to, not to the configured one, or a second caller's
push could retire a document in somebody else's folder.

## Acceptance criteria

- [ ] `push(path, name, folder=None)` puts the document in `folder`, and in the configured one when it is None
- [ ] `push_bytes`, `push_markdown` and `documents` take the same argument and mean the same by it
- [ ] The folder id is remembered per folder, so two callers in one process do not share one
- [ ] A folder that is not there is made at the top level; one that is there is found
- [ ] `_retire` looks only in the folder just pushed to — a document of the same name in the configured folder is untouched when the push named another
- [ ] The answer's `where` is the folder actually used
- [ ] `digest_build` passes its `folder` setting, and an empty one means the connector decides
- [ ] The runbook and `docs/` say the folder belongs to the caller and that Harry only makes top-level folders

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

