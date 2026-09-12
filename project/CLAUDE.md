# The board — conventions

This directory is the record of *why*. `packages/` is the record of *what*. This file is
the source of truth for how the board works; `board.py` does the mechanical parts.

## Hierarchy

**Feature → Story → Subtask.** A feature on the full track has exactly one requirements
page and zero or more ADRs. A feature on the story track has neither.

- **Feature** — a capability, tracked end to end. Gets a branch and a worktree.
- **Story** — a unit of work under a feature. Its acceptance criteria drive the tests.
- **Subtask** — a step within a story, when the story has a natural order. Optional.
- **ADR** — a decision. Lives in a global log, linked from features, never deleted.

## Two tracks

Most work is small. Writing a 220-line requirements page for it is how a board stops
being used.

**Story track** — `board.py new-feature "…" --track story`. A feature stub with
acceptance criteria, one story, no requirements page, no ADR, no plan verification.

It qualifies when **all** of these hold:

- one module, or core alone — not both
- no change to the module contract (`registry.py`, `sdk.py`)
- no new credential, no new external service, no new scheduled job
- no new words a person reads — on the page, in Slack, in an alert
- under about 200 lines of diff
- an existing test file to extend

**Full track** — the default. Anything touching a boundary, a credential, an external
dependency, or a safety control. It gets the requirements page, ADRs where a future
reader would ask "why that way?", and `plan-verifier` before any code.

When in doubt, full. A story-track feature that grows past its test is re-opened on the
full track; that costs ten minutes, and a boundary changed without a decision record
costs an afternoon.

## Ids

`{TYPE}-{YYMMDD}-{6 hex}` — e.g. `FEAT-260912-a1b2c3`, `STORY-260912-d4e5f6`,
`ADR-260912-9f8e7d`.

The date sorts, the hash prevents collisions when two agents open work at the same
moment. **Never hand-write an id.** `board.py` allocates them.

## Files

| Type | Path |
|---|---|
| Feature | `features/FEAT-{YYMMDD}-{hash}-{slug}.md` |
| Story | `stories/STORY-{YYMMDD}-{hash}-{slug}.md` |
| Requirements | `requirements/FEAT-{YYMMDD}-{hash}.md` — full track only, one per feature |
| ADR | `decisions/ADR-{YYMMDD}-{hash}-{slug}.md` |

## Statuses

**A feature stores no status at all.** All three of its states are read from git:

| State | Is |
|---|---|
| `Backlog` | no `feat/` branch |
| `In Progress` | a `feat/` branch that has not merged |
| `Done` | a merge commit on `main` carrying the id |

`board.py set … status` on a feature refuses, because there is nothing to set. This
removes the board's two most likely lies — a feature with every box ticked whose status
was never flipped, and one marked In Progress that nobody ever branched — and it removes
a board commit per feature at each end.

The second half of that was not theoretical. `start` used to write the status, and it
wrote it into whichever checkout it ran in: the flip landed on `main` while the branch
carried on saying Backlog, and the two then collided at merge over a field neither of them
should have been storing.

**Stories still type a status.** Git knows nothing about a story — no branch, no merge
commit — so `Backlog` → `In Progress` → `Done` is set by hand there.

`make worktree` is how a feature leaves Backlog: it runs `board.py can-start` first, which
checks three things, cheapest first:

1. **The clarify gate.** A feature cannot leave Backlog while a `[NEEDS CLARIFICATION: …]`
   marker is live anywhere in its feature file or requirements page.
2. **The cap.** Three features in flight is the ceiling. `FORCE=1` gets past it and
   wants a note saying why.
3. **The overlap.** Two features that declare the same `touches:` area cannot both be
   In Progress. Two sessions must never own the same file.

An ADR left `Proposed` blocks any feature that links it. Decide, or drop the link.

## What a feature touches

```bash
python project/board.py touches FEAT-260912-a1b2c3 modules/news modules/digest
```

Names the areas the feature will edit — a module directory, `core`, `project`, `docs`.
It is what makes the overlap check possible, and what `make lanes` prints.

`make lanes` reads the board, the branches and the worktrees together, so it cannot
drift from them. It warns on an overlap, on a live feature with no branch, and on a
worktree directory git does not know about.

## Requirements page (full track)

Seven sections, every one read by somebody. A section that says "TBD" counts as missing.

- **Context & problem** — the problem in your own terms. Not the solution.
- **Goals** / **Non-goals** — the non-goals are what stop scope drift at close.
- **Scenarios** — Gherkin `Given / When / Then`. Each one testable. These become the
  acceptance criteria and then the tests. **Put the numbers on the scenario line that
  needs them** — a limit, a timeout, a page size, a path. There is no separate numbered
  requirements list to restate them in.
