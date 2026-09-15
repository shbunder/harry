---
id: FEAT-260915-153297
title: The hourly strip knows the sky, not only the temperature
track: story
created: 2026-09-15
touches: [connectors/weather, docs, tools/weather_forecast]
stories: [STORY-260915-70a0f7]
decisions: []
---

# FEAT-260915-153297 — The hourly strip knows the sky, not only the temperature

## Summary

`forecast()['hours']` carries seventeen temperatures and no sky. Nine degrees under a sun and
nine under a thundercloud are different mornings, and the page's hourly strip draws an icon
for each hour — so the design spike fetches Open-Meteo's `weather_code` itself, on a second
request, and reaches into the connector's module for the WMO table to read it with.

Both of those go away here. The hourly block already carries `weather_code` on the same
request the temperatures come from, and the table that turns a code into a word is already in
this connector.

## Acceptance criteria

- [ ] Each entry in `hours` carries `summary`: the same word `today()['summary']` uses, or null for a code the table does not carry
- [ ] It rides on the request that already fetches the day — one call, not two
- [ ] An answer with temperatures and no codes still gives the seventeen readings, with `summary: null` on each
- [ ] An unrecognised WMO code gives the temperature and no word, and says which code, once per answer rather than once per hour
- [ ] The `weather_forecast` tool returns it, and `TOOL.md` says what it is
- [ ] `docs/` describes it beside the rest of the weather connector

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260915-70a0f7]] — Every hour on the strip says what the sky is doing

## Notes

<!-- Appended by `board.py note`. -->

## Links

