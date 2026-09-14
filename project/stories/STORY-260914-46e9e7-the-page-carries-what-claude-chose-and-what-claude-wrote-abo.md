---
id: STORY-260914-46e9e7
title: The page carries what Claude chose and what Claude wrote about it
feature: FEAT-260912-0f2744
status: Backlog
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

- [ ] digest_build takes an intro and picks of id-and-note, and the front page carries the intro verbatim
- [ ] Each picked article appears with Claude's note above its text, unedited
- [ ] An article whose text could not be fetched appears with its headline and note, saying the text was unavailable
- [ ] An id that is not among today's candidates is an error naming it
- [ ] The PDF is 509.34 by 679.13 points, with an outline entry per article in the order Claude picked
- [ ] With no tablet connector the page is written under the data volume and the answer says where; with one, it is pushed
- [ ] The morning-page job is one markdown file, served as a prompt, telling Claude the three calls to make
- [ ] `make digest-dry` renders to out/digest.pdf and says what it could not put on the page

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

