---
id: FEAT-260912-e7ce2d
title: The page knows what today looks like
track: full
created: 2026-09-12
touches: [connectors/icloud, docs, tools/icloud]
stories: [STORY-260914-f7a91e, STORY-260914-2245c2]
decisions: [ADR-260914-1d19b8, ADR-260914-969901]
---

# FEAT-260912-e7ce2d — The page knows what today looks like

## Summary

Today's calendar and to-dos, from iCloud over CalDAV. Apple's Reminders support is the flakiest dependency in the plan, so the to-do half has to be able to fail on its own without taking the agenda with it.

## Acceptance criteria

<!-- One box per scenario. These are what the pre-close-verifier builds its
     traceability matrix from. -->

- [ ] Today's events come back as `{at, title, where}`, earliest first
- [ ] A recurring event shows today's instance at today's time, not the series start
- [ ] A moved instance comes back once at its new time; a cancelled one is not there at all
- [ ] An all-day event reads `at: "all day"` and sorts before every timed event
- [ ] Times are local — an event stored 07:30Z reads "09:30" in Europe/Brussels
- [ ] A free day is an empty list, not an error
- [ ] Which calendars are read is configurable, and leaving it empty means all of them
- [ ] A calendar name that matches nothing is logged and skipped; one malformed event is skipped too
- [ ] iCloud unreachable raises after 15 seconds, the page says "Agenda unavailable", and the rest renders
- [ ] A revoked password says to make a new one at account.apple.com
- [ ] Either failure puts one line in Slack, once per 24 hours, carrying no password, URL or response body
- [ ] The app-specific password reaches no log, no exception and no Slack message
- [ ] With no credential the connector and its tool are skipped, saying what is missing, and the rest of Harry loads
- [ ] `icloud_list_events(day)` answers for today or a named day, is readOnlyHint true, defers, and is in `provides:`
- [ ] Reminders are not read, and the reason is recorded rather than left as an empty section
- [ ] Every parsing test uses an iCalendar document in tests/fixtures/icloud/, and its README says they are handmade and why; the one live test is never in the gate
- [ ] docs/sources.md and the runbook say where the password comes from and what happens when it lapses

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260914-f7a91e]] — Harry can read today's agenda out of iCloud
- [ ] [[STORY-260914-2245c2]] — Claude can ask what a day looks like

## Notes

<!-- Appended by `board.py note`. -->
- **2026-09-13** — iCloud spike, three results. (1) CONNECTION PASS: app-specific password authenticates against https://caldav.icloud.com, 17 calendars listed. (2) REMINDERS FAIL: 14 VTODO items come back and every single one is an Apple upgrade placeholder - 'De maker van deze lijst heeft deze herinneringen bijgewerkt' / 'Waar zijn mij herinneringen?' - across 17 lists. Zero real reminders. These lists have been upgraded to a format CalDAV does not expose. The to-do section must move source or drop; it blocks nothing else. (3) RECURRENCE FAIL: searching today with expand=True returned one event whose DTSTART is 2026-09-07, i.e. the series start rather than today's instance. The agenda needs instance times, so this connector has to expand client-side or read RRULE itself. Budget for that; it is not a one-liner.
- **2026-09-13** — How the reminder failure was nearly missed, worth keeping: the spike first printed PASS because it counted VTODO items without looking at them. Fourteen items came back, so it said Reminders work. They were all placeholders. A count is not a finding - the spike now classifies and fails, which is the same lesson as .claude/rules/inert-controls.md in a place nobody thought to apply it.

## Links

- Requirements: [[FEAT-260912-e7ce2d]]
- Decision: [[ADR-260914-1d19b8]] — Harry does not read Reminders, because CalDAV cannot see them
- Decision: [[ADR-260914-969901]] — Recurring events are expanded by Harry, not by iCloud

