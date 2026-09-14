---
name: weather
description: A stand-in forecast, so the loader's tests have a connector that works
expires: never
enabled: true
config:
  place:
    description: The place to forecast for
    default: Leuven
---

**Not the weather connector.** That one is `.harry/connectors/weather/`, it talks to
Open-Meteo, and its `today()` returns `{summary, high, low, rain_chance}`. This one
returns `{place, summary}` and talks to nobody.

It exists so that "the rest still came up" is a claim about something. The folders never
meet: every test copies the one it wants into its own temporary root.
