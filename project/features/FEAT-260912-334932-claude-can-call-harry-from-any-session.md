---
id: FEAT-260912-334932
title: Claude can call Harry from any session
status: Backlog
track: full
created: 2026-09-12
touches: [core/mcp]
stories: []
decisions: []
---

# FEAT-260912-334932 — Claude can call Harry from any session

## Summary

The surface Harry exists to offer. Tools declared under .harry/tools/ become MCP tools with their body as the description; a job brief becomes an MCP prompt. Most tools stay out of the roster until tool search finds them, which is what keeps the surface cheap as it grows.

## Acceptance criteria

<!-- One box per scenario. These are what the pre-close-verifier builds its
     traceability matrix from. -->

- [ ] `claude mcp add` against Harry connects, and `claude mcp list` shows it connected
- [ ] A declared tool appears over MCP with its TOOL.md body as the description and its annotations attached
- [ ] A tool with always_load false is absent from the roster until tool search finds it
- [ ] A request with no bearer token, or the wrong one, is refused
- [ ] A trigger: claude job's brief is offered as an MCP prompt named for the job
- [ ] The tool roster comes back in the same order on every request

## Stories

<!-- Maintained by `board.py new-story`. -->

## Notes

<!-- Appended by `board.py note`. -->

## Links

- Requirements: [[FEAT-260912-334932]]
