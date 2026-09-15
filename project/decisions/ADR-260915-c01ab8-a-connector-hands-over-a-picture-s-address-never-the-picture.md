---
id: ADR-260915-c01ab8
title: A connector hands over a picture's address, never the picture
status: Accepted
created: 2026-09-15
feature: FEAT-260915-10c6e3
supersedes: ''
superseded_by: ''
---

# ADR-260915-c01ab8 — A connector hands over a picture's address, never the picture

## Status

Accepted

Drives [[FEAT-260915-10c6e3]].

## Context & problem

The news connector is about to start carrying the picture each feed publishes. "Carrying a
picture" can mean two quite different things, and the difference decides who pays for it.

The page needs the bytes in the end: a PDF cannot reference a remote image, so somewhere the
picture has to be fetched and embedded. The question is whether `news_search` — a tool Claude
calls over MCP, forty candidates at a time — is where that happens.

Measured against the live feeds while building the design spike: forty candidates carry about
thirty pictures, averaging 90 KB each at the sizes the page uses. Two of the three image
hosts answer a plain request; `images.tijd.be` answers **403 to a bare request and 200 to one
carrying a browser User-Agent**, which is a per-host workaround somebody has to own.

## Decision drivers

- An MCP answer is read by a model and should be kilobytes, not megabytes
- Feed parsing is tested against recorded fixtures with no network at all, and must stay that
  way — `.claude/rules/external-sources.md`
- Thirty pictures would be fetched so that six can be printed
- One slow or dead image host must not make listing headlines slow or failed — **Degrading**
- A per-host workaround should have one owner, not be rediscovered by each caller

## Considered options

### Option 1: the connector returns the URL

`image` is a string, exactly as the feed published it, with one normalisation: a BBC
thumbnail's `/standard/240/` becomes `/standard/800/`, because the same path serves both and
240px is a postage stamp. Nothing is fetched while parsing a feed.

**For:** a `news_search` answer stays a few kilobytes of JSON. A candidate Claude does not
choose costs nothing. Parsing a feed stays a pure function over a document, so the fixtures
keep working. The 403 workaround lands on whoever fetches, once.

**Against:** the digest feature has to do the fetching, with its own timeout and fallback —
work that does not disappear, only moves. A URL can rot between being listed and being
fetched, so the renderer needs a path for a picture that was there a minute ago.

### Option 2: the connector fetches and returns a data URI

**For:** one place does the fetching, and a caller holding a candidate holds everything it
needs. A dead image URL is discovered while listing rather than while rendering.

**Against:** a single `news_search` answer becomes roughly 3.6 MB of base64 through the MCP
transport, for pictures mostly about to be discarded. Every feed parse becomes thirty HTTP
requests, so every test of it needs a network stand-in and the recorded fixtures stop being
enough. One slow image host makes listing headlines slow; a dead one makes it fail.

## Decision outcome

The connector answers with the address. Whoever renders fetches, and owns the per-host
workarounds — including the browser User-Agent that `images.tijd.be` requires.

**Degrading** drove it: a picture host is one more thing that breaks, and the section that
must survive it is the headline list, not the picture. Folding the fetch into feed parsing
would make a dead image host able to take down the list of stories.

This is also the line the connector already draws for text. `article(id)` fetches a page
because a caller asked for that one story; `candidates()` fetches nothing for forty.

## Consequences

**Good:** listing headlines stays one HTTP request per feed. Feed parsing stays testable
against recorded documents. `image` means the same thing to Claude as it does inside Harry —
an address — so nothing has to be explained twice.

**Bad:** it makes the digest feature harder, and deliberately so. That feature now has to
fetch each chosen picture with a timeout, carry the browser User-Agent for `images.tijd.be`,
embed the bytes as a data URI, and render the story without a picture when any of that fails
— four things that would otherwise have been somebody else's problem. A picture that 404s
between `news_search` and `digest_build` is discovered late, at render time, which is the
cost of not fetching early.
