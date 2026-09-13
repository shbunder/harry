---
id: FEAT-260913-ebf402
title: The board CLI can undo and move, not only create
track: story
created: 2026-09-13
touches: [project/board.py]
stories: []
decisions: []
---

# FEAT-260913-ebf402 — The board CLI can undo and move, not only create

## Summary

Three rough edges found by using the board on a real feature. Every one forced a hand-edit of a markdown file, which is exactly the drift the CLI exists to prevent — and each hand-edit is a chance to leave the body and the frontmatter disagreeing.

Small, and worth doing before the next feature rather than after the tenth.

## Acceptance criteria

<!-- One box per scenario. These are what the pre-close-verifier builds its
     traceability matrix from. -->

- [ ] Ticking a box prints the criterion it ticked, for every box — today one preceded by a blank line prints nothing, because the regex `^(\s*)- \[( |x)\] ` lets `\s` eat the newline and the match starts on the blank line. `[ \t]*` fixes it
- [ ] A box can be unticked. `check --off`, or an `uncheck`. Ticking the wrong one is a two-character mistake and today it costs a hand-edit
- [ ] A story can be moved between features in one command, updating its `feature:`, both features' `stories:` lists and both bodies together — today that is four edits by hand and any one of them can be forgotten
- [ ] Each of the three has a test that fails without the fix

## Stories

<!-- Maintained by `board.py new-story`. -->

## Notes

<!-- Appended by `board.py note`. -->
- **2026-09-13** — All three were hit while opening and closing FEAT-260912-cfeb21. The blank-line regex bug is cosmetic but it masks a mis-tick; the missing uncheck was needed within an hour of the first one; the missing move was needed when the tunnel story was split out.

## Links

