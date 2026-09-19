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
and low in whole degrees, the chance of rain as a whole percentage, when the sun rises and sets
as local `HH:MM`, and `hours` — the shape of the day, one temperature and one word an hour from
06:00 to 23:00 in local time.

```
{"available": true, "place": "Leuven", "summary": "overcast",
 "high": 22, "low": 18, "rain_chance": 59,
 "sunrise": "07:22", "sunset": "19:46",
 "hours": [{"at": "06:00", "temperature": 17, "summary": "clear"},
           {"at": "07:00", "temperature": 17, "summary": "clear"}, …]}
```

`hours` is what tells you whether the warm part is the morning or the evening, and whether
the rain is at the school run or after supper — the high and the day's one word cannot say
either. Each hour's `summary` comes from the same table the day's does, so the two never
disagree; it is `null` for a condition the table does not carry. `hours` is `[]` when the
service answered the day but not the hours, which costs the strip and nothing else.
`sunrise` and `sunset` are each `null` when the service did not send one.

Reach for this when the question is about today's weather where the page is read. It is one
place, set in Harry's configuration — it cannot answer for anywhere else, and there is no
argument to make it.

**When the service is down it answers `{"available": false, "place": …, "why": …}` rather
than failing.** A forecast nobody can get is an answer, not an error, and `why` says what
happened — there is nothing to retry and no other way to ask.

Not for tomorrow, the week, wind or pressure. It answers today, in one line, for
one place.
