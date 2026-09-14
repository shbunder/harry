---
name: weather_forecast
namespace: weather
description: What the weather will do today, where the page is read
requires: [weather]
always_load: false
annotations:
  readOnlyHint: true
  idempotentHint: true
  openWorldHint: true
enabled: true
---

Returns today's forecast for the configured place: a word for the conditions, the day's high
and low in whole degrees, and the chance of rain as a whole percentage.

```
{"available": true, "place": "Leuven", "summary": "overcast",
 "high": 22, "low": 18, "rain_chance": 59}
```

Reach for this when the question is about today's weather where the page is read. It is one
place, set in Harry's configuration — it cannot answer for anywhere else, and there is no
argument to make it.

**When the service is down it answers `{"available": false, "place": …, "why": …}` rather
than failing.** A forecast nobody can get is an answer, not an error, and `why` says what
happened — there is nothing to retry and no other way to ask.

Not for tomorrow, the week, wind, pressure or sunrise. It answers today, in one line, for
one place.
