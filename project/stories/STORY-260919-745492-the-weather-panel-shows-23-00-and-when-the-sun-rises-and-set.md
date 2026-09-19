---
id: STORY-260919-745492
title: The weather panel shows 23:00 and when the sun rises and sets
feature: FEAT-260919-e9cab2
status: Backlog
created: 2026-09-19
---

# STORY-260919-745492 — The weather panel shows 23:00 and when the sun rises and sets

Part of [[FEAT-260919-e9cab2]].

## Description

One story because the two halves meet on one panel. The connector reads 23:00 and the sun's times from the answer it already gets, and the page draws them. Splitting it would leave a field nobody draws, or a slot with nothing to fill it.

## Acceptance criteria

- [ ] The strip on the front sheet shows 08:00, 12:00, 16:00, 20:00 and 23:00, in that order, each with its own temperature and icon, chosen by clock time rather than by position in the list
- [ ] Read back off the PDF, the 23:00 label ends inside the 34pt right margin, and the page reports nothing crowded
- [ ] `forecast()['hours']` carries eighteen readings, 06:00 to 23:00; 05:00 and earlier stay off
- [ ] `forecast()` carries `sunrise` and `sunset` as local "HH:MM" strings, asked for in the `daily` list of the one request Harry already makes
- [ ] The weather panel reads "Sunrise 07:22 · Sunset 19:46" for a forecast carrying those two times
- [ ] An answer with no sunrise or sunset, or one that cannot be read as a time, prints no sunrise line and keeps the high, low, rain chance and strip; one INFO line says so, and nothing reaches Slack
- [ ] An hourly block that stops before 23:00 draws the hours it has, with no empty slot
- [ ] The `weather_forecast` tool returns `sunrise`, `sunset` and the eighteen hours, and its `TOOL.md` says so and no longer says it is not for sunrise
- [ ] With `PLACE=Ghent`, the weather panel says Ghent, not Leuven
- [ ] `docs/` describes the fifth hour and the sunrise line beside the rest of the weather

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

