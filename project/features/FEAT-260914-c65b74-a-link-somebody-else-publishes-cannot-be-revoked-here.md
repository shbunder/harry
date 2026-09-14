---
id: FEAT-260914-c65b74
title: A link somebody else publishes cannot be revoked here
track: story
created: 2026-09-14
touches: [connectors/icloud, docs]
stories: [STORY-260914-28f344]
decisions: []
---

# FEAT-260914-c65b74 — A link somebody else publishes cannot be revoked here

## Summary

Harry tells you to republish a broken calendar link in Outlook. For the link this was built
against, you cannot: it is published by an employer and the person using Harry does not own
the calendar. The advice sends them looking for a button that is not theirs.

**And it makes this the one credential in Harry that cannot be rotated.** The reMarkable
token is revoked by removing the device. The Apple app-specific password is revoked by
generating a new one. The De Tijd session is refreshed by logging in again. A published link
you do not own is revoked by somebody else, on their schedule, or never — so if it leaks,
it stays leaked.

That is a real property of the system and it is currently written down nowhere. Three
messages and three pages say the opposite.

## Acceptance criteria

- [ ] A broken link says to get a fresh one from whoever publishes that calendar, rather than assuming the reader can republish it
- [ ] The message still fits on one line in Slack and still names the link
- [ ] `CONNECTOR.md` says plainly that a link you do not own cannot be revoked by you, and what follows from that
- [ ] `docs/operating.md`'s credential table says which credentials can be rotated and which cannot
- [ ] A test asserts the messages do not tell the reader to do something only a calendar's owner can do

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260914-28f344]] — Say who can reissue a published link

## Notes

<!-- Appended by `board.py note`. -->

## Links

