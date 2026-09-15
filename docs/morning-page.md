# The morning page

What all of it is for. At 06:30 a Claude scheduled task asks Harry what today could contain,
decides what matters, writes a short intro, and asks for the page. Harry fetches the chosen
articles, draws the paper and puts it on the tablet before anybody is up.

**Two calls, and the judgement happens between them.**

```
digest_list_candidates()        → the weather, the agenda, forty headlines
        … Claude chooses …
digest_build(intro, picks, more) → a PDF on the tablet
```

That gap is the product. Harry hands over forty headlines and takes back six, and which six —
and what to say about them, and which of them are the same story, and what subject each
belongs to — never happens inside Harry. See
[ADR-260912-bd36c2](../project/decisions/ADR-260912-bd36c2-harry-never-calls-a-model.md).

## What the paper looks like

**One front sheet.** A masthead with the name you chose and today's date. A weather panel: an
icon for the day, the high in display type, and four hours across the afternoon each with a
temperature and an icon of its own. Claude's intro, set across two columns. Then the day's
timetable beside the six stories.

**The timetable is a real calendar.** A block is as tall as the time it takes and drawn in its
calendar's colour, with a legend naming only the calendars that have something on today.
Overlapping events get columns, and **the columns are local** — three meetings colliding at
09:00 do not make a lone 20:00 event one third of a column wide.

**A second sheet.** Everything else worth knowing, three cards across, in sections: at home,
abroad, AI and technology, culture, basketball, and one more thing. A section with nothing in
it is not drawn — on a day with no basketball, and that is most days, an empty heading would
say a source is broken when the truth is that nothing happened.

**Then a page per article**, in the same order the sections run. Source and subject as a
kicker, the headline, the picture, Claude's note set apart, and the text in two columns. At
the foot: the other pieces on the same story as full rows, and the ways out.

**Everything is tappable.** The tablet has no address bar, so every headline, thumbnail,
companion and way out is a link in the PDF. The arrows only ever mean travel — `←` is the
story before this one and `→` the one after. The front page and the second sheet are jumps,
so they carry no arrow at all.

**509.34 × 679.13 points**, the Paper Pro's exact page; at any other size the tablet rescales
it and the type goes soft. The left margin carries 24 points more than the others, because the
tablet's own edit bar sits over that strip.

## Setting it up

```bash
cat > .harry/tools/digest_build/.env.local <<'ENV'
NAME=The Bundervoet Daily
COLOURS=Shaun=yellow|Jan=green|Kids=pink|KBC Agenda=blue
FOLDER=🗞️ Daily
ENV
```

| Setting | What it is | Default |
|---|---|---|
| `NAME` | What the journal calls itself, on the masthead | `The Morning Page` |
| `COLOURS` | Which ink each calendar is drawn in. One of yellow, green, pink, blue, red, purple, grey | empty, and every calendar is grey |
| `FOLDER` | Which folder on the tablet the page goes into. Empty leaves it to the tablet connector | empty |
| `OUT_DIR` | Where the PDF is written. It stays there whether or not the tablet took it | `/data/digest` |
| `TIMEZONE` | Which day "today" means, and the clock the timetable prints | `Europe/Brussels` |

**Those five are the whole of what a reader sets.** Everything else about the look is decided
in the feature. A setting is something true of every morning; anything true of *this* morning
is an argument on the call — the intro, the picks, the notes, the grouping, the subjects.

## Seeing it without a tablet

```bash
make digest-candidates > candidates.json     # what today could contain
# choose, and write picks.json
make digest-dry PICKS=picks.json             # build it to out/, push nothing
```

`digest-dry` passes `deliver=false`, so it does not push even on a machine that has a tablet
token — a command whose whole purpose is "does the page look right" should not put anything
on somebody's device.

Both go through `scripts/call_tool.py`, which calls one tool by name with JSON arguments and
knows about no capability at all. Naming a tool in a Makefile recipe is a developer
convenience; core never learns a capability's name.

## When something is missing

Every section fails on its own. **The page renders with any of them gone.**

| What is missing | What you get | What reaches Slack |
|---|---|---|
| No weather connector, or it raises | The panel is absent; everything else is untouched | Nothing — weather is the deliberate exception |
| The calendar raises, or its password lapsed | No timetable; the six stories fill the sheet | The calendar connector's own line |
| A story's text cannot be fetched | Its page, with the headline, your note and the feed's own summary, saying the full text was unavailable | The news connector's own line |
| A picture will not come | The story without it. Nothing is retried beyond the one browser User-Agent | Nothing — a feed with no pictures is a feed, not a fault |
| A calendar has no colour assigned | Its events in grey, and the legend says so | Nothing |
| No tablet, or `deliver=false` | The page on disk, and the answer says where | Nothing |
| **The task never fired at all** | Yesterday's paper, and no error anywhere | **`morning-page has not run today`**, from the watchdog |

That last row is the one that matters. An external trigger cannot report its own absence: a
scheduled task that never fires produces silence, and silence looks exactly like a morning
nobody checked. The watchdog is the only thing that tells the difference, which is why the
brief ends by telling Claude to call `harry_mark_done`.

**Nothing else here reaches Slack.** Each source owns its own alert, because each one knows
what its own failure means — a lapsed De Tijd login is that connector's to report, a dead feed
is the news connector's. The page sees only "this section is unavailable" and cannot tell a
source that broke from one nobody has configured.

## An id that lost or gained a word

`digest_build` resolves an id when exactly one candidate's id begins it, or when it begins
exactly one candidate's id. The answer lists everything it resolved.

That is not politeness. The brief was run against a real morning's headlines on Haiku twice:
the first run **dropped the last word** of two ids, and the second, against a brief rewritten
to warn about exactly that, **rebuilt two from the headline** and made them longer. Prose did
not fix it and a third rewrite would not have either. A string begins another or it does not,
which makes it arithmetic and therefore Harry's to do.

An id matching nothing, or matching two, is an error naming what it could have meant. And
Harry says what it resolved, because a silent correction is how the wrong story gets printed
and nobody finds out.
