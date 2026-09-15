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

- [x] Each entry in `hours` carries `summary`: the same word `today()['summary']` uses, or null for a code the table does not carry
- [x] It rides on the request that already fetches the day — one call, not two
- [x] An answer with temperatures and no codes still gives the seventeen readings, with `summary: null` on each
- [x] An unrecognised WMO code gives the temperature and no word, and says which code, once per answer rather than once per hour
- [x] The `weather_forecast` tool returns it, and `TOOL.md` says what it is
- [x] `docs/` describes it beside the rest of the weather connector

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260915-70a0f7]] — Every hour on the strip says what the sky is doing

## Lessons Learned

### What worked

**Threading a set through the word lookup, so one bad code says one thing.** `_word` takes
the `unknown` set and adds to it; `_hours` says the line once at the end, naming every code
sorted. Four different mutations of that aggregation each turned a test red, including
naming only the first code.

**Re-recording the fixture rather than hand-editing it**, and saying in the fixture README
what it now carries and why — both WMO codes the table knows, and a daily code that matches
one of them, so the day and its hours can be checked against each other.

### What to do differently

**A recording is not a sample of the domain.** The test for "an hour and its day read the
same table" passed against a private two-entry table, because the recording happens to carry
only codes `0` and `3` and any hand-written stub would get those right. Twenty-four of the
twenty-seven codes could have drifted silently. Parametrise over the table you are claiming
to share, not over what the fixture happens to hold.

**Guard the big failure at least as loudly as the small one.** A single unrecognised code
warned. Every hour losing its word was completely silent — no line at any level — which is
the larger loss and the one nobody would notice. When adding a degraded path, look at what
the neighbouring path already logs and ask whether the new one is quieter.

**`# type: ignore[code]` is mypy. This gate runs pyright**, which ignores the bracket and
suppresses every error on the line. It reads narrow and behaves broad.

### Patterns to reuse

- **`Weather._word(code, unknown)`** — a lookup that remembers what it could not resolve, so
  the caller can report once for the whole answer instead of once per item. Any per-row
  parse with a per-answer log line wants this shape.
- **`test_an_hour_and_its_day_agree_on_every_code_the_table_carries`** — when two call paths
  must share one table, parametrise over values the fixture does *not* carry. That is the
  test a private copy of the table cannot pass.

## Notes

<!-- Appended by `board.py note`. -->

## Links

