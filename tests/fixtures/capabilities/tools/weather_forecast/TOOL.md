---
name: weather_forecast
namespace: weather
description: What the weather will do today, where you are
requires: [weather]
always_load: true
annotations:
  readOnlyHint: true
  idempotentHint: true
enabled: true
---

Returns today's forecast for the configured place: the summary, the high and the low.
Reach for this when the question is about today's weather rather than the week's.
