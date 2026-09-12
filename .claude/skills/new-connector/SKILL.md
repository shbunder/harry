---
name: new-connector
description: Add a connector to Harry — somewhere Harry can reach, with its credential, its health check and its renewal procedure, under .harry/connectors/. Use for a new data source, output surface or external service.
---

Add a connector for: $ARGUMENTS

A connector is **somewhere Harry can reach**. It owns the credential, the client code, the
tools that use it, and the runbook for when it stops working. One folder under
`.harry/connectors/`. `.harry/README.md` has a worked example.

### 1. Open the feature

```bash
/new-feature <what this lets Harry reach, in your terms>
```

A connector is almost always the **full track**: it brings an external dependency and
usually a credential. Declare `--touches .harry/connectors/<name>`.

### 2. Write the declaration

`.harry/connectors/<name>/CONNECTOR.md`. The `name` must match the folder.

```yaml
---
name: <name>
description: <what it reaches, and what that gets you>
requires_env: [SOME_TOKEN, SOME_URL]   # absent config disables the connector, quietly and cleanly
provides: [<tool>, …]                  # the tools this connector declares
expires: never                         # never | manual | session
enabled: true
---
```

`expires:` is required and it is not bookkeeping — it is what tells Harry to watch the
credential at all. `session` means a browser login that lapses on its own; `manual` means a
token you renew by hand; `never` means it does not expire.

### 3. The body is the runbook

This is why a connector is a folder. Write, for whoever reads it under pressure:

- what breaks when this stops working, and what still renders
- what reaches Slack when it does
- **the exact steps to fix it** — the URL to visit, the command to run, where the file goes

The De Tijd re-login and the reMarkable re-pairing belong here, next to the code they are
about, rather than in a documentation page somebody has to remember exists.

### 4. List what it provides, then add the tools separately

`provides:` in the frontmatter names the tools that will use this connector. Each one is
its own folder under `.harry/tools/`, added with `/new-tool` — so somebody can extend this
connector later without editing it.

Keep each tool a **verb with facts in and facts out**. If a tool is choosing, ranking or
summarising, that is judgement and it belongs on Claude's side — return the candidates
instead. `.claude/rules/no-model-calls.md` and `.claude/rules/tool-design.md`.

### 5. Configuration

Every value goes in `harry/config.py`, typed, with a comment saying what it is for **and how
to get it** — the pairing URL, the app-password page, the login script. Then the same key
and explanation in `.env`, the committed one. Secrets stay empty there and are filled in
`.env.local`. `.claude/rules/secrets-and-config.md`.

### 6. Answer the failure questions before writing any code

1. **What does a caller get when this is unreachable?** Never an exception that escapes —
   a degraded result the job can still use.
2. **What reaches Slack, and how often?**
3. **If `expires:` is not `never`, how does Harry find out it lapsed?** A health check that
   is itself heuristic: try the thing, see if it works.

### 7. Tests

- The happy path, against a **recorded fixture** in `tests/fixtures/` — never a live URL.
- The failure path: record the real 403, the malformed entry, the rejected write, and
  assert what the caller gets and what gets sent.
- The disabled path: with `requires_env` absent, the connector registers nothing and Harry
  still starts.
- Anything that genuinely needs the real service is marked `live` and runs from
  `make test-live`.

```bash
uv run python scripts/check_capabilities.py
make check
```

### 8. Prove the contract still holds

```bash
grep -rn "connectors\." packages/harry/src/harry/*.py    # core must name no capability
```

Must come back empty. The moment core knows a connector's name, adding the next one stops
being one folder.

### 9. Report

The connector name, what it reaches, what it needs configured, whether its credential
expires and how you would find out, and what callers get on the day it is down.
