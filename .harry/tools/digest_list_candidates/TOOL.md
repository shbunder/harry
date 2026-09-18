---
name: digest_list_candidates
namespace: digest
description: Everything today could contain — the weather, the agenda and the headlines, in one call
optional: [weather, icloud, news]
config:
  nearby_feeds:
    description: 'Feed slugs that are local papers, separated by |. A story from one of these counts only when it names a place in nearby_places. Empty means no feed is treated as local.'
    default: ""
  nearby_places:
    description: 'The places a local story must name to be worth handing over, separated by |. Matched against the title and the summary, case-insensitively.'
    default: ""
  nearby_limit:
    description: How many local stories to hand over at most. They go last in the list, after everything else.
    default: 5
always_load: true
annotations:
  readOnlyHint: true
  idempotentHint: true
  openWorldHint: true
enabled: true
---

Returns everything today could go on the morning page: the weather where it is read, what is
on the calendar, and up to forty headlines with their summaries and ids.

**Local papers are held to a narrower rule.** A feed named in `nearby_feeds` publishes far
more than a national one and almost none of it is about the places this page cares about —
measured on 2026-09-18, one of them put 17 of the newest 40 on the page and pushed the local
feed that mattered down to a single story. So a story from one of those feeds is handed over
only when it names one of `nearby_places`, at most `nearby_limit` of them arrive, and they
come **last** rather than competing on recency. Everything else is untouched.

```
{"date": "2026-09-15",
 "weather": {"available": true, "place": "Leuven", "summary": "overcast",
             "high": 29, "low": 17, "rain_chance": 53,
             "hours": [{"at": "06:00", "temperature": 17, "summary": "clear"}, …]},
 "agenda":  {"available": true,
             "events": [{"at": "09:30", "ends": "10:00", "title": "standup",
                         "where": "meeting room", "calendar": "Shaun"}]},
 "headlines": [{"id": "vrt-2026-09-15-44-gemeenten-vragen-uitstel-voor",
                "title": "44 gemeenten vragen uitstel voor sociale woonplicht",
                "source": "VRT NWS", "feed": "vrt", "date": "2026-09-15",
                "summary": "44 Vlaamse gemeenten vragen uitstel …",
                "image": "https://images.vrt.be/…jpg"}],
 "dropped": 0,
 "unavailable": []}
```

**Reach for this first, every morning.** It is one call instead of three, and the three would
each have to be found first. Read all of it before choosing anything, then pass your choices
to `digest_build`.

**Nothing here is chosen, ranked or summarised.** Headlines come back newest first, which is a
fact rather than an opinion; `summary` is the feed's own words, verbatim. Deciding which six
matter is the reason this tool hands you forty rather than six.

`limit` caps the headlines at 40 by default and 60 at most, and `dropped` says how many did
not fit. `detail` is `concise` unless you ask — each summary cut to 280 characters, which is
enough to tell what a story is about and about a third of the tokens across forty of them.
`detail="full"` gives the whole summary, the exact `published` time and the `link`.

**A section that is not there says so rather than vanishing.** `weather` and `agenda` each
carry `available`; when it is `false`, `why` says what happened. `unavailable` lists every
source that could not answer, by name. **If `unavailable` has an entry, say so** — a short
list of headlines looks exactly like a quiet news day, and a missing agenda looks exactly
like a free morning.

Not a search, and not an archive: it is today, from the sources this Harry is configured
with. For a particular story or an older one, use `news_search`.
