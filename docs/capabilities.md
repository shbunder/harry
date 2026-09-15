# Capabilities: how Harry finds what it can do

Everything Harry can do is a folder somebody dropped in. Nothing in Harry's core knows any
of their names — adding one is a folder, never a core change.

```
.harry/
├── connectors/<name>/CONNECTOR.md  + connector.py  + .env, .env.local
├── tools/<name>/TOOL.md            + tool.py
└── jobs/<name>/JOB.md              + job.py, or nothing at all
```

## What happens at start-up

1. **Look.** Three places, in this order, and **a later one replaces an earlier capability
   of the same name**: the package's own `capabilities/` (empty today), `.harry/` in the
   working directory, then `$HARRY_CAPABILITIES_DIR` when it is set. Replacing is how you
   swap a connector out without forking anything, and it is said out loud in the log and in
   `/health` rather than done quietly.
2. **Read.** The declaration's frontmatter is what Harry does with it. The body is what
   Claude is told — stored and served exactly as written, never parsed.
3. **Check.** Is it enabled? Does its name match its folder? Are its required settings
   set? Do the connectors it names in `requires:` exist and work? Does its code reach past
   `harry.sdk`?
4. **Run.** Import `connector.py` / `tool.py` / `job.py`, if there is one, and call its
   `register`.

Connectors go first, so a tool that needs one can be told its connector is missing.

**Every capability loads inside its own try/except.** One that is half-written is logged
and stepped over; the rest come up. That is the property that makes it safe to leave an
unfinished folder on disk, and it is what lets you develop here at all.

## The code a capability writes

One file, named after its kind, with one function:

```python
# .harry/connectors/weather/connector.py
from harry.sdk import Context, Registry


class Forecast:
    def __init__(self, place: str) -> None:
        self.place = place


def register(registry: Registry, context: Context) -> None:
    registry.connector(Forecast(context.config['place']))
```

`registry` has three methods — `connector()`, `tool()` and `job()` — and none of them takes
a name. The name, the description and the annotations are in the declaration Harry has
already read: **the declaration is the metadata, the Python is the behaviour.** Each
returns what you passed, so it reads as a decorator:

```python
# .harry/tools/weather_forecast/tool.py
def register(registry: Registry, context: Context) -> None:
    @registry.tool
    def weather_forecast(day: str = 'today') -> dict:
        return {'day': day, 'summary': 'grey, as ever'}
```

**`requires:` or `optional:` — one question decides it.** *If this connector is missing, is
there still something worth doing?* Answer **no** and it goes in `requires:`: the capability
is skipped, loudly, with a reason. Answer **yes** and it goes in `optional:`: the capability
loads, and the name is simply not in `connectors`. The morning page is why both exist — a
lapsed calendar password costs the agenda column, not the page. A connector in neither list
is never handed over at all.

`connectors` is the other half of those two lists. Declare what you need and it is handed to
you — you never import another capability, because two folders that import each other are
two folders that cannot be swapped:

```python
def register(registry: Registry, context: Context) -> None:
    slack = context.connectors['slack']
```

You get exactly what you declared. A connector that did not load, or that registered
nothing to hand over, means this capability is skipped at start-up with the reason — rather
than failing on its first call.

`alert()` is the other half of alerting: `registry.alerts()` below offers somewhere alerts
*go*, and this is how a capability raises one. **`log` is for whoever is reading the log;
`alert` is for whoever is not.** See [alerting.md](alerting.md).

A capability may also take on a **role** alongside its kind. There is one today:
`registry.alerts(fn)` offers this capability as somewhere Harry can report a fault, and it
does not use up the folder's one implementation — see [alerting.md](alerting.md).

`context` is what the capability is told about itself:

| Field | What it is |
|---|---|
| `name`, `kind` | `weather`, `connector` |
| `folder` | Where it lives, wherever that is |
| `declaration` | The frontmatter, as a mapping |
| `body` | The declaration's body, verbatim |
| `config` | Its settings, resolved |
| `config_for(principal)` | The same settings for one person — the NUC serves more than one |
| `connectors` | What `requires:` and `optional:` named, as the objects those connectors registered. An optional one that did not load is absent — ask `'icloud' in connectors` |
| `log` | A logger named for this capability |
| `alert(message, key)` | Say something went wrong, to whoever is *not* reading the log |

