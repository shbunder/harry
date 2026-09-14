---
name: icloud
description: Your calendar — what today looks like, from iCloud and any published links
provides: [icloud_list_events]
expires: manual
enabled: true
config:
  username:
    description: The Apple ID the calendar belongs to, usually an email address.
    required: true
  app_password:
    description: 'An app-specific password from account.apple.com → Sign-In and Security → App-Specific Passwords. Shown once. Needs two-factor turned on. Looks like abcd-efgh-ijkl-mnop.'
    required: true
    secret: true
  calendars:
    description: Which iCloud calendars to read, by name, comma-separated. Empty means all of them — which is the right answer for most accounts.
    default: ''
  subscribed:
    description: 'Published calendar links to read alongside iCloud, as Name=url separated by |. A link like this IS the credential — anyone holding it can read that calendar — so it belongs only in .env.local, and it is revoked by republishing the calendar in Outlook. Unset means iCloud only.'
    secret: true
  timezone:
    description: An IANA zone, so "today" and the times on the page mean the time in the room rather than in UTC.
    default: Europe/Brussels
---

The agenda line on the morning page. `09:30 standup · 14:00 dentist`, read over coffee.

**This reads the whole calendar, not only Apple's part of it.** iCloud over CalDAV, plus any
number of published `.ics` links — the kind work hands you — merged into one day. The folder
is called `icloud` because that is where most of it comes from; a published link is
configured here too, in `SUBSCRIBED`.

**Events only. Harry does not read Reminders**, and that is a decision with evidence behind
it rather than something unfinished — a spike walked all 17 lists on a real account and
every to-do that came back was an Apple upgrade placeholder. Those lists moved to a format
CalDAV cannot see. There is no empty to-dos section on the page, on purpose: one that is
blank every morning is indistinguishable from a clear day, forever.

**Harry never writes.** No creating, moving or deleting events. The password can do all
three; this connector does not.

**What Harry sends:** nothing, in the normal case. iCloud being unreachable, or the password
being refused, puts one line in Slack once per 24 hours.

## Setting it up

Two values, in `.env.local` beside this file — never in `.env`, which is generated and
committed:

```bash
cat > .harry/connectors/icloud/.env.local <<'ENV'
USERNAME=you@icloud.com
APP_PASSWORD=abcd-efgh-ijkl-mnop
ENV
```

The password comes from **account.apple.com → Sign-In and Security → App-Specific
Passwords**. Generate one, label it `Harry`, and copy it — **it is shown once**. The section
only appears if two-factor is turned on for the account.

To read only some iCloud calendars, add their names:

```bash
CALENDARS=Home, Work
```

Empty — the default — reads all of them.

## A calendar your work publishes

Outlook, Google and most calendar servers can publish a read-only `.ics` link. Add it with a
name you choose, separated by `|` if there is more than one:

```bash
SUBSCRIBED=KBC Agenda=https://outlook.office365.com/owa/calendar/…/reachcalendar.ics
```

The **name** is what you will see in Slack if that link stops working. Its events land in the
same day as everything else, with the same handling of repeating meetings.

**That link is a password.** There is nothing beside it — the long random segment in the URL
is the whole of its security, so anyone who has the link can read that calendar. Which means:

- It goes in `.env.local` and nowhere else. Never in a message, a ticket, or `.env`.
- Harry never prints it. A link that fails is reported by its name.
- **To revoke it, republish that calendar in Outlook.** That issues a new URL and kills the
  old one. There is no other way to take it back.

**A link that cannot be read costs the whole agenda, on purpose.** Everywhere else in Harry a
dead source costs its own section and the page renders. Here the section is your day, and a
day missing your work meetings looks exactly like a quiet day — you would read it and walk
into a 09:00. So the page says `Agenda unavailable`, which sends you to your phone.

Each link is fetched at most once every five minutes. The measured Outlook feed is 189 KB,
because a published link is the whole calendar in one document rather than a query for one
day.

## When the password stops working

An app-specific password does not expire on a clock. It dies when you change your Apple ID
password, which revokes **every** app-specific password on the account at once. So the day
you change your Apple password, Harry's agenda stops, along with anything else using one.

You will see `the password was refused` in Slack. Make a new one the same way and replace
the line in `.env.local`.

## Recurring events

iCloud accepts a request to expand a repeating event into its occurrences and then ignores
it, returning the start of the series instead. A weekly standup would arrive dated last
Monday. **Harry expands them itself**, so the page shows today's instance at today's time,
with moved instances at their new time and cancelled ones absent.

## When it stops working

| What happened | What you see | What to do |
|---|---|---|
| iCloud is unreachable or slow | `Agenda unavailable` on the page; one Slack line | Usually transient. The next build is a fresh attempt. The 15-second ceiling is **per request**, and reading every calendar is one request each — name the ones you care about in `CALENDARS` if a slow morning matters |
| The password was refused | `the password was refused`; one Slack line | Make a new app-specific password at account.apple.com and replace it in `.env.local` |
| A calendar in `CALENDARS` does not exist | The other calendars' events, and a log line | Check the name — it is the name as it appears in the Calendar app |
| A `SUBSCRIBED` link answers 404 or 403 | `Agenda unavailable`; one Slack line naming the link | The link has been withdrawn. Republish that calendar in Outlook and put the new link in `.env.local` |
| A `SUBSCRIBED` link answers a sign-in page | `Agenda unavailable`; one Slack line saying it is not a calendar | Same fix — the link has expired |
| A `SUBSCRIBED` entry is not `Name=url` | The other links, and a log line naming its position | Check for a missing `=` or a stray `|` |
| One event will not parse | The rest of the day, and a log line | Nothing. One malformed entry is not an outage |
| Nothing on the page and nothing in Slack | `Nothing on today` | That is a free day. An empty agenda and a dead one are different answers here on purpose |
| A repeating meeting is at the wrong time | — | Check `TIMEZONE`. The times are converted to it, and the default is Europe/Brussels |
