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

- [ ] `push`, `push_bytes`, `push_markdown` and `documents` each take a folder, and use the connector's setting when the caller names none
- [ ] A named folder is found if it is there and made at the top level if it is not, exactly as the configured one is
- [ ] Two callers naming two folders get two folders, and neither sees the other's documents
- [ ] The replace stays bounded to the folder the document was pushed to — a name that exists in another folder is untouched
- [ ] `digest_build` has its own `folder` setting, defaulting to empty, which means "wherever the tablet connector puts things"
- [ ] The answer says which folder a document went to, so a caller is never guessing
- [ ] `docs/` and the runbook say the folder belongs to whoever is pushing, and that Harry only ever makes top-level folders

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260915-edb7a7]] — A push names its folder, and the connector supplies the default

## Notes

<!-- Appended by `board.py note`. -->

## Links

