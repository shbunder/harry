# Where the morning page gets its facts

Each source is one folder under `.harry/connectors/`, with its runbook in its own
`CONNECTOR.md` — beside the code it is about, rather than in a page somebody has to
remember exists. This page is the index and the part that is true of all of them.

| Source | Needs | What the page loses without it |
|---|---|---|
| [weather](../.harry/connectors/weather/CONNECTOR.md) | nothing | the weather line |

*(calendar, news, De Tijd and the tablet arrive as their own features.)*

## What every source promises

The page calls each one the same way, and the contract was written down before any of them
existed:

```
weather.today()          → {summary, high, low, rain_chance}, or None
calendar.today()         → [{at, title, where}]
news.candidates(limit)   → [{id, title, source, published, summary}], newest first
news.article(id)         → {id, title, source, published, text}
tablet.push(path, name)  → {where}
```

**A source that cannot answer returns nothing rather than raising.** One dead source costs
one section of the page; everything else renders. That is not politeness, it is the whole
reason the page is worth having on a morning when something is broken.

## Weather

Open-Meteo. No account, no key, one call.

```
18–22°, overcast, 59% rain
```

Ships pointed at Leuven and works from a fresh clone. To point it somewhere else, put only
what differs in `.env.local` beside the declaration — never in `.env`, which is generated:

```bash
cat > .harry/connectors/weather/.env.local <<'ENV'
LATITUDE=51.05
LONGITUDE=3.72
PLACE=Ghent
ENV
```

**Claude can ask for it directly**, with the `weather_forecast` tool. It is deferred like
most tools, so a session finds it with `harry_find_tools("weather")` first.

**When Open-Meteo is down**, the page says `Weather unavailable` and the tool answers
`{"available": false, "why": "open-meteo did not answer within 5s"}` rather than failing. A
forecast nobody can get is an answer, not an error — a tool that raises tells the model it
did something wrong, and it did not.

**Nothing reaches Slack, and weather is the deliberate exception.** Every other source
alerts when it degrades, because a page that quietly lost a source three weeks ago looks
exactly like a page that had nothing from it that day. Weather is different twice over:
there is no credential to lapse, and `Weather unavailable` where a forecast belongs looks
like nothing else on the page. You would notice on day two.

The word comes from a fixed table of WMO codes. Intensity is dropped — "moderate rain" and
"heavy rain" are the same decision about a coat. **A code the table does not have gives the
three numbers and no word**, so the line reads `18–22°, 59% rain`: true and useful, where an
invented word would be neither. The code is logged so it can be added.
