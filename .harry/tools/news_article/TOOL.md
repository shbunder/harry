---
name: news_article
namespace: news
description: The full text of one headline from news_search
requires: [news]
always_load: false
annotations:
  readOnlyHint: true
  idempotentHint: true
  openWorldHint: true
enabled: true
---

Fetches one story's page and returns the prose from it — the article, without the
navigation, the related links or the cookie banner.

```
{"available": true,
 "id": "bbc-2026-09-14-russia-hits-ukrainian-train-shortly",
 "title": "Russia hits Ukrainian train shortly after Boris Johnson …",
 "source": "BBC News", "published": "2026-09-14T03:38:13+00:00",
 "link": "https://www.bbc.co.uk/news/articles/cy5zg41dkqwo",
 "summary": "The former UK PM said he was unharmed after the strike …",
 "image": "https://ichef.bbci.co.uk/ace/standard/800/cpsprodpb/715d/….png",
 "text": "A Russian drone has hit a train near the Ukraine-Poland border …"}
```

Takes an `id` from `news_search` — call that first. Reach for this once you have chosen
which stories matter and need to read them: to write about one, to answer a question the
headline does not answer, or to put the text on a page.

**Ask for the ones you picked, not all of them.** Each call fetches a page.

The id is resolved against the feeds each time, so a story that has scrolled off the feed
since you searched gives an error telling you to search again. That is not a fault — it
means the feed moved on.

**When the page cannot be read it answers `{"available": false, "why": …}`** and keeps the
headline, the source, the time, **the feed's own `summary` and the `image`**. Some sites
block scripted clients, and some ids point at a video or a live blog with no prose in it.
Both are answers, not errors: there is nothing to retry. Say what you have — the summary is
real reporting and the headline is still true.

`summary` is always the feed's own one-line description, whether or not the page loaded, so
a story never comes back with nothing to print. `image` is the address of the feed's picture,
or — when the feed published none — the one the article's own page shows when it is shared.
It is still an address and still costs no request of its own: the page was fetched to get the
text out of it. `null` when neither has one.

Not for a URL of your own. It reads the stories Harry's own feeds carry, by their id.
