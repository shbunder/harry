# Where the morning page gets its facts

Each source is one folder under `.harry/connectors/`, with its runbook in its own
`CONNECTOR.md` — beside the code it is about, rather than in a page somebody has to
remember exists. This page is the index and the part that is true of all of them.

| Source | Needs | What the page loses without it |
|---|---|---|
| [weather](../.harry/connectors/weather/CONNECTOR.md) | nothing | the weather line |
| [news](../.harry/connectors/news/CONNECTOR.md) | nothing | the headlines, and the articles chosen from them |
| [remarkable](../.harry/connectors/remarkable/CONNECTOR.md) | a device token | the delivery — the page is still written to disk |
| [icloud](../.harry/connectors/icloud/CONNECTOR.md) | an Apple app-specific password, plus any published calendar links | the agenda line |

*(De Tijd arrives as its own feature.)*

## What every source promises

**The page itself is not built yet** — weather and news are. The contract below was written
down first, deliberately, so each source has something to satisfy rather than an interface
invented when the page finally calls it:

```
weather.today()          → {summary, high, low, rain_chance}, or None
weather.forecast()       → the same four, plus available, place and hours
calendar.today()         → [{at, ends, title, where, calendar}], empty list on a free day
news.candidates(limit)   → [{id, title, source, feed, published, date, summary, link, image}], newest first
news.article(id)         → {available, id, title, source, published, link, summary, image, text}
tablet.push(path, name)  → {where}
```

News carries four fields beyond what was first written down. `feed` is the slug you filter
by, `date` is the local day the id is built from, `link` is what makes a headline clickable
on a page, and `image` is the address of the picture the feed published — or `null` where it
published none. `article()` carries `available`: on a page that will not load it is
`false`, there is no `text`, and `why` says what happened — **the headline, the source, the
time, the feed's own summary and the picture are still there**, so the page can print the
story and say the text could not be read.

**A source that cannot answer today's question returns nothing rather than raising** — the
one exception being `news.article(id)`, which raises on an id it does not know, because that
is a caller asking for something that was never offered rather than a source being down.

One dead source costs one section of the page; everything else renders. That is not
politeness, it is the whole reason the page is worth having on a morning when something is
broken.

## Weather

Open-Meteo. No account, no key, one call.

```
18–22°, overcast, 59% rain
```

`today()` is those four facts and nothing else — it is what a caller wanting one line asks
for. `forecast()` is the same lookup for a caller that wants to be told why it failed, and it
carries one thing more: **`hours`, the shape of the day.** Seventeen readings, 06:00 to 22:00
in local time, one an hour:

```
{"hours": [{"at": "06:00", "temperature": 17, "summary": "clear"},
           {"at": "07:00", "temperature": 17, "summary": "clear"}, …]}
```

That is what the page's hourly strip is drawn from, and it is the part the day's high cannot
tell you: whether the warm part is the morning or the evening, and whether the rain lands on
the school run or after supper. Each hour's `summary` is read from **the same WMO table the
day's word comes from**, so an hour and the day it belongs to can never disagree about what a
code means — and it is `null` for a code the table does not carry, exactly as the day's is.
An unrecognised code is logged **once per answer naming every code it could not read**, not
once per hour.

**An answer that carries the day but not the hours gives `hours: []`** — the panel keeps its
word, its high, its low and its rain chance, and loses only the strip. **An answer with the
hours but no codes keeps all seventeen readings**, each with `summary: null`: the numbers are
the part that cannot be guessed from the day's own word. Nothing is said in Slack for either,
because the day arrived.

Ships pointed at Leuven and works from a fresh clone. To point it somewhere else, put only
what differs in `.env.local` beside the declaration — never in `.env`, which is generated:

```bash
cat > .harry/connectors/weather/.env.local <<'ENV'
LATITUDE=51.05
LONGITUDE=3.72
PLACE=Ghent
ENV
```

**Claude can ask for it directly**, with the `weather_forecast` tool. It is deferred like
most tools, so a session finds it with `harry_find_tools("weather")` first.

