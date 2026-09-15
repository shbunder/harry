---
id: FEAT-260915-eb3236
title: The caller says which folder a document belongs in
track: story
created: 2026-09-15
touches: [connectors/remarkable, docs, tools/digest_build]
stories: [STORY-260915-edb7a7]
decisions: []
---

# FEAT-260915-eb3236 — The caller says which folder a document belongs in

## Summary

**The folder is the caller's business, not the tablet's.** It is configured on the reMarkable
connector today, so every document Harry pushes goes to one place — and the moment there is a
second thing to deliver, that is wrong. A weekly digest belongs beside the daily one, not in
it. A book Claude was asked to put on the tablet belongs somewhere else again.

The connector owns the tablet: the credential, the client, the two attempts, and the rule that
a push replaces the copy it supersedes. Where a given document belongs is something only the
thing producing it knows.

So `push` takes a folder, the connector's setting becomes the default for a caller that does
not care, and `digest_build` gains a `folder` of its own — which is where **🗞️ Daily**
belongs.

## Acceptance criteria

- [x] `push`, `push_bytes`, `push_markdown` and `documents` each take a folder, and use the connector's setting when the caller names none
- [x] A named folder is found if it is there and made at the top level if it is not, exactly as the configured one is
- [x] Two callers naming two folders get two folders, and neither sees the other's documents
- [x] The replace stays bounded to the folder the document was pushed to — a name that exists in another folder is untouched
- [x] `digest_build` has its own `folder` setting, defaulting to empty, which means "wherever the tablet connector puts things"
- [x] The answer says which folder a document went to, so a caller is never guessing
- [x] `docs/` and the runbook say the folder belongs to whoever is pushing, and that Harry only ever makes top-level folders

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260915-edb7a7]] — A push names its folder, and the connector supplies the default

## Lessons Learned

### What worked

**Moving the bound with the thing it bounds.** The delete had to follow the folder, not stay
on the configured one — otherwise a second caller's push retires a document of the same name
in somebody else's folder, on a token with no scopes. The test builds the real trap: the same
name in two folders, a push into one, and an assertion that the other survives.

**A cache keyed by the thing it is about.** `_folder_id` was one slot. Two callers in one
process would have shared it, and the second one's document would have landed in the first
one's folder — a bug that ships quietly and looks like a mystery a week later.

### What to do differently

**Widening a boundary orphans whatever was on the other side of it.** Giving the digest its
own folder made `remarkable_list_documents` blind to where the page goes — and its body still
said it sees "the folder Harry pushes into", which was true the day before. "Did the page
arrive?" then answers with an empty list and a body that says an empty list means not-yet.
**When a thing stops being singular, find everything that assumed it was one.**

**Write down why an asymmetry exists, in the code.** The listing takes a folder and the push
does not, because reading cannot do harm and pushing carries the delete. That is a good rule
and an obvious inconsistency, which is exactly the shape the next person "fixes". The reason
is in the tool's own docstring and a test asserts the sentence is still there.

### Patterns to reuse

- **`Tablet._where(client, folder)`** — find-or-make, always at the top level, remembered per
  name. The `put_folder` with no parent is the bound that keeps a caller-named folder beside
  a person's documents rather than inside them.
- **`test_the_replacement_looks_only_in_the_folder_just_pushed_to`** — the shape for any
  scoped destructive operation: put the same target in two scopes, act on one, assert the
  other is untouched.

## Notes

<!-- Appended by `board.py note`. -->
- **2026-09-15** — Reflection: pre-close verifier said REQUEST CHANGES on four Importants, all fixed. The sharpest was one this change created: giving the digest its own folder made remarkable_list_documents blind to where the page goes, while its body still told Claude it sees the folder Harry pushes into — so 'did the page arrive?' would answer with an empty list from the wrong folder. It takes a folder now; the push still does not, because reading a folder cannot do harm and pushing carries the delete, and that reason is written in the tool with a test asserting the sentence survives. Two controls could not fail: the Slack line naming the folder, and push_markdown's folder argument which had no caller and no test. Traceability 7/7 and 8/8. Eight controls probed by deletion; live tests pass against the tablet.

## Links

