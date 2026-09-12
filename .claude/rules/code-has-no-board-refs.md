# Code says what it does; the board says why

A `FEAT-…`, `STORY-…` or `ADR-…` never appears in source code.

## Never

- `# Added for FEAT-260912-a1b2c3` on any line of Python, YAML, TOML, CSS or shell
- A docstring that cites a story instead of explaining the function
- A test named after the item that requested it
- A `TODO` pointing at a board id

## Always

- Say the reason in the comment itself. Not *"see ADR-260912-9f8e7d"* but *"APScheduler
  rather than cron: the container has no cron daemon and the job needs the app's config"*
- Put the pointer the other way round. The board links to the code; the code does not link
  back
- Let git carry the trail. `git log -S<what changed>` finds the commit, whose message
  carries the id

## Why

A board id in a comment is a pointer into a file the reader has to go and open, and the
reason they are reading this line is that they want it *now*. It goes stale the moment the
feature is renamed or superseded. And it is never actually the reason the line exists — the
reason is a sentence, and writing the sentence is the work the reference avoided.

The commit message is the right place for the id: it is attached to the change rather than
to the code, so it does not rot as the code moves.

## Common rationalizations

| Excuse | Reality |
|---|---|
| "It's traceability" | Traceability runs board → test, and the verifier builds it at close. |
| "The reason is long" | Then it is a docstring, or a doc page. Still not an id. |
| "Someone will want the context" | They will want the reason. Write the reason. |

## What the guard actually checks

`scripts/check_no_board_refs.py` flags an id **only when it resolves to a real board
item** — a file under `project/features/`, `project/stories/` or `project/decisions/`.

An id-shaped string that matches nothing on the board is test data, not a reference.
That distinction is not a loophole, it is what makes the board's own test suite
writable: `tests/test_board.py` is full of example ids, and a guard that matched on
shape alone would have failed on this repo's first commit while looking correct on
every run before it.

`project/`, `docs/`, `.claude/` and the two top-level markdown files are exempt. They
are the record of *why* and they cite ids by design.

## Enforcement

`scripts/check_no_board_refs.py`, run by `make lint` and by the suite. Severity:
**Important** — it fails the gate.