**When Open-Meteo is down**, the page says `Weather unavailable` and the tool answers
`{"available": false, "why": "open-meteo did not answer within 5s"}` rather than failing. A
forecast nobody can get is an answer, not an error — a tool that raises tells the model it
did something wrong, and it did not.

**Nothing reaches Slack, and weather is the deliberate exception.** Every other source
alerts when it degrades, because a page that quietly lost a source three weeks ago looks
exactly like a page that had nothing from it that day. Weather is different twice over:
there is no credential to lapse, and `Weather unavailable` where a forecast belongs looks
like nothing else on the page. You would notice on day two.

The word comes from a fixed table of WMO codes. Intensity is dropped — "moderate rain" and
"heavy rain" are the same decision about a coat. **A code the table does not have gives the
three numbers and no word**, so the line reads `18–22°, 59% rain`: true and useful, where an
invented word would be neither. The code is logged so it can be added.

## News

Two public feeds, no credential: VRT NWS for Belgium and BBC News for the world. Harry
fetches both, turns them into one list of candidates, and fetches the full text of whatever
Claude picks.

**Harry does not choose.** No ranking, no scoring, no summarising. `summary` is the feed's
own description, word for word. Choosing six stories out of forty is Claude's job, and the
two tools stay separate so that choice happens where the judgement is.

```
vrt-2026-09-14-tessenderlo-ham-hakt-knoop-door   VRT NWS
bbc-2026-09-14-russia-hits-ukrainian-train-shortly   BBC News
```

An id is the feed slug, the date and the first five words of the title. The date is local —
a story published 22:30 UTC is filed under the next morning, which is the day you would have
read it.

### The picture

Every candidate carries `image`: **the address of the picture the feed published**, or `null`
where it published none. VRT attaches one as an Atom `rel="enclosure"` link and the BBC as a
`media:thumbnail`. The BBC's is 240 pixels wide and the same path serves any size, so Harry
asks for 800 — a fixed substitution, `/standard/240/` for `/standard/800/`, the same two
strings every time.

**Nothing is fetched to answer this.** Forty candidates carry about thirty pictures at 90 KB
each; downloading them to list headlines would be 3.6 MB of base64 through the tool call for
pictures mostly about to be discarded, and it would make one slow image host able to slow down
listing the news. Whoever renders a page fetches the ones it chose, and owns the awkward hosts
— `images.tijd.be` answers 403 to a plain request and 200 to a browser. See
[ADR-260915-c01ab8](../project/decisions/ADR-260915-c01ab8-a-connector-hands-over-a-picture-s-address-never-the-picture.md).

A feed that publishes no pictures is a feed, not a fault: `image` is `null` and nothing
reaches Slack.

**Claude reaches it with two tools**, both deferred, so a session finds them with
`harry_find_tools("news")` first:

- `news_search(query, source, since, limit, detail)` — the headlines. 20 by default, never
  more than 50. `detail` is `concise` unless you ask, which cuts each summary to 200
  characters and costs about a third of the tokens.
- `news_article(id)` — the full text of one of them, with the navigation and the cookie
  banner removed.

`news_article` resolves the id by re-reading the feeds, so nothing is held between the two
calls. A story that dropped off the feed since the search is an error telling you to search
again, not a stale article. Each feed is downloaded at most once every 5 minutes, which is
what keeps that from costing seven downloads per page.

### Configuring the feeds

Ships pointed at VRT NWS and BBC News and works from a fresh clone. Adding a third is a
line in `.env.local` beside the declaration — never in `.env`, which is generated:

```bash
cat > .harry/connectors/news/.env.local <<'ENV'
FEEDS=vrt=VRT NWS=https://www.vrt.be/vrtnws/nl.rss.articles.xml|bbc=BBC News=https://feeds.bbci.co.uk/news/rss.xml|world=BBC World=https://feeds.bbci.co.uk/news/world/rss.xml
ENV
```

