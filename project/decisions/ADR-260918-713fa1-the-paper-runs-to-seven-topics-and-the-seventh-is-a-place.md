---
id: ADR-260918-713fa1
title: The paper runs to seven topics, and the seventh is a place
status: Accepted
created: 2026-09-18
feature: FEAT-260918-4065d5
supersedes: ''
superseded_by: ''
---

# ADR-260918-713fa1 — The paper runs to seven topics, and the seventh is a place

## Status

Accepted

Drives [[FEAT-260918-4065d5]].

## Context & problem

The reader wants news from Oostende, Leuven and Holsbeek on the morning page. The page has
six topics, and `marks.py` says why there are six:

> Six, because six shapes stay distinguishable at eleven points and a seventh would not.

That is a claim about a printed page, and no test asserts it — `len(TOPICS)` is read
nowhere. So it was settled by printing one. `scratch/regional-look.py` patched a seventh
topic into the table in memory and rendered today's real stories through the real tool.

What came back, on 2026-09-18:

- A pin at eleven points is distinguishable from the house, the globe, the chip, the book,
  the ball and the spark. The front page carried two Nearby picks at 1 and 2, each marked,
  above a `belgium` pick marked with the house.
- The second sheet headed its first section "Nearby" and ran it above "At home" without any
  change to how the other sections draw.
- Nothing else in the layout moved.

The six-shape limit was a reasonable guess that turned out not to bind. The page has room.

**The second half of the problem is that the sources do not carry these towns.** VRT NWS's
national feed carried two stories naming Oostende or Leuven in fifty on that day, and
Holsbeek — about ten thousand people — will not appear in a national feed in a normal week.
VRT's own regional feeds answer **410 Gone**.

## Decision drivers

- **Explainable** — the reader picks the paper up over coffee and should know where to look
- A topic is what decides the running order, so adding one is a layout decision, not a label
- Nothing that makes Harry judge what a story is about
- Sources that can be added the way every other feed is: a line in `.env.local`

## Considered options

### Option 1: A seventh topic, `regional`, printed as "Nearby", running first

A new entry at the head of `TOPICS`, with a pin. Claude assigns it on the morning, like every
other topic.

**For:** the running order becomes what the reader's attention already is — my towns, my
country, the world, then the rest. Measured to render correctly before it was chosen.
**Against:** overturns a written constraint, so the reasoning has to be written down. One more
shape for a reader to learn.

### Option 2: Keep six, and fold local news into `belgium`

Nothing changes in the code. A Leuven story is a Belgian story, which it is.

**For:** no layout change, no new shape, no ADR.
**Against:** it does not answer the request. A Holsbeek council decision and a federal budget
would print under the same heading in the same order, and the local one would lose every
time — the reader wants them separated precisely because they are not the same kind of news.

### Option 3: A seventh topic, running last

`regional` after `oddity`, so the front page keeps its current shape.

**For:** a day with nothing nearby looks exactly like today's page.
**Against:** it buries the section the feature exists to add. The oddity is deliberately the
last thing read; putting the reader's own town after it says the town matters less.

### Option 4: Harry matches town names against the headlines

A keyword rule: any headline naming the three towns is `regional`.

**For:** no judgement needed from Claude, and no brief change.
**Against:** **it is the thing this repo does not do.** `marks.py` already says why — a
keyword rule files every article mentioning a company under technology on the day one of them
is about a court case. "Oostende" appears in a story about a national basketball club's away
game. Which topic a story belongs to is judgement, and judgement is Claude's.

## Decision outcome

**Option 1, with the position reversed on the day: seven topics, `regional` printed as
"Nearby" and running near the back** — after basketball, before the oddity.

It was built running first, and the owner moved it once they had seen it. Their reason is the
better one: the three towns are a **standing interest**, like basketball, rather than the
day's news. The front of the paper is what happened; the back is what this reader keeps an eye
on. **Explainable** still drove it, to the opposite arrangement — "news first, my things
after" is the truer sentence.

