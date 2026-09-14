---
id: FEAT-260914-e871d4
title: An event title fits on one line
track: story
created: 2026-09-14
touches: [connectors/icloud]
stories: [STORY-260914-1d8a9c]
decisions: []
---

# FEAT-260914-e871d4 — An event title fits on one line

## Summary

A real calendar entry, read off a real account:

```
'👨‍👧‍👦 Kids
🏫 School [15:15 - 15:30]'
```

The title carries a newline. Nothing in Harry put it there — somebody typed it into their
calendar, and iCalendar carries it faithfully. It appears five times in one week on this
account.

The morning page is a PDF read at arm's length over coffee, and a one-line agenda entry that
is two lines breaks the row it sits in. Claude reading it over MCP gets a JSON string with a
newline in the middle, which is not wrong but is not what a title is.

Fold the whitespace. This is formatting, not judgement: no word is dropped, no meaning is
decided, and the same rule applies to every title from every calendar.

## Acceptance criteria

- [x] A title containing a newline comes back as one line, with the parts separated by a single space
- [x] Runs of spaces and tabs collapse to one space, and the ends are trimmed
- [x] No word is dropped and nothing is truncated — this is folding, not shortening
- [x] The same holds for `where`, which is free text in the same way
- [x] A title that was already one line is unchanged, character for character

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260914-1d8a9c]] — Fold a multi-line event title onto one line

## Notes

<!-- Appended by `board.py note`. -->

## Links

