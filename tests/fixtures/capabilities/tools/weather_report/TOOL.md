---
name: weather_report
namespace: weather
description: Hands back what it was given, so the wiring can be looked at
requires: [weather]
always_load: true
annotations:
  readOnlyHint: true
enabled: true
---

Returns the connector it was handed and the whole mapping it came in, so a test can check
that a tool really can use the connector it declared without importing it.