- **When it degrades** — what this does when its source is gone: what still renders, and
  what reaches you. Harry talks to things that break; this section is why the page
  survives them. "Nothing external" is a valid answer.
- **Out of scope** — read at close, by the verifier, to catch what got built anyway.
- **Open questions** — and inline `[NEEDS CLARIFICATION: …]` where it blocks design.
  Once answered, **fold the answer into the scenario it changed and delete the marker.**
  There is no transcript section: a resolved debate left on the page is noise the next
  agent will dutifully act on.
- **Links** — `[[ADR-…]]` wiki-style.

## ADR

MADR. Context & problem → Decision drivers → Considered options → Decision outcome →
Consequences.

**At least two options, genuinely considered.** The rejected one needs a fair statement
of its case — an ADR whose alternatives are strawmen is a rationalisation with a
template around it.

State the outcome actively: *"Claude has the LLM; Harry performs heuristic work only."* Not *"It was decided that…"*. Name the core
principle that drove it, if one did — Heuristic, Modular, Degrading, Alerting, Bounded,
Explainable.

The **Consequences** section names what this makes harder. That paragraph is the one
people come back for.

Reserve an ADR for a real boundary: a transport, a storage layout, a dependency pin, a
credential model. A decision nobody would contest does not need a record.

## Traceability

The spine. Every criterion can be followed to the test that proves it.

| When | Who | Produces |
|---|---|---|
| Feature opens (full track) | `plan-verifier` | scenario → story |
| Feature closes | `pre-close-verifier` | acceptance criterion → file → test |
| After merge | `/finish-feature` | the matrix, as a Reflection note on the feature |

A criterion with nothing to automate is marked `by inspection: <why>`, and the why has
to convince a skeptic. "Needs a paired tablet" convinces. "Hard to test" does not.

## Writing

The board is read by people who did not write it — you in three weeks, an agent with no
memory of the session that opened the item. Write for them.

**Say what it does for the person using Harry.** A title is a plain sentence about the
thing: *"The page still renders when a feed is dead"*, not *"Section-level degradation"*.
If a reader has to work out what the title refers to, it is a riddle, not a title.

**One idea per sentence. Short sentences.** The dense clause-after-clause style reads as
authoritative and costs the reader a second pass.

**Define a technical term the first time, in the same sentence, once.** File names,
function names and identifiers are welcome — they are how you find the code. The words
*around* them carry the meaning.

**Never** use these without translating them: seam, surface, invariant, orthogonal,
idempotent, composition root, resolver constraint, fence, tier, band.

**No aphorisms and no allusion.** *"Which is the point"*, *"and that is the finding"* —
these read as writing to be admired rather than to be understood. Say the thing instead.

**Lead with the answer.** What is broken, what this makes possible, what changes.

An acceptance criterion is *"When VRT NWS is unreachable, the page prints 'VRT NWS
unavailable' and the other sections still render"*. It is not *"The news section
degrades gracefully"*.

### The test before you commit

Read it back and ask: **would a product owner who has never opened this codebase
understand what this is and whether it worked?** If not, rewrite it.

Evidence keeps its precision. A measured number, a file path, a test name and a command
are the parts a reader can check. Shorten the prose around them, never the facts.

## Lessons

Every closed feature carries `## Lessons Learned`: what worked, what to do differently,
patterns to reuse *with file paths*. `scripts/query_lessons.py` mines this section and
`/new-feature` reads it as step 1.

Write the entry you would want to find. A lesson that says "be careful with async" helps
nobody. A lesson that says "De Tijd's storage state lasted 23 days; the alert fired on
day 24 from `modules/news/browser.py:88`" is worth the line.

## Commits

Board commits and code commits never mix — `.claude/rules/git-staging.md`.
Stage by name, never `git add .`.

| Kind | Format |
|---|---|
| Open | `FEAT-…: create <slug> — feature, requirements, ADR(s)` |
| Story | `STORY-…: create <slug> (under FEAT-…)` |
| ADR | `ADR-…: <title> (for FEAT-…)` |
| Close | `FEAT-…: done — <plain-language outcome>` |
| Code | `[STORY-…] impl: <what changed>` / `fix: <what>` |
| Merge | `merge feat/FEAT-…-slug (FEAT-…)`, always `--no-ff` |

**The merge commit is load-bearing.** It is what makes a feature Done, so `--no-ff` is
not a style preference — a fast-forward merge leaves the board reporting In Progress
forever.

Branch: `feat/FEAT-{YYMMDD}-{hash}-{slug}`, opened with `make worktree`. Creating it is
what puts the feature In Progress, so the branch name carrying the id is load-bearing.

A board id never appears in source code — `.claude/rules/code-has-no-board-refs.md`.
