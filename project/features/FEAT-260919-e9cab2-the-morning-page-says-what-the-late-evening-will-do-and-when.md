---
id: FEAT-260919-e9cab2
title: The morning page says what the late evening will do, and when the sun rises and sets
track: full
created: 2026-09-19
touches: [connectors/weather, docs, tools/digest_build, tools/digest_list_candidates, tools/weather_forecast]
stories: [STORY-260919-745492]
decisions: []
---

# FEAT-260919-e9cab2 — The morning page says what the late evening will do, and when the sun rises and sets

## Summary

The weather panel shows four hours, the last at 20:00, so the late evening is not on the page. Open-Meteo already sends every hour to midnight on the call Harry makes each morning; the connector throws away everything after 22:00. Sunrise and sunset are two more daily fields on that same call, never asked for.

This adds 23:00 as a fifth hour on the strip and a "Sunrise 07:22 · Sunset 19:46" line beside the high and low, on the one request Harry already makes. A missing sunrise costs that line and nothing else.

## Acceptance criteria

- [x] The strip on the front sheet shows 08:00, 12:00, 16:00, 20:00 and 23:00, in that order, each with its own temperature and icon, chosen by clock time rather than by position in the list
- [x] Read back off the PDF, the 23:00 label ends inside the 34pt right margin, and the page reports nothing crowded
- [x] `forecast()['hours']` carries eighteen readings, 06:00 to 23:00; 05:00 and earlier stay off
- [x] `forecast()` carries `sunrise` and `sunset` as local "HH:MM" strings, asked for in the `daily` list of the one request Harry already makes
- [x] The weather panel reads "Sunrise 07:22 · Sunset 19:46" for a forecast carrying those two times
- [x] `sunrise` and `sunset` are always in the forecast, each null when it cannot be read. With both null the panel prints no sun line and keeps the high, low, rain chance and strip; with one, that one prints on its own. One INFO line names what was missing, and nothing reaches Slack
- [x] An hourly block that stops before 23:00 draws whichever of the five hours it has; no other hour takes 23:00's place, and there is no empty slot
- [x] With no forecast at all, the panel draws dashes with no place and no sun line, and the rest of the page renders
- [x] The `weather_forecast` tool returns `sunrise`, `sunset` and the eighteen hours, and its `TOOL.md` says so and no longer says it is not for sunrise
- [x] With `PLACE=Ghent`, the weather panel says Ghent, not Leuven
- [x] The `digest_list_candidates` `TOOL.md` example shows `sunrise` and `sunset` in the weather Claude reads each morning
- [x] `docs/sources.md`, `docs/morning-page.md`, the weather `CONNECTOR.md` runbook and the fixtures README describe the fifth hour and the sun line, and the runbook names the missing-sunrise case

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260919-745492]] — The weather panel shows 23:00 and when the sun rises and sets

## Notes

<!-- Appended by `board.py note`. -->

## Links

- Requirements: [[FEAT-260919-e9cab2]]
