---
id: FEAT-260912-334932
title: Claude can call Harry from any session
track: full
created: 2026-09-12
touches: [core/main, core/mcp, core/registry, core/loader]
stories: [STORY-260913-1b32e7, STORY-260913-78d843, STORY-260913-c63603, STORY-260913-f28eb4]
decisions: [ADR-260912-b22e46, ADR-260913-18a8ae, ADR-260913-f38787]
---

# FEAT-260912-334932 — Claude can call Harry from any session

## Summary

The surface Harry exists to offer. Tools declared under .harry/tools/ become MCP tools with their body as the description; a job brief becomes an MCP prompt. Most tools stay out of the roster until tool search finds them, which is what keeps the surface cheap as it grows.

## Acceptance criteria

<!-- One box per scenario. These are what the pre-close-verifier builds its
     traceability matrix from. -->

- [ ] A declared tool is callable over MCP with its TOOL.md body as the description, its frontmatter annotations, and a schema derived from the typed signature
- [ ] A capability the loader skipped is not published, while /health still explains why
- [ ] The roster comes back in name order, identical on every request
- [ ] A tool with always_load false is absent from the roster until harry_find_tools reveals it, after which it lists and calls
- [ ] The roster is never empty: harry_find_tools is always there, so an all-deferred roster cannot happen at run time
- [ ] A trigger: claude job's brief is an MCP prompt named for the job, rendered verbatim; a trigger: schedule job has none
- [ ] A request with no bearer token, or the wrong one, is refused; the configured one gets the roster
- [ ] A tool whose signature declares a principal is handed the caller's, and principal is absent from its input schema
- [ ] A tool that raises returns an error with no traceback and no file path, and every other tool still works
- [ ] `claude mcp add` against a running Harry connects, and `claude mcp list` shows it connected

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260913-1b32e7]] — Every tool a capability registered is callable over MCP
- [ ] [[STORY-260913-78d843]] — Most tools stay out of the roster until somebody looks for one
- [ ] [[STORY-260913-c63603]] — A job's brief is a prompt, so the scheduled task has nothing to copy
- [ ] [[STORY-260913-f28eb4]] — Only a caller Harry recognises gets in, and a tool can find out who

## Notes

<!-- Appended by `board.py note`. -->

## Links

- Requirements: [[FEAT-260912-334932]]
- [[ADR-260912-b22e46]] — tools are one verb each, namespaced, leaning on MCP's own features
- [[ADR-260913-18a8ae]] — a tool exists because someone would ask for it
- [[ADR-260913-f38787]] — the roots list and the principal
