---
id: FEAT-260915-257c60
title: A capability test never picks up this machine's .env.local
track: story
created: 2026-09-15
touches: [.claude/skills, CLAUDE.md, tests]
stories: [STORY-260915-a8264c]
decisions: []
---

# FEAT-260915-257c60 — A capability test never picks up this machine's .env.local

## Summary

**`make check` fails on this machine right now, and it is nobody's change that did it.**
Fifty-six tests fail — thirty-seven of the fifty-one in `test_news_connector.py` and
nineteen of the twenty-four in `test_news_tools.py` — because a gitignored
`.harry/connectors/news/.env.local` on this laptop adds De Tijd to the feed list and the
test fixtures copy the whole capability folder, `.env.local` included, into their temporary
root. The connector then asks for a feed no fixture mocks.

So the suite's result depends on an untracked file. Add a third feed on your machine and
thirty-one tests break; take it away and they pass. On a machine with no `.env.local` at
all, every one of them is green and nothing warns you. The gate is the only thing between
a change and `main`, and right now it says different things to different people.

`respx` refuses the unmocked request, so nothing actually leaves the machine — the damage is
to what the gate *means*, not to the rule in `.claude/rules/external-sources.md`. But it is
the same defect one step earlier: a test whose behaviour depends on what is sitting in the
working tree is a test that would reach the network the moment the interception went away.

## Acceptance criteria

- [x] A capability test's temporary root holds the declaration and the committed `.env`, and never a `.env.local` from the working tree
- [x] `make check` passes with a `.env.local` present in every capability folder, and passes with none — `by inspection: the suite cannot run itself three ways. Verified by copying the tree to a scratch directory and running pytest with a .env.local planted in all twelve capability folders (news pointed at a third feed, weather at Reykjavik), with the four this machine really has, and with none: 670 passed each time`
- [x] `tests/test_news_connector.py` passes on this machine, where `.harry/connectors/news/.env.local` names a third feed — 51 of 51, where it was 14 of 51 before
- [x] One helper does the copying, and a test fails if any test file copies `.harry/` some other way
- [x] The helper has a test that gives it a source folder containing `.env.local` and asserts the copy has none
- [x] `__pycache__` does not travel either — a stale `.pyc` from the working tree is the same class of leak

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260915-a8264c]] — One helper copies a capability, and it leaves the machine behind

## Lessons Learned

### What worked

**Running the suite three ways, in a scratch copy of the tree.** A `.env.local` planted in
all twelve capability folders, then only the four this machine really has, then none: 670
passed each time. That is the whole claim of this feature, and it is not a thing any single
test can assert — the suite cannot run itself. Copying the tree to a scratch directory made
it a five-minute check instead of a belief.

**Deleting the control and counting.** Turning the ignore list into a no-op put the number
on the board: fifty-six failures, thirty-seven of them in `test_news_connector.py`. It also
corrected the story I had been telling — `respx` refuses the unmocked request, so nothing
ever reached `tijd.be`. The bug was real and the number was wrong, and only running it said
which.

### What to do differently

**Re-measure a number before you write it down twice.** "Thirty-one of forty-five" was
measured once, before an unrelated feature added six tests to that file, and then copied
into a docstring, a `CLAUDE.md` paragraph and a commit message. All three were wrong by the
time they were written. A number that appears in prose has a shelf life.

**A guard that matches one spelling guards one spelling.** The first version looked for
`copytree(REPO / '.harry' / …)` literally. Four ways round it, all plausible: assign the
source to a variable, rename the constant, build the path inline, reach for `copy2`. Parsing
the file and tainting any name assigned from an expression mentioning `.harry` catches all
four, and lets the helper itself through by construction rather than by an exclusion list.

**An exclusion needs a reason you have tested.** The first guard excluded its own file
"because the pattern is written down here". It is not — the literal is written `copytree\(`,
which does not match `copytree(`. The exclusion protected nothing and made the one file most
likely to grow a second copier the only one nobody scanned.

### Patterns to reuse

- **`tests/capability_copy.py`** — the one door into `.harry/` for a test. Any new connector
  or tool test copies its folder with `copy_capability`, and `new-connector`/`new-tool` now
  say so.
- **`tests/test_capability_copy.py::_copies_out_of_harry`** — AST rather than regex when the
  rule is about *where a path came from* rather than how it was typed. Taint the names
  assigned from the interesting expression, then check each call's first argument for a
  tainted name or the literal. Reusable for any "nothing must reach X except through Y".
- **`::test_a_local_env_beside_a_capability_never_reaches_a_loaded_test`** — stage a real
  capability, plant the bad file beside the staged copy, then take the copy a test would
  take and load it. Asserting against the real `.harry/` tree instead would pass on every
  machine except the one where the bug lives, which is the trap this whole feature is about.

## Notes

<!-- Appended by `board.py note`. -->
- **2026-09-15** — Reflection: pre-close verifier said REQUEST CHANGES on four findings, all fixed on the branch — a guard that matched one spelling of the mistake rather than the mistake, a '*.pyc' pattern nothing exercised, a self-exclusion whose stated reason was false, and a failure count that had gone stale in three places. Traceability 6/6 on the feature and 6/6 on the story, two marked by inspection with the command and the result because the suite cannot run itself three ways. Verified by running the whole suite with a .env.local in all twelve capability folders, in the four this machine has, and in none: 670 passed each time. Scope: one line each added to the new-connector and new-tool skills, since the ninth call site is most likely to be written by somebody following one.

## Links

