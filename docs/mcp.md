# Talking to Harry from Claude

Harry serves the Model Context Protocol — the way Claude calls an outside service — at
`/mcp`, behind a bearer token. Everything a capability registered is published there; core
knows the name of none of it.

## Registering it

```bash
claude mcp add --transport http harry http://localhost:7430/mcp \
  --header "Authorization: Bearer $(grep '^HARRY_API_TOKEN=' .env.local | cut -d= -f2)"
claude mcp list
```

Off the machine, the URL is `HARRY_PUBLIC_URL` instead of localhost.

**`.mcp.json` in this repository is not a shortcut past that.** It registers Harry at
`localhost:7430` with `Bearer ${HARRY_API_TOKEN:-probe-token-not-a-secret}`, expanded from
the **shell environment** — and nothing here exports `.env.local`, by design: `config.py` is
the only reader, which is what keeps its precedence true. So a session started in this
repository sends the probe's placeholder token and Harry answers 401 to its own owner,
correctly. Either export the real token in your shell before starting the session, or use
the `claude mcp add` recipe above, which reads the file.

Port 7430 is also where `make probe` serves. If `/health` there returns 404, what is
answering is the probe and not Harry.

## Settings

| Key | Default | What it does |
|---|---|---|
| `HARRY_API_TOKEN` | empty | The bearer token. **Empty authorises nobody, including you** — an unconfigured Harry behind the tunnel would otherwise serve the internet. Generate one with `openssl rand -hex 32` and put it in `.env.local` |
| `HARRY_PORT` | `7430` | Where Harry listens |
| `HARRY_PUBLIC_URL` | empty | The tunnel hostname, for a session that is not on this machine |

## What gets published

**A tool** — one folder under `.harry/tools/`, one verb, one function:

| Part of the tool | Comes from |
|---|---|
| Name | The folder, which the declaration must agree with |
| Description | The `TOOL.md` **body**, verbatim |
| Annotations | The `annotations:` block — `readOnlyHint` and the rest |
| Input schema | The typed Python signature, and nowhere else |

The description is the part that matters. It is what Claude reads to decide whether to call
this tool, and small changes to it move selection accuracy more than almost anything else
you can edit. Harry serves it exactly as written — it never summarises, templates or
re-words it.

**A job's brief** — a job with `trigger: claude` becomes an MCP prompt named for the job,
rendered verbatim. A scheduled task invokes the prompt instead of carrying a copy of the
brief that drifts from the file, and the job appears in any client's prompt picker for
nothing. A `trigger: schedule` job's body is documentation; nothing serves it.

**Nothing that did not load.** A tool whose connector has no credential is skipped by the
loader and never reaches the roster. A tool that appeared anyway would be one Claude picks,
and the failure would read as a broken tool rather than a missing password. `/health` still
says what was skipped and why — see [capabilities.md](capabilities.md).

A tool folder with a `TOOL.md` and no `tool.py` is refused for the same reason: there is
nothing behind it to call.

## Most tools are not in the list

The tool list is sent to the model on **every** request, so a tool sitting in it unused is
rent, paid forever. Only tools declaring `always_load: true` start in the list. Everything
else is found on demand:

```
harry_find_tools("note")
→ { "found": [{"name": "notes_search", "description": "Find a note by a word in its title or its text"}],
    "note": "Added 1 tool(s) to your list. They stay there until Harry restarts." }
```

**The rule, in one sentence:** a tool matches when the query, lowercased, appears anywhere in
its name, its namespace or its body. Substring, case-insensitive, no stemming and no
ranking. Results come back in name order, capped at `limit` — 10 by default, 50 at most —
and a capped answer says to search more narrowly.

That is deliberately a rule and not a relevance score. A score is an opinion, and opinions
belong on Claude's side of the boundary.

Harry has two tools of its own and both are always in the list. The other is
`harry_mark_done`, which a job's brief asks you to call when the work is done — Harry has no
other way of knowing it happened, and without it the deadline watchdog reports a miss about
work you actually did. See [jobs.md](jobs.md).

`harry_find_tools` is always in the list too. A list with nothing in it is
rejected outright by the API, so the one tool that can never be deferred is not one anybody
can delete.

**A reveal is server-wide and lasts until Harry restarts.** Not per conversation: FastMCP
4.0.3 hands out a fresh session id on every request, on every transport, so there is nothing
to key a per-conversation list on. This is a disclosure change rather than a permission one
— everyone who can reach Harry is already allowed every tool — so what one person's search
costs everybody is a few hundred tokens of list, not access. Per-person permissions will
need a stable session, and this is the paragraph to come back to.

## When something goes wrong

| What happened | What the caller gets |
|---|---|
| No `Authorization` header | 401. Nothing is listed and nothing runs |
| A token that is not the configured one | 401. A wrong token is not a quieter version of the right one |
| `HARRY_API_TOKEN` unset | 401 for everybody, owner included |
| A tool raises | An error carrying the tool's name and the exception's own message. No traceback, no file path, no line number. Every other tool still works |

**Steering text is the tool's job.** `ValueError('no articles since 05:00, try
since=yesterday')` reaches Claude as exactly that sentence. The only thing that knows what to
try instead is the tool that failed, so Harry carries the sentence through and adds nothing.

**A tool that blocks** is not handled here. A client aborts a silent call at 300 seconds;
progress notifications reset that clock, and `scripts/mcp_probe.py` has the pattern
(`sleep_reporting` — 660 seconds, reporting every 30, returns). It belongs to the first tool
that blocks rather than to the transport.

**Nothing here reaches Slack.** A refused token and a failing tool are both answered inside
the call, to the caller. Alerting is its own feature.

## A tool that knows who is asking

A tool function may declare a `principal` parameter:

```python
def register(registry: Registry, context: Context) -> None:
    @registry.tool
    def account_whoami(principal: Principal) -> dict:
        return {'id': principal.id, 'name': principal.name}
```

Harry fills it in from the bearer token the request carried, and **removes it from the
schema** so the caller never sees a field it could get wrong. A principal the caller could
pass would be a caller claiming to be somebody, which is worth nothing.

One token and one person today. The parameter exists so that a second is a token rather than
a change to every tool signature.

## Checking it from the outside

```bash
make probe ARGS="call --ping"     # can a client reach Harry at all
curl -s localhost:7430/health | jq # what loaded, and what did not
```

`make probe` answers reachability without needing any of Harry's own tools to work — see
[operating.md](operating.md).
