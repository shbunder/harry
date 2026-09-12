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

## Links

- Requirements: [[FEAT-260912-e7ce2d]]
