---
id: FEAT-260919-f11974
title: The weather panel says Weather unavailable when there is no forecast
track: full
created: 2026-09-19
touches: [docs, tools/digest_build]
stories: []
decisions: []
---

# FEAT-260919-f11974 — The weather panel says Weather unavailable when there is no forecast

## Summary

When there is no forecast — Open-Meteo is down, or no weather connector is set up — the front sheet still draws the weather panel, with a cloud, `–°`, `High –° · Low –°`, `Rain –%` and an empty strip. It reads like a broken page rather than a missing source.

Harry's docs already promise something better, in six places: `docs/morning-page.md` (the "When something is missing" table), `docs/sources.md` (Weather), the weather `CONNECTOR.md` runbook and the `connector.py` docstring all say the page prints `Weather unavailable`. Nothing in `.harry/tools/digest_build/` prints it. The only test of the case, `test_no_weather_connector_costs_the_panel_and_not_the_page`, checks that nothing is crowded and never reads the panel.

Found by the plan check on FEAT-260919-e9cab2, which pinned today's dashes with a test so this change has something to turn red.

## Acceptance criteria

<!-- One box per scenario. These are what the pre-close-verifier builds its
     traceability matrix from. -->

- [ ] <criterion>

## Stories

<!-- Maintained by `board.py new-story`. -->

## Notes

<!-- Appended by `board.py note`. -->

## Links

- Requirements: [[FEAT-260919-f11974]]
