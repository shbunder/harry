---
id: STORY-260914-0297e2
title: A published link's events are in the same day
feature: FEAT-260914-289e1f
status: Done
created: 2026-09-14
---

# STORY-260914-0297e2 — A published link's events are in the same day

Part of [[FEAT-260914-289e1f]].

## Description

One setting, one fetch, and the documents merged into the calendar that already gets
expanded. The recurrence work is done — the measured Outlook feed went through it and
produced a sensible week — so this story is about getting the bytes there and failing
honestly when they do not arrive.

## Acceptance criteria

- [x] A link named in `SUBSCRIBED` puts its events in the same day as the iCloud ones, in one time-ordered list
- [x] A repeating meeting from a link lands on the right day, through the same expansion
- [x] An instance a link overrides with `RECURRENCE-ID` appears once, at the overridden time
- [x] Two links both contribute, and each is fetched once
- [x] `SUBSCRIBED` is `Name=url` separated by `|`, split on the first `=` so the URL may contain more
- [x] A malformed entry is skipped with a log line and the others still load
- [x] A link that 404s, times out or is unreachable fails the whole read — a partial agenda is the thing this feature exists to prevent
- [x] A link answering HTML rather than a calendar does the same, saying it did not answer with a calendar
- [x] Either failure names the label, never the URL, and puts one line in Slack per link per 24 hours
- [x] The URL reaches no log line, no exception message and no Slack message — asserted against a planted value
- [x] Each link is fetched at most once every 5 minutes; a call after that fetches again
- [x] `SUBSCRIBED` empty — the default — reads nothing over HTTP and changes nothing
- [x] The parsing tests run against a fixture shaped like the measured Outlook feed, whose events are invented because the real ones are somebody's work calendar
- [x] The runbook and `docs/sources.md` say the link is a credential and that republishing in Outlook is how to revoke it

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

