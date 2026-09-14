---
id: FEAT-260912-5f7ec5
title: The page knows what the weather will do in Leuven
track: full
created: 2026-09-12
touches: [connectors/weather, tools/weather_forecast]
stories: [STORY-260914-4cebef, STORY-260914-6b94e4]
decisions: [ADR-260913-210e08, ADR-260913-18a8ae]
---

# FEAT-260912-5f7ec5 — The page knows what the weather will do in Leuven

## Summary

The smallest connector, and the one that proves the shape. Open-Meteo needs no key and answers daily and hourly in one call, so this is where the connector contract gets exercised before anything with a credential depends on it.

## Acceptance criteria

<!-- One box per scenario. These are what the pre-close-verifier builds its
     traceability matrix from. -->

- [ ] weather.today() returns {summary, high, low, rain_chance} from one call with no key, rounded to whole degrees and a whole percentage
- [ ] A weather_forecast tool returns the same four facts and the place they are for, and is deferred rather than in the roster every request
- [ ] Open-Meteo refusing, erroring, or not answering within 5 seconds makes today() return None and the tool answer {available: false, why}, without raising
- [ ] A 200 whose body is missing today's entry returns None and says so in the log, rather than raising a KeyError mid-page
- [ ] latitude, longitude, timezone and place are the connector's own settings, defaulting to Leuven
- [ ] Every test runs against a recorded answer — the happy path, the 500, the timeout and the malformed body — and none reaches api.open-meteo.com
- [ ] The Slack connector's provides: is untouched; weather exposes weather_forecast in its own

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260914-4cebef]] — Harry knows what the weather will do, and says nothing when it cannot
- [ ] [[STORY-260914-6b94e4]] — Claude can ask for the forecast from any session

## Notes

<!-- Appended by `board.py note`. -->

## Links

- Requirements: [[FEAT-260912-5f7ec5]]
- [[FEAT-260912-0f2744]] — the page that calls `weather.today()`
- [[ADR-260913-210e08]] — a capability is handed the connectors it declared
- [[ADR-260913-18a8ae]] — a tool exists because someone would ask for it
