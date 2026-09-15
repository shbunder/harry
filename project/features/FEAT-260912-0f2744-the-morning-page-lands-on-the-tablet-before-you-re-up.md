---
id: FEAT-260912-0f2744
title: The morning page lands on the tablet before you're up
track: full
created: 2026-09-12
touches: [core, docs, jobs/morning-page, scripts, tools/digest]
stories: [STORY-260914-397bbd, STORY-260914-abef7c, STORY-260914-46e9e7]
decisions: [ADR-260913-c477cd, ADR-260913-210e08, ADR-260912-b22e46, ADR-260912-bd36c2]
---

# FEAT-260912-0f2744 — The morning page lands on the tablet before you're up

## Summary

What all of it is for. At 06:30 a Claude scheduled task asks Harry for candidates, decides what matters, writes a short intro and asks for the page. Harry fetches the chosen articles, renders the PDF and pushes it. Not headlines: the full articles, as pages behind the front page.

## Acceptance criteria

<!-- One box per scenario. These are what the pre-close-verifier builds its
     traceability matrix from. -->

- [x] A capability may declare a connector `optional:` — handed over when it loaded, absent when it did not, and the capability still loads
- [x] `requires:` still refuses a capability whose connector is missing, and `make lint` refuses an `optional:` naming a connector that does not exist
- [x] digest_list_candidates calls weather.forecast(), calendar.today() and news.search(limit) and returns their answers, and returns the same shape with no sources loaded at all
- [x] Candidates come back newest first, capped at limit, and a capped answer says how many were dropped; summary is the source's own text, truncated at 280 characters under concise
- [x] A source that raises, and a source that returns None, both leave that section reading "unavailable" rather than blank, with the others intact
- [x] digest_build takes an intro, picks of id/note/also/topic for the front page, and a `more` list of id/also/topic for the second; the front page carries the intro verbatim
- [x] Each picked article appears with the note Claude wrote above its text, unedited
- [x] An article whose text could not be fetched still appears with its headline and note, saying the text was unavailable
- [x] digest_build resolves each pick with news.article(id), so nothing is held between the two calls, and an id the source does not know is an error naming it
- [x] picks is capped at 12
- [ ] digest_build emits a progress notification per article so the call survives past 300 seconds — **not built**, see the note below
- [x] The page renders at exactly 509.34 by 679.13 points, its left margin 24 points wider than the others, with an outline entry per article in the paper's own topic order
- [x] The masthead carries the configured name, and the date on its own baseline with the weekday under it
- [x] The weather panel carries an icon for the day and four hours each with a temperature and an icon of its own
- [x] Each event is a block as tall as its own length, drawn in its calendar's colour, with a legend naming only the calendars that have something on today
- [x] Three events overlapping at 09:00 are each a third of the column wide, and an event alone at 20:00 is the full width
- [x] Nothing crosses the bottom or right margin whatever length the intro runs to, and the answer says so when the day column will not fit on the front sheet — the timetable fills the column on a day with enough hours in it, and is capped at 34 points an hour so a quiet day does not become a spreadsheet
- [x] Each index entry carries its number, its topic mark, its headline, its source and its picture
- [x] A pick carrying `also` shows two "see also" links and a count of the rest, and every companion has its own page reachable from the lead and from the front page
- [x] Every headline, thumbnail, companion and way out is a link annotation in the PDF
- [x] A picture is fetched with a browser User-Agent, and one that cannot be fetched costs the picture and nothing else
- [x] The reader sets the journal name and the calendar colours; Claude sets the intro, the picks, the notes, the grouping and the topics, on the call
- [x] The second page is one sheet of ten to twelve more stories, three across, in sections ordered home, abroad, technology, culture, sport, oddity — and a section with nothing in it is not drawn
- [x] Article pages run in that same order, front-page stories and second-page ones together
- [x] Every card on the second page is a link to its own article page
- [x] An id where exactly one candidate's id begins it, or which begins exactly one candidate's id, resolves to that candidate; the answer lists every id it had to resolve and what it became; no match or two matches is an error naming the id and the candidates it could have meant
- [x] An id that is a beginning of two candidates is refused rather than guessed, and an exact match always wins — the news connector disambiguates a collision by appending `-2`, so one candidate's id **can** be a prefix of another's and the rule has to survive it
- [x] The morning-page brief produces a valid answer on Haiku and on Sonnet against a real morning's candidates — `by inspection: the gate cannot run a model. Run three times against 2026-09-15's forty candidates — Sonnet once, Haiku twice. Sonnet passed every mechanical rule; Haiku got the counts, topics and grouping right both times and the ids wrong both times, in opposite directions, which is where the resolution rule came from. Recorded in the requirements, Scenario 8`
- [x] With no tablet the page is written to out_dir/<date>.pdf and the answer quotes the path; with one, tablet.push is called and the answer quotes what it returned, and the page stays on disk
- [x] The morning-page job is one markdown file whose brief is served as a prompt and tells Claude the three calls to make
- [x] `make digest-dry PICKS=…` renders to out/<date>.pdf through scripts/call_tool.py with no server and no push, and prints what did not load
- [x] `make digest-now` is removed — it names a module that never existed, and pushing is another feature's
- [x] Both digest tools are always_load, because a tool-search round trip at 06:30 is a failure mode with no upside

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260914-397bbd]] — A capability can declare a connector optional and still load without it
- [ ] [[STORY-260914-abef7c]] — Claude can see what today could contain, and pick from it
- [ ] [[STORY-260914-46e9e7]] — The page carries what Claude chose and what Claude wrote about it

## Lessons Learned

### What worked

**Designing in a throwaway and showing it.** `scratch/digest-look.py` rendered the real page
from the real sources and was revised five times on its reader's notes before a line of it
became a tool. The first attempt was rejected in one sentence — *"not at all what I had in
mind"* — and that cost an afternoon of a spike rather than a feature. The requirements page
was then rewritten to match what had been approved, which is the only reason it describes a
newspaper rather than a list.

**Running the brief on the model that will actually run it.** Three runs against a real
morning's forty headlines — Sonnet once, Haiku twice. The judgement was right every time: six
picks, the topics, the grouping, no sport on a day with no basketball. What broke was
clerical, twice, in opposite directions: ids truncated on the first run and **lengthened** on
the second, after the brief had been rewritten to warn about exactly the first failure. That
is what turned "write it more clearly" into "this is Harry's job", and it is not a conclusion
reasoning would have reached.

**Deleting each control and counting.** Nine on `digest_build`, six on `digest_list_candidates`,
three on the loader. Two of my own tests could not fail and were rewritten: the picture-cache
one asserted an empty dictionary after a build with no pictures in it, and the "second sheet
overflows" one used cards with no pictures, which are half the height.

### What to do differently

**A source that reports its own failure is not a source that raises.** `section()` wrapped
every answer in `available: True`, and the weather connector — the one source that catches its
own errors and answers `{'available': False, 'why': …}` — was therefore reported to Claude as
working, with an empty `unavailable`. Three tests exercised the *raising* path and none the
answering one, because the stand-in's `how.get('answer') or WORKING` made the failing shape
unexpressible. **A fixture that cannot express a failure hides it.**

**Ask what a helper does when its subject already exists.** `_retire`, `_deliver`, `_forecast`
— three places this session where the real question was "what happens when this fails *after*
the important thing succeeded". A push that fails must not lose the path to a page that is
already rendered.

**Coverage was measuring nothing under `.harry/` and nobody noticed.** It was listed in
`source` and the tracer never discovered the files, because capability tests load copies under
`/tmp`. The first test to load the real tree took the total from 92% to 69%. The percentage
has never said anything about connector or tool code — mutation probing is the only evidence
there. `[tool.coverage.paths]` aliasing is the fix and it is smaller than it looks.

**A criterion written before the code can be false rather than unmet.** "The timetable ends
within 10 points of the bottom margin" — `hour_height` caps at 34 points an hour on purpose,
so a quiet day leaves 200 points of white and always will. "Candidates never have ids that
begin one another" — they do, by design, because `_unique` appends `-2`. Both were ticked.
Re-read the criteria against the code at close, not just the tests against the criteria.

### Patterns to reuse

- **`inside(catalogue, name)`** (`tests/test_digest_build.py`) — digs one function out of the
  loaded tool's own globals instead of importing the capability by path. `.harry` is off
  pytest's path on purpose; this respects that and still allows a unit-level assertion.
- **`scripts/call_tool.py`** — calls any tool by name with JSON arguments, no server and no
  client, and learns no capability's name. `test_call_tool_knows_no_capability_by_name` parses
  its AST and blanks the string constants first, so the guard bans the name in the code
  without banning the explanation in the docstring.
- **The two-pass `fit`** (`.harry/tools/digest_build/page.py`) — render, measure the boxes,
  render again with what you measured. WeasyPrint reports positions in CSS pixels, so multiply
  by 72/96 before comparing to points.
- **`tests/fixtures/digest/connectors/`** — four stand-in connectors steered by one JSON plan
  file named in an environment variable. One folder covers "answers", "raises", "reports its
  own failure" and "is not there", which is four folders' worth of fixture otherwise.

## Notes

- **2026-09-15** — the progress notification is the one criterion here that is not built. `digest_build` blocks for a minute or two and a silent MCP call is aborted at 300 seconds, so it is a real risk on a slow morning, not a nicety. It needs a way for a capability to reach `context.report_progress`, which is an SDK change and therefore its own feature rather than a line in this one. Measured today: a full build with eighteen articles took about ninety seconds.

<!-- Appended by `board.py note`. -->
- **2026-09-14** — 2026-09-14: returned to Backlog before any code, on Shaun's re-sequencing — sources first, then the page. The plan stays and is the more valuable half: the five source signatures the page will call are written down, so weather, calendar, news, De Tijd and the tablet each have something concrete to satisfy rather than an interface invented when the page is built. The branch carried only board files and was cherry-picked to main, so this feature is Backlog again with its requirements intact. ADR-260913-c477cd still stands: its motivation shifts from 'the sources do not exist yet' to 'a lapsed credential should cost one section of the page, not the page', which is the stronger argument anyway.
- **2026-09-15** — Reflection: pre-close verifier said REQUEST CHANGES on five Criticals, all fixed. The sharpest: a weather source that reports its own failure was handed to Claude as available, so on a morning open-meteo was down the intro would have been written about a forecast that was not there — three tests covered the raising path and none the answering one, because the stand-in could not express it. Also a failed push took the whole answer down, losing the path to a page already on disk; the two overflow warnings were inert; and the picture cache never emptied on a service that runs for weeks. Two criteria were false rather than unmet and are corrected on the board; one (the progress notification) is unbuilt and unticked with a note. Traceability 31/35 built and tested, 1 by inspection with its evidence, 3 corrected. Twenty-one controls probed by deletion across three tools. Coverage of .harry/ is a known blind spot carried on FEAT-260914-e1e8d0.

## Links

- Requirements: [[FEAT-260912-0f2744]]
- [[ADR-260913-c477cd]] — a capability may declare a connector optional
- [[ADR-260913-210e08]] — a capability is handed the connectors it declared
- [[ADR-260912-b22e46]] — tools are one verb each, and why the digest is two
- [[ADR-260912-bd36c2]] — Harry never calls a model
- Decision: [[ADR-260913-c477cd]] — A capability may declare a connector optional, and render without it