**Only `harry.sdk` may be imported.** Reaching for `harry.scheduler`, `harry.store`,
`harry.mcp` or `harry.main` — or `harry` itself — is refused *before* the module runs, so a
forbidden import never takes effect. Files beside the entry module are read too, and
relative imports between them are fine: a capability is a folder, and its client usually
lives in a second file.

A folder with **no Python at all** is a whole capability for a connector or a job. That is
how a `trigger: claude` job is one markdown file: Claude runs the half that needs a mind.

**A tool is the exception.** A tool with nothing behind it is one Claude will pick and then
fail on, and that failure reads as a broken tool rather than an unfinished folder — so the
loader refuses it. What happens to a tool once it has loaded is [mcp.md](mcp.md).

## What it takes to be skipped

Each of these costs exactly that one capability, and each one's reason appears in
`/health`:

| What is wrong | The reason you get |
|---|---|
| No `CONNECTOR.md` in the folder | `no CONNECTOR.md, so nothing here is loaded` |
| Frontmatter that will not parse | `the frontmatter block is never closed with ---` |
| `name:` disagrees with the folder | `its declaration is named 'x' but the folder is 'y'` |
| `enabled: false` | `disabled in its declaration` |
| A `required: true` setting with no value | `required setting app_password is not set` |
| A connector in `requires:` that did not load | `needs icloud, which did not load` |
| A connector in `optional:` that did not load | nothing — the capability loads, and the name is not in `connectors` |
| An import that reaches past the SDK | `reaches past harry.sdk — connector.py:9 imports harry.scheduler` |
| `register` missing from the module | `connector.py has no register(registry, context)` |
| A **tool** with no `tool.py` beside it | `no tool.py, so there is nothing for this tool to call` |
| Anything the code raises | `ModuleNotFoundError: No module named 'caldav'` |

Any value the capability declared `secret: true` is replaced with `[redacted]` in every
reason and every log line before it goes anywhere. Exception messages written in a hurry
are exactly where a credential ends up.

## Asking what loaded

```bash
curl -s localhost:7430/health | jq
```

```json
{
  "status": "ok",
  "roots": ["/app/.harry"],
  "loaded": 4,
  "skipped": 1,
  "capabilities": [
    {"name": "weather", "kind": "connector", "status": "loaded", "root": "/app/.harry"},
    {"name": "icloud", "kind": "connector", "status": "skipped", "root": "/app/.harry",
     "reason": "required setting app_password is not set"}
  ]
}
```

**A skipped capability is not an error status.** Harry running with four of five is Harry
running, so this stays 200 — returning 503 would train you to ignore the number, and then
the one that matters goes unread too. The response says which one is missing and why;
whether that matters is your call.

No setting values appear here, secret or otherwise. This says what is running; a
configuration dump is a different thing with a different audience.

A capability that was replaced by one of the same name in a later root shows as skipped
with `shadowed_by` naming what took over. That is the answer to "why did my edit have no
effect", and it is here rather than only in a log line from a restart three weeks ago.

## Settings

One key, in the root `.env`:

| Key | Default | What it does |
|---|---|---|
| `HARRY_CAPABILITIES_DIR` | empty | A directory of capabilities outside this repository, loaded last, so it can replace anything in `.harry/` |
| `HARRY_LOG_LEVEL` | `INFO` | At `INFO` every capability that loads says so at start-up. A skip is a WARNING and appears at any level |

Empty means unset. A capability's own settings live in its own folder, not here — see
[operating.md](operating.md) for the layering and `.harry/README.md` for the key names.

## When it is the loader that breaks

- **No `.harry/` at all** — Harry starts with nothing and says `no capabilities found`
  in the log. A fresh install is not an error.
- **A root that does not exist** — skipped. The bundled directory is empty today and
  `HARRY_CAPABILITIES_DIR` is usually unset.
- **A capability that hangs on import** — not handled, deliberately. A timeout around
  every import is machinery for a case nobody has hit; if it happens, `/health` never
  answers, which is a visible failure rather than a silent one.

**Nothing here reaches Slack yet.** A start-up failure is in `/health` and in the logs on
the machine somebody has just restarted, which is enough until the alerting feature lands.
After that, a capability skipped three weeks ago will say so; today it looks exactly like
one that was never installed.

Harry restarts to pick up a change. There is no reload.