Feeds are separated by `|`, and each one is `slug=Name=url` split on the first two `=`.
Harry reads RSS 2.0 and Atom; check a new feed is one of those, because nothing will tell
you it is not except an empty section. An entry that is not `slug=Name=url` is skipped with
a line in the log, and a `FEEDS` with nothing usable in it skips the connector entirely — a
news source with nothing to read is misconfigured, not degraded.

### When a feed dies

**One line reaches Slack**, once per source per 24 hours:

```
VRT NWS: VRT NWS answered 404
```

That is the whole point of the feature. A dead feed makes the candidate list shorter and
nothing else — it looks exactly like a quiet news day, where `Weather unavailable` on the
page is unmissable. The Slack line is the only thing that tells the difference. It carries
the source name and a sentence, never the feed URL and never anything from the response.

The other feeds still return, and `news_search` lists what failed:

```json
{"candidates": [...], "unavailable": [{"source": "VRT NWS", "why": "VRT NWS answered 404"}]}
```

`candidates()` — what the page calls — stays a plain list and never grows an `unavailable`
key. It cannot report a dead feed and it is not asked to.

**A feed that answers 200 and carries nothing is reported too**, saying it answered an empty
feed, under its own key. That is not a hypothetical: VRT served a valid Atom document with
zero entries for a while on 14 September 2026, an hour after carrying fifty stories, and the
first version of this connector said nothing at all about it — which is precisely the quiet
news day this whole feature exists to distinguish from a broken one.

**A feed that failed is never served from the last success.** A headline list that silently
ages is worse than a short one, because nothing on the page says how old it is.

An article page that blocks Harry or has no prose in it answers
`{"available": false, "why": …}` and puts one line in Slack the same way. Usually that is a
site that started blocking scripted clients — the De Tijd problem, which needs a browser
session — or an id pointing at a video.

**A feed is refused unread if it declares its own entities.** That is deliberate: it is how
an XML parser is made to allocate all the memory on the machine, and a news feed has no
reason to carry entity declarations. See
[ADR-260914-5a682c](../project/decisions/ADR-260914-5a682c-feeds-are-parsed-with-the-standard-library-not-a-feed-librar.md).

## The tablet

Where Harry's output goes. One folder, one write, and the most dangerous credential here.

**The device token grants complete read and write access to every document on the tablet,
with no scopes and no expiry.** There is no read-only variant to ask for. So this connector
does one thing — add a document — and deleting, moving and renaming are not exposed even
though the token permits all three.

### Pairing, once per machine

1. Open **my.remarkable.com/device/desktop/connect** and copy the 8-character code. It
   expires in a few minutes, so do this and the next step in one sitting.
2. Run:

```bash
make remarkable-pair CODE=abcd1234
```

That exchanges the code for a permanent device token and writes it to
`.harry/connectors/remarkable/.env.local`, which is gitignored. It prints that it worked and
does not print the token. A code that has already expired says `the code was refused` — go
back and get another.

**The token is not kept in `~/.rmapi`**, which is where remarkapy would put it. A home
directory is outside the repository, which is the good half, and outside the container,
which is the bad half: the NUC would have nowhere to read it from. A container injects
`HARRY_REMARKABLE_DEVICE_TOKEN` instead.

To revoke it, remove the device at my.remarkable.com, then pair again.

### What it does

Documents go into one folder, named in `FOLDER` and `Harry` by default. It is created at the
top level the first time something is pushed and found rather than re-made after that.

**Claude reaches it with two tools**, both deferred, so a session finds them with
`harry_find_tools("remarkable")` first:

- `remarkable_push_document(name, path=…)` or `(name, markdown=…)` — puts one document
  there. Markdown is rendered at 509.34 × 679.13 points, the Paper Pro's exact page, because
  at any other size the tablet rescales it and the type goes soft. Exactly one of `path` and
  `markdown`; both or neither is an error.
- `remarkable_list_documents()` — what is in that folder, newest first. An empty list means
  the folder is empty or not made yet, and is not an error.

The morning page **will** use the connector directly, as `tablet.push(path, name)` — that
page is not built yet.

