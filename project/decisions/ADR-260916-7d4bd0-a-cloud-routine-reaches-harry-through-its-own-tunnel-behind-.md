---
id: ADR-260916-7d4bd0
title: A cloud routine reaches Harry through its own tunnel, behind a bearer token
status: Accepted
created: 2026-09-16
feature: FEAT-260913-fdd33f
supersedes: ''
superseded_by: ''
---

# ADR-260916-7d4bd0 — A cloud routine reaches Harry through its own tunnel, behind a bearer token

## Status

Accepted — decided by the operator on 2026-09-16, choosing between the two routes below
after the local one had been proven that morning.

Drives [[FEAT-260913-fdd33f]].

## Context & problem

Harry never calls a model ([[ADR-260912-bd36c2]]), so the 06:30 page is fired by Claude,
outside Harry. That ADR named the route as its own unproven half.

Two routes exist, and by the time this was decided one of them had been proven:

- **Local.** A systemd timer runs a headless `claude -p` on the NUC against
  `localhost:7430`. Proven 2026-09-16: `digest_list_candidates` returned Leuven's weather,
  forty headlines and an unavailable agenda, with bearer auth, in 8.6s.
- **Cloud.** A Claude cloud routine reaches Harry at a public hostname through a
  Cloudflare tunnel. Unproven. The docs are silent on how a routine presents a secret in an
  MCP header, and on the idle ceiling of a tool call.

**The trade is not small, and it is the reason this is an ADR.** Harry holds the
reMarkable device token, which grants read and write over every document on the tablet
with no scopes. The cloud route puts the service holding it on a public hostname, guarded
by one static bearer token.

## Decision drivers

- **Bounded:** a public endpoint is exposure the local route does not have.
- The morning page should not depend on the NUC being the only place Claude can reach
  Harry from.
- Marcel's tunnel carries a Telegram webhook and must not be disturbed.
- The unknowns are about the routine, not about Harry, so they can be settled against a
  server that holds nothing.

## Considered options

### Option 1: A cloud routine, through Harry's own tunnel

A second named tunnel, `harry`, on the account marcel already uses, at
`harry.marcel-bot.com`. A committed `.mcp.json` entry `harry-remote` points at it, with the
token taken from the routine's environment.

**For:** the trigger does not live on the machine it is triggering, so a routine's run log
is visible from anywhere, and a routine that never fired is visible somewhere other than the
NUC. It reuses a Cloudflare account and zone that already work, and opens reaching Harry
from a laptop or a phone later without a second project.

It does not make the page independent of the NUC — Harry runs there, so a NUC that is down
fails this route exactly as it fails the local one.

**Against:** a public hostname in front of an unscoped tablet token, with one bearer token
as the only guard. Two open questions about routines, and a routine's environment variables
are readable by anyone who can use that environment. A second credential — the tunnel's
own credentials file — that can lapse. **And a dependency on GitHub:** a routine clones the
repository to find `.mcp.json`, so an outage there is a morning with no page.

### Option 2: A local timer running `claude -p` on the NUC

**For:** proven. No public endpoint, no tunnel, no second credential for Cloudflare. The
committed `.mcp.json` already points at localhost with the header resolved from the
environment.

**Against:** the trigger and the thing it triggers share a machine, so a NUC that is down
takes both with it — though the watchdog reports that the moment the NUC is back. It rides
on the Claude login already on the NUC, which lapses quietly; a lapsed login produces "no
page by 07:00", which the watchdog already says.

### Option 3: A second hostname on marcel's tunnel

**For:** one `cloudflared` process and one credentials file instead of two, so one thing to
keep current and one thing that can lapse.

**Rejected on the facts.** Marcel's tunnel runs with `--url` and no config file, and a
`--url` tunnel is single-origin. Adding a hostname means ingress rules and a restart of the
process carrying Telegram's webhook, after which one `cloudflared` failure takes out both —
and the saving of one process is not worth coupling a newspaper to a chat bot.

## Decision outcome

**Option 1**, chosen by the operator, **with the local route kept as the written fallback**:
if a cloud routine cannot present the token to Harry, the trigger moves to Option 2 and the
tunnel is removed rather than left standing.

Three conditions come with it, because they are what make the trade acceptable:

1. **The probe goes behind the tunnel before Harry does.** The two unknowns are settled
   against a server that holds no credential.
2. **Harry's tunnel writes no configuration file where marcel's process will read it.** It
   runs with `--url`, as marcel's does. A `config.yml` in `~/.cloudflared/` would be read by
   marcel's `--url` process on its next start, and `cloudflared` refuses `--url` alongside
   ingress rules.
3. **A tunnel that does not end up carrying Harry is deleted**, DNS record included.

## Consequences

**Good:** the trigger path gets proven end to end from outside the house; reaching Harry
from elsewhere becomes possible; marcel is not touched.

**Bad — keep these in view:**

- Harry is publicly reachable. The bearer token is the only thing between the internet and
  a service that can rewrite the tablet. Rotating it means changing `.env.local` on the NUC
  and the routine's environment in the same sitting.
- Every failure of this route — tunnel down, token refused, routine not fired, NUC off —
  reaches Slack as the same sentence: "morning-page has not run today". Telling them apart
  is a triage order written in `docs/`, not a distinct alert.
- There are now two ways the trigger can be configured, and one of them is not in use. The
  local route's proof stays on the board so the fallback is not rediscovered from nothing.
