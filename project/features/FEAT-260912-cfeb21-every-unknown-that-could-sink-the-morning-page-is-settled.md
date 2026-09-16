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
- **2026-09-13** — Reflection: pre-close-verifier returned REQUEST CHANGES with 3 Critical, 6 Important, 2 Suggestion - all acted on before merge. The Criticals were all in the promoted code, not the spikes: os.environ read three times (and already disagreeing with harry.config, 7430 against 7431 in the worktree), a --sleep-reporting flag that did nothing, and an assertion weakened to > 0 that passed with no key in the file at all. Traceability 11/11 criteria, 2 deliberately unticked with reasons. Scope drift: none material - mcp_probe and the test fix were both declared in touches before the verifier looked. Shortcuts: none. One process failure worth repeating aloud: a board note run from main instead of the worktree stranded itself uncommitted on main and blocked the merge, the same wrong-tree mistake that produced the In Progress flaw.
- **2026-09-16** — Later finding, 2026-09-16: the lesson recorded here — 'Playwright against a bot-blocked site needs channel=chromium' — has aged. De Tijd's edge now 403s full Chromium in headless mode as well as the headless shell; only a headed browser under Xvfb gets 200. channel='chromium' is necessary and no longer sufficient. Measured from the harry image against the public homepage. Details on FEAT-260912-9c933f.

## Lessons Learned

### What worked

**Registering the thing locally instead of standing up the tunnel.** Five of six spikes
turned out to be answerable against an MCP server on `localhost` registered in `.mcp.json`,
which took minutes. Only the scheduled-task question actually needed a tunnel, and
splitting it out let everything else finish. Reach for `scripts/mcp_probe.py` before
building infrastructure to test against.

**Three exit states, not two.** `UNKNOWN` for "could not reach it" kept a down service from
being written up as a design failure. It earned itself twice — once when a refused
connection was reported as `FAIL`, and once when a fresh De Tijd session 403'd and the
message blamed expiry.

**The close verifier.** It found three Critical defects in code that had a green gate and
20 passing tests, including a config read that already disagreed with `harry.config` in the
tree it was running in. Do not skip it because the diff looks small.

### What to do differently

**A count is not a finding.** The iCloud spike printed `PASS` because it counted 14 VTODO
items without reading them; every one was an Apple upgrade placeholder and there were zero
real reminders. Classify what comes back, then assert on the classification —
`.claude/rules/inert-controls.md`, in a place nobody had pointed it at.

**Do not read `os.environ` in anything, including a throwaway.** `scripts/mcp_probe.py` did,
and inside a worktree it bound port 7430 while `harry.config` said 7431 — the collision
`make worktree` exists to prevent. `os.environ` never reads `.env.local` either, so a real
token configured there was invisible. Go through `config.py` from the first line.

**Test the PASS path, not just the failure.** The probe's failure branch had a test and its
success path had none, so the thing the script exists to do was unverified while the gate
was green.

**Wire a flag the same commit you add it.** `--sleep-reporting` shipped doing nothing:
`cmd_call` never read it, so the headline finding could not be reproduced through the
interface built to reproduce it.

### Patterns to reuse, with paths

**`scripts/mcp_probe.py`** — `serve`, `call`, `calls`. Reach for it whenever "can X reach
Harry" comes up; `calls` answers it after the fact, so nobody has to be watching at 06:30.

**A blocking tool must report progress.** `sleep_reporting` in the same file is the shape:
300s silent is aborted, 660s reporting every 30s returns. Any tool that blocks — `ask_human`
first — emits progress on an interval well under the client's ceiling. 30s against 300s is
the margin, and it needs nothing configured anywhere.

**Playwright against a bot-blocked site needs `channel='chromium'`.** The default headless
is `chrome-headless-shell`, which De Tijd 403s on every URL including its homepage, with a
perfectly good session attached. See `scratch/tijd-login.py`. Get it wrong and the failure
looks exactly like an expired login — check the session's age before believing that.

**`tests/test_mcp_probe.py`** — an MCP server tested in process, no port and no tunnel:
`Client(server)` connects to the object directly, and `progress_handler=` counts
notifications.

## Links

- Requirements: [[FEAT-260912-cfeb21]]
- Decision: [[ADR-260912-bd36c2]] — its Consequences names the connector spike as its own
  unproven half. That spike moved to [[FEAT-260913-fdd33f]], which carries the obligation to
  amend the ADR once it is answered.

