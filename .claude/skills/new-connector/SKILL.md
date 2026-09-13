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
provides: [<tool>, …]                  # the tools this connector declares
expires: never                         # never | manual | session
enabled: true
config:
  some_token:
    description: <what it is, and how to get one>
    secret: true                       # never rendered into the committed .env
    required: true                     # absent, the connector disables itself and says so
  some_url:
    description: <what it points at>
    default: https://example.test
---
```

`config:` is the schema and the only place a setting is declared. There is no
`requires_env` — it said less and was a second copy of `required: true`.

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

### 4. Decide what to expose, and in what shape

**Write down everything this connector can read**, before thinking about tools. For iCloud
that is events, calendars, to-dos, and whatever else CalDAV will answer.

Then go through that list once and ask of each: **would somebody actually ask for this?**

- Yes → it becomes a tool. Add it to `provides:` and run `/new-tool`.
- No → leave it. Not exposing something needs no justification.

Both easy answers are wrong. Exposing only what a job needs traps the data — Harry holds
the credential and an ordinary question returns nothing. Exposing everything the API has
hands over a protocol and lets the service decide Harry's surface.

**Then decide the shape, which matters as much as the answer.** `icloud_list_events(day)`
is a tool; `icloud_caldav_report(xml)` is a protocol wearing a tool's name. Ask what the
person wants back, not what the service returns.

**Write down what you chose not to expose**, in the body, in a line each. Nothing will
catch a useful read path you forgot — it simply will not be there, and nobody finds out
until they ask and get nothing.

Three things always stay internal: the health check, anything only core would call, and a
write that should be approved before it is offered casually.

Keep each tool a **verb with facts in and facts out**. If a tool is choosing, ranking or
summarising, that is judgement and it belongs on Claude's side — return the candidates
instead. `.claude/rules/no-model-calls.md` and `.claude/rules/tool-design.md`.

### 5. Configuration lives in this folder

```bash
make env-template
```

That writes `.env` beside your declaration, from `config:`. **Never edit it** — `make lint`
fails when it has drifted from the schema. Put your own values in `.env.local` beside it,
which is gitignored.

Keys there are bare: `SOME_TOKEN`, not `HARRY_<NAME>_SOME_TOKEN`. The folder is the
namespace. The prefixed spelling is the environment override, for a container, and the
generated file names it beside every key.

Write the `description` for somebody who has to get the value at 07:00 — the page to visit,
the command to run. It becomes the comment beside the key, and that is the only place
anybody will look. `.claude/rules/secrets-and-config.md`.

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
grep -rn "connectors\." src/harry/*.py    # core must name no capability
```

Must come back empty. The moment core knows a connector's name, adding the next one stops
being one folder.

### The code, if it has any

`.harry/connectors/<name>/connector.py`, with one function:

```python
from harry.sdk import Context, Registry


def register(registry: Registry, context: Context) -> None:
    registry.connector(...)
```

`registry.connector()` takes no name — the name, the description and the annotations are in
the declaration Harry already read, and a second copy would drift from the first. It
returns what you passed, so `@registry.connector` over a function works.

`context` carries `name`, `kind`, `folder`, `declaration`, `body`, `config`,
`config_for(principal)`, `log` and `connectors`.

**`context.connectors` is how you use another capability** — `context.connectors['slack']`
is what the connector you named in `requires:` registered. You never import one: two
folders that import each other are two folders that cannot be swapped.

**Import `harry.sdk` and nothing else under `harry`.** Reaching further is refused before
your module runs, so the capability is skipped and `/health` names the import. Files beside
the entry module are checked too, and relative imports between them are fine.

A folder with no Python at all is still a whole capability.

### 9. Report

The connector name, what it reaches, what it needs configured, whether its credential
expires and how you would find out, and what callers get on the day it is down.
