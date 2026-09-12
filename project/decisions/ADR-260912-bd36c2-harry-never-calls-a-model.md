---
id: ADR-260912-bd36c2
title: Harry never calls a model
status: Accepted
created: 2026-09-12
feature: ''
supersedes: ''
superseded_by: ''
---

# ADR-260912-bd36c2 — Harry never calls a model

## Status

Accepted

## Context & problem

Harry and Claude split one job between them, and the split has to be stated in a way that
settles arguments rather than starting them.

The original plan described the morning page like this: at 06:30 Harry's scheduler wakes
up and runs `claude -p` on the NUC. That session asks Harry for candidates, picks what
matters, and asks Harry to build the page. The plan chose it for two practical reasons — a
NUC is awake at 06:30 when a laptop is not, and a Claude scheduled task in the cloud may
not be able to reach a self-hosted server on a personal plan.

Both reasons are about **where the clock lives**, and framing it that way hid the more
important question. If Harry may invoke `claude -p`, then Harry runs a model. It needs an
API key or a subscription token. It needs the Claude Code CLI, and Node to install it. It
needs your `~/.claude` credentials mounted into its container. And it acquires a second
credential that expires quietly and needs its own alert, on top of the De Tijd session
that already does.

Nothing about "who owns the clock" makes any of that necessary. It arrived as a side
effect of an unexamined boundary.

## Decision drivers

1. One sentence a reader can apply without asking anyone — and a decision they can check.
2. Fewer credentials in Harry, especially fewer that expire on their own schedule.
3. A container that is easy to rebuild and hard to get wrong.
4. Not blocking the morning page on a connector question nobody has tested yet.

## Considered options

### Option 1: Harry owns the clock and invokes `claude -p`

The plan as written. Harry's scheduler is the trigger; a Claude Code session on the NUC
does the choosing over localhost MCP.

**For:** The NUC never sleeps, so 06:30 always fires. The MCP call never leaves the
machine — no tunnel, no latency, no external dependency in the critical path. It works on
any plan, because `claude mcp add` does. And the thing that owns the schedule is the thing
that can notice the schedule did not run.

**Against:** Harry runs a model. That brings an API key or a subscription token into
Harry's own credential set, plus Node, npm and the Claude Code CLI in the image, plus a
read-only mount of your `~/.claude` into the container. The token expires and needs its own
lapse alert. And the boundary between the two halves stops being checkable: once Harry may
call a model, there is no principled answer to "should this bit of judgement live in Harry
or in Claude?" — only taste, re-argued per feature.

### Option 2: Claude owns the clock; Harry never calls a model

A Claude scheduled task fires at 06:30. It calls `list_candidates()`, reads what comes
back, decides, and calls `build_digest()`. Harry fetches the chosen articles, renders the
page, pushes it to the tablet.

**For:** One sentence settles every future question about where a capability belongs.
Harry keeps exactly three credentials and one of them stops existing. The image loses Node,
npm and the CLI. Nothing mounts your Claude credentials anywhere. Harry stays a service you
can reason about without thinking about tokens or model behaviour at all.

**Against:** It depends on a Claude scheduled task being able to reach a self-hosted MCP
server, which is untested on this account and may need a plan Harry's owner does not have.
And an external trigger cannot report its own absence: if the task never fires, nothing in
Harry knows — unless Harry is given a way to notice, which is the consequence below.

## Decision outcome

**Harry never calls a model.** Claude has the LLM; Harry performs heuristic work only.

Every action Harry takes is a rule that can be written down in advance: fetch this feed,
extract this text, render this page, push this file, retry twice, alert on the third.
Where judgement is needed, Claude supplies it through an MCP call.

Concretely: Harry holds no `ANTHROPIC_API_KEY`, ships no Claude Code CLI, mounts no
`~/.claude`, and has no code path that reaches a model provider.

Harry keeps a scheduler, and that is not a contradiction. Its jobs are the heuristic ones —
refresh a cache, retry a failed push, check whether a credential still works, notice that
no page was built today. Claude may also ask Harry to create a job, which is a request to
run a rule on a timer, not a delegation of judgement.

This names the principle **Heuristic**, and it is the one the other four rest on.

## Consequences

**Good:**

- One credential disappears. Harry's dangerous three become the reMarkable device token,
  the iCloud app password and the De Tijd browser session — and only one of those expires
  quietly, instead of two.
- The image drops Node, npm and the Claude Code CLI, and compose drops the `~/.claude`
  mount. Less to rebuild, less to keep current, and nothing of yours inside the container.
- "Should this live in Harry or in Claude?" has a mechanical answer for every future
  capability: does it need judgement? The question stops being re-argued per feature.
- Harry becomes testable without a model anywhere in the loop. Every path is a fixture.

**Bad — and this is the part to keep in view:**

- **Harry can no longer report its own absence.** When Harry owned the trigger, a morning
  with no page was a job that failed and said so. With an external trigger, a task that
  never fires produces silence, and silence looks exactly like a morning you did not check.
  The answer is a heuristic watchdog: a Harry job that asks "was a digest built since
  05:00?" and posts to Slack when the answer is no. That job is now load-bearing rather
  than nice to have, and it belongs in the first digest feature, not a later one.
- **The trigger path is unproven.** A Claude scheduled task reaching a self-hosted MCP
  server over the tunnel is Phase 0's connector spike, and it is now on the critical path
  rather than a ten-minute curiosity. If it fails, the clock has to live somewhere else
  that is still not Harry — a `cron` entry on the NUC calling the tunnel, or a Claude Code
  routine — and this decision holds either way.
- The morning page gains a network round trip it did not have. A cloud task reaching Harry
  over the tunnel is slower and has more to go wrong than a localhost call. For one page a
  day this is not worth optimising, and saying so here stops it being rediscovered.
