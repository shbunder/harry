# Harry

**Claude thinks. Harry does.**

Harry is a service that runs on a NUC, on 24/7. It holds the credentials, runs the
browsers, renders the documents, talks to the reMarkable tablet and to Slack. Claude
decides what should happen; Harry makes it happen.

Named after Harry Nyquist, Claude Shannon's collaborator at Bell Labs.

Two things it exists for:

1. **A morning page on the reMarkable Paper Pro** at 06:30 — weather in Leuven, the day's
   calendar and to-dos, and the **full text** of a handful of articles Claude picked from
   VRT NWS, De Tijd and the BBC. Not headlines: pages.
2. **A Slack loop for Claude Code** — a session that needs a decision calls `ask_human()`,
   Harry posts it to Slack and holds the call open, your answer comes back as the tool
   result and the session carries on mid-turn.

Every capability is a module: one directory, one `register` function, no core change.

## Getting started

```bash
make env-install          # install the workspace and the dev tools
make browser              # the Chromium that tier-2 article fetching drives
make check                # the gate
make serve                # Harry on http://localhost:7430
```

Configuration is two files. **`.env` is committed** and lists every key with its working
default — you do not copy it. Create **`.env.local`** beside it and put in only the
secrets and whatever differs on this machine; it wins over `.env`, key by key. Details in
[.claude/rules/secrets-and-config.md](.claude/rules/secrets-and-config.md).

On macOS, WeasyPrint renders through pango: `brew install pango`.

## Working on it

```bash
make lanes                # what is in flight, and what collides
make board                # the board
make lessons Q="…"        # what past features learned
make spike S=…            # run a Phase 0 spike
```

Work is tracked on an in-repo board under [project/](project/). Open a feature with
`/new-feature`, close it with `/finish-feature`. The conventions are in
[project/CLAUDE.md](project/CLAUDE.md); how to work in this repo at all is in
[CLAUDE.md](CLAUDE.md).

Three features in flight at once is the cap. A feature declares what it `touches:` and the
board refuses two live features that name the same area.

## What runs where

| Piece | Where | Does what |
|---|---|---|
| Harry | NUC, Docker, port 7430 | Fetches, renders, pushes, retries, alerts. Never calls a model. |
| The 06:30 trigger | A Claude scheduled task | Asks for candidates, decides what matters, asks for the page |
| Claude Code on the Mac | Over the tunnel | Ad-hoc: "put this on my tablet", "what's in flight?" |

**Claude has the LLM; Harry performs heuristic work only.** That one line decides where
every capability belongs, and it is why Harry holds no provider key, ships no model CLI,
and mounts nothing of yours. See
[ADR-260912-bd36c2](project/decisions/ADR-260912-bd36c2-harry-never-calls-a-model.md).

Harry still has its own jobs — refresh a cache, retry a push, check a credential, and
notice at 07:00 that no page was built today. That last one matters more than it looks: an
external trigger cannot report its own absence.

## Three credentials that deserve care

The **reMarkable device token** grants complete read and write access to every document on
the tablet — no scopes, no read-only mode. The **iCloud app-specific password** gives full
calendar access. The **De Tijd password** can change the account as well as read it, and the
session Harry saves with it is a live login.

All three live only on the NUC, each in its own connector's `.env.local`, and the De Tijd
session on the data volume — never in `.env`, which is committed. Harry renews the De Tijd
session by itself, and says in Slack when any of them stops working — see
[docs/operating.md](docs/operating.md).
