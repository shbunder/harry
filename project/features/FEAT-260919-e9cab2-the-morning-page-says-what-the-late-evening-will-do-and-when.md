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
- [x] An hourly block that stops before 23:00 draws whichever of the five hours it has, each where it sits in a full strip. Nothing stands in for 23:00 — not 22:00 and not an empty cell — so the right end of the strip is left blank
- [x] With no forecast at all, the panel draws dashes with no place and no sun line, and the rest of the page renders
- [x] The `weather_forecast` tool returns `sunrise`, `sunset` and the eighteen hours, and its `TOOL.md` says so and no longer says it is not for sunrise
- [x] With `PLACE=Ghent`, the weather panel says Ghent, not Leuven
- [x] The `digest_list_candidates` `TOOL.md` example shows `sunrise` and `sunset` in the weather Claude reads each morning
- [x] `docs/sources.md`, `docs/morning-page.md` and the fixtures README describe the fifth hour and the sun line, and the weather `CONNECTOR.md` runbook names the missing-sunrise case

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260919-745492]] — The weather panel shows 23:00 and when the sun rises and sets

## Lessons Learned

### What worked

**Running the real connector into the real page.** `test_the_real_forecast_reaches_the_panel`
loads `.harry/connectors/weather/` beside the stand-in news and mocks only Open-Meteo, with the
answer recorded on 19 September 2026. Every other page test hands over a stand-in, so it is the
only test where the connector and the page could disagree about a key's name. Setting
`PLACE=Ghent` in it is what exposed the hard-coded `Leuven` in `page.py`, which every fixture
had matched for as long as the page existed.

**Picking the strip's hours by clock time.** `[2::4][:4]` gave 08, 12, 16 and 20 only because
the list started at 06:00. A forecast starting at 07:00 turned the same rule into 09, 13, 17 and
21. `STRIP` in `sheet.py` names the five hours, and the strip's width is worked out from it.

**Measuring the page on WeasyPrint's layout, not the PDF.** The PDF says where a label starts
and never where it ends, so the first margin test bounded the end by a whole cell — sound, but
it would have gone red on a correct flush-right strip. `strip_cells` captures the HTML
`digest_build` hands to `render` and reads each cell's border box and its label's text box off
the same layout call `render` makes. The 23:00 label ends at 467.11pt, its cell at 469.66pt,
the margin at 475.34pt.

### What to do differently

**A flex row fails by squeezing, not by spilling.** With the strip left at its old 118pt, five
25pt cells did not cross the margin: flex shrank them to 19pt and the labels nearly touched.
The margin assertion stayed green and only a spacing assertion (25pt cells, 6pt apart) caught
it. When a row gains an item, assert the item's size as well as the row's edge.

**I ticked two criteria no test could fail.** "Each hour with its own icon" had no test at all
— every hour drawing the day's icon passed 859 of 859. "No empty slot" was untested and untrue:
with hours ending at 22:00 the strip keeps its width and the right end is blank. The pre-close
verifier found both by mutating the code. Break each ticked claim once before ticking it.

**A test fed 06:00 to 22:00 cannot fail for 23:00.** The old strip test used `range(6, 23)` and
checked four labels, so it would have stayed green if 23:00 were never drawn. Re-read a test's
input, not only its assertions, when the feature moves the boundary it sits on.

**Docs promised "Weather unavailable" in six places and nothing prints it.** Found by the plan
check rendering the case; opened as FEAT-260919-f11974 rather than fixed here.

### Patterns to reuse

- **`captured(catalogue, monkeypatch)` and `strip_cells(html)`** in `tests/test_digest_build.py`
  — capture the HTML a tool renders by patching `render` in the loaded tool's globals, then
  measure any box on it with WeasyPrint. Reusable for any "does it fit" claim on the front sheet.
- **`front_runs(path)`** in the same file — each text run on the front sheet with its x
  position, from pypdf's `visitor_text`.
- **`Weather._sun` and `_clock`** in `.harry/connectors/weather/connector.py` — a field read
  softly beside facts read strictly: `fullmatch` or `None`, always present, one INFO line naming
  what was missing. A missing field costs its line, never the forecast.
- **An old recording as the degraded case.** `leuven-hourly.json` predates the sun fields, so it
  is also *the service answered without them*, with nothing hand-edited.

## Notes

<!-- Appended by `board.py note`. -->
- **2026-09-19** — Reflection: plan-verifier WARN (8 plan-wording findings, all folded in); pre-close verifier REQUEST CHANGES then APPROVE WITH NOTES, both notes fixed. Traceability 12/12. Degraded paths exercised: no sunrise or sunset (recorded answer from before they were asked for), one of the two unreadable in 7 shapes, an hourly block stopping at 22:00, no forecast at all. Mutants: 17 run on source across three rounds, all red at close. Scope drift: the hard-coded Leuven on the panel, folded in as Scenario 7 because it sits on the line this feature edits. Live check: weather_forecast against Open-Meteo on 2026-09-19 answered sunrise 07:22, sunset 19:46, 18 hours to 23:00. Gate at 051fcb7: 860 passed, coverage 92%.

## Links

- Requirements: [[FEAT-260919-e9cab2]]
