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

Measurement from the spike, against the live feeds: forty candidates carry about thirty
pictures, averaging 90 KB each at the sizes the page uses. Two of the three image hosts
answer a plain request; `images.tijd.be` answers **403 to a bare request and 200 to one with
a browser User-Agent**, which is a per-host workaround somebody has to own.

## Options

### 1. The connector returns the URL (chosen)

`image` is a string, exactly as the feed published it, with one normalisation: a BBC
thumbnail's `/standard/240/` becomes `/standard/800/`, because the same path serves both and
240px is a postage stamp. Nothing is fetched while parsing a feed.

- A `news_search` answer stays a few kilobytes of JSON, which is what an MCP answer should be
- A candidate Claude does not choose costs nothing. Thirty pictures are fetched to print six
- Parsing a feed stays a pure function over a document, which is what makes it testable
  against a recorded fixture with no network at all
- The 403 workaround lands on whoever fetches, which is the renderer, once

### 2. The connector fetches and returns a data URI

- A single `news_search` answer becomes roughly 3.6 MB of base64 through the MCP transport,
  for pictures that are mostly about to be discarded
- Every feed parse becomes thirty HTTP requests, so every test of it needs a network stand-in
- One slow image host makes listing headlines slow, and a dead one makes it fail

Rejected on the first point alone. The rest is why it is not close.

## Decision

The connector answers with the address. Whoever renders fetches, and owns the per-host
workarounds — including the browser User-Agent that `images.tijd.be` requires.

This is the same line the connector already draws for text: `article(id)` fetches a page
because a caller asked for that one story, while `candidates()` fetches nothing for forty.

## Consequences

- The digest feature must fetch and embed pictures, with a timeout and a fallback to no
  picture. That belongs in its requirements, and it is where the browser User-Agent lives
- A URL that 404s by the time it is fetched costs one picture, not the page
- `image` is a URL in the tool surface, so the field means the same thing to Claude as it
  does inside Harry
