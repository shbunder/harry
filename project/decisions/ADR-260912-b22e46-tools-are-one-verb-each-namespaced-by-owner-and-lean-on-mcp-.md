---
id: ADR-260912-b22e46
title: Tools are one verb each, namespaced by owner, and lean on MCP's own features
status: Accepted
created: 2026-09-12
feature: ''
supersedes: ''
superseded_by: ''
---

# ADR-260912-b22e46 — Tools are one verb each, namespaced by owner, and lean on MCP's own features

## Status

Accepted. Reverses one paragraph of
[ADR-260912-399f07](ADR-260912-399f07-capabilities-are-folders-under-harry-connectors-tools-and-jo.md)
— tools do get their own folder — and leaves the rest of it standing.

## Context & problem

Harry's entire value crosses one surface: the MCP tools Claude calls. Get their shape
wrong and no amount of correct plumbing behind them helps, because the model either cannot
find the right tool or cannot tell what it does.

The question that forced this was concrete. For the daily digest, Claude asks for today's
candidates, decides what matters, then asks for the page to be built. **Is that two tools,
or one tool with two modes?** And underneath it: how should the surface be organised so it
still works at thirty tools rather than five?

Answering from taste would have been cheap and probably wrong, so this was researched
against Anthropic's published tool-design guidance and the 2026-07-28 MCP specification.

## Decision drivers

1. Claude has to pick the right tool without reading all of them.
2. The morning page is one round trip a day; the surface has to stay cheap in tokens.
3. A capability should declare its tools, not have them assembled by hand somewhere else.
4. Whatever the protocol already solves, Harry should not re-solve.

## Considered options

### Option 1: One tool per workflow, with a mode argument

`daily_digest(action="get_articles" | "build", …)`.

**For:** One name to find, one thing in the roster, and the workflow is visible in a single
place. Fewer entries as the surface grows.

**Against:** It forfeits three things that MCP defines **per tool**, not per call:
annotations (`readOnlyHint` on the read, and not on the push that reaches your tablet);
`outputSchema`, since the two actions return different shapes so a merged schema describes
neither; and tool search, which matches on name and description — a tool that does
everything has a description that matches everything, which retrieves like nothing. The
input schema also becomes a union where almost every field is conditionally required, and
the model cannot tell which.

### Option 2: One tool per verb, aggressively consolidated

Each tool is one action. Separate tools are merged wherever the model does not need to see
what passed between them.

**For:** Every per-tool MCP feature works as designed. Anthropic's guidance is explicitly to
consolidate multi-step workflows — `schedule_event` rather than `list_users` plus
`list_events` plus `create_event` — and the reason is that the intermediate results are
never needed again and only cost context.

**Against:** Taken literally it would merge the digest's two calls too, and that is exactly
wrong here. More entries in the roster, which needs an answer of its own at scale.

## Decision outcome

**One tool per verb**, with one consolidation rule and one exception, stated so neither gets
re-argued:

> **Consolidate when the model does not need to see what passed between the steps.
> Keep them apart when the model's judgement on that intermediate *is* the product.**

Every example in Anthropic's guidance is the first case — Claude does not care about the
user list, it wants the event scheduled. The digest is the second: Claude must see the forty
headlines, because choosing among them is the entire reason
[ADR-260912-bd36c2](ADR-260912-bd36c2-harry-never-calls-a-model.md) exists. Consolidating
would mean either the tool picks the articles, which deletes the judgement Harry is built to
preserve, or the tool calls itself.

So `digest_list_candidates` and `digest_build` are two tools. That round trip is the
product, not overhead. Everywhere the intermediate is *not* the product, merge.

### Tools get their own folder

`.harry/tools/<name>/TOOL.md`, reversing the paragraph in ADR-260912-399f07. A third party
can then add `.harry/tools/push_epub/` against someone else's `remarkable` connector without
touching it, which is the extensibility the folder layout existed for in the first place.

