---
name: new-story
description: Add a story under an existing feature on Harry's board. Use for a unit of work that belongs to a feature already open. To open the feature itself use /new-feature.
---

Add a story for: $ARGUMENTS

### 1. Find the parent feature

```bash
make board
```

If the current branch is `feat/FEAT-…`, that is the parent unless the user says otherwise. A
story with no feature is a signal the work is not tracked at all — stop and ask whether it
needs a feature first.

### 2. Allocate

```bash
uv run python project/board.py new-story "<name>" --feature FEAT-…
```

This creates `project/stories/{id}-{slug}.md` and registers the story in the feature's body
**and** its frontmatter.

### 3. Write the acceptance criteria

These drive the tests, so write checkable statements, not activities.

- Bad: *Wire up the article fetcher*
- Good: *A De Tijd article whose browser session has expired falls back to its RSS summary,
  the page still renders, and `#harry` gets one message naming the source*

Every criterion must map to a scenario on the requirements page, if the feature has one. If
it maps to nothing, either the scenario is missing or the story is not justified — say which.

If the story touches anything outside the process, one criterion must be about what happens
when that thing is unavailable. See `.claude/rules/external-sources.md`.

### 4. Subtasks, only if the story has a natural order

```bash
uv run python project/board.py add-subtask STORY-… "<step>"
```

Skip this for most stories. A subtask list on a story that is one change is bookkeeping.

### 5. Commit the board

```bash
git add project/stories/{id}-{slug}.md project/features/FEAT-…-{slug}.md
git commit -m "STORY-…: create <slug> (under FEAT-…)"
```

Both files: the story, and the feature whose frontmatter now lists it.

### 6. Report

The story id, its criteria, and which scenario each one covers.
