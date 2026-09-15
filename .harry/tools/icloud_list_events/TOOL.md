---
name: icloud_list_events
namespace: icloud
description: What is on the calendar for a given day
requires: [icloud]
always_load: false
annotations:
  readOnlyHint: true
  idempotentHint: true
  openWorldHint: true
enabled: true
---

Returns the events on one day, earliest first, with the times in the local timezone.

```
[{"at": "09:30", "ends": "10:00", "title": "standup", "where": "meeting room", "calendar": "Shaun"},
 {"at": "14:00", "ends": null, "title": "dentist", "where": "", "calendar": "Kids"}]
```

Reach for this when the question is about someone's day — what is on, whether an afternoon
is free, what time a thing starts. `day` takes an ISO date like `2026-09-15`; leave it out
for today.

**An empty list means a free day.** It is a real answer, not a failure — if the calendar
could not be read, this call fails instead, so you never have to guess which one you are
looking at. Say "nothing on" only when you got an empty list.

`at` is `"all day"` for an event with no time, and those come first. `where` is often empty;
plenty of events have no location.

`ends` is when it finishes, in the same `"HH:MM"` shape — it is what says whether 14:00 is a
phone call or the rest of the afternoon. It is `null` when there is no end to give: an
all-day entry, or an event saved with a start and nothing else.

`calendar` is which calendar the event came from — the name shown in the calendar app, or the
label of a published link somebody shared. It is what tells your own meetings from the kids'
school run when both are on the same day. A calendar that will not give its name reads as
`"Calendar"`.

Repeating events are shown as they fall on the day asked for, including ones that were moved
to a different time. An instance that was cancelled is simply not there.

**Events only.** Reminders and to-dos are not visible over this protocol — Apple moved them
to a store it does not expose — so this tool cannot answer "what's due today", and an empty
result never means "no reminders".

It reads one person's whole calendar — the iCloud account, plus any published links they
have added, such as one their employer hands out — and never writes: no creating, moving or
cancelling anything.
