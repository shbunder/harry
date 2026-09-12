---
id: FEAT-260912-11772e
title: Harry runs jobs on time, and tells you when one never ran
track: full
created: 2026-09-12
touches: [core/scheduler]
stories: []
decisions: []
---

# FEAT-260912-11772e — Harry runs jobs on time, and tells you when one never ran

## Summary

Harry owns the clock for its own heuristic work, and owns the deadline for work it does not trigger. That second half is the one that matters: a Claude scheduled task that never fires produces silence, and silence looks exactly like a morning you did not check.

## Acceptance criteria

<!-- One box per scenario. These are what the pre-close-verifier builds its
     traceability matrix from. -->

- [ ] A trigger: schedule job fires at its cron time, in the timezone it declares
- [ ] A job already running is not started a second time
- [ ] A job with a deadline that has not finished by then puts one message in Slack
- [ ] The watchdog reports once per missed deadline, not once per check
- [ ] A job that raises is logged and alerted, and the other jobs still run

## Stories

<!-- Maintained by `board.py new-story`. -->

## Notes

<!-- Appended by `board.py note`. -->

## Links

- Requirements: [[FEAT-260912-11772e]]
