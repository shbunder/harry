---
name: finish-feature
description: Close a feature — verify it, merge it, tick the board, and capture the lessons. Use when the work on a feat/ branch is believed complete. Do not use to merge an unverified branch.
---

Close the feature on the current branch (or: $ARGUMENTS).

### 1. Commit outstanding code

```bash
git status --porcelain
```

Stage by name, commit with `[STORY-…] impl: <what changed>`. Nothing uncommitted survives
into the next step.

### 2. Read what actually changed

```bash
FEAT=$(git rev-parse --abbrev-ref HEAD | grep -oE 'FEAT-[0-9]{6}-[0-9a-f]{6}')
git diff main...HEAD --stat
git log main..HEAD --oneline
```

Read the feature file, its requirements page if it has one, and every story. You are about to
claim this work is done — know what you are claiming.

### 3. Tick the board

```bash
uv run python project/board.py check $FEAT <n>              # acceptance criteria
uv run python project/board.py check STORY-… <n>
```

Tick only what is genuinely done. An unticked box here is information, not a failure — it
tells you what to do next.

### 4. Run the gate

```bash
make check
```

Format, lint, the board-reference guard, pyright, and the covered suite. It takes a lock; if
another session holds it, wait rather than working around it.

Everything must pass. Not "pass except for the flaky one" — `.claude/rules/debugging.md`.

If the diff touched a module that talks to something external, also run its live tests once,
by hand, and say what happened:

```bash
make test-live ARGS="tests/<module>"
```

### 5. Verify

Delegate to the `pre-close-verifier` subagent with the feature id.

Act on every **REQUEST CHANGES** finding before continuing. Fix them as `[STORY-…] fix:
<what>` commits on the branch. Report notes to the user.

### 6. Stragglers

```bash
git status --porcelain
grep -rn "NEEDS CLARIFICATION" project/
grep -rn "TODO\|FIXME" $(git diff main...HEAD --name-only | grep -E '\.py$') 2>/dev/null
uv run python scripts/check_no_board_refs.py --diff
```

All four must come back clean.

### 7. Capture the lessons

Add `## Lessons Learned` to the feature file, in three parts:

- **What worked** — a technique worth repeating
- **What to do differently** — the thing that cost time, and why
- **Patterns to reuse** — with file paths, so the next feature can find them

Write the entry you would want to find. `scripts/query_lessons.py` mines this section and
step 2 of `/new-feature` reads it. "Be careful with async" helps nobody. "De Tijd's storage
state lasted 23 days; the alert fired from `modules/news/browser.py:88`" is worth the line.

### 8. Merge — from the main checkout, and never fast-forward

The feature was built in `.claude/worktrees/<short-id>`. `git switch main` **fails there**:
main is already checked out in the primary tree, and git refuses to have one branch in two
worktrees. Merge from the main checkout instead — the worktree can stay open.

```bash
cd "$(git rev-parse --path-format=absolute --git-common-dir)/.."   # the main checkout
git switch main
git merge --no-ff feat/$FEAT-<slug> -m "merge feat/$FEAT-<slug> ($FEAT)"
```

**`--no-ff` is not a style preference here.** The merge commit is what makes the feature
Done — `board.py` derives the status by reading it. A fast-forward merge leaves the board
reporting In Progress forever.

Everything from here runs in the main checkout.

### 9. Confirm the board now says Done, and note the reflection

There is no status to flip. Check that the derivation worked, then record what closing found:

```bash
uv run python project/board.py list features --status Done | grep $FEAT
uv run python project/board.py note $FEAT "Reflection: <verifier verdict>; traceability <n>/<n>; degraded paths tested <…>; scope drift <…>"
git add project/features/$FEAT-<slug>.md
git commit -m "$FEAT: done — <one-line plain-language outcome>"
```

If the grep finds nothing, the merge was a fast-forward. Fix that before anything else.

### 10. Clean up

Order matters: `git branch -d` **fails while a worktree holds the branch**, so the worktree
goes first.

```bash
git -C .claude/worktrees/<short-id> status --porcelain   # empty = safe to remove
git worktree remove .claude/worktrees/<short-id>
git branch -d feat/$FEAT-<slug>
```

`git worktree remove` refuses if the worktree has uncommitted changes — that refusal is a
finding, not an obstacle, and step 1 was supposed to have committed them. Read the status
before reaching for `--force`; `--force` cannot tell your work from scaffolding.

```bash
make lanes
```

Should now show one fewer lane, and the area this feature held should be free.

### 11. Report

Give the user: what shipped, the verifier's verdict, the traceability count, any criterion
marked `by inspection` and why, which degraded paths were actually exercised, the lessons
captured, and what the next feature should probably be.
