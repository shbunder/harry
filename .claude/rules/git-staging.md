# Every file in a commit is there because you decided it should be

Two rules, one subject: what goes into a commit, and what a commit is about.

## Never

- `git add .`, `git add -A`, `git add --all`, `git commit -a`
- Staging a directory to "pick up the rest of my changes"
- One commit that touches both `project/**` and any source file
- Amending a code commit to "also tick the box"
- `git merge` without `--no-ff` on a feature branch

## Always

- `git add <path> <path> …`, naming each file
- `git status` before staging and `git diff --cached` before committing
- **Check what actually landed.** `git add` aborts the whole staging operation when one
  pathspec matches nothing, so the commit that follows can contain something quite
  different from what its message describes
- Two commits for board and code: board first when opening work, board last when closing
- Board format: `FEAT-…: create <slug> — feature, requirements, ADR(s)` or
  `FEAT-…: done — <plain-language outcome>`. Code format: `[STORY-…] impl: <what changed>`
- Merge format: `merge feat/FEAT-…-slug (FEAT-…)`, with `--no-ff`

## Why

Blanket staging is how a `.env.local`, a saved browser session, a stray debug print, or
half an unrelated experiment ends up in history. In this repo one of those is a credential that
grants total read and write access to a tablet. Naming files forces you to look at what
you are shipping.

`project/` is the record of *why* and everything else is the record of *what*. Six months
from now somebody runs `git log -- project/` to reconstruct how a decision was reached and
`git log -- packages/` to reconstruct how it was built. A mixed commit makes both
unreadable, and makes `git revert` on a bad implementation quietly revert the requirement
that justified it.

`--no-ff` is load-bearing here rather than stylistic. **The merge commit is what makes a
feature Done** — `board.py` derives the status from it. A fast-forward merge leaves the
board reporting In Progress forever, and nobody notices until the lane will not clear.

## Common rationalizations

| Excuse | Reality |
|---|---|
| "It's all one feature anyway" | Then naming five files costs five seconds. |
| "`.gitignore` covers the risky stuff" | It covers what you predicted. Never what you didn't. |
| "I'll fix it in the next commit" | A commit that shipped two concerns stays two concerns forever. |
| "The status flip *is* part of finishing" | There is no status flip. The merge commit is the status. |
| "The commit succeeded, so it staged" | Exit status is not content. Read `git show --stat`. |
| "Fast-forward is a cleaner history" | It is a history in which nothing was ever finished. |

## Exceptions

None.

## Enforcement

`.claude/agents/pre-close-verifier.md` inspects `git diff main...HEAD` per commit and flags
any that spans both trees or unrelated concerns. Severity: **Important**. `/finish-feature`
keeps the merge and the board note as separate commits.
