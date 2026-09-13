# Harry — working in this repo

**Claude thinks. Harry does.** Harry is a service on a NUC that Claude works with. It
holds the credentials, runs the browsers, renders the documents, talks to the tablet and
to Slack. Claude decides what should happen; Harry makes it happen.

Named after Harry Nyquist, Claude Shannon's collaborator at Bell Labs.

Everything Harry can do lives in [.harry/](.harry/), in three kinds:

> A **connector** is somewhere Harry can reach.
> A **tool** is something Claude can ask for.
> A **job** is something Harry does on its own.

Each folder under those is one **implementation** of a capability. Core provides the
registry, the MCP server, the scheduler, the store and the HTTP app, and nothing else.
Adding a connector or a tool is one folder; adding a job is one markdown file with no
Python at all. None of them is ever a core change.

**If Harry can read it, Claude can ask for it.** Every read path a connector has becomes
a tool unless there is a stated reason it should not, and "no job needs it yet" is not one.
Harry holding an iCloud credential while *"what's on my calendar?"* returns nothing is reach
thrown away. Jobs are one consumer of a connector, not its reason for existing. Deferral is
what makes that affordable. See
[ADR-260913-63991e](project/decisions/ADR-260913-63991e-if-harry-can-read-it-claude-can-ask-for-it.md).

**The tool surface is where Harry's value crosses**, so its shape is governed:
`<namespace>_<verb>`, one verb each, most of them deferred, and the body of every `TOOL.md`
is the description Claude reads to choose. See
[.claude/rules/tool-design.md](.claude/rules/tool-design.md) and
[ADR-260912-b22e46](project/decisions/ADR-260912-b22e46-tools-are-one-verb-each-namespaced-by-owner-and-lean-on-mcp-.md).

A `PreToolUse` hook guards the paths that must not change casually, so you do not need
to memorise which ones — the hook will tell you.

## Commands

```bash
make env-install      # install the workspace and the dev tools
make check            # THE GATE: format, lint, typecheck, covered tests
make test             # tests only, no coverage floor
make serve            # run Harry natively on 7430
make board            # list the board
make lanes            # what is in flight, and what collides
make lessons Q="…"    # search lessons learned before starting anything
make spike S=…        # run a Phase 0 spike from scratch/
make digest-dry       # build the morning page to out/digest.pdf without pushing
```

**Prefer `make` targets over bare commands.** They encode the right interpreter, the
right flags, and the lock the gate needs.

Configuration is two files: **`.env` is committed** and carries every key with its
working default; **`.env.local`** is gitignored, holds the secrets and whatever differs
on this machine, and wins key by key. The Makefile loads neither — `harry/config.py` is
the only reader, which is what keeps that order true. See
[.claude/rules/secrets-and-config.md](.claude/rules/secrets-and-config.md).

**There is no CI, by choice.** Nothing runs on a push, so `make check` before you finish
is the only thing between a change and `main`. `make check` takes a lock: if a second
session is running the gate, wait for it rather than halving each other's speed and
producing failures neither can reproduce alone.

## Core principles

The standard every change is held to, and the name every review finding cites.

- **Heuristic** *(over reasoning)* — **Harry never calls a model.** Claude has the LLM;
  Harry performs heuristic work only. Every action Harry takes is a rule that can be
  written down in advance: fetch this feed, extract this text, render this page, push this
  file, retry twice, alert on the third. Where judgement is needed, Claude supplies it
  through an MCP call. Harry holds no `ANTHROPIC_API_KEY`, ships no Claude Code CLI, and
  has no code path that reaches a model provider. See
  [.claude/rules/no-model-calls.md](.claude/rules/no-model-calls.md) and
  [ADR-260912-bd36c2](project/decisions/ADR-260912-bd36c2-harry-never-calls-a-model.md).
- **Modular** *(over monolithic)* — a capability is a folder with a declaration and a `register`
  function, discovered at start-up. **Every capability loads inside its own try/except:
  one broken connector is logged and skipped, the rest come up.** Capabilities import
  `harry.sdk` and never reach into core. See
  [.claude/rules/capability-shape.md](.claude/rules/capability-shape.md).
- **Degrading** *(over all-or-nothing)* — every section of the morning page fails on its
  own. A dead feed prints "unavailable" and the rest renders. De Tijd's login expiring
  costs you full article text for that source, not the page. See
  [.claude/rules/external-sources.md](.claude/rules/external-sources.md).
- **Alerting** *(over silent)* — a degraded source, a lapsed credential, a push that
  failed twice: it reaches Slack. A fire-and-forget job on a reverse-engineered protocol
  fails silently and you find out in three weeks. reMarkable broke every write in August
  2026 and needed a patched client — that is the shape of failure to design for.
