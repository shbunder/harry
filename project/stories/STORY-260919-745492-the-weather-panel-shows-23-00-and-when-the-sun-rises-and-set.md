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
- [ ] `sunrise` and `sunset` are always in the forecast, each null when it cannot be read. With both null the panel prints no sun line and keeps the high, low, rain chance and strip; with one, that one prints on its own. One INFO line names what was missing, and nothing reaches Slack
- [ ] An hourly block that stops before 23:00 draws whichever of the five hours it has; no other hour takes 23:00's place, and there is no empty slot
- [ ] With no forecast at all, the panel draws dashes with no place and no sun line, and the rest of the page renders
- [ ] The `weather_forecast` tool returns `sunrise`, `sunset` and the eighteen hours, and its `TOOL.md` says so and no longer says it is not for sunrise
- [ ] With `PLACE=Ghent`, the weather panel says Ghent, not Leuven
- [ ] The `digest_list_candidates` `TOOL.md` example shows `sunrise` and `sunset` in the weather Claude reads each morning
- [ ] `docs/sources.md`, `docs/morning-page.md`, the weather `CONNECTOR.md` runbook and the fixtures README describe the fifth hour and the sun line, and the runbook names the missing-sunrise case

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

Tests that asserted the old behaviour, each updated rather than deleted:

- `tests/test_weather_connector.py` — the `daily` field list (now six), hours `range(6, 24)` ending
  at 23:00, `'23:00' not in` turned round to `in` with the 05:00 half kept, the exact list in
  the unreadable-hour test, and every `17` / `[None] * 17` / `[None] * 15` count (now 18 / 16).
  `test_claude_can_ask_for_the_forecast` now expects `sunrise: None, sunset: None` for a
  recording made before the sun was asked for.
- `tests/test_digest_build.py` — `test_the_weather_strip_carries_four_hours` could not fail
  for 23:00: it fed hours 06 to 22. Replaced by a test that feeds 06 to 23 and checks all five
  hours in order.
- `.harry/tools/digest_build/sheet.py` — the strip's hard-coded `118pt` is now worked out from
  `STRIP`.

