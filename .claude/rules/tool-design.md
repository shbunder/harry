---
paths:
  - ".harry/tools/**"
  - ".harry/**/TOOL.md"
---

# A tool is one verb, and the model has to find it

Tools are the only surface Harry's value crosses. Get their shape wrong and correct
plumbing behind them does not help, because the model either cannot find the right tool or
cannot tell what it does.

Decided in
[ADR-260912-b22e46](../../project/decisions/ADR-260912-b22e46-tools-are-one-verb-each-namespaced-by-owner-and-lean-on-mcp-.md),
against Anthropic's published tool-design guidance and the 2026-07-28 MCP specification.

## The consolidation rule

> **Consolidate when the model does not need to see what passed between the steps.
> Keep them apart when the model's judgement on that intermediate *is* the product.**

Merging `list_users` + `list_events` + `create_event` into `schedule_event` is right:
Claude does not care about the user list, it wants the event scheduled, and the
intermediate only costs context.

`digest_list_candidates` and `digest_build` stay apart: Claude must see the forty headlines,
because choosing among them is the entire reason
[no-model-calls.md](no-model-calls.md) exists. That round trip is the product, not overhead.

## Never

- **A tool with a mode argument.** `daily_digest(action="get"|"build")` forfeits three
  things MCP defines per tool: annotations, `outputSchema`, and tool-search matching. Its
  input schema also becomes a union where the model cannot tell what is required when
- A dot in a tool name. MCP permits it; the Claude API's validation is narrower
- A tool name without its namespace prefix
- Declare the input schema in the frontmatter. It comes from the typed Python signature —
  two copies drift
- Return an opaque id where a meaningful one exists
- Return a traceback. Return what to try instead
- Emit the roster in filesystem order

## Always

- **`<namespace>_<verb>`**, lowercase with underscores. The folder supplies the namespace
- **Write the body for Claude.** It is the MCP description — the text the model reads to
  decide whether to call this tool, and small refinements to it move selection accuracy
  more than almost anything else you can change. Say what it returns, when to reach for it,
  and when not to
- **Search, never list.** `news_search(query, since, limit=50)` over `news_list_all()`.
  Default limits, pagination, and truncation that tells the caller to search more narrowly
- **Semantic ids.** `vrt-2026-09-12-nmbs-staking`, not `a7f3c9`. Resolving opaque
  identifiers to meaningful ones measurably cuts hallucination when one tool's output feeds
  another's input — which is exactly the digest's shape
- **A `detail` argument** wherever output can be large: `concise` against `full`. Measured
  at roughly a third of the tokens. Across forty candidates that is the whole cost
- **`readOnlyHint`, and the other hints where they apply.** This is how a client gates
  `remarkable_push_document`, which reaches your tablet, without gating `news_search`
- **`resource_link` for anything big.** Return forty headlines as links to the bodies, not
  the bodies. Claude fetches the six it picked
- **`always_load: true` only for what is needed nearly every run.** Everything else defers.
  The defer-plus-search pattern cuts tool-definition tokens by about 85% on MCP-heavy
  workloads *and* improves selection accuracy. At least one tool must stay loaded

## Why

Two costs, paid on every request. The roster is sent in full on every call, so every tool
that is loaded and unused is rent. And the model picks from names and descriptions alone —
if two tools read alike, it picks wrong, and the failure looks like a bug in the tool it
chose.

Deferral answers the first and namespacing answers the second. Both are declaration fields
rather than judgement calls, which is what makes them survive thirty tools.

## Common rationalizations

| Excuse | Reality |
|---|---|
| "Two tools is two round trips" | One of them is where Claude decides. That is the product. |
| "One tool with a mode is fewer entries" | And no annotations, no output schema, and it retrieves like nothing. |
| "The description is obvious from the name" | The name is 30 characters. The model has nothing else to go on. |
| "Load them all, it's only a few thousand tokens" | On every request, forever, most of them unused. |
| "The UUID is what the API returns" | Then map it. The model is the consumer, not the API. |

## Enforcement

`scripts/check_capabilities.py` in `make lint`: the namespace prefix, the underscore rule,
a missing `readOnlyHint`, an unknown annotation, a near-empty description body, and a roster
where every tool is deferred — which the API rejects outright. `tests/test_capabilities.py`
makes each one fail. Severity: **Important**; **Critical** for a mode argument or a deferred
roster.
