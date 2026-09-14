---
id: STORY-260914-4cebef
title: Harry knows what the weather will do, and says nothing when it cannot
feature: FEAT-260912-5f7ec5
status: Backlog
created: 2026-09-14
---

# STORY-260914-4cebef — Harry knows what the weather will do, and says nothing when it cannot

Part of [[FEAT-260912-5f7ec5]].

## Description

The connector: one call to Open-Meteo, four facts back, and None whenever it cannot answer. The interface the page already wrote down, satisfied for the first time.

## Acceptance criteria

<!-- These drive the tests. Write checkable statements, not activities.
     Bad:  Wire up the article fetcher
     Good: A De Tijd article whose browser session has expired falls back to its RSS
           summary, and the page still renders -->

- [ ] weather.today() returns {summary, high, low, rain_chance} from a single GET asking for weather_code, temperature_2m_max, temperature_2m_min and precipitation_probability_max
- [ ] high and low are whole degrees and rain_chance is a whole percentage — the page is read at arm's length
- [ ] A refused connection, a 500, or no answer within 5 seconds returns None rather than raising
- [ ] A 200 whose body has no entry for today returns None and says so in the log, rather than a KeyError mid-page
- [ ] summary comes from the WMO table on the requirements page, and an unlisted code gives summary None with the three numbers intact
- [ ] latitude, longitude, timezone and place are declared in config: and generated into the committed .env with the Leuven defaults
- [ ] Every test runs against a recorded answer; none reaches api.open-meteo.com

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

