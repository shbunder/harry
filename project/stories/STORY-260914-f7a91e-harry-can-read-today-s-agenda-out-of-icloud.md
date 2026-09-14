---
id: STORY-260914-f7a91e
title: Harry can read today's agenda out of iCloud
feature: FEAT-260912-e7ce2d
status: Done
created: 2026-09-14
---

# STORY-260914-f7a91e — Harry can read today's agenda out of iCloud

Part of [[FEAT-260912-e7ce2d]].

## Description

The connector: the credential, the CalDAV client, the recurrence expansion and the runbook.

This is the folder the Apple app-specific password goes in, so it comes first — nothing else
in this feature can be configured until it exists.

The recurrence work is here rather than in a later story because it is not a refinement.
iCloud returns the series start for a recurring event, so without expansion a weekly standup
is either on the page at last week's time or missing from it entirely, and the second one
looks exactly like a meeting that was cancelled.

## Acceptance criteria

- [x] Today's timed events come back as {at, title, where}, earliest first
- [x] A weekly event whose series starts 2026-09-07 shows at 09:30 on 2026-09-14, not on the 7th
- [x] An instance moved to 11:00 comes back once, at 11:00
- [x] An instance that was deleted is not in the day at all
- [x] An all-day event comes back as {at: "all day"} and sorts before every timed event
- [x] An event stored as 2026-09-14T07:30:00Z reads as "09:30" under TIMEZONE Europe/Brussels
- [x] A day with nothing on it is an empty list, not an error — a free day is information
- [x] CALENDARS names which calendars are read; empty means all of them
- [x] A name in CALENDARS matching no calendar is logged and skipped, and the others still load
- [x] One malformed event is skipped with a log line and the rest of the day still returns
- [x] iCloud unreachable or slow raises after 15 seconds, so the page prints "Agenda unavailable"
- [x] A 401 says the password was refused and to make a new one at account.apple.com
- [x] Either failure puts one line in Slack, once per 24 hours, with no password, no URL and nothing from the response
- [x] The app-specific password reaches no log line, no exception message and no Slack message — asserted against a planted value
- [x] With no credential the connector is skipped naming both missing settings, and the rest of Harry loads
- [x] `expand=True` is not passed to iCloud at all, because it is accepted and ignored
- [x] Every parsing test runs against an iCalendar document in tests/fixtures/icloud/, never a live account — the documents are written by hand against RFC 5545, because no account was configured when they were written, and the README says so and says what they therefore cannot prove
- [x] A live test reads a real account, marked live and never in the gate
- [x] docs/sources.md and the runbook name account.apple.com and say what a lapsed password looks like — both greppable, and tested
- [x] Those pages read clearly to somebody doing the renewal at 07:00 — by inspection: no automation can judge that, and it is the half that matters

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

