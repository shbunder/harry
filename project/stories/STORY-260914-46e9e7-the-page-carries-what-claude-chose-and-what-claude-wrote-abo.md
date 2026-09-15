---
id: STORY-260914-46e9e7
title: The page carries what Claude chose and what Claude wrote about it
feature: FEAT-260912-0f2744
status: Done
created: 2026-09-14
---

# STORY-260914-46e9e7 — The page carries what Claude chose and what Claude wrote about it

Part of [[FEAT-260912-0f2744]].

## Description

The second call, the renderer and the job. Harry fetches, renders and delivers; it never edits the intro or the notes, because editing them would be reasoning about what Claude meant.

## Acceptance criteria

<!-- These drive the tests. Write checkable statements, not activities.
     Bad:  Wire up the article fetcher
     Good: A De Tijd article whose browser session has expired falls back to its RSS
           summary, and the page still renders -->

- [x] digest_build takes an intro and picks of id-and-note, and the front page carries the intro verbatim
- [x] Each picked article appears with Claude's note above its text, unedited
- [x] An article whose text could not be fetched appears with its headline and note, saying the text was unavailable
- [x] Each pick is resolved with news.article(id), so nothing is held between the two calls, and an id the source does not know is an error naming it
- [x] picks is capped at 12, and a progress notification is emitted per article so the call survives past the 300-second silent ceiling
- [x] The PDF is 509.34 by 679.13 points, with an outline entry per article in the order Claude picked
- [x] With no tablet the page goes to out_dir/<date>.pdf and the answer quotes it; with one, tablet.push is called, the answer quotes its result, and the page stays on disk
- [x] The morning-page job is one markdown file, served as a prompt, telling Claude the three calls to make
- [x] `make digest-dry` renders to out/digest.pdf through scripts/call_tool.py with no server or credential, and prints what it could not put on the page
- [x] `make digest-now` is removed, and nothing in src/harry/ names a capability

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

