---
id: FEAT-260915-257c60
title: A capability test never picks up this machine's .env.local
track: story
created: 2026-09-15
touches: [tests]
stories: [STORY-260915-a8264c]
decisions: []
---

# FEAT-260915-257c60 — A capability test never picks up this machine's .env.local

## Summary

**`make check` fails on this machine right now, and it is nobody's change that did it.**
Thirty-one of the forty-five news tests reach `tijd.be` and fail, because a gitignored
`.harry/connectors/news/.env.local` on this laptop adds De Tijd to the feed list and the
test fixtures copy the whole capability folder — `.env.local` included — into their
temporary root.

So the suite's result depends on an untracked file. Add a third feed on your machine and
thirty-one tests break; take it away and they pass. On a machine with no `.env.local` at
all, every one of them is green and nothing warns you. The gate is the only thing between
a change and `main`, and right now it says different things to different people.

It also means tests reach the network, which is the one thing `.claude/rules/external-sources.md`
says they must never do — "a suite that reaches the network is a suite that fails on a
train".

## Acceptance criteria

- [ ] A capability test's temporary root holds the declaration and the committed `.env`, and never a `.env.local` from the working tree
- [ ] `make check` passes with a `.env.local` present in every capability folder, and passes with none
- [ ] `tests/test_news_connector.py` passes on this machine, where `.harry/connectors/news/.env.local` names a third feed
- [ ] One helper does the copying, and a test fails if any test file copies `.harry/` some other way
- [ ] The helper has a test that gives it a source folder containing `.env.local` and asserts the copy has none
- [ ] `__pycache__` does not travel either — a stale `.pyc` from the working tree is the same class of leak

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260915-a8264c]] — One helper copies a capability, and it leaves the machine behind

## Notes

<!-- Appended by `board.py note`. -->

## Links