- **Bounded** *(over trusting)* — three secrets here are all-or-nothing. The reMarkable
  device token grants complete read and write access to every document on the tablet,
  with no scopes. The iCloud app password gives full calendar access. The De Tijd storage
  state is a live logged-in session. All three live only in the NUC's `.env.local` and
  the data volume — never in the committed `.env`. See
  [.claude/rules/secrets-and-config.md](.claude/rules/secrets-and-config.md).
- **Explainable** *(over clever)* — the morning page is read at arm's length over coffee
  by someone who is not debugging it. So is every Slack message Harry sends.

## Shape of the thing

| Piece | Owns | Never does |
|---|---|---|
| `harry.registry` | The contract: `connector`, `tool`, `job`, `route`, `slack_action`, `on` | Know what any individual capability does |
| `harry.mcp` | FastMCP at `/mcp`, bearer auth | Implement a tool |
| `harry.scheduler` | APScheduler, and the deadline watchdog | Decide what a job does |
| `harry.store` | SQLite and files under `/data` | Reach the network |
| `harry.sdk` | What a capability is allowed to import | Import a capability |
| `.harry/connectors/*` | One external thing each: its credential, its client, its runbook | Import another capability, or `harry.core.*` |
| | **Every read path it has becomes a tool** — see below | Keep data to itself because no job wants it yet |
| `.harry/tools/*` | One verb each — the MCP surface Claude calls | Choose, rank or summarise; that is judgement |
| `.harry/jobs/*` | One trigger each, composing tools | Reimplement what a tool already does |

There is no `section` in the registry. A page is assembled by the job that produces it —
the morning page is one job among many, not the shape of the product.

**A Claude scheduled task owns the clock.** At 06:30 it calls `list_candidates()`,
reads the weather, the calendar and ~40 headlines, decides what matters, and calls
`build_digest()` with its choices and an intro it wrote. Harry fetches the chosen
articles, renders the page and pushes it to the tablet.

Harry keeps a scheduler, and that is not a contradiction — its jobs are the heuristic
ones. Refresh a cache. Retry a failed push. Check whether a credential still works. And
notice at 07:00 that no digest was built today, and say so in Slack.

**That last job is load-bearing.** An external trigger cannot report its own absence: a
scheduled task that never fires produces silence, and silence looks exactly like a morning
you did not check. The watchdog is the only thing that tells the difference, so it ships
with the first digest feature rather than later.

## When performing code changes

- Work is tracked on the in-repo board under [project/](project/). Open with
  `/new-feature`, close with `/finish-feature`. Conventions live in
  [project/CLAUDE.md](project/CLAUDE.md).
- **Most work takes the story track** — a feature stub, its criteria, one story, no
  requirements page. The full track is for a module boundary, a credential, a new
  external dependency, or anything you would want an ADR for. `project/CLAUDE.md` has
  the test.
- Query the lessons first: `make lessons Q="<topic>"`. It is step 1 of `/new-feature`
  for a reason.
- Declare what a feature `touches:` before starting it. `board.py start` refuses a
  feature that overlaps something already in flight, and `make lanes` shows why.
  **Three features in flight at once is the cap.** Past three you cannot hold the
  collisions in your head.
- Enforceable constraints live in [.claude/rules/](.claude/rules/) — one concept per
  file, some scoped by path. Read the ones that match what you are touching.
- Docs live in [docs/](docs/) and ship with the change, not after it.
- Never ask the user what reading the code can answer.

## Subagents and skills

Skills (`/new-feature`, `/new-story`, `/new-adr`, `/finish-feature`, `/new-connector`,
`/new-tool`, `/new-job`, `/spike`) are procedures. Subagents (`plan-verifier`, `pre-close-verifier`,
`code-reviewer`) are fresh-context verifiers.

**Delegate file-heavy investigation to these rather than reading in the main context.**

## Testing what Harry talks to

Harry's dependencies are feeds, a bot-blocked newspaper, a reverse-engineered tablet
API and Apple's flakiest protocol. **Feed and article parsing is tested against recorded
fixtures in `tests/fixtures/`, never a live URL** — a suite that reaches the network is
a suite that fails on a train. The tests that do reach out are marked `live` and are
never part of the gate: `make test-live` runs them deliberately.

## Writing

Harry's output is read by a person with coffee, and its board is read by someone who was
not in the session that opened it. Short sentences, one idea each. Lead with the answer.
Define a technical term the first time, in the same sentence, once. The full standard is
in [project/CLAUDE.md](project/CLAUDE.md) § Writing, and it applies to the board, to
docs, and to every word Harry puts on a page or into Slack.
