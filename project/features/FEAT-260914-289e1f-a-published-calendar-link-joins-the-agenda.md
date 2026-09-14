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

- [x] A published `.ics` link named in `SUBSCRIBED` contributes its events to the same day
- [x] Repeating meetings and overridden instances from a link are handled by the same expansion
- [x] More than one link works, each fetched once, at most once every 5 minutes
- [x] A link that cannot be read fails the whole read rather than returning a partial day
- [x] A link answering HTML rather than a calendar says so
- [x] Failures name the label, never the URL, and reach Slack once per link per 24 hours
- [x] The URL appears in no log, no exception, no exception **chain** and no Slack message, asserted through the MCP tool call that logs the traceback
- [x] One event inside a link that will not parse costs that event, not the day — the one deliberate exception, with the reason written down
- [x] A malformed `SUBSCRIBED` entry costs one link and is logged
- [x] Empty — the default — changes nothing and fetches nothing
- [x] Tests run against a fixture shaped like the measured Outlook feed, with invented events
- [x] The runbook and docs say the link is a credential and how to revoke it

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260914-0297e2]] — A published link's events are in the same day

## Notes

<!-- Appended by `board.py note`. -->

## Links

- Requirements: [[FEAT-260914-289e1f]]
- Decision: [[ADR-260914-98cc64]] — A published calendar link is read by the calendar connector, not a new one


## Lessons Learned

### What worked

**Fetching the real link before designing against it.** One request settled the shape:
189 KB, `Microsoft Exchange Server 2010`, 234 events, **40 series, 76 `RECURRENCE-ID`
overrides, 2 `EXDATE`s**, 38 all-day. Running it through the existing expansion produced a
sensible week before a line of this feature was written, so "does the recurrence code handle
Outlook" was never a question anybody had to hold open.

It also retired an assumption. The handmade fixtures from the calendar feature guessed that a
real server sends `RECURRENCE-ID` overrides as separate `VEVENT`s in one document. Seventy-six
of them, measured. `moved-instance.ics` was right, and now it is known to be right.

**Deciding the tool surface first, and letting it pick the architecture.** The rule said two
connectors; the tool surface said one. The deciding argument was not tidiness but the failure
each produces: two tools that both answer "what is on today" means the model sometimes gets
half a day and reports it confidently. The ADR names the rule it bends and the condition for
splitting later, rather than pretending there was no tension.

### What to do differently

**A secret in a URL defeats protections written for a secret in a header.** Three separate
things leaked it, and each one had to be found on its own:

- `httpx` logs every request line, URL included, at `INFO`. `HARRY_LOG_LEVEL=INFO` would
  have written the link into the log on every successful read.
- `httpx` also puts the URL inside `HTTPStatusError`'s message, so `raise … from error` hands
  it to anything formatting a traceback — and FastMCP does that at `ERROR` for a failing tool
  call, whatever the log level is. **This one leaked on exactly the failure the feature is
  designed around**, and it survived the first fix.
- `Context.redact` replaced the whole config value, so a message quoting one link out of two
  matched nothing at all.

**Ask what shape the credential is, not just where it is stored.** Every control here was
written for `Authorization: Bearer …`.

**A test that calls the function underneath cannot see what the layer above logs.** The
no-leak test called the connector directly and asserted on `str(error)`. Both gaps were
invisible: production reaches this through MCP, and MCP is what logs the chain. It was green
while the property was false, which is worse than no test.

**A helper named `a_context` already existed in that file.** Appending a second definition
silently replaced it and broke ten unrelated tests. Grep before you add a module-level name
to a file you did not write.

**`respx.get(...)` in an assertion registers a route.** Calling it a second time to read
`call_count` shadowed the mock and turned a cached body into an empty string, which surfaced
three tests later as a parse error. Capture the route once.

### Patterns to reuse

- **`_parts_of()` in `src/harry/registry.py`** — a compound secret setting is scrubbed piece
  by piece as well as whole, leaving the labels alone so messages stay readable.
- **`TALKATIVE` in `src/harry/main.py`** — HTTP clients held at `WARNING` because one of
  Harry's credentials is a URL. It protects every connector, not just this one.
- **`raise … from None` at `.harry/connectors/icloud/connector.py`** — with the reason on the
  line above, because the next reader's instinct will be to restore the cause.
- **`test_the_link_does_not_reach_the_log_through_a_failing_tool_call`** — asserts a secret's
  absence through the MCP call that does the logging, rather than at the function beneath it.
- **`tests/fixtures/icloud/README.md`** — says which fixture was measured, what was measured
  about it, and what was invented instead, for a document whose real contents could not be
  committed.
