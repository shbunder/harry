# iCloud fixtures

Seven iCalendar documents, and **all of them are written by hand.**

That is worth saying plainly, because every other fixture directory here holds recordings.
Nothing could be recorded from a real account: the app-specific password had not been
generated when these were written, and `tests/test_icloud_connector.py::test_a_real_account_still_answers`
is the `live` test that will confirm the real thing matches.

What makes handmade acceptable here is that iCalendar is a specification — RFC 5545 says
exactly what `RRULE`, `EXDATE` and `RECURRENCE-ID` mean, and a document that follows it is
not a guess about Apple's behaviour. **The one thing these cannot prove is what iCloud
actually sends**, and that is precisely what the spike already measured and what the live
test re-checks.

| File | What it is for |
|---|---|
| `weekly-standup.ics` | A weekly Monday event whose series starts **2026-09-07**. The whole reason the connector expands recurrences itself: iCloud returns this object, dated the 7th, when asked for the 14th |
| `moved-instance.ics` | The same UID with a `RECURRENCE-ID` of 09:30 on the 14th and a `DTSTART` of 11:00. It only suppresses the generated 09:30 occurrence if the expander sees it and the master together |
| `cancelled-standup.ics` | The same series with an `EXDATE` for the 14th, so that Monday has no standup |
| `all-day.ics` | `DTSTART;VALUE=DATE` — a date with no time, which must read as "all day" rather than midnight |
| `stored-in-utc.ics` | `20260914T073000Z`, which is 09:30 in Brussels. Times on the page are the time in the room |
| `afternoon.ics` | An ordinary 14:00 event with a location, so ordering and `where` have something real |
| `malformed.ics` | A `DTSTART` that is not a timestamp. One event that will not parse must cost one event, not the day |

The dates are all around **Monday 14 September 2026**, which is a Monday, so the weekly
series lands on it.
