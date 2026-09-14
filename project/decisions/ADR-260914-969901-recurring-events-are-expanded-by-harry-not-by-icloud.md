---
id: ADR-260914-969901
title: Recurring events are expanded by Harry, not by iCloud
status: Accepted
created: 2026-09-14
feature: FEAT-260912-e7ce2d
supersedes: ''
superseded_by: ''
---

# ADR-260914-969901 — Recurring events are expanded by Harry, not by iCloud

## Status

Accepted

Drives [[FEAT-260912-e7ce2d]].

## Context & problem

A weekly standup is the most ordinary thing on anybody's calendar, and it is the case iCloud
gets wrong.

CalDAV has a server-side answer for this. A client asks for a date range with
`expand=True`, and the server is supposed to return one object per occurrence, each with its
own start time. **iCloud accepts the request and ignores it.** A spike on 13 September 2026
searched a real account for a single day with `expand=True` and got back an event whose
`DTSTART` was 2026-09-07 — the start of the series, not the instance that falls on the day
asked for.

Two things follow, and the second is worse than the first. An agenda built on that prints
last Monday's date beside a meeting that is happening this morning. And a connector that
filters by date afterwards — the obvious defence — drops the event entirely, because the
date it carries is not today's. **The failure mode is a recurring meeting silently missing
from the page**, which looks exactly like a morning it was cancelled.

So the expansion has to happen here. The question is what does it.

## Decision drivers

- **Degrading.** Whatever goes wrong must be one event missing with a log line, not an
  agenda that is quietly incomplete.
- **Explainable.** When a meeting is on the page at the wrong time, somebody has to find out
  why in one file.
- **Heuristic.** Expansion is arithmetic on a rule — RFC 5545 says exactly what `RRULE`,
  `RDATE`, `EXDATE` and `RECURRENCE-ID` mean. There is no judgement in it, which is what
  makes it Harry's work at all.
- Correctness has a long tail. Moved instances, cancelled instances, timezone shifts across
  a DST boundary, and events that started before the window and run into it.

## Considered options

### Option 1: `recurring-ical-events`, a library that does exactly this

`recurring_ical_events.of(calendar).between(start, end)` returns the occurrences in a window,
with `RRULE`, `RDATE`, `EXDATE` and `RECURRENCE-ID` overrides already applied.

**For:** The long tail is the whole problem, and this library's entire purpose is that tail.
Moved instances (`RECURRENCE-ID`) and cancelled ones (`EXDATE`) are handled, which are
exactly the two cases a hand-rolled version gets wrong first and notices last — because both
produce a *plausible* agenda. It is already installed: `caldav` depends on it, so this is
declaring something Harry is running either way rather than adding a dependency. It builds on
`icalendar`, also already present.

**Against:** Harry does not own the rules. An occurrence that comes out wrong is debugged in
somebody else's code, and the fix is a version bump rather than an edit.

### Option 2: Read `RRULE` with `dateutil.rrule` and apply the exceptions by hand

`python-dateutil` is installed and its `rrulestr()` parses an `RRULE` into dates.

**For:** Harry owns the arithmetic, which is maybe forty lines for the common cases, and a
wrong occurrence is fixed in the file it came from. `dateutil` is a smaller surface than a
calendar library.

**Against:** `rrulestr` covers `RRULE` and nothing else. `EXDATE` is a second pass,
`RECURRENCE-ID` overrides are a third, and the two interact — a moved instance must suppress
the generated one, which means matching by original start time across a timezone conversion.
Every one of those bugs produces an agenda that looks right. This is the option that is
smaller to write and larger to own.

### Option 3: Trust `expand=True` and filter afterwards

**For:** No expansion code at all.

**Against:** Measured not to work. It is listed because it is what the CalDAV documentation
says to do, so somebody will propose it, and the answer is that the spike already tried it
against the real account.

## Decision outcome

**Harry expands recurring events with `recurring-ical-events`, declared explicitly in
`pyproject.toml`, and asks iCloud for the raw objects rather than for an expansion.**

`expand=True` is not passed at all. Asking for something the server silently ignores makes
the code read as though the server handles it, which is how the next person loses an
afternoon.

The dependency moves from transitive to declared. It arrives through `caldav` today, and
something Harry imports directly is something Harry should say it needs — otherwise a
`caldav` release that drops it breaks the agenda with nothing to point at.

The core principle is **Degrading**: the option was chosen for which failures it prevents,
and both of the ones it prevents — a moved instance duplicated, a cancelled instance shown —
produce a page that looks correct.

## Consequences

**What this makes harder.** Recurrence correctness is now somebody else's release cycle. A
bug in `recurring-ical-events` is a bug in Harry's agenda, and the fix is a pin bump rather
than an edit. Harry also carries a fourth calendar-shaped dependency — `caldav`,
`icalendar`, `recurring-ical-events`, `dateutil` — where somebody reading `pyproject.toml`
might reasonably expect one.

**What it makes easier.** The four cases that are easy to get wrong and hard to notice —
moved, cancelled, timezone-shifted, spanning — are handled by something whose tests cover
them. And the connector's own code is about turning an occurrence into `{at, title, where}`,
which is the part that is actually about Harry.

**What to watch.** If iCloud ever starts honouring `expand=True`, this stays as it is. Two
expansions, one of which only sometimes happens, is worse than one that always does.
