---
id: STORY-260912-bdf4d2
title: iCloud answers over CalDAV
feature: FEAT-260912-cfeb21
status: Backlog
created: 2026-09-12
---

# STORY-260912-bdf4d2 — iCloud answers over CalDAV

Part of [[FEAT-260912-cfeb21]].

## Description

Apple's Reminders support over CalDAV is the least reliable dependency in the plan. The calendar half is expected to work; the to-do half is the question, and its answer only changes one section of the page.

## Acceptance criteria

<!-- These drive the tests. Write checkable statements, not activities.
     Bad:  Wire up the article fetcher
     Good: A De Tijd article whose browser session has expired falls back to its RSS
           summary, and the page still renders -->

- [ ] Today's events come back from https://caldav.icloud.com with time, title and location
- [ ] Whether Reminders arrive as VTODO is recorded either way
- [ ] The calendars available on the account are listed, so the connector knows what it can be pointed at
- [ ] The app-specific password is read from the environment and appears in no output

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

