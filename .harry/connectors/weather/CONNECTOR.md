---
name: weather
description: Today's forecast for one place, from Open-Meteo, with no account and no key
provides: [weather_forecast]
expires: never
enabled: true
config:
  latitude:
    description: Decimal degrees north. Leuven is 50.88. Look a place up once at open-meteo.com rather than making Harry geocode it every morning.
    default: 50.88
  longitude:
    description: Decimal degrees east. Leuven is 4.70.
    default: 4.7
  timezone:
    description: An IANA zone, so "today" means the day where the page is read rather than in UTC.
    default: Europe/Brussels
  place:
    description: What to call this spot on the page and in an answer. Open-Meteo never sees it.
    default: Leuven
---

The smallest source Harry has, and the only one with no credential. Open-Meteo answers
today in a single call and asks for nothing in return.

**What Harry sends:** one line. `18–22°, overcast, 59% rain`.

**When this stops working**, the weather line on the morning page says `Weather unavailable`
and everything else renders. Nothing reaches Slack, deliberately: there is no credential to
lapse, and an unavailable weather line looks like nothing else on the page — you would
notice on day two. The reasoning is on the requirements page rather than in somebody's head.

## The words

Open-Meteo answers with a WMO weather code, an integer. Harry turns it into a word with a
fixed table and nothing else. Intensity is dropped — "moderate rain" and "heavy rain" are
the same decision about a coat, and the shorter line is the readable one.

**A code the table does not have gives no word and the three numbers**, so the page reads
`18–22°, 59% rain`. That is true and useful, where a word Harry invented for a condition it
does not recognise would be neither. The code is logged so it can be added.

## Setting it up

Nothing. It ships pointed at Leuven and works from a fresh clone.

To point it somewhere else, put what differs in `.env.local` beside this file — never in
`.env`, which is generated:

```bash
cat > .harry/connectors/weather/.env.local <<'ENV'
LATITUDE=51.05
LONGITUDE=3.72
PLACE=Ghent
ENV
```

## When it stops working

| What happened | What you see | What to do |
|---|---|---|
| Open-Meteo is down or unreachable | `Weather unavailable` | Nothing. One attempt, five seconds, and tomorrow is a new call |
| It answers a shape this connector does not understand | `Weather unavailable`, logged | Check open-meteo.com/en/docs — a free endpoint may have changed |
| A WMO code with no word | `18–22°, 59% rain`, and the code in the log | Add the code to the table in `connector.py` |
| Coordinates in the sea | A forecast for the sea | Nothing validates this, and nothing can |
