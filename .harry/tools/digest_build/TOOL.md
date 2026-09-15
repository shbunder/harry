---
name: digest_build
namespace: digest
description: Build the morning page from the stories you chose, and put it on the tablet
optional: [news, weather, icloud, remarkable]
config:
  name:
    description: What the journal calls itself, on the masthead
    default: The Morning Page
  colours:
    description: Which ink each calendar is drawn in — Shaun=yellow|Kids=pink. One of yellow, green, pink, blue, red, purple, grey; a calendar nobody names gets grey
    default: ""
  out_dir:
    description: Where the PDF is written. It stays there whether or not a tablet took it
    default: /data/digest
  timezone:
    description: Which day "today" means, and the clock the timetable prints
    default: Europe/Brussels
always_load: true
annotations:
  readOnlyHint: false
  destructiveHint: true
  idempotentHint: true
  openWorldHint: true
enabled: true
---

Takes what you chose from `digest_list_candidates` and turns it into the morning page: a front
sheet, a second sheet of everything else, and a page for every article. Then it puts the PDF
on the tablet.

```json
{"intro": "A full Tuesday: the school run at seven, then meetings stacked three deep …",
 "picks": [{"id": "vrt-2026-09-15-44-gemeenten-vragen-uitstel-voor",
            "note": "Forty-four municipalities asking to be excused from the housing duty.",
            "topic": "belgium"},
           {"id": "vrt-2026-09-15-treinverkeer-in-nederland-zwaar-verstoord",
            "note": "Dutch rail is down and sabotage is suspected. Three papers, three angles.",
            "topic": "world",
            "also": ["bbc-2026-09-15-suspected-sabotage-causes-major-netherlands"]}],
 "more":  [{"id": "vrt-2026-09-15-robots-nemen-eentonig-werk-over", "topic": "tech"}]}
```

**`picks` is the front page** — six or so, each with a `note`, which is the line you write
about why it is worth their time. It goes on the page above the article, unedited. **`more`
is the second sheet** — ten to twelve others, grouped by subject, and no note: a card there is
a glance, not an argument.

`topic` is one of `belgium`, `world`, `tech`, `culture`, `sport`, `oddity`, and it decides
where a story sits. **The whole paper is laid out in that order** — home, abroad, technology,
culture, sport, and the one worth knowing — so the topic is not decoration, it is the
running order.

`also` lists the ids of other pieces on the **same event**. They appear under the lead on the
front page, in full at the foot of its article, and each gets a page of its own.

**Nothing here is chosen, rewritten or summarised.** Which stories, what to say about them,
which are the same event, what subject each belongs to — all of it is yours and arrives on
this call. Harry sorts, fetches, draws and delivers.

An id that lost or gained a word still finds its story: if exactly one candidate's id begins
yours, or yours begins exactly one, it resolves — and `resolved` in the answer says which, so
you can see it happened. An id matching none or several is an error naming what it could have
meant.

**Up to 12 on the front page and 20 on the second.** Past that it is not a morning page.

This blocks for a minute or two: it fetches every article and every picture. The answer says
how many pages, whether either sheet ran over, and what the tablet said.

**A second build for the same day replaces the first on the tablet** rather than sitting
beside it, so calling this twice leaves one document. The page is also on disk either way, at
the path in the answer.
