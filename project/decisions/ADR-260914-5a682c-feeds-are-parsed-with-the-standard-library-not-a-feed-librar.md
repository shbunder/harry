---
id: ADR-260914-5a682c
title: Feeds are parsed with the standard library, not a feed library
status: Accepted
created: 2026-09-14
feature: FEAT-260912-24d052
supersedes: ''
superseded_by: ''
---

# ADR-260914-5a682c — Feeds are parsed with the standard library, not a feed library

## Status

Accepted

Drives [[FEAT-260912-24d052]].

## Context & problem

Harry reads two news feeds and they are not the same format. The BBC serves RSS 2.0 —
a `<channel>` of `<item>` elements, no namespace. VRT NWS serves Atom — a namespaced
`<feed>` of `<entry>` elements, where the title is `{http://www.w3.org/2005/Atom}title` and
the article link is the one `<link>` out of three with `rel="alternate"`.

That was measured, not assumed. A parser written for RSS 2.0 alone read the 63 KB VRT
document without error and returned zero headlines, because "this feed has no items" and
"I do not understand this document" are the same result.

There are two feeds today. There will be more — the `FEEDS` setting exists so a third is a
line in a file. Whatever reads them has to keep working when someone adds a feed that is
Atom, or RSS 1.0, or RSS 2.0 with a `<dc:date>` instead of a `<pubDate>`.

The obvious answer is `feedparser`: one function, every format since 1999, published
since 2004. Harry already pins five external packages, so one more is not a principle
being broken.

## Decision drivers

- **Explainable.** When a headline comes out wrong, the fix has to be findable by someone
  reading `connector.py` at arm's length, not by reading a normalising layer's rules.
- **Bounded.** Every dependency is code Harry runs on input from the open internet. A feed
  is attacker-adjacent: anybody who can post to a feed Harry reads chooses some of the
  bytes that parser sees.
- **Degrading.** A malformed feed must fail as one unavailable source. That is a property
  of Harry's error handling, and it needs the parser's failure to be an exception Harry can
  name, not a partially-populated result.
- Two feeds today. The cost of a small parser is small at two and grows slowly.

## Considered options

### Option 1: `xml.etree.ElementTree` from the standard library, reading both formats

Roughly 40 lines: try `<channel>/<item>` with no namespace, then Atom `<entry>` with the
namespace, and map each format's fields onto one shape.

**For:** No new dependency. The whole mapping — which element becomes `title`, which link
becomes `link`, which of `pubDate`/`published`/`updated` becomes `published` — is on one
screen, in the file the fix belongs in. A document that is not XML raises `ParseError`,
one exception, which is exactly what the unavailable-source path needs. On Python 3.12
ElementTree does not fetch external entities — `<!ENTITY e SYSTEM "file:///etc/passwd">`
raises `ParseError: undefined entity`, measured, so a feed cannot read the NUC's disk.

**Against:** ElementTree *does* expand internal entities, so a feed carrying a
"billion laughs" bomb — a few hundred bytes of nested entity declarations that expand to
gigabytes — would take the NUC's memory. Measured on 3.12: three levels expanded without
complaint. Harry has to refuse the document itself, which is the `<!DOCTYPE` check below.

**Against:** Harry owns the format knowledge. A feed in a format the 40 lines do not cover
reads as empty until somebody extends them. RSS 1.0 and Dublin Core dates are not handled
on day one. `feedparser` would have handled them without anybody noticing they existed.

### Option 2: `feedparser`

`feedparser.parse(bytes)` returns one normalised structure for RSS 0.9 through 2.0, Atom
0.3 and 1.0, RSS 1.0, and CDF, with dates already parsed and HTML already sanitised.

**For:** Twenty years of other people's edge cases, free. A new feed in any format works
with no change to Harry. Dates in six formats are one `published_parsed` field. It is the
default answer for a reason.

**Against:** It does not raise on a document it cannot read. It sets `bozo` and returns
whatever it salvaged, so "unreadable feed" arrives as a flag on a half-filled object rather
than as an exception — the degradation path would be built on remembering to check a field
instead of on control flow. It is 6,000 lines that run on bytes from the open internet, and it
resolves entities too, so it needs the same refusal. And it is
unmaintained in practice: 6.0.11 is from 2024 and the tracker has open issues older than
this repo.

### Option 3: `httpx` + a regular expression over the XML

**For:** No parser at all.

**Against:** Parsing XML with regular expressions is wrong in ways that are entertaining to
read about and expensive to debug. Listed so that nobody proposes it as the small option;
it is not smaller than 40 lines of ElementTree.

## Decision outcome

**Harry parses feeds with `xml.etree.ElementTree` and maps RSS 2.0 and Atom onto one
candidate shape itself, in `.harry/connectors/news/connector.py`.**

A format the mapping does not cover produces no candidates from that feed, and that is
reported as an unavailable source with the reason, so it is visible in Slack rather than
silent — which is the actual failure this decision is about.

**A feed document carrying a `<!DOCTYPE` before its root element is refused unread.** A news
feed has no legitimate reason to declare a document type, and every entity-expansion attack
on an XML parser has to get its declarations in through one. Refusing it is six lines and
turns the one remaining hole into an unavailable source. `tests/fixtures/news/bomb.xml` is
the recorded bomb, and the test that parses it is what keeps the refusal real.

Adding a format is adding a branch to one function beside the two that are already there.
`feedparser` gets reconsidered when Harry reads a feed the standard library genuinely
cannot, or when there are enough feeds that a normalising layer is cheaper than the
branches. Neither is true at two.

The core principle is **Degrading**: the parser was chosen for how it fails.

## Consequences

**What this makes harder.** Harry now owns feed-format knowledge it did not want. Somebody
adding a feed has to check that it is RSS 2.0 or Atom, and there is nothing that will tell
them it is not except an empty section and a Slack line. The scenario "a configured feed
answers 200 with HTML instead of XML" exists in the requirements because of this decision,
and the test for it is the thing standing between this choice and a silent empty feed.

Dates are Harry's problem too. RSS 2.0 uses RFC 822 (`Mon, 14 Sep 2026 03:38:13 GMT`) and
Atom uses ISO 8601 (`2026-09-14T09:05:56.000Z`). Both are in the standard library, but a
third spelling is a bug rather than a missing feature.

The `<!DOCTYPE` refusal will reject a legitimate feed one day — a feed that quotes the
string in an article description before its root element cannot exist, but a feed that
declares a real DTD can. It would arrive as that source going unavailable in Slack, which is
the right way for a wrong guess to show up.

**What it makes easier.** There is one file to read when a headline is wrong, and it is the
file the headline came from. And the unavailable-source path is driven by an exception,
which is testable by pointing the connector at a fixture full of HTML.
