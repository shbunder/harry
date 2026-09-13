---
id: FEAT-260913-fdd33f
title: A Claude scheduled task can reach Harry on the NUC
track: full
created: 2026-09-13
touches: [docs, nuc, scratch]
stories: [STORY-260912-76bb6b]
decisions: []
---

# FEAT-260913-fdd33f — A Claude scheduled task can reach Harry on the NUC

## Summary

The morning page is triggered by a Claude scheduled task, so whether such a task can reach a self-hosted MCP server decides whether the page has a trigger at all. Split out of the Phase 0 spikes once everything else was answerable on localhost: this one needs a tunnel and a NUC that is actually serving, which is deployment work rather than a throwaway script.

It blocks only the morning page. Core, alerting and every connector can be built without it.

## Acceptance criteria

<!-- One box per scenario. These are what the pre-close-verifier builds its
     traceability matrix from. -->

- [ ] Harry is reachable at https://harry.<domain>/mcp through the Cloudflare Tunnel, behind a bearer token
- [ ] A Claude scheduled task calls a tool there and the result comes back to that session
- [ ] What had to be configured, and where, is written down — this is the setup nobody will remember
- [ ] If a scheduled task cannot reach it, the reason is recorded: the plan, the account tier, or the network
- [ ] Where the trigger lives instead, if it cannot, is decided and written down rather than left open
- [ ] The NUC can be developed against: how code gets there and how Harry is run is documented

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260912-76bb6b]] — A Claude scheduled task reaches Harry over the tunnel

## Notes

<!-- Appended by `board.py note`. -->

## Links

- Requirements: [[FEAT-260913-fdd33f]]
