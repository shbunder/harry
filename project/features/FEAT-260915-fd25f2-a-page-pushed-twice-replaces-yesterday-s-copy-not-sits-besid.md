---
id: FEAT-260915-fd25f2
title: A page pushed twice replaces yesterday's copy, not sits beside it
track: story
created: 2026-09-15
touches: [connectors/remarkable, docs]
stories: [STORY-260915-1c6e8e]
decisions: []
---

# FEAT-260915-fd25f2 — A page pushed twice replaces yesterday's copy, not sits beside it

## Summary

`push(path, name)` creates a document every time. Pushing the morning page twice on the same
day leaves **two documents both called `2026-09-15`** in the folder, and the tablet gives no
hint which is the newer one. Found by pushing today's page twice while iterating on its
design; the listing came back with the name twice and no timestamps.

That is fine exactly once a day and wrong the moment anything retries, re-renders or gets
built again after a fix — which is every morning something goes slightly wrong. The reader
opens one of two identical-looking files and cannot tell whether they are reading the page
that has the correction in it.

Harry has no delete today, deliberately: the device token grants complete read and write
over every document on the tablet, and a connector that can remove things is a connector
that can remove the wrong thing. So the shape to find is "put this content at this name",
not "list, delete, push".

## Acceptance criteria

- [x] Pushing the same name twice leaves one document in the folder, carrying the second push's content
- [x] The first push of a name still creates it
- [x] A push that replaces says so in the log, naming the document
- [x] Nothing gains the ability to delete a document the caller did not name — a test asserts the connector has no code path that removes anything else
- [x] `docs/` says what happens on a second push, beside the rest of the tablet connector
- [x] The push tool's own declaration says it too — `destructiveHint: true`, and a body that no longer claims nothing is ever deleted
- [x] The runbook says what to do about the duplicates already on the tablet, since nothing here removes them

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260915-1c6e8e]] — A push replaces the copy it supersedes, and removes nothing else

## Lessons Learned

### What worked

**Parsing the module instead of grepping it.** `test_the_one_call_that_removes_anything_lives_in_one_place`
walks the AST, counts the calls whose attribute is `delete`, and names the function holding
the one that exists. A string search would pass on a second delete added three lines lower.
That is the right shape for any "this may happen in exactly one place" rule.

**Deleting each bound in turn, and counting.** The id bound took eight tests with it, the
name bound two, the type bound two, the folder bound four. On the one call in Harry that can
remove something from a device whose token has no scopes, that was worth the ten minutes.

### What to do differently

**A tool's declaration is part of the change, not documentation of it.** `destructiveHint`
stayed `false` after a push started removing things, and the body still told Claude that
pushing the same name twice gives two documents. `destructiveHint` is the one signal a client
uses to decide whether to ask a person first. **When behaviour changes, the frontmatter and
the body are the first two files to open, not the last.**

**A test that asserts the old truth will defend it.** `assert push.destructive_hint is False,
'it adds; adding is not destroying'` was written when it was true, and then certified the
wrong answer for the whole of this branch. When you change what something does, grep the
suite for the assertion that used to be right.

**Fail one call, not every call.** The ordering test — which the story called "the whole
safety argument" — set `fail_for = 99`, so the listing failed too and `_retire` bailed into
its own `except`. It passed against retire-then-push. A degraded-path test has to fail
exactly the thing whose failure it is about.

**A broad `except` catches the subclass you were relying on being different.** `ExpiredToken`
is a `RemarkableAPIError`, so one catch sent somebody to tidy a folder when the answer was to
pair the machine again.

### Patterns to reuse

- **`Tablet._retire`** (`.harry/connectors/remarkable/connector.py`) — do the additive thing
  first, then the removal, and say in the docstring why that order is the safety argument.
  The worst a failure can then do is leave the old state, which is visible.
- **`test_a_failed_removal_does_not_silence_the_next_failed_push`** — the way to prove two
  alert keys are separate is to make both faults happen and count what reached the sink. A
  grep for `key='retire'` asserts a setting.
- **The stand-in shape check** (`test_the_stand_in_has_the_same_shape_as_the_real_client`) —
  when a hand-written double gains a method, that loop is the second file to edit. Every
  proof written against the double is about a client that may not exist.

## Notes

<!-- Appended by `board.py note`. -->

## Links

