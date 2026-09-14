---
name: new-tool
description: Add a tool to Harry — one verb Claude can ask for, under .harry/tools/. Use when Claude needs to be able to do something new over MCP. For somewhere Harry can reach use /new-connector; for something Harry does on its own use /new-job.
---

Add a tool for: $ARGUMENTS

A tool is **something Claude can ask for**. It is the only surface Harry's value crosses,
so its shape matters more than its implementation. `.claude/rules/tool-design.md` is the
standard; this is the procedure.

### 1. Check it is one verb, and check it should not be merged

> **Consolidate when the model does not need to see what passed between the steps.
> Keep them apart when the model's judgement on that intermediate *is* the product.**

Before adding anything, look at the tools that already exist:

```bash
ls .harry/tools/
```

If your new tool would be called immediately after an existing one, and Claude does not
need to read what the first returned, **merge them instead of adding this.** That is the
common case and it is what keeps the roster small.

If Claude must see the intermediate to decide something, they are two tools. Say which
case this is, in one line, before continuing.

**Never a mode argument.** `thing(action="get"|"build")` forfeits annotations,
`outputSchema` and tool-search matching, all of which MCP defines per tool.

### 2. Name it

`<namespace>_<verb>`, lowercase, underscores only — never dots, which MCP permits but the
Claude API's own validation does not. The namespace is the owner: `digest_`, `news_`,
`remarkable_`.

The folder name is the tool name.

### 3. Open the feature

```bash
/new-feature <what this lets Claude do, in your terms>
```

Usually the **story track**, unless the tool brings a new connector or a new credential.
Declare `--touches .harry/tools/<name>`.

### 4. Write the declaration

`.harry/tools/<name>/TOOL.md`:

```yaml
---
name: <namespace>_<verb>
namespace: <namespace>
description: <one line for the roster>
requires: [<connector>, …]
optional: [<connector>, …]
always_load: false          # true only if it is needed nearly every run
annotations:
  readOnlyHint: true        # required — it is how a client knows what to gate
  destructiveHint: false
  idempotentHint: true
  openWorldHint: false
enabled: true
---
```

`always_load: false` is the default and should stay that way. Deferred tools are loaded on
demand by tool search, which cuts tool-definition tokens by about 85% on a large roster
*and* improves selection accuracy. Set `true` only for the two or three tools a session
reaches for nearly every time.

`readOnlyHint` is required because nothing else carries the difference between reading a
feed and pushing to your tablet.

### 5. Write the body — this is the part that matters

The body is the **MCP description**: what Claude reads to decide whether to call this tool.
Small refinements here move selection accuracy more than almost anything else in the repo.

Write three things:

- **What it returns**, concretely. Not "digest data" — "the weather, the day's agenda, and
  up to 40 headlines with summaries and ids".
- **When to reach for it**, and what usually follows.
- **When not to** — the neighbouring tool it gets confused with, named.

Describe it as you would to a new colleague, and make the implicit explicit.

### 6. Shape the signature

The input schema comes from the **typed Python signature** — do not declare it in the
frontmatter, or it becomes a second copy that drifts.

- Unambiguous parameter names: `article_ids`, not `ids`.
- A `limit` with a sensible default (50) on anything that could return a lot.
- A `detail: "concise" | "full"` argument wherever output can be large. Concise measures at
  roughly a third of the tokens.
- Return **semantic ids** — `vrt-2026-09-12-nmbs-staking`, not `a7f3c9`. This measurably
  cuts hallucination when this tool's output feeds another's input.
- Return **`resource_link`** for anything big, so Claude fetches only what it picked.
- High-signal fields only. `title`, `source`, `published` — not `mime_type`, `uuid`.

### 7. Errors steer

`isError: true` with what to try instead: *"no articles since 05:00 — try
`since=yesterday`"*. Never a traceback, never a bare code.

### 7b. Settings, if it has any

Declare them in this tool's own `config:` and run `make env-template`. Bare keys — the
folder is the namespace.

### 8. Validate and test

```bash
uv run python scripts/check_capabilities.py
make check
```

The validator catches the namespace prefix, a dotted name, a missing `readOnlyHint`, an
unknown annotation, a near-empty description, and a roster where everything is deferred.

Then tests: the happy path against a fixture, the failure path asserting the steering
message, and — if `requires` names a connector — the path where that connector is down.

### The code, if it has any

`.harry/tools/<name>/tool.py`, with one function:

```python
from harry.sdk import Context, Registry


def register(registry: Registry, context: Context) -> None:
    registry.tool(...)
```

`registry.tool()` takes no name — the name, the description and the annotations are in
the declaration Harry already read, and a second copy would drift from the first. It
returns what you passed, so `@registry.tool` over a function works.

`context` carries `name`, `kind`, `folder`, `declaration`, `body`, `config`,
`config_for(principal)`, `log`, `connectors` and `alert`.

**`context.alert(message, key=…)` is how you report your own failure.** `log` is for
whoever is reading the log; `alert` is for whoever is not — a feed dead since March, a
credential that lapsed. The key makes it one message a day, and Harry scopes it to you.
Your declared secrets are scrubbed from the message first.

**`context.connectors` is how you use another capability** — `context.connectors['slack']`
is what the connector you named in `requires:` registered. You never import one: two
folders that import each other are two folders that cannot be swapped.

**Import `harry.sdk` and nothing else under `harry`.** Reaching further is refused before
your module runs, so the capability is skipped and `/health` names the import. Files beside
the entry module are checked too, and relative imports between them are fine.

A folder with no Python at all is still a whole capability.

### 9. Report

The tool name, whether it merged with an existing one or stands apart and why, what it
returns, whether it is loaded or deferred and on what evidence, and the neighbouring tool
its description tells Claude to prefer instead.
