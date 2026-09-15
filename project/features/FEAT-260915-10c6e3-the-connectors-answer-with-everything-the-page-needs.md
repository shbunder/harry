---
id: FEAT-260915-10c6e3
title: The connectors answer with everything the page needs
track: full
created: 2026-09-15
touches: [connectors/icloud, connectors/news, connectors/weather, docs, tools/icloud, tools/news, tools/weather_forecast]
stories: [STORY-260915-58dc98, STORY-260915-98499e, STORY-260915-005396]
decisions: [ADR-260915-c01ab8]
---

# FEAT-260915-10c6e3 — The connectors answer with everything the page needs

## Summary

The morning page was designed once as a spike, and five times it had to go round the back of
a connector to get something it needed: the shape of the day's temperature, when an event
ends, which calendar an event is from, the picture a feed published, and the summary a feed
wrote. Those five are what make the page a page rather than a list — a weather panel with an
hourly strip, a timetable with proportional blocks in the user's own colours, and headlines
with pictures. This closes all five, in the three connectors that own them, and passes each
one on through the tool Claude reads.

## Acceptance criteria

- [ ] `weather.forecast()` carries `hours`: seventeen `{at, temperature}` entries, 06:00 to 22:00 local, inclusive
- [ ] An Open-Meteo answer with no hourly block gives `hours: []`, leaves the rest of the panel intact, and says nothing in Slack
- [ ] `today()` is unchanged: `summary`, `high`, `low`, `rain_chance` and nothing else
- [ ] A timed event carries `ends` in the same `"HH:MM"` shape as `at`; an all-day event carries `ends: null`; `at` itself does not change
- [ ] Every event carries `calendar` — a CalDAV calendar's display name, or a published link's label
- [ ] A CalDAV calendar with no readable name still returns its events, as `calendar: "Calendar"`, and logs that calendar once per read
- [ ] Every candidate carries `image` in both `concise` and `full`: the feed's URL or null, with a BBC thumbnail asked for at 800px rather than 240px
- [ ] A feed carrying no images gives `image: null` and raises no alert
- [ ] `news.article(id)` carries `summary` and `image`, including when the page could not be read
- [ ] `weather_forecast`, `icloud_list_events`, `news_search` and `news_article` return the new fields, and each `TOOL.md` says what they are
- [ ] `docs/` describes every new field beside the connector that answers it

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260915-58dc98]] — The weather answers with the shape of the day
- [ ] [[STORY-260915-98499e]] — Every event says when it ends and whose calendar it is
- [ ] [[STORY-260915-005396]] — A headline carries its picture and its summary

## Notes

<!-- Appended by `board.py note`. -->

## Links

- Requirements: [[FEAT-260915-10c6e3]]
- Decision: [[ADR-260915-c01ab8]] — A connector hands over a picture's address, never the picture

