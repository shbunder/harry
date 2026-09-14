---
name: news
description: Headlines from public news feeds, and the full text of a story you pick
provides: [news_search, news_article]
expires: never
enabled: true
config:
  feeds:
    description: 'Every feed, separated by |. Each is slug=Name=url, split on the first two = so a URL can carry as many more as it likes. The slug starts every id from that feed; the Name is what a person reads.'
    default: vrt=VRT NWS=https://www.vrt.be/vrtnws/nl.rss.articles.xml|bbc=BBC News=https://feeds.bbci.co.uk/news/rss.xml
  timezone:
    description: An IANA zone. Decides which day a story is filed under, so "today" means the day where the page is read rather than in UTC.
    default: Europe/Brussels
---

The forty headlines the morning page is chosen from. Harry fetches every configured feed,
turns both formats into one list, and fetches the full text of whatever Claude picks.

**Harry does not choose.** No ranking, no scoring, no summarising. `summary` is the
description the feed supplied, word for word. Choosing six stories out of forty is the
judgement this whole design keeps on Claude's side.

**What Harry sends:** nothing, in the normal case. A feed that fails puts one line in
Slack — `VRT NWS: VRT NWS answered 404` — once per source per 24 hours.

## Two formats, and why that matters

The BBC serves RSS 2.0. VRT NWS serves Atom. Harry reads both, and a feed in a third format
produces no headlines and is reported as unavailable rather than quietly returning nothing.

Adding a feed is a line in `.env.local`. Check first that it is RSS 2.0 or Atom — nothing
will tell you it is not except an empty section and a line in Slack.

## Ids

A candidate's id is the feed slug, the date, and the first five words of the title:

```
vrt-2026-09-14-tessenderlo-ham-hakt-knoop-door
bbc-2026-09-14-russia-hits-ukrainian-train-shortly
```

The date is local — 22:30 UTC is the next day in Brussels, and the id says the day you
would have read it. Two stories from one feed on one day that start the same way get `-2`.

`news_article` resolves that id by re-reading the feeds, so nothing is held between the two
calls. A story that has dropped off the feed by the time you ask for it is an error saying
to search again, not a stale article.

## Setting it up

Nothing. It ships pointed at VRT NWS and BBC News and works from a fresh clone. There is no
credential — both feeds are public.

To change the feeds, put what differs in `.env.local` beside this file — never in `.env`,
which is generated and committed:

```bash
cat > .harry/connectors/news/.env.local <<'ENV'
FEEDS=vrt=VRT NWS=https://www.vrt.be/vrtnws/nl.rss.articles.xml|bbc=BBC News=https://feeds.bbci.co.uk/news/rss.xml|world=BBC World=https://feeds.bbci.co.uk/news/world/rss.xml
ENV
```

A `FEEDS` entry that is not `slug=Name=url` is skipped with a line in the log, and the rest
still load. `FEEDS` empty altogether disables the connector, because a news source with
nothing to read is not degraded, it is misconfigured.

## Fetching

Each feed is downloaded at most once every 5 minutes and reused in between. Building one
morning page is a `news_search` and then a handful of `news_article` calls, each of which
re-resolves its id — without the reuse that is seven downloads of the same two documents.

**A feed that failed is never served from an older success.** A headline list that silently
ages is worse than a short one, because nothing on the page says how old it is.

## When it stops working

| What happened | What you see | What to do |
|---|---|---|
| A feed 404s or is unreachable | That source in `unavailable` with why; one Slack line | Open the URL in a browser. Feed URLs move |
| A feed times out after 10s | The same | Usually transient. It retries on the next call |
| A feed answers HTML — a consent wall, an error page | `the document is not XML`, in `unavailable` | The URL is probably now a web page, not a feed |
| A feed is XML but not RSS 2.0 or Atom | `the document is XML but not a feed`, with its root element | Harry reads RSS 2.0 and Atom. See ADR-260914-5a682c |
| A feed declares its own entities | `the document declares its own entities` | Nothing is wrong with Harry. Refusing it is deliberate — that is how an XML parser is made to eat all the memory on the machine |
| An article page answers 403 | `available: false` with why; one Slack line | The site started blocking scripted clients. It needs a browser session, like De Tijd |
| An article page loads but has no prose | `there was no article text in it` | Usually a video or a live blog. Nothing to do |
| Slack is quiet but a source is clearly dead | Check the log | An alert is sent once per source per 24 hours. The second failure today is silent on purpose |
