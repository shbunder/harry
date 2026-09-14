---
id: FEAT-260914-289e1f
title: A published calendar link joins the agenda
track: full
created: 2026-09-14
touches: [connectors/icloud, core, docs]
stories: [STORY-260914-0297e2]
decisions: [ADR-260914-98cc64]
---

# FEAT-260914-289e1f — A published calendar link joins the agenda

## Summary

Part of the calendar is an Outlook link rather than an iCloud account. Harry reads it into
the same agenda, so the morning page shows the whole day rather than the half of it that
lives at Apple.

The link is a credential — the random segment in the URL is the password — so it is declared
secret, never printed, and revoked by republishing in Outlook.

## Acceptance criteria

- [ ] A published `.ics` link named in `SUBSCRIBED` contributes its events to the same day
- [ ] Repeating meetings and overridden instances from a link are handled by the same expansion
- [ ] More than one link works, each fetched once, at most once every 5 minutes
- [ ] A link that cannot be read fails the whole read rather than returning a partial day
- [ ] A link answering HTML rather than a calendar says so
- [ ] Failures name the label, never the URL, and reach Slack once per link per 24 hours
- [ ] The URL appears in no log, no exception, no exception **chain** and no Slack message, asserted through the MCP tool call that logs the traceback
- [ ] One event inside a link that will not parse costs that event, not the day — the one deliberate exception, with the reason written down
- [ ] A malformed `SUBSCRIBED` entry costs one link and is logged
- [ ] Empty — the default — changes nothing and fetches nothing
- [ ] Tests run against a fixture shaped like the measured Outlook feed, with invented events
- [ ] The runbook and docs say the link is a credential and how to revoke it

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260914-0297e2]] — A published link's events are in the same day

## Notes

<!-- Appended by `board.py note`. -->

## Links

- Requirements: [[FEAT-260914-289e1f]]
- Decision: [[ADR-260914-98cc64]] — A published calendar link is read by the calendar connector, not a new one

