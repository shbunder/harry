---
id: FEAT-260912-5f7ec5
title: The page knows what the weather will do in Leuven
track: full
created: 2026-09-12
touches: [connectors/weather]
stories: []
decisions: []
---

# FEAT-260912-5f7ec5 — The page knows what the weather will do in Leuven

## Summary

The smallest connector, and the one that proves the shape. Open-Meteo needs no key and answers daily and hourly in one call, so this is where the connector contract gets exercised before anything with a credential depends on it.

## Acceptance criteria

<!-- One box per scenario. These are what the pre-close-verifier builds its
     traceability matrix from. -->

- [ ] Today's forecast for Leuven comes back from a single call with no API key
- [ ] A weather_forecast tool returns the day's range, the conditions and the chance of rain
- [ ] When Open-Meteo cannot be reached the caller gets "weather unavailable" rather than an exception
- [ ] Parsing is tested against a recorded response, never a live call

## Stories

<!-- Maintained by `board.py new-story`. -->

## Notes

<!-- Appended by `board.py note`. -->

## Links

- Requirements: [[FEAT-260912-5f7ec5]]