### When a push fails

A failed upload is tried **exactly once more**. A retry that works says nothing — it is not a
fault. Two failures raise, so whoever asked knows the page did not arrive, and put one line
in Slack:

```
reMarkable: the tablet could not be reached
```

Once per 24 hours, naming the tablet and what happened. Never the token, never a URL, never
anything from the response.

| What happened | What you see | What to do |
|---|---|---|
| The cloud is unreachable or slow | Retried once, then `the tablet could not be reached` | Usually transient. The next push is a fresh attempt |
| The token was revoked | `the tablet refused the token — pair this machine again` | `make remarkable-pair CODE=…` with a fresh code |
| The push worked but nothing is on the device | — | The tablet syncs when it has wifi and the screen is on. Give it a minute |
| Every write started failing and nothing here changed | Two failures, one Slack line | reMarkable changed the protocol — it happened in August 2026. Bump the exact `remarkapy` pin and run `make test-live ARGS=tests/test_remarkable_connector.py` |
| A document you never opened vanished | — | The free tier removes untouched documents after 50 days. Irrelevant for a page replaced every morning |

Nothing else is affected: a failed push costs the delivery, and whatever was being pushed is
still on disk where it was.

**`remarkapy` is pinned to exactly 0.3.1.** The protocol is reverse-engineered and a release
broke every write in August 2026; a version range would deliver that release on the next
rebuild, on a morning nobody changed anything. Moving the pin is a deliberate act with a live
test attached.

## The calendar

Your whole calendar, one day at a time. `09:30 standup · 14:00 dentist`.

Each event carries five things:

```
{"at": "09:30", "ends": "10:00", "title": "standup",
 "where": "meeting room", "calendar": "Shaun"}
```

`at` and `ends` are both `"HH:MM"` in your timezone, and `ends` is what lets the page draw a
block as tall as the time it takes rather than a line of text. **`ends` is `null` whenever
there is no block to draw** — an all-day entry, an event saved with a start and nothing else,
or something that runs past midnight, whose end belongs to tomorrow rather than to this
morning's timetable.

`calendar` is the name of the calendar it came from: what the calendar app shows, or the
label you gave a published link. It is what tells your meetings from the kids' school run,
and it is the only thing the page has to colour them by. **A calendar that will not give its
name reads as `"Calendar"`** and its events still appear — a nameless calendar is a cosmetic
problem, a missing afternoon is not.

**Not only Apple's part of it.** iCloud over CalDAV, plus any number of published `.ics`
links — the kind work hands you — merged into one day. The folder is called `icloud` because
that is where most of it comes from; a published link is configured there too.

**Events only. Harry does not read Reminders**, and that is a decision rather than an
omission — a spike walked all 17 lists on a real account and every to-do that came back was
an Apple upgrade placeholder. Those lists moved to a store CalDAV cannot see. There is no
empty to-dos section on the page, because one that is blank every morning is
indistinguishable from a clear day, forever. See
[ADR-260914-1d19b8](../project/decisions/ADR-260914-1d19b8-harry-does-not-read-reminders-because-caldav-cannot-see-them.md).

**Harry never writes.** The password can create, move and delete events. This connector
reads, and a test asserts it has no code that could do anything else.

### Setting it up

```bash
cat > .harry/connectors/icloud/.env.local <<'ENV'
USERNAME=you@icloud.com
APP_PASSWORD=abcd-efgh-ijkl-mnop
ENV
```

The password comes from **account.apple.com → Sign-In and Security → App-Specific
Passwords**. Generate one, label it `Harry`, copy it — **it is shown once**. The section only
appears if two-factor is turned on.

`CALENDARS=Home, Work` reads only those two iCloud calendars; empty, the default, reads all
of them. `TIMEZONE` decides what "today" means and what time is printed, and defaults to
Europe/Brussels.

### A calendar your work publishes

Outlook, Google and most calendar servers can publish a read-only `.ics` link. Add it with a
name you choose, separated by `|` if there is more than one:

