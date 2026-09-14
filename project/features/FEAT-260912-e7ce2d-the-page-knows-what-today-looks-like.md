---
id: FEAT-260912-e7ce2d
title: The page knows what today looks like
track: full
created: 2026-09-12
touches: [connectors/icloud, docs, tools/icloud]
stories: [STORY-260914-f7a91e, STORY-260914-2245c2]
decisions: [ADR-260914-1d19b8, ADR-260914-969901]
---

# FEAT-260912-e7ce2d — The page knows what today looks like

## Summary

Today's calendar and to-dos, from iCloud over CalDAV. Apple's Reminders support is the flakiest dependency in the plan, so the to-do half has to be able to fail on its own without taking the agenda with it.

## Acceptance criteria

<!-- One box per scenario. These are what the pre-close-verifier builds its
     traceability matrix from. -->

- [x] Today's events come back as `{at, title, where}`, earliest first
- [x] A recurring event shows today's instance at today's time, not the series start
- [x] A moved instance comes back once at its new time; a cancelled one is not there at all
- [x] An all-day event reads `at: "all day"` and sorts before every timed event
- [x] Times are local — an event stored 07:30Z reads "09:30" in Europe/Brussels
- [x] A free day is an empty list, not an error
- [x] Which calendars are read is configurable, and leaving it empty means all of them
- [x] A calendar name that matches nothing is logged and skipped; one malformed event is skipped too
- [x] iCloud unreachable raises rather than returning an empty day, so a dead calendar is never reported as a free morning
- [x] The 15-second ceiling is per request, and both the runbook and the Slack line say so rather than promising a total
- [x] A revoked password says to make a new one at account.apple.com
- [x] Either failure puts one line in Slack, once per 24 hours, carrying no password, URL or response body
- [x] The app-specific password reaches no log, no exception and no Slack message
- [x] With no credential the connector and its tool are skipped, saying what is missing, and the rest of Harry loads
- [x] `icloud_list_events(day)` answers for today or a named day, is readOnlyHint true, defers, and is in `provides:`
- [x] Reminders are not read, and the reason is recorded rather than left as an empty section
- [x] Every parsing test uses an iCalendar document in tests/fixtures/icloud/, and its README says they are handmade and why; the one live test is never in the gate
- [x] docs/sources.md and the runbook say where the password comes from and what happens when it lapses

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260914-f7a91e]] — Harry can read today's agenda out of iCloud
- [ ] [[STORY-260914-2245c2]] — Claude can ask what a day looks like

## Notes

- **The page half of "Agenda unavailable" is the digest's, not this feature's.** This connector raises; what a page prints when it does belongs to FEAT-260912-0f2744, which has the criterion. Nothing in this repository renders an agenda yet.

<!-- Appended by `board.py note`. -->
- **2026-09-13** — iCloud spike, three results. (1) CONNECTION PASS: app-specific password authenticates against https://caldav.icloud.com, 17 calendars listed. (2) REMINDERS FAIL: 14 VTODO items come back and every single one is an Apple upgrade placeholder - 'De maker van deze lijst heeft deze herinneringen bijgewerkt' / 'Waar zijn mij herinneringen?' - across 17 lists. Zero real reminders. These lists have been upgraded to a format CalDAV does not expose. The to-do section must move source or drop; it blocks nothing else. (3) RECURRENCE FAIL: searching today with expand=True returned one event whose DTSTART is 2026-09-07, i.e. the series start rather than today's instance. The agenda needs instance times, so this connector has to expand client-side or read RRULE itself. Budget for that; it is not a one-liner.
- **2026-09-13** — How the reminder failure was nearly missed, worth keeping: the spike first printed PASS because it counted VTODO items without looking at them. Fourteen items came back, so it said Reminders work. They were all placeholders. A count is not a finding - the spike now classifies and fails, which is the same lesson as .claude/rules/inert-controls.md in a place nobody thought to apply it.

## Links

- Requirements: [[FEAT-260912-e7ce2d]]
- Decision: [[ADR-260914-1d19b8]] — Harry does not read Reminders, because CalDAV cannot see them
- Decision: [[ADR-260914-969901]] — Recurring events are expanded by Harry, not by iCloud


