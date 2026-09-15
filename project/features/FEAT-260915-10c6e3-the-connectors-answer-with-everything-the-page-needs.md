---
id: FEAT-260915-10c6e3
title: The connectors answer with everything the page needs
track: full
created: 2026-09-15
touches: [connectors/icloud, connectors/news, connectors/weather, docs, tools/icloud, tools/news, tools/weather_forecast]
stories: [STORY-260915-58dc98, STORY-260915-98499e, STORY-260915-005396]
decisions: [ADR-260915-c01ab8]
---

# FEAT-260915-10c6e3 — The connectors answer with everything the page needs

## Summary

The morning page was designed once as a spike, and five times it had to go round the back of
a connector to get something it needed: the shape of the day's temperature, when an event
ends, which calendar an event is from, the picture a feed published, and the summary a feed
wrote. Those five are what make the page a page rather than a list — a weather panel with an
hourly strip, a timetable with proportional blocks in the user's own colours, and headlines
with pictures. This closes all five, in the three connectors that own them, and passes each
one on through the tool Claude reads.

## Acceptance criteria

- [x] `weather.forecast()` carries `hours`: seventeen `{at, temperature}` entries, 06:00 to 22:00 local, inclusive
- [x] An Open-Meteo answer with no hourly block gives `hours: []`, leaves the rest of the panel intact, and says nothing in Slack
- [x] `today()` is unchanged: `summary`, `high`, `low`, `rain_chance` and nothing else
- [x] A timed event carries `ends` in the same `"HH:MM"` shape as `at`; an all-day event carries `ends: null`; `at` itself does not change
- [x] Every event carries `calendar` — a CalDAV calendar's display name, or a published link's label
- [x] A CalDAV calendar with no readable name still returns its events, as `calendar: "Calendar"`, and logs that calendar once per read
- [x] Every candidate carries `image` in both `concise` and `full`: the feed's URL or null, with a BBC thumbnail asked for at 800px rather than 240px
- [x] A feed carrying no images gives `image: null` and raises no alert
- [x] `news.article(id)` carries `summary` and `image`, including when the page could not be read
- [x] `weather_forecast`, `icloud_list_events`, `news_search` and `news_article` return the new fields, and each `TOOL.md` says what they are
- [x] `docs/` describes every new field beside the connector that answers it
- [x] An event that runs past midnight has no end to draw today — a three-day conference was otherwise drawing a block from 00:00 to 09:00 across this morning
- [x] An event whose end cannot be read keeps its place on the page as a point in time, rather than being dropped inside the expander with nothing said

The last two were not planned. Both were found by deleting a control and watching no test
go red, and both are the same defect the connector already guards against for a start time:
a meeting disappearing with no trace.

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260915-58dc98]] — The weather answers with the shape of the day
- [ ] [[STORY-260915-98499e]] — Every event says when it ends and whose calendar it is
- [ ] [[STORY-260915-005396]] — A headline carries its picture and its summary

## Lessons Learned

### What worked

**Deleting each control and re-running is the only thing that found the two real bugs.**
Seventeen gates, deleted one at a time. Sixteen turned a test red. The one that did not —
`recurring_ical_events` filling in `DTEND` for an event that has none — is what exposed a
three-day conference drawing a block from midnight to nine across the school run. Reasoning
about that code would never have produced it; the library's behaviour is not in its
signature.

**Recording the failure as a document beats mocking it.** `bad-end.ics`, `no-end.ics`,
`conference.ics` and — best of the four — `leuven-today.json` reused as *the service
answered the day but not the hours*, because it is a real answer from before the hourly
block was ever asked for. That is the exact shape a changed endpoint produces, and no mock
would have been written that way.

**Two passes of the renderer, rather than a constant.** The morning page's calendar column
had a guessed `GRID_ROOM` that was wrong by 40pt in both directions on consecutive days,
because the intro is Claude's text and the all-day band is as tall as today happens to be.
Laying the sheet out once at a deliberately short scale, reading where the timetable
actually starts, then laying it out again with the rest of the page — that is measurement
instead of guessing, and it costs one extra render on a job that runs at 06:30.

### What to do differently

**A field added to a connector is four changes, not one.** Connector, tool body, `docs/`,
and a test that reaches it the way production does. The tool bodies were the ones that
nearly shipped short — `news_article` gained two fields and was not in scenario 9 until the
plan verifier caught it. Write the scenario against *every* tool that returns the shape, not
the obvious one.

**An assertion on a single word proves nothing.** `assert 'calendar' in body` passed with
the entire explanatory paragraph deleted, because that `TOOL.md` already said "calendar"
three times in prose about the calendar app. Assert a phrase only the new text carries.

**The suite's result depends on a gitignored file, and nobody noticed.** Copying this
machine's `.harry/connectors/news/.env.local` into a worktree made 31 news tests reach a
live URL, because the test fixtures copy the whole capability folder. That is `main`'s
state today on this machine, not something this feature introduced — but it means the gate
has been passing or failing on an untracked file. It has its own feature.

### Patterns to reuse

- **`fit()` in `scratch/digest-look.py`** — render, measure the box positions, re-render.
  WeasyPrint reports positions in **CSS pixels**, so multiply by 72/96 before comparing to
  points. A flex box will not split across pages, so it lands wholly on page 2 the moment it
  is one point too tall; measure `.intro`'s bottom rather than the flex box's top, because
  the flex box's top is a lie once it has moved.
- **`Weather._hours`** (`.harry/connectors/weather/connector.py`) — the shape of "this rides
  on a request that is already being made, and it may never raise, because the thing the
  caller actually wanted arrived in the same response".
- **`Agenda._readable`** (`.harry/connectors/icloud/connector.py`) — a library that skips
  silently is a library you touch the fields of yourself, before handing it the document. It
  now repairs an unreadable end rather than losing the event, which is the general shape:
  drop the field, keep the record, say so once.
- **`tests/test_news_connector.py::test_nothing_is_fetched_to_find_out_what_a_picture_is`** —
  `assert len(respx.calls) == 2` is how you hold a decision about what a call must *not* do.
  Any ADR that says "this does not fetch" needs one.
- **The docs assertions** (`test_the_docs_describe_the_shape_of_the_day` and its three
  siblings) — whitespace-normalise the page first, then assert on a phrase long enough to be
  unique. It holds the docs criterion without pretending to judge whether the prose is any
  good.

## Notes

<!-- Appended by `board.py note`. -->
- **2026-09-15** — Reflection: pre-close verifier said REQUEST CHANGES on three Important findings, all fixed on the branch — four docs criteria with no test behind them, one assertion that matched prose predating the change, and a degradation row promising a weather alert that has never existed. Traceability 13/13 after adding the two behaviours nobody had written down. Degraded paths actually exercised: no hourly block, an unreadable hourly reading, mismatched hourly arrays, a calendar that raises on its own name, a calendar with an empty name, an event whose DTEND is nonsense, a feed with no pictures, an article page answering 403. Seventeen controls deleted one at a time; sixteen went red first time, the seventeenth found a real bug. Scope drift: two unplanned behaviours, both defects the plan did not anticipate, both now criteria.

## Links

- Requirements: [[FEAT-260915-10c6e3]]
- Decision: [[ADR-260915-c01ab8]] — A connector hands over a picture's address, never the picture