```bash
SUBSCRIBED=KBC Agenda=https://outlook.office365.com/owa/calendar/…/reachcalendar.ics
```

The name is what you will see in Slack if that link stops working. Its events land in the
same day as everything else, with the same handling of repeating meetings — the real Outlook
feed this was built against carries 234 events, 40 of them repeating and 76 of them single
instances moved out of their series, and all of it expands correctly.

**That link is a password.** The long random segment in the URL is the whole of its security,
so anyone holding it can read that calendar. It goes in `.env.local` and nowhere else, and
Harry never prints it — a link that fails is named, not quoted.

**Revoking it means republishing the calendar, which only its owner can do.** If it is your
own calendar, that is a two-minute job. If it is your employer's, you cannot: the link is
theirs to reissue, on their schedule or never. **That makes a published link you do not own
the one credential here that its user cannot rotate** — every other one in Harry has an
owner-side revocation, and this one does not. Worth knowing before you paste one anywhere.

Harry's HTTP client would otherwise write that URL into the log on every read, at `INFO`.
`configure_logging` in `harry/main.py` keeps `httpx` and friends at `WARNING` for exactly
that reason, and a test fails if it stops.

Each link is fetched at most once every five minutes. A published link is the whole calendar
in one document — 189 KB in the measured case — rather than a query for one day.

**A link that cannot be read costs the whole agenda, deliberately.** Everywhere else in Harry
a dead source costs its own section and the page renders. Here the section is your day, and a
day missing your work meetings looks exactly like a quiet day — you would read it and walk
into a 09:00. So the page says `Agenda unavailable`, which sends you to your phone.

**The password does not expire on a clock — it dies when you change your Apple ID
password**, which revokes every app-specific password on the account at once. That is the
one thing to remember: the day you change your Apple password, the agenda stops.

### Repeating events

iCloud accepts a request to expand a repeating event into its occurrences, then ignores it
and returns the start of the series. A weekly standup would arrive dated last Monday, and an
agenda that filtered by date would drop it — which looks exactly like a cancelled meeting.

**Harry expands them itself.** Today's instance at today's time, an instance moved to 11:00
at 11:00, and a cancelled one absent. See
[ADR-260914-969901](../project/decisions/ADR-260914-969901-recurring-events-are-expanded-by-harry-not-by-icloud.md).

### Claude can ask directly

`icloud_list_events(day)` — deferred, so a session finds it with `harry_find_tools("calendar")`
first. No `day` means today; `day="2026-09-15"` means that day.

### When it stops working

| What happened | What you see | What to do |
|---|---|---|
| iCloud unreachable or slow | `Agenda unavailable`; one Slack line | Usually transient. The ceiling is 15 seconds **per request**, and every calendar is a request — name the ones you want in `CALENDARS` if a slow morning matters |
| The password was refused | `the password was refused`; one Slack line | Make a new one at account.apple.com and replace it in `.env.local` |
| A calendar in `CALENDARS` does not exist | The others' events, and a log line | Check the name as it appears in the Calendar app |
| A `SUBSCRIBED` link answers 404 or 403 | `Agenda unavailable`; one Slack line naming the link | It has been withdrawn. Ask whoever publishes that calendar for a fresh link — if it is yours, republish it |
| A `SUBSCRIBED` link answers a sign-in page | `Agenda unavailable`; one Slack line | Same — and the same person reissues it |
| A `SUBSCRIBED` entry is not `Name=url` | The other links, and a log line naming its position | Check for a missing `=` or a stray pipe |
| One event will not parse | The rest of the day, and a log line | Nothing. One bad entry is not an outage |
| `Nothing on today` and nothing in Slack | — | A free day. An empty agenda and a dead one are different answers here on purpose |
| A repeating meeting is at the wrong time | — | Check `TIMEZONE`. Times are converted to it |

**An empty agenda and a dead agenda must not look alike.** A free day returns a list; a
calendar that cannot be read raises. That is why this source raises where weather and news
answer with `available: false` — an empty list already means something here.
