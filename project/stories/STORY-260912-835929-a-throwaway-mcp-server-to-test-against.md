---
id: STORY-260912-835929
title: A throwaway MCP server to test against
feature: FEAT-260912-cfeb21
status: Backlog
created: 2026-09-12
---

# STORY-260912-835929 — A throwaway MCP server to test against

Part of [[FEAT-260912-cfeb21]].

## Description

Two of the spikes need something to call. Standing it up once, with both tools on it, means the reachability question and the blocking question are answered against the same server rather than two slightly different ones.

## Acceptance criteria

<!-- These drive the tests. Write checkable statements, not activities.
     Bad:  Wire up the article fetcher
     Good: A De Tijd article whose browser session has expired falls back to its RSS
           summary, and the page still renders -->

- [ ] A FastMCP server serves a `ping` tool that returns immediately and a `sleep` tool that returns after five minutes
- [ ] It is reachable on localhost behind a bearer token
- [ ] It is reachable at https://harry.<domain>/mcp through the existing Cloudflare Tunnel
- [ ] Everything it is made of lives in scratch/ and is imported by nothing

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

