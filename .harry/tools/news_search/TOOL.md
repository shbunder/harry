---
name: news_search
namespace: news
description: Today's headlines from the configured news feeds, newest first
requires: [news]
always_load: false
annotations:
  readOnlyHint: true
  idempotentHint: true
  openWorldHint: true
enabled: true
---

Returns the headlines Harry's news feeds are carrying right now — VRT NWS for Belgium and
BBC News for the world, unless this Harry is configured differently. Newest first, 20 by
default, never more than 50.

```
{"candidates": [
   {"id": "vrt-2026-09-14-tessenderlo-ham-hakt-knoop-door",
    "title": "Tessenderlo-Ham hakt knoop door: vanaf 1 januari 2027 …",
    "source": "VRT NWS", "feed": "vrt", "date": "2026-09-14",
    "summary": "Het OCMW van Tessenderlo-Ham zet de maaltijdbedeling …",
    "image": "https://images.vrt.be/vrtnws_share/2026/09/14/c2dac003-….jpg"}],
 "unavailable": []}
```

Reach for this when you need to know what happened today, or to choose stories for
something — a digest, a briefing, an answer about the news. It gives you headlines and the
feed's own one-line summary, which is usually enough to choose from. Pass an `id` to
`news_article` for the full text of the ones you want.

Narrow it rather than reading everything: `source` takes a feed slug (`vrt`, `bbc`), `since`
takes a date (`2026-09-14`) and keeps anything published on or after it, and `query` keeps
candidates whose title or summary contains it.

`detail` is `concise` unless you ask otherwise — the summary cut to 200 characters, which is
enough to tell what a story is about and about a third of the tokens across twenty of them.
`detail="full"` adds the whole summary, the exact `published` time and the `link`. Ask for
`full` when you need the URL or the time of day; `concise` is right for choosing.

**`unavailable` is not decoration.** A feed that is down makes this list shorter and
nothing else — it looks exactly like a quiet news day. If `unavailable` has an entry, say
so rather than reporting that there was little news.

`summary` is the feed's own text, not Harry's. Nothing here is ranked, scored or
summarised by Harry; the order is by time published and nothing else.

`image` is the address of the picture the feed published, or `null` when it published none —
De Tijd, for one, never does. **It is an address, not a picture:** nothing is fetched to
answer this call. Whoever renders the page downloads it. Use it to tell which stories can
lead a page with a photograph and which will be text.

Not a search of the whole internet, and not an archive. It is what the configured feeds are
carrying now — roughly the last day or two.