**The schema is not declared.** It is derived from the typed Python signature, the way
FastMCP already does it. Declaring it in the frontmatter as well would be a second copy of
something the code already knows, and the two would drift.

**The body is the MCP description** — the text Claude reads to decide whether to call this
tool. Anthropic's finding is that small refinements to a tool description yield outsized
changes in selection accuracy, which makes this the highest-leverage prose in the repo.

### The rules that hold at scale

| Rule | Why |
|---|---|
| Name is `<namespace>_<verb>`, lowercase with underscores | The folder supplies the namespace, so it is mechanical rather than chosen. Underscores, not dots: MCP permits dots but the Claude API's own tool-name validation is narrower, and the intersection is what travels. |
| Search, never list | `news_search(query, since, limit=50)` over `news_list_all()`. Default limits, pagination, and truncation that tells the caller to search more narrowly. |
| Semantic ids, not opaque ones | `vrt-2026-09-12-nmbs-staking`, not `a7f3c9`. Resolving opaque identifiers to meaningful ones measurably cuts hallucination when one tool's output feeds another's input — which is precisely the digest's shape. |
| A `detail` argument where output can be large | `concise` against `full`. Anthropic measured concise at roughly a third of the tokens. Across forty candidates that is the difference between a cheap ask and an expensive one. |
| Errors steer, not explain | `isError: true` with "no articles since 05:00, try `since=yesterday`". Never a traceback. |
| The roster is sorted | The MCP specification says deterministic ordering improves prompt-cache hit rates. Filesystem order is not deterministic. |
| Most tools are deferred | `always_load: true` is the exception. Anthropic reports the defer-plus-search pattern cuts tool-definition tokens by about 85% on MCP-heavy workloads *and* improves selection accuracy. At least one tool must stay loaded — deferring all of them is a 400. |

### What we take from the protocol rather than build

- **`annotations`** — `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`.
  This is how a client can gate `remarkable_push_document`, which reaches your tablet,
  without gating `news_search`. It only works per tool, which is half the case against the
  mode argument.
- **`outputSchema` and `structuredContent`** — as of 2026-07-28 output schemas are
  unrestricted and structured content may be any JSON value. Declaring the output means
  Claude knows a candidate list's shape before it calls.
- **`resource_link` in tool results** — `digest_list_candidates` returns forty headlines as
  links to the bodies, not the bodies. Claude fetches the six it picked. This is the token
  shape the digest wants, and it may remove the need for a separate fetch tool entirely.
- **Prompts** — a `trigger: claude` job's brief is exposed as an MCP prompt named for the
  job. The scheduled task invokes the prompt instead of calling a bespoke tool to fetch
  text, and the job shows up in any MCP client's prompt picker for free.

## Consequences

**Good:**

- The consolidation question has a written answer, so the next tool does not reopen it.
- Namespace, deferral and annotations become declaration fields rather than per-tool
  judgement calls, which is what makes them consistent at thirty tools.
- The schema has one source — the function signature — so it cannot drift.
- A third party can extend someone else's connector without editing it.

**Bad:**

- **More folders.** A trivial tool still costs a directory and a markdown file. The
  description earns it; the boilerplate around the description does not, and `/new-tool`
  exists to make that cost a single command.
- **Deferral is a guess until measured.** `always_load` is set by whoever writes the tool,
  based on how often they think it is needed. Wrong guesses are invisible — a deferred tool
  that is actually needed every time costs a search round trip on every run, and nothing
  reports it. Worth measuring once there are enough tools to matter.
- **`resource_link` needs the client to follow it.** If a client renders links as text
  rather than fetching them, the digest flow degrades to headlines without bodies. Proving
  this works belongs with the connector spike, not after the renderer is written.
- **Two round trips for the digest, permanently.** That is a deliberate cost, and the first
  rule above is what stops somebody "optimising" it away later.
