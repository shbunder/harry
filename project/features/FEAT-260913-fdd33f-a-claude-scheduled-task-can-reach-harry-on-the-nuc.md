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
- **2026-09-15** — The NUC already runs cloudflared, and the reusable part is the account, not the tunnel. A named tunnel 'marcel' (b7748dba-28df-47c5-9604-273f8a22fecf) has run as /etc/systemd/system/cloudflared-marcel.service since April, serving the zone marcel-bot.com. It starts with `cloudflared tunnel run --url http://localhost:7420 marcel` and there is no config.yml anywhere — ~/.cloudflared holds only cert.pem and the tunnel credentials JSON. A --url tunnel is single-origin, so adding harry.marcel-bot.com to it means dropping --url, writing ingress rules and restarting the process that carries Telegram's webhook. One cloudflared failure would then take out both the bot and the morning page. Make a second tunnel instead: cert.pem is account-scoped, so `cloudflared tunnel create harry`, `cloudflared tunnel route dns harry harry.marcel-bot.com` and a cloudflared-harry.service beside marcel's need no new Cloudflare setup and leave marcel untouched. Domain for the first acceptance criterion: harry.marcel-bot.com. Ports 7430 and 7431 are free; marcel owns 7420 and 7421.
- **2026-09-16** — SPIKE 2026-09-16 — the morning page's trigger does not need the tunnel. A headless 'claude -p' on the NUC reaches the containerised Harry over localhost and gets a real tool result back. What ran: Claude Code 2.1.220 on the NUC, already logged in on the subscription (~/.claude/.credentials.json, not read); the harry image started with 'docker run -e HARRY_API_TOKEN' on 7430, token generated in memory and never written to disk; an MCP config with header 'Authorization: Bearer ${HARRY_API_TOKEN}'; then: claude -p '<ask>' --mcp-config <that file> --strict-mcp-config --allowedTools mcp__harry__digest_list_candidates --model haiku --output-format json. What came back: subtype=success, terminal_reason=completed, permission_denials=[], result 'PLACE=Leuven HEADLINES=40 AGENDA=false' — real weather, all forty headlines, and the agenda correctly unavailable with no calendar configured. 8.6s end to end, $0.048 on Haiku for that one call. Auth is enforced, not bypassed: against the same container, POST /mcp initialize with no token 401, wrong token 401, right token 200. The repository's own .mcp.json already points at http://localhost:7430/mcp with the header resolved from $HARRY_API_TOKEN, so nearly all of the local route is already committed. WHAT THIS DOES NOT PROVE: the tunnel route. A Claude cloud routine reaching Harry through Cloudflare is still untested, and the docs leave two gaps in it — how a routine holds a bearer token without committing it (routine environment variables are readable by anyone who can use the environment), and the tool-call timeout ceiling, which is only sourced from GitHub issues (~60s) while this repo measured 300s idle in the CLI. STORY-260912-76bb6b's first criterion names the tunnel URL specifically and is not ticked by this.

## Links

- Requirements: [[FEAT-260913-fdd33f]]
