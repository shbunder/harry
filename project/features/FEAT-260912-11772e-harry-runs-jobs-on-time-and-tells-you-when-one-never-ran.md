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

- [x] A trigger: schedule job fires at its cron time, in the timezone it declares, running what the capability registered
- [x] A job already running is not started a second time, and harry.scheduler says so in its own words rather than leaving it to APScheduler
- [x] A job that raises is logged and alerted, keyed on the job, and the other jobs still run
- [x] harry_mark_done records when a job finished, the record survives a restart, and it is always in the MCP roster because a brief cannot search for it
- [x] A trigger: claude brief ends by telling Claude to call harry_mark_done, because nothing else can tell Harry the work happened
- [x] The watchdog runs every five minutes and once at start-up, so a deadline missed while Harry was switched off is reported when it comes back
- [x] A deadline that passes with nothing finished since midnight in that job's timezone sends one alert naming the job and the time it was due
- [x] A deadline that passes after the job finished sends nothing, and yesterday's completion does not count as today's
- [x] A missed deadline is reported once per day even across a restart, because the date reported is written down beside the completion
- [x] No jobs, a disabled job, and a trigger: claude job with no deadline are all a working Harry that watches nothing
- [x] A store file that cannot be read starts Harry with an empty record and says so; one that cannot be written logs at WARNING and does not break the caller
- [x] An alert that could not be delivered does not mark the deadline reported, so the next check tries again
- [x] docs/operating.md describes the watchdog Harry actually runs, and docs/mcp.md names the second always-loaded tool

## Stories

<!-- Maintained by `board.py new-story`. -->
- [x] [[STORY-260913-350825]] — Harry runs its own jobs on time, and one that fails costs only itself
- [x] [[STORY-260913-6a5e03]] — Harry remembers when a job finished, across a restart
- [x] [[STORY-260913-6fafd0]] — A deadline that passes with nothing done reaches a person, once

## Notes

<!-- Appended by `board.py note`. -->
- **2026-09-13** — Reflection: pre-close-verifier returned REQUEST CHANGES — 2 Critical, 4 Important, 2 Suggestions, all acted on. Traceability 13/13 feature criteria and 21/21 story criteria; the two docs criteria are by inspection in practice and were not marked so on the board, which is worth doing next time. Degraded paths exercised: a job that raises, a job still running, a scheduled job with no code, a timezone that is not a timezone, a deadline that will not parse, a store that cannot be read, a store that cannot be written, an alert nobody took, a disabled job, and a job with no deadline. Scope drift: /health gained a jobs section, which was the verifier's own suggestion and gave Store.as_dict and app.state.jobs their only callers.

## Lessons Learned

### What worked

**Driving a real scheduler by nudging the clock.** `tests/test_scheduler.py` builds a real
`BackgroundScheduler` with real jobs and brings a fire time forward with
`modify_job(next_run_time=…)`, rather than waiting for 05:00 or calling the registered
function. A test that calls the function proves the capability works and nothing about the
clock. Both scheduler mutations the verifier tried went red immediately.

**Two facts in a file, argued for on the page before it was written.** The store section
made the case against SQLite and the case against memory, and named the exact failure the
in-memory version would produce: a restart loses every completion, the watchdog reports a
miss about a page delivered an hour earlier, and a false alarm on every deploy is how a
channel gets muted. Nobody had to rediscover that.

**Pushing the one judgement call across the boundary.** Harry cannot know that a job it
does not fire has finished, and inferring it would be reasoning. `harry_mark_done` puts the
sentence in the job's own brief instead, so core stays ignorant of every job by name.

### What to do differently

**"It runs on a schedule" needs a test that lets the schedule run it.** Every deadline test
called `check_deadlines()` by hand, so deleting the start-up check and pointing the interval
job at a no-op both left 329 tests green. The watchdog is the only thing that tells a missed
morning from a silent one, and nothing proved it ever fired on its own. **Whenever a control
is reached by a timer, an event or a route, one test has to arrive that way.**

**A promise one module makes is not kept by the module after it.** The loader wraps every
capability in its own try/except. The scheduler then crashed on a declaration the loader had
let through — `timezone: Mars/Olympus` — so no jobs were scheduled, the watchdog was never
registered, and `/health` never answered. This is the second time in three features that a
property established earlier was given back by the next thing to touch the same objects.
**Ask of every new module: which promise does the thing before me make, and do I still keep
it?**

**A convention in prose is not a mechanism.** "Every `trigger: claude` brief ends by asking
for `harry_mark_done`" was a sentence in one fixture. The first real job to omit it would
have passed the gate and produced a false alarm every morning. It is now a check in
`scripts/check_capabilities.py`.

**A number that is only in a declaration is not a tested number.** `assert
watchdog.trigger.interval == 5 minutes` passes whatever the job is registered against.

### Patterns to reuse

- **`tests/test_scheduler.py::fire_now`** — `modify_job(next_run_time=now)` on a real
  scheduler. The way to test anything on a timer without sleeping through it.
- **`Jobs._safely`** — one job's declaration cannot take the others down. Same shape as the
  loader's per-capability try/except, and the next module that iterates capabilities needs
  its own.
- **`src/harry/store.py`** — two facts per job in one JSON file, every failure path real: a
  file that is not JSON, a file that is JSON but not this file, a time that will not parse,
  and a directory that cannot be written. Each leaves Harry running.
- **`Alerts.send` returning whether anybody took it** — the watchdog only marks a deadline
  reported when somebody actually heard, so the one morning it mattered is tried again.
- **`/health`'s `jobs` section** — "the watchdog has been quiet, is it even watching?"
  answered somewhere other than a log line from this morning.

## Links

- Requirements: [[FEAT-260912-11772e]]
- [[ADR-260912-bd36c2]] — Harry never calls a model, which is why an external trigger exists
- [[ADR-260912-399f07]] — capabilities are folders under `.harry/`
- [[ADR-260913-816553]] — a capability can be somewhere alerts go
