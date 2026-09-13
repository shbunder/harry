---
id: FEAT-260912-e7ce2d
title: The page knows what today looks like
track: full
created: 2026-09-12
touches: [connectors/icloud]
stories: []
decisions: []
---

# FEAT-260912-e7ce2d — The page knows what today looks like

## Summary

Today's calendar and to-dos, from iCloud over CalDAV. Apple's Reminders support is the flakiest dependency in the plan, so the to-do half has to be able to fail on its own without taking the agenda with it.

## Acceptance criteria

<!-- One box per scenario. These are what the pre-close-verifier builds its
     traceability matrix from. -->

- [ ] Today's events come back from iCloud with their time, title and location
- [ ] To-dos due today come back as well, or that section alone says unavailable and the agenda still renders
- [ ] Which calendars are read is configurable, and leaving it empty means all of them
- [ ] When iCloud cannot be reached the agenda says unavailable and the rest of the page renders
- [ ] The app-specific password never reaches a log, a span, or an error message

## Stories

<!-- Maintained by `board.py new-story`. -->

## Notes

<!-- Appended by `board.py note`. -->
- **2026-09-13** — iCloud spike, three results. (1) CONNECTION PASS: app-specific password authenticates against https://caldav.icloud.com, 17 calendars listed. (2) REMINDERS FAIL: 14 VTODO items come back and every single one is an Apple upgrade placeholder - 'De maker van deze lijst heeft deze herinneringen bijgewerkt' / 'Waar zijn mij herinneringen?' - across 17 lists. Zero real reminders. These lists have been upgraded to a format CalDAV does not expose. The to-do section must move source or drop; it blocks nothing else. (3) RECURRENCE FAIL: searching today with expand=True returned one event whose DTSTART is 2026-09-07, i.e. the series start rather than today's instance. The agenda needs instance times, so this connector has to expand client-side or read RRULE itself. Budget for that; it is not a one-liner.
- **2026-09-13** — How the reminder failure was nearly missed, worth keeping: the spike first printed PASS because it counted VTODO items without looking at them. Fourteen items came back, so it said Reminders work. They were all placeholders. A count is not a finding - the spike now classifies and fails, which is the same lesson as .claude/rules/inert-controls.md in a place nobody thought to apply it.

## Links

- Requirements: [[FEAT-260912-e7ce2d]]
