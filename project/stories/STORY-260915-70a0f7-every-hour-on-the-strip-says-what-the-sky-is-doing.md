---
id: STORY-260915-70a0f7
title: Every hour on the strip says what the sky is doing
feature: FEAT-260915-153297
status: Done
created: 2026-09-15
---

# STORY-260915-70a0f7 — Every hour on the strip says what the sky is doing

Part of [[FEAT-260915-153297]].

## Description

`_hours` reads `hourly.time` and `hourly.temperature_2m`. Asking for `weather_code` alongside
is one more field on the `hourly` parameter, and `WORDS` — the WMO table `_read` already uses
for the day — turns it into the word.

The one thing to get right is the log line. `_read` warns on an unknown code once, because it
reads one code. Seventeen hours of the same unknown code would warn seventeen times, which is
how a useful line becomes noise.

## Acceptance criteria

- [x] Each of the seventeen `hours` entries is `{at, temperature, summary}`
- [x] `summary` uses the same `WORDS` table as `today()`, so an hour and the day can never disagree about what a code means
- [x] `hourly` asks for `temperature_2m,weather_code` on the one request that already fetches the day
- [x] An hourly block with no `weather_code` array still gives seventeen readings, each `summary: null`
- [x] An hour whose code the table does not carry gives the temperature and `summary: null`
- [x] Seventeen hours of the same unknown code produce one log line naming that code, not seventeen
- [x] `weather_forecast` returns it and `TOOL.md` says what it is; `docs/sources.md` describes it

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

