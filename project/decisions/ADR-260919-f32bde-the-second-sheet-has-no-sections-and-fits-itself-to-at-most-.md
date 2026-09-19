---
id: ADR-260919-f32bde
title: The second sheet has no sections, and fits itself to at most two pages
status: Accepted
created: 2026-09-19
feature: FEAT-260919-f580cd
supersedes: ''
superseded_by: ''
---

# ADR-260919-f32bde — The second sheet has no sections, and fits itself to at most two pages

## Status

Accepted

Drives [[FEAT-260919-f580cd]].

## Context & problem

The second sheet was built from sections: a heading per topic, then that topic's stories as
cards four across. The owner said on 2026-09-19 that it **feels too empty**, and asked for
something that fills the page and feels more like a newspaper.

Sections are the cause, not the card size. A section with two stories in a four-across row
leaves half a row white. A section heading costs its height whether it heads one story or
four. And every card is the same size, so nothing on the page leads the eye. The brief
compensated by asking Claude for "about four in each category", because "a section with one
story in it looks broken" — the layout was steering the choice of news.

The owner also set a limit every layout must keep: **the front page, at most two index pages,
then the articles.** Twenty stories is the most the tool accepts, and how much room they take
depends on their headlines, their pictures and their companions, none of which are known
until the morning.

Four section-less designs were rendered from one real morning, a full day of 18 stories and
a light day of 10, and shown to the owner:

| Design | Full day | Light day |
|---|---|---|
| Mosaic — rows of tiles whose widths add up to four | broken: WeasyPrint 70 does not honour grid spans | — |
| Magazine — a hero, three features, a two-column list | 2 pages, the second 47% full | 1 page |
| Featured — a pair, then a three-column list | 2 pages, the second 32% full | 1 page |
| **Broadsheet** — three ruled columns, a picture every few | **1 page, 97% full** | **1 page, 97% full** |

## Decision drivers

- **Explainable** — read at arm's length over coffee; the page should look full and ordered
- The layout must not steer which stories Claude picks
- Never more than two pages of index, whatever the day hands over
- The paper's running order — home, abroad, technology, culture, sport, nearby, the one worth
  knowing — stays
- Only layouts WeasyPrint 70 draws correctly

## Considered options

### Option 1: Broadsheet, with no section headings, fitted to the day

Three columns with rules between them. Stories run in the paper's order and each carries its
topic's mark beside its source. The story opening each run of *k* gets a picture and the first
sentence of its summary; the rest are headline and byline. Harry tries a short ladder of settings for
*k* and the picture's height, renders the sheet alone for each, and keeps the one with the
fewest pages — and among those, the one whose last page is fullest.

**For:** filled a full and a light day to 97% of one page, measured. Columns flow, so a topic
with one story costs one story's height, not a row. Fitting is a rule written down in advance
— try these nine, keep the fewest pages and then the fullest — so it is Harry's to do. The topic stays visible, as a
mark in its own colour.
**Against:** the reader loses the heading that said where one subject ends and the next
begins; they read it from the marks instead. Fitting costs a render per setting — about a
second each.

### Option 2: Keep the sections, and lay them out denser

Sections in two flowing columns, or each section as a lead with a list beside it. Both were
rendered that morning before the section-less designs.

**For:** the reader can find "Culture" by its heading. Nothing about the order changes.
**Against:** a heading still costs its height over one story, and a one-story section still
looks thin. The brief would keep asking for "about four in each category" to hide it — which
is the layout choosing the news.

### Option 3: A fixed section-less shape — Magazine or Featured

A hero or a pair at the top, then a list.

**For:** a strong lead gives the page a front of its own.
**Against:** one shape for every day. A full day ran to a second page that was half white,
and there is no dial to turn without redesigning. The hero is also a ranking, and ranking
is Claude's, not Harry's.

## Decision outcome

**The second sheet has no sections: it is set as a broadsheet in three columns, each story
marked with its topic, in the paper's running order — and Harry fits it to the day, taking
the fewest pages and then the fullest last page.** Fewest first, because a day that fits one
page should get one page; a fuller second page is not worth turning to. Driven by
**Explainable**: a page that fills reads as a paper, and one with white under every row reads
as broken.

The brief stops asking for "about four in each category". A category gets what the day has.

## Consequences

**Good:** the sheet fills on a light day and on a full one, without anyone choosing a number
for that day. The brief no longer bends the news to fit the layout. The ladder's leanest
setting is what keeps a full day to two pages; `SECOND_SHEET_PAGES` stays as the report for
the day it does not, and `crowded` says so.

**Bad:** **there is no longer a place on the page that says "Culture".** A reader looking for
one subject scans for its mark. The topic's longer heading — "At home", "And one more thing"
— has nothing left to print it, and goes.

**Harder:** the layout is now measured, not declared. The sheet's height depends on the ladder,
the fonts and WeasyPrint's column balancing, so a test can assert that it fits and that it
chose the fullest setting, not what it will look like. A change to the stylesheet can move
which setting wins, and only a render shows it.
