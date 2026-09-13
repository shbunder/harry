---
id: FEAT-260912-11772e
title: Harry runs jobs on time, and tells you when one never ran
track: full
created: 2026-09-12
touches: [core/main, core/scheduler, core/store, core/mcp]
stories: [STORY-260913-350825, STORY-260913-6a5e03, STORY-260913-6fafd0]
decisions: [ADR-260912-bd36c2, ADR-260912-399f07, ADR-260913-816553]
---

# FEAT-260912-11772e — Harry runs jobs on time, and tells you when one never ran

## Summary

Harry owns the clock for its own heuristic work, and owns the deadline for work it does not trigger. That second half is the one that matters: a Claude scheduled task that never fires produces silence, and silence looks exactly like a morning you did not check.

## Acceptance criteria

<!-- One box per scenario. These are what the pre-close-verifier builds its
     traceability matrix from. -->

- [ ] A trigger: schedule job fires at its cron time, in the timezone it declares, running what the capability registered
- [ ] A job already running is not started a second time, and harry.scheduler says so in its own words rather than leaving it to APScheduler
- [ ] A job that raises is logged and alerted, keyed on the job, and the other jobs still run
- [ ] harry_mark_done records when a job finished, the record survives a restart, and it is always in the MCP roster because a brief cannot search for it
- [ ] A trigger: claude brief ends by telling Claude to call harry_mark_done, because nothing else can tell Harry the work happened
- [ ] The watchdog runs every five minutes and once at start-up, so a deadline missed while Harry was switched off is reported when it comes back
- [ ] A deadline that passes with nothing finished since midnight in that job's timezone sends one alert naming the job and the time it was due
- [ ] A deadline that passes after the job finished sends nothing, and yesterday's completion does not count as today's
- [ ] A missed deadline is reported once per day even across a restart, because the date reported is written down beside the completion
- [ ] No jobs, a disabled job, and a trigger: claude job with no deadline are all a working Harry that watches nothing
- [ ] A store file that cannot be read starts Harry with an empty record and says so; one that cannot be written logs at WARNING and does not break the caller
- [ ] An alert that could not be delivered does not mark the deadline reported, so the next check tries again
- [ ] docs/operating.md describes the watchdog Harry actually runs, and docs/mcp.md names the second always-loaded tool

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260913-350825]] — Harry runs its own jobs on time, and one that fails costs only itself
- [ ] [[STORY-260913-6a5e03]] — Harry remembers when a job finished, across a restart
- [ ] [[STORY-260913-6fafd0]] — A deadline that passes with nothing done reaches a person, once

## Notes

<!-- Appended by `board.py note`. -->

## Links

- Requirements: [[FEAT-260912-11772e]]
- [[ADR-260912-bd36c2]] — Harry never calls a model, which is why an external trigger exists
- [[ADR-260912-399f07]] — capabilities are folders under `.harry/`
- [[ADR-260913-816553]] — a capability can be somewhere alerts go
