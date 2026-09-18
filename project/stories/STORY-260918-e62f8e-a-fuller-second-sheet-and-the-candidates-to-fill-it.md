---
id: STORY-260918-e62f8e
title: A fuller second sheet, and the candidates to fill it
feature: FEAT-260918-50ca24
status: Backlog
created: 2026-09-18
---

# STORY-260918-e62f8e — A fuller second sheet, and the candidates to fill it

Part of [[FEAT-260918-50ca24]].

## Description

<!-- What changes, and why this is one unit of work rather than two. -->

## Acceptance criteria

<!-- These drive the tests. Write checkable statements, not activities.
     Bad:  Wire up the article fetcher
     Good: A De Tijd article whose browser session has expired falls back to its RSS
           summary, and the page still renders -->

- [ ] `.harry/jobs/morning-page/JOB.md` asks for 60 candidates, and says the second sheet may run to two pages with up to 20 stories, about four per category where the day has them
- [ ] The brief still says a category with nothing in it is left out rather than padded, and still says nothing appears on both sheets
- [ ] `page.py` reports "crowded" only when the second sheet passes **two** pages, and a test fails if the threshold moves back to one
- [ ] The three extra De Tijd feeds are recorded as fixtures, and a test proves the connector drops the stories two of them share
- [ ] `docs/sources.md` lists the four De Tijd feeds in use and names the other four sections that exist
- [ ] `by inspection: the file is this machine's configuration and is gitignored` — the three feeds are added to the NUC's `.harry/connectors/news/.env.local`
- [ ] Measured on the running stack: how many candidates arrive, split by source, and how many De Tijd stories are duplicates across its sections

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

