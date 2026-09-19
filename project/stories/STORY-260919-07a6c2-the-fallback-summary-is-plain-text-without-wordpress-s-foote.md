---
id: STORY-260919-07a6c2
title: The fallback summary is plain text, without WordPress's footer
feature: FEAT-260919-94821d
status: Done
created: 2026-09-19
---

# STORY-260919-07a6c2 — The fallback summary is plain text, without WordPress's footer

Part of [[FEAT-260919-94821d]].

## Description

`page.plain()` turns a feed's summary into text: it drops WordPress's footer paragraph,
strips tags, and reads character codes until nothing changes, at most three times. The article
page's fallback (`.lede`) and the second sheet's `gist()` both use it, so one rule decides what
a summary looks like on paper. The footer is dropped rather than printed because it is the
publishing platform's, not the paper's reporting: every KW item carries it, and as text it
repeats the headline under the summary.

Tested against the recorded fixtures `kw-west-vlaanderen.xml`, `robtv.xml` and
`tijd-nieuws.xml`, through `digest_build` with the story's text unreadable.

## Acceptance criteria

- [x] Built through `digest_build` with KW's "Ardooise senioren" summary and the text unreadable, the story's page carries "Na een welverdiende pauze zijn de senioren opnieuw gestart" and "Er …", and no `<`, no `&#`, no "appeared first on"
- [x] The same with ROB tv's "Nieuws donderdag 17 september" summary carries no "nbsp" and no `&`
- [x] The same with De Tijd's "Ontsnapt het Franstalig hoger onderwijs aan de hakbijl?" summary carries "politiek & economie"
- [x] The second-sheet tests for KW's and ROB tv's summaries still pass unchanged

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes


- **2026-09-19** — Reproduced first: on the unfixed code the KW case failed (the page printed the summary's HTML) and the ROB tv case printed nbsp; De Tijd passed, as it should. Three mutants — the lede escaped raw, the footer kept, one decode pass — each fail a case. The first line of an article's text is set in small caps, and pypdf reads some of those glyphs back as capitals ('Na eeN welverdieNde'), so printed phrases are compared with says().

