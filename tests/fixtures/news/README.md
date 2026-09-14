# News fixtures

Everything the news connector is tested against. No test here reaches a URL.

## Recorded, on 14 September 2026

| File | What it is | What was changed |
|---|---|---|
| `vrt-nws.xml` | `www.vrt.be/vrtnws/nl.rss.articles.xml` — Atom, namespaced `<feed>` of `<entry>` | 50 entries cut to the first 8. Nothing else touched |
| `bbc-news.xml` | `feeds.bbci.co.uk/news/rss.xml` — RSS 2.0, `<channel>` of `<item>` | 35 items cut to 8 |
| `bbc-world.xml` | `feeds.bbci.co.uk/news/world/rss.xml` — RSS 2.0 | 25 items cut to 8 |
| `vrt-article.html` | The article behind the first VRT entry, after the `vrtnws.be/p.oL1bKEomY` redirect | Nothing |
| `bbc-article.html` | `www.bbc.co.uk/news/articles/cy5zg41dkqwo` | Nothing |

**The two BBC files overlap on purpose.** Both carry `cy5zg41dkqwo`, `cx2z5gjj838o`,
`cwyzp47py48o` and `c0qx5d79kdeo`. `cx2z5gjj838o` is the useful one: the same story under
two different headlines —

- news: *Watch: Why Russian strike on train could be sign of escalation*
- world: *Watch: Why a Russian strike on train near Ukraine-Poland border could mark an escalation*

That pair is why the connector deduplicates on the link rather than the headline. A test
that used only `cy5zg41dkqwo`, whose headlines match, would pass either way.

`vrt-nws.xml` also carries one entry published 2026-04-20 among seven from September, so
filtering by date has something real to exclude.

## Written by hand

| File | What it is |
|---|---|
| `collision.xml` | Three Atom entries whose first six title words are identical, so two ids must collide. One is published 22:30 UTC, which is the next day in Brussels |
| `bomb.xml` | A "billion laughs" entity bomb. Nine levels of nested entities from about 800 bytes. **Do not parse this file without the `<!DOCTYPE` refusal** — `xml.etree.ElementTree` expands it |
| `not-a-feed.html` | An HTML error page, for a feed URL that answers 200 with the wrong thing |

These three are handmade because no real feed offers them. Everything a real feed can
supply is recorded above.
