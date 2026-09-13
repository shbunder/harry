---
id: FEAT-260912-cfeb21
title: Every unknown that could sink the morning page is settled
track: full
created: 2026-09-12
touches: [scratch, scripts/mcp_probe.py, tests/test_config.py]
stories: [STORY-260912-835929, STORY-260912-f7cda6, STORY-260912-8d003e, STORY-260912-8bc2b4, STORY-260912-bdf4d2]
decisions: [ADR-260912-bd36c2]
---

# FEAT-260912-cfeb21 — Every unknown that could sink the morning page is settled

## Summary

Five questions nobody has answered, each of which can invalidate a later phase. Each one is a throwaway script that prints PASS, FAIL or UNKNOWN, and each finding is recorded as a dated note on the feature that depends on it. The connector question is the one on the critical path: if a Claude scheduled task cannot reach Harry, the morning page has no trigger and nothing downstream is safe to build.

## Acceptance criteria

<!-- One box per scenario. These are what the pre-close-verifier builds its
     traceability matrix from. -->

- [x] The tunnel question is split out to [[FEAT-260913-fdd33f]] — it needs a serving NUC, not a script
- [x] A De Tijd article's full body is on stdout, pulled through a browser session saved by hand
- [x] An MCP tool call that blocks for five minutes returns its result rather than timing out
- [x] A one-page PDF pushed with remarkapy appears on the tablet, and we know whether the free tier carries it
- [x] iCloud answers over CalDAV, and both open questions are settled: Reminders come back as
      placeholders only, and a recurring event is returned unexpanded — the connector owns both
- [x] Every finding is written into the decision or scenario that depends on it, quoting what was measured

## Stories

<!-- Maintained by `board.py new-story`. -->
- [x] [[STORY-260912-835929]] — A throwaway MCP server to test against
- [x] [[STORY-260912-f7cda6]] — A blocking tool call survives five minutes
- [x] [[STORY-260912-8d003e]] — A De Tijd article comes back in full
- [x] [[STORY-260912-8bc2b4]] — A PDF reaches the tablet
- [x] [[STORY-260912-bdf4d2]] — iCloud answers over CalDAV

## Notes

<!-- Appended by `board.py note`. -->
- **2026-09-12** — The first worktree ever opened went red on tests/test_config.py: it asserted port == 7430 while `make worktree` writes HARRY_PORT=7431 into that tree's .env.local by design. The test now reads .env alone. Declared in `touches` rather than left as silent scope drift — the fix is scaffolding, not Phase 0, and it made every worktree's gate red.
- **2026-09-12** — Design flaw found opening this feature: In Progress is typed while Done is derived, which is the same failure the board was built to prevent. board.py start mutates whichever checkout it runs in, so the flip landed uncommitted on main and the branch never saw it; both sides then disagreed on a frontmatter line at merge. Recommendation: derive In Progress from an unmerged feat/ branch, the way Done is derived from the merge commit. lanes already reads branches and worktrees, so the machinery exists. Not fixed here — it changes the board contract and belongs in its own decision, not inside a spike feature whose touches are scratch.
- **2026-09-12** — Blocking call, transport half: PASS. A 300s tool call returned after 300.1s over FastMCP streamable HTTP on localhost, client timeout 900s, no keepalive tuning, nothing dropped. This proves the transport holds. It does NOT prove a Claude Code session holds - that is a different client with its own timeout, and it is the half that decides Phase 4. Longest success so far 300s; no failing length found, because nothing has failed.
- **2026-09-12** — Incidental, worth keeping: fastmcp 4.0.3 puts StaticTokenVerifier in fastmcp.server.auth.providers.jwt, not .providers.bearer where you would look first.
- **2026-09-12** — Cosmetic bug in board.py check, found using it: the box regex is ^(\s*)- \[( |x)\] and \s matches newlines, so for a box preceded by a blank line the match starts on that blank line and the confirmation prints an empty criterion. The right box is still ticked - only the message is wrong. Fix is [ \t]* instead of \s*. Not fixed here: this feature touches scratch and one test file, and board.py is neither.
- **2026-09-12** — Scope correction on the tunnel, from Shaun: it is only needed for a CLOUD Claude scheduled task reaching Harry. Registering the probe as a local MCP server at http://localhost:7430/mcp answers everything else with a real Claude client and no tunnel at all — which is the half of the blocking-call question that was still open. .mcp.json now sits at the repo root pointing there, and the same entry works unchanged for real Harry, because the port has one owner.
- **2026-09-12** — board.py has no way to untick a box. I ticked the tunnel criterion on 835929 by miscounting and had to edit the markdown by hand, which is exactly the drift the CLI exists to prevent. Worth an 'uncheck' command, or a 'check --off'.
- **2026-09-13** — PROGRESS DEFEATS THE CEILING. sleep_reporting(660, every=30) returned after 660.1s from a real Claude Code session - more than double the 300s that aborted the silent call. So a blocking tool holds indefinitely as long as it reports progress, with NO client configuration. That is the finding that matters, because Harry cannot configure the sessions that call it: the per-server timeout in .mcp.json works but only for clients somebody has already set up. ask_human can be the blocking design in the plan rather than a request id plus a poll. Its one obligation is to emit progress on an interval comfortably under the shortest ceiling it might meet - 30s against a 300s default is a 10x margin.
- **2026-09-13** — PHASE 4 TAKES THE BLOCKING DESIGN. ask_human() holds the tool call open and returns your Slack answer as the tool result, so the session continues mid-turn with no restart - the plan's design, not the request-id-plus-poll fallback. Its one obligation, and the reason it works: it must emit an MCP progress notification on an interval comfortably under the shortest ceiling it might meet. 30s against Claude Code's 300s default is a 10x margin and needs nothing configured on any client. Measured: 660s silent fails, 660s with progress every 30s returns. This should become an ADR when Phase 4 opens; it is a note now because inventing a decision record to hold a fact for a phase nobody has started is worse than waiting.
- **2026-09-13** — The tunnel question and its story moved to FEAT-260913-fdd33f. Everything else here was answerable against a locally registered MCP server, which needed nothing stood up; that one needs a serving NUC and a tunnel, which is deployment work rather than a throwaway script. It blocks only the morning page - core, alerting and every connector can be built without it.

## Links

- Requirements: [[FEAT-260912-cfeb21]]
- Decision: [[ADR-260912-bd36c2]] — its Consequences names the connector spike as its own
  unproven half. That spike moved to [[FEAT-260913-fdd33f]], which carries the obligation to
  amend the ADR once it is answered.

