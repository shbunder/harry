---
id: STORY-260913-1b32e7
title: Every tool a capability registered is callable over MCP
feature: FEAT-260912-334932
status: Backlog
created: 2026-09-13
---

# STORY-260913-1b32e7 — Every tool a capability registered is callable over MCP

Part of [[FEAT-260912-334932]].

## Description

Publishing what the loader registered: the name, the body as the description, the frontmatter's annotations, and the schema FastMCP derives from the typed signature. The ordering rule lives here because it is a property of the roster rather than of any one tool.

## Acceptance criteria

<!-- These drive the tests. Write checkable statements, not activities.
     Bad:  Wire up the article fetcher
     Good: A De Tijd article whose browser session has expired falls back to its RSS
           summary, and the page still renders -->

- [ ] A loaded tool is callable over MCP, and calling it runs the function the capability registered
- [ ] Its description is the TOOL.md body verbatim — Harry never edits, summarises or templates it
- [ ] Its annotations are the ones in the frontmatter, readOnlyHint included
- [ ] Its input schema comes from the typed Python signature and is declared nowhere else
- [ ] A tool the loader skipped is not published, while /health still says why it was skipped
- [ ] Two consecutive list calls return the same tools in name order
- [ ] A tool that raises comes back as an error with no traceback and no file path, and the other tools still work

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

