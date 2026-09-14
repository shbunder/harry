---
id: ADR-260914-1d19b8
title: Harry does not read Reminders, because CalDAV cannot see them
status: Accepted
created: 2026-09-14
feature: FEAT-260912-e7ce2d
supersedes: ''
superseded_by: ''
---

# ADR-260914-1d19b8 — Harry does not read Reminders, because CalDAV cannot see them

## Status

Accepted

Drives [[FEAT-260912-e7ce2d]].

## Context & problem

The morning page was going to carry two lines from iCloud: the day's events, and the to-dos
due today. The second one is not possible.

A spike on 13 September 2026 authenticated against `https://caldav.icloud.com` with an
app-specific password and walked all 17 lists on the account. **14 VTODO items came back,
and every one was an Apple upgrade placeholder** — items whose summaries read *"De maker van
deze lijst heeft deze herinneringen bijgewerkt"* and *"Waar zijn mijn herinneringen?"*. Not
one was a real reminder.

Those lists have been migrated to Apple's newer Reminders format, which is synced through
CloudKit and not exposed over CalDAV. The placeholders are what Apple leaves behind for
CalDAV clients: a note saying the data has moved, in the shape of a to-do.

The spike nearly missed this. Its first version counted VTODO items, found 14, and printed
`PASS`. **A count is not a finding** — the items had to be read before the result meant
anything, and that lesson is now in `.claude/rules/inert-controls.md` territory in a place
nobody had pointed it at.

## Decision drivers

- **Explainable.** A to-do line that is empty every morning is worse than no to-do line: it
  looks like you have nothing due, every single day, and you would believe it for weeks.
- **Bounded.** The alternatives all mean holding a second credential, or running Apple's
  private protocol against an account.
- **Degrading.** Whatever ships has to fail in a way somebody notices. A section that is
  structurally always empty cannot.
- The events half works and is the larger part of the value.

## Considered options

### Option 1: Drop to-dos, ship the agenda

**For:** The agenda is what the line on the page is mostly for, and it works today against a
real account. Nothing is built that cannot work. The decision and its evidence are written
down, so the next person does not spend an afternoon rediscovering the placeholders.

**Against:** The feature ships at half the scope it was opened with, and "what's due today"
is a real thing to want on a morning page. Somebody will ask for it again.

### Option 2: Reach Reminders through CloudKit

Apple's CloudKit web services expose the newer Reminders store.

**For:** It is the only route to the actual data, and it is a documented API rather than a
reverse-engineered one.

**Against:** It needs a CloudKit container and an API token for an *app*, which is a
developer-account artefact rather than something a person generates for themselves — Harry
would be impersonating an application that does not exist. It is a second credential with a
different lifecycle in a repository whose whole credential story is "three secrets, each
declared, each with a renewal procedure". And the reminders it can see are the ones in a
container Harry owns, not the ones in your personal store. This is a larger feature than the
calendar it was meant to garnish.

### Option 3: Run AppleScript or the EventKit framework on a Mac

**For:** EventKit sees everything the Reminders app sees, because it is what the app uses.

**Against:** Harry runs in a container on a NUC. This option is "Harry runs on a Mac that is
logged in and awake", which is a different product. Listed because it is the answer people
reach for, and it is genuinely the only thing that works — on hardware Harry does not have.

### Option 4: Ship a to-do section that is empty

**For:** No code is deleted; the day Apple restores CalDAV access it starts working.

**Against:** It is the failure mode the whole Alerting principle exists to prevent. An empty
section every morning is indistinguishable from a clear day, forever, and nothing would ever
report it — because nothing is broken.

## Decision outcome

**Harry reads events from iCloud and does not read Reminders. The to-do half of the morning
page is dropped, not deferred.**

There is no empty section, no placeholder line and no "coming soon". The page carries what
Harry can actually get.

If to-dos matter enough later, the honest route is a to-do source that has an API — Todoist,
Things via its own sync, a text file in the data volume — added as its own connector. That
is a feature somebody asks for, not a repair of this one.

The core principle is **Explainable**: a section that is always empty tells a reader
something false, every morning, and never corrects itself.

## Consequences

**What this makes harder.** "What's due today" is not on the morning page and will not be
without a different source. Anybody who assumed iCloud Reminders were reachable — reasonably,
since they appear in the same app as the calendar — has to be told why, and this record is
where they find out.

The evidence has a shelf life. Apple could restore CalDAV visibility for migrated lists, and
nothing here would notice. That is acceptable: the cost of being wrong is that a feature
stays unbuilt for longer, not that anything breaks.

**What it makes easier.** The calendar connector is one credential, one protocol and one
kind of object. The recurrence work that the agenda genuinely needs gets the attention that
would have gone into a second half that could never work.
