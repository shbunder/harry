---
id: STORY-260913-6fafd0
title: A deadline that passes with nothing done reaches a person, once
feature: FEAT-260912-11772e
status: Backlog
created: 2026-09-13
---

# STORY-260913-6fafd0 — A deadline that passes with nothing done reaches a person, once

Part of [[FEAT-260912-11772e]].

## Description

The half that only exists because Harry does not own the clock. An external trigger cannot report its own absence, and silence looks exactly like a morning you did not check.

## Acceptance criteria

<!-- These drive the tests. Write checkable statements, not activities.
     Bad:  Wire up the article fetcher
     Good: A De Tijd article whose browser session has expired falls back to its RSS
           summary, and the page still renders -->

- [ ] The watchdog runs every five minutes and once at start-up, so a deadline missed while Harry was down is reported when it comes back
- [ ] A trigger: claude job with a deadline is checked against that time in that job's own timezone
- [ ] Nothing finished since midnight in that timezone sends one alert: "<job> has not run today. It was due by <time>."
- [ ] A completion earlier the same morning sends nothing
- [ ] Yesterday's completion does not count as today's
- [ ] The same missed deadline is not reported twice on the same day, even across a restart
- [ ] A failed alert does not mark the deadline reported, so the next check tries again
- [ ] A disabled job, and a trigger: claude job with no deadline, are not watched
- [ ] docs/operating.md says what the watchdog actually checks, replacing the "since 05:00" rule written before it existed

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

