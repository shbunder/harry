---
name: new-feature
description: Open a new feature on Harry's board — pick the track, write what it needs, declare what it touches, and open the branch in its own worktree. Use when the user describes a capability worth tracking. For a unit of work under an existing feature use /new-story; for a typo, skip tracking entirely.
---

Open a feature for: $ARGUMENTS

The board lives in `project/`. `project/CLAUDE.md` is the source of truth for its
conventions; `project/board.py` does the mechanical parts. Let the CLI allocate ids — never
hand-write one.

### 1. Start from a clean base

```bash
git status --porcelain
git switch main && git pull --ff-only 2>/dev/null || true
```

Uncommitted work must be committed or stashed first. Do not open a feature on a dirty tree.

### 2. Query the lessons — always, before anything else

```bash
make lessons Q="<keywords from the request>"
```

Read what comes back. If a past feature hit something relevant, it changes how you write
this one. Not optional, not a formality.

### 3. Check the lane is free

```bash
make lanes
```

Three features in flight is the cap. If three are already live, say so and ask which one to
finish first rather than opening a fourth.

### 4. Pick the track

`project/CLAUDE.md` § *Two tracks* has the test. **Story track** when all of these hold: one
module or core alone; no change to `registry.py` or `sdk.py`; no new credential, external
service or scheduled job; no new words a person reads; under about 200 lines of diff; an
existing test file to extend. **Full track** otherwise, and when in doubt.

Say which track you picked and which condition decided it.

```bash
# story track
uv run python project/board.py new-feature "<name>" --track story --touches <area> [<area> …]

# full track
uv run python project/board.py new-feature "<name>" --touches <area> [<area> …]
```

`--touches` names the areas this will edit — `modules/news`, `core`, `docs`. It is what
makes the overlap check possible. A feature with no `touches:` cannot be checked against
anything.

### 5. Write it

**Story track** — fill the feature's `## Summary` and `## Acceptance criteria`. Checkable
statements, not activities. Then one story (step 6). No requirements page, no ADR.

**Full track** — fill every section of `project/requirements/{id}.md`:

- **Context & problem** — the problem, in the user's terms. Not the solution.
- **Goals & non-goals** — the non-goals stop scope drift at close.
- **Scenarios** — Gherkin `Given/When/Then`, each testable. **Put the numbers here**, on the
  line that needs them. There is no separate requirements list.
- **When it degrades** — what still renders, what the reader sees instead, what reaches
  Slack. Write "nothing external" if it touches none. This section is why the morning page
  survives its sources; skipping it is the most common way a Harry feature ships broken.
- **Out of scope**
- **Open questions**

Before you write: **never ask the user what reading the code can answer.** Read first.

Where something is genuinely underspecified and the answer changes the design:

```
[NEEDS CLARIFICATION: does a digest with no reachable feeds still push a page?]
```

Then mirror the scenarios into the feature's `## Acceptance criteria` as `- [ ]` items.

### 6. Break it into stories

```bash
uv run python project/board.py new-story "<name>" --feature {id}
```

One story per coherent unit of work. Each needs `## Acceptance criteria` as checkable
statements — these drive the tests. Every scenario must map to at least one story. A
story-track feature gets exactly one.

### 7. Record the decisions (full track)

Any choice a future reader would ask "why that way?" about gets an ADR:

```bash
uv run python project/board.py new-adr "<title>" --feature {id}
```

Two options minimum, and say why the rejected one was rejected. Set `status: Accepted` once
the decision is actually made — `plan-verifier` blocks on a `Proposed` ADR.

Reserve it for a real boundary: a transport, a storage layout, a credential model, a
dependency pin on something reverse-engineered. Not for every choice.

### 8. Clarify gate

```bash
uv run python project/board.py clarifications {id}
```

Exits non-zero while any marker is live. Resolve each with the user, then **fold the answer
into the scenario it changed and delete the marker.** Do not park it in a transcript.

### 9. Commit the board

Board files only — never mixed with code. Stage by name.

```bash
git add project/features/{id}-{slug}.md project/requirements/{id}.md \
        project/stories/STORY-*.md project/decisions/ADR-*.md
git commit -m "{id}: create <slug> — feature, requirements, ADR(s)"
```

Drop the paths that do not exist on the story track — `git add` aborts the whole staging
operation when one pathspec matches nothing.

### 10. Branch, in its own worktree

This checkout is shared with other live sessions. A branch checked out here can be committed
onto and switched away underneath you, so feature work gets its own worktree.

```bash
make worktree FEAT={id} SLUG={slug}
uv run python project/board.py start {id}
```

`make worktree` seeds the gitignored files a fresh worktree needs, and gives it **its own
port and its own data directory** — two stacks sharing one SQLite file and one port is how a
second session kills the first.

`board.py start` is the gate: it refuses on a live clarification marker, past the cap of
three, or on an overlap with something already in flight. Read the refusal rather than
reaching for `--force`.

Everything after this step happens in the worktree. Check `git rev-parse --show-toplevel` if
unsure which tree you are in; `/finish-feature` merges from the main checkout.

### 11. Verify the plan (full track only)

Delegate to the `plan-verifier` subagent with the feature id. Act on any BLOCK before writing
code; report WARNs to the user with your recommendation.

The story track skips this. That is the point of it.

### 12. Report

Tell the user: the feature id, the track and why, the branch, the worktree's port, the story
list, any ADRs, the verifier's verdict, and what you propose to build first.
