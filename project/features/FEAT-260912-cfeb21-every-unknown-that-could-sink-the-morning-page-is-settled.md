---
id: FEAT-260912-cfeb21
title: Every unknown that could sink the morning page is settled
status: In Progress
track: full
created: 2026-09-12
touches: [scratch, tests/test_config.py]
stories: [STORY-260912-835929, STORY-260912-76bb6b, STORY-260912-f7cda6, STORY-260912-8d003e, STORY-260912-8bc2b4, STORY-260912-bdf4d2]
decisions: [ADR-260912-bd36c2]
---

# FEAT-260912-cfeb21 — Every unknown that could sink the morning page is settled

## Summary

Five questions nobody has answered, each of which can invalidate a later phase. Each one is a throwaway script that prints PASS or FAIL, and each finding is written into the decision or the scenario that depends on it. The connector question is the one on the critical path: if a Claude scheduled task cannot reach Harry, the morning page has no trigger and nothing downstream is safe to build.

## Acceptance criteria

<!-- One box per scenario. These are what the pre-close-verifier builds its
     traceability matrix from. -->

- [ ] A Claude scheduled task calls a tool on Harry over the tunnel and gets the result back
- [ ] A De Tijd article's full body is on stdout, pulled through a browser session saved by hand
- [ ] An MCP tool call that blocks for five minutes returns its result rather than timing out
- [ ] A one-page PDF pushed with remarkapy appears on the tablet, and we know whether the free tier carries it
- [ ] Today's iCloud events come back over CalDAV, and we know whether Reminders arrive as VTODO
- [ ] Every finding is written into the decision or scenario that depends on it, quoting what was measured

## Stories

<!-- Maintained by `board.py new-story`. -->
- [ ] [[STORY-260912-835929]] — A throwaway MCP server to test against
- [ ] [[STORY-260912-76bb6b]] — A Claude scheduled task reaches Harry over the tunnel
- [ ] [[STORY-260912-f7cda6]] — A blocking tool call survives five minutes
- [ ] [[STORY-260912-8d003e]] — A De Tijd article comes back in full
- [ ] [[STORY-260912-8bc2b4]] — A PDF reaches the tablet
- [ ] [[STORY-260912-bdf4d2]] — iCloud answers over CalDAV

## Notes

<!-- Appended by `board.py note`. -->
- **2026-09-12** — The first worktree ever opened went red on tests/test_config.py: it asserted port == 7430 while `make worktree` writes HARRY_PORT=7431 into that tree's .env.local by design. The test now reads .env alone. Declared in `touches` rather than left as silent scope drift — the fix is scaffolding, not Phase 0, and it made every worktree's gate red.

## Links

- Requirements: [[FEAT-260912-cfeb21]]
- Decision: [[ADR-260912-bd36c2]] — its Consequences names this feature's connector spike as its own unproven half

