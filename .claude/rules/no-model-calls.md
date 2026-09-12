---
paths:
  - "packages/harry/src/harry/**"
  - "Dockerfile"
  - "docker-compose.yml"
  - "**/.env*"
---

# Harry never calls a model

Claude has the LLM. Harry performs heuristic work only.

Every action Harry takes is a rule that can be written down in advance: fetch this feed,
extract this text, render this page, push this file, retry twice, alert on the third.
Where judgement is needed, Claude supplies it through an MCP call.

Decided in
[ADR-260912-bd36c2](../../project/decisions/ADR-260912-bd36c2-harry-never-calls-a-model.md).

## Never

- Import or depend on `anthropic`, `openai`, or any other model client
- Shell out to `claude`, `claude -p`, or any other model CLI
- Read `ANTHROPIC_API_KEY` or any provider credential, in `config.py` or anywhere else
- Install a model CLI in the image, or mount anyone's `~/.claude` into the container
- Write a heuristic that is really a judgement in disguise — scoring an article for
  "interestingness", ranking headlines by importance, summarising prose, choosing a tone

## Always

- Put the judgement in Claude's hands through a tool. Harry returns **candidates with
  facts**; Claude returns **choices with reasons**
- Keep every Harry rule stateable in one sentence a person could follow by hand. Dedupe by
  title similarity above a threshold, cap at N articles, retry twice then alert — all fine,
  because each one is a rule rather than an opinion
- When a job genuinely needs judgement, make it two steps: Harry gathers, Claude decides,
  Harry executes. The blocking MCP call is the mechanism, and it is the same shape as
  `ask_human()`

## Why

Two reasons, and the second is the one that lasts.

**The credentials.** A Harry that may call a model needs a provider key or a subscription
token, plus the CLI and the runtime to install it, plus a mount of your own credentials
into its container. That is a second credential that expires quietly, on top of the De Tijd
session that already does. The ADR's consequences section has the full count.

**The boundary stays checkable.** Once Harry may call a model, "should this bit of
judgement live in Harry or in Claude?" has no principled answer — only taste, re-argued on
every feature, drifting a little each time. With this rule the answer is mechanical: does
it need judgement? Then it is Claude's, and Harry's job is to hand over the facts and carry
out the result.

## The one thing this costs

**Harry cannot report its own absence.** When Harry owned the trigger, a morning with no
page was a job that failed and said so. With an external trigger, a task that never fires
produces silence — and silence looks exactly like a morning you did not check.

So the watchdog is not optional: a Harry job that asks "was a digest built since 05:00?"
and posts to Slack when the answer is no. It is pure heuristic — a timestamp comparison —
and it is the only thing standing between you and three quiet weeks. See **Alerting** in
`CLAUDE.md`.

## Common rationalizations

| Excuse | Reality |
|---|---|
| "It's only a small classification" | A classification is a judgement. Return the candidates and let Claude classify. |
| "A round trip to Claude is slow" | It is one page a day. The ADR says so, so it stops being rediscovered. |
| "Harry already has the data, it may as well rank it" | Ranking is the product. That is the half Claude is for. |
| "Just for the fallback path, when Claude is unreachable" | A fallback that quietly writes a worse page is exactly what **Degrading** and **Alerting** forbid. Print "unavailable" and say so. |
| "The CLI is already in the image" | Then the image is wrong. That is what this rule deletes. |

## Enforcement

`.claude/agents/code-reviewer.md` and `pre-close-verifier` check the diff for a model
client, a model CLI invocation, a provider credential, and for a heuristic that is really a
judgement. `tests/test_no_model_dependencies.py` fails if a provider package reaches the
dependency tree. Severity: **Critical** — cite **Heuristic**.
