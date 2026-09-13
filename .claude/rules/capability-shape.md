---
paths:
  - ".harry/**"
  - "src/harry/**"
---

# A connector, a tool or a job — and core never learns any of their names

> A **connector** is somewhere Harry can reach.
> A **tool** is something Claude can ask for.
> A **job** is something Harry does on its own.

Decided in
[ADR-260912-399f07](../../project/decisions/ADR-260912-399f07-capabilities-are-folders-under-harry-connectors-tools-and-jo.md).
Core provides the registry, the MCP server, the scheduler, the store and the HTTP app.
Nothing else.

```
.harry/
├── connectors/<name>/CONNECTOR.md   + the code that reaches it
├── tools/<name>/TOOL.md             + the function it calls
└── jobs/<name>/JOB.md               + the scripts it runs
```

Each folder is one **implementation** of a capability. How a tool in particular must be
shaped — one verb, namespaced, deferred by default, and what its body has to say — is
[tool-design.md](tool-design.md); this file covers what all three kinds have in common.

## Never

- Name a capability in core. No `if name == 'digest'`, no registry of known connectors, no
  import list. Discovery walks the directory
- Import one capability from another. If two need the same thing, it belongs in the SDK or
  in a connector they both declare
- `import harry.scheduler`, `harry.store`, `harry.mcp` or `harry.main` from a capability.
  They import `harry.sdk` and only `harry.sdk`
- **Parse, template or branch on a job's body.** That is reasoning, and Harry does not
  reason — see [no-model-calls.md](no-model-calls.md)
- Put a second clock on a `trigger: claude` job. Two schedules that can disagree is the
  thing that decision removed
- Let one capability's failure take another down

## Always

- **Load every capability inside its own try/except.** One broken connector is logged and
  skipped; the rest come up. This is the single rule that makes a half-finished capability
  safe to leave on disk, and it is what lets you develop here at all
- Keep the two halves of a declaration straight. **Frontmatter is what Harry does** —
  machine-readable and executed. **The body is what Claude is told** — stored and served
  verbatim
- Declare `requires_env` on a connector, and `requires` on a job. A capability whose
  configuration is absent reports that and disables itself; it does not crash and it does
  not pretend to work
- Give every connector an `expires:`. Two of Harry's three credentials do expire, and one
  nobody declared is one nobody watches
- Give every `trigger: claude` job a `deadline:`. An external trigger cannot report its own
  absence
- **Let a job compose tools rather than reimplement them.** The morning page calls
  `build_digest`; it does not know how to render a PDF. Two code paths for the same work
  get fixed twice and drift in between
- Support `$HARRY_CAPABILITIES_DIR` for out-of-tree capabilities from day one. A contract
  that only works in-tree is not a contract

## Why

The whole point is that adding a capability — Todoist, a dishwasher, a weekly reading list
— is one folder, and a job is one markdown file with no Python at all. The moment core
knows a capability's name, that stops being true and every later one costs a core edit and
a core review.

The try/except is not defensive programming, it is the property that makes the design
usable. Without it, the first capability you leave half-written stops the morning page from
rendering, and you learn to develop somewhere else.

The three kinds exist because one word was hiding three different things. A connector holds
a credential and a renewal procedure. A tool is where judgement crosses from Claude into
Harry. A job has a trigger and a deadline. Calling all three "modules" meant you had to
open the file to find out which you were looking at.

## Common rationalizations

| Excuse | Reality |
|---|---|
| "Just this one import from the scheduler" | Then the SDK is missing something. Add it there. |
| "The morning-page job obviously needs the news connector" | It needs `requires: [news]`, which the registry already resolves. |
| "A broken capability should fail loudly" | It should fail loudly **and alone**. Log it, skip it, alert it. |
| "The job can just render the page itself" | Then rendering has two homes. Call the tool. |
| "I'll template one value into the brief" | That is Harry reading the body. Pass it as a tool argument instead. |
| "Out-of-tree capabilities are a later problem" | The directory walk costs four lines now and a redesign later. |

## Enforcement

`scripts/check_capabilities.py` validates every declaration and runs in `make lint`: a name
that disagrees with its folder, a schedule with no timezone, a `trigger: claude` job with no
deadline, a connector with no `expires`, a job requiring a connector that does not exist, a
folder with no declaration at all. `tests/test_capabilities.py` makes each of those fail.

`.claude/agents/code-reviewer.md` and `pre-close-verifier` check imports in `.harry/**`
against this rule, and check that discovery still names no capability. Severity:
**Critical** — cite **Modular**.
