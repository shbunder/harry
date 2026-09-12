---
id: ADR-260912-399f07
title: Capabilities are folders under .harry — connectors, tools and jobs
status: Accepted
created: 2026-09-12
feature: ''
supersedes: ''
superseded_by: ''
---

# ADR-260912-399f07 — Capabilities are folders under .harry: connectors, tools and jobs

## Status

Accepted

## Context & problem

The original plan had one kind of extension: a **module**, a directory under
`harry/modules/` with a `module.yaml` and a `register()` function that could declare a
tool, a digest section, a scheduled job, an HTTP route and a Slack action.

Two things were wrong with it.

**The morning page was special.** `r.section()` existed in the global registry because the
digest was assumed to be *the* output. But the morning page is one job among many — a
weekly reading list, a monthly bill summary and a watchdog are all the same shape. A
registry method that only one capability ever uses is that capability leaking into core.

**One word covered three different things.** The reMarkable cloud is a place Harry can
reach, with a credential and a renewal procedure. `push_document` is something Claude can
ask for. The morning page is something that happens at a time. Calling all three "modules"
meant nothing about a module told you what it needed, what it exposed, or when it ran.

## Decision drivers

1. A sentence that settles where a new capability belongs, without a conversation.
2. Adding a job should require no Python, and no core change ever.
3. The operational runbook for a credential should live next to the credential.
4. Keep the model boundary from [ADR-260912-bd36c2](ADR-260912-bd36c2-harry-never-calls-a-model.md)
   checkable, not just stated.

## Considered options

### Option 1: Keep one `module` kind

Everything stays a directory with a `register()` function; jobs are declared in Python with
`r.job()`.

**For:** One concept to learn and one discovery mechanism. Registering a job in code means
it can be built from anything at import time. Nothing to rename.

**Against:** Adding a job needs Python, so the cheapest thing anyone would want to add is
the one with the highest floor. The word "module" carries no information — you open
`module.yaml` to find out whether the thing holds a credential or renders a page. And the
registry keeps accumulating methods for whatever the newest capability happens to need,
which is how `r.section()` got there.

### Option 2: Three kinds, declared on the filesystem under `.harry/`

**Connectors** and **jobs** are folders with a markdown file, discovered by walking the
directory. **Tools** are declared in Python by whichever connector or job owns them.

**For:** The kind is the answer to "what is this?" — a connector holds a credential, a job
has a trigger, a tool is a verb Claude can call. A job becomes a markdown file with a YAML
header, so adding one needs no Python at all. The De Tijd re-login procedure lives in
`.harry/connectors/tijd/CONNECTOR.md`, beside the code it is about, instead of in a
documentation page somebody has to remember exists. And `.harry/` mirrors `.claude/`, so
anyone who has used Claude Code reads the layout immediately.

**Against:** Three concepts instead of one, and a filesystem format is a thing that can be
malformed — which needs a validator that Python's import mechanism gave for free. `.harry/`
is hidden, and it holds the product rather than configuration, so every path-aware tool
(coverage, pyright, ruff, `COPY` in the Dockerfile) has to be told about a directory that
does not show up in `ls`.

## Decision outcome

**Harry's capabilities are three kinds, and two of them are folders under `.harry/`.**

> A **connector** is somewhere Harry can reach.
> A **tool** is something Claude can ask for.
> A **job** is something Harry does on its own.

```
.harry/
├── connectors/<name>/CONNECTOR.md   + the code that reaches it
└── jobs/<name>/JOB.md               + the scripts it runs
```

**Tools do not get their own directory.** A tool is a function signature and a docstring,
which is exactly what MCP publishes; a markdown file per tool would be filing, not design.
Every tool is declared with `r.tool()` inside the connector or job that owns it, so it
always has one. `tools` is still a first-class word — it is what the MCP surface is made
of, and it is the only place judgement crosses from Claude into Harry.

> **Reversed by
> [ADR-260912-b22e46](ADR-260912-b22e46-tools-are-one-verb-each-namespaced-by-owner-and-lean-on-mcp-.md).**
> Tools do get their own folder, `.harry/tools/<name>/`. The argument above weighed only the
> filing cost and missed the one that matters: a tool in its own folder can be added against
> someone else's connector without editing it, which is the extensibility this whole layout
> existed for. The rest of this decision stands.

`r.section()` leaves the registry. A page is assembled by the job that produces it.

### What each file carries

**Frontmatter is what Harry does.** Machine-readable and executed: the trigger, the
schedule, the deadline, the connectors required, whether it is enabled.

**The body is what Claude is told.** Harry stores it and serves it verbatim. It never
parses it, templates it, or branches on it — that would be reasoning, which Harry does not
do.

A job with no mind in the loop has a body that is documentation and nothing serves it. That
is not an inconsistency: `trigger:` says which kind of job it is, so it is never ambiguous
which the body is for.

## Consequences

**Good:**

- **Adding a job needs no Python.** A markdown file with a YAML header is the whole thing,
  which is the right floor for the cheapest capability to add.
- **The watchdog is free for every job.** `deadline:` is a field, not a feature, so any job
  that declares one is watched — and the alert that
  [ADR-260912-bd36c2](ADR-260912-bd36c2-harry-never-calls-a-model.md) made load-bearing
  stops being specific to the morning page.
- **The runbook lives with the thing.** How to renew the De Tijd session sits in that
  connector's own file, next to the code that uses it.
- **Core stops growing.** The registry has one method per kind rather than one per
  capability that needed something.
- **The morning page stops being special**, which was the point.

**Bad:**

- **A filesystem format can be malformed**, where an import either worked or raised.
  `scripts/check_capabilities.py` runs in `make lint` to catch it at the gate rather than
  at 06:30.
- **`.harry/` is hidden and holds the product.** Coverage, pyright, ruff and the Dockerfile
  each need the path added, and those four rosters are now a thing that can disagree. The
  same hazard already exists for `project/` and `scripts/`, and it has already been got
  wrong once here.
- **Two mechanisms, not one.** Connectors and jobs are discovered from disk; tools are
  registered in code. The seam is defensible — a tool has no configuration of its own — but
  it is a seam, and somebody will eventually ask why tools have no folder. The answer is in
  this file.
- **A job's body is trusted text that Claude acts on.** It is authored in the repo and
  reviewed like code, which is what makes that safe. Content fetched from the outside must
  never reach it.
