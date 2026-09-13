---
id: STORY-260913-350825
title: Harry runs its own jobs on time, and one that fails costs only itself
feature: FEAT-260912-11772e
status: Backlog
created: 2026-09-13
---

# STORY-260913-350825 — Harry runs its own jobs on time, and one that fails costs only itself

Part of [[FEAT-260912-11772e]].

## Description

APScheduler, the cron times and the timezones, and the rule that one job's failure is one job's failure. The half Harry owns outright.

## Acceptance criteria

<!-- These drive the tests. Write checkable statements, not activities.
     Bad:  Wire up the article fetcher
     Good: A De Tijd article whose browser session has expired falls back to its RSS
           summary, and the page still renders -->

- [ ] A job with `schedule: "0 5 * * *"` and `timezone: Europe/Brussels` is scheduled for 05:00 Brussels time
- [ ] A job in another timezone fires at its own 05:00, not at the machine's
- [ ] Firing a job runs the function the capability registered
- [ ] A job still running when its next fire time arrives is not started again, and harry.scheduler logs it in its own words — asserted on Harry's logger, not APScheduler's
- [ ] A job that raises is logged with its exception type and message
- [ ] A job that raises sends one alert naming the job and what it raised, keyed on the job
- [ ] A job that raises does not stop another job from running
- [ ] No jobs at all is a scheduler that starts, says so, and serves

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