## Lessons Learned

### What worked

**Letting the spike delete half the feature.** This was opened as "events and to-dos". The
spike walked all 17 lists, read what came back rather than counting it, and found fourteen
Apple upgrade placeholders and zero reminders. The to-do half is gone with the evidence in
[[ADR-260914-1d19b8]] rather than shipped as a section that would have been blank every
morning forever. **A spike that only confirms is not worth running.**

**Writing down what the fixtures cannot prove, next to the fixtures.** Every other fixture
directory here holds recordings; these are handmade, because no account was configured when
they were written. `tests/fixtures/icloud/README.md` says that, says why it is acceptable
(iCalendar is a specification, not a guess about Apple), and says exactly which three
behaviours remain unevidenced — whether iCloud really sends a `RECURRENCE-ID` override as a
separate object, whether `EXDATE` lands on the master, and what an all-day event looks like
on the wire. The verifier could then review the compromise instead of discovering it.

**Two greps standing in for two boundaries.**
`test_the_connector_never_writes_to_the_calendar` searches the source for `save_event`,
`add_event`, `.delete(`, `mkcalendar` and `add_todo`; `test_reminders_are_never_asked_for`
checks nothing asks for `VTODO`. Both are "we deliberately do not do this" decisions that
would otherwise live in a comment, and both now fail the gate if somebody reaches for them.

### What to do differently

**The same bug, in a second connector, two features apart.** One alert key for the whole
connector meant a transient blip at any hour silenced the revoked-password message — the
only one with something a person can act on — for 24 hours. The tablet connector had
exactly this and its fix is written in its own source, four lines of comment explaining why
the key is the *fault* and not the connector. It was not reused here. **When a review
teaches a rule, go and look at whether the rule already applies somewhere else in the
repository.**

**Six controls passed my own probe round and still could not fail.** I probed four —
recurrence, timezone conversion, all-day, the alert key — and all four bit, which made the
set feel checked. The six I did not probe were all green when deleted, including the one
that mattered most: `skip_bad_series`, without which one malformed event takes down the
whole agenda with no log and no Slack. **Probing a sample proves the sample. List every
control in the diff and take each one out.**

**A test can reach the right conclusion without ever entering the state it is about.** The
connection-reset test failed, then succeeded, and passed with the reset deleted — because
the failure happened during sign-in, when nothing is cached yet, so there was nothing to
reset. It took two rewrites to build a stand-in that signs in and *then* breaks. **Ask which
state the control is for, and check the test actually gets there.**

**One `str.replace` that silently did not match.** A batch of edits to the failure block
half-applied, because the formatter had rewrapped the code since I read it. The tests caught
it immediately, and only because they were run. **Assert on every replacement, or read the
file back.**

### Patterns to reuse

- **`.harry/connectors/icloud/connector.py`** — every event from every calendar into one
  `icalendar.Calendar` before expanding, because a moved or cancelled instance arrives as a
  separate object and only suppresses the generated occurrence if the expander sees both at
  once. Expanding per object gives you the standup twice.
- **`_readable()`** in the same file — touching a field where a skip can be logged, because
  the library's own `skip_bad_series` drops it silently and a recurring meeting vanishing
  with no trace is the failure the whole connector is arranged against.
- **The raise-versus-`available: false` split**, explained in four registers for four
  audiences — module docstring, `CONNECTOR.md`, `docs/sources.md` and `TOOL.md`. An empty
  list already means "free day" here, so a dead source cannot also return one. The `TOOL.md`
  sentence — *"Say 'nothing on' only when you got an empty list"* — is the one the model
  reads.
- **`test_the_stand_in_has_the_same_shape_as_the_real_client`** — reflects over
  `caldav.Calendar.search` and pins `server_expand`, which is the argument the whole
  recurrence decision turns on.
- **`tests/fixtures/icloud/README.md`** — a fixture directory that says which files are
  recordings, which are handmade, and what each one exists to catch.
