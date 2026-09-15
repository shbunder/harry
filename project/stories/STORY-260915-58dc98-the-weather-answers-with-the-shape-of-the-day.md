---
id: STORY-260915-58dc98
title: The weather answers with the shape of the day
feature: FEAT-260915-10c6e3
status: Backlog
created: 2026-09-15
---

# STORY-260915-58dc98 — The weather answers with the shape of the day

Part of [[FEAT-260915-10c6e3]].

## Description

`weather.forecast()` asks Open-Meteo for the daily block and gets one call's worth of
answer back. The same call can carry `hourly=temperature_2m`, so this is one request, one
parser and one degraded path — splitting it into a second method would be a second call to
the same endpoint for data the first one could have carried.

`today()` keeps exactly the four keys it has. It is the narrow answer for whoever wants the
day in one line, and widening it would make every caller carry the strip.

## Acceptance criteria

- [ ] `forecast()` carries `hours`: seventeen `{at, temperature}` entries for 06:00 to 22:00 local time, inclusive of both ends
- [ ] `at` is `"HH:MM"` in the connector's configured timezone, not UTC
- [ ] `temperature` is a whole number of degrees
- [ ] An answer with a daily block and no hourly block gives `hours: []`, keeps `available: true`, and sends nothing to Slack
- [ ] `today()` returns `summary`, `high`, `low`, `rain_chance` and nothing else
- [ ] The `weather_forecast` tool returns `hours`, and its `TOOL.md` says what it is
- [ ] One Open-Meteo answer carrying an `hourly` block is recorded in `tests/fixtures/weather/` and noted in that folder's record — the three there today all lack one
- [ ] `docs/` describes `hours` beside the rest of the weather connector

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

