# `.harry/` — what Harry can do

> A **connector** is somewhere Harry can reach.
> A **tool** is something Claude can ask for.
> A **job** is something Harry does on its own.

Decided in
[ADR-260912-399f07](../project/decisions/ADR-260912-399f07-capabilities-are-folders-under-harry-connectors-tools-and-jo.md).
Laid out like `.claude/skills/`, so if you have used Claude Code you already read this.

```
.harry/
├── connectors/<name>/CONNECTOR.md   + .env, .env.local, and the code that reaches it
├── tools/<name>/TOOL.md             + the function it calls
└── jobs/<name>/JOB.md               + the scripts it runs
```

**A capability carries its own settings.** `.env` beside the declaration is committed and
**generated** — `make env-template` writes it from the `config:` block, so the description
beside each key cannot drift from the schema. `.env.local` beside it is yours and is
gitignored. You never edit `.env`.

**Keys are bare.** `APP_PASSWORD`, not `HARRY_ICLOUD_APP_PASSWORD` — the folder is the
namespace, so two connectors cannot collide. The prefixed spelling survives as the
*environment override*, which is how a container injects one; the generated file names it
beside every key.

Each of those is one **implementation** of a capability. Core defines the kinds; a fourth
kind is a core change, deliberately, because a kind is a contract.

## The two rules that make this work

**Frontmatter is what Harry does.** Machine-readable and executed: the trigger, the
schedule, the deadline, the connectors required.

**The body is what Claude is told.** Harry stores it and serves it verbatim. It never
parses it, templates it, or branches on it — that would be reasoning, and Harry does not
reason. A job with no mind in the loop has a body that is documentation and nothing serves
it; `trigger:` says which kind it is.

Everything here is validated by `scripts/check_capabilities.py`, which `make lint` runs. A
malformed header fails at the gate rather than at 06:30.

## The code beside it

One file, named after the kind — `connector.py`, `tool.py`, `job.py` — with one function:

```python
from harry.sdk import Context, Registry


def register(registry: Registry, context: Context) -> None:
    registry.connector(Forecast(context.config['place']))
```

`registry` has three methods, `connector()`, `tool()` and `job()`, and **none of them takes
a name**: the name, the description and the annotations are in the declaration Harry has
already read. Each returns what you passed, so `@registry.tool` over the function works.

`context` carries `name`, `kind`, `folder`, `declaration`, `body`, `config`,
`config_for(principal)`, `log` — and `connectors`, which is what your `requires:` and
`optional:` named, as
the objects those connectors registered. **That is how you use another capability: you
declare it and it is handed to you.** You never import one.

**Only `harry.sdk` may be imported.** Reaching for `harry.scheduler`, `harry.store`,
`harry.mcp`, `harry.main` — or bare `harry` — is refused before your module runs. Files
beside the entry module are read by that check too, and relative imports between them are
fine: a capability is a folder, and the client usually lives in a second file.

**A folder with no Python is a whole capability.** That is how a `trigger: claude` job is
one markdown file.

Every capability loads inside its own try/except, so a half-written one is logged, skipped,
and listed in `/health` with the reason. The rest come up. See
[docs/capabilities.md](../docs/capabilities.md).

## A job

`.harry/jobs/morning-page/JOB.md`

```markdown
---
name: morning-page
description: The day's weather, agenda and a few full articles, on the tablet by 07:00
trigger: claude                 # claude | schedule
deadline: "07:00"               # the watchdog alerts if it has not finished by then
timezone: Europe/Brussels
requires: [remarkable, icloud, news]
enabled: true
---

Ask Harry for today's candidates. Read the headlines and summaries, and pick the six to
eight that matter to me — I care about Belgian politics, monetary policy and anything
about how people actually use these tools.

Write a two-sentence intro in your own words, then call `build_digest` with your picks.
Skip anything that is the same story from a second source.
```

