---
id: STORY-260912-76bb6b
title: A Claude cloud routine reaches the probe over the tunnel, with a token of its own
feature: FEAT-260913-fdd33f
status: Backlog
created: 2026-09-12
---

# STORY-260912-76bb6b — A Claude cloud routine reaches the probe over the tunnel, with a token of its own

Part of [[FEAT-260913-fdd33f]].

## Description

Scenarios 3 and 4, and the one on the critical path. The operator chose a cloud routine
([[ADR-260916-7d4bd0]]); if a routine cannot present a bearer token to a server behind the
tunnel, the trigger moves to the proven local route and the tunnel is deleted.

**Against the probe, not Harry.** Both questions here are about the routine, so they are
answered by a server holding nothing. Harry takes its place in STORY-260916-120de6.

**The check has to be able to fail.** The committed `.mcp.json` header falls back to
`probe-token-not-a-secret`, and a probe with no token configured accepts exactly that — so
a routine with no secret at all would get `ping` back and the unknown would be written up
as settled. The `harry-remote` entry carries no fallback, the probe runs with a throwaway
that is not the fallback, and the routine is run once WITHOUT the token to watch it refused.

**The ceiling has to be the routine's.** The call passes through Cloudflare's edge, which
has its own origin-response timeout — error 524, 100 seconds by default for a proxied
hostname. The same sleeps are run from the NUC through the tunnel first, so a limit the NUC
also hits is Cloudflare's and a limit only the routine hits is the routine's.

## Acceptance criteria

<!-- These drive the tests. Write checkable statements, not activities.
     Bad:  Wire up the article fetcher
     Good: A De Tijd article whose browser session has expired falls back to its RSS
           summary, and the page still renders -->

- [ ] `.mcp.json` carries a second server, `harry-remote`, at `https://harry.marcel-bot.com/mcp` with header `Bearer ${HARRY_API_TOKEN}` and no fallback value, on a branch `spike/harry-remote` pushed to origin — not on `main`; the `harry` entry is unchanged
- [ ] The routine checks out `spike/harry-remote`, and its cloud environment allows outbound HTTPS to `harry.marcel-bot.com`
- [ ] A cloud routine run with no `HARRY_API_TOKEN` in its environment appears in the probe's server output refused with 401, and the call log shows no successful call from it
- [ ] The same routine run with the throwaway token in its environment calls `ping`, the result comes back to that routine's session, and the probe's call log records it
- [ ] Where the routine's token was put, and how it reached the request header, is written down step by step
- [ ] `sleep` for 30, 60, 120 and 300 seconds is run from the NUC through the tunnel, and then from the routine; the longest that returns on each path is recorded, and a limit the NUC also hits is attributed to Cloudflare rather than the routine
- [ ] If every sleep up to 300 returns from the routine, that is recorded as "at least 300s" and no longer sleep is attempted
- [ ] A routine request that never appears in the probe's server output is treated as a setup fault — branch, network setting or routine — and fixed and retried, not recorded as the route failing
- [ ] If a request does arrive and the token demonstrably cannot reach the header, the reason is recorded, the tunnel and its DNS record and `spike/harry-remote` are deleted, and a dated note on FEAT-260912-0f2744 hands the trigger to the local `claude -p` route — written after FEAT-260915-2a6ce1 merges, since that branch already carries a note on the same file
- [ ] The finding is a dated note on FEAT-260912-0f2744, quoting what was configured and what came back
- [ ] ADR-260912-bd36c2's Consequences is amended, since it names this route as its own unproven half

## Subtasks

<!-- Maintained by `board.py add-subtask`. Only when the story has a natural order. -->

## Notes