Two rules came with the move, and they are what make the section affordable:

- **A local paper is filtered before Claude sees it.** A story from a feed named in
  `nearby_feeds` is handed over only if it names one of `nearby_places`, capped at
  `nearby_limit`, and placed last. Without it KW took 17 of the newest 40 and left ROB tv with
  one — the feed that actually covers the towns, squeezed out by the one that covers the
  province.
- **A nearby story leads the front page only when another paper carries it too**, enforced by
  `digest_build` refusing a front-page `regional` pick with an empty `also`.

**Does that filter contradict Option 4 below?** It is close, and the line is worth stating.
Option 4 was rejected for deciding **what a story is about** by keyword, which is judgement.
This decides **which candidates are worth handing over** from a paper that files fifty a day,
which is a rule a person could apply by hand — the connector already filters by `query` and
`source` the same way. Claude still assigns every topic. The filter is blunt in both
directions and that is accepted: a Holsbeek story naming only a village inside it is dropped,
and `OH Leuven` matches wherever the club is playing. A filter tight enough to fix either
would be one that reads the story.

The sources come from two feeds that were fetched and read before this was written — ROB tv
for the Leuven area including Holsbeek's neighbours, and KW for West Flanders and the coast.
They are configured exactly as VRT and the BBC are, as `slug=Name=url` in the connector's
`.env.local`, so no code learns their names.

**Oostende is the weak side of this and the owner chose it knowingly.** HLN is the only feed
that is both current and actually about Oostende, and it is out by preference. Of what
remains, Focus-WTV's Oostende feed stopped in March 2014 while still answering 200, Stad
Oostende gives all 146 items the timestamp of the fetch, and Nieuwsblad answers 403. KW
carries the whole province, so Oostende arrives a few items at a time among fifty.

**Which stories are local stays Claude's**, handed over with the pick. The brief names the
three towns. Harry matches town names only to decide which of a local paper's stories are
worth handing over; it never decides what a story is about.

## Consequences

**Good:**

- The running order means something a person can state: the day's news, then the things this
  reader keeps an eye on — basketball, the three towns, and the one worth repeating.
- The six-shape claim is replaced by a rendered page rather than a second opinion. The spike
  that produced it was thrown away — `scratch/` is gitignored, so nothing here survives a
  merge — which is why what it measured is written out above instead of pointed at. The
  method is the reusable part: patch `TOPICS` in memory, render a real day through
  `digest_build` with `deliver=false`, and look at the first two pages.
- Adding the feeds costs no code, which is the property the news connector was built for.

**What this makes harder:**

- **An eighth topic is now a real question rather than a settled one.** Seven shapes were
  measured; eight were not, and the next person will find the constraint gone rather than
  proven. The spike is the thing to run again, not the docstring to edit.
- **The front page has one more claim on it.** Six picks now include up to two local stories,
  so a day with a heavy national story and a good local one is a harder choice for Claude,
  not an easier one. The brief still asks for six.
- **Oostende is thinly covered**, by choice. KW is a province rather than a town, so most
  mornings it brings nothing local and the Nearby section is Leuven-area only. If that turns
  out to be too quiet, the source to add back is the one already ruled out on taste rather
  than a new one to go looking for.
- **Nearby stories are never illustrated.** VRT carries a picture on every entry; ROB tv and
  KW carry none — 0 of 8 each. Since the section now sits at the back this costs little, but a
  nearby story that does earn the front page will be the plain card among illustrated ones.
  The pictures are absent at the source, so there is nothing to configure.
- **The front-page rule can be satisfied without being met.** Harry checks that an `also`
  exists, not that it names a national paper, so two local papers covering the same event
  would pass. That is deliberate — the alternative is Harry deciding which sources count —
  but it means the rule is only as good as the brief Claude is following.
- **Two more feeds are two more things that can fail quietly.** A Nearby section with one
  story looks exactly like a quiet week, which is why a failed feed has to reach
  `unavailable` and the intro.