`trigger: claude` means Harry does not fire this. A Claude scheduled task does, at a time
it owns, and asks Harry for the brief above. Harry supplies the text and the facts; Claude
supplies the judgement. That boundary is
[ADR-260912-bd36c2](../project/decisions/ADR-260912-bd36c2-harry-never-calls-a-model.md).

**A `trigger: claude` job's body is published as an MCP prompt** named for the job. The
scheduled task invokes the prompt rather than calling a tool to fetch text, and the job
shows up in any MCP client's prompt picker for free — that is what prompts are for in the
protocol, so Harry does not build a second mechanism for it.

A heuristic job looks like this instead — `trigger: schedule`, and nothing reads the body:

```markdown
---
name: refresh-feeds
description: Re-fetch every configured feed, so the morning ask is instant
trigger: schedule
schedule: "0 5 * * *"
timezone: Europe/Brussels
requires: [news]
enabled: true
---

Runs an hour before the page is built. Failures are not alerted on their own — a stale
cache shows up as a feed marked unavailable on the page, which is already reported.
```

## A tool

`.harry/tools/digest_list_candidates/TOOL.md`

```markdown
---
name: digest_list_candidates          # <namespace>_<verb>, underscores only
namespace: digest
description: Today's weather, agenda and headlines, as a menu to choose from
requires: [news, icloud]
always_load: true                     # the exception — most tools defer
annotations:
  readOnlyHint: true                  # required: it is how a client knows what to gate
  idempotentHint: true
enabled: true
---

Returns everything today could contain: the weather, the day's agenda, and up to 40
headlines with their summaries and ids. Nothing is chosen for you — pick the six to eight
that matter and pass their ids to `digest_build`. Reach for this first, every morning.
```

**The body is the MCP description** — the text Claude reads to decide whether to call this
tool. Small refinements to it move selection accuracy more than almost anything else you
can change, which makes it the highest-leverage prose in the repo.

**The input schema is not declared.** It comes from the typed Python signature, the way
FastMCP already does it. Declaring it here too would be a second copy of what the code
knows, and the two would drift.

Why `digest_list_candidates` and `digest_build` are two tools rather than one with a mode
argument — and the rule for when to merge instead —
is [.claude/rules/tool-design.md](../.claude/rules/tool-design.md).

## A connector

`.harry/connectors/tijd/CONNECTOR.md`

```markdown
---
name: tijd
description: De Tijd's articles, read the way a subscriber reads them — in a logged-in browser
provides: []                    # nobody asks for "log in to De Tijd"; news_article returns the text
expires: session                # never | manual | session
enabled: true
config:
  email:
    description: The email address the De Tijd subscription signs in with.
    required: true
    secret: true
  password:
    description: That account's De Tijd password.
    required: true
    secret: true
  session_dir:
    description: Where the logged-in session is saved. On the data volume and nowhere else.
    default: /data/tijd
---

De Tijd's articles, in full … **Harry logs in by itself** whenever the saved session has
lapsed …

## When it goes wrong

| What reaches Slack | What happened | What to do |
…
```

The renewal procedure lives here, beside the code it is about, rather than in a
documentation page somebody has to remember exists. `expires:` is what tells Harry to watch
the credential at all.

**`provides:` is where the choice to expose something is written down**, and `make lint`
checks it both ways: a name in the list must be a tool that exists, and a tool namespaced
after a connector must appear in that connector's list. A tool composed from several
connectors is namespaced after none of them and is nobody's to offer.

Precedence for one setting, highest first:

1. `HARRY_<NAME>_<KEY>` in the environment — a container injecting
2. `.env.local` in this folder — your machine
3. `.env` in this folder — committed, generated
4. the `default:` in the declaration

An empty value in a file means *unset*, not *empty* — otherwise the generated file, which
leaves every secret blank, would wipe out the defaults it was generated from.

## Adding one

```
/new-job <what it does>              # a markdown file, no Python needed
/new-tool <the verb Claude can ask for>
/new-connector <what it reaches>     # a folder, its credential, and its runbook
```
