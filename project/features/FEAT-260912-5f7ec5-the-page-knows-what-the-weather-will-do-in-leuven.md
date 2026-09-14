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

- [ ] weather.today() returns {summary, high, low, rain_chance} from one GET asking for weather_code, temperature_2m_max, temperature_2m_min and precipitation_probability_max, rounded to whole degrees and a whole percentage
- [ ] summary comes from a WMO code table written down on the requirements page, and a code the table does not have gives summary None and the three numbers, logged
- [ ] weather_forecast answers {available: true, place, summary, high, low, rain_chance}, is deferred, and is listed in the connector's provides: — which make lint enforces
- [ ] Open-Meteo refusing, erroring, or not answering within 5 seconds makes today() return None and the tool answer {available: false, place, why}, without raising — available is on both answers so Claude reads one key
- [ ] A 200 whose body is missing today's entry returns None and says so in the log, rather than raising a KeyError mid-page
- [ ] latitude, longitude, timezone and place are declared in config:, generated into the committed .env with the Leuven defaults, and overridden by .env.local
- [ ] Every test runs against a recorded answer — the happy path, the 500, the timeout and the malformed body — and none reaches api.open-meteo.com
- [ ] Nothing here reaches Slack, and the requirements page says why weather is a deliberate exception and what would have to exist for it not to be

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
