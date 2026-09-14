---
id: ADR-260914-98cc64
title: A published calendar link is read by the calendar connector, not a new one
status: Accepted
created: 2026-09-14
feature: FEAT-260914-289e1f
supersedes: ''
superseded_by: ''
---

# ADR-260914-98cc64 — A published calendar link is read by the calendar connector, not a new one

## Status

Accepted

Drives [[FEAT-260914-289e1f]].

## Context & problem

Part of the calendar is an Outlook link rather than an iCloud account, and that is not going
to be unusual: work publishes a URL, home is in Apple, and the person has one day.

`capability-shape.md` says a connector owns **"one external thing each: its credential, its
client, its runbook"**. By that reading a published `.ics` link is plainly a second thing. It
has its own credential — the random segment in the URL *is* the password. It has its own
client: `httpx`, not `caldav`. It has its own runbook: you revoke it by republishing in
Outlook, which has nothing to do with Apple app-specific passwords.

So the rule points at a second connector. The tool surface points the other way, and that is
the tension this record exists for.

## Decision drivers

- **The tool surface is where Harry's value crosses**, and `tool-design.md` is explicit:
  "the model picks from names and descriptions alone — if two tools read alike, it picks
  wrong, and the failure looks like a bug in the tool it chose."
- **Explainable.** Somebody setting this up six months from now has one question — "where do
  I configure my calendar?" — and should find one answer.
- **Degrading.** Whatever ships must not produce a partial agenda that looks complete.
- The morning page's contract is `calendar.today()`, singular. Two sources means somebody
  merges them, and that somebody has to exist.

## Considered options

### Option 1: The calendar connector reads both, with a `SUBSCRIBED` setting

**For:** One tool answers "what is on today", which is the only question anybody has. One
runbook covers the whole calendar. `calendar.today()` stays one call returning one day, so
nothing downstream learns that the day came from two places. The news connector is the
precedent already in the tree: VRT NWS and the BBC are two unrelated organisations behind one
`news` connector, because they answer the same question.

**Against:** The folder is called `icloud` and now reads things that are not iCloud. That is
a real cost, paid by every future reader of the folder name. It holds two credential kinds
with two renewal procedures in one runbook, which is exactly the coupling the rule is written
to prevent.

### Option 2: A second connector, and two tools

`subscriptions` alongside `icloud`, each with its own tool.

**For:** Obeys the rule as written. Either can be configured without the other — somebody with
no Apple account and one work link gets a working calendar. Each failure mode stays with the
thing that has it.

**Against:** **Two tools that read alike.** `icloud_list_events` and
`subscriptions_list_events` both answer "what is on my calendar", and the model has thirty
characters and a description to choose between them. It will sometimes pick one, get half the
day, and report that half confidently — which is precisely the partial agenda this feature
exists to prevent, arriving through the fix for it. A person asking "am I free at three?"
would be told yes.

### Option 3: A second connector, and one tool that merges them

The tool declares `requires: [icloud]` and `optional: [subscriptions]`.

**For:** The rule is obeyed and there is still one tool. This is the technically correct
answer.

**Against:** `optional:` is decided but not built — it is a criterion of FEAT-260912-0f2744,
which has not started. Building it here would pull a core change into a connector feature and
leave the digest's own criterion already satisfied by work done somewhere else, which makes
that feature's traceability a fiction. It is also the arrangement where a person has to know
which of two folders their work calendar lives in.

## Decision outcome

**The calendar connector reads published links as well as iCloud calendars, through one
`SUBSCRIBED` setting, and publishes one tool.**

The rule being bent is named rather than glossed: one connector, two transports, two kinds of
credential. The reason is that the alternative puts two indistinguishable tools in front of
the model, and a wrong pick there produces a confident half-answer about somebody's day.

The core principle is **Explainable**: one question, one place to configure it, one answer.

**When to revisit.** If a third transport arrives, or if somebody needs subscribed links with
no Apple account at all, this becomes Option 3 — and by then `optional:` will exist, because
the digest needs it. At that point the split costs a folder move and the tool stays exactly
where it is.

## Consequences

**What this makes harder.** The folder is called `icloud` and the name is now partly wrong.
Anyone looking for where a work calendar is configured has to be told, which is why the
runbook and `docs/sources.md` both say it in the first paragraph. The connector's runbook
covers two renewal procedures that have nothing to do with each other — an Apple app-specific
password, and republishing a link in Outlook — and a person reading it about one has to skip
the other.

It also means the iCloud credential is still required to read a subscribed link, because the
connector will not load without it. Somebody with only a work link cannot use this today.
That is the sharpest edge of the decision and the thing most likely to force Option 3.

**What it makes easier.** One tool, one setting file, one `calendar.today()`. A day is a day,
and nothing downstream — not the tool, not the morning page, not the person reading it — has
to know that half of it came over CalDAV and half over HTTPS.
