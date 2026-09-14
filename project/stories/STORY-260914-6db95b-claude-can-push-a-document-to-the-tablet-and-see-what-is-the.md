---
id: STORY-260914-6db95b
title: Claude can push a document to the tablet and see what is there
feature: FEAT-260912-74f222
status: Done
created: 2026-09-14
---

# STORY-260914-6db95b — Claude can push a document to the tablet and see what is there

Part of [[FEAT-260912-74f222]].

## Description

The two tools, so "put this on my tablet" works from any session rather than only from the
morning page.

Markdown is here because the useful version of this is Claude writing something and sending
it. A tool that only accepts a path is a tool only the digest can call.

## Acceptance criteria

- [x] `remarkable_push_document(path=…, name=…)` puts an existing PDF on the tablet and answers where it went
- [x] `remarkable_push_document(markdown=…, name=…)` renders the markdown to a PDF at 509.34 by 679.13 points and pushes that
- [x] Passing neither path nor markdown, or both, is an error naming which
- [x] A path that is not a PDF and is not markdown is an error saying what is accepted
- [x] `remarkable_list_documents()` returns the names, ids and last-modified times of what is in the folder, newest first
- [x] A folder that does not exist yet lists as empty rather than raising
- [x] The push tool is readOnlyHint false and destructiveHint false — it adds, and adding is not destroying
- [x] The list tool is readOnlyHint true
- [x] Both tools defer, and both are listed in the connector's `provides:`
- [x] Both tools are skipped, saying they need the connector, when no token is configured

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

