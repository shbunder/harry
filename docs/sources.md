# Where the morning page gets its facts

Each source is one folder under `.harry/connectors/`, with its runbook in its own
`CONNECTOR.md` — beside the code it is about, rather than in a page somebody has to
remember exists. This page is the index and the part that is true of all of them.

| Source | Needs | What the page loses without it |
|---|---|---|
| [weather](../.harry/connectors/weather/CONNECTOR.md) | nothing | the weather line |
| [news](../.harry/connectors/news/CONNECTOR.md) | nothing | the headlines, and the articles chosen from them |

*(calendar, De Tijd and the tablet arrive as their own features.)*

## What every source promises

**The page itself is not built yet** — weather and news are. The contract below was written
down first, deliberately, so each source has something to satisfy rather than an interface
invented when the page finally calls it:

```
weather.today()          → {summary, high, low, rain_chance}, or None
calendar.today()         → [{at, title, where}]
news.candidates(limit)   → [{id, title, source, feed, published, date, summary, link}], newest first
news.article(id)         → {available, id, title, source, published, link, text}
tablet.push(path, name)  → {where}
```

News carries three fields beyond what was first written down. `feed` is the slug you filter
by, `date` is the local day the id is built from, and `link` is what makes a headline
clickable on a page. `article()` carries `available`: on a page that will not load it is
`false`, there is no `text`, and `why` says what happened — **the headline, the source and
the time are still there**, so the page can print the story and say the text could not be
read.

**A source that cannot answer today's question returns nothing rather than raising** — the
one exception being `news.article(id)`, which raises on an id it does not know, because that
is a caller asking for something that was never offered rather than a source being down.

One dead source costs one section of the page; everything else renders. That is not
politeness, it is the whole reason the page is worth having on a morning when something is
broken.

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

## News

Two public feeds, no credential: VRT NWS for Belgium and BBC News for the world. Harry
fetches both, turns them into one list of candidates, and fetches the full text of whatever
Claude picks.

**Harry does not choose.** No ranking, no scoring, no summarising. `summary` is the feed's
own description, word for word. Choosing six stories out of forty is Claude's job, and the
two tools stay separate so that choice happens where the judgement is.

```
vrt-2026-09-14-tessenderlo-ham-hakt-knoop-door   VRT NWS
bbc-2026-09-14-russia-hits-ukrainian-train-shortly   BBC News
```

An id is the feed slug, the date and the first five words of the title. The date is local —
a story published 22:30 UTC is filed under the next morning, which is the day you would have
read it.

**Claude reaches it with two tools**, both deferred, so a session finds them with
`harry_find_tools("news")` first:

- `news_search(query, source, since, limit, detail)` — the headlines. 20 by default, never
  more than 50. `detail` is `concise` unless you ask, which cuts each summary to 200
  characters and costs about a third of the tokens.
- `news_article(id)` — the full text of one of them, with the navigation and the cookie
  banner removed.

`news_article` resolves the id by re-reading the feeds, so nothing is held between the two
calls. A story that dropped off the feed since the search is an error telling you to search
again, not a stale article. Each feed is downloaded at most once every 5 minutes, which is
what keeps that from costing seven downloads per page.

### Configuring the feeds

Ships pointed at VRT NWS and BBC News and works from a fresh clone. Adding a third is a
line in `.env.local` beside the declaration — never in `.env`, which is generated:

```bash
cat > .harry/connectors/news/.env.local <<'ENV'
FEEDS=vrt=VRT NWS=https://www.vrt.be/vrtnws/nl.rss.articles.xml|bbc=BBC News=https://feeds.bbci.co.uk/news/rss.xml|world=BBC World=https://feeds.bbci.co.uk/news/world/rss.xml
ENV
```

Feeds are separated by `|`, and each one is `slug=Name=url` split on the first two `=`.
Harry reads RSS 2.0 and Atom; check a new feed is one of those, because nothing will tell
you it is not except an empty section. An entry that is not `slug=Name=url` is skipped with
a line in the log, and a `FEEDS` with nothing usable in it skips the connector entirely — a
news source with nothing to read is misconfigured, not degraded.

### When a feed dies

**One line reaches Slack**, once per source per 24 hours:

```
VRT NWS: VRT NWS answered 404
```

That is the whole point of the feature. A dead feed makes the candidate list shorter and
nothing else — it looks exactly like a quiet news day, where `Weather unavailable` on the
page is unmissable. The Slack line is the only thing that tells the difference. It carries
the source name and a sentence, never the feed URL and never anything from the response.

The other feeds still return, and `news_search` lists what failed:

```json
{"candidates": [...], "unavailable": [{"source": "VRT NWS", "why": "VRT NWS answered 404"}]}
```

`candidates()` — what the page calls — stays a plain list and never grows an `unavailable`
key. It cannot report a dead feed and it is not asked to.

**A feed that failed is never served from the last success.** A headline list that silently
ages is worse than a short one, because nothing on the page says how old it is.

An article page that blocks Harry or has no prose in it answers
`{"available": false, "why": …}` and puts one line in Slack the same way. Usually that is a
site that started blocking scripted clients — the De Tijd problem, which needs a browser
session — or an id pointing at a video.

**A feed is refused unread if it declares its own entities.** That is deliberate: it is how
an XML parser is made to allocate all the memory on the machine, and a news feed has no
reason to carry entity declarations. See
[ADR-260914-5a682c](../project/decisions/ADR-260914-5a682c-feeds-are-parsed-with-the-standard-library-not-a-feed-librar.md).
